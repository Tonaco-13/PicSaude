"""
tests/integration/test_historico_retencoes.py
=============================================

T6 — GET /dispensadores/historico: prescrições em que a unidade dispensou ≥1
item, com dispensacao_id (comprovante/estorno), comprador (T5) e estorno.

Check de Determinismo (Jules): a leitura tem ORDER BY explícito — duas chamadas
devolvem a mesma ordem. O histórico é reconstruído de `dispensacoes`/`estornos`,
nunca de `prescricao_custodia` (evita a dívida do fetchone sem ORDER BY).
"""
from __future__ import annotations

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
    proto = f"PROTO-HIST-{uuid.uuid4().hex[:10]}"
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


def _historico(client, cnpj):
    r = client.get("/dispensadores/historico", headers=_h(cnpj))
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------

def test_historico_lista_dispensacoes_da_unidade(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    disp_id = _dispensar(client, proto, item_id, _CNPJ_A, 3, comprador="MARIA PORTADORA")

    body = _historico(client, _CNPJ_A)
    rec = next(h for h in body["historico"] if h["protocolo"] == proto)
    it = rec["itens_dispensados"][0]
    assert it["dispensacao_id"] == disp_id
    assert it["quantidade_dispensada"] == 3
    assert it["estornado"] is False
    assert rec["comprador"]["nome"] == "MARIA PORTADORA"


def test_historico_isolado_por_cnpj(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    _dispensar(client, proto, item_id, _CNPJ_A, 2)

    # A farmácia B não vê o que A dispensou.
    protos_b = {h["protocolo"] for h in _historico(client, _CNPJ_B)["historico"]}
    assert proto not in protos_b


def test_historico_reflete_estorno(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, _CNPJ_A)
    disp_id = _dispensar(client, proto, item_id, _CNPJ_A, 3)
    r = client.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"}, headers=_h(_CNPJ_A))
    assert r.status_code == 201, r.text

    rec = next(h for h in _historico(client, _CNPJ_A)["historico"] if h["protocolo"] == proto)
    it = rec["itens_dispensados"][0]
    assert it["quantidade_estornada"] == 3
    assert it["estornado"] is True


def test_historico_ordem_deterministica(client, outer_conn):
    """Check de Determinismo: duas leituras devolvem a mesma ordem (ORDER BY)."""
    _, p1, i1 = _seed(outer_conn, _CNPJ_A)
    _, p2, i2 = _seed(outer_conn, _CNPJ_A)
    _dispensar(client, p1, i1, _CNPJ_A, 1)
    _dispensar(client, p2, i2, _CNPJ_A, 1)

    ordem1 = [h["protocolo"] for h in _historico(client, _CNPJ_A)["historico"]]
    ordem2 = [h["protocolo"] for h in _historico(client, _CNPJ_A)["historico"]]
    assert ordem1 == ordem2
    assert p1 in ordem1 and p2 in ordem1
