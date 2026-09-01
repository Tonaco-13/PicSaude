"""
lista_espera.py (router) — POST /lista-espera

Despacho "Lista de espera direta" (`module`): endpoint público, sem
autenticação, para o formulário "em obras" (`entrar.html`) registrar
interesse na plataforma. Sem GET — nunca expõe a lista (enumeração é
vazamento, §5 do despacho). Armazenamento em `app/domain/lista_espera.py`
(base própria, sobrevive ao reset diário — ver o módulo).

Defesas mínimas de superfície pública (§4 do despacho):
  - Validação de campo (nome 2–200, email formato+tamanho) — Pydantic.
  - Honeypot (`empresa`) — campo fora da visão/tab-order na tela; um
    preenchimento automatizado o alcança, uma pessoa não.
  - Rate limit por IP — `app/middleware/rate_limit.py::ROUTE_LIMITS`.
  - Caps — backstop de volume total em `app/domain/lista_espera.py`.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.domain import lista_espera as _store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["lista-espera"])

_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class InscricaoListaEspera(BaseModel):
    nome: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=254)
    origem: str | None = Field(None, max_length=100)
    # Honeypot — nome de campo plausível o bastante para um preenchimento
    # automatizado alcançar; a tela o mantém fora da visão e do tab-order
    # (ver entrar.html). Vazio é o único valor legítimo.
    empresa: str = Field("", max_length=200)

    @field_validator("nome")
    @classmethod
    def _validar_nome(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("nome muito curto")
        return v

    @field_validator("email")
    @classmethod
    def _validar_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _RE_EMAIL.match(v):
            raise ValueError("email em formato inválido")
        return v


@router.post("/lista-espera", status_code=status.HTTP_201_CREATED)
def inscrever_lista_espera(payload: InscricaoListaEspera) -> dict:
    if payload.empresa:
        # Honeypot acionado — resposta IDÊNTICA à de sucesso, sem gravar.
        # Não avisa o robô de que foi pego; só descarta em silêncio.
        logger.info("lista de espera: honeypot acionado, inscrição descartada")
        return {"status": "ok"}

    try:
        _store.registrar_inscricao(payload.nome, payload.email, payload.origem)
    except _store.ListaEspereCheia:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lista de espera temporariamente indisponível. Tente mais tarde.",
        )

    return {"status": "ok"}
