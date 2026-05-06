"""
test_nome_validator.py
======================
Ticket 64 — NomeValidator: validação fuzzy de nomes de prescritores.

Cobre:
  1.  Nome idêntico → válido
  2.  Acento diferente → válido (normalização NFKD)
  3.  Luiz vs Luis → válido (edit_distance == 1)
  4.  Thiago vs Tiago → válido (SequenceMatcher ~0.91)
  5.  Preposição diferente → válido (preposições ignoradas)
  6.  Sufixo divergente → inválido (Jr vs Sr)
  7.  Sobrenome completamente diferente → inválido
  8.  Typo leve no sobrenome → válido (SequenceMatcher >= 0.80)
  9.  Nome comum → válido como par (ambiguidade é responsabilidade do chamador)
 10.  Nome próprio muito diferente → inválido
"""

import pytest

from app.domain.nome_validator import (
    NomeValidator,
    _edit_distance,
    _extrair,
    _normalizar,
    _sim,
    _sim_nome_proprio,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def validator() -> NomeValidator:
    return NomeValidator()


# ---------------------------------------------------------------------------
# Helpers internos — normalização e extração
# ---------------------------------------------------------------------------


def test_normalizar_remove_acentos():
    assert _normalizar("João") == "joao"


def test_normalizar_lowercase_e_strip():
    assert _normalizar("  ANA PAULA  ") == "ana paula"


def test_normalizar_colapsa_espacos():
    assert _normalizar("MARIA   DE   SOUZA") == "maria de souza"


def test_normalizar_remove_pontuacao_leve():
    assert _normalizar("Dr. Carlos.") == "dr carlos"


def test_extrair_nome_simples():
    resultado = _extrair("João da Silva Filho")
    assert resultado["nome_proprio"] == "joao"
    assert resultado["sobrenome"] == "silva"
    assert "da" in resultado["preposicoes"]
    assert "filho" in resultado["sufixos"]


def test_extrair_sem_preposicao():
    resultado = _extrair("Ana Santos")
    assert resultado["nome_proprio"] == "ana"
    assert resultado["sobrenome"] == "santos"
    assert resultado["preposicoes"] == []
    assert resultado["sufixos"] == []


def test_extrair_string_vazia():
    resultado = _extrair("")
    assert resultado["nome_proprio"] == ""
    assert resultado["sobrenome"] == ""


def test_edit_distance_identico():
    assert _edit_distance("luiz", "luiz") == 0


def test_edit_distance_substituicao_1():
    assert _edit_distance("luiz", "luis") == 1


def test_edit_distance_string_vazia():
    assert _edit_distance("", "abc") == 3


def test_sim_nome_proprio_luiz_luis():
    """Luiz vs Luis: SequenceMatcher=0.75, edit_distance=1 → boost para 0.87."""
    score = _sim_nome_proprio("luiz", "luis")
    assert score >= 0.85, f"Esperado >= 0.85, obtido {score:.3f}"


def test_sim_nome_proprio_identico():
    assert _sim_nome_proprio("joao", "joao") == pytest.approx(1.0)


def test_sim_nome_proprio_muito_diferente():
    score = _sim_nome_proprio("paulo", "roberto")
    assert score < 0.85


# ---------------------------------------------------------------------------
# Casos principais — validar_correspondencia
# ---------------------------------------------------------------------------


# Caso 1 — Nome idêntico
def test_caso1_nome_identico(validator):
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="João da Silva",
        nome_cnes="João da Silva",
        nome_conselho="João da Silva",
    )
    assert valido is True
    assert motivo == "ok"
    assert confianca == pytest.approx(1.0)


# Caso 2 — Acento diferente
def test_caso2_acento_diferente(validator):
    """Joao (sem acento) vs João (com acento) → normalização resolve."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Joao da Silva",
        nome_cnes="João da Silva",
        nome_conselho="João da Silva",
    )
    assert valido is True, f"Esperado válido, motivo: {motivo}"
    assert confianca > 0.90


# Caso 3 — Luiz vs Luis
def test_caso3_luiz_vs_luis(validator):
    """
    Variante ortográfica clássica em dados de saúde brasileiros.
    SequenceMatcher puro daria 0.75 (abaixo de 0.85), mas edit_distance=1
    ativa o boost para 0.87, garantindo passagem no limiar.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Luiz Carlos Pereira",
        nome_cnes="Luis Carlos Pereira",
        nome_conselho="Luis Carlos Pereira",
    )
    assert valido is True, f"Esperado válido, motivo: {motivo}"
    assert confianca > 0.0


# Caso 4 — Thiago vs Tiago
def test_caso4_thiago_vs_tiago(validator):
    """SequenceMatcher('thiago', 'tiago') ≈ 0.909 — acima do limiar 0.85."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Thiago Menezes Santos",
        nome_cnes="Tiago Menezes Santos",
        nome_conselho="Tiago Menezes Santos",
    )
    assert valido is True, f"Esperado válido, motivo: {motivo}"


# Caso 5 — Preposição diferente
def test_caso5_preposicao_diferente(validator):
    """
    'Maria de Souza' vs 'Maria da Souza' — preposições são ignoradas
    na comparação de nome_proprio e sobrenome.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Maria de Souza",
        nome_cnes="Maria da Souza",
        nome_conselho="Maria da Souza",
    )
    assert valido is True, f"Esperado válido, motivo: {motivo}"


