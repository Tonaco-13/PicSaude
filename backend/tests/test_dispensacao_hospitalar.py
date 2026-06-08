"""
test_dispensacao_hospitalar.py
==============================
Testes de integração — Dispensação Hospitalar (Ticket 27).

COBERTURA
---------
  1. Dispensação hospitalar válida (total e parcial)
  2. Dose unitária: true/false
  3. quantidade_doses opcional
  4. Erros: sem saldo, item inválido, prescrição inválida, status bloqueado
  5. Persistência: dispensacoes_hospitalares + dispensacoes base
  6. Evento no ledger: dispensacao_hospitalar_registrada
  7. Custódia com contexto hospitalar
  8. org_id e unidade_id obrigatórios
  9. Modalidades: internacao | urgencia_emergencia | cirurgia
  10. Fracionamento: múltiplas dispensações do mesmo item
  11. Não regressão: fluxo ambulatorial intacto
  12. Isolamento de role: prescritor não pode dispensar no hospitalar

Banco em memória via tmp_path (conftest.py).
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from tests.conftest import PAYLOAD_PADRAO, PAYLOAD_DOIS_ITENS, PAYLOAD_DISPENSA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def proto(prescritor):
    """Prescrição digital com 1 item (AMOXICILINA 500mg, qtd=10)."""
    r = prescritor.post("/prescricoes", json=PAYLOAD_PADRAO)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def proto_dois_itens(prescritor):
    """Prescrição digital com 2 itens."""
    r = prescritor.post("/prescricoes", json=PAYLOAD_DOIS_ITENS)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def item_id(proto, db_path):
    """ID do primeiro (único) item da prescrição padrão — via DB direto."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    row = conn.execute(
        """
        SELECT i.id FROM prescricao_itens i
        JOIN prescricoes p ON p.id = i.prescricao_id
        WHERE p.protocolo = ?
        ORDER BY i.id LIMIT 1
        """,
        (proto,),
    ).fetchone()
    conn.close()
    assert row is not None, f"Nenhum item encontrado para o protocolo {proto}"
    return row[0]


