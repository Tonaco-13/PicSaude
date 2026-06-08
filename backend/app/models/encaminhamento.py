from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Encaminhamento(Base):
    """
    Encaminhamento clínico entre prescritor de origem e prescritor de destino.

    tipo_agregacao_status = "direto" (ver domain/states_encaminhamento.py)
    """

    __tablename__ = "encaminhamentos"

    id                         = Column(Integer, primary_key=True, autoincrement=True)
    protocolo                  = Column(String(50), unique=True, nullable=False, index=True)
    prescritor_id              = Column(Integer, ForeignKey("prescritores.id"), nullable=True)
    paciente_id                = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    cns_destino                = Column(String(20), nullable=False)
    especialidade_destino      = Column(String(200), nullable=False)
    cid                        = Column(String(20), nullable=True)
    justificativa_clinica      = Column(Text, nullable=False)
    status                     = Column(String(30), nullable=False, default="emitido")
    tipo_emissao               = Column(String(20), nullable=False, default="novo")
    origem_encaminhamento_id   = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=True)
    assinatura_hash            = Column(String(64), nullable=True)
    data_emissao               = Column(String(10), nullable=False)
    data_validade              = Column(String(10), nullable=False)
    criado_em                  = Column(DateTime, server_default=func.now(), nullable=False)
