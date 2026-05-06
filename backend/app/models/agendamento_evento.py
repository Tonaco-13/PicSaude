from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AgendamentoEvento(Base):
    """
    Ledger imutável de eventos do agendamento.

    Regra: nunca recebe UPDATE nem DELETE.
    Todo evento de negócio relevante gera um INSERT nesta tabela.
    """

    __tablename__ = "agendamento_eventos"

    id              = Column(Integer, primary_key=True, index=True)
    agendamento_id  = Column(Integer, ForeignKey("agendamentos.id"), nullable=False, index=True)
    evento          = Column(Text, nullable=False)
    payload         = Column(Text, nullable=True)   # JSON livre por evento
    criado_em       = Column(Text, nullable=False)

    agendamento = relationship("Agendamento")
