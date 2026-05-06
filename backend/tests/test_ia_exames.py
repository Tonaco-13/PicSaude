"""
test_ia_exames.py
=================
Testes unitários e de integração da IA de exames v1 — Ticket 31.

COBERTURA
---------
  1. Normalização textual (normalizacao_exame)
  2. Base TUSS — lookup exato, alias, fuzzy, ausente
  3. Função principal (ia_exames.normalizar_exame) — pipeline completo
  4. Endpoint POST /ia/exames/normalizar (via TestClient)
  5. Endpoint GET /ia/status — inclui chave "exames"

Sem banco de dados. Sem dependências externas além da stdlib e rapidfuzz.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.ai.normalizacao_exame import normalizar_nome_exame
from app.ai.tuss_base import BASE_TUSS
from app.ai.ia_exames import normalizar_exame


# ---------------------------------------------------------------------------
# Fixture: cliente autenticado como prescritor
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    from app.main import app
    from app.auth.dependencies import get_current_user

    _prescritor = {"sub": "prescritor:test", "role": "prescritor"}
    app.dependency_overrides[get_current_user] = lambda: _prescritor

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Normalização textual
# ---------------------------------------------------------------------------

class TestNormalizacaoExame:

    def test_lowercase(self):
        assert normalizar_nome_exame("HEMOGRAMA") == "hemograma"

    def test_remove_acentos(self):
        resultado = normalizar_nome_exame("Glicemia de Jejum")
        assert "a" in resultado   # sem acento
        assert "Glicemia" not in resultado

    def test_abreviacao_us(self):
        resultado = normalizar_nome_exame("US abdome")
        assert "ultrassonografia" in resultado
        assert "abdome" in resultado

    def test_abreviacao_ecg(self):
        assert normalizar_nome_exame("ECG") == "eletrocardiograma"

    def test_abreviacao_tsh(self):
        assert normalizar_nome_exame("TSH") == "tireoestimulante"

    def test_abreviacao_rm(self):
        resultado = normalizar_nome_exame("RM crânio")
        assert "ressonancia magnetica" in resultado

    def test_abreviacao_tc(self):
        resultado = normalizar_nome_exame("TC tórax")
        assert "tomografia computadorizada" in resultado

    def test_separador_barra(self):
        resultado = normalizar_nome_exame("TGO/TGP")
        assert "/" not in resultado
        assert "aspartato aminotransferase" in resultado

    def test_parenteses_removidos(self):
        resultado = normalizar_nome_exame("Hemograma (completo)")
        assert "(" not in resultado
        assert ")" not in resultado

    def test_espacos_multiplos_normalizados(self):
        resultado = normalizar_nome_exame("  hemograma   completo  ")
        assert "  " not in resultado
        assert resultado == resultado.strip()

    def test_string_vazia(self):
        assert normalizar_nome_exame("") == ""


# ---------------------------------------------------------------------------
# 2. Base TUSS — lookup
# ---------------------------------------------------------------------------

class TestBaseTUSS:

    def test_total_registros_positivo(self):
        assert BASE_TUSS.total > 0

    def test_versao_definida(self):
        assert BASE_TUSS.versao.startswith("tuss_local")

    def test_buscar_exato_hemograma(self):
        reg = BASE_TUSS.buscar_exato("hemograma completo com contagem de plaquetas")
        assert reg is not None
        assert reg["codigo_tuss"] == "40301079"

    def test_buscar_alias_hemograma(self):
        reg = BASE_TUSS.buscar_exato("hemograma")
        assert reg is not None
        assert reg["codigo_tuss"] == "40301079"

    def test_buscar_alias_glicemia(self):
        reg = BASE_TUSS.buscar_exato("glicemia jejum")
        assert reg is not None
        assert "glicos" in reg["nome_padrao"].lower() or "glicos" in reg["nome_busca"]

    def test_buscar_exato_inexistente(self):
        reg = BASE_TUSS.buscar_exato("exame inexistente xyz abc 999")
        assert reg is None

    def test_buscar_fuzzy_encontra_proximo(self):
        # "hemograma complet" deve encontrar hemograma completo por fuzzy
        reg, score = BASE_TUSS.buscar_fuzzy("hemograma complet", threshold=0.70)
        assert reg is not None
        assert score > 0.70

    def test_buscar_fuzzy_abaixo_threshold(self):
        reg, score = BASE_TUSS.buscar_fuzzy("xyz nada aqui abc 9999", threshold=0.80)
        assert reg is None


# ---------------------------------------------------------------------------
# 3. Função principal — pipeline completo
# ---------------------------------------------------------------------------

class TestNormalizarExame:

    def test_match_exato_hemograma(self):
        resp = normalizar_exame("hemograma")
        assert resp["match_tipo"] == "alias"
        assert resp["codigo_tuss"] == "40301079"
        assert resp["score"] == 1.0
        assert resp["versao_base"] is not None

    def test_match_exato_nome_padrao(self):
        resp = normalizar_exame("hemograma completo com contagem de plaquetas")
        assert resp["match_tipo"] == "exato"
        assert resp["score"] == 1.0

    def test_nome_entrada_preservado(self):
        resp = normalizar_exame("HEMOGRAMA COMPLETO")
        assert resp["nome_entrada"] == "HEMOGRAMA COMPLETO"

    def test_nome_normalizado_gerado(self):
        resp = normalizar_exame("HEMOGRAMA COMPLETO")
        assert resp["nome_normalizado"] == "hemograma completo"

    def test_preparo_retornado(self):
        resp = normalizar_exame("glicemia")
        assert resp["preparo_sugerido"] is not None
        assert "jejum" in resp["preparo_sugerido"].lower()

    def test_categoria_retornada(self):
        resp = normalizar_exame("hemograma")
        assert resp["categoria"] == "hematologia"

    def test_abreviacao_us_pipeline(self):
        resp = normalizar_exame("US abdome total")
        # ultrassonografia abdome total — deve encontrar algo ou retornar nenhum
        assert "nome_normalizado" in resp
        assert "ultrassonografia" in resp["nome_normalizado"]

    def test_abreviacao_ecg_pipeline(self):
        resp = normalizar_exame("ECG")
        assert "eletrocardiograma" in resp["nome_normalizado"]
        assert resp["codigo_tuss"] is not None
        assert resp["categoria"] == "cardiologia"

    def test_abreviacao_tsh_pipeline(self):
        resp = normalizar_exame("TSH")
        assert "tireoestimulante" in resp["nome_normalizado"]
        assert resp["codigo_tuss"] is not None
        assert resp["categoria"] == "hormonal"

    def test_sem_match_retorna_nenhum(self):
        # Chars aleatórios sem nenhuma palavra clínica reconhecível
        resp = normalizar_exame("qwxzjv ptrfgh klmnop 7742")
        assert resp["match_tipo"] == "nenhum"
        assert resp["codigo_tuss"] is None
        assert resp["nome_padronizado"] is None
        assert resp["score"] == 0.0
        assert resp["fonte"] is None
        assert resp["versao_base"] is None

    def test_aviso_presente(self):
        resp = normalizar_exame("hemograma")
        assert resp["aviso"]
        assert len(resp["aviso"]) > 20

    def test_alertas_lista(self):
        resp = normalizar_exame("hemograma")
        assert isinstance(resp["alertas"], list)

    def test_contexto_laudo_aceito(self):
        resp = normalizar_exame("hemograma", contexto="laudo")
        assert resp["codigo_tuss"] == "40301079"

    def test_resposta_tem_todos_campos(self):
        resp = normalizar_exame("hemograma")
        campos = [
            "nome_entrada", "nome_normalizado", "codigo_tuss", "nome_padronizado",
            "categoria", "preparo_sugerido", "match_tipo", "score",
            "fonte", "versao_base", "alertas", "aviso",
        ]
        for campo in campos:
            assert campo in resp, f"Campo ausente: {campo}"

    def test_fonte_preenchida_em_match(self):
        resp = normalizar_exame("hemograma")
        assert resp["fonte"] == "TUSS/BASE_LOCAL"

    def test_fonte_nula_sem_match(self):
        resp = normalizar_exame("qwxzjv ptrfgh klmnop 7742")
        assert resp["fonte"] is None


# ---------------------------------------------------------------------------
# 4. Endpoint POST /ia/exames/normalizar
# ---------------------------------------------------------------------------

class TestEndpointNormalizarExame:

    def test_hemograma_200(self, client):
        resp = client.post("/ia/exames/normalizar", json={"nome_exame": "hemograma"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["codigo_tuss"] == "40301079"
        assert data["match_tipo"] in ("exato", "alias")

    def test_abreviacao_ecg_200(self, client):
        resp = client.post("/ia/exames/normalizar", json={"nome_exame": "ECG"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["codigo_tuss"] is not None
        assert data["categoria"] == "cardiologia"

    def test_contexto_laudo(self, client):
        resp = client.post(
            "/ia/exames/normalizar",
            json={"nome_exame": "hemograma", "contexto": "laudo"},
        )
        assert resp.status_code == 200

    def test_contexto_invalido_422(self, client):
        resp = client.post(
            "/ia/exames/normalizar",
            json={"nome_exame": "hemograma", "contexto": "invalido"},
        )
        assert resp.status_code == 422

    def test_nome_vazio_422(self, client):
        resp = client.post("/ia/exames/normalizar", json={"nome_exame": ""})
        assert resp.status_code == 422

    def test_sem_body_422(self, client):
        resp = client.post("/ia/exames/normalizar", json={})
        assert resp.status_code == 422

    def test_sem_autenticacao_401(self):
        from app.main import app
        from app.auth.dependencies import get_current_user
        # Temporarily remove any override so real auth runs
        override = app.dependency_overrides.pop(get_current_user, None)
        try:
            with TestClient(app) as c:
                resp = c.post("/ia/exames/normalizar", json={"nome_exame": "hemograma"})
            assert resp.status_code == 401
        finally:
            if override is not None:
                app.dependency_overrides[get_current_user] = override


# ---------------------------------------------------------------------------
# 5. GET /ia/status — inclui chave "exames"
# ---------------------------------------------------------------------------

class TestStatusIA:

    def test_status_200(self, client):
        resp = client.get("/ia/status")
        assert resp.status_code == 200

    def test_status_tem_chave_exames(self, client):
        data = client.get("/ia/status").json()
        assert "exames" in data

    def test_status_exames_base_carregada(self, client):
        data = client.get("/ia/status").json()
        assert data["exames"]["base_carregada"] is True
        assert data["exames"]["total_registros"] > 0

    def test_status_tem_chave_farmaceutica(self, client):
        data = client.get("/ia/status").json()
        assert "farmaceutica" in data
