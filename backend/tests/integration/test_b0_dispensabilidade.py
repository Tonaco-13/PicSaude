"""TICKET-B0 — dispensabilidade derivada do saldo efetivo (PostgreSQL).

Opção A (martelo Fabiano): o rótulo `status_item='dispensado'` permanece como
registro histórico; a dispensabilidade deriva do SALDO EFETIVO (Σ dispensado −
Σ estornado). Estorno total reabre a custódia e re-habilita o item.

Cobre §6.1–6.6:
  §6.1 dispensar total → estornar total → re-dispensar É ACEITO (não mais 409)
  §6.2 pós-estorno total: fila reaparece, item acionavel=true, 1 custodia_transferida
  §6.3 estorno parcial: saldo repõe, acionavel, NENHUMA custódia nova
  §6.4 cancelado/devolvido_prescritor/encerrado_fisico nunca acionavel (qualquer saldo)
  §6.5 status_item='dispensado' nunca é apagado (registro histórico intacto)
  §6.6 guard-rail de unicidade (R2) não acusa duplicidade no ciclo

Palavra-chave "b0"/"acionavel" no nome casa o filtro -k do gate.
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

import pytest

from app.auth.jwt import criar_access_token

_CNPJ = "12345678000195"


def _h(cnpj: str = _CNPJ) -> dict:
    return {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='Farmácia B0')}"}


def _seed(outer_conn, quantidade=10, status_item="em_custodia", cnpj=_CNPJ):
    """Semeia prescrição+item+custódia ativa do dispensador (savepoint)."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-B0-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s,'DR B0',true,%s,%s) RETURNING id", ("9" + uuid.uuid4().hex[:14], now, now))
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s,'PAC B0',true,%s,%s) RETURNING id", ("9" + uuid.uuid4().hex[:10], now, now))
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s,%s,%s,'em_custodia','nova',%s,%s,%s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now))
        presc_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "posologia, status_item, created_at, updated_at) "
            "VALUES (%s,'LOSARTANA','50mg',%s,'1x',%s,%s,%s) RETURNING id",
            (presc_id, quantidade, status_item, now, now))
        item_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
            "transferida_em, encerrada_em, motivo, created_at) "
            "VALUES (%s,%s,'dispensador',%s,%s,NULL,'seed-b0',%s)",
            (presc_id, item_id, cnpj, now, now))
    return {"proto": proto, "presc_id": presc_id, "item_id": item_id}


def _dispensar(client, proto, item_id, qtd):
    return client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar",
                       json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": qtd}, headers=_h())


def _estornar(client, disp_id, qtd=None):
    body = {"motivo": "outro"}
    if qtd is not None:
        body["quantidade"] = qtd
    return client.post(f"/dispensacoes/{disp_id}/estornar", json=body, headers=_h())


def _item_na_fila(client, proto, item_id):
    r = client.get("/dispensadores/fila", headers=_h())
    assert r.status_code == 200, r.text
    for p in r.json()["fila"]:
        if p["protocolo"] == proto:
            for it in p["itens"]:
                if it["item_id"] == item_id:
                    return it
    return None


def _conta_custodia_transferida(outer_conn, presc_id):
    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM prescricao_eventos "
                    "WHERE prescricao_id = %s AND tipo_evento = 'custodia_transferida'", (presc_id,))
        return cur.fetchone()[0]


# ---------------------------------------------------------------------------

def test_b0_redispensa_apos_estorno_total_aceita(client, outer_conn):
    """§6.1 — dispensar total → estornar total → re-dispensar o mesmo item."""
    s = _seed(outer_conn, quantidade=10)
    r1 = _dispensar(client, s["proto"], s["item_id"], 10)
    assert r1.status_code == 201, r1.text
    disp_id = r1.json()["dispensacao_id"]

    re = _estornar(client, disp_id)          # estorno total (remanescente)
    assert re.status_code == 201, re.text
    assert re.json()["custodia_reaberta"] is True
    assert re.json()["saldo_restante"] == 10

    # antes do B0 isto era 409 "status dispensado"; agora com saldo>0 é aceito.
    r2 = _dispensar(client, s["proto"], s["item_id"], 10)
    assert r2.status_code == 201, r2.text


