"""
token_apresentacao.py
=====================
Modelo SQLAlchemy — tokens_apresentacao (Ticket 24)

O token de apresentação é uma credencial efêmera, persistida e revogável
gerada sob demanda pelo paciente para apresentação no balcão da farmácia.

SEMÂNTICA
---------
  O token NÃO executa custódia nem dispensação.
  Ele resolve o protocolo de forma segura e fluida, sem expor o UUID diretamente.

ESTADOS
-------
  ativo     → expirado (automático quando expira_em < agora)
  ativo     → revogado (paciente revoga explicitamente)
  Não existe estado 'consumido' — o token é multiuso dentro da validade.

INVALIDAÇÃO
-----------
  O token é considerado inválido quando:
  1. status = 'expirado' ou 'revogado'
  2. expira_em < agora (verificado no momento da resolução)
  3. prescrição associada está em estado terminal (dispensada/cancelada/encerrada_localmente)
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text

from app.database import Base


class TokenApresentacao(Base):
    __tablename__ = "tokens_apresentacao"

    id              = Column(Integer, primary_key=True)

    # Código amigável (8 chars Crockford) — o que o paciente apresenta
    codigo_curto    = Column(String(8), nullable=False, unique=True, index=True)

    # Prescrição referenciada
    protocolo       = Column(Text, nullable=False, index=True)

    # Dono do token (CPF do paciente)
    paciente_cpf    = Column(String(11), nullable=False, index=True)

    # Escopo único no MVP — preparado para extensão
    escopo          = Column(String(30), nullable=False, default="apresentacao")

    # Estado do token
    status          = Column(String(20), nullable=False, default="ativo")
    # status ∈ { ativo, expirado, revogado }

    # Temporalidade
    expira_em       = Column(Text, nullable=False)
    criado_em       = Column(Text, nullable=False)

    # Ticket 44 — Circulação atomizada
    # NULL = token da prescrição inteira (comportamento original, pré-T44)
    # INTEGER = FK para prescricao_itens.id — token de item específico
    item_id         = Column(Integer, ForeignKey("prescricao_itens.id"), nullable=True)

    # Revogação
    revogado_em     = Column(Text, nullable=True)
    revogado_por    = Column(Text, nullable=True)   # CNS ou CPF de quem revogou
