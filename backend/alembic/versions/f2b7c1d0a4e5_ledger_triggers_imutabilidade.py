"""TICKET-LEDGER-TRIGGERS-MIGRACAO — triggers de imutabilidade do ledger

Revision ID: f2b7c1d0a4e5
Revises: a7b8c9d0e1f2
Create Date: 2026-07-18

CLAUDE.md §2: as tabelas `*_eventos` nunca recebem UPDATE nem DELETE. Até aqui,
quem sustentava isso no banco era `init_tables.py` — em código `sqlite3.connect()`,
SQLite-only — e o `predeploy.sh` do Render (`alembic upgrade head` + `seed_demo.py`)
NUNCA chama `init_tables.py`. Resultado medido: em PostgreSQL os triggers nunca
existiram. O §2 dizia que o banco recusa; só a convenção recusava.

Esta migração passa a ser a AUTORIDADE dos 16 triggers (8 tabelas × UPDATE/DELETE),
nos dois dialetos, com a MESMA mensagem de recusa. É a migração — não o script de
bootstrap — que roda em produção.

Não é incidente: produção ainda não existe (Etapa 8 ⛔). É dívida paga antes do parto.

Por que a lista de tabelas é literal aqui
-----------------------------------------
`TABELAS_LEDGER` (em `app.domain.ledger_imutabilidade`) é lista VIVA: diz quais
ledgers devem estar protegidos AGORA. Se esta migração a lesse, o efeito dela
dependeria de QUANDO rodasse — banco migrado hoje com 16 triggers, banco criado
do zero depois da 9ª tabela com 18. Dois bancos no mesmo `alembic head` com
schemas diferentes: exatamente o defeito que este ticket conserta.

Então: compartilha-se o COMO (`sql_criar`/`sql_remover`, fonte única do DDL) e
congela-se o QUÊ (a tupla abaixo, escrita nesta migração). Mesmo princípio do R4
(CLAUDE.md §2a) — o grupo é congelado POR VALOR no ato do movimento.

Ledger novo daqui em diante: entra em `TABELAS_LEDGER` e ganha uma migração
NOVA com a sua própria tupla. Esta aqui nunca é editada (CLAUDE.md §9); há
guard-rail em `tests/test_ledger_imutabilidade.py` que trava estes 8 nomes.

Dialetos
--------
SQLite     : `RAISE(FAIL, ...)` em trigger BEFORE — semântica e texto preservados
             exatamente como estavam (há teste que casa a string).
PostgreSQL : `RAISE(FAIL, ...)` não existe → função PL/pgSQL com RAISE EXCEPTION
             + um trigger BEFORE FOR EACH ROW por tabela/ação.

Idempotente nos dois sentidos: `IF NOT EXISTS` (SQLite) e DROP+CREATE (PG) no
upgrade; `IF EXISTS` no downgrade.

Cuidado para o futuro (SQLite): `op.batch_alter_table` recria a tabela e leva os
triggers junto. Migração posterior que faça batch em tabela de ledger deve
reaplicar `sql_criar_sqlite((...,))` para aquela tabela — passando-a
explicitamente, com a sua própria tupla congelada.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.domain.ledger_imutabilidade import sql_criar, sql_remover

revision: str = "f2b7c1d0a4e5"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tabelas sobre as quais ESTA migração agiu — congeladas por valor.
# Não importar de `TABELAS_LEDGER`: ver "Por que a lista de tabelas é literal
# aqui", no topo. Alterar estes nomes reescreve o passado e quebra o guard-rail.
TABELAS_CONGELADAS: tuple[str, ...] = (
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "agendamento_eventos",
    "circulacao_diagnostica_eventos",
    "encaminhamento_eventos",
    "atestado_eventos",
    "contrarreferencia_eventos",
)


def upgrade() -> None:
    dialeto = op.get_bind().dialect.name
    for comando in sql_criar(dialeto, TABELAS_CONGELADAS):
        op.execute(comando)


def downgrade() -> None:
    dialeto = op.get_bind().dialect.name
    for comando in sql_remover(dialeto, TABELAS_CONGELADAS):
        op.execute(comando)
