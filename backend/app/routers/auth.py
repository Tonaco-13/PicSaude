from __future__ import annotations

import json
import os
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.auth.jwt import criar_access_token
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.conselho_profissional import conselho_ou_padrao, formatar_registro
from app.domain.ledger import registrar_evento_ledger
from app.domain.states import ESTADOS_TERMINAIS_PRESCRICAO
from app.routers.custodia import transferir_posse, _fechar_custodia_ativa  # choke-point de posse (COER-2) + fecha custódia de item terminal
from app.routers.pedidos_exame import (  # TICKET-J.7 — posse do exame vem da custódia, não do status
    DETENTOR_PACIENTE,
    detentor_atual_pedido,
    posse_do_cidadao,
)
from app.routers.agendamentos import (  # TICKET-J.11 — selo do compromisso vigente no cartão
    agendamento_atual_do_pedido,
    resumo_agendamento_para_cartao,
)
from app.domain.states_exame import ESTADOS_TERMINAIS_PEDIDO_EXAME
from app.instance import get_instance_id_conn
from app.utils.helpers import normalize_cnpj, normalize_cpf

router = APIRouter()


# TICKET-6 P1#2 — em DEMO_MODE, OTP legado devolve 403 demo_mode_ativo.
def _reject_if_demo() -> None:
    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "demo_mode_ativo",
                "mensagem": "Login real desabilitado em modo demo. Use o seletor em /.",
            },
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SolicitarCodigoIn(BaseModel):
    cpf: str
    telefone: Optional[str] = None  # kept for backward compat, not required


class ValidarCodigoIn(BaseModel):
    cpf: str
    codigo: str


# ---------------------------------------------------------------------------
# POST /paciente/enviar-codigo
# ---------------------------------------------------------------------------

@router.post("/paciente/enviar-codigo")
def enviar_codigo(body: SolicitarCodigoIn, _demo=Depends(_reject_if_demo)):
    cpf = normalize_cpf(body.cpf)

    if not cpf:
        raise HTTPException(status_code=400, detail="CPF inválido ou não informado.")

    codigo = str(secrets.randbelow(900000) + 100000)
    agora = datetime.utcnow().isoformat()
    expiracao = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    with get_tx() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO pacientes (cpf, nome, created_at, updated_at, ativo)
            VALUES (?, 'PACIENTE', ?, ?, false)
            """,
            (cpf, agora, agora),
        )
        conn.execute(
            """
            INSERT INTO codigos_login (cpf, codigo, expiracao, usado, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (cpf, codigo, expiracao, agora),
        )

    # Print OTP no stdout APENAS em dev/test — em produção (Render),
    # OTP nunca aparece nos logs. Bloqueador de segurança CODEX 2026-05-06.
    # SEM default: PICSAUDE_ENV ausente é tratado como "não-dev/test",
    # então deploy sem env configurada NÃO vaza OTP.
    _cpf_mascarado = f"*******{cpf[-4:]}" if len(cpf) >= 4 else "***"
    if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
        print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

    return {"ok": True, "mensagem": "Código de verificação gerado. Em produção será enviado por SMS."}


# ---------------------------------------------------------------------------
# POST /paciente/validar-codigo  → retorna JWT com role="paciente"
# ---------------------------------------------------------------------------

