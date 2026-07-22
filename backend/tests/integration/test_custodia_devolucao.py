"""
tests/integration/test_custodia_devolucao.py
=============================================

Cobertura E2E focal para POST /prescricoes/{protocolo}/itens/{item_id}/devolver
(`backend/app/routers/custodia.py::devolver_item`).

Origem: TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md (achado P2-A do CODEX 4E.2).
T1 (PLANO_DEMO_CIRCULACAO.md, 2026-07-05): devolução ao paciente reabre
custódia — ver seção "T1" ao final do arquivo.

Invariantes verificadas:
- Vocabulário canônico (CLAUDE.md §2): eventos separados
    `item_devolvido_paciente` (abandono) e `item_devolvido_prescritor` (erro clínico).
- Ator gravado no ledger vem do JWT — nunca hardcoded `"sistema"`.
- Resposta HTTP preserva o shape atual (protocolo, item_id, nome_medicamento,
    status_item, status_prescricao).
- Estado de domínio do item bate com o destino (`devolvido_paciente` /
    `devolvido_prescritor`).
- `instance_id` continua sendo um UUID v4 (marca d'água da instalação — Etapa 4).
- (T1) Devolução ao paciente abre nova custódia em seu nome — CLAUDE.md §3
    ("cada prescrição tem um detentor de custódia a cada momento"). Devolução
    ao prescritor NÃO reabre custódia aqui — fora do escopo do T1, ver
    TICKET-COERENCIA-DEVOLUCOES.md.

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

# T1 — segunda farmácia (mesmo CNPJ do seed T0.5/seed_demo.py) para os
# cenários de re-apresentação. Independente do seed: o teste cria seu
# próprio JWT e custódia, não depende de seed_demo.py ter rodado.
_DISPENSADOR_CNPJ_NORTE = "99999999000272"
_DISPENSADOR_NOME_NORTE = "Farmácia Demo Norte"


# ---------------------------------------------------------------------------
# Helpers locais (não criar fixtures globais — TICKET §6.5)
# ---------------------------------------------------------------------------

def _jwt_dispensador() -> str:
    return criar_access_token(
        sub=_DISPENSADOR_CNPJ, role="dispensador", nome=_DISPENSADOR_NOME,
    )


def _jwt_dispensador_norte() -> str:
    return criar_access_token(
        sub=_DISPENSADOR_CNPJ_NORTE, role="dispensador", nome=_DISPENSADOR_NOME_NORTE,
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


# ---------------------------------------------------------------------------
# T1 — Devolução ao paciente reabre custódia (PLANO_DEMO_CIRCULACAO.md)
# ---------------------------------------------------------------------------
#
# Antes do T1, `_fechar_custodia_ativa` fechava a custódia do item na
# devolução mas nunca abria uma nova em nome do paciente — o item ficava
# sem detentor entre a devolução e a próxima apresentação, violando
# CLAUDE.md §3 ("cada prescrição tem um detentor de custódia a cada
# momento"). Estes testes cobrem a reabertura e o ciclo completo de
# re-apresentação em outra farmácia que ela habilita.

def _custodia_ativa_item(outer_conn, prescricao_id: int, item_id: int):
    """Linha de custódia ATIVA (encerrada_em IS NULL) do item, ou None."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT detentor_tipo, detentor_id
              FROM prescricao_custodia
             WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NULL
            """,
            (prescricao_id, item_id),
        )
        row = cur.fetchone()
    return None if row is None else {"detentor_tipo": row[0], "detentor_id": row[1]}


def _custodias_encerradas_do_item(outer_conn, prescricao_id: int, item_id: int) -> int:
    """Conta quantas linhas de custódia do item já estão encerradas."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM prescricao_custodia
             WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NOT NULL
            """,
            (prescricao_id, item_id),
        )
        return cur.fetchone()[0]


def test_devolver_item_ao_paciente_reabre_custodia_do_paciente(client, outer_conn):
    """
    T1 — depois de `devolver(para=paciente)`, a custódia ativa do item passa
    a ser do paciente (CPF do seed, normalizado) e a custódia anterior do
    dispensador aparece encerrada — nenhum momento sem detentor.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    assert _custodias_encerradas_do_item(outer_conn, prescricao_id, item_id) == 0

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "paciente", "motivo": "abandono no balcão"},
        headers=_headers(_jwt_dispensador()),
    )
    assert r.status_code == 200, r.text

    ativa = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ativa is not None, "item ficou sem detentor de custódia após devolução — viola CLAUDE.md §3"
    assert ativa["detentor_tipo"] == "paciente"
    assert ativa["detentor_id"] == SEED_PACIENTE_CPF

    # A custódia anterior (dispensador, seedada em _seed_prescricao_com_itens_em_custodia)
    # deve estar encerrada — não duas custódias ativas simultâneas.
    assert _custodias_encerradas_do_item(outer_conn, prescricao_id, item_id) == 1


