"""Ticket 19 — Testes de regras de validade e emissão de receituários.

Estratégia
----------
Testes unitários puros (1-12) para funções de regras_receituario.py,
sem banco de dados. Testes de integração (13-15) para validar o fluxo
end-to-end via endpoints POST /gerar e GET /pdf.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from app.domain.regras_receituario import (
    RegraReceituario,
    REGRAS_RECEITUARIO,
    VALIDADE_POR_TIPO_RETENCAO,
    obter_regra_receituario,
    calcular_data_validade,
    receituario_expirado,
    assinatura_atende_minimo,
    status_permite_pdf,
    validar_emissao_receituario,
)
from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Testes unitários puros (1-12)
# ---------------------------------------------------------------------------

def test_regras_tipos_conhecidos():
    """Verifica que todos os 6 tipos têm regra definida."""
    tipos_esperados = {
        "notificacao_receita_a",
        "notificacao_receita_b",
        "receita_controle_especial",
        "notificacao_receita_especial",
        "receita_retencao",
        "receita_simples",
    }
    tipos_conhecidos = set(REGRAS_RECEITUARIO.keys())
    assert tipos_conhecidos == tipos_esperados


def test_validade_notificacao_b_30_dias():
    """Notificação B tem 30 dias de validade."""
    regra = obter_regra_receituario("notificacao_receita_b")
    assert regra.validade_dias == 30
    assert regra.vias == 2
    assert regra.retencao_farmacia is True
    assert regra.requer_sncr is True


def test_validade_receita_retencao_10_dias():
    """Receita de retenção tem 10 dias (antimicrobianos)."""
    regra = obter_regra_receituario("receita_retencao")
    assert regra.validade_dias == 10
    assert regra.assinatura_minima == "avancada"
    assert regra.requer_sncr is False


def test_receita_simples_sem_validade():
    """Receita simples não tem validade (None)."""
    regra = obter_regra_receituario("receita_simples")
    assert regra.validade_dias is None
    assert regra.vias == 1
    assert regra.retencao_farmacia is False
    assert regra.requer_sncr is False


def test_calcular_data_validade():
    """Testa cálculo de data_validade = data_emissao + validade_dias."""
    agora = datetime(2026, 4, 26, 10, 0, 0)

    # Notificação B: 30 dias
    validade_b = calcular_data_validade(agora, "notificacao_receita_b")
    assert validade_b == datetime(2026, 5, 26, 10, 0, 0)

    # Receita de retenção: 10 dias
    validade_ret = calcular_data_validade(agora, "receita_retencao")
    assert validade_ret == datetime(2026, 5, 6, 10, 0, 0)

    # Receita simples: None
    validade_simples = calcular_data_validade(agora, "receita_simples")
    assert validade_simples is None


def test_validade_condicional_antimicrobiano_10_dias():
    """Receita retenção + antimicrobiano = 10 dias (RDC 471/2021)."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    validade = calcular_data_validade(
        agora, "receita_retencao", tipo_retencao="antimicrobiano",
    )
    assert validade == datetime(2026, 5, 6, 10, 0, 0)  # +10 dias


def test_validade_condicional_glp1_90_dias():
    """Receita retenção + GLP-1 = 90 dias (IN 360/2025)."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    validade = calcular_data_validade(
        agora, "receita_retencao", tipo_retencao="glp1_agonista",
    )
    assert validade == datetime(2026, 7, 25, 10, 0, 0)  # +90 dias


def test_validade_retencao_sem_tipo_usa_fallback():
    """Receita retenção sem tipo_retencao usa fallback de 10 dias."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    validade = calcular_data_validade(agora, "receita_retencao")
    assert validade == datetime(2026, 5, 6, 10, 0, 0)  # fallback = 10


def test_validade_retencao_tipo_desconhecido_usa_fallback():
    """Receita retenção com tipo_retencao desconhecido usa fallback."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    validade = calcular_data_validade(
        agora, "receita_retencao", tipo_retencao="outro_tipo",
    )
    assert validade == datetime(2026, 5, 6, 10, 0, 0)  # fallback = 10


def test_tipo_retencao_ignorado_para_outros_tipos():
    """tipo_retencao é ignorado para tipos que não são receita_retencao."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    # Mesmo passando tipo_retencao, Notificação B deve dar 30 dias
    validade = calcular_data_validade(
        agora, "notificacao_receita_b", tipo_retencao="glp1_agonista",
    )
    assert validade == datetime(2026, 5, 26, 10, 0, 0)  # 30 dias inalterado


def test_mapa_validade_por_tipo_retencao():
    """Verifica valores do mapa VALIDADE_POR_TIPO_RETENCAO."""
    assert VALIDADE_POR_TIPO_RETENCAO["antimicrobiano"] == 10
    assert VALIDADE_POR_TIPO_RETENCAO["glp1_agonista"] == 90


