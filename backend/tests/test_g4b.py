"""
test_g4b.py — Testes do G4B — Adapter Layer
============================================

Cobre:
  API Keys:
  - Criação de API key (admin)
  - Criação falha se prestador não existe → 404
  - Listagem de API keys
  - Revogação (deleção lógica)
  - Revogação de key inexistente → 404
  - Revogação de key já revogada → 409
  - Não admin não pode criar/listar/revogar API keys → 403

  Autenticação dupla em /eventos:
  - Admin acessa /eventos via JWT (comportamento G4A original)
  - Integrador acessa /eventos via API key
  - Integrador só vê eventos do seu org_id (guardrail de escopo)
  - API key inválida → 401
  - API key revogada → 401
  - Sem autenticação → 401
  - Integrador dá ACK em evento do seu org_id → ok
  - Integrador NÃO dá ACK em evento de outro org_id → 403

  Adapter JSON Local:
  - Ciclo de processamento com eventos pendentes
  - Idempotência: evento já processado não é reprocessado
  - Cursor atualizado após ciclo
  - Falha de persistência não dá ACK
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de fixture
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
    path = str(tmp_path / "test_g4b.db")
    _init_schema(path)
    return path


@pytest.fixture()
def admin_client(db_path):
    from app.main import app
    from app.auth.dependencies import get_current_user, get_current_user_or_api_key
    _admin = {"role": "admin", "sub": "admin@test"}
    app.dependency_overrides[get_current_user] = lambda: _admin
    app.dependency_overrides[get_current_user_or_api_key] = lambda: _admin
    with (
        patch("app.routers.api_keys.get_conn", _make_get_conn(db_path)),
        patch("app.routers.prestadores.get_conn", _make_get_conn(db_path)),
        patch("app.routers.eventos.get_conn", _make_get_conn(db_path)),
        patch("app.auth.dependencies.get_conn", side_effect=_make_get_conn(db_path)),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_user_or_api_key, None)


@pytest.fixture()
def prescritor_client(db_path):
    from app.main import app
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "pres@test"}
    with (
        patch("app.routers.api_keys.get_conn", _make_get_conn(db_path)),
    ):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user, None)


def _criar_prestador(client, org_id="hosp-teste"):
    client.post("/prestadores", json={"org_id": org_id, "nome": "Hospital Teste", "tipo": "hospital"})


def _criar_api_key(client, org_id="hosp-teste", nome="Adapter Teste"):
    r = client.post("/admin/api-keys", json={"org_id": org_id, "nome": nome})
    assert r.status_code == 201
    return r.json()


def _hash_chave(chave: str) -> str:
    return hashlib.sha256(chave.encode()).hexdigest()


def _inserir_evento(db_path, org_id="hosp-teste", evento_id=None):
    """Insere evento direto no banco para testes de consumo."""
    conn = sqlite3.connect(db_path)
    evt_id = evento_id or f"evt_{uuid.uuid4()}"
    conn.execute(
        """
        INSERT INTO eventos_publicacao
            (id, tipo_evento, objeto_tipo, objeto_id, payload, org_id, publicado, tentativas, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, datetime('now'))
        """,
        (evt_id, "agendamento_realizado", "agendamento", str(uuid.uuid4()), '{"teste": true}', org_id),
    )
    conn.commit()
    conn.close()
    return evt_id


# ─────────────────────────────────────────────────────────────────────────────
# API Keys — criação
# ─────────────────────────────────────────────────────────────────────────────

class TestCriarApiKey:
    def test_criar_com_sucesso(self, admin_client):
        _criar_prestador(admin_client)
        r = admin_client.post("/admin/api-keys", json={"org_id": "hosp-teste", "nome": "Adapter HIS"})
        assert r.status_code == 201

    def test_retorna_chave_bruta(self, admin_client):
        _criar_prestador(admin_client)
        r = admin_client.post("/admin/api-keys", json={"org_id": "hosp-teste", "nome": "Adapter HIS"})
        assert "chave" in r.json()
        assert len(r.json()["chave"]) > 20

    def test_retorna_aviso_guardar_chave(self, admin_client):
        _criar_prestador(admin_client)
        r = admin_client.post("/admin/api-keys", json={"org_id": "hosp-teste", "nome": "Adapter"})
        assert "aviso" in r.json()

    def test_prestador_inexistente_retorna_404(self, admin_client):
        r = admin_client.post("/admin/api-keys", json={"org_id": "nao-existe", "nome": "Adapter"})
        assert r.status_code == 404

    def test_nao_admin_retorna_403(self, prescritor_client):
        r = prescritor_client.post("/admin/api-keys", json={"org_id": "x", "nome": "x"})
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# API Keys — listagem e revogação
# ─────────────────────────────────────────────────────────────────────────────

class TestGerenciarApiKey:
    def test_listar_retorna_lista(self, admin_client):
        _criar_prestador(admin_client)
        _criar_api_key(admin_client)
        r = admin_client.get("/admin/api-keys")
        assert r.status_code == 200
        assert len(r.json()["api_keys"]) == 1

    def test_listar_nao_expoe_chave_hash(self, admin_client):
        _criar_prestador(admin_client)
        _criar_api_key(admin_client)
        r = admin_client.get("/admin/api-keys")
        # chave_hash não deve aparecer na listagem
        assert "chave_hash" not in r.json()["api_keys"][0]
        assert "chave" not in r.json()["api_keys"][0]

    def test_revogar_com_sucesso(self, admin_client, db_path):
        _criar_prestador(admin_client)
        key_data = _criar_api_key(admin_client)
        r = admin_client.delete(f"/admin/api-keys/{key_data['id']}")
        assert r.status_code == 200
        assert r.json()["revogada"] is True

    def test_revogar_inexistente_retorna_404(self, admin_client):
        r = admin_client.delete("/admin/api-keys/nao-existe")
        assert r.status_code == 404

    def test_revogar_ja_revogada_retorna_409(self, admin_client):
        _criar_prestador(admin_client)
        key_data = _criar_api_key(admin_client)
        admin_client.delete(f"/admin/api-keys/{key_data['id']}")
        r = admin_client.delete(f"/admin/api-keys/{key_data['id']}")
        assert r.status_code == 409

    def test_nao_admin_nao_pode_listar(self, prescritor_client):
        r = prescritor_client.get("/admin/api-keys")
        assert r.status_code == 403


# ─────────────────────────────────────────────────────────────────────────────
# Autenticação dupla em /eventos
# ─────────────────────────────────────────────────────────────────────────────

class TestEventosAutenticacao:
    def test_admin_jwt_acessa_eventos(self, admin_client, db_path):
        _inserir_evento(db_path)
        r = admin_client.get("/eventos")
        assert r.status_code == 200

    def test_sem_autenticacao_retorna_401(self, db_path):
        from app.main import app
        with (
            patch("app.routers.eventos.get_conn", _make_get_conn(db_path)),
            patch("app.auth.dependencies.get_conn", side_effect=_make_get_conn(db_path)),
        ):
            with TestClient(app) as c:
                r = c.get("/eventos")
        assert r.status_code == 401

    def test_api_key_invalida_retorna_401(self, db_path):
        from app.main import app
        with (
            patch("app.routers.eventos.get_conn", _make_get_conn(db_path)),
            patch("app.auth.dependencies.get_conn", side_effect=_make_get_conn(db_path)),
        ):
            with TestClient(app) as c:
                r = c.get("/eventos", headers={"X-Api-Key": "chave-invalida-qualquer"})
        assert r.status_code == 401

    def _raw_client_api_key(self, db_path):
        """Cria TestClient sem overrides de dependency — para testar API key real."""
        from app.main import app
        from app.auth.dependencies import get_current_user_or_api_key
        # Remove override temporariamente para que a validação real de API key ocorra
        override = app.dependency_overrides.pop(get_current_user_or_api_key, None)
        patches = (
            patch("app.routers.eventos.get_conn", _make_get_conn(db_path)),
            patch("app.auth.dependencies.get_conn", side_effect=_make_get_conn(db_path)),
        )
        return app, override, get_current_user_or_api_key, patches

    def test_integrador_via_api_key_acessa_eventos(self, admin_client, db_path):
        _criar_prestador(admin_client)
        key_data = _criar_api_key(admin_client, org_id="hosp-teste")
        chave = key_data["chave"]
        _inserir_evento(db_path, org_id="hosp-teste")

        app, override, dep, patches = self._raw_client_api_key(db_path)
        try:
            with patches[0], patches[1]:
                with TestClient(app) as c:
                    r = c.get("/eventos", headers={"X-Api-Key": chave})
        finally:
            if override:
                app.dependency_overrides[dep] = override
        assert r.status_code == 200

    def test_integrador_so_ve_seu_org_id(self, admin_client, db_path):
        """Integrador não pode ver eventos de outro org_id."""
        _criar_prestador(admin_client, org_id="hosp-a")
        _criar_prestador(admin_client, org_id="hosp-b")
        key_data = _criar_api_key(admin_client, org_id="hosp-a")
        chave = key_data["chave"]

        _inserir_evento(db_path, org_id="hosp-a")
        _inserir_evento(db_path, org_id="hosp-b")

        app, override, dep, patches = self._raw_client_api_key(db_path)
        try:
            with patches[0], patches[1]:
                with TestClient(app) as c:
                    r = c.get("/eventos", headers={"X-Api-Key": chave})
        finally:
            if override:
                app.dependency_overrides[dep] = override

        assert r.status_code == 200
        eventos = r.json()["eventos"]
        for evt in eventos:
            assert evt["org_id"] == "hosp-a"
        assert len(eventos) == 1

    def test_integrador_ack_proprio_evento(self, admin_client, db_path):
        _criar_prestador(admin_client, org_id="hosp-a")
        key_data = _criar_api_key(admin_client, org_id="hosp-a")
        chave = key_data["chave"]
        evt_id = _inserir_evento(db_path, org_id="hosp-a")

        app, override, dep, patches = self._raw_client_api_key(db_path)
        try:
            with patches[0], patches[1]:
                with TestClient(app) as c:
                    r = c.post(f"/eventos/{evt_id}/ack", headers={"X-Api-Key": chave})
        finally:
            if override:
                app.dependency_overrides[dep] = override
        assert r.status_code == 200

    def test_integrador_nao_faz_ack_evento_outro_org(self, admin_client, db_path):
        _criar_prestador(admin_client, org_id="hosp-a")
        _criar_prestador(admin_client, org_id="hosp-b")
        key_data = _criar_api_key(admin_client, org_id="hosp-a")
        chave_a = key_data["chave"]
        evt_id_b = _inserir_evento(db_path, org_id="hosp-b")

        app, override, dep, patches = self._raw_client_api_key(db_path)
        try:
            with patches[0], patches[1]:
                with TestClient(app) as c:
                    r = c.post(f"/eventos/{evt_id_b}/ack", headers={"X-Api-Key": chave_a})
        finally:
            if override:
                app.dependency_overrides[dep] = override
        assert r.status_code == 403

    def test_api_key_revogada_retorna_401(self, admin_client, db_path):
        _criar_prestador(admin_client)
        key_data = _criar_api_key(admin_client)
        chave = key_data["chave"]
        admin_client.delete(f"/admin/api-keys/{key_data['id']}")

        app, override, dep, patches = self._raw_client_api_key(db_path)
        try:
            with patches[0], patches[1]:
                with TestClient(app) as c:
                    r = c.get("/eventos", headers={"X-Api-Key": chave})
        finally:
            if override:
                app.dependency_overrides[dep] = override
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Adapter JSON Local — testes unitários
# ─────────────────────────────────────────────────────────────────────────────

class TestAdapterJsonLocal:
    """
    Testa a lógica do adapter sem fazer chamadas HTTP reais.
    O ClientePicSaude é mockado.
    """

    def _make_evento(self, evento_id=None, org_id="hosp-x"):
        eid = evento_id or f"evt_{uuid.uuid4()}"
        return {
            "id":          eid,
            "tipo_evento": "agendamento_realizado",
            "objeto":      {"tipo": "agendamento", "id": str(uuid.uuid4())},
            "org_id":      org_id,
            "unidade_id":  None,
            "timestamp":   "2026-01-01T10:00:00",
            "publicado":   False,
            "payload":     {"info": "teste"},
        }

    def test_ciclo_processa_evento(self, tmp_path):
        from adapters.json_local.adapter import Config, EstadoLocal, executar_ciclo

        cfg = MagicMock(spec=Config)
        cfg.org_id     = "hosp-x"
        cfg.limite     = 100
        cfg.output_dir = tmp_path / "output"

        estado  = EstadoLocal(str(tmp_path / "state.db"))
        evento  = self._make_evento(org_id="hosp-x")
        evt_id  = evento["id"]

        cliente = MagicMock()
        cliente.buscar_eventos.return_value = {
            "eventos":        [evento],
            "proximo_cursor": "2026-01-01T10:00:01",
        }
        cliente.ack.return_value = True

        n = executar_ciclo(cfg, estado, cliente)
        assert n == 1
        estado.fechar()

    def test_idempotencia_nao_reprocessa(self, tmp_path):
        from adapters.json_local.adapter import Config, EstadoLocal, executar_ciclo

        cfg = MagicMock(spec=Config)
        cfg.org_id     = "hosp-x"
        cfg.limite     = 100
        cfg.output_dir = tmp_path / "output"

        estado  = EstadoLocal(str(tmp_path / "state.db"))
        evento  = self._make_evento(org_id="hosp-x")
        evt_id  = evento["id"]

        # Marcar como já processado
        estado.registrar(evt_id, "ok")

        cliente = MagicMock()
        cliente.buscar_eventos.return_value = {
            "eventos":        [evento],
            "proximo_cursor": None,
        }
        cliente.ack.return_value = True

        n = executar_ciclo(cfg, estado, cliente)
        assert n == 0  # idempotência: não reprocessado
        cliente.ack.assert_not_called()
        estado.fechar()

    def test_cursor_atualizado_apos_ciclo(self, tmp_path):
        from adapters.json_local.adapter import Config, EstadoLocal, executar_ciclo

        cfg = MagicMock(spec=Config)
        cfg.org_id     = "hosp-x"
        cfg.limite     = 100
        cfg.output_dir = tmp_path / "output"

        estado = EstadoLocal(str(tmp_path / "state.db"))
        evento = self._make_evento(org_id="hosp-x")

        cliente = MagicMock()
        cliente.buscar_eventos.return_value = {
            "eventos":        [evento],
            "proximo_cursor": "2026-06-01T00:00:00",
        }
        cliente.ack.return_value = True

        executar_ciclo(cfg, estado, cliente)
        cursor = estado.obter_cursor("hosp-x")
        assert cursor == "2026-06-01T00:00:00"
        estado.fechar()

    def test_falha_persistencia_nao_da_ack(self, tmp_path):
        from adapters.json_local.adapter import Config, EstadoLocal, executar_ciclo

        cfg = MagicMock(spec=Config)
        cfg.org_id     = "hosp-x"
        cfg.limite     = 100
        # diretório inválido (arquivo, não pasta)
        invalid_dir = tmp_path / "bloqueado.txt"
        invalid_dir.write_text("bloqueado")
        cfg.output_dir = invalid_dir  # tentativa de gravar em arquivo = erro

        estado  = EstadoLocal(str(tmp_path / "state.db"))
        evento  = self._make_evento(org_id="hosp-x")

        cliente = MagicMock()
        cliente.buscar_eventos.return_value = {
            "eventos":        [evento],
            "proximo_cursor": None,
        }
        cliente.ack.return_value = True

        n = executar_ciclo(cfg, estado, cliente)
        assert n == 0  # falhou a persistência
        cliente.ack.assert_not_called()  # ACK não dado
        estado.fechar()

    def test_zero_eventos_retorna_zero(self, tmp_path):
        from adapters.json_local.adapter import Config, EstadoLocal, executar_ciclo

        cfg = MagicMock(spec=Config)
        cfg.org_id     = "hosp-x"
        cfg.limite     = 100
        cfg.output_dir = tmp_path / "output"

        estado  = EstadoLocal(str(tmp_path / "state.db"))
        cliente = MagicMock()
        cliente.buscar_eventos.return_value = {"eventos": [], "proximo_cursor": None}

        n = executar_ciclo(cfg, estado, cliente)
        assert n == 0
        estado.fechar()
