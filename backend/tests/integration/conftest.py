"""
Ticket 13 — Testes de integração contra PostgreSQL real.

Arquitetura de isolamento
-------------------------
Cada teste roda dentro de uma transação externa (BEGIN) aberta em uma única
conexão psycopg2 dedicada (`outer_conn`). Essa conexão é injetada em todas as
chamadas de `get_conn()` da aplicação via `monkeypatch`, substituída por um
wrapper `SavepointConnection` que:

  * compartilha o mesmo raw psycopg2 conn da fixture `outer_conn`;
  * abre um SAVEPOINT na construção (cada request vive dentro do seu próprio
    savepoint, independente do outer tx);
  * `commit()`  → RELEASE SAVEPOINT          (o dado fica na outer tx)
  * `rollback()`→ ROLLBACK TO SAVEPOINT       (o dado some da outer tx)
  * `close()`   → RELEASE se ainda não finalizado (semântica de commit-on-close)

No teardown, o outer tx é revertido (`outer_conn.rollback()`), descartando
absolutamente todo dado inserido durante o teste — inclusive seeds. Nada é
persistido em `picsaude_test`.

Por que este padrão
-------------------
A alternativa ingênua ("abrir uma conexão, fazer rollback") não funciona com
`TestClient` do FastAPI: a aplicação chama `get_conn()` internamente e obtém
sua PRÓPRIA conexão do pool SQLAlchemy — conexões diferentes, transações
diferentes, isolamento nenhum. O monkeypatch força o app a usar a conexão
controlada pelo teste.

Concorrência
------------
O wrapper compartilha uma única raw conn — é `NÃO thread-safe`. Para o
`test_concorrencia.py` existe uma fixture paralela (`client_concorrencia`)
que NÃO faz monkeypatch: usa o pool real do app, faz commits reais e limpa
dados no teardown por CPF sentinela.
"""
from __future__ import annotations

import os
import sys

