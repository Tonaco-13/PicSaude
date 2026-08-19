"""Custódia PARCIAL de exames — J.10 (`module`), dialeto PostgreSQL.

DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md §4, sobre a base do PR `core`
"custódia de exame ganha posse atual" (branch `core/custodia-exame-posse-atual`,
este arquivo roda EMPILHADO nela):

  (i)   transferir 2 de 5 → 2 na fila do CNPJ, 3 com o cidadão e
        transferíveis a outro                                  → test_parcial_…
  (ii)  devolução → item `pendente` + custódia paciente + evento
                                                                → test_devolucao_…
  (iv)  remanescentes circulam a outro laboratório até o resultado
                                                                → test_remanescente_…
  (vi)  fila de um CNPJ não mostra item sob custódia de outro   → test_fila_…

O AC (iii) — constraint recusando dupla posse ativa — já está coberto NOS DOIS
dialetos pelos testes do PR core (`test_j10_core_posse_exame.py` aqui,
`test_j10_core_migracao_sqlite.py` no SQLite). O AC (v) é o smoke de navegador
`tests/browser/test_j10_custodia_parcial.py`.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import json

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

_NOMES_ITENS = ["HEMOGRAMA", "GLICEMIA", "TSH", "COLESTEROL", "URINA"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_paciente(cpf: str = SEED_PACIENTE_CPF) -> str:
    return criar_access_token(sub=cpf, role="paciente", nome=SEED_PACIENTE_NOME)


def _token_lab(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="LAB TESTE")


def _emitir_5_itens(client, token_prescritor: str) -> str:
    payload = {
        "cns_prescritor":      SEED_PRESCRITOR_CNS,
        "nome_prescritor":     "DR. TESTE J10",
        "cpf_paciente":        SEED_PACIENTE_CPF,
        "nome_paciente":       SEED_PACIENTE_NOME,
        "tipo_emissao":        "novo",
        "prioridade":          "rotina",
        "enviar_ao_paciente":  True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in _NOMES_ITENS],
    }
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _item_ids(outer_conn, proto: str) -> list[int]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id FROM pedido_exame_itens i "
            "JOIN pedidos_exame p ON p.id = i.pedido_id "
            "WHERE p.protocolo = %s ORDER BY i.id",
            (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _posse_viva(outer_conn, proto: str) -> list[tuple]:
    """(item_id, para) das custódias ATIVAS — a resposta do "quem detém o quê"."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT c.item_id, c.para FROM pedido_exame_custodia c "
            "JOIN pedidos_exame p ON p.id = c.pedido_id "
            "WHERE p.protocolo = %s AND c.encerrada_em IS NULL ORDER BY c.item_id NULLS FIRST",
            (proto,),
        )
        return cur.fetchall()


def _eventos_custodia(outer_conn, proto: str) -> list[dict]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT e.dados_json FROM pedido_exame_eventos e "
            "JOIN pedidos_exame p ON p.id = e.pedido_id "
            "WHERE p.protocolo = %s AND e.tipo_evento = 'custodia_transferida' "
            "ORDER BY e.id",
            (proto,),
        )
        return [json.loads(r[0]) for r in cur.fetchall() if r[0]]


def _fila(client, cnpj: str) -> dict:
    r = client.get("/dispensadores/fila-exames", headers=_headers(_token_lab(cnpj)))
    assert r.status_code == 200, r.text
    return r.json()


def _fila_do_pedido(client, cnpj: str, proto: str) -> dict | None:
    return next((p for p in _fila(client, cnpj)["fila"] if p["protocolo"] == proto), None)


def _cartao(client, proto: str) -> dict:
    r = client.get("/paciente/pedidos-exame", headers=_headers(_token_paciente()))
    assert r.status_code == 200, r.text
    todos = [*r.json()["posse"], *r.json()["em_andamento"], *r.json()["historico"]]
    return next(p for p in todos if p["protocolo"] == proto)


