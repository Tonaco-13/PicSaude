"""Transferência de custódia de pedido de exame pelo CIDADÃO + fila do laboratório.

Contexto
--------
A demo pedia que transferir um pedido de exame fosse o MESMO gesto de transferir
uma receita: o cidadão escolhe o estabelecimento, entrega a posse, e o objeto cai
na fila daquele CNPJ. Antes, o cidadão não tinha esse caminho — só `agendar`
(papel prescritor) e a chave de circulação (digitada pelo operador do lab).

O que este arquivo trava
------------------------
1. **Paridade com a receita**: `POST /pedidos-exame/{proto}/transferir-laboratorio`
   move a posse (custódia nível-pedido `paciente → <cnpj>`), leva o pedido a
   `agendado` e os itens pendentes a `agendado`.
2. **Ledger não perde nem a posse nem o estado** (§2): o ato emite
   `custodia_transferida` E `pedido_agendado`.
3. **Ownership antes de estado** (anti-leak #52): outro CPF leva 403, não 409.
4. **Posse é exclusiva**: pedido já com laboratório (status `agendado`) → 409;
   terminal → 422.
5. **A ponte com a bancada**: o pedido transferido cai na fila do laboratório
   (`GET /dispensadores/fila-exames`, GAP-4/#148). Escopo por CNPJ, ex-custodiante e
   filtros já são cobertos por `test_fila_exames_dispensador.py` — aqui guardamos só o
   elo novo: transferir pelo cidadão põe o pedido na bancada certa, acionável.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
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

_CNPJ_LAB_A = "12345678000195"
_CNPJ_LAB_B = "98765432000110"
_CPF_OUTRO_PACIENTE = "98765432100"

_PAYLOAD_BASE = {
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


def _token(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _token_paciente(cpf: str = SEED_PACIENTE_CPF) -> str:
    return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)


def _emitir_pedido(client, token_prescritor: str, nome_exame: str = "HEMOGRAMA") -> str:
    payload = {**_PAYLOAD_BASE, "itens": [{"nome_exame": nome_exame, "quantidade": 1}]}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _transferir(client, proto: str, cnpj: str, token: str | None = None):
    return client.post(
        f"/pedidos-exame/{proto}/transferir-laboratorio",
        json={"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB DEMO"},
        headers=_headers(token or _token_paciente()),
    )


def _fila(client, cnpj: str) -> list[dict]:
    r = client.get("/dispensadores/fila-exames", headers=_headers(_token(cnpj, "dispensador")))
    assert r.status_code == 200, r.text
    return r.json()["fila"]


def _linhas(outer_conn, sql: str, params: tuple) -> list[tuple]:
    with outer_conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ---------------------------------------------------------------------------
# 1 + 2 — o ato: posse, estado e ledger
# ---------------------------------------------------------------------------

def test_cidadao_transfere_pedido_e_posse_vai_ao_laboratorio(
    client, outer_conn, seed_usuario, seed_paciente
):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    r = _transferir(client, proto, _CNPJ_LAB_A)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "agendado"
    assert body["itens_transferidos"] == 1
    assert body["cnpj_laboratorio"] == _CNPJ_LAB_A

    # Estado do pedido e dos itens
    estados = _linhas(
        outer_conn,
        "SELECT p.status, i.status_item FROM pedidos_exame p "
        "JOIN pedido_exame_itens i ON i.pedido_id = p.id WHERE p.protocolo = %s",
        (proto,),
    )
    assert estados and all(e[0] == "agendado" and e[1] == "agendado" for e in estados)

    # Custódia de NÍVEL-PEDIDO: paciente → CNPJ, com o CNPJ já canônico
    custodia = _linhas(
        outer_conn,
        "SELECT c.de, c.para FROM pedido_exame_custodia c "
        "JOIN pedidos_exame p ON p.id = c.pedido_id "
        "WHERE p.protocolo = %s AND c.item_id IS NULL ORDER BY c.id DESC",
        (proto,),
    )
    assert custodia[0] == ("paciente", _CNPJ_LAB_A)


def test_transferencia_emite_custodia_transferida_e_pedido_agendado(
    client, outer_conn, seed_usuario, seed_paciente
):
    """§2 — posse e estado são fatos distintos; o ledger registra os dois."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    eventos = _linhas(
        outer_conn,
        "SELECT e.tipo_evento, e.dados_json FROM pedido_exame_eventos e "
        "JOIN pedidos_exame p ON p.id = e.pedido_id "
        "WHERE p.protocolo = %s ORDER BY e.id",
        (proto,),
    )
    tipos = [e[0] for e in eventos]
    assert "custodia_transferida" in tipos, tipos
    assert "pedido_agendado" in tipos, tipos

    payload_custodia = next(
        json.loads(e[1]) if isinstance(e[1], str) else e[1]
        for e in eventos if e[0] == "custodia_transferida"
    )
    assert payload_custodia["de"] == "paciente"
    assert payload_custodia["para_id"] == _CNPJ_LAB_A
    assert payload_custodia["motivo"] == "transferencia_laboratorio"


# ---------------------------------------------------------------------------
# 3 + 4 — quem pode, quando pode
# ---------------------------------------------------------------------------

def test_outro_paciente_leva_403_e_nao_descobre_o_estado(
    client, seed_usuario, seed_paciente
):
    """Ownership ANTES do estado (anti-leak #52): 403, nunca 409/422."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    r = _transferir(client, proto, _CNPJ_LAB_A, token=_token_paciente(_CPF_OUTRO_PACIENTE))
    assert r.status_code == 403, r.text


def test_prescritor_nao_usa_o_caminho_do_cidadao(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    r = _transferir(client, proto, _CNPJ_LAB_A, token=token_p)
    assert r.status_code == 403, r.text


def test_pedido_ja_no_laboratorio_nao_transfere_de_novo(client, seed_usuario, seed_paciente):
    """Posse é exclusiva — espelho do 409 da receita fora de transferida_paciente."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    r = _transferir(client, proto, _CNPJ_LAB_B)
    assert r.status_code == 409, r.text


def test_pedido_terminal_nao_transfere(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    rc = client.post(
        f"/pedidos-exame/{proto}/cancelar",
        json={"motivo": "teste"},
        headers=_headers(token_p),
    )
    assert rc.status_code == 200, rc.text

    r = _transferir(client, proto, _CNPJ_LAB_A)
    assert r.status_code == 422, r.text


def test_cnpj_invalido_leva_400(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)

    r = _transferir(client, proto, "123")
    assert r.status_code == 400, r.text


# ---------------------------------------------------------------------------
# 5 — a fila do laboratório
# ---------------------------------------------------------------------------

def test_pedido_transferido_aparece_na_fila_do_laboratorio(
    client, seed_usuario, seed_paciente
):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p, "GLICEMIA")
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    fila = _fila(client, _CNPJ_LAB_A)
    alvo = next((p for p in fila if p["protocolo"] == proto), None)
    assert alvo is not None, f"pedido não caiu na fila do laboratório: {fila}"
    assert alvo["status"] == "agendado"
    assert alvo["paciente"]["nome"] == SEED_PACIENTE_NOME
    assert alvo["itens"][0]["nome_exame"] == "GLICEMIA"
    # `acionavel` é derivado no backend — item 'agendado' pode ser coletado.
    assert alvo["itens"][0]["acionavel"] is True




def test_fila_exames_exige_papel_de_dispensador(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    r = client.get("/dispensadores/fila-exames", headers=_headers(token_p))
    assert r.status_code == 403, r.text



