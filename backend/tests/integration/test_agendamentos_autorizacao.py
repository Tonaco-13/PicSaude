"""TICKET-5C-BIS-C — Autorização mínima de ownership em agendamentos.py.

Espelha o §9. Particularidade: o prestador (role `dispensador`) é institucional —
ownership via `prestadores.cnpj → org_id`.

DISPENSADOR INSTITUCIONAL (pós-C.1): o schema org_id (Ticket 30:
`prestadores.org_id` + `unidades`) já está migrado na PG (TICKET-5C-BIS-C.1, na main).
O resolver `prestadores.cnpj → org_id` resolve de verdade: sem prestador cadastrado →
fail-closed 403; com prestador cujo CNPJ casa a org do agendamento → 2xx; org distinta
ou prestador inativo → 403. Ambos os lados são cobertos abaixo.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

_CNS_PRESC = "111111111111111"   # prescritor do pedido (dono)
_CNS_OUTRO = "222222222222222"
_CPF_PAC   = "44455566677"        # paciente do pedido (dono)
_CPF_OUTRO = "99988877766"
_ORG_A     = "org-aaa"
_CNPJ_A    = "12345678000195"

_TABELAS = ("agendamentos", "agendamento_eventos")


def _headers(t): return {"Authorization": f"Bearer {t}"}
def _tok(sub, role, nome="ATOR"): return criar_access_token(sub=sub, role=role, nome=nome)


def _contagens(outer_conn, tabelas=_TABELAS):
    out = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _criar_pedido(client, cns=_CNS_PRESC, cpf=_CPF_PAC):
    payload = {
        "cns_prescritor": cns, "nome_prescritor": "DR",
        "cpf_paciente": cpf, "nome_paciente": "PAC",
        "tipo_emissao": "novo", "prioridade": "rotina",
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }
    r = client.post("/pedidos-exame", json=payload, headers=_headers(_tok(cns, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _criar_agendamento(client, pedido_proto, creator_cns=_CNS_PRESC, org_id=_ORG_A):
    payload = {
        "pedido_protocolo": pedido_proto, "data_hora": "2026-07-01T10:00:00",
        "org_id": org_id, "unidade_id": "u1", "tipo_agendamento": "exame",
    }
    r = client.post("/agendamentos", json=payload, headers=_headers(_tok(creator_cns, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _novo_ag(client, org_id=_ORG_A):
    return _criar_agendamento(client, _criar_pedido(client), org_id=org_id)


# ===========================================================================
# Dispensador — fail-closed (schema institucional ausente na PG, §D1 / C.1)
# ===========================================================================

def test_dispensador_fail_closed_403(client):
    """Sem schema org_id de prestadores na PG, qualquer dispensador → 403,
    em todas as superfícies (get/criar/confirmar/listar). Fail-closed seguro."""
    ped = _criar_pedido(client)
    ag = _criar_agendamento(client, ped)
    disp = _headers(_tok(_CNPJ_A, "dispensador"))

    assert client.get(f"/agendamentos/{ag}", headers=disp).status_code == 403
    assert client.post(f"/agendamentos/{ag}/confirmar", headers=disp).status_code == 403
    assert client.get(f"/pedidos-exame/{ped}/agendamentos", headers=disp).status_code == 403
    # criar por dispensador também é negado (não resolve org)
    ped2 = _criar_pedido(client)
    r = client.post("/agendamentos", json={
        "pedido_protocolo": ped2, "data_hora": "2026-07-01T10:00:00",
        "org_id": _ORG_A, "unidade_id": "u1",
    }, headers=disp)
    assert r.status_code == 403, r.text


# ===========================================================================
# Dispensador — resolução POSITIVA (pós-C.1: schema org_id existe na PG).
# Prestador semeado (org_id + cnpj); o resolver prestadores.cnpj→org_id liga
# (ou nega) por igualdade de org. Espelho positivo do fail-closed acima.
# ===========================================================================

_CNPJ_MASC  = "98.765.432/0001-10"   # mesmo dígito-base de _CNPJ_LIMPO
_CNPJ_LIMPO = "98765432000110"


def _seed_prestador(client, org_id, cnpj, nome="Lab", tipo="laboratorio"):
    r = client.post("/prestadores", json={
        "org_id": org_id, "nome": nome, "tipo": tipo, "cnpj": cnpj,
    }, headers=_headers(_tok("admin", "admin")))
    assert r.status_code == 201, r.text


def test_disp_org_match_confirma_200(client):
    """Prestador cujo CNPJ resolve para a org do agendamento: GET e confirmar
    liberados (2xx). Positivo simétrico ao fail-closed."""
    _seed_prestador(client, _ORG_A, _CNPJ_A)
    ag = _novo_ag(client, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.get(f"/agendamentos/{ag}", headers=disp).status_code == 200
    assert client.post(f"/agendamentos/{ag}/confirmar", headers=disp).status_code == 200


def test_disp_cnpj_mascarado_resolve_200(client):
    """CNPJ gravado mascarado no cadastro e enviado limpo no JWT: a normalização
    READ-SIDE do resolver faz o vínculo (prova o normalize_cnpj na leitura)."""
    _seed_prestador(client, "org-masc", _CNPJ_MASC)
    ag = _novo_ag(client, org_id="org-masc")
    disp = _headers(_tok(_CNPJ_LIMPO, "dispensador"))
    assert client.get(f"/agendamentos/{ag}", headers=disp).status_code == 200


def test_disp_org_diferente_403(client):
    """Prestador resolve para org distinta da do agendamento → 403 (vínculo existe,
    mas é de outra org)."""
    _seed_prestador(client, "org-outra", _CNPJ_A)
    ag = _novo_ag(client, org_id=_ORG_A)   # agendamento em org-aaa, não org-outra
    disp = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.get(f"/agendamentos/{ag}", headers=disp).status_code == 403


def test_disp_inativo_403(client, outer_conn):
    """Prestador inativo não resolve (resolver filtra ativo = true) → 403.
    Semeado direto via outer_conn — o CRUD só cria ativo=true."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em) "
            "VALUES (%s,%s,%s,%s,%s, false, %s)",
            ("p-inativo", _ORG_A, "Lab Inativo", "laboratorio", _CNPJ_A, "2026-01-01"),
        )
    ag = _novo_ag(client, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_A, "dispensador"))
    assert client.get(f"/agendamentos/{ag}", headers=disp).status_code == 403


