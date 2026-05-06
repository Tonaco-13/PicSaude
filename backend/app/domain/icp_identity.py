"""
icp_identity.py
===============
Ticket 66 — Binding ICP-Brasil A1/A3: parsing criptográfico + extração de identidade.

Camada:
  1. Recebe certificado bruto (PEM) — apenas do backend
  2. Faz parsing X.509 com cryptography.x509
  3. Extrai CPF, nome e (quando presente) CRM/CRO + UF
  4. Retorna ICPIdentidade para integração com pipeline do Ticket 65

Fontes de dados por campo
--------------------------
  CPF   : OID 2.16.76.1.3.1 (SAN OtherName, DOC-ICP-04.4 Pessoa Física)
           → offset fixo: posição 9 a 19 da string decodificada
           → fallback: regex 11 dígitos em OU / CN
  Nome  : CN (CommonName) do Subject
  CRM/CRO: OU (OrganizationalUnit) — regex tolerante a variações reais

OID ICP-Brasil 2.16.76.1.3.1 — formato DOC-ICP-04.4 Pessoa Física:
  Posição  0-7  : DDMMAAAA (data de nascimento, 8 chars)
  Posição  8    : E (tipo de documento de identificação, 1 char)
  Posição  9-19 : CPF sem pontuação (11 chars)
  Posição 20-30 : NIS / PIS / PASEP (11 chars, pode ser zeros)
  Posição 31-45 : RG (15 chars, pode conter letras, completado com espaços)
  Posição 46-51 : Órgão emissor do RG (6 chars)

Segurança:
  - O frontend envia apenas o PEM bruto
  - NUNCA confiar em CPF/nome enviados pelo frontend
  - O backend é a única fonte de verdade criptográfica
  - Validação ICP completa (OCSP/CRL/cadeia) é responsabilidade do Ticket 67

Compatibilidade A1/A3:
  - Funciona para qualquer certificado X.509 PEM válido
  - Não assume origem do certificado
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.x509.oid import NameOID

# ---------------------------------------------------------------------------
# OIDs ICP-Brasil
# ---------------------------------------------------------------------------

_OID_ICP_PESSOA_FISICA = x509.ObjectIdentifier("2.16.76.1.3.1")
# Outros OIDs ICP-Brasil (reservados para extensão futura):
# 2.16.76.1.3.6 → CPF pessoa jurídica responsável
# 2.16.76.1.3.5 → dados do responsável pessoa física por PJ

# ---------------------------------------------------------------------------
# Expressões regulares
# ---------------------------------------------------------------------------

# Conselho: aceita variações reais encontradas em produção
# Exemplos: "CRM PE 12345" / "CRM-PE 12345" / "CRO-SP-54321" / "CRM.PE.29243"
_RE_CONSELHO = re.compile(
    r"\b(CRM|CRO)[\s\-\.]*([A-Z]{2})[\s\-\.]*(\d{3,7})\b",
    re.IGNORECASE,
)

# CPF: 11 dígitos contíguos (para busca em OU/CN como fallback)
_RE_CPF_11 = re.compile(r"\d{11}")

# CPF formatado: 000.000.000-00
_RE_CPF_FORMATTED = re.compile(r"\d{3}\.\d{3}\.\d{3}-\d{2}")


# ---------------------------------------------------------------------------
# Estrutura de resultado
# ---------------------------------------------------------------------------


@dataclass
class ICPIdentidade:
    """
    Identidade extraída de um certificado ICP-Brasil.

    Campos sempre presentes:
      cpf_certificado  : str | None
      nome_certificado : str | None
      conselho_numero  : str | None
      conselho_uf      : str | None
      conselho_tipo    : "CRM" | "CRO" | None
      fonte_campos     : dict — rastreabilidade de cada campo
      erro             : str | None — mensagem de erro de parsing (não lança)
      parseable        : bool — True se o PEM foi lido com sucesso

    """

    cpf_certificado: Optional[str] = None
    nome_certificado: Optional[str] = None
    conselho_numero: Optional[str] = None
    conselho_uf: Optional[str] = None
    conselho_tipo: Optional[str] = None
    fonte_campos: dict = field(default_factory=dict)
    erro: Optional[str] = None
    parseable: bool = False

    def precisa_conselho_manual(self) -> bool:
        """True quando conselho não pôde ser extraído do certificado."""
        return self.conselho_numero is None

    def to_dict(self) -> dict:
        return {
            "cpf_certificado":  self.cpf_certificado,
            "nome_certificado": self.nome_certificado,
            "conselho_numero":  self.conselho_numero,
            "conselho_uf":      self.conselho_uf,
            "conselho_tipo":    self.conselho_tipo,
            "fonte_campos":     self.fonte_campos,
            "erro":             self.erro,
            "parseable":        self.parseable,
        }


# ---------------------------------------------------------------------------
# Helpers de parsing
# ---------------------------------------------------------------------------


def _decode_der_string(raw: bytes) -> Optional[str]:
    """
    Decodifica uma string DER-encoded (UTF8String, IA5String, PrintableString,
    BMPString ou raw), desembrulhando wrappers ASN.1 recursivamente.

    Tags de string reconhecidas:
      0x0C  UTF8String
      0x16  IA5String
      0x13  PrintableString
      0x1B  GeneralString
      0x1E  BMPString (UTF-16 BE)

    Tags wrapper (desembrulhadas recursivamente):
      0x04       OCTET STRING
      0x30       SEQUENCE
      0x80-0xBF  context-specific (ex.: [0] EXPLICIT de OtherName)

    Alguns emissores ICP-Brasil (Serpro, Certisign, Serasa) encapsulam
    o valor do OID 2.16.76.1.3.1 em uma ou mais camadas wrapper.
    Sem o unwrap, bytes do TLV header vazam para a string decodificada,
    deslocando os offsets do DOC-ICP-04.4 (bug de CPF off-by-one).

    Retorna None em caso de erro, sem lançar exceção.
    """
    if not raw:
        return None
    try:
        tag = raw[0]

        # Wrapper tags — desembrulhar e recursão
        if tag in (0x04, 0x30) or (tag & 0xC0) == 0x80:
            length = raw[1]
            offset = 2
            if length & 0x80:
                n_bytes = length & 0x7F
                length = int.from_bytes(raw[2 : 2 + n_bytes], "big")
                offset = 2 + n_bytes
            inner = raw[offset : offset + length]
            return _decode_der_string(inner)

        # String tags
        if tag in (0x0C, 0x16, 0x13, 0x1B):
            length = raw[1]
            offset = 2
            if length & 0x80:
                n_bytes = length & 0x7F
                length = int.from_bytes(raw[2 : 2 + n_bytes], "big")
                offset = 2 + n_bytes
            data = raw[offset : offset + length]
            return data.decode("utf-8", errors="replace")
        if tag == 0x1E:
            # BMPString → UTF-16 BE
            length = raw[1]
            offset = 2
            if length & 0x80:
                n_bytes = length & 0x7F
                length = int.from_bytes(raw[2 : 2 + n_bytes], "big")
                offset = 2 + n_bytes
            data = raw[offset : offset + length]
            return data.decode("utf-16-be", errors="replace")
        # Fallback: tenta UTF-8 direto
        return raw.decode("utf-8", errors="ignore") or None
    except Exception:
        return None


def _extrair_cpf_oid(raw: bytes, cpf_cn: Optional[str] = None) -> Optional[str]:
    """
    Extrai o CPF do valor bruto do OID 2.16.76.1.3.1.

    O formato DOC-ICP-04.4 documenta o CPF nas posições 9–19 da string
    (8 chars data nascimento + 1 char tipo documento + 11 chars CPF).
    No entanto, alguns emissores (Serpro, Certisign) omitem o campo de
    tipo de documento ou variam a codificação DER, deslocando o offset.

    Estratégia (robusta para múltiplos emissores):
      1. Decodifica a string DER (com unwrap de wrappers ASN.1)
      2. Tenta offsets 8:19 e 9:20 (cobre ambas as variações conhecidas)
      3. Se cpf_cn fornecido (extraído do CN), valida contra ele
      4. Fallback: procura 11 dígitos contíguos na string decodificada

    Parameters
    ----------
    raw     : bytes DER do valor do OID 2.16.76.1.3.1
    cpf_cn  : CPF extraído do CN do Subject (para validação cruzada)

    Returns
    -------
    CPF como string de 11 dígitos, ou None.
    """
    decoded = _decode_der_string(raw)
    if not decoded:
        return None

    # Estratégia 1: offsets conhecidos do DOC-ICP-04.4
    # Posição 8:19 = sem campo tipo_documento (Serpro, alguns emissores)
    # Posição 9:20 = com campo tipo_documento (DOC-ICP-04.4 literal)
    candidates_offset: list[str] = []
    for start, end in [(8, 19), (9, 20)]:
        if len(decoded) >= end:
            candidate = decoded[start:end]
            if candidate.isdigit() and len(set(candidate)) > 1:
                candidates_offset.append(candidate)

    # Se temos cpf_cn, validar contra ele (prioridade máxima)
    if cpf_cn and candidates_offset:
        for c in candidates_offset:
            if c == cpf_cn:
                return c

    # Se apenas um candidato, usar ele
    if len(candidates_offset) == 1:
        return candidates_offset[0]

    # Se dois candidatos sem cpf_cn para desempatar, preferir 8:19
    # (variação Serpro — mais comum no Brasil)
    if len(candidates_offset) == 2:
        return candidates_offset[0]  # 8:19

    # Fallback: sequências de 11 dígitos não-triviais
    for m in _RE_CPF_11.finditer(decoded):
        candidate = m.group()
        if len(set(candidate)) > 1:  # evitar "00000000000"
            if cpf_cn and candidate == cpf_cn:
                return candidate
    # Sem validação cruzada, retornar primeiro match
    for m in _RE_CPF_11.finditer(decoded):
        candidate = m.group()
        if len(set(candidate)) > 1:
            return candidate

    return None


def _extrair_cpf_ou(ous: list[str]) -> Optional[str]:
    """
    Tenta extrair CPF de campos OU quando OID não está disponível.

    Procura por CPF formatado (000.000.000-00) ou 11 dígitos contíguos.
    """
    for ou in ous:
        m = _RE_CPF_FORMATTED.search(ou)
        if m:
            return re.sub(r"\D", "", m.group())
        m = _RE_CPF_11.search(ou)
        if m:
            candidate = m.group()
            if len(set(candidate)) > 1:
                return candidate
    return None


def _extrair_conselho(ous: list[str]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Extrai conselho (tipo, UF, número) de campos OU.

    Percorre todos os OU e retorna o primeiro match.

    Returns
    -------
    (tipo, uf, numero) em maiúsculas, ou (None, None, None).
    """
    for ou in ous:
        m = _RE_CONSELHO.search(ou)
        if m:
            tipo = m.group(1).upper()
            uf   = m.group(2).upper()
            num  = m.group(3)
            return tipo, uf, num
    return None, None, None


