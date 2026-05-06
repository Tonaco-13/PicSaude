"""
eventos.py
==========
Event Publishing Layer — G4A + G4B.

Endpoints:
  GET  /eventos                — poll de eventos pendentes (ou todos)
  POST /eventos/{id}/ack       — marca evento como consumido

Segurança (G4B):
  Aceita role "admin" (JWT) ou role "integrador" (API Key institucional).
  Integrador: org_id enforçado pela API key — não pode acessar outros orgs.
  Admin: org_id opcional (útil para diagnóstico).

Guardrail de escopo:
  Integrador → org_id fixado na API key, query param ignorado.
  Admin      → usa org_id do query param se fornecido.

Classificação de mudança: module (G4A/G4B)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_eventos_access
from app.database_tx import get_tx

router = APIRouter(prefix="/eventos", tags=["eventos"])

_LIMITE_MAXIMO = 500


# ---------------------------------------------------------------------------
# GET /eventos
# ---------------------------------------------------------------------------

@router.get("")
def listar_eventos(
    org_id:              Optional[str]  = Query(None,  description="Filtro por org_id (ignorado para integrador — usa org_id da API key)"),
    desde:               Optional[str]  = Query(None,  description="ISO 8601 — retorna eventos após este timestamp"),
    limite:              int             = Query(100,   ge=1, le=_LIMITE_MAXIMO),
    incluir_consumidos:  bool            = Query(False, description="Inclui eventos já consumidos (publicado=1)"),
    objeto_tipo:         Optional[str]   = Query(None,  description="Filtro por tipo de objeto: prescricao, pedido_exame, agendamento, laudo"),
    usuario:             dict            = Depends(require_eventos_access),
):
    """
    Retorna eventos do outbox para consumo externo.

    Ordem: criado_em ASC (para garantir processamento em sequência).
    Cursor: use o `proximo_cursor` da resposta como `desde` na próxima chamada.

    Uso típico de adapter:
        1. GET /eventos?org_id=X&desde=<ultimo_cursor>
        2. Processar eventos retornados
        3. POST /eventos/{id}/ack para cada evento processado
        4. Repetir com `proximo_cursor`

    Segurança (G4B):
        - admin:      org_id do query param é opcional
        - integrador: org_id é fixado pela API key (query param ignorado)
    """
    # Integrador: org_id enforçado pela credencial — não pode acessar outros orgs
    if usuario.get("role") == "integrador":
        org_id_efetivo = usuario["org_id"]
    else:
        org_id_efetivo = org_id  # admin: usa query param (pode ser None)

    with get_tx() as conn:
        conds  = []
        params = []

        if not incluir_consumidos:
            conds.append("publicado = 0")

        if org_id_efetivo:
            conds.append("org_id = ?")
            params.append(org_id_efetivo)

        if desde:
            conds.append("criado_em > ?")
            params.append(desde)

        if objeto_tipo:
            conds.append("objeto_tipo = ?")
            params.append(objeto_tipo)

        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        params.append(limite)

        rows = conn.execute(
            f"""
            SELECT id, tipo_evento, objeto_tipo, objeto_id,
                   payload, org_id, unidade_id, publicado,
                   criado_em, publicado_em
            FROM eventos_publicacao
            {where}
            ORDER BY criado_em ASC
            LIMIT ?
            """,
            params,
        ).fetchall()

    eventos = []
    for r in rows:
        payload_raw = r["payload"]
        try:
            payload_obj = json.loads(payload_raw)
        except Exception:
            payload_obj = payload_raw

        eventos.append({
            "id":          r["id"],
            "tipo_evento": r["tipo_evento"],
            "objeto": {
                "tipo": r["objeto_tipo"],
                "id":   r["objeto_id"],
            },
            "org_id":      r["org_id"],
            "unidade_id":  r["unidade_id"],
            "timestamp":   r["criado_em"],
            "publicado":   bool(r["publicado"]),
            "publicado_em": r["publicado_em"],
            "payload":     payload_obj,
        })

    proximo_cursor = eventos[-1]["timestamp"] if eventos else None

    return {
        "eventos":         eventos,
        "total":           len(eventos),
        "proximo_cursor":  proximo_cursor,
    }


# ---------------------------------------------------------------------------
# POST /eventos/{id}/ack
# ---------------------------------------------------------------------------

@router.post("/{evento_id}/ack")
def ack_evento(
    evento_id: str,
    usuario: dict = Depends(require_eventos_access),
):
    """
    Marca um evento como consumido (publicado = 1).

    Idempotente: ack duplo retorna 200 sem erro.
    O evento permanece na tabela para auditoria — sem DELETE.
    """
    agora = datetime.now(timezone.utc).isoformat()
    with get_tx() as conn:
        row = conn.execute(
            "SELECT id, org_id, publicado, publicado_em FROM eventos_publicacao WHERE id = ?",
            (evento_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Evento '{evento_id}' não encontrado.")

        # Integrador não pode dar ack em eventos de outro org_id
        if usuario.get("role") == "integrador" and row["org_id"] != usuario.get("org_id"):
            raise HTTPException(
                status_code=403,
                detail="Sem permissão para dar ack neste evento.",
            )

        if row["publicado"] == 0:
            conn.execute(
                """
                UPDATE eventos_publicacao
                SET publicado = 1, publicado_em = ?, tentativas = tentativas + 1
                WHERE id = ?
                """,
                (agora, evento_id),
            )

    # Idempotente: já estava acked — retorna o publicado_em original
    if row["publicado"] == 0:
        return {"ok": True, "publicado_em": agora}
    return {"ok": True, "publicado_em": row["publicado_em"]}
