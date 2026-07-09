from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import require_role
from app.config import DEFAULT_LIMIT, MAX_LIMIT
from app.database import get_conn
from app.database_tx import get_tx
from app.domain.cnes_prescritor import _get_cnes_conn
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
