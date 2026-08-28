"""
tests/integration/test_importar_snapshot_rdc_pg.py — G1 end-to-end (real PG).

Roda `importar_snapshot_rdc_substancias.py` como SUBPROCESSO contra um
banco descartável — mesma disciplina de `test_reset_demo_db_pg.py`. Prova
o caminho inteiro: JSON → `aplicar_snapshot_carimbado` → linha em
`catalogo_substancias` com versao/data_snapshot + carimbo ativo em
`catalogo_regulatorio_carimbo`.

Pula sem `DATABASE_URL` de Postgres (guardado pelo conftest desta pasta).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
from sqlalchemy.engine.url import make_url

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _BACKEND_ROOT / "scripts" / "importar_snapshot_rdc_substancias.py"

_DATABASE_URL = os.environ["DATABASE_URL"]
_URL = make_url(_DATABASE_URL)
_THROWAWAY_DB = (_URL.database or "picsaude") + "_rdcimport"
_THROWAWAY_URL = _URL.set(database=_THROWAWAY_DB).render_as_string(hide_password=False)


def _admin_exec(sql: str) -> None:
    conn = psycopg2.connect(_DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


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


@pytest.fixture(scope="module")
def banco_com_migracoes():
    _admin_exec(f'DROP DATABASE IF EXISTS "{_THROWAWAY_DB}" WITH (FORCE)')
    _admin_exec(f"CREATE DATABASE \"{_THROWAWAY_DB}\" TEMPLATE template0 ENCODING 'UTF8'")
    env = {**os.environ, "DATABASE_URL": _THROWAWAY_URL}
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(_BACKEND_ROOT), env=env,
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    try:
        yield
    finally:
        _admin_exec(f'DROP DATABASE IF EXISTS "{_THROWAWAY_DB}" WITH (FORCE)')


def _rodar_importador(arquivo: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": _THROWAWAY_URL}
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--arquivo", str(arquivo)],
        cwd=str(_BACKEND_ROOT), env=env,
        capture_output=True, text=True, timeout=30,
    )


def test_importar_snapshot_completo_end_to_end(banco_com_migracoes, tmp_path):
    arquivo = tmp_path / "consolidado-teste.json"
    arquivo.write_text(json.dumps({
        "fonte": "Portaria 344/98 Anexo I (teste e2e)",
        "versao": "RDC 000/2099",
        "data_snapshot": "2099-01-01",
        "entradas": [
            {"dcb": "Morfina E2E", "classe_controle": "A1", "tipo_retencao": None, "observacao": None},
        ],
    }), encoding="utf-8")

    proc = _rodar_importador(arquivo)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "1 entradas" in proc.stdout

    classe = _query_one(
        "SELECT classe_controle FROM catalogo_substancias WHERE dcb_normalizada = %s",
        ("morfina e2e",),
    )
    assert classe == "A1"

    versao = _query_one(
        "SELECT versao FROM catalogo_substancias WHERE dcb_normalizada = %s",
        ("morfina e2e",),
    )
    assert versao == "RDC 000/2099"

    carimbo_versao = _query_one("SELECT versao FROM catalogo_regulatorio_carimbo WHERE id = 1")
    assert carimbo_versao == "RDC 000/2099"


def test_importar_e_idempotente(banco_com_migracoes, tmp_path):
    arquivo = tmp_path / "consolidado-idem.json"
    arquivo.write_text(json.dumps({
        "fonte": "Teste idempotência",
        "versao": "v-idem",
        "data_snapshot": "2099-01-01",
        "entradas": [
            {"dcb": "Substancia Idempotencia PG", "classe_controle": "B1", "tipo_retencao": None},
        ],
    }), encoding="utf-8")

    assert _rodar_importador(arquivo).returncode == 0
    assert _rodar_importador(arquivo).returncode == 0

    n = _query_one(
        "SELECT COUNT(*) FROM catalogo_substancias WHERE dcb_normalizada = %s",
        ("substancia idempotencia pg",),
    )
    assert n == 1
