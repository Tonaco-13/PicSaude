from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class PrescricaoCustodia(Base):
    """
    Cadeia de custódia sanitária digital.

    Cada linha representa a abertura de uma custódia. A custódia ativa
    é aquela com encerrada_em = NULL.

    Regras de negócio:
    - Ao transferir a custódia, encerra_em é preenchido na linha anterior
      e uma nova linha é aberta para o novo detentor.
    - detentor_tipo: 'paciente' | 'dispensador' | 'prescritor'
    - detentor_id:   CPF (paciente), CNPJ (dispensador) ou CNS (prescritor)
      — sempre normalizado (só dígitos).

    Granularidade:
    - item_id = NULL  → custódia da PRESCRIÇÃO inteira
    - item_id != NULL → custódia de um ITEM específico (dispensação granular)
    """

    __tablename__ = "prescricao_custodia"

    id             = Column(Integer, primary_key=True, index=True)
    prescricao_id  = Column(Integer, ForeignKey("prescricoes.id"), nullable=False, index=True)
    item_id        = Column(Integer, ForeignKey("prescricao_itens.id"), nullable=True, index=True)
    detentor_tipo  = Column(String, nullable=False)   # paciente | dispensador | prescritor
    detentor_id    = Column(String, nullable=False)   # CPF / CNPJ / CNS (só dígitos)
    transferida_em = Column(DateTime, default=datetime.utcnow, nullable=False)
    encerrada_em   = Column(DateTime, nullable=True)  # NULL = custódia ativa
    motivo         = Column(String, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Contexto operacional — Ticket 27 (Farmácia Hospitalar MVP)
    # NULL = ambulatorial (comportamento padrão, compatível com todos os registros existentes)
    # 'hospitalar' = farmácia hospitalar (paciente não é detentor intermediário)
    contexto_operacional = Column(String, nullable=True)
    unidade_id           = Column(String, nullable=True)

    prescricao = relationship("Prescricao")
