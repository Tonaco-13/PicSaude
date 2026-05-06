"""
auth/dependencies.py
====================
FastAPI dependencies para autenticação e autorização (RBAC).

Uso nos routers:

    from app.auth.dependencies import require_role
    from app.domain.roles import PERFIS_AUDITORIA

    # Perfil único:
    @router.post("/prescricoes")
    def criar(payload: PrescricaoIn, usuario=Depends(require_role("prescritor"))):
        ...

    # Múltiplos perfis:
    @router.get("/dispensacoes/{id}/comprovante")
    def comprovante(id: int, usuario=Depends(require_role("dispensador", "auditor", "admin"))):
        ...

    # Usar agrupamento do domain/roles.py:
    @router.get("/relatorios/dispensacoes.csv")
    def relatorio(usuario=Depends(require_role(*PERFIS_AUDITORIA))):
        ...

    # Para endpoints de adapter (aceita JWT ou API Key):
    @router.get("/eventos")
    def eventos(usuario=Depends(require_eventos_access)):
        ...
"""

from __future__ import annotations

import hashlib
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.auth.jwt import verificar_access_token
from app.database_tx import get_tx

# tokenUrl aponta para o endpoint de login — usado pelo /docs para o botão Authorize
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ---------------------------------------------------------------------------
# Dependency base: extrai e valida o token JWT
# ---------------------------------------------------------------------------

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Valida o Bearer token e retorna o payload do JWT.
    HTTP 401 se o token for inválido ou expirado.
    """
    try:
        return verificar_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ---------------------------------------------------------------------------
# Dependency de autorização: exige perfil específico
# ---------------------------------------------------------------------------

def require_role(*roles: str):
    """
    Factory de dependency que exige um dos perfis informados.

    HTTP 401 → token ausente ou inválido
    HTTP 403 → token válido mas perfil não autorizado
    """
    def _check(usuario: dict = Depends(get_current_user)) -> dict:
        if usuario.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Perfil '{usuario.get('role')}' não tem permissão para este endpoint. "
                    f"Perfis permitidos: {sorted(roles)}"
                ),
            )
        return usuario

    return _check


# ---------------------------------------------------------------------------
# G4B — Autenticação dupla: JWT ou API Key institucional
# ---------------------------------------------------------------------------

def _hash_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


def get_current_user_or_api_key(
    x_api_key:     Optional[str] = Header(None, alias="X-Api-Key"),
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Aceita dois mecanismos de autenticação:

    1. X-Api-Key: <chave>  → valida contra api_keys; retorna role=integrador + org_id
    2. Authorization: Bearer <token> → valida JWT normalmente

    Prioridade: X-Api-Key primeiro; Bearer como fallback.
    HTTP 401 se nenhum for fornecido ou ambos forem inválidos.
    """
    # ── Caminho 1: API Key institucional ──────────────────────────────────────
    if x_api_key:
        chave_hash = _hash_chave(x_api_key)
        with get_tx() as conn:
            row = conn.execute(
                "SELECT org_id, nome, ativo FROM api_keys WHERE chave_hash = ?",
                (chave_hash,),
            ).fetchone()

        if not row or not row["ativo"]:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key inválida ou revogada.",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        return {
            "role":    "integrador",
            "org_id":  row["org_id"],
            "sub":     f"apikey:{row['nome']}",
            "nome":    row["nome"],
        }

    # ── Caminho 2: Bearer token JWT ───────────────────────────────────────────
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        try:
            return verificar_access_token(token)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    # ── Nenhum mecanismo fornecido ────────────────────────────────────────────
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Autenticação obrigatória: forneça X-Api-Key ou Authorization: Bearer.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_eventos_access(usuario: dict = Depends(get_current_user_or_api_key)) -> dict:
    """
    Dependency para endpoints de eventos (G4B).
    Aceita role=admin ou role=integrador.

    - admin:      pode ver qualquer org_id (filtro opcional)
    - integrador: restrito ao org_id da API key (enforçado no endpoint)
    """
    if usuario.get("role") not in ("admin", "integrador"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Perfil '{usuario.get('role')}' não tem acesso à API de eventos. "
                "Requer: admin ou integrador."
            ),
        )
    return usuario
