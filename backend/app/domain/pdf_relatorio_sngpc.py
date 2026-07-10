"""
pdf_relatorio_sngpc.py
======================
PDF da escrituração SNGPC do dispensador (TICKET-F5-RELATORIO-SNGPC, Fatia A).

Visão do DISPENSADOR (livro da própria farmácia), distinta da visão do auditor
(`pdf_relatorio_dispensacoes.py`, escopo global). Aqui cada linha é um MOVIMENTO
(dispensação ou estorno), não um estado — espelhando o ledger imutável.

FORMATO
-------
A4 landscape, margens 12 mm, 14 colunas em fonte 5.5pt.

AVISO DE TRUNCAMENTO (critério §5.8 · nota 3 do Z AI)
----------------------------------------------------
Acima de 1000 registros o PDF exibe aviso VISÍVEL de truncamento e aponta o CSV
para exportação completa — nunca truncamento silencioso.

CPF SENTINELA
-------------
'00000000000' já é excluído na query; ainda assim o formatador mascara CPF
parcialmente no PDF (documento visual), mantendo o CSV como escrituração crua.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ---------------------------------------------------------------------------
# Paleta PicSaúde (mesma do PDF de auditoria)
# ---------------------------------------------------------------------------

NAVY    = colors.HexColor("#1a2e44")
GREEN   = colors.HexColor("#2e7d32")
GREY_BG = colors.HexColor("#eceff1")
ORANGE  = colors.HexColor("#e65100")
RED     = colors.HexColor("#b71c1c")
WHITE   = colors.white

_CPF_NAO_IDENTIFICADO = "00000000000"

_MAX_REGISTROS_PDF = 1000


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()
    titulo = ParagraphStyle("titulo", parent=base["Normal"], fontSize=14,
                            fontName="Helvetica-Bold", textColor=NAVY, spaceAfter=2)
    subtitulo = ParagraphStyle("subtitulo", parent=base["Normal"], fontSize=8,
                               fontName="Helvetica", textColor=colors.HexColor("#546e7a"),
                               spaceAfter=2)
    filtro = ParagraphStyle("filtro", parent=base["Normal"], fontSize=7,
                            fontName="Helvetica", textColor=colors.HexColor("#475569"),
                            spaceAfter=1)
    aviso = ParagraphStyle("aviso", parent=base["Normal"], fontSize=8,
                           fontName="Helvetica-Bold", textColor=RED,
                           spaceBefore=4, spaceAfter=4)
    cabecalho = ParagraphStyle("cabecalho", parent=base["Normal"], fontSize=5.5,
                               fontName="Helvetica-Bold", textColor=WHITE,
                               alignment=TA_CENTER, leading=7)
    celula = ParagraphStyle("celula", parent=base["Normal"], fontSize=5.5,
                            fontName="Helvetica", textColor=colors.HexColor("#1e293b"),
                            leading=7)
    return titulo, subtitulo, filtro, aviso, cabecalho, celula


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.HexColor("#64748b"))
    texto = "Sistema PicSaúde — Escrituração SNGPC do dispensador · Documento gerado automaticamente"
    w, _ = landscape(A4)
    canvas.drawCentredString(w / 2, 8 * mm, texto)
    canvas.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Colunas (mm) — total ≈ 268 mm (dentro dos 273 mm úteis em landscape)
# ---------------------------------------------------------------------------

_COLUNAS = [
    ("Movimento",    15 * mm),
    ("Data",         18 * mm),
    ("Disp. ID",     11 * mm),
    ("Protocolo",    20 * mm),
    ("Medicamento",  25 * mm),
    ("Dose",         13 * mm),
    ("Qtd",          9 * mm),
    ("Saldo Item",   12 * mm),
    ("Lote",         13 * mm),
    ("Paciente",     23 * mm),
    ("CPF Pac.",     16 * mm),
    ("Comprador",    23 * mm),
    ("Prescritor",   21 * mm),
    ("Motivo Est.",  17 * mm),
]

_HEADERS    = [c[0] for c in _COLUNAS]
_COL_WIDTHS = [c[1] for c in _COLUNAS]


def _fmt_data(iso: str | None) -> str:
    if not iso:
        return "N/I"
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y\n%H:%M")
    except ValueError:
        return str(iso)[:16]


def _fmt_cpf(cpf: str | None) -> str:
    if not cpf or cpf == _CPF_NAO_IDENTIFICADO:
        return "Não ident."
    c = str(cpf).replace(".", "").replace("-", "")
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.***-**"
    return str(cpf)


def _fmt_comprador(m: dict) -> str:
    nome = m.get("comprador_nome") or ""
    if m.get("comprador_eh_paciente"):
        return f"{nome}\n(= paciente)" if nome else "(= paciente)"
    return nome


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------

def gerar_pdf_sngpc(
    movimentos: list[Any],
    filtros: dict,
    limitado: bool = False,
    total_no_periodo: int | None = None,
) -> bytes:
    """
    Gera o PDF da escrituração SNGPC do dispensador.

    Parâmetros
    ----------
    movimentos       : lista de movimentos já ordenados para exibição (dicts do
                       domínio `relatorio_sngpc`), já truncada em <= 1000.
    filtros          : dict com data_inicio, data_fim, cnpj (para o cabeçalho).
    limitado         : True se a lista foi truncada em 1000 registros.
    total_no_periodo : total real de movimentos no período (antes do truncamento),
                       exibido no aviso quando `limitado`.
    """
    titulo_s, subtitulo_s, filtro_s, aviso_s, cabecalho_s, celula_s = _estilos()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
    )

    agora_utc = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    story = []

    # 1. Cabeçalho
    story.append(Paragraph("PicSaúde", titulo_s))
    story.append(Paragraph("Escrituração SNGPC — Movimentos do Estabelecimento", subtitulo_s))
    story.append(Paragraph(f"Emitido em: {agora_utc}", filtro_s))
    story.append(Spacer(1, 3 * mm))

    # 2. Filtros aplicados
    periodo = f"{filtros.get('data_inicio') or '—'}  até  {filtros.get('data_fim') or '—'}"
    story.append(Paragraph(f"Período: {periodo}", filtro_s))
    if filtros.get("cnpj"):
        story.append(Paragraph(f"Estabelecimento (CNPJ): {filtros['cnpj']}", filtro_s))
    story.append(Paragraph(f"Movimentos exibidos: {len(movimentos)}", filtro_s))

    # 3. Aviso de truncamento (§5.8 — nunca silencioso)
    if limitado:
        total_txt = f" (total no período: {total_no_periodo})" if total_no_periodo else ""
        story.append(Paragraph(
            f"⚠  Relatório truncado em {_MAX_REGISTROS_PDF} registros{total_txt} — "
            "use o CSV para exportação completa.",
            aviso_s,
        ))

    story.append(Spacer(1, 3 * mm))

    # 4. Tabela
    header_row = [Paragraph(h, cabecalho_s) for h in _HEADERS]
    data_table = [header_row]

    for m in movimentos:
        linha = [
            Paragraph(m.get("tipo_movimento") or "", celula_s),
            Paragraph(_fmt_data(m.get("data_movimento")), celula_s),
            Paragraph(str(m.get("dispensacao_id") or ""), celula_s),
            Paragraph(m.get("protocolo_prescricao") or "", celula_s),
            Paragraph(m.get("medicamento") or "", celula_s),
            Paragraph(m.get("dose") or "", celula_s),
            Paragraph(str(m.get("quantidade") if m.get("quantidade") is not None else ""), celula_s),
            Paragraph(str(m.get("saldo_escriturado_item") if m.get("saldo_escriturado_item") is not None else ""), celula_s),
            Paragraph(m.get("lote") or "", celula_s),
            Paragraph(m.get("paciente_nome") or "", celula_s),
            Paragraph(_fmt_cpf(m.get("paciente_cpf")), celula_s),
            Paragraph(_fmt_comprador(m), celula_s),
            Paragraph(m.get("prescritor_nome") or "", celula_s),
            Paragraph(m.get("motivo_estorno") or "", celula_s),
        ]
        data_table.append(linha)

    tabela = Table(data_table, colWidths=_COL_WIDTHS, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTSIZE",    (0, 0), (-1, 0), 5.5),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, 0), [NAVY]),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("FONTSIZE",    (0, 1), (-1, -1), 5.5),
        ("VALIGN",      (0, 1), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("LINEBELOW",   (0, 0), (-1, 0), 1, GREEN),
    ]))
    story.append(tabela)

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
