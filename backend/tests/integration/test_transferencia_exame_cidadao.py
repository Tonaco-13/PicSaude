"""Transferência de custódia de pedido de exame pelo CIDADÃO + fila do laboratório.

Contexto
--------
A demo pedia que transferir um pedido de exame fosse o MESMO gesto de transferir
uma receita: o cidadão escolhe o estabelecimento, entrega a posse, e o objeto cai
na fila daquele CNPJ. Antes, o cidadão não tinha esse caminho — só `agendar`
(papel prescritor) e a chave de circulação (digitada pelo operador do lab).

TICKET-J.7 (`core`, martelo do Fabiano em 15/08 — DESPACHO-ENG-011 §4 + §11a)
----------------------------------------------------------------------------
Este arquivo foi escrito quando transferir fazia DUAS coisas: entregava a posse
E movia pedido e itens para `agendado`. O martelo separou os fatos —

  > transferir ao laboratório é um ato de posse (custódia), não de agenda;
  > itens continuam `pendente`; quem promove a `agendado` é o laboratório,
  > criando agendamento com data/hora/unidade — ou realizando direto.

— e as asserções abaixo passaram a travar a regra nova.

O que este arquivo trava
------------------------
1. **Transferir é SÓ posse**: custódia nível-pedido `paciente → <cnpj>`; pedido
   permanece `emitido`, itens permanecem `pendente`.
2. **Um fato, um evento** (AC §4.3(i)): o ato emite `custodia_transferida` e
   NADA mais — em especial, nunca `pedido_agendado`, que anunciava um
   agendamento inexistente.
3. **Ownership antes de estado** (anti-leak #52): outro CPF leva 403, não 409.
4. **Posse é exclusiva, e quem sabe disso é a CUSTÓDIA**: pedido já entregue a
   um laboratório → 409 na segunda tentativa, mesmo o status seguindo `emitido`
   (o guard deixou de ser por status justamente por isso); terminal → 422.
5. **A ponte com a bancada**: o pedido transferido cai na fila do laboratório
   (`GET /dispensadores/fila-exames`, GAP-4/#148) **acionável**, com o item em
   `pendente`. Escopo por CNPJ, ex-custodiante e filtros já são cobertos por
   `test_fila_exames_dispensador.py` — aqui guardamos só o elo novo.
6. **`agendado` só se alcança agendando** (AC §4.3(iii)) e o ciclo completo
   fecha pelos dois caminhos que o martelo autoriza: com agendamento e com
   coleta direta (AC §4.3(iv)).

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


def _emitir_pedido(
    client,
    token_prescritor: str,
    nome_exame: str = "HEMOGRAMA",
    *,
    enviar_ao_paciente: bool = False,
) -> str:
    """Emite um pedido. `enviar_ao_paciente` grava a custódia inicial.

    TICKET-J.7 — o flag importa e por pouco não custou caro. Sem ele, a emissão
    NÃO grava linha de custódia de nível-pedido e `detentor_atual_pedido`
    devolve `None`; com ele, grava `para='paciente'` (o PAPEL, não o CPF). Um
    guard que só tratasse o caso `None` passaria na integração inteira e
    quebraria na vitrine — foi exatamente o que o gate de navegador acusou
    antes do merge. Daí o parâmetro existir e o teste abaixo usar os dois.
    """
    payload = {**_PAYLOAD_BASE, "itens": [{"nome_exame": nome_exame, "quantidade": 1}]}
    if enviar_ao_paciente:
        payload["enviar_ao_paciente"] = True
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
    assert body["status"] == "emitido", "transferir não é agendar (J.7)"
    assert body["itens_transferidos"] == 1
    assert body["cnpj_laboratorio"] == _CNPJ_LAB_A

    # TICKET-J.7 — o ESTADO não se move: quem mudou foi a posse.
    estados = _linhas(
        outer_conn,
        "SELECT p.status, i.status_item FROM pedidos_exame p "
        "JOIN pedido_exame_itens i ON i.pedido_id = p.id WHERE p.protocolo = %s",
        (proto,),
    )
    assert estados and all(e[0] == "emitido" and e[1] == "pendente" for e in estados), (
        f"transferir mexeu em estado — deveria mexer só em custódia: {estados}"
    )

    # Custódia de NÍVEL-PEDIDO: paciente → CNPJ, com o CNPJ já canônico
    custodia = _linhas(
        outer_conn,
        "SELECT c.de, c.para FROM pedido_exame_custodia c "
        "JOIN pedidos_exame p ON p.id = c.pedido_id "
        "WHERE p.protocolo = %s AND c.item_id IS NULL ORDER BY c.id DESC",
        (proto,),
    )
    assert custodia[0] == ("paciente", _CNPJ_LAB_A)


def test_transferencia_emite_somente_custodia_transferida(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC §4.3(i) — UM fato, UM evento.

    O `pedido_agendado` que saía daqui nomeava uma transição que não deveria
    acontecer e anunciava um agendamento inexistente (`data_agendamento: None`
    era a confissão). Posse e estado continuam sendo fatos distintos (§2) — só
    que aqui houve apenas UM deles.
    """
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
    assert "pedido_agendado" not in tipos, (
        f"transferir voltou a anunciar agendamento que não existe: {tipos}"
    )
    # Nada além de emissão + custódia foi para o ledger neste caminho.
    assert [tp for tp in tipos if tp != "pedido_emitido"] == ["custodia_transferida"], tipos

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
    # AC §4.3(ii) — a fila lê CUSTÓDIA, então o pedido chega mesmo `emitido`.
    assert alvo["status"] == "emitido"
    assert alvo["paciente"]["nome"] == SEED_PACIENTE_NOME
    assert alvo["itens"][0]["nome_exame"] == "GLICEMIA"
    assert alvo["itens"][0]["status_item"] == "pendente"
    # `acionavel` é derivado no backend. TICKET-J.7: `pendente` É acionável — é
    # o estado em que há MAIS a fazer (marcar hora ou coletar direto). Sem isso
    # a tela do laboratório, que esconde pedido sem item acionável, sumiria com
    # o exame recém-recebido.
    assert alvo["itens"][0]["acionavel"] is True