def _transferir(client, proto: str, cnpj: str, itens: list[int] | None = None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB TESTE"}
    if itens is not None:
        body["itens"] = itens
    return client.post(
        f"/pedidos-exame/{proto}/transferir-laboratorio",
        json=body,
        headers=_headers(_token_paciente()),
    )


def _devolver(client, proto: str, item_id: int, cnpj: str, motivo="Não realizamos este exame"):
    return client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/devolver",
        json={"motivo": motivo},
        headers=_headers(_token_lab(cnpj)),
    )


# ---------------------------------------------------------------------------
# AC (i) — transferência parcial: 2 de 5
# ---------------------------------------------------------------------------

def test_parcial_dois_de_cinco_aci(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert len(ids) == 5

    r = _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[1], ids[3]])
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["parcial"] is True
    assert corpo["itens_transferidos"] == 2
    assert corpo["itens"] == sorted([ids[1], ids[3]])

    # Explosão §3.3: não sobrou posse ativa de nível-pedido; cada item ativo
    # tem a SUA linha — 2 com o CNPJ, 3 com o cidadão.
    posse = dict(_posse_viva(outer_conn, proto))
    assert None not in posse, "nível-pedido foi dissolvido"
    assert posse[ids[1]] == _CNPJ_LAB_A and posse[ids[3]] == _CNPJ_LAB_A
    for outro in (ids[0], ids[2], ids[4]):
        assert posse[outro] == "paciente"

    # Itens NÃO mudam de estado (J.7 segue valendo na parcial).
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.status_item FROM pedido_exame_itens i WHERE i.id = ANY(%s)",
            (ids,),
        )
        assert {r[0] for r in cur.fetchall()} == {"pendente"}

    # Fila de A: o pedido está lá, com EXATAMENTE os 2 itens dele.
    fila = _fila_do_pedido(client, _CNPJ_LAB_A, proto)
    assert fila is not None
    assert {it["item_id"] for it in fila["itens"]} == {ids[1], ids[3]}

    # Um evento por linha aberta — todos nível-item, motivo da parcial; as 3
    # linhas que só re-expressam a granularidade vêm marcadas como tal.
    parc = [e for e in _eventos_custodia(outer_conn, proto)
            if e.get("motivo") == "transferencia_parcial"]
    assert len(parc) == 5
    assert {e.get("item_id") for e in parc} == set(ids)
    reex = {e.get("item_id") for e in parc if e.get("reexpressao_nivel_item")}
    assert reex == {ids[0], ids[2], ids[4]}

    # Carteira: pedido segue "com o cidadão" (ele ainda detém 3); por item,
    # 3 seus, 2 com o laboratório — é o que habilita os checkboxes (§3.6).
    cartao = _cartao(client, proto)
    assert cartao["sob_minha_custodia"] is True
    por_id = {it["id"]: it for it in cartao["itens"]}
    assert por_id[ids[1]]["sob_minha_custodia"] is False
    assert por_id[ids[1]]["detentor"] == _CNPJ_LAB_A
    for outro in (ids[0], ids[2], ids[4]):
        assert por_id[outro]["sob_minha_custodia"] is True


def test_parcial_guarda_item_que_nao_e_do_cidadao(client, outer_conn, seed_usuario, seed_paciente):
    """Cidadão não entrega a outro CNPJ item que está com o primeiro (409)."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0]]).status_code == 201

    r = _transferir(client, proto, _CNPJ_LAB_B, itens=[ids[0]])
    assert r.status_code == 409, r.text


def test_parcial_valida_payload_de_itens(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)

    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[]).status_code == 422
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[0]]).status_code == 422
    # id que não é do pedido: 404, não 500 nem 409 genérico
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[999999]).status_code == 404


def test_retrocompat_sem_itens_continua_nivel_pedido(client, outer_conn, seed_usuario, seed_paciente):
    """Payload sem `itens` (pedido nunca explodido): o caminho J.7 intacto."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)

    r = _transferir(client, proto, _CNPJ_LAB_A)
    assert r.status_code == 201, r.text
    corpo = r.json()
    assert corpo["parcial"] is False
    assert corpo["itens_transferidos"] == 5

    posse = dict(_posse_viva(outer_conn, proto))
    assert set(posse) == {None}, "posse ativa única, de nível-pedido"
    assert posse[None] == _CNPJ_LAB_A

    # Segunda integral em outro CNPJ segue levando 409 (posse exclusiva, J.7).
    assert _transferir(client, proto, _CNPJ_LAB_B).status_code == 409


