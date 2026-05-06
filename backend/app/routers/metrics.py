"""
routers/metrics.py — Ticket 11
================================
Endpoint GET /metrics — métricas operacionais em memória.

RESTRIÇÃO: aceita apenas requisições originadas de 127.0.0.1 / ::1 (localhost).
Requisições externas recebem 403.

LIMITAÇÕES (por design):
  - Métricas são por processo/worker — não agregadas entre múltiplos workers.
  - Reiniciam a zero em cada restart.
  - Sem persistência. Para produção real: usar Prometheus + Grafana.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.observabilidade.metrics import metrics

router = APIRouter(tags=["observabilidade"])

_LOCALHOST_IPS = {"127.0.0.1", "::1", "localhost"}


def _is_localhost(request: Request) -> bool:
    # Verifica IP direto; respeita X-Forwarded-For apenas se vier de loopback
    client_host = request.client.host if request.client else ""
    if client_host in _LOCALHOST_IPS:
        return True
    # Rejeitar X-Forwarded-For: poderia ser forjado por cliente externo
    return False


@router.get("/metrics", summary="Métricas operacionais (somente localhost)")
async def get_metrics(request: Request) -> JSONResponse:
    if not _is_localhost(request):
        return JSONResponse(
            status_code=403,
            content={
                "erro": "acesso_negado",
                "detalhe": "Endpoint /metrics acessível apenas a partir de localhost.",
            },
        )

    snapshot = metrics.snapshot()
    snapshot["timestamp"] = datetime.now(timezone.utc).isoformat()
    snapshot["aviso"] = (
        "Métricas por processo/worker. Reiniciam em restart. "
        "Sem agregação entre múltiplos workers."
    )
    return JSONResponse(content=snapshot)
