from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PedidoExameEvento(Base):
    """
    Ledger imutável de eventos do pedido de exame.

    REGRA: nunca recebe UPDATE nem DELETE.
    Todo evento relevante deve gerar um INSERT nesta tabela.

    Vocabulário de tipo_evento: ver EVENTOS_PEDIDO_EXAME em domain/states_exame.py
    """

    __tablename__ = "pedido_exame_eventos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id   = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    tipo_evento = Column(String(60), nullable=False)
    dados_json  = Column(Text, nullable=True)
    criado_em   = Column(DateTime, server_default=func.now(), nullable=False)
