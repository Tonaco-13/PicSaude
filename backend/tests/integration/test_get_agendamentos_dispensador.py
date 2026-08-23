"""`GET /pedidos-exame/{p}/agendamentos` aceita dispensador — ENG-015, PR 1.

A ÚLTIMA ASSIMETRIA DA FAMÍLIA DO #171
---------------------------------------
O `dispensador` já estava em `require_role` deste endpoint, mas o ownership o
recusava sempre:

    else:  # dispensador → 403
        _assert_or_403(False, ..., "Prestador não lista agendamentos por pedido.")

Resultado: o laboratório MARCA (`POST /agendamentos`), REMARCA e REGISTRA FALTA
(micro-ticket #171) — mas não consegue LISTAR o que ele mesmo marcou. A tela da
clínica precisava dizer ao operador que a lista "é visível ao prescritor e ao
cidadão, não ao laboratório", que é o aviso confuso que o desenho §3 manda
matar.

Era a mesma família de acidente do #171: papel esquecido numa decisão de
ownership, não decisão registrada.

O ESCOPO É DE POSSE — como o GET do pedido
-------------------------------------------
O `GET /pedidos-exame/{proto}` devolve 403 quando a unidade não detém NADA do
pedido, e filtra os itens quando detém parte. O agendamento é do PEDIDO (não
tem granularidade de item), então não há o que filtrar: ou a unidade é parte, e
vê a agenda, ou não é, e leva 403. Predicado reusado da fonte única
(`dispensador_tem_algo_no_pedido`, do #172) — nada de reescrever.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB_A = "12345678000195"
_LAB_B = "98765432000110"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(cpf=SEED_PACIENTE_CPF): return criar_access_token(sub=cpf, role="paciente", nome="PAC")
def _tok_lab(c): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _emitir(client, tp, nomes=("HEMOGRAMA", "GLICEMIA")) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in nomes],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ids(outer_conn, proto) -> list[int]:
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT i.id FROM pedido_exame_itens i JOIN pedidos_exame p ON p.id = i.pedido_id "
            "WHERE p.protocolo = %s ORDER BY i.id", (proto,))
        return [r[0] for r in cur.fetchall()]


def _transferir(client, proto, cnpj, itens=None):
    body = {"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"}
    if itens is not None:
        body["itens"] = itens
    return client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json=body, headers=_h(_tok_pac()))


def _agendar(client, tp, proto):
    r = client.post("/agendamentos", json={
        "pedido_protocolo": proto, "data_hora": "2026-09-01T08:00:00",
        "org_id": "org-aaa", "unidade_id": "u1", "tipo_agendamento": "exame",
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _listar(client, proto, cnpj):
    return client.get(f"/pedidos-exame/{proto}/agendamentos", headers=_h(_tok_lab(cnpj)))


# ---------------------------------------------------------------------------
# 1 — a assimetria morre
# ---------------------------------------------------------------------------

def test_lab_que_detem_o_pedido_lista_a_agenda(client, seed_usuario, seed_paciente):
    """Quem marca tem de conseguir ver o que marcou."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    ag = _agendar(client, tp, proto)

    r = _listar(client, proto, _LAB_A)
    assert r.status_code == 200, r.text
    assert [a["protocolo"] for a in r.json()["agendamentos"]] == [ag]


def test_lab_com_posse_parcial_tambem_lista(client, outer_conn, seed_usuario, seed_paciente):
    """Ser PARTE do pedido basta — o agendamento é do pedido, não do item."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    _agendar(client, tp, proto)

    assert _listar(client, proto, _LAB_A).status_code == 200


# ---------------------------------------------------------------------------
# 2 — o escopo de POSSE não afrouxou
# ---------------------------------------------------------------------------

def test_lab_sem_posse_nenhuma_segue_403(client, seed_usuario, seed_paciente):
    """Abrir o papel não é abrir a porta: quem não é parte segue fora."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _transferir(client, proto, _LAB_A).status_code == 201
    _agendar(client, tp, proto)

    r = _listar(client, proto, _LAB_B)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_do_pedido"


def test_ex_custodiante_perde_a_agenda(client, outer_conn, seed_usuario, seed_paciente):
    """Posse ATUAL, não histórica — mesma régua do resto do módulo.

    Sem agendar antes de propósito: devolver item já `agendado` exige o ATO
    COMPOSTO do §2 (cancela + devolve), que é entrega do PR 2. Aqui o que se
    testa é o ESCOPO — quem deixa de ser parte deixa de ver a agenda —, e ele
    não depende de haver compromisso marcado.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    ids = _ids(outer_conn, proto)
    assert _transferir(client, proto, _LAB_A, itens=[ids[0]]).status_code == 201
    assert _listar(client, proto, _LAB_A).status_code == 200

    r = client.post(f"/pedidos-exame/{proto}/itens/{ids[0]}/devolver",
                    json={"motivo": "não realizamos"}, headers=_h(_tok_lab(_LAB_A)))
    assert r.status_code == 200, r.text

    assert _listar(client, proto, _LAB_A).status_code == 403


# ---------------------------------------------------------------------------
# 3 — os outros papéis não mudaram
# ---------------------------------------------------------------------------

def test_prescritor_e_paciente_inalterados(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    _agendar(client, tp, proto)

    assert client.get(f"/pedidos-exame/{proto}/agendamentos", headers=_h(tp)).status_code == 200
    assert client.get(f"/pedidos-exame/{proto}/agendamentos",
                      headers=_h(_tok_pac())).status_code == 200


def test_paciente_alheio_segue_403(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    _agendar(client, tp, proto)

    r = client.get(f"/pedidos-exame/{proto}/agendamentos",
                   headers=_h(_tok_pac("99988877766")))
    assert r.status_code == 403, r.text
