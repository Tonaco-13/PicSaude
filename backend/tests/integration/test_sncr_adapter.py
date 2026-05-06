"""Ticket 16A — Testes de integração do adapter SNCR (stub) e do endpoint
POST /prescricoes/{protocolo}/receituarios/numerar.

Cobertura
---------
1. Stub (unidade — sem TestClient):
   - Numeração com prefixo STUB-, sequencial, vinculação ao CPF.
   - health_check.

2. Factory:
   - Default → SNCRStub.
   - SNCR_ADAPTER=real → NotImplementedError.

3. Endpoint /numerar (integração — TestClient + outer_conn):
   - Receituário controlado → numeracao_sncr começa com STUB-, status=numerado_stub.
   - Receita simples → status=nao_requer_sncr, numeracao_sncr=NULL.
   - Idempotência: chamar duas vezes não renumera.
   - Assinatura insuficiente → todo_regulatorio no ledger (NÃO 422).
   - Evento receituarios_numerados registrado com adapter="stub".
   - Status "numerado_stub" ≠ "numerado" — receituário stub é distinguível.

Estratégia de setup
-------------------
Reusa helpers de `test_receituarios.py` (insere prescrição + itens via
outer_conn, gera receituários via /gerar, depois testa /numerar). Mantém
o padrão de SAVEPOINT-por-request da fixture `client`.
"""
from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Helpers de setup
# ---------------------------------------------------------------------------

def _inserir_prescritor_e_paciente(outer_conn) -> tuple[int, int]:
    now = datetime.utcnow().isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        prescritor_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        paciente_id = cur.fetchone()[0]
    return prescritor_id, paciente_id


def _inserir_prescricao(
    outer_conn,
    *,
    assinatura_modo: str | None,
    classes_itens: list[str | None],
    protocolo: str,
    tipo_certificado: str | None = None,
) -> int:
    """Insere prescrição + itens. Se tipo_certificado dado, cria também
    `prescricao_assinatura` para que o endpoint /numerar consulte o nível.
    """
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    now = datetime.utcnow()
    now_iso = now.isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', %s, 'nova', %s, %s, %s)
            RETURNING id
            """,
            (protocolo, prescritor_id, paciente_id, assinatura_modo, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        for idx, classe in enumerate(classes_itens, start=1):
            cur.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   posologia, status_item, classe_controle, created_at, updated_at)
                VALUES (%s, %s, '500mg', 10, '1 cp/dia', 'pendente', %s, %s, %s)
                """,
                (
                    prescricao_id,
                    f"MEDICAMENTO {classe or 'LIVRE'} {idx}",
                    classe,
                    now,
                    now,
                ),
            )

        if tipo_certificado is not None:
            cur.execute(
                """
                INSERT INTO prescricao_assinatura
                  (prescricao_id, tipo_certificado, status_validacao,
                   created_at, updated_at)
                VALUES (%s, %s, 'assinatura_pendente', %s, %s)
                """,
                (prescricao_id, tipo_certificado, now_iso, now_iso),
            )
    return prescricao_id


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _gerar(client, token: str, protocolo: str):
    return client.post(
        f"/prescricoes/{protocolo}/receituarios/gerar",
        headers=_headers(token),
    )


def _numerar(client, token: str, protocolo: str):
    return client.post(
        f"/prescricoes/{protocolo}/receituarios/numerar",
        headers=_headers(token),
    )


# ---------------------------------------------------------------------------
# 1. Testes do stub (unidade — sem TestClient)
# ---------------------------------------------------------------------------

def test_stub_gera_numeracao_com_prefixo_stub():
    from app.adapters.sncr_stub import SNCRStub

    stub = SNCRStub()
    res = stub.requisitar_numeracao("notificacao_receita_a", "12345678901", 1)

    assert len(res) == 1
    r = res[0]
    assert r.sucesso is True
    assert r.dados is not None
    assert r.dados.numero.startswith("STUB-"), \
        f"Numeração stub deve começar com STUB-, recebeu {r.dados.numero}"
    assert r.dados.tipo_receituario == "notificacao_receita_a"


