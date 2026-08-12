"""
tests/integration/test_estorno.py
=================================

Cobertura E2E do T2 — estorno de dispensação como objeto sanitário DERIVADO
(POST /dispensacoes/{id}/estornar), conforme TICKET-ESTORNO-OBJETO-DERIVADO.md.

Invariantes verificadas:
- Estorno cria objeto derivado imutável `estornos` (protocolo UUID, referencia
  a dispensação de origem) — a `dispensacoes` original permanece intocada.
- Evento `estorno_registrado` no ledger da prescrição (reconciliável — T7).
- Saldo efetivo do item = Σ dispensado − Σ estornado (reposto) → re-dispensável.
- O item NÃO é mutado (a reversão vive no objeto-estorno — §1 do ticket).
- Owner-check: dispensador só estorna dispensação do próprio CNPJ.
- Motivo validado contra o enum MOTIVOS_ESTORNO.
- Estorno duplo além do saldo da dispensação → 409.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.auth.jwt import criar_access_token

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
)

_CNPJ_A = "12345678000195"
_CNPJ_B = "99999999000272"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _jwt_disp(cnpj: str) -> str:
    return criar_access_token(sub=cnpj, role="dispensador", nome=f"Farmácia {cnpj}")


def _seed(outer_conn, cnpj: str = _CNPJ_A, quantidade: int = 10):
    """Prescrição em_custodia + 1 item (qty) + custódia ativa do dispensador."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-EST-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "posologia, status_item, created_at, updated_at) "
            "VALUES (%s, 'LOSARTANA', '50mg', %s, '1cp/dia', 'em_custodia', %s, %s) RETURNING id",
            (prescricao_id, quantidade, now, now),
        )
        item_id = cur.fetchone()[0]
        for iid in (None, item_id):
            cur.execute(
                "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
                "transferida_em, encerrada_em, motivo, created_at) "
                "VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed', %s)",
                (prescricao_id, iid, cnpj, now, now),
            )
    return prescricao_id, proto, item_id


def _dispensar(client, proto, item_id, cnpj, qtd):
    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": cnpj, "quantidade_dispensada": qtd},
        headers=_headers(_jwt_disp(cnpj)),
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Caminho feliz — objeto derivado + reposição de saldo
# ---------------------------------------------------------------------------

def test_estorno_cria_objeto_derivado_e_repoe_saldo(client, outer_conn):
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 4)
    disp_id = disp["dispensacao_id"]
    assert disp["saldo_restante"] == 6

    e = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"motivo": "pagamento_nao_concluido"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    body = e.json()
    assert body["origem_dispensacao_id"] == disp_id
    assert body["quantidade_estornada"] == 4
    assert body["saldo_restante"] == 10           # saldo reposto
    assert body["status_item"] == "em_custodia"   # item NÃO mutado
    assert uuid.UUID(body["protocolo"]).version == 4

    # Objeto derivado gravado (imutável).
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT quantidade_estornada, motivo, origem_dispensacao_id, prescricao_id "
            "FROM estornos WHERE prescricao_item_id = %s", (item_id,),
        )
        row = cur.fetchone()
    assert row == (4, "pagamento_nao_concluido", disp_id, prescricao_id)

    # Dispensação de origem permanece intocada.
    with outer_conn.cursor() as cur:
        cur.execute("SELECT quantidade_dispensada FROM dispensacoes WHERE id = %s", (disp_id,))
        assert cur.fetchone()[0] == 4

    # Evento no ledger da prescrição.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos "
            "WHERE prescricao_id = %s AND tipo_evento = 'estorno_registrado'", (prescricao_id,),
        )
        assert cur.fetchone()[0] == 1

    # Saldo reposto aparece na fila (Σ efetivo).
    fila = client.get("/dispensadores/fila", headers=_headers(_jwt_disp(_CNPJ_A))).json()
    itens = next(p["itens"] for p in fila["fila"] if p["protocolo"] == proto)
    it = next(i for i in itens if i["item_id"] == item_id)
    assert it["saldo"] == 10


def test_redispensa_apos_estorno_usa_saldo_reposto(client, outer_conn):
    """
    Ciclo mínimo: dispensar PARCIAL (item continua `em_custodia`) → estornar →
    saldo reposto é dispensável de novo. (Dispensação TOTAL levaria o item a
    `dispensado` terminal e o estorno, por ser objeto derivado, não o reabre —
    fork #1 do ticket. Por isso a reposição operacional é no caminho parcial.)
    """
    _, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 4)  # parcial → item em_custodia
    disp_id = disp["dispensacao_id"]
    assert disp["saldo_restante"] == 6

    e = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    assert e.json()["saldo_restante"] == 10
    assert e.json()["status_item"] == "em_custodia"

    # Re-dispensa do saldo reposto (prova que a reposição é operacional).
    redisp = _dispensar(client, proto, item_id, _CNPJ_A, 3)
    assert redisp["saldo_restante"] == 7


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------

