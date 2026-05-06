"""
PicSaúde — Contrato de Estados
================================
Fonte de verdade para todos os valores válidos de status de prescrição e item.

REGRA: nenhum router, model ou migration deve introduzir um novo estado
sem atualizar este arquivo, a seção 5b do CLAUDE.md e o DDL PostgreSQL.

Qualquer teste pode importar estas constantes para garantir consistência:

    from app.domain.states import ESTADOS_PRESCRICAO, ESTADOS_ITEM
    assert prescricao["status"] in ESTADOS_PRESCRICAO
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Tipos literais — mypy detecta strings inválidas em tempo de análise estática
# ---------------------------------------------------------------------------

EstadoPrescricao = Literal[
    "pendente",
    "transferida_paciente",
    "em_custodia",
    "parcialmente_dispensada",
    "dispensada",
    "cancelada",
    "expirada",
    "encerrada_localmente",
]

EstadoItem = Literal[
    "pendente",
    "em_custodia",
    "dispensado",
    "devolvido_paciente",
    "devolvido_prescritor",
    "cancelado",
    "estornado",
    "encerrado_fisico",
]

# ---------------------------------------------------------------------------
# Estados de Prescrição  (prescricoes.status)
# ---------------------------------------------------------------------------

ESTADOS_PRESCRICAO: frozenset[str] = frozenset({
    # Fluxo digital
    "pendente",                 # emitida, aguarda transferência ao paciente
    "transferida_paciente",     # em custódia do cidadão
    "em_custodia",              # retida pelo dispensador
    "parcialmente_dispensada",  # ao menos um item dispensado
    "dispensada",               # todos os itens ativos dispensados  [terminal]
    "cancelada",                # revogação clínica                  [terminal]
    "expirada",                 # data_validade ultrapassada          [terminal]
    # Fluxo físico
    "encerrada_localmente",     # emissão exclusivamente em papel     [terminal]
})

ESTADOS_TERMINAIS_PRESCRICAO: frozenset[str] = frozenset({
    "dispensada",
    "cancelada",
    "expirada",
    "encerrada_localmente",
})

# ---------------------------------------------------------------------------
# Transições válidas de Prescrição
# ---------------------------------------------------------------------------

TRANSICOES_PRESCRICAO: dict[str, frozenset[str]] = {
    "pendente":                frozenset({"transferida_paciente", "cancelada", "expirada"}),
    "transferida_paciente":    frozenset({"em_custodia", "cancelada", "expirada"}),
    "em_custodia":             frozenset({"parcialmente_dispensada", "dispensada", "cancelada", "transferida_paciente"}),
    "parcialmente_dispensada": frozenset({"dispensada", "cancelada", "expirada"}),
    "dispensada":              frozenset(),   # terminal
    "cancelada":               frozenset(),   # terminal
    "expirada":                frozenset(),   # terminal
    "encerrada_localmente":    frozenset(),   # terminal — fluxo físico
}

# ---------------------------------------------------------------------------
# Estados de Item  (prescricao_itens.status_item)
# ---------------------------------------------------------------------------

ESTADOS_ITEM: frozenset[str] = frozenset({
    # Fluxo digital
    "pendente",               # estado inicial
    "em_custodia",            # dispensador reteve para dispensação
    "dispensado",             # entregue ao paciente               [terminal]
    "devolvido_paciente",     # abandono de compra; retry possível
    "devolvido_prescritor",   # erro identificado; aguarda nova prescrição [terminal*]
    "cancelado",              # revogação clínica                  [terminal]
    "estornado",              # dispensação revertida               [terminal]
    # Fluxo físico
    "encerrado_fisico",       # emitido em papel; fora do ciclo digital [terminal]
})

ESTADOS_TERMINAIS_ITEM: frozenset[str] = frozenset({
    "dispensado",
    "devolvido_prescritor",   # (*) aguarda nova prescrição derivada (origem_prescricao_id)
    "cancelado",
    "estornado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Item
# ---------------------------------------------------------------------------

TRANSICOES_ITEM: dict[str, frozenset[str]] = {
    "pendente":              frozenset({"em_custodia", "cancelado"}),
    "em_custodia":           frozenset({"dispensado", "devolvido_paciente", "devolvido_prescritor", "cancelado"}),
    "devolvido_paciente":    frozenset({"em_custodia", "cancelado"}),   # retry permitido
    "dispensado":            frozenset({"estornado"}),
    "devolvido_prescritor":  frozenset(),   # terminal — aguarda nova prescrição
    "cancelado":             frozenset(),   # terminal
    "estornado":             frozenset(),   # terminal
    "encerrado_fisico":      frozenset(),   # terminal — nunca volta ao ciclo digital
}

# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

def transicao_valida_prescricao(de: str, para: str) -> bool:
    """Retorna True se a transição de estado da prescrição é permitida."""
    return para in TRANSICOES_PRESCRICAO.get(de, frozenset())


def transicao_valida_item(de: str, para: str) -> bool:
    """Retorna True se a transição de estado do item é permitida."""
    return para in TRANSICOES_ITEM.get(de, frozenset())


def eh_terminal_prescricao(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_PRESCRICAO


def eh_terminal_item(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ITEM


# ---------------------------------------------------------------------------
# Mapeamento de transições → eventos obrigatórios no ledger
# ---------------------------------------------------------------------------
# Cada chave (de, para) aponta para o tipo_evento que DEVE ser inserido em
# prescricao_eventos quando a transição ocorre.  None = sem evento próprio
# (a transição é coberta por outro evento já emitido, ex. emissão digital).
#
# NOTA SOBRE INCONSISTÊNCIA DOCUMENTADA:
#   Em custodia.py, devolução dispensador→prescritor transiciona a prescrição
#   para "pendente" (não previsto em TRANSICOES_PRESCRICAO["em_custodia"]).
#   E devolução dispensador→paciente transiciona itens para "pendente" em vez
#   de "devolvido_paciente" → "em_custodia" (conforme o state machine do item).
#   Essas transições FUNCIONAM mas desviam do modelo formal.
#   Correção sugerida: introduzir "transferida_prescritor" como estado para
#   devolução ao prescritor, e usar "devolvido_paciente" explicitamente no
#   abandono de balcão. Não corrigido agora para não quebrar o comportamento.
# ---------------------------------------------------------------------------

EVENTOS_PRESCRICAO: dict[tuple[str, str], str] = {
    # estado_atual          , novo_estado              : tipo_evento
    ("pendente",                "transferida_paciente"): "custodia_transferida",
    ("pendente",                "cancelada"):            "prescricao_cancelada",
    ("pendente",                "expirada"):             "prescricao_expirada",
    ("transferida_paciente",    "em_custodia"):          "custodia_transferida",
    ("transferida_paciente",    "cancelada"):            "prescricao_cancelada",
    ("transferida_paciente",    "expirada"):             "prescricao_expirada",
    ("em_custodia",             "parcialmente_dispensada"): "dispensacao_parcial",
    ("em_custodia",             "dispensada"):           "dispensacao_registrada",
    ("em_custodia",             "cancelada"):            "prescricao_cancelada",
    ("em_custodia",             "transferida_paciente"): "custodia_transferida",
    ("parcialmente_dispensada", "dispensada"):           "dispensacao_registrada",
    ("parcialmente_dispensada", "cancelada"):            "prescricao_cancelada",
    ("parcialmente_dispensada", "expirada"):             "prescricao_expirada",
}

EVENTOS_ITEM: dict[tuple[str, str], str] = {
    # estado_atual       , novo_estado          : tipo_evento
    ("pendente",           "em_custodia"):        "custodia_transferida",
    ("pendente",           "cancelado"):          "item_cancelado",
    ("em_custodia",        "dispensado"):         "item_dispensado",
    ("em_custodia",        "devolvido_paciente"): "item_devolvido_paciente",
    ("em_custodia",        "devolvido_prescritor"): "item_devolvido_prescritor",
    ("em_custodia",        "cancelado"):          "item_cancelado",
    ("devolvido_paciente", "em_custodia"):        "custodia_transferida",
    ("devolvido_paciente", "cancelado"):          "item_cancelado",
    ("dispensado",         "estornado"):          "item_estornado",
}


def evento_obrigatorio_prescricao(de: str, para: str) -> str | None:
    """
    Retorna o tipo_evento obrigatório para a transição de prescrição,
    ou None se a transição não tiver evento próprio mapeado.
    """
    return EVENTOS_PRESCRICAO.get((de, para))


def evento_obrigatorio_item(de: str, para: str) -> str | None:
    """
    Retorna o tipo_evento obrigatório para a transição de item,
    ou None se a transição não tiver evento próprio mapeado.
    """
    return EVENTOS_ITEM.get((de, para))


# ---------------------------------------------------------------------------
# Vocabulário de eventos de renovação  (Ticket 13)
# Esses eventos NÃO correspondem a transições de estado da prescrição —
# são registros autônomos no ledger descrevendo o fluxo de solicitação.
# ---------------------------------------------------------------------------

EVENTOS_RENOVACAO: frozenset[str] = frozenset({
    "renovacao_solicitada",   # paciente solicitou renovação ao prescritor
    "renovacao_atendida",     # prescritor emitiu nova prescrição
    "renovacao_recusada",     # prescritor recusou com justificativa
})

# Status válidos de solicitacao_renovacao
ESTADOS_SOLICITACAO_RENOVACAO: frozenset[str] = frozenset({
    "pendente",    # aguardando resposta do prescritor
    "atendida",    # prescritor emitiu nova prescrição
    "recusada",    # prescritor recusou
    "cancelada",   # paciente cancelou antes da resposta
})
