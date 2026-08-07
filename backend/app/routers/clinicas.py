"""
routers/clinicas.py — relatórios do prestador clínica/laboratório (arco V2).

DESPACHO-ENG-008 (R3): a clínica/lab não tinha como extrair um relatório dos
exames sob sua responsabilidade. Só a farmácia tinha extração
(`/dispensadores/relatorio.{csv,pdf}` — escrituração SNGPC), e aquele router é
específico de farmácia.

Por que router novo e não mais um endpoint em `/dispensadores`: a clínica
compartilha o PAPEL (`dispensador`) mas não o DOMÍNIO — lá é medicamento e
Anvisa, aqui é exame e operação do prestador. O domínio clínica/lab tende a
crescer (R4 faturamento, TUSS, integrações), e acumulá-lo no router da farmácia
repetiria um custo que já se pagou uma vez.

Contrato deste módulo:
  - READ-ONLY. Nenhum INSERT/UPDATE/DELETE, nenhuma escrita no ledger.
  - Escopo = CNPJ do JWT, pela custódia ATUAL nível-pedido — a MESMA semântica
    de `_assert_dispensador_dono_pedido` (pedidos_exame.py). O `c.para = ?` não é
    um filtro de conveniência: é a guarda que faz o endpoint poder existir.
  - Papel `dispensador` apenas. Visão cross-establishment é do auditor, em
    `/relatorios/*` — não se mistura.
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.pdf_relatorio_exames import MAX_REGISTROS_PDF, gerar_pdf_exames
from app.utils.helpers import normalize_cnpj

router = APIRouter(prefix="/clinicas", tags=["clinicas"])


# Ordem do §2.4 do ENG-008 preservada; `nome_exame` e `paciente_nome` entram como
# INSERÇÕES, não como reordenação. Sem elas o relatório sai identificando o exame
# só por `codigo_tuss` — que é nullable e hoje vem vazio na maior parte da base:
# a clínica leria uma lista de protocolos sem saber de quem nem de quê.
CABECALHO_CSV = [
    "protocolo",
    "item_id",
    "nome_exame",         # + (ENG-008 §2.4 não pedia; ver nota acima)
    "codigo_tuss",
    "status_item",
    "data_coleta",
    "data_resultado",
    "data_agendamento",
    "paciente_nome",      # + (idem)
]


# ---------------------------------------------------------------------------
# Janela de período — espelha dispensadores.py:371-396
# ---------------------------------------------------------------------------

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
    """Sem filtros → últimos 30 dias. Devolve (dt_inicio, dt_fim, filtros)."""
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


# ---------------------------------------------------------------------------
# Leitura
# ---------------------------------------------------------------------------
# A custódia ATUAL nível-pedido é a de maior id (`item_id IS NULL`) — mesma regra
# de `_assert_dispensador_dono_pedido`. Um prestador que já custodiou e perdeu a
# custódia NÃO aparece no próprio relatório: o relatório mostra o que está sob
# responsabilidade agora, não o que já passou pela bancada.
#
# `data_coleta` vem do ledger (`pedido_coletado`) agregada POR PEDIDO: o schema
# não tem carimbo de coleta por item (`pedido_exame_itens` só guarda
# `resultado_em`). Num pedido com itens coletados em dias diferentes, a coluna
# repete a data da primeira coleta. Preferi a agregação honesta a extrair o
# `item_id` de dentro do `dados_json` — o que exigiria função JSON divergente
# entre SQLite e PostgreSQL num caminho meramente informativo. Fica registrado
# como lacuna de schema (ver PR do ENG-008).
_SQL_ITENS_DO_CNPJ = """
SELECT pe.protocolo               AS protocolo,
       pei.id                     AS item_id,
       pei.nome_exame             AS nome_exame,
       pei.codigo_tuss            AS codigo_tuss,
       pei.status_item            AS status_item,
       pei.resultado_em           AS data_resultado,
       pei.criado_em              AS item_criado_em,
       pa.nome                    AS paciente_nome,
       col.data_coleta            AS data_coleta,
       ag.data_agendamento        AS data_agendamento
  FROM pedido_exame_custodia c
  JOIN pedidos_exame       pe  ON pe.id  = c.pedido_id
  JOIN pedido_exame_itens  pei ON pei.pedido_id = c.pedido_id
  LEFT JOIN pacientes      pa  ON pa.id  = pe.paciente_id
  LEFT JOIN (
        SELECT pedido_id, MIN(criado_em) AS data_coleta
          FROM pedido_exame_eventos
         WHERE tipo_evento = 'pedido_coletado'
         GROUP BY pedido_id
  ) col ON col.pedido_id = c.pedido_id
  LEFT JOIN (
        SELECT pedido_id, MAX(data_hora) AS data_agendamento
          FROM agendamentos
         WHERE status <> 'cancelado'
         GROUP BY pedido_id
  ) ag ON ag.pedido_id = c.pedido_id
 WHERE c.item_id IS NULL
   AND c.id = (
        SELECT MAX(id) FROM pedido_exame_custodia
         WHERE pedido_id = c.pedido_id AND item_id IS NULL
   )
   AND c.para = ?
 ORDER BY pe.protocolo, pei.id
