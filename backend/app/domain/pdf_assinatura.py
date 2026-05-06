"""
pdf_assinatura.py
=================
Assinatura digital PAdES-B em PDF — Ticket 21.

Propósito
---------
Embute assinatura ICP-Brasil dentro do PDF do receituário no padrão
PAdES-B (PDF Advanced Electronic Signatures, baseline). O resultado:

  - É um PDF auto-contido com assinatura criptográfica embutida
  - Validável OFFLINE pelo Adobe Reader, pyHanko, qualquer ferramenta PAdES
  - Inclui certificado emissor + cadeia CA do .pfx
  - Tem selo visual no rodapé (nome, CPF, data, "ICP-Brasil")

NÃO inclui (futuro)
-------------------
- PAdES-T (timestamp via TSA): exige integração com servidor de timestamp
- PAdES-LT/LTA (long-term + revogação embutida): exige OCSP/CRL
- Validação online de revogação (CRL/OCSP)

Distinção das duas assinaturas do PicSaúde
------------------------------------------
1. Assinatura do PAYLOAD CANÔNICO (T66/T68) — valida o ato clínico,
   opera sobre `documento_canonico.py`. Persiste em `prescricao_assinatura`.
2. Assinatura PAdES do PDF (este módulo) — valida o documento
   regulatório entregue à farmácia. Persiste como evento no ledger.

Ambas usam o mesmo certificado ICP-Brasil, mas assinam objetos
diferentes.

Compatibilidade
---------------
Aceita certificados ICP-Brasil A1 (.pfx/.p12). Tipos A3 (token USB)
exigem PKCS#11 — fora do escopo desta fase.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import fields, signers
from pyhanko.sign.signers.pdf_signer import PdfSigner, PdfSignatureMetadata


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MetadataAssinatura:
    """Metadados aplicados ao selo visual e ao dicionário de assinatura.

    Estes campos NÃO substituem os dados do certificado — pyHanko vincula
    automaticamente o subject do certificado à assinatura. Estes valores
    aparecem no selo visual (texto humano) e no dicionário /SigningTime,
    /Reason, /Location do PDF.
    """
    nome_prescritor:    str
    cpf_prescritor:     str
    crm_prescritor:     Optional[str] = None
    uf_prescritor:      Optional[str] = None
    razao:              str = "Prescrição médica digital"
    localizacao:        Optional[str] = None
    contato:            Optional[str] = None


# ---------------------------------------------------------------------------
# Erros de domínio
# ---------------------------------------------------------------------------

class AssinaturaPdfError(Exception):
    """Erro genérico de assinatura PAdES."""


class SenhaPfxInvalida(AssinaturaPdfError):
    """Senha do .pfx não desbloqueia o arquivo."""


class CertificadoSemKeyUsage(AssinaturaPdfError):
    """Certificado não tem `KeyUsage.digitalSignature`."""


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _fmt_cpf_visual(cpf: str) -> str:
    """Formata CPF como 000.000.000-00 para o selo visual."""
    c = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(c) != 11:
        return cpf or ""
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"


def _texto_selo_visual(meta: MetadataAssinatura, agora: datetime) -> str:
    """Texto exibido no selo visual de assinatura.

    pyHanko suporta texto multilinha via SigStampStyle/TextStampStyle.
    Mantemos o conteúdo curto para caber em ~25mm de altura.
    """
    cpf_fmt = _fmt_cpf_visual(meta.cpf_prescritor)
    linhas: list[str] = [
        f"Assinado digitalmente por:",
        f"{meta.nome_prescritor}",
        f"CPF: {cpf_fmt}",
    ]
    if meta.crm_prescritor and meta.uf_prescritor:
        linhas.append(f"CRM-{meta.uf_prescritor} {meta.crm_prescritor}")
    linhas.append(agora.astimezone(timezone.utc).strftime("Data: %d/%m/%Y %H:%M:%S UTC"))
    linhas.append("Certificado ICP-Brasil")
    return "\n".join(linhas)


def _validar_keyusage_digital_signature(cert) -> None:
    """Levanta CertificadoSemKeyUsage se o certificado não tem
    KeyUsage.digitalSignature ativo. Aceita certificados sem extensão
    KeyUsage (alguns ICP-Brasil legados não declaram explicitamente).
    """
    from cryptography.x509 import ExtensionNotFound
    from cryptography.x509.oid import ExtensionOID

    try:
        ku_ext = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
    except ExtensionNotFound:
        # Certificado sem KeyUsage — aceitamos como compatibilidade com
        # ICP-Brasil legados. Anotação para auditoria.
        return
    ku = ku_ext.value
    if not ku.digital_signature:
        raise CertificadoSemKeyUsage(
            "Certificado não possui KeyUsage.digitalSignature"
        )


# ---------------------------------------------------------------------------
# Carregamento do .pfx
# ---------------------------------------------------------------------------

@dataclass
class PfxCarregado:
    """Resultado do carregamento de um .pfx — somente memória, descartar
    após uso.
    """
    chave_privada: object   # cryptography PrivateKey
    certificado: object     # cryptography Certificate
    cadeia: list            # lista de Certificate (CAs intermediárias)


def carregar_pfx(pfx_bytes: bytes, senha: str) -> PfxCarregado:
    """Carrega um .pfx/.p12 com a senha fornecida.

    Levanta SenhaPfxInvalida se a senha estiver errada.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12

    try:
        chave, cert, cadeia = pkcs12.load_key_and_certificates(
            pfx_bytes, senha.encode("utf-8") if senha else None,
        )
    except Exception as exc:
        # cryptography levanta ValueError quando senha errada / arquivo corrompido.
        raise SenhaPfxInvalida(
            "Senha do certificado inválida ou .pfx corrompido"
        ) from exc

    if cert is None or chave is None:
        raise AssinaturaPdfError(
            "Arquivo .pfx não contém chave privada e certificado"
        )

    _validar_keyusage_digital_signature(cert)

    return PfxCarregado(
        chave_privada=chave,
        certificado=cert,
        cadeia=list(cadeia or []),
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def assinar_pdf_icp(
    pdf_bytes: bytes,
    pfx_bytes: bytes,
    senha: str,
    metadata: MetadataAssinatura,
    *,
    nome_campo: str = "Sig1",
    com_selo_visual: bool = True,
    pagina_selo: int = 0,
    posicao_selo_mm: tuple[float, float, float, float] = (20.0, 8.0, 110.0, 33.0),
    agora: Optional[datetime] = None,
) -> bytes:
    """Assina um PDF com certificado ICP-Brasil A1 no padrão PAdES-B.

    Parâmetros
    ----------
    pdf_bytes : bytes
        PDF original (gerado por `pdf_receituario.gerar_pdf_receituario`).
    pfx_bytes : bytes
        Arquivo .pfx/.p12 do prescritor.
    senha : str
        Senha do .pfx.
    metadata : MetadataAssinatura
        Dados para o selo visual e dicionário de assinatura.
    nome_campo : str
        Nome interno do campo de assinatura (default "Sig1").
    com_selo_visual : bool
        Se True, embute selo visual no rodapé. False = assinatura invisível.
    pagina_selo : int
        Índice da página onde o selo aparece (0 = primeira).
    posicao_selo_mm : (x, y, w, h) em mm
        Posição e tamanho do selo. Default: 20mm da esquerda, 8mm do bottom,
        110mm de largura, 25mm de altura. PDF coordinate system tem y=0 no
        bottom; pyHanko usa pixels (1mm ≈ 2.835pt).
    agora : datetime | None
        Timestamp da assinatura. Default: now() UTC.

    Retorna
    -------
    bytes do PDF assinado, com PAdES-B embutido. Validável offline no
    Adobe Reader e via `pyhanko.sign.validation`.

    Levanta
    -------
    SenhaPfxInvalida          : senha errada
    CertificadoSemKeyUsage    : cert sem KeyUsage.digitalSignature
    AssinaturaPdfError        : outras falhas
    """
    if agora is None:
        agora = datetime.now(timezone.utc)

    # 1. Carregar .pfx (valida senha + KeyUsage)
    carregado = carregar_pfx(pfx_bytes, senha)

    # 2. Construir signer pyHanko via PKCS12 in-memory.
    #    `load_pkcs12_data` aceita bytes (load_pkcs12 espera path).
    #    other_certs é obrigatório nesta versão do pyHanko — passamos
    #    iterável vazio. A cadeia CA do .pfx é absorvida automaticamente
    #    pelo loader.
    signer = signers.SimpleSigner.load_pkcs12_data(
        pfx_bytes,
        other_certs=(),
        passphrase=senha.encode("utf-8") if senha else None,
    )
    if signer is None:
        # Defensivo — load_pkcs12 deveria ter levantado, mas se retornar
        # None silenciosamente, evitamos NoneType crash adiante.
        raise AssinaturaPdfError(
            "Falha ao construir SimpleSigner a partir do .pfx"
        )

    # 3. Preparar IncrementalPdfFileWriter com o PDF original
    pdf_in = io.BytesIO(pdf_bytes)
    writer = IncrementalPdfFileWriter(pdf_in)

    # 4. Configurar campo de assinatura — visível ou invisível
    if com_selo_visual:
        x_mm, y_mm, w_mm, h_mm = posicao_selo_mm
        # Conversão mm → pt (1mm = 2.834645669 pt)
        x_pt = x_mm * 2.834645669
        y_pt = y_mm * 2.834645669
        w_pt = w_mm * 2.834645669
        h_pt = h_mm * 2.834645669
        sig_field = fields.SigFieldSpec(
            sig_field_name=nome_campo,
            on_page=pagina_selo,
            box=(x_pt, y_pt, x_pt + w_pt, y_pt + h_pt),
        )
    else:
        sig_field = fields.SigFieldSpec(sig_field_name=nome_campo)
    fields.append_signature_field(writer, sig_field)

    # 5. Estilo de carimbo visual (texto livre simples — evita dependência de imagem).
    text_stamp_style = None
    if com_selo_visual:
        from pyhanko.stamp import TextStampStyle
        from pyhanko.pdf_utils.text import TextBoxStyle
        from pyhanko.pdf_utils import layout

        text_stamp_style = TextStampStyle(
            stamp_text=_texto_selo_visual(metadata, agora),
            text_box_style=TextBoxStyle(),
            border_width=0.5,
        )

    # 6. Metadados PAdES-B do PDF
    sig_meta = PdfSignatureMetadata(
        field_name=nome_campo,
        reason=metadata.razao,
        location=metadata.localizacao,
        contact_info=metadata.contato,
        # PAdES sem long-term info (LT/LTA fora do escopo desta fase).
        subfilter=fields.SigSeedSubFilter.PADES,
    )

    # 7. Assinar
    pdf_signer = PdfSigner(
        signature_meta=sig_meta,
        signer=signer,
        stamp_style=text_stamp_style,
    )

    out = io.BytesIO()
    pdf_signer.sign_pdf(writer, output=out)
    return out.getvalue()


# ---------------------------------------------------------------------------
# Validação (consumida pelos testes)
# ---------------------------------------------------------------------------

def pdf_tem_assinatura(pdf_bytes: bytes) -> bool:
    """True se o PDF contém pelo menos uma assinatura PAdES detectável.

    Usa pyHanko para inspecionar o documento. Não valida criptograficamente
    nem checa cadeia — apenas confirma a presença da entrada de assinatura.
    """
    from pyhanko.pdf_utils.reader import PdfFileReader
    try:
        r = PdfFileReader(io.BytesIO(pdf_bytes))
        return bool(r.embedded_signatures)
    except Exception:
        return False
