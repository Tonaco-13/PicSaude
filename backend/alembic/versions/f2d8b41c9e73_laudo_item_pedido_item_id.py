"""Laudo ganha o ELO de verdade: `laudo_itens.pedido_item_id`

ENG-014, frente 1 (v2) · `DESENHO-LAUDO-POSSE-POR-ITEM-E-ABERTURA.md` §2.1.

POR QUE A COLUNA EXISTE
-----------------------
O guard de posse por item do laudo precisava saber QUAL item do pedido cada
item do laudo cobre. Esse elo não existia: `laudo_itens` guardava só
`nome_exame`/`codigo_tuss` — texto livre. Autorizar por casamento de nome é a
mesma família de defeito que a casa já rejeitou três vezes (posse lida do
status no J.7, predicado duplicado no #168, relatório lendo nível-pedido no
#172): decidir direito de operar a partir de um proxy não-autoritativo.

Dois itens de mesmo `nome_exame` no mesmo pedido, ou um exame renomeado, e a
autorização muda de dono. O elo fecha isso: **o id é a chave, o nome é
exibição.**

SEM BACKFILL — DE PROPÓSITO
---------------------------
Linhas históricas ficam `NULL` para sempre. Reconstruir o passado casando nome
seria cometer o mesmo pecado, agora dentro de uma migração — e migração é
registro histórico (§9), não lugar de adivinhar. Espírito R3: o histórico é
fato consumado.

Os laudos legados (todos os itens sem elo) continuam operáveis pela **ponte
registrada** do §2.2 — o predicado grossa `dispensador_tem_algo_no_pedido`,
reusado do #172. Laudo novo de dispensador nunca nasce na ponte: o §2.1 exige
o elo em TODOS os itens.

NULLABLE
--------
Não é frouxidão: é a distinção entre "legado" e "novo". Um `NOT NULL` exigiria
backfill — exatamente o que se recusa acima.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "f2d8b41c9e73"
down_revision = "e7c3a9f21b58"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # A FK é declarada nos dois dialetos, mas com `batch_alter_table` no SQLite:
    # ALTER TABLE ... ADD CONSTRAINT não existe lá, e o batch recria a tabela.
    if dialect == "sqlite":
        with op.batch_alter_table("laudo_itens") as batch:
            batch.add_column(sa.Column("pedido_item_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_laudo_itens_pedido_item", "pedido_exame_itens",
                ["pedido_item_id"], ["id"],
            )
    else:
        op.add_column("laudo_itens", sa.Column("pedido_item_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_laudo_itens_pedido_item", "laudo_itens", "pedido_exame_itens",
            ["pedido_item_id"], ["id"],
        )

    # Índice: o guard de operação pergunta "este laudo tem item com elo sob
    # minha custódia?" a cada gesto. Sem índice, varredura por laudo.
    op.create_index("ix_laudo_itens_pedido_item_id", "laudo_itens", ["pedido_item_id"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_laudo_itens_pedido_item_id", table_name="laudo_itens")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("laudo_itens") as batch:
            batch.drop_constraint("fk_laudo_itens_pedido_item", type_="foreignkey")
            batch.drop_column("pedido_item_id")
    else:
        op.drop_constraint("fk_laudo_itens_pedido_item", "laudo_itens", type_="foreignkey")
        op.drop_column("laudo_itens", "pedido_item_id")
