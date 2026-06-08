from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class EncaminhamentoItem(Base):
    """
    Item do encaminhamento.

    No E1 o status do objeto é agregado diretamente; itens registram o alvo
    assistencial e acompanham o estado operacional mínimo.
    """

    __tablename__ = "encaminhamento_itens"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    encaminhamento_id   = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=False, index=True)
    especialidade       = Column(String(200), nullable=False)
    procedimento        = Column(String(200), nullable=True)
    motivo              = Column(Text, nullable=True)
    status_item         = Column(String(30), nullable=False, default="pendente")
    criado_em           = Column(DateTime, server_default=func.now(), nullable=False)
