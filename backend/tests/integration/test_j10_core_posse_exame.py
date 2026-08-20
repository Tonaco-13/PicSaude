"""Posse atual da custódia de exame — J.10-CORE, dialeto PostgreSQL.

DESPACHO-ENG-012 §7 · caminho (b) do `DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`.

O QUE ESTE ARQUIVO TRAVA
------------------------
1. **A constraint existe e morde em PG.** Dupla posse ativa do mesmo pedido é
   `IntegrityError` — o R2 na camada de custódia (um objeto em dois lugares ao
   mesmo tempo) deixa de ser convenção de código e vira invariante de banco.
   O par em SQLite está em `tests/test_j10_core_migracao_sqlite.py` (§9 do
   CLAUDE.md: os dois dialetos, sempre).
2. **Todo caminho de produto fecha a anterior.** Emitir na carteira, agendar e
   transferir ao laboratório passam pelo choke-point; depois de cada um, existe
   exatamente UMA posse ativa. É o que a constraint prova em silêncio — e o que
   este arquivo prova em voz alta, caminho por caminho.
3. **A posse continua sendo lida certo.** `detentor_atual_pedido` responde pela
   custódia ATIVA e não mais por "a última linha"; a fila do laboratório, a
   carteira do cidadão e os guards de ownership seguem coerentes (regressão do
   J.7, que é quem depende dessa leitura).

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

from contextlib import contextmanager

import psycopg2
import pytest

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNPJ_LAB_A = "12345678000195"
_CNPJ_LAB_B = "98765432000110"

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE J10CORE",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_paciente(cpf: str = SEED_PACIENTE_CPF) -> str:
    return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)


def _emitir(client, token_prescritor: str, *, enviar_ao_paciente: bool = False) -> str:
    payload = dict(_PAYLOAD_BASE)
    if enviar_ao_paciente:
        payload["enviar_ao_paciente"] = True
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _transferir(client, proto: str, cnpj: str = _CNPJ_LAB_A):
    return client.post(
        f"/pedidos-exame/{proto}/transferir-laboratorio",
        json={"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB DEMO"},
        headers=_headers(_token_paciente()),
    )


def _pedido_id(outer_conn, proto: str) -> int:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM pedidos_exame WHERE protocolo = %s", (proto,))
        return cur.fetchone()[0]


def _custodias(outer_conn, proto: str) -> list[tuple]:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.item_id, c.de, c.para, c.encerrada_em
              FROM pedido_exame_custodia c
              JOIN pedidos_exame p ON p.id = c.pedido_id
             WHERE p.protocolo = %s
             ORDER BY c.id
            """,
            (proto,),
        )
        return cur.fetchall()


def _ativas(outer_conn, proto: str) -> list[tuple]:
    return [c for c in _custodias(outer_conn, proto) if c[3] is None]


@contextmanager
def _espera_unique_violation(outer_conn, nome: str):
    """Espera `UniqueViolation` no bloco SEM destruir o isolamento do teste.

    O `outer_conn` mantém UM outer tx por teste, revertido no teardown — é o
    que isola um teste do outro. Depois de um erro, o PostgreSQL bloqueia a
    transação até um rollback; mas `outer_conn.rollback()` desfaria também o
    setup deste teste, e `commit()` vazaria as linhas para os testes seguintes
    (rompendo a isolação inteira do arquivo, não só a deste caso).

    SAVEPOINT contém a violação exatamente onde ela acontece.
    """
    with outer_conn.cursor() as cur:
        cur.execute(f"SAVEPOINT {nome}")
    try:
        yield
    except psycopg2.errors.UniqueViolation:
        with outer_conn.cursor() as cur:
            cur.execute(f"ROLLBACK TO SAVEPOINT {nome}")
        return
    raise AssertionError(
        "esperava UniqueViolation — a constraint de posse única não mordeu"
    )


# ---------------------------------------------------------------------------
# 1 — a constraint, no dialeto PostgreSQL
# ---------------------------------------------------------------------------

