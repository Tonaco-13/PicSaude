"""
pdf_laudo.py
============
Geração do PDF do laudo clínico no formato institucional PicSaúde.

FORMATO
-------
A4 portrait (210 × 297 mm), margens 20 mm.

BLOCOS DO DOCUMENTO
-------------------
1. Cabeçalho    — identidade PicSaúde + título + badge de status
2. Autor        — nome e CNS do responsável técnico (patologista, bioquímico, etc.)
3. Paciente     — nome, CPF mascarado
4. Pedido       — protocolo do pedido de exame vinculado (se houver)
5. Resultados   — itens do laudo (nome, conclusão, resultado resumido, valor ref.)
6. Documento    — protocolo, data emissão, validade, hash SHA-256
7. Assinatura   — área física de assinatura do responsável técnico
8. Rodapé       — PicSaúde, protocolo

PALETA (compartilhada com pdf_prescricao.py e pdf_pedido_exame.py)
-------------------------------------------------------------------
Navy     #1a2e44   — cabeçalho, títulos de seção
Green    #2e7d32   — conclusão normal / laudo liberado
Orange   #e65100   — conclusão alterado / urgência
Amber    #f57f17   — conclusão indeterminado
Slate    #546e7a   — laudo físico, conclusão inconclusivo
Teal     #00695c   — nome do exame
Grey bg  #eceff1   — fundo de seção
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Paleta de cores
# ---------------------------------------------------------------------------

NAVY      = colors.HexColor("#1a2e44")
GREEN     = colors.HexColor("#2e7d32")
ORANGE    = colors.HexColor("#e65100")
AMBER     = colors.HexColor("#f57f17")
SLATE     = colors.HexColor("#546e7a")
TEAL      = colors.HexColor("#00695c")
GREY_BG   = colors.HexColor("#eceff1")
WHITE     = colors.white
BLACK     = colors.black


# ---------------------------------------------------------------------------
# Badge por status do laudo
# ---------------------------------------------------------------------------

_BADGE_STATUS: dict[str, tuple[str, object]] = {
    "em_producao":        ("LAUDO — EM PRODUÇÃO",      SLATE),
    "assinado":           ("LAUDO ASSINADO",            TEAL),
    "liberado":           ("LAUDO LIBERADO",            GREEN),
    "ciencia_paciente":   ("LAUDO — CIÊNCIA PACIENTE",  GREEN),
    "ciencia_prescritor": ("LAUDO — CIÊNCIA CLÍNICA",   GREEN),
    "encerrado":          ("LAUDO ENCERRADO",           NAVY),
    "cancelado":          ("LAUDO CANCELADO",           ORANGE),
    "expirado":           ("LAUDO EXPIRADO",            ORANGE),
    "encerrado_fisico":   ("LAUDO — FÍSICO (PAPEL)",    SLATE),
}

_COR_CONCLUSAO: dict[str, object] = {
    "normal":        GREEN,
    "alterado":      ORANGE,
    "indeterminado": AMBER,
    "inconclusivo":  SLATE,
}


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _fmt_cpf(cpf: str) -> str:
    c = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(c) != 11:
        return cpf or "—"
    return f"{c[:3]}.***.***.{c[9:]}"


def _fmt_data(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y às %H:%M") if "T" in iso else dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or "—"


def _truncar_hash(h: str | None) -> str:
    if not h:
        return "não gerado"
    if len(h) <= 28:
        return h
    return f"{h[:16]}...{h[-8:]}"


def _hex_cor(color_obj) -> str:
    return color_obj.hexval().lstrip("#")


# ---------------------------------------------------------------------------
# Estilos de parágrafo
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    def s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name=name, **kw)

    return {
        "titulo": s("titulo", fontName="Helvetica-Bold", fontSize=16,
                    textColor=WHITE, alignment=TA_LEFT, leading=20),
        "subtitulo_header": s("subtitulo_header", fontName="Helvetica", fontSize=9,
                              textColor=colors.HexColor("#cfd8dc"), alignment=TA_LEFT, leading=12),
        "tipo_header": s("tipo_header", fontName="Helvetica-Bold", fontSize=9,
                         textColor=WHITE, alignment=TA_RIGHT, leading=12),
        "secao": s("secao", fontName="Helvetica-Bold", fontSize=8, textColor=NAVY,
                   alignment=TA_LEFT, spaceBefore=2, spaceAfter=2),
        "label": s("label", fontName="Helvetica-Bold", fontSize=9,
                   textColor=NAVY, leading=13),
        "valor": s("valor", fontName="Helvetica", fontSize=9,
                   textColor=BLACK, leading=13),
        "nome_exame": s("nome_exame", fontName="Helvetica-Bold", fontSize=10,
                        textColor=TEAL, leading=14),
        "conclusao_normal": s("conclusao_normal", fontName="Helvetica-Bold", fontSize=9,
                              textColor=GREEN, leading=13, leftIndent=8),
        "conclusao_alterado": s("conclusao_alterado", fontName="Helvetica-Bold", fontSize=9,
                                textColor=ORANGE, leading=13, leftIndent=8),
        "conclusao_indeterminado": s("conclusao_indeterminado", fontName="Helvetica-Bold", fontSize=9,
                                     textColor=AMBER, leading=13, leftIndent=8),
        "conclusao_inconclusivo": s("conclusao_inconclusivo", fontName="Helvetica-Bold", fontSize=9,
                                    textColor=SLATE, leading=13, leftIndent=8),
        "detalhe_item": s("detalhe_item", fontName="Helvetica", fontSize=9,
                          textColor=colors.HexColor("#212121"), leading=13, leftIndent=8),
        "hash_text": s("hash_text", fontName="Courier", fontSize=7.5,
                       textColor=colors.HexColor("#424242"), leading=11),
        "rodape": s("rodape", fontName="Helvetica", fontSize=7.5,
                    textColor=colors.HexColor("#757575"), alignment=TA_CENTER, leading=11),
        "assinatura_label": s("assinatura_label", fontName="Helvetica", fontSize=8,
                              textColor=colors.HexColor("#616161"), alignment=TA_CENTER, leading=12),
        "pedido_ref": s("pedido_ref", fontName="Helvetica-Oblique", fontSize=9,
                        textColor=colors.HexColor("#37474f"), leading=13),
    }


# ---------------------------------------------------------------------------
# Blocos reutilizáveis
# ---------------------------------------------------------------------------

def _bloco_cabecalho(styles: dict, status: str, tipo_emissao: str, page_width: float) -> Table:
    chave = "encerrado_fisico" if tipo_emissao == "fisico" else status
    label_badge, cor_badge = _BADGE_STATUS.get(chave, ("LAUDO CLÍNICO", NAVY))

    esq = [
        Paragraph("PicSaúde", styles["titulo"]),
        Paragraph("Plataforma de Custódia Sanitária Digital", styles["subtitulo_header"]),
    ]
    dir_ = [
        Paragraph(
            f'<font color="#{_hex_cor(cor_badge)}" size="8"><b>{label_badge}</b></font>',
            styles["tipo_header"],
        ),
    ]

    tbl = Table([[esq, dir_]], colWidths=[page_width * 0.55, page_width * 0.45])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (0, -1), 14),
        ("RIGHTPADDING",  (1, 0), (1, -1), 14),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _titulo_secao(texto: str, styles: dict, page_width: float) -> Table:
    tbl = Table([[Paragraph(texto.upper(), styles["secao"])]], colWidths=[page_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GREY_BG),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, NAVY),
    ]))
    return tbl


def _linha_lv(label: str, valor: str, styles: dict, page_width: float) -> Table:
    tbl = Table(
        [[Paragraph(label, styles["label"]), Paragraph(valor or "—", styles["valor"])]],
        colWidths=[page_width * 0.28, page_width * 0.72],
    )
    tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _paragrafo_conclusao(conclusao: str, styles: dict) -> Paragraph:
    """Retorna parágrafo de conclusão com cor adequada."""
    mapa_estilo = {
        "normal":        "conclusao_normal",
        "alterado":      "conclusao_alterado",
        "indeterminado": "conclusao_indeterminado",
        "inconclusivo":  "conclusao_inconclusivo",
    }
    estilo = mapa_estilo.get(conclusao, "detalhe_item")
    texto  = f"Conclusão: {conclusao.upper()}"
    return Paragraph(texto, styles[estilo])


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf_laudo(
    *,
    protocolo:        str,
    status:           str,
    tipo_emissao:     str,
    assinatura_hash:  Optional[str],
    data_emissao:     str,
    data_validade:    Optional[str],
    # autor (responsável técnico)
    nome_autor:       str,
    cns_autor:        str,
    # paciente
    nome_paciente:    str,
    cpf_paciente:     str,
    # pedido vinculado (opcional)
    pedido_protocolo: Optional[str],
    # itens
    itens: list,   # list[dict]: nome_exame, codigo_tuss, resultado_resumo,
                   #              conclusao, valor_referencia, status_item
) -> bytes:
    """
    Gera o PDF do laudo clínico e retorna os bytes.

    itens: lista de dicts com chaves:
        nome_exame, codigo_tuss, resultado_resumo, conclusao, valor_referencia, status_item
    """
    buf = io.BytesIO()
    margin = 20 * mm
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title=f"Laudo Clínico — {protocolo[:8].upper()}",
        author="PicSaúde",
        subject="Laudo clínico digital",
    )

    page_w = A4[0] - 2 * margin
    st = _build_styles()
    story = []

    # 1. Cabeçalho
    story.append(_bloco_cabecalho(st, status, tipo_emissao, page_w))
    story.append(Spacer(1, 5 * mm))

    # 2. Responsável técnico (autor)
    story.append(_titulo_secao("Responsável técnico", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_autor or "—", st, page_w))
    story.append(_linha_lv("CNS",  cns_autor  or "—", st, page_w))
    story.append(Spacer(1, 4 * mm))

    # 3. Paciente
    story.append(_titulo_secao("Paciente", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_paciente or "—", st, page_w))
    cpf_exibir = (
        "Não identificado"
        if cpf_paciente == "00000000000"
        else _fmt_cpf(cpf_paciente)
    )
    story.append(_linha_lv("CPF", cpf_exibir, st, page_w))
    story.append(Spacer(1, 4 * mm))

    # 4. Pedido vinculado (se houver)
    if pedido_protocolo and pedido_protocolo.strip():
        story.append(_titulo_secao("Pedido de exame vinculado", st, page_w))
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(f"Protocolo: {pedido_protocolo}", st["pedido_ref"]))
        story.append(Spacer(1, 4 * mm))

    # 5. Resultados dos exames
    story.append(_titulo_secao("Resultados", st, page_w))
    story.append(Spacer(1, 2 * mm))

    for idx, item in enumerate(itens, start=1):
        nome            = (item.get("nome_exame") or "").upper()
        codigo_tuss     = item.get("codigo_tuss") or None
        resultado_resumo = item.get("resultado_resumo") or None
        conclusao       = item.get("conclusao") or None
        valor_referencia = item.get("valor_referencia") or None

        story.append(Paragraph(f"{idx}. {nome}", st["nome_exame"]))

        if codigo_tuss:
            story.append(Paragraph(f"TUSS: {codigo_tuss}", st["detalhe_item"]))

        if conclusao:
            story.append(_paragrafo_conclusao(conclusao, st))

        if resultado_resumo:
            story.append(Paragraph(f"Resultado: {resultado_resumo}", st["detalhe_item"]))

        if valor_referencia:
            story.append(Paragraph(f"Valor de referência: {valor_referencia}", st["detalhe_item"]))

        story.append(Spacer(1, 3 * mm))

    # 6. Identificação do documento
    story.append(_titulo_secao("Identificação do documento", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Protocolo",       protocolo,               st, page_w))
    story.append(_linha_lv("Data de emissão", _fmt_data(data_emissao), st, page_w))
    if data_validade:
        story.append(_linha_lv("Validade",    _fmt_data(data_validade), st, page_w))
    story.append(_linha_lv("Status",          status,                  st, page_w))

    story.append(Spacer(1, 1 * mm))
    hash_tbl = Table(
        [[Paragraph("<b>Hash SHA-256</b>", st["label"]),
          Paragraph(_truncar_hash(assinatura_hash), st["hash_text"])]],
        colWidths=[page_w * 0.28, page_w * 0.72],
    )
    hash_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(hash_tbl)
    story.append(Spacer(1, 4 * mm))

    # Caixa informativa de custódia
    caixa_texto = (
        "Laudo emitido pela plataforma PicSaúde. "
        "A autenticidade pode ser verificada pelo protocolo acima."
    )
    caixa_tbl = Table(
        [[Paragraph(caixa_texto, st["valor"])]],
        colWidths=[page_w],
    )
    caixa_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("BOX",           (0, 0), (-1, -1), 1.5, TEAL),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(caixa_tbl)
    story.append(Spacer(1, 6 * mm))

    # 7. Área de assinatura
    story.append(HRFlowable(width=page_w, thickness=0.5, color=NAVY))
    story.append(Spacer(1, 15 * mm))
    linha_assinatura = Table(
        [[
            Paragraph("_" * 45, st["assinatura_label"]),
            Paragraph(
                f"<b>{nome_autor or 'Responsável Técnico'}</b><br/>CNS {cns_autor or ''}",
                st["assinatura_label"],
            ),
        ]],
        colWidths=[page_w * 0.5, page_w * 0.5],
    )
    linha_assinatura.setStyle(TableStyle([
        ("ALIGN",  (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(linha_assinatura)
    story.append(Spacer(1, 3 * mm))

    # 8. Rodapé
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=page_w, thickness=0.3, color=colors.HexColor("#bdbdbd")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Documento gerado por PicSaúde — Plataforma de Custódia Sanitária Digital"
        f"&nbsp;&nbsp;|&nbsp;&nbsp;Protocolo: {protocolo}",
        st["rodape"],
    ))

    doc.build(story)
    return buf.getvalue()