# Caso 6 — Sufixo divergente
def test_caso6_sufixo_divergente(validator):
    """
    'Carlos Silva Jr' vs 'Carlos Silva Sr' — sufixos distintos indicam
    pessoas diferentes; deve ser rejeitado.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Carlos Silva Jr",
        nome_cnes="Carlos Silva Sr",
        nome_conselho="Carlos Silva Sr",
    )
    assert valido is False
    assert "sufixo" in motivo


# Caso 7 — Sobrenome completamente diferente
def test_caso7_sobrenome_diferente(validator):
    """
    Mesmo nome próprio, sobrenome totalmente diferente → inválido.
    'Ana Santos' vs 'Ana Rodrigues': sim('santos','rodrigues') ≈ 0.47.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Ana Santos",
        nome_cnes="Ana Rodrigues",
        nome_conselho="Ana Rodrigues",
    )
    assert valido is False
    assert "sobrenome" in motivo


# Caso 8 — Typo leve no sobrenome
def test_caso8_typo_leve_sobrenome(validator):
    """
    'Ferreira' vs 'Ferreyra' — 1 caractere diferente (i→y).
    SequenceMatcher ≈ 0.875, acima do limiar de sobrenome 0.80.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Cristiane Ferreira",
        nome_cnes="Cristiane Ferreyra",
        nome_conselho="Cristiane Ferreyra",
    )
    assert valido is True, f"Esperado válido (typo leve), motivo: {motivo}"


# Caso 9 — Nome comum (ambiguidade é responsabilidade do chamador)
def test_caso9_nome_comum_match_valido(validator):
    """
    Nomes comuns como 'José Silva' devem passar a validação de par.
    A detecção de ambiguidade (múltiplos candidatos) é responsabilidade
    do chamador, não do NomeValidator.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="José da Silva",
        nome_cnes="José da Silva",
        nome_conselho="José da Silva",
    )
    assert valido is True
    assert confianca > 0.90


# Caso 10 — Nome próprio muito diferente
def test_caso10_nome_proprio_muito_diferente(validator):
    """
    'Paulo Mendes' vs 'Roberto Mendes' — nomes próprios sem semelhança.
    SequenceMatcher('paulo','roberto') ≈ 0.18, edit_distance=5 → inválido.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Paulo Mendes",
        nome_cnes="Roberto Mendes",
        nome_conselho="Roberto Mendes",
    )
    assert valido is False
    assert "nome_proprio" in motivo


# ---------------------------------------------------------------------------
# Casos adicionais — robustez e edge cases
# ---------------------------------------------------------------------------


def test_nome_conselho_vazio_usa_cnes(validator):
    """Quando nome_conselho não está disponível, validação usa apenas CNES."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Ana Paula Ramos",
        nome_cnes="Ana Paula Ramos",
        nome_conselho="",
    )
    assert valido is True
    assert confianca == pytest.approx(1.0)


def test_nome_proprio_vazio_invalido(validator):
    """String vazia no certificado → inválido."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="",
        nome_cnes="João Silva",
        nome_conselho="João Silva",
    )
    assert valido is False


def test_nomes_com_multiplos_sobrenomes(validator):
    """Nome completo com múltiplos sobrenomes — extrai corretamente."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Maria Clara Oliveira Santos",
        nome_cnes="Maria Clara Oliveira Santos",
        nome_conselho="Maria Clara Oliveira Santos",
    )
    assert valido is True
    assert confianca == pytest.approx(1.0)


def test_acento_mais_caixa_alta(validator):
    """Certificado em maiúsculas vs CNES com acentos — normalização resolve."""
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="MARCOS AURELIO FIGUEIREDO",
        nome_cnes="Márcus Aurélio Figueirêdo",
        nome_conselho="Marcos Aurelio Figueiredo",
    )
    # Marcos vs Marcus: SequenceMatcher("marcos","marcus")=0.833, edit=1 → boost 0.87 ✓
    assert valido is True, f"Esperado válido, motivo: {motivo}"


def test_confianca_retornada_quando_valido(validator):
    """Confiança deve ser float em [0.0, 1.0] quando válido."""
    valido, _motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Luiz Gonzaga Pereira",
        nome_cnes="Luis Gonzaga Pereira",
        nome_conselho="Luis Gonzaga Pereira",
    )
    assert valido is True
    assert 0.0 <= confianca <= 1.0


def test_confianca_zero_quando_invalido(validator):
    """Confiança deve ser 0.0 quando inválido."""
    valido, _motivo, confianca = validator.validar_correspondencia(
        nome_certificado="João Alves",
        nome_cnes="Pedro Alves",
        nome_conselho="Pedro Alves",
    )
    assert valido is False
    assert confianca == pytest.approx(0.0)


def test_sufixo_apenas_em_certificado_sem_cnes_aceita(validator):
    """
    Sufixo presente no certificado mas ausente no CNES → não rejeita.
    REGRA 4: só compara sufixos se AMBOS têm.
    """
    valido, motivo, confianca = validator.validar_correspondencia(
        nome_certificado="Carlos Eduardo Silva Junior",
        nome_cnes="Carlos Eduardo Silva",
        nome_conselho="Carlos Eduardo Silva",
    )
    assert valido is True, f"Esperado válido (sufixo só no cert), motivo: {motivo}"
