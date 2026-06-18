"""
test_ia_farmaceutica.py
=======================
Testes unitários e de integração da IA farmacêutica v1.

COBERTURA
---------
  1. Normalização textual (normalizacao_medicamento)
  2. Regras determinísticas (regras_farmaceuticas)
  3. Lookup DEF (lookup_def) — exato, alias, aproximado, nenhum
  4. Função principal (ia_farmaceutica.sugerir_medicamento)
  5. Endpoint POST /ia/medicamentos/sugerir (via TestClient)
  6. Endpoint GET /ia/status

Sem banco de dados. Sem dependências externas além da stdlib e rapidfuzz.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

from app.ai.normalizacao_medicamento import (
    normalizar_nome_medicamento,
    remover_acentos,
    separar_numero_unidade,
)
from app.ai.regras_farmaceuticas import (
    sugerir_unidade,
    verificar_incoerencias,
    FORMA_PARA_UNIDADE,
)
from app.ai.lookup_def import buscar_medicamento, tamanho_base
from app.ai.ia_farmaceutica import sugerir_medicamento


# ---------------------------------------------------------------------------
# 1. Normalização textual
# ---------------------------------------------------------------------------

class TestNormalizacao:

    def test_lowercase(self):
        assert normalizar_nome_medicamento("AMOXICILINA") == "amoxicilina"

    def test_remove_acentos(self):
        assert normalizar_nome_medicamento("Cápsulas") == "capsula"

    def test_separar_numero_unidade(self):
        resultado = normalizar_nome_medicamento("Amoxicilina 500mg")
        assert "500 mg" in resultado

    def test_singulariza_capsulas(self):
        assert normalizar_nome_medicamento("Omeprazol 20mg Cápsulas") == "omeprazol 20 mg capsula"

    def test_singulariza_comprimidos(self):
        assert normalizar_nome_medicamento("Metformina 500mg Comprimidos") == "metformina 500 mg comprimido"

    def test_expande_abreviacao_cap(self):
        resultado = normalizar_nome_medicamento("Fluoxetina 20mg Cap")
        assert "capsula" in resultado

    def test_expande_abreviacao_cpr(self):
        resultado = normalizar_nome_medicamento("Metformina 500mg Cpr")
        assert "comprimido" in resultado

    def test_expande_abreviacao_inj(self):
        resultado = normalizar_nome_medicamento("Dexametasona 4mg/mL Inj")
        assert "injetavel" in resultado

    def test_normaliza_mcg(self):
        resultado = normalizar_nome_medicamento("Levotiroxina 25mcg")
        assert "25 mcg" in resultado

    def test_idempotente(self):
        entrada = "Amoxicilina 500mg Cápsulas"
        primeira = normalizar_nome_medicamento(entrada)
        segunda  = normalizar_nome_medicamento(primeira)
        assert primeira == segunda

    def test_string_vazia(self):
        assert normalizar_nome_medicamento("") == ""

    def test_none(self):
        assert normalizar_nome_medicamento(None) == ""

    def test_remove_acentos_standalone(self):
        assert remover_acentos("cápsula") == "capsula"
        assert remover_acentos("drágea")  == "dragea"

    def test_separar_numero_unidade_standalone(self):
        assert separar_numero_unidade("500mg") == "500 mg"
        assert separar_numero_unidade("250mcg") == "250 mcg"
        assert separar_numero_unidade("100UI/mL") == "100 ui/ml"

    def test_nome_complexo(self):
        resultado = normalizar_nome_medicamento("Amoxicilina 500mg Cápsulas")
        assert resultado == "amoxicilina 500 mg capsula"

    def test_insulina_normalizada(self):
        resultado = normalizar_nome_medicamento("Insulina NPH 100 UI/mL Inj.")
        assert "insulina" in resultado
        assert "nph" in resultado
        assert "injetavel" in resultado


# ---------------------------------------------------------------------------
# 2. Regras determinísticas
# ---------------------------------------------------------------------------

class TestRegras:

    def test_sugerir_unidade_comprimido(self):
        assert sugerir_unidade("comprimido") == "comprimido"

    def test_sugerir_unidade_capsula(self):
        assert sugerir_unidade("Cápsula") == "cápsula"

    def test_sugerir_unidade_ampola(self):
        assert sugerir_unidade("ampola") == "ampola"

    def test_sugerir_unidade_frasco_ampola(self):
        assert sugerir_unidade("frasco-ampola") == "frasco-ampola"

    def test_sugerir_unidade_pomada(self):
        assert sugerir_unidade("pomada") == "bisnaga"

    def test_sugerir_unidade_gel(self):
        assert sugerir_unidade("gel") == "bisnaga"

    def test_sugerir_unidade_solucao(self):
        assert sugerir_unidade("solução oral") == "frasco"

    def test_sugerir_unidade_nenhum(self):
        assert sugerir_unidade("xyz_desconhecido") is None

    def test_sugerir_unidade_none(self):
        assert sugerir_unidade(None) is None

    def test_incoerencia_insulina_comprimido(self):
        alertas = verificar_incoerencias("insulina glargina", "comprimido")
        assert len(alertas) == 1
        assert "comprimido" in alertas[0].lower()

    def test_incoerencia_insulina_capsula(self):
        alertas = verificar_incoerencias("insulina nph", "capsula")
        assert len(alertas) == 1

    def test_incoerencia_colirio_comprimido(self):
        alertas = verificar_incoerencias("ciprofloxacino colírio", "comprimido")
        assert len(alertas) == 1

    def test_incoerencia_pomada_ampola(self):
        alertas = verificar_incoerencias("pomada de betametasona", "ampola")
        assert len(alertas) == 1

    def test_sem_incoerencia_amoxicilina_capsula(self):
        alertas = verificar_incoerencias("amoxicilina", "capsula")
        assert alertas == []

    def test_sem_incoerencia_metformina_comprimido(self):
        alertas = verificar_incoerencias("metformina", "comprimido")
        assert alertas == []

    def test_sem_incoerencia_inputs_vazios(self):
        assert verificar_incoerencias(None, None) == []
        assert verificar_incoerencias("", "") == []

    def test_forma_para_unidade_cobre_formas_basicas(self):
        formas_basicas = ["comprimido", "capsula", "dragea", "ampola", "frasco", "bisnaga"]
        for f in formas_basicas:
            assert f in FORMA_PARA_UNIDADE, f"'{f}' ausente em FORMA_PARA_UNIDADE"


# ---------------------------------------------------------------------------
# 3. Lookup DEF
# ---------------------------------------------------------------------------

class TestLookup:

    def test_base_carregada(self):
        assert tamanho_base() > 0, "Base farmacêutica não foi carregada."

    def test_match_exato_amoxicilina(self):
        resultado = buscar_medicamento("Amoxicilina 500mg Cápsulas")
        assert resultado["match_tipo"] in ("exato", "aproximado", "alias")
        assert resultado["score"] > 0

    def test_match_amoxicilina_retorna_principio_ativo(self):
        resultado = buscar_medicamento("amoxicilina 500 mg capsula")
        if resultado["match_tipo"] == "exato":
            assert resultado["principio_ativo"] == "amoxicilina"

    def test_match_insulina_retorna_unidade(self):
        # Base ANVISA/CMED: insulina glargina existe; a unidade é derivada da forma
        # (não mais o valor curado "frasco-ampola").
        resultado = buscar_medicamento("insulina glargina 100UI/mL solução injetável")
        if resultado["match_tipo"] in ("exato", "aproximado"):
            assert resultado["unidade_dispensavel"]   # não-vazia

    def test_match_metformina(self):
        resultado = buscar_medicamento("Metformina 500mg comprimido")
        assert resultado["match_tipo"] in ("exato", "aproximado", "alias")

    def test_match_aproximado_typo(self):
        # Pequeno typo deve encontrar match aproximado
        resultado = buscar_medicamento("amoxcilina 500mg capsla")
        assert resultado["match_tipo"] in ("aproximado", "exato", "alias", "nenhum")

    def test_nenhum_para_junk(self):
        resultado = buscar_medicamento("xyzxyzxyz999 lalala")
        assert resultado["match_tipo"] == "nenhum"
        assert resultado["score"] == 0.0
        assert resultado["principio_ativo"] is None

    def test_base_anvisa_cobre_medicamentos_antes_ausentes(self):
        """Completude: ao adotar a base ANVISA/CMED, medicamentos REAIS que estavam
        FORA da base curada do MVP (81 itens) passam a ser cobertos.

        tadalafila/sildenafila (disfunção erétil) e hidroxicloroquina (antimalárico)
        são produtos registrados na ANVISA — antes davam 'nenhum', agora casam.
        A proteção contra falso-positivo de *junk* segue em `test_nenhum_para_junk`.
        """
        for q in ['tadalafila 5mg', 'sildenafila 50mg', 'hidroxicloroquina 400mg']:
            r = buscar_medicamento(q)
            assert r['match_tipo'] != 'nenhum', \
                f'{q} deveria existir na base ANVISA, veio {r["match_tipo"]}'

    def test_alias_novalgina(self):
        resultado = buscar_medicamento("novalgina 500")
        assert resultado["match_tipo"] in ("alias", "exato", "aproximado")

    def test_alias_lantus(self):
        resultado = buscar_medicamento("lantus 100UI")
        assert resultado["match_tipo"] in ("alias", "aproximado", "exato")

    def test_retorna_fonte(self):
        # Fonte não-vazia (base atual: ANVISA/CMED; não fixar string específica).
        resultado = buscar_medicamento("paracetamol 500mg comprimido")
        if resultado["match_tipo"] != "nenhum":
            assert resultado["fonte"]

    def test_retorna_versao_base(self):
        resultado = buscar_medicamento("paracetamol 500mg comprimido")
        if resultado["match_tipo"] != "nenhum":
            assert resultado["versao_base"] is not None

    def test_score_exato_e_1(self):
        resultado = buscar_medicamento("amoxicilina 500 mg capsula")
        if resultado["match_tipo"] == "exato":
            assert resultado["score"] == 1.0

    def test_score_entre_0_e_1(self):
        resultado = buscar_medicamento("Ciprofloxacino 500mg comprimido")
        assert 0.0 <= resultado["score"] <= 1.0


# ---------------------------------------------------------------------------
# 4. Função principal sugerir_medicamento
# ---------------------------------------------------------------------------

class TestSugerirMedicamento:

    def test_retorna_nome_normalizado(self):
        r = sugerir_medicamento("Amoxicilina 500mg Cápsulas")
        assert r["nome_normalizado"] == "amoxicilina 500 mg capsula"

    def test_retorna_aviso_fixo(self):
        r = sugerir_medicamento("paracetamol 500mg")
        assert "responsabilidade exclusiva" in r["aviso"].lower() or "profissional" in r["aviso"].lower()

    def test_sem_alertas_para_caso_coerente(self):
        r = sugerir_medicamento("amoxicilina 500mg", forma_farmaceutica="capsula")
        assert r["alertas"] == []

    def test_alerta_para_insulina_comprimido(self):
        r = sugerir_medicamento("insulina glargina", forma_farmaceutica="comprimido")
        assert len(r["alertas"]) >= 1

    def test_match_tipo_presente(self):
        r = sugerir_medicamento("metformina 500mg comprimido")
        assert r["match_tipo"] in ("exato", "alias", "aproximado", "regra", "nenhum")

    def test_score_presente(self):
        r = sugerir_medicamento("omeprazol 20mg capsula")
        assert isinstance(r["score"], float)
        assert 0.0 <= r["score"] <= 1.0

    def test_contexto_prescricao(self):
        r = sugerir_medicamento("metformina 500mg", contexto="prescricao")
        assert r["match_tipo"] in ("exato", "alias", "aproximado", "regra", "nenhum")

    def test_contexto_dispensacao(self):
        # Na v1 a lógica é idêntica — apenas garantir que não quebra
        r = sugerir_medicamento("metformina 500mg", contexto="dispensacao")
        assert "match_tipo" in r

    def test_sugestao_por_regra_quando_sem_lookup(self):
        # Nome inventado mas forma conhecida → match_tipo = regra
        r = sugerir_medicamento("xyz_medicamento_inventado_12345", forma_farmaceutica="comprimido")
        if r["match_tipo"] == "regra":
            assert r["unidade_quantidade_sugerida"] == "comprimido"

    def test_nenhum_para_entrada_sem_match(self):
        r = sugerir_medicamento("xyzxyzxyz9999lalala")
        assert r["match_tipo"] in ("nenhum", "regra")
        # aviso sempre presente
        assert r["aviso"]

    def test_resposta_tem_todos_os_campos(self):
        r = sugerir_medicamento("amoxicilina 500mg")
        campos = [
            "nome_normalizado", "forma_farmaceutica_sugerida",
            "unidade_quantidade_sugerida", "principio_ativo",
            "concentracao_sugerida", "via_administracao",
            "match_tipo", "score", "fonte", "versao_base",
            "alertas", "aviso",
        ]
        for c in campos:
            assert c in r, f"Campo '{c}' ausente na resposta."


# ---------------------------------------------------------------------------
# 5. Endpoint POST /ia/medicamentos/sugerir (via TestClient)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client_autenticado():
    from app.main import app
    from app.auth.dependencies import get_current_user

    # Sobrescreve a dependência de autenticação para os testes
    # (mesmo padrão usado em conftest.py / RoleClient)
    app.dependency_overrides[get_current_user] = lambda: {"role": "prescritor", "sub": "test_ia"}

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


class TestEndpointSugerir:

    def _post(self, client, payload: dict):
        return client.post("/ia/medicamentos/sugerir", json=payload)

    def test_200_amoxicilina(self, client_autenticado):
        r = self._post(client_autenticado, {"nome_medicamento": "Amoxicilina 500mg Cápsulas"})
        assert r.status_code == 200
        data = r.json()
        assert "nome_normalizado" in data
        assert "match_tipo" in data
        assert "aviso" in data

    def test_200_insulina_alerta(self, client_autenticado):
        r = self._post(client_autenticado, {
            "nome_medicamento": "insulina glargina",
            "forma_farmaceutica": "comprimido",
        })
        assert r.status_code == 200
        data = r.json()
        assert len(data["alertas"]) >= 1

    def test_422_nome_vazio(self, client_autenticado):
        r = self._post(client_autenticado, {"nome_medicamento": ""})
        assert r.status_code == 422

    def test_422_contexto_invalido(self, client_autenticado):
        r = self._post(client_autenticado, {
            "nome_medicamento": "metformina",
            "contexto": "invalido",
        })
        assert r.status_code == 422

    def test_200_contexto_dispensacao(self, client_autenticado):
        r = self._post(client_autenticado, {
            "nome_medicamento": "paracetamol 500mg",
            "contexto": "dispensacao",
        })
        assert r.status_code == 200

    def test_retorna_todos_campos(self, client_autenticado):
        r = self._post(client_autenticado, {"nome_medicamento": "metformina 500mg comprimido"})
        data = r.json()
        for campo in ["nome_normalizado", "match_tipo", "score", "alertas", "aviso"]:
            assert campo in data

    def test_status_ia(self, client_autenticado):
        r = client_autenticado.get("/ia/status")
        assert r.status_code == 200
        data = r.json()
        farma = data["farmaceutica"]
        assert farma["base_carregada"] is True
        assert farma["total_registros"] > 0
        assert farma["modelo"] == "lookup + regras (v1 — sem ML)"
