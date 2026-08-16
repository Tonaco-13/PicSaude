from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class PedidoExameCustodia(Base):
    """
    Cadeia de custódia do pedido de exame.

    Granularidade:
        item_id = NULL  → custódia do pedido inteiro
        item_id = X     → custódia de item específico

    Transições permitidas:
        prescritor      → paciente           (emissão digital)
        paciente        → prestador_exame    (agendamento/apresentação)
        prestador_exame → paciente           (laudo disponível)

    REGRA: sem registros para fluxo físico (encerrado_fisico).

    POSSE ATUAL (J.10-CORE, migração `d4b8c1e07f36`)
    ------------------------------------------------
    A tabela nasceu como LEDGER de transferências: quem detinha era a última
    linha (`ORDER BY id DESC LIMIT 1`). Num ledger não existe "linha ativa" que
    um índice único possa restringir, e a unicidade de posse — o R2 na camada de
    custódia — ficava só na convenção de código. Com `encerrada_em`, esta tabela
    passa a ter a mesma forma de `prescricao_custodia`:

        posse atual  ⇔  encerrada_em IS NULL

    e um índice único parcial garante NO MÁXIMO UMA por `(pedido_id, item_id)`,
    nos dois dialetos. Toda escrita passa pelo choke-point
    `routers/pedidos_exame.py::transferir_posse_exame` — nenhum caminho de
    produto faz `INSERT` à mão.
    """

    __tablename__ = "pedido_exame_custodia"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id       = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    item_id         = Column(Integer, ForeignKey("pedido_exame_itens.id"), nullable=True)
    de              = Column(String(100), nullable=False)    # papel ou CNPJ
    para            = Column(String(100), nullable=False)
    transferido_em  = Column(DateTime, server_default=func.now(), nullable=False)
    # J.10-CORE: NULL = posse ATIVA. Índice único parcial garante no máximo uma
    # ativa por (pedido_id, item_id) — ver docstring da classe.
    encerrada_em    = Column(DateTime, nullable=True)
    dados_json      = Column(Text, nullable=True)
