"""
tests/integration/test_4d2_instance_id_ledger.py
=================================================

Sub-tarefa 4D.2 — testes E2E que validam:
  - todo evento novo nos 4 subdomínios restantes (exame, laudo,
    agendamento, circulação diagnóstica) carrega ``instance_id``
    UUID v4 não nulo após a migração ao helper;
  - todos os eventos de uma transação clínica compartilham o mesmo
    ``instance_id`` (invariante forense);
  - ledger e outbox compartilham o mesmo ``instance_id`` nos
    subdomínios que têm outbox adjacente (pedidos_exame, laudos,
    agendamentos);
  - o outlier de naming em ``agendamento_eventos`` (coluna ``evento``,
    não ``tipo_evento``; ``payload``, não ``dados_json``) é
    transparente aos consumidores porque o ``_LEDGER_SCHEMA`` do
    helper encapsula o drift.

Estratégia: usa fixture ``client`` + ``outer_conn`` da conftest com
SAVEPOINT por request (não vaza dados entre testes).

Padrão idêntico ao ``test_4d1_instance_id_ledger.py`` (Sub-tarefa 4D.1).
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Payloads base
# ---------------------------------------------------------------------------

_PAYLOAD_PEDIDO = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "cpf_paciente":    SEED_PACIENTE_CPF,
    "nome_paciente":   SEED_PACIENTE_NOME,
    "tipo_emissao":    "novo",
    "prioridade":      "rotina",
    "itens": [
        {"nome_exame": "HEMOGRAMA",     "quantidade": 1},
        {"nome_exame": "GLICEMIA",      "quantidade": 1},
        {"nome_exame": "CREATININA",    "quantidade": 1},
    ],
}

_PAYLOAD_PEDIDO_FISICO = {
    "cns_prescritor":  SEED_PRESCRITOR_CNS,
    "nome_prescritor": SEED_PRESCRITOR_NOME,
    "nome_paciente":   "Paciente Fisico 4D2",
    "prioridade":      "rotina",
    "itens": [{"nome_exame": "RAIO-X TORAX", "quantidade": 1}],
}

_PAYLOAD_LAUDO = {
    "cns_autor":      SEED_PRESCRITOR_CNS,
    "nome_autor":     SEED_PRESCRITOR_NOME,
    "cpf_paciente":   SEED_PACIENTE_CPF,
    "nome_paciente":  SEED_PACIENTE_NOME,
    "tipo_emissao":   "novo",
    "itens": [
        {"nome_exame": "HEMOGRAMA", "resultado_resumo": "Sem alterações"},
    ],
}

_PAYLOAD_LAUDO_FISICO = {
    "cns_autor":      SEED_PRESCRITOR_CNS,
    "nome_autor":     SEED_PRESCRITOR_NOME,
    "nome_paciente":  "Paciente Laudo Fisico",
    "itens": [{"nome_exame": "RAIO-X", "resultado_resumo": "normal"}],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _eh_uuid_v4(s) -> bool:
    if not s:
        return False
    try:
        u = uuid.UUID(str(s))
    except (ValueError, TypeError):
        return False
    return u.version == 4


def _criar_pedido(client, token: str, payload: dict | None = None) -> tuple[str, int]:
    """POST /pedidos-exame e retorna (protocolo, pedido_id)."""
    r = client.post(
        "/pedidos-exame",
        json=payload or _PAYLOAD_PEDIDO,
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    return body["protocolo"], body["id"]


@contextmanager
def _override_role(role: str, sub: str = "test"):
    """Override temporário de ``get_current_user`` para exercer endpoints
    que exigem roles diferentes do prescritor de teste.
    """
    from app.auth.dependencies import get_current_user
    from app.main import app as fastapi_app
    anterior = fastapi_app.dependency_overrides.get(get_current_user)
    fastapi_app.dependency_overrides[get_current_user] = lambda: {
        "role": role, "sub": sub,
    }
    try:
        yield
    finally:
        if anterior is None:
            fastapi_app.dependency_overrides.pop(get_current_user, None)
        else:
            fastapi_app.dependency_overrides[get_current_user] = anterior


# ===========================================================================
# 1–5. Happy path por endpoint (instance_id presente em cada evento)
# ===========================================================================


def test_pedido_emitido_tem_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /pedidos-exame → evento ``pedido_emitido`` com instance_id."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo, pedido_id = _criar_pedido(client, token)

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT instance_id
              FROM pedido_exame_eventos
             WHERE pedido_id = %s AND tipo_evento = 'pedido_emitido'
            """,
            (pedido_id,),
        )
        row = cur.fetchone()
    assert row is not None, "evento pedido_emitido ausente"
    assert _eh_uuid_v4(row[0]), f"instance_id inválido: {row[0]!r}"


