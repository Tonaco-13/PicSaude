"""
pdf_receituario.py
==================
Gerador de PDF do RECEITUÁRIO regulatório — Ticket 17.

Distinção em relação a `pdf_prescricao.py`
------------------------------------------
- `pdf_prescricao` gera o PDF do ATO CLÍNICO (todos os itens, documento
  interno/operacional).
- `pdf_receituario` gera o PDF do DOCUMENTO REGULATÓRIO (por grupo, modelo
  Anvisa Versão 2, apresentado na farmácia).

Uma prescrição com 3 itens (ex: A1 + B1 + sem classe) gera 1 PDF de
prescrição e 3 PDFs de receituário distintos.

Compatibilidade
---------------
Estrutura e campos obrigatórios compatíveis com os modelos Anvisa
Versão 2 (publicada 16/03/2026, mandatória em 18/05/2026). NÃO afirmamos
reprodução visual pixel-perfect — apenas alinhamento estrutural.

Mudança V1 → V2 (confirmada): o paciente é identificado por CPF, não
mais por endereço.

Modos de operação
-----------------
- adapter_usado="stub" → marca d'água "DOCUMENTO SEM VALIDADE
  REGULATÓRIA" + faixa "[DESENVOLVIMENTO]" + CPF mascarado.
- adapter_usado="real" → sem marca d'água, sem faixa de dev. CPF
  conforme decisão regulatória final (TODO_REGULATORIO).
- nao_requer_sncr (receita simples) → sem faixa SNCR e sem marca d'água.
"""
from __future__ import annotations

import io
from typing import Optional

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.domain.pdf_prescricao import _fmt_cpf, _fmt_data, _truncar_hash


# ---------------------------------------------------------------------------
# Mapeamento de cores e layout por tipo (modelos Anvisa V2 — aproximação)
# ---------------------------------------------------------------------------

CORES_RECEITUARIO: dict[str, dict] = {
    "notificacao_receita_a": {
        "cor_primaria":         colors.HexColor("#F9A825"),  # Amarelo Anvisa
        "cor_fundo_cabecalho":  colors.HexColor("#FFF8E1"),  # Amarelo claro
        "cor_borda":            colors.HexColor("#F57F17"),  # Amarelo forte
        "cor_titulo":           colors.HexColor("#212121"),  # Preto sobre amarelo
        "titulo":               "NOTIFICAÇÃO DE RECEITA A",
        "subtitulo":            "Listas A1 / A2 / A3 — Portaria SVS/MS nº 344/1998",
        "cor_papel":            "AMARELA",
        "tipo_abrev":           "NRA",
        "alerta":               "ATENÇÃO: Substância sujeita a controle especial",
        "info_vias":            "3 VIAS — 1ª via Anvisa / 2ª via farmácia / 3ª via paciente",
    },
    "notificacao_receita_b": {
        "cor_primaria":         colors.HexColor("#1565C0"),  # Azul Anvisa
        "cor_fundo_cabecalho":  colors.HexColor("#E3F2FD"),  # Azul claro
        "cor_borda":            colors.HexColor("#0D47A1"),  # Azul forte
        "cor_titulo":           colors.white,
        "titulo":               "NOTIFICAÇÃO DE RECEITA B",
        "subtitulo":            "Listas B1 / B2 — Portaria SVS/MS nº 344/1998",
        "cor_papel":            "AZUL",
        "tipo_abrev":           "NRB",
        "alerta":               None,
        "info_vias":            "2 VIAS — 1ª via farmácia / 2ª via paciente",
    },
    "receita_controle_especial": {
        "cor_primaria":         colors.HexColor("#37474F"),  # Cinza-escuro
        "cor_fundo_cabecalho":  colors.HexColor("#ECEFF1"),  # Cinza claro
        "cor_borda":            colors.HexColor("#263238"),  # Quase preto
        "cor_titulo":           colors.white,
        "titulo":               "RECEITA DE CONTROLE ESPECIAL",
        "subtitulo":            "Lista C — 2 vias — Portaria SVS/MS nº 344/1998",
        "cor_papel":            "BRANCA",
        "tipo_abrev":           "RCE",
        "alerta":               None,
        "info_vias":            "2 VIAS — 1ª via retida pela farmácia",
    },
    "notificacao_receita_especial": {
        "cor_primaria":         colors.HexColor("#6A1B9A"),  # Roxo
        "cor_fundo_cabecalho":  colors.HexColor("#F3E5F5"),  # Roxo claro
        "cor_borda":            colors.HexColor("#4A148C"),  # Roxo forte
        "cor_titulo":           colors.white,
        "titulo":               "NOTIFICAÇÃO DE RECEITA ESPECIAL",
        "subtitulo":            "Retinoides / Talidomida — Listas D1 / D2",
        "cor_papel":            "BRANCA",
        "tipo_abrev":           "NRE",
        "alerta":               "ATENÇÃO: Medicamento com risco teratogênico",
        "info_vias":            "2 VIAS — 1ª via farmácia / 2ª via paciente",
    },
    "receita_simples": {
        "cor_primaria":         colors.HexColor("#2E7D32"),  # Verde PicSaúde
        "cor_fundo_cabecalho":  colors.HexColor("#E8F5E9"),  # Verde claro
        "cor_borda":            colors.HexColor("#1B5E20"),  # Verde forte
        "cor_titulo":           colors.white,
        "titulo":               "RECEITA SIMPLES",
        "subtitulo":            "Sem controle regulatório especial",
        "cor_papel":            "BRANCA",
        "tipo_abrev":           "RSI",
        "alerta":               None,
        "info_vias":            "1 VIA",
    },
    "receita_retencao": {
        "cor_primaria":         colors.HexColor("#00695C"),  # Verde-azulado
        "cor_fundo_cabecalho":  colors.HexColor("#E0F2F1"),
        "cor_borda":            colors.HexColor("#004D40"),
        "cor_titulo":           colors.white,
        "titulo":               "RECEITA COM RETENÇÃO",
        "subtitulo":            "RDC 471/2021 — antimicrobianos / GLP-1",
        "cor_papel":            "BRANCA",
        "tipo_abrev":           "RRT",
        "alerta":               None,
        "info_vias":            "2 VIAS — 1ª via farmácia / 2ª via paciente",
    },
}


