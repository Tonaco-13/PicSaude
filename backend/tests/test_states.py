"""
Testes unitários — domain/states.py (Camada 1)

Cobrem exclusivamente a lógica pura do contrato de estados:
  - conjuntos de estados válidos
  - identificação de terminais
  - transições permitidas e proibidas
  - eventos obrigatórios por transição

Sem banco de dados, sem FastAPI, sem fixtures externas.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.states import (
    ESTADOS_PRESCRICAO,
    ESTADOS_TERMINAIS_PRESCRICAO,
    TRANSICOES_PRESCRICAO,
    EVENTOS_PRESCRICAO,
    ESTADOS_ITEM,
    ESTADOS_TERMINAIS_ITEM,
    TRANSICOES_ITEM,
    EVENTOS_ITEM,
    transicao_valida_prescricao,
    transicao_valida_item,
    eh_terminal_prescricao,
    eh_terminal_item,
    evento_obrigatorio_prescricao,
    evento_obrigatorio_item,
)


# ---------------------------------------------------------------------------
# 1. Completude dos conjuntos
# ---------------------------------------------------------------------------

class TestConjuntos:

    def test_terminais_prescricao_sao_subconjunto_de_estados(self):
        assert ESTADOS_TERMINAIS_PRESCRICAO <= ESTADOS_PRESCRICAO

    def test_terminais_item_sao_subconjunto_de_estados(self):
        assert ESTADOS_TERMINAIS_ITEM <= ESTADOS_ITEM

    def test_transicoes_prescricao_cobrem_todos_os_estados(self):
        """Todo estado deve ter entrada em TRANSICOES_PRESCRICAO (mesmo que vazia)."""
        for estado in ESTADOS_PRESCRICAO:
            assert estado in TRANSICOES_PRESCRICAO, f"Estado '{estado}' sem entrada em TRANSICOES_PRESCRICAO"

    def test_transicoes_item_cobrem_todos_os_estados(self):
        for estado in ESTADOS_ITEM:
            assert estado in TRANSICOES_ITEM, f"Estado '{estado}' sem entrada em TRANSICOES_ITEM"

    def test_destinos_de_transicao_prescricao_sao_estados_validos(self):
        for de, destinos in TRANSICOES_PRESCRICAO.items():
            for para in destinos:
                assert para in ESTADOS_PRESCRICAO, (
                    f"Destino '{para}' de '{de}' não consta em ESTADOS_PRESCRICAO"
                )

    def test_destinos_de_transicao_item_sao_estados_validos(self):
        for de, destinos in TRANSICOES_ITEM.items():
            for para in destinos:
                assert para in ESTADOS_ITEM, (
                    f"Destino '{para}' de '{de}' não consta em ESTADOS_ITEM"
                )

    def test_eventos_prescricao_referenciam_estados_validos(self):
        for (de, para) in EVENTOS_PRESCRICAO:
            assert de in ESTADOS_PRESCRICAO, f"Evento com estado-de '{de}' inválido"
            assert para in ESTADOS_PRESCRICAO, f"Evento com estado-para '{para}' inválido"

    def test_eventos_item_referenciam_estados_validos(self):
        for (de, para) in EVENTOS_ITEM:
            assert de in ESTADOS_ITEM, f"Evento com estado-de '{de}' inválido"
            assert para in ESTADOS_ITEM, f"Evento com estado-para '{para}' inválido"


# ---------------------------------------------------------------------------
# 2. Estados terminais
# ---------------------------------------------------------------------------

class TestTerminais:

    @pytest.mark.parametrize("status", [
        "dispensada", "cancelada", "expirada", "encerrada_localmente"
    ])
    def test_prescricao_terminal_identificada(self, status):
        assert eh_terminal_prescricao(status) is True

    @pytest.mark.parametrize("status", [
        "pendente", "transferida_paciente", "em_custodia", "parcialmente_dispensada"
    ])
    def test_prescricao_nao_terminal(self, status):
        assert eh_terminal_prescricao(status) is False

    @pytest.mark.parametrize("status", [
        "dispensado", "devolvido_prescritor", "cancelado", "estornado", "encerrado_fisico"
    ])
    def test_item_terminal_identificado(self, status):
        assert eh_terminal_item(status) is True

    @pytest.mark.parametrize("status", [
        "pendente", "em_custodia", "devolvido_paciente"
    ])
    def test_item_nao_terminal(self, status):
        assert eh_terminal_item(status) is False

    def test_terminais_prescricao_tem_frozenset_vazio_em_transicoes(self):
        """Estados terminais não devem ter transições de saída."""
        for terminal in ESTADOS_TERMINAIS_PRESCRICAO:
            assert TRANSICOES_PRESCRICAO[terminal] == frozenset(), (
                f"Terminal '{terminal}' tem transições de saída não-vazias"
            )

    def test_terminais_item_tem_frozenset_vazio_em_transicoes(self):
        # `dispensado` é terminal de negócio mas permite escape para `estornado`
        # (reversão após dispensação). Os demais terminais não têm saída.
        terminais_sem_escape = ESTADOS_TERMINAIS_ITEM - {"dispensado"}
        for terminal in terminais_sem_escape:
            assert TRANSICOES_ITEM[terminal] == frozenset(), (
                f"Terminal '{terminal}' tem transições de saída não-vazias"
            )
        # dispensado só permite estornado
        assert TRANSICOES_ITEM["dispensado"] == frozenset({"estornado"})


# ---------------------------------------------------------------------------
# 3. Transições válidas de Prescrição
# ---------------------------------------------------------------------------

class TestTransicoesPrescricao:

    @pytest.mark.parametrize("de, para", [
        ("pendente",                "transferida_paciente"),
        ("pendente",                "cancelada"),
        ("pendente",                "expirada"),
        ("transferida_paciente",    "em_custodia"),
        ("transferida_paciente",    "cancelada"),
        ("transferida_paciente",    "expirada"),
        ("em_custodia",             "parcialmente_dispensada"),
        ("em_custodia",             "dispensada"),
        ("em_custodia",             "cancelada"),
        ("em_custodia",             "transferida_paciente"),
        ("parcialmente_dispensada", "dispensada"),
        ("parcialmente_dispensada", "cancelada"),
        ("parcialmente_dispensada", "expirada"),
    ])
    def test_transicao_valida(self, de, para):
        assert transicao_valida_prescricao(de, para) is True

    @pytest.mark.parametrize("de, para", [
        # A partir de terminais
        ("dispensada",              "pendente"),
        ("cancelada",               "pendente"),
        ("expirada",                "pendente"),
        ("encerrada_localmente",    "pendente"),
        # Saltos não permitidos
        ("pendente",                "dispensada"),
        ("pendente",                "em_custodia"),
        ("pendente",                "parcialmente_dispensada"),
        ("transferida_paciente",    "dispensada"),
        ("transferida_paciente",    "parcialmente_dispensada"),
        # Semântica errada
        ("encerrada_localmente",    "cancelada"),
        ("dispensada",              "cancelada"),
    ])
    def test_transicao_invalida(self, de, para):
        assert transicao_valida_prescricao(de, para) is False

    def test_estado_desconhecido_retorna_false(self):
        assert transicao_valida_prescricao("inexistente", "pendente") is False
        assert transicao_valida_prescricao("pendente", "inexistente") is False


# ---------------------------------------------------------------------------
# 4. Transições válidas de Item
# ---------------------------------------------------------------------------

class TestTransicoesItem:

    @pytest.mark.parametrize("de, para", [
        ("pendente",           "em_custodia"),
        ("pendente",           "cancelado"),
        ("em_custodia",        "dispensado"),
        ("em_custodia",        "devolvido_paciente"),
        ("em_custodia",        "devolvido_prescritor"),
        ("em_custodia",        "cancelado"),
        ("devolvido_paciente", "em_custodia"),
        ("devolvido_paciente", "cancelado"),
        ("devolvido_paciente", "devolvido_prescritor"),  # COER2-POS-MERGE-FIX
        ("dispensado",         "estornado"),
    ])
    def test_transicao_valida(self, de, para):
        assert transicao_valida_item(de, para) is True

    @pytest.mark.parametrize("de, para", [
        # A partir de terminais
        ("dispensado",          "pendente"),
        ("cancelado",           "pendente"),
        ("estornado",           "pendente"),
        ("encerrado_fisico",    "pendente"),
        ("encerrado_fisico",    "em_custodia"),
        ("devolvido_prescritor","em_custodia"),
        ("devolvido_prescritor","dispensado"),
        # Saltos não permitidos
        ("pendente",            "dispensado"),
        ("pendente",            "devolvido_paciente"),
        ("pendente",            "estornado"),
    ])
    def test_transicao_invalida(self, de, para):
        assert transicao_valida_item(de, para) is False

    def test_encerrado_fisico_nao_tem_saida(self):
        """encerrado_fisico nunca volta ao ciclo digital — regra semântica crítica."""
        for destino in ESTADOS_ITEM:
            assert transicao_valida_item("encerrado_fisico", destino) is False

    def test_devolvido_prescritor_nao_pode_ser_dispensado(self):
        """Item devolvido ao prescritor por erro não pode seguir para dispensação."""
        assert transicao_valida_item("devolvido_prescritor", "dispensado") is False

    def test_devolvido_paciente_pode_retry(self):
        """Abandono de balcão permite nova tentativa."""
        assert transicao_valida_item("devolvido_paciente", "em_custodia") is True

    def test_dispensado_so_permite_estorno(self):
        """Após dispensação, apenas estorno é permitido."""
        for destino in ESTADOS_ITEM - {"estornado"}:
            assert transicao_valida_item("dispensado", destino) is False
        assert transicao_valida_item("dispensado", "estornado") is True


# ---------------------------------------------------------------------------
# 5. Eventos obrigatórios
# ---------------------------------------------------------------------------

class TestEventos:

    @pytest.mark.parametrize("de, para, evento_esperado", [
        ("pendente",                "transferida_paciente",    "custodia_transferida"),
        ("pendente",                "cancelada",               "prescricao_cancelada"),
        ("pendente",                "expirada",                "prescricao_expirada"),
        ("transferida_paciente",    "em_custodia",             "custodia_transferida"),
        ("em_custodia",             "parcialmente_dispensada", "dispensacao_parcial"),
        ("em_custodia",             "dispensada",              "dispensacao_registrada"),
        ("em_custodia",             "cancelada",               "prescricao_cancelada"),
        ("em_custodia",             "transferida_paciente",    "custodia_transferida"),
        ("parcialmente_dispensada", "dispensada",              "dispensacao_registrada"),
        ("parcialmente_dispensada", "cancelada",               "prescricao_cancelada"),
        ("parcialmente_dispensada", "expirada",                "prescricao_expirada"),
    ])
    def test_evento_prescricao(self, de, para, evento_esperado):
        assert evento_obrigatorio_prescricao(de, para) == evento_esperado

    @pytest.mark.parametrize("de, para, evento_esperado", [
        ("pendente",           "em_custodia",          "custodia_transferida"),
        ("pendente",           "cancelado",            "item_cancelado"),
        ("em_custodia",        "dispensado",           "item_dispensado"),
        ("em_custodia",        "devolvido_paciente",   "item_devolvido_paciente"),
        ("em_custodia",        "devolvido_prescritor", "item_devolvido_prescritor"),
        ("em_custodia",        "cancelado",            "item_cancelado"),
        ("devolvido_paciente", "em_custodia",          "custodia_transferida"),
        ("devolvido_paciente", "cancelado",            "item_cancelado"),
        ("devolvido_paciente", "devolvido_prescritor", "item_devolvido_prescritor"),  # COER2-POS-MERGE-FIX
        ("dispensado",         "estornado",            "item_estornado"),
    ])
    def test_evento_item(self, de, para, evento_esperado):
        assert evento_obrigatorio_item(de, para) == evento_esperado

    def test_transicao_sem_mapeamento_retorna_none(self):
        assert evento_obrigatorio_prescricao("inexistente", "pendente") is None
        assert evento_obrigatorio_item("inexistente", "pendente") is None

    def test_todos_os_pares_validos_prescricao_tem_evento(self):
        """Toda transição válida de prescrição deve ter evento mapeado."""
        for de, destinos in TRANSICOES_PRESCRICAO.items():
            for para in destinos:
                assert evento_obrigatorio_prescricao(de, para) is not None, (
                    f"Transição válida ('{de}' → '{para}') sem evento mapeado em EVENTOS_PRESCRICAO"
                )

    def test_todos_os_pares_validos_item_tem_evento(self):
        """Toda transição válida de item deve ter evento mapeado."""
        for de, destinos in TRANSICOES_ITEM.items():
            for para in destinos:
                assert evento_obrigatorio_item(de, para) is not None, (
                    f"Transição válida ('{de}' → '{para}') sem evento mapeado em EVENTOS_ITEM"
                )


# ---------------------------------------------------------------------------
# 6. Semântica: fluxo físico vs digital
# ---------------------------------------------------------------------------

class TestSemantica:

    def test_encerrada_localmente_e_terminal(self):
        """Prescrição física nunca entra em ciclo digital."""
        assert eh_terminal_prescricao("encerrada_localmente") is True

    def test_encerrada_localmente_nao_aceita_cancelada(self):
        """cancelada = revogação clínica digital; não se aplica a fluxo físico."""
        assert transicao_valida_prescricao("encerrada_localmente", "cancelada") is False

    def test_encerrado_fisico_e_terminal(self):
        assert eh_terminal_item("encerrado_fisico") is True

    def test_cancelado_e_cancelada_sao_estados_distintos(self):
        """cancelado (item) e cancelada (prescrição) não podem ser confundidos."""
        assert "cancelado" not in ESTADOS_PRESCRICAO
        assert "cancelada" not in ESTADOS_ITEM

    def test_encerrado_fisico_nao_e_cancelado(self):
        """encerrado_fisico != cancelado; semântica completamente diferente."""
        assert "encerrado_fisico" != "cancelado"
        assert "encerrado_fisico" in ESTADOS_ITEM
        assert "cancelado" in ESTADOS_ITEM
