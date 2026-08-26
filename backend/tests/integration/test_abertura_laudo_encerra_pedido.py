"""MARTELO DO FABIANO, 26/08/2026 (`core`) — abrir o laudo fecha o pedido.

SUPERA o martelo de 24/08 ("a ciência é explícita e não se deriva de abrir o
laudo; ciência do laudo é do laudo, ciência do pedido é do pedido"), que está
registrado em `cidadao.html`. A regra nova, dita pelo arquiteto após percorrer a
vitrine: *"o exame anda sozinho para o Histórico assim que o cidadão abre"*.

O que muda: a primeira abertura do laudo pelo cidadão passa a ENCERRAR também os
itens do PEDIDO que aquele laudo cobre, e a redirivar o status do pedido. Antes,
o cidadão precisava de dois gestos — abrir o laudo e, à parte, confirmar ciência
do pedido — e o pedido ficava aberto se ele fizesse só o primeiro.

O QUE **NÃO** MUDA, e estes testes guardam:
  - Abrir segue IDEMPOTENTE: a segunda abertura não emite nada, nem no ledger do
    laudo nem no do pedido (espírito R2 — um fato, um evento).
  - O laudo cobre ITENS, não o pedido inteiro. Num pedido dividido entre
    laboratórios (J.10), abrir o laudo de um NÃO encerra o item do outro.
  - `POST /pedidos-exame/{proto}/encerrar` continua existindo e funcionando: há
    pedido sem laudo, e há o caminho do prescritor.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)
from tests.integration.test_laudo_abertura import _h, _tok_lab, _tok_pac, _LAB


def _pedido_com_resultado(client, tp, nomes: list[str], quantos_com_resultado=None):
    """Pedido entregue ao laboratório, coletado e com resultado registrado."""
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": n, "quantidade": 1} for n in nomes],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    assert client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json={"cnpj_laboratorio": _LAB, "nome_laboratorio": "LAB"},
                       headers=_h(_tok_pac())).status_code == 201

    hl = _h(_tok_lab())
    ids = [i["id"] for i in client.get(f"/pedidos-exame/{proto}", headers=hl).json()["itens"]]
    alvos = ids if quantos_com_resultado is None else ids[:quantos_com_resultado]
    for i in alvos:
        assert client.post(f"/pedidos-exame/{proto}/itens/{i}/coletar",
                           json={}, headers=hl).status_code == 201
        assert client.post(f"/pedidos-exame/{proto}/itens/{i}/resultado",
                           json={"resultado_resumo": "98 mg/dL"}, headers=hl).status_code in (200, 201)
    return proto, ids


def _laudo_liberado_de(client, proto, itens_do_laudo: list[tuple[str, int]]) -> str:
    hl = _h(_tok_lab())
    rl = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": n, "conclusao": "normal", "pedido_item_id": i}
                  for n, i in itens_do_laudo],
    }, headers=hl)
    assert rl.status_code == 201, rl.text
    lp = rl.json()["protocolo"]
    assert client.post(f"/laudos/{lp}/assinar", headers=hl).status_code == 200
    assert client.post(f"/laudos/{lp}/liberar", json={}, headers=hl).status_code == 200
    return lp


def _pedido(client, proto, tok=None):
    r = client.get(f"/pedidos-exame/{proto}", headers=_h(tok or _tok_lab()))
    assert r.status_code == 200, r.text
    return r.json()


def _eventos_pedido(client, proto) -> list[str]:
    return [e["tipo_evento"] for e in _pedido(client, proto)["eventos"]]


# ---------------------------------------------------------------------------
# O martelo
# ---------------------------------------------------------------------------

def test_abrir_o_laudo_encerra_o_pedido(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _pedido_com_resultado(client, tp, ["GLICEMIA"])
    lp = _laudo_liberado_de(client, proto, [("GLICEMIA", ids[0])])

    antes = _pedido(client, proto)
    assert antes["status"] == "resultado_disponivel"
    assert antes["itens"][0]["status_item"] == "resultado_disponivel"

    r = client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    assert r.json()["primeira_abertura"] is True

    depois = _pedido(client, proto)
    assert depois["status"] == "encerrado", "o pedido não andou sozinho para o Histórico"
    assert depois["itens"][0]["status_item"] == "encerrado"
    assert "pedido_encerrado" in _eventos_pedido(client, proto)


def test_o_ledger_do_pedido_diz_de_onde_veio_o_encerramento(
    client, seed_usuario, seed_paciente
):
    """A ciência é DERIVADA — e o ledger não pode fingir que houve gesto próprio.

    Mesma disciplina do `laudo_aberto_paciente`, que grava `origem: "abertura"`.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _pedido_com_resultado(client, tp, ["GLICEMIA"])
    lp = _laudo_liberado_de(client, proto, [("GLICEMIA", ids[0])])
    assert client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac())).status_code == 200

    ev = next(e for e in _pedido(client, proto)["eventos"]
              if e["tipo_evento"] == "pedido_encerrado")
    import json as _json
    dados = ev["dados_json"]
    dados = _json.loads(dados) if isinstance(dados, str) else dados
    assert dados.get("origem") == "abertura_laudo", dados
    assert dados.get("laudo_protocolo") == lp, dados


