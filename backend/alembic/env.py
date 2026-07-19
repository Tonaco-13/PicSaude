"""
alembic/env.py — Configuração de ambiente do Alembic para o PicSaúde.

Princípios:
  - A URL do banco vem EXCLUSIVAMENTE de DATABASE_URL (variável de ambiente).
  - Em dev (sem DATABASE_URL), usa SQLite — mesma lógica de database.py,
    importando o resolvedor de lá em vez de reimplementá-lo (dívida #98).
  - target_metadata aponta para Base.metadata (todos os models registrados).
  - render_as_batch=True para SQLite (emula ALTER TABLE); desativado em PG.

Qual banco o Alembic vai migrar
-------------------------------
  DATABASE_URL definida        → é ela, sempre. Produção nunca entra no ramo
                                 SQLite abaixo, então nada aqui a alcança.
  PICSAUDE_DEMO_MODE=true      → PIX_SAUDE_DEMO_DB (banco demo)
  PIX_SAUDE_DB=<path>          → esse path
  nada disso                   → data/pix_saude_pe.db (dev)

Exemplos:
  PICSAUDE_DEMO_MODE=true alembic upgrade head   # migra o banco demo
  PIX_SAUDE_DB=/tmp/x.db      alembic upgrade head   # migra /tmp/x.db

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
from app.database import Base, _resolve_sqlite_db_path

# ---------------------------------------------------------------------------
# Configuração do alembic.ini
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Resolve DATABASE_URL — mesma lógica de database.py, sem duplicar código
# ---------------------------------------------------------------------------
# Dívida #98. Este bloco PROMETIA "sem duplicar código" e logo abaixo cravava
# "pix_saude_pe.db" — por 22 migrações. Duas consequências medidas:
#
#   - `PICSAUDE_DEMO_MODE=true alembic upgrade head` migrava o banco de DEV.
#     Por isso o banco demo nunca recebia migração: não havia como mandá-la
#     para ele. A reconstrução virava receita manual (init_tables + seed).
#   - `PIX_SAUDE_DB=/tmp/x.db alembic upgrade head` também migrava o de dev,
#     em silêncio. Quem rodava achando que mexia num banco efêmero mutava o
#     dev real — aconteceu no TICKET-LEDGER-TRIGGERS-MIGRACAO.
#
# Agora o resolvedor vem de `app.database`, que honra as duas variáveis. O
# código passa a tornar o comentário verdade.
#
# Precedência (a de database.py, não uma nova): DATABASE_URL vence sempre.
# É ela que protege produção — prod a define e nunca chega ao ramo SQLite,
# então este caminho é prod-safe por construção.
_DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Render entrega `postgres://`; SQLAlchemy 1.4+ exige `postgresql://` (idempotente).
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = "postgresql://" + _DATABASE_URL[len("postgres://"):]

if not _DATABASE_URL:
    # Sem DATABASE_URL: SQLite. QUAL arquivo é decisão do resolvedor de
    # database.py — demo (PIX_SAUDE_DEMO_DB) ou dev (DB_PATH/PIX_SAUDE_DB).
    # `abspath` só normaliza os ".." do path default e deixa a mensagem
    # legível; para path relativo o resultado é o mesmo que o app faria,
    # porque ambos resolvem contra o cwd.
    _db_path = os.path.abspath(_resolve_sqlite_db_path())
    _DATABASE_URL = f"sqlite:///{_db_path}"
    _modo = "demo" if os.getenv("PICSAUDE_DEMO_MODE", "").lower() == "true" else "dev"
    print(
        f"[alembic/env.py] DATABASE_URL não configurada — "
        f"usando SQLite {_modo}: {_db_path}"
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
