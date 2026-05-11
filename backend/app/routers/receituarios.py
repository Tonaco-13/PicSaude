"""
routers/receituarios.py
=======================
Ticket 15 — Geração de receituários regulatórios a partir de uma prescrição
(RDC Anvisa 1.000/2025 + Portaria SVS/MS 344/1998).

Endpoint
--------
POST /prescricoes/{protocolo}/receituarios/gerar

Comportamento
-------------
- Autorização: role `prescritor`. O CNS do token deve ser o do prescritor
  que emitiu a prescrição original (nenhum outro prescritor pode derivar
  receituários de uma prescrição alheia).
- Busca a prescrição por `protocolo` + carrega itens.
- Usa `domain/motor_regulatorio` para agrupar itens em N receituários
  e validar se a assinatura da prescrição atende ao nível exigido por
  cada grupo.
- Idempotência: se já existem receituários ativos para esta prescrição
  **cobrindo exatamente** os mesmos itens, retorna os existentes sem
  duplicar. Caso contrário, marca os anteriores como substituídos
  (`substituido_em = now`) e gera um conjunto novo.
- Registra evento imutável `receituarios_gerados` no ledger
  `prescricao_eventos`.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.adapters.sncr_factory import get_sncr_adapter
from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.catalogo_regulatorio import validar_itens_prescricao
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn
from app.domain.motor_regulatorio import (
    Receituario as ReceituarioDTO,
    agrupar_por_receituario,
    validar_assinatura_para_receituario,
)
from app.domain.pdf_receituario import (
    gerar_pdf_receituario,
    tipo_abrev,
)
from app.domain.regras_receituario import (
    calcular_data_validade,
    validar_emissao_receituario,
)

router = APIRouter(prefix="/prescricoes", tags=["receituarios"])


# ---------------------------------------------------------------------------
# Helpers de acesso ao banco
# ---------------------------------------------------------------------------

def _row_to_dict(row: Any) -> dict:
    """Converte sqlite3.Row / _PgRow em dict previsível."""
    if row is None:
        return {}
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def _carregar_prescricao(conn, protocolo: str) -> dict:
    row = conn.execute(
        """
        SELECT p.id, p.protocolo, p.assinatura_modo, p.assinatura_hash,
               p.tipo_emissao, p.status, pr.cns AS prescritor_cns
          FROM prescricoes p
          JOIN prescritores pr ON pr.id = p.prescritor_id
         WHERE p.protocolo = ?
        """,
        (protocolo,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Prescrição não encontrada.")
    return _row_to_dict(row)


def _carregar_itens(conn, prescricao_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, nome_medicamento, concentracao, quantidade,
               unidade_quantidade, forma_farmaceutica, posologia,
               status_item, classe_controle, tipo_retencao
          FROM prescricao_itens
         WHERE prescricao_id = ?
         ORDER BY id ASC
        """,
        (prescricao_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _receituarios_ativos_existentes(conn, prescricao_id: int) -> list[dict]:
    """Receituários com `substituido_em IS NULL` para a prescrição."""
    rows = conn.execute(
        """
        SELECT id, tipo_receituario, grupo_id, grupo_nome,
               assinatura_minima, assinatura_valida, vias,
               retencao_farmacia, requer_sncr, numeracao_sncr,
               status, created_at, numerado_em, emitido_em, adapter_usado,
               data_validade
          FROM receituarios
         WHERE prescricao_id = ?
           AND substituido_em IS NULL
         ORDER BY id ASC
        """,
        (prescricao_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _itens_de_receituario(conn, receituario_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT prescricao_item_id FROM receituario_itens WHERE receituario_id = ? ORDER BY id ASC",
        (receituario_id,),
    ).fetchall()
    return [_row_to_dict(r)["prescricao_item_id"] for r in rows]


def _coletar_itens_por_receituario_existente(
    conn, receituarios: list[dict]
) -> dict[int, set[int]]:
    return {
        r["id"]: set(_itens_de_receituario(conn, r["id"])) for r in receituarios
    }


def _snapshot_itens_novos(receituarios: list[ReceituarioDTO]) -> dict[str, set[int]]:
    """Mapa tipo_receituario → conjunto de prescricao_item_id."""
    return {
        r.tipo: {int(item["id"]) for item in r.itens} for r in receituarios
    }


def _snapshot_itens_existentes(
    conn, receituarios_existentes: list[dict]
) -> dict[str, set[int]]:
    by_type: dict[str, set[int]] = {}
    for rec in receituarios_existentes:
        ids = set(_itens_de_receituario(conn, rec["id"]))
        by_type[rec["tipo_receituario"]] = ids
    return by_type


def _serializar_receituario_db(rec: dict) -> dict:
    return {
        "id":                 rec["id"],
        "tipo":               rec["tipo_receituario"],
        "grupo_id":           rec["grupo_id"],
        "grupo_nome":         rec["grupo_nome"],
        "assinatura_minima":  rec["assinatura_minima"],
        "assinatura_valida":  bool(rec["assinatura_valida"]),
        "vias":               rec["vias"],
        "retencao_farmacia":  bool(rec["retencao_farmacia"]),
        "requer_sncr":        bool(rec["requer_sncr"]),
        "numeracao_sncr":     rec["numeracao_sncr"],
        "status":             rec["status"],
        "data_validade":      rec.get("data_validade").isoformat() if rec.get("data_validade") else None,
    }


# ---------------------------------------------------------------------------
# POST /prescricoes/{protocolo}/receituarios/gerar
# ---------------------------------------------------------------------------

@router.post(
    "/{protocolo}/receituarios/gerar",
    status_code=201,
    summary="Gera receituários regulatórios (RDC 1.000/2025) a partir da prescrição",
)
def gerar_receituarios(
    protocolo: str,
    usuario: dict = Depends(require_role("prescritor")),
):
    """Gera os N receituários regulatórios necessários para a prescrição.

    Ver módulo `app/domain/motor_regulatorio.py` para regras de agrupamento
    e validação de assinatura. Este endpoint apenas persiste o resultado
    e registra o evento de auditoria.
    """
    cns_token = usuario.get("sub") or ""
    agora = datetime.utcnow()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        # Reutilizado pelo evento principal e pelos N todo_regulatorio
        # do loop (invariante §6.3).
        instance_id = get_instance_id_conn(conn)

        # 1. Carregar prescrição e validar posse
        prescricao = _carregar_prescricao(conn, protocolo)
        if prescricao.get("prescritor_cns") != cns_token:
            raise HTTPException(
                status_code=403,
                detail="Somente o prescritor que emitiu a prescrição pode gerar receituários.",
            )

        # 2. Carregar itens
        itens = _carregar_itens(conn, prescricao["id"])
        if not itens:
            raise HTTPException(
                status_code=422,
                detail="Prescrição sem itens — nada a derivar.",
            )

        # 2a. Ticket 20 — validação cruzada com catálogo regulatório.
        # Alertas são informativos (fase 1 não bloqueia) e seguem com
        # a resposta tanto no caminho idempotente quanto no fresh.
        alertas_regulatorios = validar_itens_prescricao(itens, conn)
        alertas_resposta = [
            {
                "item_id":                a.item_id,
                "nome_medicamento":       a.nome_medicamento,
                "severidade":             a.severidade,
                "alerta":                 a.mensagem,
                "sugestao_classe":        a.sugestao_classe,
                "sugestao_tipo_retencao": a.sugestao_tipo_retencao,
            }
            for a in alertas_regulatorios
        ]

        # 3. Agrupar por receituário (motor regulatório)
        try:
            receituarios_dto = agrupar_por_receituario(prescricao, itens)
        except ValueError as exc:
            # Classe de controle desconhecida
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        if not receituarios_dto:
            raise HTTPException(
                status_code=422,
                detail="Motor regulatório não produziu nenhum receituário.",
            )

        # 4. Idempotência — se snapshot bate, retornar existentes
        existentes = _receituarios_ativos_existentes(conn, prescricao["id"])
        snap_novo = _snapshot_itens_novos(receituarios_dto)
        snap_existente = _snapshot_itens_existentes(conn, existentes)
        if snap_existente == snap_novo:
            # Nada a fazer — retornar o que já está no banco
            resposta_existente = [_serializar_receituario_db(r) for r in existentes]
            for rec, dto in zip(
                sorted(existentes, key=lambda r: r["tipo_receituario"]),
                sorted(receituarios_dto, key=lambda d: d.tipo),
            ):
                # Preenche itens retornados (para coerência com resposta fresca)
                rec_resp = next(
                    r for r in resposta_existente if r["id"] == rec["id"]
                )
                rec_resp["itens"] = [
                    {
                        "prescricao_item_id": it["id"],
                        "nome_medicamento":   it["nome_medicamento"],
                        "classe_controle":    it.get("classe_controle"),
                    }
                    for it in dto.itens
                ]
            return {
                "prescricao_protocolo":     protocolo,
                "receituarios":             resposta_existente,
                "total_receituarios":       len(resposta_existente),
                "todos_assinatura_valida":  all(
                    bool(r["assinatura_valida"]) for r in existentes
                ),
                "idempotente":              True,
                "alertas_regulatorios":     alertas_resposta,
            }

        # 5. Divergência — marcar antigos como substituídos e gerar novos.
        #    Postgres trata NULL como "não igual" em UNIQUE, então criar
        #    novos com substituido_em = NULL coexiste com antigos já
        #    marcados (substituido_em != NULL).
        if existentes:
            conn.execute(
                """
                UPDATE receituarios
                   SET substituido_em = ?
                 WHERE prescricao_id = ?
                   AND substituido_em IS NULL
                """,
                (agora, prescricao["id"]),
            )

        # 6. Persistir novos receituários + associações
        receituarios_persistidos: list[dict] = []
        for dto in receituarios_dto:
            validacao = validar_assinatura_para_receituario(prescricao, dto)
            # Ticket 19 — calcular data_validade a partir do tipo.
            # Para receita_retencao, extrair tipo_retencao dos itens.
            # Se houver tipos mistos (antimicrobiano + glp1), o fallback
            # conservador (10 dias) é usado automaticamente pela função.
            _tipo_ret: str | None = None
            if dto.tipo == "receita_retencao" and dto.itens:
                _tipos_ret = {
                    it.get("tipo_retencao")
                    for it in dto.itens
                    if it.get("tipo_retencao")
                }
                if len(_tipos_ret) == 1:
                    _tipo_ret = _tipos_ret.pop()
                # Se len > 1 (mistos), _tipo_ret fica None → fallback 10 dias
            data_validade = calcular_data_validade(
                agora, dto.tipo, tipo_retencao=_tipo_ret,
            )

            cur = conn.execute(
                """
                INSERT INTO receituarios
                    (prescricao_id, tipo_receituario, grupo_id, grupo_nome,
                     assinatura_minima, assinatura_valida, vias,
                     retencao_farmacia, requer_sncr, numeracao_sncr,
                     status, substituido_em, created_at, data_validade)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, 'gerado', NULL, ?, ?)
                """,
                (
                    prescricao["id"],
                    dto.tipo,
                    dto.grupo_id,
                    dto.grupo_nome,
                    dto.assinatura_minima,
                    validacao.valido,
                    dto.vias,
                    dto.retencao_farmacia,
                    dto.requer_sncr,
                    agora,
                    data_validade,
                ),
            )
            receituario_id = cur.lastrowid

            for it in dto.itens:
                conn.execute(
                    """
                    INSERT INTO receituario_itens
                        (receituario_id, prescricao_item_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (receituario_id, it["id"], agora),
                )

            receituarios_persistidos.append(
                {
                    "id":                 receituario_id,
                    "tipo":               dto.tipo,
                    "grupo_id":           dto.grupo_id,
                    "grupo_nome":         dto.grupo_nome,
                    "assinatura_minima":  dto.assinatura_minima,
                    "assinatura_valida":  validacao.valido,
                    "vias":               dto.vias,
                    "retencao_farmacia":  dto.retencao_farmacia,
                    "requer_sncr":        dto.requer_sncr,
                    "numeracao_sncr":     None,
                    "status":             "gerado",
                    "data_validade":      data_validade.isoformat() if data_validade else None,
                    "itens": [
                        {
                            "prescricao_item_id": it["id"],
                            "nome_medicamento":   it["nome_medicamento"],
                            "classe_controle":    it.get("classe_controle"),
                        }
                        for it in dto.itens
                    ],
                    "validacao_assinatura": {
                        "valido":           validacao.valido,
                        "nivel_exigido":    validacao.nivel_exigido,
                        "nivel_presente":   validacao.nivel_presente,
                        "motivo_rejeicao":  validacao.motivo_rejeicao,
                    },
                }
            )

        # 7. Registrar evento no ledger (imutável)
        ev_payload = {
            "quantidade": len(receituarios_persistidos),
            "tipos": [r["tipo"] for r in receituarios_persistidos],
            "itens_por_receituario": {
                r["tipo"]: [it["prescricao_item_id"] for it in r["itens"]]
                for r in receituarios_persistidos
            },
            "validacao_assinatura": {
                r["tipo"]: r["validacao_assinatura"]
                for r in receituarios_persistidos
            },
            "regenerado": bool(existentes),
            "ticket_referencia": "TICKET-15",
        }
        # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao["id"],
            tipo_evento="receituarios_gerados",
            instance_id=instance_id,
            payload=ev_payload,
            ator_tipo="prescritor",
            ator_id=cns_token,
        )

        # 8. Ticket 18 — TODO_REGULATORIO provisório para receita_retencao.
        #    Premissa atual: requer_sncr=False (RDC 471 não tem ferramenta
        #    SNCR para retenção definida hoje). Quando a Anvisa publicar
        #    integração para esse fluxo, reavaliar.
        for rec in receituarios_persistidos:
            if rec["tipo"] == "receita_retencao":
                todo = {
                    "receituario_id":   rec["id"],
                    "tipo_receituario": rec["tipo"],
                    "motivo":           "requer_sncr_retencao_provisorio",
                    "detalhe": (
                        "Confirmar se, quando a ferramenta SNCR para receitas "
                        "sujeitas à retenção (RDC 471/2021) estiver disponível, "
                        "haverá numeração SNCR no fluxo prescritor ou apenas "
                        "registro eletrônico de uso pela farmácia."
                    ),
                    "ticket_referencia": "TICKET-18",
                }
                # Ticket 4D.1: reutiliza instance_id da transação (invariante §6.3).
                registrar_evento_ledger(
                    conn,
                    objeto_tipo="prescricao",
                    objeto_id=prescricao["id"],
                    tipo_evento="todo_regulatorio",
                    instance_id=instance_id,
                    payload=todo,
                    ator_tipo="prescritor",
                    ator_id=cns_token,
                )

    return {
        "prescricao_protocolo":    protocolo,
        "receituarios":            receituarios_persistidos,
        "total_receituarios":      len(receituarios_persistidos),
        "todos_assinatura_valida": all(
            r["assinatura_valida"] for r in receituarios_persistidos
        ),
        "idempotente":             False,
        "alertas_regulatorios":    alertas_resposta,
    }


# ---------------------------------------------------------------------------
# Ticket 16A — POST /prescricoes/{protocolo}/receituarios/numerar
# ---------------------------------------------------------------------------
#
# Fluxo: gerar (Ticket 15) → numerar (Ticket 16A) → emitir (Ticket 17, futuro)
#
# Numerar = obter número de receituário do SNCR (RDC 1.000/2025).
# Hoje, o SNCR não tem API documentada publicamente — usamos um adapter
# pluggable (`app.adapters.sncr_factory`) com implementação stub. Quando
# a API real estiver disponível, troca-se o adapter via SNCR_ADAPTER=real.
#
# Receituários não-controlados (receita_simples / receita_comum) NÃO passam
# pelo SNCR. Para esses, o status final é "nao_requer_sncr" — semântica
# explícita de que a numeração SNCR não se aplica (em vez de "numerado",
# que implicaria que passou pelo SNCR).

# Mapeamento de status pós-numeração (em função do adapter)
_ADAPTER_PARA_STATUS_NUMERADO = {
    "stub": "numerado_stub",
    "real": "numerado",
}

# Tipos que NUNCA passam pelo SNCR — derivados do motor regulatório.
# - receita_simples / receita_comum: sem controle regulatório (Portaria 344)
# - receita_retencao (Ticket 18): RDC 471/2021 não tem ferramenta SNCR
#   definida hoje. requer_sncr=False é premissa provisória — TODO_REGULATORIO
#   é registrado pelo /gerar para reavaliação quando Anvisa publicar API.
_TIPOS_SEM_SNCR = frozenset({"receita_simples", "receita_comum", "receita_retencao"})


def _requer_sncr(tipo_receituario: str) -> bool:
    """Decisão local explícita — não inferir de outro campo.

    Mantém a regra única e auditável aqui em vez de espalhar `if`s pelo
    resto do código consumidor. Coerente com `motor_regulatorio.py`,
    onde `requer_sncr` é uma propriedade do grupo regulatório.
    """
    return tipo_receituario not in _TIPOS_SEM_SNCR


def _serializar_receituario_numerado(rec: dict, *, requer_sncr: bool) -> dict:
    return {
        "id":              rec["id"],
        "tipo":            rec["tipo_receituario"],
        "numeracao_sncr":  rec["numeracao_sncr"],
        "status":          rec["status"],
        "numerado_em":     rec["numerado_em"].isoformat() if rec.get("numerado_em") else None,
        "adapter_usado":   rec.get("adapter_usado"),
        "requer_sncr":     requer_sncr,
    }


@router.post(
    "/{protocolo}/receituarios/numerar",
    status_code=200,
    summary="Numera receituários gerados via SNCR (RDC 1.000/2025)",
)
def numerar_receituarios(
    protocolo: str,
    usuario: dict = Depends(require_role("prescritor")),
):
    """Atribui numeração SNCR aos receituários `gerado` da prescrição.

    Comportamento:
      - Receituários que requerem SNCR → adapter.requisitar_numeracao()
        e status → "numerado_stub" (com SNCRStub) ou "numerado" (com SNCRReal).
      - Receituários que NÃO requerem SNCR → status → "nao_requer_sncr",
        sem chamada ao adapter, numeracao_sncr permanece NULL.
      - Receituários já numerados são idempotentes (retornados como-estão).

    Validação de assinatura:
      Este endpoint NÃO valida criptograficamente a assinatura. Apenas
      consulta o nível declarado em `prescricao_assinatura` e, se
      insuficiente para o grupo, registra um evento "todo_regulatorio"
      (não bloqueia). A validação criptográfica real é responsabilidade
      do fluxo de emissão (Ticket 17).
    """
    cns_token = usuario.get("sub") or ""
    agora = datetime.utcnow()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        # Reutilizado pelo evento principal e pelos N todo_regulatorio
        # do loop (invariante §6.3).
        instance_id = get_instance_id_conn(conn)

        # 1. Carregar prescrição e validar posse
        prescricao = _carregar_prescricao(conn, protocolo)
        if prescricao.get("prescritor_cns") != cns_token:
            raise HTTPException(
                status_code=403,
                detail="Somente o prescritor que emitiu a prescrição pode numerar receituários.",
            )

        # 2. Carregar receituários ativos
        existentes = _receituarios_ativos_existentes(conn, prescricao["id"])
        if not existentes:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Nenhum receituário gerado para esta prescrição. "
                    "Chame POST /prescricoes/{protocolo}/receituarios/gerar primeiro."
                ),
            )

        # 3. Carregar nível de assinatura declarada (não-bloqueante)
        sig_row = conn.execute(
            """
            SELECT tipo_certificado
              FROM prescricao_assinatura
             WHERE prescricao_id = ?
            """,
            (prescricao["id"],),
        ).fetchone()
        tipo_certificado_declarado = (
            _row_to_dict(sig_row).get("tipo_certificado") if sig_row else None
        )

        # 4. Inicializar adapter
        adapter = get_sncr_adapter()
        nome_adapter = adapter.nome_adapter
        status_numerado = _ADAPTER_PARA_STATUS_NUMERADO.get(
            nome_adapter, "numerado"
        )

        # Identificador do prescritor para vincular numeração SNCR.
        # MVP: usamos o CNS (PicSaúde não armazena CPF do prescritor hoje).
        # Quando SNCRReal chegar (Ticket 16B), pode ser necessário ter CPF
        # real — Ticket 16B fará essa migração explicitamente.
        identificador_prescritor = cns_token

        # 5. Numerar cada receituário
        resultados: list[dict] = []
        eventos_todo: list[dict] = []
        numeracoes_emitidas: list[dict] = []
        mudancas: int = 0

        for rec in existentes:
            tipo = rec["tipo_receituario"]
            requer = _requer_sncr(tipo)

            # 5a. Idempotência — se já numerado (ou já marcado como
            # nao_requer_sncr), retornar como está.
            if rec["status"] in ("numerado", "numerado_stub", "nao_requer_sncr"):
                resultados.append(
                    _serializar_receituario_numerado(rec, requer_sncr=requer)
                )
                continue

            # 5b. Receituários que não passam pelo SNCR → status semântico próprio
            if not requer:
                conn.execute(
                    """
                    UPDATE receituarios
                       SET status = 'nao_requer_sncr',
                           numerado_em = ?,
                           adapter_usado = NULL
                     WHERE id = ?
                    """,
                    (agora, rec["id"]),
                )
                rec_atualizado = dict(rec)
                rec_atualizado.update({
                    "status": "nao_requer_sncr",
                    "numerado_em": agora,
                    "adapter_usado": None,
                })
                resultados.append(
                    _serializar_receituario_numerado(rec_atualizado, requer_sncr=False)
                )
                mudancas += 1
                continue

            # 5c. Receituário controlado — pedir numeração ao adapter
            res_lista = adapter.requisitar_numeracao(
                tipo_receituario=tipo,
                prescritor_cpf=identificador_prescritor,
                quantidade=1,
            )
            if not res_lista or not res_lista[0].sucesso:
                erro = res_lista[0] if res_lista else None
                detalhe = (erro.erro if erro else "Falha desconhecida no adapter SNCR")
                codigo = (erro.codigo_erro if erro else "SNCR_DESCONHECIDO")
                # Nada parcial é persistido — get_tx() faz rollback automático.
                raise HTTPException(
                    status_code=502,
                    detail={
                        "erro": "falha_numeracao_sncr",
                        "tipo_receituario": tipo,
                        "receituario_id": rec["id"],
                        "codigo_erro": codigo,
                        "mensagem": detalhe,
                        "adapter": nome_adapter,
                    },
                )

            numeracao = res_lista[0].dados
            assert numeracao is not None  # contrato: sucesso=True implica dados!=None

            conn.execute(
                """
                UPDATE receituarios
                   SET numeracao_sncr = ?,
                       status = ?,
                       numerado_em = ?,
                       adapter_usado = ?
                 WHERE id = ?
                """,
                (numeracao.numero, status_numerado, agora, nome_adapter, rec["id"]),
            )
            rec_atualizado = dict(rec)
            rec_atualizado.update({
                "numeracao_sncr": numeracao.numero,
                "status": status_numerado,
                "numerado_em": agora,
                "adapter_usado": nome_adapter,
            })
            resultados.append(
                _serializar_receituario_numerado(rec_atualizado, requer_sncr=True)
            )
            numeracoes_emitidas.append({
                "receituario_id": rec["id"],
                "tipo_receituario": tipo,
                "numeracao_sncr": numeracao.numero,
            })
            mudancas += 1

            # 5d. Validação informativa do nível de assinatura (não bloqueante).
            #     Compara o nível declarado pelo certificado com o exigido
            #     pelo grupo regulatório do receituário. Se insuficiente,
            #     registra evento "todo_regulatorio" no ledger.
            nivel_declarado = _certificado_para_nivel(tipo_certificado_declarado)
            nivel_exigido = rec["assinatura_minima"]
            if not _nivel_atende_minimo(nivel_declarado, nivel_exigido):
                eventos_todo.append({
                    "receituario_id": rec["id"],
                    "tipo_receituario": tipo,
                    "motivo": "nivel_assinatura_insuficiente",
                    "nivel_declarado": nivel_declarado,
                    "nivel_exigido": nivel_exigido,
                    "tipo_certificado_declarado": tipo_certificado_declarado,
                    "acao_necessaria": "validar_assinatura_antes_emissao",
                })

        # 6. Registrar eventos no ledger — apenas se houve mudança real,
        #    para preservar a invariante "ledger reflete fatos novos".
        if mudancas > 0:
            ev_payload = {
                "adapter": nome_adapter,
                "receituarios_numerados": len(numeracoes_emitidas),
                "numeracoes": numeracoes_emitidas,
                "ticket_referencia": "TICKET-16A",
            }
            # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=prescricao["id"],
                tipo_evento="receituarios_numerados",
                instance_id=instance_id,
                payload=ev_payload,
                ator_tipo="prescritor",
                ator_id=cns_token,
            )

            # Eventos TODO_REGULATORIO — um por receituário com pendência
            for todo in eventos_todo:
                # Ticket 4D.1: reutiliza instance_id da transação (invariante §6.3).
                registrar_evento_ledger(
                    conn,
                    objeto_tipo="prescricao",
                    objeto_id=prescricao["id"],
                    tipo_evento="todo_regulatorio",
                    instance_id=instance_id,
                    payload=todo,
                    ator_tipo="prescritor",
                    ator_id=cns_token,
                )

    return {
        "prescricao_protocolo":   protocolo,
        "adapter":                nome_adapter,
        "receituarios":           resultados,
        "total_numerados":        len(numeracoes_emitidas),
        "total_nao_requer_sncr":  sum(
            1 for r in resultados if r["status"] == "nao_requer_sncr"
        ),
        "idempotente":            mudancas == 0,
    }


# ---------------------------------------------------------------------------
# Helpers de validação informativa de assinatura (Ticket 16A)
# ---------------------------------------------------------------------------

# Mapeia `prescricao_assinatura.tipo_certificado` → nível regulatório.
# Mesmo vocabulário do motor (NIVEL_QUALIFICADA / NIVEL_AVANCADA / NIVEL_NENHUMA).
_CERT_PARA_NIVEL = {
    "A1":            "qualificada",
    "A3":            "qualificada",
    "gov_br_nuvem":  "avancada",
    None:            "nenhuma",
}

_ORDEM_NIVEL_INFORMATIVA = {
    "nenhuma":     0,
    "avancada":    1,
    "qualificada": 2,
}


def _certificado_para_nivel(tipo_certificado: Optional[str]) -> str:
    return _CERT_PARA_NIVEL.get(tipo_certificado, "nenhuma")


def _nivel_atende_minimo(nivel_presente: str, nivel_exigido: str) -> bool:
    return (
        _ORDEM_NIVEL_INFORMATIVA.get(nivel_presente, 0)
        >= _ORDEM_NIVEL_INFORMATIVA.get(nivel_exigido, 0)
    )


# ---------------------------------------------------------------------------
# Ticket 17 — GET /prescricoes/{protocolo}/receituarios/{id}/pdf
# ---------------------------------------------------------------------------
#
# Fluxo: gerar (T15) → numerar (T16A) → emitir/baixar PDF (T17)
#
# Estados aceitos para download:
#   numerado_stub | numerado | nao_requer_sncr → gera PDF e transiciona
#                                                para "emitido"
#   emitido                                    → re-baixa PDF, NÃO emite
#                                                novo evento receituario_emitido,
#                                                apenas pdf_acessado (auditoria leve)
#   gerado / cancelado                         → 422 (precisa numerar / cancelado)
#
# CPF do paciente:
#   adapter_usado="stub"  → CPF mascarado (123.***.***-01)
#   adapter_usado="real"  → mascarado por enquanto. Registramos
#                           todo_regulatorio para confirmar com Anvisa
#                           se o documento final exige CPF completo.
# Receita simples (nao_requer_sncr): também masca (mesma regra de
#   privacidade).

# Estados que aceitam emissão pela primeira vez (transição → emitido).
_STATUS_EMITIVEIS = frozenset({"numerado_stub", "numerado", "nao_requer_sncr"})

# Mensagens curtas para 422
_MSG_NAO_NUMERADO = (
    "Receituário não numerado. Chame "
    "POST /prescricoes/{protocolo}/receituarios/numerar primeiro."
)
_MSG_CANCELADO = "Receituário cancelado — PDF indisponível."


def _carregar_receituario(conn, receituario_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT id, prescricao_id, tipo_receituario, grupo_id, grupo_nome,
               assinatura_minima, assinatura_valida, vias,
               retencao_farmacia, requer_sncr, numeracao_sncr, status,
               numerado_em, emitido_em, adapter_usado, substituido_em,
               created_at, data_validade
          FROM receituarios
         WHERE id = ?
        """,
        (receituario_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


def _carregar_itens_de_receituario(conn, receituario_id: int) -> list[dict]:
    """Carrega itens da prescrição associados a este receituário,
    com todos os campos necessários para o PDF.
    """
    rows = conn.execute(
        """
        SELECT pi.id, pi.nome_medicamento, pi.concentracao,
               pi.quantidade, pi.unidade_quantidade,
               pi.forma_farmaceutica, pi.posologia,
               pi.classe_controle, pi.tipo_retencao
          FROM receituario_itens ri
          JOIN prescricao_itens pi ON pi.id = ri.prescricao_item_id
         WHERE ri.receituario_id = ?
         ORDER BY ri.id ASC
        """,
        (receituario_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _carregar_dados_pdf(conn, prescricao_id: int) -> dict:
    """Carrega prescrição + prescritor + paciente para o PDF."""
    row = conn.execute(
        """
        SELECT p.id, p.protocolo,
               p.assinatura_modo, p.assinatura_hash,
               p.tipo_emissao, p.indicacao_clinica,
               p.data_emissao, p.data_validade,
               pr.cns AS prescritor_cns, pr.nome AS prescritor_nome,
               pa.cpf AS paciente_cpf, pa.nome AS paciente_nome
          FROM prescricoes p
          JOIN prescritores pr ON pr.id = p.prescritor_id
          JOIN pacientes pa ON pa.id = p.paciente_id
         WHERE p.id = ?
        """,
        (prescricao_id,),
    ).fetchone()
    return _row_to_dict(row)


@router.get(
    "/{protocolo}/receituarios/{receituario_id}/pdf",
    summary="Baixa o PDF do receituário regulatório (modelo Anvisa V2)",
    response_class=StreamingResponse,
)
def baixar_pdf_receituario(
    protocolo: str,
    receituario_id: int,
    usuario: dict = Depends(require_role("prescritor")),
):
    """Gera e devolve o PDF do receituário.

    Comportamento:
      - Receituários `numerado_stub` / `numerado` / `nao_requer_sncr`:
        gera PDF, atualiza status → `emitido`, registra evento
        `receituario_emitido` no ledger.
      - Receituários `emitido` (acesso repetido): regenera PDF on-the-fly
        e registra evento `receituario_pdf_acessado` (trilha de acesso,
        sem inflar o ledger com novo `receituario_emitido`).
      - Receituários `gerado` / `cancelado`: 422.
    """
    cns_token = usuario.get("sub") or ""
    agora = datetime.utcnow()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        # Reutilizado pelos eventos receituario_emitido/todo/pdf_acessado
        # (invariante §6.3).
        instance_id = get_instance_id_conn(conn)

        # 1. Validar prescrição + posse
        prescricao = _carregar_prescricao(conn, protocolo)
        if prescricao.get("prescritor_cns") != cns_token:
            raise HTTPException(
                status_code=403,
                detail=(
                    "Somente o prescritor que emitiu a prescrição pode "
                    "baixar receituários."
                ),
            )

        # 2. Carregar receituário e validar pertinência à prescrição
        receituario = _carregar_receituario(conn, receituario_id)
        if not receituario:
            raise HTTPException(
                status_code=404, detail="Receituário não encontrado.",
            )
        if receituario["prescricao_id"] != prescricao["id"]:
            raise HTTPException(
                status_code=404,
                detail="Receituário não pertence a esta prescrição.",
            )
        if receituario.get("substituido_em") is not None:
            raise HTTPException(
                status_code=410,
                detail=(
                    "Receituário foi substituído por uma nova geração. "
                    "Use o receituário ativo correspondente."
                ),
            )

        # 3. Validar status
        status_atual = receituario["status"]
        if status_atual == "cancelado":
            raise HTTPException(status_code=422, detail=_MSG_CANCELADO)
        if status_atual not in _STATUS_EMITIVEIS and status_atual != "emitido":
            # Inclui "gerado" e quaisquer outros estados não previstos
            raise HTTPException(status_code=422, detail=_MSG_NAO_NUMERADO)

        # 3a. Ticket 19 — validar regras de emissão (validade, etc)
        valido, motivos = validar_emissao_receituario(
            tipo_receituario=receituario["tipo_receituario"],
            status=status_atual,
            data_validade=receituario.get("data_validade"),
            assinatura_modo=None,
            numeracao_sncr=receituario.get("numeracao_sncr"),
            adapter_usado=receituario.get("adapter_usado"),
        )
        # Se inválido E não é re-download (status != "emitido"), bloqueia
        if not valido and status_atual != "emitido":
            raise HTTPException(status_code=422, detail="; ".join(motivos))

        # 4. Carregar dados clínicos para o PDF
        dados = _carregar_dados_pdf(conn, prescricao["id"])
        itens = _carregar_itens_de_receituario(conn, receituario_id)

        # 5. Gerar PDF
        # Ticket 19: usar data_validade do receituário, não da prescrição
        data_validade_receitua = receituario.get("data_validade")
        pdf_bytes = gerar_pdf_receituario(
            tipo_receituario=receituario["tipo_receituario"],
            grupo_nome=receituario["grupo_nome"],
            numeracao_sncr=receituario["numeracao_sncr"],
            status=status_atual,
            vias=receituario["vias"],
            retencao_farmacia=bool(receituario["retencao_farmacia"]),
            adapter_usado=receituario.get("adapter_usado"),
            protocolo=dados["protocolo"],
            assinatura_hash=dados.get("assinatura_hash"),
            assinatura_modo=dados.get("assinatura_modo"),
            data_emissao=str(dados["data_emissao"]) if dados.get("data_emissao") else "",
            data_validade=(
                str(data_validade_receitua) if data_validade_receitua else None
            ),
            indicacao_clinica=dados.get("indicacao_clinica"),
            nome_prescritor=dados.get("prescritor_nome") or "",
            cns_prescritor=dados.get("prescritor_cns") or "",
            nome_paciente=dados.get("paciente_nome") or "",
            cpf_paciente=dados.get("paciente_cpf") or "",
            itens=itens,
        )

        # 6. Transição de status + evento no ledger
        if status_atual in _STATUS_EMITIVEIS:
            conn.execute(
                """
                UPDATE receituarios
                   SET status = 'emitido',
                       emitido_em = ?
                 WHERE id = ?
                """,
                (agora, receituario_id),
            )
            payload = {
                "receituario_id":     receituario_id,
                "tipo_receituario":   receituario["tipo_receituario"],
                "numeracao_sncr":     receituario["numeracao_sncr"],
                "adapter_usado":      receituario.get("adapter_usado"),
                "ticket_referencia":  "TICKET-17",
            }
            # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=prescricao["id"],
                tipo_evento="receituario_emitido",
                instance_id=instance_id,
                payload=payload,
                ator_tipo="prescritor",
                ator_id=cns_token,
            )

            # Modo real (futuro) — registrar TODO regulatório enquanto
            # decisão sobre exibir CPF completo no PDF não estiver formalizada.
            if receituario.get("adapter_usado") == "real":
                todo_payload = {
                    "receituario_id":   receituario_id,
                    "tipo_receituario": receituario["tipo_receituario"],
                    "motivo":           "cpf_paciente_em_pdf_real",
                    "questao": (
                        "Confirmar com Anvisa se o documento regulatório final "
                        "exige CPF completo do paciente ou aceita mascaramento."
                    ),
                    "acao_necessaria":  "validacao_juridica_pre_producao",
                }
                # Ticket 4D.1: reutiliza instance_id da transação (invariante §6.3).
                registrar_evento_ledger(
                    conn,
                    objeto_tipo="prescricao",
                    objeto_id=prescricao["id"],
                    tipo_evento="todo_regulatorio",
                    instance_id=instance_id,
                    payload=todo_payload,
                    ator_tipo="prescritor",
                    ator_id=cns_token,
                )
        else:
            # status_atual == "emitido" — re-download. Auditoria leve para
            # não inflar o ledger com novos receituario_emitido.
            payload = {
                "receituario_id":   receituario_id,
                "tipo_receituario": receituario["tipo_receituario"],
            }
            # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=prescricao["id"],
                tipo_evento="receituario_pdf_acessado",
                instance_id=instance_id,
                payload=payload,
                ator_tipo="prescritor",
                ator_id=cns_token,
            )

    # 7. Resposta — StreamingResponse com Content-Disposition
    abrev = tipo_abrev(receituario["tipo_receituario"])
    filename = f"receituario-{abrev}-{receituario_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length":      str(len(pdf_bytes)),
        },
    )


# ---------------------------------------------------------------------------
# Ticket 21 — POST /receituarios/{id}/pdf-assinado
# ---------------------------------------------------------------------------
#
# Embute assinatura ICP-Brasil PAdES-B no PDF do receituário. Endpoint
# SEPARADO de GET /pdf para isolar a lógica criptográfica e garantir
# que a senha do .pfx (no body JSON) NUNCA viaje em header logável.
#
# Importante: o body deste endpoint contém senha sensível. O middleware
# de observabilidade do PicSaúde já não loga bodies por design — ainda
# assim, a constante BODY_NUNCA_LOGAR (ver app/middleware/sensitive_body.py)
# documenta explicitamente esta rota como sensível.

from pydantic import BaseModel, Field

from app.domain.cofre_pfx import decifrar_pfx
from app.domain.pdf_assinatura import (
    MetadataAssinatura,
    SenhaPfxInvalida,
    assinar_pdf_icp,
)


class PdfAssinadoRequest(BaseModel):
    """Body do POST /pdf-assinado. A senha é sensível — não logar."""
    senha_pfx: str = Field(..., min_length=1, max_length=200)


def _carregar_certificado_ativo(conn, prescritor_id: int) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT id, pfx_cifrado, pfx_iv, pfx_tag, hash_cert_der, serial,
               valido_de, valido_ate, nome_no_certificado, cpf_no_certificado
          FROM prescritor_certificados
         WHERE prescritor_id = ?
           AND ativo = TRUE
        """,
        (prescritor_id,),
    ).fetchone()
    return _row_to_dict(row) if row else None


@router.post(
    "/{protocolo}/receituarios/{receituario_id}/pdf-assinado",
    summary="Gera PDF do receituário com assinatura PAdES-B embutida",
    response_class=StreamingResponse,
)
def baixar_pdf_assinado(
    protocolo: str,
    receituario_id: int,
    body: PdfAssinadoRequest,
    usuario: dict = Depends(require_role("prescritor")),
):
    """Gera PDF do receituário e embute assinatura ICP-Brasil PAdES-B.

    Pré-requisitos:
      - prescritor logado
      - receituário em status emitível (numerado_stub / numerado /
        nao_requer_sncr / emitido)
      - prescricao.assinatura_modo == "icp_brasil_local"
      - prescritor tem certificado ativo cadastrado

    Comportamento:
      - Carrega .pfx cifrado, decifra com chave de ambiente, abre com
        a senha fornecida no body.
      - Gera PDF via `gerar_pdf_receituario` (T17), depois assina com
        pyHanko (PAdES-B).
      - Registra evento `pdf_assinado_pades` no ledger com hash do
        PDF assinado, serial do certificado e hash_cert_der.
      - Idempotência: cada request gera um novo PDF assinado (a
        assinatura embute timestamp e o hash difere). NÃO altera o
        status do receituário (assinatura PAdES é independente da
        emissão lógica).
    """
    cns_token = usuario.get("sub") or ""
    agora = datetime.utcnow()

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        instance_id = get_instance_id_conn(conn)

        # 1. Validar prescrição + posse
        prescricao = _carregar_prescricao(conn, protocolo)
        if prescricao.get("prescritor_cns") != cns_token:
            raise HTTPException(
                status_code=403,
                detail="Somente o prescritor que emitiu a prescrição pode assinar.",
            )

        # 2. Receituário pertence à prescrição?
        receituario = _carregar_receituario(conn, receituario_id)
        if not receituario:
            raise HTTPException(status_code=404, detail="Receituário não encontrado.")
        if receituario["prescricao_id"] != prescricao["id"]:
            raise HTTPException(
                status_code=404,
                detail="Receituário não pertence a esta prescrição.",
            )

        # 3. Status emitível? Reuso do conjunto + emitido (re-assinatura permitida).
        status_atual = receituario["status"]
        if status_atual == "cancelado":
            raise HTTPException(status_code=422, detail=_MSG_CANCELADO)
        if status_atual not in _STATUS_EMITIVEIS and status_atual != "emitido":
            raise HTTPException(status_code=422, detail=_MSG_NAO_NUMERADO)

        # 4. Modo de assinatura compatível?
        dados = _carregar_dados_pdf(conn, prescricao["id"])
        if (dados.get("assinatura_modo") or "") != "icp_brasil_local":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Receituário não usa assinatura ICP-Brasil "
                    "(assinatura_modo != 'icp_brasil_local')."
                ),
            )

        # 5. Carregar prescritor + certificado ativo
        pres_row = conn.execute(
            "SELECT id FROM prescritores WHERE cns = ?",
            (cns_token,),
        ).fetchone()
        if not pres_row:
            raise HTTPException(
                status_code=404, detail="Prescritor não cadastrado.",
            )
        prescritor_id = pres_row["id"] if hasattr(pres_row, "keys") else pres_row[0]
        cert = _carregar_certificado_ativo(conn, prescritor_id)
        if not cert:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Nenhum certificado ICP-Brasil ativo encontrado. "
                    "Faça upload via POST /prescritor/certificado."
                ),
            )

        # 6. Decifrar .pfx (chave de ambiente AES-GCM)
        pfx_bytes = decifrar_pfx(
            bytes(cert["pfx_cifrado"]),
            bytes(cert["pfx_iv"]),
            bytes(cert["pfx_tag"]),
        )

        # 7. Gerar PDF base
        itens = _carregar_itens_de_receituario(conn, receituario_id)
        pdf_base = gerar_pdf_receituario(
            tipo_receituario=receituario["tipo_receituario"],
            grupo_nome=receituario["grupo_nome"],
            numeracao_sncr=receituario["numeracao_sncr"],
            status=status_atual,
            vias=receituario["vias"],
            retencao_farmacia=bool(receituario["retencao_farmacia"]),
            adapter_usado=receituario.get("adapter_usado"),
            protocolo=dados["protocolo"],
            assinatura_hash=dados.get("assinatura_hash"),
            assinatura_modo=dados.get("assinatura_modo"),
            data_emissao=str(dados["data_emissao"]) if dados.get("data_emissao") else "",
            data_validade=(
                str(dados["data_validade"]) if dados.get("data_validade") else None
            ),
            indicacao_clinica=dados.get("indicacao_clinica"),
            nome_prescritor=dados.get("prescritor_nome") or "",
            cns_prescritor=dados.get("prescritor_cns") or "",
            nome_paciente=dados.get("paciente_nome") or "",
            cpf_paciente=dados.get("paciente_cpf") or "",
            itens=itens,
        )

        # 8. Assinar com pyHanko (PAdES-B)
        meta = MetadataAssinatura(
            nome_prescritor=cert["nome_no_certificado"] or dados.get("prescritor_nome") or "",
            cpf_prescritor=cert["cpf_no_certificado"],
            crm_prescritor=None,   # T65 binding pode preencher futuramente
            uf_prescritor=None,
            razao="Receituário regulatório PicSaúde",
        )
        try:
            pdf_assinado = assinar_pdf_icp(
                pdf_bytes=pdf_base,
                pfx_bytes=pfx_bytes,
                senha=body.senha_pfx,
                metadata=meta,
            )
        except SenhaPfxInvalida:
            raise HTTPException(
                status_code=401, detail="Senha do certificado inválida.",
            )
        finally:
            # Apaga o .pfx descriptografado da memória local o quanto
            # antes (Python não dá garantias fortes — best effort).
            del pfx_bytes

        # 9. Registrar evento no ledger
        import hashlib as _hashlib
        hash_pdf_assinado = _hashlib.sha256(pdf_assinado).hexdigest()
        payload = {
            "receituario_id":   receituario_id,
            "tipo_receituario": receituario["tipo_receituario"],
            "hash_pdf":         hash_pdf_assinado,
            "serial_cert":      cert["serial"],
            "hash_cert_der":    cert["hash_cert_der"],
            "nivel_pades":      "B",
            "ticket_referencia": "TICKET-21",
        }
        # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=prescricao["id"],
            tipo_evento="pdf_assinado_pades",
            instance_id=instance_id,
            payload=payload,
            ator_tipo="prescritor",
            ator_id=cns_token,
        )

    # 10. Resposta
    abrev = tipo_abrev(receituario["tipo_receituario"])
    filename = f"receituario-{abrev}-{receituario_id}-assinado.pdf"
    return StreamingResponse(
        iter([pdf_assinado]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length":      str(len(pdf_assinado)),
        },
    )
