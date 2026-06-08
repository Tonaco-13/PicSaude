from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class EncaminhamentoEvento(Base):
    """
    Ledger imutável de eventos do encaminhamento.

    REGRA: nunca recebe UPDATE nem DELETE.
    """

    __tablename__ = "encaminhamento_eventos"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    encaminhamento_id   = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=False, index=True)
    tipo_evento         = Column(String(80), nullable=False)
    ator_tipo           = Column(String(40), nullable=False)
    ator_id             = Column(String(100), nullable=True)
    payload             = Column(Text, nullable=True)
    instance_id         = Column(String(36), nullable=True)
    created_at          = Column(DateTime, server_default=func.now(), nullable=False)
