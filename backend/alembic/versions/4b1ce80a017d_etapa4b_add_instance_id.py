"""etapa4b add instance_id to ledger and main tables

Revision ID: 4b1ce80a017d
Revises: e2e98a4780e4
Create Date: 2026-05-07 09:00:00.000000

Sub-tarefa 4B do plano de produção (docs/PLANO-PRODUCAO-V2.md §4).

Adiciona coluna ``instance_id VARCHAR(36) NULL`` em 10 tabelas para suportar
a marca d'água de rastreabilidade da instância PicSaúde, conforme
``DATA-PROTECTION.md §4.2``.

Tabelas afetadas:

  Eventos do ledger imutável (6):
    - prescricao_eventos
    - pedido_exame_eventos
    - laudo_eventos
    - circulacao_diagnostica_eventos
    - agendamento_eventos
    - eventos_publicacao            (outbox externo G4A)

  Objetos sanitários principais (4):
    - prescricoes
    - pedidos_exame
    - laudos
    - agendamentos

Decisões arquiteturais (validadas pelo CODEX em 2026-05-06):

  - Coluna NULLABLE: preserva registros pré-instance_id sem forçar backfill
    automático (o que violaria a imutabilidade do ledger). Backfill será
    operação manual controlada na Etapa 8 (pré-deploy), não automática.

  - Tipo VARCHAR(36): compatibilidade dual SQLite/PostgreSQL. Formato
    canônico de UUID v4 ("xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx") cabe em
    36 caracteres. Em produção PostgreSQL pura, pode ser refatorado para
    tipo nativo ``UUID`` (16 bytes) sem perda de dados.

  - ``op.batch_alter_table``: necessário para SQLite (que não suporta ALTER
    TABLE ADD COLUMN com algumas constraints). Em PostgreSQL, batch é
    transparente — gera ALTER TABLE direto.

  - ``instance_id`` NÃO entra no documento canônico assinado
    (``domain/documento_canonico.py``). É metadado externo, não conteúdo
    clínico. Não bumpar ``VERSAO_ESQUEMA``.

Após esta migration, novos registros (criados via helper de inserção em
ledger da Sub-tarefa 4C) sempre terão ``instance_id`` preenchido. Registros
antigos permanecem com ``NULL`` até backfill manual.

Sem índices nesta migration: ``instance_id`` é primariamente metadado de
auditoria, não chave de busca rotineira. Se necessário no futuro, índice
parcial ``WHERE instance_id IS NOT NULL`` pode ser adicionado.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic
revision = "4b1ce80a017d"
down_revision = "a3f5c8d9e1b2"  # regulariza_circulacao_diagnostica (precondição: cria a tabela circulacao_diagnostica_eventos)
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Lista das tabelas afetadas
# ---------------------------------------------------------------------------

# Eventos do ledger imutável.
# instance_id em cada evento permite rastrear qual instância gerou o evento
# (DATA-PROTECTION.md §4.2 — marca d'água de rastreabilidade).
TABELAS_LEDGER = [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "circulacao_diagnostica_eventos",
    "agendamento_eventos",
    "eventos_publicacao",  # outbox externo G4A (rastreabilidade externa)
]

# Objetos sanitários principais.
# instance_id em cada objeto permite identificar a origem mesmo após
# replicação/clone do banco — útil em forense de exfiltração de dados.
TABELAS_PRINCIPAIS = [
    "prescricoes",
    "pedidos_exame",
    "laudos",
    "agendamentos",
]

TODAS_AS_TABELAS = TABELAS_LEDGER + TABELAS_PRINCIPAIS


# ---------------------------------------------------------------------------
# Upgrade / Downgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    """Adiciona coluna ``instance_id`` NULLABLE em 10 tabelas."""
    for tabela in TODAS_AS_TABELAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "instance_id",
                    sa.String(length=36),
                    nullable=True,
                    comment=(
                        "UUID v4 da instância PicSaúde "
                        "(DATA-PROTECTION.md §4.2 — marca d'água)"
                    ),
                )
            )


def downgrade() -> None:
    """Remove coluna ``instance_id`` de 10 tabelas (rollback)."""
    for tabela in TODAS_AS_TABELAS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.drop_column("instance_id")
