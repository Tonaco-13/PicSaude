from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class ContrarreferenciaEvento(Base):
    """Ledger imutável da Contrarreferência (INSERT-only — NUCLEO §2/§5)."""

    __tablename__ = "contrarreferencia_eventos"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    contrarreferencia_id = Column(Integer, ForeignKey("contrarreferencias.id"), nullable=False, index=True)
    tipo_evento         = Column(String(80), nullable=False)
    ator_tipo           = Column(String(40), nullable=False)
    ator_id             = Column(String(100), nullable=True)
    payload             = Column(Text, nullable=True)
    instance_id         = Column(String(36), nullable=True)
    created_at          = Column(DateTime, server_default=func.now(), nullable=False)
