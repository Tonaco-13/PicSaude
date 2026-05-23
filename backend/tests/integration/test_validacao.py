"""TICKET-5C V7 — GET /prescricoes/{p}/validacao owner check."""
from __future__ import annotations

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
        {"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
         "quantidade": 10, "posologia": "1 cápsula 3x ao dia"},
    ],
}

_CNS_PRESCRITOR_B = "999888777666555"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_v7_validacao_outro_prescritor_403(client, seed_usuario, seed_paciente):
    """V7 — prescritor B não pode ler validação documental de prescrição de A;
    dispensador e admin passam direto."""
    token_a = obter_token_prescritor(client, seed_usuario)
    r = client.post("/prescricoes", json=_PAYLOAD_BASE, headers=_headers(token_a))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    token_b = criar_access_token(sub=_CNS_PRESCRITOR_B, role="prescritor", nome="DR. B")
    token_admin = criar_access_token(sub="admin@picsaude", role="admin", nome="ADMIN")
    token_disp = criar_access_token(sub="12345678000195", role="dispensador", nome="DROGARIA")

    # Prescritor B → 403
    rb = client.get(f"/prescricoes/{proto}/validacao", headers=_headers(token_b))
    assert rb.status_code == 403, rb.text
    assert rb.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"

    # Dono A → 200
    ra = client.get(f"/prescricoes/{proto}/validacao", headers=_headers(token_a))
    assert ra.status_code == 200, ra.text

    # Admin → 200
    radmin = client.get(f"/prescricoes/{proto}/validacao", headers=_headers(token_admin))
    assert radmin.status_code == 200, radmin.text

    # Dispensador autenticado → 200 (passa direto, fluxo de balcão)
    rd = client.get(f"/prescricoes/{proto}/validacao", headers=_headers(token_disp))
    assert rd.status_code == 200, rd.text
