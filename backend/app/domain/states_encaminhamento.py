"""
PicSaúde — Contrato de Estados: Encaminhamento
================================================
Objeto sanitário de referência clínica entre prescritor de origem e
prescritor de destino.

tipo_agregacao_status = "direto"

O encaminhamento tem transições no nível do OBJETO. Itens carregam
especialidade/procedimento/motivo, mas a progressão independente por item
fica para uma versão futura.
"""

from __future__ import annotations

from typing import Literal


EstadoEncaminhamento = Literal[
    "emitido",
    "em_regulacao",
    "agendado",
    "atendido",
    "contrarreferido",
    "encerrado",
    "cancelado",
    "expirado",
    "negado",
    "encerrado_fisico",
]

EstadoItemEncaminhamento = Literal[
    "pendente",
    "em_andamento",
    "concluido",
    "cancelado",
    "encerrado_fisico",
]


ESTADOS_ENCAMINHAMENTO: frozenset[str] = frozenset({
    "emitido",
    "em_regulacao",
    "agendado",
    "atendido",
    "contrarreferido",
    "encerrado",
    "cancelado",
    "expirado",
    "negado",
    "encerrado_fisico",
})

ESTADOS_TERMINAIS_ENCAMINHAMENTO: frozenset[str] = frozenset({
    "encerrado",
    "cancelado",
    "expirado",
    "negado",
    "encerrado_fisico",
})

TRANSICOES_ENCAMINHAMENTO: dict[str, frozenset[str]] = {
    "emitido":         frozenset({"em_regulacao", "agendado", "cancelado", "expirado", "negado"}),
    "em_regulacao":   frozenset({"agendado", "negado", "cancelado", "expirado"}),
    "agendado":       frozenset({"atendido", "cancelado", "expirado"}),
    "atendido":       frozenset({"contrarreferido", "encerrado", "cancelado"}),
    "contrarreferido": frozenset({"encerrado", "cancelado"}),
    "encerrado":      frozenset(),
    "cancelado":      frozenset(),
    "expirado":       frozenset(),
    "negado":         frozenset(),
    "encerrado_fisico": frozenset(),
}


ESTADOS_ITEM_ENCAMINHAMENTO: frozenset[str] = frozenset({
    "pendente",
    "em_andamento",
    "concluido",
    "cancelado",
    "encerrado_fisico",
})

ESTADOS_TERMINAIS_ITEM_ENCAMINHAMENTO: frozenset[str] = frozenset({
    "concluido",
    "cancelado",
    "encerrado_fisico",
})

TRANSICOES_ITEM_ENCAMINHAMENTO: dict[str, frozenset[str]] = {
    "pendente":        frozenset({"em_andamento", "cancelado"}),
    "em_andamento":   frozenset({"concluido", "cancelado"}),
    "concluido":      frozenset(),
    "cancelado":      frozenset(),
    "encerrado_fisico": frozenset(),
}


EVENTOS_ENCAMINHAMENTO: frozenset[str] = frozenset({
    "encaminhamento_emitido",
    "encaminhamento_impresso",
    "encaminhamento_em_regulacao",
    "encaminhamento_agendado",
    "encaminhamento_atendido",
    "encaminhamento_encerrado",
    "encaminhamento_cancelado",
    "encaminhamento_negado",
    "custodia_transferida",
})


def transicao_valida_encaminhamento(de: str, para: str) -> bool:
    return para in TRANSICOES_ENCAMINHAMENTO.get(de, frozenset())


def transicao_valida_item_encaminhamento(de: str, para: str) -> bool:
    return para in TRANSICOES_ITEM_ENCAMINHAMENTO.get(de, frozenset())


def eh_terminal_encaminhamento(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ENCAMINHAMENTO


def eh_terminal_item_encaminhamento(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ITEM_ENCAMINHAMENTO


def derivar_status_encaminhamento(status_atual: str, status_itens: list[str] | None = None) -> str:
    """Passthrough para agregação ``direto``.

    A assinatura mantém o formato de derivação esperado pelo checklist do
    núcleo, mas o status oficial é transitado explicitamente no objeto.
    """
    return status_atual
