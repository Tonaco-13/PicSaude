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


# ---------------------------------------------------------------------------
# TICKET-I.1 — o GET resolve a identidade do paciente e o laudo vigente
# ---------------------------------------------------------------------------
# `pedidos_exame` guarda `paciente_id`, não nome/CPF. A tela do laboratório
# sempre esperou os campos resolvidos (`renderizarPedido` já os procurava) e,
# sem eles, mostrava "Paciente: —" e não tinha como preencher o laudo.

def test_get_pedido_resolve_identidade_do_paciente(client, outer_conn, seed_usuario, seed_paciente):
    """AC I.1 — `paciente_nome`/`paciente_cpf` vêm resolvidos no GET."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/pedidos-exame", json=_PAYLOAD_BASE, headers=_headers(token))
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    body = client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()
    assert body["paciente_nome"] == SEED_PACIENTE_NOME
    assert body["paciente_cpf"] == SEED_PACIENTE_CPF


def test_get_pedido_sem_laudo_devolve_campos_nulos(client, outer_conn, seed_usuario, seed_paciente):
    """Ausência de laudo é `None` explícito, não campo faltando: a tela decide
    o gate do botão por este valor e não pode ter que adivinhar."""
    token = obter_token_prescritor(client, seed_usuario)
    proto = client.post(
        "/pedidos-exame", json=_PAYLOAD_BASE, headers=_headers(token)
    ).json()["protocolo"]

    body = client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()
    assert "laudo_protocolo" in body and body["laudo_protocolo"] is None
    assert "laudo_status" in body and body["laudo_status"] is None


def test_get_pedido_expoe_laudo_vigente_e_ignora_terminal(
    client, outer_conn, seed_usuario, seed_paciente
):
    """AC I.1 — o laudo vigente aparece; o CANCELADO (terminal) não.

    É esse campo que impede um segundo laudo nascer depois de um reload — e é
    por isso que ele precisa ignorar terminais: um laudo cancelado não pode
    travar a emissão do laudo bom.
    """
    token = obter_token_prescritor(client, seed_usuario)
    proto = client.post(
        "/pedidos-exame", json=_PAYLOAD_BASE, headers=_headers(token)
    ).json()["protocolo"]

    laudo = {
        "cns_autor": "987654321098765", "nome_autor": "DR. TESTE TICKET13",
        "cpf_paciente": SEED_PACIENTE_CPF, "nome_paciente": SEED_PACIENTE_NOME,
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": "HEMOGRAMA"}],
    }
    r = client.post("/laudos", json=laudo, headers=_headers(token))
    assert r.status_code == 201, r.text
    proto_laudo = r.json()["protocolo"]

    body = client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()
    assert body["laudo_protocolo"] == proto_laudo
    assert body["laudo_status"] == "em_producao"

    # Cancelado → terminal → some do campo, e o pedido volta a poder ser laudado.
    assert client.post(
        f"/laudos/{proto_laudo}/cancelar", json={"motivo": "erro"}, headers=_headers(token)
    ).status_code == 200

    body2 = client.get(f"/pedidos-exame/{proto}", headers=_headers(token)).json()
    assert body2["laudo_protocolo"] is None, "laudo cancelado não pode travar o pedido"
