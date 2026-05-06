"""
test_confianca_cuidado.py
=========================
Ticket 50 — Testes do Score Composto de Confiança do Cuidado.

Cobertura (≥ 25 testes):
  - Casos alto (prescritor forte + prestador verificado)
  - Casos médio (prescritor parcial + contexto variado)
  - Casos baixo / crítico (divergente, nao_encontrado, manual não confirmado)
  - Explicabilidade (fatores, resumo, nível coerente com pontuação)
  - Clamping (pontuação nunca sai de 0–100)
  - Retrocompatibilidade (None inputs não quebram)
  - calcular_score_confianca_prescricao
  - calcular_score_confianca_dispensacao
"""

import pytest

from app.domain.confianca_cuidado import (
    calcular_score_confianca_dispensacao,
    calcular_score_confianca_prescricao,
)

# ---------------------------------------------------------------------------
# Fixtures de cnes_validacao
# ---------------------------------------------------------------------------

def _cnes(nivel, divergencias=None, conselho="71", vinculos=2, cns_encontrado=True):
    return {
        "nivel_validacao_cnes":  nivel,
        "cns_encontrado":        cns_encontrado,
        "conselho":              conselho if cns_encontrado else None,
        "vinculos_ativos":       vinculos if cns_encontrado else 0,
        "divergencias":          divergencias or [],
    }


FORTE    = _cnes("forte")
PARCIAL  = _cnes("parcial")
DIVERGENTE  = _cnes("divergente", divergencias=["nome_divergente: ..."])
NAO_ENCONTRADO = _cnes("nao_encontrado", cns_encontrado=False, conselho=None, vinculos=0)


# ===========================================================================
# 1. calcular_score_confianca_prescricao — estrutura de retorno
# ===========================================================================

