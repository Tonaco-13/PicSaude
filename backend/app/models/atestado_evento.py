from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class AtestadoEvento(Base):
    """
    Ledger imutável de eventos do atestado.

    REGRA: nunca recebe UPDATE nem DELETE.
    Todo evento relevante deve gerar um INSERT nesta tabela.

    Vocabulário de tipo_evento: ver EVENTOS_ATESTADO em domain/states_atestado.py.
    O atestado tem ator explícito (prescritor) — tem_ator=True no _LEDGER_SCHEMA.
    """

    __tablename__ = "atestado_eventos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    atestado_id = Column(Integer, ForeignKey("atestados.id"), nullable=False, index=True)
    tipo_evento = Column(String(60), nullable=False)
    ator_tipo   = Column(String(40), nullable=True)
    ator_id     = Column(String(100), nullable=True)
    payload     = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now(), nullable=False)
    instance_id = Column(String(36), nullable=True)
