"""
test_estorno.py — T2: estorno de dispensação (paridade PostgreSQL, gate real).

Espelha tests/integration/test_dispensacoes.py. Casa o allowlist `-k estorno`
do gate de CI. Subconjunto focal: estorno completo + ledger duplo; estorno
parcial que repõe saldo Σ efetivo; ownership entre CNPJs (403).
"""
from __future__ import annotations

from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)

_CNPJ_X = "12345678000195"
_CNPJ_Y = "98765432000110"

_PRESC = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "nova",
    "itens": [
        {"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
         "quantidade": 10, "posologia": "1 cap 3x ao dia"},
    ],
}


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _disp_token(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="DROGARIA")


def _setup(client, outer_conn, seed_usuario, cnpj=_CNPJ_X):
    """Emite prescrição, seeda custódia do dispensador, dispensa 5/10.
    Retorna (proto, prescricao_id, item_id, dispensacao_id)."""
    token_a = obter_token_prescritor(client, seed_usuario)
    r = client.post("/prescricoes", json=_PRESC, headers=_h(token_a))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM prescricoes WHERE protocolo = %s", (proto,))
        presc_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM prescricao_itens WHERE prescricao_id = %s LIMIT 1", (presc_id,))
        item_id = cur.fetchone()[0]
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO prescricao_custodia
              (prescricao_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed-t2', %s)
            """,
            (presc_id, item_id, cnpj, now, now),
        )
        cur.execute("UPDATE prescricao_itens SET status_item = 'em_custodia' WHERE id = %s", (item_id,))

    rd = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": cnpj, "quantidade_dispensada": 5},
        headers=_h(_disp_token(cnpj)),
    )
    assert rd.status_code == 201, rd.text
    return proto, presc_id, item_id, rd.json()["dispensacao_id"]


def test_estorno_completo_e_ledger_duplo(client, outer_conn, seed_usuario, seed_paciente):
    proto, presc_id, item_id, disp_id = _setup(client, outer_conn, seed_usuario)

    r = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 5, "motivo": "desistencia"},
        headers=_h(_disp_token(_CNPJ_X)),
    )
    assert r.status_code == 201, r.text
    assert r.json()["saldo_estornavel_restante"] == 0

    with outer_conn.cursor() as cur:
        cur.execute("SELECT quantidade_dispensada FROM dispensacoes WHERE id = %s", (disp_id,))
        assert cur.fetchone()[0] == 5   # intocada
        cur.execute(
            "SELECT id, quantidade_estornada, motivo FROM estornos WHERE origem_dispensacao_id = %s",
            (disp_id,),
        )
        est = cur.fetchone()
        assert est[1] == 5 and est[2] == "desistencia"
        cur.execute("SELECT tipo_evento FROM estorno_eventos WHERE estorno_id = %s", (est[0],))
        assert "estorno_registrado" in [x[0] for x in cur.fetchall()]
        cur.execute("SELECT tipo_evento FROM prescricao_eventos WHERE prescricao_id = %s", (presc_id,))
        assert "dispensacao_estornada" in [x[0] for x in cur.fetchall()]


def test_estorno_parcial_repoe_saldo(client, outer_conn, seed_usuario, seed_paciente):
    proto, presc_id, item_id, disp_id = _setup(client, outer_conn, seed_usuario)

    r = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 3, "motivo": "falha_pagamento"},
        headers=_h(_disp_token(_CNPJ_X)),
    )
    assert r.status_code == 201, r.text

    # saldo efetivo = 10 − (5 − 3) = 8 → redispensa 8 fecha o item
    rd = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ_X, "quantidade_dispensada": 8},
        headers=_h(_disp_token(_CNPJ_X)),
    )
    assert rd.status_code == 201, rd.text
    assert rd.json()["status_item"] == "dispensado"


def test_estorno_de_outro_cnpj_403(client, outer_conn, seed_usuario, seed_paciente):
    proto, presc_id, item_id, disp_id = _setup(client, outer_conn, seed_usuario)

    r = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"quantidade_estornada": 1, "motivo": "desistencia"},
        headers=_h(_disp_token(_CNPJ_Y)),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "nao_e_dono_da_dispensacao"
