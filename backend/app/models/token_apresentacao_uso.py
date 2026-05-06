"""
token_apresentacao_uso.py
=========================
Modelo SQLAlchemy — tokens_apresentacao_usos (Ticket 24)

Registro imutável de cada tentativa de resolução de um token.
Funciona como audit log técnico separado do ledger clínico principal.

DIFERENÇA DO LEDGER CLÍNICO
----------------------------
  O ledger (prescricao_eventos) registra eventos sanitários com efeito transacional.
  Esta tabela registra eventos técnicos de apresentação — sem efeito na máquina de estados.

RESULTADOS POSSÍVEIS
--------------------
  resolvido            → token válido, protocolo retornado
  expirado             → token expirado no momento da tentativa
  revogado             → token foi revogado pelo paciente
  nao_encontrado       → codigo_curto não existe no banco
  prescricao_encerrada → prescrição já não está disponível para dispensação
"""

from __future__ import annotations

from sqlalchemy import Column, Integer, String, Text

from app.database import Base


class TokenApresentacaoUso(Base):
    __tablename__ = "tokens_apresentacao_usos"

    id                    = Column(Integer, primary_key=True)

    # Referência ao token (denormalizado para facilitar queries)
    token_id              = Column(Integer, nullable=True)        # FK lógico (sem constraint para simplicidade)
    codigo_curto          = Column(String(8), nullable=False, index=True)

    # Quem usou
    dispensador_cns       = Column(String(15), nullable=True)
    cnpj_estabelecimento  = Column(String(14), nullable=True)

    # Resultado da tentativa
    resultado             = Column(String(30), nullable=False)
    # resultado ∈ { resolvido, expirado, revogado, nao_encontrado, prescricao_encerrada }

    # Protocolo resolvido (preenchido apenas quando resultado = 'resolvido')
    protocolo_resolvido   = Column(Text, nullable=True)

    # Timestamp
    criado_em             = Column(Text, nullable=False)
