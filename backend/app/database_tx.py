"""
database_tx.py
==============
Context manager centralizado para transações simples.

Uso:
    with get_tx() as conn:
        conn.execute(...)

Comportamento:
    - Sucesso: commit automático ao sair do bloco
    - Exceção (incluindo HTTPException): rollback automático + re-raise
    - Sempre fecha a conexão via finally

NÃO usar em endpoints com múltiplos commits intencionais
(ex: tokens.py::resolver_token — mantém padrão manual).
"""
from __future__ import annotations

from contextlib import contextmanager

from app.database import get_conn


@contextmanager
def get_tx():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