def test_estorno_owner_check_outro_cnpj(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, cnpj=_CNPJ_A, quantidade=5)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 2)

    r = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "erro_dispensacao"},
        headers=_headers(_jwt_disp(_CNPJ_B)),   # outro estabelecimento
    )
    assert r.status_code == 403, r.text


def test_estorno_motivo_invalido(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, quantidade=5)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 2)

    r = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "porque_sim"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert r.status_code == 422, r.text


def test_estorno_duplo_alem_do_saldo_da_dispensacao_409(client, outer_conn):
    _, proto, item_id = _seed(outer_conn, quantidade=5)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 2)
    disp_id = disp["dispensacao_id"]
    h = _headers(_jwt_disp(_CNPJ_A))

    r1 = client.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"}, headers=h)
    assert r1.status_code == 201, r1.text
    r2 = client.post(f"/dispensacoes/{disp_id}/estornar", json={"motivo": "outro"}, headers=h)
    assert r2.status_code == 409, r2.text


# ---------------------------------------------------------------------------
# T3 — trigger de saldo efetivo instalado no Postgres (rede de segurança)
# ---------------------------------------------------------------------------

def test_trigger_t3_saldo_efetivo_instalado(outer_conn):
    """
    O trigger `trg_check_saldo_efetivo` (Σ dispensado − Σ estornado ≤ prescrito)
    está instalado no Postgres. O bloqueio comportamental espelha a validação
    de app (custodia.py) — coberta pelo caminho 422 do dispensar.
    """
    with outer_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM pg_trigger WHERE tgname = 'trg_check_saldo_efetivo'")
        assert cur.fetchone()[0] == 1


# ---------------------------------------------------------------------------
# T1.5 — detenção prévia (dois ramos) + flag (c): ledger da auto-retenção
# ---------------------------------------------------------------------------

