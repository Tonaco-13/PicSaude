"""
pdf_atestado.py
===============
PDF institucional do atestado (A4 portrait, paleta PicSaúde).

Blocos: cabeçalho → prescritor → paciente → corpo do atestado (finalidade +
período + cláusula clínica opcional) → identificação (protocolo/datas/hash) →
fecho "local, data" → área de assinatura → rodapé com protocolo.

Título, adjetivo do corpo e sigla do registro NÃO são hardcodados aqui: vêm de
`domain/conselho_profissional.py`, a fonte única (um atestado do CFO é
"ATESTADO ODONTOLÓGICO" e fala em "cuidados odontológicos"). Atestado legado, sem
conselho declarado, cai no `CONSELHO_PADRAO` e renderiza como sempre renderizou.
"""
from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from app.domain.conselho_profissional import conselho_ou_padrao, formatar_registro

NAVY    = colors.HexColor("#1a2e44")
GREEN   = colors.HexColor("#2e7d32")
ORANGE  = colors.HexColor("#e65100")
GREY    = colors.HexColor("#546e7a")
GREY_BG = colors.HexColor("#eceff1")


def _fmt_cpf(cpf: str) -> str:
    c = "".join(ch for ch in (cpf or "") if ch.isdigit())
    if len(c) != 11 or c == "00000000000":
        return "não identificado"
    return f"{c[:3]}.***.***.{c[9:]}"


