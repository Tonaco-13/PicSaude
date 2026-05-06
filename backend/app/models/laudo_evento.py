from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class LaudoEvento(Base):
    """
    Ledger imutável de eventos do laudo.

    REGRA: nunca recebe UPDATE nem DELETE.
    Vocabulário de tipo_evento: ver EVENTOS_LAUDO em domain/states_laudo.py
    """

    __tablename__ = "laudo_eventos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    laudo_id    = Column(Integer, ForeignKey("laudos.id"), nullable=False, index=True)
    tipo_evento = Column(String(60), nullable=False)
    dados_json  = Column(Text, nullable=True)
    criado_em   = Column(DateTime, server_default=func.now(), nullable=False)
