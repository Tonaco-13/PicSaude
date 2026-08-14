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


# ---------------------------------------------------------------------------
# TICKET-D — agregação por SIGTAP (SUS) além de TUSS (planos)
# ---------------------------------------------------------------------------
# Duas fontes pagadoras, um caminho de agregação. Segue contabilidade interna
# read-only: nada é transmitido a operadora ou ao SUS (guia TISS/APAC é adapter,
# depende de G4A). O que muda é POR QUAL TABELA se conta.

def _carimbar_sigtap(outer_conn, proto: str, codigo: str | None) -> None:
    """`codigo_sigtap` não entra pelo payload de emissão (nem o TUSS entra) —
    mesmo recurso do `_concluir_exame`: UPDATE direto no item."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            UPDATE pedido_exame_itens SET codigo_sigtap = %s
             WHERE pedido_id = (SELECT id FROM pedidos_exame WHERE protocolo = %s)
            """,
            (codigo, proto),
        )


def test_agrupar_por_tuss_e_o_default_sem_regressao(client, outer_conn, seed_usuario, seed_paciente):
    """AC1 — omitir o parâmetro e pedir `tuss` explicitamente têm que produzir o
    MESMO CSV. Se divergirem, o default deixou de ser o comportamento antigo."""
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    h = _headers(_token(_CNPJ_A, "dispensador"))

    sem_param = client.get("/clinicas/faturamento.csv", headers=h)
    com_tuss = client.get("/clinicas/faturamento.csv?agrupar_por=tuss", headers=h)
    assert sem_param.status_code == 200 and com_tuss.status_code == 200
    assert sem_param.text == com_tuss.text


def test_agrupar_por_sigtap_agrega_pela_tabela_do_sus(client, outer_conn, seed_usuario, seed_paciente):
    """AC2 — o mesmo exame conta por outro código quando o pagador é o SUS."""
    token_p = obter_token_prescritor(client, seed_usuario)
    for _ in range(2):
        proto = _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
        _carimbar_sigtap(outer_conn, proto, "0202020380")
    proto_g = _concluir_exame(client, token_p, _CNPJ_A, "GLICEMIA", "40302016", outer_conn)
    _carimbar_sigtap(outer_conn, proto_g, "0202010473")

    h = _headers(_token(_CNPJ_A, "dispensador"))
    r = client.get("/clinicas/faturamento.csv?agrupar_por=sigtap", headers=h)
    assert r.status_code == 200, r.text

    # O cabeçalho nomeia a tabela: quem abre o arquivo não precisa lembrar da URL.
    assert next(csv.reader(io.StringIO(r.text))) == [
        "codigo_sigtap", "qtd", "primeiro_resultado", "ultimo_resultado",
    ]

    por_sigtap = {row["codigo_sigtap"]: int(row["qtd"]) for row in _csv_rows(r)}
    assert por_sigtap["0202020380"] == 2
    assert por_sigtap["0202010473"] == 1
    # Ordem estável (qtd desc) — mesmo requisito de reprodutibilidade do TUSS.
    assert _csv_rows(r)[0]["codigo_sigtap"] == "0202020380"


