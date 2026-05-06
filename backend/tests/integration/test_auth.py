"""Ticket 13 — autenticação do prescritor contra banco real."""
from __future__ import annotations


def test_login_valido_retorna_access_token(client, seed_usuario):
    r = client.post(
        "/auth/token",
        data={"username": seed_usuario["cns"], "password": seed_usuario["senha"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert body.get("role") == "prescritor"
    assert body.get("token_type") == "bearer"


def test_login_credenciais_invalidas(client, seed_usuario):
    r = client.post(
        "/auth/token",
        data={"username": seed_usuario["cns"], "password": "senha_errada"},
    )
    assert r.status_code == 401


def test_login_usuario_inexistente(client):
    r = client.post(
        "/auth/token",
        data={"username": "000000000000000", "password": "qualquer"},
    )
    assert r.status_code == 401


def test_acesso_sem_token_rejeitado(client):
    """Endpoint protegido exige Bearer; sem token → 401."""
    r = client.post("/prescricoes", json={})
    assert r.status_code == 401
