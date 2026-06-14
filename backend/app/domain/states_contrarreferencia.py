"""
PicSaúde — Contrato de Estados: Contrarreferência
=================================================
Objeto sanitário DERIVADO do Encaminhamento (E2). É o retorno clínico do
prescritor de destino.

tipo_agregacao_status = "direto" (sem itens no MVP).

Máquina mínima (decisão R, 2026-06-08): a *ciência da origem* é carregada pelo
PARENT (encaminhamento: `contrarreferido → encerrado` via /encerrar), não
duplicada aqui. A contrarreferência nasce `registrada`; `cancelada` é o único
outro terminal (forward-compat — sem endpoint de cancelamento no E2).
"""

from __future__ import annotations

from typing import Literal


EstadoContrarreferencia = Literal[
    "registrada",
    "cancelada",
]

ESTADOS_CONTRARREFERENCIA: frozenset[str] = frozenset({
    "registrada",
    "cancelada",
})

ESTADOS_TERMINAIS_CONTRARREFERENCIA: frozenset[str] = frozenset({
    "cancelada",
})

TRANSICOES_CONTRARREFERENCIA: dict[str, frozenset[str]] = {
    "registrada": frozenset({"cancelada"}),
    "cancelada":  frozenset(),
}


def transicao_valida_contrarreferencia(de: str, para: str) -> bool:
    return para in TRANSICOES_CONTRARREFERENCIA.get(de, frozenset())


def eh_terminal_contrarreferencia(status: str) -> bool:
    return status in ESTADOS_TERMINAIS_CONTRARREFERENCIA
