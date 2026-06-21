"""Unit — busca multi-resultado de medicamentos (autocomplete) em lookup_def.

Suporta o endpoint /ia/medicamentos/buscar e o autocomplete do prescritor.
"""
from __future__ import annotations

from app.ai.lookup_def import buscar_medicamentos


def test_retorna_multiplos_candidatos():
    rs = buscar_medicamentos("amoxicilina", 5)
    assert 1 < len(rs) <= 5
    assert all(r["principio_ativo"] for r in rs)
    assert all("amoxicilina" in (r["principio_ativo"] or "") for r in rs)


def test_campos_para_autocomplete_presentes():
    rs = buscar_medicamentos("losartana", 3)
    assert rs
    r = rs[0]
    for campo in ("principio_ativo", "forma_farmaceutica", "concentracao_texto",
                  "via_administracao", "match_tipo", "score"):
        assert campo in r


def test_dedup_por_registro():
    rs = buscar_medicamentos("dipirona", 8)
    chaves = [(r["principio_ativo"], r["concentracao_texto"], r["forma_farmaceutica"]) for r in rs]
    assert len(chaves) == len(set(chaves))   # sem duplicatas


def test_termo_curto_ou_junk_retorna_vazio():
    assert buscar_medicamentos("a", 5) == []
    assert buscar_medicamentos("", 5) == []


def test_respeita_max_resultados():
    assert len(buscar_medicamentos("a"  + "moxicilina", 2)) <= 2


def test_substring_prioriza_farmaco_certo_e_concentracoes():
    """Busca por substring traz o fármaco certo em todas as concentrações,
    sem poluir com aproximações erradas (capecitabina/escetamina p/ 'escita')."""
    rs = buscar_medicamentos("escita", 8)
    assert rs
    pas = {(r["principio_ativo"] or "") for r in rs}
    assert pas == {"oxalato de escitalopram"}          # nada de fármaco errado
    concs = {r["concentracao_texto"] for r in rs}
    assert "15 mg" in concs and "20 mg" in concs       # concentrações antes ausentes


def test_fuzzy_ainda_tolera_erro_de_digitacao():
    """Erro de digitação ainda casa via fuzzy (fallback após o substring)."""
    rs = buscar_medicamentos("amoxiciclina", 3)
    assert any("amoxicilina" in (r["principio_ativo"] or "") for r in rs)


def test_unidade_de_dispensacao_fidedigna():
    """A unidade vem da forma (não fica vazia/errada para não-sólidos)."""
    from app.ai.lookup_def import _unidade_de_forma
    assert _unidade_de_forma("comprimido revestido")          == "comprimido"
    assert _unidade_de_forma("cápsula dura")                  == "cápsula"
    assert _unidade_de_forma("solução injetável")             == "ampola"
    assert _unidade_de_forma("pó liofilizado para solução injetável") == "frasco-ampola"
    assert _unidade_de_forma("xarope")                        == "frasco"
    assert _unidade_de_forma("creme dermatológico")           == "bisnaga"
    assert _unidade_de_forma("supositório")                   == "supositório"
    # toda busca retorna uma unidade não-vazia
    for r in buscar_medicamentos("dipirona", 6):
        assert r["unidade_dispensavel"]
