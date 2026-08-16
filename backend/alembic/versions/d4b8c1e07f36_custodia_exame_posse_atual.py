"""Custódia de exame ganha posse atual: encerrada_em + unicidade + data-fix

TICKET J.10-CORE (`core`) — DESPACHO-ENG-012 §7, caminho (b) do
`DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md` §5, recomendado pelo arquiteto e
aprovado no parecer `J7-PRS` §3.

O QUE MUDA E POR QUÊ
--------------------
`pedido_exame_custodia` nasceu como **ledger de transferências** (`de`/`para`/
`transferido_em`), enquanto `prescricao_custodia` é modelo de **posse atual**
(`detentor_*` + `encerrada_em` + índice único parcial, COER-2). Num ledger
append-only **não existe "linha ativa"** para um índice único restringir: toda
linha é fato passado e a posse é leitura derivada (`ORDER BY id DESC LIMIT 1`).

Consequência: a unicidade de posse do exame — um objeto não pode estar em dois
lugares ao mesmo tempo, o **R2 na camada de custódia** — era afirmada só por
convenção de código. A lição do COER-2 e o §9 do CLAUDE.md são explícitos:
*invariante afirmado sem constraint de banco não é invariante*. Esta migração
dá ao exame a mesma forma que a receita já tem, nos DOIS dialetos.

ORDEM OBRIGATÓRIA DENTRO DO upgrade()
-------------------------------------
  1. COLUNA   — `encerrada_em` nullable (toda linha histórica nasce "ativa").
  2. DATA-FIX — sem ele o índice falha imediatamente: como todas as linhas
     nascem ativas, um pedido com 3 transferências teria 3 posses ativas.
     Régua de corte (a mesma do COER-2): por `(pedido_id, item_id)`, mantém
     aberta a linha mais recente por `(transferido_em DESC, id DESC)`.
  3. CONSTRAINT — índice único parcial, dialect-aware:
       PostgreSQL 15+: (pedido_id, item_id) NULLS NOT DISTINCT WHERE ...
         (sem NULLS NOT DISTINCT, dois (pid, NULL) não colidem e a dupla posse
          de PEDIDO INTEIRO passa silenciosa — §14 do COER-2)
       SQLite:         (pedido_id, COALESCE(item_id, -1)) WHERE ...
         (-1 é sentinela segura: item_id é FK para pedido_exame_itens.id, > 0)

O `encerrada_em` DE CADA LINHA FECHADA É A DATA DA TRANSFERÊNCIA SEGUINTE
------------------------------------------------------------------------
E não `utcnow()`. Uma custódia terminou quando a próxima começou — é um fato
que o próprio ledger já registra. Carimbar "agora" inventaria uma história em
que todas as posses antigas terminaram no dia da migração, e o R1 (§2a) diz que
relatório de período fechado deve ser reproduzível para sempre: reescrever o
passado com a data do deploy quebraria justamente isso.

SOBRE O EVENTO EMITIDO
----------------------
Cada linha fechada emite `custodia_reconciliada_data_fix` em
`pedido_exame_eventos` — mesmo nome e mesma disciplina do COER-2 (emitido **pela
migração**, nunca no caminho clínico). Nota de leitura para o auditor: aqui o
evento significa *"linha superada pelo modelo de posse atual"*, não *"anomalia
encontrada"*. Na forma antiga a cadeia era coerente por construção (a última
linha era o detentor); o que a migração faz é **normalizar**, não corrigir. O
payload carrega `origem` para que a distinção fique legível no ledger.
"""
from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d4b8c1e07f36"
down_revision = "c0e2f1a3b4d5"
branch_labels = None
depends_on = None


# Nomes dos índices — distintos por dialeto (a expressão indexada difere).
_IDX_PG = "uq_custodia_exame_ativa_pedido_item_pg"
_IDX_SQLITE = "uq_custodia_exame_ativa_pedido_item_sqlite"