@router.post("/paciente/validar-codigo")
def validar_codigo(body: ValidarCodigoIn, _demo=Depends(_reject_if_demo)):
    cpf    = normalize_cpf(body.cpf)
    codigo = (body.codigo or "").strip()

    if not cpf or not codigo:
        raise HTTPException(status_code=400, detail="CPF e código são obrigatórios.")

    with get_tx() as conn:
        agora_check = datetime.utcnow().isoformat()
        row = conn.execute(
            """
            SELECT id FROM codigos_login
            WHERE cpf = ?
              AND codigo = ?
              AND usado = 0
              AND expiracao >= ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (cpf, codigo, agora_check),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Código inválido, expirado ou já utilizado.")

        conn.execute("UPDATE codigos_login SET usado = 1 WHERE id = ?", (row["id"],))
        conn.execute("UPDATE pacientes SET ativo = true WHERE cpf = ?", (cpf,))

        paciente = conn.execute(
            "SELECT nome FROM pacientes WHERE cpf = ?", (cpf,)
        ).fetchone()
        nome = (paciente["nome"] if paciente else None) or "Paciente"

    access_token = criar_access_token(sub=cpf, role="paciente", nome=nome)
    return {"ok": True, "access_token": access_token, "token_type": "bearer", "nome": nome, "cpf": cpf}


# ---------------------------------------------------------------------------
# GET /paciente/prescricoes  — carteira digital do cidadão
# ---------------------------------------------------------------------------

@router.get("/paciente/prescricoes")
def listar_prescricoes(usuario=Depends(require_role("paciente"))):
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.protocolo,
                p.status,
                p.tipo_emissao,
                p.data_emissao,
                pr.nome AS prescritor_nome
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE pa.cpf = ?
              AND p.tipo_emissao != 'fisica'
            ORDER BY p.id DESC
            """,
            (cpf,),
        ).fetchall()

        prescricoes = []
        for row in rows:
            itens = conn.execute(
                """
                SELECT nome_medicamento, concentracao, quantidade, posologia, status_item
                FROM prescricao_itens
                WHERE prescricao_id = ?
                """,
                (row["id"],),
            ).fetchall()
            prescricoes.append({
                "protocolo":      row["protocolo"],
                "status":         row["status"],
                "tipo_emissao":   row["tipo_emissao"],
                "data_emissao":   row["data_emissao"],
                "prescritor_nome": row["prescritor_nome"],
                "itens": [dict(i) for i in itens],
            })

    _EM_POSSE   = {"transferida_paciente", "pendente"}
    # COER-2: transferida_prescritor = devolvida ao médico p/ correção. Sai da POSSE
    # do cidadão (não é mais dele) e entra no HISTÓRICO — nunca "Documento Ativo"
    # (raiz do Cenário 2, quando reusava "pendente" e a carteira a mostrava ativa).
    _HISTORICO  = {"em_custodia", "parcialmente_dispensada", "dispensada",
                   "cancelada", "expirada", "transferida_prescritor"}

    return {
        "posse":    [p for p in prescricoes if p["status"] in _EM_POSSE],
        "historico": [p for p in prescricoes if p["status"] in _HISTORICO],
    }


# ---------------------------------------------------------------------------
# POST /paciente/prescricoes/{proto}/transferir-farmacia
# paciente → dispensador
# ---------------------------------------------------------------------------

