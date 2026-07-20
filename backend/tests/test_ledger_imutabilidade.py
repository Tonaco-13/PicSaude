"""test_ledger_imutabilidade.py — TICKET-LEDGER-TRIGGERS-MIGRACAO
================================================================
Prova que o banco RECUSA UPDATE/DELETE nas 8 tabelas de ledger (CLAUDE.md §2),
nos DOIS dialetos, com a MESMA mensagem.

Por que os dois bancos
----------------------
Antes deste ticket o teste era SQLite-only, e os triggers eram criados só por
`init_tables.py` — que o `predeploy.sh` do Render nunca chama. O teste ficava
verde em dev enquanto o PostgreSQL, onde a produção vai rodar, não tinha trigger
nenhum. Um teste que só cobre o dialeto de desenvolvimento não prova invariante
de produção.

Por que o schema vem do Alembic
-------------------------------
Os bancos aqui são construídos por `alembic upgrade head` — o MESMO comando do
`predeploy.sh`. Se o teste aplicasse os triggers por conta própria (via fixture),
provaria apenas que a fixture funciona. Quem tem que criar os triggers é a
migração.

Armadilha da vacuidade
----------------------
O ledger nasce VAZIO. `UPDATE`/`DELETE` sobre tabela sem linha nenhuma passam
sem disparar trigger BEFORE ... FOR EACH ROW — e o teste ficaria verde por
vacuidade. Todo teste de mutação aqui INSERE um evento antes e afirma que a
linha existe.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest

from app.domain.ledger_imutabilidade import TABELAS_LEDGER, mensagem

# ---------------------------------------------------------------------------
# INSERT mínimo por tabela — SQL válido nos dois dialetos.
# Timestamps como literal ISO: o PostgreSQL faz o cast para timestamp.
# ---------------------------------------------------------------------------

_INSERTS: dict[str, str] = {
    "prescricao_eventos":
        "INSERT INTO prescricao_eventos (prescricao_id, tipo_evento, ator_tipo, created_at)"
        " VALUES (999, 'teste', 'sistema', '2026-01-01T00:00:00')",
    "pedido_exame_eventos":
        "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, criado_em)"
        " VALUES (999, 'teste', '2026-01-01T00:00:00')",
    "laudo_eventos":
        "INSERT INTO laudo_eventos (laudo_id, tipo_evento, criado_em)"
        " VALUES (999, 'teste', '2026-01-01T00:00:00')",
    "agendamento_eventos":
        "INSERT INTO agendamento_eventos (agendamento_id, evento, criado_em)"
        " VALUES (999, 'teste', '2026-01-01T00:00:00')",
    "circulacao_diagnostica_eventos":
        "INSERT INTO circulacao_diagnostica_eventos (circulacao_id, tipo_evento, criado_em)"
        " VALUES (999, 'teste', '2026-01-01T00:00:00')",
    "encaminhamento_eventos":
        "INSERT INTO encaminhamento_eventos (encaminhamento_id, tipo_evento, ator_tipo, created_at)"
        " VALUES (999, 'teste', 'sistema', '2026-01-01T00:00:00')",
    "contrarreferencia_eventos":
        "INSERT INTO contrarreferencia_eventos (contrarreferencia_id, tipo_evento, ator_tipo, created_at)"
        " VALUES (999, 'teste', 'sistema', '2026-01-01T00:00:00')",
    "atestado_eventos":
        "INSERT INTO atestado_eventos (atestado_id, tipo_evento, created_at)"
        " VALUES (999, 'teste', '2026-01-01T00:00:00')",
}

# Guarda de cobertura: nenhuma tabela de ledger pode ficar de fora do teste.
assert set(_INSERTS) == set(TABELAS_LEDGER), (
    "Tabela de ledger sem INSERT de teste — a cobertura silenciosa é o próprio "
    "defeito que este ticket corrigiu."
)


# ---------------------------------------------------------------------------
# Alembic — constrói o schema pelo mesmo caminho do predeploy
# ---------------------------------------------------------------------------

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _alembic(url: str, alvo: str, *, descer: bool = False) -> None:
    """Roda `alembic upgrade|downgrade <alvo>` contra `url`.

    `env.py` lê `DATABASE_URL` a cada execução, então basta ajustar o ambiente
    ao redor da chamada — e restaurá-lo depois, para não vazar entre testes.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    url_antes = os.environ.get("DATABASE_URL")
    cwd_antes = os.getcwd()
    os.environ["DATABASE_URL"] = url
    try:
        os.chdir(_BACKEND_ROOT)
        if descer:
            command.downgrade(cfg, alvo)
        else:
            command.upgrade(cfg, alvo)
    finally:
        os.chdir(cwd_antes)
        if url_antes is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = url_antes


