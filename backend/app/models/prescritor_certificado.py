"""
prescritor_certificado.py
==========================
Model SQLAlchemy — Ticket 21 — Certificados ICP-Brasil dos prescritores.

Tabela separada de `prescritores` por DOIS motivos:
  1. Permite histórico (renovação, revogação, substituição) sem poluir
     a entidade principal.
  2. Cada PDF assinado pode ser auditado contra o certificado que o
     assinou via `hash_cert_der` no evento do ledger — esse hash é
     imutável e único por certificado.

Apenas UM certificado ativo por prescritor por vez (`ativo=TRUE`).
Upload de novo cert marca o anterior como `ativo=FALSE` +
`substituido_em=now()`.

Segurança:
  - .pfx é armazenado AES-256-GCM cifrado em `pfx_cifrado`.
  - IV (12 bytes) e tag (16 bytes) são persistidos.
  - A chave de criptografia (`PFX_ENCRYPTION_KEY`) é variável de
    ambiente — nunca persistida no banco.
  - A senha do .pfx é fornecida pelo prescritor a cada uso e nunca
    é persistida.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class PrescritorCertificado(Base):
    """Certificado ICP-Brasil A1 vinculado a um prescritor (Ticket 21)."""

    __tablename__ = "prescritor_certificados"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prescritor_id = Column(
        Integer, ForeignKey("prescritores.id"), nullable=False, index=True,
    )

    # Bytes do .pfx criptografados com AES-256-GCM.
    pfx_cifrado = Column(LargeBinary, nullable=False)
    pfx_iv = Column(LargeBinary(12), nullable=False)        # IV de 12 bytes
    pfx_tag = Column(LargeBinary(16), nullable=False)       # tag autenticada

    # Fingerprint imutável do certificado (SHA-256 do DER).
    hash_cert_der = Column(String(64), nullable=False)

    # Metadados extraídos do certificado.
    serial = Column(String(100), nullable=False)
    valido_de = Column(DateTime, nullable=False)
    valido_ate = Column(DateTime, nullable=False)
    nome_no_certificado = Column(String(200), nullable=False)
    cpf_no_certificado = Column(String(11), nullable=False)
    emissor = Column(String(200), nullable=True)

    # Lifecycle.
    ativo = Column(Boolean, nullable=False, default=True)
    revogado_em = Column(DateTime, nullable=True)        # revogação manual
    substituido_em = Column(DateTime, nullable=True)     # upload de novo cert

    uploaded_em = Column(DateTime, nullable=False, default=datetime.utcnow)

    prescritor = relationship("Prescritor")

    __table_args__ = (
        UniqueConstraint(
            "prescritor_id", "hash_cert_der",
            name="uq_prescritor_cert_hash",
        ),
    )
