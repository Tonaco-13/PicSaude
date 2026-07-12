"""TICKET-CORE-R2 — idempotência de mutação + guard-rail de unicidade (PostgreSQL).

Dois grupos:

  1. **Concorrência (§6.1)** — duas requisições concorrentes idênticas de
     dispensação do MESMO item, contra o pool real (sem o isolamento por
     savepoint, que compartilha uma conexão e não exerce `FOR UPDATE`). Com o
     lock, uma grava e a outra encontra saldo esgotado → 409; nunca 2 movimentos
     (sem oversell). Idem para estorno concorrente da mesma dispensação.

  2. **Guard-rail de unicidade (§6.2 / §2a R2)** — após dispensar→estornar→
     dispensar, a projeção do relatório do dispensador não tem `dispensacao_id`
     (tipo dispensacao) nem `estorno_protocolo` (tipo estorno) duplicado. É o
     `HAVING COUNT(*) > 1` do ticket materializado sobre o CSV real.

Palavra-chave "idempotencia"/"unicidade" no nome casa o filtro -k do gate.
"""
from __future__ import annotations

import concurrent.futures
import csv
import io
import threading
import uuid
from datetime import datetime

import psycopg2

from app.auth.jwt import criar_access_token
from tests.integration.conftest import DATABASE_URL

_CNPJ = "12345678000195"


def _h(cnpj: str = _CNPJ) -> dict:
    tok = criar_access_token(sub=cnpj, role="dispensador", nome="Farmácia R2")
    return {"Authorization": f"Bearer {tok}"}


# ---------------------------------------------------------------------------
# Grupo 1 — concorrência real contra o pool (client_concorrencia)
# ---------------------------------------------------------------------------

def _seed_commit(quantidade: int = 10, cnpj: str = _CNPJ):
    """Semeia prescrição+item+custódia COMMITADOS. Devolve ids p/ cleanup."""
    cns = "9" + uuid.uuid4().hex[:14]
    cpf = "9" + uuid.uuid4().hex[:10]
    proto = f"PROTO-R2-{uuid.uuid4().hex[:10]}"
    now = datetime.utcnow().isoformat()
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
                "VALUES (%s,%s,true,%s,%s) RETURNING id", (cns, "DR R2", now, now))
            pres_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
                "VALUES (%s,%s,true,%s,%s) RETURNING id", (cpf, "PAC R2", now, now))
            pac_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, "
                "tipo_emissao, data_emissao, created_at, updated_at) "
                "VALUES (%s,%s,%s,'em_custodia','nova',%s,%s,%s) RETURNING id",
                (proto, pres_id, pac_id, now, now, now))
            presc_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, "
                "quantidade, posologia, status_item, created_at, updated_at) "
                "VALUES (%s,'LOSARTANA','50mg',%s,'1x','em_custodia',%s,%s) RETURNING id",
                (presc_id, quantidade, now, now))
            item_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, "
                "detentor_id, transferida_em, encerrada_em, motivo, created_at) "
                "VALUES (%s,%s,'dispensador',%s,%s,NULL,'seed-r2',%s)",
                (presc_id, item_id, cnpj, now, now))
    finally:
        conn.close()
    return {"cns": cns, "cpf": cpf, "proto": proto, "presc_id": presc_id, "item_id": item_id}


def _cleanup(seed):
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM estornos WHERE prescricao_id = %s", (seed["presc_id"],))
            cur.execute("DELETE FROM dispensacoes WHERE prescricao_item_id = %s", (seed["item_id"],))
            cur.execute("DELETE FROM prescricao_eventos WHERE prescricao_id = %s", (seed["presc_id"],))
            cur.execute("DELETE FROM prescricao_custodia WHERE prescricao_id = %s", (seed["presc_id"],))
            cur.execute("DELETE FROM prescricao_itens WHERE prescricao_id = %s", (seed["presc_id"],))
            cur.execute("DELETE FROM prescricoes WHERE id = %s", (seed["presc_id"],))
            cur.execute("DELETE FROM pacientes WHERE cpf = %s", (seed["cpf"],))
            cur.execute("DELETE FROM prescritores WHERE cns = %s", (seed["cns"],))
    finally:
        conn.close()


def test_dispensar_concorrente_idempotencia_pg(client_concorrencia):
    """§6.1 — 2 dispensações concorrentes do saldo inteiro → 1 movimento, não 2."""
    client = client_concorrencia
    seed = _seed_commit(quantidade=10)
    try:
        barreira = threading.Barrier(2)

        def _disp():
            barreira.wait()  # dispara as duas o mais junto possível
            r = client.post(
                f"/prescricoes/{seed['proto']}/itens/{seed['item_id']}/dispensar",
                json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 10},
                headers=_h(),
            )
            return r.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(_disp) for _ in range(2)]
            codes = sorted(f.result() for f in futs)

        assert all(c < 500 for c in codes), f"5xx sob concorrência: {codes}"
        # Exatamente uma criou (201); a outra foi barrada (409 saldo esgotado).
        assert codes.count(201) == 1, f"esperado 1×201, veio {codes}"
        assert codes.count(409) == 1, f"esperado 1×409, veio {codes}"

        # A verdade no banco: um único movimento; Σ dispensado ≤ prescrito.
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(quantidade_dispensada),0) "
                    "FROM dispensacoes WHERE prescricao_item_id = %s", (seed["item_id"],))
                n, total = cur.fetchone()
        finally:
            conn.close()
        assert n == 1, f"double-submit gravou {n} movimentos (esperado 1)"
        assert total == 10, f"oversell: Σ dispensado = {total} (prescrito 10)"
    finally:
        _cleanup(seed)


