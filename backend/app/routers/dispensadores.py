import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.config import DEFAULT_LIMIT, MAX_LIMIT
from app.database import get_conn
from app.database_tx import get_tx
from app.domain.cnes_prescritor import _get_cnes_conn
from app.domain import relatorio_sngpc as sngpc
from app.domain.pdf_relatorio_sngpc import gerar_pdf_sngpc
from app.utils.helpers import normalize_cnpj, normalize_nome

router = APIRouter(prefix="/dispensadores")

_CPF_NAO_IDENTIFICADO = "00000000000"


def _cpf_display(cpf: Optional[str]) -> str:
    """CPF sentinela (prescrição física sem identificação) nunca é cidadão real."""
    return "não identificado" if not cpf or cpf == _CPF_NAO_IDENTIFICADO else cpf


@router.get("/busca")
def busca(
    nome: Optional[str] = Query(None, min_length=3),
    cnpj: Optional[str] = Query(None, min_length=3),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    filters = ["e.TP_UNIDADE = '43'"]
    params: list = []

    if nome:
        filters.append("UPPER(COALESCE(NULLIF(TRIM(e.NO_FANTASIA), ''), e.NO_RAZAO_SOCIAL)) LIKE '%' || ? || '%'")
        params.append(normalize_nome(nome))

    if cnpj:
        cnpj_digits = "".join(c for c in cnpj if c.isdigit())
        filters.append("REPLACE(REPLACE(e.NU_CNPJ, '.', ''), '/', '') LIKE '%' || ? || '%'")
        params.append(cnpj_digits)

    where = " AND ".join(filters)
    params.append(limit)

    sql = f"""
    SELECT
      e.CO_CNES,
      e.NU_CNPJ,
      COALESCE(NULLIF(TRIM(e.NO_FANTASIA), ''), e.NO_RAZAO_SOCIAL) AS nome_exibicao,
      e.NO_RAZAO_SOCIAL,
      e.NO_FANTASIA,
      e.CO_MUNICIPIO_GESTOR,
      e.TP_UNIDADE
    FROM estabelecimentos_cnes e
    WHERE {where}
    ORDER BY nome_exibicao
    LIMIT ?
    """

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    conn = _get_cnes_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
        result = []
        for r in rows:
            row = dict(r)
            row["NU_CNPJ"] = normalize_cnpj(row.get("NU_CNPJ"))
            result.append(row)
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# T4 — Fila do dispensador (PLANO_DEMO_CIRCULACAO §5)
# ---------------------------------------------------------------------------
# Prescrições sob custódia ATIVA do CNPJ autenticado. É o que faz o balcão
# "ver as receitas chegarem" em vez de resolver token/protocolo na mão.
#
# Guardrail (Z AI, mantido): a query filtra pelo DETENTOR REAL na cadeia de
# custódia (prescricao_custodia ativa), nunca uma view sem máquina de estados.
# Polling no front basta para a demo.
#
# Classe `module`. Saldo efetivo = Σ dispensado − Σ estornado (T2): a query
# subtrai `estornos` para que a fila reflita o saldo reposto por um estorno.

@router.get("/fila")
def fila(
    usuario=Depends(require_role("dispensador", "admin")),
    cnpj: Optional[str] = Query(None, description="Só admin: filtra por CNPJ."),
):
    """Fila de dispensação: prescrições em custódia ativa do dispensador."""
    # Dispensador vê a própria fila (CNPJ do JWT). Admin pode informar ?cnpj=.
    if usuario["role"] == "dispensador":
        cnpj_alvo = normalize_cnpj(usuario["sub"])
    else:
        if not cnpj:
            raise HTTPException(
                status_code=422,
                detail={"codigo": "cnpj_obrigatorio_admin",
                        "mensagem": "admin deve informar ?cnpj= para consultar a fila."},
            )
        cnpj_alvo = normalize_cnpj(cnpj)

    with get_tx() as conn:
        prescricoes = conn.execute(
            """
            SELECT DISTINCT p.id, p.protocolo, p.status, p.data_emissao,
                   pac.nome AS paciente_nome, pac.cpf AS paciente_cpf,
                   pr.nome  AS prescritor_nome
              FROM prescricao_custodia c
              JOIN prescricoes p   ON p.id  = c.prescricao_id
              JOIN pacientes pac   ON pac.id = p.paciente_id
              JOIN prescritores pr ON pr.id  = p.prescritor_id
             WHERE c.detentor_tipo = 'dispensador'
               AND c.detentor_id   = ?
               AND c.encerrada_em IS NULL
             ORDER BY p.data_emissao DESC
            """,
            (cnpj_alvo,),
        ).fetchall()

        fila_out = []
        for p in prescricoes:
            itens = conn.execute(
                """
                SELECT i.id, i.nome_medicamento, i.concentracao, i.quantidade, i.status_item,
                       COALESCE((SELECT SUM(d.quantidade_dispensada)
                                   FROM dispensacoes d
                                  WHERE d.prescricao_item_id = i.id), 0)
                     - COALESCE((SELECT SUM(e.quantidade_estornada)
                                   FROM estornos e
                                  WHERE e.prescricao_item_id = i.id), 0) AS ja_dispensado
                  FROM prescricao_itens i
                 WHERE i.prescricao_id = ?
                 ORDER BY i.id
                """,
                (p["id"],),
            ).fetchall()

            itens_out = []
            for it in itens:
                prescrito = it["quantidade"] or 0
                ja = it["ja_dispensado"] or 0
                itens_out.append({
                    "item_id": it["id"],
                    "nome_medicamento": it["nome_medicamento"],
                    "concentracao": it["concentracao"],
                    "quantidade": prescrito,
                    "quantidade_dispensada": ja,
                    "saldo": prescrito - ja,
                    "status_item": it["status_item"],
                })

            fila_out.append({
                "protocolo": p["protocolo"],
                "status": p["status"],
                "data_emissao": p["data_emissao"],
                "paciente": {"nome": p["paciente_nome"], "cpf": _cpf_display(p["paciente_cpf"])},
                "prescritor": {"nome": p["prescritor_nome"]},
                "itens": itens_out,
            })

        return {"cnpj": cnpj_alvo, "total": len(fila_out), "fila": fila_out}


# ---------------------------------------------------------------------------
# T6 — Histórico de retenções desta unidade (PLANO_DEMO_CIRCULACAO §5)
# ---------------------------------------------------------------------------
# Prescrições em que ESTE estabelecimento dispensou ≥1 item, com dispensacao_id
# (para linkar comprovante e estorno), comprador (T5) e estorno por item.
#
# Check de Determinismo (Jules): toda leitura tem ORDER BY explícito. E o
# histórico é reconstruído a partir de `dispensacoes`/`estornos` — NÃO de
# `prescricao_custodia` — exatamente como recomendado no portão de core (a
# dívida do fetchone sem ORDER BY em custodia.py:766 fica fora deste caminho).

@router.get("/historico")
def historico(
    usuario=Depends(require_role("dispensador", "admin")),
    cnpj: Optional[str] = Query(None, description="Só admin: filtra por CNPJ."),
    limit: int = Query(100, ge=1, le=500),
):
    """Histórico de retenções: prescrições dispensadas por este estabelecimento."""
    if usuario["role"] == "dispensador":
        cnpj_alvo = normalize_cnpj(usuario["sub"])
    else:
        if not cnpj:
            raise HTTPException(
                status_code=422,
                detail={"codigo": "cnpj_obrigatorio_admin",
                        "mensagem": "admin deve informar ?cnpj= para consultar o histórico."},
            )
        cnpj_alvo = normalize_cnpj(cnpj)

    with get_tx() as conn:
        # Prescrições onde este CNPJ dispensou — ORDER BY determinístico.
        prescricoes = conn.execute(
            """
            SELECT p.id, p.protocolo, p.status,
                   pac.nome AS paciente_nome, pac.cpf AS paciente_cpf,
                   MAX(d.dispensado_em) AS ultima_dispensacao
              FROM dispensacoes d
              JOIN prescricao_itens i ON i.id = d.prescricao_item_id
              JOIN prescricoes p       ON p.id = i.prescricao_id
              JOIN pacientes pac       ON pac.id = p.paciente_id
             WHERE d.cnpj_estabelecimento = ?
             GROUP BY p.id, p.protocolo, p.status, pac.nome, pac.cpf
             ORDER BY MAX(d.dispensado_em) DESC, p.id DESC
             LIMIT ?
            """,
            (cnpj_alvo, limit),
        ).fetchall()

        historico_out = []
        for p in prescricoes:
            disps = conn.execute(
                """
                SELECT d.id AS dispensacao_id, d.prescricao_item_id AS item_id,
                       i.nome_medicamento, i.concentracao,
                       d.quantidade_dispensada, d.lote,
                       d.comprador_nome, d.comprador_documento,
                       COALESCE((SELECT SUM(e.quantidade_estornada) FROM estornos e
                                  WHERE e.origem_dispensacao_id = d.id), 0) AS quantidade_estornada
                  FROM dispensacoes d
                  JOIN prescricao_itens i ON i.id = d.prescricao_item_id
                 WHERE d.cnpj_estabelecimento = ? AND i.prescricao_id = ?
                 ORDER BY d.id
                """,
                (cnpj_alvo, p["id"]),
            ).fetchall()

            comprador_nome = None
            itens_out = []
            for d in disps:
                q_disp = d["quantidade_dispensada"] or 0
                q_est = d["quantidade_estornada"] or 0
                if d["comprador_nome"] and not comprador_nome:
                    comprador_nome = d["comprador_nome"]
                itens_out.append({
                    "dispensacao_id": d["dispensacao_id"],
                    "item_id": d["item_id"],
                    "nome_medicamento": d["nome_medicamento"],
                    "concentracao": d["concentracao"],
                    "quantidade_dispensada": q_disp,
                    "lote": d["lote"],
                    "comprador_nome": d["comprador_nome"],
                    "quantidade_estornada": q_est,
                    "estornado": q_est > 0 and q_est >= q_disp,
                })

            historico_out.append({
                "protocolo": p["protocolo"],
                "status": p["status"],
                "ultima_dispensacao": p["ultima_dispensacao"],
                "paciente": {"nome": p["paciente_nome"], "cpf": _cpf_display(p["paciente_cpf"])},
                # Comprador da unidade (T5) — fallback ao paciente no MVP.
                "comprador": {"nome": comprador_nome or p["paciente_nome"],
                              "eh_paciente": not comprador_nome},
                "itens_dispensados": itens_out,
            })

        return {"cnpj": cnpj_alvo, "total": len(historico_out), "historico": historico_out}


# ---------------------------------------------------------------------------
# TICKET-F5 — Relatório consolidado + escrituração SNGPC (Fatia A, `module`)
# ---------------------------------------------------------------------------
# Visão do DISPENSADOR: escrituração da própria farmácia, travada ao CNPJ do JWT
# (§2.2 — CNPJ nunca por query param). Distinta da visão do auditor
# (/relatorios/*, escopo global, pré-T2/T5 — ver DIVIDA-RELATORIO-AUDITOR).
#
# Escrituração POR MOVIMENTO (§2.3, CLAUDE.md §2): cada dispensação e cada estorno
# são 1 linha. Toda a lógica de unificação/saldo/ordenação vive em
# app/domain/relatorio_sngpc.py (pura, testável). READ-ONLY: nenhum INSERT/UPDATE
# em tabela clínica, nenhum evento novo no ledger.

_MAX_REGISTROS_PDF = 1000

# CNPJ do JWT → dispensações do estabelecimento. Sentinela de CPF excluída (§6a).
# Toda a PII (paciente/comprador/prescritor) atrás de require_role("dispensador").
_SQL_DISPENSACOES_MOV = """
SELECT
    d.id                    AS dispensacao_id,
    d.dispensado_em         AS data_movimento,
    d.prescricao_item_id    AS item_id,
    p.protocolo             AS protocolo_prescricao,
    i.nome_medicamento      AS medicamento,
    i.concentracao          AS dose,
    i.unidade_quantidade    AS unidade_quantidade,
    d.quantidade_dispensada AS quantidade,
    d.lote                  AS lote,
    d.fabricante            AS fabricante,
    pac.nome                AS paciente_nome,
    pac.cpf                 AS paciente_cpf,
    d.comprador_nome        AS comprador_nome,
    d.comprador_documento   AS comprador_documento,
    pr.nome                 AS prescritor_nome,
    pr.cns                  AS prescritor_cns,
    i.status_item           AS status_item
FROM dispensacoes d
JOIN prescricao_itens i ON i.id  = d.prescricao_item_id
JOIN prescricoes p      ON p.id  = i.prescricao_id
JOIN pacientes pac      ON pac.id = p.paciente_id
JOIN prescritores pr    ON pr.id  = p.prescritor_id
WHERE d.cnpj_estabelecimento = ?
  AND pac.cpf != ?
"""

# Estornos do estabelecimento. lote/fabricante/comprador vêm da dispensação de
# origem (JOIN em origem_dispensacao_id). `dispensacao_id` da linha = origem (§3).
_SQL_ESTORNOS_MOV = """
SELECT
    e.origem_dispensacao_id AS dispensacao_id,
    e.protocolo             AS estorno_protocolo,
    e.criado_em             AS data_movimento,
    e.prescricao_item_id    AS item_id,
    p.protocolo             AS protocolo_prescricao,
    i.nome_medicamento      AS medicamento,
    i.concentracao          AS dose,
    i.unidade_quantidade    AS unidade_quantidade,
    e.quantidade_estornada  AS quantidade,
    d.lote                  AS lote,
    d.fabricante            AS fabricante,
    pac.nome                AS paciente_nome,
    pac.cpf                 AS paciente_cpf,
    d.comprador_nome        AS comprador_nome,
    d.comprador_documento   AS comprador_documento,
    pr.nome                 AS prescritor_nome,
    pr.cns                  AS prescritor_cns,
    e.motivo                AS motivo_estorno,
    i.status_item           AS status_item,
    e.id                    AS estorno_id
FROM estornos e
JOIN dispensacoes d     ON d.id  = e.origem_dispensacao_id
JOIN prescricao_itens i ON i.id  = e.prescricao_item_id
JOIN prescricoes p      ON p.id  = e.prescricao_id
JOIN pacientes pac      ON pac.id = p.paciente_id
JOIN prescritores pr    ON pr.id  = p.prescritor_id
WHERE e.cnpj_estabelecimento = ?
  AND pac.cpf != ?
"""


def _parse_dia(valor: Optional[str], campo: str) -> Optional[date]:
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail={"codigo": "data_invalida",
                    "mensagem": f"{campo} deve estar no formato YYYY-MM-DD."},
        )


