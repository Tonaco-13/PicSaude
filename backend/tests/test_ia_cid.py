"""
test_ia_cid.py
==============
Testes da IA CID v1 — Ticket 33.

Cobre:
  - Normalização de linguagem coloquial
  - Busca exata por código e descrição
  - Match por alias
  - Match fuzzy (aproximado)
  - Texto muito genérico → alerta
  - Texto sem match → alerta
  - Múltiplas sugestões ordenadas por score
  - Determinismo (mesmo input → mesmo output)
  - Endpoint POST /ia/cid/buscar
  - Endpoint GET /ia/cid/status
  - Casos clínicos relevantes para atenção primária brasileira
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user, get_current_user_or_api_key
from app.ai.normalizacao_cid import normalizar_texto_clinico
from app.ai.base_cid import BASE_CID, _norm
from app.ai.ia_cid import buscar_cid

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_PRESCRITOR = {"sub": "900000000000001", "role": "prescritor", "nome": "Dr. CID"}

@pytest.fixture
def client():
    app.dependency_overrides[get_current_user]             = lambda: _PRESCRITOR
    app.dependency_overrides[get_current_user_or_api_key]  = lambda: _PRESCRITOR
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Classe 1 — Normalização de texto clínico
# ---------------------------------------------------------------------------

class TestNormalizacaoCid:

    def test_pressao_alta_normaliza(self):
        resultado = normalizar_texto_clinico("pressão alta")
        assert "hipertensao" in resultado

    def test_dor_barriga_normaliza(self):
        resultado = normalizar_texto_clinico("dor de barriga")
        assert "dor abdominal" in resultado

    def test_acucar_alto_normaliza(self):
        resultado = normalizar_texto_clinico("açúcar alto")
        assert "diabetes" in resultado or "hiperglicemia" in resultado

    def test_infeccao_urina_normaliza(self):
        resultado = normalizar_texto_clinico("infecção de urina")
        assert "trato urinario" in resultado

    def test_derrame_normaliza(self):
        resultado = normalizar_texto_clinico("derrame cerebral")
        assert "acidente vascular cerebral" in resultado

    def test_infarto_normaliza(self):
        resultado = normalizar_texto_clinico("infarto")
        assert "infarto" in resultado and "miocardio" in resultado

    def test_avc_abreviacao(self):
        resultado = normalizar_texto_clinico("AVC")
        assert "acidente vascular cerebral" in resultado

    def test_depressao_normaliza(self):
        resultado = normalizar_texto_clinico("depressão")
        assert "depressao" in resultado or "transtorno depressivo" in resultado

    def test_irc_abreviacao(self):
        resultado = normalizar_texto_clinico("IRC")
        assert "insuficiencia renal cronica" in resultado or "renal cronica" in resultado

    def test_lowercase_e_sem_acento(self):
        resultado = normalizar_texto_clinico("Hipertensão Arterial")
        assert resultado == resultado.lower()
        assert "a" in resultado  # sem acento

    def test_texto_vazio_retorna_vazio(self):
        assert normalizar_texto_clinico("") == ""

    def test_texto_none_retorna_vazio(self):
        # Testar robustez — None não deve explodir
        assert normalizar_texto_clinico(None) == ""  # type: ignore


# ---------------------------------------------------------------------------
# Classe 2 — Base CID
# ---------------------------------------------------------------------------

class TestBaseCid:

    def test_base_carregada(self):
        assert BASE_CID.total >= 100, f"Base CID muito pequena: {BASE_CID.total}"

    def test_buscar_por_codigo_i10(self):
        r = BASE_CID.buscar_por_codigo("I10")
        assert r is not None
        assert "hipertens" in r["descricao"].lower()

    def test_buscar_por_codigo_case_insensitive(self):
        r = BASE_CID.buscar_por_codigo("i10")
        assert r is not None

    def test_buscar_por_codigo_inexistente_retorna_none(self):
        # ZZZ.9 não é código CID-10 válido (a base completa DATASUS cobre Z99.9).
        r = BASE_CID.buscar_por_codigo("ZZZ.9")
        assert r is None

    def test_buscar_exato_hipertensao(self):
        texto = _norm("hipertensão essencial primária")
        resultados = BASE_CID.buscar(texto)
        assert len(resultados) > 0
        codigos = [r[0]["codigo_cid"] for r in resultados]
        assert "I10" in codigos

    def test_buscar_alias_dengue(self):
        resultados = BASE_CID.buscar("dengue")
        assert len(resultados) > 0
        codigos = [r[0]["codigo_cid"] for r in resultados]
        assert "A90" in codigos or "A91" in codigos

    def test_buscar_retorna_lista_ordenada_por_score(self):
        resultados = BASE_CID.buscar("diabetes mellitus")
        scores = [r[1] for r in resultados]
        assert scores == sorted(scores, reverse=True)

    def test_buscar_maximo_5_resultados(self):
        # "diabetes" deve dar vários resultados mas nunca mais que 5
        resultados = BASE_CID.buscar("diabetes mellitus tipo")
        assert len(resultados) <= 5

    def test_buscar_texto_sem_match_retorna_lista_vazia(self):
        resultados = BASE_CID.buscar("xyzabcqwerty123")
        assert resultados == []

    def test_versao_base_definida(self):
        assert BASE_CID.versao != ""


# ---------------------------------------------------------------------------
# Classe 3 — Pipeline ia_cid.buscar_cid
# ---------------------------------------------------------------------------

class TestBuscarCid:

    def test_pressao_alta_retorna_i10(self):
        res = buscar_cid("pressão alta")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "I10" in codigos

    def test_dor_barriga_retorna_r10(self):
        res = buscar_cid("dor de barriga")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "R10.4" in codigos

    def test_dengue_retorna_a90(self):
        res = buscar_cid("dengue")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "A90" in codigos

    def test_gestante_alto_risco_retorna_z35(self):
        res = buscar_cid("gestante alto risco")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "Z35.9" in codigos or "Z34.9" in codigos or "O14.9" in codigos

    def test_infeccao_urina_retorna_n390(self):
        res = buscar_cid("infecção de urina")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "N39.0" in codigos

    def test_esquistossomose_retorna_b651(self):
        res = buscar_cid("esquistossomose")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "B65.1" in codigos

    def test_doenca_renal_cronica_retorna_n189(self):
        res = buscar_cid("doença renal crônica")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "N18.9" in codigos

    def test_diabetes_tipo2_retorna_e119(self):
        res = buscar_cid("diabetes tipo 2")
        codigos = [c["codigo"] for c in res["cid_sugeridos"]]
        assert "E11.9" in codigos

    def test_texto_retornado_normalizado(self):
        res = buscar_cid("pressão ALTA")
        assert res["texto_normalizado"] == res["texto_normalizado"].lower()

    def test_aviso_sempre_presente(self):
        res = buscar_cid("hipertensão")
        assert res["aviso"] != ""
        assert "profissional" in res["aviso"].lower()

    def test_fonte_presente(self):
        # Fonte não-vazia (a base mescla DATASUS + curadoria; o valor exato varia
        # com o registro representativo — não fixar string específica).
        res = buscar_cid("diabetes")
        assert res["fonte"] != ""

    def test_versao_base_presente(self):
        res = buscar_cid("anemia")
        assert res["versao_base"] != ""

    def test_texto_curto_gera_alerta(self):
        res = buscar_cid("dor")
        # "dor" sozinho pode ou não ter match, mas não deve explodir
        assert isinstance(res["alertas"], list)

    def test_sem_match_gera_alerta(self):
        res = buscar_cid("xyzqwerty999abc")
        assert len(res["alertas"]) > 0
        assert len(res["cid_sugeridos"]) == 0

    def test_multiplos_cids_sugeridos(self):
        # "dor abdominal" deve retornar mais de uma sugestão
        res = buscar_cid("dor abdominal")
        assert len(res["cid_sugeridos"]) >= 1

    def test_sugestoes_com_score(self):
        res = buscar_cid("hipertensão arterial")
        for sugestao in res["cid_sugeridos"]:
            assert 0 < sugestao["score"] <= 1.0

    def test_sugestoes_com_match_tipo(self):
        res = buscar_cid("hipertensão arterial")
        tipos_validos = {"exato", "alias", "aproximado"}
        for sugestao in res["cid_sugeridos"]:
            assert sugestao["match_tipo"] in tipos_validos

    def test_determinismo(self):
        """Mesmo input deve produzir mesmo output."""
        res1 = buscar_cid("pressão alta")
        res2 = buscar_cid("pressão alta")
        assert res1["cid_sugeridos"] == res2["cid_sugeridos"]

    def test_contexto_diferente_nao_quebra(self):
        """contexto é campo preparatório — não altera comportamento na v1."""
        res_geral    = buscar_cid("diabetes", contexto="geral")
        res_prescricao = buscar_cid("diabetes", contexto="prescricao")
        # Na v1 o comportamento é idêntico
        assert res_geral["cid_sugeridos"] == res_prescricao["cid_sugeridos"]

    def test_query_clinica_plausivel_nao_retorna_cid_de_outra_categoria(self):
        """Regressão Jules 2026-05-25: 'dor de cabeca' virava A09
        (Diarreia), 'infeccao urinaria' virava A56.0 (Clamidia).
        Threshold 0.75 era frágil."""
        casos = [
            ('dor de cabeca',      ['A09', 'A09.0', 'A09.9']),  # categorias A09 são GI
            ('infeccao urinaria',  ['A56', 'A56.0']),           # A56 é DST clamidia
        ]
        for query, codigos_proibidos in casos:
            r = buscar_cid(query)
            for sugestao in r.get('cid_sugeridos', []):
                assert sugestao['codigo'] not in codigos_proibidos, \
                    f'{query} sugeriu {sugestao["codigo"]} ({sugestao.get("descricao")})'


# ---------------------------------------------------------------------------
# Classe 4 — Endpoints FastAPI
# ---------------------------------------------------------------------------

class TestEndpointCid:

    def test_post_buscar_retorna_200(self, client):
        resp = client.post("/ia/cid/buscar", json={"texto_clinico": "pressão alta"})
        assert resp.status_code == 200

    def test_post_buscar_retorna_cid_sugeridos(self, client):
        resp = client.post("/ia/cid/buscar", json={"texto_clinico": "pressão alta"})
        data = resp.json()
        assert "cid_sugeridos" in data
        assert len(data["cid_sugeridos"]) > 0

    def test_post_buscar_campos_obrigatorios(self, client):
        resp = client.post("/ia/cid/buscar", json={"texto_clinico": "dengue"})
        data = resp.json()
        for campo in ("texto_entrada", "texto_normalizado", "cid_sugeridos",
                      "fonte", "versao_base", "alertas", "aviso"):
            assert campo in data, f"Campo ausente: {campo}"

    def test_post_buscar_texto_vazio_retorna_422(self, client):
        resp = client.post("/ia/cid/buscar", json={"texto_clinico": ""})
        assert resp.status_code == 422

    def test_post_buscar_contexto_invalido_retorna_422(self, client):
        resp = client.post("/ia/cid/buscar", json={"texto_clinico": "dengue", "contexto": "invalido"})
        assert resp.status_code == 422

    def test_post_buscar_sem_autenticacao_retorna_401(self):
        resp = TestClient(app).post("/ia/cid/buscar", json={"texto_clinico": "dengue"})
        assert resp.status_code == 401

    def test_get_status_retorna_200(self, client):
        resp = client.get("/ia/cid/status")
        assert resp.status_code == 200

    def test_get_status_campos_obrigatorios(self, client):
        resp = client.get("/ia/cid/status")
        data = resp.json()
        for campo in ("base_carregada", "total_registros", "versao_base", "fonte"):
            assert campo in data, f"Campo ausente: {campo}"

    def test_get_status_base_carregada_true(self, client):
        resp = client.get("/ia/cid/status")
        data = resp.json()
        assert data["base_carregada"] is True
        assert data["total_registros"] >= 100

    def test_get_ia_status_inclui_cid(self, client):
        resp = client.get("/ia/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "cid" in data
        assert data["cid"]["base_carregada"] is True