def test_devolver_item_ao_prescritor_nao_reabre_custodia_do_paciente(client, outer_conn):
    """
    Guarda de escopo: devolução ao PRESCRITOR não deve abrir custódia do
    paciente (T1 é escopado só ao ramo para=paciente — ver
    TICKET-COERENCIA-DEVOLUCOES.md para o ramo prescritor). Este teste
    trava caso um refactor futuro generalize a reabertura incorretamente.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "prescritor", "motivo": "dose inadequada"},
        headers=_headers(_jwt_dispensador()),
    )
    assert r.status_code == 200, r.text

    ativa = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ativa is None, (
        f"devolução ao prescritor abriu custódia inesperada: {ativa} "
        "— fora do escopo do T1"
    )


def test_devolucao_e_redispensacao_parcial_em_outra_farmacia_transfere_custodia(client, outer_conn):
    """
    Ciclo completo do §1 do PLANO_DEMO_CIRCULACAO.md, no recorte do item:
    dispensação parcial (farmácia A) → devolução (custódia volta ao
    paciente) → re-apresentação com nova dispensação parcial (farmácia B,
    T0.5) → custódia ativa passa a ser da farmácia B, nunca voltando a
    ficar "presa" no paciente.

    Cobre também o ajuste em `dispensar_item`: sem ele, o ramo de
    dispensação parcial só abre custódia "se não houver nenhuma ativa" —
    e depois do T1 pode haver uma ativa (do paciente) que precisa ser
    fechada, não apenas ignorada.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    # Farmácia A dispensa parcialmente (4 de 10) — custódia continua com A
    # (mesmo detentor da custódia seedada; não deve haver churn).
    r1 = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 4},
        headers=_headers(_jwt_dispensador()),
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["saldo_restante"] == 6

    ativa_pos_dispensa_a = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ativa_pos_dispensa_a == {"detentor_tipo": "dispensador", "detentor_id": _DISPENSADOR_CNPJ}

    # Paciente abandona o restante na farmácia A — custódia volta ao paciente (T1).
    r2 = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "paciente", "motivo": "vai tentar em outra farmácia"},
        headers=_headers(_jwt_dispensador()),
    )
    assert r2.status_code == 200, r2.text
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == {
        "detentor_tipo": "paciente", "detentor_id": SEED_PACIENTE_CPF,
    }

    # T1.5 — re-apresentação na Farmácia B: a retenção é pré-requisito da
    # dispensação (o dispensador precisa DETER o item). Modela o passo que a
    # demo faz por auto-retenção: o paciente apresenta a receita em B, custódia
    # paciente→B. Sem isto, o T1.5 (corretamente) rejeitaria a dispensação de B.
    _reapresentar = datetime.utcnow().isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            "UPDATE prescricao_custodia SET encerrada_em = %s "
            "WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NULL",
            (_reapresentar, prescricao_id, item_id),
        )
        cur.execute(
            "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, "
            "detentor_id, transferida_em, encerrada_em, motivo, created_at) "
            "VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'reapresentacao', %s)",
            (prescricao_id, item_id, _DISPENSADOR_CNPJ_NORTE, _reapresentar, _reapresentar),
        )

    # Farmácia B (T0.5) dispensa parte do saldo remanescente (3 de 6).
    r3 = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ_NORTE, "quantidade_dispensada": 3},
        headers=_headers(_jwt_dispensador_norte()),
    )
    assert r3.status_code == 201, r3.text
    assert r3.json()["saldo_restante"] == 3
    assert r3.json()["status_item"] == "em_custodia"

    # Custódia ativa agora é da farmácia B — a do paciente foi encerrada,
    # não apenas ignorada (é o que o ajuste em dispensar_item garante).
    ativa_pos_dispensa_b = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ativa_pos_dispensa_b == {
        "detentor_tipo": "dispensador", "detentor_id": _DISPENSADOR_CNPJ_NORTE,
    }

    # Farmácia B dispensa o saldo final — item chega a estado terminal e a
    # custódia é encerrada (item entregue não tem mais detentor a rastrear).
    r4 = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ_NORTE, "quantidade_dispensada": 3},
        headers=_headers(_jwt_dispensador_norte()),
    )
    assert r4.status_code == 201, r4.text
    assert r4.json()["saldo_restante"] == 0
    assert r4.json()["status_item"] == "dispensado"
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) is None


