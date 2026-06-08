"""cria objeto sanitário encaminhamento — TICKET-ENCAMINHAMENTO-E1

Revision ID: 7c2e8f91a4b6
Revises: c1f0a5b3d7e9
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "7c2e8f91a4b6"
down_revision: Union[str, Sequence[str], None] = "c1f0a5b3d7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("encaminhamentos"):
        op.create_table(
            "encaminhamentos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("protocolo", sa.String(length=50), nullable=False),
            sa.Column("prescritor_id", sa.Integer(), nullable=True),
            sa.Column("paciente_id", sa.Integer(), nullable=True),
            sa.Column("cns_destino", sa.String(length=20), nullable=False),
            sa.Column("especialidade_destino", sa.String(length=200), nullable=False),
            sa.Column("cid", sa.String(length=20), nullable=True),
            sa.Column("justificativa_clinica", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'emitido'")),
            sa.Column("tipo_emissao", sa.String(length=20), nullable=False, server_default=sa.text("'novo'")),
            sa.Column("origem_encaminhamento_id", sa.Integer(), nullable=True),
            sa.Column("assinatura_hash", sa.String(length=64), nullable=True),
            sa.Column("data_emissao", sa.String(length=10), nullable=False),
            sa.Column("data_validade", sa.String(length=10), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("protocolo", name="uq_encaminhamentos_protocolo"),
            sa.ForeignKeyConstraint(["prescritor_id"], ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_encaminhamento_id"], ["encaminhamentos.id"]),
        )
        op.create_index("ix_encaminhamentos_protocolo", "encaminhamentos", ["protocolo"])
        op.create_index("ix_encaminhamentos_prescritor_id", "encaminhamentos", ["prescritor_id"])
        op.create_index("ix_encaminhamentos_paciente_id", "encaminhamentos", ["paciente_id"])
        op.create_index("ix_encaminhamentos_cns_destino", "encaminhamentos", ["cns_destino"])

    if not _table_exists("encaminhamento_itens"):
        op.create_table(
            "encaminhamento_itens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("encaminhamento_id", sa.Integer(), nullable=False),
            sa.Column("especialidade", sa.String(length=200), nullable=False),
            sa.Column("procedimento", sa.String(length=200), nullable=True),
            sa.Column("motivo", sa.Text(), nullable=True),
            sa.Column("status_item", sa.String(length=30), nullable=False, server_default=sa.text("'pendente'")),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["encaminhamento_id"], ["encaminhamentos.id"]),
        )
        op.create_index("ix_encaminhamento_itens_encaminhamento_id", "encaminhamento_itens", ["encaminhamento_id"])

    if not _table_exists("encaminhamento_eventos"):
        op.create_table(
            "encaminhamento_eventos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("encaminhamento_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento", sa.String(length=80), nullable=False),
            sa.Column("ator_tipo", sa.String(length=40), nullable=False),
            sa.Column("ator_id", sa.String(length=100), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["encaminhamento_id"], ["encaminhamentos.id"]),
        )
        op.create_index("ix_encaminhamento_eventos_encaminhamento_id", "encaminhamento_eventos", ["encaminhamento_id"])

    if not _table_exists("encaminhamento_custodia"):
        op.create_table(
            "encaminhamento_custodia",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("encaminhamento_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=True),
            sa.Column("detentor_tipo", sa.String(length=40), nullable=False),
            sa.Column("detentor_id", sa.String(length=100), nullable=False),
            sa.Column("transferida_em", sa.String(length=40), nullable=False),
            sa.Column("encerrada_em", sa.String(length=40), nullable=True),
            sa.Column("motivo", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["encaminhamento_id"], ["encaminhamentos.id"]),
            sa.ForeignKeyConstraint(["item_id"], ["encaminhamento_itens.id"]),
        )
        op.create_index("ix_encaminhamento_custodia_encaminhamento_id", "encaminhamento_custodia", ["encaminhamento_id"])
        op.create_index("ix_encaminhamento_custodia_item_id", "encaminhamento_custodia", ["item_id"])


def downgrade() -> None:
    if _table_exists("encaminhamento_custodia"):
        op.drop_index("ix_encaminhamento_custodia_item_id", table_name="encaminhamento_custodia")
        op.drop_index("ix_encaminhamento_custodia_encaminhamento_id", table_name="encaminhamento_custodia")
        op.drop_table("encaminhamento_custodia")
    if _table_exists("encaminhamento_eventos"):
        op.drop_index("ix_encaminhamento_eventos_encaminhamento_id", table_name="encaminhamento_eventos")
        op.drop_table("encaminhamento_eventos")
    if _table_exists("encaminhamento_itens"):
        op.drop_index("ix_encaminhamento_itens_encaminhamento_id", table_name="encaminhamento_itens")
        op.drop_table("encaminhamento_itens")
    if _table_exists("encaminhamentos"):
        op.drop_index("ix_encaminhamentos_cns_destino", table_name="encaminhamentos")
        op.drop_index("ix_encaminhamentos_paciente_id", table_name="encaminhamentos")
        op.drop_index("ix_encaminhamentos_prescritor_id", table_name="encaminhamentos")
        op.drop_index("ix_encaminhamentos_protocolo", table_name="encaminhamentos")
        op.drop_table("encaminhamentos")
