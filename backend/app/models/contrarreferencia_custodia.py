from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class ContrarreferenciaCustodia(Base):
    """Cadeia de custódia da Contrarreferência (NUCLEO §4). Sem itens no MVP."""

    __tablename__ = "contrarreferencia_custodia"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    contrarreferencia_id = Column(Integer, ForeignKey("contrarreferencias.id"), nullable=False, index=True)
    item_id             = Column(Integer, nullable=True)   # sempre NULL no MVP (sem itens)
    detentor_tipo       = Column(String(40), nullable=False)
    detentor_id         = Column(String(100), nullable=False)
    transferida_em      = Column(String(40), nullable=False)
    encerrada_em        = Column(String(40), nullable=True)
    motivo              = Column(String(120), nullable=True)
    created_at          = Column(DateTime, server_default=func.now(), nullable=False)
