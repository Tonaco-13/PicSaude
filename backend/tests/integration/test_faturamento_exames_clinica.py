"""DESPACHO-ENG-009 (R4) — faturamento de exames: projeção read-only do ledger.

Faturamento aqui é **contabilidade interna**: quantos exames de cada procedimento
foram concluídos no período, sob a custódia do próprio prestador. Não é guia
TISS, não publica nada — por isso não depende de G4A.

O que este arquivo trava
------------------------
1. **Invariante do despacho (§3): nenhuma escrita.** Row-count de `pedidos_exame`,
   `pedido_exame_itens`, `pedido_exame_eventos` e `pedido_exame_custodia` idêntico
   antes e depois de CSV **e** PDF. Uma projeção que escreve deixa de ser projeção.
2. **Nenhum estado novo** em `ESTADOS_PEDIDO_EXAME` — o R4 não inventa vocabulário.
3. **Isolamento por CNPJ** (AC3): clínica A não fatura exame da clínica B.
4. **Equivalência com o ledger** — a projeção ancora em
   `pedido_exame_itens.resultado_em`, e não no `dados_json` do evento (que exigiria
   função JSON divergente entre dialetos). Este arquivo prova que as duas contas
   batem: o total faturado é igual ao número de eventos `resultado_registrado` do
   prestador. Se algum dia divergirem, é aqui que aparece.
5. Agregação: por `codigo_tuss`, sem TUSS vira `(não classificado)` (§6), ordem
   estável, período com default de 30 dias.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import csv
import io

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNPJ_A = "12345678000195"
_CNPJ_B = "98765432000110"

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE TICKET13",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
}

_TABELAS_ESCRITA = (
    "pedidos_exame",
    "pedido_exame_itens",
    "pedido_exame_eventos",
    "pedido_exame_custodia",
)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token(sub: str, role: str) -> str:
    return criar_access_token(sub=sub, role=role, nome="ATOR")


def _contagens(outer_conn) -> dict:
    out = {}
    with outer_conn.cursor() as cur:
        for t in _TABELAS_ESCRITA:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _concluir_exame(client, token_prescritor, cnpj: str, nome_exame: str,
                    codigo_tuss: str | None, outer_conn) -> str:
    """Ciclo completo até o resultado: criar → agendar → coletar → resultado.

    O `codigo_tuss` entra por UPDATE direto: o payload de criação do MVP não
    expõe o campo, e o R4 agrega justamente por ele.
    """
    payload = {**_PAYLOAD_BASE, "itens": [{"nome_exame": nome_exame, "quantidade": 1}]}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    item_id = client.get(
        f"/pedidos-exame/{proto}", headers=_headers(token_prescritor)
    ).json()["itens"][0]["id"]

    if codigo_tuss is not None:
        with outer_conn.cursor() as cur:
            cur.execute(
                "UPDATE pedido_exame_itens SET codigo_tuss = %s WHERE id = %s",
                (codigo_tuss, item_id),
            )

    assert client.post(
        f"/pedidos-exame/{proto}/agendar", json={"cnpj_prestador": cnpj},
        headers=_headers(token_prescritor),
    ).status_code == 201

    h_disp = _headers(_token(cnpj, "dispensador"))
    assert client.post(f"/pedidos-exame/{proto}/itens/{item_id}/coletar", headers=h_disp).status_code == 201
    assert client.post(
        f"/pedidos-exame/{proto}/itens/{item_id}/resultado",
        json={"resultado_resumo": f"{nome_exame}: normal"},
        headers=_headers(token_prescritor),
    ).status_code == 201
    return proto


def _csv_rows(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


# ---------------------------------------------------------------------------
# §3 / AC4 — read-only absoluto
# ---------------------------------------------------------------------------

def test_faturamento_nao_escreve_nada(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)

    h = _headers(_token(_CNPJ_A, "dispensador"))
    antes = _contagens(outer_conn)
    assert client.get("/clinicas/faturamento.csv", headers=h).status_code == 200
    assert client.get("/clinicas/faturamento.pdf", headers=h).status_code == 200
    depois = _contagens(outer_conn)

    assert depois == antes, f"faturamento escreveu no banco: {antes} → {depois}"


def test_r4_nao_introduz_estado_novo():
    """AC5 — a projeção não inventa vocabulário de estado."""
    from app.domain.states_exame import ESTADOS_PEDIDO_EXAME

    esperado = {
        "emitido", "agendado", "coletado", "em_analise", "resultado_disponivel",
        "encerrado", "cancelado", "expirado", "encerrado_fisico",
    }
    assert set(ESTADOS_PEDIDO_EXAME) == esperado, (
        "R4 é projeção read-only: se esta lista mudou, a mudança veio de outro "
        f"lugar e precisa de revisão própria. Atual: {sorted(ESTADOS_PEDIDO_EXAME)}"
    )


# ---------------------------------------------------------------------------
# AC3 — isolamento por CNPJ
# ---------------------------------------------------------------------------

def test_clinica_a_nao_fatura_exame_da_clinica_b(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    _concluir_exame(client, token_p, _CNPJ_B, "GLICEMIA", "40302016", outer_conn)

    rows_a = _csv_rows(client.get("/clinicas/faturamento.csv", headers=_headers(_token(_CNPJ_A, "dispensador"))))
    tuss_a = {r["codigo_tuss"] for r in rows_a}
    assert "40304361" in tuss_a
    assert "40302016" not in tuss_a, "VAZAMENTO: A faturou procedimento da clínica B"

    rows_b = _csv_rows(client.get("/clinicas/faturamento.csv", headers=_headers(_token(_CNPJ_B, "dispensador"))))
    tuss_b = {r["codigo_tuss"] for r in rows_b}
    assert "40302016" in tuss_b
    assert "40304361" not in tuss_b, "VAZAMENTO: B faturou procedimento da clínica A"


# ---------------------------------------------------------------------------
# Equivalência com o ledger — a âncora escolhida tem de bater com o evento
# ---------------------------------------------------------------------------

def test_faturamento_equivale_ao_ledger(client, outer_conn, seed_usuario, seed_paciente):
    """A projeção ancora em `resultado_em`; a verdade é o ledger. As contas batem.

    Se alguém mudar o caminho de escrita e deixar o carimbo do item dessincronizado
    do evento `resultado_registrado`, este teste acusa — é o que sustenta a decisão
    de não extrair `item_id` do `dados_json`.
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    protos = [
        _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn),
        _concluir_exame(client, token_p, _CNPJ_A, "GLICEMIA", "40302016", outer_conn),
        _concluir_exame(client, token_p, _CNPJ_A, "TSH", "40316458", outer_conn),
    ]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM pedido_exame_eventos ev
             WHERE ev.tipo_evento = 'resultado_registrado'
               AND ev.pedido_id IN (
                     SELECT id FROM pedidos_exame WHERE protocolo = ANY(%s)
               )
            """,
            (protos,),
        )
        eventos_no_ledger = cur.fetchone()[0]

    rows = _csv_rows(client.get("/clinicas/faturamento.csv",
                                headers=_headers(_token(_CNPJ_A, "dispensador"))))
    total_faturado = sum(int(r["qtd"]) for r in rows)

    assert eventos_no_ledger == 3, f"pré-condição: 3 eventos esperados, vieram {eventos_no_ledger}"
    assert total_faturado == eventos_no_ledger, (
        f"projeção ({total_faturado}) divergiu do ledger ({eventos_no_ledger}) — "
        "o carimbo `resultado_em` saiu de sincronia com `resultado_registrado`"
    )


# ---------------------------------------------------------------------------
# Agregação e contrato
# ---------------------------------------------------------------------------

def test_agrega_por_tuss_e_conta_repeticoes(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    for _ in range(3):
        _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    _concluir_exame(client, token_p, _CNPJ_A, "GLICEMIA", "40302016", outer_conn)

    rows = _csv_rows(client.get("/clinicas/faturamento.csv",
                                headers=_headers(_token(_CNPJ_A, "dispensador"))))
    por_tuss = {r["codigo_tuss"]: int(r["qtd"]) for r in rows}
    assert por_tuss["40304361"] == 3
    assert por_tuss["40302016"] == 1
    # Ordem: maior quantidade primeiro (desempate por código, para ser reproduzível).
    assert rows[0]["codigo_tuss"] == "40304361"
    # Janela do procedimento repetido: primeiro <= último.
    linha = next(r for r in rows if r["codigo_tuss"] == "40304361")
    assert linha["primeiro_resultado"] <= linha["ultimo_resultado"]


def test_item_sem_tuss_vira_nao_classificado(client, outer_conn, seed_usuario, seed_paciente):
    """§6 — `codigo_tuss` é nullable; o exame concluído não pode sumir da conta."""
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "EXAME SEM TUSS", None, outer_conn)

    rows = _csv_rows(client.get("/clinicas/faturamento.csv",
                                headers=_headers(_token(_CNPJ_A, "dispensador"))))
    assert any(r["codigo_tuss"] == "(não classificado)" and int(r["qtd"]) >= 1 for r in rows), rows


def test_contrato_csv_pdf_periodo_e_papel(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    h = _headers(_token(_CNPJ_A, "dispensador"))

    # AC1/§2.3 — cabeçalho exato do despacho.
    r = client.get("/clinicas/faturamento.csv", headers=h)
    assert r.status_code == 200, r.text
    assert next(csv.reader(io.StringIO(r.text))) == [
        "codigo_tuss", "qtd", "primeiro_resultado", "ultimo_resultado",
    ]
    assert 'attachment; filename="faturamento_exames_' in r.headers["content-disposition"]

    # AC2 — janela antiga não contém o exame de hoje; default (30 dias) contém.
    assert _csv_rows(client.get(
        "/clinicas/faturamento.csv?data_inicio=2020-01-01&data_fim=2020-01-31", headers=h)) == []
    assert len(_csv_rows(client.get("/clinicas/faturamento.csv", headers=h))) >= 1

    # PDF servível.
    rp = client.get("/clinicas/faturamento.pdf", headers=h)
    assert rp.status_code == 200
    assert rp.content[:4] == b"%PDF"

    # Papel: só dispensador.
    assert client.get(
        "/clinicas/faturamento.csv",
        headers=_headers(_token(SEED_PRESCRITOR_CNS, "prescritor")),
    ).status_code == 403
