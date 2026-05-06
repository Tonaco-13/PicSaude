from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PedidoExameItem(Base):
    """
    Item individual de um pedido de exame.

    Status possíveis (ver domain/states_exame.py):
        pendente · agendado · coletado · em_analise
        resultado_disponivel · encerrado · cancelado · nao_realizado · encerrado_fisico

    O estado do pedido (PedidoExame.status) é sempre derivado dos estados
    dos itens via domain/states_exame.derivar_status_pedido().
    """

    __tablename__ = "pedido_exame_itens"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id           = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    nome_exame          = Column(String(200), nullable=False)
    codigo_tuss         = Column(String(20), nullable=True)    # interoperabilidade futura
    codigo_sigtap       = Column(String(20), nullable=True)    # tabela SUS
    status_item         = Column(String(30), nullable=False, default="pendente")
    quantidade          = Column(Integer, nullable=False, default=1)
    resultado_resumo    = Column(Text, nullable=True)          # texto curto do laudo
    resultado_url       = Column(Text, nullable=True)          # link/path para arquivo
    resultado_em        = Column(DateTime, nullable=True)
    criado_em           = Column(DateTime, server_default=func.now(), nullable=False)
