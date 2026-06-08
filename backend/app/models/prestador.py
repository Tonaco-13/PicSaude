"""
models/prestador.py
===================
Identidade formal de um prestador de serviços de saúde (Ticket 30).

Um Prestador corresponde a uma organização real (clínica, hospital,
laboratório, farmácia). Seu org_id é o identificador global usado
nas tabelas operacionais (agendamentos, dispensacoes_hospitalares, etc.)

Regras:
  - org_id é UNIQUE e imutável após criação.
  - cnpj é opcional no MVP (integração CNES é ticket futuro).
  - Deleção lógica via campo ativo — nunca DELETE físico.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Text

from app.database import Base

# Subconjuntos nomeados por domínio operacional (Ticket 60 — R2)
_TIPOS_DISPENSADOR = frozenset({"farmacia", "hospital", "usf"})
_TIPOS_LABORATORIO = frozenset({"laboratorio"})
_TIPOS_VALIDOS     = _TIPOS_DISPENSADOR | _TIPOS_LABORATORIO | {"clinica"}


class Prestador(Base):
    __tablename__ = "prestadores"

    id         = Column(Text, primary_key=True)       # UUID gerado na criação
    org_id     = Column(Text, nullable=False, unique=True)
    nome       = Column(Text, nullable=False)
    tipo       = Column(Text, nullable=False)          # dispensador: farmacia|hospital|usf  /  laboratorio  /  clinica
    cnpj       = Column(Text, nullable=True)
    ativo      = Column(Boolean, nullable=False, default=True)   # C.1: Boolean (código usa ativo=true)
    criado_em  = Column(Text, nullable=False)