@pytest.fixture()
def item_ids(proto_dois_itens, db_path):
    """IDs dos dois itens da prescrição de dois itens — via DB direto."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        """
        SELECT i.id FROM prescricao_itens i
        JOIN prescricoes p ON p.id = i.prescricao_id
        WHERE p.protocolo = ?
        ORDER BY i.id
        """,
        (proto_dois_itens,),
    ).fetchall()
    conn.close()
    assert len(rows) == 2
    return [r[0] for r in rows]


PAYLOAD_HOSP = {
    "org_id":                 "HOSP-ALBERT-EINSTEIN",
    "unidade_id":             "FARM-HOSP-CENTRAL",
    "setor":                  "UTI Adulto",
    "leito":                  "12A",
    "modalidade":             "internacao",
    "quantidade_dispensada":  5,
    "dose_unitaria":          False,
    "dispensado_por":         "Farm. Silva",
}


@pytest.fixture(autouse=True)
def prestador_hospitalar_padrao(db_path):
    """Vínculo institucional mínimo para o dispensador padrão dos testes."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        INSERT OR IGNORE INTO prestadores
          (id, org_id, nome, tipo, cnpj, ativo, criado_em)
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (
            "prestador-hospitalar-padrao",
            PAYLOAD_HOSP["org_id"],
            "Hospital Teste",
            "hospital",
            "12345678000195",
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()


def _hosp_url(protocolo: str, item_id: int) -> str:
    return f"/prescricoes/{protocolo}/itens/{item_id}/dispensar/hospitalar"


# ---------------------------------------------------------------------------
# 1. Dispensação válida
# ---------------------------------------------------------------------------

class TestDispensacaoValida:

    def test_dispensacao_total(self, dispensador, proto, item_id):
        """Dispensa todos os 10 itens de uma vez."""
        payload = {**PAYLOAD_HOSP, "quantidade_dispensada": 10}
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["quantidade_dispensada"] == 10
        assert data["saldo_restante"] == 0
        assert data["status_item"] == "dispensado"
        assert data["status_prescricao"] == "dispensada"
        assert data["contexto"] == "hospitalar"
        assert data["org_id"] == "HOSP-ALBERT-EINSTEIN"

    def test_dispensacao_parcial(self, dispensador, proto, item_id):
        """
        Dispensa 5 de 10 — item fica em_custodia (saldo restante).
        Prescrição fica em_custodia porque nenhum item está 100% dispensado.
        (Mesmo comportamento do fluxo ambulatorial.)
        """
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["quantidade_dispensada"] == 5
        assert data["saldo_restante"] == 5
        assert data["status_item"] == "em_custodia"
        assert data["status_prescricao"] == "em_custodia"

    def test_retorna_dispensacao_id(self, dispensador, proto, item_id):
        """Resposta deve conter dispensacao_id (FK para tabela base)."""
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 201
        assert "dispensacao_id" in r.json()
        assert isinstance(r.json()["dispensacao_id"], int)

    def test_contexto_hospitalar_na_resposta(self, dispensador, proto, item_id):
        """Resposta deve conter campos hospitalares."""
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 201
        data = r.json()
        assert data["setor"] == "UTI Adulto"
        assert data["leito"] == "12A"
        assert data["unidade_id"] == "FARM-HOSP-CENTRAL"


# ---------------------------------------------------------------------------
# 2. Dose unitária
# ---------------------------------------------------------------------------

class TestDoseUnitaria:

    def test_dose_unitaria_true(self, dispensador, proto, item_id):
        payload = {
            **PAYLOAD_HOSP,
            "quantidade_dispensada": 6,
            "dose_unitaria": True,
            "quantidade_doses": 6,
        }
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 201, r.text
        assert r.json()["quantidade_dispensada"] == 6

    def test_dose_unitaria_false_sem_doses(self, dispensador, proto, item_id):
        """dose_unitaria=False e sem quantidade_doses — deve funcionar normalmente."""
        payload = {**PAYLOAD_HOSP, "dose_unitaria": False}
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 201, r.text

    def test_quantidade_doses_opcional_sem_dose_unitaria(self, dispensador, proto, item_id):
        """quantidade_doses pode ser omitida quando dose_unitaria=False."""
        payload = {k: v for k, v in PAYLOAD_HOSP.items() if k != "quantidade_doses"}
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 3. Modalidades
# ---------------------------------------------------------------------------

class TestModalidades:

    def test_modalidade_internacao(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "modalidade": "internacao"},
        )
        assert r.status_code == 201

    def test_modalidade_urgencia_emergencia(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "modalidade": "urgencia_emergencia"},
        )
        assert r.status_code == 201

    def test_modalidade_cirurgia(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "modalidade": "cirurgia"},
        )
        assert r.status_code == 201

    def test_modalidade_invalida(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "modalidade": "ambulatorial"},
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 4. Erros de validação
# ---------------------------------------------------------------------------

class TestErros:

    def test_protocolo_inexistente(self, dispensador, item_id):
        r = dispensador.post(
            _hosp_url("protocolo-nao-existe-00000000", item_id),
            json=PAYLOAD_HOSP,
        )
        assert r.status_code == 404

    def test_item_inexistente(self, dispensador, proto):
        r = dispensador.post(_hosp_url(proto, 99999), json=PAYLOAD_HOSP)
        assert r.status_code == 404

    def test_quantidade_zero(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 0},
        )
        assert r.status_code == 422

    def test_quantidade_negativa(self, dispensador, proto, item_id):
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": -1},
        )
        assert r.status_code == 422

    def test_supera_saldo(self, dispensador, proto, item_id):
        """Tentar dispensar mais do que o saldo disponível (10 unidades)."""
        r = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 11},
        )
        assert r.status_code == 422

    def test_sem_saldo_apos_dispensacao_total(self, dispensador, proto, item_id):
        """Segunda dispensação após esgotar o saldo deve retornar 409."""
        dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 10},
        )
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 409

    def test_org_id_ausente(self, dispensador, proto, item_id):
        payload = {k: v for k, v in PAYLOAD_HOSP.items() if k != "org_id"}
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 422

    def test_unidade_id_ausente(self, dispensador, proto, item_id):
        payload = {k: v for k, v in PAYLOAD_HOSP.items() if k != "unidade_id"}
        r = dispensador.post(_hosp_url(proto, item_id), json=payload)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# 5. Persistência