def test_constraint_recusa_dupla_posse_ativa_do_pedido(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC (iii) do §11c, dialeto PG — injetando a tentativa por SQL cru.

    Por SQL cru de propósito: o objetivo é provar que o BANCO recusa, não que o
    código evita. Um invariante que só o código sustenta é a lição do COER-2 —
    e é o que este PR existe para encerrar no módulo de exames.

    `NULLS NOT DISTINCT` é o detalhe que faz a guarda valer no nível-PEDIDO: sem
    ele, dois `(pedido_id, NULL)` não colidiriam e a dupla posse do pedido
    inteiro passaria silenciosa (§14 do COER-2).
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)
    pid = _pedido_id(outer_conn, proto)

    assert len(_ativas(outer_conn, proto)) == 1, "a emissão abriu exatamente uma posse"

    with _espera_unique_violation(outer_conn, "sp_dupla_pedido"):
        with outer_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pedido_exame_custodia
                  (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
                VALUES (%s, NULL, 'paciente', %s, NOW(), NULL, NULL)
                """,
                (pid, _CNPJ_LAB_A),
            )


def test_constraint_recusa_dupla_posse_ativa_de_item(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Mesma guarda no nível-item — é a que o J.10 (`module`) vai exercitar."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p)
    pid = _pedido_id(outer_conn, proto)

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens WHERE pedido_id = %s LIMIT 1", (pid,)
        )
        item_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO pedido_exame_custodia
              (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
            VALUES (%s, %s, 'paciente', %s, NOW(), NULL, NULL)
            """,
            (pid, item_id, _CNPJ_LAB_A),
        )

    with _espera_unique_violation(outer_conn, "sp_dupla_item"):
        with outer_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pedido_exame_custodia
                  (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
                VALUES (%s, %s, 'paciente', %s, NOW(), NULL, NULL)
                """,
                (pid, item_id, _CNPJ_LAB_B),
            )


def test_constraint_permite_posse_encerrada_convivendo_com_ativa(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A constraint guarda EXCLUSIVIDADE, não imobilidade.

    Depois de emitir e transferir há duas linhas — uma encerrada e uma ativa.
    Se o índice não fosse parcial, o histórico seria impossível de manter, e a
    cadeia de custódia (§3) deixaria de existir para caber na constraint.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)
    assert _transferir(client, proto).status_code == 201

    todas = _custodias(outer_conn, proto)
    assert len(todas) == 2
    assert len([c for c in todas if c[3] is None]) == 1


# ---------------------------------------------------------------------------
# 2 — todo caminho de produto passa pelo choke-point
# ---------------------------------------------------------------------------

def test_emissao_na_carteira_abre_uma_posse(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)

    ativas = _ativas(outer_conn, proto)
    assert len(ativas) == 1
    assert ativas[0][1] == "prescritor"
    assert ativas[0][2] == "paciente", "para o cidadão, a coluna guarda o PAPEL"


def test_transferir_fecha_a_posse_do_cidadao(client, outer_conn, seed_usuario, seed_paciente):
    """O caminho do J.7, agora com fechamento explícito.

    Antes, transferir só inseria: a posse do cidadão continuava "ativa" no
    banco e a verdade dependia de quem lesse a última linha. Agora a posse
    anterior é fechada no mesmo ato — e a constraint não deixa esquecer.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)
    assert _transferir(client, proto).status_code == 201

    ativas = _ativas(outer_conn, proto)
    assert len(ativas) == 1
    assert ativas[0][2] == _CNPJ_LAB_A

    encerradas = [c for c in _custodias(outer_conn, proto) if c[3] is not None]
    assert len(encerradas) == 1
    assert encerradas[0][2] == "paciente", "a posse fechada é a do cidadão"