def test_sem_itens_em_modo_item_envia_os_meus(client, outer_conn, seed_usuario, seed_paciente):
    """"Nenhum marcado = todos" (§3.6): em modo-item, tudo o que É do cidadão."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    # Sem `itens`: os 3 que estão com o cidadão vão a B; os 2 de A intocados.
    r = _transferir(client, proto, _CNPJ_LAB_B)
    assert r.status_code == 201, r.text
    assert r.json()["itens_transferidos"] == 3

    posse = dict(_posse_viva(outer_conn, proto))
    assert posse[ids[0]] == _CNPJ_LAB_A and posse[ids[1]] == _CNPJ_LAB_A
    for outro in (ids[2], ids[3], ids[4]):
        assert posse[outro] == _CNPJ_LAB_B


# ---------------------------------------------------------------------------
# AC (ii) — devolução por item
# ---------------------------------------------------------------------------

def test_devolucao_por_item_acii(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201  # nível-pedido

    r = _devolver(client, proto, ids[2], _CNPJ_LAB_A, motivo="Sem reagente no momento")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["status_item"] == "pendente", "devolução é posse, não estado"
    assert corpo["detentor"] == "paciente"
    assert corpo["motivo"] == "devolucao_nao_realizavel"

    # Explosão a partir da devolução: nível-pedido fechado; o item devolvido
    # com o cidadão; os demais re-expressos em nível-item com a própria unidade.
    posse = dict(_posse_viva(outer_conn, proto))
    assert None not in posse
    assert posse[ids[2]] == "paciente"
    for outro in (ids[0], ids[1], ids[3], ids[4]):
        assert posse[outro] == _CNPJ_LAB_A

    # O evento da devolução: motivo canônico + declarado, no nível do item.
    alvo = [
        e for e in _eventos_custodia(outer_conn, proto)
        if e.get("motivo") == "devolucao_nao_realizavel" and e.get("item_id") == ids[2]
    ]
    assert alvo, "devolução sem custodia_transferida é bug (§2 do CLAUDE.md)"
    assert alvo[0]["para"] == "paciente"
    assert alvo[0].get("motivo_declarado") == "Sem reagente no momento"

    # Fila de A: o pedido segue, mas o item devolvido NÃO (AC vi na devolução).
    fila = _fila_do_pedido(client, _CNPJ_LAB_A, proto)
    assert fila is not None
    assert {it["item_id"] for it in fila["itens"]} == {ids[0], ids[1], ids[3], ids[4]}


def test_devolucao_em_modo_item_so_o_item_mexe(client, outer_conn, seed_usuario, seed_paciente):
    """Devolução quando o pedido já opera por item: uma linha muda, só ela."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    r = _devolver(client, proto, ids[0], _CNPJ_LAB_A)
    assert r.status_code == 200, r.text

    posse = dict(_posse_viva(outer_conn, proto))
    assert posse[ids[0]] == "paciente"
    assert posse[ids[1]] == _CNPJ_LAB_A, "o outro item do CNPJ não foi tocado"
    assert posse[ids[2]] == "paciente" and posse[ids[3]] == "paciente"


