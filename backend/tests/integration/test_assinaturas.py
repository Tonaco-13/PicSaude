"""TICKET-5C — V8 (GET) + V11 (POST) /prescricoes/{p}/assinatura owner check."""
from __future__ import annotations

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

_PAYLOAD_ASSINATURA = {
    "tipo_certificado":     "A1",
    "emissor":              "AC CertiSign G7",
    "serial_certificado":   "deadbeefcafebabe",
    "timestamp_assinatura": "2026-05-23T10:00:00",
    "hash_documento":       "a" * 64,
}

_CNS_PRESCRITOR_B = "999888777666555"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _criar_prescricao_de_a(client, token_a) -> str:
    r = client.post("/prescricoes", json=_PAYLOAD_PRESCRICAO, headers=_headers(token_a))
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ===========================================================================
# V8 — GET /assinatura
# ===========================================================================

def test_v8_assinatura_outro_prescritor_403(client, seed_usuario, seed_paciente):
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    token_b = criar_access_token(sub=_CNS_PRESCRITOR_B, role="prescritor", nome="DR. B")
    token_admin = criar_access_token(sub="admin@picsaude", role="admin", nome="ADMIN")

    rb = client.get(f"/prescricoes/{proto}/assinatura", headers=_headers(token_b))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"

    # Admin passa direto. Pode retornar 200 (com dados) ou 404 (sem assinatura
    # ainda registrada para essa prescrição). O que NÃO pode é 403.
    radmin = client.get(f"/prescricoes/{proto}/assinatura", headers=_headers(token_admin))
    assert radmin.status_code != 403, radmin.text


# ===========================================================================
# V11 — POST /assinatura
# ===========================================================================

_TABELAS_V11 = (
    "prescricao_assinatura",
    "prescricao_eventos",
    "eventos_publicacao",
)


def _contagens(outer_conn, tabelas: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def test_v11_assinatura_post_outro_prescritor_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """V11 — prescritor B não pode registrar metadados de assinatura em
    prescrição de A. Rollback efetivo: nada gravado em prescricao_assinatura
    nem evento no ledger."""
    token_a = obter_token_prescritor(client, seed_usuario)
    proto = _criar_prescricao_de_a(client, token_a)

    baseline = _contagens(outer_conn, _TABELAS_V11)

    token_b = criar_access_token(sub=_CNS_PRESCRITOR_B, role="prescritor", nome="DR. B")
    rb = client.post(
        f"/prescricoes/{proto}/assinatura",
        json=_PAYLOAD_ASSINATURA, headers=_headers(token_b),
    )
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"

    # Rollback efetivo — nem prescricao_assinatura nem evento escapam.
    depois = _contagens(outer_conn, _TABELAS_V11)
    for t in _TABELAS_V11:
        assert depois[t] == baseline[t], (
            f"{t}: baseline={baseline[t]} depois={depois[t]} — rollback incompleto"
        )

    # Caminho válido preservado para o dono A → 201
    ra = client.post(
        f"/prescricoes/{proto}/assinatura",
        json=_PAYLOAD_ASSINATURA, headers=_headers(token_a),
    )
    assert ra.status_code == 201, ra.text

    # Cenário UPDATE: prescritor B tenta de novo após A já ter registrado.
    # Capturar campos pré-tentativa para garantir que UPDATE não escapou.
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pa.serial_certificado, pa.dados_assinatura_b64, pa.updated_at
              FROM prescricao_assinatura pa
              JOIN prescricoes p ON p.id = pa.prescricao_id
             WHERE p.protocolo = %s
            """,
            (proto,),
        )
        antes_update = cur.fetchone()

    payload_b_diferente = {
        **_PAYLOAD_ASSINATURA,
        "serial_certificado": "FRAUD_SERIAL_B_5C",
        "dados_assinatura_b64": "FRAUD_DATA_B_5C",
    }
    rb2 = client.post(
        f"/prescricoes/{proto}/assinatura",
        json=payload_b_diferente, headers=_headers(token_b),
    )
    assert rb2.status_code == 403, rb2.text

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pa.serial_certificado, pa.dados_assinatura_b64, pa.updated_at
              FROM prescricao_assinatura pa
              JOIN prescricoes p ON p.id = pa.prescricao_id
             WHERE p.protocolo = %s
            """,
            (proto,),
        )
        depois_update = cur.fetchone()
    assert depois_update == antes_update, (
        "UPDATE em prescricao_assinatura escapou do rollback do 403"
    )

    # Protocolo inexistente + token A → 404 (preservado via _get_meta_prescricao)
    r404 = client.post(
        "/prescricoes/PROTO-INEXISTENTE-5C/assinatura",
        json=_PAYLOAD_ASSINATURA, headers=_headers(token_a),
    )
    assert r404.status_code == 404, r404.text
