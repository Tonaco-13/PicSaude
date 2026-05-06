"""
PicSaúde — Contrato de Estados: Pedido de Exame
=================================================
Espelho de states.py para o domínio de pedidos de exame.

REGRA: nenhum router, model ou migration deve introduzir um novo estado
sem atualizar este arquivo, a seção 7 do CLAUDE.md e docs/ARQUITETURA_EXAMES.md.

Princípio central: o estado do PEDIDO é derivado dos estados dos ITENS.
Nunca atualizar pedidos_exame.status diretamente — sempre via função derivar_status_pedido().
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Tipos literais
# ---------------------------------------------------------------------------

EstadoPedidoExame = Literal[
    "emitido",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
]

EstadoItemExame = Literal[
    "pendente",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "nao_realizado",      # reservado v2 — ver docs/ARQUITETURA_EXAMES.md
    "encerrado_fisico",
]

# ---------------------------------------------------------------------------
# Estados de Pedido  (pedidos_exame.status)
# ---------------------------------------------------------------------------

ESTADOS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "emitido",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",
    "encerrado",           # terminal
    "cancelado",           # terminal
    "expirado",            # terminal
    "encerrado_fisico",    # terminal — fluxo físico
})

ESTADOS_TERMINAIS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Pedido
# ---------------------------------------------------------------------------

TRANSICOES_PEDIDO_EXAME: dict[str, frozenset[str]] = {
    "emitido":              frozenset({"agendado", "cancelado", "expirado"}),
    "agendado":             frozenset({"coletado", "cancelado", "expirado"}),
    "coletado":             frozenset({"em_analise", "cancelado"}),
    "em_analise":           frozenset({"resultado_disponivel", "cancelado"}),
    "resultado_disponivel": frozenset({"encerrado", "cancelado"}),
    "encerrado":            frozenset(),   # terminal
    "cancelado":            frozenset(),   # terminal
    "expirado":             frozenset(),   # terminal
    "encerrado_fisico":     frozenset(),   # terminal — fluxo físico
}

# ---------------------------------------------------------------------------
# Estados de Item  (pedido_exame_itens.status_item)
# ---------------------------------------------------------------------------

ESTADOS_ITEM_EXAME: frozenset[str] = frozenset({
    "pendente",
    "agendado",
    "coletado",
    "em_analise",
    "resultado_disponivel",  # terminal de fluxo normal
    "encerrado",             # terminal — ciência registrada
    "cancelado",             # terminal
    "nao_realizado",         # terminal — reservado v2
    "encerrado_fisico",      # terminal — fluxo físico
})

ESTADOS_TERMINAIS_ITEM_EXAME: frozenset[str] = frozenset({
    "resultado_disponivel",
    "encerrado",
    "cancelado",
    "nao_realizado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Item
# ---------------------------------------------------------------------------

TRANSICOES_ITEM_EXAME: dict[str, frozenset[str]] = {
    "pendente":              frozenset({"agendado", "cancelado"}),
    "agendado":              frozenset({"coletado", "cancelado"}),
    "coletado":              frozenset({"em_analise", "cancelado"}),
    "em_analise":            frozenset({"resultado_disponivel", "cancelado"}),
    "resultado_disponivel":  frozenset({"encerrado"}),
    "encerrado":             frozenset(),   # terminal
    "cancelado":             frozenset(),   # terminal
    "nao_realizado":         frozenset(),   # terminal — reservado v2
    "encerrado_fisico":      frozenset(),   # terminal — nunca volta ao ciclo digital
}

# ---------------------------------------------------------------------------
# Vocabulário de eventos no ledger  (pedido_exame_eventos.tipo_evento)
# ---------------------------------------------------------------------------

EVENTOS_PEDIDO_EXAME: frozenset[str] = frozenset({
    "pedido_emitido",           # emissão digital
    "pedido_impresso",          # fluxo físico — ato de impressão
    "encerrado_localmente",     # fluxo físico — status terminal (mesmo nome da prescrição)
    "pedido_agendado",          # agendamento confirmado com prestador
    "pedido_coletado",          # coleta realizada
    "pedido_em_analise",        # laboratório iniciou processamento
    "resultado_registrado",     # laudo inserido no sistema pelo prestador
    "resultado_comunicado",     # paciente/prescritor notificado
    "pedido_encerrado",         # ciência registrada
    "pedido_cancelado",         # cancelamento (qualquer fase)
    "pedido_expirado",          # validade ultrapassada
    "custodia_transferida",     # qualquer transferência de posse
    "pedido_corrigido",         # derivação por correção
})

# ---------------------------------------------------------------------------
# Derivação de status do pedido a partir dos itens
# ---------------------------------------------------------------------------

# Prioridade para derivação: quanto menor o índice, mais avançado o estado
_PRIORIDADE_ESTADO = [
    "resultado_disponivel",
    "em_analise",
    "coletado",
    "agendado",
    "pendente",   # == "emitido" no nível do item
]


def derivar_status_pedido(status_itens: list[str]) -> str:
    """
    Deriva o status do pedido a partir da lista de status dos seus itens ativos.

    Itens em estado terminal (encerrado/cancelado/nao_realizado/encerrado_fisico)
    são ignorados no cálculo do estado agregado.

    Se todos os itens estiverem em estado terminal:
    - todos encerrados ou resultado_disponivel → "encerrado"
    - ao menos um cancelado (sem encerrado) → "cancelado"
    """
    ativos = [s for s in status_itens if s not in ESTADOS_TERMINAIS_ITEM_EXAME
              or s == "resultado_disponivel"]

    # Remove resultado_disponivel dos "ativos" para recálculo correto
    ativos_sem_resultado = [s for s in status_itens if s not in ESTADOS_TERMINAIS_ITEM_EXAME]

    if not ativos_sem_resultado:
        # Todos terminais — determina se foi encerrado ou cancelado
        terminais = [s for s in status_itens]
        if all(s in {"encerrado", "resultado_disponivel", "nao_realizado", "encerrado_fisico"}
               for s in terminais):
            return "encerrado"
        return "cancelado"

    for estado in _PRIORIDADE_ESTADO:
        if estado in ativos_sem_resultado:
            return estado if estado != "pendente" else "emitido"

    return "emitido"


# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

def transicao_valida_pedido(de: str, para: str) -> bool:
    return para in TRANSICOES_PEDIDO_EXAME.get(de, frozenset())


def transicao_valida_item_exame(de: str, para: str) -> bool:
    return para in TRANSICOES_ITEM_EXAME.get(de, frozenset())


def eh_terminal_pedido(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_PEDIDO_EXAME


def eh_terminal_item_exame(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ITEM_EXAME
