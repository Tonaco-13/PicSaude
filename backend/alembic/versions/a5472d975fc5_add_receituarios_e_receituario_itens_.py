"""add_receituarios_e_receituario_itens_ticket15

Revision ID: a5472d975fc5
Revises: 19d01716a86d
Create Date: 2026-04-24

Ticket 15 — Motor regulatório RDC 1.000/2025.

Adiciona duas tabelas:
  - receituarios          — um receituário regulatório por (prescrição × tipo)
  - receituario_itens     — associação (receituário ↔ prescricao_itens)

Não altera nenhuma tabela existente.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a5472d975fc5'
down_revision: Union[str, Sequence[str], None] = '19d01716a86d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("receituarios"):
        op.create_table(
            "receituarios",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("prescricao_id", sa.Integer(), nullable=False),
            sa.Column("tipo_receituario", sa.String(length=50), nullable=False),
            sa.Column("grupo_id", sa.String(length=50), nullable=False),
            sa.Column("grupo_nome", sa.String(length=100), nullable=False),
            sa.Column("assinatura_minima", sa.String(length=20), nullable=False),
            sa.Column(
                "assinatura_valida",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("vias", sa.Integer(), nullable=False),
            sa.Column(
                "retencao_farmacia",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column(
                "requer_sncr",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("numeracao_sncr", sa.String(length=50), nullable=True),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default="gerado",
            ),
            sa.Column("substituido_em", sa.DateTime(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["prescricao_id"],
                ["prescricoes.id"],
                name="fk_receituarios_prescricao_id",
            ),
            # Um receituário ATIVO por (prescricao × tipo). Regenerações
            # marcam os antigos com substituido_em (valor não NULL) e
            # permitem um novo ativo, preservando histórico.
            sa.UniqueConstraint(
                "prescricao_id",
                "tipo_receituario",
                "substituido_em",
                name="uq_receituario_prescricao_tipo_ativo",
            ),
        )
        op.create_index(
            "ix_receituarios_prescricao_id",
            "receituarios",
            ["prescricao_id"],
        )

    if not _table_exists("receituario_itens"):
        op.create_table(
            "receituario_itens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("receituario_id", sa.Integer(), nullable=False),
            sa.Column("prescricao_item_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.ForeignKeyConstraint(
                ["receituario_id"],
                ["receituarios.id"],
                name="fk_receituario_itens_receituario_id",
            ),
            sa.ForeignKeyConstraint(
                ["prescricao_item_id"],
                ["prescricao_itens.id"],
                name="fk_receituario_itens_prescricao_item_id",
            ),
            sa.UniqueConstraint(
                "receituario_id",
                "prescricao_item_id",
                name="uq_receituario_item_par",
            ),
        )
        op.create_index(
            "ix_receituario_itens_receituario_id",
            "receituario_itens",
            ["receituario_id"],
        )
        op.create_index(
            "ix_receituario_itens_prescricao_item_id",
            "receituario_itens",
            ["prescricao_item_id"],
        )


def downgrade() -> None:
    if _table_exists("receituario_itens"):
        op.drop_index(
            "ix_receituario_itens_prescricao_item_id",
            table_name="receituario_itens",
        )
        op.drop_index(
            "ix_receituario_itens_receituario_id",
            table_name="receituario_itens",
        )
        op.drop_table("receituario_itens")

    if _table_exists("receituarios"):
        op.drop_index("ix_receituarios_prescricao_id", table_name="receituarios")
        op.drop_table("receituarios")
