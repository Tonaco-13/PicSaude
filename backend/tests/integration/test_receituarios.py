"""Ticket 15 — testes de integração do motor regulatório RDC 1.000/2025.

Estratégia de setup
-------------------
Em vez de passar pelo endpoint `POST /prescricoes` (que tem validações de
assinatura ICP/gov.br complexas — requer `cert_pem`+`assinatura_b64` pareados
para modos com validade CFM), cada teste insere a prescrição **diretamente**
no banco via `outer_conn`. Isso deixa o teste focar no que queremos
validar: o comportamento do motor regulatório ao combinar
`assinatura_modo` × `classe_controle` dos itens.

Isolamento: o SAVEPOINT da outer tx (conftest.py) garante que nada do que
o teste insere/cria pelo endpoint fica no banco após o teardown.
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
# Helpers de setup (inserção direta no banco via outer_conn)
# ---------------------------------------------------------------------------

def _inserir_prescritor_e_paciente(outer_conn) -> tuple[int, int]:
    """Insere prescritor + paciente, devolve (prescritor_id, paciente_id)."""
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
) -> int:
    """Insere prescrição + itens com as classes dadas. Devolve prescricao_id."""
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    now = datetime.utcnow()
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
    return prescricao_id


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _gerar(client, token: str, protocolo: str):
    return client.post(
        f"/prescricoes/{protocolo}/receituarios/gerar",
        headers=_headers(token),
    )


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_prescricao_sem_controlados_gera_receita_simples(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo=None,
        classes_itens=[None, None],
        protocolo="TEST-RECSIMPLES-001",
    )

    r = _gerar(client, token, "TEST-RECSIMPLES-001")
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["total_receituarios"] == 1
    rec = body["receituarios"][0]
    assert rec["tipo"] == "receita_simples"
    assert rec["assinatura_minima"] == "nenhuma"
    assert rec["assinatura_valida"] is True  # "nenhuma" é sempre atendido
    assert len(rec["itens"]) == 2


def test_prescricao_com_b1_gera_notificacao_b(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1"],
        protocolo="TEST-B1-001",
    )

    r = _gerar(client, token, "TEST-B1-001")
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["total_receituarios"] == 1
    rec = body["receituarios"][0]
    assert rec["tipo"] == "notificacao_receita_b"
    assert rec["assinatura_minima"] == "qualificada"
    assert rec["assinatura_valida"] is True
    assert rec["requer_sncr"] is True
    assert rec["retencao_farmacia"] is True


def test_prescricao_mista_gera_multiplos_receituarios(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=[None, "B1", "A1"],
        protocolo="TEST-MISTA-001",
    )

    r = _gerar(client, token, "TEST-MISTA-001")
    assert r.status_code == 201, r.text
    body = r.json()

    tipos = [rec["tipo"] for rec in body["receituarios"]]
    # Ordem por severidade: A (1) → B (2) → Simples (99)
    assert tipos == [
        "notificacao_receita_a",
        "notificacao_receita_b",
        "receita_simples",
    ]
    assert body["total_receituarios"] == 3
    for rec in body["receituarios"]:
        assert len(rec["itens"]) == 1


def test_agrupamento_mesmo_grupo(
    client, outer_conn, seed_usuario, seed_paciente
):
    """2×B1 + 1×B2 → 1 único receituário (notificação B) com 3 itens."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1", "B1", "B2"],
        protocolo="TEST-GRUPO-B-001",
    )

    r = _gerar(client, token, "TEST-GRUPO-B-001")
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["total_receituarios"] == 1
    rec = body["receituarios"][0]
    assert rec["tipo"] == "notificacao_receita_b"
    assert len(rec["itens"]) == 3


def test_validacao_assinatura_icp_atende_qualificada(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1"],
        protocolo="TEST-ICP-QUALIFICADA",
    )

    r = _gerar(client, token, "TEST-ICP-QUALIFICADA")
    assert r.status_code == 201
    rec = r.json()["receituarios"][0]
    assert rec["assinatura_valida"] is True
    assert rec["validacao_assinatura"]["nivel_presente"] == "qualificada"
    assert rec["validacao_assinatura"]["nivel_exigido"] == "qualificada"


