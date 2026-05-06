"""
test_ledger_imutabilidade.py — Ticket 62A
==========================================
Verifica que os triggers BEFORE UPDATE e BEFORE DELETE bloqueiam
modificações nas tabelas de ledger (prescricao_eventos, pedido_exame_eventos,
laudo_eventos, agendamento_eventos, circulacao_diagnostica_eventos).
"""
from __future__ import annotations

import sqlite3

import pytest

# Mapeamento: tabela → (coluna_fk, coluna_tipo_evento)
# Permite inserir um evento mínimo sem precisar de registro pai (foreign_keys=OFF)
TABELAS_LEDGER = {
    "prescricao_eventos": (
        "INSERT INTO prescricao_eventos (prescricao_id, tipo_evento, ator_tipo, created_at)"
        " VALUES (999, 'teste', 'sistema', '2026-01-01T00:00:00')"
    ),
    "pedido_exame_eventos": (
        "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento) VALUES (999, 'teste')"
    ),
    "laudo_eventos": (
        "INSERT INTO laudo_eventos (laudo_id, tipo_evento) VALUES (999, 'teste')"
    ),
    "agendamento_eventos": (
        "INSERT INTO agendamento_eventos (agendamento_id, evento, criado_em) VALUES (999, 'teste', '2026-01-01T00:00:00')"
    ),
    "circulacao_diagnostica_eventos": (
        "INSERT INTO circulacao_diagnostica_eventos (circulacao_id, tipo_evento, criado_em) VALUES (999, 'teste', '2026-01-01T00:00:00')"
    ),
}


def _conn_sem_fk(db_path: str) -> sqlite3.Connection:
    """Abre conexão SQLite com FK desativado para permitir INSERTs de teste."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    return conn


@pytest.mark.parametrize("tabela", list(TABELAS_LEDGER))
def test_triggers_existem(db_path: str, tabela: str) -> None:
    """Confirma que os dois triggers foram criados para cada tabela."""
    conn = sqlite3.connect(db_path)
    triggers = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
    }
    conn.close()

    assert f"prevent_update_{tabela}" in triggers, (
        f"Trigger prevent_update_{tabela} não encontrado no banco"
    )
    assert f"prevent_delete_{tabela}" in triggers, (
        f"Trigger prevent_delete_{tabela} não encontrado no banco"
    )


@pytest.mark.parametrize("tabela,sql_insert", list(TABELAS_LEDGER.items()))
def test_insert_permitido(db_path: str, tabela: str, sql_insert: str) -> None:
    """INSERT deve funcionar normalmente — ledger cresce apenas por inserção."""
    conn = _conn_sem_fk(db_path)
    try:
        conn.execute(sql_insert)
        conn.commit()
        count = conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        assert count >= 1
    finally:
        conn.close()


@pytest.mark.parametrize("tabela,sql_insert", list(TABELAS_LEDGER.items()))
def test_update_bloqueado(db_path: str, tabela: str, sql_insert: str) -> None:
    """UPDATE deve falhar com mensagem explícita de ledger imutável."""
    conn = _conn_sem_fk(db_path)
    try:
        conn.execute(sql_insert)
        conn.commit()
        rowid = conn.execute(f"SELECT id FROM {tabela} LIMIT 1").fetchone()[0]

        with pytest.raises(sqlite3.DatabaseError, match="Ledger imutável"):
            # SET id = id é no-op mas ainda dispara BEFORE UPDATE
            conn.execute(f"UPDATE {tabela} SET id = id WHERE id = ?", (rowid,))
            conn.commit()
    finally:
        conn.close()


@pytest.mark.parametrize("tabela,sql_insert", list(TABELAS_LEDGER.items()))
def test_delete_bloqueado(db_path: str, tabela: str, sql_insert: str) -> None:
    """DELETE deve falhar com mensagem explícita de ledger imutável."""
    conn = _conn_sem_fk(db_path)
    try:
        conn.execute(sql_insert)
        conn.commit()
        rowid = conn.execute(f"SELECT id FROM {tabela} LIMIT 1").fetchone()[0]

        with pytest.raises(sqlite3.DatabaseError, match="Ledger imutável"):
            conn.execute(f"DELETE FROM {tabela} WHERE id = ?", (rowid,))
            conn.commit()
    finally:
        conn.close()