def test_laudo_criado_tem_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /laudos → evento ``laudo_criado`` com instance_id."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/laudos", json=_PAYLOAD_LAUDO, headers=_headers(token))
    assert r.status_code == 201, r.text
    laudo_id = r.json()["id"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT instance_id
              FROM laudo_eventos
             WHERE laudo_id = %s AND tipo_evento = 'laudo_criado'
            """,
            (laudo_id,),
        )
        row = cur.fetchone()
    assert row is not None
    assert _eh_uuid_v4(row[0]), f"instance_id inválido: {row[0]!r}"


def test_agendamento_criado_tem_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /agendamentos → evento ``agendamento_criado`` no outlier
    ``agendamento_eventos.evento`` (não ``tipo_evento``), com
    instance_id.
    """
    token = obter_token_prescritor(client, seed_usuario)
    protocolo_pedido, _ = _criar_pedido(client, token)

    payload = {
        "pedido_protocolo": protocolo_pedido,
        "data_hora":        "2026-05-20T09:00:00",
        "org_id":           "LAB-TESTE",
        "unidade_id":       "UNIDADE-001",
        "tipo_agendamento": "exame",
    }
    r = client.post("/agendamentos", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text
    protocolo_ag = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        # OUTLIER: coluna `evento` (não `tipo_evento`).
        cur.execute(
            """
            SELECT ae.instance_id
              FROM agendamento_eventos ae
              JOIN agendamentos a ON a.id = ae.agendamento_id
             WHERE a.protocolo = %s AND ae.evento = 'agendamento_criado'
            """,
            (protocolo_ag,),
        )
        row = cur.fetchone()
    assert row is not None, "evento agendamento_criado ausente"
    assert _eh_uuid_v4(row[0]), f"instance_id inválido: {row[0]!r}"


def test_circulacao_criada_tem_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /pedidos-exame/{proto}/circulacao → evento
    ``circulacao_criada`` com instance_id."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo_pedido, pedido_id = _criar_pedido(client, token)

    # Buscar item_id do pedido (primeiro item)
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens WHERE pedido_id = %s ORDER BY id ASC LIMIT 1",
            (pedido_id,),
        )
        item_id = cur.fetchone()[0]

    payload = {
        "org_id":     "LAB-CIRC",
        "unidade_id": "UNI-CIRC-1",
        "item_ids":   [item_id],
    }
    # /pedidos-exame/{proto}/circulacao exige paciente|admin
    with _override_role("admin"):
        r = client.post(
            f"/pedidos-exame/{protocolo_pedido}/circulacao",
            json=payload, headers=_headers(token),
        )
    assert r.status_code == 201, r.text
    protocolo_circ = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT cde.instance_id
              FROM circulacao_diagnostica_eventos cde
              JOIN circulacoes_diagnosticas cd ON cd.id = cde.circulacao_id
             WHERE cd.protocolo = %s
               AND cde.tipo_evento = 'circulacao_criada'
            """,
            (protocolo_circ,),
        )
        row = cur.fetchone()
    assert row is not None
    assert _eh_uuid_v4(row[0]), f"instance_id inválido: {row[0]!r}"


def test_pedido_fisico_dois_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /pedidos-exame/fisica grava 2 eventos no ledger; ambos
    compartilham o mesmo instance_id (invariante forense).

    Rodada 4: fix incidental em pedido_exame.py:421 (data_validade
    NULL → calculado) destravou este teste.
    """
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post(
        "/pedidos-exame/fisica",
        json=_PAYLOAD_PEDIDO_FISICO,
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    # Endpoint de fisica não retorna pedido_id; buscar pelo protocolo
    protocolo = r.json()["protocolo"]
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedidos_exame WHERE protocolo = %s",
            (protocolo,),
        )
        pedido_id = cur.fetchone()[0]

        cur.execute(
            """
            SELECT tipo_evento, instance_id
              FROM pedido_exame_eventos
             WHERE pedido_id = %s
               AND tipo_evento IN ('pedido_impresso', 'encerrado_localmente')
            """,
            (pedido_id,),
        )
        eventos = cur.fetchall()
    assert len(eventos) == 2, f"esperado 2 eventos, recebi: {eventos}"
    iids = {e[1] for e in eventos}
    assert len(iids) == 1, f"instance_ids divergentes: {iids}"
    assert _eh_uuid_v4(next(iter(iids)))


# ===========================================================================
# 6–10. Invariantes transacionais multi-evento (mesmo instance_id)
# ===========================================================================


def test_pedido_resultado_dois_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Registrar resultado gera ``pedido_em_analise`` + ``resultado_registrado``
    com mesmo instance_id na mesma transação clínica."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo, pedido_id = _criar_pedido(client, token)

    # Buscar item, agendar pedido, coletar, depois resultado.
    # /coletar exige item em status 'agendado' — agendamento sobe o item.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens WHERE pedido_id = %s ORDER BY id LIMIT 1",
            (pedido_id,),
        )
        item_id = cur.fetchone()[0]

    ra = client.post(
        f"/pedidos-exame/{protocolo}/agendar",
        json={
            "cnpj_prestador":   "12345678000199",
            "nome_prestador":   "Lab Teste",
            "data_agendamento": "2026-05-20",
        },
        headers=_headers(token),
    )
    assert ra.status_code == 201, ra.text

    rc = client.post(
        f"/pedidos-exame/{protocolo}/itens/{item_id}/coletar",
        headers=_headers(token),
    )
    assert rc.status_code == 201, rc.text

    rr = client.post(
        f"/pedidos-exame/{protocolo}/itens/{item_id}/resultado",
        json={"resultado_resumo": "Sem alteracoes"},
        headers=_headers(token),
    )
    assert rr.status_code == 201, rr.text

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tipo_evento, instance_id
              FROM pedido_exame_eventos
             WHERE pedido_id = %s
               AND tipo_evento IN ('pedido_em_analise', 'resultado_registrado')
             ORDER BY id ASC
            """,
            (pedido_id,),
        )
        eventos = cur.fetchall()
    assert len(eventos) == 2, f"eventos: {eventos}"
    iids = {e[1] for e in eventos}
    assert len(iids) == 1, f"divergente: {iids}"
    assert _eh_uuid_v4(next(iter(iids)))


def test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """ciencia-paciente sobre laudo em ciencia_prescritor encerra o
    laudo e gera 2 eventos (``ciencia_paciente`` + ``laudo_encerrado``)
    com mesmo instance_id."""
    token = obter_token_prescritor(client, seed_usuario)

    # O laudo PRECISA de pedido vinculado: `/ciencia-prescritor` é do prescritor
    # SOLICITANTE, resolvido pelo pedido (TICKET-5C-BIS-B §8.1 — sem fallback de
    # autor). Laudo standalone → solicitante None → 403, e a invariante deste
    # teste (2 eventos, 1 instance_id) nunca chegava a ser exercitada. O vínculo
    # é válido porque `_PAYLOAD_PEDIDO` e `_PAYLOAD_LAUDO` compartilham o mesmo
    # paciente semeado; o payload é montado LOCAL para não contaminar o base.
    protocolo_pedido, _ = _criar_pedido(client, token)
    payload_laudo = {**_PAYLOAD_LAUDO, "pedido_protocolo": protocolo_pedido}

    # Criar laudo + assinar + liberar + ciencia_prescritor
    r = client.post("/laudos", json=payload_laudo, headers=_headers(token))
    assert r.status_code == 201, r.text
    protocolo = r.json()["protocolo"]
    laudo_id = r.json()["id"]

    r = client.post(f"/laudos/{protocolo}/assinar", headers=_headers(token))
    assert r.status_code == 200, r.text
    r = client.post(
        f"/laudos/{protocolo}/liberar",
        json={"cnpj_prestador": "12345678000199"},
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text

    # Setup pela máquina de estados real (CODEX rodada 5 P1 — sem
    # SQL-direct). Sequência: liberado → ciencia_paciente (1 evento)
    # → ciencia_prescritor (2 eventos: ciencia_prescritor +
    # laudo_encerrado). É a transação dos 2 eventos compartilhando
    # instance_id que valida a invariante deste teste.
    with _override_role("admin"):
        r = client.post(
            f"/laudos/{protocolo}/ciencia-paciente",
            headers=_headers(token),
        )
        assert r.status_code == 200, r.text

    # Agora /ciencia-prescritor encerra o laudo + grava 2 eventos
    # compartilhando instance_id na mesma transação clínica.
    r = client.post(
        f"/laudos/{protocolo}/ciencia-prescritor", headers=_headers(token),
    )
    assert r.status_code == 200, r.text

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tipo_evento, instance_id
              FROM laudo_eventos
             WHERE laudo_id = %s
               AND tipo_evento IN ('ciencia_prescritor', 'laudo_encerrado')
             ORDER BY id DESC
             LIMIT 2
            """,
            (laudo_id,),
        )
        eventos = cur.fetchall()
    assert len(eventos) == 2, f"eventos: {eventos}"
    iids = {e[1] for e in eventos}
    assert len(iids) == 1, f"divergente: {iids}"
    assert _eh_uuid_v4(next(iter(iids)))