def test_stub_numeracao_sequencial():
    from app.adapters.sncr_stub import SNCRStub

    stub = SNCRStub()
    res = stub.requisitar_numeracao("notificacao_receita_b", "11122233344", 3)

    numeros = [r.dados.numero for r in res]
    # Os 9 últimos dígitos formam a sequência
    seqs = [int(n.split("-")[-1]) for n in numeros]
    assert seqs == [1, 2, 3], f"Sequência inesperada: {seqs}"


def test_stub_vincula_cpf_prescritor():
    from app.adapters.sncr_stub import SNCRStub

    stub = SNCRStub()
    res = stub.requisitar_numeracao("notificacao_receita_a", "98765432100", 1)

    assert res[0].dados.prescritor_cpf == "98765432100"


def test_stub_health_check():
    from app.adapters.sncr_stub import SNCRStub
    assert SNCRStub().health_check() is True


def test_stub_tipo_desconhecido_retorna_erro():
    from app.adapters.sncr_stub import SNCRStub
    stub = SNCRStub()
    res = stub.requisitar_numeracao("tipo_inexistente", "12345678901", 1)
    assert res[0].sucesso is False
    assert res[0].codigo_erro == "SNCR_INVALIDO"


def test_stub_verificar_numeracao_emitida_e_garbage():
    from app.adapters.sncr_stub import SNCRStub
    stub = SNCRStub()

    res = stub.requisitar_numeracao("notificacao_receita_a", "11122233344", 1)
    numero = res[0].dados.numero

    ok = stub.verificar_numeracao(numero)
    assert ok.sucesso is True

    # Sem prefixo STUB-
    bad = stub.verificar_numeracao("SNCR-2026-NRA-000000099")
    assert bad.sucesso is False
    assert bad.codigo_erro == "SNCR_INVALIDO"


# ---------------------------------------------------------------------------
# 2. Testes da factory
# ---------------------------------------------------------------------------

def test_factory_retorna_stub_por_default(monkeypatch):
    from app.adapters.sncr_factory import get_sncr_adapter
    from app.adapters.sncr_stub import SNCRStub

    monkeypatch.delenv("SNCR_ADAPTER", raising=False)
    a = get_sncr_adapter()
    assert isinstance(a, SNCRStub)
    assert a.nome_adapter == "stub"


def test_factory_stub_explicito(monkeypatch):
    from app.adapters.sncr_factory import get_sncr_adapter
    from app.adapters.sncr_stub import SNCRStub

    monkeypatch.setenv("SNCR_ADAPTER", "stub")
    a = get_sncr_adapter()
    assert isinstance(a, SNCRStub)


def test_factory_real_levanta_erro(monkeypatch):
    from app.adapters.sncr_factory import get_sncr_adapter

    monkeypatch.setenv("SNCR_ADAPTER", "real")
    with pytest.raises(NotImplementedError) as exc:
        get_sncr_adapter()
    assert "Ticket 16B" in str(exc.value) or "real" in str(exc.value).lower()


def test_factory_valor_invalido_levanta_erro(monkeypatch):
    from app.adapters.sncr_factory import get_sncr_adapter

    monkeypatch.setenv("SNCR_ADAPTER", "lua")
    with pytest.raises(ValueError):
        get_sncr_adapter()


# ---------------------------------------------------------------------------
# 3. Testes do endpoint /numerar
# ---------------------------------------------------------------------------

