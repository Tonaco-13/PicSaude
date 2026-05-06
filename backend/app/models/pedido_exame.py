from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PedidoExame(Base):
    """
    Pedido de exame emitido pelo prescritor.

    Status possíveis (ver domain/states_exame.py):
        emitido · agendado · coletado · em_analise
        resultado_disponivel · encerrado · cancelado · expirado · encerrado_fisico

    tipo_emissao:
        novo | correcao | renovacao

    prioridade:
        rotina | urgente | urgentissimo
    """

    __tablename__ = "pedidos_exame"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    protocolo           = Column(String(50), unique=True, nullable=False, index=True)
    prescritor_id       = Column(Integer, ForeignKey("prescritores.id"), nullable=True)
    paciente_id         = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    status              = Column(String(30), nullable=False, default="emitido")
    tipo_emissao        = Column(String(20), nullable=False, default="novo")
    origem_pedido_id    = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=True)
    prioridade          = Column(String(20), nullable=False, default="rotina")
    indicacao_clinica   = Column(Text, nullable=True)
    data_emissao        = Column(String(10), nullable=False)   # ISO 8601 date
    data_validade       = Column(String(10), nullable=False)   # ISO 8601 date
    assinatura_hash     = Column(String(64), nullable=True)    # SHA-256 do documento canônico
    criado_em           = Column(DateTime, server_default=func.now(), nullable=False)
