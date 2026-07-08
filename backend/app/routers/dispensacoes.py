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

import hashlib
import io
import json
import uuid
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn
from app.utils.helpers import normalize_cnpj, normalize_cns

router = APIRouter(prefix="/dispensacoes", tags=["dispensacoes"])

# T2 — motivos de estorno (enum ratificado por Fabiano, 2026-07-08).
# 'outro' exige texto livre em motivo_detalhe. Espelhado na CheckConstraint
# do model Estorno e na migração Alembic (paridade SQLite × Postgres).
_MOTIVOS_ESTORNO = {"falha_pagamento", "desistencia", "erro_dispensacao", "outro"}


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
    usuario=Depends(require_role("dispensador", "prescritor", "auditor", "admin")),
):
    """
    Retorna o comprovante de uma dispensação específica.

    - ?formato=json  (padrão) → payload JSON estruturado
    - ?formato=pdf            → arquivo PDF para impressão
    """
    # V9 (TICKET-5C §4.9) — owner check multi-role.
    # admin/auditor passam direto; dispensador exige CNPJ; prescritor exige CNS.
    if usuario["role"] not in ("admin", "auditor"):
        with get_tx() as conn:
            info = conn.execute(
                """
                SELECT d.cnpj_estabelecimento, pr.cns AS prescritor_cns
                  FROM dispensacoes d
                  JOIN prescricao_itens i ON i.id = d.prescricao_item_id
                  JOIN prescricoes p       ON p.id = i.prescricao_id
                  JOIN prescritores pr     ON pr.id = p.prescritor_id
                 WHERE d.id = ?
                """,
                (dispensacao_id,),
            ).fetchone()
            if not info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Dispensação {dispensacao_id} não encontrada.",
                )
            if usuario["role"] == "dispensador":
                if normalize_cnpj(usuario["sub"]) != info["cnpj_estabelecimento"]:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "codigo": "nao_e_dono_da_dispensacao",
                            "mensagem": "Esta dispensação foi realizada por outro estabelecimento.",
                        },
                    )
            elif usuario["role"] == "prescritor":
                if normalize_cns(usuario["sub"]) != info["prescritor_cns"]:
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "codigo": "nao_e_dono_da_prescricao",
                            "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                        },
                    )

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


# ---------------------------------------------------------------------------
# T2 — Estorno de dispensação (objeto sanitário derivado imutável)
# ---------------------------------------------------------------------------
# Classe `core` — ledger + novo objeto derivado (CLAUDE.md §10). Estorno NÃO
# muta `dispensacoes` (imutável §1) nem o status do item (permanece `dispensado`);
# repõe saldo Σ efetivo. Ledger DUPLO: `estorno_registrado` no ledger próprio +
# `dispensacao_estornada` no ledger da prescrição.
# Ver TICKET-T2-ESTORNO-DISPENSACAO.md e TICKET-ESTORNO-OBJETO-DERIVADO.md.


class EstornarIn(BaseModel):
    quantidade_estornada: int = Field(gt=0)
    motivo: str
    motivo_detalhe: Optional[str] = None

    @field_validator("motivo")
    @classmethod
    def _motivo_valido(cls, v: str) -> str:
        if v not in _MOTIVOS_ESTORNO:
            raise ValueError(f"motivo inválido; use um de {sorted(_MOTIVOS_ESTORNO)}")
        return v


