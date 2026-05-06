"""
dispensacao_hospitalar.py
=========================
Extensão operacional da dispensação para o contexto hospitalar.

Princípio (Ticket 26/27): a dispensação hospitalar NÃO substitui a
dispensação ambulatorial — é uma extensão contextual. O registro base
vai para `dispensacoes` (mesma auditoria, mesma constraint de quantidade);
o contexto hospitalar (unidade, leito, dose unitária) vai para esta tabela.

Campos obrigatórios: org_id e unidade_id (escopo institucional explícito,
conforme diretriz §6b do CLAUDE.md).

Campos opcionais: setor, leito, dose_unitaria, quantidade_doses.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, ForeignKey, Integer, Text

from app.database import Base


class DispensacaoHospitalar(Base):
    """
    Contexto hospitalar de uma dispensação registrada em `dispensacoes`.

    Cada linha desta tabela aponta para um registro de `dispensacoes` via
    `dispensacao_id` (vínculo ao registro base) e para o item específico
    via `prescricao_item_id` (redundante, mas útil para queries hospitalares
    sem precisar de join triplo).

    Invariante: a constraint de quantidade é verificada no registro base
    (`dispensacoes.quantidade_dispensada`). Esta tabela nunca replica essa
    lógica — registra apenas o contexto operacional.
    """

    __tablename__ = "dispensacoes_hospitalares"

    id                 = Column(Integer, primary_key=True, autoincrement=True)

    # Vínculo ao registro base (dispensacoes)
    dispensacao_id     = Column(Integer, ForeignKey("dispensacoes.id"), nullable=False, index=True)

    # Referências diretas para queries hospitalares sem join triplo
    prescricao_item_id = Column(Integer, ForeignKey("prescricao_itens.id"), nullable=False, index=True)
    protocolo          = Column(Text, nullable=False, index=True)

    # Escopo institucional — obrigatório para contexto hospitalar (§6b CLAUDE.md)
    org_id             = Column(Text, nullable=False, index=True)
    unidade_id         = Column(Text, nullable=False, index=True)

    # Destino assistencial — contexto operacional
    setor              = Column(Text, nullable=True)   # UTI, Clínica Médica, etc.
    leito              = Column(Text, nullable=True)   # identificador do leito

    # Modalidade de dispensação
    modalidade         = Column(Text, nullable=False, default="internacao")
    # internacao | urgencia_emergencia | cirurgia

    # Dose unitária: True = dispensado em doses individuais
    dose_unitaria      = Column(Boolean, nullable=False, default=False)
    quantidade_doses   = Column(Integer, nullable=True)  # relevante quando dose_unitaria = True

    # Quem dispensou (farmacêutico hospitalar)
    dispensado_por     = Column(Text, nullable=False)
    dispensado_em      = Column(Text, nullable=False)   # ISO 8601
    criado_em          = Column(Text, nullable=False)   # ISO 8601
