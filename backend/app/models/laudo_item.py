from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class LaudoItem(Base):
    """
    Item individual de um laudo clínico.

    status_item possíveis (ver domain/states_laudo.py):
        em_producao · concluido · cancelado · encerrado_fisico

    conclusao:
        normal | alterado | indeterminado | inconclusivo
    """

    __tablename__ = "laudo_itens"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    laudo_id          = Column(Integer, ForeignKey("laudos.id"), nullable=False, index=True)
    # ENG-014 (v2, §2.1) — O ELO DE VERDADE com o item do pedido.
    #
    # `nome_exame` é EXIBIÇÃO; este id é a CHAVE. Antes dele, autorizar por item
    # só era possível casando nome (texto livre) — dois itens homônimos no mesmo
    # pedido, ou um exame renomeado, mudariam quem pode operar o laudo.
    #
    # NULL = legado (nascido antes do elo; a migração `f2d8b41c9e73` não faz
    # backfill de propósito). Esses laudos operam pela ponte registrada do §2.2.
    pedido_item_id    = Column(Integer, ForeignKey("pedido_exame_itens.id"),
                               nullable=True, index=True)
    nome_exame        = Column(String(200), nullable=False)
    codigo_tuss       = Column(String(20), nullable=True)
    resultado_resumo  = Column(Text, nullable=True)
    conclusao         = Column(String(30), nullable=True)   # normal|alterado|indeterminado|inconclusivo
    valor_referencia  = Column(Text, nullable=True)
    resultado_url     = Column(Text, nullable=True)
    status_item       = Column(String(30), nullable=False, default="em_producao")
    criado_em         = Column(DateTime, server_default=func.now(), nullable=False)
