"""ticket19_add_data_validade_to_receituarios

Adiciona a coluna `data_validade` à tabela `receituarios` (Ticket 19).

Contexto regulatório
--------------------
Cada tipo de receituário tem prazo de validade específico:
- Notificação A (amarela):     30 dias
- Notificação B (azul):         30 dias
- Controle Especial (branca):   30 dias
- Notificação Especial:         30 dias (Talidomida pode diferir)
- Retenção (antimicrobianos):   10 dias
- Receita Simples:              sem validade (NULL)

A coluna é calculada no endpoint /gerar como:
  data_validade = created_at + validade_dias (do tipo de receituário)

Tipo: DateTime, nullable=True
  - NULL = sem validade definida (receita_simples)
  - datetime = data até a qual o receituário é válido

Idempotência
------------
A migration usa `_column_exists()` para não falhar se a coluna já
existir (ex.: SQLite de dev atualizado manualmente).

Revision ID: c3d7a8b9e1f2
Revises: af5133f5f172
Create Date: 2026-04-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c3d7a8b9e1f2'
down_revision: Union[str, Sequence[str], None] = 'af5133f5f172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona data_validade a receituarios (idempotente)."""
    if not _column_exists("receituarios", "data_validade"):
        op.add_column(
            "receituarios",
            sa.Column(
                "data_validade",
                sa.DateTime(),
                nullable=True,
                comment=(
                    "Validade do receituário (Ticket 19). NULL = sem validade "
                    "definida. Calculada como: created_at + validade_dias "
                    "do tipo de receituário (regras_receituario.py). "
                    "Bloqueada para emissão de PDF se expirada (exceto re-download)."
                ),
            ),
        )


def downgrade() -> None:
    """Remove data_validade de receituarios (idempotente)."""
    if _column_exists("receituarios", "data_validade"):
        op.drop_column("receituarios", "data_validade")