def _seed_custodia_paciente(outer_conn, quantidade: int = 5):
    """Prescrição sob custódia do PACIENTE (dispensador NÃO detém o item) —
    força o caminho T1.5 no dispensar."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-T15-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'transferida_paciente', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
            "posologia, status_item, created_at, updated_at) "
            "VALUES (%s, 'LOSARTANA', '50mg', %s, '1cp/dia', 'pendente', %s, %s) RETURNING id",
            (prescricao_id, quantidade, now, now),
        )
        item_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
            "transferida_em, encerrada_em, motivo, created_at) "
            "VALUES (%s, %s, 'paciente', %s, %s, NULL, 'seed', %s)",
            (prescricao_id, item_id, SEED_PACIENTE_CPF, now, now),
        )
    return prescricao_id, proto, item_id


def test_t1_5_auto_retencao_demo_emite_custodia_transferida(client, outer_conn, monkeypatch):
    """
    T1.5 em DEMO: dispensar item não-retido auto-retém E emite
    `custodia_transferida` no ledger (flag c do portão — sem o evento o T6
    reconstruiria a retenção com buraco).
    """
    monkeypatch.setattr("app.routers.custodia.PICSAUDE_DEMO_MODE", True)
    prescricao_id, proto, item_id = _seed_custodia_paciente(outer_conn, quantidade=5)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ_A, "quantidade_dispensada": 2},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert r.status_code == 201, r.text

    # §3 — UM detentor a cada momento: exatamente UMA custódia ativa do item,
    # e é a do dispensador (a do paciente foi encerrada). A retenção é
    # TRANSFERÊNCIA de posse, não brota uma segunda custódia em paralelo.
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT detentor_tipo, detentor_id FROM prescricao_custodia "
            "WHERE prescricao_id=%s AND item_id=%s AND encerrada_em IS NULL",
            (prescricao_id, item_id),
        )
        ativas = cur.fetchall()
    assert len(ativas) == 1, f"custódia dupla (viola §3 — posse brotou): {ativas}"
    assert ativas[0] == ("dispensador", _CNPJ_A)

    # Evento custodia_transferida gravado (ledger completo).
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id=%s "
            "AND tipo_evento='custodia_transferida' AND payload_json LIKE '%%auto_retencao_demo%%'",
            (prescricao_id,),
        )
        assert cur.fetchone()[0] == 1


def test_t1_5_producao_rejeita_item_nao_retido(client, outer_conn):
    """T1.5 em produção (DEMO_MODE=false, padrão nos testes): item não retido
    por este estabelecimento → 409 item_nao_retido (detenção é pré-requisito)."""
    _, proto, item_id = _seed_custodia_paciente(outer_conn, quantidade=5)

    r = client.post(
        f"/prescricoes/{proto}/itens/{item_id}/dispensar",
        json={"cnpj_estabelecimento": _CNPJ_A, "quantidade_dispensada": 2},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["codigo"] == "item_nao_retido"


# ===========================================================================
# TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO (10/08)
# Estorno TOTAL nos motivos "cidadão recupera" devolve a custódia ao paciente
# (item → devolvido_paciente, prescrição → transferida_paciente). Estorno
# PARCIAL e motivo `erro_dispensacao` preservam o TICKET-B0 (dispensador).
# ===========================================================================

def _jwt_paciente() -> str:
    return criar_access_token(sub=SEED_PACIENTE_CPF, role="paciente", nome=SEED_PACIENTE_NOME)


def _custodia_ativa_item(outer_conn, prescricao_id, item_id):
    """Retorna [(detentor_tipo, detentor_id), ...] ativos para o item."""
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT detentor_tipo, detentor_id FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NULL",
            (prescricao_id, item_id),
        )
        return [(r[0], r[1]) for r in cur.fetchall()]


def test_estorno_total_desistencia_devolve_ao_cidadao(client, outer_conn):
    """§8.1 — estorno TOTAL por desistencia_paciente: item → devolvido_paciente,
    prescrição → transferida_paciente, custódia ativa do PACIENTE, carteira do
    cidadão mostra em POSSE, devolver-prescritor aceita (via §3 destravada)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 10)   # TOTAL → dispensado
    disp_id = disp["dispensacao_id"]

    e = client.post(
        f"/dispensacoes/{disp_id}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    body = e.json()
    assert body["status_item"] == "devolvido_paciente"
    assert body["status_prescricao"] == "transferida_paciente"
    assert body["destino_custodia"] == "paciente"

    # Custódia ativa do item está com o PACIENTE (cpf do seed).
    detentores = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert detentores == [("paciente", SEED_PACIENTE_CPF)], detentores

    # Carteira do cidadão: prescrição em POSSE (a dor do bug — agora visível).
    carteira = client.get("/paciente/prescricoes", headers=_headers(_jwt_paciente()))
    assert carteira.status_code == 200, carteira.text
    em_posse = [p["protocolo"] for p in carteira.json()["posse"]]
    assert proto in em_posse, f"proto não voltou à posse: {em_posse}"

    # Via de devolução ao prescritor destravada (§3 — paciente → prescritor).
    dev = client.post(
        f"/paciente/prescricoes/{proto}/devolver-prescritor",
        json={"motivo": "Erro identificado após dispensação"},
        headers=_headers(_jwt_paciente()),
    )
    assert dev.status_code == 201, dev.text


def test_estorno_total_pagamento_nao_concluido_devolve_ao_cidadao(client, outer_conn):
    """§8.4 (martelo Fabiano) — pagamento_nao_concluido total também volta ao
    cidadão (mesmo ramo da desistencia_paciente)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=8)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 8)
    e = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "pagamento_nao_concluido"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    assert e.json()["status_item"] == "devolvido_paciente"
    assert e.json()["destino_custodia"] == "paciente"
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == [("paciente", SEED_PACIENTE_CPF)]


def test_estorno_total_erro_dispensacao_mantem_dispensador_b0(client, outer_conn):
    """§8.3 (regressão TICKET-B0) — erro_dispensacao total: item permanece
    `dispensado`, custódia reaberta no DISPENSADOR, re-dispensável (B0 intacto)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 10)   # TOTAL
    e = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "erro_dispensacao"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    body = e.json()
    assert body["status_item"] == "dispensado"            # NÃO mutado (B0)
    assert body["destino_custodia"] == "dispensador"
    # Custódia ativa do item volta ao dispensador (re-dispensável).
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == [("dispensador", _CNPJ_A)]
    # Re-dispensa do saldo reposto é aceita (TICKET-B0 §6.1).
    redisp = _dispensar(client, proto, item_id, _CNPJ_A, 5)
    assert redisp["saldo_restante"] == 5


