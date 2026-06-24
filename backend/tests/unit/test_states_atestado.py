"""Contrato de estados do atestado (monolítico — sem itens)."""
from __future__ import annotations

from app.domain.states_atestado import (
    ESTADOS_ATESTADO,
    ESTADOS_TERMINAIS_ATESTADO,
    EVENTOS_ATESTADO,
    TRANSICOES_ATESTADO,
    eh_terminal_atestado,
    transicao_valida_atestado,
)


def test_emitido_transiciona_para_assinado_cancelado_expirado():
    assert transicao_valida_atestado("emitido", "assinado")
    assert transicao_valida_atestado("emitido", "cancelado")
    assert transicao_valida_atestado("emitido", "expirado")


def test_assinado_ainda_pode_ser_revogado_ou_expirar():
    assert transicao_valida_atestado("assinado", "cancelado")
    assert transicao_valida_atestado("assinado", "expirado")
    # mas não "desassina"
    assert not transicao_valida_atestado("assinado", "emitido")


def test_terminais_nao_transicionam():
    for t in ("cancelado", "expirado", "encerrada_localmente"):
        assert eh_terminal_atestado(t)
        assert TRANSICOES_ATESTADO[t] == frozenset()


def test_emitido_nao_e_terminal():
    assert not eh_terminal_atestado("emitido")
    assert not eh_terminal_atestado("assinado")


def test_transicao_invalida_e_falsa():
    assert not transicao_valida_atestado("emitido", "encerrada_localmente")  # físico não vem do digital
    assert not transicao_valida_atestado("cancelado", "assinado")
    assert not transicao_valida_atestado("emitido", "estado_inexistente")


def test_todas_as_transicoes_apontam_para_estados_validos():
    for origem, destinos in TRANSICOES_ATESTADO.items():
        assert origem in ESTADOS_ATESTADO
        for d in destinos:
            assert d in ESTADOS_ATESTADO


def test_vocabulario_de_eventos_minimo():
    for ev in ("atestado_emitido", "atestado_assinado", "atestado_cancelado",
               "atestado_impresso", "encerrada_localmente", "custodia_transferida"):
        assert ev in EVENTOS_ATESTADO