def test_numerar_receituario_controlado_stub(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Receituário B1 → numeracao_sncr=STUB-..., status=numerado_stub."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1"],
        protocolo="TEST-NUM-CONTROLADO-001",
        tipo_certificado="A1",  # cobre nivel qualificada
    )

    r1 = _gerar(client, token, "TEST-NUM-CONTROLADO-001")
    assert r1.status_code == 201, r1.text

    r2 = _numerar(client, token, "TEST-NUM-CONTROLADO-001")
    assert r2.status_code == 200, r2.text
    body = r2.json()

    assert body["adapter"] == "stub"
    assert body["total_numerados"] == 1
    rec = body["receituarios"][0]
    assert rec["status"] == "numerado_stub", \
        f"status deve ser 'numerado_stub' (não 'numerado'), recebeu {rec['status']}"
    assert rec["numeracao_sncr"].startswith("STUB-"), rec["numeracao_sncr"]
    assert rec["adapter_usado"] == "stub"
    assert rec["requer_sncr"] is True


def test_numerar_receita_simples_marca_nao_requer_sncr(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Receita simples → status='nao_requer_sncr', numeracao_sncr=NULL."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo=None,
        classes_itens=[None, None],
        protocolo="TEST-NUM-SIMPLES-001",
    )

    r1 = _gerar(client, token, "TEST-NUM-SIMPLES-001")
    assert r1.status_code == 201, r1.text

    r2 = _numerar(client, token, "TEST-NUM-SIMPLES-001")
    assert r2.status_code == 200, r2.text
    body = r2.json()

    assert body["total_numerados"] == 0
    assert body["total_nao_requer_sncr"] == 1
    rec = body["receituarios"][0]
    assert rec["status"] == "nao_requer_sncr"
    assert rec["numeracao_sncr"] is None
    assert rec["requer_sncr"] is False
    assert rec["adapter_usado"] is None


def test_numerar_idempotente_nao_renumera(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Segunda chamada a /numerar não muda nada."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1"],
        protocolo="TEST-NUM-IDEMP-001",
        tipo_certificado="A1",
    )

    _gerar(client, token, "TEST-NUM-IDEMP-001")

    r1 = _numerar(client, token, "TEST-NUM-IDEMP-001")
    assert r1.status_code == 200
    numeracao_1 = r1.json()["receituarios"][0]["numeracao_sncr"]

    r2 = _numerar(client, token, "TEST-NUM-IDEMP-001")
    assert r2.status_code == 200
    body2 = r2.json()
    numeracao_2 = body2["receituarios"][0]["numeracao_sncr"]

    assert numeracao_1 == numeracao_2, "Renumerou indevidamente"
    assert body2["idempotente"] is True


def test_numerar_sem_gerar_404(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Chamar /numerar sem antes ter chamado /gerar → 404."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1"],
        protocolo="TEST-NUM-SEM-GERAR-001",
        tipo_certificado="A1",
    )

    r = _numerar(client, token, "TEST-NUM-SEM-GERAR-001")
    assert r.status_code == 404, r.text


def test_numerar_registra_todo_regulatorio_assinatura_insuficiente(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Receituário A1 com gov.br → numera mas registra todo_regulatorio."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        classes_itens=["A1"],
        protocolo="TEST-NUM-TODO-001",
        tipo_certificado="gov_br_nuvem",  # avancada < qualificada exigida
    )

    _gerar(client, token, "TEST-NUM-TODO-001")
    r = _numerar(client, token, "TEST-NUM-TODO-001")

    # NÃO bloqueia com 422 — numera normalmente
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_numerados"] == 1
    assert body["receituarios"][0]["status"] == "numerado_stub"

    # Mas registra evento todo_regulatorio
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
            JOIN prescricoes p ON p.id = pe.prescricao_id
            WHERE p.protocolo = %s AND pe.tipo_evento = 'todo_regulatorio'
            ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-NUM-TODO-001",),
        )
        row = cur.fetchone()
    assert row is not None, "Evento todo_regulatorio deveria ter sido registrado"
    payload = json.loads(row[0])
    assert payload["motivo"] == "nivel_assinatura_insuficiente"
    assert payload["nivel_declarado"] == "avancada"
    assert payload["nivel_exigido"] == "qualificada"


