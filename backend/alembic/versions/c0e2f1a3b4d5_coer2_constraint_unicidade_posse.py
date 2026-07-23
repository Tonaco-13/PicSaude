"""COER-2: constraint de unicidade de posse ativa + data-fix de reconciliação

TICKET-COERENCIA-DEVOLUCOES-2 (core). Instala a GUARDA durável do choke-point de
posse: no máximo UMA custódia ativa por (prescricao_id, item_id) com
encerrada_em IS NULL. Dupla posse ativa = o R2 na camada de custódia (um objeto
em dois lugares ao mesmo tempo) — alarme, não erro cosmético.

Ordem OBRIGATÓRIA dentro do upgrade (§4/§5 do ticket):
  1. DATA-FIX primeiro — reconcilia qualquer dupla-posse já existente. Sem isto,
     a criação do índice único falha com IntegrityError em qualquer banco que já
     acumulou violações. Emite `custodia_reconciliada_data_fix` no ledger (trilha).
  2. CONSTRAINT depois — índice único parcial nos DOIS dialetos (CLAUDE.md §9):
       PostgreSQL 15+: ... (prescricao_id, item_id) NULLS NOT DISTINCT WHERE ...
         (sem NULLS NOT DISTINCT, dois (pid, NULL) não colidem → dupla posse de
          PRESCRIÇÃO INTEIRA passa silenciosa — §14 do ticket)
       SQLite:         ... (prescricao_id, COALESCE(item_id, -1)) WHERE ...
         (sem NULLS NOT DISTINCT no SQLite; -1 é sentinela segura — item_id é FK
          para prescricao_itens.id, sempre > 0)

Corte da reconciliação (mesma régua do COER-2 do #119): mantém a custódia mais
recente por (created_at DESC, id DESC); encerra as demais.
"""
from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c0e2f1a3b4d5"
down_revision = "a3c7e1f95b02"
branch_labels = None
depends_on = None


# Nomes dos índices — distintos por dialeto (a expressão indexada difere).
_IDX_PG = "uq_custodia_ativa_prescricao_item_pg"
_IDX_SQLITE = "uq_custodia_ativa_prescricao_item_sqlite"


def _reconciliar_dupla_posse(bind) -> int:
    """Encerra custódias ativas excedentes por (prescricao_id, item_id-coalesced).

    Retorna quantas custódias foram encerradas. Determinístico e idempotente:
    reexecutar em um banco já limpo não encontra grupos e não faz nada.
    """
    agora = datetime.utcnow().isoformat()

    grupos = bind.execute(sa.text(
        """
        SELECT prescricao_id,
               CASE WHEN item_id IS NULL THEN -1 ELSE item_id END AS k
          FROM prescricao_custodia
         WHERE encerrada_em IS NULL
         GROUP BY prescricao_id, CASE WHEN item_id IS NULL THEN -1 ELSE item_id END
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    encerradas = 0
    for pres_id, k in grupos:
        if k == -1:
            item_pred = "item_id IS NULL"
            params = {"pid": pres_id}
        else:
            item_pred = "item_id = :iid"
            params = {"pid": pres_id, "iid": k}

        ativos = bind.execute(sa.text(
            f"""
            SELECT id, detentor_tipo, detentor_id
              FROM prescricao_custodia
             WHERE prescricao_id = :pid AND {item_pred} AND encerrada_em IS NULL
             ORDER BY created_at DESC, id DESC
            """
        ), params).fetchall()

        # ativos[0] é a "verdadeira" (mais recente). Encerra as demais.
        mantida_id = ativos[0][0]
        for extra in ativos[1:]:
            extra_id, det_tipo, det_id = extra[0], extra[1], extra[2]
            bind.execute(sa.text(
                "UPDATE prescricao_custodia SET encerrada_em = :agora WHERE id = :id"
            ), {"agora": agora, "id": extra_id})

            payload = json.dumps({
                "custodia_id_encerrada": extra_id,
                "custodia_id_mantida": mantida_id,
                "detentor_tipo": det_tipo,
                "detentor_id": det_id,
                "nivel": "prescricao" if k == -1 else "item",
                "item_id": None if k == -1 else k,
                "origem": "migracao_coer2_data_fix",
            }, ensure_ascii=False)

            # Ledger append-only (CLAUDE.md §2): a reconciliação é evento de
            # negócio. Os triggers de imutabilidade recusam UPDATE/DELETE — não
            # INSERT. instance_id NULL: registro de migração, sem marca d'água de
            # instalação. ator = sistema/migração.
            bind.execute(sa.text(
                """
                INSERT INTO prescricao_eventos
                    (prescricao_id, tipo_evento, ator_tipo, ator_id,
                     payload_json, created_at, instance_id)
                VALUES
                    (:pid, 'custodia_reconciliada_data_fix', 'sistema', 'migracao_coer2',
                     :payload, :agora, NULL)
                """
            ), {"pid": pres_id, "payload": payload, "agora": agora})
            encerradas += 1

    return encerradas


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── 1. DATA-FIX (§5) — antes da constraint, senão o índice falha ──────────
    _reconciliar_dupla_posse(bind)

    # ── 2. CONSTRAINT (Passo 1b) — índice único parcial, dialect-aware ────────
    if dialect == "postgresql":
        op.execute(
            f"CREATE UNIQUE INDEX {_IDX_PG} "
            "ON prescricao_custodia (prescricao_id, item_id) "
            "NULLS NOT DISTINCT "
            "WHERE encerrada_em IS NULL"
        )
    elif dialect == "sqlite":
        op.execute(
            f"CREATE UNIQUE INDEX {_IDX_SQLITE} "
            "ON prescricao_custodia (prescricao_id, COALESCE(item_id, -1)) "
            "WHERE encerrada_em IS NULL"
        )
    else:
        raise RuntimeError(
            f"Dialeto '{dialect}' não suportado por COER-2 "
            "(esperado postgresql ou sqlite)."
        )


def downgrade() -> None:
    # Só a constraint é reversível. A reconciliação do data-fix é uma correção de
    # dados (não um schema) e é irreversível por design — o ledger já registrou.
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(f"DROP INDEX IF EXISTS {_IDX_PG}")
    elif dialect == "sqlite":
        op.execute(f"DROP INDEX IF EXISTS {_IDX_SQLITE}")
