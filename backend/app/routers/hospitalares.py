"""
hospitalares.py
===============
Endpoint de dispensação hospitalar do PicSaúde — Ticket 27.

Princípios (CLAUDE.md §6b + docs/ARQUITETURA_FARMACIA_HOSPITALAR.md):
  - Subdomínio operacional da dispensação, não novo objeto sanitário
  - Mesmo papel RBAC: dispensador
  - Contexto operacional diferente: org_id + unidade_id obrigatórios
  - Paciente NÃO é detentor intermediário no fluxo hospitalar
  - Constraint de quantidade: Σ dispensado ≤ prescrito (idêntica ao ambulatorial)
  - Ledger: novo evento `dispensacao_hospitalar_registrada` (não altera eventos existentes)
  - Registro base vai para `dispensacoes` (mesma tabela); contexto vai para
    `dispensacoes_hospitalares` (extensão — nunca caminho paralelo)

Guardrail obrigatório (§6b):
  Toda query em `dispensacoes_hospitalares` que opere em contexto institucional
  deve incluir filtro de org_id. Queries deste router sempre filtram por org_id.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.motor_regulatorio import escriturar_grupo_regulatorio
from app.instance import get_instance_id_conn
from app.utils.helpers import normalize_cnpj, _assert_or_403, _normalizar_identidade_jwt

router = APIRouter(prefix="/prescricoes", tags=["farmacia_hospitalar"])


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_MODALIDADES_VALIDAS = {"internacao", "urgencia_emergencia", "cirurgia"}

_BLOQUEADOS_DISPENSAR = {
    "dispensado",
    "cancelado",
    "devolvido_prescritor",
    "estornado",
    "encerrado_fisico",
}


# ---------------------------------------------------------------------------
# Schema de entrada
# ---------------------------------------------------------------------------

class DispensarHospitalarIn(BaseModel):
    # Escopo institucional — obrigatório para contexto hospitalar (§6b CLAUDE.md)
    org_id:     str
    unidade_id: str

    # Destino assistencial
    setor: Optional[str] = None
    leito: Optional[str] = None

    # Modalidade
    modalidade: str = "internacao"

    # Dispensação
    quantidade_dispensada: int
    cnpj_estabelecimento:  Optional[str] = None   # opcional; usado no registro base
    dispensado_por:        Optional[str] = None

    # Dose unitária
    dose_unitaria:    bool = False
    quantidade_doses: Optional[int] = None

    # Tratamento 4 — origem do contexto institucional: 'cnes_verificado' | 'manual' | None
    origem_contexto:            Optional[str]  = None
    # Ticket 46 — gate leve
    contexto_confirmado_manual: Optional[bool] = None

    @field_validator("quantidade_dispensada")
    @classmethod
    def qtd_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantidade_dispensada deve ser maior que zero")
        return v

    @field_validator("modalidade")
    @classmethod
    def modalidade_valida(cls, v: str) -> str:
        if v not in _MODALIDADES_VALIDAS:
            raise ValueError(
                f"Modalidade inválida: '{v}'. Aceitas: {sorted(_MODALIDADES_VALIDAS)}"
            )
        return v

    @field_validator("quantidade_doses")
    @classmethod
    def doses_positivas(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("quantidade_doses deve ser maior que zero")
        return v


# ---------------------------------------------------------------------------
# Helpers internos
# (análogos aos de custodia.py — sem importação cruzada para evitar acoplamento)
# ---------------------------------------------------------------------------

def _get_prescricao(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM prescricoes WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Prescrição '{protocolo}' não encontrada.")
    return dict(row)


def _org_id_do_dispensador(conn, cnpj_norm: str) -> str | None:
    # §6b — leitura institucional para ownership payload-vs-JWT: resolve
    # prestadores.cnpj (gravado cru) → org_id. Normaliza READ-SIDE; só ativo;
    # org única (0 ou >1 ambíguo → None → 403). Fail-closed se schema ausente.
    if len(cnpj_norm) != 14:
        return None
    try:
        rows = conn.execute(
            "SELECT org_id, cnpj FROM prestadores WHERE cnpj IS NOT NULL AND ativo = true"
        ).fetchall()
    except Exception:
        return None
    orgs = {r["org_id"] for r in rows if normalize_cnpj(r["cnpj"]) == cnpj_norm}
    return orgs.pop() if len(orgs) == 1 else None


def _fechar_custodia_ativa(conn, prescricao_id: int, item_id, agora: str) -> None:
    """Fecha custódia ativa da prescrição ou de um item específico."""
    if item_id is None:
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (agora, prescricao_id),
        )
    else:
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id = ? AND encerrada_em IS NULL
            """,
            (agora, prescricao_id, item_id),
        )


