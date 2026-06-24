"""
PicSaúde — Contrato de Estados: Atestado Médico
=================================================
Espelho de states.py para o domínio de atestados.

REGRA: nenhum router, model ou migration deve introduzir um novo estado
sem atualizar este arquivo, a seção 7 do CLAUDE.md e docs/ARQUITETURA_ATESTADO.md.

Diferença essencial: o atestado é um objeto **MONOLÍTICO** — um documento único,
sem itens (diferente de prescrição/exame). Logo não há `status_item` nem derivação
por itens: o status é direto. (Exceção documentada ao núcleo, como o agendamento.)
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Tipos literais
# ---------------------------------------------------------------------------

EstadoAtestado = Literal[
    "emitido",               # criado digitalmente, entregue ao paciente
    "assinado",              # assinatura ICP-Brasil (PAdES) aplicada
    "cancelado",             # terminal — revogação clínica
    "expirado",              # terminal — período do atestado ultrapassado
    "encerrada_localmente",  # terminal — emissão exclusivamente física
]

# ---------------------------------------------------------------------------
# Estados de Atestado  (atestados.status)
# ---------------------------------------------------------------------------

ESTADOS_ATESTADO: frozenset[str] = frozenset({
    "emitido",
    "assinado",
    "cancelado",              # terminal
    "expirado",               # terminal
    "encerrada_localmente",   # terminal — fluxo físico
})

ESTADOS_TERMINAIS_ATESTADO: frozenset[str] = frozenset({
    "cancelado",
    "expirado",
    "encerrada_localmente",
})

# ---------------------------------------------------------------------------
# Transições válidas
# ---------------------------------------------------------------------------

TRANSICOES_ATESTADO: dict[str, frozenset[str]] = {
    "emitido":              frozenset({"assinado", "cancelado", "expirado"}),
    "assinado":             frozenset({"cancelado", "expirado"}),
    "cancelado":            frozenset(),   # terminal
    "expirado":             frozenset(),   # terminal
    "encerrada_localmente": frozenset(),   # terminal — fluxo físico
}

# ---------------------------------------------------------------------------
# Vocabulário de eventos no ledger  (atestado_eventos.tipo_evento)
# ---------------------------------------------------------------------------

EVENTOS_ATESTADO: frozenset[str] = frozenset({
    "atestado_emitido",        # emissão digital
    "atestado_assinado",       # PDF assinado em ICP-Brasil (PAdES)
    "atestado_corrigido",      # derivação por correção (origem_atestado_id)
    "atestado_cancelado",      # revogação clínica
    "atestado_expirado",       # período ultrapassado
    "atestado_impresso",       # fluxo físico — ato de impressão
    "encerrada_localmente",    # fluxo físico — status terminal (mesmo nome da prescrição)
    "custodia_transferida",    # transferência de posse (emissão: prescritor → paciente)
})

# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

def transicao_valida_atestado(de: str, para: str) -> bool:
    return para in TRANSICOES_ATESTADO.get(de, frozenset())


def eh_terminal_atestado(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ATESTADO
