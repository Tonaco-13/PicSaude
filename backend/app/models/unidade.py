"""
models/unidade.py
=================
Unidade operacional de um prestador (Ticket 30).

Uma Unidade é um local físico ou setor dentro de um prestador
(ex: Laboratório Central, UTI, Farmácia Hospitalar).

Regras:
  - unidade_id é UNIQUE dentro do mesmo prestador.
  - Mesma unidade_id em prestadores diferentes: permitido.
  - Deleção lógica via campo ativo — nunca DELETE físico.
  - prestador_id referencia prestadores(id).
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Text, UniqueConstraint

from app.database import Base

_TIPOS_VALIDOS = ("ambulatorio", "enfermaria", "laboratorio", "farmacia", "administrativo", "usf")


class Unidade(Base):
    __tablename__ = "unidades"
    __table_args__ = (
        UniqueConstraint("prestador_id", "unidade_id", name="uq_prestador_unidade"),
    )

    id           = Column(Text, primary_key=True)
    prestador_id = Column(Text, ForeignKey("prestadores.id"), nullable=False)
    unidade_id   = Column(Text, nullable=False)
    nome         = Column(Text, nullable=False)
    tipo         = Column(Text, nullable=True)    # ambulatorio|enfermaria|laboratorio|farmacia|administrativo|usf
    ativo        = Column(Boolean, nullable=False, default=True)   # C.1: Boolean (código usa ativo=true)
    criado_em    = Column(Text, nullable=False)