def _janela_periodo(data_inicio: Optional[str], data_fim: Optional[str]):
    """Resolve a janela de exibição. Sem filtros → últimos 30 dias (§3 contrato).
    Retorna (dt_inicio 00:00:00, dt_fim 23:59:59, filtros_str) para corte/cabeçalho."""
    di = _parse_dia(data_inicio, "data_inicio")
    df = _parse_dia(data_fim, "data_fim")
    if di is None and df is None:
        df = date.today()
        di = df - timedelta(days=30)
    dt_inicio = datetime.combine(di, datetime.min.time()) if di else None
    dt_fim = datetime.combine(df, datetime.max.time().replace(microsecond=0)) if df else None
    filtros = {"data_inicio": di.isoformat() if di else None,
               "data_fim": df.isoformat() if df else None}
    return dt_inicio, dt_fim, filtros


def _movimentos_do_cnpj(conn, cnpj: str) -> list[dict]:
    """Constrói os movimentos (com saldo corrido por corte temporal) do CNPJ.
    Saldo calculado sobre TODO o histórico do estabelecimento; o filtro de período
    é aplicado só na exibição (mantém o período fechado estável — §5.9)."""
    disp_rows = conn.execute(
        _SQL_DISPENSACOES_MOV, (cnpj, _CPF_NAO_IDENTIFICADO)
    ).fetchall()
    est_rows = conn.execute(
        _SQL_ESTORNOS_MOV, (cnpj, _CPF_NAO_IDENTIFICADO)
    ).fetchall()
    return sngpc.construir_movimentos(disp_rows, est_rows)