def test_devolucao_guardas(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    # Quem não detém o item não o devolve — nem outro laboratório…
    assert _devolver(client, proto, ids[0], _CNPJ_LAB_B).status_code == 403
    # …nem um CNPJ qualquer no pedido do cidadão.
    assert _devolver(client, proto, ids[2], _CNPJ_LAB_B).status_code == 403
    # Item inexistente: 404.
    assert _devolver(client, proto, 999999, _CNPJ_LAB_A).status_code == 404


def test_devolucao_exige_item_pendente(client, outer_conn, seed_usuario, seed_paciente):
    """Item coletado tem material na unidade: devolução de posse é 422.

    `agendado` idem — quem devolve um item marcado primeiro cancela o
    agendamento (caminho existente), que é o que o devolve a `pendente`.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A).status_code == 201

    r = client.post(
        f"/pedidos-exame/{proto}/itens/{ids[0]}/coletar",
        headers=_headers(_token_lab(_CNPJ_LAB_A)),
    )
    assert r.status_code == 201, r.text

    assert _devolver(client, proto, ids[0], _CNPJ_LAB_A).status_code == 422


# ---------------------------------------------------------------------------
# AC (iv) — remanescentes circulam a outro laboratório ATÉ O RESULTADO
# ---------------------------------------------------------------------------

def test_remanescente_circula_ate_o_resultado_aciv(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    # O item que ficou com o cidadão segue a OUTRO laboratório…
    assert _transferir(client, proto, _CNPJ_LAB_B, itens=[ids[2]]).status_code == 201

    # …que coleta (guard item-scoped: B detém o item, não o pedido)…
    r = client.post(
        f"/pedidos-exame/{proto}/itens/{ids[2]}/coletar",
        headers=_headers(_token_lab(_CNPJ_LAB_B)),
    )
    assert r.status_code == 201, r.text

    # …e registra o resultado. Fim do percurso digital do item.
    r = client.post(
        f"/pedidos-exame/{proto}/itens/{ids[2]}/resultado",
        json={"resultado_resumo": "dentro da normalidade"},
        headers=_headers(_token_lab(_CNPJ_LAB_B)),
    )
    assert r.status_code == 201, r.text
    assert r.json()["status_item"] == "resultado_disponivel"

    # A coleta de item alheio continua bloqueada (guard item-scoped fecha):
    assert client.post(
        f"/pedidos-exame/{proto}/itens/{ids[3]}/coletar",
        headers=_headers(_token_lab(_CNPJ_LAB_B)),
    ).status_code == 403


# ---------------------------------------------------------------------------
# AC (vi) — fila de um CNPJ não mostra item sob custódia de outro
# ---------------------------------------------------------------------------

def test_fila_nao_vaza_item_entre_prestadores_acvi(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201
    assert _transferir(client, proto, _CNPJ_LAB_B, itens=[ids[2]]).status_code == 201

    # Cada fila vê o pedido, mas só os SEUS itens — nem sobra nem falta.
    assert {it["item_id"] for it in _fila_do_pedido(client, _CNPJ_LAB_A, proto)["itens"]} == {ids[0], ids[1]}
    assert {it["item_id"] for it in _fila_do_pedido(client, _CNPJ_LAB_B, proto)["itens"]} == {ids[2]}

    # CNPJ sem posse nenhuma não vê o pedido (regressão do J.7 preservada).
    assert _fila_do_pedido(client, "11111111000111", proto) is None


def test_get_pedido_filtra_itens_pela_posse_acvi(client, outer_conn, seed_usuario, seed_paciente):
    """O GET individual também não vaza: parcial vê só o seu; de fora, 403."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _emitir_5_itens(client, token_p)
    ids = _item_ids(outer_conn, proto)
    assert _transferir(client, proto, _CNPJ_LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    r = client.get(f"/pedidos-exame/{proto}", headers=_headers(_token_lab(_CNPJ_LAB_A)))
    assert r.status_code == 200, r.text
    assert {it["id"] for it in r.json()["itens"]} == {ids[0], ids[1]}

    # Quem não detém nada do pedido segue levando 403, como sempre.
    assert client.get(
        f"/pedidos-exame/{proto}", headers=_headers(_token_lab(_CNPJ_LAB_B))
    ).status_code == 403
