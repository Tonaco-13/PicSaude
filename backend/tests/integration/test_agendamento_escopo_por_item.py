"""`POST /agendamentos` respeita a custódia por item — ENG-014, PR A (guard).

O DEFEITO (achado do arquiteto, 20/08)
--------------------------------------
`criar_agendamento` promovia a `agendado` **todos** os itens `pendente` do
pedido (`_itens_ativos_do_pedido`), sem olhar quem detém o quê. Depois da
custódia parcial (#170), um pedido pode ter itens em três mãos ao mesmo tempo:
2 com o laboratório A, 1 com o B, 2 ainda com o cidadão.

Resultado: **o laboratório A agendava exames que não são dele** — inclusive os
que o cidadão ainda não entregou a ninguém. É a mesma família do anti-vazamento
AC (vi) do J.10, um andar acima: lá a fila MOSTRAVA item alheio, aqui o
agendamento MEXIA nele.

A REGRA
-------
`itens: [...]` opcional no payload. Ausente = **os que o solicitante detém**
(não "todos"). Presente = só os listados, e item alheio é recusado.

O default importa tanto quanto o guard: "todos os pendentes" é justamente a
suposição que a custódia parcial invalidou.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import pytest

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB_A = "12345678000195"
_LAB_B = "98765432000110"
_NOMES = ["HEMOGRAMA", "GLICEMIA", "TSH"]


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


def _transferir(client, proto, cnpj, itens=None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"}
    if itens is not None:
        body["itens"] = itens
    return client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json=body, headers=_h(_tok_pac()))


def _agendar(client, proto, cnpj, itens=None, org_id="org-aaa"):
    body = {"pedido_protocolo": proto, "data_hora": "2026-09-01T08:00:00",
            "org_id": org_id, "unidade_id": "u1", "tipo_agendamento": "exame"}
    if itens is not None:
        body["itens"] = itens
    return client.post("/agendamentos", json=body, headers=_h(_tok_lab(cnpj)))


# ---------------------------------------------------------------------------
# 1 — o vazamento que o guard fecha
# ---------------------------------------------------------------------------

def test_lab_parcial_nao_agenda_item_alheio(client, outer_conn, seed_usuario, seed_paciente):
    """O defeito, nomeado: A detém 1 de 3 e agendava os 3.

    Os outros dois seguem com o cidadão — que nem entregou ainda. Depois do
    guard, só o item de A muda de estado.
    """
    _seed_prestador(client, "org-aaa", _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)

    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    r = _agendar(client, proto, _LAB_A)
    assert r.status_code in (200, 201), r.text

    status = _status_itens(outer_conn, proto)
    assert status == ["agendado", "pendente", "pendente"], (
        f"o laboratório agendou item que não detém: {status}"
    )


def test_itens_explicitos_alheios_sao_recusados(client, outer_conn, seed_usuario, seed_paciente):
    """Pedir explicitamente o item do outro é 403 — e não move nada."""
    _seed_prestador(client, "org-aaa", _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    r = _agendar(client, proto, _LAB_A, itens=[ids[1]])
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido_exame"
    assert _status_itens(outer_conn, proto) == ["pendente", "pendente", "pendente"]


def test_lab_sem_posse_nenhuma_nao_agenda(client, outer_conn, seed_usuario, seed_paciente):
    """Quem não detém nada não agenda nada — 403, não um agendamento vazio."""
    _seed_prestador(client, "org-aaa", _LAB_A)
    _seed_prestador(client, "org-bbb", _LAB_B)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201

    r = _agendar(client, proto, _LAB_B, org_id="org-bbb")
    assert r.status_code == 403, r.text
    assert _status_itens(outer_conn, proto) == ["pendente", "pendente", "pendente"]


# ---------------------------------------------------------------------------
# 2 — o que NÃO pode ter mudado
# ---------------------------------------------------------------------------

def test_posse_do_pedido_inteiro_agenda_tudo(client, outer_conn, seed_usuario, seed_paciente):
    """Retrocompatibilidade: sem parcial, o gesto de sempre agenda o pedido todo.

    O default virou "os que detenho" — e quem detém o pedido inteiro detém
    todos, então o comportamento antigo é preservado por construção.
    """
    _seed_prestador(client, "org-aaa", _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)

    assert _transferir(client, proto, _LAB_A).status_code == 201
    assert _agendar(client, proto, _LAB_A).status_code in (200, 201)
    assert _status_itens(outer_conn, proto) == ["agendado"] * 3


def test_itens_explicitos_proprios_agendam_so_eles(client, outer_conn, seed_usuario, seed_paciente):
    """Recorte fino: detenho 2, agendo 1."""
    _seed_prestador(client, "org-aaa", _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0], ids[1]]).status_code == 201

    assert _agendar(client, proto, _LAB_A, itens=[ids[0]]).status_code in (200, 201)
    assert _status_itens(outer_conn, proto) == ["agendado", "pendente", "pendente"]


def test_prescritor_e_paciente_seguem_agendando_o_pedido(client, outer_conn, seed_usuario, seed_paciente):
    """O guard é de POSSE do prestador; prescritor e paciente não mudam.

    Sem esta regressão, apertar o dispensador quebraria os dois caminhos que a
    integração usa desde o Ticket 29.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    r = client.post("/agendamentos", json={
        "pedido_protocolo": proto, "data_hora": "2026-09-01T08:00:00",
        "org_id": "org-aaa", "unidade_id": "u1", "tipo_agendamento": "exame",
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    assert _status_itens(outer_conn, proto) == ["agendado"] * 3


def test_itens_vazio_e_recusado(client, outer_conn, seed_usuario, seed_paciente):
    """`itens: []` é ambíguo — omita o campo para agendar o que detém."""
    _seed_prestador(client, "org-aaa", _LAB_A)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201

    r = _agendar(client, proto, _LAB_A, itens=[])
    assert r.status_code == 422, r.text