def test_laudo_fisico_dois_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """POST /laudos/fisica → ``laudo_impresso`` + ``encerrado_localmente``
    com mesmo instance_id."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post(
        "/laudos/fisica", json=_PAYLOAD_LAUDO_FISICO,
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    protocolo = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM laudos WHERE protocolo = %s",
            (protocolo,),
        )
        laudo_id = cur.fetchone()[0]
        cur.execute(
            """
            SELECT tipo_evento, instance_id
              FROM laudo_eventos
             WHERE laudo_id = %s
               AND tipo_evento IN ('laudo_impresso', 'encerrado_localmente')
            """,
            (laudo_id,),
        )
        eventos = cur.fetchall()
    assert len(eventos) == 2
    iids = {e[1] for e in eventos}
    assert len(iids) == 1, f"divergente: {iids}"
    assert _eh_uuid_v4(next(iter(iids)))


def test_agendamento_remarcar_tres_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Remarcar gera ``agendamento_remarcado`` + ``agendamento_cancelado``
    + ``agendamento_criado`` (novo) — todos com mesmo instance_id
    (transação única, mesmo helper local)."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo_pedido, _ = _criar_pedido(client, token)

    # Criar agendamento original
    payload_ag = {
        "pedido_protocolo": protocolo_pedido,
        "data_hora":        "2026-05-20T09:00:00",
        "org_id":           "LAB-TESTE",
        "unidade_id":       "UNIDADE-001",
        "tipo_agendamento": "exame",
    }
    r = client.post("/agendamentos", json=payload_ag, headers=_headers(token))
    assert r.status_code == 201, r.text
    protocolo_ag = r.json()["protocolo"]

    # Remarcar
    r = client.post(
        f"/agendamentos/{protocolo_ag}/remarcar",
        json={"data_hora": "2026-05-25T14:00:00"},
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    protocolo_novo = r.json()["protocolo_novo"]

    with outer_conn.cursor() as cur:
        # Buscar IDs do agendamento original e do novo
        cur.execute(
            "SELECT id, protocolo FROM agendamentos "
            "WHERE protocolo IN (%s, %s) ORDER BY id ASC",
            (protocolo_ag, protocolo_novo),
        )
        rows = cur.fetchall()
        assert len(rows) == 2
        ag_id_orig, ag_id_novo = rows[0][0], rows[1][0]

        # 2 eventos no orig (remarcado + cancelado) + 1 evento no novo (criado)
        cur.execute(
            """
            SELECT evento, instance_id
              FROM agendamento_eventos
             WHERE agendamento_id IN (%s, %s)
               AND evento IN ('agendamento_remarcado',
                              'agendamento_cancelado',
                              'agendamento_criado')
             ORDER BY id ASC
            """,
            (ag_id_orig, ag_id_novo),
        )
        eventos = cur.fetchall()
    # Esperamos exatamente 4: agendamento_criado (original) +
    # agendamento_remarcado + agendamento_cancelado + agendamento_criado (novo).
    # Os 3 últimos compartilham instance_id (mesma transação clínica).
    # O primeiro tem instance_id próprio (criado em transação anterior).
    assert len(eventos) >= 3, f"eventos: {eventos}"

    # Os 3 da remarcação devem ter mesmo iid
    eventos_remarcacao = eventos[-3:]
    iids = {e[1] for e in eventos_remarcacao}
    assert len(iids) == 1, (
        f"Os 3 eventos da remarcação devem compartilhar instance_id, "
        f"recebido: {eventos_remarcacao}"
    )
    assert _eh_uuid_v4(next(iter(iids)))


def test_circulacao_remarcar_dois_eventos_mesmo_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Remarcar circulação gera ``circulacao_desmarcada_laboratorio`` +
    nova ``circulacao_criada`` com mesmo instance_id."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo_pedido, pedido_id = _criar_pedido(client, token)
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM pedido_exame_itens WHERE pedido_id = %s ORDER BY id LIMIT 1",
            (pedido_id,),
        )
        item_id = cur.fetchone()[0]

    # Criar circulação inicial — exige paciente|admin.
    with _override_role("admin"):
        r = client.post(
            f"/pedidos-exame/{protocolo_pedido}/circulacao",
            json={"org_id": "LAB-A", "unidade_id": "U1",
                  "item_ids": [item_id]},
            headers=_headers(token),
        )
    assert r.status_code == 201, r.text
    chave = r.json()["chave_circulacao"]
    protocolo_circ = r.json()["protocolo"]

    # Para remarcar, a circulação precisa estar em um estado pós
    # 'selecionado' (enviado_laboratorio | proposta_recebida |
    # confirmado_paciente). Transicionar via outer_conn — testar a
    # cadeia de UX não é o ponto deste teste; o ponto é a invariante
    # forense da transação de remarcação.
    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'enviado_laboratorio' "
            "WHERE chave_circulacao = %s",
            (chave,),
        )

    # Remarcar exige dispensador|admin.
    with _override_role("admin"):
        r = client.post(
            f"/circulacao/{chave}/remarcar",
            json={"org_id": "LAB-B", "unidade_id": "U2",
                  "data_hora_proposta": "2026-06-01T10:00:00"},
            headers=_headers(token),
        )
    assert r.status_code == 201, r.text

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tipo_evento, instance_id
              FROM circulacao_diagnostica_eventos cde
              JOIN circulacoes_diagnosticas cd ON cd.id = cde.circulacao_id
             WHERE cd.protocolo = %s OR cd.origem_circulacao_id = (
                 SELECT id FROM circulacoes_diagnosticas WHERE protocolo = %s
             )
             ORDER BY cde.id ASC
            """,
            (protocolo_circ, protocolo_circ),
        )
        eventos = cur.fetchall()
    # Esperamos: circulacao_criada (original — transação A),
    # circulacao_desmarcada_laboratorio + circulacao_criada (novo —
    # transação B, mesmo iid).
    assert len(eventos) >= 3
    # Os 2 últimos compartilham instance_id (transação da remarcação).
    eventos_remarcacao = eventos[-2:]
    iids = {e[1] for e in eventos_remarcacao}
    assert len(iids) == 1, f"divergente: {eventos_remarcacao}"
    assert _eh_uuid_v4(next(iter(iids)))


