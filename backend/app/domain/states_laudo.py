"""
PicSaúde — Contrato de Estados: Laudo
======================================
Espelho de states.py para o domínio de laudos.

DIFERENÇA FUNDAMENTAL em relação a prescrição e pedido de exame:
    tipo_agregacao_status = "direto"

O laudo tem transições no nível do OBJETO, não derivadas dos itens.
Isso ocorre porque ciência, assinatura e liberação são operações sobre o
laudo inteiro, não sobre itens individuais.

Documentação desta exceção: docs/ARQUITETURA_LAUDO.md (Refinamento 2)
Contrato do núcleo: docs/NUCLEO_SANITARIO.md (seção 3 — tipo_agregacao_status)

REGRA: nenhum router, model ou migration deve introduzir um novo estado
sem atualizar este arquivo, a seção 7 do CLAUDE.md e docs/ARQUITETURA_LAUDO.md.
"""

from __future__ import annotations

from typing import Literal

# ---------------------------------------------------------------------------
# Tipos literais
# ---------------------------------------------------------------------------

EstadoLaudo = Literal[
    "em_producao",
    "assinado",
    "liberado",
    "ciencia_paciente",
    "ciencia_prescritor",
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
]

EstadoItemLaudo = Literal[
    "em_producao",
    "concluido",
    "cancelado",
    "encerrado_fisico",
]

# ---------------------------------------------------------------------------
# Estados de Laudo  (laudos.status)
# ---------------------------------------------------------------------------

ESTADOS_LAUDO: frozenset[str] = frozenset({
    "em_producao",
    "assinado",
    "liberado",
    "ciencia_paciente",
    "ciencia_prescritor",
    "encerrado",          # terminal
    "cancelado",          # terminal
    "expirado",           # terminal
    "encerrado_fisico",   # terminal — fluxo físico
})

ESTADOS_TERMINAIS_LAUDO: frozenset[str] = frozenset({
    "encerrado",
    "cancelado",
    "expirado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Laudo
# (tipo_agregacao_status = "direto" — transições controladas pelos endpoints)
# ---------------------------------------------------------------------------

TRANSICOES_LAUDO: dict[str, frozenset[str]] = {
    "em_producao":        frozenset({"assinado", "cancelado"}),
    "assinado":           frozenset({"liberado", "cancelado"}),
    "liberado":           frozenset({"ciencia_paciente", "ciencia_prescritor", "encerrado", "cancelado"}),
    "ciencia_paciente":   frozenset({"ciencia_prescritor", "encerrado"}),
    "ciencia_prescritor": frozenset({"ciencia_paciente", "encerrado"}),
    "encerrado":          frozenset(),   # terminal
    "cancelado":          frozenset(),   # terminal
    "expirado":           frozenset(),   # terminal
    "encerrado_fisico":   frozenset(),   # terminal — fluxo físico
}

# ---------------------------------------------------------------------------
# Estados de Item do Laudo  (laudo_itens.status_item)
# ---------------------------------------------------------------------------

ESTADOS_ITEM_LAUDO: frozenset[str] = frozenset({
    "em_producao",
    "concluido",          # terminal de fluxo normal
    "cancelado",          # terminal
    "encerrado_fisico",   # terminal — fluxo físico
})

ESTADOS_TERMINAIS_ITEM_LAUDO: frozenset[str] = frozenset({
    "concluido",
    "cancelado",
    "encerrado_fisico",
})

# ---------------------------------------------------------------------------
# Transições válidas de Item do Laudo
# ---------------------------------------------------------------------------

TRANSICOES_ITEM_LAUDO: dict[str, frozenset[str]] = {
    "em_producao":    frozenset({"concluido", "cancelado"}),
    "concluido":      frozenset(),   # terminal
    "cancelado":      frozenset(),   # terminal
    "encerrado_fisico": frozenset(), # terminal
}

# ---------------------------------------------------------------------------
# Vocabulário de eventos no ledger  (laudo_eventos.tipo_evento)
# ---------------------------------------------------------------------------

EVENTOS_LAUDO: frozenset[str] = frozenset({
    "laudo_criado",           # emissão digital
    "laudo_impresso",         # fluxo físico — ato de impressão
    "encerrado_localmente",   # fluxo físico — estado terminal (padrão do núcleo)
    "laudo_assinado",         # responsável técnico declarou assinatura
    "laudo_liberado",         # laudo disponibilizado ao paciente/prescritor
    "ciencia_paciente",       # paciente registrou ciência
    "ciencia_prescritor",     # prescritor registrou ciência clínica
    "laudo_encerrado",        # ciclo completo
    "laudo_cancelado",        # cancelamento
    "laudo_expirado",         # validade ultrapassada
    "custodia_transferida",   # qualquer transferência de posse
    "laudo_corrigido",        # derivação por correção (novo laudo com origem_laudo_id)
    # ENG-014 (PR C) — martelo (a) do Fabiano, 20/08: "abrir o laudo = dar
    # ciência". O evento nomeia a ABERTURA, que é o fato real; a ciência é
    # consequência DERIVADA. O ledger fica honesto — "abriu em X → ciência
    # derivada da abertura" —, nunca uma "ciência" anunciando fato que não
    # ocorreu (a lição do `pedido_agendado` fantasma do J.7).
    "laudo_aberto_paciente",  # cidadão abriu o laudo (carimba laudos.aberto_em)
})

# ---------------------------------------------------------------------------
# Helpers de validação
# ---------------------------------------------------------------------------

def transicao_valida_laudo(de: str, para: str) -> bool:
    return para in TRANSICOES_LAUDO.get(de, frozenset())


def transicao_valida_item_laudo(de: str, para: str) -> bool:
    return para in TRANSICOES_ITEM_LAUDO.get(de, frozenset())


def eh_terminal_laudo(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_LAUDO


def eh_terminal_item_laudo(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_ITEM_LAUDO


# ---------------------------------------------------------------------------
# Nota sobre derivar_status_laudo
# ---------------------------------------------------------------------------
# O laudo usa tipo_agregacao_status = "direto".
# Não há função derivar_status_laudo() — o status é transitado explicitamente
# pelos endpoints de negócio (/assinar, /liberar, /ciencia-*, /encerrar).
# Ver: docs/NUCLEO_SANITARIO.md seção 3 e docs/ARQUITETURA_LAUDO.md Refinamento 2.
