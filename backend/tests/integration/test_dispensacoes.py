"""TICKET-5C V9 — GET /dispensacoes/{id}/comprovante owner check multi-role."""
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


_PAYLOAD_PRESCRICAO = {
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

_CNS_PRESCRITOR_B = "999888777666555"
_CNPJ_X = "12345678000195"
_CNPJ_Y = "98765432000110"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_dispensador(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="DROGARIA")


def _setup_dispensacao_de_x(client, outer_conn, seed_usuario):
    """
    Seed: prescrição emitida por A, custódia atribuída ao dispensador X (CNPJ X),
    1 dispensação registrada em CNPJ X. Retorna o id da dispensação.
    """
    token_a = obter_token_prescritor(client, seed_usuario)
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO, headers=_headers(token_a))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM prescricoes WHERE protocolo = %s", (proto,))
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id FROM prescricao_itens WHERE prescricao_id = %s LIMIT 1",
            (prescricao_id,),
        )
        item_id = cur.fetchone()[0]
        # Seedar custódia ativa do dispensador X (item-level basta — dispensar_item
        # não exige custódia da prescrição inteira).
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO prescricao_custodia
              (prescricao_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'v9-seed', %s)
            """,
            (prescricao_id, item_id, _CNPJ_X, now, now),
        )
        # Atualizar item para em_custodia
        cur.execute(
            "UPDATE prescricao_itens SET status_item = 'em_custodia' WHERE id = %s",
            (item_id,),
        )

    # Realizar dispensação com token de X
    payload = {"cnpj_estabelecimento": _CNPJ_X, "quantidade_dispensada": 5}
    rd = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json=payload, headers=_headers(_token_dispensador(_CNPJ_X)),
    )
    assert rd.status_code == 201, rd.text

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM dispensacoes WHERE prescricao_item_id = %s ORDER BY id DESC LIMIT 1",
            (item_id,),
        )
        return cur.fetchone()[0]


# ===========================================================================
# V9a — dispensador outro
# ===========================================================================

def test_v9_comprovante_dispensador_outro_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    dispensacao_id = _setup_dispensacao_de_x(client, outer_conn, seed_usuario)

    # Token de dispensador Y (CNPJ Y) tenta ler comprovante de X
    ry = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(_token_dispensador(_CNPJ_Y)),
    )
    assert ry.status_code == 403, ry.text
    assert ry.json()["detail"]["codigo"] == "nao_e_dono_da_dispensacao"

    # Dono X → 200
    rx = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(_token_dispensador(_CNPJ_X)),
    )
    assert rx.status_code == 200, rx.text

    # Admin → 200
    radmin = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(criar_access_token(sub="admin@picsaude", role="admin", nome="A")),
    )
    assert radmin.status_code == 200, radmin.text

    # Auditor → 200
    raud = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(criar_access_token(sub="auditor@picsaude", role="auditor", nome="A")),
    )
    assert raud.status_code == 200, raud.text


# ===========================================================================
# V9b — prescritor outro
# ===========================================================================

def test_v9_comprovante_prescritor_outro_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    dispensacao_id = _setup_dispensacao_de_x(client, outer_conn, seed_usuario)

    token_a = obter_token_prescritor(client, seed_usuario)
    token_b = criar_access_token(sub=_CNS_PRESCRITOR_B, role="prescritor", nome="DR. B")

    # Prescritor B (não-dono da prescrição) → 403
    rb = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(token_b),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"

    # Prescritor A (dono) → 200
    ra = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante",
        headers=_headers(token_a),
    )
    assert ra.status_code == 200, ra.text
