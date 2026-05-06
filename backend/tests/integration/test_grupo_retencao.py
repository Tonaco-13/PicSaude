"""Ticket 18 — Testes de integração do GRUPO_RETENCAO.

Cobre antimicrobianos (RDC 471/2021 + IN 83/2021) e agonistas de GLP-1
(IN 360/2025). Esses dois sistemas são INDEPENDENTES da Portaria
344/1998 — usam o campo `tipo_retencao`, não `classe_controle`.

Cobertura
---------
1. Antimicrobiano → receita_retencao
2. GLP-1 (semaglutida) → receita_retencao
3. Mistura (controlado + retenção + simples) → 3 receituários distintos
4. Portaria 344 PREVALECE sobre RDC 471 quando ambos preenchidos
5. tipo_retencao desconhecido → ValueError (NÃO simples)
6. Assinatura gov.br ATENDE para retenção (avancada é suficiente)
7. ICP-Brasil também atende (qualificada > avancada)
8. Fluxo completo: gerar → numerar (nao_requer_sncr) → PDF (emitido)
9. Itens com tipo_retencao não são atomizáveis
10. GRUPO_RETENCAO está ativo
11. TODO_REGULATORIO registrado no ledger ao gerar receita_retencao
12. RTC não existe mais — RRT é a abreviação correta
"""
from __future__ import annotations

import json
from datetime import datetime

