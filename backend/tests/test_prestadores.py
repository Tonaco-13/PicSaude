"""
test_prestadores.py — Testes do módulo de Prestadores (Ticket 30)

Cobre:
  - Criação de prestador (happy path)
  - org_id duplicado → 409
  - Tipo de prestador inválido → 422
  - Campos obrigatórios ausentes → 422
  - Listagem de prestadores
  - Consulta por org_id
  - Prestador inexistente → 404
  - Criação de unidade (happy path)
  - Unidade duplicada no mesmo prestador → 409
  - Mesma unidade_id em prestadores diferentes → permitido
  - Tipo de unidade inválido → 422
  - Listagem de unidades
  - Consulta de unidade específica
  - Unidade inexistente → 404
  - Role enforcement (apenas admin)
  - Persistência correta (org_id imutável no retorno)
"""
from __future__ import annotations

import sqlite3
import sys
import os
from unittest.mock import patch

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
    path = str(tmp_path / "test_prestadores.db")
    _init_schema(path)
    return path


@pytest.fixture()
def admin_client(db_path):
    from app.main import app
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"role": "admin", "sub": "admin@test"}
    with patch("app.routers.prestadores.get_conn", _make_get_conn(db_path)):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def prescritor_client(db_path):
    from app.main import app
    from app.auth.dependencies import get_current_user
    app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "123"}
    with patch("app.routers.prestadores.get_conn", _make_get_conn(db_path)):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user, None)


PAYLOAD_PRESTADOR = {
    "org_id": "hosp-teste",
    "nome":   "Hospital Universitário Teste",
    "tipo":   "hospital",
    "cnpj":   "12345678000199",
}

PAYLOAD_UNIDADE = {
    "unidade_id": "lab-central",
    "nome":       "Laboratório Central",
    "tipo":       "laboratorio",
}


# ─────────────────────────────────────────────────────────────────────────────
# Criação de prestador
# ─────────────────────────────────────────────────────────────────────────────