# ---------------------------------------------------------------------------
# Adaptadores de dialeto
# ---------------------------------------------------------------------------

class _Transacao:
    """Transação de teste — nunca faz COMMIT; tudo é revertido no fim."""

    def __init__(self, conn, erro_db, savepoint: bool):
        self._conn = conn
        self._erro_db = erro_db
        self._savepoint = savepoint
        self._n = 0

    def executar(self, sql: str) -> None:
        self._conn.execute(sql) if isinstance(self._conn, sqlite3.Connection) \
            else self._cursor().execute(sql)

    def _cursor(self):
        return self._conn.cursor()

    def escalar(self, sql: str):
        if isinstance(self._conn, sqlite3.Connection):
            return self._conn.execute(sql).fetchone()[0]
        cur = self._conn.cursor()
        cur.execute(sql)
        return cur.fetchone()[0]

    def recusa(self, sql: str) -> str:
        """Executa `sql` esperando que o banco RECUSE. Devolve a mensagem do erro.

        No PostgreSQL a exceção aborta a transação inteira; o SAVEPOINT permite
        continuar o teste depois da recusa.
        """
        self._n += 1
        ponto = f"sp_{self._n}"
        if self._savepoint:
            self._cursor().execute(f"SAVEPOINT {ponto}")
        try:
            self.executar(sql)
        except self._erro_db as exc:
            if self._savepoint:
                self._cursor().execute(f"ROLLBACK TO SAVEPOINT {ponto}")
            return str(exc)
        pytest.fail(f"O banco ACEITOU uma mutação que deveria recusar: {sql}")


class _LedgerSQLite:
    dialeto = "sqlite"
    erro_db = sqlite3.DatabaseError

    def __init__(self, db_path: str):
        self.db_path = db_path

    @contextmanager
    def transacao(self, tabela: str):
        conn = sqlite3.connect(self.db_path)
        # FK OFF: o evento de teste aponta para um pai inexistente de propósito —
        # o alvo aqui é o trigger de imutabilidade, não a integridade referencial.
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            yield _Transacao(conn, self.erro_db, savepoint=False)
        finally:
            conn.rollback()   # nada persiste
            conn.close()

    def triggers(self) -> set[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            return {
                linha[0] for linha in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger'"
                )
            }
        finally:
            conn.close()


class _LedgerPostgres:
    dialeto = "postgresql"

    def __init__(self, url: str):
        import psycopg2
        self._psycopg2 = psycopg2
        self.erro_db = psycopg2.errors.RaiseException
        self.url = url

    def _conectar(self):
        conn = self._psycopg2.connect(self.url)
        conn.autocommit = False
        return conn

    @contextmanager
    def transacao(self, tabela: str):
        conn = self._conectar()
        try:
            cur = conn.cursor()
            # DDL é transacional no PostgreSQL: dropar as FKs aqui dentro e
            # reverter no fim devolve o schema intacto. Equivale ao
            # `PRAGMA foreign_keys = OFF` do SQLite, sem tocar nos triggers
            # (`session_replication_role = replica` desativaria justamente o que
            # estamos testando).
            cur.execute(
                "SELECT conname FROM pg_constraint "
                "WHERE conrelid = %s::regclass AND contype = 'f'",
                (tabela,),
            )
            for (conname,) in cur.fetchall():
                cur.execute(f"ALTER TABLE {tabela} DROP CONSTRAINT {conname}")
            yield _Transacao(conn, self.erro_db, savepoint=True)
        finally:
            conn.rollback()   # desfaz inserts E o drop das FKs
            conn.close()

    def triggers(self) -> set[str]:
        conn = self._conectar()
        try:
            cur = conn.cursor()
            cur.execute("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal")
            return {linha[0] for linha in cur.fetchall()}
        finally:
            conn.rollback()
            conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _sqlite_migrado(tmp_path_factory) -> str:
    """SQLite limpo, schema construído SÓ por `alembic upgrade head`."""
    db = tmp_path_factory.mktemp("ledger") / "migrado.db"
    _alembic(f"sqlite:///{db}", "head")
    return str(db)


def _url_postgres_de_teste() -> str:
    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith("postgresql"):
        pytest.skip(
            "PostgreSQL ausente. Configure DATABASE_URL=postgresql://…/picsaude_test "
            "para exercer o dialeto onde a produção roda."
        )
    if "test" not in url.lower():
        pytest.skip("DATABASE_URL não é banco de teste — recusando tocar nele.")
    return url


@pytest.fixture(scope="session")
def _postgres_migrado() -> str:
    url = _url_postgres_de_teste()
    _alembic(url, "head")   # idempotente
    return url


