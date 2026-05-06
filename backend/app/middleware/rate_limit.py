"""
rate_limit.py — Ticket 62C
===========================
Rate limiting por IP, in-memory, sem dependências externas.

Características:
- Janela deslizante de 60 segundos
- Limites por rota (auth < tokens < circulação < default)
- Proteção contra memory leak (limpeza por requisição + limpeza global)
- Cloud-ready: lê X-Forwarded-For para IP real atrás de proxy
- Compatível com Cloud Run (stateless por instância — sem Redis)

Para desabilitar em testes/dev, defina a variável de ambiente:
    RATE_LIMIT_DISABLED=1
"""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Deque, Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

WINDOW_SECONDS = 60

# Prefixos de rota → limite de requisições por janela
# Avaliados em ordem; o primeiro match vence.
ROUTE_LIMITS: list[tuple[str, int]] = [
    ("/auth/token",          5),
    ("/tokens/apresentacao", 10),
    ("/circulacao",          20),
]
DEFAULT_LIMIT = 30

# Threshold para limpeza global do dicionário de IPs
_MAX_IPS = 10_000

# ---------------------------------------------------------------------------
# Estado global (in-memory, por instância de processo)
# ---------------------------------------------------------------------------

# { ip: deque([timestamp, ...]) }  — timestamps em ordem crescente
_store: Dict[str, Deque[float]] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ip(request: Request) -> str:
    """Retorna o IP do cliente, respeitando X-Forwarded-For (proxy/Cloud Run)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Formato: "client, proxy1, proxy2" — pega o primeiro (cliente real)
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _get_limit(path: str) -> int:
    """Retorna o limite correspondente ao prefixo da rota."""
    normalized = path.rstrip("/")
    for prefix, limit in ROUTE_LIMITS:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return limit
    return DEFAULT_LIMIT


def _purge_ip(timestamps: Deque[float], now: float) -> None:
    """Remove do deque todos os timestamps fora da janela atual."""
    cutoff = now - WINDOW_SECONDS
    while timestamps and timestamps[0] <= cutoff:
        timestamps.popleft()


def _global_cleanup(now: float) -> None:
    """Remove IPs sem timestamps válidos quando o dicionário cresce demais."""
    cutoff = now - WINDOW_SECONDS
    stale = [ip for ip, ts in _store.items() if not ts or ts[-1] <= cutoff]
    for ip in stale:
        del _store[ip]


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting por IP com janela deslizante.

    Adicione ao app ANTES dos demais middlewares:

        app.add_middleware(RateLimitMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        # Permite bypass via env var — útil em testes e ambientes de dev controlados
        if os.getenv("RATE_LIMIT_DISABLED"):
            return await call_next(request)

        now = time.monotonic()
        ip = _get_ip(request)
        path = request.url.path
        limit = _get_limit(path)

        # Inicializa deque para IP novo
        if ip not in _store:
            # Limpeza global proativa antes de adicionar novo IP
            if len(_store) >= _MAX_IPS:
                _global_cleanup(now)
            _store[ip] = deque()

        timestamps = _store[ip]

        # Remove timestamps fora da janela para este IP
        _purge_ip(timestamps, now)

        if len(timestamps) >= limit:
            retry_after = int(WINDOW_SECONDS - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Muitas requisições. Tente novamente em instantes.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        return await call_next(request)
