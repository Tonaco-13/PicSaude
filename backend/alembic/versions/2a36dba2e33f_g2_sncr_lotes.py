"""g2_sncr_lotes

DESENHO-TALAO-DIGITAL-SNCR.md §2 — G2, store próprio do adapter SNCR para
lotes (talonários digitais): o prescritor adquire um lote por
(prescritor × tipo_receituario), com faixa [inicio..fim] e `valida_ate`
opcional; a numeração passa a sacar sequencialmente do lote ativo quando
existir um, mantendo o caminho sob-demanda atual quando não existir
(retrocompat).

`sncr_lotes` é tabela do ADAPTER, não do núcleo clínico — SEM FK para
`prescricoes`/`prescritores`/etc. (§10 CLAUDE.md: adapter nunca escreve em
tabela clínica; aqui a regra irmã é "não referencia" — o vínculo com o
prescritor é por identificador solto, `prescritor_identificador`, do
mesmo jeito que `NumeracaoSNCR.prescritor_cpf` já é solto na interface).

`proximo` é o cursor de consumo dentro da própria linha do lote — trava
de concorrência via SELECT...FOR UPDATE (PG; SQLite serializa globalmente)
no momento do saque, nunca duas requisições concorrentes saem com o mesmo
número (AC3 do §2).

Revision ID: 2a36dba2e33f
Revises: 2fb9182a0846
Create Date: 2026-08-30 11:32:59.678051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '2a36dba2e33f'
down_revision: Union[str, Sequence[str], None] = '2fb9182a0846'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table)


def upgrade() -> None:
    if not _table_exists("sncr_lotes"):
        op.create_table(
            "sncr_lotes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("lote_id", sa.String(80), nullable=False, unique=True),
            sa.Column("tipo_receituario", sa.String(50), nullable=False),
            sa.Column("prescritor_identificador", sa.String(50), nullable=False),
            sa.Column("inicio", sa.Integer(), nullable=False),
            sa.Column("fim", sa.Integer(), nullable=False),
            sa.Column("proximo", sa.Integer(), nullable=False),
            sa.Column("valida_ate", sa.DateTime(), nullable=True),
            sa.Column("adapter_usado", sa.String(20), nullable=False),
            sa.Column(
                "criado_em", sa.DateTime(), nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_sncr_lotes_prescritor_tipo",
            "sncr_lotes",
            ["prescritor_identificador", "tipo_receituario"],
        )


def downgrade() -> None:
    if _table_exists("sncr_lotes"):
        op.drop_index("ix_sncr_lotes_prescritor_tipo", table_name="sncr_lotes")
        op.drop_table("sncr_lotes")
