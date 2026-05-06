"""
models/meta_instalacao.py
=========================
Metadados de instalação da instância PicSaúde (G5).

Tabela chave-valor para rastrear versão do núcleo, data de bootstrap
e outros metadados operacionais. Usada por GET /health/version.

Chaves padrão:
  nucleo_version    → versão do núcleo PicSaúde
  instalado_em      → timestamp ISO do bootstrap
  org_id            → identificador institucional da instância
  schema_version    → versão do esquema de banco
  bootstrap_version → versão do script de bootstrap utilizado
"""

from __future__ import annotations

from sqlalchemy import Column, Text

from app.database import Base


class MetaInstalacao(Base):
    __tablename__ = "meta_instalacao"

    chave     = Column(Text, primary_key=True)
    valor     = Column(Text, nullable=False)
    criado_em = Column(Text, nullable=False)
