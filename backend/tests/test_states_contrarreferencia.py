"""
test_states_contrarreferencia.py
================================
Testes estruturais — domain/states_contrarreferencia.py (TICKET-ENCAMINHAMENTO-E2).

Exercita o contrato de estados da contrarreferência (máquina mínima R:
`registrada · cancelada`) para que ele não seja contrato morto: completude dos
conjuntos, terminais sem saída, e os helpers `transicao_valida_*`/`eh_terminal_*`.
O `origem_contrarreferencia_id` + o estado `cancelada` ficam de gancho para o
futuro endpoint de cancelar/derivar — este teste garante que o guard estará
correto quando esse endpoint chegar.

Sem banco, sem FastAPI, sem fixtures.
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.states_contrarreferencia import (
    ESTADOS_CONTRARREFERENCIA,
    ESTADOS_TERMINAIS_CONTRARREFERENCIA,
    TRANSICOES_CONTRARREFERENCIA,
    eh_terminal_contrarreferencia,
    transicao_valida_contrarreferencia,
)


class TestConjuntos:

    def test_estados_esperados(self):
        assert ESTADOS_CONTRARREFERENCIA == {"registrada", "cancelada"}

    def test_terminais_esperados(self):
        assert ESTADOS_TERMINAIS_CONTRARREFERENCIA == {"cancelada"}

    def test_terminais_sao_subconjunto_de_estados(self):
        assert ESTADOS_TERMINAIS_CONTRARREFERENCIA <= ESTADOS_CONTRARREFERENCIA

    def test_nao_terminais_tem_entrada_em_transicoes(self):
        nao_terminais = ESTADOS_CONTRARREFERENCIA - ESTADOS_TERMINAIS_CONTRARREFERENCIA
        for estado in nao_terminais:
            assert estado in TRANSICOES_CONTRARREFERENCIA

    def test_destinos_de_transicao_sao_estados_validos(self):
        for de, destinos in TRANSICOES_CONTRARREFERENCIA.items():
            for para in destinos:
                assert para in ESTADOS_CONTRARREFERENCIA

    def test_terminais_tem_transicoes_vazias(self):
        for terminal in ESTADOS_TERMINAIS_CONTRARREFERENCIA:
            assert len(TRANSICOES_CONTRARREFERENCIA.get(terminal, frozenset())) == 0


class TestTransicoes:

    def test_registrada_para_cancelada_valida(self):
        assert transicao_valida_contrarreferencia("registrada", "cancelada")

    def test_cancelada_nao_reabre(self):
        assert not transicao_valida_contrarreferencia("cancelada", "registrada")

    def test_registrada_para_registrada_invalida(self):
        assert not transicao_valida_contrarreferencia("registrada", "registrada")

    def test_estado_desconhecido_sem_transicao(self):
        assert not transicao_valida_contrarreferencia("inexistente", "cancelada")


class TestTerminais:

    def test_cancelada_e_terminal(self):
        assert eh_terminal_contrarreferencia("cancelada")

    def test_registrada_nao_e_terminal(self):
        assert not eh_terminal_contrarreferencia("registrada")


class TestNaoRegressao:

    def test_estados_disjuntos_do_encaminhamento(self):
        # 'cancelada' (contrarreferência) ≠ 'cancelado' (encaminhamento) — sem colisão
        from app.domain.states_encaminhamento import ESTADOS_ENCAMINHAMENTO
        assert not (ESTADOS_CONTRARREFERENCIA & ESTADOS_ENCAMINHAMENTO)
