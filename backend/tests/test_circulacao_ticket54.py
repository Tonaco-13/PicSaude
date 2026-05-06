"""
test_circulacao_ticket54.py
===========================
Testes de integração — Circulação Diagnóstica, Ticket 54.

COBERTURA
---------
  POST /circulacao/{chave}/proposta
    1.  Proposta válida muda status para proposta_recebida
    2.  Campos data_hora_proposta, local_texto e instrucoes_preparo persistidos
    3.  Evento circulacao_proposta_recebida inserido no ledger
    4.  Evento contém campos corretos
    5.  data_hora_proposta ausente → 422
    6.  Estado incompatível (não é enviado_laboratorio) → 409
    7.  Chave inexistente → 404
    8.  Paciente não pode propor → 403
    9.  Prescritor não pode propor → 403
   10.  local_texto e instrucoes_preparo são opcionais

  POST /circulacao/{chave}/confirmar
   11.  Confirmação válida muda status para confirmado_paciente
   12.  Evento circulacao_confirmada_paciente inserido no ledger
   13.  Evento registra confirmado_por
   14.  Estado incompatível (não é proposta_recebida) → 409
   15.  Chave inexistente → 404
   16.  Dispensador não pode confirmar → 403
   17.  Prescritor não pode confirmar → 403

  POST /circulacao/{chave}/desmarcar
   18.  Paciente desmarca de proposta_recebida → desmarcado_paciente
   19.  Paciente desmarca de confirmado_paciente → desmarcado_paciente
   20.  Dispensador desmarca de enviado_laboratorio → desmarcado_laboratorio
   21.  Dispensador desmarca de proposta_recebida → desmarcado_laboratorio
   22.  Dispensador desmarca de confirmado_paciente → desmarcado_laboratorio
   23.  Paciente não pode desmarcar de enviado_laboratorio → 409
   24.  Estado terminal bloqueia desmarcação → 409
   25.  Chave inexistente → 404
   26.  Prescritor não pode desmarcar → 403
   27.  Evento circulacao_desmarcada_paciente inserido (ator paciente)
   28.  Evento circulacao_desmarcada_laboratorio inserido (ator dispensador)
   29.  Desmarcação com motivo persiste motivo no evento

  Não regressão
   30.  GET /circulacao/{chave} continua funcionando após proposta
   31.  Pedido de exame não muda após proposta
   32.  Itens do pedido não mudam após proposta
   33.  Pedido de exame não muda após confirmação
   34.  Pedido de exame não muda após desmarcação

Banco em memória via tmp_path (conftest.py).
"""
from __future__ import annotations

import json as _json
import sqlite3
import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.conftest import PAYLOAD_PEDIDO


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------

PAYLOAD_PROPOSTA = {
    "data_hora_proposta": "2026-06-15T08:00:00",
    "local_texto":        "Unidade Central — Sala 3",
    "instrucoes_preparo": "Jejum de 12 horas",
}

