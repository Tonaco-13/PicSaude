"""
lista_espera.py — armazenamento da lista de espera do "em obras" (entrar.html).

Despacho "Lista de espera direta" (`module`) — a base sobrevive ao reset
diário da vitrine (`scripts/reset_demo_db.py`: `DROP SCHEMA "public" CASCADE`
em PostgreSQL, remoção do arquivo único em SQLite). Por desenho, esta base
NUNCA está no raio de alcance de nenhum dos dois:

  - **PostgreSQL**: schema PRÓPRIO (`lista_espera`), nunca `public` — o reset
    só dropa `current_schema()` (normalmente `public`); um schema diferente
    nunca entra no `CASCADE`. Migração: `598f8273be73`.
  - **SQLite** (dev/demo local sem `DATABASE_URL`): arquivo PRÓPRIO
    (`data/lista_espera.db`), fora do path que `_reset_sqlite()` apaga
    (`PIX_SAUDE_DEMO_DB`/`DB_PATH`). Bootstrap idempotente aqui mesmo — não
    é tabela do Alembic (SQLite não tem `CREATE SCHEMA`).

Sem GET público (enumeração é vazamento — §5 do despacho): este módulo não
expõe leitura nenhuma para roteador algum. `contar_inscricoes()` existe só
para script manual/teste — nunca importado por um router.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.database import DATABASE_URL

logger = logging.getLogger(__name__)

_USE_POSTGRES = DATABASE_URL.startswith("postgresql")

_SQLITE_PATH = Path(__file__).resolve().parents[3] / "data" / "lista_espera.db"

_DDL_SQLITE = """
CREATE TABLE IF NOT EXISTS inscricoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT NOT NULL,
    origem TEXT,
    created_at TEXT NOT NULL
)
"""

# "Caps" (despacho §4) — backstop de volume total, independente do rate
# limit por IP: um ataque distribuído por muitos IPs ainda respeitaria o
# limite por IP mas poderia encher a base. Limite generoso — não é o
# controle principal (esse é o rate limit), é a rede de segurança.
_MAX_INSCRICOES = 100_000


class ListaEspereCheia(Exception):
    """Backstop de volume total atingido — ver `_MAX_INSCRICOES`."""


def _conn_sqlite() -> sqlite3.Connection:
    _SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_SQLITE_PATH), timeout=30)
    conn.execute(_DDL_SQLITE)
    return conn


def contar_inscricoes() -> int:
    """Só para script manual/teste — NUNCA importado por um router (sem GET
    público, §5 do despacho: enumeração é vazamento)."""
    if _USE_POSTGRES:
        from sqlalchemy import text

        from app.database import engine

        with engine.connect() as conn:
            return conn.execute(
                text("SELECT COUNT(*) FROM lista_espera.inscricoes")
            ).scalar()

    conn = _conn_sqlite()
    try:
        return conn.execute("SELECT COUNT(*) FROM inscricoes").fetchone()[0]
    finally:
        conn.close()


def registrar_inscricao(nome: str, email: str, origem: str | None) -> None:
    """Grava uma inscrição. Sem retorno de id — ninguém consulta por id
    (sem GET público)."""
    if contar_inscricoes() >= _MAX_INSCRICOES:
        raise ListaEspereCheia(
            f"lista de espera atingiu o backstop de {_MAX_INSCRICOES} inscrições"
        )

    agora = datetime.now(timezone.utc).isoformat()

    if _USE_POSTGRES:
        from sqlalchemy import text

        from app.database import engine

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO lista_espera.inscricoes "
                    "(nome, email, origem, created_at) "
                    "VALUES (:nome, :email, :origem, :created_at)"
                ),
                {"nome": nome, "email": email, "origem": origem, "created_at": agora},
            )
        return

    conn = _conn_sqlite()
    try:
        conn.execute(
            "INSERT INTO inscricoes (nome, email, origem, created_at) "
            "VALUES (?, ?, ?, ?)",
            (nome, email, origem, agora),
        )
        conn.commit()
    finally:
        conn.close()