def tipo_abrev(tipo_receituario: str) -> str:
    """Retorna a abreviação curta usada no nome do arquivo (NRA/NRB/RCE/...)."""
    return CORES_RECEITUARIO.get(tipo_receituario, {}).get("tipo_abrev", "REC")


# ---------------------------------------------------------------------------
# Estilos de parágrafo
# ---------------------------------------------------------------------------

def _build_styles(cor_titulo) -> dict:
    base = getSampleStyleSheet()  # noqa: F841

    def s(name, **kw) -> ParagraphStyle:
        return ParagraphStyle(name=name, **kw)

    return {
        "titulo_header": s(
            "titulo_header",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=cor_titulo,
            alignment=TA_LEFT,
            leading=20,
        ),
        "subtitulo_header": s(
            "subtitulo_header",
            fontName="Helvetica",
            fontSize=8.5,
            textColor=cor_titulo,
            alignment=TA_LEFT,
            leading=11,
        ),
        "marca_sncr": s(
            "marca_sncr",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=cor_titulo,
            alignment=TA_RIGHT,
            leading=11,
        ),
        "secao": s(
            "secao",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.HexColor("#1a2e44"),
            alignment=TA_LEFT,
        ),
        "label": s(
            "label",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#1a2e44"),
            leading=13,
        ),
        "valor": s(
            "valor",
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.black,
            leading=13,
        ),
        "alerta": s(
            "alerta",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=colors.HexColor("#B71C1C"),
            alignment=TA_CENTER,
            leading=13,
        ),
        "info_vias": s(
            "info_vias",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#212121"),
            alignment=TA_CENTER,
            leading=13,
        ),
        "sncr_label": s(
            "sncr_label",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.HexColor("#212121"),
            alignment=TA_LEFT,
            leading=14,
        ),
        "sncr_dev": s(
            "sncr_dev",
            fontName="Helvetica-Bold",
            fontSize=8,
            textColor=colors.HexColor("#D32F2F"),
            alignment=TA_LEFT,
            leading=11,
        ),
        "nome_medicamento": s(
            "nome_medicamento",
            fontName="Helvetica-Bold",
            fontSize=10,
            textColor=colors.HexColor("#2e7d32"),
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
        "qr_label": s(
            "qr_label",
            fontName="Helvetica",
            fontSize=7,
            textColor=colors.HexColor("#616161"),
            alignment=TA_CENTER,
            leading=10,
        ),
        "assinatura_label": s(
            "assinatura_label",
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#616161"),
            alignment=TA_CENTER,
            leading=12,
        ),
        "rodape": s(
            "rodape",
            fontName="Helvetica",
            fontSize=7.5,
            textColor=colors.HexColor("#757575"),
            alignment=TA_CENTER,
            leading=11,
        ),
        "rodape_alerta": s(
            "rodape_alerta",
            fontName="Helvetica-Bold",
            fontSize=7.5,
            textColor=colors.HexColor("#D32F2F"),
            alignment=TA_CENTER,
            leading=11,
        ),
    }


# ---------------------------------------------------------------------------
# Helpers de bloco
# ---------------------------------------------------------------------------

def _bloco_cabecalho(
    layout: dict,
    styles: dict,
    page_width: float,
) -> Table:
    """Cabeçalho colorido com tipo do receituário + marca SNCR."""
    esq = [
        Paragraph(layout["titulo"], styles["titulo_header"]),
        Paragraph(layout["subtitulo"], styles["subtitulo_header"]),
    ]
    dir_ = [
        Paragraph("PicSaúde", styles["marca_sncr"]),
        Paragraph(
            "SNCR — Sistema Nacional de Controle de Receituários",
            styles["marca_sncr"],
        ),
    ]
    tbl = Table(
        [[esq, dir_]],
        colWidths=[page_width * 0.55, page_width * 0.45],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), layout["cor_primaria"]),
        ("LINEBELOW",     (0, 0), (-1, -1), 2.5, layout["cor_borda"]),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (0, -1), 14),
        ("RIGHTPADDING",  (1, 0), (1, -1), 14),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return tbl