@router.get("/relatorio.csv", summary="Escrituração SNGPC (CSV) do dispensador")
def relatorio_csv(
    usuario=Depends(require_role("dispensador")),
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    data_fim: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
):
    """CSV por movimento (dispensação|estorno) da própria farmácia. Escopo = CNPJ
    do JWT. Sentinela de CPF excluída. Sem endereço em nenhuma coluna (§2.4)."""
    cnpj = normalize_cnpj(usuario["sub"])
    dt_inicio, dt_fim, _ = _janela_periodo(data_inicio, data_fim)

    with get_tx() as conn:
        movs = _movimentos_do_cnpj(conn, cnpj)

    movs = sngpc.ordenar_exibicao(sngpc.filtrar_periodo(movs, dt_inicio, dt_fim))

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(sngpc.CABECALHO_CSV)
    for m in movs:
        writer.writerow(sngpc.linha_csv(m))
    buffer.seek(0)

    filename = f"dispensacoes_sngpc_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/relatorio.pdf", summary="Relatório consolidado (PDF) do dispensador")
def relatorio_pdf(
    usuario=Depends(require_role("dispensador")),
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (padrão: 30 dias atrás)"),
    data_fim: Optional[str] = Query(None, description="YYYY-MM-DD (padrão: hoje)"),
):
    """PDF consolidado (A4 landscape) da própria farmácia. Limitado a 1000
    registros — acima disso, aviso VISÍVEL de truncamento no documento (§5.8)."""
    cnpj = normalize_cnpj(usuario["sub"])
    dt_inicio, dt_fim, filtros = _janela_periodo(data_inicio, data_fim)
    filtros["cnpj"] = normalize_cnpj(cnpj)

    with get_tx() as conn:
        movs = _movimentos_do_cnpj(conn, cnpj)

    movs = sngpc.ordenar_exibicao(sngpc.filtrar_periodo(movs, dt_inicio, dt_fim))

    total_no_periodo = len(movs)
    limitado = total_no_periodo > _MAX_REGISTROS_PDF
    if limitado:
        movs = movs[:_MAX_REGISTROS_PDF]

    pdf_bytes = gerar_pdf_sngpc(
        movimentos=movs,
        filtros=filtros,
        limitado=limitado,
        total_no_periodo=total_no_periodo if limitado else None,
    )

    filename = f"relatorio_dispensacoes_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
