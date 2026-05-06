"""ticket18_add_tipo_retencao_to_prescricao_itens

Adiciona a coluna `tipo_retencao` à tabela `prescricao_itens` (Ticket 18).

Contexto regulatório
--------------------
A Portaria SVS/MS 344/1998 classifica substâncias por LISTAS
(A1, B1, C5, D1...) — campo `classe_controle`. A RDC Anvisa 471/2021
classifica medicamentos sujeitos à retenção por SUBSTÂNCIA (DCB),
fora do escopo da Portaria 344.

Os dois sistemas são independentes; o motor regulatório roteia itens
para `GRUPO_RETENCAO` quando `tipo_retencao` está preenchido.

Tipo: String(30), nullable=True
  - NULL = não sujeito a retenção por RDC 471
  - "antimicrobiano" — RDC 471/2021 + IN 83/2021
  - "glp1_agonista"  — IN 360/2025 (semaglutida, liraglutida, ...)

Idempotência
------------
A migration usa `_column_exists()` para não falhar se a coluna já
existir (ex.: SQLite de dev atualizado manualmente).

Revision ID: af5133f5f172
Revises: b7f9c2e1a3d4
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'af5133f5f172'
down_revision: Union[str, Sequence[str], None] = 'b7f9c2e1a3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona tipo_retencao a prescricao_itens (idempotente)."""
    if not _column_exists("prescricao_itens", "tipo_retencao"):
        op.add_column(
            "prescricao_itens",
            sa.Column(
                "tipo_retencao",
                sa.String(30),
                nullable=True,
                comment=(
                    "Tipo de retenção (RDC 471/2021). NULL = não sujeito a "
                    "retenção. Valores: 'antimicrobiano' (RDC 471/IN 83/2021), "
                    "'glp1_agonista' (IN 360/2025). Coexiste com classe_controle "
                    "(Portaria 344/1998) — ver app/domain/retencao.py."
                ),
            ),
        )


def downgrade() -> None:
    """Remove tipo_retencao de prescricao_itens (idempotente)."""
    if _column_exists("prescricao_itens", "tipo_retencao"):
        op.drop_column("prescricao_itens", "tipo_retencao")
