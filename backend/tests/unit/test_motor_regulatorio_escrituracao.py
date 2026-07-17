"""
test_motor_regulatorio_escrituracao.py — TICKET-R4-ESCRITURACAO-REGULATORIA.

Prova PURA (sem banco, sem FastAPI) do helper que resolve a identidade
regulatória a CONGELAR no movimento de dispensação (CLAUDE.md §2a R4):

  - item controlado (B1 / retenção) → (id_grupo, versão do motor)
  - item não-controlado (NULL/vazio) → (None, None)  [NULL honesto]
  - item COM classe/retenção que o motor não classifica → falha ALTA
    (ValueError/RuntimeError propagado; nunca NULL silencioso para controlado)

Fronteira (§ ticket): resolvido de campo ESTRUTURADO pelo motor LOCAL — sem
fuzzy, sem chamada externa.
"""
from __future__ import annotations

import pytest

from app.domain.motor_regulatorio import (
    MOTOR_REGULATORIO_VERSAO,
    escriturar_grupo_regulatorio,
    grupo_por_id,
)


# --------------------------------------------------------------------- controlado

def test_b1_congela_grupo_azul_e_versao():
    grupo_id, versao = escriturar_grupo_regulatorio("B1", None)
    assert grupo_id == "notificacao_receita_b"
    assert versao == MOTOR_REGULATORIO_VERSAO


def test_a1_congela_grupo_amarela():
    grupo_id, versao = escriturar_grupo_regulatorio("A1", None)
    assert grupo_id == "notificacao_receita_a"
    assert versao == MOTOR_REGULATORIO_VERSAO


def test_retencao_rdc471_congela_grupo_retencao():
    grupo_id, versao = escriturar_grupo_regulatorio(None, "antimicrobiano")
    assert grupo_id == "receita_retencao"
    assert versao == MOTOR_REGULATORIO_VERSAO


# ----------------------------------------------------------------- não-controlado

@pytest.mark.parametrize("classe,retencao", [
    (None, None),
    ("", ""),
    ("   ", None),
    (None, ""),
])
def test_nao_controlado_congela_null_honesto(classe, retencao):
    """Ambos vazios → sem escrituração regulatória. NUNCA inventa grupo."""
    assert escriturar_grupo_regulatorio(classe, retencao) == (None, None)


# ------------------------------------------------------------------- falha alta

def test_classe_desconhecida_falha_alto():
    """Classe preenchida mas fora da Portaria 344/retenção → ValueError (não NULL)."""
    with pytest.raises(ValueError):
        escriturar_grupo_regulatorio("Z9", None)


def test_retencao_desconhecida_falha_alto():
    with pytest.raises(ValueError):
        escriturar_grupo_regulatorio(None, "tipo_inexistente")


# ------------------------------------------------ grupo_por_id (slug → nome, R4-FE)

def test_grupo_por_id_resolve_nome_do_slug():
    """Fonte única slug→nome: a tela pergunta ao motor, não hardcoda nomes."""
    g = grupo_por_id("notificacao_receita_b")
    assert g is not None
    assert g.nome == "Notificação de Receita B (Azul)"


def test_grupo_por_id_ida_e_volta_com_escrituracao():
    """O nome resolve exatamente do slug que a escrituração congela."""
    slug, _versao = escriturar_grupo_regulatorio("B1", None)
    assert grupo_por_id(slug).nome == "Notificação de Receita B (Azul)"


@pytest.mark.parametrize("slug", [None, "", "grupo_inexistente"])
def test_grupo_por_id_slug_desconhecido_ou_vazio_retorna_none(slug):
    """Slug desconhecido/vazio → None (UI degrada para o slug, não quebra)."""
    assert grupo_por_id(slug) is None
