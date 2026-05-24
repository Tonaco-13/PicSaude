"""
pdf_prescricao.py
=================
Geração do PDF da receita médica no formato institucional PicSaúde.

FORMATO
-------
A4 portrait (210 × 297 mm), margens 20 mm.

BLOCOS DO DOCUMENTO
-------------------
1. Cabeçalho    — identidade PicSaúde + título + badge de tipo
2. Prescritor   — nome, CNS, modo de assinatura
3. Paciente     — nome, CPF mascarado
4. Itens        — medicamentos prescritos com posologia
5. Rodapé       — protocolo, data, hash, assinatura do prescritor
6. Área de assinatura — linha para prescrições físicas ou digitais sem
                        prova criptográfica armazenada (MVP)

CORES (paleta PicSaúde)
-----------------------
Navy     #1a2e44   — cabeçalho, títulos de seção
Green    #2e7d32   — borda verde, nomes de medicamento
Orange   #e65100   — badge de emissão física
Slate    #546e7a   — badge operacional
Cyan     #00695c   — badge gov.br
Grey bg  #eceff1   — fundo de seção leve
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
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
SLATE     = colors.HexColor("#546e7a")
CYAN_DARK = colors.HexColor("#00695c")
GREY_BG   = colors.HexColor("#eceff1")
WHITE     = colors.white
BLACK     = colors.black
LIGHT_GREEN = colors.HexColor("#e8f5e9")


# ---------------------------------------------------------------------------
# Helpers de formatação
# ---------------------------------------------------------------------------

def _fmt_cpf(cpf: str) -> str:
    """Formata CPF com máscara parcial: 123.***.***-01"""
    c = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(c) != 11:
        return cpf or "—"
    return f"{c[:3]}.***.***.{c[9:]}"


def _fmt_data(iso) -> str:
    """Converte ISO 8601 ou datetime em DD/MM/AAAA HH:MM."""
    try:
        dt = iso if hasattr(iso, "strftime") else datetime.fromisoformat(iso)
        return dt.strftime("%d/%m/%Y às %H:%M")
    except (ValueError, TypeError):
        return str(iso) if iso else "—"


def _truncar_hash(h: str | None) -> str:
    """Exibe os primeiros 16 + '...' + últimos 8 caracteres do hash."""
    if not h:
        return "não gerado"
    if len(h) <= 28:
        return h
    return f"{h[:16]}...{h[-8:]}"


# ---------------------------------------------------------------------------
# Mapa de rótulos para nivel_formal
# ---------------------------------------------------------------------------

_LABEL_NIVEL: dict[str, tuple[str, object]] = {
    # (label_curto, cor_badge)
    "fisica":              ("FÍSICA — IMPRESSA EM PAPEL",          ORANGE),
    "operacional":         ("OPERACIONAL — SEM VALIDADE CFM",       SLATE),
    "cfm_pendente":        ("DIGITAL — ICP-BRASIL (A1/A3)",         GREEN),
    "cfm_gov_br_pendente": ("DIGITAL — GOV.BR (NUVEM)",             CYAN_DARK),
}

_DESCRICAO_NIVEL: dict[str, str] = {
    "fisica":              "Emissão exclusivamente em papel. Sem cadeia digital de custódia.",
    "operacional":         "Prescrição rastreada digitalmente. Sem pretensão declarada de validade CFM.",
    "cfm_pendente":        "Declara assinatura com certificado digital ICP-Brasil (token A1/A3). "
                           "Resolução CFM 2.299/2021.",
    "cfm_gov_br_pendente": "Declara assinatura em nuvem gov.br. Módulo em implantação. "
                           "Resolução CFM 2.299/2021.",
}


# ---------------------------------------------------------------------------
# Estilos de parágrafo reutilizáveis
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    base = getSampleStyleSheet()

    def s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name=name, **kw)

    return {
        "titulo": s(
            "titulo",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=WHITE,
            alignment=TA_LEFT,
            leading=20,
        ),
        "subtitulo_header": s(
            "subtitulo_header",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#cfd8dc"),
            alignment=TA_LEFT,
            leading=12,
        ),
        "tipo_header": s(
            "tipo_header",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=WHITE,
            alignment=TA_RIGHT,
            leading=12,
        ),
        "secao": s(
            "secao",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceBefore=2,
            spaceAfter=2,
        ),
        "label": s(
            "label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=NAVY,
            leading=13,
        ),
        "valor": s(
            "valor",
            fontName="Helvetica",
            fontSize=9,
            textColor=BLACK,
            leading=13,
        ),
        "nome_medicamento": s(
            "nome_medicamento",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=GREEN,
            leading=14,
        ),
        "posologia": s(
            "posologia",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#212121"),
            leading=13,
            leftIndent=8,
        ),
        "hash_text": s(
            "hash_text",
            fontName="Courier",
            fontSize=7.5,
            textColor=colors.HexColor("#424242"),
            leading=11,
        ),
        "rodape": s(
            "rodape",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=colors.HexColor("#757575"),
            alignment=TA_CENTER,
            leading=11,
        ),
        "assinatura_label": s(
            "assinatura_label",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#616161"),
            alignment=TA_CENTER,
            leading=12,
        ),
    }


# ---------------------------------------------------------------------------
# Bloco de cabeçalho (fundo navy, badge de tipo)
# ---------------------------------------------------------------------------

def _bloco_cabecalho(styles: dict, nivel: str, page_width: float) -> Table:
    label_nivel, cor_badge = _LABEL_NIVEL.get(
        nivel, ("TIPO DESCONHECIDO", SLATE)
    )

    esq = [
        Paragraph("PicSaúde", styles["titulo"]),
        Paragraph("Plataforma de Custódia Sanitária Digital", styles["subtitulo_header"]),
    ]

    dir_ = [
        Paragraph("RECEITA MÉDICA", styles["tipo_header"]),
        Paragraph(
            f'<font color="#{_hex_cor(cor_badge)}" size="8"><b>{label_nivel}</b></font>',
            styles["tipo_header"],
        ),
    ]

    tbl = Table([[esq, dir_]], colWidths=[page_width * 0.55, page_width * 0.45])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",  (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",  (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (1, 0), (1, -1), 14),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _hex_cor(color_obj) -> str:
    """Extrai hex sem '#' de um objeto HexColor do reportlab."""
    hex_full = color_obj.hexval()          # ex: '#2e7d32'
    return hex_full.lstrip("#")


# ---------------------------------------------------------------------------
# Bloco de seção com fundo cinza-claro
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Linha label / valor (2 colunas)
# ---------------------------------------------------------------------------

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
# Função principal de geração
# ---------------------------------------------------------------------------

def gerar_pdf_prescricao(
    *,
    protocolo:       str,
    status:          str,
    tipo_emissao:    str,
    assinatura_modo: Optional[str],
    assinatura_hash: Optional[str],
    nivel_formal:    str,
    data_emissao:    str,
    # prescritor
    nome_prescritor: str,
    cns_prescritor:  str,
    # paciente
    nome_paciente:   str,
    cpf_paciente:    str,
    # itens
    itens: list,   # list[dict]: nome_medicamento, concentracao, quantidade, posologia
    # TICKET-6: marca d'água "DEMO" diagonal quando True
    is_demo:         bool = False,
) -> bytes:
    """
    Gera o PDF da receita médica e retorna os bytes.

    Parâmetros
    ----------
    itens : lista de dicts com chaves:
        nome_medicamento, concentracao (opcional), quantidade (opcional), posologia (opcional)
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
        title=f"Receita Médica — {protocolo[:8].upper()}",
        author="PicSaúde",
        subject="Prescrição médica digital",
    )

    page_w = A4[0] - 2 * margin
    st = _build_styles()
    story = []

    # -----------------------------------------------------------------------
    # 1. Cabeçalho
    # -----------------------------------------------------------------------
    story.append(_bloco_cabecalho(st, nivel_formal, page_w))
    story.append(Spacer(1, 5 * mm))

    # -----------------------------------------------------------------------
    # 2. Prescritor
    # -----------------------------------------------------------------------
    story.append(_titulo_secao("Prescritor", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome",         nome_prescritor or "—", st, page_w))
    story.append(_linha_lv("CNS",          cns_prescritor  or "—", st, page_w))
    story.append(_linha_lv(
        "Modo de assinatura",
        _label_assinatura(assinatura_modo, nivel_formal),
        st, page_w,
    ))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # 3. Paciente
    # -----------------------------------------------------------------------
    story.append(_titulo_secao("Paciente", st, page_w))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_paciente or "—", st, page_w))
    cpf_exibir = (
        "Não identificado"
        if cpf_paciente == "00000000000"
        else _fmt_cpf(cpf_paciente)
    )
    story.append(_linha_lv("CPF",  cpf_exibir, st, page_w))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # 4. Medicamentos prescritos
    # -----------------------------------------------------------------------
    story.append(_titulo_secao("Medicamentos prescritos", st, page_w))
    story.append(Spacer(1, 2 * mm))

    for idx, item in enumerate(itens, start=1):
        nome_med    = (item.get("nome_medicamento") or "").upper()
        conc        = item.get("concentracao") or None
        qtd         = item.get("quantidade")
        unidade     = item.get("unidade_quantidade") or None
        forma       = item.get("forma_farmaceutica") or None
        posologia   = item.get("posologia") or None

        # Linha do nome do medicamento (destacada)
        titulo_med = f"{idx}. {nome_med}"
        if conc:
            titulo_med += f"  <font size='9' color='#616161'>({conc})</font>"
        story.append(Paragraph(titulo_med, st["nome_medicamento"]))

        if qtd is not None:
            qtd_texto = f"{qtd} {unidade}" if unidade else str(qtd)
            if forma:
                qtd_texto += f"  <font size='9' color='#616161'>({forma})</font>"
            story.append(Paragraph(
                f"Quantidade: <b>{qtd_texto}</b>",
                st["posologia"],
            ))
        if posologia:
            story.append(Paragraph(
                f"Posologia: {posologia}",
                st["posologia"],
            ))
        story.append(Spacer(1, 2.5 * mm))

    # -----------------------------------------------------------------------
    # 5. Identificação do documento
    # -----------------------------------------------------------------------
    story.append(_titulo_secao("Identificação do documento", st, page_w))
    story.append(Spacer(1, 1.5 * mm))

    story.append(_linha_lv("Protocolo",    protocolo,                     st, page_w))
    story.append(_linha_lv("Data de emissão", _fmt_data(data_emissao),    st, page_w))
    story.append(_linha_lv("Status",       status,                        st, page_w))
    story.append(_linha_lv("Tipo de emissão", tipo_emissao,               st, page_w))

    # Hash em fonte monoespaçada
    hash_exibir = _truncar_hash(assinatura_hash)
    story.append(Spacer(1, 1 * mm))

    hash_tbl = Table(
        [[
            Paragraph("<b>Hash SHA-256</b>", st["label"]),
            Paragraph(hash_exibir, st["hash_text"]),
        ]],
        colWidths=[page_w * 0.28, page_w * 0.72],
    )
    hash_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(hash_tbl)

    # Caixa de validade formal com borda colorida
    story.append(Spacer(1, 3 * mm))
    _, cor_badge = _LABEL_NIVEL.get(nivel_formal, ("", SLATE))
    descricao = _DESCRICAO_NIVEL.get(nivel_formal, "")
    validade_tbl = Table(
        [[Paragraph(descricao, st["valor"])]],
        colWidths=[page_w],
    )
    validade_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("BOX",           (0, 0), (-1, -1), 1.5, cor_badge),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    story.append(validade_tbl)
    story.append(Spacer(1, 6 * mm))

    # -----------------------------------------------------------------------
    # 6. Área de assinatura
    # -----------------------------------------------------------------------
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
        ("ALIGN",   (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",  (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(linha_assinatura)
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # 7. Rodapé final
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 4 * mm))
    story.append(HRFlowable(width=page_w, thickness=0.3, color=colors.HexColor("#bdbdbd")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Documento gerado por PicSaúde — Plataforma de Custódia Sanitária Digital&nbsp;&nbsp;|"
        f"&nbsp;&nbsp;Protocolo: {protocolo}",
        st["rodape"],
    ))

    # TICKET-6 — marca d'água "DEMO" diagonal em cada página quando is_demo=True.
    # Importado lazy para evitar overhead no caminho normal.
    if is_demo:
        from reportlab.lib import colors as _colors
        from reportlab.lib.pagesizes import A4 as _A4

        def _draw_demo_watermark(canvas, _doc):
            canvas.saveState()
            canvas.setFont("Helvetica-Bold", 96)
            canvas.setFillColorRGB(0.85, 0.85, 0.85)  # cinza claro translúcido
            canvas.translate(_A4[0] / 2, _A4[1] / 2)
            canvas.rotate(45)
            canvas.drawCentredString(0, 0, "DEMO")
            canvas.restoreState()

        doc.build(story, onFirstPage=_draw_demo_watermark, onLaterPages=_draw_demo_watermark)
    else:
        doc.build(story)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _label_assinatura(assinatura_modo: Optional[str], nivel_formal: str) -> str:
    """Retorna texto legível para o campo 'Modo de assinatura' no PDF."""
    if nivel_formal == "fisica":
        return "Emissão exclusivamente física (papel impresso)"
    if assinatura_modo is None:
        return "Nenhum (prescrição operacional)"
    if assinatura_modo == "icp_brasil_local":
        return "Certificado digital ICP-Brasil — Token A1/A3 (Resolução CFM 2.299/2021)"
    if assinatura_modo == "gov_br_nuvem":
        return "Assinatura gov.br em nuvem (Resolução CFM 2.299/2021) — em implantação"
    return assinatura_modo


_DESCRICAO_NIVEL = {
    "fisica":              "Emissão exclusivamente em papel. Sem cadeia digital de custódia.",
    "operacional":         "Prescrição rastreada digitalmente. Sem pretensão declarada de validade CFM.",
    "cfm_pendente":        (
        "Declara assinatura com certificado digital ICP-Brasil (token A1/A3). "
        "Resolução CFM 2.299/2021. Hash de integridade calculado no momento da emissão."
    ),
    "cfm_gov_br_pendente": (
        "Declara assinatura em nuvem gov.br. Resolução CFM 2.299/2021. "
        "Módulo gov.br em implantação."
    ),
}
