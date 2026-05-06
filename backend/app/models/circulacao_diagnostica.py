from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CirculacaoDiagnostica(Base):
    """
    Objeto sanitário que representa a circulação operacional de um subconjunto
    de itens de um pedido de exame entre paciente e laboratório.

    Antecede o agendamento concreto: o paciente seleciona itens, gera uma chave
    de circulação e a apresenta ao laboratório, que pode propor data/hora/preparo.
    A confirmação do paciente encerra o ciclo de negociação.

    Não tem custódia (sem transferência de posse física entre atores).
    Não tem assinatura/hash (não é documento clínico autônomo).
    org_id e unidade_id referem-se ao laboratório destinatário (obrigatórios).

    Remarcação cria nova CirculacaoDiagnostica com origem_circulacao_id
    preenchido; a anterior é encerrada em desmarcado_paciente ou
    desmarcado_laboratorio.

    Referência arquitetural: docs/ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md
    Estados: domain/states_circulacao_diagnostica.py
    """

    __tablename__ = "circulacoes_diagnosticas"

    id                    = Column(Integer, primary_key=True, index=True)
    protocolo             = Column(String, unique=True, nullable=False, index=True)   # UUID
    chave_circulacao      = Column(String, unique=True, nullable=False, index=True)   # chave apresentada ao laboratório

    pedido_id             = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)

    # Laboratório destinatário — contexto institucional obrigatório
    org_id                = Column(Text, nullable=False, index=True)
    unidade_id            = Column(Text, nullable=False, index=True)

    # Proposta do laboratório — preenchidos em proposta_recebida
    data_hora_proposta    = Column(Text, nullable=True)    # ISO 8601 datetime
    local_texto           = Column(Text, nullable=True)
    instrucoes_preparo    = Column(Text, nullable=True)

    observacao            = Column(Text, nullable=True)

    status                = Column(String(30), nullable=False, default="selecionado")
    tipo_emissao          = Column(String(20), nullable=False, default="novo")   # novo | remarcacao
    origem_circulacao_id  = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=True)

    validade              = Column(Text, nullable=False)   # ISO 8601 datetime — expiração da chave

    criado_por            = Column(Text, nullable=False)   # CPF do paciente
    criado_em             = Column(Text, nullable=False)   # ISO 8601 datetime

    pedido   = relationship("PedidoExame")
    paciente = relationship("Paciente")
