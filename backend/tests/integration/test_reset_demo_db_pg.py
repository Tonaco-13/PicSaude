"""
TICKET-DEMO-RESET-PG — testes contra PostgreSQL real (AC4/5/6/9/10).

Pula sem `DATABASE_URL` de Postgres (guardado pelo conftest desta pasta).

Estratégia de isolamento
------------------------
`reset_demo_db.py` faz `DROP SCHEMA public CASCADE` — destrutivo por design. Não
pode rodar contra o `picsaude_test` compartilhado (nukearia a suíte inteira).
Então cada rodada cria um banco DESCARTÁVEL na MESMA cluster (derivado da
DATABASE_URL de teste), roda o reset como SUBPROCESSO — exatamente como Fabiano
rodaria no Render Shell — e faz as asserções conectando direto nele. O banco
descartável é dropado no teardown.

AC coberto aqui:
  AC4  — verde: rebuild de PG limpo → alembic head + 17 triggers + personas.
  AC5  — vermelho-antes-de-verde: PG sujo (artefato injetado) → rebuild → some.
  AC6  — idempotente: rodar duas vezes → mesmo estado final.
  AC9  — alvo protegido: sem --sim-eu-quero e não-interativo → aborta, sem DROP.
  AC10 — schema efetivo + dispose: provado de forma funcional (a migração e o
         seed só completam num pool limpo; 17 triggers presentes o confirmam).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy.engine.url import make_url

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_RESET_SCRIPT = _BACKEND_ROOT / "scripts" / "reset_demo_db.py"

_DATABASE_URL = os.environ["DATABASE_URL"]  # garantido pelo conftest (contém 'test')
_URL = make_url(_DATABASE_URL)
_THROWAWAY_DB = (_URL.database or "picsaude") + "_resetself"
_THROWAWAY_URL = _URL.set(database=_THROWAWAY_DB).render_as_string(hide_password=False)

# Personas canônicas do seed_demo.
_CNS_PRESCRITOR_DEMO = "980001112223334"
_CNPJ_DISPENSADOR_DEMO = "99999999000191"
_CPF_CONTAMINACAO = "88888888888"


def _alembic_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    return ScriptDirectory.from_config(cfg).get_current_head()


def _admin_exec(sql: str) -> None:
    """Executa DDL de nível-cluster (CREATE/DROP DATABASE) conectado ao banco
    de manutenção (o próprio picsaude_test), em autocommit."""
    conn = psycopg2.connect(_DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


def _rodar_reset(*extra_args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "DATABASE_URL": _THROWAWAY_URL,
        "PICSAUDE_DEMO_MODE": "true",
        "PICSAUDE_ENV": "stg",  # != prod
    }
    env.pop("PIX_SAUDE_DEMO_DB", None)
    return subprocess.run(
        [sys.executable, str(_RESET_SCRIPT), *extra_args],
        cwd=str(_BACKEND_ROOT),
        env=env,
        stdin=subprocess.DEVNULL,  # não-interativo (isatty == False)
        capture_output=True,
        text=True,
        timeout=300,
    )


def _query_one(sql: str, params=()):
    conn = psycopg2.connect(_THROWAWAY_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


def _trigger_count() -> int:
    return _query_one(
        """
        SELECT count(*) FROM pg_trigger t
        JOIN pg_class c     ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT t.tgisinternal AND n.nspname = current_schema()
        """
    )


def _snapshot() -> dict[str, int]:
    """Contagem de linhas de todas as tabelas do schema — baseline determinístico
    que um rebuild limpo reproduz. Inclui alembic_version (constante = 1)."""
    conn = psycopg2.connect(_THROWAWAY_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                "ORDER BY tablename"
            )
            tabelas = [r[0] for r in cur.fetchall()]
            snap: dict[str, int] = {}
            for t in tabelas:
                cur.execute(f'SELECT count(*) FROM "{t}"')
                snap[t] = cur.fetchone()[0]
            return snap
    finally:
        conn.close()


def _injetar_contaminacao() -> None:
    conn = psycopg2.connect(_THROWAWAY_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
                "VALUES (%s, %s, true, now(), now())",
                (_CPF_CONTAMINACAO, "CONTAMINACAO-RESET-TEST"),
            )
    finally:
        conn.close()


def _contaminacao_presente() -> bool:
    return _query_one(
        "SELECT count(*) FROM pacientes WHERE cpf = %s", (_CPF_CONTAMINACAO,)
    ) > 0


@pytest.fixture(scope="module")
def banco_descartavel():
    """Cria o banco descartável na cluster; dropa no teardown."""
    _admin_exec(f'DROP DATABASE IF EXISTS "{_THROWAWAY_DB}" WITH (FORCE)')
    _admin_exec(f'CREATE DATABASE "{_THROWAWAY_DB}" TEMPLATE template0 ENCODING \'UTF8\'')
    try:
        yield
    finally:
        _admin_exec(f'DROP DATABASE IF EXISTS "{_THROWAWAY_DB}" WITH (FORCE)')


def _rebuild_ok(*extra_args: str) -> None:
    proc = _rodar_reset("--sim-eu-quero", *extra_args)
    assert proc.returncode == 0, f"reset falhou:\n{proc.stdout}\n{proc.stderr}"


# ---------------------------------------------------------------------------
# AC4 — verde: rebuild de PG limpo
# ---------------------------------------------------------------------------

def test_ac4_rebuild_verde(banco_descartavel):
    _rebuild_ok()

    assert _query_one("SELECT version_num FROM alembic_version") == _alembic_head()

    # 17 = 16 imutabilidade (8 tabelas × UPDATE/DELETE) + 1 saldo (PG-only).
    assert _trigger_count() == 17, f"esperava 17 triggers, achei {_trigger_count()}"

    assert _query_one(
        "SELECT count(*) FROM prescritores WHERE cns = %s", (_CNS_PRESCRITOR_DEMO,)
    ) == 1
    assert _query_one(
        "SELECT count(*) FROM prestadores WHERE cnpj = %s", (_CNPJ_DISPENSADOR_DEMO,)
    ) == 1


# ---------------------------------------------------------------------------
# AC5 — vermelho-antes-de-verde: prova que o reset LIMPA (não só acrescenta)
# ---------------------------------------------------------------------------

def test_ac5_anti_contaminacao(banco_descartavel):
    _rebuild_ok()
    baseline = _snapshot()

    _injetar_contaminacao()
    assert _contaminacao_presente(), "pré-condição: artefato injetado deve existir"
    assert _snapshot() != baseline, "pré-condição: estado sujo difere do baseline"

    _rebuild_ok()

    assert not _contaminacao_presente(), "reset NÃO limpou o artefato de contaminação"
    assert _snapshot() == baseline, "estado pós-rebuild difere do baseline determinístico"


# ---------------------------------------------------------------------------
# AC6 — idempotente
# ---------------------------------------------------------------------------

def test_ac6_idempotente(banco_descartavel):
    _rebuild_ok()
    snap1 = _snapshot()
    _rebuild_ok()
    snap2 = _snapshot()
    assert snap1 == snap2, "rebuild não é idempotente (estado final divergiu)"
    assert _trigger_count() == 17


# ---------------------------------------------------------------------------
# AC9 — alvo protegido: sem flag e não-interativo → aborta, sem DROP
# ---------------------------------------------------------------------------

def test_ac9_alvo_protegido_sem_flag(banco_descartavel):
    _rebuild_ok()
    _injetar_contaminacao()  # marcador que PROVA que nada foi dropado

    proc = _rodar_reset()  # SEM --sim-eu-quero, stdin fechado (não-interativo)
    assert proc.returncode != 0, "deveria abortar sem confirmação do alvo"
    assert "ABORTANDO" in proc.stdout, proc.stdout

    # AC8/AC10 — o alvo foi ecoado (host+dbname, schema efetivo lido do
    # search_path) ANTES de abortar.
    assert _THROWAWAY_DB in proc.stdout, "dbname não foi ecoado no alvo"
    assert "Schema : public" in proc.stdout, "schema efetivo não foi ecoado"

    # A credencial nunca aparece como par `user:senha@` (mascarada). Checa o
    # PADRÃO de credencial, não o VALOR da senha — que pode colidir com o dbname
    # como substring (em CI a senha 'picsaude' ⊂ 'picsaude_test_resetself', o que
    # dava um falso-positivo). Só há o que mascarar quando a URL traz senha.
    if _URL.password:
        raw_userinfo = f"{_URL.username}:{_URL.password}@"
        assert raw_userinfo not in proc.stdout, "credencial vazou no eco do alvo"
        assert "<credenciais>@" in proc.stdout, "máscara de credencial não aplicada"

    # Nenhum DROP emitido: schema e marcador intactos.
    assert _query_one("SELECT version_num FROM alembic_version") == _alembic_head()
    assert _contaminacao_presente(), "o marcador sumiu — houve DROP indevido sem confirmação"
