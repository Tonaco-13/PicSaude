"""Abrir o laudo é dar ciência — ENG-014, PR C (frente 2 do desenho).

MARTELO (a), Fabiano 20/08
--------------------------
    "Abrir o laudo = dar ciência" — o evento nomeia a ABERTURA (fato real);
    a ciência é consequência DERIVADA, declarada como regra.

O ledger fica honesto: *abriu em X → ciência derivada da abertura*. Nunca uma
"ciência" anunciando fato que não ocorreu — a lição do `pedido_agendado`
fantasma que o J.7 matou.

MARTELO (b): faturamento ancorado na LIBERAÇÃO
----------------------------------------------
O fato financeiro é da unidade; a leitura é comportamento do cidadão.
`aberto_em` é coluna informativa — **nunca gatilho**. Há regressão explícita
para isso (AC v): laudo aberto e laudo não-aberto faturam igual.

MÁQUINA DE ESTADOS: MUDANÇA NENHUMA
------------------------------------
`liberado → ciencia_paciente` já é aresta válida e o endpoint de ciência já
compõe as duas ciências. Isto é um CAMINHO NOVO para uma transição existente —
mesmo formato do martelo do J.7.

ACs cobertos: (ii), (iii), (iv), (v), (vi-parcial: estranho não abre).

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import csv
import io as _io

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_LAB = "12345678000195"
_CPF_OUTRO = "99988877766"


def _h(t): return {"Authorization": f"Bearer {t}"}
def _tok_pac(cpf=SEED_PACIENTE_CPF): return criar_access_token(sub=cpf, role="paciente", nome="PAC")
def _tok_lab(c=_LAB): return criar_access_token(sub=c, role="dispensador", nome="LAB")


def _laudo_liberado(client, tp) -> str:
    """Pedido → entrega → coleta → resultado → laudo assinado e liberado."""
    r = client.post("/pedidos-exame", json={
        "cns_prescritor": SEED_PRESCRITOR_CNS, "nome_prescritor": "DR",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "tipo_emissao": "novo", "prioridade": "rotina", "enviar_ao_paciente": True,
        "itens": [{"nome_exame": "GLICEMIA", "quantidade": 1}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    assert client.post(f"/pedidos-exame/{proto}/transferir-laboratorio",
                       json={"cnpj_laboratorio": _LAB, "nome_laboratorio": "LAB"},
                       headers=_h(_tok_pac())).status_code == 201

    hl = _h(_tok_lab())
    item_id = client.get(f"/pedidos-exame/{proto}", headers=hl).json()["itens"][0]["id"]
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar",
                       json={}, headers=hl).status_code == 201
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
                       json={"resultado_resumo": "98 mg/dL"}, headers=hl).status_code in (200, 201)

    rl = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": "GLICEMIA", "conclusao": "normal"}],
    }, headers=hl)
    assert rl.status_code == 201, rl.text
    lp = rl.json()["protocolo"]
    assert client.post(f"/laudos/{lp}/assinar", headers=hl).status_code == 200
    assert client.post(f"/laudos/{lp}/liberar", json={}, headers=hl).status_code == 200
    return lp


def _eventos(client, lp, tp) -> list[str]:
    r = client.get(f"/laudos/{lp}", headers=_h(tp))
    assert r.status_code == 200, r.text
    return [e["tipo_evento"] for e in r.json().get("eventos", [])]


def _abrir(client, lp, cpf=SEED_PACIENTE_CPF):
    return client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_pac(cpf)))


# ---------------------------------------------------------------------------
# AC (ii) — abrir laudo liberado → evento + ciência derivada
# ---------------------------------------------------------------------------

def test_abrir_liberado_deriva_ciencia(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    r = _abrir(client, lp)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["primeira_abertura"] is True
    assert corpo["ciencia_derivada"] is True
    assert corpo["status"] == "ciencia_paciente"
    assert corpo["aberto_em"]

    evs = _eventos(client, lp, tp)
    assert "laudo_aberto_paciente" in evs, "o evento tem de NOMEAR a abertura"
    assert "ciencia_paciente" in evs, "a ciência é derivada, mas é registrada"
    # A ordem é a dos fatos: abriu, e daí derivou.
    assert evs.index("laudo_aberto_paciente") < evs.index("ciencia_paciente")


def test_ledger_diz_de_onde_veio_a_ciencia(client, seed_usuario, seed_paciente):
    """A ciência derivada carrega `origem: abertura`.

    Sem isso, o ledger teria uma ciência indistinguível de um clique
    deliberado — e a auditoria não saberia que o fato foi a LEITURA.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)
    _abrir(client, lp)

    r = client.get(f"/laudos/{lp}", headers=_h(tp))
    ev = next(e for e in r.json()["eventos"] if e["tipo_evento"] == "ciencia_paciente")
    import json as _json
    dados = ev["dados_json"]
    dados = _json.loads(dados) if isinstance(dados, str) else dados
    assert dados.get("origem") == "abertura"


# ---------------------------------------------------------------------------
# AC (iii) — composição com a ciência do prescritor
# ---------------------------------------------------------------------------

