"""Unit — apresentações comerciais (embalagens reais da CMED) por medicamento.

Suporta o campo OPCIONAL de apresentação comercial no card de prescrição.
"""
from __future__ import annotations

from app.ai.apresentacoes_comerciais import (
    apresentacoes_comerciais, _rotulo, total_indexado,
)


def test_indice_carregado():
    assert total_indexado() > 1000   # base CMED real indexada


def test_rotulo_contagem_solido():
    assert _rotulo("500 MG CAP DURA CT BL AL X 30", "cápsula dura") == "caixa com 30 cápsulas"
    assert _rotulo("500 MG COM REV CT BL AL X 1", "comprimido revestido") == "caixa com 1 comprimido"


def test_rotulo_volume_liquido():
    assert _rotulo("50 MG/ML PO SUS OR CT FR VD X 150 ML", "pó para suspensão oral") == "frasco com 150 ml"


def test_rotulo_sem_pack_retorna_none():
    assert _rotulo("500 MG CAP DURA CT BL AL", "cápsula dura") is None


def test_apresentacoes_de_medicamento_real():
    rs = apresentacoes_comerciais("dipirona", "500 mg", "comprimido", 8)
    assert rs                                   # tem embalagens
    assert all(r.startswith(("caixa", "frasco", "bisnaga")) for r in rs)
    # ordenadas (menor primeiro)
    import re
    nums = [float(re.search(r"com (\d+)", r).group(1)) for r in rs if re.search(r"com (\d+)", r)]
    assert nums == sorted(nums)


def test_medicamento_inexistente_retorna_vazio():
    assert apresentacoes_comerciais("xpto inexistente", "1 mg", "comprimido") == []
