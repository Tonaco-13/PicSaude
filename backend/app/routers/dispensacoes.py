"""
dispensacoes.py
===============
Endpoints de consulta e comprovante de dispensação do PicSaúde.

Segurança:
  - Nunca retorna a prescrição inteira, apenas dados do comprovante.
  - 404 imediato se a dispensação não existir.

Formatos suportados em GET /dispensacoes/{id}/comprovante:
  ?formato=json  → dict estruturado  (default)
  ?formato=pdf   → application/pdf via reportlab
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.auth.dependencies import require_role
from app.database_tx import get_tx

router = APIRouter(prefix="/dispensacoes", tags=["dispensacoes"])


# ---------------------------------------------------------------------------
# Query principal — join de todas as tabelas necessárias
# ---------------------------------------------------------------------------

_SQL_COMPROVANTE = """
SELECT
    d.id                        AS dispensacao_id,
    d.cnpj_estabelecimento,
    d.quantidade_dispensada,
    d.dispensado_por,
    d.dispensado_em,
    d.lote,
    d.fabricante,
    d.observacao,

    i.nome_medicamento,
    i.concentracao,
    i.quantidade                AS quantidade_prescrita,
    i.posologia,

    p.protocolo,
    p.data_emissao,

    pac.nome                    AS paciente_nome,
    pac.cpf                     AS paciente_cpf,

    pr.nome                     AS prescritor_nome,
    pr.cns                      AS prescritor_cns,

    e.nome_fantasia             AS estabelecimento_nome,
    e.razao_social              AS estabelecimento_razao

FROM dispensacoes d
JOIN prescricao_itens i     ON i.id  = d.prescricao_item_id
JOIN prescricoes p          ON p.id  = i.prescricao_id
JOIN pacientes pac          ON pac.id = p.paciente_id
JOIN prescritores pr        ON pr.id  = p.prescritor_id
LEFT JOIN estabelecimentos_proprios e ON e.cnpj = d.cnpj_estabelecimento

