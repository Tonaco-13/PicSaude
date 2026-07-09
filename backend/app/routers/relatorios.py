"""
relatorios.py
=============
Relatórios exportáveis do PicSaúde para auditoria sanitária e fiscalização.

SEGURANÇA:
  Este endpoint retorna dados pessoais (nome + CPF de pacientes).
  TODO: proteger com perfil gestor/auditor quando autenticação for implementada.
  Por ora: disponível apenas em ambiente local (CORS restrito a 127.0.0.1).

Endpoints:
  GET /relatorios/dispensacoes.csv
      ?data_inicio=YYYY-MM-DD   (opcional)
      ?data_fim=YYYY-MM-DD      (opcional)

Adaptações em relação ao schema atual:
  - apresentacao    → coluna não existe em prescricao_itens; omitida
  - fabricacao      → coluna não existe em dispensacoes; substituída por fabricante
  - validade        → coluna não existe em dispensacoes; omitida
  - comprador_*     → tabela separada não existe; comprador = paciente (MVP)
  - Sentinela CPF '00000000000' excluída do relatório analítico
"""

from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.pdf_relatorio_dispensacoes import gerar_pdf_dispensacoes
from app.utils.helpers import normalize_cnpj

router = APIRouter(prefix="/relatorios", tags=["relatorios"])

# CPF sentinela: não é um cidadão real — excluir de relatórios analíticos
_CPF_NAO_IDENTIFICADO = "00000000000"


def _cnpj_escopo(usuario: dict, cnpj_param: Optional[str]) -> Optional[str]:
    """Escopo institucional do relatório (CLAUDE.md §6b — guardrail de `org_id`).

    O dispensador só pode enxergar as PRÓPRIAS dispensações: o CNPJ é FORÇADO
    ao do JWT (`sub`), ignorando qualquer valor recebido na query — um
    dispensador nunca consegue ler o relatório de outro estabelecimento.
    Auditor/admin filtram livremente (ou veem tudo, quando nenhum CNPJ é dado).

    Retorna o CNPJ normalizado a aplicar em `WHERE d.cnpj_estabelecimento = ?`,
    ou None quando não há filtro (auditor/admin sem CNPJ informado).
    """
    if usuario["role"] == "dispensador":
        return normalize_cnpj(usuario["sub"])
    return normalize_cnpj(cnpj_param) if cnpj_param else None


# ---------------------------------------------------------------------------
# Query principal — mesma base de dados do comprovante, garantindo consistência
# ---------------------------------------------------------------------------

_SQL_BASE = """
SELECT
    d.id                            AS dispensacao_id,
    p.protocolo                     AS protocolo_prescricao,
    d.dispensado_em                 AS data_dispensacao,

    i.nome_medicamento              AS medicamento,
    i.concentracao                  AS dose,
    i.quantidade                    AS quantidade_prescrita,
    d.quantidade_dispensada,
    i.unidade_quantidade,

    d.lote,
    d.fabricante,

    pac.nome                        AS paciente_nome,
    pac.cpf                         AS paciente_cpf,

    pr.nome                         AS prescritor_nome,
    pr.cns                          AS prescritor_cns,

    COALESCE(
        e.nome_fantasia,
        e.razao_social,
        'CNPJ ' || d.cnpj_estabelecimento
    )                               AS estabelecimento_nome,
    d.cnpj_estabelecimento          AS estabelecimento_cnpj,

    p.status                        AS status_prescricao,
    i.status_item,
    p.tipo_emissao

FROM dispensacoes d
JOIN prescricao_itens i
    ON i.id = d.prescricao_item_id
JOIN prescricoes p
    ON p.id = i.prescricao_id
JOIN pacientes pac
    ON pac.id = p.paciente_id
JOIN prescritores pr
    ON pr.id = p.prescritor_id
LEFT JOIN estabelecimentos_proprios e
    ON e.cnpj = d.cnpj_estabelecimento

WHERE pac.cpf != ?
"""

