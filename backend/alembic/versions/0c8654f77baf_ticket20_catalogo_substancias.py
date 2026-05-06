"""ticket20_catalogo_substancias

Cria a tabela `catalogo_substancias` (Ticket 20).

Propósito
---------
Catálogo regulatório local indexado por DCB. Oráculo de validação
para confrontar a classificação declarada pelo prescritor
(`prescricao_itens.classe_controle` / `tipo_retencao`) contra a
classificação publicada pela Anvisa.

Decisão sobre busca por similaridade
------------------------------------
A primeira proposta era usar `pg_trgm` (GIN index com gin_trgm_ops)
para autocomplete por similaridade. Decisão: usar busca por prefixo +
ILIKE com índice btree convencional. Justificativas:

  1. pg_trgm não está disponível no pgserver embarcado deste projeto.
  2. Volume esperado é 50–200 substâncias — ILIKE+btree é suficiente.
  3. Reduz dependência de extensão.

Quando a base crescer (>1000 substâncias) ou pg_trgm estiver
disponível, criar GIN index em uma migration adicional.

Revision ID: 0c8654f77baf
Revises: c3d7a8b9e1f2
Create Date: 2026-04-29
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '0c8654f77baf'
down_revision: Union[str, Sequence[str], None] = 'c3d7a8b9e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table)


def upgrade() -> None:
    if _table_exists("catalogo_substancias"):
        return

    op.create_table(
        "catalogo_substancias",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dcb", sa.String(200), nullable=False),
        sa.Column("dcb_normalizada", sa.String(250), nullable=False),
        sa.Column("dcb_display", sa.String(200), nullable=False),
        sa.Column("classe_controle", sa.String(10), nullable=True),
        sa.Column("tipo_retencao", sa.String(30), nullable=True),
        sa.Column("fonte", sa.String(100), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column(
            "ativo", sa.Boolean(), nullable=False, server_default=sa.true(),
        ),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "dcb_normalizada", name="uq_catalogo_dcb_normalizada",
        ),
    )

    op.create_index(
        "ix_catalogo_dcb_normalizada",
        "catalogo_substancias",
        ["dcb_normalizada"],
    )
    op.create_index(
        "ix_catalogo_classificacao",
        "catalogo_substancias",
        ["classe_controle", "tipo_retencao", "ativo"],
    )


def downgrade() -> None:
    if not _table_exists("catalogo_substancias"):
        return
    op.drop_index("ix_catalogo_classificacao", "catalogo_substancias")
    op.drop_index("ix_catalogo_dcb_normalizada", "catalogo_substancias")
    op.drop_table("catalogo_substancias")
