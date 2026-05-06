"""
routers/api_keys.py
===================
Gestão de API Keys institucionais (G4B).

Endpoints (role=admin):
  POST   /admin/api-keys              — criar API key para um org_id
  GET    /admin/api-keys              — listar API keys (sem expor chave)
  DELETE /admin/api-keys/{id}         — revogar API key (deleção lógica)

A chave bruta só é retornada uma vez, na criação.
Armazenada como sha256 — nunca recuperável.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.database_tx import get_tx

router = APIRouter(prefix="/admin/api-keys", tags=["api-keys"])


class ApiKeyIn(BaseModel):
    org_id: str
    nome:   str


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


# ---------------------------------------------------------------------------
# POST /admin/api-keys — criar API key
# ---------------------------------------------------------------------------

@router.post("", status_code=201, summary="Criar API key institucional")
def criar_api_key(body: ApiKeyIn, usuario=Depends(require_role("admin"))):
    org_id = body.org_id.strip()
    nome   = body.nome.strip()

    if not org_id:
        raise HTTPException(status_code=422, detail="org_id não pode ser vazio.")
    if not nome:
        raise HTTPException(status_code=422, detail="nome não pode ser vazio.")

    # Verificar que o org_id existe em prestadores
    with get_tx() as conn:
        prestador = conn.execute(
            "SELECT id FROM prestadores WHERE org_id = ? AND ativo = true", (org_id,)
        ).fetchone()
        if not prestador:
            raise HTTPException(
                status_code=404,
                detail=f"Prestador com org_id '{org_id}' não encontrado ou inativo.",
            )

        chave_bruta = secrets.token_urlsafe(32)
        chave_hash  = _hash_chave(chave_bruta)
        key_id      = str(uuid.uuid4())
        agora       = _agora()

        conn.execute(
            """
            INSERT INTO api_keys (id, org_id, nome, chave_hash, ativo, criado_em, criado_por)
            VALUES (?, ?, ?, ?, true, ?, ?)
            """,
            (key_id, org_id, nome, chave_hash, agora, usuario.get("sub")),
        )

    # chave_bruta retornada APENAS aqui — nunca mais recuperável
    return {
        "ok":        True,
        "id":        key_id,
        "org_id":    org_id,
        "nome":      nome,
        "chave":     chave_bruta,   # retornada uma única vez
        "criado_em": agora,
        "aviso":     "Guarde esta chave agora — ela não poderá ser recuperada.",
    }


# ---------------------------------------------------------------------------
# GET /admin/api-keys — listar API keys
# ---------------------------------------------------------------------------

@router.get("", summary="Listar API keys")
def listar_api_keys(_=Depends(require_role("admin"))):
    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT id, org_id, nome, ativo, criado_em, criado_por
            FROM api_keys
            ORDER BY criado_em DESC
            """
        ).fetchall()
    return {"api_keys": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# DELETE /admin/api-keys/{id} — revogar API key (deleção lógica)
# ---------------------------------------------------------------------------

@router.delete("/{key_id}", status_code=200, summary="Revogar API key")
def revogar_api_key(key_id: str, _=Depends(require_role("admin"))):
    with get_tx() as conn:
        row = conn.execute(
            "SELECT id, ativo FROM api_keys WHERE id = ?", (key_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="API key não encontrada.")
        if not row["ativo"]:
            raise HTTPException(status_code=409, detail="API key já está revogada.")

        conn.execute(
            "UPDATE api_keys SET ativo = false WHERE id = ?", (key_id,)
        )

    return {"ok": True, "id": key_id, "revogada": True}