def _abrir_custodia_hospitalar(
    conn,
    prescricao_id: int,
    item_id,
    detentor_tipo: str,
    detentor_id: str,
    motivo: Optional[str],
    contexto_operacional: str,
    unidade_id: str,
    agora: str,
) -> None:
    """
    Abre custódia com contexto hospitalar.

    Diferença do _abrir_custodia ambulatorial: inclui contexto_operacional e
    unidade_id — campos adicionados em Ticket 27 à tabela prescricao_custodia.
    """
    conn.execute(
        """
        INSERT INTO prescricao_custodia
          (prescricao_id, item_id, detentor_tipo, detentor_id,
           transferida_em, encerrada_em, motivo, created_at,
           contexto_operacional, unidade_id)
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?)
        """,
        (
            prescricao_id, item_id, detentor_tipo, detentor_id,
            agora, motivo, agora,
            contexto_operacional, unidade_id,
        ),
    )


def _gravar_evento(
    conn, prescricao_id: int, tipo_evento: str,
    ator_tipo: str, ator_id: str, payload: dict, agora: str,
    *, instance_id: str,
) -> None:
    """
    Ticket 4D.1: helper interno passa a delegar ao registrar_evento_ledger.
    `instance_id` é keyword-only obrigatório — caller obtém uma vez por
    transação clínica via get_instance_id_conn(conn).

    `agora` é mantido na assinatura por compat — o helper central usa
    seu próprio timestamp UTC. Eventos hospitalares e seus pares
    (custódia/UPDATE) continuam alinhados pela ordem do INSERT.
    """
    registrar_evento_ledger(
        conn,
        objeto_tipo="prescricao",
        objeto_id=prescricao_id,
        tipo_evento=tipo_evento,
        instance_id=instance_id,
        payload=payload,
        ator_tipo=ator_tipo,
        ator_id=ator_id,
    )


