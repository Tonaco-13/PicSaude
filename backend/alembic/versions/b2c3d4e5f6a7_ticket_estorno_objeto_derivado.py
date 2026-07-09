"""T2 — estorno como objeto sanitário derivado (estornos)

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-09

TICKET-ESTORNO-OBJETO-DERIVADO.md (martelo Fabiano 2026-06-15):
o estorno é um objeto sanitário DERIVADO e IMUTÁVEL (padrão origem_*_id),
não uma transição de estado que muta o item. A `dispensacoes` original
permanece intocada. Saldo efetivo do item = Σ dispensado − Σ estornado.

prescricao_item_id e prescricao_id são denormalizados (deriváveis de
origem_dispensacao_id) para manter as queries de saldo/status sem JOIN;
são imutáveis, gravados uma vez na criação.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("estornos"):
        op.create_table(
            "estornos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("protocolo", sa.String(length=50), nullable=False),
            sa.Column("origem_dispensacao_id", sa.Integer(), nullable=False),
            sa.Column("prescricao_item_id", sa.Integer(), nullable=False),
            sa.Column("prescricao_id", sa.Integer(), nullable=False),
            sa.Column("cnpj_estabelecimento", sa.String(length=14), nullable=False),
            sa.Column("paciente_id", sa.Integer(), nullable=True),
            sa.Column("autor_tipo", sa.String(length=40), nullable=False),
            sa.Column("autor_id", sa.String(length=100), nullable=True),
            sa.Column("quantidade_estornada", sa.Integer(), nullable=False),
            sa.Column("motivo", sa.String(length=40), nullable=False),
            sa.Column("assinatura_hash", sa.String(length=64), nullable=True),
            sa.Column("data_emissao", sa.DateTime(), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["origem_dispensacao_id"], ["dispensacoes.id"]),
            sa.ForeignKeyConstraint(["prescricao_item_id"], ["prescricao_itens.id"]),
            sa.ForeignKeyConstraint(["prescricao_id"], ["prescricoes.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
        )
        op.create_index("ix_estornos_protocolo", "estornos", ["protocolo"], unique=True)
        op.create_index("ix_estornos_origem_dispensacao_id", "estornos", ["origem_dispensacao_id"])
        op.create_index("ix_estornos_prescricao_item_id", "estornos", ["prescricao_item_id"])
        op.create_index("ix_estornos_prescricao_id", "estornos", ["prescricao_id"])
        op.create_index("ix_estornos_cnpj_estabelecimento", "estornos", ["cnpj_estabelecimento"])


def downgrade() -> None:
    if _table_exists("estornos"):
        op.drop_index("ix_estornos_cnpj_estabelecimento", table_name="estornos")
        op.drop_index("ix_estornos_prescricao_id", table_name="estornos")
        op.drop_index("ix_estornos_prescricao_item_id", table_name="estornos")
        op.drop_index("ix_estornos_origem_dispensacao_id", table_name="estornos")
        op.drop_index("ix_estornos_protocolo", table_name="estornos")
        op.drop_table("estornos")
