"""
receituario.py
==============
Models ORM — Ticket 15 — Receituários regulatórios derivados de uma prescrição.

Contexto
--------
Uma única prescrição clínica pode exigir múltiplos receituários
regulatórios distintos (amarela, azul, branca, simples…). Este módulo
define o agregado persistente:

  receituarios           — um por (prescrição × tipo de receituário)
  receituario_itens      — tabela de associação (receituário ↔ item da prescrição)

A lógica de agrupamento (classe → grupo → tipo) vive em
`app/domain/motor_regulatorio.py`. A persistência é feita pelo endpoint
`POST /prescricoes/{protocolo}/receituarios/gerar` em
`app/routers/receituarios.py`.

Ciclo de vida de um receituário:
  gerado → numerado (Ticket 16) → emitido (Ticket 17)
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Receituario(Base):
    """Receituário regulatório derivado de uma prescrição (Ticket 15)."""

    __tablename__ = "receituarios"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Prescrição clínica de origem (um-para-muitos: 1 prescrição → N receituários).
    prescricao_id = Column(
        Integer,
        ForeignKey("prescricoes.id"),
        nullable=False,
        index=True,
    )

    tipo_receituario = Column(String(50), nullable=False)   # ex: "notificacao_receita_a"
    grupo_id         = Column(String(50), nullable=False)   # ex: "notificacao_receita_a"
    grupo_nome       = Column(String(100), nullable=False)  # ex: "Notificação de Receita A (Amarela)"

    # Regra regulatória aplicada
    assinatura_minima  = Column(String(20), nullable=False)    # "qualificada"|"avancada"|"nenhuma"
    assinatura_valida  = Column(Boolean, nullable=False, default=False)
    vias               = Column(Integer, nullable=False)
    retencao_farmacia  = Column(Boolean, nullable=False, default=False)
    requer_sncr        = Column(Boolean, nullable=False, default=False)

    # Preenchido no Ticket 16 (integração SNCR).
    numeracao_sncr = Column(String(50), nullable=True)

    # Ciclo de vida — ver app/adapters/sncr_interface.py para racional:
    #   "gerado"             → criado pelo motor regulatório
    #   "nao_requer_sncr"    → receita simples/comum, não passa pelo SNCR
    #   "numerado_stub"      → numeração obtida via SNCRStub (dev/teste)
    #   "numerado"           → numeração real obtida do SNCR (Ticket 16B)
    #   "emitido"            → assinado e disponibilizado ao paciente
    #   "dispensado"         → registro de utilização feito pela farmácia
    #   "expirado"           → prazo ultrapassado sem dispensação
    #   "cancelado"          → cancelado por correção/erro
    status = Column(String(30), nullable=False, default="gerado")

    # Ticket 16A — timestamps do ciclo de vida pós-numeração
    numerado_em = Column(DateTime, nullable=True)
    emitido_em  = Column(DateTime, nullable=True)
    # Identifica qual implementação do SNCRAdapter gerou a numeração ("stub"
    # ou "real"). Rastreabilidade — qualquer auditoria deve poder distinguir.
    adapter_usado = Column(String(20), nullable=True)

    # Ticket 19 — Validade do receituário (se aplicável)
    data_validade = Column(DateTime, nullable=True)

    # Soft-delete para regeneração idempotente (veja endpoint gerar).
    # NULL = ativo. DateTime = momento de substituição por nova geração.
    substituido_em = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Não declaramos back_populates com Prescricao para não alterar o model
    # existente (salvaguarda do Ticket 15). A navegação fica unilateral.
    prescricao = relationship("Prescricao", foreign_keys=[prescricao_id])
    itens = relationship(
        "ReceituarioItem",
        back_populates="receituario",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "prescricao_id",
            "tipo_receituario",
            "substituido_em",
            name="uq_receituario_prescricao_tipo_ativo",
        ),
    )


class ReceituarioItem(Base):
    """Item de prescrição pertencente a um receituário."""

    __tablename__ = "receituario_itens"

    id = Column(Integer, primary_key=True, autoincrement=True)

    receituario_id = Column(
        Integer,
        ForeignKey("receituarios.id"),
        nullable=False,
        index=True,
    )
    prescricao_item_id = Column(
        Integer,
        ForeignKey("prescricao_itens.id"),
        nullable=False,
        index=True,
    )

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    receituario = relationship("Receituario", back_populates="itens")
    # Sem back_populates em PrescricaoItem — não alteramos o model existente.
    prescricao_item = relationship("PrescricaoItem", foreign_keys=[prescricao_item_id])

    __table_args__ = (
        UniqueConstraint(
            "receituario_id",
            "prescricao_item_id",
            name="uq_receituario_item_par",
        ),
    )
