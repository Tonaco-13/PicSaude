"""R4 — escrituração regulatória congelada na dispensação (grupo + versão)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-17

TICKET-R4-ESCRITURACAO-REGULATORIA (CLAUDE.md §2a R4):
congela a IDENTIDADE REGULATÓRIA do movimento no ato da DISPENSAÇÃO — regime
vigente à saída do produto. Duas colunas nullable em `dispensacoes`:

  - grupo_regulatorio_id     — id_grupo (slug estável) resolvido pelo motor local
                               (motor_regulatorio.escriturar_grupo_regulatorio).
                               NULL honesto = item não-controlado (sem escrituração).
  - motor_regulatorio_versao — carimbo da versão da regra sob a qual o movimento
                               foi escriturado. Dá R1 pleno: se a RDC mudar a
                               definição do grupo, o movimento passado guarda sob
                               qual versão foi escriturado (sem congelar todos os
                               campos materiais).

Congelamento POR VALOR, não FK/derivação ao vivo (re-resolver na leitura daria a
resposta do motor de hoje e mudaria período fechado — feriria R1). Precedente:
`lote`/`fabricante` (nullable, congelados no INSERT).

Idempotência: `_column_exists()` para não falhar se a coluna já existir.
Dual-DB: `String` sem length → TEXT/VARCHAR em ambos (SQLite + PostgreSQL).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona grupo_regulatorio_id + motor_regulatorio_versao (idempotente)."""
    if not _column_exists("dispensacoes", "grupo_regulatorio_id"):
        op.add_column(
            "dispensacoes",
            sa.Column(
                "grupo_regulatorio_id",
                sa.String(),
                nullable=True,
                comment=(
                    "R4 — id_grupo (slug estável) congelado no ato da dispensação. "
                    "NULL = item não-controlado (sem escrituração). Resolvido pelo "
                    "motor local; nunca chamada externa. Ver CLAUDE.md §2a R4."
                ),
            ),
        )
    if not _column_exists("dispensacoes", "motor_regulatorio_versao"):
        op.add_column(
            "dispensacoes",
            sa.Column(
                "motor_regulatorio_versao",
                sa.String(),
                nullable=True,
                comment=(
                    "R4 — versão do motor_regulatorio sob a qual o movimento foi "
                    "escriturado (dá R1 pleno). NULL = item não-controlado."
                ),
            ),
        )


def downgrade() -> None:
    """Remove as colunas de escrituração regulatória (idempotente)."""
    if _column_exists("dispensacoes", "motor_regulatorio_versao"):
        op.drop_column("dispensacoes", "motor_regulatorio_versao")
    if _column_exists("dispensacoes", "grupo_regulatorio_id"):
        op.drop_column("dispensacoes", "grupo_regulatorio_id")
