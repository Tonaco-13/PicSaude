from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Prescritor(Base):
    __tablename__ = "prescritores"

    id = Column(Integer, primary_key=True, index=True)
    cns = Column(String, unique=True, index=True, nullable=False)
    nome = Column(String, nullable=False)
    telefone_vinculado = Column(String, nullable=True)
    email = Column(String, nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prescricoes = relationship("Prescricao", back_populates="prescritor")
