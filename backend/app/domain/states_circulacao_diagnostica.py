"""
states_circulacao_diagnostica.py
================================
Contrato de estados do módulo de Circulação Diagnóstica (Ticket 51–57).

Classificação do objeto: objeto sanitário — tem identidade própria (UUID),
chave de circulação, máquina de estados e ledger próprios. Antecede e pode
gerar um agendamento concreto.

Fonte de verdade para:
  - circulacao_diagnostica.status
  - transições válidas
  - estados terminais

Referência arquitetural: docs/ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md §7
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Estados válidos
# ---------------------------------------------------------------------------

ESTADOS_CIRCULACAO_DIAGNOSTICA: frozenset[str] = frozenset({
    "selecionado",           # paciente selecionou itens; chave gerada, não enviada
    "enviado_laboratorio",   # paciente apresentou a chave ao laboratório
    "proposta_recebida",     # laboratório propôs data, hora, unidade e preparo
    "confirmado_paciente",   # paciente aceitou a proposta
    "realizado",             # laboratório registrou a coleta                [terminal]
    "desmarcado_paciente",   # paciente desmarcou antes ou após confirmação  [terminal]
    "desmarcado_laboratorio", # laboratório desmarcou                        [terminal]
    "arquivado_laboratorio", # laboratório arquivou sem proposta ou após insucesso [terminal]
    "expirado",              # validade da chave ultrapassada                [terminal]
})

ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA: frozenset[str] = frozenset({
    "realizado",
    "desmarcado_paciente",
    "desmarcado_laboratorio",
    "arquivado_laboratorio",
    "expirado",
})

# ---------------------------------------------------------------------------
# Transições permitidas
# De → {para...}
# ---------------------------------------------------------------------------

TRANSICOES_CIRCULACAO_DIAGNOSTICA: dict[str, frozenset[str]] = {
    "selecionado": frozenset({
        "enviado_laboratorio",
        "expirado",
    }),
    "enviado_laboratorio": frozenset({
        "proposta_recebida",
        "desmarcado_laboratorio",
        "arquivado_laboratorio",
        "expirado",
    }),
    "proposta_recebida": frozenset({
        "confirmado_paciente",
        "desmarcado_paciente",
        "desmarcado_laboratorio",
        "expirado",
    }),
    "confirmado_paciente": frozenset({
        "realizado",
        "desmarcado_paciente",
        "desmarcado_laboratorio",
    }),
}

# ---------------------------------------------------------------------------
# Eventos do ledger
# ---------------------------------------------------------------------------

EVENTOS_CIRCULACAO_DIAGNOSTICA: frozenset[str] = frozenset({
    "circulacao_criada",
    "circulacao_enviada_laboratorio",
    "circulacao_proposta_recebida",
    "circulacao_confirmada_paciente",
    "circulacao_realizada",
    "circulacao_desmarcada_paciente",
    "circulacao_desmarcada_laboratorio",
    "circulacao_arquivada_laboratorio",
    "circulacao_expirada",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def eh_terminal_circulacao_diagnostica(status: str) -> bool:
    """Retorna True se o status da circulação diagnóstica for terminal."""
    return status in ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA


def transicao_valida_circulacao_diagnostica(de: str, para: str) -> bool:
    """Retorna True se a transição de → para é permitida."""
    return para in TRANSICOES_CIRCULACAO_DIAGNOSTICA.get(de, frozenset())


def validar_transicao_circulacao_diagnostica(de: str, para: str) -> None:
    """Levanta ValueError se a transição é inválida."""
    if eh_terminal_circulacao_diagnostica(de):
        raise ValueError(
            f"Circulação diagnóstica em estado terminal '{de}' não pode ser alterada."
        )
    if not transicao_valida_circulacao_diagnostica(de, para):
        validas = sorted(TRANSICOES_CIRCULACAO_DIAGNOSTICA.get(de, frozenset()))
        raise ValueError(
            f"Transição '{de}' → '{para}' não é permitida. "
            f"Transições válidas a partir de '{de}': {validas}"
        )
