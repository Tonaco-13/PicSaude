"""
tests/unit/test_lista_espera.py — despacho "Lista de espera direta" (module).

Cobre POST /lista-espera: validação de campo, honeypot (§4), e o rate limit
por IP já existente em `app/middleware/rate_limit.py` (§4). Sobrevivência
ao reset (§2) é provada contra PostgreSQL real em
`tests/integration/test_reset_demo_db_pg.py::test_lista_espera_sobrevive_ao_reset`
— este arquivo isola o storage SQLite em `tmp_path` (nunca toca
`data/lista_espera.db` de verdade).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.domain import lista_espera as store
from app.main import app
from app.middleware import rate_limit as _rl


@pytest.fixture(autouse=True)
def _isolar_storage(tmp_path, monkeypatch):
    """Cada teste grava num arquivo SQLite descartável — nunca o real."""
    monkeypatch.setattr(store, "_SQLITE_PATH", tmp_path / "lista_espera_test.db")
    yield


@pytest.fixture()
def client():
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


def _payload(**over):
    base = {"nome": "Maria de Teste", "email": "maria@example.com", "origem": "teste"}
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# Caminho feliz
# ---------------------------------------------------------------------------

def test_inscricao_valida_grava_e_devolve_201(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload())
    assert resp.status_code == 201, resp.text
    assert store.contar_inscricoes() == 1


def test_origem_e_opcional(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    payload = _payload()
    del payload["origem"]
    resp = client.post("/lista-espera", json=payload)
    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Validação (§4 do despacho: nome 2–200, email formato+tamanho)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nome", ["", "A", "  A  "])
def test_nome_curto_demais_e_rejeitado(client, monkeypatch, nome):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload(nome=nome))
    assert resp.status_code == 422
    assert store.contar_inscricoes() == 0


def test_nome_muito_longo_e_rejeitado(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload(nome="A" * 201))
    assert resp.status_code == 422


@pytest.mark.parametrize("email", ["", "sem-arroba", "a@b", "@example.com", "a@.com"])
def test_email_mal_formado_e_rejeitado(client, monkeypatch, email):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload(email=email))
    assert resp.status_code == 422
    assert store.contar_inscricoes() == 0


def test_email_muito_longo_e_rejeitado(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    longo = "a" * 250 + "@example.com"
    resp = client.post("/lista-espera", json=_payload(email=longo))
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Honeypot (§4) — preenchido → resposta IDÊNTICA a sucesso, sem gravar
# ---------------------------------------------------------------------------

def test_honeypot_preenchido_finge_sucesso_sem_gravar(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload(empresa="Acme Bot Corp"))
    assert resp.status_code == 201, resp.text
    assert resp.json() == {"status": "ok"}
    assert store.contar_inscricoes() == 0, "honeypot acionado NÃO deveria gravar"


def test_honeypot_vazio_e_o_caminho_normal(client, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_DISABLED", "1")
    resp = client.post("/lista-espera", json=_payload(empresa=""))
    assert resp.status_code == 201
    assert store.contar_inscricoes() == 1


# ---------------------------------------------------------------------------
# Rate limit por IP (§4) — mesma régua do /auth/token, 5/janela
# ---------------------------------------------------------------------------

def test_rate_limit_bloqueia_apos_o_limite(client, monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)
    _rl._store.clear()  # isolamento: outros testes não vazam janela pra este

    limite = next(l for prefix, l in _rl.ROUTE_LIMITS if prefix == "/lista-espera")

    for i in range(limite):
        resp = client.post("/lista-espera", json=_payload(email=f"ok{i}@example.com"))
        assert resp.status_code == 201, f"request {i} deveria passar: {resp.text}"

    bloqueado = client.post("/lista-espera", json=_payload(email="excedente@example.com"))
    assert bloqueado.status_code == 429, bloqueado.text
    assert "Retry-After" in bloqueado.headers
    assert store.contar_inscricoes() == limite, "request bloqueado não deveria ter gravado"
