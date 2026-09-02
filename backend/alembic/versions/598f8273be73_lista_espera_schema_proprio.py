"""lista_espera_schema_proprio

Despacho "Lista de espera direta" (`module`) — a base da lista de espera do
"em obras" (`entrar.html`) precisa sobreviver ao reset diário da vitrine
(`scripts/reset_demo_db.py`), que em PostgreSQL faz
`DROP SCHEMA "<current_schema()>" CASCADE` — normalmente `public`.

A régua adotada: em vez de "declarar uma exceção" dentro do script de reset
(o que exigiria salvar/restaurar linhas ao redor de um DROP CASCADE — frágil,
e o script de reset é código sensível demais para crescer uma exceção por
tabela), a tabela nasce **fora do schema que o reset alcança**. Um schema
diferente nunca entra no `CASCADE` de outro. Por construção, não por exceção.

Em SQLite (dev/demo local sem `DATABASE_URL`), a mesma tabela vive num
ARQUIVO próprio (`data/lista_espera.db`), fora do path que
`_reset_sqlite()` apaga (`PIX_SAUDE_DEMO_DB`/`DB_PATH`) — bootstrap feito
pelo próprio módulo de armazenamento (`app/domain/lista_espera.py`), não por
esta migração: SQLite não tem `CREATE SCHEMA`, e um arquivo à parte não é
"schema do Alembic" nenhum. Esta migração é PostgreSQL-only por desenho.

VERMELHO ACHADO AO RODAR O RESET DE VERDADE: `alembic_version` mora no
schema que o reset dropa (`public`) — depois de um `DROP SCHEMA "public"
CASCADE`, o Alembic não tem memória nenhuma de ter rodado esta migração
antes, e reaplica `upgrade()` do zero contra um `lista_espera.inscricoes`
que SOBREVIVEU ao drop (esse é o ponto inteiro da tabela existir num schema
à parte). `CREATE TABLE` incondicional colide com "relation already
exists". Por isso o guard idempotente abaixo — a mesma disciplina de
`2a36dba2e33f_g2_sncr_lotes.py::_table_exists`, ciente de schema.

Revision ID: 598f8273be73
Revises: 2a36dba2e33f
Create Date: 2026-09-01 18:35:11.433346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '598f8273be73'
down_revision: Union[str, Sequence[str], None] = '2a36dba2e33f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEMA = "lista_espera"


def _table_exists(table: str, schema: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table, schema=schema)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite: arquivo próprio, bootstrap pelo módulo de domínio.

    op.execute(f'CREATE SCHEMA IF NOT EXISTS "{_SCHEMA}"')
    if not _table_exists("inscricoes", _SCHEMA):
        op.create_table(
            "inscricoes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome", sa.String(200), nullable=False),
            sa.Column("email", sa.String(254), nullable=False),
            sa.Column("origem", sa.String(100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                       server_default=sa.func.now()),
            schema=_SCHEMA,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    if _table_exists("inscricoes", _SCHEMA):
        op.drop_table("inscricoes", schema=_SCHEMA)
    op.execute(f'DROP SCHEMA IF EXISTS "{_SCHEMA}"')