def test_b0_fila_reaparece_acionavel_e_um_evento(client, outer_conn):
    """§6.2 — pós-estorno total: fila reaparece, acionavel=true, 1 custodia_transferida."""
    s = _seed(outer_conn, quantidade=10)
    assert _conta_custodia_transferida(outer_conn, s["presc_id"]) == 0

    disp_id = _dispensar(client, s["proto"], s["item_id"], 10).json()["dispensacao_id"]
    # dispensação total fechou a custódia → item some da fila.
    assert _item_na_fila(client, s["proto"], s["item_id"]) is None

    assert _estornar(client, disp_id).status_code == 201

    it = _item_na_fila(client, s["proto"], s["item_id"])
    assert it is not None, "prescrição deve reaparecer na fila após o estorno"
    assert it["saldo"] == 10
    assert it["acionavel"] is True
    assert it["status_item"] == "dispensado"       # rótulo histórico intacto
    # exatamente UM custodia_transferida novo (a reabertura), sem duplicar.
    assert _conta_custodia_transferida(outer_conn, s["presc_id"]) == 1


def test_b0_estorno_parcial_nao_reabre_custodia(client, outer_conn):
    """§6.3 — estorno parcial: saldo repõe, acionavel, NENHUMA custódia nova."""
    s = _seed(outer_conn, quantidade=10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 6).json()["dispensacao_id"]  # parcial → custódia segue aberta

    re = _estornar(client, disp_id, qtd=3)         # estorno parcial
    assert re.status_code == 201, re.text
    assert re.json()["custodia_reaberta"] is False

    it = _item_na_fila(client, s["proto"], s["item_id"])
    assert it is not None
    assert it["saldo"] == 7                          # 10 − (6 − 3)
    assert it["acionavel"] is True
    # nenhum custodia_transferida (não havia custódia a reabrir).
    assert _conta_custodia_transferida(outer_conn, s["presc_id"]) == 0


@pytest.mark.parametrize("status_terminal", ["cancelado", "devolvido_prescritor", "encerrado_fisico"])
def test_b0_status_hard_nunca_acionavel(client, outer_conn, status_terminal):
    """§6.4 — terminais hard nunca viram acionavel, mesmo com saldo>0."""
    s = _seed(outer_conn, quantidade=10, status_item=status_terminal)  # saldo 10, sem dispensação

    it = _item_na_fila(client, s["proto"], s["item_id"])
    assert it is not None
    assert it["saldo"] == 10
    assert it["acionavel"] is False, f"{status_terminal} não pode ser acionavel"

    # e o guard de dispensação também bloqueia (409), com qualquer saldo.
    r = _dispensar(client, s["proto"], s["item_id"], 1)
    assert r.status_code == 409, r.text


def test_b0_rotulo_dispensado_nunca_apagado(client, outer_conn):
    """§6.5 — status_item='dispensado' e a dispensação original permanecem."""
    s = _seed(outer_conn, quantidade=10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10).json()["dispensacao_id"]
    assert _estornar(client, disp_id).status_code == 201

    with outer_conn.cursor() as cur:
        cur.execute("SELECT status_item FROM prescricao_itens WHERE id = %s", (s["item_id"],))
        assert cur.fetchone()[0] == "dispensado"     # rótulo não apagado
        cur.execute("SELECT COUNT(*) FROM dispensacoes WHERE id = %s", (disp_id,))
        assert cur.fetchone()[0] == 1                # dispensação original imutável


def test_b0_guardrail_unicidade_no_ciclo(client, outer_conn):
    """§6.6 — dispensar→estornar→dispensar não gera identificador duplicado no relatório."""
    s = _seed(outer_conn, quantidade=10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10).json()["dispensacao_id"]
    assert _estornar(client, disp_id).status_code == 201
    assert _dispensar(client, s["proto"], s["item_id"], 10).status_code == 201

    resp = client.get("/dispensadores/relatorio.csv", headers=_h())
    assert resp.status_code == 200
    linhas = [x for x in csv.DictReader(io.StringIO(resp.text)) if x["protocolo_prescricao"] == s["proto"]]
    disp_ids = [x["dispensacao_id"] for x in linhas if x["tipo_movimento"] == "dispensacao"]
    est_protos = [x["estorno_protocolo"] for x in linhas if x["tipo_movimento"] == "estorno"]
    assert len(disp_ids) == len(set(disp_ids)), f"dispensacao_id duplicado: {disp_ids}"
    assert len(est_protos) == len(set(est_protos)), f"estorno_protocolo duplicado: {est_protos}"
    # 2 dispensações (antes e depois do estorno) + 1 estorno para este item.
    assert len(disp_ids) == 2 and len(est_protos) == 1, (disp_ids, est_protos)