def _reconciliar_posse_exame(bind) -> int:
    """Fecha as custódias superadas, mantendo a mais recente por grupo.

    Determinística e idempotente: reexecutar num banco já normalizado não
    encontra grupo com mais de uma linha ativa e não faz nada.
    """
    grupos = bind.execute(sa.text(
        """
        SELECT pedido_id,
               CASE WHEN item_id IS NULL THEN -1 ELSE item_id END AS k
          FROM pedido_exame_custodia
         WHERE encerrada_em IS NULL
         GROUP BY pedido_id, CASE WHEN item_id IS NULL THEN -1 ELSE item_id END
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    encerradas = 0
    for pedido_id, k in grupos:
        if k == -1:
            item_pred = "item_id IS NULL"
            params = {"pid": pedido_id}
        else:
            item_pred = "item_id = :iid"
            params = {"pid": pedido_id, "iid": k}

        ativas = bind.execute(sa.text(
            f"""
            SELECT id, de, para, transferido_em
              FROM pedido_exame_custodia
             WHERE pedido_id = :pid AND {item_pred} AND encerrada_em IS NULL
             ORDER BY transferido_em DESC, id DESC
            """
        ), params).fetchall()

        # ativas[0] é a posse corrente — permanece aberta. As demais são fatos
        # passados: cada uma terminou quando a IMEDIATAMENTE seguinte começou,
        # e a seguinte é a anterior nesta lista (ordenada do mais novo ao mais
        # antigo). Daí `ativas[i - 1]` ser quem carimba a data de `ativas[i]`.
        mantida_id = ativas[0][0]
        for i in range(1, len(ativas)):
            linha_id, de, para, _ = ativas[i]
            fim = ativas[i - 1][3]        # transferido_em de quem a sucedeu

            bind.execute(sa.text(
                "UPDATE pedido_exame_custodia SET encerrada_em = :fim WHERE id = :id"
            ), {"fim": fim, "id": linha_id})

            payload = json.dumps({
                "custodia_id_encerrada": linha_id,
                "custodia_id_mantida":   mantida_id,
                "de":                    de,
                "para":                  para,
                "nivel":                 "pedido" if k == -1 else "item",
                "item_id":               None if k == -1 else k,
                "origem":                "migracao_j10_posse_atual",
            }, ensure_ascii=False, default=str)

            # Ledger append-only (CLAUDE.md §2): os triggers de imutabilidade
            # recusam UPDATE/DELETE — não INSERT. `instance_id` NULL: registro
            # de migração, sem marca d'água de instalação.
            bind.execute(sa.text(
                """
                INSERT INTO pedido_exame_eventos
                    (pedido_id, tipo_evento, dados_json, criado_em, instance_id)
                VALUES
                    (:pid, 'custodia_reconciliada_data_fix', :payload, :criado_em, NULL)
                """
            ), {"pid": pedido_id, "payload": payload, "criado_em": fim})
            encerradas += 1

    return encerradas


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    # ── 1. COLUNA ────────────────────────────────────────────────────────────
    op.add_column(
        "pedido_exame_custodia",
        sa.Column("encerrada_em", sa.DateTime(), nullable=True),
    )

    # ── 2. DATA-FIX — antes da constraint, senão o índice falha ──────────────
    _reconciliar_posse_exame(bind)

    # ── 3. CONSTRAINT — índice único parcial, dialect-aware ──────────────────
    if dialect == "postgresql":
        op.execute(
            f"CREATE UNIQUE INDEX {_IDX_PG} "
            "ON pedido_exame_custodia (pedido_id, item_id) "
            "NULLS NOT DISTINCT "
            "WHERE encerrada_em IS NULL"
        )
    elif dialect == "sqlite":
        op.execute(
            f"CREATE UNIQUE INDEX {_IDX_SQLITE} "
            "ON pedido_exame_custodia (pedido_id, COALESCE(item_id, -1)) "
            "WHERE encerrada_em IS NULL"
        )
    else:
        raise RuntimeError(
            f"Dialeto '{dialect}' não suportado por J.10-CORE "
            "(esperado postgresql ou sqlite)."
        )


def downgrade() -> None:
    # A reconciliação é correção de DADOS e é irreversível por design — o ledger
    # já a registrou. Reversível: o índice e a coluna.
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        op.execute(f"DROP INDEX IF EXISTS {_IDX_PG}")
    elif dialect == "sqlite":
        op.execute(f"DROP INDEX IF EXISTS {_IDX_SQLITE}")
    op.drop_column("pedido_exame_custodia", "encerrada_em")
