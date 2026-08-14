"""TICKET-J.5 (`core`) — a coleta via agendamento entra no ledger DO PEDIDO.

O DEFEITO QUE ESTE ARQUIVO TRAVA
--------------------------------
`POST /agendamentos/{proto}/realizar` transiciona os itens do pedido para
`coletado`, mas só gravava `agendamento_realizado` — no ledger do AGENDAMENTO.
Quem lesse a trilha do pedido (`GET /pedidos-exame/{proto}`) via o item coletado
**sem nenhum evento explicando quando nem por quê**: buraco de proveniência no
objeto sanitário.

A outra via de coleta (`pedidos_exame.py::coletar_item_exame`) sempre emitiu
`pedido_coletado`. Depois do J.5, as duas contam a mesma história — e o payload
registra qual delas foi (`via`), porque coleta no balcão e coleta por
agendamento são o mesmo fato com origens diferentes.

Nome do arquivo casa com `test_pedidos_exame` no `-k` do gate — de propósito.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

import json

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNPJ_LAB = "12345678000195"

_PAYLOAD = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE TICKET13",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [
        {"nome_exame": "HEMOGRAMA", "quantidade": 1},
        {"nome_exame": "GLICEMIA", "quantidade": 1},
    ],
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _eventos_do_pedido(outer_conn, proto: str) -> list[tuple]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.tipo_evento, e.dados_json, e.instance_id "
            "FROM pedido_exame_eventos e JOIN pedidos_exame p ON p.id = e.pedido_id "
            "WHERE p.protocolo = %s ORDER BY e.id",
            (proto,),
        )
        return cur.fetchall()


def _payload(bruto):
    return json.loads(bruto) if isinstance(bruto, str) else bruto


def _preparar_agendamento(client, token_pre: str) -> tuple[str, str]:
    """Pedido emitido → agendado no lab → agendamento criado e confirmado."""
    r = client.post("/pedidos-exame", json=_PAYLOAD, headers=_headers(token_pre))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    assert client.post(
        f"/pedidos-exame/{proto}/agendar", json={"cnpj_prestador": _CNPJ_LAB},
        headers=_headers(token_pre),
    ).status_code == 201

    r_ag = client.post(
        "/agendamentos",
        json={
            "pedido_protocolo": proto,
            "cnpj_prestador":   _CNPJ_LAB,
            "org_id":           "org-demo",
            "unidade_id":       "unidade-demo",
            "data_hora":        "2026-12-01T09:00:00",
        },
        headers=_headers(token_pre),
    )
    assert r_ag.status_code in (200, 201), r_ag.text
    return proto, r_ag.json()["protocolo"]


# ---------------------------------------------------------------------------
# AC do J.5
# ---------------------------------------------------------------------------

def test_realizar_agendamento_emite_pedido_coletado_no_ledger_do_pedido(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC — `realizar` gera `agendamento_realizado` (ledger do agendamento) **e**
    `pedido_coletado` (ledger do pedido), um por item coletado."""
    token = obter_token_prescritor(client, seed_usuario)
    proto, proto_ag = _preparar_agendamento(client, token)

    antes = [e[0] for e in _eventos_do_pedido(outer_conn, proto)]
    assert "pedido_coletado" not in antes, antes

    r = client.post(f"/agendamentos/{proto_ag}/realizar", headers=_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["itens_coletados"] == 2

    eventos = _eventos_do_pedido(outer_conn, proto)
    tipos = [e[0] for e in eventos]
    assert tipos.count("pedido_coletado") == 2, tipos

    payloads = [_payload(e[1]) for e in eventos if e[0] == "pedido_coletado"]
    assert {p["nome_exame"] for p in payloads} == {"HEMOGRAMA", "GLICEMIA"}
    for p in payloads:
        assert p["via"] == "agendamento"
        assert p["agendamento_protocolo"] == proto_ag
        assert p["item_id"]


def test_eventos_do_ato_compartilham_instance_id(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Invariante forense do 4D.2: um ato, um `instance_id`. Os `pedido_coletado`
    nascem na MESMA transação do `agendamento_realizado` e têm de carregar o
    mesmo identificador — senão a auditoria não consegue amarrar os dois lados
    do mesmo gesto."""
    token = obter_token_prescritor(client, seed_usuario)
    proto, proto_ag = _preparar_agendamento(client, token)
    assert client.post(
        f"/agendamentos/{proto_ag}/realizar", headers=_headers(token)
    ).status_code == 200

    ids_pedido = {e[2] for e in _eventos_do_pedido(outer_conn, proto)
                  if e[0] == "pedido_coletado"}
    assert len(ids_pedido) == 1, ids_pedido

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.instance_id FROM agendamento_eventos e "
            "JOIN agendamentos a ON a.id = e.agendamento_id "
            "WHERE a.protocolo = %s AND e.evento = 'agendamento_realizado'",
            (proto_ag,),
        )
        id_agendamento = {r[0] for r in cur.fetchall()}

    assert ids_pedido == id_agendamento, (ids_pedido, id_agendamento)


def test_a_via_do_balcao_continua_intacta(client, outer_conn, seed_usuario, seed_paciente):
    """Regressão: a coleta direta (`/itens/{id}/coletar`) segue emitindo
    `pedido_coletado` sem `via` — o J.5 acrescentou um caminho, não mexeu no
    existente."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/pedidos-exame", json=_PAYLOAD, headers=_headers(token))
    proto = r.json()["protocolo"]
    assert client.post(
        f"/pedidos-exame/{proto}/agendar", json={"cnpj_prestador": _CNPJ_LAB},
        headers=_headers(token),
    ).status_code == 201

    item_id = client.get(
        f"/pedidos-exame/{proto}", headers=_headers(token)
    ).json()["itens"][0]["id"]
    assert client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/coletar", json={},
        headers=_headers(_tok(_CNPJ_LAB, "dispensador")),
    ).status_code == 201

    payloads = [_payload(e[1]) for e in _eventos_do_pedido(outer_conn, proto)
                if e[0] == "pedido_coletado"]
    assert len(payloads) == 1, payloads
    assert "via" not in payloads[0], payloads[0]


def test_realizar_sem_item_agendado_nao_emite_evento_orfao(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Se nenhum item estava `agendado`, não há coleta — e não pode haver evento.
    Ledger é imutável: evento emitido por engano não se apaga."""
    token = obter_token_prescritor(client, seed_usuario)
    proto, proto_ag = _preparar_agendamento(client, token)

    # Coleta os dois itens pelo balcão ANTES de realizar o agendamento.
    h_lab = _headers(_tok(_CNPJ_LAB, "dispensador"))
    for item in client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()["itens"]:
        assert client.post(
            f"/pedidos-exame/{proto}/itens/{item['id']}/coletar", json={}, headers=h_lab
        ).status_code == 201

    r = client.post(f"/agendamentos/{proto_ag}/realizar", headers=_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["itens_coletados"] == 0

    # Só os 2 do balcão — o `realizar` não acrescentou nenhum.
    tipos = [e[0] for e in _eventos_do_pedido(outer_conn, proto)]
    assert tipos.count("pedido_coletado") == 2, tipos
