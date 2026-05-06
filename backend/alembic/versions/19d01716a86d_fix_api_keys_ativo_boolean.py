"""fix_api_keys_ativo_boolean

Alinha api_keys.ativo com o padrão BOOLEAN já adotado em todos os outros
models do PicSaúde (usuarios, pacientes, prescritores, etc. — corrigidos
no Ticket 7). A tabela api_keys ficou de fora porque não estava no baseline
Alembic até o Ticket 8.1.

Alteração:
  api_keys.ativo  INTEGER default=1  →  BOOLEAN default=True

Em PostgreSQL: usa USING ativo::boolean para converter dados existentes.
Em SQLite (dev): ALTER COLUMN type não existe — a coluna já aceita true/false;
  a migration retorna sem ação via _is_sqlite().

Revision ID: 19d01716a86d
Revises: f8d8f30ed04e
Create Date: 2026-04-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '19d01716a86d'
down_revision: Union[str, Sequence[str], None] = 'f8d8f30ed04e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_sqlite() -> bool:
    return op.get_bind().dialect.name == "sqlite"


def upgrade() -> None:
    """Converte api_keys.ativo de INTEGER para BOOLEAN."""
    if _is_sqlite():
        # SQLite não suporta ALTER COLUMN type.
        # A coluna já funciona com true/false (duck typing do SQLite).
        # Nenhuma ação necessária — o model Python já usa Boolean.
        return

    # PostgreSQL não consegue converter server_default='1' (integer) para
    # boolean em uma única operação. É necessário:
    #   1. Dropar o default existente
    #   2. Alterar o tipo com USING para converter os dados
    #   3. Resetar o default como boolean true
    op.execute("ALTER TABLE api_keys ALTER COLUMN ativo DROP DEFAULT")
    op.alter_column(
        "api_keys",
        "ativo",
        type_=sa.Boolean(),
        postgresql_using="ativo::boolean",
        nullable=False,
    )
    op.execute("ALTER TABLE api_keys ALTER COLUMN ativo SET DEFAULT true")


def downgrade() -> None:
    """Reverte api_keys.ativo de BOOLEAN para INTEGER."""
    if _is_sqlite():
        return

    op.execute("ALTER TABLE api_keys ALTER COLUMN ativo DROP DEFAULT")
    op.alter_column(
        "api_keys",
        "ativo",
        type_=sa.Integer(),
        nullable=False,
    )
    op.execute("ALTER TABLE api_keys ALTER COLUMN ativo SET DEFAULT 1")
