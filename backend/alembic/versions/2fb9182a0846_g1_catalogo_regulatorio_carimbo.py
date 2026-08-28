"""g1_catalogo_regulatorio_carimbo

DESENHO-TALAO-DIGITAL-SNCR.md §1/§1.1 — G1, Opção 2 (mecânica agora, dado
depois). Duas peças:

1. `catalogo_substancias` ganha `versao`/`data_snapshot` (nullable) — cada
   entrada PODE citar a versão/data exatas da publicação que a classificou.
   As 56 atuais (seed curado à mão) ficam NULL aqui: não têm citação
   pontual, só `fonte` (norma ampla). Isso não é uma lacuna desta migração
   — é honesto sobre o que o seed sempre foi.

2. `catalogo_regulatorio_carimbo` — tabela de UMA linha (id=1) que declara
   se a base está "carimbada" (completa, versionada, pronta para inverter
   o princípio da cautela — §1 do desenho). `versao IS NULL` = carimbo
   PENDENTE (comportamento atual, silêncio na ausência); `versao IS NOT
   NULL` = carimbo ativo. Esta migração insere a linha com tudo NULL —
   o carimbo nasce pendente, por design (§1.1: a fonte consolidada ainda
   não chegou; ativá-lo é gesto de uma migração/import FUTURO, não desta).

Revision ID: 2fb9182a0846
Revises: b3e7d21a90c4
Create Date: 2026-08-28 14:59:34.331140

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = '2fb9182a0846'
down_revision: Union[str, Sequence[str], None] = 'b3e7d21a90c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table)


def _tem_coluna(table: str, coluna: str) -> bool:
    bind = op.get_bind()
    return any(c["name"] == coluna for c in inspect(bind).get_columns(table))


def upgrade() -> None:
    if not _tem_coluna("catalogo_substancias", "versao"):
        op.add_column(
            "catalogo_substancias",
            sa.Column("versao", sa.String(50), nullable=True),
        )
    if not _tem_coluna("catalogo_substancias", "data_snapshot"):
        op.add_column(
            "catalogo_substancias",
            sa.Column("data_snapshot", sa.String(10), nullable=True),
        )

    if not _table_exists("catalogo_regulatorio_carimbo"):
        op.create_table(
            "catalogo_regulatorio_carimbo",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fonte", sa.String(200), nullable=True),
            sa.Column("versao", sa.String(50), nullable=True),
            sa.Column("data_snapshot", sa.String(10), nullable=True),
            sa.Column(
                "atualizado_em", sa.DateTime(), nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.execute(
            "INSERT INTO catalogo_regulatorio_carimbo "
            "(id, fonte, versao, data_snapshot) VALUES (1, NULL, NULL, NULL)"
        )


def downgrade() -> None:
    if _table_exists("catalogo_regulatorio_carimbo"):
        op.drop_table("catalogo_regulatorio_carimbo")
    if _tem_coluna("catalogo_substancias", "data_snapshot"):
        op.drop_column("catalogo_substancias", "data_snapshot")
    if _tem_coluna("catalogo_substancias", "versao"):
        op.drop_column("catalogo_substancias", "versao")
