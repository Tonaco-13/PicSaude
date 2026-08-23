"""ENG-015, PR 2 — o ato composto (§2) e a válvula do §6.

AS DUAS REGRAS QUE ESTE ARQUIVO PROVA
-------------------------------------

**§2 — "Não realizamos" sobre item já AGENDADO é ATO COMPOSTO.**
Cancela o compromisso (com motivo) **e** devolve a custódia: dois fatos, dois
eventos (`agendamento_cancelado` + `custodia_transferida`), nunca um UPDATE que
funda. O teste central aqui é o do MEIO do caminho: cancelar sozinho **não**
devolve posse — o item fica "livre no papel, preso na prática", que é
exatamente o motivo de o ato ser composto. Se um dia alguém fizer o cancelamento
devolver a custódia de carona, este arquivo acusa: seriam dois fatos num evento
só, e o ledger deixaria de poder contá-los separados.

**§6 — um agendamento ativo por PEDIDO, e a mensagem ensina a válvula.**
A limitação permanece (o agendamento não tem elo com os itens; dois ativos não
saberiam dizer quem cobre o quê). O que muda é o texto do 409, que antes dava à
segunda unidade o conselho errado — "cancele o atual" — sobre agenda alheia. A
válvula é nativa e não é contorno: a coleta direta do J.7
(`pendente → coletado`), ato legítimo e completo de quem atende na hora.

Requer PostgreSQL (o conftest de integração pula sem DATABASE_URL de PG).
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

_LAB_A = "12345678000195"
_LAB_B = "98765432000110"
_ORG_A = "org-aaa"
_ORG_B = "org-bbb"
_NOMES = ["HEMOGRAMA", "GLICEMIA"]


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)
def _tok_lab(c): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _seed_prestador(client, org_id, cnpj):
    r = client.post("/prestadores", json={
        "org_id": org_id, "nome": "Lab", "tipo": "laboratorio", "cnpj": cnpj,
    }, headers=_h(criar_access_token(sub="admin", role="admin", nome="ADM")))
    assert r.status_code == 201, r.text


def _emitir(client, tp) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in _NOMES],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ids(outer_conn, proto) -> list[int]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id FROM pedido_exame_itens i JOIN pedidos_exame p ON p.id = i.pedido_id "
            "WHERE p.protocolo = %s ORDER BY i.id", (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _status_itens(outer_conn, proto) -> list[str]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.status_item FROM pedido_exame_itens i "
            "  JOIN pedidos_exame p ON p.id = i.pedido_id "
            " WHERE p.protocolo = %s ORDER BY i.id", (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _detentor_do_item(outer_conn, proto, item_id) -> str | None:
    """Quem detém a POSSE ATUAL do item — nível-item, senão nível-pedido."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.para FROM pedido_exame_custodia c
              JOIN pedidos_exame p ON p.id = c.pedido_id
             WHERE p.protocolo = %s AND c.encerrada_em IS NULL
               AND (c.item_id = %s OR c.item_id IS NULL)
             ORDER BY (c.item_id IS NULL), c.id DESC
             LIMIT 1
            """,
            (proto, item_id),
        )
        r = cur.fetchone()
        return r[0] if r else None


def _eventos_agendamento(outer_conn, ag_proto) -> list[tuple[str, dict]]:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.evento, e.payload FROM agendamento_eventos e
              JOIN agendamentos a ON a.id = e.agendamento_id
             WHERE a.protocolo = %s ORDER BY e.id
            """,
            (ag_proto,),
        )
        out = []
        for tipo, payload in cur.fetchall():
            out.append((tipo, json.loads(payload) if isinstance(payload, str) else (payload or {})))
        return out