# ---------------------------------------------------------------------------
# Função principal de parsing
# ---------------------------------------------------------------------------


def parsear_certificado_icp(cert_pem: str) -> ICPIdentidade:
    """
    Faz parsing criptográfico de um certificado ICP-Brasil PEM.

    Esta função é a única autoridade de extração de identidade do certificado.
    O resultado deve ser alimentado diretamente no pipeline do Ticket 65
    via resolver_identidade_prescritor().

    Parâmetros
    ----------
    cert_pem : str
        Certificado X.509 em formato PEM (incluindo markers BEGIN/END).
        Aceita A1 e A3 — a origem não é verificada aqui.

    Retorna
    -------
    ICPIdentidade
        Sempre retorna um objeto, nunca lança exceção.
        Se o PEM for inválido: parseable=False, erro=<mensagem>.

    Notas de segurança
    ------------------
    - Não valida cadeia de confiança (responsabilidade do Ticket 67)
    - Não consulta OCSP/CRL
    - Não verifica assinatura em relação a uma CA raiz
    """
    # ── Carregar certificado ───────────────────────────────────────────────
    try:
        cert = x509.load_pem_x509_certificate(
            cert_pem.encode("utf-8"),
            default_backend(),
        )
    except Exception as exc:
        return ICPIdentidade(
            erro=f"pem_invalido: {exc}",
            parseable=False,
            fonte_campos={"cpf": "nao_encontrado", "nome": "nao_encontrado", "conselho": "nao_encontrado"},
        )

    identidade = ICPIdentidade(parseable=True)
    fonte: dict = {}

    # ── Extração de nome (CN) ─────────────────────────────────────────────
    try:
        cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            raw_cn = cn_attrs[0].value.strip().upper()
            # Serpro e alguns emissores concatenam CPF no CN:
            #   "FABIANO TONACO BORGES:83086439149"
            # Limpar o sufixo ":CPF" para obter apenas o nome.
            if ":" in raw_cn:
                raw_cn = raw_cn.split(":")[0].strip()
            identidade.nome_certificado = raw_cn
            fonte["nome"] = "cn"
        else:
            fonte["nome"] = "nao_encontrado"
    except Exception:
        fonte["nome"] = "nao_encontrado"

    # ── Coletar campos OU ─────────────────────────────────────────────────
    ous: list[str] = []
    try:
        for attr in cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME):
            ous.append(attr.value or "")
    except Exception:
        pass

    # ── Extrair CPF do CN como referência para validação cruzada ────────
    # Serpro concatena CPF no CN: "NOME:CPF". Usar como hint para o OID.
    cpf_cn: Optional[str] = None
    if identidade.nome_certificado:
        try:
            raw_cn_full = cn_attrs[0].value.strip() if cn_attrs else ""
            if ":" in raw_cn_full:
                cpf_hint = raw_cn_full.split(":")[-1].strip()
                if cpf_hint.isdigit() and len(cpf_hint) == 11:
                    cpf_cn = cpf_hint
        except Exception:
            pass

    # ── Extração de CPF — OID 2.16.76.1.3.1 (SAN OtherName) ──────────────
    cpf: Optional[str] = None
    fonte_cpf = "nao_encontrado"

    try:
        san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        for name in san_ext.value:
            if isinstance(name, x509.OtherName):
                if name.type_id == _OID_ICP_PESSOA_FISICA:
                    cpf = _extrair_cpf_oid(name.value, cpf_cn=cpf_cn)
                    if cpf:
                        fonte_cpf = "oid_2.16.76.1.3.1"
                        break
    except x509.ExtensionNotFound:
        pass
    except Exception:
        pass

    # Fallback 1: OID em SAN como GeneralName alternativo (alguns emissores)
    if cpf is None:
        try:
            san_ext = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            for name in san_ext.value:
                if isinstance(name, x509.RFC822Name):
                    # Alguns certificados embedam CPF no e-mail como cpf@cpf.br
                    m = _RE_CPF_11.search(name.value or "")
                    if m and len(set(m.group())) > 1:
                        cpf = m.group()
                        fonte_cpf = "san_rfc822"
                        break
        except Exception:
            pass

    # Fallback 2: CPF nos campos OU
    if cpf is None:
        cpf = _extrair_cpf_ou(ous)
        if cpf:
            fonte_cpf = "ou"

    identidade.cpf_certificado = cpf
    fonte["cpf"] = fonte_cpf

    # ── Extração de conselho (CRM/CRO) — OU ──────────────────────────────
    tipo_c, uf_c, num_c = _extrair_conselho(ous)
    if tipo_c and uf_c and num_c:
        identidade.conselho_tipo   = tipo_c
        identidade.conselho_uf     = uf_c
        identidade.conselho_numero = num_c
        fonte["conselho"] = "ou"
    else:
        fonte["conselho"] = "nao_encontrado"

    identidade.fonte_campos = fonte
    return identidade