# ---------------------------------------------------------------------------
# Condição vinculante do Conselheiro (PR #76, docs/PARECER_PR76_T1.md) —
# custódia ativa de OUTRO dispensador não pode ser assumida silenciosamente
# em `dispensar_item`.
# ---------------------------------------------------------------------------

def _seed_prescricao_com_custodia_prescricao_inteira(outer_conn, num_itens: int = 1):
    """
    Seed mínimo: prescrição em `em_custodia`, itens em `em_custodia`, mas
    custódia ativa registrada APENAS no nível de prescrição inteira
    (item_id IS NULL) — o formato que a apresentação padrão no balcão
    (`transferir_custodia`, paciente → dispensador) realmente produz.
    Ao contrário de `_seed_prescricao_com_itens_em_custodia`, nenhuma linha
    de custódia por item é seedada aqui — é exatamente a lacuna de
    granularidade que o adendo (d2) do parecer cobre.

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
            item_ids.append(cur.fetchone()[0])
            # Sem INSERT em prescricao_custodia por item — só a de prescrição
            # inteira acima, de propósito.
    return prescricao_id, proto, item_ids


def test_dispensar_item_retido_por_custodia_de_prescricao_inteira_retorna_409(client, outer_conn):
    """
    Cenário (d2) do parecer: Farmácia A retém a custódia da PRESCRIÇÃO
    INTEIRA (item_id IS NULL) — o formato real da apresentação padrão no
    balcão — sem nunca ter dispensado nada. Farmácia B tenta dispensar um
    item específico — deve ser bloqueado com 409, não assumir a custódia
    através da lacuna de granularidade (item_id = ? não pega item_id IS NULL).
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_custodia_prescricao_inteira(outer_conn)

    # Confere o setup: custódia ativa é da prescrição inteira, nada no nível de item.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT detentor_tipo, detentor_id FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (prescricao_id,),
        )
        ativa_prescricao = cur.fetchone()
    assert ativa_prescricao == ("dispensador", _DISPENSADOR_CNPJ)
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) is None

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ_NORTE, "quantidade_dispensada": 3},
        headers=_headers(_jwt_dispensador_norte()),
    )

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["codigo"] == "item_retido_por_outro_estabelecimento"

    # Custódia da farmácia A (nível prescrição inteira) permanece intacta.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT detentor_tipo, detentor_id FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (prescricao_id,),
        )
        assert cur.fetchone() == ("dispensador", _DISPENSADOR_CNPJ)

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM dispensacoes WHERE prescricao_item_id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == 0