# ---------------------------------------------------------------------------

class TestPersistencia:

    def test_registro_base_em_dispensacoes(self, dispensador, proto, item_id, db_path):
        """Deve criar registro em `dispensacoes` (tabela base)."""
        import sqlite3
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT * FROM dispensacoes WHERE prescricao_item_id = ?", (item_id,)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[3] == 5  # quantidade_dispensada (coluna índice 3)

    def test_extensao_em_dispensacoes_hospitalares(self, dispensador, proto, item_id, db_path):
        """Deve criar registro em `dispensacoes_hospitalares` com org_id."""
        import sqlite3
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT * FROM dispensacoes_hospitalares WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_org_id_na_extensao_hospitalar(self, dispensador, proto, item_id, db_path):
        """org_id deve estar presente na tabela dispensacoes_hospitalares."""
        import sqlite3
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM dispensacoes_hospitalares WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()
        conn.close()
        assert row["org_id"] == "HOSP-ALBERT-EINSTEIN"
        assert row["unidade_id"] == "FARM-HOSP-CENTRAL"
        assert row["setor"] == "UTI Adulto"
        assert row["leito"] == "12A"

    def test_fracionamento_multiplas_dispensacoes(self, dispensador, proto, item_id, db_path):
        """
        Mesmo item pode ser dispensado em múltiplos eventos hospitalares
        desde que Σ quantidade_dispensada ≤ prescrito.
        """
        import sqlite3
        # Dia 1: 4 unidades
        r1 = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 4},
        )
        assert r1.status_code == 201
        # Dia 3: mais 4 unidades
        r2 = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 4},
        )
        assert r2.status_code == 201
        assert r2.json()["saldo_restante"] == 2

        conn = sqlite3.connect(db_path)
        total = conn.execute(
            "SELECT SUM(quantidade_dispensada) FROM dispensacoes WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()[0]
        conn.close()
        assert total == 8  # 4 + 4


# ---------------------------------------------------------------------------
# 6. Evento no ledger
# ---------------------------------------------------------------------------

class TestEvento:

    def test_evento_ledger_criado(self, dispensador, proto, item_id, db_path):
        """Deve criar evento `dispensacao_hospitalar_registrada` no ledger."""
        import sqlite3
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT * FROM prescricao_eventos WHERE tipo_evento = ?",
            ("dispensacao_hospitalar_registrada",),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_payload_evento_completo(self, dispensador, proto, item_id, db_path):
        """Evento deve conter org_id, unidade_id, setor, leito, dose_unitaria."""
        import sqlite3
        import json as _json
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT payload_json FROM prescricao_eventos WHERE tipo_evento = ?",
            ("dispensacao_hospitalar_registrada",),
        ).fetchone()
        conn.close()
        payload = _json.loads(row[0])
        assert payload["org_id"] == "HOSP-ALBERT-EINSTEIN"
        assert payload["unidade_id"] == "FARM-HOSP-CENTRAL"
        assert payload["setor"] == "UTI Adulto"
        assert payload["leito"] == "12A"
        assert payload["dose_unitaria"] is False


# ---------------------------------------------------------------------------
# 7. Custódia hospitalar
# ---------------------------------------------------------------------------