# ===========================================================================
# criar — dono do pedido (§D3) + rollback
# ===========================================================================

def test_criar_por_prescritor_e_paciente_dono_201(client):
    ped = _criar_pedido(client)
    r1 = client.post("/agendamentos", json={
        "pedido_protocolo": ped, "data_hora": "2026-07-01T10:00:00",
        "org_id": _ORG_A, "unidade_id": "u1",
    }, headers=_headers(_tok(_CNS_PRESC, "prescritor")))
    assert r1.status_code == 201, r1.text

    ped2 = _criar_pedido(client)
    r2 = client.post("/agendamentos", json={
        "pedido_protocolo": ped2, "data_hora": "2026-07-01T10:00:00",
        "org_id": _ORG_A, "unidade_id": "u1",
    }, headers=_headers(_tok(_CPF_PAC, "paciente")))
    assert r2.status_code == 201, r2.text


def test_criar_por_nao_dono_403_rollback(client, outer_conn):
    ped = _criar_pedido(client)
    base = _contagens(outer_conn)
    r = client.post("/agendamentos", json={
        "pedido_protocolo": ped, "data_hora": "2026-07-01T10:00:00",
        "org_id": _ORG_A, "unidade_id": "u1",
    }, headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido"
    assert _contagens(outer_conn) == base


# ===========================================================================
# listar por pedido — prescritor/paciente dono
# ===========================================================================

def test_listar_por_pedido_prescritor_200_outro_403(client):
    ped = _criar_pedido(client)
    _criar_agendamento(client, ped)
    url = f"/pedidos-exame/{ped}/agendamentos"
    assert client.get(url, headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 200
    assert client.get(url, headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403


# ===========================================================================
# GET / transições / remarcar — ownership
# ===========================================================================

def test_get_ownership(client):
    ag = _novo_ag(client)
    assert client.get(f"/agendamentos/{ag}", headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 200
    assert client.get(f"/agendamentos/{ag}", headers=_headers(_tok(_CPF_PAC, "paciente"))).status_code == 200
    r = client.get(f"/agendamentos/{ag}", headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert client.get(f"/agendamentos/{ag}", headers=_headers(_tok(_CPF_OUTRO, "paciente"))).status_code == 403


def test_confirmar_nao_dono_403_dono_200(client):
    ag = _novo_ag(client)
    assert client.post(f"/agendamentos/{ag}/confirmar", headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403
    assert client.post(f"/agendamentos/{ag}/confirmar", headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 200


def test_remarcar_nao_dono_403_dono_201(client):
    ag = _novo_ag(client)
    assert client.post(f"/agendamentos/{ag}/remarcar", json={"data_hora": "2026-08-01T09:00:00"},
                       headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403
    assert client.post(f"/agendamentos/{ag}/remarcar", json={"data_hora": "2026-08-01T09:00:00"},
                       headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 201


# ===========================================================================
# admin bypass + anti-leak
# ===========================================================================

def test_admin_bypass(client):
    ag = _novo_ag(client)
    assert client.get(f"/agendamentos/{ag}", headers=_headers(_tok("admin", "admin"))).status_code == 200
    assert client.post(f"/agendamentos/{ag}/confirmar", headers=_headers(_tok("admin", "admin"))).status_code == 200


def test_antileak_403_precede_409(client):
    ag = _novo_ag(client)
    assert client.post(f"/agendamentos/{ag}/cancelar", headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 200
    # não-dono confirma agendamento cancelado: 403 (ownership), não 409 (estado)
    r = client.post(f"/agendamentos/{ag}/confirmar", headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_agendamento"
