from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Atestado(Base):
    """
    Atestado médico emitido pelo prescritor — objeto sanitário MONOLÍTICO
    (um documento único, sem itens).

    Status possíveis (ver domain/states_atestado.py):
        emitido · assinado · cancelado · expirado · encerrada_localmente

    tipo_emissao:
        nova | correcao | fisica
    """

    __tablename__ = "atestados"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    protocolo             = Column(String(50), unique=True, nullable=False, index=True)
    prescritor_id         = Column(Integer, ForeignKey("prescritores.id"), nullable=True)
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    status                = Column(String(30), nullable=False, default="emitido")
    tipo_emissao          = Column(String(20), nullable=False, default="nova")
    origem_atestado_id    = Column(Integer, ForeignKey("atestados.id"), nullable=True)
    finalidade            = Column(String(120), nullable=False)   # obrigatória
    indicacao_clinica     = Column(Text, nullable=True)           # opcional (privacidade)
    codigo_cid            = Column(String(10), nullable=True)      # opcional
    dias_afastamento      = Column(Integer, nullable=True)        # opcional (nem todo atestado afasta)
    nome_profissional     = Column(String(200), nullable=True)    # declarado no formulário
    registro_profissional = Column(String(60), nullable=True)     # CRM/registro declarado
    assinatura_modo       = Column(String(40), nullable=True)     # icp_brasil_local | gov_br_nuvem | NULL
    assinatura_hash       = Column(String(64), nullable=True)     # SHA-256 do documento canônico
    data_documento        = Column(String(10), nullable=False)    # ISO 8601 date
    data_emissao          = Column(String(10), nullable=False)    # ISO 8601 date
    data_validade         = Column(String(10), nullable=True)     # data_documento + dias (se afastamento)
    instance_id           = Column(String(36), nullable=True)
    criado_em             = Column(DateTime, server_default=func.now(), nullable=False)