def _eventos_pedido(outer_conn, proto) -> list[str]:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT e.tipo_evento FROM pedido_exame_eventos e
              JOIN pedidos_exame p ON p.id = e.pedido_id
             WHERE p.protocolo = %s ORDER BY e.id
            """,
            (proto,),
        )
        return [r[0] for r in cur.fetchall()]


def _transferir(client, proto, cnpj, itens=None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"}
    if itens is not None:
        body["itens"] = itens
    return client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json=body, headers=_h(_tok_pac()))


def _agendar(client, proto, cnpj, org_id, itens=None):
    body = {"pedido_protocolo": proto, "data_hora": "2026-09-01T08:00:00",
            "org_id": org_id, "unidade_id": f"u-{org_id}", "tipo_agendamento": "exame"}
    if itens is not None:
        body["itens"] = itens
    return client.post("/agendamentos", json=body, headers=_h(_tok_lab(cnpj)))


# ===========================================================================
# 1 — §2: o ato composto, e o meio do caminho que ele existe para não deixar
# ===========================================================================

def test_cancelar_sozinho_nao_devolve_a_posse(client, outer_conn, seed_usuario, seed_paciente):
    """A METADE que justifica o ato composto.

    Cancelar devolve o ITEM a `pendente` — mas a custódia continua na unidade.
    "Livre no papel, preso na prática": o cidadão não pode levar o exame a
    outro laboratório, porque ninguém devolveu nada a ele.

    Guarda de regressão em duas direções: se um dia o cancelamento passar a
    devolver posse de carona, este teste cai — e deve cair, porque aí seriam
    dois fatos num evento só.
    """
    _seed_prestador(client, _ORG_A, _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    ag = _agendar(client, proto, _LAB_A, _ORG_A)
    assert ag.status_code in (200, 201), ag.text
    ag_proto = ag.json()["protocolo"]
    assert _status_itens(outer_conn, proto) == ["agendado", "agendado"]

    r = client.post(f"/agendamentos/{ag_proto}/cancelar",
                    json={"motivo": "equipamento em manutenção"},
                    headers=_h(_tok_lab(_LAB_A)))
    assert r.status_code == 200, r.text

    assert _status_itens(outer_conn, proto) == ["pendente", "pendente"], (
        "cancelar deve devolver os itens a `pendente`"
    )
    assert _detentor_do_item(outer_conn, proto, ids[0]) == _LAB_A, (
        "cancelar NÃO devolve custódia — se devolveu, dois fatos viraram um"
    )


def test_o_ato_composto_sao_dois_fatos_e_dois_eventos(client, outer_conn, seed_usuario, seed_paciente):
    """§2 inteiro: cancelar (com motivo) + devolver. O item chega ao cidadão.

    Os dois eventos ficam em ledgers diferentes — o do AGENDAMENTO conta que o
    compromisso caiu e por quê; o do PEDIDO conta que a posse mudou de mãos.
    É essa separação que permite auditar "por que não foi feito" sem inferir
    da custódia, e "onde está" sem inferir do estado.
    """
    _seed_prestador(client, _ORG_A, _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    ag_proto = _agendar(client, proto, _LAB_A, _ORG_A).json()["protocolo"]

    # fato 1 — o compromisso cai, com o porquê declarado
    r1 = client.post(f"/agendamentos/{ag_proto}/cancelar",
                     json={"motivo": "não realizamos este exame nesta unidade"},
                     headers=_h(_tok_lab(_LAB_A)))
    assert r1.status_code == 200, r1.text
    assert r1.json()["motivo"] == "não realizamos este exame nesta unidade"

    eventos_ag = _eventos_agendamento(outer_conn, ag_proto)
    tipos = [t for t, _ in eventos_ag]
    assert tipos == ["agendamento_criado", "agendamento_cancelado"], tipos
    payload_cancel = dict(eventos_ag[-1][1])
    assert payload_cancel.get("motivo_declarado") == "não realizamos este exame nesta unidade", (
        "o motivo não chegou ao ledger — cancelamento mudo é o que o §2 proíbe"
    )

    # fato 2 — a posse volta ao cidadão
    r2 = client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/devolver",
                     json={"motivo": "não realizamos este exame nesta unidade"},
                     headers=_h(_tok_lab(_LAB_A)))
    assert r2.status_code == 200, r2.text

    assert _detentor_do_item(outer_conn, proto, ids[0]) == "paciente"
    assert "custodia_transferida" in _eventos_pedido(outer_conn, proto)
    # e o item segue `pendente`: devolver é posse, não clínica (J.10)
    assert _status_itens(outer_conn, proto)[0] == "pendente"


def test_cancelar_sem_corpo_continua_valendo(client, outer_conn, seed_usuario, seed_paciente):
    """O `motivo` é opcional de propósito: `/cancelar` já existia sem corpo e é
    chamado também pelo paciente e pelo prescritor. Exigi-lo agora quebraria
    clientes que não pediram esta mudança."""
    _seed_prestador(client, _ORG_A, _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    ag_proto = _agendar(client, proto, _LAB_A, _ORG_A).json()["protocolo"]

    r = client.post(f"/agendamentos/{ag_proto}/cancelar", headers=_h(_tok_lab(_LAB_A)))
    assert r.status_code == 200, r.text
    assert r.json()["motivo"] is None
    assert "motivo_declarado" not in _eventos_agendamento(outer_conn, ag_proto)[-1][1]


# ===========================================================================
# 2 — §6: a limitação reproduzida, e a válvula que a mensagem ensina
# ===========================================================================

def test_segunda_unidade_esbarra_na_limitacao_e_o_texto_ensina_a_valvula(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A REPRODUÇÃO pedida pelo §6, com duas unidades de verdade.

    A detém o item 1 e marca. B detém o item 2 e tenta marcar: 409, porque o
    agendamento é do PEDIDO. O texto não pode mandar B cancelar o compromisso
    de A — agenda alheia não se cancela. Tem de apontar a coleta direta.
    """
    _seed_prestador(client, _ORG_A, _LAB_A)
    _seed_prestador(client, _ORG_B, _LAB_B)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)

    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201

    assert _agendar(client, proto, _LAB_A, _ORG_A).status_code in (200, 201)

    r = _agendar(client, proto, _LAB_B, _ORG_B)
    assert r.status_code == 409, r.text
    detalhe = r.json()["detail"]
    assert "OUTRA unidade" in detalhe, detalhe
    assert "execute direto" in detalhe.lower(), (
        f"a mensagem não ensina a válvula (coleta direta): {detalhe}"
    )
    assert "cancele o atual" not in detalhe.lower(), (
        f"a mensagem ainda manda cancelar agenda alheia: {detalhe}"
    )


