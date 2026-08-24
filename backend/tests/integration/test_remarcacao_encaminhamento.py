"""Remarcação do encaminhamento — o RE-ATO (mini-desenho do arquiteto, 24/08).

O RULING, EM UMA LINHA
----------------------
**A data da visita é atributo do compromisso, não identidade do
encaminhamento.** Por isso remarcar é RE-ATO de agendar, e não derivação.

A regra da casa — *"remarcação = novo objeto derivado"* — vale quando o OBJETO
É o compromisso: no módulo de Agendamento, AG-001 vira AG-002 com
`origem_agendamento_id`. Aqui o objeto é o ENCAMINHAMENTO CLÍNICO (quem, por
quê, para qual especialidade), e a data é atributo dele. Derivar um
encaminhamento inteiro para trocar um horário copiaria conteúdo clínico para
mover uma marca de calendário.

O QUE NÃO NASCEU
----------------
Estado novo, aresta nova, evento novo: **nenhum**. O ato é aditivo no ledger e
idempotente no estado — e há teste para cada uma dessas três negativas, porque
"não criei nada" é a afirmação mais fácil de fazer e a mais fácil de furar
depois.

DE ONDE VEIO
------------
Achado do #188: escrevendo o teste da carteira, supus que dava para remarcar e
a máquina devolveu **409**. Ficou registrado como GAP na comissão de
diagnóstico (#189, A3). Este arquivo é o fechamento dele.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import json

from app.auth.jwt import criar_access_token
from app.domain.states_encaminhamento import (
    EVENTOS_ENCAMINHAMENTO,
    ESTADOS_ENCAMINHAMENTO,
    TRANSICOES_ENCAMINHAMENTO,
)

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNS_DESTINO = "700000000000001"
_CNS_ALHEIO  = "700000000000009"
_D1 = "2026-09-10T09:00:00"
_D2 = "2026-09-24T14:30:00"
_D3 = "2026-10-01T08:00:00"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok(cns): return criar_access_token(sub=cns, role="prescritor", nome="DR")
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)


def _emitir(client, tp) -> str:
    r = client.post("/encaminhamentos", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO, "especialidade_destino": "CARDIOLOGIA",
        "justificativa_clinica": "dor torácica em investigação",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _agendar(client, proto, data, tok=None):
    return client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": data},
                       headers=_h(tok or _tok(_CNS_DESTINO)))


def _eventos(outer_conn, proto):
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ev.tipo_evento, ev.payload FROM encaminhamento_eventos ev
              JOIN encaminhamentos e ON e.id = ev.encaminhamento_id
             WHERE e.protocolo = %s ORDER BY ev.id
            """, (proto,))
        return [(t, json.loads(p) if isinstance(p, str) else (p or {}))
                for t, p in cur.fetchall()]


def _carteira(client, proto):
    d = client.get("/paciente/encaminhamentos", headers=_h(_tok_pac())).json()
    todos = [*d.get("ativos", []), *d.get("historico", [])]
    return next((x for x in todos if x["protocolo"] == proto), None)


def _status(outer_conn, proto):
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM encaminhamentos WHERE protocolo = %s", (proto,))
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# AC (i) — remarcar muda a data SEM criar objeto
# ---------------------------------------------------------------------------

def test_remarcar_muda_a_data_sem_novo_objeto(client, outer_conn, seed_usuario, seed_paciente):
    """O coração do ruling: um encaminhamento, uma data nova."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _agendar(client, proto, _D1).status_code == 200

    r = _agendar(client, proto, _D2)
    assert r.status_code == 200, r.text
    assert r.json()["remarcacao"] is True
    assert r.json()["data_anterior"] == _D1

    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM encaminhamentos WHERE protocolo = %s", (proto,))
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT COUNT(*) FROM encaminhamentos "
                    " WHERE origem_encaminhamento_id IS NOT NULL")
        derivados = cur.fetchone()[0]
    assert derivados == 0, (
        "nasceu um objeto DERIVADO para trocar um horário — é o que o ruling "
        "recusa: a data é atributo do compromisso, não identidade do objeto"
    )


def test_a_primeira_chamada_nao_e_remarcacao(client, seed_usuario, seed_paciente):
    """`emitido → agendado` segue sendo o agendar de sempre."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    r = _agendar(client, proto, _D1)
    assert r.status_code == 200
    assert r.json()["remarcacao"] is False
    assert r.json()["data_anterior"] is None


# ---------------------------------------------------------------------------
# AC (ii) — o ledger encadeia por data_anterior → data_nova
# ---------------------------------------------------------------------------

