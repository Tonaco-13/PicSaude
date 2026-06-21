"""
F3 — binding verificável certificado ↔ prescritor (CPF).

Cobre a decisão pura em app/domain/binding_cert.py:
  - cadastro vazio   → vincular (TOFU), grava o CPF do certificado;
  - cadastro == cert → ok;
  - cadastro != cert → divergente;
  - comparação sobre CPF normalizado (formatação ignorada).
"""
from __future__ import annotations

from app.domain.binding_cert import (
    STATUS_DIVERGENTE,
    STATUS_OK,
    STATUS_VINCULAR,
    avaliar_binding_cpf,
)


def test_cadastro_vazio_vincula_tofu():
    """Sem CPF no cadastro → vincula (1ª vez) e devolve o CPF a gravar."""
    b = avaliar_binding_cpf(cpf_certificado="529.982.247-25", cpf_cadastro=None)
    assert b.status == STATUS_VINCULAR
    assert b.cpf_para_gravar == "52998224725"   # normalizado (só dígitos)


def test_cadastro_vazio_string_tambem_vincula():
    b = avaliar_binding_cpf(cpf_certificado="52998224725", cpf_cadastro="")
    assert b.status == STATUS_VINCULAR
    assert b.cpf_para_gravar == "52998224725"


def test_cpf_igual_ok():
    b = avaliar_binding_cpf(cpf_certificado="52998224725", cpf_cadastro="52998224725")
    assert b.status == STATUS_OK
    assert b.cpf_para_gravar is None


def test_cpf_igual_com_formatacao_diferente_ok():
    """Formatação diferente não deve gerar divergência — compara normalizado."""
    b = avaliar_binding_cpf(
        cpf_certificado="52998224725",
        cpf_cadastro="529.982.247-25",
    )
    assert b.status == STATUS_OK


def test_cpf_diferente_divergente():
    b = avaliar_binding_cpf(cpf_certificado="52998224725", cpf_cadastro="11144477735")
    assert b.status == STATUS_DIVERGENTE
    assert b.cpf_para_gravar is None
