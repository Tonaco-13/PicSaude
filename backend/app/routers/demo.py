"""
demo.py
=======
TICKET-6 — DEMO_MODE: endpoint de seleção de papel + listagem de personas.

O router é registrado apenas quando `PICSAUDE_DEMO_MODE=true` (ver
`app/main.py`). Em modo normal, esses endpoints retornam 404.

POST /demo/login   — seletor de papel, devolve apenas access token (KISS §3.7.1)
GET  /demo/info    — listagem de personas + reset horário previsto

§3.3 TICKET-6 — personas canônicas (identificadores fixos, sintéticos):
  - Prescritor:  CNS  980001112223334  Dra. Demo Maria Souza
  - Dispensador: CNPJ 99999999000191   Farmácia Demo Central
  - Paciente:    CPF  12345678909      João Demo da Silva
  - Admin:       sub  admin-demo       Demo Admin              (somente DEMO_ADMIN=true)

JWT emitido tem o mesmo formato do JWT real (`sub`, `role`, `nome`,
`tipo: "access"`) — garante que 5C (owner checks) continua funcionando
sem caminho especial.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.jwt import criar_access_token
from app.config import PICSAUDE_DEMO_ADMIN, PICSAUDE_DEMO_MODE

router = APIRouter(prefix="/demo", tags=["demo"])


# ---------------------------------------------------------------------------
# Personas canônicas (§3.3 TICKET-6 com IDs novos — P3#8 CODEX rodada 1)
# ---------------------------------------------------------------------------

_PERSONAS: dict[str, dict] = {
    "prescritor": {
        "role":  "prescritor",
        "sub":   "980001112223334",
        "nome":  "Dra. Demo Maria Souza",
        "identificador_visivel": "CNS 980 0011 1222 3334",
    },
    "dispensador": {
        "role":  "dispensador",
        "sub":   "99999999000191",
        "nome":  "Farmácia Demo Central",
        "identificador_visivel": "CNPJ 99.999.999/0001-91",
    },
    "paciente": {
        "role":  "paciente",   # §3.3 — usa "paciente" (não "cidadao") por
                                #         compatibilidade com routers reais
        "sub":   "12345678909",
        "nome":  "João Demo da Silva",
        "identificador_visivel": "CPF 123.456.789-09",
    },
    "admin": {
        "role":  "admin",
        "sub":   "admin-demo",
        "nome":  "Demo Admin",
        "identificador_visivel": "admin-demo (apenas DEMO_ADMIN=true)",
    },
}


def _papeis_demo_disponiveis() -> list[str]:
    base = ["prescritor", "dispensador", "paciente"]
    if PICSAUDE_DEMO_ADMIN:
        base.append("admin")
    return base


def _proximo_reset_horario() -> str:
    agora = datetime.now(timezone.utc)
    proxima = (agora + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    return proxima.isoformat()


# ---------------------------------------------------------------------------
# Schema de entrada
# ---------------------------------------------------------------------------

class DemoLoginIn(BaseModel):
    role: str

    @field_validator("role")
    @classmethod
    def role_valido(cls, v: str) -> str:
        if v not in _PERSONAS:
            raise ValueError(
                f"role inválido: '{v}'. Aceitos: {sorted(_PERSONAS.keys())}"
            )
        return v


# ---------------------------------------------------------------------------
# POST /demo/login — emite access token para a persona escolhida
# ---------------------------------------------------------------------------

@router.post("/login", status_code=200, summary="Login demo — seletor de papel")
def demo_login(payload: DemoLoginIn) -> dict:
    """
    Emite JWT demo (apenas access token; sem refresh — §3.7.1 KISS).

    Defesa em profundidade: o router só é registrado quando
    PICSAUDE_DEMO_MODE=true (main.py), mas validamos novamente aqui caso
    alguém monte o router fora do gate.
    """
    if not PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=404,
            detail={"codigo": "demo_mode_inativo", "mensagem": "Modo demo indisponível."},
        )

    if payload.role not in _papeis_demo_disponiveis():
        # admin pedido sem DEMO_ADMIN=true → 403 com lista atual.
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "papel_demo_indisponivel",
                "mensagem": (
                    f"Papel '{payload.role}' não está disponível neste demo. "
                    f"Aceitos: {_papeis_demo_disponiveis()}."
                ),
            },
        )

    persona = _PERSONAS[payload.role]
    access_token = criar_access_token(
        sub=persona["sub"], role=persona["role"], nome=persona["nome"],
    )
    return {
        "access_token": access_token,
        "token_type":   "bearer",
        "role":         persona["role"],
        "sub":          persona["sub"],
        "nome":         persona["nome"],
    }


# ---------------------------------------------------------------------------
# GET /demo/info — listagem de personas + reset horário previsto
# ---------------------------------------------------------------------------

@router.get("/info", summary="Personas demo + próximo reset")
def demo_info() -> dict:
    """Lista personas disponíveis no demo atual + timestamp do próximo reset."""
    return {
        "personas": [
            {
                "role":  p["role"],
                "nome":  p["nome"],
                "sub":   p["sub"],
                "identificador_visivel": p["identificador_visivel"],
            }
            for papel, p in _PERSONAS.items()
            if papel in _papeis_demo_disponiveis()
        ],
        "proximo_reset": _proximo_reset_horario(),
    }