def test_estornar_concorrente_idempotencia_pg(client_concorrencia):
    """§6.1 — 2 estornos concorrentes da mesma dispensação → some 1 reverte."""
    client = client_concorrencia
    seed = _seed_commit(quantidade=10)
    try:
        r = client.post(
            f"/prescricoes/{seed['proto']}/itens/{seed['item_id']}/dispensar",
            json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 10},
            headers=_h(),
        )
        assert r.status_code == 201, r.text
        disp_id = r.json()["dispensacao_id"]

        barreira = threading.Barrier(2)

        def _est():
            barreira.wait()
            rr = client.post(f"/dispensacoes/{disp_id}/estornar",
                             json={"motivo": "outro"}, headers=_h())
            return rr.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futs = [pool.submit(_est) for _ in range(2)]
            codes = sorted(f.result() for f in futs)

        assert all(c < 500 for c in codes), f"5xx sob concorrência: {codes}"
        assert codes.count(201) == 1, f"esperado 1×201, veio {codes}"
        assert codes.count(409) == 1, f"esperado 1×409 (já estornada), veio {codes}"

        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*), COALESCE(SUM(quantidade_estornada),0) "
                    "FROM estornos WHERE origem_dispensacao_id = %s", (disp_id,))
                n, total = cur.fetchone()
        finally:
            conn.close()
        assert n == 1, f"estorno duplicado: {n} estornos (esperado 1)"
        assert total == 10, f"Σ estornado = {total} (dispensado 10)"
    finally:
        _cleanup(seed)


# ---------------------------------------------------------------------------
# Grupo 2 — guard-rail de unicidade sobre a projeção do relatório (savepoint)
# ---------------------------------------------------------------------------

def _seed_savepoint(outer_conn, quantidade=10, cnpj=_CNPJ):
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-R2G-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s,'DR R2G',true,%s,%s) RETURNING id",
            ("9" + uuid.uuid4().hex[:14], now, now))
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s,'PAC R2G',true,%s,%s) RETURNING id",
            ("9" + uuid.uuid4().hex[:10], now, now))
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, "
            "tipo_emissao, data_emissao, created_at, updated_at) "
            "VALUES (%s,%s,%s,'em_custodia','nova',%s,%s,%s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now))
        presc_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, "
            "quantidade, posologia, status_item, created_at, updated_at) "
            "VALUES (%s,'LOSARTANA','50mg',%s,'1x','em_custodia',%s,%s) RETURNING id",
            (presc_id, quantidade, now, now))
        item_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, "
            "detentor_id, transferida_em, encerrada_em, motivo, created_at) "
            "VALUES (%s,%s,'dispensador',%s,%s,NULL,'seed-r2g',%s)",
            (presc_id, item_id, cnpj, now, now))
    return proto, item_id


def test_guardrail_unicidade_identificadores_pg(client, outer_conn):
    """§6.2 / §2a R2 — ciclo dispensar→estornar→dispensar; nenhum dispensacao_id
    nem estorno_protocolo aparece mais de uma vez no relatório."""
    proto, item_id = _seed_savepoint(outer_conn)

    # dispensar parcial → estornar → dispensar de novo (3 movimentos, 3 ids)
    r1 = client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar",
                     json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 4}, headers=_h())
    assert r1.status_code == 201, r1.text
    disp1 = r1.json()["dispensacao_id"]

    re = client.post(f"/dispensacoes/{disp1}/estornar", json={"motivo": "outro"}, headers=_h())
    assert re.status_code == 201, re.text

    r2 = client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar",
                     json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": 6}, headers=_h())
    assert r2.status_code == 201, r2.text

    resp = client.get("/dispensadores/relatorio.csv", headers=_h())
    assert resp.status_code == 200, resp.text
    linhas = [x for x in csv.DictReader(io.StringIO(resp.text))
              if x["protocolo_prescricao"] == proto]

    # HAVING COUNT(*) > 1 materializado — deve vir VAZIO nos dois eixos.
    disp_ids = [x["dispensacao_id"] for x in linhas if x["tipo_movimento"] == "dispensacao"]
    est_protos = [x["estorno_protocolo"] for x in linhas if x["tipo_movimento"] == "estorno"]
    assert len(disp_ids) == len(set(disp_ids)), f"dispensacao_id duplicado: {disp_ids}"
    assert len(est_protos) == len(set(est_protos)), f"estorno_protocolo duplicado: {est_protos}"
    # sanidade: o ciclo produziu 2 dispensações + 1 estorno para este item
    assert len(disp_ids) == 2 and len(est_protos) == 1, (disp_ids, est_protos)