def test_dispensar_item_retido_por_outra_farmacia_retorna_409(client, outer_conn):
    """
    Cenário (d) do parecer: Farmácia A retém a custódia ativa do item (sem
    dispensar nada) e Farmácia B tenta dispensar — deve ser bloqueado com
    409 (`item_retido_por_outro_estabelecimento`), não assumir a custódia
    silenciosamente.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    # Farmácia A já detém a custódia ativa do item (seed) e não dispensou nada.
    ativa_antes = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ativa_antes == {"detentor_tipo": "dispensador", "detentor_id": _DISPENSADOR_CNPJ}

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ_NORTE, "quantidade_dispensada": 3},
        headers=_headers(_jwt_dispensador_norte()),
    )

    assert r.status_code == 409, r.text
    assert r.json()["detail"]["codigo"] == "item_retido_por_outro_estabelecimento"

    # Custódia da farmácia A permanece intacta — nenhuma tomada silenciosa.
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == ativa_antes

    # Nenhuma dispensação foi registrada — o guard corta antes de qualquer mutação.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM dispensacoes WHERE prescricao_item_id = %s", (item_id,),
        )
        assert cur.fetchone()[0] == 0


# ---------------------------------------------------------------------------
# T (PLANO_DEMO_CIRCULACAO): a devolução volta a ser VISÍVEL ao prescritor
#
# Fecha o loop de circulação da receita: um item devolvido ao prescritor
# (erro clínico) precisa reaparecer no painel do médico via
# GET /prescritor/prescricoes — backend como fonte de verdade, substituindo a
# leitura de localStorage no prescritor.html. Escopo por CNS = `sub` do JWT.
# ---------------------------------------------------------------------------

def test_prescritor_ve_devolucao_no_painel(client, outer_conn):
    """Item devolvido ao prescritor reaparece no histórico E na caixa de correções."""
    prescricao_id, proto, item_ids = _seed_prescricao_com_itens_em_custodia(
        outer_conn, num_itens=2,
    )
    item_devolvido, item_intacto = item_ids

    # Dispensador devolve UM item ao prescritor (erro clínico).
    r = client.post(
        f"/prescricoes/{proto}/itens/{item_devolvido}/devolver",
        json={"para": "prescritor", "motivo": "dose inadequada — paciente pediátrico"},
        headers=_headers(_jwt_dispensador()),
    )
    assert r.status_code == 200, r.text

    # O prescritor consulta seu painel.
    r = client.get("/prescritor/prescricoes", headers=_headers(_jwt_prescritor()))
    assert r.status_code == 200, r.text
    body = r.json()

    protos_hist = {p["protocolo"] for p in body["historico"]}
    protos_corr = {p["protocolo"] for p in body["correcoes"]}
    assert proto in protos_hist, "prescrição sumiu do histórico do prescritor"
    assert proto in protos_corr, "devolução não apareceu na caixa de correções"

    # id real presente (para reemissão com origem_prescricao_id) e status do
    # item refletindo a devolução; o item intacto permanece em_custodia.
    pres = next(p for p in body["historico"] if p["protocolo"] == proto)
    assert pres["id"] == prescricao_id
    assert pres["tem_devolucao"] is True
    status_por_id = {i["id"]: i["status_item"] for i in pres["itens"]}
    assert status_por_id[item_devolvido] == "devolvido_prescritor"
    assert status_por_id[item_intacto] == "em_custodia"

    # Motivo da recusa vem do ledger — o médico precisa saber por que corrigir.
    item_dev = next(i for i in pres["itens"] if i["id"] == item_devolvido)
    assert item_dev["motivo_devolucao"] == "dose inadequada — paciente pediátrico"


def test_painel_prescritor_isolado_por_cns(client, outer_conn):
    """RBAC: um prescritor só enxerga as próprias prescrições (escopo por CNS = sub)."""
    _, proto, _ = _seed_prescricao_com_itens_em_custodia(outer_conn, num_itens=1)

    token_outro = criar_access_token(
        sub="111222333444555", role="prescritor", nome="DR. OUTRO PRESCRITOR",
    )
    r = client.get("/prescritor/prescricoes", headers=_headers(token_outro))
    assert r.status_code == 200, r.text
    protos = {p["protocolo"] for p in r.json()["historico"]}
    assert proto not in protos, "vazou prescrição de outro prescritor — escopo por CNS falhou"


def _seed_correcao(outer_conn, origem_id: int):
    """Seed direto de uma prescrição-filha de correção derivando de `origem_id`."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-CORR-{uuid.uuid4().hex[:10]}"
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
               origem_prescricao_id, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', 'correcao', %s, %s, %s, %s)
            RETURNING id
            """,
            (proto, pres_id, pac_id, origem_id, now, now, now),
        )
        nova_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               posologia, status_item, created_at, updated_at)
            VALUES (%s, 'MEDICAMENTO_CORRIGIDO', '250mg', 10, '1cp 12/12h', 'pendente', %s, %s)
            """,
            (nova_id, now, now),
        )
    return nova_id, proto