# ---------------------------------------------------------------------------
# Resposta de binding completa
# ---------------------------------------------------------------------------


def binding_icp(
    cert_pem: str,
    conn=None,
    conselho_provider=None,
) -> dict:
    """
    Pipeline completo de binding ICP → identidade profissional.

    Passo 1: parsear certificado
    Passo 2: se conselho extraído → chamar Ticket 65
    Passo 3: se conselho ausente  → retornar necessita_conselho_manual

    Parâmetros
    ----------
    cert_pem           : str — certificado PEM bruto
    conn               : conexão SQLite (opcional — necessária para Ticket 65)
    conselho_provider  : ConselhoProvider (opcional — para testes)

    Retorna
    -------
    dict com:
      status            : "ok" | "nao_encontrado_cnes" | "nao_encontrado_conselho"
                          | "multiplo_vinculo" | "divergente"
                          | "necessita_conselho_manual" | "erro_parsing"
      icp               : ICPIdentidade.to_dict()
      identidade        : resultado do Ticket 65 (ou None)
      mensagem          : string amigável para UX (quando necessita_conselho_manual)
      extraido_em       : timestamp UTC
    """
    extraido_em = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Passo 1 — parsing
    icp = parsear_certificado_icp(cert_pem)

    if not icp.parseable:
        return {
            "status":      "erro_parsing",
            "icp":         icp.to_dict(),
            "identidade":  None,
            "mensagem":    f"Certificado inválido: {icp.erro}",
            "extraido_em": extraido_em,
        }

    # Passo 2 — conselho ausente → fallback manual
    if icp.precisa_conselho_manual():
        return {
            "status":      "necessita_conselho_manual",
            "icp":         icp.to_dict(),
            "identidade":  None,
            "mensagem":    "Informe CRM/CRO e UF para continuar.",
            "extraido_em": extraido_em,
        }

    # Passo 3 — pipeline Ticket 65
    if conn is None:
        # Sem conexão ao banco: retornar apenas o ICP parseado
        return {
            "status":      "icp_parseado",
            "icp":         icp.to_dict(),
            "identidade":  None,
            "mensagem":    None,
            "extraido_em": extraido_em,
        }

    from app.domain.identidade_prescritor import resolver_identidade_prescritor

    identidade = resolver_identidade_prescritor(
        conn=conn,
        cpf_certificado=icp.cpf_certificado or "",
        nome_certificado=icp.nome_certificado or "",
        conselho_numero=icp.conselho_numero,
        conselho_uf=icp.conselho_uf,
        conselho_provider=conselho_provider,
    )

    return {
        "status":      identidade["status"],
        "icp":         icp.to_dict(),
        "identidade":  identidade,
        "mensagem":    None,
        "extraido_em": extraido_em,
    }