def _bloco_alerta(texto: str, styles: dict, page_width: float) -> Table:
    """Faixa de alerta vermelha (controlados A / talidomida)."""
    tbl = Table([[Paragraph(texto, styles["alerta"])]], colWidths=[page_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFEBEE")),
        ("BOX",           (0, 0), (-1, -1), 1.0, colors.HexColor("#B71C1C")),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return tbl


def _bloco_sncr(
    numeracao_sncr: Optional[str],
    is_stub: bool,
    styles: dict,
    page_width: float,
    cor_borda,
) -> Table:
    """Faixa com numeração SNCR. Se stub, indica desenvolvimento."""
    if is_stub:
        linhas = [
            Paragraph(f"<b>Nº SNCR:</b> {numeracao_sncr}", styles["sncr_label"]),
            Paragraph(
                "[DESENVOLVIMENTO — numeração não regulatória]",
                styles["sncr_dev"],
            ),
        ]
    else:
        linhas = [
            Paragraph(f"<b>Nº SNCR:</b> {numeracao_sncr or '—'}", styles["sncr_label"]),
        ]
    tbl = Table([[linhas]], colWidths=[page_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
        ("BOX",           (0, 0), (-1, -1), 1.0, cor_borda),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
    ]))
    return tbl


def _bloco_info_vias(texto: str, styles: dict, page_width: float, cor_borda) -> Table:
    tbl = Table([[Paragraph(texto, styles["info_vias"])]], colWidths=[page_width])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#F5F5F5")),
        ("LINEABOVE",     (0, 0), (-1, -1), 0.5, cor_borda),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, cor_borda),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _titulo_secao(texto: str, styles: dict, page_width: float, cor) -> Table:
    tbl = Table(
        [[Paragraph(texto.upper(), styles["secao"])]],
        colWidths=[page_width],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#ECEFF1")),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.5, cor),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
    ]))
    return tbl


