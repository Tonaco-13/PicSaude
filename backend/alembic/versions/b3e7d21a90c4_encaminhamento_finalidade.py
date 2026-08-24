"""ENG-016 §5 (`module`): `encaminhamentos.finalidade` — a finalidade estruturada

Martelo 2 do §11 do DESENHO-ENCAMINHAMENTO-UX (Fabiano, 23/08): a finalidade
entra no MVP como dado ESTRUTURADO, não como prosa dentro da justificativa.

POR QUE COLUNA, E POR QUE AGORA
-------------------------------
"Para que estou mandando este paciente" é dado OPERACIONAL — é por ele que a
regulação futura vai filtrar fila ("todas as segundas opiniões de cardiologia").
Enterrado no texto da justificativa, vira coisa que só um humano lê. E retrofit
em documento canônico é pior que nascer certo: mudar depois o que o hash cobre
divide a base em antes e depois.

NULLABLE, e é decisão
---------------------
Encaminhamentos já emitidos não têm finalidade e não podem ganhá-la — objeto
sanitário emitido é imutável (§1). Backfill com um valor plausível seria
inventar declaração clínica que ninguém fez. `NULL` aqui significa "emitido
antes da finalidade existir", que é a verdade, e é a mesma convenção do §6b
para escopo institucional ausente.

A TELA sempre manda; o SCHEMA aceita ausência. Quem lê distingue os dois casos
pelo valor, não por adivinhação.

Sem CHECK de vocabulário no banco: a lista curta (`avaliacao · conduta ·
exame_complementar · segunda_opiniao · seguimento · outra`) vive na aplicação,
com "outra" exigindo texto livre. Um CHECK congelaria no schema um vocabulário
que ainda vai crescer, e mudar CHECK é migração — enquanto a lista da aplicação
é uma linha.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "b3e7d21a90c4"
down_revision = "a1c9e4d70b26"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "encaminhamentos",
        sa.Column("finalidade", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "encaminhamentos",
        sa.Column("finalidade_texto", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    # `batch_alter_table` porque o SQLite não faz DROP COLUMN direto em todas as
    # versões — mesmo cuidado da `f2d8b41c9e73` (elo do laudo).
    with op.batch_alter_table("encaminhamentos") as batch:
        batch.drop_column("finalidade_texto")
        batch.drop_column("finalidade")