from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Helpers
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
    itens_data: list[dict],   # cada dict: {classe_controle, tipo_retencao, nome}
    protocolo: str,
    tipo_certificado: str | None = None,
) -> int:
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
        for idx, dados in enumerate(itens_data, start=1):
            cur.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   posologia, status_item, classe_controle, tipo_retencao,
                   created_at, updated_at)
                VALUES (%s, %s, '500mg', 30, '1 cp 8/8h', 'pendente',
                        %s, %s, %s, %s)
                """,
                (
                    prescricao_id,
                    dados.get("nome") or f"MED-{idx}",
                    dados.get("classe_controle"),
                    dados.get("tipo_retencao"),
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


def _baixar_pdf(client, token: str, protocolo: str, receituario_id: int):
    return client.get(
        f"/prescricoes/{protocolo}/receituarios/{receituario_id}/pdf",
        headers=_headers(token),
    )


# ---------------------------------------------------------------------------
# 1–2. Antimicrobiano e GLP-1 → receita_retencao
# ---------------------------------------------------------------------------

def test_item_antimicrobiano_gera_receituario_retencao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[
            {"nome": "AMOXICILINA", "tipo_retencao": "antimicrobiano"},
        ],
        protocolo="TEST-RET-AMOX-001",
        tipo_certificado="gov_br_nuvem",
    )
    r = _gerar(client, token, "TEST-RET-AMOX-001")
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["total_receituarios"] == 1
    rec = body["receituarios"][0]
    assert rec["tipo"] == "receita_retencao"
    assert "Retenção" in rec["grupo_nome"]
    assert rec["assinatura_minima"] == "avancada"
    assert rec["vias"] == 2
    assert rec["requer_sncr"] is False
    assert rec["retencao_farmacia"] is True


def test_item_glp1_gera_receituario_retencao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[
            {"nome": "SEMAGLUTIDA", "tipo_retencao": "glp1_agonista"},
        ],
        protocolo="TEST-RET-GLP1-001",
        tipo_certificado="gov_br_nuvem",
    )
    r = _gerar(client, token, "TEST-RET-GLP1-001")
    assert r.status_code == 201, r.text
    rec = r.json()["receituarios"][0]
    assert rec["tipo"] == "receita_retencao"   # mesmo grupo de antimicrobiano
    assert rec["vias"] == 2
    assert rec["requer_sncr"] is False


# ---------------------------------------------------------------------------
# 3. Mistura: controlado + retenção + simples → 3 receituários distintos
# ---------------------------------------------------------------------------

def test_item_misto_controlado_e_retencao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        itens_data=[
            {"nome": "DIAZEPAM",       "classe_controle": "B1"},
            {"nome": "AMOXICILINA",    "tipo_retencao":   "antimicrobiano"},
            {"nome": "DIPIRONA"},  # nem classe nem retenção → simples
        ],
        protocolo="TEST-RET-MIX-001",
        tipo_certificado="A1",
    )
    r = _gerar(client, token, "TEST-RET-MIX-001")
    assert r.status_code == 201, r.text
    body = r.json()

    tipos = sorted(rec["tipo"] for rec in body["receituarios"])
    assert tipos == [
        "notificacao_receita_b",
        "receita_retencao",
        "receita_simples",
    ]
    assert body["total_receituarios"] == 3
    for rec in body["receituarios"]:
        assert len(rec["itens"]) == 1


# ---------------------------------------------------------------------------
# 4. Portaria 344 PREVALECE sobre RDC 471 quando ambos preenchidos
# ---------------------------------------------------------------------------

def test_classe_controle_prevalece_sobre_tipo_retencao():
    """Caso raro: item com D1 + tipo_retencao preenchido deve cair em
    GRUPO_D (Portaria 344 é mais restritiva e prevalece)."""
    from app.domain.motor_regulatorio import GRUPO_D, grupo_regulatorio

    g = grupo_regulatorio("D1", tipo_retencao="antimicrobiano")
    assert g.id_grupo == GRUPO_D.id_grupo
    assert g.tipo_receituario == "notificacao_receita_especial"


# ---------------------------------------------------------------------------
# 5. tipo_retencao desconhecido → ValueError (NÃO simples)
# ---------------------------------------------------------------------------

def test_tipo_retencao_invalido_motor_levanta_erro():
    """Motor regulatório DEVE rejeitar valor desconhecido — classificar
    como simples seria risco regulatório."""
    import pytest
    from app.domain.motor_regulatorio import grupo_regulatorio

    with pytest.raises(ValueError) as exc:
        grupo_regulatorio(None, tipo_retencao="valor_invalido")
    assert "valor_invalido" in str(exc.value)
    assert "antimicrobiano" in str(exc.value).lower()


def test_tipo_retencao_invalido_endpoint_retorna_422(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Endpoint /gerar deve retornar 422 quando item tem tipo_retencao
    inválido salvo no banco (bypass do schema Pydantic)."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[
            {"nome": "FAKE_DRUG", "tipo_retencao": "valor_invalido"},
        ],
        protocolo="TEST-RET-INVALIDO-001",
    )
    r = _gerar(client, token, "TEST-RET-INVALIDO-001")
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "valor_invalido" in detail or "desconhecido" in detail.lower()


# ---------------------------------------------------------------------------
# 6–7. Assinaturas que atendem retenção
# ---------------------------------------------------------------------------

def test_assinatura_govbr_aceita_para_retencao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "AMOXICILINA", "tipo_retencao": "antimicrobiano"}],
        protocolo="TEST-RET-GOVBR-001",
        tipo_certificado="gov_br_nuvem",
    )
    r = _gerar(client, token, "TEST-RET-GOVBR-001")
    assert r.status_code == 201
    rec = r.json()["receituarios"][0]
    assert rec["assinatura_valida"] is True
    assert rec["validacao_assinatura"]["nivel_presente"] == "avancada"


def test_assinatura_icp_tambem_aceita_para_retencao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        itens_data=[{"nome": "SEMAGLUTIDA", "tipo_retencao": "glp1_agonista"}],
        protocolo="TEST-RET-ICP-001",
        tipo_certificado="A1",
    )
    r = _gerar(client, token, "TEST-RET-ICP-001")
    assert r.status_code == 201
    rec = r.json()["receituarios"][0]
    assert rec["assinatura_valida"] is True
    assert rec["validacao_assinatura"]["nivel_presente"] == "qualificada"


# ---------------------------------------------------------------------------
# 8. Fluxo completo gerar → numerar → PDF para retenção
# ---------------------------------------------------------------------------

def test_fluxo_completo_retencao_gerar_numerar_pdf(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "AMOXICILINA", "tipo_retencao": "antimicrobiano"}],
        protocolo="TEST-RET-FLUXO-001",
        tipo_certificado="gov_br_nuvem",
    )
    r1 = _gerar(client, token, "TEST-RET-FLUXO-001")
    assert r1.status_code == 201
    rec = r1.json()["receituarios"][0]
    assert rec["tipo"] == "receita_retencao"

    # Numerar — deve cair em nao_requer_sncr (requer_sncr=False)
    r2 = _numerar(client, token, "TEST-RET-FLUXO-001")
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["total_numerados"] == 0
    assert body["total_nao_requer_sncr"] == 1
    rec_num = body["receituarios"][0]
    assert rec_num["status"] == "nao_requer_sncr"
    assert rec_num["numeracao_sncr"] is None

    # PDF — transiciona para emitido
    r3 = _baixar_pdf(client, token, "TEST-RET-FLUXO-001", rec["id"])
    assert r3.status_code == 200, r3.text
    assert r3.content[:4] == b"%PDF"
    assert "RRT" in r3.headers["content-disposition"]


# ---------------------------------------------------------------------------
# 9. Itens com tipo_retencao não são atomizáveis
# ---------------------------------------------------------------------------

def test_nao_atomiza_item_retencao():
    from app.domain.medicamento import (
        eh_item_atomizavel,
        motivo_nao_atomizavel,
    )

    # Antimicrobiano → bloqueado
    item_amox = {"nome_medicamento": "AMOXICILINA",
                 "tipo_retencao": "antimicrobiano"}
    assert eh_item_atomizavel(item_amox) is False
    motivo = motivo_nao_atomizavel(item_amox)
    assert motivo is not None
    assert "RDC 471" in motivo

    # GLP-1 → bloqueado
    item_glp1 = {"nome_medicamento": "SEMAGLUTIDA",
                 "tipo_retencao": "glp1_agonista"}
    assert eh_item_atomizavel(item_glp1) is False

    # Sem nada → atomizável
    item_simples = {"nome_medicamento": "DIPIRONA"}
    assert eh_item_atomizavel(item_simples) is True


# ---------------------------------------------------------------------------
# 10. GRUPO_RETENCAO ativo
# ---------------------------------------------------------------------------

def test_grupo_retencao_ativo():
    from app.domain.motor_regulatorio import GRUPO_RETENCAO

    assert GRUPO_RETENCAO.status_implementacao == "ativo"
    # Defesa-em-profundidade: garantir que o nome do grupo reflete a RDC
    assert "471" in GRUPO_RETENCAO.observacao
    assert GRUPO_RETENCAO.assinatura_minima == "avancada"
    assert GRUPO_RETENCAO.requer_sncr is False
    assert GRUPO_RETENCAO.vias == 2
    assert GRUPO_RETENCAO.retencao_farmacia is True


# ---------------------------------------------------------------------------
# 11. TODO_REGULATORIO registrado ao gerar receita_retencao
# ---------------------------------------------------------------------------

def test_gerar_retencao_registra_todo_regulatorio_provisorio(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Premissa atual: requer_sncr=False para retenção. Quando a Anvisa
    publicar ferramenta SNCR para esse fluxo, reavaliar — registramos
    um todo_regulatorio para garantir que essa decisão fique no ledger."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        itens_data=[{"nome": "AMOXICILINA", "tipo_retencao": "antimicrobiano"}],
        protocolo="TEST-RET-TODO-001",
        tipo_certificado="gov_br_nuvem",
    )
    r = _gerar(client, token, "TEST-RET-TODO-001")
    assert r.status_code == 201

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento = 'todo_regulatorio'
             ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-RET-TODO-001",),
        )
        row = cur.fetchone()
    assert row is not None, "TODO_REGULATORIO deveria ter sido registrado"
    payload = json.loads(row[0])
    assert payload["motivo"] == "requer_sncr_retencao_provisorio"
    assert payload["tipo_receituario"] == "receita_retencao"
    assert payload["ticket_referencia"] == "TICKET-18"


# ---------------------------------------------------------------------------
# 12. Abreviação correta — RRT (não RTC)
# ---------------------------------------------------------------------------

def test_abreviacao_receita_retencao_e_rrt():
    """Padronização Ticket 18: stub e PDF concordam em RRT."""
    from app.adapters.sncr_stub import _ABREV_TIPO
    from app.domain.pdf_receituario import tipo_abrev

    assert _ABREV_TIPO["receita_retencao"] == "RRT"
    assert tipo_abrev("receita_retencao") == "RRT"
    # RTC não deve mais aparecer em lugar algum
    assert "RTC" not in _ABREV_TIPO.values()


# ---------------------------------------------------------------------------
# 13. Schema de entrada da API valida tipo_retencao
# ---------------------------------------------------------------------------

def test_schema_api_aceita_tipo_retencao_valido():
    """O schema Pydantic do POST /prescricoes deve aceitar tipo_retencao
    e normalizar (case-insensitive)."""
    from app.routers.prescricoes import ItemIn

    item = ItemIn(
        nome_medicamento="amoxicilina",
        tipo_retencao="ANTIMICROBIANO",  # uppercase — deve normalizar
    )
    assert item.tipo_retencao == "antimicrobiano"

    item_glp1 = ItemIn(nome_medicamento="semaglutida", tipo_retencao="glp1_agonista")
    assert item_glp1.tipo_retencao == "glp1_agonista"


def test_schema_api_rejeita_tipo_retencao_invalido():
    import pytest
    from pydantic import ValidationError
    from app.routers.prescricoes import ItemIn

    with pytest.raises(ValidationError) as exc:
        ItemIn(nome_medicamento="X", tipo_retencao="bogus_value")
    assert "bogus_value" in str(exc.value)
