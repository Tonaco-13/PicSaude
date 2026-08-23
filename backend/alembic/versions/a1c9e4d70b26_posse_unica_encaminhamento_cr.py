"""ENG-016 §6 (`core`): unicidade de posse ativa no encaminhamento e na contrarreferência

Espelho exato do #168 (COER-2, `c0e2f1a3b4d5`) sobre a TERCEIRA circulação.

POR QUE AGORA
-------------
`encaminhamento_custodia` e `contrarreferencia_custodia` já nasceram com
`encerrada_em` — a forma de POSSE, não de ledger —, mas sem o índice único
parcial que a torna invariante. Até aqui a unicidade vivia só na convenção do
código (`_fechar_custodia_ativa` seguido de `_abrir_custodia`), e a onda ENG-016
passa a ESCREVER custódia pelas telas, inclusive por um gesto novo do cidadão
(`entregar`, §1a). Convenção de código não é invariante de banco (COER-2), e
dupla posse ativa é o **R2 na camada de custódia** (CLAUDE.md §2a): um objeto em
dois lugares ao mesmo tempo é alarme, não erro cosmético.

ORDEM OBRIGATÓRIA DENTRO DO UPGRADE (mesma do #168)
---------------------------------------------------
1. **DATA-FIX primeiro.** Sem ele, `CREATE UNIQUE INDEX` estoura com
   IntegrityError em qualquer banco que já tenha acumulado violação — e o
   deploy morre no `alembic upgrade head`. Nos caminhos de hoje a dupla posse
   não deveria existir (o fechamento sempre precede a abertura), mas "não
   deveria" é a frase que o COER-2 existe para não aceitar: a migração
   reconcilia o que encontrar, e num banco limpo não encontra nada e não faz
   nada.
2. **CONSTRAINT depois**, nos DOIS dialetos (CLAUDE.md §9):
     PostgreSQL 15+ : (obj_id, item_id) NULLS NOT DISTINCT WHERE encerrada_em IS NULL
       — sem `NULLS NOT DISTINCT`, dois (obj, NULL) NÃO colidem, e a dupla posse
         do OBJETO INTEIRO passa silenciosa. É o caso normal aqui: as duas
         tabelas só operam em nível-objeto hoje (`item_id` sempre NULL), então
         sem essa cláusula o índice não guardaria absolutamente nada.
     SQLite         : (obj_id, COALESCE(item_id, -1)) WHERE encerrada_em IS NULL
       — o SQLite não tem `NULLS NOT DISTINCT`; -1 é sentinela segura
         (`item_id`, quando existe, é FK e sempre > 0).

O FORMATO DE `encerrada_em` DA CONTRARREFERÊNCIA — verificado, como o despacho
pediu: `character varying(40)` nas DUAS tabelas, nullable, mesma semântica
("posse atual ⇔ encerrada_em IS NULL"). O espelho é literal, sem adaptação.

NOTA SOBRE `contrarreferencia_custodia.item_id`: a coluna existe e é nullable,
mas não há `contrarreferencia_itens` nem FK — a CR é monolítica hoje. O índice
cobre o par mesmo assim, por simetria: se um dia a CR ganhar itens, a guarda já
está no lugar, e uma guarda que precisa ser lembrada depois é a que falta.

A TUPLA DO QUE ESTA MIGRAÇÃO TOCOU vai escrita nela mesma, por valor
(CLAUDE.md §9 — "a migração declara sobre o que agiu"): lista viva resolvida na
leitura faria bancos no mesmo `head` divergirem conforme quando rodassem.
"""
from __future__ import annotations

import json
from datetime import datetime

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a1c9e4d70b26"
down_revision = "f2d8b41c9e73"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# O QUE ESTA MIGRAÇÃO AGIU SOBRE — congelado por valor (§9).
#
# (tabela de custódia, coluna-objeto, tabela de ledger, nome do índice PG,
#  nome do índice SQLite)
# ---------------------------------------------------------------------------
_ALVOS: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "encaminhamento_custodia", "encaminhamento_id", "encaminhamento_eventos",
        "uq_custodia_ativa_encaminhamento_item_pg",
        "uq_custodia_ativa_encaminhamento_item_sqlite",
    ),
    (
        "contrarreferencia_custodia", "contrarreferencia_id", "contrarreferencia_eventos",
        "uq_custodia_ativa_contrarreferencia_item_pg",
        "uq_custodia_ativa_contrarreferencia_item_sqlite",
    ),
)


