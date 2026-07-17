"""
pdf_relatorio_dispensacoes.py
=============================
Geração do PDF de auditoria de dispensações do PicSaúde.

FORMATO
-------
A4 landscape (297 × 210 mm), margens 12 mm.
14 colunas em fonte 6.5pt — necessário para caber em A4 landscape.

BLOCOS DO DOCUMENTO
-------------------
1. Cabeçalho   — identidade PicSaúde + título + timestamp UTC
2. Filtros     — período, estabelecimento, medicamento aplicados
3. Aviso       — se registros truncados em 1000
4. Tabela      — dados de dispensação (14 colunas)
5. Rodapé      — numeração de página (via canvas callback)

CPF SENTINELA
-------------
'00000000000' → substituído por 'Não identificado' no relatório.
O sentinel nunca é exportado bruto.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
# Paleta PicSaúde
# ---------------------------------------------------------------------------

NAVY     = colors.HexColor("#1a2e44")
GREEN    = colors.HexColor("#2e7d32")
GREY_BG  = colors.HexColor("#eceff1")
ORANGE   = colors.HexColor("#e65100")
WHITE    = colors.white

# ---------------------------------------------------------------------------
# Constante sentinela
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO = "00000000000"


# ---------------------------------------------------------------------------
# Estilos
# ---------------------------------------------------------------------------

def _estilos():
    base = getSampleStyleSheet()

    titulo = ParagraphStyle(
        "titulo",
        parent=base["Normal"],
        fontSize=14,
        fontName="Helvetica-Bold",
        textColor=NAVY,
        spaceAfter=2,
    )
    subtitulo = ParagraphStyle(
        "subtitulo",
        parent=base["Normal"],
        fontSize=8,
        fontName="Helvetica",
        textColor=colors.HexColor("#546e7a"),
        spaceAfter=2,
    )
    filtro_label = ParagraphStyle(
        "filtro_label",
        parent=base["Normal"],
        fontSize=7,
        fontName="Helvetica",
        textColor=colors.HexColor("#475569"),
        spaceAfter=1,
    )
    aviso = ParagraphStyle(
        "aviso",
        parent=base["Normal"],
        fontSize=7.5,
        fontName="Helvetica-Bold",
        textColor=ORANGE,
        spaceBefore=4,
        spaceAfter=4,
    )
    cabecalho_col = ParagraphStyle(
        "cabecalho_col",
        parent=base["Normal"],
        fontSize=5.5,
        fontName="Helvetica-Bold",
        textColor=WHITE,
        alignment=TA_CENTER,
        leading=7,
    )
    celula = ParagraphStyle(
        "celula",
        parent=base["Normal"],
        fontSize=5.5,
        fontName="Helvetica",
        textColor=colors.HexColor("#1e293b"),
        leading=7,
    )
    return titulo, subtitulo, filtro_label, aviso, cabecalho_col, celula


# ---------------------------------------------------------------------------
# Callback de rodapé com numeração de página
# ---------------------------------------------------------------------------

def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 6)
    canvas.setFillColor(colors.HexColor("#64748b"))
    texto = "Sistema PicSaúde — Custódia Sanitária Digital · Documento gerado automaticamente"
    w, h = landscape(A4)
    canvas.drawCentredString(w / 2, 8 * mm, texto)
    canvas.drawRightString(w - 12 * mm, 8 * mm, f"Página {doc.page}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Larguras das colunas (mm) — total ≈ 252 mm (dentro dos 273 mm úteis em landscape)
# ---------------------------------------------------------------------------

# Cada coluna declara os campos de ``_SQL_BASE`` (routers/relatorios.py) que
# consome. A declaração é o contrato conferido pelo teste de paridade CSV↔PDF:
# todo campo projetado aqui tem coluna correspondente no CSV de auditoria.
_COLUNAS = [
    ("Data Disp.",    ("data_dispensacao",),      18 * mm),
    ("Protocolo",     ("protocolo_prescricao",),  21 * mm),
    ("Medicamento",   ("medicamento",),           26 * mm),
    ("Concentração",  ("dose",),                  15 * mm),
    ("Qtd. Pres.",    ("quantidade_prescrita",),  11 * mm),
    ("Qtd. Disp.",    ("quantidade_dispensada",), 11 * mm),
    ("Unidade",       ("unidade_quantidade",),    12 * mm),
    ("Lote",          ("lote",),                  13 * mm),
    ("Fabricante",    ("fabricante",),            19 * mm),
    ("Paciente",      ("paciente_nome",),         24 * mm),
    ("CPF Paciente",  ("paciente_cpf",),          16 * mm),
    ("Prescritor",    ("prescritor_nome",),       22 * mm),
    ("CNS",           ("prescritor_cns",),        15 * mm),
    ("Estab. / CNPJ", ("estabelecimento_nome", "estabelecimento_cnpj"), 29 * mm),
]

_HEADERS    = [col[0] for col in _COLUNAS]
_CAMPOS     = [campo for col in _COLUNAS for campo in col[1]]
_COL_WIDTHS = [col[2] for col in _COLUNAS]


# ---------------------------------------------------------------------------
# Formatação de data
# ---------------------------------------------------------------------------

def _fmt_data(s: str | None) -> str:
    if not s:
        return "N/I"
    try:
        dt = datetime.fromisoformat(s)
        return dt.strftime("%d/%m/%Y\n%H:%M")
    except ValueError:
        return s[:16] if s else "N/I"


def _fmt_cpf(cpf: str | None) -> str:
    if not cpf or cpf == _CPF_NAO_IDENTIFICADO:
        return "Não ident."
    # Exibe CPF parcialmente mascarado: 123.456.***-**
    c = cpf.replace(".", "").replace("-", "")
    if len(c) == 11:
        return f"{c[:3]}.{c[3:6]}.***-**"
    return cpf


def _estab(nome: str | None, cnpj: str | None) -> str:
    partes = []
    if nome:
        partes.append(nome[:22])
    if cnpj:
        c = cnpj
        if len(c) == 14:
            c = f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
        partes.append(c)
    return "\n".join(partes) if partes else "N/I"


# ---------------------------------------------------------------------------
# Função pública
# ---------------------------------------------------------------------------

def gerar_pdf_dispensacoes(
    rows: list[Any],
    filtros: dict,
    limitado: bool = False,
) -> bytes:
    """
    Gera o PDF de auditoria de dispensações.

    Parâmetros
    ----------
    rows      : resultado da query SQL (sqlite3.Row ou dict)
    filtros   : dicionário com as chaves data_inicio, data_fim,
                cnpj_estabelecimento, medicamento (valores ou None)
    limitado  : True se rows foi truncado em MAX_REGISTROS

    Retorna
    -------
    bytes do PDF gerado em memória
    """
    titulo_s, subtitulo_s, filtro_s, aviso_s, cabecalho_s, celula_s = _estilos()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=14 * mm,
        bottomMargin=16 * mm,
    )

    agora_utc = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")
    story     = []

    # ------------------------------------------------------------------
    # 1. Cabeçalho
    # ------------------------------------------------------------------
    story.append(Paragraph("PicSaúde", titulo_s))
    story.append(Paragraph("Relatório de Dispensações de Medicamentos", subtitulo_s))
    story.append(Paragraph(f"Emitido em: {agora_utc}", filtro_s))
    story.append(Spacer(1, 3 * mm))

    # ------------------------------------------------------------------
    # 2. Filtros aplicados
    # ------------------------------------------------------------------
    linhas_filtro = []
    periodo = (
        f"{filtros.get('data_inicio') or '—'}  até  {filtros.get('data_fim') or '—'}"
    )
    linhas_filtro.append(f"Período: {periodo}")
    if filtros.get("cnpj_estabelecimento"):
        linhas_filtro.append(f"Estabelecimento (CNPJ): {filtros['cnpj_estabelecimento']}")
    if filtros.get("medicamento"):
        linhas_filtro.append(f"Medicamento (filtro): {filtros['medicamento']}")
    linhas_filtro.append(f"Total de registros no relatório: {len(rows)}")

    for linha in linhas_filtro:
        story.append(Paragraph(linha, filtro_s))

    # ------------------------------------------------------------------
    # 3. Aviso de truncamento
    # ------------------------------------------------------------------
    if limitado:
        story.append(Paragraph(
            "⚠  Relatório limitado aos 1 000 registros mais recentes. "
            "Use o CSV para exportação completa.",
            aviso_s,
        ))

    story.append(Spacer(1, 3 * mm))

    # ------------------------------------------------------------------
    # 4. Tabela
    # ------------------------------------------------------------------
    # Cabeçalho
    header_row = [Paragraph(h, cabecalho_s) for h in _HEADERS]
    data_table = [header_row]

    # Linhas de dados
    for idx, r in enumerate(rows):
        estab_nome = r["estabelecimento_nome"] if r["estabelecimento_nome"] else None
        estab_cnpj = r["estabelecimento_cnpj"]

        linha = [
            Paragraph(_fmt_data(r["data_dispensacao"]),  celula_s),
            Paragraph(r["protocolo_prescricao"] or "",   celula_s),
            Paragraph(r["medicamento"] or "",             celula_s),
            Paragraph(r["dose"] or "",                   celula_s),
            Paragraph(str(r["quantidade_prescrita"] or ""), celula_s),
            Paragraph(str(r["quantidade_dispensada"]),   celula_s),
            Paragraph(r.get("unidade_quantidade") or "", celula_s),
            Paragraph(r["lote"] or "",                   celula_s),
            Paragraph(r["fabricante"] or "",             celula_s),
            Paragraph(r["paciente_nome"] or "",          celula_s),
            Paragraph(_fmt_cpf(r["paciente_cpf"]),       celula_s),
            Paragraph(r["prescritor_nome"] or "",        celula_s),
            Paragraph(r["prescritor_cns"] or "",         celula_s),
            Paragraph(_estab(estab_nome, estab_cnpj),   celula_s),
        ]
        data_table.append(linha)

    tabela = Table(data_table, colWidths=_COL_WIDTHS, repeatRows=1)

    # Estilo da tabela
    estilo_tabela = TableStyle([
        # Cabeçalho
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTSIZE",    (0, 0), (-1, 0), 5.5),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        ("VALIGN",      (0, 0), (-1, 0), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, 0), [NAVY]),
        # Linhas de dados — alternadas
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, GREY_BG]),
        ("FONTSIZE",    (0, 1), (-1, -1), 5.5),
        ("VALIGN",      (0, 1), (-1, -1), "TOP"),
        ("TOPPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        # Grade
        ("GRID",        (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("LINEBELOW",   (0, 0), (-1, 0), 1, GREEN),
    ])
    tabela.setStyle(estilo_tabela)
    story.append(tabela)

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)
    return buf.getvalue()
