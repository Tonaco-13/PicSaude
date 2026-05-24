"""
config_publico.py
=================
TICKET-6 — endpoint público de configuração que o frontend consulta para
saber se o sistema está em modo demo.

Endpoint sempre disponível (registrado fora do gate `PICSAUDE_DEMO_MODE`).
Em modo normal, devolve `demo_mode=false` e o frontend renderiza login real.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Response

from app.config import (
    PICSAUDE_DEMO_ADMIN,
    PICSAUDE_DEMO_MODE,
    PICSAUDE_VERSION,
)

router = APIRouter(prefix="/config", tags=["config"])


def _papeis_demo_disponiveis() -> list[str]:
    """Lista de papéis aceitos pelo /demo/login conforme flags atuais."""
    base = ["prescritor", "dispensador", "paciente"]
    if PICSAUDE_DEMO_ADMIN:
        base.append("admin")
    return base


def _proximo_reset_horario() -> str:
    """ISO 8601 UTC da próxima hora cheia (alinha com cron `0 * * * *`)."""
    agora = datetime.now(timezone.utc)
    proxima = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return proxima.isoformat()


@router.get("/public", summary="Estado público do sistema (não autenticado)")
def get_config_publico(response: Response) -> dict:
    """
    Retorna estado público do sistema. Sem autenticação.

    Frontend usa para decidir entre login real e seletor demo.

    Não expõe nada sensível: versão é pública, `demo_mode` é estado público,
    `demo_roles` é lista fixa, `proximo_reset` é uma hora cheia futura.
    `instance_id` real NÃO é exposto.

    Cache-Control: no-store (P3#10 TICKET-6) — `proximo_reset` muda com o
    tempo; cache do navegador atrasaria o banner.
    """
    response.headers["Cache-Control"] = "no-store"
    proximo_reset: Optional[str] = _proximo_reset_horario() if PICSAUDE_DEMO_MODE else None
    return {
        "version":       PICSAUDE_VERSION,
        "demo_mode":     PICSAUDE_DEMO_MODE,
        "demo_admin":    PICSAUDE_DEMO_ADMIN,
        "demo_roles":    _papeis_demo_disponiveis() if PICSAUDE_DEMO_MODE else [],
        "proximo_reset": proximo_reset,
        "instance_id":   None,
    }
