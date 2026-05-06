"""
auth/jwt.py
===========
Criação e verificação de tokens JWT do PicSaúde.

Access Token:  TTL curto (padrão 15 min) — usado em cada request
Refresh Token: TTL longo (padrão 24h)   — usado apenas para renovar o access

Payload do Access Token:
  sub   → identificador do usuário (CNS, CNPJ ou e-mail)
  role  → perfil (prescritor|dispensador|auditor|admin|cidadao)
  nome  → nome do usuário
  tipo  → "access"
  exp   → expiração (Unix timestamp)

Payload do Refresh Token:
  sub   → identificador
  tipo  → "refresh"
  exp   → expiração
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import JWT_ACCESS_TTL_MINUTES, JWT_ALGORITHM, JWT_REFRESH_TTL_MINUTES, JWT_SECRET

# ---------------------------------------------------------------------------
# Hash de senha
# ---------------------------------------------------------------------------

# argon2 é mais moderno que bcrypt e evita conflitos de versão com passlib 1.7 + bcrypt 4.x
_pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return _pwd_ctx.hash(senha)


def verificar_senha(senha: str, hash_: str) -> bool:
    return _pwd_ctx.verify(senha, hash_)


# ---------------------------------------------------------------------------
# Tokens JWT
# ---------------------------------------------------------------------------

def _agora_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def criar_access_token(
    sub: str,
    role: str,
    nome: str,
    extra: Optional[dict] = None,
) -> str:
    payload = {
        "sub":  sub,
        "role": role,
        "nome": nome,
        "tipo": "access",
        "exp":  _agora_utc() + timedelta(minutes=JWT_ACCESS_TTL_MINUTES),
        **(extra or {}),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def criar_refresh_token(sub: str) -> str:
    payload = {
        "sub":  sub,
        "tipo": "refresh",
        "exp":  _agora_utc() + timedelta(minutes=JWT_REFRESH_TTL_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verificar_access_token(token: str) -> dict:
    """
    Decodifica e valida um access token.
    Levanta ValueError em caso de token inválido, expirado ou de tipo errado.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"Token inválido: {exc}") from exc

    if payload.get("tipo") != "access":
        raise ValueError("Token não é do tipo 'access'.")

    return payload


def verificar_refresh_token(token: str) -> str:
    """
    Decodifica um refresh token e retorna o `sub`.
    Levanta ValueError se inválido ou expirado.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise ValueError(f"Refresh token inválido: {exc}") from exc

    if payload.get("tipo") != "refresh":
        raise ValueError("Token não é do tipo 'refresh'.")

    return payload["sub"]
