"""ENG-016 §3 — `GET /encaminhamentos/meus`: lista por DEVER, selo por POSSE.

A LEI Nº 1 DO §2, EXECUTÁVEL
----------------------------
  > Abas listam por DEVER do papel; selos mostram POSSE física — duas queries.
  > `atendido` é dever do destino com posse no cidadão: listar por custódia o
  > faria sumir da tela exatamente quando vira obrigação.

É o caso que dá nome à regra, e é o teste central deste arquivo. Uma
implementação que listasse por custódia passaria em quase tudo — e falharia
justamente onde o profissional precisa ser lembrado do que deve.

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

_CNS_DESTINO = "700000000000001"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok(cns): return criar_access_token(sub=cns, role="prescritor", nome="DR")
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente",
                                          nome=SEED_PACIENTE_NOME)


def _emitir(client, token) -> str:
    r = client.post("/encaminhamentos", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR ORIGEM",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "cns_destino": _CNS_DESTINO, "especialidade_destino": "CARDIOLOGIA",
        "justificativa_clinica": "dor torácica", "finalidade": "avaliacao",
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, headers=_h(token))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _meus(client, token) -> dict:
    r = client.get("/encaminhamentos/meus", headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()


def _achar(lista, proto):
    return next((x for x in lista if x["protocolo"] == proto), None)


def test_cada_um_ve_pelo_seu_chapeu(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)

    do_origem = _meus(client, tp)
    assert _achar(do_origem["encaminhados"], proto), "a origem não vê o que emitiu"
    assert not _achar(do_origem["recebidos"], proto), "a origem apareceu como destino"

    do_destino = _meus(client, _tok(_CNS_DESTINO))
    assert _achar(do_destino["recebidos"], proto), "o destino não vê o que recebeu"
    assert not _achar(do_destino["encaminhados"], proto)


def test_atendido_e_dever_do_destino_com_posse_no_cidadao(client, seed_usuario, seed_paciente):
    """O CASO QUE DÁ NOME À LEI Nº 1.

    Depois de atender, o documento volta ao cidadão (posse) — e o destino passa
    a DEVER a contrarreferência. Se a lista fosse por custódia, o item sumiria
    da tela dele no exato momento em que vira obrigação.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok(_CNS_DESTINO)

    assert client.post(f"/encaminhamentos/{proto}/agendar",
                       json={"data_agendamento": "2026-09-10T09:00:00"},
                       headers=_h(td)).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200
    assert client.post(f"/encaminhamentos/{proto}/atender",
                       headers=_h(td)).status_code == 200

    linha = _achar(_meus(client, td)["recebidos"], proto)
    assert linha is not None, (
        "o encaminhamento sumiu da tela do destino ao virar obrigação — "
        "a lista está seguindo a custódia, e a lei nº 1 do §2 proíbe"
    )
    assert linha["dever"] == "devo_retorno"
    assert linha["posse_tipo"] == "paciente", "a posse voltou ao cidadão"


def test_os_deveres_do_destino_acompanham_o_percurso(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    td = _tok(_CNS_DESTINO)

    assert _achar(_meus(client, td)["recebidos"], proto)["dever"] == "chegou"

    client.post(f"/encaminhamentos/{proto}/agendar",
                json={"data_agendamento": "2026-09-10T09:00:00"}, headers=_h(td))
    assert _achar(_meus(client, td)["recebidos"], proto)["dever"] == "chegou", (
        "agendar não tira o item da gaveta de decisão — ele ainda não foi atendido"
    )

    client.post(f"/encaminhamentos/{proto}/atender", headers=_h(td))
    assert _achar(_meus(client, td)["recebidos"], proto)["dever"] == "devo_retorno"

    client.post(f"/encaminhamentos/{proto}/contrarreferir",
                json={"conteudo_clinico": "avaliado e devolvido"}, headers=_h(td))
    assert _achar(_meus(client, td)["recebidos"], proto)["dever"] == "devolvi"


def test_a_posse_vem_da_custodia_e_muda_com_o_gesto_do_cidadao(client, seed_usuario, seed_paciente):
    """O selo do §2 lei nº 2 — e a prova de que ele lê custódia, não status."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)

    assert _achar(_meus(client, tp)["encaminhados"], proto)["posse_tipo"] == "paciente"

    assert client.post(f"/encaminhamentos/{proto}/entregar",
                       headers=_h(_tok_pac())).status_code == 200
    linha = _achar(_meus(client, tp)["encaminhados"], proto)
    assert linha["posse_tipo"] == "prescritor"
    assert linha["posse_id"] == _CNS_DESTINO
    assert linha["status"] == "emitido", (
        "o estado mudou junto com a posse — §1a: entregar não é etapa clínica"
    )


def test_prescritor_alheio_nao_ve_nada(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    alheio = _meus(client, _tok("700000000000009"))
    assert not _achar(alheio["encaminhados"], proto)
    assert not _achar(alheio["recebidos"], proto)
