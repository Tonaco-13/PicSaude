"""
tests/integration/test_custodia_devolucao.py
=============================================

Cobertura E2E focal para POST /prescricoes/{protocolo}/itens/{item_id}/devolver
(`backend/app/routers/custodia.py::devolver_item`).

Origem: TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md (achado P2-A do CODEX 4E.2).

Invariantes verificadas:
- Vocabulário canônico (CLAUDE.md §2): eventos separados
    `item_devolvido_paciente` (abandono) e `item_devolvido_prescritor` (erro clínico).
- Ator gravado no ledger vem do JWT — nunca hardcoded `"sistema"`.
- Resposta HTTP preserva o shape atual (protocolo, item_id, nome_medicamento,
    status_item, status_prescricao).
- Estado de domínio do item bate com o destino (`devolvido_paciente` /
    `devolvido_prescritor`).
- `instance_id` continua sendo um UUID v4 (marca d'água da instalação — Etapa 4).

Princípios de teste (TICKET §6, integrando P2 da rodada 1 do CODEX):
- Cada cenário monta o próprio setup.
- Asserções de ledger filtram por `prescricao_id` criado no teste — não
    consultam estado histórico do banco.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
)

_DISPENSADOR_CNPJ = "12345678000195"
_DISPENSADOR_NOME = "DROGARIA TESTE 4E2"


# ---------------------------------------------------------------------------
# Helpers locais (não criar fixtures globais — TICKET §6.5)
# ---------------------------------------------------------------------------

def _jwt_dispensador() -> str:
    return criar_access_token(
        sub=_DISPENSADOR_CNPJ, role="dispensador", nome=_DISPENSADOR_NOME,
    )


def _jwt_prescritor() -> str:
    return criar_access_token(
        sub=SEED_PRESCRITOR_CNS, role="prescritor", nome=SEED_PRESCRITOR_NOME,
    )


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _eh_uuid_v4(s) -> bool:
    if not s:
        return False
    try:
        return uuid.UUID(str(s)).version == 4
    except (ValueError, TypeError):
        return False


def _seed_prescricao_com_itens_em_custodia(outer_conn, num_itens: int = 1):
    """
    Seed mínimo: prescrição em `em_custodia`, itens em `em_custodia`,
    custódia ativa do dispensador (prescrição inteira + cada item).

    Roda no outer tx (`outer_conn`). As inserções ficam visíveis aos
    savepoints abertos pelo TestClient e somem no rollback do teardown.

    Retorna: (prescricao_id, protocolo, [item_id, ...]).
    """
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-DEV-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) "
            "ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) "
            "ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s)
            RETURNING id
            """,
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_custodia
              (prescricao_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (%s, NULL, 'dispensador', %s, %s, NULL, 'seed_test', %s)
            """,
            (prescricao_id, _DISPENSADOR_CNPJ, now, now),
        )
        item_ids: list[int] = []
        for i in range(num_itens):
            cur.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   posologia, status_item, created_at, updated_at)
                VALUES (%s, %s, '500mg', 10, '1cp 8/8h', 'em_custodia', %s, %s)
                RETURNING id
                """,
                (prescricao_id, f"MEDICAMENTO_TESTE_{i + 1}", now, now),
            )
            item_id = cur.fetchone()[0]
            item_ids.append(item_id)
            cur.execute(
                """
                INSERT INTO prescricao_custodia
                  (prescricao_id, item_id, detentor_tipo, detentor_id,
                   transferida_em, encerrada_em, motivo, created_at)
                VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed_test', %s)
                """,
                (prescricao_id, item_id, _DISPENSADOR_CNPJ, now, now),
            )
    return prescricao_id, proto, item_ids


def _ler_ultimo_evento_devolucao(outer_conn, prescricao_id: int) -> dict:
    """Retorna o evento de devolução mais recente da prescrição criada no teste."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT tipo_evento, ator_tipo, ator_id, payload_json, instance_id
              FROM prescricao_eventos
             WHERE prescricao_id = %s
               AND tipo_evento LIKE 'item_devolvido%%'
             ORDER BY id DESC LIMIT 1
            """,
            (prescricao_id,),
        )
        row = cur.fetchone()
    assert row is not None, (
        f"Evento de devolução não encontrado para prescricao_id={prescricao_id}"
    )
    return {
        "tipo_evento": row[0],
        "ator_tipo":   row[1],
        "ator_id":     row[2],
        "payload":     json.loads(row[3]) if row[3] else {},
        "instance_id": row[4],
    }


# ---------------------------------------------------------------------------
# C1 — Devolução ao paciente (abandono)
# ---------------------------------------------------------------------------

def test_devolver_item_ao_paciente_dispensador(client, outer_conn):
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "paciente", "motivo": "abandono no balcão"},
        headers=_headers(_jwt_dispensador()),
    )

    # Resposta HTTP — shape preservado (sem breaking change para o frontend).
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["protocolo"] == proto
    assert body["item_id"] == item_id
    assert body["status_item"] == "devolvido_paciente"
    assert "nome_medicamento" in body
    assert "status_prescricao" in body

    # Estado de domínio do item.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == "devolvido_paciente"

    # Ledger — filtrado por prescricao_id deste teste.
    ev = _ler_ultimo_evento_devolucao(outer_conn, prescricao_id)
    assert ev["tipo_evento"] == "item_devolvido_paciente"
    assert ev["ator_tipo"]   == "dispensador"
    assert ev["ator_id"]     == _DISPENSADOR_CNPJ
    assert ev["ator_id"]     != "sistema"
    assert _eh_uuid_v4(ev["instance_id"])
    assert ev["payload"]["devolvido_para"]   == "paciente"
    assert ev["payload"]["motivo"]           == "abandono no balcão"
    assert ev["payload"]["novo_status_item"] == "devolvido_paciente"
    assert ev["payload"]["item_id"]          == item_id