def test_caixa_correcao_limpa_apos_correcao_emitida(client, outer_conn):
    """Devolução sai da caixa quando a correção derivada é emitida (permanece no histórico)."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "prescritor", "motivo": "erro de dose"},
        headers=_headers(_jwt_dispensador()),
    )
    assert r.status_code == 200, r.text

    # Antes da correção: aparece na caixa de correções.
    body = client.get("/prescritor/prescricoes", headers=_headers(_jwt_prescritor())).json()
    assert proto in {p["protocolo"] for p in body["correcoes"]}

    # Emite a correção derivada (origem = prescrição devolvida).
    _seed_correcao(outer_conn, origem_id=prescricao_id)

    # Depois: some da caixa (foi tratada), mas permanece no histórico.
    body = client.get("/prescritor/prescricoes", headers=_headers(_jwt_prescritor())).json()
    assert proto not in {p["protocolo"] for p in body["correcoes"]}, "caixa não limpou após correção"
    assert proto in {p["protocolo"] for p in body["historico"]}


# ---------------------------------------------------------------------------
# B1 — dispensar_item devolve dispensacao_id (PLANO_DEMO_CIRCULACAO.md, T5)
# ---------------------------------------------------------------------------
#
# Sem o id da dispensação na resposta, o balcão não tinha como linkar o
# comprovante (GET /dispensacoes/{id}/comprovante) logo após dispensar —
# tinha que "adivinhar" o id por outra via. Estes testes travam o contrato:
# a resposta traz `dispensacao_id`, e ele resolve o comprovante de verdade.

def test_dispensar_item_retorna_dispensacao_id(client, outer_conn):
    """A resposta do dispensar inclui `dispensacao_id` (inteiro positivo)."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 4},
        headers=_headers(_jwt_dispensador()),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "dispensacao_id" in body, "resposta do dispensar não traz dispensacao_id"
    assert isinstance(body["dispensacao_id"], int)
    assert body["dispensacao_id"] > 0

    # Bate com a linha realmente gravada em `dispensacoes`.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM dispensacoes WHERE prescricao_item_id = %s "
            "ORDER BY id DESC LIMIT 1",
            (item_id,),
        )
        assert cur.fetchone()[0] == body["dispensacao_id"]


def test_comprovante_alcancavel_com_dispensacao_id_do_dispensar(client, outer_conn):
    """
    Fecha o fluxo do balcão (T5): o `dispensacao_id` devolvido pelo dispensar
    resolve o comprovante — o mesmo dispensador que dispensou consegue lê-lo.
    """
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    disp = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 10},
        headers=_headers(_jwt_dispensador()),
    )
    assert disp.status_code == 201, disp.text
    dispensacao_id = disp.json()["dispensacao_id"]

    comp = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante?formato=json",
        headers=_headers(_jwt_dispensador()),
    )
    assert comp.status_code == 200, comp.text
    dados = comp.json()
    assert dados["dispensacao_id"] == dispensacao_id
    assert dados["protocolo_prescricao"] == proto
    assert dados["medicamento"]["quantidade_dispensada"] == 10

    # O balcão baixa o comprovante em PDF (?formato=pdf) — mesma chamada do
    # frontend. Cobre o caminho de data no PDF, que quebrava contra o PG
    # (dispensado_em é DateTime → PostgreSQL devolve objeto, não string ISO).
    pdf = client.get(
        f"/dispensacoes/{dispensacao_id}/comprovante?formato=pdf",
        headers=_headers(_jwt_dispensador()),
    )
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# COER — TICKET-COERENCIA-DEVOLUCOES: devolução ao paciente devolve a POSSE
# (status + custódia de prescrição inteira + fila do dispensador).
#
# Antes deste ticket, devolver(para=paciente) reabria só a custódia de ITEM
# (T1), mas `_recalcular_status_prescricao` contava `devolvido_paciente` como
# item ativo sem dispensação → a prescrição voltava a "em_custodia" (histórico
# do paciente; gates de devolver-prescritor / re-apresentação em 409). E a
# custódia de PRESCRIÇÃO INTEIRA (item_id IS NULL) do dispensador seguia ativa
# e obsoleta, prendendo a receita na fila do dispensador. Opção A (Fabiano,
# 2026-07-22): reusar o estado "transferida_paciente".
# ---------------------------------------------------------------------------


