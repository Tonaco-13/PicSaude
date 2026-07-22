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
# TICKET-B0 — bloqueio HARD de dispensação (independe do saldo)
# ---------------------------------------------------------------------------
# Estados terminais que impedem dispensação MESMO com saldo efetivo > 0. É o
# conjunto dos terminais de item MENOS 'dispensado': o rótulo 'dispensado'
# permanece como registro histórico (§2 estorno-derivado), mas deixa de ser o
# critério de dispensabilidade — com saldo reposto por um estorno o item volta a
# ser dispensável (CLAUDE.md §4 · §2a R1). Fonte ÚNICA para o guard de
# dispensação (custodia.py) e o campo `acionavel` da fila (dispensadores.py).
BLOQUEADOS_HARD_DISPENSA: frozenset[str] = ESTADOS_TERMINAIS_ITEM - frozenset({"dispensado"})

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
# Estorno — objeto sanitário DERIVADO (T2, TICKET-ESTORNO-OBJETO-DERIVADO.md)
# ---------------------------------------------------------------------------
# O estorno NÃO é uma transição de estado do item: é um objeto derivado e
# imutável (tabela `estornos`) que referencia a dispensação de origem. Por isso
# o item NÃO é mutado para `estornado` no fluxo real — a transição
# `dispensado → estornado` acima permanece como scaffolding dormente (§5 do
# ticket: sua remoção/SM2 é adiada para não desincronizar o paper). O efeito do
# estorno é contábil: saldo efetivo do item = Σ dispensado − Σ estornado.
#
# Enum de motivo (Fase 0.2 do PLANO_DEMO_CIRCULACAO.md), ancorado no vocabulário
# do ledger (CLAUDE.md §2 — `pagamento_nao_concluido` já existe).
MOTIVOS_ESTORNO: frozenset[str] = frozenset({
    "pagamento_nao_concluido",   # cartão recusado / pagamento falhou no balcão
    "desistencia_paciente",      # paciente desistiu da compra
    "erro_dispensacao",          # lote/fármaco registrado por engano
    "outro",                     # outro motivo (detalhar em observação livre)
})

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
#   RESOLVIDO — ramo paciente (TICKET-COERENCIA-DEVOLUCOES, 2026-07-22, Opção A):
#   a devolução dispensador→paciente (custodia.py::devolver_item) transiciona o item
#   para "devolvido_paciente" e, quando a posse volta integralmente ao paciente, a
#   prescrição para "transferida_paciente" via _recalcular_status_prescricao —
#   transição já prevista em TRANSICOES_PRESCRICAO["em_custodia"] e EVENTOS_PRESCRICAO
#   (("em_custodia","transferida_paciente") → "custodia_transferida"). A custódia de
#   prescrição inteira (item_id IS NULL) obsoleta do dispensador é reconciliada na
#   mesma transação. Reusa estado existente: sem estado novo, sem DDL.
#
#   PENDENTE — ramo prescritor (fora do escopo do ticket acima, §8):
#   Em custodia.py, devolução dispensador→prescritor transiciona a prescrição
#   para "pendente" (não previsto em TRANSICOES_PRESCRICAO["em_custodia"]).
#   Em auth.py:devolver_prescritor (paciente → prescritor), itens transicionam
#   de "pendente" diretamente para "devolvido_prescritor" (terminal), pulando
#   "em_custodia" exigido por TRANSICOES_ITEM. Apontado pelo CODEX em 2026-05-21
#   (4E.2). Ver docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md §3.3.
#   Essas transições FUNCIONAM mas desviam do modelo formal.
#   Correção sugerida: introduzir "transferida_prescritor" como estado para
#   devolução ao prescritor. Não corrigido agora para não quebrar o comportamento.
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
