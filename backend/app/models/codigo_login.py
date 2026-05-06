from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.database import Base


class CodigoLogin(Base):
    __tablename__ = "codigos_login"

    id        = Column(Integer, primary_key=True, index=True)
    cpf       = Column(String, nullable=False, index=True)
    codigo    = Column(String, nullable=False)
    expiracao = Column(DateTime, nullable=False)
    usado     = Column(Integer, nullable=False, default=0)   # 0=pendente, 1=usado
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