def test_a_valvula_funciona_de_verdade(client, outer_conn, seed_usuario, seed_paciente):
    """A mensagem só ensina o que existe: B coleta direto o item que detém.

    Um evento (`pedido_coletado`), sem compromisso nenhum — a aresta
    `pendente → coletado` do J.7. E a agenda de A segue de pé: a válvula não
    atropela o compromisso alheio.
    """
    _seed_prestador(client, _ORG_A, _LAB_A)
    _seed_prestador(client, _ORG_B, _LAB_B)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _transferir(client, proto, _LAB_B, itens=[ids[1]]).status_code == 201
    ag_a = _agendar(client, proto, _LAB_A, _ORG_A).json()["protocolo"]

    r = client.post(f"/pedidos-exame/{proto}/itens/{ids[1]}/coletar",
                    json={}, headers=_h(_tok_lab(_LAB_B)))
    assert r.status_code in (200, 201), r.text

    assert _status_itens(outer_conn, proto) == ["agendado", "coletado"]
    assert _eventos_pedido(outer_conn, proto).count("pedido_coletado") == 1, (
        "a coleta direta é UM fato — se virou três, alguém trouxe de volta o "
        "agendamento instantâneo que o J.7 matou"
    )
    ag = client.get(f"/agendamentos/{ag_a}", headers=_h(_tok_lab(_LAB_A)))
    assert ag.status_code == 200 and ag.json()["status"] == "criado", (
        "a válvula de B derrubou o compromisso de A"
    )


def test_mesma_unidade_recebe_o_conselho_certo(client, outer_conn, seed_usuario, seed_paciente):
    """Quando o compromisso ativo é SEU, o conselho é outro: remarque.

    Metade esquecida do §6 — a mensagem única servia mal aos dois casos.
    """
    _seed_prestador(client, _ORG_A, _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    assert _agendar(client, proto, _LAB_A, _ORG_A).status_code in (200, 201)

    r = _agendar(client, proto, _LAB_A, _ORG_A)
    assert r.status_code == 409, r.text
    detalhe = r.json()["detail"]
    assert "Remarque" in detalhe, detalhe
    assert "OUTRA unidade" not in detalhe, detalhe