def _jwt_paciente() -> str:
    return criar_access_token(
        sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME,
    )


def _status_prescricao(outer_conn, prescricao_id: int) -> str:
    with outer_conn.cursor() as cur:
        cur.execute("SELECT status FROM prescricoes WHERE id = %s", (prescricao_id,))
        return cur.fetchone()[0]


def _custodia_ativa_prescricao(outer_conn, prescricao_id: int):
    """Custódia ATIVA de PRESCRIÇÃO INTEIRA (item_id IS NULL), ou None."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT detentor_tipo, detentor_id
              FROM prescricao_custodia
             WHERE prescricao_id = %s AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (prescricao_id,),
        )
        row = cur.fetchone()
    return None if row is None else {"detentor_tipo": row[0], "detentor_id": row[1]}


def _count_custodia_ativa_dispensador(outer_conn, prescricao_id: int, cnpj: str) -> int:
    """Quantas custódias ativas (qualquer nível) o dispensador ainda detém."""
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM prescricao_custodia
             WHERE prescricao_id = %s AND detentor_tipo = 'dispensador'
               AND detentor_id = %s AND encerrada_em IS NULL
            """,
            (prescricao_id, cnpj),
        )
        return cur.fetchone()[0]


def _eventos_custodia_transferida(outer_conn, prescricao_id: int) -> list:
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT ator_tipo, ator_id, payload_json
              FROM prescricao_eventos
             WHERE prescricao_id = %s AND tipo_evento = 'custodia_transferida'
             ORDER BY id
            """,
            (prescricao_id,),
        )
        rows = cur.fetchall()
    return [
        {"ator_tipo": r[0], "ator_id": r[1], "payload": json.loads(r[2]) if r[2] else {}}
        for r in rows
    ]


def _saldo_efetivo_item(outer_conn, item_id: int) -> dict:
    """prescrito, Σ dispensado, Σ estornado e saldo efetivo (= prescrito − (disp − est))."""
    with outer_conn.cursor() as cur:
        cur.execute("SELECT quantidade FROM prescricao_itens WHERE id = %s", (item_id,))
        prescrito = cur.fetchone()[0]
        cur.execute(
            "SELECT COALESCE(SUM(quantidade_dispensada), 0) FROM dispensacoes "
            "WHERE prescricao_item_id = %s",
            (item_id,),
        )
        dispensado = cur.fetchone()[0]
        cur.execute(
            "SELECT COALESCE(SUM(quantidade_estornada), 0) FROM estornos "
            "WHERE prescricao_item_id = %s",
            (item_id,),
        )
        estornado = cur.fetchone()[0]
    return {
        "prescrito": prescrito,
        "dispensado": dispensado,
        "estornado": estornado,
        "saldo_efetivo": prescrito - (dispensado - estornado),
    }


def _devolver_ao_paciente(client, proto, item_id, motivo="abandono no balcão"):
    return client.post(
        f"/prescricoes/{proto}/itens/{item_id}/devolver",
        json={"para": "paciente", "motivo": motivo},
        headers=_headers(_jwt_dispensador()),
    )


# COER-1 — status volta à posse ------------------------------------------------

def test_coer1_devolucao_ao_paciente_volta_status_a_posse(client, outer_conn):
    """Itens ativos voltam todos ao paciente → status 'transferida_paciente'
    (era 'em_custodia')."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = _devolver_ao_paciente(client, proto, item_id)
    assert r.status_code == 200, r.text
    assert r.json()["status_prescricao"] == "transferida_paciente"
    assert _status_prescricao(outer_conn, prescricao_id) == "transferida_paciente"


