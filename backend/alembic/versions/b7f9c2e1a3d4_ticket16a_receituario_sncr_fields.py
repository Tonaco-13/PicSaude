"""ticket16a_receituario_sncr_fields

Ticket 16A — Adapter SNCR com Stub.

Altera a tabela `receituarios` para suportar o ciclo de vida pós-numeração:

  1. Expande `status` de String(20) para String(30) — comporta novos
     estados como "nao_requer_sncr" e "todo_regulatorio" sem aperto.
  2. Adiciona `numerado_em` (DateTime, nullable) — timestamp da numeração.
  3. Adiciona `emitido_em`  (DateTime, nullable) — timestamp da emissão.
  4. Adiciona `adapter_usado` (String(20), nullable) — "stub" | "real".

Rationale
---------
- O ciclo de vida do receituário cresceu (ver app/models/receituario.py)
  para incluir "nao_requer_sncr", "numerado_stub", "numerado", "expirado",
  "cancelado". O maior nome ("todo_regulatorio") tem 16 caracteres; mantemos
  String(30) para folga futura.
- `adapter_usado` é a chave de rastreabilidade: qualquer auditoria pode
  distinguir entre numeração emitida pelo stub (dev/teste) e real (produção).
- `numerado_em` / `emitido_em` complementam `created_at` (que reflete a
  inserção do receituário em si, não as transições de ciclo de vida).

Idempotência
------------
Migration usa `has_column()` antes de adicionar — segura para reaplicação
em ambientes onde alguém já alterou o schema manualmente.

Revision ID: b7f9c2e1a3d4
Revises: a5472d975fc5
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "b7f9c2e1a3d4"
down_revision: Union[str, Sequence[str], None] = "a5472d975fc5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Adiciona campos do ciclo de vida SNCR e expande `status`."""
    # 1. Expandir `status` para String(30) — somente Postgres aceita
    #    ALTER COLUMN ... TYPE; em SQLite a coluna já é dinâmica.
    if _is_postgres():
        op.alter_column(
            "receituarios",
            "status",
            existing_type=sa.String(length=20),
            type_=sa.String(length=30),
            existing_nullable=False,
            existing_server_default="gerado",
        )

    # 2. numerado_em
    if not _column_exists("receituarios", "numerado_em"):
        op.add_column(
            "receituarios",
            sa.Column("numerado_em", sa.DateTime(), nullable=True),
        )

    # 3. emitido_em
    if not _column_exists("receituarios", "emitido_em"):
        op.add_column(
            "receituarios",
            sa.Column("emitido_em", sa.DateTime(), nullable=True),
        )

    # 4. adapter_usado
    if not _column_exists("receituarios", "adapter_usado"):
        op.add_column(
            "receituarios",
            sa.Column(
                "adapter_usado",
                sa.String(length=20),
                nullable=True,
                comment="SNCRAdapter usado para a numeração: 'stub' | 'real'.",
            ),
        )


def downgrade() -> None:
    """Reverte campos adicionados; encolhe `status` de volta para String(20).

    AVISO: o downgrade encolhe `status` para 20. Se há linhas com status
    ocupando mais de 20 caracteres ("nao_requer_sncr" cabe em 15, mas
    "todo_regulatorio" tem 16 — ainda OK), Postgres permitirá. Se a
    aplicação tiver introduzido valores >20 chars, este downgrade falhará
    deliberadamente (preferível a truncar dados).
    """
    if _column_exists("receituarios", "adapter_usado"):
        op.drop_column("receituarios", "adapter_usado")
    if _column_exists("receituarios", "emitido_em"):
        op.drop_column("receituarios", "emitido_em")
    if _column_exists("receituarios", "numerado_em"):
        op.drop_column("receituarios", "numerado_em")

    if _is_postgres():
        op.alter_column(
            "receituarios",
            "status",
            existing_type=sa.String(length=30),
            type_=sa.String(length=20),
            existing_nullable=False,
            existing_server_default="gerado",
        )
