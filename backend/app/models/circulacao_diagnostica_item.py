from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class CirculacaoDiagnosticaItem(Base):
    """
    Vínculo entre uma circulação diagnóstica e os itens do pedido de exame
    selecionados pelo paciente para esse envio ao laboratório.

    Um item do pedido (pedido_exame_itens) não pode pertencer a duas
    circulações ativas simultaneamente — constraint verificada no router.

    Não tem status_item próprio nesta versão (Ticket 52).
    A rastreabilidade de estado por item é suportada pelo pedido_exame_itens.

    Referência: docs/ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md §5
    """

    __tablename__ = "circulacao_diagnostica_itens"

    id                    = Column(Integer, primary_key=True, index=True)
    circulacao_id         = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=False, index=True)
    pedido_exame_item_id  = Column(Integer, ForeignKey("pedido_exame_itens.id"), nullable=False, index=True)
    nome_exame            = Column(String(200), nullable=False)   # denormalizado para leitura
    criado_em             = Column(Text, nullable=False)          # ISO 8601 datetime

    circulacao = relationship("CirculacaoDiagnostica")
