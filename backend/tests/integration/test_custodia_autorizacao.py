"""TICKET-5C — Autorização mínima em custodia.py (V5, V6, V10).

V5 — GET /prescricoes/{p}/custodia (multi-role matrix)
V6 — POST /prescricoes/{p}/custodia/transferir (5 regras §3.4)
V10 — POST /prescricoes/{p}/itens/{i}/dispensar (CNPJ vs JWT)
"""
from __future__ import annotations

from datetime import datetime
import uuid

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


_PAYLOAD_BASE = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "nova",
    "itens": [
        {
            "nome_medicamento": "AMOXICILINA",
            "concentracao":     "500mg",
            "quantidade":       10,
            "posologia":        "1 cápsula 3x ao dia",
        }
    ],
}

_CNS_PRESCRITOR_B = "999888777666555"     # 15 dígitos (P3 #7 CODEX rodada 1)
_CNPJ_DISPENSADOR_A = "12345678000195"
_CNPJ_DISPENSADOR_B = "98765432000110"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _token_prescritor_b() -> str:
    return criar_access_token(sub=_CNS_PRESCRITOR_B, role="prescritor", nome="DR. B")


def _token_dispensador(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome="DROGARIA")


def _contagens(outer_conn, tabelas: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def _criar_prescricao_de_a(client, token_a) -> str:
    r = client.post("/prescricoes", json=_PAYLOAD_BASE, headers=_headers(token_a))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ===========================================================================
# V5 — GET /custodia
# ===========================================================================

def test_v5_custodia_sem_token_401(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    r = client.get(f"/prescricoes/{proto}/custodia")
    assert r.status_code == 401, r.text


def test_v5_custodia_outro_prescritor_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    rb = client.get(f"/prescricoes/{proto}/custodia", headers=_headers(_token_prescritor_b()))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "sem_vinculo_com_prescricao"

    # Dono A → 200
    ra = client.get(f"/prescricoes/{proto}/custodia", headers=_headers(token_a))
    assert ra.status_code == 200, ra.text


# ===========================================================================
# V6 — POST /custodia/transferir (5 sub-testes)
# ===========================================================================

_TABELAS_V6 = ("prescricao_custodia", "prescricao_eventos")


def test_v6_prescritor_b_de_prescritor_a_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V6 §5.6a — token B, payload.de_id = CNS_A. Bypass clássico."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)
    baseline = _contagens(outer_conn, _TABELAS_V6)

    payload = {
        "de": "prescritor", "de_id": SEED_PRESCRITOR_CNS,
        "para": "paciente", "para_id": SEED_PACIENTE_CPF,
    }
    rb = client.post(
        f"/prescricoes/{proto}/custodia/transferir",
        json=payload, headers=_headers(_token_prescritor_b()),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "ator_mismatch"

    depois = _contagens(outer_conn, _TABELAS_V6)
    for t in _TABELAS_V6:
        assert depois[t] == baseline[t]


def test_v6_prescritor_b_de_paciente_sobre_prescricao_a_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V6 §5.6b — bypass via payload.de=paciente em endpoint que não aceita."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)
    baseline = _contagens(outer_conn, _TABELAS_V6)

    payload = {
        "de": "paciente", "de_id": SEED_PACIENTE_CPF,
        "para": "dispensador", "para_id": _CNPJ_DISPENSADOR_B,
    }
    rb = client.post(
        f"/prescricoes/{proto}/custodia/transferir",
        json=payload, headers=_headers(_token_prescritor_b()),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "ator_mismatch"
    assert "Fluxo paciente não é aceito" in rb.json()["detail"]["mensagem"]

    depois = _contagens(outer_conn, _TABELAS_V6)
    for t in _TABELAS_V6:
        assert depois[t] == baseline[t]


def test_v6_prescritor_b_de_dispensador_sobre_prescricao_a_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V6 §5.6c — bypass: role prescritor declarando de=dispensador."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)
    baseline = _contagens(outer_conn, _TABELAS_V6)

    payload = {
        "de": "dispensador", "de_id": _CNPJ_DISPENSADOR_B,
        "para": "prescritor", "para_id": SEED_PRESCRITOR_CNS,
    }
    rb = client.post(
        f"/prescricoes/{proto}/custodia/transferir",
        json=payload, headers=_headers(_token_prescritor_b()),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "ator_mismatch"
    assert "Role do JWT não coincide" in rb.json()["detail"]["mensagem"]

    depois = _contagens(outer_conn, _TABELAS_V6)
    for t in _TABELAS_V6:
        assert depois[t] == baseline[t]


def test_v6_prescritor_b_de_prescritor_b_sobre_prescricao_a_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V6 §5.6d — JWT bate com payload.de_id, mas a prescrição não é dele.
    Bypass mais sofisticado, fechado pela regra 3 (ownership real)."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)
    baseline = _contagens(outer_conn, _TABELAS_V6)

    payload = {
        "de": "prescritor", "de_id": _CNS_PRESCRITOR_B,  # próprio JWT
        "para": "paciente", "para_id": SEED_PACIENTE_CPF,
    }
    rb = client.post(
        f"/prescricoes/{proto}/custodia/transferir",
        json=payload, headers=_headers(_token_prescritor_b()),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "ator_mismatch"

    depois = _contagens(outer_conn, _TABELAS_V6)
    for t in _TABELAS_V6:
        assert depois[t] == baseline[t]


def test_v6_dispensador_com_custodia_item_level_nao_autoriza_transferencia_global_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V6 §5.6e — dispensador com custódia ATIVA apenas de UM item
    (item_id IS NOT NULL) não pode transferir custódia da prescrição
    INTEIRA (item_id IS NULL). Fechado pela cláusula AND item_id IS NULL."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    # Buscar IDs criados
    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM prescricoes WHERE protocolo = %s", (proto,))
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id FROM prescricao_itens WHERE prescricao_id = %s LIMIT 1",
            (prescricao_id,),
        )
        item_id = cur.fetchone()[0]

        # Inserir custódia ATIVA item-level para dispensador D — sem
        # custódia para a prescrição inteira.
        now = datetime.utcnow().isoformat()
        cur.execute(
            """
            INSERT INTO prescricao_custodia
              (prescricao_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'item-level seed v6', %s)
            """,
            (prescricao_id, item_id, _CNPJ_DISPENSADOR_A, now, now),
        )

    baseline = _contagens(outer_conn, _TABELAS_V6)
    payload = {
        "de": "dispensador", "de_id": _CNPJ_DISPENSADOR_A,
        "para": "prescritor", "para_id": SEED_PRESCRITOR_CNS,
    }
    r = client.post(
        f"/prescricoes/{proto}/custodia/transferir",
        json=payload, headers=_headers(_token_dispensador(_CNPJ_DISPENSADOR_A)),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "ator_mismatch"

    depois = _contagens(outer_conn, _TABELAS_V6)
    for t in _TABELAS_V6:
        assert depois[t] == baseline[t]


# ===========================================================================
# V10 — POST /itens/{i}/dispensar
# ===========================================================================

_TABELAS_V10 = (
    "dispensacoes",
    "prescricao_eventos",
    "eventos_publicacao",
)


def test_v10_dispensar_cnpj_mismatch_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V10 — token B + payload.cnpj=A → 403 com rollback total da escrita."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    with outer_conn.cursor() as cur:
        cur.execute("SELECT id FROM prescricoes WHERE protocolo = %s", (proto,))
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "SELECT id, status_item FROM prescricao_itens WHERE prescricao_id = %s LIMIT 1",
            (prescricao_id,),
        )
        item_row = cur.fetchone()
        item_id, status_item_antes = item_row[0], item_row[1]

    baseline = _contagens(outer_conn, _TABELAS_V10)

    # Captura adicional: baseline de eventos da prescrição específica
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id = %s",
            (prescricao_id,),
        )
        eventos_prescricao_antes = cur.fetchone()[0]

    payload = {
        "cnpj_estabelecimento": _CNPJ_DISPENSADOR_A,   # CNPJ de A no payload
        "quantidade_dispensada": 5,
    }
    # Token de dispensador B
    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json=payload, headers=_headers(_token_dispensador(_CNPJ_DISPENSADOR_B)),
    )
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["codigo"] == "ator_mismatch"
    assert "CNPJ do payload" in r.json()["detail"]["mensagem"]

    # Rollback efetivo
    depois = _contagens(outer_conn, _TABELAS_V10)
    for t in _TABELAS_V10:
        assert depois[t] == baseline[t]

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == status_item_antes

        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id = %s",
            (prescricao_id,),
        )
        assert cur.fetchone()[0] == eventos_prescricao_antes