class TestEstruturaRetornoPrescricao:
    def test_retorna_dict_com_chaves_obrigatorias(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert {"nivel", "pontuacao", "fatores", "resumo"} <= r.keys()

    def test_pontuacao_e_int(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert isinstance(r["pontuacao"], int)

    def test_fatores_e_lista(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert isinstance(r["fatores"], list)

    def test_resumo_e_string_nao_vazia(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert isinstance(r["resumo"], str) and len(r["resumo"]) > 10


# ===========================================================================
# 2. Níveis — prescrição (sem contexto de prestador)
# ===========================================================================

class TestNiveisPrescricao:
    def test_forte_nivel_alto(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert r["nivel"] == "alto"

    def test_forte_pontuacao_ge_70(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert r["pontuacao"] >= 70

    def test_parcial_nivel_medio(self):
        r = calcular_score_confianca_prescricao(PARCIAL)
        assert r["nivel"] == "medio"

    def test_parcial_pontuacao_40_a_69(self):
        r = calcular_score_confianca_prescricao(PARCIAL)
        assert 40 <= r["pontuacao"] <= 69

    def test_divergente_nivel_critico_ou_baixo(self):
        r = calcular_score_confianca_prescricao(DIVERGENTE)
        assert r["nivel"] in ("critico", "baixo")

    def test_nao_encontrado_nivel_baixo_ou_critico(self):
        r = calcular_score_confianca_prescricao(NAO_ENCONTRADO)
        assert r["nivel"] in ("baixo", "critico")

    def test_sem_cnes_validacao_nivel_medio_ou_baixo(self):
        r = calcular_score_confianca_prescricao(None)
        # base=30 → baixo
        assert r["nivel"] == "baixo"
        assert r["pontuacao"] == 30


# ===========================================================================
# 3. Fatores explicáveis — prescrição
# ===========================================================================

class TestFatoresPrescricao:
    def test_forte_tem_fator_forte(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert any("forte" in f.lower() for f in r["fatores"])

    def test_parcial_tem_fator_parcial(self):
        r = calcular_score_confianca_prescricao(PARCIAL)
        assert any("parcial" in f.lower() for f in r["fatores"])

    def test_divergente_tem_fator_divergencia(self):
        r = calcular_score_confianca_prescricao(DIVERGENTE)
        assert any("divergên" in f.lower() or "divergente" in f.lower() for f in r["fatores"])

    def test_nao_encontrado_tem_fator_nao_encontrado(self):
        r = calcular_score_confianca_prescricao(NAO_ENCONTRADO)
        assert any("não encontrado" in f.lower() for f in r["fatores"])

    def test_forte_tem_fator_conselho(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert any("conselho" in f.lower() for f in r["fatores"])

    def test_forte_tem_fator_vinculos(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert any("vínculo" in f.lower() for f in r["fatores"])

    def test_sem_dados_sem_fatores(self):
        r = calcular_score_confianca_prescricao(None)
        assert r["fatores"] == []


# ===========================================================================
# 4. calcular_score_confianca_dispensacao — casos alto
# ===========================================================================

class TestDispensacaoAlto:
    def test_forte_cnes_verificado_nivel_alto(self):
        r = calcular_score_confianca_dispensacao(FORTE, "cnes_verificado")
        assert r["nivel"] == "alto"

    def test_forte_cnes_verificado_pontuacao_ge_70(self):
        r = calcular_score_confianca_dispensacao(FORTE, "cnes_verificado")
        assert r["pontuacao"] >= 70

    def test_parcial_cnes_verificado_nivel_alto(self):
        r = calcular_score_confianca_dispensacao(PARCIAL, "cnes_verificado")
        assert r["nivel"] == "alto"

    def test_parcial_cnes_verificado_tem_fator_prestador(self):
        r = calcular_score_confianca_dispensacao(PARCIAL, "cnes_verificado")
        assert any("cnes" in f.lower() for f in r["fatores"])


# ===========================================================================
# 5. calcular_score_confianca_dispensacao — casos médio
# ===========================================================================

class TestDispensacaoMedio:
    def test_forte_manual_confirmado_nivel_medio_ou_alto(self):
        r = calcular_score_confianca_dispensacao(FORTE, "manual", contexto_confirmado_manual=True)
        assert r["nivel"] in ("medio", "alto")

    def test_parcial_manual_confirmado_nivel_medio(self):
        r = calcular_score_confianca_dispensacao(PARCIAL, "manual", contexto_confirmado_manual=True)
        assert r["nivel"] == "medio"

    def test_parcial_manual_confirmado_tem_fator_manual(self):
        r = calcular_score_confianca_dispensacao(PARCIAL, "manual", contexto_confirmado_manual=True)
        assert any("manual" in f.lower() for f in r["fatores"])


# ===========================================================================
# 6. calcular_score_confianca_dispensacao — casos baixo / crítico
# ===========================================================================

class TestDispensacaoBaixoCritico:
    def test_divergente_manual_nao_conf_critico(self):
        r = calcular_score_confianca_dispensacao(DIVERGENTE, "manual", contexto_confirmado_manual=False)
        assert r["nivel"] in ("critico", "baixo")

    def test_nao_encontrado_manual_nao_conf_baixo_ou_critico(self):
        r = calcular_score_confianca_dispensacao(NAO_ENCONTRADO, "manual", contexto_confirmado_manual=None)
        assert r["nivel"] in ("baixo", "critico")

    def test_parcial_manual_nao_conf_nivel_baixo(self):
        # parcial sem conselho/vínculos: base 30 + parcial 20 - manual_nao_conf 20 = 30 → baixo
        parcial_simples = _cnes("parcial", conselho=None, vinculos=0)
        r = calcular_score_confianca_dispensacao(parcial_simples, "manual", contexto_confirmado_manual=False)
        assert r["nivel"] == "baixo"

    def test_divergente_sem_contexto_nivel_critico(self):
        r = calcular_score_confianca_dispensacao(DIVERGENTE, None)
        assert r["nivel"] in ("critico", "baixo")


# ===========================================================================
# 7. Clamping — pontuação nunca sai de 0–100
# ===========================================================================

class TestClamping:
    def test_pontuacao_nunca_acima_100(self):
        r = calcular_score_confianca_dispensacao(FORTE, "cnes_verificado")
        assert r["pontuacao"] <= 100

    def test_pontuacao_nunca_abaixo_0(self):
        cnes_muito_ruim = _cnes(
            "divergente",
            divergencias=["d1", "d2", "d3", "d4", "d5"],
            cns_encontrado=True, conselho=None, vinculos=0,
        )
        r = calcular_score_confianca_dispensacao(cnes_muito_ruim, "manual", contexto_confirmado_manual=False)
        assert r["pontuacao"] >= 0


# ===========================================================================
# 8. Retrocompatibilidade — None inputs não quebram
# ===========================================================================

class TestRetrocompatibilidade:
    def test_cnes_none_prescricao_nao_quebra(self):
        r = calcular_score_confianca_prescricao(None)
        assert r["nivel"] in ("alto", "medio", "baixo", "critico")

    def test_cnes_none_dispensacao_nao_quebra(self):
        r = calcular_score_confianca_dispensacao(None, None, None)
        assert r["nivel"] in ("alto", "medio", "baixo", "critico")

    def test_origem_vazia_nao_quebra(self):
        r = calcular_score_confianca_dispensacao(FORTE, "")
        assert r["nivel"] in ("alto", "medio", "baixo", "critico")

    def test_confirmado_none_com_manual_nao_quebra(self):
        r = calcular_score_confianca_dispensacao(FORTE, "manual", None)
        assert r["nivel"] in ("alto", "medio", "baixo", "critico")


# ===========================================================================
# 9. Resumo coerente
# ===========================================================================

class TestResumo:
    def test_resumo_forte_menciona_alto_ou_cnes(self):
        r = calcular_score_confianca_prescricao(FORTE)
        assert "alta" in r["resumo"].lower() or "cnes" in r["resumo"].lower()

    def test_resumo_divergente_menciona_divergencia(self):
        r = calcular_score_confianca_prescricao(DIVERGENTE)
        assert "divergên" in r["resumo"].lower()

    def test_resumo_parcial_menciona_parcial(self):
        r = calcular_score_confianca_prescricao(PARCIAL)
        assert "parcial" in r["resumo"].lower()

    def test_resumo_sem_dados_menciona_insuficiente(self):
        r = calcular_score_confianca_prescricao(None)
        assert "insuficiente" in r["resumo"].lower()