@pytest.fixture(params=["sqlite", "postgresql"])
def ledger_db(request):
    """Um banco por dialeto, ambos migrados por Alembic."""
    if request.param == "sqlite":
        return _LedgerSQLite(request.getfixturevalue("_sqlite_migrado"))
    return _LedgerPostgres(request.getfixturevalue("_postgres_migrado"))


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tabela", TABELAS_LEDGER)
def test_triggers_criados_pela_migracao(ledger_db, tabela: str) -> None:
    """Os 16 triggers existem em banco construído apenas por `alembic upgrade head`."""
    existentes = ledger_db.triggers()
    for acao in ("update", "delete"):
        nome = f"prevent_{acao}_{tabela}"
        assert nome in existentes, (
            f"[{ledger_db.dialeto}] trigger {nome} ausente após alembic upgrade head — "
            f"o §2 do CLAUDE.md não está sustentado pelo banco."
        )


@pytest.mark.parametrize("tabela", TABELAS_LEDGER)
def test_insert_permitido(ledger_db, tabela: str) -> None:
    """O ledger cresce por inserção — INSERT nunca é bloqueado."""
    with ledger_db.transacao(tabela) as tx:
        tx.executar(_INSERTS[tabela])
        assert tx.escalar(f"SELECT COUNT(*) FROM {tabela}") >= 1


@pytest.mark.parametrize("tabela", TABELAS_LEDGER)
def test_update_bloqueado(ledger_db, tabela: str) -> None:
    with ledger_db.transacao(tabela) as tx:
        tx.executar(_INSERTS[tabela])
        rid = tx.escalar(f"SELECT MAX(id) FROM {tabela}")
        assert rid is not None, "sem linha, o trigger BEFORE não dispara (vacuidade)"

        erro = tx.recusa(f"UPDATE {tabela} SET id = id WHERE id = {rid}")
        assert mensagem("UPDATE", tabela) in erro, (
            f"[{ledger_db.dialeto}] mensagem divergente: {erro!r}"
        )


@pytest.mark.parametrize("tabela", TABELAS_LEDGER)
def test_delete_bloqueado(ledger_db, tabela: str) -> None:
    with ledger_db.transacao(tabela) as tx:
        tx.executar(_INSERTS[tabela])
        rid = tx.escalar(f"SELECT MAX(id) FROM {tabela}")
        assert rid is not None, "sem linha, o trigger BEFORE não dispara (vacuidade)"

        erro = tx.recusa(f"DELETE FROM {tabela} WHERE id = {rid}")
        assert mensagem("DELETE", tabela) in erro, (
            f"[{ledger_db.dialeto}] mensagem divergente: {erro!r}"
        )


def test_mensagem_identica_entre_dialetos() -> None:
    """A mensagem não depende do dialeto — quem depura em prod lê o mesmo texto de dev."""
    from app.domain.ledger_imutabilidade import sql_criar_postgres, sql_criar_sqlite

    esperada = "Ledger imutável: UPDATE não permitido em prescricao_eventos"
    assert any(esperada in c for c in sql_criar_sqlite(TABELAS_LEDGER))
    # No PG o texto é montado em tempo de execução (TG_OP/TG_TABLE_NAME);
    # o formato tem que produzir exatamente a mesma frase.
    assert any(
        "'Ledger imutável: % não permitido em %'" in c
        for c in sql_criar_postgres(TABELAS_LEDGER)
    )
    assert mensagem("UPDATE", "prescricao_eventos") == esperada


# ---------------------------------------------------------------------------
# Guard-rail: a migração é passado congelado, não código vivo
# ---------------------------------------------------------------------------
# Uma migração cujo efeito depende de QUANDO roda produz bancos diferentes no
# mesmo `alembic head` — o próprio defeito que este ticket conserta. Os dois
# testes abaixo travam as duas metades da correção:
#
#   1. a tupla da migração está congelada nestes 8 nomes exatos;
#   2. os construtores de DDL não têm default, então ninguém pode voltar a
#      resolver a lista na leitura só por omitir o parâmetro.
#
# É a lição do R2 (CLAUDE.md §2a — unicidade como invariante executável)
# aplicada a schema: o gate acusa, não a memória de quem revisa.

# Alvo do downgrade no round-trip: a revisão IMEDIATAMENTE ABAIXO da migração de
# triggers, na notação relativa do Alembic. Antes era "-1" — que significa "uma
# abaixo do HEAD" e só funcionava enquanto os triggers FOSSEM o head. A primeira
# migração empilhada depois deles (a3c7e1f95b02) fazia o teste desmontar a
# migração errada e acusar "downgrade deixou trigger para trás". O que este teste
# quer é sempre a mesma revisão, dita por nome.
_REVISAO_TRIGGERS = "f2b7c1d0a4e5"
_ANTES_DOS_TRIGGERS = f"{_REVISAO_TRIGGERS}-1"


