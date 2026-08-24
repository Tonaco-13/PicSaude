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
    # ENG-016 §5 — finalidade ESTRUTURADA (migração `b3e7d21a90c4`).
    # Nullable porque encaminhamento emitido antes dela não a tem e não pode
    # ganhá-la: objeto sanitário emitido é imutável (§1). O modelo acompanha a
    # migração porque a fixture SQLite dos testes monta o schema por
    # `create_all` — migração é a autoridade (§9), mas o modelo não pode
    # divergir dela, senão o dialeto de desenvolvimento fica com outro schema.
    finalidade                 = Column(String(60), nullable=True)
    finalidade_texto           = Column(String(200), nullable=True)
    status                     = Column(String(30), nullable=False, default="emitido")
    tipo_emissao               = Column(String(20), nullable=False, default="novo")
    origem_encaminhamento_id   = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=True)
    assinatura_hash            = Column(String(64), nullable=True)
    data_emissao               = Column(String(10), nullable=False)
    data_validade              = Column(String(10), nullable=False)
    criado_em                  = Column(DateTime, server_default=func.now(), nullable=False)
