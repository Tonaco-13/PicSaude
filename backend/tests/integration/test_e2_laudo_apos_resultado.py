"""ENG-019 PR 1 (opção a) — o percurso E2 (leitura imediata) também produz laudo.

CONSULTA-UX-001/NC-5: o caminho mais rápido da casa — coletar e ler na hora —
encerrava SEM laudo. Sem laudo não há artefato clínico, não há selo "Lido em" e
não há âncora de faturamento (martelo ENG-014(b)).

A causa NÃO era o backend. `clinica.html` afirmava, em comentário, que o gatilho
"Produzir laudo" só aparecia para item `em_analise` porque esse seria "o mesmo
critério que o backend exige". `laudos.py` nunca exigiu nada disso: ele exige
`pedido_item_id`, pertencimento ao pedido e POSSE. O portão era da tela, e o
comentário prometia uma restrição inexistente.

Este arquivo prova as duas metades:

  1. O backend SEMPRE aceitou laudo de item em `resultado_disponivel` — logo a
     emenda é de tela, e não afrouxa regra nenhuma de domínio. (Caracterização:
     passa antes e depois; é o que autoriza a mudança no frontend.)

  2. O payload do pedido passa a dizer, POR ITEM, se ele já está coberto por um
     laudo (`laudado`). É o que substitui o efeito colateral de que a tela vivia:
     hoje o botão some porque o item DEIXA `em_analise`. Ao aceitar também
     `resultado_disponivel`, o botão precisa de um motivo próprio para sumir —
     senão reaparece sobre item já laudado e produz um SEGUNDO laudo. O AC (iv)
     do ticket é este.

Nota de precisão sobre o E2: o item não pula a bancada. `POST /itens/{id}/resultado`
COLAPSA `coletado → em_analise → resultado_disponivel` e emite os dois eventos
(`pedido_em_analise` + `resultado_registrado`) — o item passa pela análise sem
REPOUSAR nela. Era o repouso que a tela media.

Requer PostgreSQL (conftest de integração faz skip se DATABASE_URL não for PG).
"""
from __future__ import annotations

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB = "12345678000195"


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _tok_lab(cnpj: str = _LAB) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="LAB")


def _tok_pac() -> str:
    return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)


def _emitir(client, token_presc, nomes) -> str:
    r = client.post("/pedidos-exame", json={
        "cns_prescritor":  SEED_PRESCRITOR_CNS,
        "nome_prescritor": "DR. ENG019",
        "cpf_paciente":    SEED_PACIENTE_CPF,
        "nome_paciente":   SEED_PACIENTE_NOME,
        "tipo_emissao":    "novo",
        "prioridade":      "rotina",
        "itens": [{"nome_exame": n, "quantidade": 1} for n in nomes],
    }, headers=_h(token_presc))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


def _transferir(client, proto, cnpj=_LAB):
    return client.post(
        f"/pedidos-exame/{proto}/transferir-laboratorio",
        json={"cnpj_laboratorio": cnpj, "nome_laboratorio": "LAB"},
        headers=_h(_tok_pac()),
    )


def _pedido(client, proto, token):
    r = client.get(f"/pedidos-exame/{proto}", headers=_h(token))
    assert r.status_code == 200, r.text
    return r.json()


def _percurso_e2(client, token_presc, nomes):
    """Walk-in: transfere ao laboratório, coleta e lê na hora (sem agendar)."""
    proto = _emitir(client, token_presc, nomes)
    assert _transferir(client, proto).status_code == 201
    itens = _pedido(client, proto, _tok_lab())["itens"]
    for it in itens:
        r = client.post(
            f"/pedidos-exame/{proto}/itens/{it['id']}/coletar",
            json={}, headers=_h(_tok_lab()),
        )
        assert r.status_code == 201, r.text
    return proto, [i["id"] for i in itens]


def _registrar_resultado(client, proto, item_id, resumo="Glicemia 92 mg/dL"):
    return client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json={"resultado_resumo": resumo}, headers=_h(_tok_lab()),
    )


def _criar_laudo(client, proto, itens):
    return client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto, "itens": itens,
    }, headers=_h(_tok_lab()))


# ---------------------------------------------------------------------------
# 1. O backend nunca exigiu `em_analise` — o portão era da tela
# ---------------------------------------------------------------------------

def test_backend_aceita_laudo_de_item_em_resultado_disponivel(
    client, seed_usuario, seed_paciente
):
    """Caracterização: derruba a premissa do comentário de `clinica.html`.

    Se este teste passa, a emenda do PR 1 é de TELA — nenhuma regra de domínio
    é afrouxada, porque nunca houve regra aqui.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["GLICEMIA CAPILAR"])

    assert _registrar_resultado(client, proto, ids[0]).status_code == 201
    assert _pedido(client, proto, _tok_lab())["itens"][0]["status_item"] == "resultado_disponivel"

    r = _criar_laudo(client, proto, [
        {"nome_exame": "GLICEMIA CAPILAR", "pedido_item_id": ids[0], "conclusao": "normal"},
    ])
    assert r.status_code == 201, (
        "O backend recusou laudo de item em `resultado_disponivel` — se isto falhar, "
        "a premissa do PR 1 caiu e a emenda vira `core`."
    )


def test_e2_passa_pela_analise_sem_repousar_nela(client, seed_usuario, seed_paciente):
    """O item não PULA a bancada: o `/resultado` colapsa e emite os dois eventos.

    Guarda a precisão que corrige a NC-5 — o defeito era a tela medir repouso,
    não o ledger perder a análise.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["GLICEMIA CAPILAR"])
    assert _registrar_resultado(client, proto, ids[0]).status_code == 201

    tipos = [e["tipo_evento"] for e in _pedido(client, proto, _tok_lab())["eventos"]]
    assert "pedido_em_analise" in tipos, tipos
    assert "resultado_registrado" in tipos, tipos
    assert tipos.index("pedido_em_analise") < tipos.index("resultado_registrado")


# ---------------------------------------------------------------------------
# 2. O payload diz, por item, se já há laudo cobrindo — AC (iv)
# ---------------------------------------------------------------------------

def test_item_sem_laudo_vem_com_laudado_falso(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    proto, _ = _percurso_e2(client, tp, ["HEMOGRAMA"])
    item = _pedido(client, proto, _tok_lab())["itens"][0]
    assert item["laudado"] is False


def test_item_coberto_por_laudo_vem_com_laudado_verdadeiro(
    client, seed_usuario, seed_paciente
):
    """Sem este campo, o botão reapareceria sobre item já laudado.

    A tela não pode inferir isso de `laudo_protocolo`: aquele campo só reporta
    laudo VIGENTE (não-terminal). Quando o laudo chega a `encerrado` — as duas
    ciências — ele volta a NULL, e o item pode ainda estar `resultado_disponivel`
    porque a ciência do PEDIDO é outro gesto. É exatamente a janela em que um
    segundo laudo nasceria.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    proto, ids = _percurso_e2(client, tp, ["HEMOGRAMA", "TSH"])
    assert _registrar_resultado(client, proto, ids[0], "Hb 14,1").status_code == 201

    assert _criar_laudo(client, proto, [
        {"nome_exame": "HEMOGRAMA", "pedido_item_id": ids[0], "conclusao": "normal"},
    ]).status_code == 201

    por_id = {i["id"]: i for i in _pedido(client, proto, _tok_lab())["itens"]}
    assert por_id[ids[0]]["laudado"] is True,  "item laudado deve se declarar laudado"
    assert por_id[ids[1]]["laudado"] is False, "o irmão não laudado segue laudável"