def _migracao_triggers():
    """Carrega a migração f2b7c1d0a4e5 como módulo (não é importável por nome)."""
    import importlib.util

    caminho = (
        _BACKEND_ROOT / "alembic" / "versions"
        / "f2b7c1d0a4e5_ledger_triggers_imutabilidade.py"
    )
    spec = importlib.util.spec_from_file_location("_mig_f2b7c1d0a4e5", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_tupla_da_migracao_esta_congelada() -> None:
    """Os 8 nomes sobre os quais f2b7c1d0a4e5 agiu não podem mudar.

    Editar uma migração já mergeada reescreve o passado: bancos que já rodaram
    esta revisão não a rodam de novo, então a edição só afeta bancos futuros —
    e os dois divergem em silêncio. Ledger novo = migração NOVA (CLAUDE.md §9).
    """
    congeladas = _migracao_triggers().TABELAS_CONGELADAS

    assert congeladas == (
        "prescricao_eventos",
        "pedido_exame_eventos",
        "laudo_eventos",
        "agendamento_eventos",
        "circulacao_diagnostica_eventos",
        "encaminhamento_eventos",
        "atestado_eventos",
        "contrarreferencia_eventos",
    ), (
        "A tupla de f2b7c1d0a4e5 foi alterada. Migração é registro histórico: "
        "para proteger um ledger novo, escreva uma migração NOVA — não edite "
        "esta. Se a alteração é deliberada e a revisão ainda NÃO foi mergeada "
        "nem aplicada em ambiente durável, atualize também este teste."
    )

    # A migração cobre tudo que a lista viva exige HOJE. Divergência aqui não é
    # erro da migração — é ledger novo sem a sua migração de triggers.
    assert set(congeladas) == set(TABELAS_LEDGER), (
        "TABELAS_LEDGER e a migração divergiram: há ledger na lista viva sem "
        "migração que crie seus triggers (ou vice-versa). Escreva a migração."
    )


def test_construtores_de_ddl_exigem_tabelas() -> None:
    """`tabelas` sem default: o bug não sobrevive a um chamador distraído.

    Com default, bastaria omitir o parâmetro numa migração futura para a lista
    viva voltar a ser resolvida na leitura. Sem default, a omissão é TypeError
    em tempo de chamada — o erro aparece ao escrever a migração, não meses
    depois num banco com schema divergente.
    """
    from app.domain import ledger_imutabilidade as li

    for construtor in (li.sql_criar, li.sql_remover):
        with pytest.raises(TypeError):
            construtor("sqlite")            # falta `tabelas`

    for construtor in (
        li.sql_criar_sqlite, li.sql_remover_sqlite,
        li.sql_criar_postgres, li.sql_remover_postgres,
    ):
        with pytest.raises(TypeError):
            construtor()                    # falta `tabelas`


# ---------------------------------------------------------------------------
# Round-trip da migração
# ---------------------------------------------------------------------------

def test_round_trip_sqlite(tmp_path) -> None:
    """downgrade remove os 16 triggers; upgrade recria."""
    db = tmp_path / "roundtrip.db"
    url = f"sqlite:///{db}"
    _alembic(url, "head")
    ledger = _LedgerSQLite(str(db))

    esperados = {
        f"prevent_{acao}_{t}" for t in TABELAS_LEDGER for acao in ("update", "delete")
    }
    assert esperados <= ledger.triggers()

    _alembic(url, _ANTES_DOS_TRIGGERS, descer=True)
    assert not (esperados & ledger.triggers()), "downgrade deixou trigger para trás"

    _alembic(url, "head")
    assert esperados <= ledger.triggers(), "upgrade não recriou os triggers"


def test_round_trip_postgres(_postgres_migrado: str) -> None:
    url = _postgres_migrado
    ledger = _LedgerPostgres(url)
    esperados = {
        f"prevent_{acao}_{t}" for t in TABELAS_LEDGER for acao in ("update", "delete")
    }
    assert esperados <= ledger.triggers()

    try:
        # Alvo NOMEADO, não "-1": a migração de triggers precisa ser a que desce,
        # não "uma abaixo do head". Assim que a observacao_complementar empilhou
        # em cima dela, "-1" passou a descer a migração ERRADA e deixava os
        # triggers para trás. É o mesmo defeito que test_round_trip_sqlite já
        # tinha e que _ANTES_DOS_TRIGGERS corrigiu; o gêmeo PG só corre no CI
        # (precisa de Postgres efêmero), então escapou até aqui.
        _alembic(url, _ANTES_DOS_TRIGGERS, descer=True)
        assert not (esperados & ledger.triggers()), "downgrade deixou trigger para trás"
    finally:
        # O banco de teste é compartilhado com as outras suítes: volta ao head
        # mesmo se a asserção acima falhar.
        _alembic(url, "head")

    assert esperados <= ledger.triggers(), "upgrade não recriou os triggers"
