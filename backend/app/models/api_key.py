"""
models/api_key.py
=================
API Keys institucionais para autenticação de adapters (G4B).

Cada API key pertence a um org_id (prestador).
Armazenada como sha256 — nunca em texto claro.
Criação e revogação: apenas role admin.
Uso: header X-Api-Key para autenticação em GET /eventos e POST /eventos/{id}/ack.
"""

from sqlalchemy import Boolean, Column, Text

from app.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id          = Column(Text, primary_key=True)        # UUID
    org_id      = Column(Text, nullable=False)           # prestador associado
    nome        = Column(Text, nullable=False)           # descrição descritiva
    chave_hash  = Column(Text, nullable=False, unique=True)  # sha256(chave)
    ativo       = Column(Boolean, nullable=False, default=True)
    criado_em   = Column(Text, nullable=False)
    criado_por  = Column(Text, nullable=True)            # sub do admin criador