def _fmt_data_br(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(iso)


def _truncar_hash(h: Optional[str]) -> str:
    if not h:
        return "não gerado"
    return f"{h[:16]}...{h[-8:]}" if len(h) > 28 else h


def _periodo_horario(hora_inicio: Optional[str], hora_fim: Optional[str]) -> str:
    """Trecho do horário de comparecimento — vazio quando nada foi declarado.

    As duas horas são independentes e sempre opcionais: um atendimento pode ter
    hora de chegada sem alta prevista. Cada combinação tem sua redação; nenhuma
    inventa a hora que falta.
    """
    ini = (hora_inicio or "").strip()
    fim = (hora_fim or "").strip()
    if ini and fim:
        return f", no período das {ini} às {fim}"
    if ini:
        return f", a partir das {ini}"
    if fim:
        return f", até as {fim}"
    return ""


def _corpo_atestado(
    nome_paciente: str, finalidade: str, dias: Optional[int],
    data_documento: str, indicacao: Optional[str], cid: Optional[str],
    adjetivo_cuidados: str = "médicos", adjetivo_atendimento: str = "médico",
    hora_inicio: Optional[str] = None, hora_fim: Optional[str] = None,
) -> str:
    """Frase do atestado, adaptada a afastamento vs. comparecimento.

    `adjetivo_cuidados` vem do conselho emissor ("médicos" | "odontológicos") —
    ver domain/conselho_profissional.py. O horário entra nos DOIS ramos: declarado
    e não impresso seria perda silenciosa de um dado que o profissional digitou.
    """
    # Cláusula clínica opcional (privacidade: só aparece se declarada).
    clausula = ""
    if indicacao and cid:
        clausula = f", em razão de quadro clínico compatível com {indicacao} (CID {cid})"
    elif indicacao:
        clausula = f", em razão de quadro clínico compatível com {indicacao}"
    elif cid:
        clausula = f" (CID {cid})"

    data_fmt = _fmt_data_br(data_documento)
    periodo = _periodo_horario(hora_inicio, hora_fim)
    if dias and dias > 0:
        return (
            f"Atesto, para os devidos fins de <b>{finalidade}</b>, que "
            f"<b>{nome_paciente}</b> esteve sob cuidados {adjetivo_cuidados} na data de "
            f"{data_fmt}{periodo}{clausula}, devendo permanecer afastado(a) de suas "
            f"atividades habituais por <b>{dias} dia(s)</b> a partir desta data."
        )
    return (
        f"Atesto, para os devidos fins de <b>{finalidade}</b>, que "
        f"<b>{nome_paciente}</b> compareceu a atendimento {adjetivo_atendimento} na data de "
        f"{data_fmt}{periodo}{clausula}."
    )


def gerar_pdf_atestado(
    *,
    protocolo: str,
    status: str,
    tipo_emissao: str,
    finalidade: str,
    indicacao_clinica: Optional[str],
    codigo_cid: Optional[str],
    dias_afastamento: Optional[int],
    data_documento: str,
    data_validade: Optional[str],
    assinatura_modo: Optional[str],
    assinatura_hash: Optional[str],
    nome_prescritor: str,
    cns_prescritor: str,
    registro_profissional: Optional[str],
    nome_paciente: str,
    cpf_paciente: str,
    conselho: Optional[str] = None,
    uf_registro: Optional[str] = None,
    municipio_emissao: Optional[str] = None,
    hora_inicio: Optional[str] = None,
    hora_fim: Optional[str] = None,
    is_demo: bool = False,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Atestado {protocolo[:8]}",
    )
    base = getSampleStyleSheet()
    st_titulo = ParagraphStyle("t", parent=base["Title"], textColor=NAVY, fontSize=18, spaceAfter=2)
    st_sub    = ParagraphStyle("s", parent=base["Normal"], textColor=GREY, fontSize=9, alignment=TA_CENTER)
    st_sec    = ParagraphStyle("sec", parent=base["Normal"], textColor=NAVY, fontSize=10, spaceBefore=10, spaceAfter=3, leading=12, fontName="Helvetica-Bold")
    st_txt    = ParagraphStyle("x", parent=base["Normal"], fontSize=10.5, leading=15)
    st_corpo  = ParagraphStyle("c", parent=base["Normal"], fontSize=12, leading=20, alignment=TA_JUSTIFY, spaceBefore=8, spaceAfter=8)
    st_meta   = ParagraphStyle("m", parent=base["Normal"], fontSize=8, textColor=GREY, leading=11)

    # Conselho emissor: decide título, adjetivos e sigla do registro. Legado
    # (conselho NULL) cai no padrão CFM e renderiza como sempre renderizou.
    cons = conselho_ou_padrao(conselho)
    registro_fmt = formatar_registro(conselho, uf_registro, registro_profissional)

    story = []
    story.append(Paragraph("PicSaúde", st_titulo))
    story.append(Paragraph("Plataforma de Custódia Sanitária Digital", st_sub))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=GREEN))
    story.append(Spacer(1, 6))
    titulo = cons.titulo_documento + (" (cópia física)" if tipo_emissao == "fisica" else "")
    story.append(Paragraph(f'<para align="center"><font color="#1a2e44" size="14"><b>{titulo}</b></font></para>', st_txt))
    story.append(Spacer(1, 10))

    # Prescritor — o REGISTRO vem antes do CNS: quem identifica o profissional
    # perante a norma (e perante quem recebe o atestado) é o CRM/CRO+UF; o CNS é
    # identificador de sistema, não de habilitação.
    story.append(Paragraph("PROFISSIONAL", st_sec))
    ident_prof = f"{nome_prescritor} — "
    ident_prof += f"{registro_fmt} · CNS {cns_prescritor}" if registro_fmt else f"CNS {cns_prescritor}"
    story.append(Paragraph(ident_prof, st_txt))

    # Paciente
    story.append(Paragraph("PACIENTE", st_sec))
    story.append(Paragraph(f"{nome_paciente} — CPF {_fmt_cpf(cpf_paciente)}", st_txt))

    # Corpo
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_BG))
    story.append(Paragraph(_corpo_atestado(
        nome_paciente, finalidade, dias_afastamento, data_documento,
        indicacao_clinica, codigo_cid,
        adjetivo_cuidados=cons.adjetivo_cuidados,
        adjetivo_atendimento=cons.adjetivo_atendimento,
        hora_inicio=hora_inicio, hora_fim=hora_fim), st_corpo))
    if data_validade:
        story.append(Paragraph(f"Período de afastamento até <b>{_fmt_data_br(data_validade)}</b>.", st_txt))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_BG))

    # Fecho "local, data" — o CFM exige LOCAL e DATA no atestado. A data já vinha
    # em `data_documento`; o local é `municipio_emissao`. Fica ACIMA da área de
    # assinatura, na posição clássica do documento em papel. Atestado legado (sem
    # município declarado) simplesmente não imprime o fecho — melhor a ausência
    # honesta do que um local inventado num documento assinado.
    if municipio_emissao and municipio_emissao.strip():
        story.append(Spacer(1, 22))
        story.append(Paragraph(
            f'<para align="center">{municipio_emissao.strip()}, {_fmt_data_br(data_documento)}.</para>',
            st_txt))

    # Assinatura
    story.append(Spacer(1, 26))
    if assinatura_modo == "icp_brasil_local":
        story.append(Paragraph('<para align="center">Documento assinado digitalmente (ICP-Brasil)</para>', st_meta))
    else:
        story.append(Paragraph('<para align="center">_______________________________________</para>', st_txt))
        ident_assin = f"{nome_prescritor} — "
        ident_assin += f"{registro_fmt} · CNS {cns_prescritor}" if registro_fmt else f"CNS {cns_prescritor}"
        story.append(Paragraph(f'<para align="center">{ident_assin}</para>', st_meta))

    # Identificação / rodapé
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GREY_BG))
    story.append(Paragraph(
        f"Protocolo: {protocolo} · Emitido em {_fmt_data_br(data_documento)} · "
        f"Status: {status} · Hash SHA-256: {_truncar_hash(assinatura_hash)}", st_meta))
    story.append(Paragraph(
        "PicSaúde — Plataforma de Custódia Sanitária Digital. Verifique a autenticidade "
        f"pelo protocolo {protocolo}.", st_meta))

    def _watermark(canvas, _doc):
        if not is_demo:
            return
        canvas.saveState()
        canvas.setFont("Helvetica-Bold", 70)
        canvas.setFillColor(colors.HexColor("#e2e8f0"))
        canvas.translate(A4[0] / 2, A4[1] / 2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "DEMONSTRAÇÃO")
        canvas.restoreState()

    doc.build(story, onFirstPage=_watermark, onLaterPages=_watermark)
    return buf.getvalue()
