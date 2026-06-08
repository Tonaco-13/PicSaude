from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class EncaminhamentoCustodia(Base):
    """
    Cadeia de custódia do encaminhamento.

    Granularidade:
        item_id = NULL  → custódia do encaminhamento inteiro
        item_id = X     → custódia de item específico
    """

    __tablename__ = "encaminhamento_custodia"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    encaminhamento_id   = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=False, index=True)
    item_id             = Column(Integer, ForeignKey("encaminhamento_itens.id"), nullable=True)
    detentor_tipo       = Column(String(40), nullable=False)
    detentor_id         = Column(String(100), nullable=False)
    transferida_em      = Column(String(40), nullable=False)
    encerrada_em        = Column(String(40), nullable=True)
    motivo              = Column(String(120), nullable=True)
    created_at          = Column(DateTime, server_default=func.now(), nullable=False)