# ---------------------------------------------------------------------------
# C2 — Devolução ao prescritor (erro clínico)
# ---------------------------------------------------------------------------

def test_devolver_item_ao_prescritor_dispensador(client, outer_conn):
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "prescritor", "motivo": "dose inadequada — paciente pediátrico"},
        headers=_headers(_jwt_dispensador()),
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["protocolo"] == proto
    assert body["item_id"] == item_id
    assert body["status_item"] == "devolvido_prescritor"
    assert "nome_medicamento" in body
    assert "status_prescricao" in body

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == "devolvido_prescritor"

    ev = _ler_ultimo_evento_devolucao(outer_conn, prescricao_id)
    assert ev["tipo_evento"] == "item_devolvido_prescritor"
    assert ev["ator_tipo"]   == "dispensador"
    assert ev["ator_id"]     == _DISPENSADOR_CNPJ
    assert ev["ator_id"]     != "sistema"
    assert _eh_uuid_v4(ev["instance_id"])
    assert ev["payload"]["devolvido_para"]   == "prescritor"
    assert ev["payload"]["novo_status_item"] == "devolvido_prescritor"


# ---------------------------------------------------------------------------
# C3 — Ator = prescritor (quando o próprio prescritor opera o endpoint)
# ---------------------------------------------------------------------------

def test_devolver_item_ator_prescritor(client, outer_conn):
    """
    `require_role("dispensador", "prescritor")` aceita ambos. Quando o ator
    é prescritor, o evento deve refletir `ator_tipo='prescritor'` e
    `ator_id=<CNS do JWT>`, não `"sistema"`.

    Testamos com `payload.para='paciente'` como caso representativo —
    o cruzamento exaustivo payload.para × role já é coberto em C1/C2.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "paciente", "motivo": "reversão pelo próprio prescritor"},
        headers=_headers(_jwt_prescritor()),
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["protocolo"]   == proto
    assert body["item_id"]     == item_id
    assert body["status_item"] == "devolvido_paciente"
    assert "nome_medicamento" in body
    assert "status_prescricao" in body

    # Estado de domínio
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == "devolvido_paciente"

    ev = _ler_ultimo_evento_devolucao(outer_conn, prescricao_id)
    assert ev["tipo_evento"] == "item_devolvido_paciente"
    assert ev["ator_tipo"]   == "prescritor"
    assert ev["ator_id"]     == SEED_PRESCRITOR_CNS
    assert ev["ator_id"]     != "sistema"
    assert _eh_uuid_v4(ev["instance_id"])


# ---------------------------------------------------------------------------
# C4 — Regressão de vocabulário (próprio setup, sem acoplamento por ordem)
# ---------------------------------------------------------------------------

def test_devolver_item_nunca_grava_tipo_evento_generico(client, outer_conn):
    """
    Garante que o endpoint nunca grava `tipo_evento='item_devolvido'` (sem
    sufixo). Vocabulário canônico CLAUDE.md §2: apenas
    `item_devolvido_paciente` e `item_devolvido_prescritor`.

    Setup próprio (2 itens), uma devolução de cada tipo, filtro estrito
    pelo `prescricao_id` deste teste — não consulta estado histórico do
    banco, então rows pré-correção (se houver) não geram falso positivo.
    """
    prescricao_id, proto, [item_a, item_b] = _seed_prescricao_com_itens_em_custodia(
        outer_conn, num_itens=2,
    )
    headers = _headers(_jwt_dispensador())

    r1 = client.post(
        f"/prescricoes/{proto}/itens/{item_a}/devolver",
        json={"para": "paciente", "motivo": "abandono"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["protocolo"]   == proto
    assert body1["item_id"]     == item_a
    assert body1["status_item"] == "devolvido_paciente"

    r2 = client.post(
        f"/prescricoes/{proto}/itens/{item_b}/devolver",
        json={"para": "prescritor", "motivo": "erro clínico"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    body2 = r2.json()
    assert body2["protocolo"]   == proto
    assert body2["item_id"]     == item_b
    assert body2["status_item"] == "devolvido_prescritor"

    # Estado de domínio dos 2 itens
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id, status_item FROM prescricao_itens "
            "WHERE id IN (%s, %s) ORDER BY id",
            (item_a, item_b),
        )
        estados = {row[0]: row[1] for row in cur.fetchall()}
        assert estados[item_a] == "devolvido_paciente"
        assert estados[item_b] == "devolvido_prescritor"

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT tipo_evento
              FROM prescricao_eventos
             WHERE prescricao_id = %s
               AND tipo_evento LIKE 'item_devolvido%%'
            """,
            (prescricao_id,),
        )
        tipos = {row[0] for row in cur.fetchall()}

    assert "item_devolvido" not in tipos, (
        f"Evento genérico 'item_devolvido' foi gravado no prescricao_id={prescricao_id} "
        "— viola CLAUDE.md §2"
    )
    assert tipos == {"item_devolvido_paciente", "item_devolvido_prescritor"}, (
        f"Vocabulário inesperado: {tipos - {'item_devolvido_paciente', 'item_devolvido_prescritor'}}"
    )