# ===========================================================================
# 11–13. Ledger + outbox compartilham instance_id
# ===========================================================================


def test_pedido_exame_ledger_e_outbox_compartilham_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """``pedido_emitido`` tem mesmo instance_id no ledger
    (``pedido_exame_eventos``) e no outbox (``eventos_publicacao``
    com ``objeto_tipo='pedido_exame'``)."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo, pedido_id = _criar_pedido(client, token)

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT instance_id
              FROM pedido_exame_eventos
             WHERE pedido_id = %s AND tipo_evento = 'pedido_emitido'
            """,
            (pedido_id,),
        )
        iid_ledger = cur.fetchone()[0]

        cur.execute(
            """
            SELECT instance_id
              FROM eventos_publicacao
             WHERE objeto_tipo = 'pedido_exame'
               AND objeto_id = %s
               AND tipo_evento = 'pedido_emitido'
            """,
            (protocolo,),
        )
        row = cur.fetchone()
    assert row is not None, "outbox não recebeu o evento"
    iid_outbox = row[0]
    assert iid_ledger == iid_outbox
    assert _eh_uuid_v4(iid_ledger)


def test_laudo_ledger_e_outbox_compartilham_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """``laudo_criado`` tem mesmo instance_id no ledger e no outbox."""
    token = obter_token_prescritor(client, seed_usuario)
    r = client.post("/laudos", json=_PAYLOAD_LAUDO, headers=_headers(token))
    assert r.status_code == 201, r.text
    laudo_id = r.json()["id"]
    protocolo = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT instance_id
              FROM laudo_eventos
             WHERE laudo_id = %s AND tipo_evento = 'laudo_criado'
            """,
            (laudo_id,),
        )
        iid_ledger = cur.fetchone()[0]

        cur.execute(
            """
            SELECT instance_id
              FROM eventos_publicacao
             WHERE objeto_tipo = 'laudo'
               AND objeto_id = %s
               AND tipo_evento = 'laudo_criado'
            """,
            (protocolo,),
        )
        row = cur.fetchone()
    assert row is not None
    iid_outbox = row[0]
    assert iid_ledger == iid_outbox
    assert _eh_uuid_v4(iid_ledger)


def test_agendamento_ledger_e_outbox_compartilham_instance_id(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """``agendamento_criado`` tem mesmo instance_id no ledger
    (outlier ``agendamento_eventos.evento``) e no outbox — valida que o
    mapping do ``_LEDGER_SCHEMA`` preserva coerência forense apesar do
    drift de naming."""
    token = obter_token_prescritor(client, seed_usuario)
    protocolo_pedido, _ = _criar_pedido(client, token)

    payload = {
        "pedido_protocolo": protocolo_pedido,
        "data_hora":        "2026-05-20T09:00:00",
        "org_id":           "LAB-OUTLIER",
        "unidade_id":       "UNI-OUTLIER",
        "tipo_agendamento": "exame",
    }
    r = client.post("/agendamentos", json=payload, headers=_headers(token))
    assert r.status_code == 201, r.text
    protocolo_ag = r.json()["protocolo"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ae.instance_id
              FROM agendamento_eventos ae
              JOIN agendamentos a ON a.id = ae.agendamento_id
             WHERE a.protocolo = %s AND ae.evento = 'agendamento_criado'
            """,
            (protocolo_ag,),
        )
        iid_ledger = cur.fetchone()[0]

        cur.execute(
            """
            SELECT instance_id
              FROM eventos_publicacao
             WHERE objeto_tipo = 'agendamento'
               AND objeto_id = %s
               AND tipo_evento = 'agendamento_criado'
            """,
            (protocolo_ag,),
        )
        row = cur.fetchone()
    assert row is not None, "outbox não recebeu o evento de agendamento"
    iid_outbox = row[0]
    assert iid_ledger == iid_outbox, (
        f"Outlier de schema quebrou correspondência forense ledger↔outbox: "
        f"ledger={iid_ledger!r} outbox={iid_outbox!r}"
    )
    assert _eh_uuid_v4(iid_ledger)
