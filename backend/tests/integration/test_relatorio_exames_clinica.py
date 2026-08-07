"""DESPACHO-ENG-008 (R3) — relatório de exames do prestador: escopo e read-only.

O que este arquivo trava
------------------------
1. **Isolamento por CNPJ** (AC5, o critério que faz o endpoint poder existir):
   a clínica A não vê exame da clínica B. Sem `c.para = ?` o relatório viraria
   um vazamento cross-establishment com aparência de feature.
2. **Custódia ATUAL, não histórica**: prestador que perdeu a custódia sai do
   próprio relatório — mesma semântica de `_assert_dispensador_dono_pedido`.
3. **Read-only** (AC7): nenhuma linha nova em `pedidos_exame`,
   `pedido_exame_itens`, `pedido_exame_eventos` ou `pedido_exame_custodia`
   depois de gerar CSV e PDF.
4. Contrato de resposta: cabeçalho CSV (AC3), `Content-Disposition` (AC6),
   período com default de 30 dias (AC2), PDF servível (AC4).
5. Papel: só `dispensador` (AC §3) — prescritor/paciente levam 403.

Requer PostgreSQL (conftest de integração pula sem DATABASE_URL de PG).
"""
from __future__ import annotations

import csv
import io
from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    obter_token_prescritor,
)

_CNPJ_A = "12345678000195"     # clínica A
_CNPJ_B = "98765432000110"     # clínica B
_CNS_PRESCRITOR_B = "999888777666555"

_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": "DR. TESTE TICKET13",
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
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


def _criar_pedido_agendado(client, token_prescritor, cnpj: str, nome_exame: str) -> str:
    """Pedido criado pelo prescritor e agendado no prestador `cnpj`."""
    payload = {**_PAYLOAD_BASE, "itens": [{"nome_exame": nome_exame, "quantidade": 1}]}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token_prescritor))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]
    ra = client.post(
        f"/pedidos-exame/{proto}/agendar",
        json={"cnpj_prestador": cnpj},
        headers=_headers(token_prescritor),
    )
    assert ra.status_code == 201, ra.text
    return proto


def _csv_rows(resp) -> list[dict]:
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


# ---------------------------------------------------------------------------
# AC5 — isolamento por CNPJ
# ---------------------------------------------------------------------------

def test_clinica_a_nao_ve_exame_da_clinica_b(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    proto_a = _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")
    proto_b = _criar_pedido_agendado(client, token_p, _CNPJ_B, "GLICEMIA")

    rows_a = _csv_rows(client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_A, "dispensador"))))
    protos_a = {r["protocolo"] for r in rows_a}
    assert proto_a in protos_a, f"clínica A não vê o próprio exame: {protos_a}"
    assert proto_b not in protos_a, "VAZAMENTO: clínica A enxergou exame da clínica B"

    rows_b = _csv_rows(client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_B, "dispensador"))))
    protos_b = {r["protocolo"] for r in rows_b}
    assert proto_b in protos_b
    assert proto_a not in protos_b, "VAZAMENTO: clínica B enxergou exame da clínica A"

    # E o conteúdo do outro também não aparece por outra coluna.
    assert "GLICEMIA" not in "".join(r["nome_exame"] for r in rows_a)


def test_prestador_sem_exame_recebe_csv_vazio_com_cabecalho(client, seed_usuario, seed_paciente):
    """Quem não custodia nada recebe cabeçalho e zero linhas — não erro, não tudo."""
    token_p = obter_token_prescritor(client, seed_usuario)
    _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")

    r = client.get("/clinicas/relatorio.csv", headers=_headers(_token("11222333000181", "dispensador")))
    assert r.status_code == 200, r.text
    assert r.text.splitlines()[0].startswith('"protocolo"')
    assert _csv_rows(r) == []


