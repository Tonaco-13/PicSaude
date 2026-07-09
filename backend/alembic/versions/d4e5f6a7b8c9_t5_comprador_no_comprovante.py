"""T5 — comprador na dispensação (comprovante COMPRADOR × PACIENTE)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-09

Colunas OPCIONAIS de comprador em `dispensacoes` (local-extension, NULL default).
O comprador (portador que retira) é distinto do paciente (indicação clínica).

Checks do Jules baked in:
- Simetria: comprador é atributo POR-DISPENSAÇÃO, gravado no INSERT e imutável —
  não há "comprador anterior" a invalidar; uma nova dispensação é uma nova linha.
- Orphan: o PII do comprador vive em `dispensacoes` (cadeia de FK até a
  prescrição/paciente), nunca numa tabela solta sem constraint.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existentes = _cols("dispensacoes")
    if "comprador_nome" not in existentes:
        op.add_column("dispensacoes", sa.Column("comprador_nome", sa.String(), nullable=True))
    if "comprador_documento" not in existentes:
        op.add_column("dispensacoes", sa.Column("comprador_documento", sa.String(), nullable=True))


def downgrade() -> None:
    existentes = _cols("dispensacoes")
    if "comprador_documento" in existentes:
        op.drop_column("dispensacoes", "comprador_documento")
    if "comprador_nome" in existentes:
        op.drop_column("dispensacoes", "comprador_nome")
