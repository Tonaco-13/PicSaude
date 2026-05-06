from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.config import DEFAULT_LIMIT, MAX_LIMIT
from app.database import get_conn
from app.domain.cnes_prescritor import _get_cnes_conn
from app.utils.helpers import (
    cbo_where_clause,
    normalize_cns,
    normalize_nome,
    vinculo_ativo_where_clause,
)

router = APIRouter()


@router.get("/busca")
def busca(
    nome: str = Query(..., min_length=3),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
):
    q = normalize_nome(nome)

    sql = f"""
    SELECT
      CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) AS cns,
      p.NO_PROFISSIONAL AS nome,
      COUNT(*) AS qtd_vinculos_ativos
    FROM profissionais_cnes p
    JOIN relacao_prof_estab r
      ON r.CO_PROFISSIONAL_SUS = p.CO_PROFISSIONAL_SUS
    LEFT JOIN estabelecimentos_cnes e
      ON e.CO_UNIDADE = r.CO_UNIDADE
    WHERE
      {vinculo_ativo_where_clause()}
      AND (r.CO_CBO LIKE '225%' OR r.CO_CBO LIKE '2232%')
      AND UPPER(p.NO_PROFISSIONAL) LIKE '%' || ? || '%'
    GROUP BY cns, nome
    ORDER BY nome
    LIMIT ?
    """

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    conn = _get_cnes_conn()
    try:
        rows = conn.execute(sql, (q, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/profissional/{cns}")
def profissional(cns: str):
    cns_n = normalize_cns(cns)

    sql = f"""
    SELECT
      CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) AS cns,
      p.NO_PROFISSIONAL AS nome,
      r.CO_CBO AS cbo,
      e.CO_CNES AS cnes,
      e.NO_FANTASIA AS estabelecimento,
      e.CO_MUNICIPIO_GESTOR AS municipio_ibge
    FROM relacao_prof_estab r
    JOIN profissionais p
      ON p.CO_PROFISSIONAL_SUS = r.CO_PROFISSIONAL_SUS
    JOIN estabelecimentos e
      ON e.CO_UNIDADE = r.CO_UNIDADE
    WHERE
      {vinculo_ativo_where_clause()}
      AND {cbo_where_clause()}
      AND CAST(CAST(p.CO_CNS AS INTEGER) AS TEXT) = ?
    ORDER BY e.NO_FANTASIA
    """

    # CNES: consulta via SQLite dedicado (_get_cnes_conn) — ver docs/arquitetura_dual_bancos.md
    conn = _get_cnes_conn()
    try:
        rows = conn.execute(sql, (cns_n,)).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="Profissional não encontrado")

        first = rows[0]

        return {
            "cns": first["cns"],
            "nome": first["nome"],
            "vinculos_ativos": [
                {
                    "cnes": r["cnes"],
                    "estabelecimento": r["estabelecimento"],
                    "cbo": r["cbo"],
                    "municipio_ibge": r["municipio_ibge"],
                }
                for r in rows
            ],
        }
    finally:
        conn.close()
