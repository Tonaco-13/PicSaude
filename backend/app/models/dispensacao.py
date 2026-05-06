from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Dispensacao(Base):
    """
    Registro de dispensação de um item da prescrição.

    Suporta dispensação parcial: quantidade_dispensada pode ser menor
    que prescricao_itens.quantidade. Nesse caso, múltiplos registros
    podem existir para o mesmo item (fracionamento ou retomada de compra).

    A soma de quantidade_dispensada de todos os registros de um item
    deve ser <= prescricao_itens.quantidade.
    """

    __tablename__ = "dispensacoes"

    id                    = Column(Integer, primary_key=True, index=True)
    prescricao_item_id    = Column(Integer, ForeignKey("prescricao_itens.id"), nullable=False, index=True)
    cnpj_estabelecimento  = Column(String, nullable=False, index=True)  # CNPJ normalizado (14 dígitos)
    quantidade_dispensada = Column(Integer, nullable=False)
    dispensado_por        = Column(String, nullable=True)   # nome/CRF do farmacêutico
    dispensado_em         = Column(DateTime, default=datetime.utcnow, nullable=False)
    lote                  = Column(String(50), nullable=True)
    fabricante            = Column(String, nullable=True)
    observacao            = Column(Text, nullable=True)
    origem_contexto       = Column(String(30), nullable=True)   # 'cnes_verificado' | 'manual' | NULL (legado)
    created_at            = Column(DateTime, default=datetime.utcnow, nullable=False)

    item = relationship("PrescricaoItem")
