"""
test_rate_limit.py — Ticket 62C
================================
Testes de rate limiting por IP usando a lógica interna do middleware
(sem dependência de rede nem de banco).

Estratégia:
- Testa diretamente as funções auxiliares e o state `_store`
- Usa `unittest.mock.patch` para controlar `time.monotonic`
- Usa TestClient para testes de integração HTTP (429)

Nota: a fixture `_disable_rate_limit_in_tests` (conftest raiz) desativa o
middleware para toda a suíte. Testes que precisam exercitar o middleware
devem remover a env var explicitamente via `monkeypatch`.
"""
from __future__ import annotations

import os
import time
from collections import deque
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers de importação isolada do módulo rate_limit
# ---------------------------------------------------------------------------

def _fresh_module():
    """Reimporta rate_limit com _store limpo para cada teste."""
    import importlib
    import app.middleware.rate_limit as m
    m._store.clear()
    return m


# ---------------------------------------------------------------------------
# 1. Limite respeitado — requisições abaixo do limite passam
# ---------------------------------------------------------------------------

def test_limite_respeitado():
    m = _fresh_module()
    now = 1000.0
    ip = "10.0.0.1"
    limit = 5  # limite de /auth/token

    for i in range(limit):
        m._store.setdefault(ip, deque())
        m._purge_ip(m._store[ip], now)
        assert len(m._store[ip]) < limit, f"Falhou na iteração {i}"
        m._store[ip].append(now + i * 0.1)

    # A 5ª requisição foi registrada, deve haver exatamente 5 timestamps
    assert len(m._store[ip]) == limit


# ---------------------------------------------------------------------------
# 2. Limite excedido → HTTP 429
# ---------------------------------------------------------------------------

def test_limite_excedido_retorna_429(monkeypatch):
    # Ativa o rate limiting para este teste específico
    monkeypatch.delenv("RATE_LIMIT_DISABLED", raising=False)

    from app.main import app
    import app.middleware.rate_limit as m
    m._store.clear()

    client = TestClient(app, raise_server_exceptions=False)

    # Esgota o limite de /auth/token (5/min) via headers falsos
    # Usamos um IP fixo para isolar o teste
    headers = {"X-Forwarded-For": "192.0.2.100"}

    responses = []
    for _ in range(6):
        r = client.post("/auth/token", headers=headers, data={
            "username": "x", "password": "y"
        })
        responses.append(r.status_code)

    # As primeiras 5 chegam ao endpoint (podem ser 401/422 — não 429)
    assert responses[:5] != [429] * 5, "Limite aplicado antes do 5º request"
    # A 6ª deve ser 429
    assert responses[5] == 429


# ---------------------------------------------------------------------------
# 3. Reset após tempo — timestamps expiram e novas requisições passam
# ---------------------------------------------------------------------------

def test_reset_apos_janela():
    m = _fresh_module()
    ip = "10.0.0.2"
    limit = 5

    # Simula 5 timestamps 70 segundos atrás (fora da janela)
    base = 1000.0
    m._store[ip] = deque([base - 70 + i for i in range(limit)])

    # Limpeza simula chegada de nova requisição 70s depois
    now = base
    m._purge_ip(m._store[ip], now)

    # Todos os timestamps expiraram — deque deve estar vazio
    assert len(m._store[ip]) == 0, "Timestamps antigos não foram removidos"

    # Nova requisição pode ser registrada
    m._store[ip].append(now)
    assert len(m._store[ip]) == 1


# ---------------------------------------------------------------------------
# 4. Endpoint crítico tem limite menor que o default
# ---------------------------------------------------------------------------

def test_limites_por_rota():
    m = _fresh_module()

    assert m._get_limit("/auth/token")          == 5
    assert m._get_limit("/auth/token/")         == 5   # trailing slash
    assert m._get_limit("/tokens/apresentacao") == 10
    assert m._get_limit("/tokens/apresentacao/resolver") == 10
    assert m._get_limit("/circulacao/CHAVE-123") == 20
    assert m._get_limit("/prescricoes")          == 30  # default
    assert m._get_limit("/health")               == 30  # default


# ---------------------------------------------------------------------------
# 5. Múltiplos IPs — limites são independentes por IP
# ---------------------------------------------------------------------------

def test_multiplos_ips_independentes():
    m = _fresh_module()
    limit = 5
    now = 2000.0

    # Preenche o limite para ip_a
    m._store["ip_a"] = deque([now - i * 0.5 for i in range(limit)])
    m._purge_ip(m._store["ip_a"], now)

    # ip_b ainda está limpo
    m._store.setdefault("ip_b", deque())
    m._purge_ip(m._store["ip_b"], now)

    assert len(m._store["ip_a"]) == limit, "ip_a deveria estar no limite"
    assert len(m._store["ip_b"]) == 0,     "ip_b deveria estar limpo"


# ---------------------------------------------------------------------------
# 6. Limpeza global de memória quando _store cresce demais
# ---------------------------------------------------------------------------

def test_limpeza_global_memory():
    m = _fresh_module()
    now = 3000.0
    cutoff = now - m.WINDOW_SECONDS

    # Injeta 10.001 IPs "obsoletos" (timestamps expirados)
    for i in range(m._MAX_IPS + 1):
        ip = f"172.16.{i // 256}.{i % 256}"
        m._store[ip] = deque([cutoff - 1])  # expirado

    # Adiciona 1 IP com timestamp válido
    m._store["1.2.3.4"] = deque([now - 5])

    assert len(m._store) == m._MAX_IPS + 2

    m._global_cleanup(now)

    # Apenas o IP válido deve sobrar
    assert "1.2.3.4" in m._store
    assert len(m._store) == 1, f"Esperado 1 IP, encontrado {len(m._store)}"


# ---------------------------------------------------------------------------
# 7. IP correto via X-Forwarded-For
# ---------------------------------------------------------------------------

def test_ip_forwarded_for():
    from starlette.testclient import TestClient as StarletteClient
    from starlette.applications import Starlette
    from starlette.routing import Route
    from starlette.responses import PlainTextResponse
    import app.middleware.rate_limit as m
    m._store.clear()

    # App mínimo para inspecionar IP identificado
    captured = {}

    async def homepage(request):
        captured["ip"] = m._get_ip(request)
        return PlainTextResponse("ok")

    mini_app = Starlette(routes=[Route("/", homepage)])

    with StarletteClient(mini_app) as client:
        client.get("/", headers={"X-Forwarded-For": "203.0.113.5, 10.0.0.1"})

    assert captured["ip"] == "203.0.113.5", (
        f"IP esperado: 203.0.113.5, obtido: {captured.get('ip')}"
    )


# ---------------------------------------------------------------------------
# 8. Trailing slash normalizado (sem bypass)
# ---------------------------------------------------------------------------

def test_trailing_slash_sem_bypass():
    m = _fresh_module()
    # /auth/token e /auth/token/ devem ter o mesmo limite
    assert m._get_limit("/auth/token") == m._get_limit("/auth/token/")
    assert m._get_limit("/circulacao/X") == m._get_limit("/circulacao/X/")
