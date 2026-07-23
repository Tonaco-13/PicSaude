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
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.database import row_lock_suffix
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.medicamento import formatar_quantidade, normalizar_unidade
from app.domain.motor_regulatorio import grupo_por_id
from app.domain.states import MOTIVOS_ESTORNO
from app.instance import get_instance_id_conn
from app.routers.custodia import transferir_posse
from app.utils.helpers import normalize_cnpj, normalize_cns

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
    d.comprador_nome,
    d.comprador_documento,
    d.grupo_regulatorio_id,
    d.motor_regulatorio_versao,

    i.nome_medicamento,
    i.concentracao,
    i.quantidade                AS quantidade_prescrita,
    i.unidade_quantidade,
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
        d = dict(row)
        # §5.A — estado de estorno (read-only sobre `estornos`, objeto derivado).
        # Determinismo (régua Jules): ORDER BY id. Nunca edita a dispensação.
        estornos = conn.execute(
            "SELECT protocolo, quantidade_estornada, motivo, criado_em "
            "FROM estornos WHERE origem_dispensacao_id = ? ORDER BY id",
            (dispensacao_id,),
        ).fetchall()
        d["_estornos"] = [dict(e) for e in estornos]
        return d


def _montar_estorno(estorno_rows: list, quantidade_dispensada) -> dict:
    """Seção derivada de estorno do comprovante (§5.A). Semântica binária vs.
    parcial computada no BACKEND — a UI nunca infere 'parcial' comparando
    quantidades no cliente. Estorno é objeto derivado; a dispensação é imutável."""
    qd = quantidade_dispensada or 0
    total = sum((e["quantidade_estornada"] or 0) for e in estorno_rows)
    estornado = total > 0
    return {
        "estornado":            estornado,
        "estorno_total":        estornado and total >= qd,
        "quantidade_estornada": total,
        "quantidade_restante":  qd - total,
        "estornos": [
            {
                "protocolo": e["protocolo"],
                "quantidade": e["quantidade_estornada"],
                "motivo":     e["motivo"],
                # criado_em: PG devolve datetime, SQLite string ISO — normalizar.
                "data": e["criado_em"].isoformat() if isinstance(e["criado_em"], datetime) else e["criado_em"],
            }
            for e in estorno_rows
        ],
    }


