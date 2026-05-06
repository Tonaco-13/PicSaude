from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class PrescricaoItem(Base):
    __tablename__ = "prescricao_itens"

    id = Column(Integer, primary_key=True, index=True)
    prescricao_id = Column(Integer, ForeignKey("prescricoes.id"), nullable=False)
    nome_medicamento = Column(String, nullable=False)
    concentracao = Column(String, nullable=True)
    quantidade = Column(Integer, nullable=True)
    unidade_quantidade = Column(String, nullable=True)   # vocabulário controlado (medicamento.py)
    forma_farmaceutica = Column(String, nullable=True)   # apresentação livre ("1 cx c/ 30 cáps.")
    posologia = Column(Text, nullable=True)
    status_item = Column(String, default="pendente", nullable=False)
    # Ticket 44 — Circulação atomizada
    # Classe regulatória do medicamento. NULL = comum (elegível para atomização).
    # Valores que bloqueiam: A1, A2, A3, B1, B2, C5, D1, D2 (ver domain/medicamento.py)
    classe_controle = Column(String(10), nullable=True)
    # Ticket 18 — Retenção por RDC 471/2021 (independente da Portaria 344).
    # NULL = não sujeito a retenção. Valores: 'antimicrobiano', 'glp1_agonista'.
    # Ver domain/retencao.py.
    tipo_retencao = Column(String(30), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prescricao = relationship("Prescricao", back_populates="itens")
