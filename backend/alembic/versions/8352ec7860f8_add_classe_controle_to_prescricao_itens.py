"""add_classe_controle_to_prescricao_itens

Adiciona a coluna `classe_controle` à tabela `prescricao_itens`.

Contexto (Ticket 44 — Circulação Atomizada):
  A coluna foi adicionada ao model PrescricaoItem mas nunca chegou ao banco
  porque create_all() não faz ALTER TABLE em tabelas existentes.
  Esta migration corrige essa divergência de forma controlada.

Tipo: String(10), nullable=True
  - NULL = medicamento comum (elegível para atomização)
  - Valores que bloqueiam atomização: A1, A2, A3, B1, B2, C5, D1, D2
  - Ver domain/medicamento.py para o vocabulário completo

Idempotência:
  A migration usa `has_column()` para não falhar se a coluna já existir
  (ex: SQLite de dev que foi atualizado manualmente antes desta migration).

Revision ID: 8352ec7860f8
Revises: 037d38d98806
Create Date: 2026-04-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '8352ec7860f8'
down_revision: Union[str, Sequence[str], None] = '037d38d98806'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona classe_controle a prescricao_itens (idempotente)."""
    if not _column_exists("prescricao_itens", "classe_controle"):
        op.add_column(
            "prescricao_itens",
            sa.Column(
                "classe_controle",
                sa.String(10),
                nullable=True,
                comment=(
                    "Classe regulatória ANVISA. NULL = medicamento comum. "
                    "Valores controlados: A1,A2,A3,B1,B2,C5,D1,D2."
                ),
            ),
        )


def downgrade() -> None:
    """Remove classe_controle de prescricao_itens (idempotente)."""
    if _column_exists("prescricao_itens", "classe_controle"):
        op.drop_column("prescricao_itens", "classe_controle")
