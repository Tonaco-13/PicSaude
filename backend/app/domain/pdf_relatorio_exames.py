"""
pdf_relatorio_exames.py — PDF do relatório de exames do prestador (R3, ENG-008).

Irmão de `pdf_relatorio_sngpc.py`, e deliberadamente NÃO uma generalização dele:
os dois relatórios respondem a autoridades diferentes (SNGPC/Anvisa × operação da
clínica) e vão divergir em colunas e rótulos. Fundi-los agora criaria um helper
com dois donos — o custo que o próprio ENG-008 cita ao recusar acumular a clínica
em `/dispensadores`.

READ-ONLY: recebe linhas já lidas e devolve bytes. Não toca banco.
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

NAVY = colors.HexColor("#1e3a8a")
GREEN = colors.HexColor("#16a34a")
RED = colors.HexColor("#dc2626")
WHITE = colors.white
GREY_BG = colors.HexColor("#f1f5f9")

# Teto de linhas no PDF. Espelha `dispensadores.py` — acima disso, aviso VISÍVEL
# (truncagem silenciosa é o que faz um relatório mentir por omissão).
MAX_REGISTROS_PDF = 1000


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
    cabecalho = ParagraphStyle("cabecalho", parent=base["Normal"], fontSize=6.5,
                               fontName="Helvetica-Bold", textColor=WHITE,
                               alignment=TA_CENTER, leading=8)
    celula = ParagraphStyle("celula", parent=base["Normal"], fontSize=6.5,
                            fontName="Helvetica", textColor=colors.HexColor("#1e293b"),
                            leading=8)
    return titulo, subtitulo, filtro, aviso, cabecalho, celula


def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.HexColor("#64748b"))
    texto = ("Sistema PicSaúde — Relatório de exames do prestador · "
             "Documento gerado automaticamente")
    w, _ = landscape(A4)
    canvas.drawCentredString(w / 2, 8 * mm, texto)
    canvas.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


# Colunas (mm) — total ≈ 262 mm (dentro dos 273 mm úteis em landscape).
_COLUNAS = [
    ("Protocolo",        38 * mm),
    ("Item",             12 * mm),
    ("Exame",            48 * mm),
    ("TUSS",             18 * mm),
    ("Status",           26 * mm),
    ("Agendamento",      26 * mm),
    ("Coleta",           26 * mm),
    ("Resultado",        26 * mm),
    ("Paciente",         42 * mm),
]

_HEADERS = [c[0] for c in _COLUNAS]
_COL_WIDTHS = [c[1] for c in _COLUNAS]


def _fmt_data(iso: Any) -> str:
    if not iso:
        return "—"
    txt = iso if isinstance(iso, str) else getattr(iso, "isoformat", lambda: str(iso))()
    try:
        return datetime.fromisoformat(str(txt)).strftime("%d/%m/%Y\n%H:%M")
    except ValueError:
        return str(txt)[:16]


def gerar_pdf_exames(
    linhas: list[dict],
    filtros: dict,
    limitado: bool = False,
    total_no_periodo: int | None = None,
) -> bytes:
    """PDF do relatório de exames do prestador.

    linhas           : já ordenadas e truncadas em <= MAX_REGISTROS_PDF.
    filtros          : data_inicio, data_fim, cnpj (cabeçalho).
    limitado         : True se houve truncagem.
    total_no_periodo : total real antes da truncagem (exibido no aviso).
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

    story.append(Paragraph("PicSaúde", titulo_s))
    story.append(Paragraph("Relatório de exames — Prestador (clínica/laboratório)", subtitulo_s))
    story.append(Paragraph(f"Emitido em: {agora_utc}", filtro_s))
    story.append(Spacer(1, 3 * mm))

    periodo = f"{filtros.get('data_inicio') or '—'}  até  {filtros.get('data_fim') or '—'}"
    story.append(Paragraph(f"Período: {periodo}", filtro_s))
    if filtros.get("cnpj"):
        story.append(Paragraph(f"Estabelecimento (CNPJ): {filtros['cnpj']}", filtro_s))
    story.append(Paragraph(f"Itens exibidos: {len(linhas)}", filtro_s))

    if limitado:
        total_txt = f" (total no período: {total_no_periodo})" if total_no_periodo else ""
        story.append(Paragraph(
            f"⚠  Relatório truncado em {MAX_REGISTROS_PDF} registros{total_txt} — "
            "use o CSV para exportação completa.",
            aviso_s,
        ))

    story.append(Spacer(1, 3 * mm))

    data_table = [[Paragraph(h, cabecalho_s) for h in _HEADERS]]
    for ln in linhas:
        data_table.append([
            Paragraph(str(ln.get("protocolo") or ""), celula_s),
            Paragraph(str(ln.get("item_id") or ""), celula_s),
            Paragraph(str(ln.get("nome_exame") or ""), celula_s),
            Paragraph(str(ln.get("codigo_tuss") or "—"), celula_s),
            Paragraph(str(ln.get("status_item") or ""), celula_s),
            Paragraph(_fmt_data(ln.get("data_agendamento")), celula_s),
            Paragraph(_fmt_data(ln.get("data_coleta")), celula_s),
            Paragraph(_fmt_data(ln.get("data_resultado")), celula_s),
            Paragraph(str(ln.get("paciente_nome") or ""), celula_s),
        ])

    tabela = Table(data_table, colWidths=_COL_WIDTHS, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
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


# ---------------------------------------------------------------------------
# Faturamento (R4 — DESPACHO-ENG-009)
# ---------------------------------------------------------------------------
# Contabilidade INTERNA: quantos exames de cada procedimento foram concluídos no
# período. Não é guia TISS, não sai da instituição.

_COLUNAS_FATURAMENTO = [
    ("Procedimento (TUSS)", 70 * mm),
    ("Quantidade",          30 * mm),
    ("Primeiro resultado",  40 * mm),
    ("Último resultado",    40 * mm),
]

_HEADERS_FAT = [c[0] for c in _COLUNAS_FATURAMENTO]
_COL_WIDTHS_FAT = [c[1] for c in _COLUNAS_FATURAMENTO]


def gerar_pdf_faturamento(
    grupos: list[dict],
    filtros: dict,
    limitado: bool = False,
    total_no_periodo: int | None = None,
) -> bytes:
    """PDF do faturamento (agregação por procedimento) do prestador."""
    titulo_s, subtitulo_s, filtro_s, aviso_s, cabecalho_s, celula_s = _estilos()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm,
        topMargin=14 * mm, bottomMargin=16 * mm,
    )

    agora_utc = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    total_exames = sum(int(g.get("qtd") or 0) for g in grupos)
    story = []

    story.append(Paragraph("PicSaúde", titulo_s))
    story.append(Paragraph(
        "Faturamento de exames — Prestador (relatório interno)", subtitulo_s))
    story.append(Paragraph(f"Emitido em: {agora_utc}", filtro_s))
    story.append(Spacer(1, 3 * mm))

    periodo = f"{filtros.get('data_inicio') or '—'}  até  {filtros.get('data_fim') or '—'}"
    story.append(Paragraph(f"Período: {periodo}", filtro_s))
    if filtros.get("cnpj"):
        story.append(Paragraph(f"Estabelecimento (CNPJ): {filtros['cnpj']}", filtro_s))
    story.append(Paragraph(
        f"Procedimentos distintos: {len(grupos)} · Exames concluídos: {total_exames}", filtro_s))
    # Anti-overclaim: um documento chamado "faturamento" precisa dizer o que NÃO é,
    # ou vira guia de cobrança na mão de quem o receber.
    story.append(Paragraph(
        "Relatório interno de contabilidade — não é guia TISS nem documento de "
        "cobrança junto a operadora.", filtro_s))

    if limitado:
        total_txt = f" (total no período: {total_no_periodo})" if total_no_periodo else ""
        story.append(Paragraph(
            f"⚠  Relatório truncado em {MAX_REGISTROS_PDF} registros{total_txt} — "
            "use o CSV para exportação completa.",
            aviso_s,
        ))

    story.append(Spacer(1, 3 * mm))

    data_table = [[Paragraph(h, cabecalho_s) for h in _HEADERS_FAT]]
    for g in grupos:
        data_table.append([
            Paragraph(str(g.get("codigo_tuss") or ""), celula_s),
            Paragraph(str(g.get("qtd") or 0), celula_s),
            Paragraph(_fmt_data(g.get("primeiro_resultado")), celula_s),
            Paragraph(_fmt_data(g.get("ultimo_resultado")), celula_s),
        ])

    tabela = Table(data_table, colWidths=_COL_WIDTHS_FAT, repeatRows=1)
    tabela.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("ALIGN",       (1, 1), (1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("TOPPADDING",  (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("LINEBELOW",   (0, 0), (-1, 0), 1, GREEN),
    ]))
    story.append(tabela)

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
