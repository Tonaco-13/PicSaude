"""migra schema institucional (prestadores.org_id + unidades) — TICKET-5C-BIS-C.1

Os models Prestador/Unidade (Ticket 30) existiam só como ORM + init_tables.py
(SQLite); a PG ficou com o `prestadores` baseline (037d38d98806): id Integer,
cnpj UNIQUE, SEM org_id — e sem `unidades`. Todo o código institucional
(login de prestador, CRUD /prestadores, api_keys, cnes, hospitalar, dispensador
de C/D) usa o schema org_id → quebrado/dev-only na PG.

Esta migration formaliza o schema Ticket-30 no histórico Alembic, com guarda
contra destruição silenciosa (drop+recreate só se vazio).

Decisões (TICKET-5C-BIS-C.1):
  - NÃO funde com estabelecimentos_proprios (conceito distinto).
  - `ativo` é Boolean (código executa `ativo = true`).
  - prestadores sem org_id e VAZIA → drop+recreate; COM linhas → ABORTA
    (backfill manual); já com org_id → só garante `unidades`.

Revision ID: c1f0a5b3d7e9
Revises: 4b1ce80a017d
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "c1f0a5b3d7e9"
down_revision: Union[str, Sequence[str], None] = "4b1ce80a017d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_prestadores() -> None:
    op.create_table(
        "prestadores",
        sa.Column("id",        sa.Text(),    nullable=False),
        sa.Column("org_id",    sa.Text(),    nullable=False),
        sa.Column("nome",      sa.Text(),    nullable=False),
        sa.Column("tipo",      sa.Text(),    nullable=False),
        sa.Column("cnpj",      sa.Text(),    nullable=True),
        sa.Column("ativo",     sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em", sa.Text(),    nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", name="uq_prestadores_org_id"),
    )
    # Login de prestador resolve por CNPJ → índice único parcial (ignora NULLs).
    # postgresql_where é específico de PG; em outros dialetos vira índice comum.
    op.create_index(
        "ix_prestadores_cnpj", "prestadores", ["cnpj"], unique=True,
        postgresql_where=sa.text("cnpj IS NOT NULL"),
    )


def _create_unidades() -> None:
    op.create_table(
        "unidades",
        sa.Column("id",           sa.Text(),    nullable=False),
        sa.Column("prestador_id", sa.Text(),    nullable=False),
        sa.Column("unidade_id",   sa.Text(),    nullable=False),
        sa.Column("nome",         sa.Text(),    nullable=False),
        sa.Column("tipo",         sa.Text(),    nullable=True),
        sa.Column("ativo",        sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("criado_em",    sa.Text(),    nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["prestador_id"], ["prestadores.id"], name="fk_unidades_prestador"),
        sa.UniqueConstraint("prestador_id", "unidade_id", name="uq_prestador_unidade"),
    )


def linhas_baseline_a_preservar(bind) -> int:
    """Guarda contra destruição silenciosa. Retorna o nº de linhas SE 'prestadores'
    está no schema baseline (sem org_id) E contém dados (→ abortar, backfill manual).
    Retorna 0 quando não existe, já tem org_id, ou está vazia (→ seguro recriar).

    Helper puro/testável (recebe um bind SQLAlchemy)."""
    insp = inspect(bind)
    if not insp.has_table("prestadores"):
        return 0
    if "org_id" in {c["name"] for c in insp.get_columns("prestadores")}:
        return 0
    return bind.execute(sa.text("SELECT COUNT(*) FROM prestadores")).scalar() or 0


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if insp.has_table("prestadores"):
        tem_org_id = "org_id" in {c["name"] for c in insp.get_columns("prestadores")}
        if not tem_org_id:
            n = linhas_baseline_a_preservar(bind)
            if n > 0:
                raise RuntimeError(
                    "TICKET-5C-BIS-C.1: 'prestadores' está no schema baseline (sem org_id) "
                    f"e contém {n} linha(s). Migration ABORTADA para não destruir dados — "
                    "faça o backfill manual para o schema Ticket-30 antes de aplicar."
                )
            # Vazia → drop + recreate no schema Ticket-30.
            if insp.has_table("unidades"):
                op.drop_table("unidades")
            op.drop_table("prestadores")
            _create_prestadores()
            _create_unidades()
        else:
            # Já no schema org_id (ex.: SQLite via init_tables) → só garante unidades.
            if not insp.has_table("unidades"):
                _create_unidades()
    else:
        _create_prestadores()
        _create_unidades()


def downgrade() -> None:
    # Não restaura o baseline antigo (stale); apenas remove o schema Ticket-30.
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("unidades"):
        op.drop_table("unidades")
    if insp.has_table("prestadores"):
        op.drop_table("prestadores")
