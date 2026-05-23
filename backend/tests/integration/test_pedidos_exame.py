"""TICKET-5A — POST /pedidos-exame: entrega digital ao paciente.

Espelha §5.2 do TICKET-5A-CARTEIRA-DIGITAL-422.md:
- 422 + rollback quando enviar_ao_paciente=true e paciente sem carteira
- 201 quando enviar_ao_paciente=true e paciente cadastrado (entrega ocorre)
- 201 quando enviar_ao_paciente=false (auto-cria paciente sem entrega)
"""
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
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "HEMOGRAMA", "quantidade": 1}],
}

_CPF_PACIENTE_NOVO_5A = "55566677788"   # CPF nunca seedado em conftest

_TABELAS_BASELINE_PEDIDO = (
    "pedido_exame_eventos",
    "pedido_exame_custodia",
    "eventos_publicacao",
    "prescritores",     # P2 CODEX rodada 2 — prescritor auto-criado também não persiste
)


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _contagens(outer_conn, tabelas: tuple[str, ...]) -> dict[str, int]:
    out: dict[str, int] = {}
    with outer_conn.cursor() as cur:
        for t in tabelas:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            out[t] = cur.fetchone()[0]
    return out


def test_pedido_exame_422_quando_enviar_ao_paciente_sem_carteira(
    client, outer_conn, seed_usuario,
):
    """5A — paciente novo + enviar_ao_paciente=true → 422 com rollback total."""
    token = obter_token_prescritor(client, seed_usuario)
    baseline = _contagens(outer_conn, _TABELAS_BASELINE_PEDIDO)

    payload = {
        **_PAYLOAD_BASE,
        "cpf_paciente":       _CPF_PACIENTE_NOVO_5A,
        "nome_paciente":      "PACIENTE NOVO 5A",
        "enviar_ao_paciente": True,
    }
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token))

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
            SELECT COUNT(*) FROM pedidos_exame pe
              JOIN pacientes pa ON pa.id = pe.paciente_id
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

    depois = _contagens(outer_conn, _TABELAS_BASELINE_PEDIDO)
    for t in _TABELAS_BASELINE_PEDIDO:
        assert depois[t] == baseline[t], (
            f"{t}: baseline={baseline[t]} depois={depois[t]} — rollback incompleto"
        )


def test_pedido_exame_201_quando_enviar_ao_paciente_com_carteira(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """5A — paciente cadastrado + enviar_ao_paciente=true → 201, entrega ocorre."""
    token = obter_token_prescritor(client, seed_usuario)

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pedido_exame_eventos "
            "WHERE tipo_evento = 'custodia_transferida'"
        )
        eventos_custodia_antes = cur.fetchone()[0]

    payload = {**_PAYLOAD_BASE, "enviar_ao_paciente": True}
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["entregue_carteira"] is True
    # pedidos_exame mantém 'emitido' (não existe 'transferida_paciente' aqui —
    # exceção documentada no router linhas 324-325).
    assert body["status"] == "emitido"
    protocolo = body["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM pedido_exame_custodia c
              JOIN pedidos_exame pe ON pe.id = c.pedido_id
             WHERE pe.protocolo = %s AND c.para = 'paciente'
            """,
            (protocolo,),
        )
        assert cur.fetchone()[0] == 1, "custódia paciente não registrada"

        cur.execute(
            "SELECT COUNT(*) FROM pedido_exame_eventos "
            "WHERE tipo_evento = 'custodia_transferida'"
        )
        assert cur.fetchone()[0] == eventos_custodia_antes + 1


def test_pedido_exame_201_quando_nao_enviar_ao_paciente_sem_carteira(
    client, outer_conn, seed_usuario,
):
    """5A — paciente novo + enviar_ao_paciente=false → 201, auto-cria sem entrega."""
    token = obter_token_prescritor(client, seed_usuario)

    payload = {
        **_PAYLOAD_BASE,
        "cpf_paciente":       _CPF_PACIENTE_NOVO_5A,
        "nome_paciente":      "PACIENTE NOVO 5A",
        "enviar_ao_paciente": False,
    }
    r = client.post("/pedidos-exame", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text

    body = r.json()
    assert body["entregue_carteira"] is False
    assert body["status"] == "emitido"

    # Paciente foi auto-criado pelo helper _localizar_ou_criar_paciente.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pacientes WHERE cpf = %s",
            (_CPF_PACIENTE_NOVO_5A,),
        )
        assert cur.fetchone()[0] == 1
