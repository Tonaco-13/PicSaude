"""
states_agendamento.py
=====================
Contrato de estados do módulo de Agendamento (Ticket 29).

Classificação do objeto: objeto sanitário leve — tem identidade própria
(UUID), máquina de estados e ledger, mas sem custódia e sem assinatura.

Fonte de verdade para:
  - agendamentos.status
  - transições válidas
  - estados terminais

Regra obrigatória: nunca atualizar agendamentos.status diretamente —
sempre via _transicionar_agendamento() no router, que valida transições.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Estados válidos
# ---------------------------------------------------------------------------

ESTADOS_AGENDAMENTO: frozenset[str] = frozenset({
    "criado",
    "confirmado",
    "realizado",
    "cancelado",
    "nao_compareceu",
})

ESTADOS_TERMINAIS_AGENDAMENTO: frozenset[str] = frozenset({
    "realizado",
    "cancelado",
    "nao_compareceu",
})

# ---------------------------------------------------------------------------
# Transições permitidas
# De → {para...}
# Nota: criado → realizado é permitido (simplificação MVP — não exige confirmação)
# ---------------------------------------------------------------------------

TRANSICOES_AGENDAMENTO: dict[str, frozenset[str]] = {
    "criado":    frozenset({"confirmado", "realizado", "cancelado", "nao_compareceu"}),
    "confirmado": frozenset({"realizado", "cancelado", "nao_compareceu"}),
}

# ---------------------------------------------------------------------------
# Eventos do ledger
# ---------------------------------------------------------------------------

EVENTOS_AGENDAMENTO: frozenset[str] = frozenset({
    "agendamento_criado",
    "agendamento_confirmado",
    "agendamento_realizado",
    "agendamento_cancelado",
    "agendamento_nao_compareceu",
    "agendamento_remarcado",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def eh_terminal(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_AGENDAMENTO


def transicao_valida(de: str, para: str) -> bool:
    """Retorna True se a transição de → para é permitida."""
    return para in TRANSICOES_AGENDAMENTO.get(de, frozenset())


def validar_transicao(de: str, para: str) -> None:
    """Levanta ValueError se a transição é inválida."""
    if eh_terminal(de):
        raise ValueError(
            f"Agendamento em estado terminal '{de}' não pode ser alterado."
        )
    if not transicao_valida(de, para):
        validas = sorted(TRANSICOES_AGENDAMENTO.get(de, frozenset()))
        raise ValueError(
            f"Transição '{de}' → '{para}' não é permitida. "
            f"Transições válidas a partir de '{de}': {validas}"
        )
