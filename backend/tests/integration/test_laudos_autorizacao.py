"""TICKET-5C-BIS-B — Autorização mínima de ownership em laudos.py.

Espelha o §9 da spec. Mirror de test_pedidos_exame_autorizacao.py.
Particularidade do módulo: o papel `prescritor` cobre DOIS atores — o **autor**
(responsável técnico) e o **solicitante** (prescritor do pedido vinculado).

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import SEED_PACIENTE_CPF  # noqa: F401 (mantém import estável)

# ---------------------------------------------------------------------------
# Identidades
# ---------------------------------------------------------------------------
_CNS_AUTOR_A   = "111111111111111"   # autor / responsável técnico
_CNS_SOLIC_S   = "222222222222222"   # prescritor solicitante (emite o pedido)
_CNS_OUTRO     = "333333333333333"   # nem autor nem solicitante
_CPF_PAC       = "44455566677"
_CPF_OUTRO_PAC = "99988877766"
_CNPJ_PREST    = "12345678000195"
_SENTINELA     = "00000000000"

_TABELAS = ("laudos", "laudo_eventos", "laudo_itens")


def _headers(token): return {"Authorization": f"Bearer {token}"}
def _tok(sub, role, nome="ATOR"): return criar_access_token(sub=sub, role=role, nome=nome)


def _contagens(outer_conn, tabelas=_TABELAS):
    out = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _laudo_id(outer_conn, proto):
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM laudos WHERE protocolo = %s", (proto,))
        return cur.fetchone()[0]


def _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, **over):
    payload = {
        "cns_autor": autor_cns, "nome_autor": "DR AUTOR",
        "cpf_paciente": paciente_cpf, "nome_paciente": "PACIENTE",
        "itens": [{"nome_exame": "HEMOGRAMA"}], **over,
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(autor_cns, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _criar_pedido(client, prescritor_cns, paciente_cpf=_CPF_PAC):
    payload = {
        "cns_prescritor": prescritor_cns, "nome_prescritor": "DR SOLIC",
        "cpf_paciente": paciente_cpf, "nome_paciente": "PACIENTE",
        "tipo_emissao": "novo", "prioridade": "rotina",
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }
    r = client.post("/pedidos-exame", json=payload, headers=_headers(_tok(prescritor_cns, "prescritor")))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ate_liberado(client, proto, autor_cns=_CNS_AUTOR_A):
    h = _headers(_tok(autor_cns, "prescritor"))
    assert client.post(f"/laudos/{proto}/assinar", headers=h).status_code == 200
    assert client.post(
        f"/laudos/{proto}/liberar", json={"cnpj_prestador": _CNPJ_PREST}, headers=h
    ).status_code == 200


# ===========================================================================
# Padrão A — criar / fisica (autor declarado vs JWT) + rollback
# ===========================================================================

def test_criar_autor_mismatch_403_rollback(client, outer_conn):
    base = _contagens(outer_conn)
    payload = {
        "cns_autor": _CNS_OUTRO, "nome_autor": "X",
        "cpf_paciente": _CPF_PAC, "nome_paciente": "P", "itens": [{"nome_exame": "X"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "autor_mismatch"
    assert _contagens(outer_conn) == base


def test_fisica_autor_mismatch_403_rollback(client, outer_conn):
    base = _contagens(outer_conn)
    payload = {"cns_autor": _CNS_OUTRO, "nome_autor": "X", "nome_paciente": "P", "itens": [{"nome_exame": "X"}]}
    r = client.post("/laudos/fisica", json=payload, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "autor_mismatch"
    assert _contagens(outer_conn) == base


# ===========================================================================
# Origem de correção (mesmo autor) — §8.3
# ===========================================================================

def test_origem_de_outro_autor_403_rollback(client, outer_conn):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A)
    l_id = _laudo_id(outer_conn, proto)
    base = _contagens(outer_conn)
    payload = {
        "cns_autor": _CNS_OUTRO, "nome_autor": "B", "cpf_paciente": _CPF_PAC,
        "nome_paciente": "P", "tipo_emissao": "correcao", "origem_laudo_id": l_id,
        "itens": [{"nome_exame": "X"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"
    assert _contagens(outer_conn) == base


def test_origem_propria_201(client, outer_conn):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A)
    l_id = _laudo_id(outer_conn, proto)
    payload = {
        "cns_autor": _CNS_AUTOR_A, "nome_autor": "A", "cpf_paciente": _CPF_PAC,
        "nome_paciente": "P", "tipo_emissao": "correcao", "origem_laudo_id": l_id,
        "itens": [{"nome_exame": "X"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 201, r.text


# ===========================================================================
# Vínculo de pedido — paciente do pedido == paciente do laudo (§8.4 / P1)
# ===========================================================================

def test_vinculo_pedido_paciente_divergente_403_rollback(client, outer_conn):
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    base = _contagens(outer_conn)
    # laudo para OUTRO paciente, vinculando o pedido do paciente _CPF_PAC
    payload = {
        "cns_autor": _CNS_AUTOR_A, "nome_autor": "A", "cpf_paciente": _CPF_OUTRO_PAC,
        "nome_paciente": "OUTRO", "pedido_protocolo": ped, "itens": [{"nome_exame": "X"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "vinculo_pedido_invalido"
    assert _contagens(outer_conn) == base


def test_vinculo_pedido_paciente_igual_201(client, outer_conn):
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, pedido_protocolo=ped)
    assert proto


# ===========================================================================
# Leitura — autor OU solicitante (GET); terceiro 403
# ===========================================================================

def test_get_autor_e_solicitante_2xx_terceiro_403(client):
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, pedido_protocolo=ped)

    # autor → 200
    assert client.get(f"/laudos/{proto}", headers=_headers(_tok(_CNS_AUTOR_A, "prescritor"))).status_code == 200
    # solicitante → 200
    assert client.get(f"/laudos/{proto}", headers=_headers(_tok(_CNS_SOLIC_S, "prescritor"))).status_code == 200
    # terceiro prescritor → 403
    r = client.get(f"/laudos/{proto}", headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


def test_leitura_custodia_pdf_qr_matriz_explicita(client):
    """CODEX r2 — prova explícita das 3 superfícies de leitura que reusam o mesmo
    ramo (custodia/pdf/qr): autor/solicitante/paciente-dono → 200; terceiro
    prescritor e paciente não-dono → 403."""
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, pedido_protocolo=ped)

    for sufixo in ("/custodia", "/pdf", "/qr"):
        url = f"/laudos/{proto}{sufixo}"
        assert client.get(url, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor"))).status_code == 200, sufixo
        assert client.get(url, headers=_headers(_tok(_CNS_SOLIC_S, "prescritor"))).status_code == 200, sufixo
        assert client.get(url, headers=_headers(_tok(_CNS_OUTRO, "prescritor"))).status_code == 403, sufixo
        assert client.get(url, headers=_headers(_tok(_CPF_PAC, "paciente"))).status_code == 200, sufixo
        assert client.get(url, headers=_headers(_tok(_CPF_OUTRO_PAC, "paciente"))).status_code == 403, sufixo


# ===========================================================================
# Autor-only — assinar/liberar/cancelar/encerrar
# ===========================================================================

def test_assinar_nao_autor_403_autor_200(client):
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, pedido_protocolo=ped)

    # solicitante (não-autor) tenta assinar → 403
    r = client.post(f"/laudos/{proto}/assinar", headers=_headers(_tok(_CNS_SOLIC_S, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"
    # autor → 200
    assert client.post(f"/laudos/{proto}/assinar", headers=_headers(_tok(_CNS_AUTOR_A, "prescritor"))).status_code == 200


# ===========================================================================
# Ciência prescritor — solicitante; autor 403; sem pedido 403
# ===========================================================================

def test_ciencia_prescritor_solicitante_2xx_autor_403(client):
    ped = _criar_pedido(client, _CNS_SOLIC_S, paciente_cpf=_CPF_PAC)
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC, pedido_protocolo=ped)
    _ate_liberado(client, proto)

    # autor não é o solicitante → 403
    r = client.post(f"/laudos/{proto}/ciencia-prescritor", headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 403, r.text
    # solicitante → 200
    assert client.post(
        f"/laudos/{proto}/ciencia-prescritor", headers=_headers(_tok(_CNS_SOLIC_S, "prescritor"))
    ).status_code == 200


def test_ciencia_prescritor_sem_pedido_403(client):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC)  # sem pedido_protocolo
    _ate_liberado(client, proto)
    # sem solicitante → ninguém (exceto admin) dá ciência clínica
    r = client.post(f"/laudos/{proto}/ciencia-prescritor", headers=_headers(_tok(_CNS_SOLIC_S, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


# ===========================================================================
# Ciência paciente — BUG ATIVO fechado
# ===========================================================================

def test_ciencia_paciente_nao_dono_403_dono_2xx(client):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC)
    _ate_liberado(client, proto)

    # paciente não-dono → 403 (antes: qualquer paciente passava)
    r = client.post(f"/laudos/{proto}/ciencia-paciente", headers=_headers(_tok(_CPF_OUTRO_PAC, "paciente")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"
    # paciente dono → 200
    assert client.post(
        f"/laudos/{proto}/ciencia-paciente", headers=_headers(_tok(_CPF_PAC, "paciente"))
    ).status_code == 200


# ===========================================================================
# CPF sentinela — P2
# ===========================================================================

def test_cpf_sentinela_paciente_403(client):
    # laudo físico sem cpf → paciente = sentinela
    payload = {"cns_autor": _CNS_AUTOR_A, "nome_autor": "A", "nome_paciente": "P", "itens": [{"nome_exame": "X"}]}
    r = client.post("/laudos/fisica", json=payload, headers=_headers(_tok(_CNS_AUTOR_A, "prescritor")))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    # token paciente com sub=sentinela NÃO acessa via custódia
    r2 = client.get(f"/laudos/{proto}/custodia", headers=_headers(_tok(_SENTINELA, "paciente")))
    assert r2.status_code == 403, r2.text
    assert r2.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


# ===========================================================================
# admin — bypassa ownership, NÃO invariantes
# ===========================================================================

def test_admin_le_sem_ownership(client):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC)
    assert client.get(f"/laudos/{proto}", headers=_headers(_tok("admin", "admin"))).status_code == 200


def test_admin_nao_bypassa_invariante_de_origem_403(client, outer_conn):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A)
    l_id = _laudo_id(outer_conn, proto)
    # admin cria correcao em nome de _CNS_OUTRO, mas origem é do autor A → 403 (invariante §8.3)
    payload = {
        "cns_autor": _CNS_OUTRO, "nome_autor": "B", "cpf_paciente": _CPF_PAC,
        "nome_paciente": "P", "tipo_emissao": "correcao", "origem_laudo_id": l_id,
        "itens": [{"nome_exame": "X"}],
    }
    r = client.post("/laudos", json=payload, headers=_headers(_tok("admin", "admin")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"


# ===========================================================================
# Anti-leak #52 — 403 precede 422 de estado
# ===========================================================================

def test_antileak_403_precede_422(client):
    proto = _criar_laudo(client, autor_cns=_CNS_AUTOR_A, paciente_cpf=_CPF_PAC)
    # autor assina (status vira 'assinado')
    assert client.post(f"/laudos/{proto}/assinar", headers=_headers(_tok(_CNS_AUTOR_A, "prescritor"))).status_code == 200
    # não-autor tenta assinar laudo já assinado: deve ver 403 (ownership), não 422 (estado)
    r = client.post(f"/laudos/{proto}/assinar", headers=_headers(_tok(_CNS_OUTRO, "prescritor")))
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_laudo"
    assert "producao" not in r.json()["detail"]["mensagem"].lower()
