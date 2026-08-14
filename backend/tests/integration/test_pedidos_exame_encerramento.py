"""TICKET-J.1 (`core`) — o ciclo do pedido chega ao fim: AC ponta a ponta.

Complementa `tests/unit/test_states_exame_derivacao.py` (a máquina de estados
pura) com o que só o HTTP prova: que o **422 circular** morreu.

O 422 circular, em uma frase: `POST /encerrar` exige o pedido em
`resultado_disponivel`, mas a derivação nunca produzia esse estado — então o
pedido ia direto a `encerrado`, o `/encerrar` recusava, `pedido_encerrado` nunca
era emitido e os itens nunca chegavam ao terminal. O ciclo do exame não tinha fim.

Nome do arquivo casa com `test_pedidos_exame` no `-k` do gate — de propósito.

Requer PostgreSQL (conftest de integração pula se DATABASE_URL não for PG).
"""
from __future__ import annotations

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
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _status(client, token: str, proto: str) -> str:
    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(token))
    assert r.status_code == 200, r.text
    return r.json()["status"]


def _itens(client, token: str, proto: str) -> list[dict]:
    return client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()["itens"]


def _eventos(outer_conn, proto: str) -> list[str]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.tipo_evento FROM pedido_exame_eventos e "
            "JOIN pedidos_exame p ON p.id = e.pedido_id "
            "WHERE p.protocolo = %s ORDER BY e.id",
            (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _ate_resultado(client, token_pre: str, n_itens: int = 1) -> tuple[str, list[int]]:
    """Emissão → agendar no lab → coletar → resultado, em N itens."""
    payload = {**_PAYLOAD, "itens": [
        {"nome_exame": f"EXAME-{i}", "quantidade": 1} for i in range(n_itens)
    ]}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_pre))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    assert client.post(
        f"/pedidos-exame/{proto}/agendar", json={"cnpj_prestador": _CNPJ_LAB},
        headers=_headers(token_pre),
    ).status_code == 201

    h_lab = _headers(_tok(_CNPJ_LAB, "dispensador"))
    ids = [i["id"] for i in _itens(client, token_pre, proto)]
    for item_id in ids:
        assert client.post(
            f"/pedidos-exame/{proto}/itens/{item_id}/coletar", json={}, headers=h_lab
        ).status_code == 201
        assert client.post(
            f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
            json={"resultado_resumo": "normal"}, headers=h_lab,
        ).status_code == 201
    return proto, ids


# ---------------------------------------------------------------------------
# AC do J.1
# ---------------------------------------------------------------------------

def test_pedido_repousa_em_resultado_disponivel(client, seed_usuario, seed_paciente):
    """AC 1 — resultado em N itens deixa o pedido em `resultado_disponivel`."""
    token = obter_token_prescritor(client, seed_usuario)
    proto, _ = _ate_resultado(client, token, n_itens=2)
    assert _status(client, token, proto) == "resultado_disponivel"


def test_encerrar_devolve_200_e_fecha_o_ciclo(client, outer_conn, seed_usuario, seed_paciente):
    """AC 2/3/4 — `/encerrar` 200; itens → `encerrado`; `pedido_encerrado` no ledger.

    Antes do J.1 este teste morria no primeiro assert com 422: o pedido já estava
    `encerrado` e o endpoint recusava — o ciclo não tinha como ser fechado pelo
    ato que o fecha.
    """
    token = obter_token_prescritor(client, seed_usuario)
    proto, _ = _ate_resultado(client, token, n_itens=2)

    r = client.post(f"/pedidos-exame/{proto}/encerrar", headers=_headers(token))
    assert r.status_code == 200, r.text

    assert _status(client, token, proto) == "encerrado"
    assert {i["status_item"] for i in _itens(client, token, proto)} == {"encerrado"}
    assert "pedido_encerrado" in _eventos(outer_conn, proto)


def test_encerrar_e_o_unico_caminho_para_encerrado(client, seed_usuario, seed_paciente):
    """`encerrado` é ciência registrada, não "o laboratório terminou".

    Com o resultado pronto e SEM chamar `/encerrar`, o pedido não pode estar
    encerrado — senão o momento "resultado disponível ao cidadão" some da
    narrativa, que foi o achado da excursão.
    """
    token = obter_token_prescritor(client, seed_usuario)
    proto, _ = _ate_resultado(client, token, n_itens=1)
    assert _status(client, token, proto) != "encerrado"


def test_pedido_com_resultado_sai_da_fila_do_laboratorio(client, seed_usuario, seed_paciente):
    """Companheiro do J.1 em `dispensadores.py`.

    O pedido repousa em `resultado_disponivel` — estado NÃO terminal. Sem incluí-lo
    em `_ESTADOS_PEDIDO_FIM_FILA`, ele ficaria preso na fila do laboratório para
    sempre, sem nenhum item acionável. Fila é trabalho pendente; a bancada acabou.
    """
    token = obter_token_prescritor(client, seed_usuario)
    proto, _ = _ate_resultado(client, token, n_itens=1)

    fila = client.get(
        "/dispensadores/fila-exames", headers=_headers(_tok(_CNPJ_LAB, "dispensador"))
    ).json()["fila"]
    assert proto not in [p["protocolo"] for p in fila]


def test_carteira_do_cidadao_mostra_em_andamento_ate_a_ciencia(
    client, seed_usuario, seed_paciente
):
    """O outro lado do J.1: para o cidadão, o pedido com resultado fica em
    ANDAMENTO (há algo a fazer — tomar ciência), não no histórico. Antes ele
    pulava direto para histórico, escondendo o resultado que acabara de sair."""
    token = obter_token_prescritor(client, seed_usuario)
    proto, _ = _ate_resultado(client, token, n_itens=1)

    carteira = client.get(
        "/paciente/pedidos-exame", headers=_headers(_tok(SEED_PACIENTE_CPF, "paciente"))
    ).json()
    assert proto in [p["protocolo"] for p in carteira["em_andamento"]]
    assert proto not in [p["protocolo"] for p in carteira["historico"]]
