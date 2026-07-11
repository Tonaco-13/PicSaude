"""
tests/integration/test_relatorio_sngpc.py — TICKET-F5, Fatia A (PostgreSQL real).

Caminho 2xx contra PG (critério §5.6): valida os tipos datetime (PG devolve
`datetime`, SQLite string ISO) na escrituração SNGPC do dispensador. Reusa o
harness de savepoint por request (conftest desta pasta), semeando via outer_conn
e exercitando os endpoints reais de dispensação/estorno.

Cobre em PG:
  §5.1 isolamento por CNPJ · §5.2 dispensação+estorno = 2 linhas + saldo reposto
  §5.6 datetime PG · §5.9 período fechado estável (estorno pós-data_fim) · read-only
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
)

_CNPJ_A = "12345678000195"
_CNPJ_B = "99999999000272"


def _h(cnpj: str) -> dict:
    return {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='Farmácia')}"}


def _seed(outer_conn, cnpj: str = _CNPJ_A, quantidade: int = 10):
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-SNGPC-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "posologia, status_item, created_at, updated_at) "
            "VALUES (%s, 'LOSARTANA', '50mg', %s, '1cp/dia', 'em_custodia', %s, %s) RETURNING id",
            (prescricao_id, quantidade, now, now),
        )
        item_id = cur.fetchone()[0]
        for iid in (None, item_id):
            cur.execute(
                "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
                "transferida_em, encerrada_em, motivo, created_at) "
                "VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed', %s)",
                (prescricao_id, iid, cnpj, now, now),
            )
    return prescricao_id, proto, item_id


def _dispensar(client, proto, item_id, cnpj, qtd, comprador=None):
    payload = {"cnpj_estabelecimento": cnpj, "quantidade_dispensada": qtd}
    if comprador:
        payload["comprador_nome"] = comprador
    r = client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar", json=payload, headers=_h(cnpj))
    assert r.status_code == 201, r.text
    return r.json()["dispensacao_id"]


def _csv(client, cnpj, **params):
    r = client.get("/dispensadores/relatorio.csv", params=params, headers=_h(cnpj))
    assert r.status_code == 200, r.text
    assert "text/csv" in r.headers["content-type"]
    return list(csv.DictReader(io.StringIO(r.text)))


# ---------------------------------------------------------------------------

def test_csv_2xx_datetime_pg(client, outer_conn):
    """§5.6 — caminho 2xx contra PG; data_movimento normalizada de datetime."""
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    _dispensar(client, proto, item_id, _CNPJ_A, 3, comprador="MARIA PORTADORA")

    linha = next(r for r in _csv(client, _CNPJ_A) if r["protocolo_prescricao"] == proto)
    assert linha["tipo_movimento"] == "dispensacao"
    assert linha["quantidade"] == "3"
    assert linha["saldo_escriturado_item"] == "3"
    assert linha["comprador_nome"] == "MARIA PORTADORA"
    assert linha["comprador_eh_paciente"] == "nao"
    # datetime PG normalizada para ISO — parseável e não vazia.
    assert datetime.fromisoformat(linha["data_movimento"])


def test_csv_isolado_por_cnpj_pg(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    _dispensar(client, proto, item_id, _CNPJ_A, 2)
    protos_b = {r["protocolo_prescricao"] for r in _csv(client, _CNPJ_B)}
    assert proto not in protos_b


def test_csv_dispensacao_estorno_saldo_pg(client, outer_conn):
    """§5.2 — dispensação + estorno = 2 linhas; saldo reposto a 0."""
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    disp_id = _dispensar(client, proto, item_id, _CNPJ_A, 3)
    r = client.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"}, headers=_h(_CNPJ_A))
    assert r.status_code == 201, r.text

    linhas = [x for x in _csv(client, _CNPJ_A) if x["protocolo_prescricao"] == proto]
    por_tipo = {x["tipo_movimento"]: x for x in linhas}
    assert set(por_tipo) == {"dispensacao", "estorno"}
    assert por_tipo["dispensacao"]["saldo_escriturado_item"] == "3"
    assert por_tipo["estorno"]["saldo_escriturado_item"] == "0"
    assert por_tipo["estorno"]["motivo_estorno"] == "outro"


def test_csv_read_only_pg(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    _dispensar(client, proto, item_id, _CNPJ_A, 3)

    def _contagens():
        with outer_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dispensacoes")
            d = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM estornos")
            e = cur.fetchone()[0]
        return d, e

    antes = _contagens()
    _csv(client, _CNPJ_A)
    assert client.get("/dispensadores/relatorio.pdf", headers=_h(_CNPJ_A)).status_code == 200
    assert _contagens() == antes


def test_periodo_fechado_estavel_pg(client, outer_conn):
    """§5.9 — estorno registrado DEPOIS do data_fim não altera a linha do período.

    Backdata a dispensação para 2020 (fixture de teste), gera o relatório de uma
    janela fechada em 2020, depois estorna (criado_em ~ hoje) e regenera a MESMA
    janela: o estorno de hoje fica fora do corte e a linha de 2020 permanece 3.
    """
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    disp_id = _dispensar(client, proto, item_id, _CNPJ_A, 3)

    # Backdata a dispensação para dentro da janela fechada de 2020.
    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE dispensacoes SET dispensado_em = %s WHERE id = %s",
            (datetime(2020, 1, 15, 10, 0, 0), disp_id),
        )

    janela = {"data_inicio": "2019-12-01", "data_fim": "2020-02-01"}

    antes = [x for x in _csv(client, _CNPJ_A, **janela) if x["protocolo_prescricao"] == proto]
    assert len(antes) == 1
    assert antes[0]["tipo_movimento"] == "dispensacao"
    assert antes[0]["saldo_escriturado_item"] == "3"

    # Estorno HOJE (criado_em ~ 2026) — posterior ao data_fim de 2020.
    r = client.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"}, headers=_h(_CNPJ_A))
    assert r.status_code == 201, r.text

    depois = [x for x in _csv(client, _CNPJ_A, **janela) if x["protocolo_prescricao"] == proto]
    # Período fechado é estável: mesma linha, mesmo saldo; o estorno não aparece.
    assert len(depois) == 1
    assert depois[0]["tipo_movimento"] == "dispensacao"
    assert depois[0]["saldo_escriturado_item"] == "3"
    assert all(x["tipo_movimento"] != "estorno" for x in depois)
