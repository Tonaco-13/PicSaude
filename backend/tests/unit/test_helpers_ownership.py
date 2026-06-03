"""TICKET-5C-BIS-A — testes unitários dos Helpers 1 e 2 (ADR-002).

Cobre o §9 (suíte unitária) do ticket:
  - `_normalizar_identidade_jwt`: contrato de totalidade (§6.2) — nunca levanta,
    sempre retorna (papel, identificador); CNPJ via normalize_cnpj (remove `.0`).
  - `_assert_or_403`: condição falsa → HTTPException(403, {codigo,mensagem});
    verdadeira → no-op.

Puro, sem banco — roda sem PostgreSQL.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.utils.helpers import _assert_or_403, _normalizar_identidade_jwt


# ===========================================================================
# _normalizar_identidade_jwt — contrato de totalidade (§6.2)
# ===========================================================================

def test_normaliza_prescritor_cns():
    papel, ident = _normalizar_identidade_jwt(
        {"role": "prescritor", "sub": "987654321098765"}
    )
    assert papel == "prescritor"
    assert ident == "987654321098765"


def test_normaliza_prescritor_cns_com_mascara():
    # sub com espaços/máscara → só dígitos (equivale a normalize_cns).
    papel, ident = _normalizar_identidade_jwt(
        {"role": "prescritor", "sub": "987 654 321 098 765"}
    )
    assert papel == "prescritor"
    assert ident == "987654321098765"


def test_normaliza_paciente_cpf():
    papel, ident = _normalizar_identidade_jwt(
        {"role": "paciente", "sub": "123.456.789-01"}
    )
    assert papel == "paciente"
    assert ident == "12345678901"


def test_normaliza_dispensador_cnpj_simples():
    papel, ident = _normalizar_identidade_jwt(
        {"role": "dispensador", "sub": "12345678000195"}
    )
    assert papel == "dispensador"
    assert ident == "12345678000195"
    assert len(ident) == 14


def test_normaliza_dispensador_cnpj_remove_sufixo_ponto_zero():
    # §8.2 — artefato Excel `.0`: normalize_cnpj remove; o strip genérico NÃO.
    papel, ident = _normalizar_identidade_jwt(
        {"role": "dispensador", "sub": "12345678000195.0"}
    )
    assert papel == "dispensador"
    assert ident == "12345678000195"


def test_normaliza_dispensador_cnpj_com_mascara():
    papel, ident = _normalizar_identidade_jwt(
        {"role": "dispensador", "sub": "12.345.678/0001-95"}
    )
    assert papel == "dispensador"
    assert ident == "12345678000195"


def test_normaliza_admin_sub_nao_clinico_nao_levanta():
    # admin/auditor não têm chave clínica — sub pode ser e-mail/apikey.
    # Contrato de totalidade: retorna (papel, <dígitos ou "">), sem exceção.
    papel, ident = _normalizar_identidade_jwt(
        {"role": "admin", "sub": "apikey:sistema"}
    )
    assert papel == "admin"
    assert ident == ""   # nenhum dígito no sub


def test_normaliza_auditor_sub_com_alguns_digitos():
    papel, ident = _normalizar_identidade_jwt(
        {"role": "auditor", "sub": "auditor-42"}
    )
    assert papel == "auditor"
    assert ident == "42"


def test_normaliza_payload_vazio_nao_levanta():
    # Totalidade extrema: dict vazio → ("", "") sem exceção.
    papel, ident = _normalizar_identidade_jwt({})
    assert papel == ""
    assert ident == ""


def test_normaliza_contrato_de_retorno_estavel():
    # Sempre tupla de 2 strings.
    for usuario in (
        {"role": "prescritor", "sub": "987654321098765"},
        {"role": "dispensador", "sub": "12.345.678/0001-95"},
        {"role": "admin", "sub": "x"},
        {},
    ):
        resultado = _normalizar_identidade_jwt(usuario)
        assert isinstance(resultado, tuple)
        assert len(resultado) == 2
        assert all(isinstance(x, str) for x in resultado)


# ===========================================================================
# _assert_or_403
# ===========================================================================

def test_assert_or_403_condicao_verdadeira_noop():
    assert _assert_or_403(True, codigo="qualquer", mensagem="ok") is None


def test_assert_or_403_condicao_falsa_levanta_403():
    with pytest.raises(HTTPException) as exc:
        _assert_or_403(
            False,
            codigo="nao_e_dono_do_pedido_exame",
            mensagem="Este pedido de exame foi emitido por outro prescritor.",
        )
    assert exc.value.status_code == 403
    assert exc.value.detail == {
        "codigo": "nao_e_dono_do_pedido_exame",
        "mensagem": "Este pedido de exame foi emitido por outro prescritor.",
    }
