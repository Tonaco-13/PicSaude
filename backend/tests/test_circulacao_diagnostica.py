"""
test_circulacao_diagnostica.py
================================
Testes de integração — Módulo de Circulação Diagnóstica (Ticket 53).

COBERTURA
---------
  1.  Criação válida (1 item)
  2.  Criação válida com múltiplos itens (subconjunto)
  3.  Resposta contém chave_circulacao, protocolo, status='selecionado'
  4.  Validade padrão aplicada quando não informada
  5.  Validade customizada aceita
  6.  Pedido inexistente → 404
  7.  org_id vazio → 422
  8.  unidade_id vazio → 422
  9.  item_ids vazio → 422
 10.  item_id não pertence ao pedido → 422
 11.  Item não pendente → 409
 12.  Item já em circulação ativa → 409
 13.  Pedido cancelado não aceita nova circulação → 409
 14.  Role prescritor tentando criar → 403
 15.  Role dispensador tentando criar → 403
 16.  Ledger: evento 'circulacao_criada' inserido
 17.  Status do pedido NÃO muda após criação (Ticket 53)
 18.  Status dos itens NÃO muda após criação (Ticket 53)
 19.  GET /circulacao/{chave} — retorna dados corretos
 20.  GET /circulacao/{chave} — chave inválida → 404
 21.  Privacidade: GET não expõe itens fora do subconjunto
 22.  GET retorna status, org_id, unidade_id, validade, criado_em
 23.  Dois subconjuntos distintos do mesmo pedido podem coexistir se itens não se sobrepõem
 24.  Item já em circulação encerrada pode entrar em nova circulação

Banco em memória via tmp_path (conftest.py).
"""
from __future__ import annotations

import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import PAYLOAD_PEDIDO


# ---------------------------------------------------------------------------
# Payloads específicos deste módulo
# ---------------------------------------------------------------------------

PAYLOAD_PEDIDO_2_ITENS = {
    "cns_prescritor":  "123456789012345",
    "nome_prescritor": "Dr. Teste",
    "cpf_paciente":    "12345678901",
    "nome_paciente":   "Paciente Teste",
    "tipo_emissao":    "novo",
    "itens": [
        {"nome_exame": "Hemograma Completo", "quantidade": 1},
        {"nome_exame": "Glicemia em Jejum",  "quantidade": 1},
    ],
}

