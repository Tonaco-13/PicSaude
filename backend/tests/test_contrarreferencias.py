"""Testes SQLite — TICKET-ENCAMINHAMENTO-E2 (contrarreferência)."""
from __future__ import annotations

import sqlite3

from tests.conftest import RoleClient


_CNS_ORIGEM = "123456789012345"
_CNS_DESTINO = "222222222222222"
_CPF_PACIENTE = "12345678901"


def _payload_enc(**overrides):
    base = {
        "cns_prescritor": _CNS_ORIGEM,
        "nome_prescritor": "Dr. Origem",
        "cpf_paciente": _CPF_PACIENTE,
        "nome_paciente": "Paciente Teste",
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "Cardiologia",
        "cid": "I10",
        "justificativa_clinica": "Avaliar hipertensao refrataria",
        "itens": [{"especialidade": "Cardiologia", "procedimento": "Consulta", "motivo": "HAS"}],
    }
    return {**base, **overrides}


def _client_as(shared, role: str, sub: str):
    class _Custom(RoleClient):
        def _activate(self):
            from app.main import app
            from app.auth.dependencies import get_current_user
            app.dependency_overrides[get_current_user] = lambda: {"role": role, "sub": sub}

    return _Custom(shared, role)


def _criar_e_atender(prescritor, shared) -> tuple[str, "RoleClient"]:
    r = prescritor.post("/encaminhamentos", json=_payload_enc())
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]
    destino = _client_as(shared, "prescritor", _CNS_DESTINO)
    assert destino.post(f"/encaminhamentos/{proto}/agendar", json={}).status_code == 200
    assert destino.post(f"/encaminhamentos/{proto}/atender").status_code == 200
    return proto, destino


def test_contrarreferir_fluxo_e_ledger_duplo(prescritor, _shared_client, db_path):
    proto, destino = _criar_e_atender(prescritor, _shared_client)
    r = destino.post(f"/encaminhamentos/{proto}/contrarreferir",
                     json={"conteudo_clinico": "Retorno: PA controlada, alta ambulatorial"})
    assert r.status_code == 201, r.text
    cr_proto = r.json()["protocolo_contrarreferencia"]
    assert r.json()["status_encaminhamento"] == "contrarreferido"

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    assert conn.execute("SELECT status FROM encaminhamentos WHERE protocolo=?", (proto,)).fetchone()["status"] == "contrarreferido"
    assert conn.execute("SELECT status, cns_autor FROM contrarreferencias WHERE protocolo=?", (cr_proto,)).fetchone()["status"] == "registrada"
    # ledger duplo
    assert conn.execute("SELECT COUNT(*) c FROM contrarreferencia_eventos WHERE tipo_evento='contrarreferencia_registrada'").fetchone()["c"] == 1
    assert conn.execute(
        "SELECT COUNT(*) c FROM encaminhamento_eventos e JOIN encaminhamentos en ON en.id=e.encaminhamento_id "
        "WHERE en.protocolo=? AND e.tipo_evento='contrarreferencia_registrada'", (proto,)).fetchone()["c"] == 1
    conn.close()


def test_contrarreferir_somente_destino(prescritor, _shared_client):
    proto, _ = _criar_e_atender(prescritor, _shared_client)
    # origem (não-destino) → 403
    assert prescritor.post(f"/encaminhamentos/{proto}/contrarreferir",
                           json={"conteudo_clinico": "x"}).status_code == 403


def test_contrarreferir_exige_atendido_409(prescritor, _shared_client):
    r = prescritor.post("/encaminhamentos", json=_payload_enc())
    proto = r.json()["protocolo"]
    destino = _client_as(_shared_client, "prescritor", _CNS_DESTINO)
    # encaminhamento ainda 'emitido' → 409
    assert destino.post(f"/encaminhamentos/{proto}/contrarreferir",
                        json={"conteudo_clinico": "x"}).status_code == 409


def test_publico_cr_neutro(prescritor, _shared_client):
    proto, destino = _criar_e_atender(prescritor, _shared_client)
    cr_proto = destino.post(f"/encaminhamentos/{proto}/contrarreferir",
                            json={"conteudo_clinico": "SEGREDO_CLINICO_DIAGNOSTICO_XYZ"}).json()["protocolo_contrarreferencia"]
    r = _shared_client.get(f"/public/contrarreferencias/{cr_proto}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "segredo_clinico_diagnostico_xyz" not in str(data).lower()
    assert "conteudo_clinico" not in data
    assert data["status_contrarreferencia"] == "registrada"