def test_receituario_expirado_helper():
    """Testa helper receituario_expirado."""
    agora = datetime(2026, 4, 26, 10, 0, 0)

    # Data no passado
    data_passada = datetime(2026, 4, 20, 10, 0, 0)
    assert receituario_expirado(data_passada, agora) is True

    # Data no futuro
    data_futura = datetime(2026, 5, 1, 10, 0, 0)
    assert receituario_expirado(data_futura, agora) is False

    # Data atual (não expirado se for >=)
    assert receituario_expirado(agora, agora) is False

    # None nunca expira
    assert receituario_expirado(None, agora) is False


def test_assinatura_atende_minimo():
    """Testa hierarquia de assinatura: qualificada > avancada > nenhuma."""
    # Qualificada atende todas
    assert assinatura_atende_minimo("qualificada", "nenhuma") is True
    assert assinatura_atende_minimo("qualificada", "avancada") is True
    assert assinatura_atende_minimo("qualificada", "qualificada") is True

    # Avançada atende nenhuma e avançada
    assert assinatura_atende_minimo("avancada", "nenhuma") is True
    assert assinatura_atende_minimo("avancada", "avancada") is True
    assert assinatura_atende_minimo("avancada", "qualificada") is False

    # Nenhuma atende apenas nenhuma
    assert assinatura_atende_minimo("nenhuma", "nenhuma") is True
    assert assinatura_atende_minimo("nenhuma", "avancada") is False
    assert assinatura_atende_minimo("nenhuma", "qualificada") is False

    # None = nenhuma
    assert assinatura_atende_minimo(None, "nenhuma") is True
    assert assinatura_atende_minimo(None, "avancada") is False


def test_status_permite_pdf():
    """Testa quais status permitem PDF."""
    permitidos = {"numerado_stub", "numerado", "nao_requer_sncr", "emitido"}
    bloqueados = {"gerado", "cancelado", "dispensado", "expirado"}

    for status in permitidos:
        assert status_permite_pdf(status) is True

    for status in bloqueados:
        assert status_permite_pdf(status) is False


