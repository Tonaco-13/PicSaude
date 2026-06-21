"""f3_add_cpf_to_prescritores

Adiciona a coluna `cpf` à tabela `prescritores` (achado F3 da auditoria de
segurança — binding verificável certificado ↔ prescritor).

Contexto
--------
No upload de certificado A1 (.pfx), o CPF contido no certificado precisa ser
amarrado ao prescritor logado. Como o model `prescritores` só tinha CNS, não
havia como cruzar. Esta coluna guarda o CPF do prescritor.

Convenção
---------
- nullable=True: objetos legados permanecem com CPF NULL.
- Vínculo na primeira vez (TOFU): o primeiro certículo cadastrado popula o CPF;
  uploads seguintes precisam casar (enforcement em routers/prescritor.py).
- A prova forte do CPF contra base confiável (CADSUS) é a Fase B (T65).

Idempotência
------------
Usa `_column_exists()` para não falhar se a coluna já existir.

Revision ID: d4e8b1c9f0a2
Revises: a3d9f2c4e1b7
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'd4e8b1c9f0a2'
down_revision: Union[str, Sequence[str], None] = 'a3d9f2c4e1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona cpf a prescritores (idempotente)."""
    if not _column_exists("prescritores", "cpf"):
        op.add_column(
            "prescritores",
            sa.Column(
                "cpf",
                sa.String(),
                nullable=True,
                comment=(
                    "CPF do prescritor (achado F3). Usado para amarrar o "
                    "certificado A1 (cpf no certificado == cpf do prescritor). "
                    "NULL = ainda não vinculado. Vínculo na 1ª vez (TOFU); "
                    "prova forte contra CADSUS é Fase B (T65)."
                ),
            ),
        )


def downgrade() -> None:
    """Remove cpf de prescritores (idempotente)."""
    if _column_exists("prescritores", "cpf"):
        op.drop_column("prescritores", "cpf")
