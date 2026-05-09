from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text
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
    # NOVO (4C): marca d'água da instância PicSaúde — preenchida pelo
    # helper registrar_evento_ledger via get_instance_id_conn().
    # Nullable=True alinhado com a migration 4B (4b1ce80a017d).
    instance_id     = Column(String(36), nullable=True)

    agendamento = relationship("Agendamento")
