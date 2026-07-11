"""TICKET-F5 §5.A — comprovante expõe o estado de estorno (PostgreSQL).

O comprovante (JSON e PDF) ganha uma seção derivada `estorno` (read-only sobre
`estornos`), sem editar/apagar a dispensação. Semântica binária vs. parcial é
computada no backend. Cobre:
  - sem estorno: estorno.estornado=false (comprovante atual intacto)
  - estorno TOTAL: estornado/estorno_total=true, quantidade_restante=0, protocolo em estornos[]
  - estorno PARCIAL: estornado=true, estorno_total=false, quantidade_restante>0
  - PDF da dispensação estornada gera com carimbo (smoke: 200 + %PDF + bytes)
  - read-only: nada em dispensacoes/estornos muda ao ler o comprovante
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.auth.jwt import criar_access_token

_CNPJ = "12345678000195"


def _h(cnpj: str = _CNPJ) -> dict:
    return {"Authorization": f"Bearer {criar_access_token(sub=cnpj, role='dispensador', nome='Farmácia 5A')}"}


def _seed(outer_conn, quantidade=10, cnpj=_CNPJ):
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-5A-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute("INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
                    "VALUES (%s,'DR 5A',true,%s,%s) RETURNING id", ("9" + uuid.uuid4().hex[:14], now, now))
        pres_id = cur.fetchone()[0]
        cur.execute("INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
                    "VALUES (%s,'PAC 5A',true,%s,%s) RETURNING id", ("9" + uuid.uuid4().hex[:10], now, now))
        pac_id = cur.fetchone()[0]
        cur.execute("INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
                    "data_emissao, created_at, updated_at) "
                    "VALUES (%s,%s,%s,'em_custodia','nova',%s,%s,%s) RETURNING id",
                    (proto, pres_id, pac_id, now, now, now))
        presc_id = cur.fetchone()[0]
        cur.execute("INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
                    "posologia, status_item, created_at, updated_at) "
                    "VALUES (%s,'LOSARTANA','50mg',%s,'1x','em_custodia',%s,%s) RETURNING id",
                    (presc_id, quantidade, now, now))
        item_id = cur.fetchone()[0]
        cur.execute("INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
                    "transferida_em, encerrada_em, motivo, created_at) "
                    "VALUES (%s,%s,'dispensador',%s,%s,NULL,'seed-5a',%s)", (presc_id, item_id, cnpj, now, now))
    return {"proto": proto, "presc_id": presc_id, "item_id": item_id}


def _dispensar(client, proto, item_id, qtd):
    r = client.post(f"/prescricoes/{proto}/itens/{item_id}/dispensar",
                    json={"cnpj_estabelecimento": _CNPJ, "quantidade_dispensada": qtd}, headers=_h())
    assert r.status_code == 201, r.text
    return r.json()["dispensacao_id"]


def _estornar(client, disp_id, qtd=None):
    body = {"motivo": "erro_dispensacao"}
    if qtd is not None:
        body["quantidade"] = qtd
    r = client.post(f"/dispensacoes/{disp_id}/estornar", json=body, headers=_h())
    assert r.status_code == 201, r.text
    return r.json()


def _comprovante(client, disp_id):
    r = client.get(f"/dispensacoes/{disp_id}/comprovante", headers=_h())
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------

def test_comprovante_sem_estorno_estornado_false(client, outer_conn):
    s = _seed(outer_conn, 10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10)
    est = _comprovante(client, disp_id)["estorno"]
    assert est["estornado"] is False
    assert est["estorno_total"] is False
    assert est["quantidade_estornada"] == 0
    assert est["quantidade_restante"] == 10
    assert est["estornos"] == []


def test_comprovante_estorno_total(client, outer_conn):
    s = _seed(outer_conn, 10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10)
    r = _estornar(client, disp_id)  # total (remanescente)
    est = _comprovante(client, disp_id)["estorno"]
    assert est["estornado"] is True
    assert est["estorno_total"] is True
    assert est["quantidade_estornada"] == 10
    assert est["quantidade_restante"] == 0
    assert len(est["estornos"]) == 1
    assert est["estornos"][0]["protocolo"] == r["protocolo"]
    assert est["estornos"][0]["quantidade"] == 10
    assert est["estornos"][0]["motivo"] == "erro_dispensacao"


def test_comprovante_estorno_parcial(client, outer_conn):
    s = _seed(outer_conn, 10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10)
    _estornar(client, disp_id, qtd=3)
    est = _comprovante(client, disp_id)["estorno"]
    assert est["estornado"] is True
    assert est["estorno_total"] is False
    assert est["quantidade_estornada"] == 3
    assert est["quantidade_restante"] == 7
    assert len(est["estornos"]) == 1


def test_comprovante_pdf_estornado_gera_com_carimbo(client, outer_conn):
    s = _seed(outer_conn, 10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10)
    _estornar(client, disp_id)
    r = client.get(f"/dispensacoes/{disp_id}/comprovante?formato=pdf", headers=_h())
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
    assert len(r.content) > 1000  # documento real, não vazio


def test_comprovante_read_only(client, outer_conn):
    s = _seed(outer_conn, 10)
    disp_id = _dispensar(client, s["proto"], s["item_id"], 10)
    _estornar(client, disp_id, qtd=4)

    def _contagens():
        with outer_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM dispensacoes")
            d = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM estornos")
            e = cur.fetchone()[0]
        return d, e

    antes = _contagens()
    _comprovante(client, disp_id)
    assert client.get(f"/dispensacoes/{disp_id}/comprovante?formato=pdf", headers=_h()).status_code == 200
    assert _contagens() == antes
