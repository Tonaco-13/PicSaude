"""cria objeto sanitário atestado (monolítico) — atestados + eventos + custodia

Revision ID: f1a2b3c4d5e6
Revises: d4e8b1c9f0a2
Create Date: 2026-06-23
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "d4e8b1c9f0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _table_exists("atestados"):
        op.create_table(
            "atestados",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("protocolo", sa.String(length=50), nullable=False),
            sa.Column("prescritor_id", sa.Integer(), nullable=True),
            sa.Column("paciente_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default=sa.text("'emitido'")),
            sa.Column("tipo_emissao", sa.String(length=20), nullable=False, server_default=sa.text("'nova'")),
            sa.Column("origem_atestado_id", sa.Integer(), nullable=True),
            sa.Column("finalidade", sa.String(length=120), nullable=False),
            sa.Column("indicacao_clinica", sa.Text(), nullable=True),
            sa.Column("codigo_cid", sa.String(length=10), nullable=True),
            sa.Column("dias_afastamento", sa.Integer(), nullable=True),
            sa.Column("nome_profissional", sa.String(length=200), nullable=True),
            sa.Column("registro_profissional", sa.String(length=60), nullable=True),
            sa.Column("assinatura_modo", sa.String(length=40), nullable=True),
            sa.Column("assinatura_hash", sa.String(length=64), nullable=True),
            sa.Column("data_documento", sa.String(length=10), nullable=False),
            sa.Column("data_emissao", sa.String(length=10), nullable=False),
            sa.Column("data_validade", sa.String(length=10), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["prescritor_id"], ["prescritores.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_atestado_id"], ["atestados.id"]),
        )
        op.create_index("ix_atestados_protocolo", "atestados", ["protocolo"], unique=True)
        op.create_index("ix_atestados_prescritor_id", "atestados", ["prescritor_id"])
        op.create_index("ix_atestados_paciente_id", "atestados", ["paciente_id"])

    if not _table_exists("atestado_eventos"):
        op.create_table(
            "atestado_eventos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("atestado_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento", sa.String(length=60), nullable=False),
            sa.Column("ator_tipo", sa.String(length=40), nullable=True),
            sa.Column("ator_id", sa.String(length=100), nullable=True),
            sa.Column("payload", sa.Text(), nullable=True),
            sa.Column("instance_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["atestado_id"], ["atestados.id"]),
        )
        op.create_index("ix_atestado_eventos_atestado_id", "atestado_eventos", ["atestado_id"])

    if not _table_exists("atestado_custodia"):
        op.create_table(
            "atestado_custodia",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("atestado_id", sa.Integer(), nullable=False),
            sa.Column("de", sa.String(length=100), nullable=False),
            sa.Column("para", sa.String(length=100), nullable=False),
            sa.Column("transferido_em", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("dados_json", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["atestado_id"], ["atestados.id"]),
        )
        op.create_index("ix_atestado_custodia_atestado_id", "atestado_custodia", ["atestado_id"])


def downgrade() -> None:
    if _table_exists("atestado_custodia"):
        op.drop_index("ix_atestado_custodia_atestado_id", table_name="atestado_custodia")
        op.drop_table("atestado_custodia")
    if _table_exists("atestado_eventos"):
        op.drop_index("ix_atestado_eventos_atestado_id", table_name="atestado_eventos")
        op.drop_table("atestado_eventos")
    if _table_exists("atestados"):
        op.drop_index("ix_atestados_paciente_id", table_name="atestados")
        op.drop_index("ix_atestados_prescritor_id", table_name="atestados")
        op.drop_index("ix_atestados_protocolo", table_name="atestados")
        op.drop_table("atestados")