@router.post("/paciente/prescricoes/{proto}/transferir-farmacia", status_code=201)
def transferir_farmacia(proto: str, body: dict, usuario=Depends(require_role("paciente"))):
    cpf  = usuario["sub"]
    cnpj = normalize_cnpj(body.get("cnpj_farmacia", ""))

    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="cnpj_farmacia inválido")

    agora = datetime.utcnow().isoformat()
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.status
            FROM prescricoes p
            JOIN pacientes pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ? AND pa.cpf = ?
            """,
            (proto, cpf),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404,
                                detail="Prescrição não encontrada ou não pertence a este paciente")

        if row["status"] != "transferida_paciente":
            raise HTTPException(status_code=409,
                                detail=f"Prescrição não está sob sua custódia (status: {row['status']})")

        pid = row["id"]

        instance_id = get_instance_id_conn(conn)
        conn.execute(
            "UPDATE prescricoes SET status = 'em_custodia', updated_at = ? WHERE id = ?",
            (agora, pid),
        )
        # COER-2: transição de posse pelo choke-point — fecha a custódia do
        # paciente + abre a do dispensador + emite custodia_transferida, atômico.
        # `motivo` canônico ('transferencia_farmacia') p/ o T6 separar este caminho
        # dos demais custodia_transferida (§6.2 do ticket).
        transferir_posse(
            conn, pid, None,
            "paciente", cpf, "dispensador", cnpj,
            "transferencia_farmacia", agora,
            ator_tipo="paciente", ator_id=cpf, instance_id=instance_id,
            extra_payload={"origem": "cidadao_app"},
        )

    return {"ok": True, "protocolo": proto, "status": "em_custodia"}


# ---------------------------------------------------------------------------
# POST /paciente/prescricoes/{proto}/devolver-prescritor
# paciente → prescritor  (erro identificado pelo paciente)
# ---------------------------------------------------------------------------

@router.post("/paciente/prescricoes/{proto}/devolver-prescritor", status_code=201)
def devolver_prescritor(proto: str, body: dict, usuario=Depends(require_role("paciente"))):
    cpf    = usuario["sub"]
    motivo = body.get("motivo") or "Devolução voluntária pelo cidadão"

    agora = datetime.utcnow().isoformat()
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.status, pr.cns AS prescritor_cns
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ? AND pa.cpf = ?
            """,
            (proto, cpf),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Prescrição não encontrada")

        if row["status"] not in ("transferida_paciente", "pendente"):
            raise HTTPException(status_code=409,
                                detail=f"Prescrição com status '{row['status']}' não pode ser devolvida")

        pid  = row["id"]
        cns  = row["prescritor_cns"]

        instance_id = get_instance_id_conn(conn)

        # Itens RETORNÁVEIS voltam ao prescritor. COER2-POS-MERGE-FIX: os dois
        # estados retornáveis são `pendente` (nunca dispensado) E `devolvido_paciente`
        # (rescaldo de estorno/devolução ao paciente — o composto do Cenário 2). Antes,
        # o WHERE só pegava `pendente`: um item `devolvido_paciente` NÃO virava
        # `devolvido_prescritor`, então a prescrição ia p/ `transferida_prescritor`
        # mas o item ficava contraditório e invisível no painel (que lê item-level
        # `devolvido_prescritor`). §9.2 (COER-2): cada item emite
        # `item_devolvido_prescritor` com `item_id` + `motivo` (texto livre do
        # cidadão) — é ESSE evento que o painel de correções do prescritor lê
        # (prescritor.py::_montar_correcoes). Antes, este caminho só emitia o
        # custodia_transferida de NÍVEL-PRESCRIÇÃO (sem item_id), então o motivo
        # não chegava ao médico ("Motivo não informado."). Agora chega.
        itens = conn.execute(
            """
            SELECT id, nome_medicamento
              FROM prescricao_itens
             WHERE prescricao_id = ?
               AND status_item IN ('pendente', 'devolvido_paciente')
            """,
            (pid,),
        ).fetchall()
        for it in itens:
            conn.execute(
                "UPDATE prescricao_itens SET status_item = 'devolvido_prescritor', updated_at = ? WHERE id = ?",
                (agora, it["id"]),
            )
            # COER2-POS-MERGE-FIX: item `devolvido_paciente` carrega uma custódia
            # de ITEM ATIVA no nome do paciente (aberta em custodia.py::devolver_item
            # para=paciente). Ao virar terminal `devolvido_prescritor`, essa custódia
            # de item precisa ser FECHADA — senão fica órfã (item terminal + custódia
            # ativa = a mesma "dupla posse" que o COER-2 mata). Espelha
            # custodia.py::devolver_item (para=prescritor NÃO reabre custódia: item
            # terminal aguarda prescrição derivada). No caminho fresh (item `pendente`)
            # não há custódia de item ativa → no-op seguro (0 linhas).
            _fechar_custodia_ativa(conn, pid, it["id"], agora)
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=pid,
                tipo_evento="item_devolvido_prescritor",
                instance_id=instance_id,
                payload={
                    "item_id": it["id"],
                    "nome_medicamento": it["nome_medicamento"],
                    "devolvido_para": "prescritor",
                    "motivo": motivo,
                    "novo_status_item": "devolvido_prescritor",
                },
                ator_tipo="paciente",
                ator_id=cpf,
            )

        # COER-2 (Opção B): posse volta ao prescritor p/ correção — estado próprio,
        # honesto contra a custódia. Antes reusava "pendente" (ambíguo: colidia com
        # "aguardando 1º envio ao paciente" → a carteira do cidadão mostrava a
        # receita devolvida como "Documento Ativo"). Raiz do Cenário 2.
        conn.execute(
            "UPDATE prescricoes SET status = 'transferida_prescritor', updated_at = ? WHERE id = ?",
            (agora, pid),
        )
        # Transição de posse pelo choke-point (nível prescrição). `motivo` canônico
        # 'devolucao_ao_prescritor' (T6); o texto livre do cidadão vai em motivo_detalhe.
        transferir_posse(
            conn, pid, None,
            "paciente", cpf, "prescritor", cns,
            "devolucao_ao_prescritor", agora,
            ator_tipo="paciente", ator_id=cpf, instance_id=instance_id,
            extra_payload={"origem": "cidadao_app", "motivo_detalhe": motivo},
        )

    return {"ok": True, "protocolo": proto, "status": "transferida_prescritor"}


# ---------------------------------------------------------------------------
# GET /paciente/prescricoes/expirando  — alertas de renovação
# ---------------------------------------------------------------------------

# Estados não-terminais que o cidadão pode enxergar
_ESTADOS_ATIVOS = frozenset({
    "pendente",
    "transferida_paciente",
    "em_custodia",
    "parcialmente_dispensada",
}) - ESTADOS_TERMINAIS_PRESCRICAO   # garante coerência com o domínio


