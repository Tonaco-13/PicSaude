"""Ticket 21 — Testes unitários do módulo de assinatura PAdES.

Não exigem PostgreSQL — testam apenas a função `assinar_pdf_icp()`
contra um PDF mínimo gerado em memória e um certificado de teste
autogerado.
"""
from __future__ import annotations

import datetime
import warnings

import pytest

# pyHanko + urllib3 emitem warnings sobre LibreSSL no macOS — ruído.
warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")


# Helper compartilhado: PDF mínimo via ReportLab (mais leve que a função
# completa de receituário — esses testes focam na assinatura, não no layout).
def _pdf_minimo() -> bytes:
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, "Receituario teste — Ticket 21")
    c.showPage()
    c.save()
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Assinatura básica
# ---------------------------------------------------------------------------

def test_assinar_pdf_basico():
    from app.domain.pdf_assinatura import (
        assinar_pdf_icp, MetadataAssinatura, pdf_tem_assinatura,
    )
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste()
    pdf = _pdf_minimo()
    meta = MetadataAssinatura(
        nome_prescritor=cert.nome,
        cpf_prescritor=cert.cpf,
    )

    assinado = assinar_pdf_icp(pdf, cert.pfx_bytes, cert.senha, meta)

    # PDF assinado é maior que o original (carrega CMS embutido)
    assert len(assinado) > len(pdf)
    # Header PDF preservado
    assert assinado[:4] == b"%PDF"
    # pyHanko detecta a assinatura embutida
    assert pdf_tem_assinatura(assinado) is True


# ---------------------------------------------------------------------------
# 2. Assinatura invisível (sem selo visual)
# ---------------------------------------------------------------------------

def test_assinar_pdf_invisivel():
    from app.domain.pdf_assinatura import (
        assinar_pdf_icp, MetadataAssinatura, pdf_tem_assinatura,
    )
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste()
    pdf = _pdf_minimo()
    meta = MetadataAssinatura(nome_prescritor=cert.nome, cpf_prescritor=cert.cpf)

    assinado = assinar_pdf_icp(
        pdf, cert.pfx_bytes, cert.senha, meta,
        com_selo_visual=False,
    )
    assert pdf_tem_assinatura(assinado) is True


# ---------------------------------------------------------------------------
# 3. Senha incorreta levanta SenhaPfxInvalida
# ---------------------------------------------------------------------------

def test_assinar_pdf_senha_invalida():
    from app.domain.pdf_assinatura import (
        assinar_pdf_icp, MetadataAssinatura, SenhaPfxInvalida,
    )
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste(senha="senha_correta")
    pdf = _pdf_minimo()
    meta = MetadataAssinatura(nome_prescritor=cert.nome, cpf_prescritor=cert.cpf)

    with pytest.raises(SenhaPfxInvalida):
        assinar_pdf_icp(pdf, cert.pfx_bytes, "senha_errada", meta)


# ---------------------------------------------------------------------------
# 4. Certificado sem KeyUsage.digitalSignature é rejeitado
# ---------------------------------------------------------------------------

def test_assinar_pdf_sem_keyusage_digital_signature():
    from app.domain.pdf_assinatura import (
        assinar_pdf_icp, MetadataAssinatura, CertificadoSemKeyUsage,
    )
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste(com_keyusage_digital_signature=False)
    pdf = _pdf_minimo()
    meta = MetadataAssinatura(nome_prescritor=cert.nome, cpf_prescritor=cert.cpf)

    with pytest.raises(CertificadoSemKeyUsage):
        assinar_pdf_icp(pdf, cert.pfx_bytes, cert.senha, meta)


# ---------------------------------------------------------------------------
# 5. Selo visual contém os campos esperados (verificação direta de helper)
# ---------------------------------------------------------------------------

def test_texto_selo_visual_contem_campos_obrigatorios():
    from app.domain.pdf_assinatura import (
        MetadataAssinatura, _texto_selo_visual,
    )

    meta = MetadataAssinatura(
        nome_prescritor="DR FULANO DE TAL",
        cpf_prescritor="83086439149",
        crm_prescritor="22847",
        uf_prescritor="PE",
    )
    agora = datetime.datetime(2026, 4, 29, 15, 45, 32, tzinfo=datetime.timezone.utc)
    texto = _texto_selo_visual(meta, agora)

    assert "DR FULANO DE TAL" in texto
    assert "830.864.391-49" in texto       # CPF formatado
    assert "CRM-PE 22847" in texto
    assert "29/04/2026" in texto
    assert "ICP-Brasil" in texto


# ---------------------------------------------------------------------------
# 6. Cadeia/certificado embutido — validar via pyhanko reader
# ---------------------------------------------------------------------------

