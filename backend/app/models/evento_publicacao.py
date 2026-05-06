"""
evento_publicacao.py
====================
Tabela de outbox para publicação de eventos externos (G4A).

Princípios:
  - Append-only: sem UPDATE de conteúdo, sem DELETE
  - Derivação do ledger clínico — não é o ledger em si
  - Falha de inserção no outbox nunca deve impactar o fluxo clínico
  - publicado: 0 = pendente, 1 = consumido (via POST /eventos/{id}/ack)
"""
from sqlalchemy import Column, Integer, Text
from app.database import Base


class EventoPublicacao(Base):
    __tablename__ = "eventos_publicacao"

    id           = Column(Text, primary_key=True)          # "evt_" + UUID
    tipo_evento  = Column(Text, nullable=False)             # ex: "agendamento_realizado"
    objeto_tipo  = Column(Text, nullable=False)             # prescricao | pedido_exame | agendamento | laudo
    objeto_id    = Column(Text, nullable=False)             # protocolo UUID do objeto
    payload      = Column(Text, nullable=False)             # JSON com contexto
    org_id       = Column(Text, nullable=True)              # NULL = sem escopo institucional
    unidade_id   = Column(Text, nullable=True)
    publicado    = Column(Integer, nullable=False, default=0)   # 0=pendente 1=consumido
    tentativas   = Column(Integer, nullable=False, default=0)
    criado_em    = Column(Text, nullable=False)             # ISO 8601 UTC
    publicado_em = Column(Text, nullable=True)              # NULL até ack
