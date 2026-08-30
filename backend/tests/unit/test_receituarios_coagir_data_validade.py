"""tests/unit/test_receituarios_coagir_data_validade.py

Achado do G3 (DESENHO-TALAO-DIGITAL-SNCR.md §3, browser test do PDF do
receituário): `data_validade` sai do SQLite como TEXT (string ISO) e do
PostgreSQL como `datetime` nativo — mesmo driver (`app.database`), leitura
por dialeto diferente. `regras_receituario.receituario_expirado` (e a
serialização via `.isoformat()`) contam com o TIPO datetime; sem
coerção na leitura, `GET /prescricoes/{proto}/receituarios/{id}/pdf`
quebrava com `TypeError: '<' not supported between instances of 'str'
and 'datetime.datetime'` — só sob SQLite, nunca visto pelos testes de
integração (que rodam contra PG, onde o driver já entrega `datetime`).

Guarda rápida, sem app/DB: prova só a função pura de coerção.
"""
from __future__ import annotations

from datetime import datetime

from app.routers.receituarios import _coagir_data_validade


def test_coagir_data_validade_converte_string_iso_para_datetime():
    rec = {"id": 1, "data_validade": "2026-09-15T10:30:00"}
    resultado = _coagir_data_validade(rec)
    assert isinstance(resultado["data_validade"], datetime)
    assert resultado["data_validade"] == datetime(2026, 9, 15, 10, 30, 0)


def test_coagir_data_validade_preserva_datetime_ja_nativo():
    """PostgreSQL já entrega datetime — a coerção é um no-op, não uma
    reconversão que poderia perder precisão/timezone."""
    original = datetime(2026, 9, 15, 10, 30, 0)
    rec = {"id": 1, "data_validade": original}
    resultado = _coagir_data_validade(rec)
    assert resultado["data_validade"] is original


def test_coagir_data_validade_preserva_none():
    rec = {"id": 1, "data_validade": None}
    resultado = _coagir_data_validade(rec)
    assert resultado["data_validade"] is None


def test_coagir_data_validade_muta_e_retorna_o_mesmo_dict():
    rec = {"id": 1, "data_validade": "2026-09-15T10:30:00"}
    resultado = _coagir_data_validade(rec)
    assert resultado is rec
