"""
cnes_demo.py
============
Base CNES da demo — **durável**, criada no boot da aplicação.

Micro-ticket `ops` do DESPACHO-ENG-011 §5.

Por que existe
--------------
A validação CNES do prescritor (`app/domain/cnes_prescritor.py`) e a resolução
de identidade por conselho (`app/domain/identidade_prescritor.py`) **sempre**
leem um SQLite dedicado — `_get_cnes_conn()` → `_resolve_sqlite_db_path()` —
mesmo quando as tabelas da aplicação vivem em PostgreSQL (arquitetura dual, ver
`docs/arquitetura_dual_bancos.md`).

Na vitrine (`PICSAUDE_DEMO_MODE=true` + `DATABASE_URL` de PostgreSQL) esse
arquivo — `/data/pix_saude_demo.db` — **não é criado por ninguém**:

  • `alembic upgrade head` migra a PostgreSQL;
  • `seed_demo.py` abre `get_conn()`, que em PostgreSQL cria o cinturão CNES
    *na PostgreSQL* — onde `_get_cnes_conn()` nunca vai olhar.

Resultado: `FileNotFoundError` no caminho de validação. O selo "baixo" do guia
deixa de ser a verdade sobre identidade sintética (TICKET-J.4 (c)) e vira falha
de base ausente. Em 14/08 o arquivo foi criado à mão pelo Shell do Render e
morreu no redeploy seguinte.

Por que no boot, e não no `predeploy.sh`
----------------------------------------
O despacho §5 propôs criar o arquivo no `predeploy.sh` e **exigiu verificar**
se ele sobrevive até o container do serviço. Não sobrevive — a documentação do
Render é explícita nos dois pontos:

  • pre-deploy: *"The pre-deploy command executes on a separate instance from
    your running service. […] Changes you make to the filesystem are not
    reflected in the deployed service."*  (render.com/docs/deploys)
  • disco: *"By default, Render services have an ephemeral filesystem. […]
    without a persistent disk, any changes you make to a service's local files
    are lost every time the service redeploys or restarts."* (render.com/docs/disks)

Confirmação empírica independente: o `render.yaml` não declara bloco `disk:`, e
o arquivo criado à mão em 14/08 morreu no redeploy — o que só acontece se
`/data` for efêmero. Fosse disco persistente, teria sobrevivido.

Logo, o sítio correto é o **boot da aplicação** (mesma decisão de "durável",
sítio diferente — previsto pelo próprio §5). Roda a cada start, é idempotente e
barato.

Fronteiras (classe `ops`)
-------------------------
Não toca em tabela clínica, não emite evento no ledger, não altera estado de
objeto sanitário. Escreve **apenas** no SQLite de referência CNES, e só quando
`PICSAUDE_DEMO_MODE=true`. Falha aqui **nunca** derruba o boot: a validação CNES
é não-bloqueante por contrato (`cnes_prescritor.py`), e degradar para
`cnes_snapshot_indisponivel` é pior que o ideal, não fatal.
"""

from __future__ import annotations