def _linha_lv(
    label: str,
    valor: str,
    styles: dict,
    page_width: float,
) -> Table:
    tbl = Table(
        [[
            Paragraph(label, styles["label"]),
            Paragraph(valor or "—", styles["valor"]),
        ]],
        colWidths=[page_width * 0.28, page_width * 0.72],
    )
    tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def _qr_drawing(dados: str, lado_mm: float = 25) -> Drawing:
    """Gera Drawing de QR code. Usa ReportLab puro (sem dependência extra)."""
    qr = QrCodeWidget(dados)
    qr.barLevel = "M"
    bounds = qr.getBounds()
    larg = bounds[2] - bounds[0]
    alt = bounds[3] - bounds[1]
    escala = (lado_mm * mm) / max(larg, alt)
    drawing = Drawing(lado_mm * mm, lado_mm * mm)
    drawing.add(qr)
    drawing.scale(escala, escala)
    drawing.translate(-bounds[0], -bounds[1])
    return drawing


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def gerar_pdf_receituario(
    *,
    # receituário
    tipo_receituario: str,
    grupo_nome: str,
    numeracao_sncr: Optional[str],
    status: str,
    vias: int,
    retencao_farmacia: bool,
    adapter_usado: Optional[str],
    # prescrição
    protocolo: str,
    assinatura_hash: Optional[str],
    assinatura_modo: Optional[str],
    data_emissao: str,
    data_validade: Optional[str],
    indicacao_clinica: Optional[str],
    # prescritor
    nome_prescritor: str,
    cns_prescritor: str,
    # paciente
    nome_paciente: str,
    cpf_paciente: str,
    # itens (lista de dicts: nome_medicamento, concentracao, quantidade,
    #        unidade_quantidade, forma_farmaceutica, posologia, classe_controle)
    itens: list[dict],
) -> bytes:
    """Gera PDF do receituário regulatório (modelo Anvisa V2).

    Retorna os bytes do PDF prontos para StreamingResponse.
    """
    layout = CORES_RECEITUARIO.get(tipo_receituario)
    if layout is None:
        # Fallback defensivo: tipo desconhecido → usa receita_simples.
        layout = CORES_RECEITUARIO["receita_simples"]

    is_stub = (adapter_usado == "stub")
    requer_sncr_view = layout["tipo_abrev"] not in ("RSI",)  # receita simples não exibe SNCR
    if numeracao_sncr is None:
        # Sem numeração: bloco SNCR não aparece.
        requer_sncr_view = False

    styles = _build_styles(layout["cor_titulo"])

    buf = io.BytesIO()
    margin = 20 * mm
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title=f"Receituário {layout['tipo_abrev']} — {protocolo[:8].upper()}",
        author="PicSaúde — SNCR",
        subject="Receituário regulatório (Anvisa V2)",
    )

    page_w = A4[0] - 2 * margin
    story: list = []

    # 1. Cabeçalho colorido
    story.append(_bloco_cabecalho(layout, styles, page_w))
    story.append(Spacer(1, 3 * mm))

    # 2. Alerta de substância controlada (se aplicável)
    if layout.get("alerta"):
        story.append(_bloco_alerta(layout["alerta"], styles, page_w))
        story.append(Spacer(1, 3 * mm))

    # 3. Faixa de numeração SNCR (apenas controlados — receita simples não exibe)
    if requer_sncr_view:
        story.append(_bloco_sncr(
            numeracao_sncr, is_stub, styles, page_w, layout["cor_borda"],
        ))
        story.append(Spacer(1, 3 * mm))

    # 4. Faixa de informação de vias
    story.append(_bloco_info_vias(
        layout["info_vias"], styles, page_w, layout["cor_borda"],
    ))
    story.append(Spacer(1, 5 * mm))

    # 5. Seção Prescritor
    story.append(_titulo_secao("Prescritor", styles, page_w, layout["cor_primaria"]))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_prescritor or "—", styles, page_w))
    story.append(_linha_lv("CNS", cns_prescritor or "—", styles, page_w))
    story.append(_linha_lv(
        "Modo de assinatura",
        _label_assinatura(assinatura_modo),
        styles, page_w,
    ))
    story.append(Spacer(1, 4 * mm))

    # 6. Seção Paciente (CPF — V2 substituiu endereço)
    story.append(_titulo_secao("Paciente", styles, page_w, layout["cor_primaria"]))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nome", nome_paciente or "—", styles, page_w))
    cpf_exibir = (
        "Não identificado"
        if cpf_paciente == "00000000000"
        else _fmt_cpf(cpf_paciente)
    )
    story.append(_linha_lv("CPF", cpf_exibir, styles, page_w))
    story.append(Spacer(1, 4 * mm))

    # 7. Seção Medicamentos
    story.append(_titulo_secao(
        "Medicamentos prescritos", styles, page_w, layout["cor_primaria"],
    ))
    story.append(Spacer(1, 2 * mm))
    for idx, item in enumerate(itens, start=1):
        nome_med = (item.get("nome_medicamento") or "").upper()
        conc = item.get("concentracao") or None
        qtd = item.get("quantidade")
        unidade = item.get("unidade_quantidade") or None
        forma = item.get("forma_farmaceutica") or None
        posologia = item.get("posologia") or None
        classe = item.get("classe_controle") or None

        titulo_med = f"{idx}. {nome_med}"
        if conc:
            titulo_med += f"  <font size='9' color='#616161'>({conc})</font>"
        if classe:
            titulo_med += f"  <font size='8' color='#B71C1C'><b>[{classe}]</b></font>"
        story.append(Paragraph(titulo_med, styles["nome_medicamento"]))

        if qtd is not None:
            qtd_texto = f"{qtd} {unidade}" if unidade else str(qtd)
            if forma:
                qtd_texto += f"  <font size='9' color='#616161'>({forma})</font>"
            story.append(Paragraph(
                f"Quantidade: <b>{qtd_texto}</b>",
                styles["posologia"],
            ))
        if posologia:
            story.append(Paragraph(
                f"Posologia: {posologia}",
                styles["posologia"],
            ))
        story.append(Spacer(1, 2.5 * mm))

    # 8. Seção Informações regulatórias
    story.append(_titulo_secao(
        "Informações regulatórias", styles, page_w, layout["cor_primaria"],
    ))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Nº de vias", str(vias), styles, page_w))
    story.append(_linha_lv(
        "Retenção pela farmácia",
        "Sim — 1ª via retida" if retencao_farmacia else "Não",
        styles, page_w,
    ))
    if indicacao_clinica:
        story.append(_linha_lv(
            "Indicação clínica", indicacao_clinica, styles, page_w,
        ))
    story.append(Spacer(1, 4 * mm))

    # 9. Seção Rastreabilidade
    story.append(_titulo_secao(
        "Rastreabilidade", styles, page_w, layout["cor_primaria"],
    ))
    story.append(Spacer(1, 1.5 * mm))
    story.append(_linha_lv("Protocolo", protocolo, styles, page_w))
    story.append(_linha_lv("Data de emissão", _fmt_data(data_emissao), styles, page_w))
    if data_validade:
        story.append(_linha_lv("Validade", _fmt_data(data_validade), styles, page_w))

    hash_tbl = Table(
        [[
            Paragraph("<b>Hash SHA-256</b>", styles["label"]),
            Paragraph(_truncar_hash(assinatura_hash), styles["hash_text"]),
        ]],
        colWidths=[page_w * 0.28, page_w * 0.72],
    )
    hash_tbl.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(hash_tbl)
    story.append(Spacer(1, 6 * mm))

    # 10. QR Code + linha de assinatura (lado a lado)
    qr_data = (
        f"protocolo={protocolo};"
        f"sncr={numeracao_sncr or 'N/A'};"
        f"hash={(assinatura_hash or 'N/A')[:16]};"
        f"tipo={tipo_receituario};"
        f"emitido={data_emissao}"
    )
    qr_drawing = _qr_drawing(qr_data, lado_mm=25)

    bloco_assinatura = [
        Paragraph("_" * 45, styles["assinatura_label"]),
        Spacer(1, 1 * mm),
        Paragraph(
            f"<b>{nome_prescritor or 'Prescritor'}</b><br/>CNS {cns_prescritor or ''}",
            styles["assinatura_label"],
        ),
    ]
    bloco_qr = [
        qr_drawing,
        Paragraph("QR — Rastreabilidade PicSaúde", styles["qr_label"]),
    ]

    qr_tbl = Table(
        [[bloco_assinatura, bloco_qr]],
        colWidths=[page_w * 0.70, page_w * 0.30],
    )
    qr_tbl.setStyle(TableStyle([
        ("VALIGN",      (0, 0), (-1, -1), "BOTTOM"),
        ("ALIGN",       (1, 0), (1, 0), "CENTER"),
        ("TOPPADDING",  (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(KeepTogether(qr_tbl))
    story.append(Spacer(1, 4 * mm))

    # 11. Rodapé
    story.append(HRFlowable(width=page_w, thickness=0.3, color=colors.HexColor("#bdbdbd")))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Documento gerado por PicSaúde — SNCR&nbsp;&nbsp;|"
        "&nbsp;&nbsp;Modelo Anvisa Versão 2 — Vigente a partir de 18/05/2026",
        styles["rodape"],
    ))
    if is_stub:
        story.append(Spacer(1, 1 * mm))
        story.append(Paragraph(
            "&#9888; Numeração STUB — apenas para desenvolvimento e testes",
            styles["rodape_alerta"],
        ))

    # Marca d'água em modo stub
    on_page = _watermark_callback(is_stub)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Marca d'água (apenas em modo stub)
# ---------------------------------------------------------------------------

def _watermark_callback(is_stub: bool):
    """Retorna callback `onPage` que desenha marca d'água em modo stub."""
    def _draw(canvas, doc):
        if not is_stub:
            return
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 40)
        # Cinza claro com transparência (~15% de opacidade).
        canvas.setFillColor(colors.HexColor("#BDBDBD"), alpha=0.18)
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "DOCUMENTO SEM VALIDADE REGULATORIA")
        canvas.restoreState()
    return _draw


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _label_assinatura(assinatura_modo: Optional[str]) -> str:
    if assinatura_modo == "icp_brasil_local":
        return "Certificado digital ICP-Brasil — Token A1/A3 (Resolução CFM 2.299/2021)"
    if assinatura_modo == "gov_br_nuvem":
        return "Assinatura gov.br em nuvem (Resolução CFM 2.299/2021) — em implantação"
    if assinatura_modo is None or assinatura_modo == "":
        return "Não declarado"
    return assinatura_modo


# Suprime aviso do reportlab sobre renderPDF não usado diretamente.
_ = renderPDF