# COER-2 — custódia de prescrição inteira reconciliada + coexistência -----------

def test_coer2_custodia_prescricao_inteira_reconciliada(client, outer_conn):
    """A custódia ativa de PRESCRIÇÃO INTEIRA passa ao paciente; a do dispensador
    fica encerrada; o dispensador não detém mais NENHUMA custódia ativa; e a
    custódia de ITEM reaberta pelo T1 coexiste (difere no item_id)."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    r = _devolver_ao_paciente(client, proto, item_id)
    assert r.status_code == 200, r.text

    # Custódia ativa de prescrição inteira vira do paciente.
    assert _custodia_ativa_prescricao(outer_conn, prescricao_id) == {
        "detentor_tipo": "paciente", "detentor_id": SEED_PACIENTE_CPF,
    }
    # Dispensador não detém mais NENHUMA custódia ativa (prescrição nem item)
    # — é o que esvazia a fila (COER-8).
    assert _count_custodia_ativa_dispensador(outer_conn, prescricao_id, _DISPENSADOR_CNPJ) == 0
    # Coexistência esperada: custódia de ITEM reaberta pelo T1 segue ativa no
    # paciente — não conflita (item_id diferente) e não afeta a fila (paciente).
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == {
        "detentor_tipo": "paciente", "detentor_id": SEED_PACIENTE_CPF,
    }

    # Ledger (§8 Opção A / nota Z AI 4): o custodia_transferida da reconciliação
    # existe UMA vez, nível prescrição, com motivo DISTINTO — o auditor separa
    # devolução integral de auto-retenção (T1.5) e reabertura de item (T1).
    devol = [
        e for e in _eventos_custodia_transferida(outer_conn, prescricao_id)
        if e["payload"].get("motivo") == "devolucao_integral_paciente"
    ]
    assert len(devol) == 1, "custodia_transferida da devolução integral ausente ou duplicado"
    assert devol[0]["payload"]["de"] == "dispensador"
    assert devol[0]["payload"]["para"] == "paciente"
    assert devol[0]["payload"]["nivel"] == "prescricao"
    assert devol[0]["ator_tipo"] == "dispensador"
    assert devol[0]["ator_id"] == _DISPENSADOR_CNPJ


# COER-3 — volta ao prescritor (trava do 409) ----------------------------------

def test_coer3_devolucao_ao_paciente_habilita_devolver_prescritor(client, outer_conn):
    """Depois de devolver ao paciente, o paciente consegue devolver ao prescritor
    (era 409 quando o status ficava preso em 'em_custodia')."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    assert _devolver_ao_paciente(client, proto, item_id).status_code == 200

    r = client.post(
        f"/paciente/prescricoes/{proto}/devolver-prescritor",
        json={"motivo": "prefiro devolver ao médico"},
        headers=_headers(_jwt_paciente()),
    )
    assert r.status_code == 201, r.text


# COER-4 — re-apresentação em outra farmácia -----------------------------------

def test_coer4_devolucao_ao_paciente_habilita_reapresentacao(client, outer_conn):
    """`transferir-farmacia` aceita 'transferida_paciente' → re-apresentação 201."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    assert _devolver_ao_paciente(client, proto, item_id).status_code == 200

    r = client.post(
        f"/paciente/prescricoes/{proto}/transferir-farmacia",
        json={"cnpj_farmacia": _DISPENSADOR_CNPJ_NORTE},
        headers=_headers(_jwt_paciente()),
    )
    assert r.status_code == 201, r.text


# COER-5 — bucket 'posse' no app do paciente -----------------------------------

def test_coer5_prescricao_aparece_em_posse_nao_historico(client, outer_conn):
    """GET /paciente/prescricoes lista a prescrição devolvida em 'posse'
    (não 'historico') — a UI só renderiza ações na posse."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    assert _devolver_ao_paciente(client, proto, item_id).status_code == 200

    body = client.get("/paciente/prescricoes", headers=_headers(_jwt_paciente())).json()
    protos_posse = {p["protocolo"] for p in body["posse"]}
    protos_hist = {p["protocolo"] for p in body["historico"]}
    assert proto in protos_posse, "prescrição devolvida não apareceu na posse do paciente"
    assert proto not in protos_hist


