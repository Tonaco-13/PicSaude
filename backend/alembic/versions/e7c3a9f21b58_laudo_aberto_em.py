"""Laudo ganha `aberto_em`: a abertura pelo cidadão como fato carimbado

ENG-014, PR C · `DESENHO-LAUDO-POSSE-POR-ITEM-E-ABERTURA.md` §3 e §9.1.

POR QUE A COLUNA EXISTE
-----------------------
Martelo (a) do Fabiano (20/08): **"abrir o laudo = dar ciência"** — o evento
nomeia a ABERTURA (fato real) e a ciência é consequência DERIVADA. Para que o
ledger não ganhe um evento a cada vez que o cidadão reabre o cartão, a abertura
precisa de um carimbo: `aberto_em` é a marca da PRIMEIRA. A segunda abertura
responde 200 e não emite nada — um fato, um evento (espírito R2, §2a).

A coluna é também o que alimenta o selo "Lido em" do Histórico da clínica
(§5): a confirmação rastreada vive na LEITURA, porque não há infra de push e
não haverá antes do G4A.

O QUE ELA NÃO É
---------------
**Não é gatilho de faturamento.** Martelo (b): o fato financeiro é da unidade
(laudo liberado); a leitura é comportamento do cidadão. `aberto_em` é coluna
informativa de relatório/histórico — nunca condição de movimento (espírito
B0/R1: o movimento se escreve quando o fato da unidade acontece).
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "e7c3a9f21b58"
down_revision = "d4b8c1e07f36"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable por construção: laudo nunca aberto tem `aberto_em IS NULL`, e é
    # essa ausência que distingue "não lido" de "lido" — sentinela seria pior
    # (CLAUDE.md §6b: ausência é ausência, não um valor especial).
    op.add_column("laudos", sa.Column("aberto_em", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("laudos", "aberto_em")