def test_validacao_assinatura_govbr_nao_atende_qualificada(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="gov_br_nuvem",
        classes_itens=["A1"],
        protocolo="TEST-GOVBR-INSUFICIENTE",
    )

    r = _gerar(client, token, "TEST-GOVBR-INSUFICIENTE")
    assert r.status_code == 201
    body = r.json()
    rec = body["receituarios"][0]
    assert rec["assinatura_valida"] is False
    assert body["todos_assinatura_valida"] is False
    motivo = rec["validacao_assinatura"]["motivo_rejeicao"]
    assert motivo is not None
    assert "qualificada" in motivo
    assert "avancada" in motivo


def test_validacao_assinatura_govbr_atende_avancada(outer_conn):
    """Valida diretamente no motor que gov.br atende 'avancada'.

    O Grupo 5 (retencao) é o único que exige nível 'avancada' hoje, mas
    nenhuma `classe_controle` atual mapeia para ele (pendente de
    classificação). Testamos a função do motor diretamente em vez de
    passar por uma prescrição real.
    """
    from app.domain.motor_regulatorio import (
        GRUPO_RETENCAO,
        Receituario as ReceituarioDTO,
        validar_assinatura_para_receituario,
    )

    receituario = ReceituarioDTO(
        tipo=GRUPO_RETENCAO.tipo_receituario,
        grupo_id=GRUPO_RETENCAO.id_grupo,
        grupo_nome=GRUPO_RETENCAO.nome,
        prescricao_id=0,
        protocolo_prescricao="x",
        itens=[],
        assinatura_minima=GRUPO_RETENCAO.assinatura_minima,
        vias=GRUPO_RETENCAO.vias,
        retencao_farmacia=GRUPO_RETENCAO.retencao_farmacia,
        requer_sncr=GRUPO_RETENCAO.requer_sncr,
        severidade=GRUPO_RETENCAO.severidade,
    )

    resultado = validar_assinatura_para_receituario(
        {"assinatura_modo": "gov_br_nuvem"}, receituario
    )
    assert resultado.valido is True
    assert resultado.nivel_presente == "avancada"
    assert resultado.nivel_exigido == "avancada"


def test_idempotencia_nao_duplica(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1", None],
        protocolo="TEST-IDEMP-001",
    )

    r1 = _gerar(client, token, "TEST-IDEMP-001")
    assert r1.status_code == 201
    ids1 = sorted(rec["id"] for rec in r1.json()["receituarios"])
    assert r1.json()["idempotente"] is False

    r2 = _gerar(client, token, "TEST-IDEMP-001")
    assert r2.status_code == 201
    ids2 = sorted(rec["id"] for rec in r2.json()["receituarios"])

    assert ids1 == ids2, "Segunda chamada deve retornar os mesmos receituários"
    assert r2.json()["idempotente"] is True

    # Confirma no banco que não há duplicação de receituários ativos
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM receituarios r
            JOIN prescricoes p ON p.id = r.prescricao_id
            WHERE p.protocolo = %s AND r.substituido_em IS NULL
            """,
            ("TEST-IDEMP-001",),
        )
        total = cur.fetchone()[0]
    assert total == 2


def test_classe_desconhecida_gera_erro(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["X9"],
        protocolo="TEST-CLASSE-INVALIDA",
    )

    r = _gerar(client, token, "TEST-CLASSE-INVALIDA")
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "X9" in detail or "desconhecida" in detail.lower()


def test_evento_ledger_registrado(
    client, outer_conn, seed_usuario, seed_paciente
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=[None, "B1"],
        protocolo="TEST-LEDGER-001",
    )

    r = _gerar(client, token, "TEST-LEDGER-001")
    assert r.status_code == 201

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
            JOIN prescricoes p ON p.id = pe.prescricao_id
            WHERE p.protocolo = %s AND pe.tipo_evento = 'receituarios_gerados'
            ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-LEDGER-001",),
        )
        row = cur.fetchone()

    assert row is not None, "Evento 'receituarios_gerados' não foi registrado no ledger"
    payload = json.loads(row[0])
    assert payload["quantidade"] == 2
    assert set(payload["tipos"]) == {"notificacao_receita_b", "receita_simples"}
    assert payload["ticket_referencia"] == "TICKET-15"
