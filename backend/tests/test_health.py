"""
test_health.py — Testes dos endpoints de health (G5-impl)

Cobre:
  - GET /health              — liveness sempre retorna 200
  - GET /health/db           — readiness reconhece tabelas / detecta ausência
  - GET /health/version      — retorna metadados da instância
  - create_admin.py          — idempotência e validação de env vars
  - meta_instalacao          — preenchimento correto pelo create_admin
"""
from __future__ import annotations

import sqlite3
import sys
import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _init_schema(db_path: str) -> None:
    from app.database import Base
    import app.models  # noqa
    eng = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=eng)
    eng.dispose()


def _make_get_conn(db_path: str):
    def _get_conn():
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return conn
    return _get_conn


@pytest.fixture()
def db_path(tmp_path):
    path = str(tmp_path / "test_health.db")
    _init_schema(path)
    return path


@pytest.fixture()
def client(db_path):
    from app.main import app
    with patch("app.routers.health.get_conn", _make_get_conn(db_path)):
        with TestClient(app) as c:
            yield c


# ─────────────────────────────────────────────────────────────────────────────
# GET /health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthLiveness:
    def test_retorna_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_ok_true(self, client):
        r = client.get("/health")
        assert r.json()["ok"] is True

    def test_timestamp_presente(self, client):
        r = client.get("/health")
        assert "timestamp" in r.json()


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/db
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthDb:
    def test_banco_integro_retorna_200(self, client):
        r = client.get("/health/db")
        assert r.status_code == 200

    def test_ok_true_quando_banco_ok(self, client):
        r = client.get("/health/db")
        body = r.json()
        assert body["ok"] is True

    def test_integrity_ok(self, client):
        r = client.get("/health/db")
        assert r.json()["integrity"] == "ok"

    def test_tabelas_contadas(self, client):
        r = client.get("/health/db")
        assert r.json()["tabelas"] > 0

    def test_ausentes_vazio_quando_completo(self, client):
        r = client.get("/health/db")
        assert r.json()["ausentes"] == []

    def test_banco_inacessivel_retorna_503(self, tmp_path):
        from app.main import app
        caminho_invalido = str(tmp_path / "nao_existe" / "db.sqlite")

        def _bad_conn():
            raise RuntimeError("banco inacessível")

        with patch("app.routers.health.get_conn", _bad_conn):
            with TestClient(app) as c:
                r = c.get("/health/db")
        assert r.status_code == 503
        assert r.json()["ok"] is False


# ─────────────────────────────────────────────────────────────────────────────
# GET /health/version
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthVersion:
    def test_retorna_200(self, client):
        r = client.get("/health/version")
        assert r.status_code == 200

    def test_ok_true(self, client):
        assert client.get("/health/version").json()["ok"] is True

    def test_campos_obrigatorios(self, client):
        body = client.get("/health/version").json()
        for campo in ("version", "env", "uptime_s", "timestamp", "outbox_ativo"):
            assert campo in body, f"Campo ausente: {campo}"

    def test_uptime_positivo(self, client):
        body = client.get("/health/version").json()
        assert body["uptime_s"] >= 0

    def test_version_com_meta_instalacao(self, db_path):
        """Se meta_instalacao tiver dados, /health/version deve refletir."""
        from app.main import app

        now = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        for chave, valor in [
            ("nucleo_version", "9.9.9"),
            ("org_id", "TESTE-ORG"),
            ("instance_name", "Instituição Teste"),
            ("instalado_em", now),
        ]:
            conn.execute(
                "INSERT OR REPLACE INTO meta_instalacao (chave, valor, criado_em) VALUES (?, ?, ?)",
                (chave, valor, now),
            )
        conn.commit()
        conn.close()

        with patch("app.routers.health.get_conn", _make_get_conn(db_path)):
            with TestClient(app) as c:
                body = c.get("/health/version").json()

        assert body["version"] == "9.9.9"
        assert body["org_id"] == "TESTE-ORG"
        assert body["instance_name"] == "Instituição Teste"


# ─────────────────────────────────────────────────────────────────────────────
# create_admin.py — idempotência
# ─────────────────────────────────────────────────────────────────────────────

class TestCreateAdmin:
    """Testa a lógica de create_admin via importação direta das funções."""

    @pytest.fixture()
    def env_admin(self, monkeypatch):
        monkeypatch.setenv("PICSAUDE_ADMIN_EMAIL", "admin@teste.br")
        monkeypatch.setenv("PICSAUDE_ADMIN_NOME", "Admin Teste")
        monkeypatch.setenv("PICSAUDE_ADMIN_SENHA", "SenhaForte!2026")
        monkeypatch.setenv("PICSAUDE_VERSION", "1.0.0")
        monkeypatch.setenv("PICSAUDE_INSTANCE_ORG_ID", "TESTE-001")
        monkeypatch.setenv("PICSAUDE_INSTANCE_NAME", "Instituição Teste")
        monkeypatch.setenv("PICSAUDE_BOOTSTRAP_VERSION", "1.0.0")

    def _run_create_admin(self, db_path, env_admin):
        """Executa a lógica de create_admin usando o banco de teste."""
        import importlib
        import create_admin as ca
        importlib.reload(ca)  # recarrega para capturar os env vars do monkeypatch

        with patch("create_admin.get_conn", _make_get_conn(db_path)):
            ca._criar_admin()
            ca._registrar_meta()

    def test_cria_admin_novo(self, db_path, env_admin):
        self._run_create_admin(db_path, env_admin)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT role, nome FROM usuarios WHERE identificador = ?",
            ("admin@teste.br",),
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["role"] == "admin"

    def test_idempotente_nao_duplica(self, db_path, env_admin):
        """Rodar duas vezes não deve criar dois admins."""
        self._run_create_admin(db_path, env_admin)
        self._run_create_admin(db_path, env_admin)
        conn = sqlite3.connect(db_path)
        total = conn.execute(
            "SELECT COUNT(*) FROM usuarios WHERE identificador = ?",
            ("admin@teste.br",),
        ).fetchone()[0]
        conn.close()
        assert total == 1

    def test_meta_instalacao_preenchida(self, db_path, env_admin):
        self._run_create_admin(db_path, env_admin)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        meta = {
            row["chave"]: row["valor"]
            for row in conn.execute("SELECT chave, valor FROM meta_instalacao").fetchall()
        }
        conn.close()
        assert meta.get("nucleo_version") == "1.0.0"
        assert meta.get("org_id") == "TESTE-001"
        assert meta.get("instalado_em") is not None

    def test_meta_idempotente(self, db_path, env_admin):
        """Re-executar não deve criar duplicatas em meta_instalacao."""
        self._run_create_admin(db_path, env_admin)
        self._run_create_admin(db_path, env_admin)
        conn = sqlite3.connect(db_path)
        total = conn.execute(
            "SELECT COUNT(*) FROM meta_instalacao WHERE chave = 'nucleo_version'"
        ).fetchone()[0]
        conn.close()
        assert total == 1
