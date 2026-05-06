from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id             = Column(Integer, primary_key=True, index=True)
    role           = Column(String, nullable=False)          # prescritor|dispensador|auditor|admin
    identificador  = Column(String, unique=True, nullable=False, index=True)
    # identificador:
    #   prescritor  → CNS (15 dígitos normalizados)
    #   dispensador → CNPJ (14 dígitos normalizados)
    #   auditor     → email
    #   admin       → email
    nome           = Column(String, nullable=False)
    senha_hash     = Column(String, nullable=False)
    ativo          = Column(Boolean, default=True, nullable=False)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