@router.get("/paciente/prescricoes/expirando")
def prescricoes_expirando(
    dias: int = Query(default=7, ge=1, le=90,
                      description="Janela em dias a partir de hoje (padrão: 7)"),
    usuario=Depends(require_role("paciente")),
):
    """
    Retorna prescrições não-terminais do cidadão cuja data_validade
    está entre hoje e hoje + `dias`.

    - CPF extraído do JWT (não aceito via query param).
    - Prescrições expiradas ou em estado terminal são ignoradas.
    - Campo `dias_restantes` calculado no servidor.
    """
    cpf   = usuario["sub"]
    hoje  = date.today()
    limite = hoje + timedelta(days=dias)

    placeholders = ",".join("?" * len(_ESTADOS_ATIVOS))
    sql = f"""
        SELECT
            p.protocolo,
            p.status,
            p.tipo_emissao,
            p.data_validade,
            COUNT(i.id)                                                AS total_itens,
            SUM(CASE WHEN i.status_item = 'dispensado' THEN 1 ELSE 0 END) AS itens_dispensados
        FROM prescricoes p
        JOIN prescricao_itens i ON i.prescricao_id = p.id
        JOIN pacientes pa       ON pa.id = p.paciente_id
        WHERE pa.cpf = ?
          AND p.data_validade IS NOT NULL
          AND p.data_validade >= ?
          AND p.data_validade <= ?
          AND p.status IN ({placeholders})
        GROUP BY p.id
        ORDER BY p.data_validade ASC
    """

    params = [cpf, hoje.isoformat(), limite.isoformat(), *sorted(_ESTADOS_ATIVOS)]

    with get_tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    resultado = []
    for r in rows:
        try:
            validade = date.fromisoformat(r["data_validade"][:10])
            dias_restantes = (validade - hoje).days
        except (ValueError, TypeError):
            dias_restantes = None

        resultado.append({
            "protocolo":        r["protocolo"],
            "status":           r["status"],
            "tipo_emissao":     r["tipo_emissao"],
            "data_validade":    r["data_validade"][:10] if r["data_validade"] else None,
            "dias_restantes":   dias_restantes,
            "itens_total":      r["total_itens"],
            "itens_dispensados": r["itens_dispensados"] or 0,
        })

    return resultado


# ---------------------------------------------------------------------------
# GET /paciente/pedidos-exame  — carteira de exames do cidadão
# ---------------------------------------------------------------------------

_EM_POSSE_EXAME   = {"emitido", "agendado"}
_HISTORICO_EXAME  = ESTADOS_TERMINAIS_PEDIDO_EXAME | {"coletado", "em_analise", "resultado_disponivel"}