def test_agendar_fecha_a_posse_anterior(client, outer_conn, seed_usuario, seed_paciente):
    """`POST /pedidos-exame/{p}/agendar` também roteia pelo choke-point.

    Este caminho abria custódia SEM emitir `custodia_transferida` — o §2 do
    CLAUDE.md é explícito em chamar isso de bug, não feature ("abrir custódia
    sem o evento é bug: o ledger é a fonte da verdade da cadeia de custódia").
    Passar pelo choke-point corrige as duas coisas de uma vez: fecha a anterior
    e emite o evento que faltava.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)

    r = client.post(
        f"/pedidos-exame/{proto}/agendar",
        json={"cnpj_prestador": _CNPJ_LAB_A, "nome_prestador": "LAB A",
              "data_agendamento": "2026-09-01"},
        headers=_headers(token_p),
    )
    assert r.status_code in (200, 201), r.text

    ativas = _ativas(outer_conn, proto)
    assert len(ativas) == 1
    assert ativas[0][2] == _CNPJ_LAB_A

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.tipo_evento FROM pedido_exame_eventos e
              JOIN pedidos_exame p ON p.id = e.pedido_id
             WHERE p.protocolo = %s
            """,
            (proto,),
        )
        eventos = [r[0] for r in cur.fetchall()]
    assert "custodia_transferida" in eventos, (
        "abrir custódia sem emitir o evento é bug (§2 do CLAUDE.md), não feature"
    )


# ---------------------------------------------------------------------------
# 3 — regressão: a leitura de posse continua correta (J.7 depende dela)
# ---------------------------------------------------------------------------

def test_carteira_e_guard_continuam_coerentes(client, seed_usuario, seed_paciente):
    """`sob_minha_custodia`, o guard de 409 e a fila leem a posse ATIVA."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)

    def _cartao():
        r = client.get("/paciente/pedidos-exame", headers=_headers(_token_paciente()))
        assert r.status_code == 200
        todos = [*r.json()["posse"], *r.json()["em_andamento"], *r.json()["historico"]]
        return [p for p in todos if p["protocolo"] == proto][0]

    assert _cartao()["sob_minha_custodia"] is True
    assert _transferir(client, proto).status_code == 201

    cartao = _cartao()
    assert cartao["sob_minha_custodia"] is False
    assert cartao["detentor"] == _CNPJ_LAB_A

    # Posse é exclusiva: o segundo laboratório leva 409, não uma segunda posse.
    r2 = _transferir(client, proto, _CNPJ_LAB_B)
    assert r2.status_code == 409, r2.text

    # E o pedido está na fila de A — e não na de B.
    def _fila(cnpj):
        rr = client.get(
            "/dispensadores/fila-exames",
            headers=_headers(criar_access_token(sub=cnpj, role="dispensador", nome="LAB")),
        )
        assert rr.status_code == 200, rr.text
        return [p["protocolo"] for p in rr.json()["fila"]]

    assert proto in _fila(_CNPJ_LAB_A)
    assert proto not in _fila(_CNPJ_LAB_B)


def test_fila_nao_mostra_pedido_cuja_posse_ja_saiu(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Ex-custodiante não vê mais o pedido.

    Com a leitura por "última linha" isso já valia; o teste garante que a troca
    para `encerrada_em IS NULL` não afrouxou nada. Um laboratório que ainda
    enxergasse o pedido depois de perder a posse poderia acioná-lo — vazamento
    entre prestadores, que é o AC (vi) do J.10 antecipado no que dá.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, token_p, enviar_ao_paciente=True)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    # A devolve ao cidadão por SQL (não há endpoint de devolução antes do J.10):
    # fecha a posse de A e reabre a do paciente — o que o choke-point fará.
    pid = _pedido_id(outer_conn, proto)
    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE pedido_exame_custodia SET encerrada_em = NOW() "
            "WHERE pedido_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (pid,),
        )
        cur.execute(
            """
            INSERT INTO pedido_exame_custodia
              (pedido_id, item_id, de, para, transferido_em, encerrada_em, dados_json)
            VALUES (%s, NULL, %s, 'paciente', NOW(), NULL, NULL)
            """,
            (pid, _CNPJ_LAB_A),
        )

    rr = client.get(
        "/dispensadores/fila-exames",
        headers=_headers(criar_access_token(sub=_CNPJ_LAB_A, role="dispensador", nome="LAB")),
    )
    assert rr.status_code == 200
    assert proto not in [p["protocolo"] for p in rr.json()["fila"]]