def test_segunda_abertura_nao_encerra_de_novo(client, seed_usuario, seed_paciente):
    """Um fato, um evento (R2). Reabrir o cartão não pode duplicar o fecho."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _pedido_com_resultado(client, tp, ["GLICEMIA"])
    lp = _laudo_liberado_de(client, proto, [("GLICEMIA", ids[0])])

    assert client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac())).status_code == 200
    r2 = client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac()))
    assert r2.status_code == 200
    assert r2.json()["primeira_abertura"] is False

    assert _eventos_pedido(client, proto).count("pedido_encerrado") == 1


def test_abertura_parcial_nao_fecha_nada_e_a_ultima_fecha_tudo(
    client, seed_usuario, seed_paciente
):
    """O fecho é ATÔMICO — escolha declarada onde o martelo não alcançou.

    Um laudo que cobre parte do pedido não fecha nem os seus próprios itens: o
    ledger do exame só tem `pedido_encerrado` ("ciência registrada"), e não há
    evento que nomeie "itens fechados, pedido aberto". Emitir `pedido_encerrado`
    com o pedido aberto seria anunciar fato que não houve.

    A consequência é boa: o pedido fecha na ÚLTIMA abertura, e fecha inteiro.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _pedido_com_resultado(client, tp, ["GLICEMIA", "HEMOGRAMA"])
    lp1 = _laudo_liberado_de(client, proto, [("GLICEMIA", ids[0])])

    assert client.post(f"/laudos/{lp1}/abrir", headers=_h(_tok_pac())).status_code == 200

    por_id = {i["id"]: i for i in _pedido(client, proto)["itens"]}
    assert por_id[ids[0]]["status_item"] == "resultado_disponivel", "fecho parcial não acontece"
    assert por_id[ids[1]]["status_item"] == "resultado_disponivel"
    assert _pedido(client, proto)["status"] == "resultado_disponivel"
    assert "pedido_encerrado" not in _eventos_pedido(client, proto)

    # A última abertura completa a ciência — e aí tudo fecha de uma vez.
    lp2 = _laudo_liberado_de(client, proto, [("HEMOGRAMA", ids[1])])
    assert client.post(f"/laudos/{lp2}/abrir", headers=_h(_tok_pac())).status_code == 200

    depois = _pedido(client, proto)
    assert depois["status"] == "encerrado"
    assert all(i["status_item"] == "encerrado" for i in depois["itens"])
    assert _eventos_pedido(client, proto).count("pedido_encerrado") == 1


def test_gesto_explicito_de_encerrar_continua_existindo(
    client, seed_usuario, seed_paciente
):
    """Há pedido sem laudo — e há o caminho do prescritor. Não se remove porta."""
    tp = obter_token_prescritor(client, seed_usuario)
    proto, _ = _pedido_com_resultado(client, tp, ["GLICEMIA"])
    assert _pedido(client, proto)["status"] == "resultado_disponivel"

    r = client.post(f"/pedidos-exame/{proto}/encerrar", headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    assert _pedido(client, proto)["status"] == "encerrado"


def test_item_com_resultado_e_sem_laudo_segura_o_pedido_aberto(
    client, seed_usuario, seed_paciente
):
    """Resultado sem laudo não é ciência de ninguém — e não pode fechar o ciclo.

    Guarda a segunda metade da regra: o fecho exige que TODO item pendente esteja
    coberto por laudo aberto. Um exame cujo resultado o laboratório registrou sem
    laudar não foi lido pelo cidadão, e segura o pedido.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _pedido_com_resultado(client, tp, ["GLICEMIA", "HEMOGRAMA"])
    lp = _laudo_liberado_de(client, proto, [("GLICEMIA", ids[0])])

    assert client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac())).status_code == 200

    d = _pedido(client, proto)
    assert d["status"] == "resultado_disponivel"
    assert all(i["status_item"] == "resultado_disponivel" for i in d["itens"])
