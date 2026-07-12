"""TICKET-CORE-R2 §3.1 — seletor do lock de linha (row_lock_suffix).

O mecanismo de serialização é PG-only: em SQLite a transação já serializa writes
e `FOR UPDATE` é erro de sintaxe. Este teste trava esse contrato (o caminho de
concorrência real contra PG vive em tests/integration/test_r2_idempotencia.py).
"""
from __future__ import annotations

import app.database as db


def test_sqlite_nao_emite_for_update(monkeypatch):
    monkeypatch.setattr(db, "_USE_SQLITE", True)
    assert db.row_lock_suffix() == ""
    assert db.row_lock_suffix(of="d") == ""


def test_pg_emite_for_update(monkeypatch):
    monkeypatch.setattr(db, "_USE_SQLITE", False)
    assert db.row_lock_suffix() == " FOR UPDATE"


def test_pg_for_update_of_alias(monkeypatch):
    """`of=` trava só uma tabela do JOIN (evita lock desnecessário nas demais)."""
    monkeypatch.setattr(db, "_USE_SQLITE", False)
    assert db.row_lock_suffix(of="d") == " FOR UPDATE OF d"
