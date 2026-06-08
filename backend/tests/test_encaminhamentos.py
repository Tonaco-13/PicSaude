"""Testes SQLite — TICKET-ENCAMINHAMENTO-E1."""
from __future__ import annotations

import sqlite3

from tests.conftest import RoleClient


_CNS_ORIGEM = "123456789012345"
_CNS_DESTINO = "222222222222222"
_CPF_PACIENTE = "12345678901"


def _payload(**overrides):
    base = {
        "cns_prescritor": _CNS_ORIGEM,
        "nome_prescritor": "Dr. Origem",
        "cpf_paciente": _CPF_PACIENTE,
        "nome_paciente": "Paciente Teste",
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "Cardiologia",
        "cid": "I10",
        "justificativa_clinica": "Avaliar hipertensao refrataria",
        "itens": [
            {
                "especialidade": "Cardiologia",
                "procedimento": "Consulta especializada",
                "motivo": "Ajuste terapeutico",
            }
        ],
    }
    return {**base, **overrides}


def _client_as(shared, role: str, sub: str):
    class _Custom(RoleClient):
        def _activate(self):
            from app.main import app
            from app.auth.dependencies import get_current_user
            app.dependency_overrides[get_current_user] = lambda: {"role": role, "sub": sub}

    return _Custom(shared, role)


def _criar(prescritor):
    r = prescritor.post("/encaminhamentos", json=_payload())
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def test_emissao_digital_cria_custodia_e_ledger(prescritor, db_path):
    proto = _criar(prescritor)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    enc = conn.execute("SELECT id, status FROM encaminhamentos WHERE protocolo = ?", (proto,)).fetchone()
    assert enc["status"] == "emitido"
    assert conn.execute(
        "SELECT status_item FROM encaminhamento_itens WHERE encaminhamento_id = ?",
        (enc["id"],),
    ).fetchone()["status_item"] == "pendente"
    assert conn.execute(
        "SELECT detentor_tipo FROM encaminhamento_custodia WHERE encaminhamento_id = ?",
        (enc["id"],),
    ).fetchone()["detentor_tipo"] == "paciente"
    tipos = [
        r["tipo_evento"] for r in conn.execute(
            "SELECT tipo_evento FROM encaminhamento_eventos WHERE encaminhamento_id = ? ORDER BY id",
            (enc["id"],),
        ).fetchall()
    ]
    conn.close()
    assert tipos == ["encaminhamento_emitido", "custodia_transferida"]


def test_fisico_encerra_itens_sem_custodia(prescritor, db_path):
    r = prescritor.post("/encaminhamentos/fisica", json=_payload(cpf_paciente=None))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    enc = conn.execute("SELECT id, status FROM encaminhamentos WHERE protocolo = ?", (proto,)).fetchone()
    item = conn.execute(
        "SELECT status_item FROM encaminhamento_itens WHERE encaminhamento_id = ?",
        (enc["id"],),
    ).fetchone()
    custodia = conn.execute(
        "SELECT COUNT(*) AS n FROM encaminhamento_custodia WHERE encaminhamento_id = ?",
        (enc["id"],),
    ).fetchone()
    evento = conn.execute(
        "SELECT tipo_evento FROM encaminhamento_eventos WHERE encaminhamento_id = ?",
        (enc["id"],),
    ).fetchone()
    conn.close()
    assert enc["status"] == "encerrado_fisico"
    assert item["status_item"] == "encerrado_fisico"
    assert custodia["n"] == 0
    assert evento["tipo_evento"] == "encaminhamento_impresso"


def test_fluxo_destino_atende_origem_encerra(prescritor, _shared_client):
    proto = _criar(prescritor)
    destino = _client_as(_shared_client, "prescritor", _CNS_DESTINO)

    assert prescritor.post(f"/encaminhamentos/{proto}/agendar", json={}).status_code == 403
    r1 = destino.post(f"/encaminhamentos/{proto}/agendar", json={})
    assert r1.status_code == 200, r1.text
    r2 = destino.post(f"/encaminhamentos/{proto}/atender")
    assert r2.status_code == 200, r2.text
    r3 = prescritor.post(f"/encaminhamentos/{proto}/encerrar")
    assert r3.status_code == 200, r3.text
    assert r3.json()["status"] == "encerrado"


def test_transicao_invalida_retorna_409(prescritor):
    proto = _criar(prescritor)
    r = prescritor.post(f"/encaminhamentos/{proto}/encerrar")
    assert r.status_code == 409


def test_publico_nao_vaza_cpf_cid_justificativa(prescritor, _shared_client):
    proto = _criar(prescritor)
    r = _shared_client.get(f"/public/encaminhamentos/{proto}")
    assert r.status_code == 200, r.text
    data = r.json()
    dumped = str(data).lower()
    assert "12345678901" not in dumped
    assert "i10" not in dumped
    assert "hipertensao" not in dumped
    # neutralização core: nenhuma clínica no aberto
    assert "cardiologia" not in dumped              # especialidade / especialidade_destino
    assert "consulta especializada" not in dumped   # procedimento
    assert "especialidade" not in data and "especialidade_destino" not in data
    assert all("especialidade" not in it and "procedimento" not in it for it in data["itens"])
    # o job (validação) é preservado:
    assert data["status_encaminhamento"] == "emitido"
    assert data["itens"][0]["status_item"] == "pendente"


def test_pdf_e_qr_do_encaminhamento(prescritor):
    proto = _criar(prescritor)
    pdf = prescritor.get(f"/encaminhamentos/{proto}/pdf")
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    qr = prescritor.get(f"/encaminhamentos/{proto}/qr")
    assert qr.status_code == 200, qr.text
    assert qr.headers["content-type"] == "image/png"
    assert qr.content.startswith(b"\x89PNG")
