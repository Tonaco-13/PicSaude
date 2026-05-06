"""
alembic/env.py — Configuração de ambiente do Alembic para o PicSaúde.

Princípios:
  - A URL do banco vem EXCLUSIVAMENTE de DATABASE_URL (variável de ambiente).
  - Em dev (sem DATABASE_URL), usa SQLite — mesma lógica de database.py.
  - target_metadata aponta para Base.metadata (todos os models registrados).
  - render_as_batch=True para SQLite (emula ALTER TABLE); desativado em PG.

Como usar:
  cd backend

  # Aplicar todas as migrations pendentes
  alembic upgrade head

  # Marcar banco já existente como estando na versão X (sem rodar a migration)
  alembic stamp <revision_id>

  # Ver histórico de migrations
  alembic history

  # Ver revisão atual no banco
  alembic current

  # Gerar SQL sem aplicar (dry run)
  alembic upgrade head --sql
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Adiciona backend/ ao sys.path para que os imports de app.* funcionem
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Importa models — TODOS devem estar registrados em Base.metadata antes de
# qualquer operação de autogenerate ou create_all.
# ---------------------------------------------------------------------------
import app.models  # noqa: F401 — registra todos os models no Base.metadata
from app.database import Base

# ---------------------------------------------------------------------------
# Configuração do alembic.ini
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL — mesma lógica de database.py, sem duplicar código
# ---------------------------------------------------------------------------
_DATABASE_URL: str = os.getenv("DATABASE_URL", "")

if not _DATABASE_URL:
    # Dev: fallback para SQLite (banco de desenvolvimento local)
    _db_path = os.path.abspath(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..",
            "data",
            "pix_saude_pe.db",
        )
    )
    _DATABASE_URL = f"sqlite:///{_db_path}"
    print(
        f"[alembic/env.py] DATABASE_URL não configurada — "
        f"usando SQLite dev: {_db_path}"
    )

# Injeta a URL resolvida na config do Alembic
# (o placeholder do alembic.ini foi intencionalmente deixado comentado)
config.set_main_option("sqlalchemy.url", _DATABASE_URL)

# ---------------------------------------------------------------------------
# Metadata alvo — Alembic usa para autogenerate e validação de schema
# ---------------------------------------------------------------------------
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helpers de contexto
# ---------------------------------------------------------------------------

def _is_sqlite() -> bool:
    return _DATABASE_URL.startswith("sqlite")


def _get_connect_args() -> dict:
    if _is_sqlite():
        return {"check_same_thread": False}
    return {}


def run_migrations_offline() -> None:
    """
    Gera SQL sem conectar ao banco (modo 'dry run').
    Útil para revisar o SQL antes de aplicar em produção.
    Execute com: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_is_sqlite(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Aplica migrations conectando ao banco real.
    SQLite usa StaticPool; PostgreSQL usa NullPool (conexão direta por migration).
    """
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _DATABASE_URL

    # SQLite não precisa de pool; PostgreSQL usa NullPool para migrations
    pool_class = pool.StaticPool if _is_sqlite() else pool.NullPool

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool_class,
        connect_args=_get_connect_args(),
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # render_as_batch: permite ALTER TABLE emulado no SQLite
            # No PostgreSQL, ALTER TABLE nativo é usado diretamente.
            render_as_batch=_is_sqlite(),
            # compare_type: autogenerate detecta mudanças de tipo de coluna
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
