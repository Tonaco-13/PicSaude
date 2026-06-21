"""
validacao_cadeia_icp.py — F2: validação da cadeia de confiança ICP-Brasil.

PROBLEMA (achado F2 da auditoria)
---------------------------------
A verificação de assinatura validava assinatura matemática + validade temporal,
mas NÃO a cadeia até a AC-Raiz ICP-Brasil nem revogação. Um certificado
autoassinado — mesmo com o nome do emissor forjado — passava como válido.

FASE A (este módulo)
--------------------
- Valida o CAMINHO do certificado até uma AC-Raiz CONFIÁVEL (rejeita
  autoassinado e cadeia não-ancorada).
- Os trust anchors vêm de `PICSAUDE_ICP_TRUSTSTORE` (bundle PEM apontado por
  variável de ambiente — NENHUM `.pem` no repositório, conforme regra do projeto).
- Sem truststore:
    * em dev/test → cadeia não avaliada (assinatura + validade ainda valem);
    * fora de dev/test → falha fechado (padrão do cofre F1).
- Revogação em soft-fail (OCSP/CRL é Fase B).
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import List, Optional

from asn1crypto import x509 as a1x
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding
from pyhanko_certvalidator import CertificateValidator, ValidationContext

_ENV_TRUSTSTORE = "PICSAUDE_ICP_TRUSTSTORE"
_AMBIENTES_SEM_TRUSTSTORE_OK = ("dev", "test")


class TrustStoreIndisponivel(RuntimeError):
    """Truststore ICP ausente num ambiente que o exige (fail-closed)."""


@dataclass(frozen=True)
class ResultadoCadeia:
    valida: bool
    erro: Optional[str] = None
    avaliada: bool = True   # False = pulada (dev/test sem truststore)


def _carregar_trust_anchors() -> Optional[List[a1x.Certificate]]:
    """Carrega as AC-Raiz do bundle PEM em PICSAUDE_ICP_TRUSTSTORE.

    Retorna None se a variável não estiver configurada.
    """
    path = os.getenv(_ENV_TRUSTSTORE)
    if not path:
        return None
    with open(path, "rb") as fh:
        certs = x509.load_pem_x509_certificates(fh.read())
    return [a1x.Certificate.load(c.public_bytes(Encoding.DER)) for c in certs]


def validar_cadeia_icp(cert_pem: str, *, momento=None) -> ResultadoCadeia:
    """Valida a cadeia do certificado até uma AC-Raiz ICP-Brasil confiável.

    Parâmetros
    ----------
    cert_pem : PEM do certificado do prescritor.
    momento  : datetime tz-aware para a validação (default: agora).

    Nunca lança por cadeia inválida — devolve ResultadoCadeia(valida=False).
    Lança TrustStoreIndisponivel se o ambiente exige truststore e ele falta.
    """
    anchors = _carregar_trust_anchors()
    if anchors is None:
        env = os.getenv("PICSAUDE_ENV", "dev").lower()
        if env in _AMBIENTES_SEM_TRUSTSTORE_OK:
            return ResultadoCadeia(valida=True, avaliada=False)
        raise TrustStoreIndisponivel(
            f"{_ENV_TRUSTSTORE} não configurado: a validação de cadeia ICP-Brasil "
            f"é obrigatória fora de dev/test (ambiente='{env}')."
        )

    try:
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
        leaf = a1x.Certificate.load(cert.public_bytes(Encoding.DER))
    except Exception as exc:
        return ResultadoCadeia(valida=False, erro=f"pem_invalido: {exc}")

    vc = ValidationContext(
        trust_roots=anchors,
        allow_fetching=False,         # sem rede; revogação local apenas
        revocation_mode="soft-fail",  # OCSP/CRL = Fase B
        moment=momento,
    )
    try:
        validator = CertificateValidator(leaf, validation_context=vc)
        asyncio.run(validator.async_validate_path())
        return ResultadoCadeia(valida=True)
    except Exception as exc:
        return ResultadoCadeia(
            valida=False, erro=f"cadeia_nao_confiavel: {type(exc).__name__}"
        )
