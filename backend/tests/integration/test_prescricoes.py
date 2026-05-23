"""Ticket 13 — emissão de prescrição + ledger contra banco real."""
from __future__ import annotations

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    obter_token_prescritor,
)


_PAYLOAD_BASE = {
    "cns_prescritor":  "987654321098765",
    "nome_prescritor": "DR. TESTE TICKET13",
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


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_criar_prescricao_valida(client, seed_usuario, seed_paciente):
    token = obter_token_prescritor(client, seed_usuario)

    r = client.post("/prescricoes", json=_PAYLOAD_BASE, headers=_headers(token))
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["protocolo"]
    assert body["status"] in ("pendente", "transferida_paciente")
    assert body["itens_count"] == 1
    assert body["tipo_emissao"] == "nova"
    assert body["documento_hash"]


def test_payload_sem_itens_retorna_422(client, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)

    payload = {**_PAYLOAD_BASE, "itens": []}
    r = client.post("/prescricoes", json=payload, headers=_headers(token))
    assert r.status_code == 422, r.text


def test_payload_tipo_emissao_invalido_retorna_422(client, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)

    payload = {**_PAYLOAD_BASE, "tipo_emissao": "inexistente"}
    r = client.post("/prescricoes", json=payload, headers=_headers(token))
    assert r.status_code == 422, r.text


def test_ledger_registra_evento_emissao(client, outer_conn, seed_usuario, seed_paciente):
    """Após criar prescrição, `prescricao_eventos` tem evento `prescricao_emitida`."""
    token = obter_token_prescritor(client, seed_usuario)

    r = client.post("/prescricoes", json=_PAYLOAD_BASE, headers=_headers(token))
    assert r.status_code == 201, r.text
    protocolo = r.json()["protocolo"]

    # Consulta direta no outer_conn — enxerga os dados inseridos via savepoint
    # (o RELEASE SAVEPOINT dentro do endpoint já propagou para a outer tx).
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.tipo_evento, pe.ator_tipo
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
             ORDER BY pe.id ASC
            """,
            (protocolo,),
        )
        eventos = cur.fetchall()

    tipos = [ev[0] for ev in eventos]
    assert "prescricao_emitida" in tipos, (
        f"Evento 'prescricao_emitida' ausente para {protocolo}. Eventos: {tipos}"
    )
    # Não deve existir RECONCILIACAO_MANUAL no caminho feliz
    assert all(t != "RECONCILIACAO_MANUAL" for t in tipos)


def test_toda_prescricao_tem_prescritor_e_paciente(client, outer_conn, seed_usuario, seed_paciente):
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/prescricoes", json=_PAYLOAD_BASE, headers=_headers(token))
    assert r.status_code == 201
    protocolo = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.id, p.prescritor_id, p.paciente_id,
                   pr.cns AS prescritor_cns,
                   pa.cpf AS paciente_cpf
              FROM prescricoes p
              JOIN prescritores pr ON pr.id = p.prescritor_id
              JOIN pacientes    pa ON pa.id = p.paciente_id
             WHERE p.protocolo = %s
            """,
            (protocolo,),
        )
        row = cur.fetchone()

    assert row is not None
    assert row[1] is not None  # prescritor_id
    assert row[2] is not None  # paciente_id
    assert row[3] == "987654321098765"
    assert row[4] == SEED_PACIENTE_CPF


# ===========================================================================
# TICKET-5A — entrega digital solicitada sem carteira → 422 + rollback
# ===========================================================================

_CPF_PACIENTE_NOVO_5A = "55566677788"   # CPF nunca seedado em conftest

# Baselines de tabelas regulatórias sob a outer tx, tiradas ANTES da request
# e comparadas DEPOIS para garantir rollback total no caminho 422.
_TABELAS_BASELINE_PRESCRICAO = (
    "prescricao_eventos",
    "prescricao_custodia",
    "eventos_publicacao",
    "prescritores",     # P2 CODEX rodada 2 — prescritor auto-criado também não persiste
)


def _contagens(outer_conn, tabelas: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def test_prescricao_422_quando_enviar_ao_paciente_sem_carteira(
    client, outer_conn, seed_usuario,
):
    """5A — paciente novo + enviar_ao_paciente=true → 422 com rollback total."""
    token = obter_token_prescritor(client, seed_usuario)
    baseline = _contagens(outer_conn, _TABELAS_BASELINE_PRESCRICAO)

    payload = {
        **_PAYLOAD_BASE,
        "cpf_paciente":         _CPF_PACIENTE_NOVO_5A,
        "nome_paciente":        "PACIENTE NOVO 5A",
        "enviar_ao_paciente":   True,
    }
    r = client.post("/prescricoes", json=payload, headers=_headers(token))

    # Contrato HTTP
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["codigo"] == "patient_no_digital_wallet"
    assert "carteira digital" in detail["mensagem"]
    assert "patient_id" not in detail   # P2 CODEX: não ecoar CPF/id

    # Rollback efetivo
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM prescricoes p
              JOIN pacientes pa ON pa.id = p.paciente_id
             WHERE pa.cpf = %s
            """,
            (_CPF_PACIENTE_NOVO_5A,),
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM pacientes WHERE cpf = %s",
            (_CPF_PACIENTE_NOVO_5A,),
        )
        assert cur.fetchone()[0] == 0   # paciente novo NÃO foi auto-criado

    depois = _contagens(outer_conn, _TABELAS_BASELINE_PRESCRICAO)
    for t in _TABELAS_BASELINE_PRESCRICAO:
        assert depois[t] == baseline[t], (
            f"{t}: baseline={baseline[t]} depois={depois[t]} — rollback incompleto"
        )


def test_prescricao_201_quando_enviar_ao_paciente_com_carteira(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """5A — paciente cadastrado + enviar_ao_paciente=true → 201, entrega ocorre."""
    token = obter_token_prescritor(client, seed_usuario)

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos WHERE tipo_evento = 'custodia_transferida'"
        )
        eventos_custodia_antes = cur.fetchone()[0]

    payload = {**_PAYLOAD_BASE, "enviar_ao_paciente": True}
    r = client.post("/prescricoes", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["entregue_carteira"] is True
    assert body["status"] == "transferida_paciente"
    protocolo = body["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM prescricao_custodia c
              JOIN prescricoes p ON p.id = c.prescricao_id
             WHERE p.protocolo = %s AND c.detentor_tipo = 'paciente'
            """,
            (protocolo,),
        )
        assert cur.fetchone()[0] == 1, "custódia paciente não registrada"

        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos WHERE tipo_evento = 'custodia_transferida'"
        )
        assert cur.fetchone()[0] == eventos_custodia_antes + 1


def test_prescricao_201_quando_nao_enviar_ao_paciente_sem_carteira(
    client, outer_conn, seed_usuario,
):
    """5A — paciente novo + enviar_ao_paciente=false → 201, auto-cria sem entrega."""
    token = obter_token_prescritor(client, seed_usuario)

    payload = {
        **_PAYLOAD_BASE,
        "cpf_paciente":         _CPF_PACIENTE_NOVO_5A,
        "nome_paciente":        "PACIENTE NOVO 5A",
        "enviar_ao_paciente":   False,
    }
    r = client.post("/prescricoes", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["entregue_carteira"] is False
    assert body["status"] == "pendente"

    # Paciente foi auto-criado (linha 297-303 do router continua executando)
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pacientes WHERE cpf = %s",
            (_CPF_PACIENTE_NOVO_5A,),
        )
        assert cur.fetchone()[0] == 1