@router.get("/paciente/pedidos-exame")
def listar_pedidos_exame(usuario=Depends(require_role("paciente"))):
    """
    Retorna os pedidos de exame do paciente autenticado, separados em:
    - posse: pedidos ainda em curso (emitido, agendado)
    - em_andamento: coletado, em_analise, resultado_disponivel
    - historico: encerrados, cancelados, expirados, encerrado_fisico

    TICKET-J.7 — cada pedido leva `sob_minha_custodia` (bool) e `detentor`.
    Os BALDES continuam por status (nada muda para quem já os consome), mas
    "posso entregar este pedido a um laboratório?" deixou de ser derivável do
    status: depois do J.7 o pedido entregue permanece `emitido`, e só a cadeia
    de custódia sabe se ele ainda está com o cidadão. A tela lê este campo em
    vez de comparar status — ver `cidadao.html::renderizarPedidosExame`.

    TICKET-J.11 — cada pedido leva também `agendamento`: o compromisso VIGENTE
    que o laboratório marcou (ou `None`). Leitura pura — zero escrita, zero
    evento, zero transição de custódia: informação ≠ custódia, e o pedido segue
    com o `prestador_exame` enquanto o cidadão lê a data. Vem por aqui, e não
    por uma chamada por cartão a `GET /pedidos-exame/{p}/agendamentos`, para
    que a carteira não faça N+1 requisições e para que "qual é o agendamento
    corrente" tenha UMA resposta, no backend (`agendamento_atual_do_pedido`).
    """
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                pe.id,
                pe.protocolo,
                pe.status,
                pe.tipo_emissao,
                pe.prioridade,
                pe.data_emissao,
                pe.data_validade,
                pr.nome AS prescritor_nome
            FROM pedidos_exame pe
            JOIN prescritores pr ON pr.id = pe.prescritor_id
            JOIN pacientes    pa ON pa.id = pe.paciente_id
            WHERE pa.cpf = ?
              AND pe.tipo_emissao != 'fisico'
            ORDER BY pe.id DESC
            """,
            (cpf,),
        ).fetchall()

        pedidos = []
        for row in rows:
            # J.10 — posse POR ITEM: depois de uma transferência parcial, parte
            # dos itens está com um CNPJ e parte com o cidadão. A linha de item
            # ativa vence; sem linha, vale a posse nível-pedido que cobre o item.
            itens = conn.execute(
                """
                SELECT i.id, i.nome_exame, i.codigo_tuss, i.quantidade, i.status_item,
                       (SELECT c2.para FROM pedido_exame_custodia c2
                         WHERE c2.pedido_id = i.pedido_id
                           AND c2.item_id = i.id
                           AND c2.encerrada_em IS NULL
                         ORDER BY c2.id DESC LIMIT 1) AS detentor_item
                  FROM pedido_exame_itens i
                 WHERE i.pedido_id = ?
                 ORDER BY i.id
                """,
                (row["id"],),
            ).fetchall()
            # TICKET-J.7 — posse vem da CUSTÓDIA, não do status. `None` = nunca
            # saiu do cidadão (a emissão não grava linha de nível-pedido).
            detentor = detentor_atual_pedido(conn, row["id"])
            itens_out = []
            algum_item_meu = False
            for i in itens:
                det_item = i["detentor_item"] if i["detentor_item"] is not None else detentor
                meu = posse_do_cidadao(det_item)
                algum_item_meu = algum_item_meu or meu
                itens_out.append({
                    "id":                 i["id"],
                    "nome_exame":         i["nome_exame"],
                    "codigo_tuss":        i["codigo_tuss"],
                    "quantidade":         i["quantidade"],
                    "status_item":        i["status_item"],
                    "detentor":           det_item or DETENTOR_PACIENTE,
                    "sob_minha_custodia": meu,
                })
            # TICKET-J.11 — o selo do compromisso. Leitura pura: nenhuma
            # transição de custódia, nenhum evento. Informação ≠ custódia — o
            # pedido segue com o `prestador_exame` enquanto o cidadão lê a data.
            agendamento = resumo_agendamento_para_cartao(
                agendamento_atual_do_pedido(conn, row["id"])
            )
            pedidos.append({
                "protocolo":      row["protocolo"],
                "status":         row["status"],
                "tipo_emissao":   row["tipo_emissao"],
                "prioridade":     row["prioridade"],
                "data_emissao":   row["data_emissao"],
                "data_validade":  row["data_validade"],
                "prescritor_nome": row["prescritor_nome"],
                "detentor":          detentor or DETENTOR_PACIENTE,
                # J.10 — no nível do pedido, "sob minha custódia" passa a ser
                # "detenho o pedido OU ao menos um item": é o que autoriza o
                # gesto de transferir os itens que seguem com o cidadão.
                "sob_minha_custodia": posse_do_cidadao(detentor) or algum_item_meu,
                "agendamento":       agendamento,     # TICKET-J.11 — None se não há compromisso vigente
                # ENG-017 (S1+S4) — o elo exame → laudo. O percurso é UM só
                # para o cidadão; a carteira tinha duas listas e nenhuma ponte.
                "laudo":             _laudo_do_pedido(conn, row["id"]),
                "itens": itens_out,
            })

    _EM_ANDAMENTO = {"coletado", "em_analise", "resultado_disponivel"}

    return {
        "posse":        [p for p in pedidos if p["status"] in _EM_POSSE_EXAME],
        "em_andamento": [p for p in pedidos if p["status"] in _EM_ANDAMENTO],
        "historico":    [p for p in pedidos if p["status"] in ESTADOS_TERMINAIS_PEDIDO_EXAME],
    }


# ---------------------------------------------------------------------------
# GET /paciente/laudos  — laudos disponíveis do cidadão
# ---------------------------------------------------------------------------

@router.get("/paciente/laudos")
def listar_laudos(usuario=Depends(require_role("paciente"))):
    """
    Retorna os laudos do paciente autenticado, separados em:
    - disponiveis: liberados e aguardando ciência
    - historico: encerrados, cancelados, expirados, encerrado_fisico
    """
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                l.id,
                l.protocolo,
                l.status,
                l.tipo_emissao,
                l.data_emissao,
                l.data_validade,
                l.aberto_em,
                pr.nome AS autor_nome
            FROM laudos l
            JOIN prescritores pr ON pr.id = l.autor_id
            JOIN pacientes    pa ON pa.id = l.paciente_id
            WHERE pa.cpf = ?
              AND l.tipo_emissao != 'fisico'
            ORDER BY l.id DESC
            """,
            (cpf,),
        ).fetchall()

        laudos = []
        for row in rows:
            itens = conn.execute(
                """
                SELECT nome_exame, codigo_tuss, conclusao, status_item
                FROM laudo_itens
                WHERE laudo_id = ?
                """,
                (row["id"],),
            ).fetchall()
            laudos.append({
                "protocolo":     row["protocolo"],
                "status":        row["status"],
                "tipo_emissao":  row["tipo_emissao"],
                "data_emissao":  row["data_emissao"],
                "data_validade": row["data_validade"],
                "autor_nome":    row["autor_nome"],
                # ENG-014 (PR C): carimbo da 1ª abertura. A tela usa para NÃO
                # chamar `POST /abrir` de novo — um fato, um evento.
                "aberto_em":     str(row["aberto_em"]).replace(" ", "T") if row["aberto_em"] else None,
                # ENG-017 (S1+S4 / R2-lite) — O RECEBIMENTO, que já era fato e
                # não era mostrado. `liberar` cria a custódia
                # `prestador → paciente`: existe o instante em que o laudo
                # chegou às mãos do cidadão, e a carteira nunca o exibiu.
                # É o handoff — exatamente o que a Regra Zero manda tornar
                # visível.
                "recebido_em":       _recebido_em_laudo(conn, row["id"]),
                # O elo de volta: o laudo sabe de que pedido nasceu. Sem ele o
                # cidadão tem duas listas e nenhuma ponte entre elas.
                "pedido_protocolo":  _pedido_do_laudo(conn, row["id"]),
                "itens":         [dict(i) for i in itens],
            })

    # ciencia_paciente entra aqui para o laudo seguir VISÍVEL ao cidadão após
    # ele dar ciência (estado não-terminal: aguarda ciência do prescritor/encerramento).
    _DISPONIVEIS    = {"liberado", "ciencia_prescritor", "ciencia_paciente"}
    _TERMINAIS_LAUDO = {"encerrado", "cancelado", "expirado", "encerrado_fisico"}

    return {
        "disponiveis": [l for l in laudos if l["status"] in _DISPONIVEIS],
        "historico":   [l for l in laudos if l["status"] in _TERMINAIS_LAUDO],
    }


