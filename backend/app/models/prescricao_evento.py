from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PrescricaoEvento(Base):
    __tablename__ = "prescricao_eventos"

    id = Column(Integer, primary_key=True, index=True)
    prescricao_id = Column(Integer, ForeignKey("prescricoes.id"), nullable=False)
    tipo_evento = Column(String, nullable=False)
    ator_tipo = Column(String, nullable=False)
    ator_id = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    prescricao = relationship("Prescricao", back_populates="eventos")