WHERE d.id = ?
"""


def _buscar_dados(dispensacao_id: int) -> dict:
    with get_tx() as conn:
        row = conn.execute(_SQL_COMPROVANTE, (dispensacao_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Dispensação {dispensacao_id} não encontrada.")
        return dict(row)


def _montar_json(d: dict) -> dict:
    """Transforma a linha bruta no payload JSON do comprovante."""
    # CPF sentinela não representa cidadão real — omitir no comprovante
    cpf_exibir = d["paciente_cpf"] if d["paciente_cpf"] != "00000000000" else "Não identificado"

    return {
        "dispensacao_id":      d["dispensacao_id"],
        "protocolo_prescricao": d["protocolo"],
        "data_dispensacao":    d["dispensado_em"],
        "data_emissao_prescricao": d["data_emissao"],

        "paciente": {
            "nome": d["paciente_nome"],
            "cpf":  cpf_exibir,
        },

        "medicamento": {
            "nome":                d["nome_medicamento"],
            "concentracao":        d["concentracao"] or "N/I",
            "posologia":           d["posologia"]    or "N/I",
            "quantidade_prescrita": d["quantidade_prescrita"],
            "quantidade_dispensada": d["quantidade_dispensada"],
        },

        "lote": {
            "numero":    d["lote"]      or "N/I",
            "fabricante": d["fabricante"] or "N/I",
        },

        "prescritor": {
            "nome": d["prescritor_nome"],
            "cns":  d["prescritor_cns"],
        },

        "dispensador": {
            # Fallback sanitário: nome_fantasia → razao_social → CNPJ
            # O estabelecimento sempre é identificável, mesmo sem cadastro completo.
            "estabelecimento": (
                d["estabelecimento_nome"]
                or d["estabelecimento_razao"]
                or f"CNPJ {d['cnpj_estabelecimento']}"
            ),
            "cnpj":           d["cnpj_estabelecimento"],
            "dispensado_por": d["dispensado_por"] or "N/I",
        },

        "observacao": d["observacao"] or None,
    }


# ---------------------------------------------------------------------------
# Geração de PDF com reportlab
# ---------------------------------------------------------------------------

def _gerar_pdf(dados: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=f"Comprovante de Dispensação #{dados['dispensacao_id']}",
    )

    styles = getSampleStyleSheet()
    cor_primaria = colors.HexColor("#1a5276")

    estilo_titulo = ParagraphStyle(
        "Titulo",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=cor_primaria,
        spaceAfter=4,
    )
    estilo_subtitulo = ParagraphStyle(
        "Subtitulo",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=cor_primaria,
        spaceBefore=10,
        spaceAfter=4,
    )
    estilo_normal = styles["Normal"]
    estilo_small  = ParagraphStyle("Small", parent=styles["Normal"], fontSize=8,
                                   textColor=colors.grey)

    def secao(titulo: str, linhas: list[tuple[str, str]]) -> list:
        """Retorna bloco de seção: título + tabela de duas colunas."""
        itens = [Paragraph(titulo, estilo_subtitulo)]
        table_data = [[Paragraph(f"<b>{k}</b>", estilo_normal),
                       Paragraph(str(v), estilo_normal)]
                      for k, v in linhas if v and v != "N/I" or True]
        t = Table(table_data, colWidths=[5 * cm, 11 * cm])
        t.setStyle(TableStyle([
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ]))
        itens.append(t)
        return itens

    # Formatar data
    def fmt_data(s: Optional[str]) -> str:
        if not s:
            return "N/I"
        try:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return s

    med = dados["medicamento"]
    lot = dados["lote"]

    story = []

    # Cabeçalho
    story.append(Paragraph("PicSaúde", estilo_titulo))
    story.append(Paragraph("COMPROVANTE DE DISPENSAÇÃO", estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=1.5, color=cor_primaria))
    story.append(Spacer(1, 0.3 * cm))

    # Protocolo e data
    story += secao("Identificação", [
        ("Dispensação nº",    str(dados["dispensacao_id"])),
        ("Protocolo",         dados["protocolo_prescricao"]),
        ("Data de dispensação", fmt_data(dados["data_dispensacao"])),
        ("Data de emissão",   fmt_data(dados["data_emissao_prescricao"])),
    ])

    story.append(Spacer(1, 0.2 * cm))
    story += secao("Paciente", [
        ("Nome", dados["paciente"]["nome"]),
        ("CPF",  dados["paciente"]["cpf"]),
    ])

    story.append(Spacer(1, 0.2 * cm))
    story += secao("Medicamento", [
        ("Nome",          med["nome"]),
        ("Concentração",  med["concentracao"]),
        ("Posologia",     med["posologia"]),
        ("Qtd. prescrita",   str(med["quantidade_prescrita"]  or "N/I")),
        ("Qtd. dispensada",  str(med["quantidade_dispensada"])),
    ])

    story.append(Spacer(1, 0.2 * cm))
    story += secao("Lote", [
        ("Número do lote", lot["numero"]),
        ("Fabricante",     lot["fabricante"]),
    ])

    story.append(Spacer(1, 0.2 * cm))
    story += secao("Prescritor", [
        ("Nome", dados["prescritor"]["nome"]),
        ("CNS",  dados["prescritor"]["cns"]),
    ])

    story.append(Spacer(1, 0.2 * cm))
    story += secao("Estabelecimento Dispensador", [
        ("Nome",            dados["dispensador"]["estabelecimento"]),
        ("CNPJ",            dados["dispensador"]["cnpj"]),
        ("Dispensado por",  dados["dispensador"]["dispensado_por"]),
    ])

    if dados.get("observacao"):
        story.append(Spacer(1, 0.2 * cm))
        story += secao("Observação", [("", dados["observacao"])])

    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "Documento gerado automaticamente pelo sistema PicSaúde. "
        "Válido para fins de rastreabilidade sanitária.",
        estilo_small,
    ))

    doc.build(story)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/{dispensacao_id}/comprovante")
def comprovante(
    dispensacao_id: int,
    formato: str = Query(default="json", pattern="^(json|pdf)$"),
    _=Depends(require_role("dispensador", "prescritor", "auditor", "admin")),
):
    """
    Retorna o comprovante de uma dispensação específica.

    - ?formato=json  (padrão) → payload JSON estruturado
    - ?formato=pdf            → arquivo PDF para impressão
    """
    dados_brutos = _buscar_dados(dispensacao_id)
    dados = _montar_json(dados_brutos)

    if formato == "pdf":
        pdf_bytes = _gerar_pdf(dados)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="comprovante_dispensacao_{dispensacao_id}.pdf"'
            },
        )

    return dados