def test_estorno_parcial_nao_muta_item_preserva_b0(client, outer_conn):
    """§8.5 (regressão) — estorno PARCIAL de qualquer motivo NÃO muta o item:
    a fração revertida vive só no saldo efetivo (TICKET-B0). Protege os testes
    existentes test_estorno_cria_objeto_derivado_e_repoe_saldo /
    test_redispensa_apos_estorno_usa_saldo_reposto (ambos parciais)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 4)   # PARCIAL → em_custodia
    e = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente"},   # mesmo motivo "cidadão recupera"
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    body = e.json()
    assert body["status_item"] == "em_custodia"            # não mutado
    assert body["saldo_restante"] == 10                    # saldo reposto
    # Nenhuma custódia ativa do PACIENTE (continua com o dispensador).
    detentores = _custodia_ativa_item(outer_conn, prescricao_id, item_id)
    assert ("paciente", SEED_PACIENTE_CPF) not in detentores


def test_estorno_total_sem_custodia_orfa(client, outer_conn):
    """§8.6 — sem custódia órfã/duplicada após o ramo paciente: no máximo UMA
    custódia ativa por (prescricao_id, item_id) e por (prescricao_id, NULL)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 10)
    client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    with outer_conn.cursor() as cur:
        # unicidade por item
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NULL",
            (prescricao_id, item_id),
        )
        assert cur.fetchone()[0] == 1
        # unicidade por prescrição (nível NULL)
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (prescricao_id,),
        )
        assert cur.fetchone()[0] <= 1


def test_estorno_total_cidadao_pode_retry_outra_farmacia(client, outer_conn):
    """§8.2 — após estorno ao cidadão, ele pode re-transferir a custódia a outra
    farmácia (retry). Prova que a posse voltou de fato ao portador."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=6)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 6)
    client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    # Cidadão re-apresenta a OUTRA farmácia (CNPJ_B).
    r = client.post(
        f"/paciente/prescricoes/{proto}/transferir-farmacia",
        json={"cnpj_farmacia": _CNPJ_B},
        headers=_headers(_jwt_paciente()),
    )
    assert r.status_code == 201, r.text


def test_estorno_total_ledger_sequencia_paciente(client, outer_conn):
    """§8.7 — ledger no ramo paciente: estorno_registrado vem PRIMEIRO (causa),
    seguido de item_devolvido_paciente e custodia_transferida (efeitos). NÃO se
    fixa ordem entre item_devolvido_paciente e custodia_transferida — o handler
    emite custodia_transferida antes do evento do item, no MESMO padrão do
    precedente ratificado `devolver_item` (custodia.py reconciliação + evento).
    Fixar item-antes-de-custódia aqui divergiria de devolver_item (auditoria do
    Revisor, 10/08)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 10)
    client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT tipo_evento FROM prescricao_eventos "
            "WHERE prescricao_id = %s AND tipo_evento IN "
            "('estorno_registrado','item_devolvido_paciente','custodia_transferida') "
            "ORDER BY id ASC",
            (prescricao_id,),
        )
        tipos = [r[0] for r in cur.fetchall()]
    assert "estorno_registrado" in tipos
    assert "item_devolvido_paciente" in tipos
    assert "custodia_transferida" in tipos
    # Causalidade: estorno_registrado é a causa, vem antes de todos os efeitos.
    idx_estorno = tipos.index("estorno_registrado")
    assert tipos.index("item_devolvido_paciente") > idx_estorno
    assert tipos.index("custodia_transferida") > idx_estorno


# ---------------------------------------------------------------------------
# Cobertura incorporada após auditoria do Revisor (10/08): 2 cenários que o PR
# original não testava — multi-item (Q2) e parcial-de-total (Q3). Nomes com
# "estorno" para casar o filtro -k do gates.yml.
# ---------------------------------------------------------------------------

