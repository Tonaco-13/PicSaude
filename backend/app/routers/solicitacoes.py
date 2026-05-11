"""
routers/solicitacoes.py
=======================
Endpoints para o fluxo de solicitação de renovação de prescrição.

Ticket 13 — Solicitação de Renovação pelo Paciente + Caixa de Entrada do Prescritor

ROTAS
-----
POST /paciente/prescricoes/{proto}/solicitar-renovacao
    — Paciente solicita renovação de uma prescrição

GET  /prescritor/solicitacoes-renovacao
    — Prescritor lista solicitações pendentes e históricas

POST /prescritor/solicitacoes-renovacao/{id}/responder
    — Prescritor responde (atender ou recusar) uma solicitação
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.states import ESTADOS_TERMINAIS_PRESCRICAO
from app.instance import get_instance_id_conn

router = APIRouter()


# ---------------------------------------------------------------------------
# POST /paciente/prescricoes/{proto}/solicitar-renovacao
# ---------------------------------------------------------------------------

@router.post("/paciente/prescricoes/{proto}/solicitar-renovacao", status_code=201)
def solicitar_renovacao(proto: str, body: dict, usuario=Depends(require_role("paciente"))):
    """
    Paciente solicita renovação de uma prescrição.
    Prescrição deve pertencer ao paciente e estar em estado não-terminal.
    Só é permitida uma solicitação pendente por prescrição por vez.
    """
    cpf    = usuario["sub"]
    motivo = (body.get("motivo") or "").strip() or None

    agora = datetime.utcnow().isoformat()
    with get_tx() as conn:
        # Localiza a prescrição e verifica pertencimento
        row = conn.execute(
            """
            SELECT p.id, p.status, pr.cns AS cns_prescritor
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ? AND pa.cpf = ?
            """,
            (proto, cpf),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404,
                                detail="Prescrição não encontrada ou não pertence a este paciente")

        if row["status"] in ESTADOS_TERMINAIS_PRESCRICAO:
            raise HTTPException(
                status_code=409,
                detail=f"Prescrição em estado terminal ('{row['status']}') não pode ser renovada",
            )

        pid           = row["id"]
        cns_prescritor = row["cns_prescritor"]

        # Garante que não há solicitação pendente para a mesma prescrição
        pendente = conn.execute(
            """
            SELECT id FROM solicitacoes_renovacao
            WHERE protocolo_prescricao = ? AND cpf_paciente = ? AND status = 'pendente'
            """,
            (proto, cpf),
        ).fetchone()

        if pendente:
            raise HTTPException(
                status_code=409,
                detail="Já existe uma solicitação de renovação pendente para esta prescrição",
            )

        # Insere a solicitação
        conn.execute(
            """
            INSERT INTO solicitacoes_renovacao
                   (protocolo_prescricao, prescricao_id, cpf_paciente, cns_prescritor,
                    status, motivo, criado_em)
            VALUES (?, ?, ?, ?, 'pendente', ?, ?)
            """,
            (proto, pid, cpf, cns_prescritor, motivo, agora),
        )

        # Ticket 4D.1: corrige bug latente (schema divergente
        # `dados_json`/`criado_em` viola NOT NULL em ator_tipo).
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=pid,
            tipo_evento="renovacao_solicitada",
            instance_id=instance_id,
            payload={
                "cpf_paciente":   cpf,
                "cns_prescritor": cns_prescritor,
                "motivo":         motivo,
                "origem":         "cidadao_app",
            },
            ator_tipo="paciente",
            ator_id=cpf,
        )

    return {"ok": True, "protocolo": proto, "status": "pendente"}


# ---------------------------------------------------------------------------
# GET /prescritor/solicitacoes-renovacao
# ---------------------------------------------------------------------------

@router.get("/prescritor/solicitacoes-renovacao")
def listar_solicitacoes(usuario=Depends(require_role("prescritor"))):
    """
    Prescritor lista todas as solicitações de renovação direcionadas a ele.
    Retorna separado em 'pendentes' e 'historico'.
    """
    cns = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                sr.id,
                sr.protocolo_prescricao,
                sr.cpf_paciente,
                sr.status,
                sr.motivo,
                sr.criado_em,
                sr.respondido_em,
                sr.observacao_resposta,
                sr.nova_prescricao_protocolo,
                pa.nome AS paciente_nome
            FROM solicitacoes_renovacao sr
            LEFT JOIN pacientes pa ON pa.cpf = sr.cpf_paciente
            WHERE sr.cns_prescritor = ?
            ORDER BY sr.criado_em DESC
            """,
            (cns,),
        ).fetchall()

    pendentes  = []
    historico  = []

    for r in rows:
        item = {
            "id":                      r["id"],
            "protocolo_prescricao":    r["protocolo_prescricao"],
            "cpf_paciente":            r["cpf_paciente"],
            "paciente_nome":           r["paciente_nome"] or "Paciente",
            "status":                  r["status"],
            "motivo":                  r["motivo"],
            "criado_em":               r["criado_em"],
            "respondido_em":           r["respondido_em"],
            "observacao_resposta":     r["observacao_resposta"],
            "nova_prescricao_protocolo": r["nova_prescricao_protocolo"],
        }
        if r["status"] == "pendente":
            pendentes.append(item)
        else:
            historico.append(item)

    return {"pendentes": pendentes, "historico": historico}


