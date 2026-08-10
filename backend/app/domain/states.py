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
    "transferida_prescritor",
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
    "transferida_prescritor",   # devolvida ao prescritor p/ correção (espelho de transferida_paciente)
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
    "pendente":                frozenset({"transferida_paciente", "transferida_prescritor", "cancelada", "expirada"}),
    "transferida_paciente":    frozenset({"em_custodia", "transferida_prescritor", "cancelada", "expirada"}),
    # Espelho de transferida_paciente: posse com o prescritor aguardando correção.
    # Não volta ao ciclo digital in-place — a correção gera prescrição DERIVADA
    # (origem_prescricao_id, §1). O original só sai para terminal (revogado/expira).
    "transferida_prescritor":  frozenset({"cancelada", "expirada"}),
    "em_custodia":             frozenset({"parcialmente_dispensada", "dispensada", "cancelada", "transferida_paciente", "transferida_prescritor"}),
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
# RESOLVIDO — COER2-POS-MERGE-FIX (2026-07-23): item em `devolvido_paciente`
# (rescaldo de estorno/devolução ao paciente) pode transicionar para
# `devolvido_prescritor` quando o cidadão devolve ao médico. Antes deste fix,
# apenas itens `pendente` podiam ir ao prescritor (auth.py::devolver_prescritor,
# WHERE status_item='pendente'), deixando o item `devolvido_paciente` em estado
# CONTRADITÓRIO com a prescrição (`transferida_prescritor`) e invisível no painel
# de correções (prescritor.py lê item-level `devolvido_prescritor`) — eco de
# "dupla posse" no nível de estado. Agora AMBOS os estados retornáveis (`pendente`
# e `devolvido_paciente`) podem ir ao prescritor, alinhado à filosofia do COER-2
# (toda transição de posse passa pelo choke-point, sem exceção de caminho).
# Diagnóstico: TICKET-COER2-POS-MERGE. O ramo dispensador→prescritor
# (custodia.py::devolver_item) já aceitava `devolvido_paciente` via block-guard.
# ---------------------------------------------------------------------------

TRANSICOES_ITEM: dict[str, frozenset[str]] = {
    "pendente":              frozenset({"em_custodia", "cancelado"}),
    "em_custodia":           frozenset({"dispensado", "devolvido_paciente", "devolvido_prescritor", "cancelado"}),
    "devolvido_paciente":    frozenset({"em_custodia", "cancelado", "devolvido_prescritor"}),   # retry ou volta ao médico (COER2-POS-MERGE-FIX)
    "dispensado":            frozenset({"estornado", "devolvido_paciente"}),  # devolvido_paciente: estorno TOTAL p/ motivos "cidadão recupera" (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO §3.2)
    "devolvido_prescritor":  frozenset(),   # terminal — aguarda nova prescrição
    "cancelado":             frozenset(),   # terminal
    "estornado":             frozenset(),   # terminal
    "encerrado_fisico":      frozenset(),   # terminal — nunca volta ao ciclo digital
}

# ---------------------------------------------------------------------------
# Estorno — objeto sanitário DERIVADO (T2, TICKET-ESTORNO-OBJETO-DERIVADO.md)
# ---------------------------------------------------------------------------
# O estorno é um objeto derivado e imutável (tabela `estornos`) que referencia
# a dispensação de origem — a `dispensacoes` original permanece intocada (§1) e
# o efeito contábil é sempre saldo efetivo = Σ dispensado − Σ estornado.
#
# MUTAÇÃO CONDICIONAL DE ITEM (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO, 10/08):
# o item SÓ é mutado pelo estorno em UM cenário restrito — estorno TOTAL
# (Σ estornado == Σ dispensado do item) nos motivos "cidadão recupera"
# (`desistencia_paciente`, `pagamento_nao_concluido`, `outro`): aí o item vai a
# `devolvido_paciente` e a custódia volta ao paciente (areasta
# `dispensado → devolvido_paciente` acima). Nos demais casos o item NÃO é
# mutado: estorno PARCIAL repõe só o saldo (comportamento TICKET-B0 preservado)
# e `erro_dispensacao` retém na farmácia p/ re-dispensação. A transição
# `dispensado → estornado` segue como scaffolding dormente (§5 do
# TICKET-ESTORNO-OBJETO-DERIVADO: remoção/SM2 adiada para não desincronizar o
# paper) — não é usada no fluxo real em nenhum caminho.
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
#   RESOLVIDO — ramo prescritor (TICKET-COERENCIA-DEVOLUCOES-2, 2026-07-23, Opção B
#   ratificada por Fabiano): introduzido o estado `transferida_prescritor` como
#   ESPELHO de `transferida_paciente` — posse com o prescritor aguardando correção.
#   Ambos os caminhos convergem para ele via o choke-point `transferir_posse`:
#     • dispensador→prescritor (custodia.py::devolver_item para=prescritor): quando
#       a posse volta INTEGRALMENTE ao prescritor, _recalcular_status_prescricao
#       retorna "transferida_prescritor" (antes retornava "cancelada" — desvio).
#     • paciente→prescritor (auth.py::devolver_prescritor): status passa a
#       "transferida_prescritor" (antes "pendente" — ambíguo, raiz do Cenário 2:
#       a carteira do cidadão não distinguia "aguardando 1º envio" de "devolvida").
#   Itens seguem em "devolvido_prescritor" (terminal, aguardam prescrição derivada);
#   a transição de posse da PRESCRIÇÃO ganha estado próprio, honesto contra a custódia.
# ---------------------------------------------------------------------------

EVENTOS_PRESCRICAO: dict[tuple[str, str], str] = {
    # estado_atual          , novo_estado              : tipo_evento
    ("pendente",                "transferida_paciente"): "custodia_transferida",
    ("pendente",                "transferida_prescritor"): "custodia_transferida",
    ("pendente",                "cancelada"):            "prescricao_cancelada",
    ("pendente",                "expirada"):             "prescricao_expirada",
    ("transferida_paciente",    "em_custodia"):          "custodia_transferida",
    ("transferida_paciente",    "transferida_prescritor"): "custodia_transferida",
    ("transferida_paciente",    "cancelada"):            "prescricao_cancelada",
    ("transferida_paciente",    "expirada"):             "prescricao_expirada",
    ("transferida_prescritor",  "cancelada"):            "prescricao_cancelada",
    ("transferida_prescritor",  "expirada"):             "prescricao_expirada",
    ("em_custodia",             "parcialmente_dispensada"): "dispensacao_parcial",
    ("em_custodia",             "dispensada"):           "dispensacao_registrada",
    ("em_custodia",             "cancelada"):            "prescricao_cancelada",
    ("em_custodia",             "transferida_paciente"): "custodia_transferida",
    ("em_custodia",             "transferida_prescritor"): "custodia_transferida",
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
    ("devolvido_paciente", "devolvido_prescritor"): "item_devolvido_prescritor",  # COER2-POS-MERGE-FIX
    ("dispensado",         "estornado"):          "item_estornado",
    ("dispensado",         "devolvido_paciente"): "item_devolvido_paciente",  # estorno TOTAL "cidadão recupera" (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO)
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
