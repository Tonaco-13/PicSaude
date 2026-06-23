from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class AtestadoCustodia(Base):
    """
    Cadeia de custódia do atestado (objeto monolítico — sem item_id).

    Transição permitida:
        prescritor → paciente   (emissão digital)

    REGRA: sem registros para fluxo físico (encerrada_localmente).
    """

    __tablename__ = "atestado_custodia"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    atestado_id    = Column(Integer, ForeignKey("atestados.id"), nullable=False, index=True)
    de             = Column(String(100), nullable=False)    # papel ou CNS/CPF
    para           = Column(String(100), nullable=False)
    transferido_em = Column(DateTime, server_default=func.now(), nullable=False)
    dados_json     = Column(Text, nullable=True)
