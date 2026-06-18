"""Unit — parser da APRESENTAÇÃO CMED (gerar_medicamentos_cmed.py).

Cobre as regras de normalização que a verificação adversarial (2 rodadas) consolidou:
forma bem-formada, concentração, via inferida/explícita, concordância de gênero,
expansão de abreviações ANVISA e tarja→controle.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "gerar_medicamentos_cmed.py"
_spec = importlib.util.spec_from_file_location("gerar_medicamentos_cmed", _SCRIPT)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]

parse = mod._parse_apresentacao


@pytest.mark.parametrize("ap, conc, forma, via", [
    ("500 MG COM REV CT BL AL X 30",            "500 mg", "comprimido revestido", "oral"),
    ("500 MG CAP DURA CT BL AL X 21",           "500 mg", "cápsula dura", "oral"),
    # sigla de via parenteral NÃO compõe a forma; vai para via
    ("500 MG PO SOL INJ IV CT FA",              "500 mg", "pó para solução injetável", "intravenosa"),
    # pó liofilizado injetável -> canônico "para solução injetável"
    ("PO LIOF INJ CT 1 FA + DIL",               "",       "pó liofilizado para solução injetável", "parenteral"),
    # concordância de gênero: pomada (fem) -> dermatológica
    ("10 MG/G POM DERM BG AL X 30 G",           "10 mg/g", "pomada dermatológica", "tópica"),
    # cápsula gel -> gelatinosa
    ("100 MG CAP GEL MOLE CT BL X 30",          "100 mg", "cápsula gelatinosa mole", "oral"),
    # abreviações expandidas
    ("20 MG/ML XAMP CT FR X 100 ML",            "20 mg/ml", "xampu", "tópica"),
    ("10 MG OVU CT BL X 1",                     "10 mg", "óvulo", "vaginal"),
    ("0,7 MG IMPL IVIT CT SER",                 "0,7 mg", "implante intravítreo", "intravítrea"),
    ("250 MCG AER DOSIF CT VAL X 200 DOSES",    "250 mcg", "aerossol dosimetrado", "inalatória"),
    # PAS DURA = pastilha (não pasta) — achado de alta gravidade
    ("3 MG PAS DURA CT 25 STRIP",               "3 mg", "pastilha dura", "bucal"),
])
def test_parse_apresentacao(ap, conc, forma, via):
    c, f, v = parse(ap)
    assert (c, f, v) == (conc, forma, via)


def test_sevoflurano_inalatoria_nao_nasal():
    c, f, v = parse("1ML/ML LIQ INAL NAS CT FR X 250ML")
    assert v == "inalatória"
    assert "nasal" not in f


def test_limpar_substancia_combo():
    assert mod._limpar_substancia("21-ACETATO DE DEXAMETASONA;CLOTRIMAZOL") == \
        "acetato de dexametasona + clotrimazol"


@pytest.mark.parametrize("tarja, esperado", [
    ("Tarja Vermelha", "venda_sob_prescricao"),
    ("Tarja Vermelha sob restrição", "venda_sob_prescricao_retida"),
    ("Tarja Preta", "controle_especial_notificacao"),
    ("Tarja Sem Tarja", "venda_livre"),
])
def test_tarja_controle(tarja, esperado):
    assert mod._tarja_controle(tarja) == esperado
