"""T2 — estorno de dispensação (objeto derivado imutável): estornos + estorno_eventos

Revision ID: b2c3d4e5f6a7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-08

Estorno como objeto sanitário DERIVADO (Opção B — martelo Fabiano, 2026-07-07):
a `dispensacoes` permanece intocada; o item permanece `dispensado`; o saldo Σ é
reposto por cálculo (Σ efetivo = Σ dispensado − Σ estornado). Ver
TICKET-ESTORNO-OBJETO-DERIVADO.md e TICKET-T2-ESTORNO-DISPENSACAO.md.
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
            sa.Column("autor_tipo", sa.String(length=40), nullable=False),
            sa.Column("autor_id", sa.String(length=100), nullable=True),
            sa.Column("paciente_id", sa.Integer(), nullable=True),
            sa.Column("quantidade_estornada", sa.Integer(), nullable=False),
            sa.Column("motivo", sa.String(length=30), nullable=False),
            sa.Column("motivo_detalhe", sa.Text(), nullable=True),
            sa.Column("assinatura_hash", sa.String(length=64), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("data_emissao", sa.String(length=10), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["origem_dispensacao_id"], ["dispensacoes.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.CheckConstraint(
                "motivo IN ('falha_pagamento', 'desistencia', 'erro_dispensacao', 'outro')",
                name="chk_estorno_motivo",
            ),
        )
        op.create_index("ix_estornos_protocolo", "estornos", ["protocolo"], unique=True)
        op.create_index("ix_estornos_origem_dispensacao_id", "estornos", ["origem_dispensacao_id"])

    if not _table_exists("estorno_eventos"):
        op.create_table(
            "estorno_eventos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("estorno_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento", sa.String(length=80), nullable=False),
            sa.Column("ator_tipo", sa.String(length=40), nullable=False),
            sa.Column("ator_id", sa.String(length=100), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["estorno_id"], ["estornos.id"]),
        )
        op.create_index("ix_estorno_eventos_estorno_id", "estorno_eventos", ["estorno_id"])


def downgrade() -> None:
    if _table_exists("estorno_eventos"):
        op.drop_index("ix_estorno_eventos_estorno_id", table_name="estorno_eventos")
        op.drop_table("estorno_eventos")
    if _table_exists("estornos"):
        op.drop_index("ix_estornos_origem_dispensacao_id", table_name="estornos")
        op.drop_index("ix_estornos_protocolo", table_name="estornos")
        op.drop_table("estornos")
