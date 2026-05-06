from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class LaudoItem(Base):
    """
    Item individual de um laudo clínico.

    status_item possíveis (ver domain/states_laudo.py):
        em_producao · concluido · cancelado · encerrado_fisico

    conclusao:
        normal | alterado | indeterminado | inconclusivo
    """

    __tablename__ = "laudo_itens"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    laudo_id          = Column(Integer, ForeignKey("laudos.id"), nullable=False, index=True)
    nome_exame        = Column(String(200), nullable=False)
    codigo_tuss       = Column(String(20), nullable=True)
    resultado_resumo  = Column(Text, nullable=True)
    conclusao         = Column(String(30), nullable=True)   # normal|alterado|indeterminado|inconclusivo
    valor_referencia  = Column(Text, nullable=True)
    resultado_url     = Column(Text, nullable=True)
    status_item       = Column(String(30), nullable=False, default="em_producao")
    criado_em         = Column(DateTime, server_default=func.now(), nullable=False)
