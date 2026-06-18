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
