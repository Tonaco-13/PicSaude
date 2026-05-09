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
    # NOVO (4C): marca d'água da instância PicSaúde — preenchida pelo
    # helper registrar_evento_ledger via get_instance_id_conn().
    # Nullable=True alinhado com a migration 4B (4b1ce80a017d).
    instance_id = Column(String(36), nullable=True)

    prescricao = relationship("Prescricao", back_populates="eventos")
