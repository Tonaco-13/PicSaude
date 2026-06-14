"""TICKET-ENCAMINHAMENTO-E2 — Contrarreferência: autorização, ledger duplo, público NEUTRO.

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
_CONTEUDO = "RETORNO_CLINICO_SECRETO_pa_controlada_alta_ambulatorial"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _payload_enc(**overrides) -> dict:
    base = {
        "cns_prescritor": SEED_PRESCRITOR_CNS,
        "nome_prescritor": SEED_PRESCRITOR_NOME,
        "cpf_paciente": SEED_PACIENTE_CPF,
        "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO,
        "especialidade_destino": "Cardiologia",
        "cid": "I10",
        "justificativa_clinica": "Avaliacao especializada",
        "itens": [{"especialidade": "Cardiologia", "procedimento": "Consulta", "motivo": "HAS"}],
    }
    return {**base, **overrides}


def _criar_enc(client, seed_usuario) -> str:
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/encaminhamentos", json=_payload_enc(), headers=_headers(token))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _levar_a_atendido(client, proto: str) -> None:
    destino = _headers(_tok(_CNS_DESTINO, "prescritor"))
    assert client.post(f"/encaminhamentos/{proto}/agendar", json={}, headers=destino).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender", headers=destino).status_code == 200


def _contrarreferir(client, proto: str, token: str, conteudo: str = _CONTEUDO):
    return client.post(
        f"/encaminhamentos/{proto}/contrarreferir",
        json={"conteudo_clinico": conteudo},
        headers=_headers(token),
    )


# ===========================================================================
# Feliz — destino contrarrefere; objeto derivado + ledger duplo + parent move
# ===========================================================================

def test_contrarreferir_destino_201_objeto_ledger_duplo(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)
    _levar_a_atendido(client, proto)

    r = _contrarreferir(client, proto, _tok(_CNS_DESTINO, "prescritor"))
    assert r.status_code == 201, r.text
    cr_proto = r.json()["protocolo_contrarreferencia"]
    assert r.json()["status_encaminhamento"] == "contrarreferido"

    with outer_conn.cursor() as cur:
        cur.execute("SELECT status, cns_autor, conteudo_clinico FROM contrarreferencias WHERE protocolo = %s", (cr_proto,))
        row = cur.fetchone()
        assert row == ("registrada", _CNS_DESTINO, _CONTEUDO)
        # parent transicionou
        cur.execute("SELECT status FROM encaminhamentos WHERE protocolo = %s", (proto,))
        assert cur.fetchone()[0] == "contrarreferido"
        # ledger DUPLO: evento na contrarreferência E no encaminhamento
        cur.execute("SELECT COUNT(*) FROM contrarreferencia_eventos WHERE tipo_evento = 'contrarreferencia_registrada'")
        assert cur.fetchone()[0] == 1
        cur.execute(
            "SELECT COUNT(*) FROM encaminhamento_eventos e JOIN encaminhamentos en ON en.id = e.encaminhamento_id "
            "WHERE en.protocolo = %s AND e.tipo_evento = 'contrarreferencia_registrada'", (proto,))
        assert cur.fetchone()[0] == 1
        # custódia retorna à origem
        cur.execute(
            "SELECT detentor_tipo, detentor_id FROM contrarreferencia_custodia c "
            "JOIN contrarreferencias cr ON cr.id = c.contrarreferencia_id WHERE cr.protocolo = %s", (cr_proto,))
        assert cur.fetchone() == ("prescritor", SEED_PRESCRITOR_CNS)


# ===========================================================================
# Ownership — só o destino contrarrefere
# ===========================================================================

def test_contrarreferir_somente_destino(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)
    _levar_a_atendido(client, proto)

    # origem (autor do encaminhamento) → 403
    assert _contrarreferir(client, proto, obter_token_prescritor(client, seed_usuario)).status_code == 403
    # outro prescritor → 403
    assert _contrarreferir(client, proto, _tok(_CNS_OUTRO, "prescritor")).status_code == 403
    # paciente → 403
    assert _contrarreferir(client, proto, _tok(SEED_PACIENTE_CPF, "paciente")).status_code == 403


# ===========================================================================
# Estado — exige 'atendido' (anti-leak: 403 não-destino precede 409 estado)
# ===========================================================================

def test_contrarreferir_estado_409_e_antileak(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)   # estado 'emitido' (não atendido)

    # destino sobre 'emitido' → 409 (estado inválido)
    assert _contrarreferir(client, proto, _tok(_CNS_DESTINO, "prescritor")).status_code == 409
    # não-destino sobre 'emitido' → 403 (ownership precede o 409 de estado)
    assert _contrarreferir(client, proto, _tok(_CNS_OUTRO, "prescritor")).status_code == 403


# ===========================================================================
# Ciência da origem — fluxo completo (parent encerra)
# ===========================================================================

def test_ciencia_origem_encerra(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)
    _levar_a_atendido(client, proto)
    assert _contrarreferir(client, proto, _tok(_CNS_DESTINO, "prescritor")).status_code == 201

    # origem dá ciência via /encerrar (contrarreferido → encerrado)
    r = client.post(f"/encaminhamentos/{proto}/encerrar", headers=_headers(obter_token_prescritor(client, seed_usuario)))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "encerrado"


# ===========================================================================
# GET autenticado — ownership; clínica visível ao dono
# ===========================================================================

def test_get_ownership_e_clinica_visivel(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)
    _levar_a_atendido(client, proto)
    cr_proto = _contrarreferir(client, proto, _tok(_CNS_DESTINO, "prescritor")).json()["protocolo_contrarreferencia"]
    url = f"/contrarreferencias/{cr_proto}"

    # autor (destino) vê — e a clínica está visível ao dono
    r = client.get(url, headers=_headers(_tok(_CNS_DESTINO, "prescritor")))
    assert r.status_code == 200 and _CONTEUDO in str(r.json())
    # origem vê
    assert client.get(url, headers=_headers(obter_token_prescritor(client, seed_usuario))).status_code == 200
    # paciente vê
    assert client.get(url, headers=_headers(_tok(SEED_PACIENTE_CPF, "paciente"))).status_code == 200
    # estranho → 403
    assert client.get(url, headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403
    assert client.get(url, headers=_headers(_tok(_CPF_OUTRO, "paciente"))).status_code == 403
    # admin → 200
    assert client.get(url, headers=_headers(_tok("admin", "admin"))).status_code == 200


# ===========================================================================
# Público NEUTRO — conteudo_clinico NUNCA no aberto
# ===========================================================================

def test_publico_neutro_sem_conteudo_clinico(client, outer_conn, seed_usuario, seed_paciente):
    proto = _criar_enc(client, seed_usuario)
    _levar_a_atendido(client, proto)
    cr_proto = _contrarreferir(client, proto, _tok(_CNS_DESTINO, "prescritor")).json()["protocolo_contrarreferencia"]

    r = client.get(f"/public/contrarreferencias/{cr_proto}")
    assert r.status_code == 200, r.text
    data = r.json()
    body = str(data)
    # NEUTRO: nenhuma clínica
    assert _CONTEUDO not in body
    assert "conteudo_clinico" not in data
    assert SEED_PACIENTE_CPF not in body
    # o job (validação) preservado
    assert data["status_contrarreferencia"] == "registrada"
    assert data["protocolo"] == cr_proto
    # inexistente → 404
    assert client.get("/public/contrarreferencias/nao-existe").status_code == 404
