"""
test_fila_dispensador.py — T4: fila do dispensador (paridade PostgreSQL).

Casa o allowlist `-k fila` do gate. O banco de integração é compartilhado entre
testes, então as asserções são por-protocolo (contém/não-contém), não por total.
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
         "quantidade": 10, "posologia": "1 cap 8/8h"},
    ],
}


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _disp(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="DROGARIA")


def _emitir_e_custodiar(client, outer_conn, seed_usuario, cnpj=_CNPJ_X):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/prescricoes", json=_PRESC, headers=_h(token))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM prescricoes WHERE protocolo = %s", (proto,))
        pid = cur.fetchone()[0]
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO prescricao_custodia
              (prescricao_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, NULL, 'dispensador', %s, %s, NULL, 'seed-fila', %s)
            """,
            (pid, cnpj, now, now),
        )
    return proto


def test_fila_mostra_prescricao_em_custodia(client, outer_conn, seed_usuario, seed_paciente):
    proto = _emitir_e_custodiar(client, outer_conn, seed_usuario, cnpj=_CNPJ_X)
    r = client.get("/dispensadores/fila", headers=_h(_disp(_CNPJ_X)))
    assert r.status_code == 200, r.text
    d = r.json()
    protos = [p["protocolo"] for p in d["fila"]]
    assert proto in protos
    alvo = next(p for p in d["fila"] if p["protocolo"] == proto)
    assert alvo["itens"][0]["nome_medicamento"] == "AMOXICILINA"
    assert alvo["itens"][0]["saldo"] == 10


def test_fila_isolada_por_cnpj(client, outer_conn, seed_usuario, seed_paciente):
    proto = _emitir_e_custodiar(client, outer_conn, seed_usuario, cnpj=_CNPJ_X)
    # Farmácia Y (outro CNPJ) não enxerga a receita retida por X.
    r = client.get("/dispensadores/fila", headers=_h(_disp(_CNPJ_Y)))
    assert r.status_code == 200, r.text
    protos = [p["protocolo"] for p in r.json()["fila"]]
    assert proto not in protos
