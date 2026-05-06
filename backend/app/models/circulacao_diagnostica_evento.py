from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CirculacaoDiagnosticaEvento(Base):
    """
    Ledger imutável de eventos da circulação diagnóstica.

    REGRA: nunca recebe UPDATE nem DELETE.
    Todo evento de negócio relevante deve gerar um INSERT nesta tabela.

    Vocabulário de tipo_evento: ver EVENTOS_CIRCULACAO_DIAGNOSTICA
    em domain/states_circulacao_diagnostica.py
    """

    __tablename__ = "circulacao_diagnostica_eventos"

    id             = Column(Integer, primary_key=True, index=True)
    circulacao_id  = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=False, index=True)
    tipo_evento    = Column(Text, nullable=False)
    dados_json     = Column(Text, nullable=True)    # JSON livre por evento
    criado_em      = Column(Text, nullable=False)   # ISO 8601 datetime

    circulacao = relationship("CirculacaoDiagnostica")