import pytest  # importado cedo para permitir skip module-level

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Skip de plataforma — extensionistas Windows/SQLite sem PostgreSQL
# (Jules audit P2#10, 2026-05-25). Posicionado ANTES dos imports pesados
# (psycopg2, alembic) para não exigir que sejam instaláveis em todas as
# plataformas. Quem quiser rodar os testes de integração precisa de PG.
# ---------------------------------------------------------------------------
if not DATABASE_URL.startswith("postgresql"):
    pytest.skip(
        "backend/tests/integration/ requer PostgreSQL. "
        "Configure DATABASE_URL=postgresql://user:senha@localhost/picsaude_test "
        "ou rode pytest excluindo essa pasta: "
        "pytest --ignore=backend/tests/integration/",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Guardrail rígido — recusar rodar fora do banco de teste
# ---------------------------------------------------------------------------
# Deve acontecer ANTES de qualquer `from app...` porque `app.database` lê
# DATABASE_URL no import e cacheia o engine.

if "test" not in DATABASE_URL.lower():
    raise RuntimeError(
        "ABORTANDO: DATABASE_URL não contém 'test'. "
        "Recuse-se a rodar testes de integração fora do banco de teste. "
        f"DATABASE_URL atual: {DATABASE_URL[:60]}..."
    )

# ---------------------------------------------------------------------------
# Imports da aplicação — seguros agora que DATABASE_URL foi validada
# ---------------------------------------------------------------------------

import itertools
import threading
import uuid
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extensions
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.auth.jwt import hash_senha
from app.database import _PgRow, _PgCursor, _pg_translate, _RE_IS_INSERT, _RE_HAS_RETURNING


# ---------------------------------------------------------------------------
# Setup automático — Alembic upgrade head no banco de teste
# ---------------------------------------------------------------------------
# Garante que TODA migration (incluindo 4B/4D.x futuras) está aplicada
# antes da coleta de testes. Evita erro do tipo:
#   psycopg2.errors.UndefinedColumn: column "instance_id" does not exist
# que apareceu no T4D.1 quando a 4B-prequel/4B não estavam aplicadas no
# banco picsaude_test.
#
# Idempotente — Alembic detecta no-op quando já está no head.

def _aplicar_migrations_alembic() -> None:
    backend_root = Path(__file__).resolve().parent.parent.parent
    alembic_ini = backend_root / "alembic.ini"
    if not alembic_ini.exists():
        return
    cfg = Config(str(alembic_ini))
    # env.py do alembic respeita DATABASE_URL — já apontando para test
    # (validado pelo guardrail acima).
    cwd_before = os.getcwd()
    try:
        os.chdir(backend_root)
        command.upgrade(cfg, "head")
    finally:
        os.chdir(cwd_before)


_aplicar_migrations_alembic()

# ---------------------------------------------------------------------------
# Constantes compartilhadas com os testes
# ---------------------------------------------------------------------------

SEED_PRESCRITOR_CNS = "987654321098765"       # CNS 15 dígitos (diferente do seed_dev.py)
SEED_PRESCRITOR_NOME = "DR. TESTE TICKET13"
SEED_PRESCRITOR_SENHA = "SenhaTest123!"

SEED_PACIENTE_CPF = "12345678901"             # 11 dígitos — normalize_cpf só strip não valida
SEED_PACIENTE_NOME = "PACIENTE TESTE TICKET13"

# ---------------------------------------------------------------------------
# Wrapper de conexão: SAVEPOINT por request sobre uma raw conn compartilhada
# ---------------------------------------------------------------------------

_sp_counter = itertools.count(1)


class SavepointConnection:
    """Wrapper que compartilha uma raw psycopg2 conn entre chamadas de
    get_conn(), isolando cada request em um SAVEPOINT. Reaproveita a
    tradução SQLite→PostgreSQL de `_PgConnection`.
    """

    __slots__ = ("_raw", "_sp", "_finalized")

    def __init__(self, raw_conn: psycopg2.extensions.connection) -> None:
        self._raw = raw_conn
        self._sp = f"picsaude_test_sp_{next(_sp_counter)}"
        self._finalized = False
        with raw_conn.cursor() as cur:
            cur.execute(f"SAVEPOINT {self._sp}")

    # ----- API idêntica à de app.database._PgConnection ----------------------

    def execute(self, sql: str, params=()) -> _PgCursor:
        from psycopg2.extras import RealDictCursor

        pg_sql, _on_conflict = _pg_translate(sql)
        is_insert = bool(_RE_IS_INSERT.match(pg_sql))
        has_returning = bool(_RE_HAS_RETURNING.search(pg_sql))

        raw_cur = self._raw.cursor(cursor_factory=RealDictCursor)
        result = _PgCursor()

        try:
            if is_insert and not has_returning:
                returning_sql = pg_sql.rstrip().rstrip(";") + " RETURNING id"
                raw_cur.execute(returning_sql, params or ())
                if raw_cur.description:
                    row = raw_cur.fetchone()
                    if row and "id" in row:
                        result.lastrowid = row["id"]
            else:
                raw_cur.execute(pg_sql, params or ())
                if raw_cur.description:
                    result._rows = [_PgRow(dict(r)) for r in (raw_cur.fetchall() or [])]
            result.rowcount = raw_cur.rowcount
        finally:
            raw_cur.close()

        return result

    def commit(self) -> None:
        if self._finalized:
            return
        with self._raw.cursor() as cur:
            cur.execute(f"RELEASE SAVEPOINT {self._sp}")
        self._finalized = True

    def rollback(self) -> None:
        if self._finalized:
            return
        with self._raw.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {self._sp}")
            cur.execute(f"RELEASE SAVEPOINT {self._sp}")
        self._finalized = True

    def close(self) -> None:
        # close() sem commit/rollback explícito → tratado como commit
        # (compatível com padrões do app que fazem try/finally close()).
        if not self._finalized:
            self.commit()

    def begin(self):
        from app.database import _PgTransaction
        return _PgTransaction(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


# ---------------------------------------------------------------------------
# Módulos onde `get_conn` foi importado localmente e precisa de monkeypatch
# ---------------------------------------------------------------------------
# `from app.database import get_conn` cria um binding local em cada módulo;
# patchar `app.database.get_conn` não afeta bindings já importados.

_ROUTERS_COM_GET_CONN_LOCAL = (
    "app.routers.prescricoes",
    "app.routers.tokens",
    "app.routers.prescritores",
    "app.routers.dispensadores",
    "app.routers.health",
)


# ---------------------------------------------------------------------------
# Fixture: conexão raw com outer tx
# ---------------------------------------------------------------------------

@pytest.fixture
def outer_conn():
    """Uma raw psycopg2 conn por teste, com outer tx aberto. Roll back no final."""
    raw = psycopg2.connect(DATABASE_URL)
    raw.autocommit = False  # garante que BEGIN implícito acontece
    try:
        # Força um BEGIN explícito para que os savepoints tenham envelope
        with raw.cursor() as cur:
            cur.execute("BEGIN")
        yield raw
    finally:
        try:
            raw.rollback()
        except Exception:
            pass
        raw.close()


# ---------------------------------------------------------------------------
# Fixture: TestClient com get_conn monkeypatched para SavepointConnection
# ---------------------------------------------------------------------------

@pytest.fixture
def client(outer_conn, monkeypatch):
    from app.main import app

    def _fake_get_conn():
        return SavepointConnection(outer_conn)

    monkeypatch.setattr("app.database.get_conn", _fake_get_conn)
    monkeypatch.setattr("app.database_tx.get_conn", _fake_get_conn)
    for modpath in _ROUTERS_COM_GET_CONN_LOCAL:
        monkeypatch.setattr(f"{modpath}.get_conn", _fake_get_conn)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Fixture: TestClient SEM isolamento (para test_concorrencia)
# ---------------------------------------------------------------------------

@pytest.fixture
def client_concorrencia():
    """TestClient que usa o pool real do app (real commits).
    Limpa dados criados pelo teste no teardown por CPF sentinela do seed.
    """
    from app.database import get_conn
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    # Cleanup — remove tudo criado pelos testes de concorrência.
    # CPF sentinela do seed garante que só dados de teste sejam afetados.
    conn = get_conn()
    try:
        conn.execute(
            """
            DELETE FROM prescricao_eventos
             WHERE prescricao_id IN (
                SELECT p.id FROM prescricoes p
                JOIN pacientes pa ON pa.id = p.paciente_id
                WHERE pa.cpf = ?
             )
            """,
            (SEED_PACIENTE_CPF,),
        )
        conn.execute(
            """
            DELETE FROM prescricao_itens
             WHERE prescricao_id IN (
                SELECT p.id FROM prescricoes p
                JOIN pacientes pa ON pa.id = p.paciente_id
                WHERE pa.cpf = ?
             )
            """,
            (SEED_PACIENTE_CPF,),
        )
        conn.execute(
            """
            DELETE FROM prescricoes
             WHERE paciente_id IN (SELECT id FROM pacientes WHERE cpf = ?)
            """,
            (SEED_PACIENTE_CPF,),
        )
        conn.execute("DELETE FROM pacientes WHERE cpf = ?", (SEED_PACIENTE_CPF,))
        conn.execute("DELETE FROM prescritores WHERE cns = ?", (SEED_PRESCRITOR_CNS,))
        conn.execute("DELETE FROM usuarios WHERE identificador = ?", (SEED_PRESCRITOR_CNS,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Seeds — inseridos DENTRO da outer tx (some no rollback)
# ---------------------------------------------------------------------------

def _agora() -> str:
    return datetime.utcnow().isoformat()


@pytest.fixture
def seed_usuario(outer_conn):
    """Cria usuário prescritor para autenticação via POST /auth/token.

    Credenciais:
      identificador (CNS): SEED_PRESCRITOR_CNS
      senha:               SEED_PRESCRITOR_SENHA
    """
    senha_hash = hash_senha(SEED_PRESCRITOR_SENHA)
    now = _agora()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
            VALUES (%s, %s, %s, %s, true, %s, %s)
            ON CONFLICT (identificador) DO NOTHING
            """,
            ("prescritor", SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, senha_hash, now, now),
        )
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cns) DO NOTHING
            """,
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
    return {
        "cns":   SEED_PRESCRITOR_CNS,
        "nome":  SEED_PRESCRITOR_NOME,
        "senha": SEED_PRESCRITOR_SENHA,
    }


@pytest.fixture
def seed_paciente(outer_conn):
    """Cria paciente de teste para uso em fluxo de prescrição.

    A criação na tabela `pacientes` também acontece dentro do endpoint de
    emissão (INSERT OR IGNORE), mas pré-cadastrar permite testar o caminho
    de paciente preexistente.
    """
    now = _agora()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cpf) DO NOTHING
            """,
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
    return {"cpf": SEED_PACIENTE_CPF, "nome": SEED_PACIENTE_NOME}


# ---------------------------------------------------------------------------
# Helper: obter token de prescritor via login real
# ---------------------------------------------------------------------------

def obter_token_prescritor(client, seed_usuario) -> str:
    """Faz POST /auth/token e devolve o access_token."""
    r = client.post(
        "/auth/token",
        data={
            "username": seed_usuario["cns"],
            "password": seed_usuario["senha"],
        },
    )
    assert r.status_code == 200, f"login falhou: {r.status_code} {r.text}"
    return r.json()["access_token"]
