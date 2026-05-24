"""
routers/health.py
=================
Endpoints de saúde e status da instância PicSaúde (G5-impl).

Endpoints:
  GET /health          — liveness: backend respondendo
  GET /health/db       — readiness: banco íntegro + tabelas presentes
  GET /health/version  — metadados da instalação (versão, org, ambiente)

Sem autenticação: esses endpoints são destinados a operadores e
infraestrutura local. Não retornam dados clínicos.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import PICSAUDE_ENV, PICSAUDE_INSTANCE_ORG_ID, PICSAUDE_VERSION
from app.database import _USE_SQLITE, get_conn
from app.database_tx import get_tx

router = APIRouter(tags=["health"])

# Timestamp de inicialização do processo (uptime)
_START_TIME: float = time.monotonic()

# Tabelas obrigatórias do núcleo PicSaúde
_TABELAS_OBRIGATORIAS: list[str] = [
    "pacientes",
    "prescritores",
    "estabelecimentos_proprios",
    "prescricoes",
    "prescricao_itens",
    "prescricao_eventos",
    "codigos_login",
    "prescricao_custodia",
    "dispensacoes",
    "usuarios",
    "prescricao_assinatura",
    "solicitacoes_renovacao",
    "pedidos_exame",
    "pedido_exame_itens",
    "pedido_exame_eventos",
    "pedido_exame_custodia",
    "laudos",
    "laudo_itens",
    "laudo_eventos",
    "laudo_custodia",
    "tokens_apresentacao",
    "tokens_apresentacao_usos",
    "dispensacoes_hospitalares",
    "agendamentos",
    "agendamento_eventos",
    "eventos_publicacao",
    "meta_instalacao",
]


# ---------------------------------------------------------------------------
# GET /health  — liveness
# ---------------------------------------------------------------------------

@router.get("/health", summary="Liveness check — backend respondendo")
def health() -> dict[str, Any]:
    return {
        "ok":        True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /health/db  — readiness
# ---------------------------------------------------------------------------

@router.get("/health/db", summary="Readiness check — banco íntegro e completo")
def health_db() -> JSONResponse:
    conn = None
    try:
        conn = get_conn()

        # 1. Integridade / conectividade do banco
        if _USE_SQLITE:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        else:
            conn.execute("SELECT 1")   # conectividade PostgreSQL
            integrity = "ok"

        # 2. Tabelas presentes
        if _USE_SQLITE:
            existentes = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        else:
            existentes = {
                row["table_name"]
                for row in conn.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                ).fetchall()
            }
        ausentes = [t for t in _TABELAS_OBRIGATORIAS if t not in existentes]

        ok = (integrity == "ok") and (len(ausentes) == 0)

        payload: dict[str, Any] = {
            "ok":        ok,
            "integrity": integrity,
            "tabelas":   len(existentes),
            "ausentes":  ausentes,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        status_code = 200 if ok else 503
    except Exception as exc:  # noqa: BLE001
        payload = {
            "ok":        False,
            "erro":      str(exc),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        status_code = 503
    finally:
        if conn is not None:
            conn.close()

    return JSONResponse(content=payload, status_code=status_code)


# ---------------------------------------------------------------------------
# GET /health/version  — metadados da instalação
# ---------------------------------------------------------------------------

@router.get("/health/version", summary="Versão e metadados da instalação")
def health_version() -> dict[str, Any]:
    uptime_s = int(time.monotonic() - _START_TIME)

    meta: dict[str, str] = {}
    try:
        with get_tx() as conn:
            rows = conn.execute("SELECT chave, valor FROM meta_instalacao").fetchall()
            meta = {row["chave"]: row["valor"] for row in rows}
    except Exception:  # noqa: BLE001
        pass  # banco pode não ter a tabela ainda (pré-bootstrap)

    return {
        "ok":              True,
        "version":         meta.get("nucleo_version", PICSAUDE_VERSION),
        "schema_version":  meta.get("schema_version", "1"),
        "env":             PICSAUDE_ENV,
        "org_id":          meta.get("org_id", PICSAUDE_INSTANCE_ORG_ID) or None,
        "instance_name":   meta.get("instance_name"),
        "instalado_em":    meta.get("instalado_em"),
        "bootstrap_version": meta.get("bootstrap_version"),
        "outbox_ativo":    True,
        "uptime_s":        uptime_s,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }
