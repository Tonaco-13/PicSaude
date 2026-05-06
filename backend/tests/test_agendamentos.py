"""
test_agendamentos.py
====================
Testes de integração — Módulo de Agendamento (Ticket 29).

COBERTURA
---------
  1. Criação válida
  2. Criação inválida (sem org_id, sem unidade_id, pedido terminal)
  3. Duplo agendamento ativo rejeitado
  4. Confirmação (criado → confirmado)
  5. Realização (→ realizado) com atualização de itens do pedido
  6. Cancelamento com devolução de itens a pendente
  7. Não comparecimento com devolução de itens a pendente
  8. Remarcação: novo objeto derivado, anterior cancelado
  9. Estado terminal não reabre
 10. Integração com itens do pedido (pendente → agendado → coletado)
 11. Ledger completo
 12. Org_id e unidade_id obrigatórios
 13. Listagem por pedido
 14. Consulta individual

Banco em memória via tmp_path (conftest.py).
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from tests.conftest import PAYLOAD_PEDIDO, PAYLOAD_AGENDAR


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pedido(prescritor):
    """Cria pedido de exame e retorna seu protocolo."""
    r = prescritor.post("/pedidos-exame", json=PAYLOAD_PEDIDO)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def agendamento(prescritor, pedido):
    """Cria agendamento e retorna seu protocolo."""
    payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
    r = prescritor.post("/agendamentos", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ---------------------------------------------------------------------------
# 1. Criação válida
# ---------------------------------------------------------------------------

class TestCriacao:

    def test_criar_agendamento_valido(self, prescritor, pedido):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "criado"
        assert data["pedido_protocolo"] == pedido
        assert data["org_id"] == PAYLOAD_AGENDAR["org_id"]
        assert data["unidade_id"] == PAYLOAD_AGENDAR["unidade_id"]
        assert "protocolo" in data

    def test_criar_atualiza_itens_para_agendado(self, prescritor, pedido):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
        prescritor.post("/agendamentos", json=payload)
        r = prescritor.get(f"/pedidos-exame/{pedido}")
        assert r.status_code == 200
        itens = r.json()["itens"]
        for item in itens:
            assert item["status_item"] == "agendado"

    def test_criar_atualiza_status_pedido(self, prescritor, pedido):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.json()["status_pedido"] == "agendado"

    def test_paciente_pode_criar_agendamento(self, paciente, prescritor):
        """Paciente também pode criar agendamento do próprio pedido."""
        r_pedido = prescritor.post("/pedidos-exame", json=PAYLOAD_PEDIDO)
        proto_pedido = r_pedido.json()["protocolo"]
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": proto_pedido}
        r = paciente.post("/agendamentos", json=payload)
        assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 2. Validação de campos obrigatórios
# ---------------------------------------------------------------------------

class TestValidacao:

    def test_org_id_obrigatorio(self, prescritor, pedido):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido, "org_id": ""}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 422

    def test_unidade_id_obrigatorio(self, prescritor, pedido):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido, "unidade_id": "  "}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 422

    def test_pedido_inexistente(self, prescritor):
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": "nao-existe-uuid"}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 404

    def test_duplo_agendamento_ativo_rejeitado(self, prescritor, agendamento, pedido):
        """Não pode haver dois agendamentos ativos para o mesmo pedido."""
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 409
        assert "ativo" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 3. Confirmação
# ---------------------------------------------------------------------------

class TestConfirmacao:

    def test_confirmar_sucesso(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/confirmar")
        assert r.status_code == 200
        assert r.json()["status"] == "confirmado"

    def test_confirmar_nao_altera_itens_pedido(self, prescritor, agendamento, pedido):
        """Confirmação não muda estado dos itens — só o agendamento."""
        prescritor.post(f"/agendamentos/{agendamento}/confirmar")
        r = prescritor.get(f"/pedidos-exame/{pedido}")
        for item in r.json()["itens"]:
            assert item["status_item"] == "agendado"


# ---------------------------------------------------------------------------
# 4. Realização
# ---------------------------------------------------------------------------

class TestRealizacao:

    def test_realizar_direto_de_criado(self, prescritor, agendamento):
        """Pode realizar sem confirmar (simplificação MVP)."""
        r = prescritor.post(f"/agendamentos/{agendamento}/realizar")
        assert r.status_code == 200
        assert r.json()["status"] == "realizado"

    def test_realizar_atualiza_itens_para_coletado(self, prescritor, agendamento, pedido):
        """MVP: realizado → itens do pedido viram coletado."""
        prescritor.post(f"/agendamentos/{agendamento}/realizar")
        r = prescritor.get(f"/pedidos-exame/{pedido}")
        for item in r.json()["itens"]:
            assert item["status_item"] == "coletado"

    def test_realizar_atualiza_status_pedido(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/realizar")
        assert r.json()["status_pedido"] == "coletado"

    def test_realizar_apos_confirmar(self, prescritor, agendamento, pedido):
        prescritor.post(f"/agendamentos/{agendamento}/confirmar")
        r = prescritor.post(f"/agendamentos/{agendamento}/realizar")
        assert r.status_code == 200
        r2 = prescritor.get(f"/pedidos-exame/{pedido}")
        for item in r2.json()["itens"]:
            assert item["status_item"] == "coletado"


# ---------------------------------------------------------------------------
# 5. Cancelamento
# ---------------------------------------------------------------------------

class TestCancelamento:

    def test_cancelar_sucesso(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        assert r.status_code == 200
        assert r.json()["status"] == "cancelado"

    def test_cancelar_devolve_itens_a_pendente(self, prescritor, agendamento, pedido):
        prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        r = prescritor.get(f"/pedidos-exame/{pedido}")
        for item in r.json()["itens"]:
            assert item["status_item"] == "pendente"

    def test_cancelar_permite_novo_agendamento(self, prescritor, agendamento, pedido):
        """Após cancelamento, pedido aceita novo agendamento."""
        prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        payload = {**PAYLOAD_AGENDAR, "pedido_protocolo": pedido}
        r = prescritor.post("/agendamentos", json=payload)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# 6. Não comparecimento
# ---------------------------------------------------------------------------

class TestNaoCompareceu:

    def test_nao_compareceu_sucesso(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/nao-compareceu")
        assert r.status_code == 200
        assert r.json()["status"] == "nao_compareceu"

    def test_nao_compareceu_devolve_itens_a_pendente(self, prescritor, agendamento, pedido):
        prescritor.post(f"/agendamentos/{agendamento}/nao-compareceu")
        r = prescritor.get(f"/pedidos-exame/{pedido}")
        for item in r.json()["itens"]:
            assert item["status_item"] == "pendente"


# ---------------------------------------------------------------------------
# 7. Estados terminais não reabrem
# ---------------------------------------------------------------------------

class TestTerminal:

    def test_realizar_terminal_rejeita(self, prescritor, agendamento):
        prescritor.post(f"/agendamentos/{agendamento}/realizar")
        r = prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        assert r.status_code == 409

    def test_cancelado_nao_reabre(self, prescritor, agendamento):
        prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        r = prescritor.post(f"/agendamentos/{agendamento}/confirmar")
        assert r.status_code == 409

    def test_nao_compareceu_nao_reabre(self, prescritor, agendamento):
        prescritor.post(f"/agendamentos/{agendamento}/nao-compareceu")
        r = prescritor.post(f"/agendamentos/{agendamento}/realizar")
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 8. Remarcação
# ---------------------------------------------------------------------------

class TestRemarcacao:

    def test_remarcar_cria_novo_objeto(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/remarcar",
                            json={"data_hora": "2026-06-01T10:00:00"})
        assert r.status_code == 201
        data = r.json()
        assert data["protocolo_anterior"] == agendamento
        assert data["protocolo_novo"] != agendamento
        assert data["status_anterior"] == "cancelado"
        assert data["status_novo"] == "criado"

    def test_remarcar_cancela_anterior(self, prescritor, agendamento):
        prescritor.post(f"/agendamentos/{agendamento}/remarcar",
                        json={"data_hora": "2026-06-01T10:00:00"})
        r = prescritor.get(f"/agendamentos/{agendamento}")
        assert r.json()["status"] == "cancelado"

    def test_remarcar_novo_herda_pedido(self, prescritor, agendamento, pedido):
        r = prescritor.post(f"/agendamentos/{agendamento}/remarcar",
                            json={"data_hora": "2026-06-01T10:00:00"})
        novo_proto = r.json()["protocolo_novo"]
        r2 = prescritor.get(f"/agendamentos/{novo_proto}")
        assert r2.json()["pedido_protocolo"] == pedido

    def test_remarcar_com_nova_unidade(self, prescritor, agendamento):
        r = prescritor.post(f"/agendamentos/{agendamento}/remarcar", json={
            "data_hora": "2026-06-01T10:00:00",
            "org_id": "NOVO-LAB",
            "unidade_id": "NOVA-UNIDADE",
        })
        novo_proto = r.json()["protocolo_novo"]
        r2 = prescritor.get(f"/agendamentos/{novo_proto}")
        assert r2.json()["org_id"] == "NOVO-LAB"

    def test_nao_pode_remarcar_cancelado(self, prescritor, agendamento):
        prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        r = prescritor.post(f"/agendamentos/{agendamento}/remarcar",
                            json={"data_hora": "2026-06-01T10:00:00"})
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 9. Ledger completo
# ---------------------------------------------------------------------------

class TestLedger:

    def test_ledger_criado(self, prescritor, agendamento, db_path):
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        eventos = conn.execute(
            "SELECT evento FROM agendamento_eventos ORDER BY id"
        ).fetchall()
        conn.close()
        nomes = [e["evento"] for e in eventos]
        assert "agendamento_criado" in nomes

    def test_ledger_ciclo_completo(self, prescritor, agendamento, db_path):
        """criado → confirmado → realizado gera 3 eventos."""
        prescritor.post(f"/agendamentos/{agendamento}/confirmar")
        prescritor.post(f"/agendamentos/{agendamento}/realizar")
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        eventos = conn.execute(
            "SELECT evento FROM agendamento_eventos ORDER BY id"
        ).fetchall()
        conn.close()
        nomes = [e["evento"] for e in eventos]
        assert "agendamento_criado" in nomes
        assert "agendamento_confirmado" in nomes
        assert "agendamento_realizado" in nomes


# ---------------------------------------------------------------------------
# 10. Listagem e consulta
# ---------------------------------------------------------------------------

class TestConsulta:

    def test_get_agendamento(self, prescritor, agendamento):
        r = prescritor.get(f"/agendamentos/{agendamento}")
        assert r.status_code == 200
        assert r.json()["protocolo"] == agendamento

    def test_listar_por_pedido(self, prescritor, agendamento, pedido):
        r = prescritor.get(f"/pedidos-exame/{pedido}/agendamentos")
        assert r.status_code == 200
        protos = [a["protocolo"] for a in r.json()["agendamentos"]]
        assert agendamento in protos

    def test_historico_inclui_cancelados(self, prescritor, agendamento, pedido):
        """Listagem inclui agendamentos cancelados (histórico completo)."""
        prescritor.post(f"/agendamentos/{agendamento}/cancelar")
        r = prescritor.get(f"/pedidos-exame/{pedido}/agendamentos")
        assert any(a["status"] == "cancelado" for a in r.json()["agendamentos"])
