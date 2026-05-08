"""regulariza tabelas do subdomínio circulação diagnóstica

Migration de regularização de débito técnico — não introduz feature nova.

Revision ID: a3f5c8d9e1b2
Revises: e2e98a4780e4
Create Date: 2026-05-08

Contexto histórico:
~~~~~~~~~~~~~~~~~~~

As três tabelas do subdomínio circulação diagnóstica (Ticket 52) foram
originalmente criadas via SQL legado em ``backend/migrations/052_circulacao_diagnostica.sql``
(idempotente, ``CREATE TABLE IF NOT EXISTS``) ou via ``init_tables.py``
(``Base.metadata.create_all()``). Ambos os caminhos contornam o Alembic.

Consequência: ambientes onde ``alembic upgrade head`` é o único caminho de
provisionamento (CI, deploy fresco no Render, contribuidor que clona o repo)
não tinham essas tabelas. A cadeia Alembic estava quebrada para esses
cenários.

Esta migration regulariza a dívida: registra formalmente as 3 tabelas na
cadeia Alembic, com schema idêntico ao SQL legado (que é a fonte de verdade
do banco produção atual). O guard ``_table_exists`` torna a operação no-op
em ambientes que já têm as tabelas (SQLite de dev), seguindo o padrão do
baseline manual ``037d38d98806``.

Decisões arquiteturais:
~~~~~~~~~~~~~~~~~~~~~~~

- **Schema-source-of-truth**: ``backend/migrations/052_circulacao_diagnostica.sql``
  (datado de 2026-03-31, Ticket 52). Reproduz fielmente: tipos, defaults,
  FKs, índices nomeados ``idx_*``.

- **``_table_exists`` guard**: ambientes pré-existentes (Mac do dev) têm
  as tabelas; ambientes novos (CI/deploy) não têm. O guard cobre os dois
  caminhos sem branchar.

- **``server_default`` em vez de ``default``** (CODEX-recomendado, 2026-05-08):
  ``default`` é Python-side (SQLAlchemy preenche em INSERT); ``server_default``
  vai para o DDL como ``DEFAULT 'selecionado'``, replicando exatamente o
  SQL legado.

- **Índices nomeados ``idx_*``** (não ``ix_*``): segue o SQL legado
  (fonte de verdade do banco produção). O drift entre ``index=True`` no
  model Python (que gera ``ix_*``) e ``idx_*`` real é capturado pela
  Task #5 — investigação separada, não bloqueia esta migration.

- **Ordem de criação** (CODEX-recomendado): mãe → itens → eventos.
  Respeita FKs. Downgrade em ordem inversa.

- **Sem ``instance_id``**: o ``instance_id`` é adicionado pela migration
  ``4b1ce80a017d_etapa4b_add_instance_id`` (sucessora desta na cadeia).
  Manter as duas migrations separadas reflete que são preocupações
  ortogonais.

- **Classe (CLAUDE.md §10)**: ``core`` — toca o ledger
  (``circulacao_diagnostica_eventos`` é tabela ``*_eventos``). Validada
  pelo CODEX em consulta ``docs/CONSULTA-CODEX-MIGRATION-CIRCULACAO.md``
  (2026-05-08).

Validação pós-condição:
~~~~~~~~~~~~~~~~~~~~~~~

A checagem de drift (colunas obrigatórias, FKs, defaults, índices) é feita
nos testes em ``tests/test_migration_regulariza_circulacao_diagnostica.py``
— não dentro da DDL. Mantém a migration limpa e o oráculo de correção
isolado no pytest.

Referências:
~~~~~~~~~~~~

- ``backend/migrations/052_circulacao_diagnostica.sql`` — DDL fonte
- ``app/models/circulacao_diagnostica.py``,
  ``app/models/circulacao_diagnostica_evento.py``,
  ``app/models/circulacao_diagnostica_item.py`` — models
- ``docs/CONSULTA-CODEX-MIGRATION-CIRCULACAO.md`` — revisão CODEX
- ``docs/PLANO-PRODUCAO-V2.md`` §4 — contexto da Etapa 4
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------

revision: str = "a3f5c8d9e1b2"
down_revision: Union[str, Sequence[str], None] = "e2e98a4780e4"  # ticket21_prescritor_certificados
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helper — idempotência (mesmo padrão do baseline 037d38d98806)
# ---------------------------------------------------------------------------


def _table_exists(name: str) -> bool:
    """Retorna True se a tabela existe no banco conectado."""
    bind = op.get_bind()
    return inspect(bind).has_table(name)


# ---------------------------------------------------------------------------
# UPGRADE — cria 3 tabelas (mãe → itens → eventos)
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """
    Cria as 3 tabelas do subdomínio circulação diagnóstica, na ordem que
    respeita as constraints de FK:

      1. circulacoes_diagnosticas (mãe)
      2. circulacao_diagnostica_itens (filha — FK para mãe)
      3. circulacao_diagnostica_eventos (filha — FK para mãe, ledger)

    Cada CREATE é envolvido em ``_table_exists()`` guard para idempotência:
    se o banco já tiver a tabela, o bloco é pulado silenciosamente.
    """

    # ------------------------------------------------------------------
    # 1. Tabela principal — circulacoes_diagnosticas
    # ------------------------------------------------------------------
    if not _table_exists("circulacoes_diagnosticas"):
        op.create_table(
            "circulacoes_diagnosticas",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("protocolo", sa.Text(), nullable=False),
            sa.Column("chave_circulacao", sa.Text(), nullable=False),
            sa.Column("pedido_id", sa.Integer(), nullable=False),
            sa.Column("paciente_id", sa.Integer(), nullable=False),
            sa.Column("org_id", sa.Text(), nullable=False),
            sa.Column("unidade_id", sa.Text(), nullable=False),
            sa.Column("data_hora_proposta", sa.Text(), nullable=True),
            sa.Column("local_texto", sa.Text(), nullable=True),
            sa.Column("instrucoes_preparo", sa.Text(), nullable=True),
            sa.Column("observacao", sa.Text(), nullable=True),
            sa.Column(
                "status",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'selecionado'"),
            ),
            sa.Column(
                "tipo_emissao",
                sa.Text(),
                nullable=False,
                server_default=sa.text("'novo'"),
            ),
            sa.Column("origem_circulacao_id", sa.Integer(), nullable=True),
            sa.Column("validade", sa.Text(), nullable=False),
            sa.Column("criado_por", sa.Text(), nullable=False),
            sa.Column("criado_em", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("protocolo"),
            sa.UniqueConstraint("chave_circulacao"),
            sa.ForeignKeyConstraint(["pedido_id"], ["pedidos_exame.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.ForeignKeyConstraint(
                ["origem_circulacao_id"], ["circulacoes_diagnosticas.id"]
            ),
        )
        op.create_index(
            "idx_circulacoes_diagnosticas_pedido_id",
            "circulacoes_diagnosticas",
            ["pedido_id"],
        )
        op.create_index(
            "idx_circulacoes_diagnosticas_paciente_id",
            "circulacoes_diagnosticas",
            ["paciente_id"],
        )
        op.create_index(
            "idx_circulacoes_diagnosticas_org_id",
            "circulacoes_diagnosticas",
            ["org_id"],
        )
        op.create_index(
            "idx_circulacoes_diagnosticas_unidade_id",
            "circulacoes_diagnosticas",
            ["unidade_id"],
        )

    # ------------------------------------------------------------------
    # 2. Itens — circulacao_diagnostica_itens
    # ------------------------------------------------------------------
    if not _table_exists("circulacao_diagnostica_itens"):
        op.create_table(
            "circulacao_diagnostica_itens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("circulacao_id", sa.Integer(), nullable=False),
            sa.Column("pedido_exame_item_id", sa.Integer(), nullable=False),
            sa.Column("nome_exame", sa.Text(), nullable=False),
            sa.Column("criado_em", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["circulacao_id"], ["circulacoes_diagnosticas.id"]
            ),
            sa.ForeignKeyConstraint(
                ["pedido_exame_item_id"], ["pedido_exame_itens.id"]
            ),
        )
        op.create_index(
            "idx_circulacao_diagnostica_itens_circulacao_id",
            "circulacao_diagnostica_itens",
            ["circulacao_id"],
        )
        op.create_index(
            "idx_circulacao_diagnostica_itens_pedido_exame_item_id",
            "circulacao_diagnostica_itens",
            ["pedido_exame_item_id"],
        )

    # ------------------------------------------------------------------
    # 3. Ledger imutável — circulacao_diagnostica_eventos
    # ------------------------------------------------------------------
    if not _table_exists("circulacao_diagnostica_eventos"):
        op.create_table(
            "circulacao_diagnostica_eventos",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("circulacao_id", sa.Integer(), nullable=False),
            sa.Column("tipo_evento", sa.Text(), nullable=False),
            sa.Column("dados_json", sa.Text(), nullable=True),
            sa.Column("criado_em", sa.Text(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(
                ["circulacao_id"], ["circulacoes_diagnosticas.id"]
            ),
        )
        op.create_index(
            "idx_circulacao_diagnostica_eventos_circulacao_id",
            "circulacao_diagnostica_eventos",
            ["circulacao_id"],
        )


# ---------------------------------------------------------------------------
# DOWNGRADE — remove em ordem inversa (filhas antes da mãe)
# ---------------------------------------------------------------------------


def downgrade() -> None:
    """
    Remove as 3 tabelas em ordem inversa de criação (filhas → mãe) para
    não violar constraints de FK. Cada DROP é guardado por
    ``_table_exists`` para tolerar ambientes parcialmente driftados.
    """

    if _table_exists("circulacao_diagnostica_eventos"):
        op.drop_index(
            "idx_circulacao_diagnostica_eventos_circulacao_id",
            table_name="circulacao_diagnostica_eventos",
        )
        op.drop_table("circulacao_diagnostica_eventos")

    if _table_exists("circulacao_diagnostica_itens"):
        op.drop_index(
            "idx_circulacao_diagnostica_itens_pedido_exame_item_id",
            table_name="circulacao_diagnostica_itens",
        )
        op.drop_index(
            "idx_circulacao_diagnostica_itens_circulacao_id",
            table_name="circulacao_diagnostica_itens",
        )
        op.drop_table("circulacao_diagnostica_itens")

    if _table_exists("circulacoes_diagnosticas"):
        op.drop_index(
            "idx_circulacoes_diagnosticas_unidade_id",
            table_name="circulacoes_diagnosticas",
        )
        op.drop_index(
            "idx_circulacoes_diagnosticas_org_id",
            table_name="circulacoes_diagnosticas",
        )
        op.drop_index(
            "idx_circulacoes_diagnosticas_paciente_id",
            table_name="circulacoes_diagnosticas",
        )
        op.drop_index(
            "idx_circulacoes_diagnosticas_pedido_id",
            table_name="circulacoes_diagnosticas",
        )
        op.drop_table("circulacoes_diagnosticas")