# ---------------------------------------------------------------------------
# POST /prescritor/solicitacoes-renovacao/{id}/responder
# ---------------------------------------------------------------------------

@router.post("/prescritor/solicitacoes-renovacao/{solicitacao_id}/responder", status_code=200)
def responder_solicitacao(
    solicitacao_id: int,
    body: dict,
    usuario=Depends(require_role("prescritor")),
):
    """
    Prescritor responde a uma solicitação de renovação.

    body:
        decisao: "atender" | "recusar"   (obrigatório)
        observacao: str                   (opcional)
        nova_prescricao_protocolo: str    (obrigatório se decisao == "atender")
    """
    cns       = usuario["sub"]
    decisao   = (body.get("decisao") or "").strip()
    observacao = (body.get("observacao") or "").strip() or None
    nova_proto = (body.get("nova_prescricao_protocolo") or "").strip() or None

    if decisao not in ("atender", "recusar"):
        raise HTTPException(status_code=400,
                            detail="Campo 'decisao' deve ser 'atender' ou 'recusar'")

    if decisao == "atender" and not nova_proto:
        raise HTTPException(
            status_code=400,
            detail="Campo 'nova_prescricao_protocolo' é obrigatório quando decisao='atender'",
        )

    agora = datetime.utcnow().isoformat()
    novo_status = "atendida" if decisao == "atender" else "recusada"
    tipo_evento = "renovacao_atendida" if decisao == "atender" else "renovacao_recusada"

    with get_tx() as conn:
        sol = conn.execute(
            """
            SELECT id, protocolo_prescricao, prescricao_id, cpf_paciente, status
            FROM solicitacoes_renovacao
            WHERE id = ? AND cns_prescritor = ?
            """,
            (solicitacao_id, cns),
        ).fetchone()

        if not sol:
            raise HTTPException(status_code=404, detail="Solicitação não encontrada")

        if sol["status"] != "pendente":
            raise HTTPException(
                status_code=409,
                detail=f"Solicitação já foi respondida (status: {sol['status']})",
            )

        conn.execute(
            """
            UPDATE solicitacoes_renovacao
               SET status = ?,
                   respondido_em = ?,
                   respondido_por = ?,
                   observacao_resposta = ?,
                   nova_prescricao_protocolo = ?
             WHERE id = ?
            """,
            (novo_status, agora, cns, observacao, nova_proto, solicitacao_id),
        )

        # Ticket 4D.1: corrige bug latente (schema divergente). Eventos
        # `renovacao_atendida`/`renovacao_recusada` agora persistem com
        # ator_tipo='prescritor' e instance_id.
        if sol["prescricao_id"]:
            instance_id = get_instance_id_conn(conn)
            registrar_evento_ledger(
                conn,
                objeto_tipo="prescricao",
                objeto_id=sol["prescricao_id"],
                tipo_evento=tipo_evento,
                instance_id=instance_id,
                payload={
                    "cns_prescritor":            cns,
                    "cpf_paciente":              sol["cpf_paciente"],
                    "observacao":                observacao,
                    "nova_prescricao_protocolo": nova_proto,
                },
                ator_tipo="prescritor",
                ator_id=cns,
            )


    return {"ok": True, "id": solicitacao_id, "status": novo_status}
