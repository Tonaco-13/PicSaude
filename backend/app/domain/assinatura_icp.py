"""
assinatura_icp.py
=================
Ticket 68 — Verificação criptográfica da assinatura ICP-Brasil (A1/A3).

Prova matematicamente que o certificado correto assinou exatamente aquele payload.

Fluxo de verificação:
  1. Serializar payload de forma determinística (JSON canônico)
  2. Calcular SHA-256 do payload serializado → digest
  3. Carregar certificado PEM → extrair public_key
  4. Verificar assinatura com Prehashed (WebPKI assina o digest, não os bytes crus)
  5. Validar validade temporal do certificado (timezone-safe)

Por que Prehashed:
  O WebCrypto API (window.crypto.subtle) assina o digest SHA-256 diretamente.
  Usar `verify(payload_bytes, ...)` com hashes.SHA256() internamente rehasharia o
  digest, resultando em SHA256(SHA256(payload)) — verificação incorreta.
  `utils.Prehashed(hashes.SHA256())` instrui a biblioteca a tratar o segundo
  argumento como o digest já calculado.

Por que JSON canônico:
  sort_keys=True + separators=(',',':') garantem que a mesma estrutura de dados
  gera exatamente os mesmos bytes em qualquer ambiente Python, compatível com
  a serialização determinística do frontend (JSON.stringify com sort).

Segurança:
  - Não confiar no frontend além do PEM + assinatura + payload
  - Assinatura inválida → HTTPException 422 (não persistir prescrição)
  - Certificado expirado → HTTPException 422
  - Fluxo físico (sem cert/assinatura) → bypass total, sem exceção
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, utils


# ---------------------------------------------------------------------------
# Resultado estruturado
# ---------------------------------------------------------------------------


@dataclass
class ResultadoVerificacao:
    """
    Resultado da verificação criptográfica de uma assinatura ICP.

    Campos:
      valida           : True quando assinatura e certificado são válidos
      assinatura_valida: True quando a verificação matemática passou
      certificado_valido: True quando o certificado está dentro do prazo
      erro             : descrição da falha (None quando valida=True)
      digest_hex       : SHA-256 do payload serializado (auditoria)
    """
    valida:             bool
    assinatura_valida:  bool
    certificado_valido: bool
    erro:               Optional[str]
    digest_hex:         Optional[str]

    def to_dict(self) -> dict:
        return {
            "valida":             self.valida,
            "assinatura_valida":  self.assinatura_valida,
            "certificado_valido": self.certificado_valido,
            "erro":               self.erro,
            "digest_hex":         self.digest_hex,
        }


# ---------------------------------------------------------------------------
# Serialização determinística do payload
# ---------------------------------------------------------------------------


def serializar_payload(dados: Any) -> bytes:
    """
    Serializa dados para bytes de forma determinística (JSON canônico).

    Regras:
      - sort_keys=True   : ordena chaves de todos os objetos
      - separators=(',',':'): sem espaços → exatamente igual ao JSON.stringify sem espaço
      - ensure_ascii=False: preserva caracteres unicode no digest

    O frontend deve usar equivalente: JSON.stringify com sorted keys ou
    uma biblioteca de JSON canônico (RFC 8785). O digest resultante deve
    ser idêntico em ambos os lados para qualquer payload idêntico.

    Parâmetros
    ----------
    dados : dict | list | qualquer tipo serializável em JSON

    Retorna
    -------
    bytes : payload serializado em UTF-8
    """
    return json.dumps(
        dados,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")


def calcular_digest(dados: Any) -> bytes:
    """
    Calcula o SHA-256 do payload serializado de forma determinística.

    Retorna
    -------
    bytes : digest SHA-256 (32 bytes)
    """
    return hashlib.sha256(serializar_payload(dados)).digest()


# ---------------------------------------------------------------------------
# Validação temporal do certificado (timezone-safe)
# ---------------------------------------------------------------------------


def _validade_cert(cert: x509.Certificate) -> tuple[datetime, datetime]:
    """
    Extrai datas de validade do certificado de forma timezone-safe.

    cryptography >= 42.0 expõe `not_valid_before_utc` e `not_valid_after_utc`
    como datetime aware. Versões anteriores expõem datetimes naive que
    assumem UTC. Usamos getattr com fallback para compatibilidade.

    Retorna
    -------
    (inicio_validade, fim_validade) — ambos timezone-aware (UTC)
    """
    if hasattr(cert, "not_valid_before_utc"):
        inicio = cert.not_valid_before_utc
    else:
        inicio = cert.not_valid_before.replace(tzinfo=timezone.utc)  # type: ignore[attr-defined]

    if hasattr(cert, "not_valid_after_utc"):
        fim = cert.not_valid_after_utc
    else:
        fim = cert.not_valid_after.replace(tzinfo=timezone.utc)  # type: ignore[attr-defined]
    return inicio, fim


def verificar_validade_temporal(cert: x509.Certificate) -> tuple[bool, Optional[str]]:
    """
    Verifica se o certificado é temporalmente válido no instante atual (UTC).

    Retorna
    -------
    (valido, erro):
      (True, None)                      — certificado dentro do prazo
      (False, "certificado_expirado")   — fim_validade < agora
      (False, "certificado_nao_ativo")  — inicio_validade > agora
    """
    agora = datetime.now(timezone.utc)
    inicio, fim = _validade_cert(cert)

    if inicio > agora:
        return False, "certificado_nao_ativo"
    if fim < agora:
        return False, "certificado_expirado"
    return True, None


# ---------------------------------------------------------------------------
# Verificação principal da assinatura
# ---------------------------------------------------------------------------


def verificar_assinatura_icp(
    cert_pem: str,
    assinatura_b64: str,
    dados_payload: Any,
) -> ResultadoVerificacao:
    """
    Verifica a assinatura ICP-Brasil de um payload.

    Esta é a função principal de verificação criptográfica.
    Nunca lança exceção — retorna ResultadoVerificacao com valida=False e erro.

    Parâmetros
    ----------
    cert_pem       : str — certificado X.509 PEM do prescritor
    assinatura_b64 : str — assinatura RSA PKCS1v15 em Base64
                          (gerada pelo WebCrypto/WebPKI sobre o digest SHA-256)
    dados_payload  : dict — payload da prescrição (exatamente como enviado ao frontend)

    Retorna
    -------
    ResultadoVerificacao

    Notas de segurança
    ------------------
    - Usa Prehashed para compatibilidade com WebCrypto (que assina o digest)
    - Validação temporal sempre executada após validação da assinatura
    - Falha em qualquer etapa → valida=False, sem persistência
    """
    # ── Passo 1 — Decodificar assinatura ──────────────────────────────────
    try:
        assinatura = base64.b64decode(assinatura_b64)
    except Exception as exc:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=False,
            certificado_valido=False,
            erro=f"base64_invalido: {exc}",
            digest_hex=None,
        )

    # ── Passo 2 — Calcular digest do payload ──────────────────────────────
    try:
        digest = calcular_digest(dados_payload)
        digest_hex = digest.hex()
    except Exception as exc:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=False,
            certificado_valido=False,
            erro=f"serializacao_falhou: {exc}",
            digest_hex=None,
        )

    # ── Passo 3 — Carregar certificado ────────────────────────────────────
    try:
        cert = x509.load_pem_x509_certificate(
            cert_pem.encode("utf-8"),
            default_backend(),
        )
        public_key = cert.public_key()
    except Exception as exc:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=False,
            certificado_valido=False,
            erro=f"pem_invalido: {exc}",
            digest_hex=digest_hex,
        )

    # ── Passo 4 — Verificar assinatura (Prehashed) ────────────────────────
    try:
        public_key.verify(
            assinatura,
            digest,
            padding.PKCS1v15(),
            utils.Prehashed(hashes.SHA256()),
        )
        assinatura_ok = True
    except InvalidSignature:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=False,
            certificado_valido=False,
            erro="assinatura_invalida",
            digest_hex=digest_hex,
        )
    except Exception as exc:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=False,
            certificado_valido=False,
            erro=f"erro_verificacao: {exc}",
            digest_hex=digest_hex,
        )

    # ── Passo 5 — Validar validade temporal (timezone-safe) ───────────────
    cert_ok, erro_temporal = verificar_validade_temporal(cert)
    if not cert_ok:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=True,   # assinatura é matematicamente válida
            certificado_valido=False,
            erro=erro_temporal,
            digest_hex=digest_hex,
        )

    # ── Passo 6 — Validar cadeia de confiança ICP-Brasil (F2) ─────────────
    # Sem isto, um autoassinado (mesmo com emissor forjado) passava. Import
    # local (padrão do projeto) para não carregar pyhanko_certvalidator à toa.
    from app.domain.validacao_cadeia_icp import (
        TrustStoreIndisponivel,
        validar_cadeia_icp,
    )
    try:
        cadeia = validar_cadeia_icp(cert_pem)
    except TrustStoreIndisponivel:
        # Fora de dev/test sem truststore → falha fechado (rejeita).
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=True,
            certificado_valido=False,
            erro="truststore_indisponivel",
            digest_hex=digest_hex,
        )
    if not cadeia.valida:
        return ResultadoVerificacao(
            valida=False,
            assinatura_valida=True,
            certificado_valido=False,
            erro=cadeia.erro or "cadeia_nao_confiavel",
            digest_hex=digest_hex,
        )

    # ── Sucesso ───────────────────────────────────────────────────────────
    return ResultadoVerificacao(
        valida=True,
        assinatura_valida=True,
        certificado_valido=True,
        erro=None,
        digest_hex=digest_hex,
    )