class TestCriarPrestador:
    def test_cria_com_sucesso(self, admin_client):
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.status_code == 201

    def test_retorna_org_id(self, admin_client):
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.json()["org_id"] == "hosp-teste"

    def test_retorna_nome(self, admin_client):
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.json()["nome"] == "Hospital Universitário Teste"

    def test_retorna_tipo(self, admin_client):
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.json()["tipo"] == "hospital"

    def test_ativo_por_padrao(self, admin_client):
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.json()["ativo"] is True

    def test_org_id_duplicado_retorna_409(self, admin_client):
        admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        r = admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.status_code == 409

    def test_tipo_invalido_retorna_422(self, admin_client):
        r = admin_client.post("/prestadores", json={**PAYLOAD_PRESTADOR, "tipo": "convenio"})
        assert r.status_code == 422

    def test_org_id_vazio_retorna_422(self, admin_client):
        r = admin_client.post("/prestadores", json={**PAYLOAD_PRESTADOR, "org_id": ""})
        assert r.status_code == 422

    def test_nome_vazio_retorna_422(self, admin_client):
        r = admin_client.post("/prestadores", json={**PAYLOAD_PRESTADOR, "nome": ""})
        assert r.status_code == 422

    def test_cnpj_opcional(self, admin_client):
        payload = {k: v for k, v in PAYLOAD_PRESTADOR.items() if k != "cnpj"}
        r = admin_client.post("/prestadores", json=payload)
        assert r.status_code == 201
        assert r.json()["cnpj"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Listagem e consulta de prestador
# ─────────────────────────────────────────────────────────────────────────────

class TestConsultaPrestador:
    def test_listar_retorna_lista(self, admin_client):
        admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        r = admin_client.get("/prestadores")
        assert r.status_code == 200
        assert len(r.json()["prestadores"]) == 1

    def test_obter_por_org_id(self, admin_client):
        admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        r = admin_client.get("/prestadores/hosp-teste")
        assert r.status_code == 200
        assert r.json()["org_id"] == "hosp-teste"

    def test_org_id_inexistente_retorna_404(self, admin_client):
        r = admin_client.get("/prestadores/nao-existe")
        assert r.status_code == 404

    def test_listar_vazio(self, admin_client):
        r = admin_client.get("/prestadores")
        assert r.json()["prestadores"] == []


# ─────────────────────────────────────────────────────────────────────────────
# Criação de unidade
# ─────────────────────────────────────────────────────────────────────────────

class TestCriarUnidade:
    def _criar_prestador(self, client):
        client.post("/prestadores", json=PAYLOAD_PRESTADOR)

    def test_cria_unidade_com_sucesso(self, admin_client):
        self._criar_prestador(admin_client)
        r = admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        assert r.status_code == 201

    def test_retorna_unidade_id(self, admin_client):
        self._criar_prestador(admin_client)
        r = admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        assert r.json()["unidade_id"] == "lab-central"

    def test_retorna_prestador_org_id(self, admin_client):
        self._criar_prestador(admin_client)
        r = admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        assert r.json()["prestador_org_id"] == "hosp-teste"

    def test_unidade_duplicada_mesmo_prestador_retorna_409(self, admin_client):
        self._criar_prestador(admin_client)
        admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        r = admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        assert r.status_code == 409

    def test_mesma_unidade_id_prestadores_diferentes_permitido(self, admin_client):
        """Mesma unidade_id em org_ids diferentes deve ser aceita."""
        admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        admin_client.post("/prestadores", json={**PAYLOAD_PRESTADOR, "org_id": "outro-hospital"})
        r1 = admin_client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)
        r2 = admin_client.post("/prestadores/outro-hospital/unidades", json=PAYLOAD_UNIDADE)
        assert r1.status_code == 201
        assert r2.status_code == 201

    def test_tipo_unidade_invalido_retorna_422(self, admin_client):
        self._criar_prestador(admin_client)
        r = admin_client.post(
            "/prestadores/hosp-teste/unidades",
            json={**PAYLOAD_UNIDADE, "tipo": "tipo_invalido"},
        )
        assert r.status_code == 422

    def test_tipo_unidade_opcional(self, admin_client):
        self._criar_prestador(admin_client)
        payload = {k: v for k, v in PAYLOAD_UNIDADE.items() if k != "tipo"}
        r = admin_client.post("/prestadores/hosp-teste/unidades", json=payload)
        assert r.status_code == 201
        assert r.json()["tipo"] is None

    def test_prestador_inexistente_retorna_404(self, admin_client):
        r = admin_client.post("/prestadores/nao-existe/unidades", json=PAYLOAD_UNIDADE)
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Listagem e consulta de unidade
# ─────────────────────────────────────────────────────────────────────────────

class TestConsultaUnidade:
    def _setup(self, client):
        client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        client.post("/prestadores/hosp-teste/unidades", json=PAYLOAD_UNIDADE)

    def test_listar_unidades(self, admin_client):
        self._setup(admin_client)
        r = admin_client.get("/prestadores/hosp-teste/unidades")
        assert r.status_code == 200
        assert len(r.json()["unidades"]) == 1

    def test_listar_unidades_prestador_inexistente_retorna_404(self, admin_client):
        r = admin_client.get("/prestadores/nao-existe/unidades")
        assert r.status_code == 404

    def test_obter_unidade(self, admin_client):
        self._setup(admin_client)
        r = admin_client.get("/prestadores/hosp-teste/unidades/lab-central")
        assert r.status_code == 200
        assert r.json()["unidade_id"] == "lab-central"

    def test_obter_unidade_inexistente_retorna_404(self, admin_client):
        admin_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        r = admin_client.get("/prestadores/hosp-teste/unidades/nao-existe")
        assert r.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# Role enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestRoleEnforcement:
    def test_prescritor_nao_pode_criar_prestador(self, prescritor_client):
        r = prescritor_client.post("/prestadores", json=PAYLOAD_PRESTADOR)
        assert r.status_code == 403

    def test_prescritor_nao_pode_listar_prestadores(self, prescritor_client):
        r = prescritor_client.get("/prestadores")
        assert r.status_code == 403

    def test_prescritor_nao_pode_criar_unidade(self, prescritor_client):
        r = prescritor_client.post("/prestadores/qualquer/unidades", json=PAYLOAD_UNIDADE)
        assert r.status_code == 403

    def test_sem_auth_retorna_401(self, db_path):
        from app.main import app
        with patch("app.routers.prestadores.get_conn", _make_get_conn(db_path)):
            with TestClient(app) as c:
                r = c.get("/prestadores")
        assert r.status_code == 401
