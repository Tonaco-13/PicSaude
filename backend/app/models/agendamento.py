from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Agendamento(Base):
    """
    Objeto sanitário leve que representa o compromisso de execução de um
    pedido de exame entre paciente e prestador.

    Não tem custódia (compromisso bilateral).
    Não tem assinatura/hash (não é documento clínico — exceção documentada).
    org_id e unidade_id são obrigatórios (agendamento é sempre institucional).

    Remarcação cria novo Agendamento com origem_agendamento_id preenchido;
    o anterior recebe status 'cancelado'.
    """

    __tablename__ = "agendamentos"

    id                    = Column(Integer, primary_key=True, index=True)
    protocolo             = Column(String, unique=True, nullable=False, index=True)

    pedido_id             = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)

    # Contexto institucional — obrigatório em agendamentos
    org_id                = Column(Text, nullable=False, index=True)
    unidade_id            = Column(Text, nullable=False, index=True)

    tipo_agendamento      = Column(String(30), nullable=False, default="exame")
    data_hora             = Column(Text, nullable=False)        # ISO 8601 datetime
    local_texto           = Column(Text, nullable=True)
    observacao            = Column(Text, nullable=True)

    status                = Column(String(30), nullable=False, default="criado")
    tipo_emissao          = Column(String(20), nullable=False, default="novo")   # novo | remarcacao
    origem_agendamento_id = Column(Integer, ForeignKey("agendamentos.id"), nullable=True)

    criado_por            = Column(Text, nullable=False)   # CNS prescritor ou CPF paciente
    criado_em             = Column(Text, nullable=False)

    pedido    = relationship("PedidoExame")
    paciente  = relationship("Paciente")