def _hash_estorno(
    *, protocolo: str, origem_dispensacao_id: int, cnpj: str,
    quantidade_estornada: int, motivo: str, data_emissao: str,
) -> str:
    """Hash SHA-256 do documento canônico do estorno (integridade — espelha CR)."""
    doc = {
        "protocolo": protocolo,
        "origem_dispensacao_id": origem_dispensacao_id,
        "cnpj_estabelecimento": cnpj,
        "quantidade_estornada": quantidade_estornada,
        "motivo": motivo,
        "data_emissao": data_emissao,
        "versao_esquema": "1",
    }
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@router.post("/{dispensacao_id}/estornar", status_code=201)
def estornar_dispensacao(
    dispensacao_id: int,
    payload: EstornarIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Registra o ESTORNO (reversão) de uma dispensação como objeto derivado imutável.

    Invariantes (Opção B — martelo Fabiano, 2026-07-07):
    - `dispensacoes` original **intocada**; item permanece `dispensado`.
    - Repõe saldo Σ efetivo (= Σ dispensado − Σ estornado): o item volta a ser
      dispensável se ainda não estiver em estado terminal.
    - Ownership: só o dispensador que registrou a dispensação (mesmo CNPJ)
      estorna; admin passa. Anti-leak 404 → 403 → 409/422.
    - Ledger DUPLO: `estorno_registrado` (ledger do estorno) +
      `dispensacao_estornada` (ledger da prescrição).
    """
    # motivo='outro' exige justificativa livre (auditoria).
    if payload.motivo == "outro" and not (payload.motivo_detalhe and payload.motivo_detalhe.strip()):
        raise HTTPException(
            status_code=422,
            detail={"codigo": "motivo_detalhe_obrigatorio",
                    "mensagem": "motivo='outro' exige motivo_detalhe."},
        )

    agora = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()
    estorno_protocolo = str(uuid.uuid4())

    with get_tx() as conn:
        disp = conn.execute(
            """
            SELECT d.id                AS dispensacao_id,
                   d.cnpj_estabelecimento,
                   d.quantidade_dispensada,
                   i.id                AS item_id,
                   i.prescricao_id     AS prescricao_id,
                   p.protocolo         AS proto_prescricao,
                   p.paciente_id       AS paciente_id
              FROM dispensacoes d
              JOIN prescricao_itens i ON i.id = d.prescricao_item_id
              JOIN prescricoes p      ON p.id = i.prescricao_id
             WHERE d.id = ?
            """,
            (dispensacao_id,),
        ).fetchone()
        if not disp:
            raise HTTPException(status_code=404, detail=f"Dispensação {dispensacao_id} não encontrada.")

        # Ownership — dispensador só estorna a própria dispensação (admin passa).
        if usuario["role"] == "dispensador":
            if normalize_cnpj(usuario["sub"]) != disp["cnpj_estabelecimento"]:
                raise HTTPException(
                    status_code=403,
                    detail={"codigo": "nao_e_dono_da_dispensacao",
                            "mensagem": "Esta dispensação foi registrada por outro estabelecimento."},
                )

        # Saldo estornável = quantidade dispensada − Σ já estornado desta dispensação.
        ja_estornado = conn.execute(
            "SELECT COALESCE(SUM(quantidade_estornada), 0) AS total FROM estornos WHERE origem_dispensacao_id = ?",
            (dispensacao_id,),
        ).fetchone()["total"]
        saldo_estornavel = disp["quantidade_dispensada"] - ja_estornado
        if saldo_estornavel <= 0:
            raise HTTPException(
                status_code=409,
                detail={"codigo": "dispensacao_ja_estornada",
                        "mensagem": "Dispensação já foi totalmente estornada."},
            )
        if payload.quantidade_estornada > saldo_estornavel:
            raise HTTPException(
                status_code=422,
                detail={"codigo": "quantidade_supera_saldo_estornavel",
                        "mensagem": (
                            f"Quantidade a estornar ({payload.quantidade_estornada}) "
                            f"supera o saldo estornável ({saldo_estornavel})."
                        )},
            )

        cnpj = disp["cnpj_estabelecimento"]
        autor_tipo = usuario["role"]
        autor_id = normalize_cnpj(usuario["sub"]) if usuario["role"] == "dispensador" else usuario.get("sub")

        doc_hash = _hash_estorno(
            protocolo=estorno_protocolo, origem_dispensacao_id=dispensacao_id,
            cnpj=cnpj, quantidade_estornada=payload.quantidade_estornada,
            motivo=payload.motivo, data_emissao=data_emissao,
        )

        instance_id = get_instance_id_conn(conn)

        cur = conn.execute(
            """
            INSERT INTO estornos
              (protocolo, origem_dispensacao_id, autor_tipo, autor_id, paciente_id,
               quantidade_estornada, motivo, motivo_detalhe, assinatura_hash,
               instance_id, data_emissao, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (estorno_protocolo, dispensacao_id, autor_tipo, autor_id, disp["paciente_id"],
             payload.quantidade_estornada, payload.motivo, payload.motivo_detalhe, doc_hash,
             instance_id, data_emissao, agora),
        )
        estorno_id = cur.lastrowid

        # Ledger DUPLO (arch §8): objeto derivado + prescrição-parent.
        registrar_evento_ledger(
            conn, objeto_tipo="estorno", objeto_id=estorno_id,
            tipo_evento="estorno_registrado", instance_id=instance_id,
            payload={
                "origem_dispensacao_id": dispensacao_id,
                "quantidade_estornada": payload.quantidade_estornada,
                "motivo": payload.motivo,
                "prescricao_protocolo": disp["proto_prescricao"],
            },
            ator_tipo=autor_tipo, ator_id=autor_id,
        )
        registrar_evento_ledger(
            conn, objeto_tipo="prescricao", objeto_id=disp["prescricao_id"],
            tipo_evento="dispensacao_estornada", instance_id=instance_id,
            payload={
                "item_id": disp["item_id"],
                "origem_dispensacao_id": dispensacao_id,
                "estorno_protocolo": estorno_protocolo,
                "quantidade_estornada": payload.quantidade_estornada,
                "motivo": payload.motivo,
            },
            ator_tipo="dispensador", ator_id=cnpj,
        )

        return {
            "protocolo_estorno": estorno_protocolo,
            "origem_dispensacao_id": dispensacao_id,
            "quantidade_estornada": payload.quantidade_estornada,
            "saldo_estornavel_restante": saldo_estornavel - payload.quantidade_estornada,
            "motivo": payload.motivo,
            "documento_hash": doc_hash,
        }
