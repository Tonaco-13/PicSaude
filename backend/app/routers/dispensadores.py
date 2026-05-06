from typing import Optional

from fastapi import APIRouter, Query

from app.config import DEFAULT_LIMIT, MAX_LIMIT
from app.database import get_conn
from app.domain.cnes_prescritor import _get_cnes_conn
from app.utils.helpers import normalize_cnpj, normalize_nome

router = APIRouter(prefix="/dispensadores")


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
