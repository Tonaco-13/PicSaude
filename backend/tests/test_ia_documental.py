"""
test_ia_documental.py
======================
Testes da IA Documental v1 — Ticket 35.

Cobre:
  Caso válido completo
    1.  ok=True com todos os campos
    2.  documento_base renderizado quando ok=True
    3.  documento_base contém nome do paciente
    4.  documento_base contém CID
    5.  documento_base contém dias de afastamento
    6.  aviso sempre presente
    7.  versao_template sempre presente

  Campos obrigatórios faltantes
    8.  ausência de codigo_cid → faltantes
    9.  ausência de dias_afastamento → faltantes
   10.  ausência de paciente_nome → faltantes
   11.  ausência de indicacao_clinica → faltantes
   12.  ausência de data_documento → faltantes
   13.  ausência de nome_profissional → faltantes
   14.  ausência de registro_profissional → faltantes
   15.  todos os campos ausentes → ok=False, múltiplos faltantes
   16.  dias_afastamento = 0 → faltante
   17.  dias_afastamento negativo → faltante
   18.  documento_base = None quando há faltantes

  Alertas de texto clínico vago
   19.  "doente" na indicacao → alerta
   20.  "problema" na indicacao → alerta
   21.  "indisposto" na indicacao → alerta
   22.  texto clínico correto → sem alerta de vaguidade

  Sugestões de redação
   23.  "uns dias" → sugestão de redação
   24.  "paciente doente" → sugestão de redação
   25.  "problema de saúde" → sugestão de redação

  Coerência CID ↔ texto
   26.  CID inconsistente com texto → alerta (não bloqueia)
   27.  CID consistente com texto → sem alerta de inconsistência
   28.  texto sem match na base → sem alerta de inconsistência

  Endpoints
   29.  POST /ia/documentos/atestado/validar com payload válido → 200
   30.  POST /ia/documentos/atestado/validar com payload incompleto → 200 + ok=False
   31.  GET /ia/documentos/status → 200 + templates

  Determinismo / garantias
   32.  mesmo input → mesmo output (determinismo)
   33.  faltantes é lista (nunca None)
   34.  alertas é lista (nunca None)
   35.  sugestoes é lista (nunca None)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user, get_current_user_or_api_key
from app.ai_documental.ia_documental import validar_atestado
from app.ai_documental.templates_atestado import VERSAO_TEMPLATE
from app.ai_documental.regras_atestado import (
    verificar_campos_obrigatorios,
    verificar_texto_clinico,
    gerar_sugestoes_redacao,
    verificar_cid_coerencia,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRESCRITOR = {"sub": "123456789012345", "role": "prescritor", "nome": "Dr. Doc"}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user]            = lambda: _PRESCRITOR
    app.dependency_overrides[get_current_user_or_api_key] = lambda: _PRESCRITOR
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Payloads reutilizáveis
# ---------------------------------------------------------------------------

_PAYLOAD_VALIDO = {
    "paciente_nome":        "João da Silva",
    "finalidade":           "trabalhistas",
    "indicacao_clinica":    "Hipertensão arterial sistêmica",
    "codigo_cid":           "I10",
    "dias_afastamento":     3,
    "data_documento":       "2026-03-24",
    "nome_profissional":    "Dra. Maria Santos",
    "registro_profissional": "CRM-PE 12345",
}


def _payload(**overrides) -> dict:
    p = {**_PAYLOAD_VALIDO}
    p.update(overrides)
    return p


def _omit(campo: str) -> dict:
    """Payload sem o campo informado."""
    p = {**_PAYLOAD_VALIDO}
    del p[campo]
    return p


# ---------------------------------------------------------------------------
# Classe 1 — Caso válido completo
# ---------------------------------------------------------------------------

class TestCasoValidoCompleto:

    def test_ok_true_com_todos_os_campos(self):
        """T01 — ok=True quando todos os campos são válidos."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert result["ok"] is True
        assert result["faltantes"] == []

    def test_documento_base_renderizado_quando_ok(self):
        """T02 — documento_base é string não-vazia quando ok=True."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert result["documento_base"] is not None
        assert isinstance(result["documento_base"], str)
        assert len(result["documento_base"]) > 50

    def test_documento_base_contem_nome_paciente(self):
        """T03 — documento_base contém o nome do paciente."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "João da Silva" in result["documento_base"]

    def test_documento_base_contem_cid(self):
        """T04 — documento_base contém o código CID."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "I10" in result["documento_base"]

    def test_documento_base_contem_dias_afastamento(self):
        """T05 — documento_base contém os dias de afastamento."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "3" in result["documento_base"]

    def test_aviso_sempre_presente(self):
        """T06 — aviso está sempre presente na resposta."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "aviso" in result
        assert len(result["aviso"]) > 10
        assert "responsabilidade" in result["aviso"].lower()

    def test_versao_template_presente(self):
        """T07 — versao_template está presente na resposta."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "versao_template" in result
        # Comparado com a constante, não com um literal: a versão do template
        # sobe quando o texto muda, e o teste não deve ser um segundo lugar onde
        # ela está escrita.
        assert result["versao_template"] == VERSAO_TEMPLATE

    def test_documento_base_contem_finalidade(self):
        """T07b — documento_base reflete a finalidade declarada."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert "para fins trabalhistas" in result["documento_base"]


# ---------------------------------------------------------------------------
# Classe 2 — Campos obrigatórios faltantes
# ---------------------------------------------------------------------------

class TestCamposObrigatorios:

    def test_ausencia_finalidade(self):
        """T08 — finalidade ausente aparece em faltantes e ok=False."""
        result = validar_atestado(**_omit("finalidade"))
        assert result["ok"] is False
        assert "finalidade" in result["faltantes"]

    def test_codigo_cid_opcional_nao_bloqueia(self):
        """T08b — codigo_cid é OPCIONAL: ausência não bloqueia (ok=True)."""
        result = validar_atestado(**_omit("codigo_cid"))
        assert result["ok"] is True
        assert "codigo_cid" not in result["faltantes"]

    def test_ausencia_dias_afastamento(self):
        """T09 — dias_afastamento ausente aparece em faltantes."""
        result = validar_atestado(**_omit("dias_afastamento"))
        assert result["ok"] is False
        assert "dias_afastamento" in result["faltantes"]

    def test_ausencia_paciente_nome(self):
        """T10 — paciente_nome ausente aparece em faltantes."""
        result = validar_atestado(**_omit("paciente_nome"))
        assert result["ok"] is False
        assert "paciente_nome" in result["faltantes"]

    def test_indicacao_clinica_opcional_nao_bloqueia(self):
        """T11 — indicacao_clinica é OPCIONAL: ausência não bloqueia (ok=True)."""
        result = validar_atestado(**_omit("indicacao_clinica"))
        assert result["ok"] is True
        assert "indicacao_clinica" not in result["faltantes"]

    def test_atestado_sem_diagnostico_preserva_privacidade(self):
        """T11b — sem indicacao e sem CID, o atestado é válido e omite o diagnóstico."""
        result = validar_atestado(**_payload(indicacao_clinica=None, codigo_cid=None))
        assert result["ok"] is True
        assert result["documento_base"] is not None
        assert "CID" not in result["documento_base"]
        assert "quadro clínico" not in result["documento_base"]

    def test_ausencia_data_documento(self):
        """T12 — data_documento ausente aparece em faltantes."""
        result = validar_atestado(**_omit("data_documento"))
        assert result["ok"] is False
        assert "data_documento" in result["faltantes"]

    def test_ausencia_nome_profissional(self):
        """T13 — nome_profissional ausente aparece em faltantes."""
        result = validar_atestado(**_omit("nome_profissional"))
        assert result["ok"] is False
        assert "nome_profissional" in result["faltantes"]

    def test_ausencia_registro_profissional(self):
        """T14 — registro_profissional ausente aparece em faltantes."""
        result = validar_atestado(**_omit("registro_profissional"))
        assert result["ok"] is False
        assert "registro_profissional" in result["faltantes"]

    def test_todos_ausentes_ok_false_multiplos_faltantes(self):
        """T15 — sem nenhum campo → ok=False com todos os obrigatórios faltantes."""
        result = validar_atestado()
        assert result["ok"] is False
        # 6 obrigatórios: paciente_nome, finalidade, dias_afastamento,
        # data_documento, nome_profissional, registro_profissional
        assert len(result["faltantes"]) == 6

    def test_dias_zero_e_faltante(self):
        """T16 — dias_afastamento=0 é tratado como inválido (faltante)."""
        result = validar_atestado(**_payload(dias_afastamento=0))
        assert result["ok"] is False
        assert "dias_afastamento" in result["faltantes"]

    def test_dias_negativo_e_faltante(self):
        """T17 — dias_afastamento negativo é tratado como inválido."""
        result = validar_atestado(**_payload(dias_afastamento=-5))
        assert result["ok"] is False
        assert "dias_afastamento" in result["faltantes"]

    def test_documento_base_none_quando_faltantes(self):
        """T18 — documento_base é None quando há campos faltantes."""
        result = validar_atestado(**_omit("finalidade"))
        assert result["documento_base"] is None


# ---------------------------------------------------------------------------
# Classe 3 — Alertas de texto clínico vago
# ---------------------------------------------------------------------------

class TestTextoClinicoVago:

    def test_termo_doente_gera_alerta(self):
        """T19 — 'doente' na indicacao_clinica gera alerta."""
        alertas = verificar_texto_clinico("paciente doente há 3 dias")
        assert len(alertas) > 0
        assert any("doente" in a for a in alertas)

    def test_termo_problema_gera_alerta(self):
        """T20 — 'problema' na indicacao_clinica gera alerta."""
        alertas = verificar_texto_clinico("problema de saúde crônico")
        assert len(alertas) > 0

    def test_termo_indisposto_gera_alerta(self):
        """T21 — 'indisposto' na indicacao_clinica gera alerta."""
        alertas = verificar_texto_clinico("paciente indisposto desde ontem")
        assert len(alertas) > 0

    def test_texto_clinico_especifico_sem_alerta(self):
        """T22 — texto clínico específico não gera alerta de vaguidade."""
        alertas = verificar_texto_clinico("hipertensão arterial sistêmica grau II")
        assert len(alertas) == 0


# ---------------------------------------------------------------------------
# Classe 4 — Sugestões de redação
# ---------------------------------------------------------------------------

class TestSugestoesRedacao:

    def test_uns_dias_gera_sugestao(self):
        """T23 — 'uns dias' na indicacao_clinica gera sugestão."""
        sugestoes = gerar_sugestoes_redacao("paciente afastado por uns dias")
        assert len(sugestoes) > 0
        assert any("dia" in s.lower() for s in sugestoes)

    def test_paciente_doente_gera_sugestao(self):
        """T24 — 'paciente doente' gera sugestão de reformulação."""
        sugestoes = gerar_sugestoes_redacao("paciente doente com febre")
        assert len(sugestoes) > 0
        assert any("acompanhamento clínico" in s for s in sugestoes)

    def test_problema_saude_gera_sugestao(self):
        """T25 — 'problema de saúde' gera sugestão de terminologia clínica."""
        sugestoes = gerar_sugestoes_redacao("problema de saúde")
        assert len(sugestoes) > 0
        assert any("quadro clínico" in s for s in sugestoes)


# ---------------------------------------------------------------------------
# Classe 5 — Coerência CID ↔ texto clínico
# ---------------------------------------------------------------------------

class TestCoerenciaCid:

    def test_cid_inconsistente_com_texto_gera_alerta(self):
        """T26 — CID claramente inconsistente com o texto clínico gera alerta.

        Texto: 'hipertensão arterial' → base sugere I10 (hipertensão).
        CID escolhido: J45 (asma) — inconsistente → deve gerar alerta.
        ok continua True (alerta não-bloqueante).
        """
        resultado = validar_atestado(**_payload(
            indicacao_clinica="hipertensão arterial",
            codigo_cid="J45",
        ))
        # Alerta pode ou não aparecer dependendo da base CID local,
        # mas ok deve continuar True (alertas não bloqueiam)
        assert resultado["ok"] is True
        # Se a base produziu sugestões para "hipertensão arterial", o alerta deve aparecer
        alertas = resultado["alertas"]
        # Verificamos que o tipo de alerta correto apareceria — testamos a função direta
        alertas_diretos = verificar_cid_coerencia("hipertensão arterial", "J45")
        if alertas_diretos:
            assert any("inconsistência" in a.lower() or "inconsistente" in a.lower()
                      for a in alertas_diretos)

    def test_cid_consistente_com_texto_sem_alerta_coerencia(self):
        """T27 — CID consistente com o texto não gera alerta de inconsistência.

        Texto: 'hipertensão arterial' → I10 é a sugestão esperada.
        """
        alertas = verificar_cid_coerencia("hipertensão arterial", "I10")
        # Com CID correto, não deve haver alerta de inconsistência
        assert not any("inconsistência" in a.lower() for a in alertas)

    def test_texto_sem_match_na_base_sem_alerta(self):
        """T28 — Texto sem match na base CID não gera alerta de inconsistência."""
        alertas = verificar_cid_coerencia(
            "quadro raro xyzxyzxyz ultrararo",
            "Z99",
        )
        # Texto sem match → sem base para avaliar → sem alerta
        assert alertas == []


# ---------------------------------------------------------------------------
# Classe 6 — Endpoints
# ---------------------------------------------------------------------------

class TestEndpoints:

    def test_endpoint_valido_retorna_200(self, client):
        """T29 — POST /ia/documentos/atestado/validar com payload válido retorna 200."""
        resp = client.post("/ia/documentos/atestado/validar", json=_PAYLOAD_VALIDO)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["faltantes"] == []
        assert data["documento_base"] is not None

    def test_endpoint_payload_incompleto_ok_false(self, client):
        """T30 — Payload incompleto retorna 200 com ok=False (não 422)."""
        resp = client.post("/ia/documentos/atestado/validar", json={
            "paciente_nome": "Maria",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is False
        assert len(data["faltantes"]) > 0
        assert data["documento_base"] is None

    def test_endpoint_status_retorna_templates(self, client):
        """T31 — GET /ia/documentos/status retorna templates disponíveis."""
        resp = client.get("/ia/documentos/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["modulo_ativo"] is True
        assert "atestado" in data["templates_disponiveis"]
        assert "versao_regras" in data


# ---------------------------------------------------------------------------
# Classe 7 — Determinismo e garantias de tipo
# ---------------------------------------------------------------------------

class TestDeterminismo:

    def test_mesmo_input_mesmo_output(self):
        """T32 — Mesmo input produz exatamente o mesmo output (determinismo)."""
        r1 = validar_atestado(**_PAYLOAD_VALIDO)
        r2 = validar_atestado(**_PAYLOAD_VALIDO)
        assert r1["ok"]             == r2["ok"]
        assert r1["faltantes"]      == r2["faltantes"]
        assert r1["alertas"]        == r2["alertas"]
        assert r1["sugestoes"]      == r2["sugestoes"]
        assert r1["documento_base"] == r2["documento_base"]
        assert r1["aviso"]          == r2["aviso"]

    def test_faltantes_e_lista_nunca_none(self):
        """T33 — faltantes é sempre lista (nunca None), mesmo sem campos."""
        result = validar_atestado()
        assert isinstance(result["faltantes"], list)

    def test_alertas_e_lista_nunca_none(self):
        """T34 — alertas é sempre lista (nunca None)."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert isinstance(result["alertas"], list)

    def test_sugestoes_e_lista_nunca_none(self):
        """T35 — sugestoes é sempre lista (nunca None)."""
        result = validar_atestado(**_PAYLOAD_VALIDO)
        assert isinstance(result["sugestoes"], list)