def _recebido_em_laudo(conn, laudo_id: int) -> Optional[str]:
    """Quando o laudo chegou às mãos do cidadão (custódia `→ paciente`).

    ENG-017. O fato já existia — `liberar` grava a linha — e nunca foi
    mostrado. `None` significa "ainda não liberado", que é a verdade, não
    ausência de dado.
    """
    row = conn.execute(
        """
        SELECT transferido_em FROM laudo_custodia
         WHERE laudo_id = ? AND item_id IS NULL AND para = 'paciente'
         ORDER BY id DESC LIMIT 1
        """,
        (laudo_id,),
    ).fetchone()
    return str(row["transferido_em"]).replace(" ", "T") if row else None


def _pedido_do_laudo(conn, laudo_id: int) -> Optional[str]:
    """Protocolo do pedido de exame que originou este laudo — o elo de volta."""
    row = conn.execute(
        """
        SELECT pe.protocolo
          FROM laudos l JOIN pedidos_exame pe ON pe.id = l.pedido_id
         WHERE l.id = ?
        """,
        (laudo_id,),
    ).fetchone()
    return row["protocolo"] if row else None


def _laudo_do_pedido(conn, pedido_id: int) -> Optional[dict]:
    """O laudo VIGENTE de um pedido, para o cartão do exame apontar.

    ENG-017 (S1+S4). O cartão dizia "Resultado disponível" e citava a seção
    *Laudos / Resultados* pelo NOME, sem levar até ela — o cidadão tinha de ler
    a frase, memorizar o nome e rolar a página. Aqui nasce o elo.

    Só o LIBERADO em diante: laudo `em_producao` ou `assinado` ainda não é do
    cidadão (a custódia não passou), e anunciá-lo prometeria o que ele não pode
    abrir.
    """
    row = conn.execute(
        """
        SELECT protocolo, status FROM laudos
         WHERE pedido_id = ?
           AND status IN ('liberado', 'ciencia_paciente', 'ciencia_prescritor', 'encerrado')
         ORDER BY id DESC LIMIT 1
        """,
        (pedido_id,),
    ).fetchone()
    return {"protocolo": row["protocolo"], "status": row["status"]} if row else None


