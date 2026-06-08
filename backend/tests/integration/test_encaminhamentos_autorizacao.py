"""TICKET-ENCAMINHAMENTO-E1 — Autorização e fluxo PG.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


_CNS_DESTINO = "222222222222222"
_CNS_OUTRO = "333333333333333"
_CPF_OUTRO = "99988877766"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _payload(**overrides) -> dict:
    base = {
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": SEED_PRESCRITOR_NOME,
        "cpf_paciente": SEED_PACIENTE_CPF,
        "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "Cardiologia",
        "cid": "I10",
        "justificativa_clinica": "Avaliacao especializada",
        "itens": [
            {
                "especialidade": "Cardiologia",
                "procedimento": "Consulta especializada",
                "motivo": "Hipertensao refrataria",
            }
        ],
    }
    return {**base, **overrides}


def _criar(client, seed_usuario, **overrides) -> str:
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/encaminhamentos", json=_payload(**overrides), headers=_headers(token))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _enc_id(outer_conn, protocolo: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM encaminhamentos WHERE protocolo = %s", (protocolo,))
        return cur.fetchone()[0]


def test_emissao_digital_201_custodia_ledger(
    client, outer_conn, seed_usuario, seed_paciente,
):
    proto = _criar(client, seed_usuario)
    enc_id = _enc_id(outer_conn, proto)
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM encaminhamentos WHERE id = %s", (enc_id,))
        assert cur.fetchone()[0] == "emitido"
        cur.execute("SELECT status_item FROM encaminhamento_itens WHERE encaminhamento_id = %s", (enc_id,))
        assert cur.fetchone()[0] == "pendente"
        cur.execute("SELECT detentor_tipo FROM encaminhamento_custodia WHERE encaminhamento_id = %s", (enc_id,))
        assert cur.fetchone()[0] == "paciente"
        cur.execute("SELECT tipo_evento FROM encaminhamento_eventos WHERE encaminhamento_id = %s ORDER BY id", (enc_id,))
        assert [r[0] for r in cur.fetchall()] == ["encaminhamento_emitido", "custodia_transferida"]


def test_fisica_201_sem_custodia_com_cpf_sentinela(
    client, outer_conn, seed_usuario,
):
    token = obter_token_prescritor(client, seed_usuario)
    payload = _payload(cpf_paciente=None, nome_paciente="Paciente Papel")
    r = client.post("/encaminhamentos/fisica", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text
    enc_id = _enc_id(outer_conn, r.json()["protocolo"])
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status, paciente_id FROM encaminhamentos WHERE id = %s", (enc_id,))
        status, paciente_id = cur.fetchone()
        assert status == "encerrado_fisico"
        cur.execute("SELECT cpf FROM pacientes WHERE id = %s", (paciente_id,))
        assert cur.fetchone()[0] == "00000000000"
        cur.execute("SELECT COUNT(*) FROM encaminhamento_custodia WHERE encaminhamento_id = %s", (enc_id,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT tipo_evento FROM encaminhamento_eventos WHERE encaminhamento_id = %s", (enc_id,))
        assert cur.fetchone()[0] == "encaminhamento_impresso"


def test_ownership_get_matriz(client, seed_usuario, seed_paciente):
    token_origem = obter_token_prescritor(client, seed_usuario)
    proto = _criar(client, seed_usuario)

    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(token_origem)).status_code == 200
    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(_tok(_CNS_DESTINO, "prescritor"))).status_code == 200
    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(_tok(SEED_PACIENTE_CPF, "paciente"))).status_code == 200
    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(_tok("admin", "admin"))).status_code == 200

    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403
    assert client.get(f"/encaminhamentos/{proto}", headers=_headers(_tok(_CPF_OUTRO, "paciente"))).status_code == 403


def test_agendar_atender_somente_destino(client, seed_usuario, seed_paciente):
    token_origem = obter_token_prescritor(client, seed_usuario)
    token_destino = _tok(_CNS_DESTINO, "prescritor")
    proto = _criar(client, seed_usuario)

    r_origem = client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=_headers(token_origem))
    assert r_origem.status_code == 403, r_origem.text
    r_paciente = client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=_headers(_tok(SEED_PACIENTE_CPF, "paciente")))
    assert r_paciente.status_code == 403
    assert client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=_headers(token_destino)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender", headers=_headers(token_destino)).status_code == 200


def test_encerrar_cancelar_somente_origem(client, seed_usuario, seed_paciente):
    token_origem = obter_token_prescritor(client, seed_usuario)
    token_destino = _tok(_CNS_DESTINO, "prescritor")
    proto = _criar(client, seed_usuario)

    assert client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=_headers(token_destino)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender", headers=_headers(token_destino)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/encerrar", headers=_headers(token_destino)).status_code == 403
    assert client.post(f"/encaminhamentos/{proto}/encerrar", headers=_headers(token_origem)).status_code == 200

    proto2 = _criar(client, seed_usuario)
    assert client.post(f"/encaminhamentos/{proto2}/cancelar", json={}, headers=_headers(token_destino)).status_code == 403
    assert client.post(f"/encaminhamentos/{proto2}/cancelar", json={}, headers=_headers(token_origem)).status_code == 200


def test_antileak_nao_dono_terminal_403_precede_409(
    client, seed_usuario, seed_paciente,
):
    token_origem = obter_token_prescritor(client, seed_usuario)
    proto = _criar(client, seed_usuario)
    assert client.post(f"/encaminhamentos/{proto}/cancelar", json={}, headers=_headers(token_origem)).status_code == 200
    r = client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_encaminhamento"


def test_transicoes_invalidas_409(client, seed_usuario, seed_paciente):
    token_origem = obter_token_prescritor(client, seed_usuario)
    token_destino = _tok(_CNS_DESTINO, "prescritor")
    proto = _criar(client, seed_usuario)
    assert client.post(f"/encaminhamentos/{proto}/encerrar", headers=_headers(token_origem)).status_code == 409
    assert client.post(f"/encaminhamentos/{proto}/atender", headers=_headers(token_destino)).status_code == 409


def test_negado_terminal_por_origem_ou_destino(client, seed_usuario, seed_paciente):
    token_origem = obter_token_prescritor(client, seed_usuario)
    proto = _criar(client, seed_usuario)
    r = client.post(f"/encaminhamentos/{proto}/negar", json={"motivo": "sem indicacao"}, headers=_headers(token_origem))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "negado"

    proto2 = _criar(client, seed_usuario)
    r2 = client.post(f"/encaminhamentos/{proto2}/negar", json={"motivo": "agenda indisponivel"}, headers=_headers(_tok(_CNS_DESTINO, "prescritor")))
    assert r2.status_code == 200, r2.text


def test_publico_nao_vaza_dados_sensiveis(client, seed_usuario, seed_paciente):
    proto = _criar(client, seed_usuario)
    r = client.get(f"/public/encaminhamentos/{proto}")
    assert r.status_code == 200, r.text
    body = str(r.json())
    assert SEED_PACIENTE_CPF not in body
    assert "I10" not in body
    assert "Avaliacao especializada" not in body