def test_abrir_com_ciencia_do_prescritor_encerra(client, seed_usuario, seed_paciente):
    """As duas ciências fecham o laudo — composição, não duplicação."""
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    assert client.post(f"/laudos/{lp}/ciencia-prescritor",
                       headers=_h(tp)).status_code == 200

    r = _abrir(client, lp)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "encerrado"
    assert r.json()["ciencia_derivada"] is True
    assert "laudo_encerrado" in _eventos(client, lp, tp)


# ---------------------------------------------------------------------------
# AC (iv) — idempotência
# ---------------------------------------------------------------------------

def test_segunda_abertura_nao_emite_nada(client, seed_usuario, seed_paciente):
    """Um fato, um evento (R2). A tela pode chamar sem medo."""
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    r1 = _abrir(client, lp)
    assert r1.json()["primeira_abertura"] is True
    evs1 = _eventos(client, lp, tp)

    r2 = _abrir(client, lp)
    assert r2.status_code == 200
    assert r2.json()["primeira_abertura"] is False
    assert r2.json()["ciencia_derivada"] is False
    assert r2.json()["aberto_em"] == r1.json()["aberto_em"], "o carimbo é o da PRIMEIRA"

    assert _eventos(client, lp, tp) == evs1, "a reabertura escreveu no ledger"


def test_abrir_ja_com_ciencia_so_registra_a_leitura(client, seed_usuario, seed_paciente):
    """Quem já deu ciência não a dá de novo — só o fato da leitura entra."""
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)
    assert client.post(f"/laudos/{lp}/ciencia-paciente",
                       headers=_h(_tok_pac())).status_code == 200

    r = _abrir(client, lp)
    assert r.status_code == 200
    assert r.json()["ciencia_derivada"] is False
    assert r.json()["status"] == "ciencia_paciente"
    assert _eventos(client, lp, tp).count("ciencia_paciente") == 1


# ---------------------------------------------------------------------------
# AC (v) — o faturamento NÃO muda (martelo (b))
# ---------------------------------------------------------------------------

def test_abertura_nao_move_faturamento(client, seed_usuario, seed_paciente):
    """Regressão do martelo (b): a leitura é do cidadão, o dinheiro é da unidade.

    Faturar pela leitura seria condicionar o movimento ao comportamento de
    quem não é parte do fato financeiro — vetado no §10 do desenho.
    """
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    def _fat():
        r = client.get("/clinicas/faturamento.csv", headers=_h(_tok_lab()))
        assert r.status_code == 200, r.text
        return list(csv.DictReader(_io.StringIO(r.text)))

    antes = _fat()
    assert len(antes) > 0, "sanidade: a unidade fatura o item com resultado"

    _abrir(client, lp)
    assert _fat() == antes, "a abertura mexeu no faturamento"


# ---------------------------------------------------------------------------
# AC (vi, parcial) — estranho não abre laudo alheio
# ---------------------------------------------------------------------------

def test_outro_paciente_nao_abre(client, seed_usuario, seed_paciente):
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    r = _abrir(client, lp, cpf=_CPF_OUTRO)
    assert r.status_code == 403, r.text


def test_papel_errado_nao_abre(client, seed_usuario, seed_paciente):
    """Abrir é do cidadão. Prescritor tem `ciencia-prescritor`; a unidade, nada."""
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)
    assert client.post(f"/laudos/{lp}/abrir", headers=_h(tp)).status_code == 403
    assert client.post(f"/laudos/{lp}/abrir", headers=_h(_tok_lab())).status_code == 403


def test_laudo_nao_liberado_nao_abre(client, seed_usuario, seed_paciente):
    """`em_producao`/`assinado` → 422: não há o que abrir."""
    tp = obter_token_prescritor(client, seed_usuario)
    r = client.post("/laudos", json={
        "cns_autor": SEED_PRESCRITOR_CNS, "nome_autor": "DRA RT",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "itens": [{"nome_exame": "GLICEMIA"}],
    }, headers=_h(tp))
    assert r.status_code == 201, r.text
    lp = r.json()["protocolo"]

    rr = _abrir(client, lp)
    assert rr.status_code == 422, rr.text


# ---------------------------------------------------------------------------
# O selo "Lido em" chega ao Histórico da unidade (§5)
# ---------------------------------------------------------------------------

def test_historico_da_unidade_ve_a_leitura(client, seed_usuario, seed_paciente):
    """A confirmação rastreada vive na LEITURA — não há push antes do G4A."""
    tp = obter_token_prescritor(client, seed_usuario)
    lp = _laudo_liberado(client, tp)

    def _laudo_no_historico():
        r = client.get("/clinicas/historico", headers=_h(_tok_lab()))
        assert r.status_code == 200, r.text
        return next(l for l in r.json()["laudos"] if l["protocolo"] == lp)

    assert _laudo_no_historico()["aberto_em"] is None, "não lido ainda"
    _abrir(client, lp)
    assert _laudo_no_historico()["aberto_em"] is not None, "a unidade não viu a leitura"
