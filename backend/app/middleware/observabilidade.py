"""
middleware/observabilidade.py — Ticket 11
==========================================
Middleware ASGI de logging e métricas por requisição.

Implementado como ASGI middleware puro (não BaseHTTPMiddleware) para evitar
o deadlock conhecido do Starlette ao empilhar múltiplos BaseHTTPMiddleware.

Para cada request:
  - Gera request_id (uuid4 curto)
  - Mede latência em ms
  - Captura status code via intercepção do send()
  - Loga estruturadamente ao final (INFO ou ERROR)
  - Atualiza contadores em memória

NÃO loga:
  - Payload do body
  - Query strings (podem conter dados sensíveis)
  - Dados clínicos, CPF, CNS, nome de paciente
"""
from __future__ import annotations

import time
import uuid
from typing import Callable

from starlette.types import ASGIApp, Receive, Scope, Send

from app.observabilidade.logging_config import get_logger
from app.observabilidade.metrics import metrics

_log = get_logger("picsaude.request")
_err = get_logger("picsaude.error")


class ObservabilidadeMiddleware:
    """Middleware ASGI puro — compatível com empilhamento de múltiplos middlewares."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex[:12]
        start = time.monotonic()

        # Extrai path e method do scope (não depende de Request object)
        path = scope.get("path", "")
        method = scope.get("method", "")

        # Adiciona request_id ao scope para uso nos handlers via state
        from starlette.datastructures import State as _State
        if not isinstance(scope.get("state"), _State):
            scope["state"] = _State()
        scope["state"].request_id = request_id

        status_code = 500

        async def send_with_logging(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 500)
                # Adiciona X-Request-Id aos headers da resposta
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        exc_type = None
        try:
            await self.app(scope, receive, send_with_logging)
        except Exception as exc:
            exc_type = type(exc).__name__
            _err.error(
                "unhandled_exception",
                extra={
                    "path": path,
                    "method": method,
                    "status": 500,
                    "request_id": request_id,
                    "type": exc_type,
                },
                exc_info=True,
            )
            raise
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            metrics.record_request(status_code, latency_ms)

            log_fn = (
                _log.info if status_code < 400
                else _err.warning if status_code < 500
                else _err.error
            )
            extra = {
                "path": path,
                "method": method,
                "status": status_code,
                "latency_ms": round(latency_ms, 2),
                "request_id": request_id,
            }
            if exc_type:
                extra["type"] = exc_type
            log_fn("request", extra=extra)