"""


def _linhas_do_cnpj(conn, cnpj: str) -> list[dict]:
    rows = conn.execute(_SQL_ITENS_DO_CNPJ, (cnpj,)).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def _como_datetime(valor) -> Optional[datetime]:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor
    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


def _data_referencia(linha: dict) -> Optional[datetime]:
    """Data pela qual o item entra (ou não) na janela do período.

    Do mais específico ao mais genérico: resultado → coleta → agendamento →
    criação do item. Um item ainda pendente entra pela criação — senão o exame
    recém-recebido sumiria do relatório de quem tem de executá-lo.
    """
    for chave in ("data_resultado", "data_coleta", "data_agendamento", "item_criado_em"):
        dt = _como_datetime(linha.get(chave))
        if dt is not None:
            return dt
    return None


def _filtrar_periodo(linhas: list[dict], dt_inicio, dt_fim) -> list[dict]:
    out = []
    for ln in linhas:
        ref = _data_referencia(ln)
        if ref is None:
            continue
        if dt_inicio and ref < dt_inicio:
            continue
        if dt_fim and ref > dt_fim:
            continue
        out.append(ln)
    return out


def _fmt(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, datetime):
        return valor.isoformat(timespec="seconds")
    return str(valor)


def _linha_csv(ln: dict) -> list[str]:
    return [
        _fmt(ln.get("protocolo")),
        _fmt(ln.get("item_id")),
        _fmt(ln.get("nome_exame")),
        _fmt(ln.get("codigo_tuss")),
        _fmt(ln.get("status_item")),
        _fmt(ln.get("data_coleta")),
        _fmt(ln.get("data_resultado")),
        _fmt(ln.get("data_agendamento")),
        _fmt(ln.get("paciente_nome")),
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/relatorio.csv", summary="Relatório de exames do prestador (CSV)")
def relatorio_exames_csv(
    usuario=Depends(require_role("dispensador")),
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    data_fim: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
):
    """CSV dos itens de exame sob custódia atual do próprio prestador.
    Escopo = CNPJ do JWT. Read-only."""
    cnpj = normalize_cnpj(usuario["sub"])
    dt_inicio, dt_fim, _ = _janela_periodo(data_inicio, data_fim)

    with get_tx() as conn:
        linhas = _linhas_do_cnpj(conn, cnpj)

    linhas = _filtrar_periodo(linhas, dt_inicio, dt_fim)

    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(CABECALHO_CSV)
    for ln in linhas:
        writer.writerow(_linha_csv(ln))
    buffer.seek(0)

    filename = f"relatorio_exames_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/relatorio.pdf", summary="Relatório de exames do prestador (PDF)")
def relatorio_exames_pdf(
    usuario=Depends(require_role("dispensador")),
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (padrão: 30 dias atrás)"),
    data_fim: Optional[str] = Query(None, description="YYYY-MM-DD (padrão: hoje)"),
):
    """PDF (A4 landscape) dos itens sob custódia atual do próprio prestador.
    Truncado em 1000 registros, com aviso VISÍVEL — nunca silencioso."""
    cnpj = normalize_cnpj(usuario["sub"])
    dt_inicio, dt_fim, filtros = _janela_periodo(data_inicio, data_fim)
    filtros["cnpj"] = cnpj

    with get_tx() as conn:
        linhas = _linhas_do_cnpj(conn, cnpj)

    linhas = _filtrar_periodo(linhas, dt_inicio, dt_fim)

    total_no_periodo = len(linhas)
    limitado = total_no_periodo > MAX_REGISTROS_PDF
    if limitado:
        linhas = linhas[:MAX_REGISTROS_PDF]

    pdf_bytes = gerar_pdf_exames(
        linhas=linhas,
        filtros=filtros,
        limitado=limitado,
        total_no_periodo=total_no_periodo if limitado else None,
    )

    filename = f"relatorio_exames_{date.today().isoformat()}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
