from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.database import Base


class Estorno(Base):
    """
    Estorno de uma dispensação registrada — objeto sanitário DERIVADO e IMUTÁVEL.

    TICKET-ESTORNO-OBJETO-DERIVADO.md (martelo Fabiano 2026-06-15):
    o estorno é uma nova asserção clínica de um novo autor e momento, então é
    modelado como objeto derivado (padrão `origem_*_id`, igual laudo↔pedido e
    correção↔prescrição) — NÃO como uma transição de estado que muta o item.
    A `dispensacoes` original permanece imutável; o saldo efetivo do item passa
    a ser Σ dispensado − Σ estornado.

    `prescricao_item_id` e `prescricao_id` são denormalizados (deriváveis de
    `origem_dispensacao_id`) para manter as queries de saldo e o recálculo de
    status sem JOIN — gravados uma vez na criação, nunca alterados.
    """

    __tablename__ = "estornos"

    id                    = Column(Integer, primary_key=True, index=True)
    protocolo             = Column(String(50), nullable=False, unique=True, index=True)  # UUID — identidade sanitária global
    origem_dispensacao_id = Column(Integer, ForeignKey("dispensacoes.id"), nullable=False, index=True)
    prescricao_item_id    = Column(Integer, ForeignKey("prescricao_itens.id"), nullable=False, index=True)
    prescricao_id         = Column(Integer, ForeignKey("prescricoes.id"), nullable=False, index=True)
    cnpj_estabelecimento  = Column(String(14), nullable=False, index=True)  # CNPJ normalizado do estabelecimento que estorna
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    autor_tipo            = Column(String(40), nullable=False)   # papel do JWT de quem estorna (dispensador)
    autor_id              = Column(String(100), nullable=True)   # identificador do autor (CNPJ)
    quantidade_estornada  = Column(Integer, nullable=False)
    motivo                = Column(String(40), nullable=False)   # enum MOTIVOS_ESTORNO (domain/states.py)
    assinatura_hash       = Column(String(64), nullable=True)    # stub MVP — assinatura do estorno (futuro)
    data_emissao          = Column(DateTime, nullable=False, default=datetime.utcnow)
    criado_em             = Column(DateTime, nullable=False, default=datetime.utcnow)