def _reconciliar(bind, tabela: str, coluna_obj: str, tabela_eventos: str) -> int:
    """Encerra custódias ativas excedentes por (objeto, item-coalesced).

    Régua de corte idêntica à do COER-2: mantém a MAIS RECENTE por
    `(created_at DESC, id DESC)` e encerra as demais. Determinístico e
    idempotente — reexecutar num banco já coerente não acha grupo nenhum.
    """
    agora = datetime.utcnow().isoformat()

    grupos = bind.execute(sa.text(
        f"""
        SELECT {coluna_obj},
               CASE WHEN item_id IS NULL THEN -1 ELSE item_id END AS k
          FROM {tabela}
         WHERE encerrada_em IS NULL
         GROUP BY {coluna_obj}, CASE WHEN item_id IS NULL THEN -1 ELSE item_id END
        HAVING COUNT(*) > 1
        """
    )).fetchall()

    encerradas = 0
    for obj_id, k in grupos:
        if k == -1:
            item_pred, params = "item_id IS NULL", {"oid": obj_id}
        else:
            item_pred, params = "item_id = :iid", {"oid": obj_id, "iid": k}

        ativos = bind.execute(sa.text(
            f"""
            SELECT id, detentor_tipo, detentor_id
              FROM {tabela}
             WHERE {coluna_obj} = :oid AND {item_pred} AND encerrada_em IS NULL
             ORDER BY created_at DESC, id DESC
            """
        ), params).fetchall()

        mantida_id = ativos[0][0]
        for extra_id, det_tipo, det_id in ativos[1:]:
            bind.execute(
                sa.text(f"UPDATE {tabela} SET encerrada_em = :agora WHERE id = :id"),
                {"agora": agora, "id": extra_id},
            )

            payload = json.dumps({
                "custodia_id_encerrada": extra_id,
                "custodia_id_mantida": mantida_id,
                "detentor_tipo": det_tipo,
                "detentor_id": det_id,
                "nivel": "objeto" if k == -1 else "item",
                "item_id": None if k == -1 else k,
                # O `origem` DISTINGUE este data-fix dos homônimos (CLAUDE.md §2:
                # o mesmo nome de evento tem sentidos próprios no ledger da
                # receita e no do exame). Aqui: "havia dupla posse e foi
                # reconciliada", como no COER-2 original.
                "origem": "migracao_eng016_posse_unica",
            }, ensure_ascii=False)

            # Ledger append-only (CLAUDE.md §2): a reconciliação é fato de
            # negócio e entra como INSERT — os triggers de imutabilidade recusam
            # UPDATE/DELETE, não INSERT. `instance_id` NULL: registro de
            # migração, sem marca d'água de instalação. Ator = sistema.
            bind.execute(sa.text(
                f"""
                INSERT INTO {tabela_eventos}
                    ({coluna_obj}, tipo_evento, ator_tipo, ator_id,
                     payload, instance_id, created_at)
                VALUES
                    (:oid, 'custodia_reconciliada_data_fix', 'sistema',
                     'migracao_eng016', :payload, NULL, :agora)
                """
            ), {"oid": obj_id, "payload": payload, "agora": agora})
            encerradas += 1

    return encerradas


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(
            f"Dialeto '{dialect}' não suportado pela ENG-016 §6 "
            "(esperado postgresql ou sqlite)."
        )

    for tabela, coluna_obj, tabela_eventos, idx_pg, idx_sqlite in _ALVOS:
        # 1. data-fix ANTES da constraint — senão o índice falha no deploy.
        _reconciliar(bind, tabela, coluna_obj, tabela_eventos)

        # 2. constraint, dialect-aware.
        if dialect == "postgresql":
            op.execute(
                f"CREATE UNIQUE INDEX {idx_pg} "
                f"ON {tabela} ({coluna_obj}, item_id) "
                "NULLS NOT DISTINCT "
                "WHERE encerrada_em IS NULL"
            )
        else:
            op.execute(
                f"CREATE UNIQUE INDEX {idx_sqlite} "
                f"ON {tabela} ({coluna_obj}, COALESCE(item_id, -1)) "
                "WHERE encerrada_em IS NULL"
            )


def downgrade() -> None:
    # Só a constraint volta. A reconciliação é correção de DADOS, não de schema,
    # e é irreversível por desenho — o ledger já registrou o que foi feito.
    bind = op.get_bind()
    dialect = bind.dialect.name
    for _tabela, _coluna, _eventos, idx_pg, idx_sqlite in _ALVOS:
        if dialect == "postgresql":
            op.execute(f"DROP INDEX IF EXISTS {idx_pg}")
        elif dialect == "sqlite":
            op.execute(f"DROP INDEX IF EXISTS {idx_sqlite}")