_CABECALHO = [
    "dispensacao_id",
    "protocolo_prescricao",
    "data_dispensacao",
    "medicamento",
    "dose",
    "quantidade_prescrita",
    "quantidade_dispensada",
    "lote",
    "fabricante",
    "paciente_nome",
    "paciente_cpf",
    "comprador_nome",       # MVP: igual ao paciente (sem tabela dedicada ainda)
    "comprador_cpf",        # MVP: igual ao paciente
    "prescritor_nome",
    "prescritor_cns",
    "estabelecimento_nome",
    "estabelecimento_cnpj",
    "status_prescricao",
    "status_item",
    "tipo_emissao",
]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/dispensacoes.csv", summary="Relatório CSV de dispensações para auditoria")
def relatorio_dispensacoes(
    data_inicio: Optional[str] = Query(
        default=None,
        description="Data inicial no formato YYYY-MM-DD (inclusive)",
    ),
    data_fim: Optional[str] = Query(
        default=None,
        description="Data final no formato YYYY-MM-DD (inclusive)",
    ),
    cnpj_estabelecimento: Optional[str] = Query(
        default=None,
        description="Filtrar por CNPJ do estabelecimento (auditor/admin). "
                    "Ignorado para dispensador — sempre travado ao próprio CNPJ.",
    ),
    usuario=Depends(require_role("auditor", "admin", "dispensador")),
):
    """
    Exporta relatório CSV de dispensações.

    - Retorna todas as dispensações por padrão (auditor/admin).
    - Filtrar por período com `data_inicio` e/ou `data_fim`.
    - CPF sentinela `00000000000` excluído automaticamente.
    - Comprador = Paciente no MVP (tabela de comprador ainda não implementada).

    **SEGURANÇA:** requer JWT `auditor`, `admin` ou `dispensador`. O dispensador
    só enxerga as próprias dispensações (escopo por CNPJ forçado — CLAUDE.md §6b).
    """
    sql    = _SQL_BASE
    params: list = [_CPF_NAO_IDENTIFICADO]

    # Escopo institucional (CLAUDE.md §6b): dispensador travado ao próprio CNPJ.
    _cnpj = _cnpj_escopo(usuario, cnpj_estabelecimento)
    if _cnpj:
        sql += " AND d.cnpj_estabelecimento = ?"
        params.append(_cnpj)

    if data_inicio:
        sql += " AND d.dispensado_em >= ?"
        params.append(f"{data_inicio}T00:00:00")

    if data_fim:
        sql += " AND d.dispensado_em <= ?"
        params.append(f"{data_fim}T23:59:59")

    sql += " ORDER BY d.dispensado_em DESC"

    with get_tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    # Gerar CSV em memória — sem arquivo temporário em disco
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(_CABECALHO)

    for r in rows:
        writer.writerow([
            r["dispensacao_id"],
            r["protocolo_prescricao"],
            r["data_dispensacao"]      or "",
            r["medicamento"],
            r["dose"]                  or "",
            r["quantidade_prescrita"]  or "",
            r["quantidade_dispensada"],
            r["lote"]                  or "",
            r["fabricante"]            or "",
            r["paciente_nome"],
            r["paciente_cpf"],
            r["paciente_nome"],        # comprador_nome = paciente (MVP)
            r["paciente_cpf"],         # comprador_cpf  = paciente (MVP)
            r["prescritor_nome"],
            r["prescritor_cns"],
            r["estabelecimento_nome"],
            r["estabelecimento_cnpj"],
            r["status_prescricao"],
            r["status_item"],
            r["tipo_emissao"],
        ])

    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="dispensacoes.csv"',
        },
    )


# ---------------------------------------------------------------------------
# GET /relatorios/dispensacoes.pdf — relatório institucional para auditoria
# ---------------------------------------------------------------------------

_MAX_REGISTROS_PDF = 1000


@router.get("/dispensacoes.pdf", summary="Relatório PDF de dispensações para auditoria sanitária")
def relatorio_dispensacoes_pdf(
    data_inicio: Optional[str] = Query(
        default=None,
        description="Data inicial YYYY-MM-DD (padrão: 30 dias atrás)",
    ),
    data_fim: Optional[str] = Query(
        default=None,
        description="Data final YYYY-MM-DD (padrão: hoje)",
    ),
    cnpj_estabelecimento: Optional[str] = Query(
        default=None,
        description="Filtrar por CNPJ do estabelecimento dispensador",
    ),
    medicamento: Optional[str] = Query(
        default=None,
        description="Filtrar por nome do medicamento (busca parcial, case-insensitive)",
    ),
    usuario=Depends(require_role("auditor", "admin", "dispensador")),
):
    """
    Exporta relatório PDF de dispensações.

    - A4 landscape, 14 colunas, fonte 6.5pt.
    - Limitado a 1 000 registros; use o CSV para exportação completa.
    - CPF sentinela `00000000000` substituído por 'Não identificado'.
    - Sem filtro de período: retorna os últimos 30 dias.

    **SEGURANÇA:** requer JWT `auditor`, `admin` ou `dispensador`. O dispensador
    só enxerga as próprias dispensações (escopo por CNPJ forçado — CLAUDE.md §6b).
    """
    from datetime import date, timedelta

    # Período padrão: últimos 30 dias
    _data_inicio = data_inicio or (date.today() - timedelta(days=30)).isoformat()
    _data_fim    = data_fim    or date.today().isoformat()

    sql    = _SQL_BASE
    params: list = [_CPF_NAO_IDENTIFICADO]

    sql += " AND d.dispensado_em >= ?"
    params.append(f"{_data_inicio}T00:00:00")
    sql += " AND d.dispensado_em <= ?"
    params.append(f"{_data_fim}T23:59:59")

    # Escopo institucional (CLAUDE.md §6b): dispensador travado ao próprio CNPJ.
    _cnpj = _cnpj_escopo(usuario, cnpj_estabelecimento)
    if _cnpj:
        sql += " AND d.cnpj_estabelecimento = ?"
        params.append(_cnpj)

    if medicamento:
        sql += " AND LOWER(i.nome_medicamento) LIKE ?"
        params.append(f"%{medicamento.lower()}%")

    sql += f" ORDER BY d.dispensado_em DESC LIMIT {_MAX_REGISTROS_PDF + 1}"

    with get_tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    limitado = len(rows) > _MAX_REGISTROS_PDF
    if limitado:
        rows = rows[:_MAX_REGISTROS_PDF]

    filtros = {
        "data_inicio":          _data_inicio,
        "data_fim":             _data_fim,
        # CNPJ efetivamente aplicado (para dispensador = o próprio, forçado).
        "cnpj_estabelecimento": _cnpj,
        "medicamento":          medicamento,
    }

    pdf_bytes = gerar_pdf_dispensacoes(
        rows=[dict(r) for r in rows],
        filtros=filtros,
        limitado=limitado,
    )

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="relatorio_dispensacoes.pdf"',
        },
    )