# ---------------------------------------------------------------------------
# GET /paciente/atestados — atestados na carteira do cidadão
# ---------------------------------------------------------------------------
# TICKET-ATESTADO-CARTEIRA-CIDADAO. O atestado JÁ chegava ao paciente: a custódia
# prescritor→paciente transfere na EMISSÃO (atestados.py) e o evento
# `custodia_transferida` já ia ao ledger. Faltava só o cidadão CONSEGUIR VER —
# sem listagem, ele precisaria saber o UUID de cor. Três objetos já tinham
# carteira (prescrições, pedidos de exame, laudos) e o atestado ficou de fora por
# omissão, não por decisão.
#
# Por que não há "enviar ao paciente" aqui (nem em lugar nenhum)
# --------------------------------------------------------------
# A prescrição exige um "Enviar ao paciente" explícito; o atestado NÃO, e isso
# está certo: o atestado É do paciente. O profissional o entrega, não o retém.
# Um estado "enviado" para atestado seria tratá-lo como receita.
#
# O que NÃO sai daqui
# -------------------
# `codigo_cid` e `indicacao_clinica` ficam de fora de propósito. O CID é opcional
# e só entra no documento com anuência do paciente (CFM art. 3º); numa LISTA ele
# viraria exibição incidental de diagnóstico — o titular abre a carteira para ver
# um comprovante e leva o diagnóstico na tela junto. O PDF já os carrega quando
# declarados, e o PDF é uma escolha deliberada de abrir.