def test_mesmo_exame_conta_nos_dois_criterios(client, outer_conn, seed_usuario, seed_paciente):
    """O total não muda com o critério — muda só o rótulo sob o qual ele aparece.
    É o que prova que SIGTAP é caminho paralelo, não filtro."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    _carimbar_sigtap(outer_conn, proto, "0202020380")
    h = _headers(_token(_CNPJ_A, "dispensador"))

    tuss = _csv_rows(client.get("/clinicas/faturamento.csv?agrupar_por=tuss", headers=h))
    sig = _csv_rows(client.get("/clinicas/faturamento.csv?agrupar_por=sigtap", headers=h))

    assert sum(int(r["qtd"]) for r in tuss) == sum(int(r["qtd"]) for r in sig)
    assert {r["codigo_tuss"] for r in tuss} == {"40304361"}
    assert {r["codigo_sigtap"] for r in sig} == {"0202020380"}


def test_item_sem_sigtap_vira_nao_classificado(client, outer_conn, seed_usuario, seed_paciente):
    """Exame com TUSS mas sem SIGTAP não pode SUMIR da conta do SUS — cai em
    `(não classificado)`, exatamente como o inverso já fazia."""
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)  # sem sigtap

    rows = _csv_rows(client.get("/clinicas/faturamento.csv?agrupar_por=sigtap",
                                headers=_headers(_token(_CNPJ_A, "dispensador"))))
    assert any(r["codigo_sigtap"] == "(não classificado)" and int(r["qtd"]) >= 1 for r in rows), rows


def test_agrupar_por_invalido_422_nomeado(client, outer_conn, seed_usuario, seed_paciente):
    """AC4 — valor fora da whitelist morre em 422 ANTES de chegar ao banco.
    É a whitelist que torna seguro interpolar o nome da coluna no SQL."""
    h = _headers(_token(_CNPJ_A, "dispensador"))
    for valor in ("invalido", "codigo_tuss", "tuss; DROP TABLE pedidos_exame"):
        r = client.get(f"/clinicas/faturamento.csv?agrupar_por={valor}", headers=h)
        assert r.status_code == 422, (valor, r.text)
        assert r.json()["detail"]["codigo"] == "agrupar_por_invalido"

    rp = client.get("/clinicas/faturamento.pdf?agrupar_por=invalido", headers=h)
    assert rp.status_code == 422, rp.text


def test_sigtap_respeita_periodo_e_escopo_por_cnpj(client, outer_conn, seed_usuario, seed_paciente):
    """AC — os guardrails do TUSS valem igual no SIGTAP: janela e escopo do JWT.
    Um critério novo não pode ser porta lateral para ver dado de outra unidade."""
    token_p = obter_token_prescritor(client, seed_usuario)
    proto_a = _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    _carimbar_sigtap(outer_conn, proto_a, "0202020380")
    proto_b = _concluir_exame(client, token_p, _CNPJ_B, "GLICEMIA", "40302016", outer_conn)
    _carimbar_sigtap(outer_conn, proto_b, "0202010473")

    h_a = _headers(_token(_CNPJ_A, "dispensador"))

    # Janela antiga não contém o exame de hoje.
    assert _csv_rows(client.get(
        "/clinicas/faturamento.csv?agrupar_por=sigtap"
        "&data_inicio=2020-01-01&data_fim=2020-01-31", headers=h_a)) == []

    # Escopo: A não vê o SIGTAP da unidade B.
    codigos_a = {r["codigo_sigtap"] for r in _csv_rows(
        client.get("/clinicas/faturamento.csv?agrupar_por=sigtap", headers=h_a))}
    assert "0202020380" in codigos_a
    assert "0202010473" not in codigos_a


def test_pdf_sigtap_servivel_e_rotulado(client, outer_conn, seed_usuario, seed_paciente):
    """AC3 — o PDF diz por qual tabela contou. Um relatório de faturamento que
    não distingue TUSS de SIGTAP convida ao erro: são pagadores diferentes."""
    from app.domain.pdf_relatorio_exames import _ROTULOS_CRITERIO

    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    _carimbar_sigtap(outer_conn, proto, "0202020380")
    h = _headers(_token(_CNPJ_A, "dispensador"))

    for criterio in ("tuss", "sigtap"):
        r = client.get(f"/clinicas/faturamento.pdf?agrupar_por={criterio}", headers=h)
        assert r.status_code == 200, (criterio, r.text)
        assert r.content[:4] == b"%PDF"

    # Os rótulos são distintos — sem isso os dois PDFs seriam indistinguíveis.
    assert _ROTULOS_CRITERIO["tuss"] != _ROTULOS_CRITERIO["sigtap"]
    assert "SIGTAP" in _ROTULOS_CRITERIO["sigtap"][1]


def test_sigtap_continua_read_only(client, outer_conn, seed_usuario, seed_paciente):
    """O critério novo não pode ter aberto caminho de escrita."""
    token_p = obter_token_prescritor(client, seed_usuario)
    _concluir_exame(client, token_p, _CNPJ_A, "HEMOGRAMA", "40304361", outer_conn)
    h = _headers(_token(_CNPJ_A, "dispensador"))

    antes = _contagens(outer_conn)
    assert client.get("/clinicas/faturamento.csv?agrupar_por=sigtap", headers=h).status_code == 200
    assert client.get("/clinicas/faturamento.pdf?agrupar_por=sigtap", headers=h).status_code == 200
    assert _contagens(outer_conn) == antes
