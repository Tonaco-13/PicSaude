"""TICKET-5C-BIS-D — Autorização mínima de ownership em circulacao_diagnostica.py.

Espelha os outros *_autorizacao.py. Particularidades:
- O módulo não tinha ownership por identidade (só papel + estado) — fechado aqui.
- `chave_circulacao` é capability; identidade é validada por cima (chave vazada
  para outro paciente → 403).
- Dispensador liga-se por `org_id` (prestadores.cnpj → org_id), MESMO gap
  institucional do C → **fail-closed (403) na PG** até a migration (TICKET-5C-BIS-C.1).
  A resolução POSITIVA do dispensador é coberta na suíte SQLite (test_circulacao_*).

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
