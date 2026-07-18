"""TICKET-LEDGER-TRIGGERS-MIGRACAO — triggers de imutabilidade do ledger

Revision ID: f2b7c1d0a4e5
Revises: a7b8c9d0e1f2
Create Date: 2026-07-18

CLAUDE.md §2: as tabelas `*_eventos` nunca recebem UPDATE nem DELETE. Até aqui,
quem sustentava isso no banco era `init_tables.py` — em código `sqlite3.connect()`,
SQLite-only — e o `predeploy.sh` do Render (`alembic upgrade head` + `seed_demo.py`)
NUNCA chama `init_tables.py`. Resultado medido: em PostgreSQL os triggers nunca
existiram. O §2 dizia que o banco recusa; só a convenção recusava.

Esta migração passa a ser a AUTORIDADE dos 14 triggers (7 tabelas × UPDATE/DELETE),
nos dois dialetos, com a MESMA mensagem de recusa. É a migração — não o script de
bootstrap — que roda em produção.

Não é incidente: produção ainda não existe (Etapa 8 ⛔). É dívida paga antes do parto.

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
reaplicar `sql_criar_sqlite()` para aquela tabela.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.domain.ledger_imutabilidade import sql_criar, sql_remover

revision: str = "f2b7c1d0a4e5"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    dialeto = op.get_bind().dialect.name
    for comando in sql_criar(dialeto):
        op.execute(comando)


def downgrade() -> None:
    dialeto = op.get_bind().dialect.name
    for comando in sql_remover(dialeto):
        op.execute(comando)