def test_relatorio_segue_custodia_atual_nao_historica(client, outer_conn, seed_usuario, seed_paciente):
    """A perde a custódia para B: some do relatório de A, aparece no de B.

    A custódia posterior entra por INSERT direto — mesmo recurso de
    `test_pedidos_exame_autorizacao.py::test_disp_caso5`: o fluxo de endpoints do
    MVP não reexpõe re-transferência de prestador (o `agendar` exige item
    'pendente', e após o 1º agendar o item já está 'agendado').
    """
    token_p = obter_token_prescritor(client, seed_usuario)
    proto = _criar_pedido_agendado(client, token_p, _CNPJ_A, "TSH")

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM pedidos_exame WHERE protocolo = %s", (proto,))
        pedido_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO pedido_exame_custodia
              (pedido_id, item_id, de, para, transferido_em, dados_json)
            VALUES (%s, NULL, %s, %s, %s, %s)
            """,
            (pedido_id, _CNPJ_A, _CNPJ_B, datetime.utcnow(),
             '{"motivo": "re-transferencia de prestador (teste)"}'),
        )

    protos_a = {r["protocolo"] for r in _csv_rows(
        client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_A, "dispensador"))))}
    protos_b = {r["protocolo"] for r in _csv_rows(
        client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_B, "dispensador"))))}

    assert proto not in protos_a, "custódia histórica não pode aparecer no relatório"
    assert proto in protos_b


# ---------------------------------------------------------------------------
# AC7 — read-only
# ---------------------------------------------------------------------------

def test_relatorio_nao_escreve_nada(client, outer_conn, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")

    antes = _contagens(outer_conn)
    assert client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_A, "dispensador"))).status_code == 200
    assert client.get("/clinicas/relatorio.pdf", headers=_headers(_token(_CNPJ_A, "dispensador"))).status_code == 200
    depois = _contagens(outer_conn)

    assert depois == antes, f"relatório escreveu no banco: {antes} → {depois}"


# ---------------------------------------------------------------------------
# AC2/3/4/6 — contrato de resposta
# ---------------------------------------------------------------------------

def test_cabecalho_csv_e_content_disposition(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")

    r = client.get("/clinicas/relatorio.csv", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="relatorio_exames_' in r.headers["content-disposition"]

    leitor = csv.reader(io.StringIO(r.text))
    assert next(leitor) == [
        "protocolo", "item_id", "nome_exame", "codigo_tuss", "status_item",
        "data_coleta", "data_resultado", "data_agendamento", "paciente_nome",
    ]
    # QUOTE_ALL (padrão dispensadores.py)
    assert r.text.splitlines()[0] == (
        '"protocolo","item_id","nome_exame","codigo_tuss","status_item",'
        '"data_coleta","data_resultado","data_agendamento","paciente_nome"'
    )


def test_pdf_servido_e_valido(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")

    r = client.get("/clinicas/relatorio.pdf", headers=_headers(_token(_CNPJ_A, "dispensador")))
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"


def test_periodo_filtra_e_data_invalida_422(client, seed_usuario, seed_paciente):
    token_p = obter_token_prescritor(client, seed_usuario)
    _criar_pedido_agendado(client, token_p, _CNPJ_A, "HEMOGRAMA")
    h = _headers(_token(_CNPJ_A, "dispensador"))

    # Janela antiga não pode conter o exame recém-criado.
    antiga = client.get("/clinicas/relatorio.csv?data_inicio=2020-01-01&data_fim=2020-01-31", headers=h)
    assert _csv_rows(antiga) == []

    # Sem filtro → default de 30 dias, que contém o exame de hoje.
    assert len(_csv_rows(client.get("/clinicas/relatorio.csv", headers=h))) >= 1

    invalida = client.get("/clinicas/relatorio.csv?data_inicio=31-12-2026", headers=h)
    assert invalida.status_code == 422, invalida.text
    assert invalida.json()["detail"]["codigo"] == "data_invalida"


# ---------------------------------------------------------------------------
# §3 — papel
# ---------------------------------------------------------------------------

def test_somente_dispensador_acessa(client, seed_usuario, seed_paciente):
    for sub, role in ((SEED_PRESCRITOR_CNS, "prescritor"), (SEED_PACIENTE_CPF, "paciente")):
        r = client.get("/clinicas/relatorio.csv", headers=_headers(_token(sub, role)))
        assert r.status_code == 403, f"{role} não deveria acessar: {r.status_code} {r.text}"