PAYLOAD_CIRC_BASE = {
    "org_id":     "LAB-TESTE",
    "unidade_id": "UNIDADE-001",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_prestador_lab(db_path, org_id="LAB-TESTE", cnpj="12345678000195"):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR IGNORE INTO prestadores
          (id, org_id, nome, tipo, cnpj, ativo, criado_em)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (f"prestador-{org_id}", org_id, f"Laboratorio {org_id}", "laboratorio", cnpj, "2026-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def prestador_lab(db_path):
    _seed_prestador_lab(db_path)


@pytest.fixture()
def pedido_1_item(prescritor):
    """Cria pedido com 1 item e retorna seu protocolo."""
    r = prescritor.post("/pedidos-exame", json=PAYLOAD_PEDIDO)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def pedido_2_itens(prescritor):
    """Cria pedido com 2 itens e retorna (protocolo, [item_ids])."""
    r = prescritor.post("/pedidos-exame", json=PAYLOAD_PEDIDO_2_ITENS)
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]
    # Busca os item_ids pelo pedido
    r2 = prescritor.get(f"/pedidos-exame/{proto}")
    assert r2.status_code == 200
    itens = r2.json()["itens"]
    return proto, [i["id"] for i in itens]


@pytest.fixture()
def circulacao(paciente, pedido_1_item, prescritor, prestador_lab):
    """Cria circulação com o único item do pedido. Retorna response JSON."""
    # Obtém item_id
    r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
    item_id = r.json()["itens"][0]["id"]
    payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
    r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1–5. Criação válida
# ---------------------------------------------------------------------------

class TestCriacaoValida:

    def test_criar_circulacao_1_item(self, paciente, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["status"] == "selecionado"
        assert "chave_circulacao" in data
        assert "protocolo" in data
        assert len(data["itens"]) == 1

    def test_criar_circulacao_subconjunto_2_itens(self, paciente, prescritor, pedido_2_itens):
        proto, item_ids = pedido_2_itens
        # Seleciona apenas o primeiro item
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_ids[0]]}
        r = paciente.post(f"/pedidos-exame/{proto}/circulacao", json=payload)
        assert r.status_code == 201, r.text
        assert len(r.json()["itens"]) == 1

    def test_criar_circulacao_todos_itens(self, paciente, prescritor, pedido_2_itens):
        proto, item_ids = pedido_2_itens
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": item_ids}
        r = paciente.post(f"/pedidos-exame/{proto}/circulacao", json=payload)
        assert r.status_code == 201, r.text
        assert len(r.json()["itens"]) == 2

    def test_chave_circulacao_presente_e_nao_vazia(self, paciente, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        chave = r.json()["chave_circulacao"]
        assert chave and len(chave) > 0

    def test_validade_padrao_quando_ausente(self, paciente, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.json()["validade"]   # não é None nem vazio

    def test_validade_customizada_aceita(self, paciente, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        validade = "2026-12-31T23:59:59"
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id], "validade": validade}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 201
        assert r.json()["validade"] == validade


# ---------------------------------------------------------------------------
# 6–13. Validações e erros
# ---------------------------------------------------------------------------

class TestValidacao:

    def test_pedido_inexistente_retorna_404(self, paciente):
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [1]}
        r = paciente.post("/pedidos-exame/nao-existe-uuid/circulacao", json=payload)
        assert r.status_code == 404

    def test_org_id_vazio_retorna_422(self, paciente, pedido_1_item, prescritor):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {"org_id": "", "unidade_id": "U1", "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 422

    def test_unidade_id_vazio_retorna_422(self, paciente, pedido_1_item, prescritor):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {"org_id": "LAB", "unidade_id": "   ", "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 422

    def test_item_ids_vazio_retorna_422(self, paciente, pedido_1_item):
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": []}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 422

    def test_item_id_nao_pertence_ao_pedido(self, paciente, pedido_1_item):
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [999999]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 422

    def test_item_nao_pendente_retorna_409(self, paciente, prescritor, pedido_1_item, db_path):
        """Item com status != pendente não pode ser selecionado."""
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        # Força o item para 'agendado' diretamente no banco
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE pedido_exame_itens SET status_item = 'agendado' WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 409

    def test_item_em_circulacao_ativa_retorna_409(self, paciente, prescritor, pedido_1_item, circulacao):
        """Item já em circulação ativa não pode entrar em outra."""
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 409

    def test_pedido_cancelado_retorna_409(self, paciente, prescritor, pedido_1_item, db_path):
        """Pedido em estado terminal não aceita nova circulação."""
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        # Força o pedido para 'cancelado' diretamente no banco
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE pedidos_exame SET status = 'cancelado' WHERE protocolo = ?", (pedido_1_item,)
        )
        conn.commit()
        conn.close()
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 14–15. Controle de acesso
# ---------------------------------------------------------------------------

class TestAcesso:

    def test_prescritor_nao_pode_criar_circulacao(self, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = prescritor.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 403

    def test_dispensador_nao_pode_criar_circulacao(self, dispensador, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = dispensador.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 403

    def test_paciente_nao_dono_nao_pode_criar_circulacao(
            self, outro_paciente, prescritor, pedido_1_item):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r = outro_paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 16. Ledger
# ---------------------------------------------------------------------------

class TestLedger:

    def test_evento_circulacao_criada_inserido(self, circulacao, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        eventos = conn.execute(
            "SELECT tipo_evento FROM circulacao_diagnostica_eventos ORDER BY id"
        ).fetchall()
        conn.close()
        tipos = [e["tipo_evento"] for e in eventos]
        assert "circulacao_criada" in tipos

    def test_evento_contem_org_id(self, circulacao, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT dados_json FROM circulacao_diagnostica_eventos WHERE tipo_evento = 'circulacao_criada'"
        ).fetchone()
        conn.close()
        import json as _json
        dados = _json.loads(row["dados_json"])
        assert dados["org_id"] == PAYLOAD_CIRC_BASE["org_id"]

    def test_evento_contem_lista_itens(self, circulacao, db_path):
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT dados_json FROM circulacao_diagnostica_eventos WHERE tipo_evento = 'circulacao_criada'"
        ).fetchone()
        conn.close()
        import json as _json
        dados = _json.loads(row["dados_json"])
        assert "itens" in dados
        assert len(dados["itens"]) >= 1


# ---------------------------------------------------------------------------
# 17–18. Não alteração de estados do pedido/itens (Ticket 53)
# ---------------------------------------------------------------------------

class TestNaoAlteracaoEstados:

    def test_status_pedido_nao_muda(self, paciente, prescritor, pedido_1_item, circulacao):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        assert r.json()["status"] == "emitido"

    def test_status_item_nao_muda(self, paciente, prescritor, pedido_1_item, circulacao):
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        for item in r.json()["itens"]:
            assert item["status_item"] == "pendente"


# ---------------------------------------------------------------------------
# 19–22. GET /circulacao/{chave}
# ---------------------------------------------------------------------------

class TestConsultaPorChave:

    def test_get_retorna_circulacao_valida(self, prescritor, circulacao):
        chave = circulacao["chave_circulacao"]
        r = prescritor.get(f"/circulacao/{chave}")
        assert r.status_code == 200
        data = r.json()
        assert data["chave_circulacao"] == chave
        assert data["status"] == "selecionado"

    def test_get_chave_invalida_retorna_404(self, prescritor):
        r = prescritor.get("/circulacao/CHAVE-INEXISTENTE")
        assert r.status_code == 404

    def test_get_retorna_campos_obrigatorios(self, prescritor, circulacao):
        r = prescritor.get(f"/circulacao/{circulacao['chave_circulacao']}")
        data = r.json()
        for campo in ("protocolo", "chave_circulacao", "status", "org_id",
                      "unidade_id", "validade", "criado_em", "itens", "paciente"):
            assert campo in data, f"Campo '{campo}' ausente na resposta"

    def test_get_retorna_itens_da_circulacao(self, prescritor, circulacao):
        r = prescritor.get(f"/circulacao/{circulacao['chave_circulacao']}")
        assert len(r.json()["itens"]) == 1

    def test_dispensador_pode_consultar_por_chave(self, dispensador, circulacao):
        r = dispensador.get(f"/circulacao/{circulacao['chave_circulacao']}")
        assert r.status_code == 200

    def test_paciente_nao_dono_nao_consulta_por_chave(self, outro_paciente, circulacao):
        r = outro_paciente.get(f"/circulacao/{circulacao['chave_circulacao']}")
        assert r.status_code == 403

    def test_dispensador_sem_org_mapeada_falha_fechado(
            self, dispensador, circulacao, db_path):
        conn = sqlite3.connect(db_path)
        conn.execute("DELETE FROM prestadores WHERE org_id = ?", (PAYLOAD_CIRC_BASE["org_id"],))
        conn.commit()
        conn.close()

        r = dispensador.get(f"/circulacao/{circulacao['chave_circulacao']}")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 21. Privacidade: subconjunto não expõe outros itens
# ---------------------------------------------------------------------------

class TestPrivacidade:

    def test_get_exibe_apenas_itens_do_subconjunto(self, paciente, prescritor, pedido_2_itens):
        proto, item_ids = pedido_2_itens
        # Cria circulação com apenas o primeiro item
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_ids[0]]}
        r = paciente.post(f"/pedidos-exame/{proto}/circulacao", json=payload)
        assert r.status_code == 201
        chave = r.json()["chave_circulacao"]

        r2 = prescritor.get(f"/circulacao/{chave}")
        itens_retornados = r2.json()["itens"]
        # Somente 1 item deve aparecer — o segundo item do pedido não vaza
        assert len(itens_retornados) == 1

    def test_get_nao_expoe_total_itens_pedido(self, prescritor, circulacao, pedido_2_itens):
        """A resposta não deve conter contagem total de itens do pedido original."""
        r = prescritor.get(f"/circulacao/{circulacao['chave_circulacao']}")
        data = r.json()
        assert "total_itens_pedido" not in data


# ---------------------------------------------------------------------------
# 23–24. Circulações paralelas e reuso após encerramento
# ---------------------------------------------------------------------------

class TestCirculacoesParalelas:

    def test_dois_subconjuntos_distintos_coexistem(self, paciente, prescritor, pedido_2_itens):
        """Dois itens distintos do mesmo pedido podem estar em circulações distintas."""
        proto, item_ids = pedido_2_itens
        payload1 = {**PAYLOAD_CIRC_BASE, "item_ids": [item_ids[0]]}
        payload2 = {"org_id": "LAB-2", "unidade_id": "U-2", "item_ids": [item_ids[1]]}
        r1 = paciente.post(f"/pedidos-exame/{proto}/circulacao", json=payload1)
        r2 = paciente.post(f"/pedidos-exame/{proto}/circulacao", json=payload2)
        assert r1.status_code == 201, r1.text
        assert r2.status_code == 201, r2.text

    def test_item_em_circulacao_encerrada_pode_entrar_em_nova(
            self, paciente, prescritor, pedido_1_item, circulacao, db_path):
        """Após circulação ser encerrada (terminal), item volta a ser elegível."""
        r = prescritor.get(f"/pedidos-exame/{pedido_1_item}")
        item_id = r.json()["itens"][0]["id"]
        # Encerra a circulação existente diretamente no banco
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'expirado' WHERE protocolo = ?",
            (circulacao["protocolo"],),
        )
        conn.commit()
        conn.close()
        # Agora deve ser possível criar nova circulação com o mesmo item
        payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
        r2 = paciente.post(f"/pedidos-exame/{pedido_1_item}/circulacao", json=payload)
        assert r2.status_code == 201, r2.text