def test_o_ledger_conta_a_cadeia_de_remarcacoes(client, outer_conn, seed_usuario, seed_paciente):
    """Sem evento novo: o MESMO `encaminhamento_agendado`, com o de/para.

    Quem lê a trilha vê a cadeia inteira sem precisar de um nome de evento novo
    para descobrir que houve remarcação.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    for d in (_D1, _D2, _D3):
        assert _agendar(client, proto, d).status_code == 200

    agendamentos = [p for t, p in _eventos(outer_conn, proto)
                    if t == "encaminhamento_agendado"]
    assert len(agendamentos) == 3, f"esperava 3 atos no ledger, vi {len(agendamentos)}"
    assert [a["data_nova"] for a in agendamentos] == [_D1, _D2, _D3]
    assert [a["data_anterior"] for a in agendamentos] == [None, _D1, _D2], (
        "a cadeia não encadeia: cada remarcação tem de dizer de ONDE veio"
    )
    assert [a["remarcacao"] for a in agendamentos] == [False, True, True]


# ---------------------------------------------------------------------------
# AC (iii) — as guardas de estado
# ---------------------------------------------------------------------------

def test_nao_se_remarca_o_passado(client, seed_usuario, seed_paciente):
    """Em `atendido` a visita JÁ ACONTECEU. Remarcar o passado não é remarcar,
    é reescrever — e objeto sanitário não se reescreve (§1)."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok(_CNS_DESTINO)
    assert _agendar(client, proto, _D1).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender", headers=_h(td)).status_code == 200

    r = _agendar(client, proto, _D2)
    assert r.status_code == 409, r.text


def test_so_o_destino_remarca(client, seed_usuario, seed_paciente):
    """Quem marcou, remarca — a lógica do #171. O prescritor de ORIGEM não
    remarca a agenda de quem vai atender."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _agendar(client, proto, _D1).status_code == 200

    assert _agendar(client, proto, _D2, tok=_tok(_CNS_ALHEIO)).status_code == 403
    assert _agendar(client, proto, _D2, tok=tp).status_code == 403


# ---------------------------------------------------------------------------
# AC (iv) — a carteira mostra a ÚLTIMA
# ---------------------------------------------------------------------------

def test_a_carteira_do_cidadao_mostra_a_data_que_vale(client, seed_usuario, seed_paciente):
    """O #188 já provava que a leitura pega a mais recente — com o evento
    injetado à mão, porque não havia como remarcar. Agora o cenário é REAL.

    Mostrar a primeira mandaria o cidadão no dia que não vale mais.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _agendar(client, proto, _D1).status_code == 200
    assert _carteira(client, proto)["data_consulta"] == _D1

    assert _agendar(client, proto, _D2).status_code == 200
    assert _carteira(client, proto)["data_consulta"] == _D2, (
        "a carteira ficou na data antiga — o cidadão iria no dia errado"
    )


# ---------------------------------------------------------------------------
# As três negativas do desenho: nenhum estado, aresta ou evento novo
# ---------------------------------------------------------------------------

def test_nenhum_estado_novo():
    assert ESTADOS_ENCAMINHAMENTO == frozenset({
        "emitido", "em_regulacao", "agendado", "atendido", "contrarreferido",
        "encerrado", "cancelado", "expirado", "negado", "encerrado_fisico",
    })


def test_nenhuma_ARESTA_nova_e_nada_de_self_loop():
    """O re-ato não pediu `agendado → agendado`.

    Self-loop é o tipo de aresta que se acrescenta "só desta vez" e depois
    ninguém sabe mais o que a máquina promete. O estado não muda porque o ato
    não é uma transição — é um fato aditivo no ledger.
    """
    assert "agendado" not in TRANSICOES_ENCAMINHAMENTO["agendado"], (
        "apareceu self-loop em `agendado` — o re-ato não precisa dele"
    )
    assert TRANSICOES_ENCAMINHAMENTO["agendado"] == frozenset(
        {"atendido", "cancelado", "expirado"})


def test_nenhum_evento_novo():
    """Vocabulário congelado — a remarcação reusa `encaminhamento_agendado`."""
    assert "encaminhamento_remarcado" not in EVENTOS_ENCAMINHAMENTO
    assert "encaminhamento_agendado" in EVENTOS_ENCAMINHAMENTO


def test_o_estado_nao_muda_ao_remarcar(client, outer_conn, seed_usuario, seed_paciente):
    """Idempotente no estado, aditivo no ledger — as duas metades do re-ato."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    assert _agendar(client, proto, _D1).status_code == 200
    antes = _status(outer_conn, proto)
    n_antes = len(_eventos(outer_conn, proto))

    assert _agendar(client, proto, _D2).status_code == 200
    assert _status(outer_conn, proto) == antes == "agendado"
    assert len(_eventos(outer_conn, proto)) == n_antes + 1, (
        "o re-ato tem de ser aditivo no ledger: um fato, um evento"
    )