def _seed_2_itens(outer_conn, qtd_a: int = 10, qtd_b: int = 5):
    """Prescrição em_custodia com DOIS itens + custódia ativa do dispensador
    nos níveis prescrição (NULL) e item (A e B)."""
    now = datetime.utcnow().isoformat()
    proto = f"PROTO-MULTI-{uuid.uuid4().hex[:10]}"
    with outer_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        pres_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (%s, %s, true, %s, %s) ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome RETURNING id",
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        pac_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO prescricoes (protocolo, prescritor_id, paciente_id, status, tipo_emissao, "
            "data_emissao, created_at, updated_at) "
            "VALUES (%s, %s, %s, 'em_custodia', 'nova', %s, %s, %s) RETURNING id",
            (proto, pres_id, pac_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        ids = []
        for nome, qtd in (("LOSARTANA", qtd_a), ("DIPIRONA", qtd_b)):
            cur.execute(
                "INSERT INTO prescricao_itens (prescricao_id, nome_medicamento, concentracao, quantidade, "
                "posologia, status_item, created_at, updated_at) "
                "VALUES (%s, %s, '50mg', %s, '1cp/dia', 'em_custodia', %s, %s) RETURNING id",
                (prescricao_id, nome, qtd, now, now),
            )
            ids.append(cur.fetchone()[0])
        for iid in (None, *ids):
            cur.execute(
                "INSERT INTO prescricao_custodia (prescricao_id, item_id, detentor_tipo, detentor_id, "
                "transferida_em, encerrada_em, motivo, created_at) "
                "VALUES (%s, %s, 'dispensador', %s, %s, NULL, 'seed', %s)",
                (prescricao_id, iid, _CNPJ_A, now, now),
            )
    return prescricao_id, proto, ids[0], ids[1]


def test_estorno_total_multi_item_irmao_dispensado_intacto(client, outer_conn):
    """Q2 (Revisor) — estorno TOTAL de 1 item entre 2: o item estornado vai a
    `devolvido_paciente`, o IRMÃO permanece `dispensado` (intacto); a prescrição
    vai a `transferida_paciente` (resumo lossy); unicidade de custódia intacta."""
    prescricao_id, proto, item_a, item_b = _seed_2_itens(outer_conn, qtd_a=10, qtd_b=5)
    _dispensar(client, proto, item_a, _CNPJ_A, 10)   # A total → dispensado
    disp_b = _dispensar(client, proto, item_b, _CNPJ_A, 5)   # B total → dispensado

    e = client.post(
        f"/dispensacoes/{disp_b['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente"},
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    assert e.json()["destino_custodia"] == "paciente"

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_b,),
        )
        assert cur.fetchone()[0] == "devolvido_paciente"   # estornado → paciente
        cur.execute(
            "SELECT status_item FROM prescricao_itens WHERE id = %s", (item_a,),
        )
        assert cur.fetchone()[0] == "dispensado"           # irmão INTACTO
        cur.execute("SELECT status FROM prescricoes WHERE id = %s", (prescricao_id,))
        assert cur.fetchone()[0] == "transferida_paciente"  # resumo lossy
        # Unicidade: no máximo 1 ativa por (pid, item) e por (pid, NULL).
        for iid, esperado in ((item_a, 0), (item_b, 1)):
            cur.execute(
                "SELECT COUNT(*) FROM prescricao_custodia "
                "WHERE prescricao_id = %s AND item_id = %s AND encerrada_em IS NULL",
                (prescricao_id, iid),
            )
            assert cur.fetchone()[0] == esperado
        cur.execute(
            "SELECT COUNT(*) FROM prescricao_custodia "
            "WHERE prescricao_id = %s AND item_id IS NULL AND encerrada_em IS NULL",
            (prescricao_id,),
        )
        assert cur.fetchone()[0] <= 1


def test_estorno_parcial_de_dispensacao_total_mantem_dispensador(client, outer_conn):
    """Q3 (Revisor) — estorno PARCIAL de uma dispensação TOTAL (item `dispensado`):
    saldo_efetivo < prescrito → NÃO é estorno_total → cai no ramo dispensador
    (B0), item NÃO mutado, custódia reaberta no dispensador. Distingue do
    `test_estorno_parcial_nao_muta_item_preserva_b0` (que cobre parcial de uma
    dispensação PARCIAL, item `em_custodia`)."""
    prescricao_id, proto, item_id = _seed(outer_conn, quantidade=10)
    disp = _dispensar(client, proto, item_id, _CNPJ_A, 10)   # TOTAL → dispensado
    e = client.post(
        f"/dispensacoes/{disp['dispensacao_id']}/estornar",
        json={"motivo": "desistencia_paciente", "quantidade": 4},   # PARCIAL do total
        headers=_headers(_jwt_disp(_CNPJ_A)),
    )
    assert e.status_code == 201, e.text
    body = e.json()
    assert body["status_item"] == "dispensado"            # NÃO mutado
    assert body["destino_custodia"] == "dispensador"      # B0
    assert body["saldo_restante"] == 4                     # 10 - (10-4)
    # Custódia ativa do item reaberta no dispensador (re-dispensável).
    assert _custodia_ativa_item(outer_conn, prescricao_id, item_id) == [("dispensador", _CNPJ_A)]
