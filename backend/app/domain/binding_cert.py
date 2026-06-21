"""
binding_cert.py — F3: binding verificável certificado ↔ prescritor (CPF).

Decide, de forma PURA e determinística, se o CPF de um certificado pode ser
amarrado ao prescritor:

  - cadastro vazio   → 'vincular' (TOFU): grava o CPF do certificado;
  - cadastro == cert → 'ok';
  - cadastro != cert → 'divergente' (rejeitar).

A comparação é feita sobre CPFs normalizados (só dígitos).

Limitação (Fase A): sem fonte confiável de CPF (o CNES não o expõe), isto
garante CONSISTÊNCIA (a conta não acumula identidades diferentes), não PROVA
de identidade. A prova forte do CPF contra base confiável (CADSUS) é a Fase B
(T65).

Pré-condição: o chamador (routers/prescritor.py) já garante que o certificado
contém CPF (422 caso contrário). Esta função não decide sobre cert sem CPF.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.utils.helpers import normalize_cpf

STATUS_OK = "ok"
STATUS_VINCULAR = "vincular"
STATUS_DIVERGENTE = "divergente"


@dataclass(frozen=True)
class BindingCpf:
    status: str                      # ok | vincular | divergente
    cpf_para_gravar: Optional[str]   # preenchido somente quando status == vincular


def avaliar_binding_cpf(
    cpf_certificado: Optional[str],
    cpf_cadastro: Optional[str],
) -> BindingCpf:
    """Avalia o binding CPF do certificado contra o CPF do prescritor."""
    cpf_cert = normalize_cpf(cpf_certificado or "")
    cpf_cad = normalize_cpf(cpf_cadastro or "")

    if not cpf_cad:
        return BindingCpf(STATUS_VINCULAR, cpf_cert)
    if cpf_cad == cpf_cert:
        return BindingCpf(STATUS_OK, None)
    return BindingCpf(STATUS_DIVERGENTE, None)