def test_validar_emissao_receituario_ok():
    """Validação bem-sucedida para cenário válido."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    data_validade = datetime(2026, 5, 26, 10, 0, 0)  # futura

    valido, motivos = validar_emissao_receituario(
        tipo_receituario="notificacao_receita_b",
        status="numerado",
        data_validade=data_validade,
        assinatura_modo="icp_brasil_local",
        numeracao_sncr="12345",
    )
    assert valido is True
    assert motivos == []


def test_validar_emissao_expirado_bloqueia():
    """Receituário expirado é bloqueado (exceto em status=emitido)."""
    agora = datetime(2026, 4, 26, 10, 0, 0)
    data_validade = datetime(2026, 4, 20, 10, 0, 0)  # passada

    # Status numerado — deve bloquear
    valido, motivos = validar_emissao_receituario(
        tipo_receituario="notificacao_receita_b",
        status="numerado",
        data_validade=data_validade,
    )
    assert valido is False
    assert any("expirado" in m.lower() for m in motivos)

    # Status emitido (re-download) — não bloqueia por expiração
    valido, motivos = validar_emissao_receituario(
        tipo_receituario="notificacao_receita_b",
        status="emitido",
        data_validade=data_validade,
    )
    assert valido is True


def test_validar_emissao_status_invalido():
    """Status inválido é bloqueado."""
    valido, motivos = validar_emissao_receituario(
        tipo_receituario="notificacao_receita_b",
        status="gerado",  # status não permite PDF
    )
    assert valido is False
    assert any("não permite geração de PDF" in m for m in motivos)


def test_obter_regra_tipo_invalido():
    """Tipo desconhecido levanta ValueError."""
    with pytest.raises(ValueError, match="Tipo de receituário desconhecido"):
        obter_regra_receituario("tipo_inexistente")


# ---------------------------------------------------------------------------
# Testes de integração (13-15) — com banco via fixtures
# ---------------------------------------------------------------------------

def _inserir_prescritor_paciente_basico(outer_conn):
    """Helper: insere prescritor + paciente. Devolve (prescritor_id, paciente_id)."""
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


def _inserir_prescricao_com_items(
    outer_conn,
    protocolo: str,
    classes_itens: list[str | None],
    assinatura_modo: str | None = None,
):
    """Helper: insere prescrição + itens. Devolve prescricao_id."""
    prescritor_id, paciente_id = _inserir_prescritor_paciente_basico(outer_conn)
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


def test_gerar_receituario_preenche_data_validade(
    client, outer_conn, seed_usuario
):
    """Integration: POST /gerar preenche data_validade nos receituários."""
    token = obter_token_prescritor(client, seed_usuario)

    # Prescrição com 1 item Notificação B (30 dias)
    _inserir_prescricao_com_items(
        outer_conn,
        protocolo="TEST-VALIDADE-001",
        classes_itens=["B1"],
        assinatura_modo="icp_brasil_local",
    )

    r = client.post(
        "/prescricoes/TEST-VALIDADE-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()

    # Deve ter 1 receituário
    assert body["total_receituarios"] == 1
    rec = body["receituarios"][0]

    # data_validade deve estar preenchida e ser ~30 dias no futuro
    assert rec["data_validade"] is not None
    data_val = datetime.fromisoformat(rec["data_validade"])
    now = datetime.utcnow()
    dias_diff = (data_val - now).days
    assert 29 <= dias_diff <= 31  # ~30 dias (tolerância de 1 dia)


def test_receituario_simples_sem_validade_em_resposta(
    client, outer_conn, seed_usuario
):
    """Integration: receita_simples tem data_validade=None."""
    token = obter_token_prescritor(client, seed_usuario)

    # Prescrição sem controle
    _inserir_prescricao_com_items(
        outer_conn,
        protocolo="TEST-SIMPLES-VALIDADE-001",
        classes_itens=[None],
        assinatura_modo=None,
    )

    r = client.post(
        "/prescricoes/TEST-SIMPLES-VALIDADE-001/receituarios/gerar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 201, r.text
    body = r.json()

    rec = body["receituarios"][0]
    assert rec["tipo"] == "receita_simples"
    assert rec["data_validade"] is None


def test_pdf_receituario_expirado_bloqueia_422(
    client, outer_conn, seed_usuario
):
    """Integration: receituário expirado no status numerado bloqueia PDF com 422."""
    token = obter_token_prescritor(client, seed_usuario)

    # Insere prescrição + receituário com data_validade no passado
    prescritor_id, paciente_id = _inserir_prescritor_paciente_basico(outer_conn)
    now = datetime.utcnow()

    with outer_conn.cursor() as cur:
        # Prescrição
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', %s, 'nova', %s, %s, %s)
            RETURNING id
            """,
            ("TEST-EXPIRADO-001", prescritor_id, paciente_id, "icp_brasil_local", now, now, now),
        )
        prescricao_id = cur.fetchone()[0]

        # Item B1
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               posologia, status_item, classe_controle, created_at, updated_at)
            VALUES (%s, %s, '500mg', 10, '1 cp/dia', 'pendente', %s, %s, %s)
            RETURNING id
            """,
            (prescricao_id, "MEDICAMENTO B1", "B1", now, now),
        )

        # Receituário com data_validade = 1 dia atrás (expirado)
        data_validade_expirada = now - timedelta(days=1)
        cur.execute(
            """
            INSERT INTO receituarios
              (prescricao_id, tipo_receituario, grupo_id, grupo_nome,
               assinatura_minima, assinatura_valida, vias, retencao_farmacia,
               requer_sncr, status, numeracao_sncr, created_at, data_validade)
            VALUES (%s, %s, %s, %s, %s, true, 2, true, true, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                prescricao_id, "notificacao_receita_b", "notificacao_receita_b",
                "Notificação de Receita B", "qualificada", "numerado",
                "123456", now, data_validade_expirada,
            ),
        )
        receituario_id = cur.fetchone()[0]

    # Tenta baixar PDF — deve bloquear com 422
    r = client.get(
        f"/prescricoes/TEST-EXPIRADO-001/receituarios/{receituario_id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, f"Esperava 422 para receituário expirado, got {r.status_code}: {r.text}"
    assert "expirado" in r.text.lower()


def test_reemissao_pdf_emitido_sempre_permitida(
    client, outer_conn, seed_usuario
):
    """Integration: re-download de status=emitido expirado não é bloqueado por validade."""
    token = obter_token_prescritor(client, seed_usuario)

    # Insere prescrição + receituário expirado mas status=emitido com sncr
    prescritor_id, paciente_id = _inserir_prescritor_paciente_basico(outer_conn)
    now = datetime.utcnow()

    with outer_conn.cursor() as cur:
        # Prescrição
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', %s, 'nova', %s, %s, %s)
            RETURNING id
            """,
            ("TEST-REEMISSAO-001", prescritor_id, paciente_id, "icp_brasil_local", now, now, now),
        )
        prescricao_id = cur.fetchone()[0]

        # Item B1
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               posologia, status_item, classe_controle, created_at, updated_at)
            VALUES (%s, %s, '500mg', 10, '1 cp/dia', 'pendente', %s, %s, %s)
            RETURNING id
            """,
            (prescricao_id, "MEDICAMENTO B1", "B1", now, now),
        )

        # Receituário expirado MAS status=emitido (com numeracao_sncr)
        data_validade_expirada = now - timedelta(days=5)
        cur.execute(
            """
            INSERT INTO receituarios
              (prescricao_id, tipo_receituario, grupo_id, grupo_nome,
               assinatura_minima, assinatura_valida, vias, retencao_farmacia,
               requer_sncr, status, numeracao_sncr, created_at, data_validade,
               emitido_em)
            VALUES (%s, %s, %s, %s, %s, true, 2, true, true, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                prescricao_id, "notificacao_receita_b", "notificacao_receita_b",
                "Notificação de Receita B", "qualificada", "emitido",
                "123456", now, data_validade_expirada, now,
            ),
        )
        receituario_id = cur.fetchone()[0]

    # Re-download deve funcionar (200 OK) mesmo com validade expirada
    r = client.get(
        f"/prescricoes/TEST-REEMISSAO-001/receituarios/{receituario_id}/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"Re-download de emitido expirado deve retornar 200, got {r.status_code}: {r.text}"
    assert r.headers["content-type"] == "application/pdf"
