"""Unit — carga da base CID-10 completa (DATASUS via CSV) + curadoria sobreposta.

A base passou de subset curado (~183) para CID-10 completo (~14k) carregado de
`data/cid10.csv`, mantendo os aliases curados (qualidade de busca). O empacotamento
usa o override `PICSAUDE_CID_CSV` (mesma estratégia do DEF).
"""
from __future__ import annotations

import os

from app.ai import base_cid


def test_resolver_cid_csv_override(monkeypatch):
    monkeypatch.setenv("PICSAUDE_CID_CSV", "/empacotado/cid10.csv")
    assert base_cid._resolver_cid_csv() == "/empacotado/cid10.csv"


def test_resolver_cid_csv_fallback_dev(monkeypatch):
    monkeypatch.delenv("PICSAUDE_CID_CSV", raising=False)
    assert base_cid._resolver_cid_csv().endswith(os.path.join("data", "cid10.csv"))


def test_base_completa_carregada():
    # No layout de dev a CSV existe → base completa (muito além do subset curado).
    assert base_cid.BASE_CID.total > 10000


def test_curadoria_de_aliases_preservada():
    # Alias clínico curado continua resolvendo após a mescla com o DATASUS.
    from app.ai.base_cid import _norm
    resultados = base_cid.BASE_CID.buscar(_norm("koch"), max_resultados=3)
    assert any(r[2] == "alias" for r in resultados), "alias curado 'koch' perdido"


def test_codigo_oficial_datasus_presente():
    r = base_cid.BASE_CID.buscar_por_codigo("A00.0")
    assert r is not None and "lera" in r["descricao"].lower()  # Cólera


def test_sem_csv_cai_para_curadoria(monkeypatch):
    # Empacotamento sem o CSV → degradação graciosa para a curadoria (nunca vazio).
    regs = base_cid._carregar_csv("/caminho/inexistente/cid10.csv")
    assert regs == []