def test_numerar_registra_evento_ledger(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Após /numerar, evento receituarios_numerados deve estar no ledger."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1", "B1"],
        protocolo="TEST-NUM-LEDGER-001",
        tipo_certificado="A1",
    )

    _gerar(client, token, "TEST-NUM-LEDGER-001")
    r = _numerar(client, token, "TEST-NUM-LEDGER-001")
    assert r.status_code == 200

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
            JOIN prescricoes p ON p.id = pe.prescricao_id
            WHERE p.protocolo = %s AND pe.tipo_evento = 'receituarios_numerados'
            ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-NUM-LEDGER-001",),
        )
        row = cur.fetchone()
    assert row is not None, "Evento receituarios_numerados não registrado"
    payload = json.loads(row[0])
    assert payload["adapter"] == "stub"
    assert payload["receituarios_numerados"] == 2  # A1 e B1
    assert payload["ticket_referencia"] == "TICKET-16A"
    assert all(n["numeracao_sncr"].startswith("STUB-") for n in payload["numeracoes"])


def test_numerar_status_distinguivel_de_real(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Confirma a salvaguarda: numeração stub → status='numerado_stub',
    nunca 'numerado'. E numeração tem prefixo STUB-.
    """
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1"],
        protocolo="TEST-NUM-DISTING-001",
        tipo_certificado="A3",
    )

    _gerar(client, token, "TEST-NUM-DISTING-001")
    r = _numerar(client, token, "TEST-NUM-DISTING-001")
    body = r.json()
    rec = body["receituarios"][0]

    # Dois sinais de "stub" distintos:
    assert rec["status"] == "numerado_stub", "status deve ser numerado_stub"
    assert rec["status"] != "numerado", "status NÃO pode ser 'numerado' (reservado para SNCR real)"
    assert rec["numeracao_sncr"].startswith("STUB-"), "numeração deve ter prefixo STUB-"
    assert rec["adapter_usado"] == "stub"


def test_numerar_prescricao_inexistente_404(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    r = _numerar(client, token, "PROTOCOLO-INEXISTENTE-XYZ")
    assert r.status_code == 404


def test_numerar_outro_prescritor_403(
    client, outer_conn, seed_usuario, seed_paciente
):
    """Apenas o prescritor da prescrição pode numerar."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1"],
        protocolo="TEST-NUM-403-001",
        tipo_certificado="A1",
    )
    _gerar(client, token, "TEST-NUM-403-001")

    # Trocar o cns do prescritor da prescrição para outro valor
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES ('111111111111111', 'OUTRO PRESCRITOR', true, %s, %s)
            ON CONFLICT (cns) DO NOTHING
            """,
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        cur.execute(
            """
            UPDATE prescricoes
               SET prescritor_id = (SELECT id FROM prescritores WHERE cns = '111111111111111')
             WHERE protocolo = %s
            """,
            ("TEST-NUM-403-001",),
        )

    r = _numerar(client, token, "TEST-NUM-403-001")
    assert r.status_code == 403


def test_numerar_mistura_controlado_e_simples(
    client, outer_conn, seed_usuario, seed_paciente
):
    """A1 + sem-classe → 2 receituários: 1 numerado_stub + 1 nao_requer_sncr."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1", None],
        protocolo="TEST-NUM-MIX-001",
        tipo_certificado="A1",
    )

    _gerar(client, token, "TEST-NUM-MIX-001")
    r = _numerar(client, token, "TEST-NUM-MIX-001")
    assert r.status_code == 200
    body = r.json()

    assert body["total_numerados"] == 1
    assert body["total_nao_requer_sncr"] == 1

    by_tipo = {rec["tipo"]: rec for rec in body["receituarios"]}
    assert by_tipo["notificacao_receita_a"]["status"] == "numerado_stub"
    assert by_tipo["notificacao_receita_a"]["numeracao_sncr"].startswith("STUB-")
    assert by_tipo["receita_simples"]["status"] == "nao_requer_sncr"
    assert by_tipo["receita_simples"]["numeracao_sncr"] is None
