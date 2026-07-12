from __future__ import annotations

import logging
import os
import re
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resolução de path SQLite — respeita PICSAUDE_DEMO_MODE (TICKET-6 P1#1)
# ---------------------------------------------------------------------------
# Usado pelo engine SQLAlchemy E pelo get_conn() — garante isolamento real
# do DB demo vs prod. Sem isso, get_conn() importaria DB_PATH direto e
# escreveria/leria no DB de produção mesmo em modo demo.

def _resolve_sqlite_db_path() -> str:
    """
    Retorna o path do arquivo SQLite a usar.
    Em DEMO_MODE: PIX_SAUDE_DEMO_DB. Caso contrário: DB_PATH.
    """
    from app.config import DB_PATH, PICSAUDE_DEMO_MODE, PIX_SAUDE_DEMO_DB
    return PIX_SAUDE_DEMO_DB if PICSAUDE_DEMO_MODE else DB_PATH


# ---------------------------------------------------------------------------
# Configuração — DATABASE_URL (PostgreSQL) com fallback SQLite para dev
# ---------------------------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Render (e alguns PaaS) entregam a connection string como `postgres://`,
# esquema que o SQLAlchemy 1.4+ rejeita ("Can't load plugin: ...:postgres").
# Normaliza para `postgresql://` — idempotente para URLs já corretas.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

_USE_SQLITE = not DATABASE_URL

if _USE_SQLITE:
    _resolved_db_path = _resolve_sqlite_db_path()
    DATABASE_URL = f"sqlite:///{_resolved_db_path}"
    from app.config import PICSAUDE_DEMO_MODE as _DEMO
    logger.warning(
        "DATABASE_URL não configurada — fallback para SQLite (%s, path=%s). "
        "Para produção: export DATABASE_URL=postgresql://user:pass@host:5432/picsaude",
        "modo demo" if _DEMO else "modo dev",
        _resolved_db_path,
    )
else:
    # Loga URL sem credenciais
    _safe_url = re.sub(r"://[^:@]+:[^@]+@", "://<credenciais>@", DATABASE_URL)
    logger.info("PostgreSQL configurado: %s", _safe_url)

# ---------------------------------------------------------------------------
# SQLAlchemy engine — ORM + pool de conexões
# ---------------------------------------------------------------------------

if _USE_SQLITE:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_pre_ping=True,  # descarta conexões mortas antes de usar
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------------------------
# Camada de compatibilidade — wrapper psycopg2 com interface sqlite3-like
#
# Objetivo: manter todos os routers existentes sem alteração, traduzindo:
#   - Placeholders:   ?             →  %s
#   - UPSERT:         INSERT OR IGNORE INTO  →  INSERT INTO … ON CONFLICT DO NOTHING
#   - lastrowid:      cursor.lastrowid  →  capturado via RETURNING id
#   - Rows:           sqlite3.Row        →  dict acessível por row["col"]
# ---------------------------------------------------------------------------

_RE_INSERT_OR_IGNORE = re.compile(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", re.IGNORECASE)
_RE_INSERT_OR_REPLACE = re.compile(r"\bINSERT\s+OR\s+REPLACE\s+INTO\b", re.IGNORECASE)
_RE_IS_INSERT = re.compile(r"^\s*INSERT\b", re.IGNORECASE)
_RE_HAS_RETURNING = re.compile(r"\bRETURNING\b", re.IGNORECASE)


def _pg_translate(sql: str) -> tuple[str, bool]:
    """Traduz SQL SQLite → PostgreSQL.

    Retorna (pg_sql, on_conflict) onde on_conflict indica que a cláusula
    ON CONFLICT já foi adicionada (não acrescentar RETURNING nesse caso).
    """
    on_conflict = False

    if _RE_INSERT_OR_IGNORE.search(sql):
        sql = _RE_INSERT_OR_IGNORE.sub("INSERT INTO", sql)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
        on_conflict = True
    elif _RE_INSERT_OR_REPLACE.search(sql):
        # Tratado como insert ignorando conflito; routers específicos devem
        # fornecer ON CONFLICT … DO UPDATE se precisarem do comportamento completo.
        sql = _RE_INSERT_OR_REPLACE.sub("INSERT INTO", sql)
        on_conflict = True

    # Substituir placeholders SQLite → psycopg2
    sql = sql.replace("?", "%s")
    return sql, on_conflict


class _PgRow(dict):
    """Row dict compatível com sqlite3.Row — suporta row["col"] E row[0] (índice inteiro)."""

    def __init__(self, data: dict) -> None:
        super().__init__(data)
        self._cols = list(data.keys())

    def __getitem__(self, key):
        if isinstance(key, int):
            return super().__getitem__(self._cols[key])
        return super().__getitem__(key)


class _PgCursor:
    """Cursor compatível com sqlite3 — suporta lastrowid, fetchone, fetchall."""

    __slots__ = ("lastrowid", "rowcount", "_rows", "_pos")

    def __init__(self) -> None:
        self.lastrowid: int | None = None
        self.rowcount: int = -1
        self._rows: list[_PgRow] = []
        self._pos: int = 0

    def fetchone(self) -> _PgRow | None:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self) -> list[_PgRow]:
        rows = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rows


class _PgTransaction:
    """Objeto de transação retornado por conn.begin() para compatibilidade."""

    def __init__(self, conn: "_PgConnection") -> None:
        self._conn = conn

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()


class _PgConnection:
    """Conexão psycopg2 com interface compatível com sqlite3.

    Uso nos routers (idêntico ao uso atual com sqlite3):

        conn = get_conn()
        try:
            row  = conn.execute("SELECT id FROM tabela WHERE cpf = ?", (cpf,)).fetchone()
            cur  = conn.execute("INSERT INTO tabela (...) VALUES (?)", (val,))
            novo_id = cur.lastrowid
            conn.commit()
        finally:
            conn.close()
    """

    def __init__(self, raw_conn: Any) -> None:
        self._raw = raw_conn

    def execute(self, sql: str, params: Any = ()) -> _PgCursor:
        from psycopg2.extras import RealDictCursor

        pg_sql, on_conflict = _pg_translate(sql)
        is_insert = bool(_RE_IS_INSERT.match(pg_sql))
        has_returning = bool(_RE_HAS_RETURNING.search(pg_sql))

        raw_cur = self._raw.cursor(cursor_factory=RealDictCursor)
        result = _PgCursor()

        if is_insert and not has_returning:
            # Adiciona RETURNING id para capturar lastrowid (comportamento sqlite3)
            # ON CONFLICT DO NOTHING + RETURNING id → retorna vazio se houve conflito
            returning_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
            raw_cur.execute(returning_sql, params or ())
            if raw_cur.description:
                row = raw_cur.fetchone()
                if row and "id" in row:
                    result.lastrowid = row["id"]
        else:
            raw_cur.execute(pg_sql, params or ())
            if raw_cur.description:
                result._rows = [_PgRow(dict(r)) for r in (raw_cur.fetchall() or [])]

        result.rowcount = raw_cur.rowcount
        return result

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()  # devolve ao pool do SQLAlchemy

    def begin(self) -> _PgTransaction:
        """Compatibilidade com padrão conn.begin() / trans.commit()."""
        return _PgTransaction(self)

    def __enter__(self) -> "_PgConnection":
        return self

    def __exit__(self, exc_type: Any, *_: Any) -> None:
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ---------------------------------------------------------------------------
# row_lock_suffix() — serialização de concorrentes (TICKET-CORE-R2 §3.1)
# ---------------------------------------------------------------------------

def row_lock_suffix(of: str | None = None) -> str:
    """Sufixo de lock de linha para serializar transações concorrentes.

    Enforcement de §2a R2 (CLAUDE.md): mutação de objeto sanitário é idempotente
    e protegida contra duplo-submit. Anexado ao `SELECT` que lê a linha antes da
    leitura-então-escrita (saldo), a transação concorrente bloqueia até a primeira
    commitar — então relê o saldo já atualizado e a checagem existente rejeita o
    excedente, em vez de gravar um segundo movimento.

    - **PostgreSQL:** ``FOR UPDATE`` (ou ``FOR UPDATE OF <alias>`` para travar só
      uma tabela do JOIN, evitando lock desnecessário nas demais).
    - **SQLite:** ``''`` — a transação já serializa writes (lock global de escrita)
      e ``FOR UPDATE`` é erro de sintaxe. O efeito real do lock só existe na PG;
      por isso o caminho de concorrência é testado contra PG.
    """
    if _USE_SQLITE:
        return ""
    return f" FOR UPDATE OF {of}" if of else " FOR UPDATE"


# ---------------------------------------------------------------------------
# get_conn() — ponto único de acesso ao banco para raw SQL
# ---------------------------------------------------------------------------

def get_conn():
    """Retorna uma conexão compatível com o código raw SQL existente.

    PostgreSQL: conexão do pool SQLAlchemy envolta no wrapper _PgConnection.
    SQLite (fallback dev): sqlite3 nativo com PRAGMAs de concorrência.
    """
    if _USE_SQLITE:
        import sqlite3

        # P1#1 TICKET-6 — usar helper compartilhado para honrar DEMO_MODE.
        _sqlite_path = _resolve_sqlite_db_path()

        if not os.path.exists(_sqlite_path):
            raise RuntimeError(f"SQLite DB não encontrado: {_sqlite_path}")
        conn = sqlite3.connect(_sqlite_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    raw = engine.raw_connection()
    raw.autocommit = False
    return _PgConnection(raw)


# ---------------------------------------------------------------------------
# init_db() — criação de tabelas via ORM (usado em init_tables.py)
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Cria todas as tabelas definidas nos models no banco configurado.

    Uso manual:
        from app.database import init_db
        init_db()
    """
    import app.models  # noqa: F401 — registra models no Base.metadata

    Base.metadata.create_all(engine)
