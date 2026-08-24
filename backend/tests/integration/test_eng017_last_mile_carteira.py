"""ENG-017 PR A — a última milha da carteira: S1+S4, S3 e o recebimento.

O QUE A COMISSÃO ACHOU, E ESTE ARQUIVO FECHA
--------------------------------------------
Sete dos nove itens do diagnóstico eram a MESMA família: **o fato aconteceu no
banco e não apareceu na tela**. Núcleo são, atrito na superfície. Aqui os fatos
que já existiam passam a chegar à carteira:

  · **S1+S4 (um defeito só)** — o cartão do exame CITAVA a seção "Laudos /
    Resultados" pelo nome e não levava até ela. Agora `pedido.laudo` traz o
    elo, e só depois de LIBERADO: laudo em produção não é do cidadão (a
    custódia não passou), e anunciá-lo prometeria o que ele não pode abrir.
  · **S3 (o mais grave)** — `POST /pedidos-exame/{p}/encerrar` existia, aceitava
    `paciente`, e nenhuma tela o chamava: todo pedido morria em
    `resultado_disponivel`. Não era o repouso do J.1 — o J.1 desenhou repouso
    AGUARDANDO CIÊNCIA, e a ciência não tinha porta.
  · **R2-lite** — `liberar` cria a custódia `prestador → paciente`. O instante
    em que o laudo chegou às mãos do cidadão era fato registrado e invisível.

A CIÊNCIA DO PEDIDO NÃO SE DERIVA DE ABRIR O LAUDO (martelo do Fabiano, 24/08):
ciência do laudo é do laudo (ENG-014), ciência do pedido é do pedido. Dois
fatos, dois eventos — e há teste para os dois não se contaminarem.

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

_CNPJ_LAB = "12345678000195"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(): return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)
def _tok_lab(c=_CNPJ_LAB): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _seed_prestador(client, org_id, cnpj):
    r = client.post("/prestadores", json={
        "org_id": org_id, "nome": "Lab", "tipo": "laboratorio", "cnpj": cnpj,
    }, headers=_h(criar_access_token(sub="admin", role="admin", nome="ADM")))
    assert r.status_code == 201, r.text


def _emitir(client, tp) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "enviar_ao_paciente": True,
        "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _ate_resultado(client, proto) -> int:
    """Percorre o pedido até `resultado_disponivel` e devolve o item_id."""
    assert client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json={"cnpj_laboratorio": _CNPJ_LAB, "nome_laboratorio": "LAB"},
                       headers=_h(_tok_pac())).status_code in (200, 201)
    item_id = client.get(f"/pedidos-exame/{proto}",
                         headers=_h(_tok_lab())).json()["itens"][0]["id"]
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
                       json={}, headers=_h(_tok_lab())).status_code in (200, 201)
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
                       json={"resultado_resumo": "sem alterações"},
                       headers=_h(_tok_lab())).status_code in (200, 201)
    return item_id


def _laudo_liberado(client, proto, item_id) -> str:
    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"pedido_item_id": item_id, "nome_exame": "HEMOGRAMA",
                   "conclusao": "normal", "resultado_resumo": "sem alterações"}],
    }, headers=_h(_tok_lab()))
    assert r.status_code in (200, 201), r.text
    lp = r.json()["protocolo"]
    assert client.post(f"/laudos/{lp}/assinar", json={}, headers=_h(_tok_lab())).status_code == 200
    assert client.post(f"/laudos/{lp}/liberar", json={}, headers=_h(_tok_lab())).status_code == 200
    return lp


def _carteira_pedido(client, proto):
    d = client.get("/paciente/pedidos-exame", headers=_h(_tok_pac())).json()
    todos = [*d.get("posse", []), *d.get("em_andamento", []), *d.get("historico", [])]
    return next((x for x in todos if x["protocolo"] == proto), None)


def _carteira_laudo(client, lp):
    d = client.get("/paciente/laudos", headers=_h(_tok_pac())).json()
    todos = [*d.get("disponiveis", []), *d.get("historico", [])]
    return next((x for x in todos if x["protocolo"] == lp), None)


# ---------------------------------------------------------------------------
# S1 + S4 — o elo exame → laudo
# ---------------------------------------------------------------------------

def test_o_cartao_do_exame_ganha_o_elo_quando_o_laudo_e_LIBERADO(
    client, seed_usuario, seed_paciente
):
    """O elo aparece na liberação, não antes.

    Laudo `em_producao` ou `assinado` ainda não é do cidadão — a custódia não
    passou. Anunciá-lo prometeria o que ele não pode abrir.
    """
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    item_id = _ate_resultado(client, proto)

    assert _carteira_pedido(client, proto)["laudo"] is None, (
        "o elo apareceu antes de o laudo existir"
    )

    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"pedido_item_id": item_id, "nome_exame": "HEMOGRAMA",
                   "conclusao": "normal"}],
    }, headers=_h(_tok_lab()))
    lp = r.json()["protocolo"]
    assert _carteira_pedido(client, proto)["laudo"] is None, (
        "laudo em produção não é do cidadão — a custódia não passou"
    )

    client.post(f"/laudos/{lp}/assinar", json={}, headers=_h(_tok_lab()))
    assert _carteira_pedido(client, proto)["laudo"] is None, (
        "assinado ainda não entrega: quem entrega é `liberar`"
    )

    client.post(f"/laudos/{lp}/liberar", json={}, headers=_h(_tok_lab()))
    elo = _carteira_pedido(client, proto)["laudo"]
    assert elo is not None and elo["protocolo"] == lp, (
        "o cartão do exame continua sem levar ao laudo (S1+S4)"
    )


def test_o_laudo_sabe_de_que_pedido_nasceu(client, seed_usuario, seed_paciente):
    """O elo de volta — sem ele o cidadão tem duas listas e nenhuma ponte."""
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    lp = _laudo_liberado(client, proto, _ate_resultado(client, proto))
    assert _carteira_laudo(client, lp)["pedido_protocolo"] == proto


# ---------------------------------------------------------------------------
# R2-lite — o recebimento, que já era fato e não era mostrado
# ---------------------------------------------------------------------------

def test_o_recebimento_aparece_na_liberacao_e_nao_antes(client, seed_usuario, seed_paciente):
    """`liberar` cria a custódia `prestador → paciente`. Antes dela, `None` —
    que significa "ainda não é seu", e não ausência de dado."""
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    item_id = _ate_resultado(client, proto)
    lp = _laudo_liberado(client, proto, item_id)

    laudo = _carteira_laudo(client, lp)
    assert laudo["recebido_em"], "o handoff não chegou à carteira (R2-lite)"
    assert laudo["recebido_em"] != laudo["data_emissao"], (
        "recebimento e data do documento são fatos diferentes e coincidiram"
    )


# ---------------------------------------------------------------------------
# S3 — a ciência do PEDIDO, que não tinha porta
# ---------------------------------------------------------------------------

def test_o_cidadao_encerra_o_proprio_pedido(client, seed_usuario, seed_paciente):
    """O gesto que existia no backend e não existia na tela.

    `resultado_disponivel` → `encerrado` é a ciência formal. Sem ela, todo
    pedido da vitrine parava — atrito infinito, porque o gesto era inalcançável.
    """
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    _ate_resultado(client, proto)

    assert _carteira_pedido(client, proto)["status"] == "resultado_disponivel"
    r = client.post(f"/pedidos-exame/{proto}/encerrar", json={}, headers=_h(_tok_pac()))
    assert r.status_code == 200, r.text
    assert _carteira_pedido(client, proto)["status"] == "encerrado"


def test_a_ciencia_do_PEDIDO_nao_se_deriva_de_abrir_o_LAUDO(
    client, seed_usuario, seed_paciente
):
    """MARTELO DO FABIANO (24/08), executável.

    Ciência do laudo é do laudo (ENG-014: abrir é dar ciência); ciência do
    pedido é do pedido. Fundi-los faria abrir um PDF encerrar um pedido de
    exame — e ninguém desfaz o que declarou sem querer.

    Este teste falha se alguém "simplificar" derivando um do outro.
    """
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    lp = _laudo_liberado(client, proto, _ate_resultado(client, proto))

    assert client.post(f"/laudos/{lp}/abrir", json={}, headers=_h(_tok_pac())).status_code == 200

    laudo = _carteira_laudo(client, lp)
    assert laudo["aberto_em"], "abrir o laudo não registrou a abertura"
    assert _carteira_pedido(client, proto)["status"] == "resultado_disponivel", (
        "abrir o LAUDO encerrou o PEDIDO — dois fatos viraram um (martelo do "
        "Fabiano, 24/08)"
    )

    client.post(f"/pedidos-exame/{proto}/encerrar", json={}, headers=_h(_tok_pac()))
    assert _carteira_pedido(client, proto)["status"] == "encerrado"


def test_encerrar_pedido_nao_tira_o_laudo_da_carteira(client, seed_usuario, seed_paciente):
    """A promessa que a confirmação faz ao cidadão: "o laudo continua na sua
    carteira". Se encerrar o pedido escondesse o laudo, a tela teria mentido no
    momento em que pediu a confirmação."""
    _seed_prestador(client, "org-lab", _CNPJ_LAB)
    tp = obter_token_prescritor(client, seed_usuario)
    proto = _emitir(client, tp)
    lp = _laudo_liberado(client, proto, _ate_resultado(client, proto))
    client.post(f"/pedidos-exame/{proto}/encerrar", json={}, headers=_h(_tok_pac()))
    assert _carteira_laudo(client, lp) is not None, "o laudo sumiu ao encerrar o pedido"
