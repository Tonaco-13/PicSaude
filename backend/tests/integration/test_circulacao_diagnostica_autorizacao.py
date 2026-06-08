"""TICKET-5C-BIS-D — Autorização mínima de ownership em circulacao_diagnostica.py.

Espelha os outros *_autorizacao.py. Particularidades:
- O módulo não tinha ownership por identidade (só papel + estado) — fechado aqui.
- `chave_circulacao` é capability; identidade é validada por cima (chave vazada
  para outro paciente → 403).
- Dispensador liga-se por `org_id` (prestadores.cnpj → org_id). Pós-C.1 (na main),
  o schema institucional existe na PG: sem prestador → fail-closed 403; com prestador
  cujo CNPJ casa a org da circulação → 2xx; org distinta / inativo → 403 (cobertos abaixo).

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

_CNS_PRESC = "111111111111111"   # prescritor do pedido (dono)
_CNS_OUTRO = "222222222222222"
_CPF_PAC   = "44455566677"        # paciente do pedido (dono da circulação)
_CPF_OUTRO = "99988877766"
_CNPJ_DISP = "12345678000195"
_ORG_A     = "org-aaa"

_TABELAS = ("circulacoes_diagnosticas", "circulacao_diagnostica_itens")


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


def _item_id(outer_conn, pedido_proto):
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens "
            "WHERE pedido_id = (SELECT id FROM pedidos_exame WHERE protocolo = %s) "
            "ORDER BY id LIMIT 1",
            (pedido_proto,),
        )
        return cur.fetchone()[0]


def _criar_circulacao(client, outer_conn, pedido_proto, paciente_cpf=_CPF_PAC, org_id=_ORG_A):
    item = _item_id(outer_conn, pedido_proto)
    payload = {"org_id": org_id, "unidade_id": "u1", "item_ids": [item]}
    r = client.post(f"/pedidos-exame/{pedido_proto}/circulacao", json=payload,
                    headers=_headers(_tok(paciente_cpf, "paciente")))
    assert r.status_code == 201, r.text
    return r.json()["chave_circulacao"]


# ===========================================================================
# criar — paciente dono do pedido (fecha o bug ativo) + rollback
# ===========================================================================

def test_criar_paciente_nao_dono_403_rollback(client, outer_conn):
    ped = _criar_pedido(client)            # paciente do pedido = _CPF_PAC
    item = _item_id(outer_conn, ped)
    base = _contagens(outer_conn)
    r = client.post(f"/pedidos-exame/{ped}/circulacao",
                    json={"org_id": _ORG_A, "unidade_id": "u1", "item_ids": [item]},
                    headers=_headers(_tok(_CPF_OUTRO, "paciente")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"
    assert _contagens(outer_conn) == base


def test_criar_paciente_dono_201(client, outer_conn):
    ped = _criar_pedido(client)
    assert _criar_circulacao(client, outer_conn, ped)  # paciente dono → 201


# ===========================================================================
# GET por chave — matriz de identidade (chave vazada → 403; dispensador fail-closed)
# ===========================================================================

def test_get_matriz_identidade(client, outer_conn):
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped)
    url = f"/circulacao/{chave}"

    assert client.get(url, headers=_headers(_tok(_CPF_PAC, "paciente"))).status_code == 200       # dono
    assert client.get(url, headers=_headers(_tok(_CNS_PRESC, "prescritor"))).status_code == 200    # prescritor dono
    # chave vazada para outro paciente → 403
    r = client.get(url, headers=_headers(_tok(_CPF_OUTRO, "paciente")))
    assert r.status_code == 403, r.text
    # outro prescritor → 403
    assert client.get(url, headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403
    # dispensador → 403 (fail-closed na PG, schema institucional ausente)
    assert client.get(url, headers=_headers(_tok(_CNPJ_DISP, "dispensador"))).status_code == 403


# ===========================================================================
# Mutações — dispensador fail-closed + paciente não-dono
# ===========================================================================

def test_dispensador_mutacoes_fail_closed_403(client, outer_conn):
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped)
    disp = _headers(_tok(_CNPJ_DISP, "dispensador"))
    # ownership (403) precede estado (409) → dispensador sempre 403 na PG
    assert client.post(f"/circulacao/{chave}/proposta",
                       json={"data_hora_proposta": "2026-07-01T10:00:00"}, headers=disp).status_code == 403
    assert client.post(f"/circulacao/{chave}/realizar", json={}, headers=disp).status_code == 403
    assert client.post(f"/circulacao/{chave}/remarcar",
                       json={"org_id": _ORG_A, "unidade_id": "u1"}, headers=disp).status_code == 403


def test_paciente_nao_dono_mutacoes_403(client, outer_conn):
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped)
    outro = _headers(_tok(_CPF_OUTRO, "paciente"))
    assert client.post(f"/circulacao/{chave}/confirmar", headers=outro).status_code == 403
    assert client.post(f"/circulacao/{chave}/desmarcar", json={}, headers=outro).status_code == 403


# ===========================================================================
# Dispensador — resolução POSITIVA (pós-C.1: schema org_id na PG).
# Prestador semeado; resolver prestadores.cnpj→org_id liga por igualdade de org.
# ===========================================================================

_CNPJ_MASC  = "98.765.432/0001-10"
_CNPJ_LIMPO = "98765432000110"


def _seed_prestador(client, org_id, cnpj, nome="Lab", tipo="laboratorio"):
    r = client.post("/prestadores", json={
        "org_id": org_id, "nome": nome, "tipo": tipo, "cnpj": cnpj,
    }, headers=_headers(_tok("admin", "admin")))
    assert r.status_code == 201, r.text


def test_disp_org_match_get_e_proposta_2xx(client, outer_conn):
    """Prestador cujo CNPJ resolve para a org da circulação: GET 200 e a mutação de
    domínio do laboratório (/proposta) → 200. O estado é conduzido a
    'enviado_laboratorio' (pré-condição de /proposta) via setup, pois a transição
    selecionado→enviado_laboratorio vem de outro fluxo, fora deste router."""
    _seed_prestador(client, _ORG_A, _CNPJ_DISP)
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_DISP, "dispensador"))
    assert client.get(f"/circulacao/{chave}", headers=disp).status_code == 200
    # pré-condição de /proposta: estado enviado_laboratorio
    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'enviado_laboratorio' "
            "WHERE chave_circulacao = %s", (chave,),
        )
    r = client.post(f"/circulacao/{chave}/proposta",
                    json={"data_hora_proposta": "2026-07-01T10:00:00"}, headers=disp)
    assert r.status_code == 200, r.text


def test_disp_cnpj_mascarado_resolve_200(client, outer_conn):
    """CNPJ mascarado no cadastro, limpo no JWT: normalização read-side liga."""
    _seed_prestador(client, "org-masc", _CNPJ_MASC)
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped, org_id="org-masc")
    disp = _headers(_tok(_CNPJ_LIMPO, "dispensador"))
    assert client.get(f"/circulacao/{chave}", headers=disp).status_code == 200


def test_disp_org_diferente_403(client, outer_conn):
    """Prestador resolve para outra org que não a da circulação → 403."""
    _seed_prestador(client, "org-outra", _CNPJ_DISP)
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_DISP, "dispensador"))
    assert client.get(f"/circulacao/{chave}", headers=disp).status_code == 403


def test_disp_inativo_403(client, outer_conn):
    """Prestador inativo não resolve → 403 (semeado direto; CRUD só cria ativo=true)."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em) "
            "VALUES (%s,%s,%s,%s,%s, false, %s)",
            ("p-inativo", _ORG_A, "Lab Inativo", "laboratorio", _CNPJ_DISP, "2026-01-01"),
        )
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped, org_id=_ORG_A)
    disp = _headers(_tok(_CNPJ_DISP, "dispensador"))
    assert client.get(f"/circulacao/{chave}", headers=disp).status_code == 403


# ===========================================================================
# admin bypass + anti-leak (403 precede 409 de estado)
# ===========================================================================

def test_admin_bypass_get(client, outer_conn):
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped)
    assert client.get(f"/circulacao/{chave}", headers=_headers(_tok("admin", "admin"))).status_code == 200


def test_antileak_403_precede_409(client, outer_conn):
    # confirmar exige 'proposta_recebida'; a circulação está em 'selecionado'.
    # Um não-dono recebe 403 (ownership) ANTES do 409 (estado).
    ped = _criar_pedido(client)
    chave = _criar_circulacao(client, outer_conn, ped)
    r = client.post(f"/circulacao/{chave}/confirmar", headers=_headers(_tok(_CPF_OUTRO, "paciente")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_da_circulacao_diagnostica"