# COER-6 — não-regressão do dispensar (parcial/total) --------------------------

def test_coer6_nao_regressao_dispensar_parcial_e_total(client, outer_conn):
    """O ramo novo do recalc só dispara com `devolvido_paciente`; dispensação
    sem devolução mantém comportamento idêntico: parcial → em_custodia,
    total → dispensada."""
    # Parcial (4/10) → em_custodia.
    _, proto_p, [item_p] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    rp = client.post(
        f"/prescricoes/{proto_p}/itens/{item_p}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 4},
        headers=_headers(_jwt_dispensador()),
    )
    assert rp.status_code == 201, rp.text
    assert rp.json()["status_item"] == "em_custodia"
    assert rp.json()["status_prescricao"] == "em_custodia"

    # Total (10/10) → dispensada.
    _, proto_t, [item_t] = _seed_prescricao_com_itens_em_custodia(outer_conn)
    rt = client.post(
        f"/prescricoes/{proto_t}/itens/{item_t}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 10},
        headers=_headers(_jwt_dispensador()),
    )
    assert rt.status_code == 201, rt.text
    assert rt.json()["status_item"] == "dispensado"
    assert rt.json()["status_prescricao"] == "dispensada"


# COER-7 — parcial + abandono: posse ≠ saldo -----------------------------------

def test_coer7_parcial_mais_abandono_posse_diferente_de_saldo(client, outer_conn):
    """Dispensa 4/10 e o paciente abandona o restante. A posse volta
    (transferida_paciente), mas o SALDO não é reposto: Σ dispensado==4 (ledger
    imutável) e saldo efetivo==6. Devolução devolve a POSSE, não o SALDO."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    # Farmácia A dispensa 4 de 10.
    r1 = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _DISPENSADOR_CNPJ, "quantidade_dispensada": 4},
        headers=_headers(_jwt_dispensador()),
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["saldo_restante"] == 6

    # Paciente abandona o restante → posse volta ao paciente (parcial NÃO trava).
    r2 = _devolver_ao_paciente(client, proto, item_id, motivo="vai tentar em outra farmácia")
    assert r2.status_code == 200, r2.text
    assert r2.json()["status_prescricao"] == "transferida_paciente"
    assert _status_prescricao(outer_conn, prescricao_id) == "transferida_paciente"

    # A parcial fica no ledger/saldo, não no status.
    saldo = _saldo_efetivo_item(outer_conn, item_id)
    assert saldo["prescrito"] == 10          # prescrito NÃO é "reposto"
    assert saldo["dispensado"] == 4          # ledger imutável — não zerou
    assert saldo["estornado"] == 0
    assert saldo["saldo_efetivo"] == 6       # re-dispensar aceita até 6


# COER-8 — 🎯 fila do dispensador limpa (padrão ANTES/DEPOIS) -------------------

def test_coer8_fila_do_dispensador_limpa_apos_devolucao(client, outer_conn):
    """Sintoma reportado ('↻ Atualizar não funciona'), provado no backend: a
    receita sai da fila do dispensador após a devolução ao paciente."""
    prescricao_id, proto, [item_id] = _seed_prescricao_com_itens_em_custodia(outer_conn)

    def _proto_na_fila() -> bool:
        r = client.get("/dispensadores/fila", headers=_headers(_jwt_dispensador()))
        assert r.status_code == 200, r.text
        return proto in {f["protocolo"] for f in r.json()["fila"]}

    # COER-8a (pré-condição): a receita ESTÁ na fila antes de devolver — sem isto
    # o teste passaria mesmo se a fila voltasse sempre vazia (falso-positivo).
    assert _proto_na_fila() is True, "pré-condição falhou: receita não estava na fila do dispensador"

    # Devolve ao paciente.
    assert _devolver_ao_paciente(client, proto, item_id).status_code == 200

    # COER-8b: a receita saiu da fila (Manifestação B do ticket).
    assert _proto_na_fila() is False, "receita continuou na fila do dispensador após devolução"
