"""TICKET-GAP-4-LISTAGENS-EXAME §2.2 — GET /dispensadores/fila-exames.

Espelha o §4 (critérios de aceite). Precedente: test_pedidos_exame_autorizacao.py
(mesma técnica — token forjado por papel/identidade, isolamento por outer tx).

Cobertura:
  - Fila escopada por custódia ATUAL (item_id IS NULL, para=<cnpj JWT>):
    laboratório A vê o pedido após 'agendar'; laboratório B não vê.
  - admin: sem ?cnpj → 422 canônico; com ?cnpj → vê a fila do CNPJ informado.
  - Filtro ?status= funciona.
  - Pedido terminal (encerrado) sai da fila mesmo com custódia registrada.
  - `acionavel` derivado: agendado/coletado → True; demais → False.
  - Ex-custodiante (perdeu a custódia) não vê mais o pedido.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Identidades de teste
# ---------------------------------------------------------------------------

_CNPJ_A = "12345678000195"        # prestador que recebe a custódia
_CNPJ_B = "98765432000110"        # outro prestador (nunca custodiante)

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE TICKET13",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(sub: str, role: str, nome: str = "ATOR") -> str:
    return criar_access_token(sub=sub, role=role, nome=nome)


def _criar_pedido(client, token_dono: str, **overrides) -> str:
    payload = {**_PAYLOAD_BASE, **overrides}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_dono))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _agendar_para(client, token, protocolo: str, cnpj: str):
    r = client.post(
        f"/pedidos-exame/{protocolo}/agendar",
        json={"cnpj_prestador": cnpj},
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text


def _fila(client, token, params: str = "") -> dict:
    r = client.get(f"/dispensadores/fila-exames{params}", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()


# ===========================================================================
# Critério §4.3 — escopo por custódia do CNPJ do JWT
# ===========================================================================

def test_fila_exames_dono_ve_nao_dono_nao_ve(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)

    fila_a = _fila(client, _token(_CNPJ_A, "dispensador"))
    assert fila_a["cnpj"] == _CNPJ_A
    protocolos = [p["protocolo"] for p in fila_a["fila"]]
    assert proto in protocolos
    assert fila_a["total"] == len(fila_a["fila"])

    # Conteúdo do card da fila (§2.2 do ticket)
    card = next(p for p in fila_a["fila"] if p["protocolo"] == proto)
    assert card["paciente"]["nome"] == SEED_PACIENTE_NOME
    assert card["paciente"]["cpf"] == SEED_PACIENTE_CPF
    assert card["status"] == "agendado"
    assert card["itens"][0]["status_item"] == "agendado"
    assert card["itens"][0]["acionavel"] is True

    fila_b = _fila(client, _token(_CNPJ_B, "dispensador"))
    assert proto not in [p["protocolo"] for p in fila_b["fila"]]


def test_fila_exames_ex_custodiante_nao_ve(client, seed_usuario, seed_paciente):
    """Custódia ATUAL manda: A perde a custódia para B → some da fila de A.

    Caminho real de troca de custodiante: agendar → A; o paciente cancela o
    agendamento (itens voltam a 'pendente', agendamentos.py:562); o prescritor
    re-agenda para B — novo registro de custódia (item_id IS NULL) sobrescreve
    o detentor atual. A guarda 'custódia atual × histórica' (P1(b)) é o que
    impede A de continuar vendo o pedido.
    """
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)

    # Paciente cancela o agendamento → itens 'agendado' → 'pendente'.
    tok_pac = _token(SEED_PACIENTE_CPF, "paciente")
    r = client.post(
        "/agendamentos",
        json={"pedido_protocolo": proto, "data_hora": "2026-08-20T08:00:00",
              "org_id": "org-a", "unidade_id": "u1"},
        headers=_headers(tok_pac),
    )
    assert r.status_code == 201, r.text
    ag_proto = r.json()["protocolo"]
    r = client.post(f"/agendamentos/{ag_proto}/cancelar", json={}, headers=_headers(tok_pac))
    assert r.status_code == 200, r.text

    # Prescritor re-agenda para B — custódia atual do pedido passa para B.
    _agendar_para(client, token_pre, proto, _CNPJ_B)

    fila_a = _fila(client, _token(_CNPJ_A, "dispensador"))
    assert proto not in [p["protocolo"] for p in fila_a["fila"]]

    fila_b = _fila(client, _token(_CNPJ_B, "dispensador"))
    assert proto in [p["protocolo"] for p in fila_b["fila"]]


# ===========================================================================
# Critério §4.2 — admin bypassa com ?cnpj= (e é obrigado a informar)
# ===========================================================================

def test_fila_exames_admin_sem_cnpj_422(client, seed_usuario):
    r = client.get("/dispensadores/fila-exames", headers=_headers(_token("admin", "admin")))
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["codigo"] == "cnpj_obrigatorio_admin"


def test_fila_exames_admin_com_cnpj_200(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)

    fila = _fila(client, _token("admin", "admin"), params=f"?cnpj={_CNPJ_A}")
    assert proto in [p["protocolo"] for p in fila["fila"]]


# ===========================================================================
# Critério §4.4 — filtro ?status=
# ===========================================================================

def test_fila_exames_filtro_status(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)
    tok_a = _token(_CNPJ_A, "dispensador")

    fila_ag = _fila(client, tok_a, params="?status=agendado")
    assert proto in [p["protocolo"] for p in fila_ag["fila"]]

    fila_col = _fila(client, tok_a, params="?status=coletado")
    assert proto not in [p["protocolo"] for p in fila_col["fila"]]


# ===========================================================================
# Critério §4.5 — pedido terminal sai da fila + `acionavel` acompanha o ciclo
# ===========================================================================

def test_fila_exames_ciclo_completo_sai_da_fila(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)
    tok_a = _token(_CNPJ_A, "dispensador")

    # Item agendado → acionavel (pode coletar)
    fila = _fila(client, tok_a)
    card = next(p for p in fila["fila"] if p["protocolo"] == proto)
    item_id = card["itens"][0]["item_id"]
    assert card["itens"][0]["acionavel"] is True

    # Coleta → ainda acionavel (pode registrar resultado)
    r = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
        json={}, headers=_headers(tok_a),
    )
    assert r.status_code == 201, r.text
    fila = _fila(client, tok_a)
    card = next(p for p in fila["fila"] if p["protocolo"] == proto)
    assert card["status"] == "coletado"
    assert card["itens"][0]["acionavel"] is True

    # Resultado registrado → pedido encerra e sai da fila
    r = client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json={"resultado_resumo": "normal"}, headers=_headers(tok_a),
    )
    assert r.status_code == 201, r.text
    fila = _fila(client, tok_a)
    assert proto not in [p["protocolo"] for p in fila["fila"]]


def test_fila_exames_pedido_cancelado_sai_da_fila(client, seed_usuario, seed_paciente):
    token_pre = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido(client, token_pre)
    _agendar_para(client, token_pre, proto, _CNPJ_A)

    r = client.post(
        f"/pedidos-exame/{proto}/cancelar", json={"motivo": "teste"},
        headers=_headers(token_pre),
    )
    assert r.status_code == 200, r.text

    fila = _fila(client, _token(_CNPJ_A, "dispensador"))
    assert proto not in [p["protocolo"] for p in fila["fila"]]
