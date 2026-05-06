from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class SolicitacaoRenovacao(Base):
    """
    Solicitação de renovação de prescrição feita pelo paciente ao prescritor.

    Status possíveis:
        pendente   — enviada, aguardando resposta do prescritor
        atendida   — prescritor emitiu nova prescrição (referência em nova_prescricao_protocolo)
        recusada   — prescritor recusou com justificativa
        cancelada  — paciente cancelou antes de resposta
    """

    __tablename__ = "solicitacoes_renovacao"

    id                       = Column(Integer, primary_key=True, autoincrement=True)
    protocolo_prescricao     = Column(String(50), nullable=False, index=True)
    prescricao_id            = Column(Integer, ForeignKey("prescricoes.id"), nullable=True)
    cpf_paciente             = Column(String(11), nullable=False, index=True)
    cns_prescritor           = Column(String(15), nullable=False, index=True)
    status                   = Column(String(20), nullable=False, default="pendente")
    motivo                   = Column(Text, nullable=True)
    criado_em                = Column(DateTime, server_default=func.now(), nullable=False)
    respondido_em            = Column(DateTime, nullable=True)
    respondido_por           = Column(String(15), nullable=True)   # CNS do prescritor
    observacao_resposta      = Column(Text, nullable=True)
    nova_prescricao_protocolo = Column(String(50), nullable=True)  # preenchido se atendida