def _recalcular_status_prescricao(conn, prescricao_id: int, agora: str) -> str:
    """
    Recalcula o status da prescrição com base no status_item de todos os itens.
    Lógica idêntica ao ambulatorial — mesma fonte de verdade.
    """
    rows = conn.execute(
        "SELECT status_item FROM prescricao_itens WHERE prescricao_id = ?",
        (prescricao_id,),
    ).fetchall()

    total      = len(rows)
    dispensados = sum(1 for r in rows if r["status_item"] == "dispensado")
    encerrados  = sum(
        1 for r in rows
        if r["status_item"] in {"cancelado", "estornado", "devolvido_prescritor", "encerrado_fisico"}
    )
    ativos = total - encerrados

    if ativos == 0:
        novo_status = "cancelada"
    elif dispensados == 0:
        novo_status = "em_custodia"
    elif dispensados >= ativos:
        novo_status = "dispensada"
    else:
        novo_status = "parcialmente_dispensada"

    conn.execute(
        "UPDATE prescricoes SET status = ?, updated_at = ? WHERE id = ?",
        (novo_status, agora, prescricao_id),
    )
    return novo_status


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/itens/{item_id}/dispensar/hospitalar", status_code=201)
def dispensar_hospitalar(
    protocolo: str,
    item_id: int,
    payload: DispensarHospitalarIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Registra dispensação hospitalar de um item da prescrição.

    Fluxo hospitalar (diferenças em relação ao ambulatorial):
    - org_id e unidade_id são OBRIGATÓRIOS (escopo institucional hospitalar)
    - Paciente não é detentor intermediário: custódia vai direto ao dispensador
      com contexto_operacional='hospitalar'
    - Suporta dose_unitaria e setor/leito como contexto assistencial
    - Registro base em `dispensacoes`; contexto em `dispensacoes_hospitalares`
    - Evento: `dispensacao_hospitalar_registrada`

    Invariantes preservados:
    - Σ quantidade_dispensada ≤ prescricao_itens.quantidade
    - Prescrição imutável após emissão
    - Ledger imutável (INSERT em prescricao_eventos, nunca UPDATE/DELETE)
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)

    # CNPJ para o registro base: usa cnpj_estabelecimento se informado,
    # caso contrário usa org_id (hospitalar pode não ter CNPJ no payload MVP)
    cnpj_base = payload.cnpj_estabelecimento or payload.org_id

    with get_tx() as conn:
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        instance_id = get_instance_id_conn(conn)

        # ── 1. Validar prescrição ──────────────────────────────────────────
        presc = _get_prescricao(conn, protocolo)

        if papel != "admin":
            org_disp = _org_id_do_dispensador(conn, ident)
            _assert_or_403(
                org_disp is not None and org_disp == payload.org_id,
                codigo="dispensador_de_outra_org",
                mensagem="Dispensação sob org distinta da do dispensador.",
            )

        # Prescrições terminais não podem ser dispensadas
        _TERMINAIS = {"dispensada", "cancelada", "expirada", "encerrada_localmente"}
        if presc["status"] in _TERMINAIS:
            raise HTTPException(
                status_code=409,
                detail=f"Prescrição com status '{presc['status']}' não pode ser dispensada.",
            )

        # ── 2. Validar item ────────────────────────────────────────────────
        item = conn.execute(
            "SELECT * FROM prescricao_itens WHERE id = ? AND prescricao_id = ?",
            (item_id, presc["id"]),
        ).fetchone()
        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item_id} não encontrado na prescrição '{protocolo}'.",
            )

        if item["status_item"] in _BLOQUEADOS_DISPENSAR:
            raise HTTPException(
                status_code=409,
                detail=f"Item com status '{item['status_item']}' não pode ser dispensado.",
            )

        # ── 3. Validar saldo disponível ────────────────────────────────────
        # Saldo efetivo = Σ dispensado − Σ estornado (T2: estorno repõe saldo).
        ja_dispensado = conn.execute(
            "SELECT COALESCE(SUM(quantidade_dispensada), 0) AS total "
            "FROM dispensacoes WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()["total"]
        ja_estornado = conn.execute(
            "SELECT COALESCE(SUM(quantidade_estornada), 0) AS total "
            "FROM estornos WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()["total"]

        prescrito = item["quantidade"] or 0
        saldo = prescrito - (ja_dispensado - ja_estornado)

        if saldo <= 0:
            raise HTTPException(
                status_code=409,
                detail="Não há saldo disponível para dispensação neste item.",
            )
        if payload.quantidade_dispensada > saldo:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Quantidade solicitada ({payload.quantidade_dispensada}) "
                    f"supera o saldo disponível ({saldo})."
                ),
            )

        # R4 (CLAUDE.md §2a) — escrituração regulatória congelada por valor, idêntica
        # ao caminho ambulatorial (custodia.py): a constraint e o registro base são
        # os mesmos, o contexto hospitalar não muda o regime do movimento. Falha
        # alta em classe inconsistente; NULL honesto p/ não-controlado.
        try:
            grupo_regulatorio_id, motor_regulatorio_versao = escriturar_grupo_regulatorio(
                item["classe_controle"], item["tipo_retencao"],
            )
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "codigo": "classe_controle_inconsistente",
                    "mensagem": (
                        "Item tem classe de controle/retenção que o motor regulatório "
                        f"não classifica; dispensação bloqueada. Detalhe: {exc}"
                    ),
                },
            )

        # ── 4. Gravar registro base em `dispensacoes` ──────────────────────
        cursor = conn.execute(
            """
            INSERT INTO dispensacoes
              (prescricao_item_id, cnpj_estabelecimento, quantidade_dispensada,
               dispensado_por, dispensado_em, lote, fabricante, observacao,
               origem_contexto, grupo_regulatorio_id, motor_regulatorio_versao, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?)
            """,
            (
                item_id, cnpj_base, payload.quantidade_dispensada,
                payload.dispensado_por or "farmaceutico_hospitalar",
                agora, payload.origem_contexto,
                grupo_regulatorio_id, motor_regulatorio_versao, agora,
            ),
        )
        dispensacao_id = cursor.lastrowid

        # ── 5. Gravar extensão hospitalar em `dispensacoes_hospitalares` ───
        # Guardrail §6b: org_id obrigatório nesta tabela — sempre presente no INSERT
        conn.execute(
            """
            INSERT INTO dispensacoes_hospitalares
              (dispensacao_id, prescricao_item_id, protocolo,
               org_id, unidade_id, setor, leito, modalidade,
               dose_unitaria, quantidade_doses,
               dispensado_por, dispensado_em, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dispensacao_id, item_id, protocolo,
                payload.org_id, payload.unidade_id,
                payload.setor, payload.leito, payload.modalidade,
                payload.dose_unitaria,   # bool nativo: PG=boolean, SQLite=0/1 (convergência)
                payload.quantidade_doses if payload.dose_unitaria else None,
                payload.dispensado_por or "farmaceutico_hospitalar",
                agora, agora,
            ),
        )

        # ── 6. Atualizar status do item ────────────────────────────────────
        novo_saldo = saldo - payload.quantidade_dispensada
        novo_status_item = "dispensado" if novo_saldo == 0 else "em_custodia"

        conn.execute(
            "UPDATE prescricao_itens SET status_item = ?, updated_at = ? WHERE id = ?",
            (novo_status_item, agora, item_id),
        )

        # ── 7. Atualizar custódia com contexto hospitalar ──────────────────
        # No fluxo hospitalar o paciente não é detentor intermediário.
        # Custódia vai direto ao dispensador com contexto_operacional='hospitalar'.
        _fechar_custodia_ativa(conn, presc["id"], item_id, agora)
        _fechar_custodia_ativa(conn, presc["id"], None, agora)

        if novo_status_item != "dispensado":
            # Item ainda em dispensação parcial: abre custódia hospitalar do item
            _abrir_custodia_hospitalar(
                conn,
                prescricao_id=presc["id"],
                item_id=item_id,
                detentor_tipo="dispensador",
                detentor_id=payload.unidade_id,
                motivo="dispensacao_hospitalar",
                contexto_operacional="hospitalar",
                unidade_id=payload.unidade_id,
                agora=agora,
            )

        # ── 8. Recalcular status da prescrição ─────────────────────────────
        novo_status_prescricao = _recalcular_status_prescricao(conn, presc["id"], agora)

        # ── 9. Evento no ledger ────────────────────────────────────────────
        evento_hosp: dict = {
            "item_id":               item_id,
            "nome_medicamento":      item["nome_medicamento"],
            "quantidade_dispensada": payload.quantidade_dispensada,
            "saldo_restante":        novo_saldo,
            "status_item":           novo_status_item,
            "org_id":                payload.org_id,
            "unidade_id":            payload.unidade_id,
            "setor":                 payload.setor,
            "leito":                 payload.leito,
            "modalidade":            payload.modalidade,
            "dose_unitaria":         payload.dose_unitaria,
            "quantidade_doses":      payload.quantidade_doses,
        }
        if payload.origem_contexto:
            evento_hosp["origem_contexto"] = payload.origem_contexto
        if payload.contexto_confirmado_manual is not None:
            evento_hosp["confirmado_manual"] = payload.contexto_confirmado_manual
        _gravar_evento(
            conn, presc["id"],
            "dispensacao_hospitalar_registrada",
            "dispensador", payload.unidade_id,
            evento_hosp,
            agora,
            instance_id=instance_id,
        )

        return {
            "protocolo":             protocolo,
            "item_id":               item_id,
            "nome_medicamento":      item["nome_medicamento"],
            "quantidade_dispensada": payload.quantidade_dispensada,
            "saldo_restante":        novo_saldo,
            "status_item":           novo_status_item,
            "status_prescricao":     novo_status_prescricao,
            "contexto":              "hospitalar",
            "org_id":                payload.org_id,
            "unidade_id":            payload.unidade_id,
            "setor":                 payload.setor,
            "leito":                 payload.leito,
            "dispensacao_id":        dispensacao_id,
        }
