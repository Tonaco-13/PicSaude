from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class LaudoCustodia(Base):
    """
    Cadeia de custódia do laudo.

    Transições permitidas:
        prestador_exame → paciente          (liberação do laudo)
        prestador_exame → prescritor        (retorno clínico direto)
        paciente        → prescritor        (encaminhamento para consulta)

    REGRA: sem registros para fluxo físico (encerrado_fisico).
    Custódia do LAUDO começa no prestador — diferente de prescrição e exame.
    """

    __tablename__ = "laudo_custodia"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    laudo_id        = Column(Integer, ForeignKey("laudos.id"), nullable=False, index=True)
    item_id         = Column(Integer, ForeignKey("laudo_itens.id"), nullable=True)
    de              = Column(String(100), nullable=False)
    para            = Column(String(100), nullable=False)
    transferido_em  = Column(DateTime, server_default=func.now(), nullable=False)
    dados_json      = Column(Text, nullable=True)
