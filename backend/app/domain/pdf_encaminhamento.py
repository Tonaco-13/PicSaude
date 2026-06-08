"""
pdf_encaminhamento.py
=====================
Geração do PDF institucional do encaminhamento clínico.
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


NAVY    = colors.HexColor("#1a2e44")
TEAL    = colors.HexColor("#00695c")
SLATE   = colors.HexColor("#546e7a")
GREY_BG = colors.HexColor("#eceff1")
WHITE   = colors.white
BLACK   = colors.black


def _fmt_cpf(cpf: str) -> str:
    c = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(c) != 11:
        return cpf or "-"
    return f"{c[:3]}.***.***.{c[9:]}"


def _fmt_data(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y às %H:%M") if "T" in iso else dt.strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return iso


def _truncar_hash(h: str | None) -> str:
    if not h:
        return "não gerado"
    return h if len(h) <= 28 else f"{h[:16]}...{h[-8:]}"


def _styles() -> dict[str, ParagraphStyle]:
    def s(name: str, **kwargs) -> ParagraphStyle:
        return ParagraphStyle(name=name, **kwargs)

    return {
        "titulo": s("titulo", fontName="Helvetica-Bold", fontSize=16, textColor=WHITE, leading=20),
        "subtitulo": s("subtitulo", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#cfd8dc"), leading=12),
        "badge": s("badge", fontName="Helvetica-Bold", fontSize=9, textColor=WHITE, alignment=TA_RIGHT, leading=12),
        "secao": s("secao", fontName="Helvetica-Bold", fontSize=8, textColor=NAVY, leading=11),
        "label": s("label", fontName="Helvetica-Bold", fontSize=9, textColor=NAVY, leading=13),
        "valor": s("valor", fontName="Helvetica", fontSize=9, textColor=BLACK, leading=13),
        "destaque": s("destaque", fontName="Helvetica-Bold", fontSize=10, textColor=TEAL, leading=14),
        "texto": s("texto", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#263238"), leading=13),
        "hash": s("hash", fontName="Courier", fontSize=7.5, textColor=colors.HexColor("#424242"), leading=11),
        "assinatura": s("assinatura", fontName="Helvetica", fontSize=8, textColor=colors.HexColor("#616161"), alignment=TA_CENTER, leading=12),
        "rodape": s("rodape", fontName="Helvetica", fontSize=7.5, textColor=colors.HexColor("#757575"), alignment=TA_CENTER, leading=11),
    }


def _header(st: dict[str, ParagraphStyle], status: str, page_width: float) -> Table:
    tbl = Table(
        [[
            [Paragraph("PicSaúde", st["titulo"]), Paragraph("Encaminhamento clínico rastreável", st["subtitulo"])],
            Paragraph(f"ENCAMINHAMENTO — {status.upper()}", st["badge"]),
        ]],
        colWidths=[page_width * 0.58, page_width * 0.42],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (1, 0), (1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _secao(titulo: str, st: dict[str, ParagraphStyle], page_width: float) -> Table:
    tbl = Table([[Paragraph(titulo.upper(), st["secao"])]], colWidths=[page_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GREY_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _linha(label: str, valor: str | None, st: dict[str, ParagraphStyle]) -> list:
    return [Paragraph(escape(label), st["label"]), Paragraph(escape(valor or "-"), st["valor"])]


def gerar_pdf_encaminhamento(
    *,
    protocolo: str,
    status: str,
    tipo_emissao: str,
    assinatura_hash: Optional[str],
    data_emissao: str,
    data_validade: str,
    nome_origem: str,
    cns_origem: str,
    cns_destino: str,
    especialidade_destino: str,
    cid: Optional[str],
    justificativa_clinica: str,
    nome_paciente: str,
    cpf_paciente: str,
    itens: list[dict],
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    page_width = A4[0] - doc.leftMargin - doc.rightMargin
    st = _styles()
    story = [_header(st, status, page_width), Spacer(1, 8)]

    story += [
        _secao("Profissionais", st, page_width),
        Table([
            _linha("Origem", f"{nome_origem} — CNS {cns_origem}", st),
            _linha("Destino", f"CNS {cns_destino}", st),
            _linha("Especialidade", especialidade_destino, st),
        ], colWidths=[32 * mm, page_width - 32 * mm]),
        Spacer(1, 6),
        _secao("Paciente", st, page_width),
        Table([
            _linha("Nome", nome_paciente, st),
            _linha("CPF", _fmt_cpf(cpf_paciente), st),
        ], colWidths=[32 * mm, page_width - 32 * mm]),
        Spacer(1, 6),
        _secao("Justificativa Clínica", st, page_width),
        Paragraph(escape(justificativa_clinica or "-"), st["texto"]),
    ]

    if cid:
        story.append(Paragraph(f"<b>CID informado:</b> {escape(cid)}", st["texto"]))
    story.append(Spacer(1, 6))

    story += [_secao("Itens", st, page_width)]
    for idx, item in enumerate(itens, start=1):
        detalhes = [
            f"<b>{idx}. {escape(item.get('especialidade') or especialidade_destino)}</b>",
            f"Procedimento: {escape(item.get('procedimento') or '-')}",
            f"Motivo: {escape(item.get('motivo') or '-')}",
            f"Status: {escape(item.get('status_item') or '-')}",
        ]
        story.append(Paragraph("<br/>".join(detalhes), st["destaque"]))
        story.append(Spacer(1, 3))

    story += [
        Spacer(1, 4),
        _secao("Documento", st, page_width),
        Table([
            _linha("Protocolo", protocolo, st),
            _linha("Emissão", _fmt_data(data_emissao), st),
            _linha("Validade", _fmt_data(data_validade), st),
            _linha("Tipo", tipo_emissao, st),
            [Paragraph("Hash", st["label"]), Paragraph(_truncar_hash(assinatura_hash), st["hash"])],
        ], colWidths=[32 * mm, page_width - 32 * mm]),
        Spacer(1, 22),
        Table(
            [[Paragraph("________________________________________", st["assinatura"])],
             [Paragraph("Assinatura do prescritor de origem", st["assinatura"])]],
            colWidths=[page_width],
        ),
        Spacer(1, 8),
        Paragraph(f"PicSaúde — protocolo {protocolo}", st["rodape"]),
    ]

    doc.build(story)
    return buffer.getvalue()
