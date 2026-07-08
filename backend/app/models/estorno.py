from __future__ import annotations

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func,
)

from app.database import Base


class Estorno(Base):
    """
    Estorno — objeto sanitário DERIVADO e IMUTÁVEL de uma dispensação (T2).

    A reversão de uma dispensação registrada é uma nova asserção clínica (novo
    autor, novo momento) → objeto derivado apontando à dispensação de origem
    (`origem_dispensacao_id`), **não** uma transição de estado que muta o item
    (`dispensado → estornado`). Fiel ao princípio §1 do CLAUDE.md
    (imutabilidade) e ao padrão de derivação (`origem_*_id`) de
    laudo↔pedido_exame e contrarreferência↔encaminhamento.

    Consequências (Opção B — martelo Fabiano, 2026-07-07):
    - A `dispensacoes` original permanece **intocada**.
    - O item permanece `dispensado`; o estado `estornado` de item **não** é usado.
    - O saldo Σ é reposto por cálculo: Σ efetivo = Σ dispensado − Σ estornado.

    Ver `docs/tickets/TICKET-ESTORNO-OBJETO-DERIVADO.md` (mecanismo) e
    `docs/tickets/TICKET-T2-ESTORNO-DISPENSACAO.md` (implementação).
    """

    __tablename__ = "estornos"
    __table_args__ = (
        CheckConstraint(
            "motivo IN ('falha_pagamento', 'desistencia', 'erro_dispensacao', 'outro')",
            name="chk_estorno_motivo",
        ),
    )

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    protocolo             = Column(String(50), unique=True, nullable=False, index=True)
    origem_dispensacao_id = Column(Integer, ForeignKey("dispensacoes.id"), nullable=False, index=True)
    autor_tipo            = Column(String(40), nullable=False)   # 'dispensador' | 'admin'
    autor_id              = Column(String(100), nullable=True)   # CNPJ do dispensador que estorna
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    quantidade_estornada  = Column(Integer, nullable=False)
    motivo                = Column(String(30), nullable=False)   # enum — ver CheckConstraint
    motivo_detalhe        = Column(Text, nullable=True)          # obrigatório quando motivo='outro'
    assinatura_hash       = Column(String(64), nullable=True)
    instance_id           = Column(String(36), nullable=True)
    data_emissao          = Column(String(10), nullable=False)
    criado_em             = Column(DateTime, server_default=func.now(), nullable=False)
