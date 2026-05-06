"""add_api_keys_and_estabelecimentos_proprios

Fecha os gaps de schema identificados no Ticket 7 e documentados no Ticket 8.

As tabelas api_keys e estabelecimentos_proprios existiam como models ORM e
eram criadas por init_tables.py, mas estavam ausentes do baseline Alembic
(revision 037d38d98806). Esta migration formaliza essas tabelas no histórico
de migrations, tornando init_tables.py desnecessário para criá-las.

Tabelas adicionadas:
  - api_keys               API keys institucionais para autenticação G4B
  - estabelecimentos_proprios  Farmácias/unidades próprias cadastradas

Idempotência:
  Cada create_table é guardado por _table_exists() para não falhar se a
  tabela já existir (ex: SQLite de dev criado previamente por init_tables.py).

Revision ID: f8d8f30ed04e
Revises: 8352ec7860f8
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'f8d8f30ed04e'
down_revision: Union[str, Sequence[str], None] = '8352ec7860f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def upgrade() -> None:
    """Cria api_keys e estabelecimentos_proprios (idempotente)."""

    # ------------------------------------------------------------------
    # api_keys — API keys institucionais (G4B)
    # Fonte: backend/app/models/api_key.py
    # ------------------------------------------------------------------
    if not _table_exists("api_keys"):
        op.create_table(
            "api_keys",
            sa.Column("id",         sa.Text(),    nullable=False),
            sa.Column("org_id",     sa.Text(),    nullable=False),
            sa.Column("nome",       sa.Text(),    nullable=False),
            sa.Column("chave_hash", sa.Text(),    nullable=False),
            sa.Column("ativo",      sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("criado_em",  sa.Text(),    nullable=False),
            sa.Column("criado_por", sa.Text(),    nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("chave_hash"),
        )

    # ------------------------------------------------------------------
    # estabelecimentos_proprios — farmácias/unidades próprias
    # Fonte: backend/app/models/estabelecimento.py
    # ------------------------------------------------------------------
    if not _table_exists("estabelecimentos_proprios"):
        op.create_table(
            "estabelecimentos_proprios",
            sa.Column("id",                 sa.Integer(),  nullable=False),
            sa.Column("cnpj",               sa.String(),   nullable=False),
            sa.Column("nome_fantasia",      sa.String(),   nullable=False),
            sa.Column("razao_social",       sa.String(),   nullable=True),
            sa.Column("telefone_vinculado", sa.String(),   nullable=True),
            sa.Column("ativo",              sa.Boolean(),  nullable=False, server_default=sa.text("true")),
            sa.Column("created_at",         sa.DateTime(), nullable=False),
            sa.Column("updated_at",         sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("cnpj"),
        )
        op.create_index("ix_estabelecimentos_proprios_id",   "estabelecimentos_proprios", ["id"],   unique=False)
        op.create_index("ix_estabelecimentos_proprios_cnpj", "estabelecimentos_proprios", ["cnpj"], unique=True)


def downgrade() -> None:
    """Remove api_keys e estabelecimentos_proprios (idempotente)."""

    if _table_exists("estabelecimentos_proprios"):
        op.drop_index("ix_estabelecimentos_proprios_cnpj", table_name="estabelecimentos_proprios")
        op.drop_index("ix_estabelecimentos_proprios_id",   table_name="estabelecimentos_proprios")
        op.drop_table("estabelecimentos_proprios")

    if _table_exists("api_keys"):
        op.drop_table("api_keys")
