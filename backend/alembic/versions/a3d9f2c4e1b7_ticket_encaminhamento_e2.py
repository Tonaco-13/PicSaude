"""cria objeto sanitário derivado contrarreferência — TICKET-ENCAMINHAMENTO-E2

Revision ID: a3d9f2c4e1b7
Revises: 7c2e8f91a4b6
Create Date: 2026-06-08
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "a3d9f2c4e1b7"
down_revision: Union[str, Sequence[str], None] = "7c2e8f91a4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("contrarreferencias"):
        op.create_table(
            "contrarreferencias",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("protocolo", sa.String(length=50), nullable=False),
            sa.Column("cns_autor", sa.String(length=20), nullable=False),
            sa.Column("autor_id", sa.Integer(), nullable=True),
            sa.Column("paciente_id", sa.Integer(), nullable=True),
            sa.Column("origem_encaminhamento_id", sa.Integer(), nullable=False),
            sa.Column("conteudo_clinico", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'registrada'")),
            sa.Column("tipo_emissao", sa.String(length=20), nullable=False, server_default=sa.text("'novo'")),
            sa.Column("origem_contrarreferencia_id", sa.Integer(), nullable=True),
            sa.Column("assinatura_hash", sa.String(length=64), nullable=True),
            sa.Column("data_emissao", sa.String(length=10), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("protocolo", name="uq_contrarreferencias_protocolo"),
            sa.ForeignKeyConstraint(["autor_id"], ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_encaminhamento_id"], ["encaminhamentos.id"]),
            sa.ForeignKeyConstraint(["origem_contrarreferencia_id"], ["contrarreferencias.id"]),
        )
        op.create_index("ix_contrarreferencias_protocolo", "contrarreferencias", ["protocolo"])
        op.create_index("ix_contrarreferencias_origem_encaminhamento_id", "contrarreferencias", ["origem_encaminhamento_id"])

    if not _table_exists("contrarreferencia_eventos"):
        op.create_table(
            "contrarreferencia_eventos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrarreferencia_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento", sa.String(length=80), nullable=False),
            sa.Column("ator_tipo", sa.String(length=40), nullable=False),
            sa.Column("ator_id", sa.String(length=100), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["contrarreferencia_id"], ["contrarreferencias.id"]),
        )
        op.create_index("ix_contrarreferencia_eventos_contrarreferencia_id", "contrarreferencia_eventos", ["contrarreferencia_id"])

    if not _table_exists("contrarreferencia_custodia"):
        op.create_table(
            "contrarreferencia_custodia",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("contrarreferencia_id", sa.Integer(), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=True),
            sa.Column("detentor_tipo", sa.String(length=40), nullable=False),
            sa.Column("detentor_id", sa.String(length=100), nullable=False),
            sa.Column("transferida_em", sa.String(length=40), nullable=False),
            sa.Column("encerrada_em", sa.String(length=40), nullable=True),
            sa.Column("motivo", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["contrarreferencia_id"], ["contrarreferencias.id"]),
        )
        op.create_index("ix_contrarreferencia_custodia_contrarreferencia_id", "contrarreferencia_custodia", ["contrarreferencia_id"])


def downgrade() -> None:
    if _table_exists("contrarreferencia_custodia"):
        op.drop_index("ix_contrarreferencia_custodia_contrarreferencia_id", table_name="contrarreferencia_custodia")
        op.drop_table("contrarreferencia_custodia")
    if _table_exists("contrarreferencia_eventos"):
        op.drop_index("ix_contrarreferencia_eventos_contrarreferencia_id", table_name="contrarreferencia_eventos")
        op.drop_table("contrarreferencia_eventos")
    if _table_exists("contrarreferencias"):
        op.drop_index("ix_contrarreferencias_origem_encaminhamento_id", table_name="contrarreferencias")
        op.drop_index("ix_contrarreferencias_protocolo", table_name="contrarreferencias")
        op.drop_table("contrarreferencias")
