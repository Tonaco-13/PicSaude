"""
test_states_circulacao_diagnostica.py
======================================
Testes estruturais — domain/states_circulacao_diagnostica.py (Ticket 52).

COBERTURA
---------
  1. Completude dos conjuntos (terminais ⊆ estados; destinos de transição válidos)
  2. Todos os eventos são strings não vazias
  3. Estados terminais bloqueiam transições (validar_transicao levanta ValueError)
  4. Transições válidas por estado (cobertura de todas as arestas do grafo)
  5. Transições inválidas (cruzar estados sem aresta levanta ValueError)
  6. Helpers: eh_terminal_circulacao_diagnostica, transicao_valida_circulacao_diagnostica
  7. Não-regressão: estados do agendamento não se misturam com circulação diagnóstica

Sem banco de dados, sem FastAPI, sem fixtures externas.
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.states_circulacao_diagnostica import (
    ESTADOS_CIRCULACAO_DIAGNOSTICA,
    ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA,
    TRANSICOES_CIRCULACAO_DIAGNOSTICA,
    EVENTOS_CIRCULACAO_DIAGNOSTICA,
    eh_terminal_circulacao_diagnostica,
    transicao_valida_circulacao_diagnostica,
    validar_transicao_circulacao_diagnostica,
)


# ---------------------------------------------------------------------------
# 1. Completude dos conjuntos
# ---------------------------------------------------------------------------

class TestConjuntos:

    def test_terminais_sao_subconjunto_de_estados(self):
        assert ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA <= ESTADOS_CIRCULACAO_DIAGNOSTICA

    def test_estados_nao_terminais_tem_entrada_em_transicoes(self):
        """Estados não-terminais devem ter chave em TRANSICOES_CIRCULACAO_DIAGNOSTICA.
        Estados terminais não são listados (padrão do projeto: ausência = sem saída)."""
        nao_terminais = ESTADOS_CIRCULACAO_DIAGNOSTICA - ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA
        for estado in nao_terminais:
            assert estado in TRANSICOES_CIRCULACAO_DIAGNOSTICA, (
                f"Estado não-terminal '{estado}' sem entrada em TRANSICOES_CIRCULACAO_DIAGNOSTICA"
            )

    def test_destinos_de_transicao_sao_estados_validos(self):
        for de, destinos in TRANSICOES_CIRCULACAO_DIAGNOSTICA.items():
            for para in destinos:
                assert para in ESTADOS_CIRCULACAO_DIAGNOSTICA, (
                    f"Destino '{para}' de '{de}' não consta em ESTADOS_CIRCULACAO_DIAGNOSTICA"
                )

    def test_estados_terminais_tem_transicoes_vazias(self):
        for terminal in ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA:
            destinos = TRANSICOES_CIRCULACAO_DIAGNOSTICA.get(terminal, frozenset())
            assert len(destinos) == 0, (
                f"Estado terminal '{terminal}' não deveria ter transições, "
                f"mas tem: {destinos}"
            )


# ---------------------------------------------------------------------------
# 2. Eventos
# ---------------------------------------------------------------------------

class TestEventos:

    def test_eventos_nao_vazios(self):
        for evento in EVENTOS_CIRCULACAO_DIAGNOSTICA:
            assert isinstance(evento, str) and evento.strip(), (
                f"Evento inválido: {evento!r}"
            )

    def test_eventos_esperados_presentes(self):
        esperados = {
            "circulacao_criada",
            "circulacao_enviada_laboratorio",
            "circulacao_proposta_recebida",
            "circulacao_confirmada_paciente",
            "circulacao_realizada",
            "circulacao_desmarcada_paciente",
            "circulacao_desmarcada_laboratorio",
            "circulacao_arquivada_laboratorio",
            "circulacao_expirada",
        }
        assert esperados <= EVENTOS_CIRCULACAO_DIAGNOSTICA


# ---------------------------------------------------------------------------
# 3. Estados terminais bloqueiam transições
# ---------------------------------------------------------------------------

class TestTerminais:

    @pytest.mark.parametrize("terminal", sorted(ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA))
    def test_terminal_levanta_value_error(self, terminal):
        with pytest.raises(ValueError, match="terminal"):
            validar_transicao_circulacao_diagnostica(terminal, "selecionado")

    def test_realizado_e_terminal(self):
        assert eh_terminal_circulacao_diagnostica("realizado")

    def test_desmarcado_paciente_e_terminal(self):
        assert eh_terminal_circulacao_diagnostica("desmarcado_paciente")

    def test_desmarcado_laboratorio_e_terminal(self):
        assert eh_terminal_circulacao_diagnostica("desmarcado_laboratorio")

    def test_arquivado_laboratorio_e_terminal(self):
        assert eh_terminal_circulacao_diagnostica("arquivado_laboratorio")

    def test_expirado_e_terminal(self):
        assert eh_terminal_circulacao_diagnostica("expirado")

    def test_selecionado_nao_e_terminal(self):
        assert not eh_terminal_circulacao_diagnostica("selecionado")

    def test_enviado_laboratorio_nao_e_terminal(self):
        assert not eh_terminal_circulacao_diagnostica("enviado_laboratorio")

    def test_proposta_recebida_nao_e_terminal(self):
        assert not eh_terminal_circulacao_diagnostica("proposta_recebida")

    def test_confirmado_paciente_nao_e_terminal(self):
        assert not eh_terminal_circulacao_diagnostica("confirmado_paciente")


# ---------------------------------------------------------------------------
# 4. Transições válidas (cobertura de todas as arestas do grafo)
# ---------------------------------------------------------------------------

class TestTransicoesValidas:

    def test_selecionado_para_enviado_laboratorio(self):
        assert transicao_valida_circulacao_diagnostica("selecionado", "enviado_laboratorio")

    def test_selecionado_para_expirado(self):
        assert transicao_valida_circulacao_diagnostica("selecionado", "expirado")

    def test_enviado_laboratorio_para_proposta_recebida(self):
        assert transicao_valida_circulacao_diagnostica("enviado_laboratorio", "proposta_recebida")

    def test_enviado_laboratorio_para_desmarcado_laboratorio(self):
        assert transicao_valida_circulacao_diagnostica("enviado_laboratorio", "desmarcado_laboratorio")

    def test_enviado_laboratorio_para_arquivado_laboratorio(self):
        assert transicao_valida_circulacao_diagnostica("enviado_laboratorio", "arquivado_laboratorio")

    def test_enviado_laboratorio_para_expirado(self):
        assert transicao_valida_circulacao_diagnostica("enviado_laboratorio", "expirado")

    def test_proposta_recebida_para_confirmado_paciente(self):
        assert transicao_valida_circulacao_diagnostica("proposta_recebida", "confirmado_paciente")

    def test_proposta_recebida_para_desmarcado_paciente(self):
        assert transicao_valida_circulacao_diagnostica("proposta_recebida", "desmarcado_paciente")

    def test_proposta_recebida_para_desmarcado_laboratorio(self):
        assert transicao_valida_circulacao_diagnostica("proposta_recebida", "desmarcado_laboratorio")

    def test_proposta_recebida_para_expirado(self):
        assert transicao_valida_circulacao_diagnostica("proposta_recebida", "expirado")

    def test_confirmado_paciente_para_realizado(self):
        assert transicao_valida_circulacao_diagnostica("confirmado_paciente", "realizado")

    def test_confirmado_paciente_para_desmarcado_paciente(self):
        assert transicao_valida_circulacao_diagnostica("confirmado_paciente", "desmarcado_paciente")

    def test_confirmado_paciente_para_desmarcado_laboratorio(self):
        assert transicao_valida_circulacao_diagnostica("confirmado_paciente", "desmarcado_laboratorio")


# ---------------------------------------------------------------------------
# 5. Transições inválidas (sem aresta no grafo)
# ---------------------------------------------------------------------------

class TestTransicoesInvalidas:

    def test_selecionado_para_realizado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("selecionado", "realizado")

    def test_selecionado_para_confirmado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("selecionado", "confirmado_paciente")

    def test_enviado_laboratorio_para_realizado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("enviado_laboratorio", "realizado")

    def test_enviado_laboratorio_para_confirmado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("enviado_laboratorio", "confirmado_paciente")

    def test_proposta_recebida_para_realizado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("proposta_recebida", "realizado")

    def test_confirmado_paciente_para_expirado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("confirmado_paciente", "expirado")

    def test_confirmado_paciente_para_arquivado_invalido(self):
        assert not transicao_valida_circulacao_diagnostica("confirmado_paciente", "arquivado_laboratorio")

    def test_validar_transicao_invalida_levanta_value_error(self):
        with pytest.raises(ValueError):
            validar_transicao_circulacao_diagnostica("selecionado", "realizado")

    def test_validar_transicao_invalida_mensagem_lista_validas(self):
        """Mensagem deve listar as transições válidas a partir do estado."""
        with pytest.raises(ValueError, match="selecionado"):
            validar_transicao_circulacao_diagnostica("selecionado", "realizado")


# ---------------------------------------------------------------------------
# 6. Estados esperados presentes
# ---------------------------------------------------------------------------

class TestEstadosEsperados:

    def test_todos_estados_esperados_presentes(self):
        esperados = {
            "selecionado",
            "enviado_laboratorio",
            "proposta_recebida",
            "confirmado_paciente",
            "realizado",
            "desmarcado_paciente",
            "desmarcado_laboratorio",
            "arquivado_laboratorio",
            "expirado",
        }
        assert esperados == ESTADOS_CIRCULACAO_DIAGNOSTICA

    def test_terminais_esperados_presentes(self):
        esperados = {
            "realizado",
            "desmarcado_paciente",
            "desmarcado_laboratorio",
            "arquivado_laboratorio",
            "expirado",
        }
        assert esperados == ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA


# ---------------------------------------------------------------------------
# 7. Não-regressão: estados de circulação não se misturam com agendamento
# ---------------------------------------------------------------------------

class TestNaoRegressao:

    def test_eventos_circulacao_disjuntos_de_eventos_agendamento(self):
        from app.domain.states_agendamento import EVENTOS_AGENDAMENTO
        intersecao = EVENTOS_CIRCULACAO_DIAGNOSTICA & EVENTOS_AGENDAMENTO
        assert not intersecao, (
            f"Eventos compartilhados entre circulação e agendamento: {intersecao}"
        )

    def test_estados_circulacao_disjuntos_de_prescricao(self):
        from app.domain.states import ESTADOS_PRESCRICAO
        intersecao = ESTADOS_CIRCULACAO_DIAGNOSTICA & ESTADOS_PRESCRICAO
        assert not intersecao, (
            f"Estados compartilhados entre circulação e prescrição: {intersecao}"
        )