# ---------------------------------------------------------------------------
# 6 — TICKET-J.7: `agendado` só se alcança agendando; o ciclo fecha pelos DOIS
#     caminhos que o martelo autoriza (AC §4.3(iii) e §4.3(iv))
# ---------------------------------------------------------------------------

def _itens_do_pedido(client, proto: str, cnpj: str) -> list[dict]:
    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(cnpj, "dispensador")))
    assert r.status_code == 200, r.text
    return r.json()["itens"]


def _status_pedido(client, proto: str, cnpj: str) -> str:
    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token(cnpj, "dispensador")))
    assert r.status_code == 200, r.text
    return r.json()["pedido"]["status"] if "pedido" in r.json() else r.json()["status"]


def test_item_so_chega_a_agendado_criando_agendamento(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC §4.3(iii) — `agendado` volta a significar o que o nome diz.

    Antes do J.7 o item chegava a `agendado` sem que existisse UMA linha em
    `agendamentos`: a fila do laboratório não distinguia "chegou, esperando
    marcar" de "já marcado para quinta às 8h". Agora só `POST /agendamentos`
    promove — e o objeto agendamento existe de verdade.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    # Recém-transferido: `pendente`, e nenhum agendamento no banco.
    assert [i["status_item"] for i in _itens_do_pedido(client, proto, _CNPJ_LAB_A)] == ["pendente"]
    assert _linhas(
        outer_conn,
        "SELECT a.id FROM agendamentos a JOIN pedidos_exame p ON p.id = a.pedido_id "
        "WHERE p.protocolo = %s",
        (proto,),
    ) == []

    # Quem dispara o `POST /agendamentos` aqui é o prescritor, e não o
    # laboratório, por uma razão de AMBIENTE e não de regra: o dispensador só
    # passa no ownership de criação se houver `prestadores.cnpj → org_id`
    # cadastrado (fail-closed do §D1), e a fixture de integração não semeia
    # prestador. A persona "laboratório agenda" é coberta no gate de navegador
    # (`tests/browser/test_j7_transferir_e_posse.py`), onde o seed da demo tem
    # a Clínica Demo registrada. O que ESTE teste trava é o mecanismo: sem
    # agendamento não há `agendado`.
    r = client.post(
        "/agendamentos",
        json={
            "pedido_protocolo": proto,
            "org_id":     "LAB_A",
            "unidade_id": "UNIDADE_01",
            "data_hora":  "2026-09-01T08:00:00",
        },
        headers=_headers(token_p),
    )
    assert r.status_code in (200, 201), r.text

    assert [i["status_item"] for i in _itens_do_pedido(client, proto, _CNPJ_LAB_A)] == ["agendado"]
    # E agora o agendamento EXISTE — é o que dá sentido ao estado.
    assert len(_linhas(
        outer_conn,
        "SELECT a.id FROM agendamentos a JOIN pedidos_exame p ON p.id = a.pedido_id "
        "WHERE p.protocolo = %s",
        (proto,),
    )) == 1


def test_ciclo_completo_com_agendamento(client, seed_usuario, seed_paciente):
    """AC §4.3(iv) — cidadão → fila → agendamento → coleta."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    h_lab = _headers(_token(_CNPJ_LAB_A, "dispensador"))
    # Agendamento criado pelo prescritor — ver nota no teste acima.
    assert client.post(
        "/agendamentos",
        json={"pedido_protocolo": proto, "org_id": "LAB_A",
              "unidade_id": "UNIDADE_01", "data_hora": "2026-09-01T08:00:00"},
        headers=_headers(token_p),
    ).status_code in (200, 201)

    item_id = _itens_do_pedido(client, proto, _CNPJ_LAB_A)[0]["id"]
    rc = client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar", json={}, headers=h_lab)
    assert rc.status_code == 201, rc.text
    assert rc.json()["status_item"] == "coletado"
    assert rc.json()["status_pedido"] == "coletado"


def test_ciclo_completo_com_coleta_direta_sem_agendamento(client, seed_usuario, seed_paciente):
    """AC §4.3(iv), segundo caminho — "ou realizando direto" (martelo §11a).

    O laboratório que já está com o material na mão não precisa inventar um
    agendamento retroativo. Aresta `pendente → coletado` em `states_exame.py`.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    h_lab = _headers(_token(_CNPJ_LAB_A, "dispensador"))
    item_id = _itens_do_pedido(client, proto, _CNPJ_LAB_A)[0]["id"]
    assert _itens_do_pedido(client, proto, _CNPJ_LAB_A)[0]["status_item"] == "pendente"

    rc = client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar", json={}, headers=h_lab)
    assert rc.status_code == 201, rc.text
    assert rc.json()["status_item"] == "coletado"
    # `emitido → coletado` sem escala em `agendado`: a aresta nova do pedido.
    assert rc.json()["status_pedido"] == "coletado"


def test_transfere_pedido_que_ja_estava_na_carteira_do_cidadao(
    client, outer_conn, seed_usuario, seed_paciente
):
    """O caminho da vitrine: emissão COM `enviar_ao_paciente`.

    Aí a custódia inicial existe e guarda `para='paciente'` — o PAPEL, não o
    CPF. Um guard de posse que comparasse o detentor com o CPF do JWT recusaria
    o dono legítimo com 409. Sem este teste, a integração ficava verde (todos os
    outros emitem sem o flag, e `detentor` vinha `None`) e a demo quebrava.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p, enviar_ao_paciente=True)

    custodia_inicial = _linhas(
        outer_conn,
        "SELECT c.de, c.para FROM pedido_exame_custodia c "
        "JOIN pedidos_exame p ON p.id = c.pedido_id "
        "WHERE p.protocolo = %s AND c.item_id IS NULL ORDER BY c.id",
        (proto,),
    )
    assert custodia_inicial == [("prescritor", "paciente")], (
        f"pré-condição: a emissão grava a posse do cidadão pelo PAPEL — {custodia_inicial}"
    )

    r = _transferir(client, proto, _CNPJ_LAB_A)
    assert r.status_code == 201, r.text

    # E a segunda tentativa continua barrada, agora com duas linhas na cadeia.
    assert _transferir(client, proto, _CNPJ_LAB_B).status_code == 409


def test_carteira_do_cidadao_sabe_que_a_posse_saiu(client, seed_usuario, seed_paciente):
    """A posse do cidadão deixou de ser derivável do status.

    Antes, `emitido` bastava para dizer "está comigo". Depois do J.7 o pedido
    entregue continua `emitido` — sem `sob_minha_custodia`, a carteira voltaria
    a oferecer "Transferir Custódia" de algo que já está no laboratório.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_pedido(client, token_p, enviar_ao_paciente=True)
    h_pac = _headers(_token_paciente())

    def _card():
        r = client.get("/paciente/pedidos-exame", headers=h_pac)
        assert r.status_code == 200, r.text
        todos = r.json()["posse"] + r.json()["em_andamento"] + r.json()["historico"]
        return next(p for p in todos if p["protocolo"] == proto)

    antes = _card()
    assert antes["sob_minha_custodia"] is True
    assert antes["detentor"] == "paciente"

    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    depois = _card()
    assert depois["status"] == "emitido", "pré-condição: o estado não mudou"
    assert depois["sob_minha_custodia"] is False, (
        "a carteira ainda acha que o pedido está com o cidadão"
    )
    assert depois["detentor"] == _CNPJ_LAB_A


def test_fila_exames_exige_papel_de_dispensador(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    r = client.get("/dispensadores/fila-exames", headers=_headers(token_p))
    assert r.status_code == 403, r.text