import logging
import os
import sqlite3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DDL do snapshot CNES da demo — FONTE ÚNICA
# ---------------------------------------------------------------------------
# Consumido por este módulo (SQLite side-car, via sqlite3) E por `seed_demo.py`
# (cinturão de schema, via `get_conn()` — PostgreSQL ou SQLite). Uma lista de
# statements individuais, e não um script: `executescript` não existe no wrapper
# `_PgConnection`.
#
# As colunas são a UNIÃO do que as queries de produção leem — não o snapshot
# nacional inteiro (esse é carregado por `scripts/importar_cnes_br.py`, que
# deriva as colunas do CSV do DataSUS):
#
#   profissionais_cnes     cnes_prescritor.validar_cns_prescritor
#                          identidade_prescritor (NO_PROFISSIONAL, CO_CNS)
#   relacao_prof_estab     idem + _buscar_cnes_por_conselho (NU_REGISTRO,
#                          CO_CONSELHO_CLASSE, SG_UF_CRM, CO_CBO, CO_UNIDADE)
#   estabelecimentos_cnes  _verificar_vinculo_prestador (NU_CNPJ → CO_CNES),
#                          login.py / prestadores.py (TP_UNIDADE, NO_FANTASIA),
#                          identidade_prescritor (JOIN por CO_UNIDADE)
#
# `CO_UNIDADE` em `estabelecimentos_cnes` é o que faltava no cinturão anterior
# do `seed_demo.py`: sem ela o LEFT JOIN de `identidade_prescritor` quebra com
# "no such column: e.CO_UNIDADE" num banco demo SQLite.
DDL_CNES_DEMO: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS profissionais_cnes (
        CO_PROFISSIONAL_SUS TEXT,
        CO_CNS              TEXT,
        NO_PROFISSIONAL     TEXT,
        CO_CPF              TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS relacao_prof_estab (
        CO_PROFISSIONAL_SUS TEXT,
        CO_UNIDADE          TEXT,
        CO_CBO              TEXT,
        CO_CONSELHO_CLASSE  TEXT,
        NU_REGISTRO         TEXT,
        SG_UF_CRM           TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
        CO_UNIDADE   TEXT,
        CO_CNES      TEXT,
        NU_CNPJ      TEXT,
        TP_UNIDADE   TEXT,
        NO_FANTASIA  TEXT,
        CO_MUNICIPIO TEXT
    )
    """,
)

# Colunas espelhadas do banco da aplicação para o side-car. Em minúsculas nos
# apelidos porque o PostgreSQL dobra identificadores não-citados para minúsculo
# e o `RealDictCursor` devolve as chaves como vieram — apelidar é o que faz a
# leitura funcionar nos dois dialetos.
_COLUNAS_ESTABELECIMENTO: tuple[str, ...] = (
    "CO_UNIDADE", "CO_CNES", "NU_CNPJ", "TP_UNIDADE", "NO_FANTASIA", "CO_MUNICIPIO",
)


def _espelhar_estabelecimentos(sqlite_conn: sqlite3.Connection) -> int:
    """Copia `estabelecimentos_cnes` do banco da aplicação para o side-car.

    As farmácias demo (§5 do despacho: "as 2 farmácias demo do snippet manual")
    **não são declaradas aqui**. Elas já têm dono — `seed_demo.py`, que as insere
    a partir de `DISPENSADOR` / `DISPENSADOR_NORTE`, os mesmos dicts que o
    guard-rail de identidades (`test_guardrail_identidades_demo.py`) casa contra
    o `config.js`. Repetir CNPJ e código CNES aqui criaria um segundo lugar para
    a mesma verdade — exatamente o que aquele guard-rail existe para impedir.
    O side-car é **projeção** do que o seed declarou, não uma segunda declaração.

    Retorna quantas linhas foram espelhadas (0 é resultado legítimo: o schema
    vazio já basta para a validação responder `nao_encontrado` em vez de estourar).
    """
    from app.database import get_conn

    conn = get_conn()
    try:
        # Lemos as colunas que a tabela de fato TEM, em vez de assumi-las. A
        # `estabelecimentos_cnes` da vitrine foi criada por uma versão anterior
        # do cinturão do seed, sem `CO_UNIDADE` — e `CREATE TABLE IF NOT EXISTS`
        # não acrescenta coluna a tabela existente. Um SELECT fixo estouraria
        # `UndefinedColumn` justamente no ambiente que este ticket conserta.
        #
        # `information_schema` basta (só se chega aqui com PostgreSQL — guard
        # `_USE_SQLITE` no chamador), e o pré-check pela existência da tabela é
        # o mesmo padrão de `routers/login.py`: na PostgreSQL, um SELECT em
        # tabela inexistente aborta a transação inteira.
        #
        # A PostgreSQL dobra identificadores não-citados para minúsculo, então a
        # comparação é feita em minúsculo dos dois lados.
        presentes = {
            linha["column_name"] for linha in conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'estabelecimentos_cnes'"
            ).fetchall()
        }
        colunas = tuple(c for c in _COLUNAS_ESTABELECIMENTO if c.lower() in presentes)
        if "NU_CNPJ" not in colunas:
            # Sem a chave de reposição não há espelho idempotente possível; e a
            # ausência dela significa que a tabela não existe (conjunto vazio).
            return 0

        seletor = ", ".join(f"{c} AS {c.lower()}" for c in colunas)
        linhas = conn.execute(f"SELECT {seletor} FROM estabelecimentos_cnes").fetchall()
    finally:
        conn.close()

    if not linhas:
        return 0

    colunas_sql = ", ".join(colunas)
    marcadores = ", ".join("?" * len(colunas))
    for linha in linhas:
        valores = tuple(linha[c.lower()] for c in colunas)
        # Idempotência por reposição: o side-car é projeção, então a linha do
        # banco da aplicação manda. Sem DELETE, um redeploy após mudança de
        # CNES/nome deixaria as duas versões convivendo.
        sqlite_conn.execute(
            "DELETE FROM estabelecimentos_cnes WHERE NU_CNPJ = ?",
            (linha["nu_cnpj"],),
        )
        sqlite_conn.execute(
            f"INSERT INTO estabelecimentos_cnes ({colunas_sql}) VALUES ({marcadores})",
            valores,
        )
    return len(linhas)


def garantir_snapshot_cnes_demo() -> None:
    """Garante o SQLite de referência CNES da demo. Idempotente; nunca levanta.

    No-op fora de `PICSAUDE_DEMO_MODE`, e no-op quando o próprio banco da
    aplicação é SQLite — nesse caso o arquivo *é* o banco da aplicação, o
    `alembic` o cria e o `seed_demo.py` já aplica o mesmo `DDL_CNES_DEMO` nele.
    Criar o arquivo aqui, antes do alembic, só trocaria o erro claro
    ("SQLite DB não encontrado") por um obscuro ("no such table: prescricoes").
    """
    from app.config import PICSAUDE_DEMO_MODE
    from app.database import _USE_SQLITE, _resolve_sqlite_db_path

    if not PICSAUDE_DEMO_MODE:
        return
    if _USE_SQLITE:
        return

    caminho = _resolve_sqlite_db_path()
    try:
        os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
        conn = sqlite3.connect(caminho, timeout=10)
        try:
            conn.row_factory = sqlite3.Row
            for ddl in DDL_CNES_DEMO:
                conn.execute(ddl)
            espelhadas = _espelhar_estabelecimentos(conn)
            conn.commit()
        finally:
            conn.close()
        logger.info(
            "[cnes-demo] snapshot CNES garantido em %s (%d estabelecimento(s) espelhado(s))",
            caminho, espelhadas,
        )
    except Exception as exc:  # noqa: BLE001 — boot nunca cai por causa da demo
        logger.warning(
            "[cnes-demo] não foi possível garantir o snapshot CNES em %s (%s). "
            "A validação CNES degrada para 'cnes_snapshot_indisponivel' — não-bloqueante.",
            caminho, exc,
        )
