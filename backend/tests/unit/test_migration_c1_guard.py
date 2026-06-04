"""TICKET-5C-BIS-C.1 — guarda da migration contra destruição silenciosa.

Testa `linhas_baseline_a_preservar` (helper puro da migration) sem precisar do
runtime do Alembic nem de PostgreSQL — usa SQLite em memória.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text

_MIG = (
    Path(__file__).resolve().parents[2]   # tests/unit -> tests -> backend
    / "alembic" / "versions"
    / "c1f0a5b3d7e9_migra_schema_institucional_prestadores_unidades.py"
)


def _carregar_migration():
    spec = importlib.util.spec_from_file_location("mig_c1", _MIG)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _conn():
    return create_engine("sqlite://").connect()


def test_baseline_sem_org_com_linhas_sinaliza_abortar():
    mig = _carregar_migration()
    conn = _conn()
    conn.execute(text("CREATE TABLE prestadores (id INTEGER PRIMARY KEY, cnpj TEXT)"))
    conn.execute(text("INSERT INTO prestadores (id, cnpj) VALUES (1, 'x'), (2, 'y')"))
    assert mig.linhas_baseline_a_preservar(conn) == 2   # > 0 → abortar (backfill)


def test_baseline_sem_org_vazia_e_seguro_recriar():
    mig = _carregar_migration()
    conn = _conn()
    conn.execute(text("CREATE TABLE prestadores (id INTEGER PRIMARY KEY, cnpj TEXT)"))
    assert mig.linhas_baseline_a_preservar(conn) == 0   # vazia → drop+recreate


def test_ja_tem_org_id_nao_aborta():
    mig = _carregar_migration()
    conn = _conn()
    conn.execute(text("CREATE TABLE prestadores (id TEXT PRIMARY KEY, org_id TEXT, cnpj TEXT)"))
    conn.execute(text("INSERT INTO prestadores (id, org_id) VALUES ('a', 'org-1')"))
    assert mig.linhas_baseline_a_preservar(conn) == 0   # já no schema Ticket-30


def test_sem_tabela_nao_aborta():
    mig = _carregar_migration()
    assert mig.linhas_baseline_a_preservar(_conn()) == 0