def _montar_json(d: dict) -> dict:
    """Transforma a linha bruta no payload JSON do comprovante."""
    # CPF sentinela não representa cidadão real — omitir no comprovante
    cpf_exibir = d["paciente_cpf"] if d["paciente_cpf"] != "00000000000" else "Não identificado"

    # T5 — COMPRADOR (portador que retira) × PACIENTE (indicação clínica).
    # MVP: sem comprador declarado na dispensação → o comprador é o próprio paciente.
    comprador_declarado = bool(d.get("comprador_nome"))

    return {
        "dispensacao_id":      d["dispensacao_id"],
        "protocolo_prescricao": d["protocolo"],
        "data_dispensacao":    d["dispensado_em"],
        "data_emissao_prescricao": d["data_emissao"],

        "paciente": {
            "nome": d["paciente_nome"],
            "cpf":  cpf_exibir,
        },

        "comprador": {
            "nome":       d["comprador_nome"] if comprador_declarado else d["paciente_nome"],
            "documento":  d["comprador_documento"] if comprador_declarado else cpf_exibir,
            "eh_paciente": not comprador_declarado,
        },

        "medicamento": {
            "nome":                d["nome_medicamento"],
            "concentracao":        d["concentracao"] or "N/I",
            "posologia":           d["posologia"]    or "N/I",
            "quantidade_prescrita": d["quantidade_prescrita"],
            "quantidade_dispensada": d["quantidade_dispensada"],
            # Unidade canônica (ou null → a UI renderiza "não informada"). NUNCA
            # defaultar para "unidade" (TICKET-UNIDADE-QUANTIDADE-VISIVEL).
            "unidade_quantidade":  normalizar_unidade(d.get("unidade_quantidade")),
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

        # R4 (CLAUDE.md §2a) — escrituração regulatória CONGELADA na dispensação.
        # Projeta o valor gravado (nunca re-resolve). grupo=None → item não-controlado
        # (a UI mostra vazio; NUNCA inventa grupo). versao = carimbo da regra sob a
        # qual o movimento foi escriturado.
        # grupo_regulatorio_nome: nome humano resolvido do SLUG congelado via
        # grupo_por_id (fonte única — o motor). A tela NÃO hardcoda nomes. Slug
        # desconhecido → None (a UI degrada para o slug, não quebra).
        "escrituracao_regulatoria": {
            "grupo_regulatorio_id":  d.get("grupo_regulatorio_id"),
            "grupo_regulatorio_nome": (
                g.nome if (g := grupo_por_id(d.get("grupo_regulatorio_id"))) else None
            ),
            "motor_regulatorio_versao": d.get("motor_regulatorio_versao"),
            "controlado": d.get("grupo_regulatorio_id") is not None,
        },

        # §5.A — estado de estorno (read-only). Sempre presente; estornado=false
        # quando não há estorno (o comprovante atual continua idêntico nesse caso).
        "estorno": _montar_estorno(d.get("_estornos", []), d["quantidade_dispensada"]),
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
    def fmt_data(s) -> str:
        if not s:
            return "N/I"
        # Paridade SQLite×PostgreSQL: a coluna `dispensado_em` é DateTime, então
        # o PostgreSQL devolve um objeto `datetime` e o SQLite uma string ISO.
        # Sem tratar o datetime, o comprovante em PDF sairia com a data crua.
        if isinstance(s, datetime):
            return s.strftime("%d/%m/%Y %H:%M")
        try:
            dt = datetime.fromisoformat(s)
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(s)

    med = dados["medicamento"]
    lot = dados["lote"]

    story = []

    # Cabeçalho
    story.append(Paragraph("PicSaúde", estilo_titulo))
    story.append(Paragraph("COMPROVANTE DE DISPENSAÇÃO", estilo_subtitulo))
    story.append(HRFlowable(width="100%", thickness=1.5, color=cor_primaria))
    story.append(Spacer(1, 0.3 * cm))

    # §5.A — carimbo inequívoco de estorno (visível, acima dos blocos). O estorno
    # ADICIONA informação; nunca some nem edita a dispensação original (CLAUDE.md §2).
    _est = dados.get("estorno") or {}
    if _est.get("estornado"):
        _refs = ", ".join(str(e["protocolo"]) for e in _est.get("estornos", []))
        if _est.get("estorno_total"):
            _carimbo_txt = f"DISPENSAÇÃO ESTORNADA — ref. estorno {_refs}"
        else:
            # Unidade real no carimbo, não "un." genérico
            # (TICKET-UNIDADE-QUANTIDADE-VISIVEL). formatar_quantidade é o
            # caminho autoritativo: pluraliza e trata unidade ausente.
            _q_disp = dados["medicamento"]["quantidade_dispensada"]
            _un_carimbo = dados["medicamento"].get("unidade_quantidade")
            _carimbo_txt = (
                f"DISPENSAÇÃO PARCIALMENTE ESTORNADA — "
                f"{_est['quantidade_estornada']} de {formatar_quantidade(_q_disp, _un_carimbo)} "
                f"(restam {_est['quantidade_restante']}) — ref. estorno {_refs}"
            )
        estilo_carimbo = ParagraphStyle(
            "Carimbo", parent=styles["Normal"], fontSize=12, leading=16,
            textColor=colors.white, backColor=colors.HexColor("#c0392b"),
            borderPadding=6, alignment=1, spaceBefore=2, spaceAfter=6,
        )
        story.append(Paragraph(f"<b>{_carimbo_txt}</b>", estilo_carimbo))
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

    # T5 — Comprador (portador que retira), distinto do paciente. No MVP, sem
    # comprador declarado, é o próprio paciente (sinalizado explicitamente).
    story.append(Spacer(1, 0.2 * cm))
    _comp = dados["comprador"]
    story += secao("Comprador (portador)", [
        ("Nome",      _comp["nome"]),
        ("Documento", _comp["documento"]),
    ] + ([("Obs.", "Mesmo que o paciente")] if _comp["eh_paciente"] else []))

    story.append(Spacer(1, 0.2 * cm))
    # Toda quantidade sai com a unidade junto — "30 comprimidos", nunca "30".
    # formatar_quantidade é o caminho autoritativo: pluraliza e, sem unidade,
    # devolve "30 (unidade não informada)" — jamais inventa "unidade".
    _un = med.get("unidade_quantidade")
    _q_presc = med["quantidade_prescrita"]
    _q_disp = med["quantidade_dispensada"]
    story += secao("Medicamento", [
        ("Nome",          med["nome"]),
        ("Concentração",  med["concentracao"]),
        ("Posologia",     med["posologia"]),
        ("Qtd. prescrita",  formatar_quantidade(_q_presc, _un) if _q_presc is not None else "N/I"),
        ("Qtd. dispensada", formatar_quantidade(_q_disp, _un)),
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
# POST /dispensacoes/{id}/estornar — estorno como objeto sanitário DERIVADO (T2)
# ---------------------------------------------------------------------------
# TICKET-ESTORNO-OBJETO-DERIVADO.md (martelo Fabiano 2026-06-15). O estorno NÃO
# muta a dispensação nem o item: cria um objeto derivado imutável (`estornos`)
# que referencia a dispensação de origem e emite `estorno_registrado` no ledger
# da prescrição. A `dispensacoes` original permanece intocada (CLAUDE.md §1). O
# saldo efetivo do item passa a ser Σ dispensado − Σ estornado (reposto na
# leitura pelas queries de saldo — custodia.py, dispensadores.py, hospitalares.py).

class EstornarIn(BaseModel):
    motivo: str                              # enum MOTIVOS_ESTORNO
    quantidade: Optional[int] = None         # default = saldo remanescente da dispensação
    observacao: Optional[str] = None


@router.post("/{dispensacao_id}/estornar", status_code=201)
def estornar_dispensacao(
    dispensacao_id: int,
    payload: EstornarIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Estorna (reverte) uma dispensação registrada — cria o objeto derivado
    `estornos` e repõe o saldo efetivo do item. A dispensação de origem
    permanece imutável. Evento no ledger da prescrição: `estorno_registrado`.

    - Dispensador só estorna dispensação do próprio CNPJ (admin bypassa).
    - Nunca estorna mais do que o saldo remanescente da própria dispensação.
    - O item NÃO é mutado (a reversão vive no objeto-estorno).
    """
    if payload.motivo not in MOTIVOS_ESTORNO:
        raise HTTPException(
            status_code=422,
            detail={"codigo": "motivo_invalido",
                    "mensagem": f"motivo deve ser um de: {sorted(MOTIVOS_ESTORNO)}."},
        )

    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        instance_id = get_instance_id_conn(conn)

        # TICKET-CORE-R2 §3.1: trava a linha da dispensação de origem (FOR UPDATE
        # OF d na PG — só a tabela `dispensacoes`, não o JOIN inteiro) para
        # serializar estornos concorrentes da MESMA dispensação. A 2ª requisição
        # bloqueia até a 1ª commitar, relê o Σ estornado abaixo e a checagem de
        # remanescente rejeita o excedente — nunca grava 2 estornos duplicados.
        disp = conn.execute(
            """
            SELECT d.id, d.cnpj_estabelecimento, d.quantidade_dispensada,
                   i.id AS item_id, i.quantidade AS qtd_prescrita, i.status_item,
                   p.id AS prescricao_id, p.status AS status_prescricao, p.paciente_id
              FROM dispensacoes d
              JOIN prescricao_itens i ON i.id = d.prescricao_item_id
              JOIN prescricoes p       ON p.id = i.prescricao_id
             WHERE d.id = ?
            """
            + row_lock_suffix(of="d"),
            (dispensacao_id,),
        ).fetchone()
        if not disp:
            raise HTTPException(status_code=404, detail=f"Dispensação {dispensacao_id} não encontrada.")

        # Owner-check (espelha o comprovante): dispensador exige CNPJ; admin bypassa.
        if usuario["role"] == "dispensador" and normalize_cnpj(usuario["sub"]) != disp["cnpj_estabelecimento"]:
            raise HTTPException(
                status_code=403,
                detail={"codigo": "nao_e_dono_da_dispensacao",
                        "mensagem": "Esta dispensação foi realizada por outro estabelecimento."},
            )

        # Saldo remanescente DESTA dispensação — nunca estorna mais do que dispensou.
        ja_estornado = conn.execute(
            "SELECT COALESCE(SUM(quantidade_estornada), 0) AS total FROM estornos WHERE origem_dispensacao_id = ?",
            (dispensacao_id,),
        ).fetchone()["total"]
        remanescente = disp["quantidade_dispensada"] - ja_estornado
        if remanescente <= 0:
            raise HTTPException(status_code=409, detail="Dispensação já totalmente estornada.")

        qtd = payload.quantidade if payload.quantidade is not None else remanescente
        if qtd <= 0 or qtd > remanescente:
            raise HTTPException(
                status_code=422,
                detail=f"quantidade a estornar ({qtd}) inválida — remanescente desta dispensação: {remanescente}.",
            )

        # Objeto derivado imutável.
        protocolo = str(uuid.uuid4())
        cur = conn.execute(
            """
            INSERT INTO estornos
              (protocolo, origem_dispensacao_id, prescricao_item_id, prescricao_id,
               cnpj_estabelecimento, paciente_id, autor_tipo, autor_id,
               quantidade_estornada, motivo, assinatura_hash, data_emissao, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            """,
            (protocolo, dispensacao_id, disp["item_id"], disp["prescricao_id"],
             disp["cnpj_estabelecimento"], disp["paciente_id"], usuario["role"], usuario["sub"],
             qtd, payload.motivo, agora, agora),
        )
        estorno_id = cur.lastrowid

        # Evento no ledger da prescrição — reconciliável (T7).
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=disp["prescricao_id"],
            tipo_evento="estorno_registrado",
            instance_id=instance_id,
            payload={
                "estorno_id": estorno_id,
                "estorno_protocolo": protocolo,
                "origem_dispensacao_id": dispensacao_id,
                "item_id": disp["item_id"],
                "quantidade_estornada": qtd,
                "motivo": payload.motivo,
                "observacao": payload.observacao,
            },
            ator_tipo="dispensador",
            ator_id=usuario["sub"],
        )

        # Saldo efetivo do item = Σ dispensado − Σ estornado (o mesmo que as
        # queries de saldo passam a computar em custodia/dispensadores/hospitalares).
        disp_total = conn.execute(
            "SELECT COALESCE(SUM(quantidade_dispensada), 0) AS t FROM dispensacoes WHERE prescricao_item_id = ?",
            (disp["item_id"],),
        ).fetchone()["t"]
        est_total = conn.execute(
            "SELECT COALESCE(SUM(quantidade_estornada), 0) AS t FROM estornos WHERE prescricao_item_id = ?",
            (disp["item_id"],),
        ).fetchone()["t"]
        saldo_efetivo = (disp["qtd_prescrita"] or 0) - (disp_total - est_total)

        # TICKET-B0 §3.2: se o estorno repôs saldo e o item ficou SEM custódia
        # ativa (caso da dispensação total — custodia.py fecha a custódia ao
        # zerar o saldo), reabrir a custódia do item para o estabelecimento que
        # detinha a dispensação (retém o item de novo para re-dispensação) e
        # emitir `custodia_transferida` — retenção sem o evento é bug (CLAUDE.md
        # §2, invariante de retenção). No estorno PARCIAL o item seguia
        # `em_custodia` com custódia aberta → nada a reabrir (não duplica).
        # Reabrir custódia é evento de custódia legítimo, NÃO a transição
        # proibida dispensado→estornado nem edição da dispensação (o item não é
        # mutado — invariante do TICKET-ESTORNO preservado).
        custodia_reaberta = False
        if saldo_efetivo > 0:
            custodia_ativa = conn.execute(
                """
                SELECT 1 FROM prescricao_custodia
                 WHERE prescricao_id = ? AND item_id = ? AND encerrada_em IS NULL
                 LIMIT 1
                """,
                (disp["prescricao_id"], disp["item_id"]),
            ).fetchone()
            if not custodia_ativa:
                # Choke-point (COER-2): estorno repôs saldo e o item ficou SEM
                # custódia (a dispensação total fechou a do item) → re-retém p/ o
                # estabelecimento (re-dispensação). O _fechar interno é no-op aqui
                # (guardado por `if not custodia_ativa`); o helper garante o evento
                # custodia_transferida que a retenção exige (§2). `motivo` canônico
                # do caminho ('estorno_reposicao_saldo', §6.2) p/ o T6 separar.
                transferir_posse(
                    conn, disp["prescricao_id"], disp["item_id"],
                    "paciente", None, "dispensador", disp["cnpj_estabelecimento"],
                    "estorno_reposicao_saldo", agora,
                    ator_tipo="dispensador", ator_id=usuario["sub"], instance_id=instance_id,
                    extra_payload={"origem_estorno_protocolo": protocolo},
                )
                custodia_reaberta = True

        return {
            "estorno_id": estorno_id,
            "protocolo": protocolo,
            "origem_dispensacao_id": dispensacao_id,
            "item_id": disp["item_id"],
            "quantidade_estornada": qtd,
            "motivo": payload.motivo,
            "saldo_restante": saldo_efetivo,
            # item NÃO é mutado — objeto derivado (TICKET-ESTORNO-OBJETO-DERIVADO §1)
            "status_item": disp["status_item"],
            "status_prescricao": disp["status_prescricao"],
            # TICKET-B0 §3.2: custódia reaberta p/ re-dispensação (saldo reposto).
            "custodia_reaberta": custodia_reaberta,
        }