def test_pdf_assinado_traz_certificado_embutido():
    """O PDF assinado deve conter o certificado do signatário embutido
    (CMS SignerInfo + certificate field)."""
    import io
    from pyhanko.pdf_utils.reader import PdfFileReader

    from app.domain.pdf_assinatura import assinar_pdf_icp, MetadataAssinatura
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste()
    pdf = _pdf_minimo()
    meta = MetadataAssinatura(nome_prescritor=cert.nome, cpf_prescritor=cert.cpf)

    assinado = assinar_pdf_icp(pdf, cert.pfx_bytes, cert.senha, meta)

    reader = PdfFileReader(io.BytesIO(assinado))
    sigs = reader.embedded_signatures
    assert len(sigs) == 1

    # O certificado deve estar no SignedData CMS embutido.
    sig = sigs[0]
    signed_data = sig.signed_data
    # SignedData tem campo 'certificates' com lista de cert_choices
    embedded_certs = signed_data["certificates"]
    assert len(embedded_certs) >= 1, \
        "PDF assinado deve embutir ao menos o certificado do signatário"


# ---------------------------------------------------------------------------
# 7. Carregar .pfx — sucesso retorna PfxCarregado
# ---------------------------------------------------------------------------

def test_carregar_pfx_retorna_pfx_carregado():
    from app.domain.pdf_assinatura import PfxCarregado, carregar_pfx
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste()
    carregado = carregar_pfx(cert.pfx_bytes, cert.senha)

    assert isinstance(carregado, PfxCarregado)
    assert carregado.chave_privada is not None
    assert carregado.certificado is not None


# ---------------------------------------------------------------------------
# 8. Certificado expirado: módulo NÃO bloqueia (decisão é do endpoint)
# ---------------------------------------------------------------------------

def test_carregar_pfx_certificado_expirado_nao_bloqueia():
    """O módulo de assinatura não rejeita certificados expirados —
    a decisão pertence à camada do endpoint (que pode emitir alerta).
    Isso permite reassinar PDFs históricos com cert expirado se preciso.
    """
    from app.domain.pdf_assinatura import carregar_pfx
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    # Certificado emitido para 1 dia, há 365 dias atrás → expirado há ~364
    no_passado = (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=365)
    )
    cert = gerar_certificado_teste(
        validade_dias=1,
        valido_de=no_passado,
    )
    # Não levanta — apenas carrega.
    resultado = carregar_pfx(cert.pfx_bytes, cert.senha)
    assert resultado.certificado is not None


# ---------------------------------------------------------------------------
# 9. Pdf_tem_assinatura: detecta presença e ausência
# ---------------------------------------------------------------------------

def test_pdf_tem_assinatura_negativo_para_pdf_sem_assinatura():
    from app.domain.pdf_assinatura import pdf_tem_assinatura

    pdf = _pdf_minimo()
    assert pdf_tem_assinatura(pdf) is False


def test_pdf_tem_assinatura_robusto_a_bytes_invalidos():
    from app.domain.pdf_assinatura import pdf_tem_assinatura

    # bytes não-PDF não devem crashar — apenas retornar False
    assert pdf_tem_assinatura(b"nao sou um pdf") is False
    assert pdf_tem_assinatura(b"") is False


# ---------------------------------------------------------------------------
# 10. Assinatura sobre PDF de receituário real
# ---------------------------------------------------------------------------

def test_assinar_pdf_receituario_real():
    """Smoke test que combina o gerador de PDF de receituário (T17) com
    a função de assinatura (T21)."""
    from app.domain.pdf_assinatura import (
        assinar_pdf_icp, MetadataAssinatura, pdf_tem_assinatura,
    )
    from app.domain.pdf_receituario import gerar_pdf_receituario
    from tests.fixtures.certificado_teste import gerar_certificado_teste

    cert = gerar_certificado_teste(nome="DR FULANO DE TAL", cpf="11122233344")

    pdf_base = gerar_pdf_receituario(
        tipo_receituario="notificacao_receita_b",
        grupo_nome="Notificação de Receita B",
        numeracao_sncr="STUB-2026-NRB-000000005",
        status="numerado_stub",
        vias=2,
        retencao_farmacia=True,
        adapter_usado="stub",
        protocolo="proto-test-21",
        assinatura_hash="a" * 64,
        assinatura_modo="icp_brasil_local",
        data_emissao="2026-04-29T12:00:00",
        data_validade="2026-05-29T12:00:00",
        indicacao_clinica="ansiedade",
        nome_prescritor="DR FULANO DE TAL",
        cns_prescritor="123456789012345",
        nome_paciente="JOAO DA SILVA",
        cpf_paciente="12345678901",
        itens=[{
            "nome_medicamento": "DIAZEPAM",
            "concentracao": "10mg",
            "quantidade": 30,
            "unidade_quantidade": "comprimidos",
            "forma_farmaceutica": "1 cx c/30",
            "posologia": "1 cp 8/8h por 7 dias",
            "classe_controle": "B1",
        }],
    )
    meta = MetadataAssinatura(
        nome_prescritor="DR FULANO DE TAL",
        cpf_prescritor="11122233344",
        crm_prescritor="22847",
        uf_prescritor="PE",
    )
    assinado = assinar_pdf_icp(pdf_base, cert.pfx_bytes, cert.senha, meta)
    assert pdf_tem_assinatura(assinado) is True
    assert assinado[:4] == b"%PDF"
    # Sanity: o PDF assinado é > base + ~5KB (CMS PKCS#7)
    assert len(assinado) >= len(pdf_base) + 1500