class TestCustodiaHospitalar:

    def test_custodia_com_contexto_hospitalar(self, dispensador, proto, item_id, db_path):
        """Custódia deve ser registrada com contexto_operacional='hospitalar'."""
        import sqlite3
        dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM prescricao_custodia
            WHERE contexto_operacional = 'hospitalar'
            ORDER BY id DESC LIMIT 1
            """,
        ).fetchone()
        conn.close()
        # Registros hospitalares têm contexto_operacional != NULL
        assert row is not None
        assert row["unidade_id"] == "FARM-HOSP-CENTRAL"


# ---------------------------------------------------------------------------
# 8. Não regressão — fluxo ambulatorial intacto
# ---------------------------------------------------------------------------

class TestNaoRegressao:

    def test_endpoint_ambulatorial_intacto(self, dispensador, proto, item_id):
        """O endpoint ambulatorial deve continuar funcionando normalmente."""
        r = dispensador.post(
            f"/prescricoes/{proto}/itens/{item_id}/dispensar",
            json=PAYLOAD_DISPENSA,
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["quantidade_dispensada"] == 5
        assert data["status_item"] == "em_custodia"

    def test_saldo_compartilhado_entre_modos(self, dispensador, proto, item_id):
        """
        O saldo é compartilhado: dispensa ambulatorial + hospitalar juntas
        não podem superar a quantidade prescrita.
        """
        # 5 unidades via ambulatorial
        r1 = dispensador.post(
            f"/prescricoes/{proto}/itens/{item_id}/dispensar",
            json=PAYLOAD_DISPENSA,
        )
        assert r1.status_code == 201

        # 5 unidades via hospitalar (total = 10 = prescrito)
        r2 = dispensador.post(
            _hosp_url(proto, item_id),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 5},
        )
        assert r2.status_code == 201
        assert r2.json()["saldo_restante"] == 0
        assert r2.json()["status_item"] == "dispensado"

    def test_saldo_esgotado_bloqueia_hospitalar(self, dispensador, proto, item_id):
        """Após esgotar saldo via ambulatorial, hospitalar deve ser bloqueado."""
        dispensador.post(
            f"/prescricoes/{proto}/itens/{item_id}/dispensar",
            json={**PAYLOAD_DISPENSA, "quantidade_dispensada": 10},
        )
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 9. Isolamento de role
# ---------------------------------------------------------------------------

class TestIsolamentoRole:

    def test_prescritor_nao_pode_dispensar_hospitalar(self, prescritor, proto, item_id):
        """Prescritor não tem permissão para o endpoint hospitalar."""
        r = prescritor.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code in (401, 403)

    def test_dispensador_pode_dispensar_hospitalar(self, dispensador, proto, item_id):
        """Dispensador tem permissão para o endpoint hospitalar."""
        r = dispensador.post(_hosp_url(proto, item_id), json=PAYLOAD_HOSP)
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# 10. Dois itens — dispensação independente
# ---------------------------------------------------------------------------

class TestDoisItens:

    def test_dispensar_apenas_um_item_hospitalar(self, dispensador, proto_dois_itens, item_ids):
        """Dispensar só o item 1: prescrição fica parcialmente_dispensada."""
        item1, item2 = item_ids
        r = dispensador.post(
            _hosp_url(proto_dois_itens, item1),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 10},
        )
        assert r.status_code == 201
        assert r.json()["status_prescricao"] == "parcialmente_dispensada"

    def test_dispensar_dois_itens_hospitalares(self, dispensador, proto_dois_itens, item_ids):
        """Dispensar ambos os itens: prescrição fica dispensada."""
        item1, item2 = item_ids
        r1 = dispensador.post(
            _hosp_url(proto_dois_itens, item1),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 10},
        )
        assert r1.status_code == 201

        r2 = dispensador.post(
            _hosp_url(proto_dois_itens, item2),
            json={**PAYLOAD_HOSP, "quantidade_dispensada": 6},
        )
        assert r2.status_code == 201
        assert r2.json()["status_prescricao"] == "dispensada"
