"""
pdf_pedido_exame.py
===================
Geração do PDF do pedido de exame no formato institucional PicSaúde.

FORMATO
-------
A4 portrait (210 × 297 mm), margens 20 mm.

BLOCOS DO DOCUMENTO
-------------------
1. Cabeçalho    — identidade PicSaúde + título + badge de prioridade
2. Prescritor   — nome, CNS
3. Paciente     — nome, CPF mascarado
4. Indicação    — indicação clínica (se houver)
5. Exames       — lista de exames solicitados (nome, código TUSS/SIGTAP, qtd)
6. Documento    — protocolo, data emissão, validade, hash SHA-256
7. Assinatura   — linha física para prescrição em papel
8. Rodapé       — PicSaúde, protocolo

PALETA (compartilhada com pdf_prescricao.py)
-------------------------------------------
Navy     #1a2e44   — cabeçalho, títulos de seção
Green    #2e7d32   — nomes dos exames
Orange   #e65100   — prioridade urgentíssimo
Amber    #f57f17   — prioridade urgente
Slate    #546e7a   — prioridade rotina, badge físico
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
GREY_BG   = colors.HexColor("#eceff1")
WHITE     = colors.white
BLACK     = colors.black
TEAL      = colors.HexColor("#00695c")


# ---------------------------------------------------------------------------
# Badge por prioridade
# ---------------------------------------------------------------------------

_BADGE_PRIORIDADE: dict[str, tuple[str, object]] = {
    "rotina":        ("PEDIDO DE EXAMES — ROTINA",          SLATE),
    "urgente":       ("PEDIDO DE EXAMES — URGENTE",         AMBER),
    "urgentissimo":  ("PEDIDO DE EXAMES — URGENTÍSSIMO",    ORANGE),
    "fisico":        ("PEDIDO DE EXAMES — FÍSICO (PAPEL)",  SLATE),
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
                        textColor=GREEN, leading=14),
        "detalhe_exame": s("detalhe_exame", fontName="Helvetica", fontSize=9,
                           textColor=colors.HexColor("#212121"), leading=13, leftIndent=8),
        "hash_text": s("hash_text", fontName="Courier", fontSize=7.5,
                       textColor=colors.HexColor("#424242"), leading=11),
        "rodape": s("rodape", fontName="Helvetica", fontSize=7.5,
                    textColor=colors.HexColor("#757575"), alignment=TA_CENTER, leading=11),
        "assinatura_label": s("assinatura_label", fontName="Helvetica", fontSize=8,
                              textColor=colors.HexColor("#616161"), alignment=TA_CENTER, leading=12),
        "indicacao": s("indicacao", fontName="Helvetica-Oblique", fontSize=9,
                       textColor=colors.HexColor("#37474f"), leading=13),
    }


# ---------------------------------------------------------------------------
# Blocos reutilizáveis
# ---------------------------------------------------------------------------

def _bloco_cabecalho(styles: dict, prioridade: str, tipo_emissao: str, page_width: float) -> Table:
    chave = tipo_emissao if tipo_emissao == "fisico" else prioridade
    label_badge, cor_badge = _BADGE_PRIORIDADE.get(chave, ("PEDIDO DE EXAMES", SLATE))

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


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf_pedido_exame(
    *,
    protocolo:         str,
    status:            str,
    tipo_emissao:      str,
    prioridade:        str,
    indicacao_clinica: Optional[str],
    assinatura_hash:   Optional[str],
    data_emissao:      str,
    data_validade:     Optional[str],
    # prescritor
    nome_prescritor:   str,
    cns_prescritor:    str,
    # paciente
    nome_paciente:     str,
    cpf_paciente:      str,
    # itens
    itens: list,   # list[dict]: nome_exame, codigo_tuss, codigo_sigtap, quantidade, status_item
) -> bytes:
    """
    Gera o PDF do pedido de exame e retorna os bytes.

    itens: lista de dicts com chaves nome_exame, codigo_tuss, codigo_sigtap, quantidade, status_item
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
        title=f"Pedido de Exame — {protocolo[:8].upper()}",
        author="PicSaúde",
        subject="Pedido de exame digital",
    )

    page_w = A4[0] - 2 * margin
    st = _build_styles()
    story = []

    # 1. Cabeçalho
    story.append(_bloco_cabecalho(st, prioridade, tipo_emissao, page_w))
    story.append(Spacer(1, 5 * mm))

    # 2. Prescritor
    story.append(_titulo_secao("Prescritor", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_prescritor or "—", st, page_w))
    story.append(_linha_lv("CNS",  cns_prescritor  or "—", st, page_w))
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

    # 4. Indicação clínica (se houver)
    if indicacao_clinica and indicacao_clinica.strip():
        story.append(_titulo_secao("Indicação clínica", st, page_w))
        story.append(Spacer(1, 1.5 * mm))
        story.append(Paragraph(indicacao_clinica.strip(), st["indicacao"]))
        story.append(Spacer(1, 4 * mm))

    # 5. Exames solicitados
    story.append(_titulo_secao("Exames solicitados", st, page_w))
    story.append(Spacer(1, 2 * mm))

    for idx, item in enumerate(itens, start=1):
        nome   = (item.get("nome_exame") or "").upper()
        tuss   = item.get("codigo_tuss") or None
        sigtap = item.get("codigo_sigtap") or None
        qtd    = item.get("quantidade", 1)

        titulo_exame = f"{idx}. {nome}"
        story.append(Paragraph(titulo_exame, st["nome_exame"]))

        codigos = []
        if tuss:
            codigos.append(f"TUSS: {tuss}")
        if sigtap:
            codigos.append(f"SIGTAP: {sigtap}")

        detalhes = []
        if codigos:
            detalhes.append(f"Código: {' | '.join(codigos)}")
        if qtd and qtd > 1:
            detalhes.append(f"Quantidade: {qtd}")

        if detalhes:
            story.append(Paragraph("  ".join(detalhes), st["detalhe_exame"]))

        story.append(Spacer(1, 2.5 * mm))

    # 6. Identificação do documento
    story.append(_titulo_secao("Identificação do documento", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Protocolo",      protocolo,             st, page_w))
    story.append(_linha_lv("Data de emissão", _fmt_data(data_emissao), st, page_w))
    if data_validade:
        story.append(_linha_lv("Validade",   _fmt_data(data_validade), st, page_w))
    story.append(_linha_lv("Prioridade",     prioridade.upper(),    st, page_w))
    story.append(_linha_lv("Status",         status,                st, page_w))

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

    # Caixa informativa de validade
    validade_texto = (
        f"Pedido válido até {_fmt_data(data_validade)}. "
        "Apresentar ao prestador de exames dentro do prazo de validade."
        if data_validade
        else "Verificar prazo de validade com o prescritor."
    )
    cor_box = ORANGE if prioridade == "urgentissimo" else (AMBER if prioridade == "urgente" else SLATE)
    caixa_tbl = Table(
        [[Paragraph(validade_texto, st["valor"])]],
        colWidths=[page_w],
    )
    caixa_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("BOX",           (0, 0), (-1, -1), 1.5, cor_box),
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
                f"<b>{nome_prescritor or 'Prescritor'}</b><br/>CNS {cns_prescritor or ''}",
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
