from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Prescricao(Base):
    __tablename__ = "prescricoes"

    id = Column(Integer, primary_key=True, index=True)
    protocolo = Column(String, unique=True, index=True, nullable=False)
    prescritor_id = Column(Integer, ForeignKey("prescritores.id"), nullable=False)
    paciente_id = Column(Integer, ForeignKey("pacientes.id"), nullable=False)
    status = Column(String, nullable=False)
    assinatura_modo = Column(String, nullable=True)
    assinatura_hash = Column(String, nullable=True)   # SHA-256 do documento canônico
    tipo_emissao = Column(String, nullable=False, default="nova")
    origem_prescricao_id = Column(Integer, ForeignKey("prescricoes.id"), nullable=True)
    # Ticket 36 — Contexto clínico estruturado (opcional, não altera fluxo nem ledger estrutural)
    indicacao_clinica = Column(Text, nullable=True)   # texto livre do prescritor (hipótese diagnóstica)
    codigo_cid = Column(String, nullable=True)        # código CID-10 escolhido via IA CID (ex: "I10")
    # Ticket 67 — String de validação auditável do prescritor (ICP + CNES + Conselho + NomeValidator)
    # Formato: CPF|CONSELHO|CNS|STATUS_NOME|HASH_CERT|TIMESTAMP
    # Gerada no momento da emissão quando cert_pem é fornecido; NULL quando emissão sem ICP.
    string_validacao_prescritor = Column(String(512), nullable=True)
    data_emissao = Column(DateTime, default=datetime.utcnow, nullable=False)
    data_validade = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    prescritor = relationship("Prescritor", back_populates="prescricoes")
    paciente = relationship("Paciente", back_populates="prescricoes")
    itens = relationship("PrescricaoItem", back_populates="prescricao")
    eventos = relationship("PrescricaoEvento", back_populates="prescricao")
