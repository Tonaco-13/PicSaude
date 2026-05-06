from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PedidoExameCustodia(Base):
    """
    Cadeia de custódia do pedido de exame.

    Granularidade:
        item_id = NULL  → custódia do pedido inteiro
        item_id = X     → custódia de item específico

    Transições permitidas:
        prescritor      → paciente           (emissão digital)
        paciente        → prestador_exame    (agendamento/apresentação)
        prestador_exame → paciente           (laudo disponível)

    REGRA: sem registros para fluxo físico (encerrado_fisico).
    """

    __tablename__ = "pedido_exame_custodia"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id       = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    item_id         = Column(Integer, ForeignKey("pedido_exame_itens.id"), nullable=True)
    de              = Column(String(100), nullable=False)    # papel ou CNPJ
    para            = Column(String(100), nullable=False)
    transferido_em  = Column(DateTime, server_default=func.now(), nullable=False)
    dados_json      = Column(Text, nullable=True)