@router.get("/paciente/atestados")
def listar_atestados(usuario=Depends(require_role("paciente"))):
    """
    Retorna os atestados do paciente autenticado, separados em:
    - vigentes:  emitidos/assinados dentro da validade (ou sem validade definida)
    - historico: cancelados, expirados, ou com validade já vencida

    Ownership vem do TOKEN (`usuario["sub"]`), nunca de CPF na URL — mesmo molde
    de /paciente/laudos.
    """
    cpf = normalize_cpf(usuario["sub"])
    hoje = date.today().isoformat()

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                a.protocolo,
                a.status,
                a.finalidade,
                a.dias_afastamento,
                a.data_documento,
                a.data_validade,
                a.municipio_emissao,
                a.conselho,
                a.uf_registro,
                a.registro_profissional,
                pr.nome AS profissional_nome
            FROM atestados a
            JOIN prescritores pr ON pr.id = a.prescritor_id
            JOIN pacientes    pa ON pa.id = a.paciente_id
            WHERE pa.cpf = ?
              AND a.tipo_emissao != 'fisico'
            ORDER BY a.id DESC
            """,
            (cpf,),
        ).fetchall()

    atestados = []
    for row in rows:
        # Título e identificação do profissional vêm da FONTE ÚNICA
        # (domain/conselho_profissional.py) — a tela não monta rótulo. Duplicar
        # "ATESTADO ODONTOLÓGICO" no HTML criaria dois lugares que divergiriam;
        # é a mesma régua de `formatar_quantidade` e `grupo_por_id`.
        conselho = conselho_ou_padrao(row["conselho"])
        atestados.append({
            "protocolo":         row["protocolo"],
            "status":            row["status"],
            "titulo_documento":  conselho.titulo_documento,
            "conselho":          conselho.id_conselho,
            "finalidade":        row["finalidade"],
            "dias_afastamento":  row["dias_afastamento"],
            "data_documento":    row["data_documento"],
            "data_validade":     row["data_validade"],
            "municipio_emissao": row["municipio_emissao"],
            "profissional_nome": row["profissional_nome"],
            "registro_profissional": formatar_registro(
                row["conselho"], row["uf_registro"], row["registro_profissional"]
            ),
        })

    # Vencido por data entra no histórico mesmo que o status ainda diga
    # 'emitido'/'assinado': não existe job que carimbe `expirado`, e mostrar um
    # atestado vencido como vigente seria a tela mentindo. A comparação é textual
    # porque as datas são ISO 'YYYY-MM-DD' — ordenáveis como string.
    _TERMINAIS_ATESTADO = {"cancelado", "expirado", "encerrada_localmente"}

    def _vigente(a: dict) -> bool:
        if a["status"] in _TERMINAIS_ATESTADO:
            return False
        return not a["data_validade"] or a["data_validade"] >= hoje

    return {
        "vigentes":  [a for a in atestados if _vigente(a)],
        "historico": [a for a in atestados if not _vigente(a)],
    }


# ---------------------------------------------------------------------------
# GET /paciente/encaminhamentos — a terceira circulação na carteira (ENG-016 §4)
# ---------------------------------------------------------------------------

@router.get("/paciente/encaminhamentos")
def listar_encaminhamentos_paciente(usuario=Depends(require_role("paciente"))):
    """Os encaminhamentos do cidadão, com POSSE e DATA DA CONSULTA.

    ENG-016 §4. Ownership vem do TOKEN (`usuario["sub"]`), nunca de CPF na URL —
    mesmo molde de `/paciente/laudos` e `/paciente/atestados`.

    DOIS FATOS, DOIS CAMPOS (§2 lei 4). O selo do cidadão mostra a data da
    CONSULTA, nunca o timestamp da custódia:

      · `data_consulta` — quando o laboratório/profissional marcou o
        atendimento. Vem do LEDGER (`encaminhamento_agendado`), que é onde o
        fato foi registrado; não há coluna, e inventar uma denormalização para
        exibir seria criar uma segunda fonte para um dado que já tem dono.
      · `posse_desde` — quando o documento mudou de mãos. Outra pergunta, outro
        campo. Mostrar um no lugar do outro faria a carteira dizer ao cidadão
        que a consulta é hoje porque a custódia mudou hoje.

    POSSE VEM DA CUSTÓDIA, nunca do status (§1a): um encaminhamento `agendado`
    tanto pode estar com o cidadão (marcaram e ele ainda não foi) quanto com o
    destino (já entregou). É `posse_tipo` que diz, e é ele que decide se o botão
    "Entregar" aparece.

    A CONTRARREFERÊNCIA vem junto quando existe: do ponto de vista do cidadão o
    percurso é um só — ele levou e o retorno voltou —, e obrigá-lo a procurar o
    retorno noutra lista seria partir em dois o que para ele é uma coisa só.
    """
    cpf = normalize_cpf(usuario["sub"])

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.protocolo, e.status, e.especialidade_destino,
                   e.finalidade, e.finalidade_texto, e.cid, e.cns_destino,
                   e.data_emissao, e.data_validade,
                   pr.nome AS prescritor_nome
              FROM encaminhamentos e
              LEFT JOIN prescritores pr ON pr.id = e.prescritor_id
              JOIN pacientes pa ON pa.id = e.paciente_id
             WHERE pa.cpf = ?
               AND e.tipo_emissao != 'fisico'
             ORDER BY e.id DESC
            """,
            (cpf,),
        ).fetchall()

        saida = []
        for row in rows:
            enc = dict(row)

            custodia = conn.execute(
                """
                SELECT detentor_tipo, detentor_id, transferida_em
                  FROM encaminhamento_custodia
                 WHERE encaminhamento_id = ? AND item_id IS NULL
                   AND encerrada_em IS NULL
                 ORDER BY id DESC LIMIT 1
                """,
                (enc["id"],),
            ).fetchone()

            # A data da consulta vive no ledger — o fato foi registrado lá.
            data_consulta = None
            for ev in conn.execute(
                """
                SELECT payload FROM encaminhamento_eventos
                 WHERE encaminhamento_id = ? AND tipo_evento = 'encaminhamento_agendado'
                 ORDER BY id DESC
                """,
                (enc["id"],),
            ).fetchall():
                try:
                    dados = json.loads(ev["payload"] or "{}")
                except (TypeError, ValueError):
                    continue
                if dados.get("data_agendamento"):
                    data_consulta = dados["data_agendamento"]
                    break

            cr = conn.execute(
                """
                SELECT protocolo, conteudo_clinico, data_emissao
                  FROM contrarreferencias
                 WHERE origem_encaminhamento_id = ?
                 ORDER BY id DESC LIMIT 1
                """,
                (enc["id"],),
            ).fetchone()

            saida.append({
                "protocolo":             enc["protocolo"],
                "status":                enc["status"],
                "especialidade_destino": enc["especialidade_destino"],
                "finalidade":            enc.get("finalidade"),
                "finalidade_texto":      enc.get("finalidade_texto"),
                "cid":                   enc.get("cid"),
                "cns_destino":           enc["cns_destino"],
                "prescritor_nome":       enc.get("prescritor_nome"),
                "data_emissao":          enc["data_emissao"],
                "data_validade":         enc["data_validade"],
                "data_consulta":         data_consulta,
                "posse_tipo":            custodia["detentor_tipo"] if custodia else None,
                "posse_desde":           custodia["transferida_em"] if custodia else None,
                "contrarreferencia": {
                    "protocolo":        cr["protocolo"],
                    "conteudo_clinico": cr["conteudo_clinico"],
                    "data_emissao":     cr["data_emissao"],
                } if cr else None,
            })

    terminais = {"encerrado", "cancelado", "expirado", "negado", "encerrado_fisico"}
    return {
        "ativos":    [e for e in saida if e["status"] not in terminais],
        "historico": [e for e in saida if e["status"] in terminais],
    }
