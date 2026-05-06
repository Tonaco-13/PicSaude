"""
observabilidade/logging_config.py — Ticket 11
===============================================
Configura logging estruturado para o PicSaúde.

Formato: JSON-compatível (um dict por linha).
Regras de privacidade:
  - NÃO logar CPF, CNS, nome de paciente ou dados clínicos.
  - Logs devem ser parseáveis por ferramentas de análise.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    """Formata registros de log como JSON em uma única linha."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        # Campos extras adicionados via extra={} no logger
        for key in ("event", "path", "method", "status", "latency_ms", "request_id", "type"):
            if hasattr(record, key) and key != "event":
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Configura o handler raiz com saída JSON para stdout."""
    root = logging.getLogger()
    if root.handlers:
        return  # já configurado
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    # Silenciar logs verbosos de bibliotecas internas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