PAYLOAD_CIRC_BASE = {
    "org_id":     "LAB-TESTE",
    "unidade_id": "UNIDADE-001",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pedido(prescritor):
    """Cria pedido de exame com 1 item e retorna protocolo."""
    r = prescritor.post("/pedidos-exame", json=PAYLOAD_PEDIDO)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


@pytest.fixture()
def circulacao(paciente, prescritor, pedido):
    """Circulação no estado inicial 'selecionado'."""
    r = prescritor.get(f"/pedidos-exame/{pedido}")
    item_id = r.json()["itens"][0]["id"]
    payload = {**PAYLOAD_CIRC_BASE, "item_ids": [item_id]}
    r = paciente.post(f"/pedidos-exame/{pedido}/circulacao", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture()
def circulacao_enviada(circulacao, db_path):
    """Circulação no estado 'enviado_laboratorio' (via SQL direto)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "UPDATE circulacoes_diagnosticas SET status = 'enviado_laboratorio' WHERE protocolo = ?",
        (circulacao["protocolo"],),
    )
    conn.commit()
    conn.close()
    return circulacao


@pytest.fixture()
def circulacao_com_proposta(circulacao_enviada, dispensador):
    """Circulação no estado 'proposta_recebida' (via endpoint /proposta)."""
    chave = circulacao_enviada["chave_circulacao"]
    r = dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
    assert r.status_code == 200, r.text
    return circulacao_enviada


@pytest.fixture()
def circulacao_confirmada(circulacao_com_proposta, paciente):
    """Circulação no estado 'confirmado_paciente' (via endpoint /confirmar)."""
    chave = circulacao_com_proposta["chave_circulacao"]
    r = paciente.post(f"/circulacao/{chave}/confirmar")
    assert r.status_code == 200, r.text
    return circulacao_com_proposta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_status_db(db_path, protocolo):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM circulacoes_diagnosticas WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    conn.close()
    return row["status"] if row else None


def _get_proposta_db(db_path, protocolo):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT data_hora_proposta, local_texto, instrucoes_preparo "
        "FROM circulacoes_diagnosticas WHERE protocolo = ?",
        (protocolo,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _get_eventos_db(db_path, protocolo):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # obtém circulacao_id via protocolo
    row = conn.execute(
        "SELECT id FROM circulacoes_diagnosticas WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        conn.close()
        return []
    eventos = conn.execute(
        "SELECT tipo_evento, dados_json FROM circulacao_diagnostica_eventos "
        "WHERE circulacao_id = ? ORDER BY id",
        (row["id"],),
    ).fetchall()
    conn.close()
    return [{"tipo_evento": e["tipo_evento"], "dados": _json.loads(e["dados_json"])} for e in eventos]


def _get_pedido_status_db(db_path, protocolo_pedido):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status FROM pedidos_exame WHERE protocolo = ?", (protocolo_pedido,)
    ).fetchone()
    conn.close()
    return row["status"] if row else None


def _get_itens_status_db(db_path, protocolo_pedido):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT pei.status_item
          FROM pedido_exame_itens pei
          JOIN pedidos_exame pe ON pe.id = pei.pedido_id
         WHERE pe.protocolo = ?
        """,
        (protocolo_pedido,),
    ).fetchall()
    conn.close()
    return [r["status_item"] for r in rows]


# ---------------------------------------------------------------------------
# 1–10. POST /circulacao/{chave}/proposta
# ---------------------------------------------------------------------------

class TestProposta:

    def test_proposta_valida_muda_status(self, dispensador, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "proposta_recebida"
        assert _get_status_db(db_path, circulacao_enviada["protocolo"]) == "proposta_recebida"

    def test_proposta_persiste_campos(self, dispensador, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        props = _get_proposta_db(db_path, circulacao_enviada["protocolo"])
        assert props["data_hora_proposta"] == PAYLOAD_PROPOSTA["data_hora_proposta"]
        assert props["local_texto"]        == PAYLOAD_PROPOSTA["local_texto"]
        assert props["instrucoes_preparo"] == PAYLOAD_PROPOSTA["instrucoes_preparo"]

    def test_proposta_grava_evento(self, dispensador, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        tipos = [e["tipo_evento"] for e in _get_eventos_db(db_path, circulacao_enviada["protocolo"])]
        assert "circulacao_proposta_recebida" in tipos

    def test_proposta_evento_contem_campos(self, dispensador, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        eventos = _get_eventos_db(db_path, circulacao_enviada["protocolo"])
        ev = next(e for e in eventos if e["tipo_evento"] == "circulacao_proposta_recebida")
        assert ev["dados"]["data_hora_proposta"] == PAYLOAD_PROPOSTA["data_hora_proposta"]
        assert ev["dados"]["local_texto"]        == PAYLOAD_PROPOSTA["local_texto"]
        assert "registrado_por" in ev["dados"]

    def test_proposta_sem_data_hora_retorna_422(self, dispensador, circulacao_enviada):
        chave = circulacao_enviada["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/proposta", json={"local_texto": "Sala 1"})
        assert r.status_code == 422

    def test_proposta_estado_incompativel_retorna_409(self, dispensador, circulacao):
        # circulação em 'selecionado', não em 'enviado_laboratorio'
        chave = circulacao["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        assert r.status_code == 409

    def test_proposta_chave_inexistente_retorna_404(self, dispensador):
        r = dispensador.post("/circulacao/CHAVE-INVALIDA/proposta", json=PAYLOAD_PROPOSTA)
        assert r.status_code == 404

    def test_paciente_nao_pode_propor(self, paciente, circulacao_enviada):
        chave = circulacao_enviada["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        assert r.status_code == 403

    def test_prescritor_nao_pode_propor(self, prescritor, circulacao_enviada):
        chave = circulacao_enviada["chave_circulacao"]
        r = prescritor.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        assert r.status_code == 403

    def test_proposta_sem_campos_opcionais(self, dispensador, circulacao_enviada, db_path):
        """local_texto e instrucoes_preparo são opcionais."""
        chave = circulacao_enviada["chave_circulacao"]
        r = dispensador.post(
            f"/circulacao/{chave}/proposta",
            json={"data_hora_proposta": "2026-07-01T09:00:00"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["local_texto"] is None
        assert r.json()["instrucoes_preparo"] is None


# ---------------------------------------------------------------------------
# 11–17. POST /circulacao/{chave}/confirmar
# ---------------------------------------------------------------------------

class TestConfirmar:

    def test_confirmar_valido_muda_status(self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/confirmar")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "confirmado_paciente"
        assert _get_status_db(db_path, circulacao_com_proposta["protocolo"]) == "confirmado_paciente"

    def test_confirmar_grava_evento(self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        paciente.post(f"/circulacao/{chave}/confirmar")
        tipos = [e["tipo_evento"] for e in _get_eventos_db(db_path, circulacao_com_proposta["protocolo"])]
        assert "circulacao_confirmada_paciente" in tipos

    def test_confirmar_evento_registra_confirmado_por(self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        paciente.post(f"/circulacao/{chave}/confirmar")
        eventos = _get_eventos_db(db_path, circulacao_com_proposta["protocolo"])
        ev = next(e for e in eventos if e["tipo_evento"] == "circulacao_confirmada_paciente")
        assert "confirmado_por" in ev["dados"]

    def test_confirmar_estado_incompativel_retorna_409(self, paciente, circulacao_enviada):
        # circulação em 'enviado_laboratorio', precisa estar em 'proposta_recebida'
        chave = circulacao_enviada["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/confirmar")
        assert r.status_code == 409

    def test_confirmar_chave_inexistente_retorna_404(self, paciente):
        r = paciente.post("/circulacao/CHAVE-INVALIDA/confirmar")
        assert r.status_code == 404

    def test_dispensador_nao_pode_confirmar(self, dispensador, circulacao_com_proposta):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/confirmar")
        assert r.status_code == 403

    def test_prescritor_nao_pode_confirmar(self, prescritor, circulacao_com_proposta):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = prescritor.post(f"/circulacao/{chave}/confirmar")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# 18–29. POST /circulacao/{chave}/desmarcar
# ---------------------------------------------------------------------------

class TestDesmarcar:

    def test_paciente_desmarca_de_proposta_recebida(
            self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "desmarcado_paciente"
        assert _get_status_db(db_path, circulacao_com_proposta["protocolo"]) == "desmarcado_paciente"

    def test_paciente_desmarca_de_confirmado_paciente(
            self, paciente, circulacao_confirmada, db_path):
        chave = circulacao_confirmada["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "desmarcado_paciente"

    def test_dispensador_desmarca_de_enviado_laboratorio(
            self, dispensador, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "desmarcado_laboratorio"
        assert _get_status_db(db_path, circulacao_enviada["protocolo"]) == "desmarcado_laboratorio"

    def test_dispensador_desmarca_de_proposta_recebida(
            self, dispensador, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "desmarcado_laboratorio"

    def test_dispensador_desmarca_de_confirmado_paciente(
            self, dispensador, circulacao_confirmada, db_path):
        chave = circulacao_confirmada["chave_circulacao"]
        r = dispensador.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "desmarcado_laboratorio"

    def test_paciente_nao_pode_desmarcar_de_enviado_laboratorio(
            self, paciente, circulacao_enviada):
        """enviado_laboratorio → desmarcado_paciente não é transição válida."""
        chave = circulacao_enviada["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 409

    def test_estado_terminal_bloqueia_desmarcacao(self, paciente, circulacao, db_path):
        """Circulação já expirada não aceita desmarcação."""
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'expirado' WHERE protocolo = ?",
            (circulacao["protocolo"],),
        )
        conn.commit()
        conn.close()
        chave = circulacao["chave_circulacao"]
        r = paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 409

    def test_desmarcar_chave_inexistente_retorna_404(self, paciente):
        r = paciente.post("/circulacao/CHAVE-INVALIDA/desmarcar", json={})
        assert r.status_code == 404

    def test_prescritor_nao_pode_desmarcar(self, prescritor, circulacao_com_proposta):
        chave = circulacao_com_proposta["chave_circulacao"]
        r = prescritor.post(f"/circulacao/{chave}/desmarcar", json={})
        assert r.status_code == 403

    def test_evento_desmarcada_paciente_inserido(
            self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        tipos = [e["tipo_evento"] for e in _get_eventos_db(db_path, circulacao_com_proposta["protocolo"])]
        assert "circulacao_desmarcada_paciente" in tipos

    def test_evento_desmarcada_laboratorio_inserido(
            self, dispensador, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/desmarcar", json={})
        tipos = [e["tipo_evento"] for e in _get_eventos_db(db_path, circulacao_com_proposta["protocolo"])]
        assert "circulacao_desmarcada_laboratorio" in tipos

    def test_desmarcar_com_motivo_persiste_no_evento(
            self, paciente, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        motivo = "Mudança de planos do paciente"
        paciente.post(f"/circulacao/{chave}/desmarcar", json={"motivo": motivo})
        eventos = _get_eventos_db(db_path, circulacao_com_proposta["protocolo"])
        ev = next(e for e in eventos if e["tipo_evento"] == "circulacao_desmarcada_paciente")
        assert ev["dados"]["motivo"] == motivo


# ---------------------------------------------------------------------------
# 30–34. Não regressão
# ---------------------------------------------------------------------------

class TestNaoRegressao:

    def test_get_circulacao_funciona_apos_proposta(
            self, prescritor, circulacao_com_proposta):
        """GET /circulacao/{chave} ainda retorna 200 após proposta (Ticket 53)."""
        chave = circulacao_com_proposta["chave_circulacao"]
        r = prescritor.get(f"/circulacao/{chave}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "proposta_recebida"

    def test_pedido_nao_muda_apos_proposta(
            self, dispensador, prescritor, pedido, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        assert _get_pedido_status_db(db_path, pedido) == "emitido"

    def test_itens_nao_mudam_apos_proposta(
            self, dispensador, prescritor, pedido, circulacao_enviada, db_path):
        chave = circulacao_enviada["chave_circulacao"]
        dispensador.post(f"/circulacao/{chave}/proposta", json=PAYLOAD_PROPOSTA)
        for s in _get_itens_status_db(db_path, pedido):
            assert s == "pendente"

    def test_pedido_nao_muda_apos_confirmar(
            self, paciente, pedido, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        paciente.post(f"/circulacao/{chave}/confirmar")
        assert _get_pedido_status_db(db_path, pedido) == "emitido"

    def test_pedido_nao_muda_apos_desmarcar(
            self, paciente, pedido, circulacao_com_proposta, db_path):
        chave = circulacao_com_proposta["chave_circulacao"]
        paciente.post(f"/circulacao/{chave}/desmarcar", json={})
        assert _get_pedido_status_db(db_path, pedido) == "emitido"
