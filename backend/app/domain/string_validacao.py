"""
string_validacao.py
===================
Ticket 67 — String de Validação Auditável.

Consolida identidade civil (CPF/ICP), profissional (CRM/CRO), institucional
(CNS/CNES) e evidência criptográfica do certificado em uma string determinística,
gerada no momento da emissão do objeto sanitário.

Formato canônico:
  CPF|CONSELHO|CNS|STATUS_NOME|HASH_CERT|TIMESTAMP

  CPF          11 dígitos (âncora civil — do certificado ICP-Brasil)
  CONSELHO     CRM-PE-12345 ou CRO-SP-54321
  CNS          15 dígitos ou NAO_RESOLVIDO
  STATUS_NOME  COERENTE_FORTE | COERENTE_PARCIAL | DIVERGENTE | NAO_VALIDADO
  HASH_CERT    SHA-256 do DER do certificado (hex 64 chars) ou SEM_CERT
  TIMESTAMP    ISO 8601 UTC (ex: 2026-04-06T14:32:10Z)

Segurança de hash:
  - Hash calculado sobre DER (não PEM cru)
  - PEM → x509.load_pem_x509_certificate → public_bytes(DER) → sha256
  - Imune a diferenças de formatação PEM (quebras de linha, encoding)
  - Mesmo certificado → mesmo hash em qualquer ambiente

Regras de negócio:
  - CPF sempre obrigatório (ausente = erro)
  - Conselho sempre obrigatório (ausente = erro)
  - CNS obrigatório quando vínculo foi resolvido pelo pipeline
  - STATUS_NOME nunca omitido
  - DIVERGENTE não bloqueia geração (registra divergência)
  - Múltiplos vínculos não resolvidos → CNS = NAO_RESOLVIDO
  - Cert ausente → HASH_CERT = SEM_CERT (emissão sem ICP; auditado)
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.serialization import Encoding

# ---------------------------------------------------------------------------
# Constantes de placeholder
# ---------------------------------------------------------------------------

_CNS_NAO_RESOLVIDO = "NAO_RESOLVIDO"
_HASH_SEM_CERT     = "SEM_CERT"
_STATUS_NAO_VAL    = "NAO_VALIDADO"

# Valores canônicos de status_nome (maiúsculas na string)
_STATUS_NOME_VALIDOS = frozenset({
    "COERENTE_FORTE",
    "COERENTE_PARCIAL",
    "DIVERGENTE",
    _STATUS_NAO_VAL,
})


# ---------------------------------------------------------------------------
# Hash criptográfico do certificado
# ---------------------------------------------------------------------------


def hash_cert_der(cert_pem: str) -> str:
    """
    Calcula SHA-256 do certificado em formato DER.

    O hash é calculado sobre o DER canônico, NÃO sobre a string PEM.
    Isso garante que o mesmo certificado gera o mesmo hash independente de:
      - quebras de linha (\n vs \r\n)
      - codificação base64 (espaços, padding)
      - headers adicionais (BEGIN/END)

    Parâmetros
    ----------
    cert_pem : str
        Certificado X.509 em formato PEM válido.

    Retorna
    -------
    str : hash SHA-256 hexadecimal de 64 caracteres, ou SEM_CERT em caso de erro.
    """
    try:
        cert = x509.load_pem_x509_certificate(
            cert_pem.encode("utf-8"),
            default_backend(),
        )
        der_bytes = cert.public_bytes(Encoding.DER)
        return hashlib.sha256(der_bytes).hexdigest()
    except Exception:
        return _HASH_SEM_CERT


# ---------------------------------------------------------------------------
# Geração da string de validação
# ---------------------------------------------------------------------------


def gerar_string_validacao_identidade(
    cpf: str,
    conselho_tipo: str,
    conselho_uf: str,
    conselho_numero: str,
    cns: Optional[str],
    status_nome: Optional[str],
    cert_pem: Optional[str],
    timestamp: Optional[datetime] = None,
) -> dict:
    """
    Gera a string de validação auditável do prescritor.

    Esta função deve ser chamada no momento da emissão do objeto sanitário
    (prescrição, pedido de exame), nunca no login.

    Parâmetros
    ----------
    cpf            CPF do prescritor (do certificado ICP-Brasil). Obrigatório.
    conselho_tipo  "CRM" ou "CRO". Obrigatório.
    conselho_uf    UF do conselho (ex: "PE"). Obrigatório.
    conselho_numero Número do registro (ex: "12345"). Obrigatório.
    cns            CNS do prescritor (do pipeline CNES). None → NAO_RESOLVIDO.
    status_nome    Resultado do NomeValidator. None → NAO_VALIDADO.
                   Valores aceitos: coerente_forte | coerente_parcial | divergente | nao_validado
                   (case-insensitive → normalizado para maiúsculas)
    cert_pem       Certificado PEM. None → HASH_CERT = SEM_CERT.
    timestamp      Momento da emissão (UTC). None → datetime.now(UTC).

    Retorna
    -------
    dict:
      string_validacao : str
      hash_cert        : str
      componentes      : dict com cada campo da string
      erro             : str | None

    Raises
    ------
    ValueError se CPF ou conselho estiverem ausentes.
    """
    # ── Validações obrigatórias ────────────────────────────────────────────
    cpf_norm = "".join(c for c in (cpf or "") if c.isdigit())
    if not cpf_norm:
        raise ValueError("CPF do prescritor é obrigatório para gerar string de validação.")

    conselho_tipo_norm = (conselho_tipo or "").strip().upper()
    conselho_uf_norm   = (conselho_uf or "").strip().upper()
    conselho_num_norm  = (conselho_numero or "").strip()

    if not conselho_tipo_norm or not conselho_uf_norm or not conselho_num_norm:
        raise ValueError(
            "Conselho (tipo, UF, número) é obrigatório para gerar string de validação. "
            "Exija fallback manual antes de chamar esta função."
        )

    # ── Componentes ────────────────────────────────────────────────────────
    ts: datetime = timestamp or datetime.now(tz=timezone.utc)
    ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")

    conselho_str = f"{conselho_tipo_norm}-{conselho_uf_norm}-{conselho_num_norm}"

    cns_str = "".join(c for c in (cns or "") if c.isdigit()) or _CNS_NAO_RESOLVIDO

    # Normalizar status_nome (aceita snake_case minúsculo ou maiúsculo)
    status_raw = (status_nome or "").upper().replace(" ", "_")
    if status_raw in {"COERENTE_FORTE", "COERENTE_PARCIAL", "DIVERGENTE"}:
        status_str = status_raw
    else:
        status_str = _STATUS_NAO_VAL

    # Hash do certificado (DER)
    if cert_pem:
        hash_str = hash_cert_der(cert_pem)
    else:
        hash_str = _HASH_SEM_CERT

    # ── Compor string canônica ────────────────────────────────────────────
    string_validacao = "|".join([
        cpf_norm,
        conselho_str,
        cns_str,
        status_str,
        hash_str,
        ts_str,
    ])

    return {
        "string_validacao": string_validacao,
        "hash_cert":        hash_str,
        "componentes": {
            "cpf":          cpf_norm,
            "conselho":     conselho_str,
            "cns":          cns_str,
            "status_nome":  status_str,
            "hash_cert":    hash_str,
            "timestamp":    ts_str,
        },
        "erro": None,
    }


# ---------------------------------------------------------------------------
# Builder integrado: ICP + Pipeline → string
# ---------------------------------------------------------------------------


def gerar_string_a_partir_de_binding(
    binding_result: dict,
    cert_pem: Optional[str],
    timestamp: Optional[datetime] = None,
) -> dict:
    """
    Constrói a string de validação a partir do resultado de binding_icp() (T66)
    e do resultado de resolver_identidade_prescritor() (T65).

    Convenção de campos esperados em `binding_result`:
      binding_result["icp"]          → ICPIdentidade.to_dict()
      binding_result["identidade"]   → resultado do T65 (ou None)

    Retorna dict idêntico ao de gerar_string_validacao_identidade(),
    ou dict com erro se os pré-requisitos não forem satisfeitos.
    """
    icp = binding_result.get("icp") or {}
    identidade = binding_result.get("identidade") or {}

    cpf           = icp.get("cpf_certificado") or ""
    conselho_tipo = icp.get("conselho_tipo") or ""
    conselho_uf   = icp.get("conselho_uf") or ""
    conselho_num  = icp.get("conselho_numero") or ""

    cns_raw = identidade.get("cns") or ""
    nome_val = identidade.get("nome_validacao") or {}
    status_nome_raw = nome_val.get("status") or ""

    try:
        return gerar_string_validacao_identidade(
            cpf=cpf,
            conselho_tipo=conselho_tipo,
            conselho_uf=conselho_uf,
            conselho_numero=conselho_num,
            cns=cns_raw,
            status_nome=status_nome_raw,
            cert_pem=cert_pem,
            timestamp=timestamp,
        )
    except ValueError as exc:
        return {
            "string_validacao": None,
            "hash_cert":        None,
            "componentes":      None,
            "erro":             str(exc),
        }
