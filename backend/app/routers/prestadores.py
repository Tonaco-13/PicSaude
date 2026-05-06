"""
routers/prestadores.py
======================
Módulo de Prestadores — identidade formal de org_id / unidade_id (Ticket 30).

Endpoints:
  POST   /prestadores                              — criar prestador
  GET    /prestadores                              — listar prestadores
  GET    /prestadores/{org_id}                     — obter prestador
  POST   /prestadores/{org_id}/unidades            — criar unidade
  GET    /prestadores/{org_id}/unidades            — listar unidades do prestador
  GET    /prestadores/{org_id}/unidades/{unidade_id} — obter unidade

Todos os endpoints exigem role=admin.

Regras de domínio:
  - org_id é UNIQUE e imutável após criação.
  - unidade_id é UNIQUE dentro do mesmo prestador.
  - Mesma unidade_id em prestadores diferentes é permitido.
  - Deleção lógica apenas (campo ativo=0).
  - Tipos válidos de prestador (dispensador): farmacia | hospital | usf
  - Tipos válidos de prestador (laboratório): laboratorio
  - Tipos válidos de prestador (outros):      clinica
  - Tipos válidos de unidade:  ambulatorio | enfermaria | laboratorio | farmacia | administrativo | usf
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.database_tx import get_tx

router = APIRouter(prefix="/prestadores", tags=["prestadores"])

# Subconjuntos nomeados por domínio operacional (Ticket 60 — R2)
_TIPOS_DISPENSADOR = frozenset({"farmacia", "hospital", "usf"})
_TIPOS_LABORATORIO = frozenset({"laboratorio"})
_TIPOS_PRESTADOR   = _TIPOS_DISPENSADOR | _TIPOS_LABORATORIO | {"clinica"}
_TIPOS_UNIDADE     = frozenset({"ambulatorio", "enfermaria", "laboratorio", "farmacia", "administrativo", "usf"})


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PrestadorIn(BaseModel):
    org_id: str
    nome:   str
    tipo:   str
    cnpj:   Optional[str] = None


class UnidadeIn(BaseModel):
    unidade_id: str
    nome:       str
    tipo:       Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prestador_ou_404(conn, org_id: str) -> dict:
    row = conn.execute(
        "SELECT id, org_id, nome, tipo, cnpj, ativo, criado_em FROM prestadores WHERE org_id = ?",
        (org_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Prestador '{org_id}' não encontrado.")
    return dict(row)


# ---------------------------------------------------------------------------
# POST /prestadores  — criar prestador
# ---------------------------------------------------------------------------

@router.post("", status_code=201, summary="Criar prestador")
def criar_prestador(body: PrestadorIn, _=Depends(require_role("admin"))):
    org_id = body.org_id.strip()
    nome   = body.nome.strip()
    tipo   = body.tipo.strip().lower()

    if not org_id:
        raise HTTPException(status_code=422, detail="org_id não pode ser vazio.")
    if not nome:
        raise HTTPException(status_code=422, detail="nome não pode ser vazio.")
    if tipo not in _TIPOS_PRESTADOR:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido: '{tipo}'. Permitidos: {sorted(_TIPOS_PRESTADOR)}",
        )

    cnpj = body.cnpj.strip() if body.cnpj else None

    prestador_id = str(uuid.uuid4())
    agora = _agora()

    with get_tx() as conn:
        existente = conn.execute(
            "SELECT id FROM prestadores WHERE org_id = ?", (org_id,)
        ).fetchone()
        if existente:
            raise HTTPException(
                status_code=409,
                detail=f"org_id '{org_id}' já cadastrado.",
            )

        conn.execute(
            """
            INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?, true, ?)
            """,
            (prestador_id, org_id, nome, tipo, cnpj, agora),
        )

    return {
        "ok":          True,
        "id":          prestador_id,
        "org_id":      org_id,
        "nome":        nome,
        "tipo":        tipo,
        "cnpj":        cnpj,
        "ativo":       True,
        "criado_em":   agora,
    }


# ---------------------------------------------------------------------------
# GET /prestadores/buscar  — busca institucional (dispensador + admin)
# ---------------------------------------------------------------------------

# Tipos CNES por módulo — filtro de segurança (Tratamento 1)
TP_UNIDADE_DISPENSADOR = {"04", "40", "70", "71"}   # farmácias
TP_UNIDADE_CLINICA     = {"01", "02", "05", "36", "39", "43", "15", "20", "21"}  # clínicas/labs/UBS

# Mapeamento de TP_UNIDADE → descrição legível
_TP_UNIDADE_DESC = {
    "01": "Posto de Saúde",
    "02": "Centro de Saúde / Unidade Básica",
    "04": "Farmácia",
    "05": "Hospital Geral",
    "15": "Unidade Mista",
    "20": "Pronto Socorro Geral",
    "21": "Pronto Socorro Especializado",
    "36": "Clínica / Centro de Especialidade",
    "39": "Unidade de Apoio Diagnose e Terapia (SADT Isolado)",
    "40": "Farmácia Hospitalar",
    "43": "Laboratório de Saúde Pública",
    "70": "Farmácia Básica",
    "71": "Farmácia Especializada",
}


@router.get("/buscar-cnes", summary="Busca no CNES bruto por módulo (público, filtrado por tipo)")
def buscar_cnes_bruto(
    q: str = "",
    modulo: str = "dispensador",
):
    """
    Busca estabelecimentos diretamente em `estabelecimentos_cnes` (base DataSUS),
    filtrando por TP_UNIDADE conforme o módulo:
      - modulo=dispensador → apenas farmácias (04, 40, 70, 71)
      - modulo=clinica     → clínicas, labs, UBS (01, 02, 05, 36, 39, 43...)

    Endpoint público — dados equivalentes ao CNES público. Retorna apenas
    campos necessários para identificação (sem org_id interno).
    """
    tipos = TP_UNIDADE_DISPENSADOR if modulo == "dispensador" else TP_UNIDADE_CLINICA
    q_norm = q.strip().lower()
    cnpj_q = "".join(c for c in q_norm if c.isdigit())

    placeholders = ", ".join("?" * len(tipos))
    with get_tx() as conn:
        if q_norm:
            rows = conn.execute(
                f"""
                SELECT CO_CNES, NO_RAZAO_SOCIAL, NO_FANTASIA, NU_CNPJ,
                       TP_UNIDADE, CO_ESTADO_GESTOR, CO_MUNICIPIO_GESTOR,
                       NO_LOGRADOURO, NO_BAIRRO, CO_CEP
                FROM estabelecimentos_cnes
                WHERE TP_UNIDADE IN ({placeholders})
                  AND (
                    LOWER(NO_RAZAO_SOCIAL) LIKE ?
                    OR LOWER(NO_FANTASIA)  LIKE ?
                    OR NU_CNPJ LIKE ?
                  )
                ORDER BY NO_RAZAO_SOCIAL ASC
                LIMIT 20
                """,
                (*tipos, f"%{q_norm}%", f"%{q_norm}%", f"%{cnpj_q}%"),
            ).fetchall()
        else:
            rows = []

    result = [
        {
            "co_cnes":    r["CO_CNES"],
            "nome":       r["NO_FANTASIA"] or r["NO_RAZAO_SOCIAL"],
            "razao_social": r["NO_RAZAO_SOCIAL"],
            "cnpj":       r["NU_CNPJ"],
            "tipo":       _TP_UNIDADE_DESC.get(r["TP_UNIDADE"], r["TP_UNIDADE"]),
            "tp_unidade": r["TP_UNIDADE"],
            "uf":         r["CO_ESTADO_GESTOR"],
            "municipio":  r["CO_MUNICIPIO_GESTOR"],
            "endereco":   ", ".join(filter(None, [r["NO_LOGRADOURO"], r["NO_BAIRRO"]])),
            "cnes_verificado": True,
        }
        for r in rows
    ]

    return {"estabelecimentos": result, "total": len(result)}


@router.get("/buscar", summary="Busca institucional por nome, CNPJ ou org_id")
def buscar_prestadores(
    q: str = "",
    _=Depends(require_role("dispensador", "admin")),
):
    """
    Busca leve de prestadores por nome, CNPJ ou org_id — parcial, case-insensitive.
    Retorna até 20 resultados com as unidades vinculadas.

    Endpoint autenticado (Tratamento 5): exige role=dispensador ou admin.
    Pré-login usa /buscar-cnes (CNES bruto, público, filtrado por TP_UNIDADE).
    """
    q_lower = q.strip().lower()
    with get_tx() as conn:
        if q_lower:
            rows = conn.execute(
                """
                SELECT id, org_id, nome, tipo, cnpj
                FROM prestadores
                WHERE ativo = true
                  AND (
                    LOWER(nome)   LIKE ?
                    OR LOWER(cnpj)   LIKE ?
                    OR LOWER(org_id) LIKE ?
                  )
                ORDER BY nome ASC
                LIMIT 20
                """,
                (f"%{q_lower}%", f"%{q_lower}%", f"%{q_lower}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, org_id, nome, tipo, cnpj FROM prestadores WHERE ativo = true ORDER BY nome ASC LIMIT 20"
            ).fetchall()

        result = []
        for r in rows:
            unidades = conn.execute(
                """
                SELECT unidade_id, nome, tipo
                FROM unidades
                WHERE prestador_id = ? AND ativo = true
                ORDER BY criado_em ASC
                """,
                (r["id"],),
            ).fetchall()
            result.append({
                "org_id":   r["org_id"],
                "nome":     r["nome"],
                "tipo":     r["tipo"],
                "cnpj":     r["cnpj"],
                "unidades": [dict(u) for u in unidades],
            })

    return {"prestadores": result, "total": len(result)}


# ---------------------------------------------------------------------------
# GET /prestadores  — listar prestadores
# ---------------------------------------------------------------------------

@router.get("", summary="Listar prestadores")
def listar_prestadores(_=Depends(require_role("admin"))):
    with get_tx() as conn:
        rows = conn.execute(
            "SELECT id, org_id, nome, tipo, cnpj, ativo, criado_em FROM prestadores ORDER BY criado_em DESC"
        ).fetchall()
    return {"prestadores": [dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# GET /prestadores/{org_id}  — obter prestador
# ---------------------------------------------------------------------------

@router.get("/{org_id}", summary="Obter prestador por org_id")
def obter_prestador(org_id: str, _=Depends(require_role("admin"))):
    with get_tx() as conn:
        prestador = _prestador_ou_404(conn, org_id)
    return prestador


# ---------------------------------------------------------------------------
# POST /prestadores/{org_id}/unidades  — criar unidade
# ---------------------------------------------------------------------------

@router.post("/{org_id}/unidades", status_code=201, summary="Criar unidade")
def criar_unidade(org_id: str, body: UnidadeIn, _=Depends(require_role("admin"))):
    unidade_id = body.unidade_id.strip()
    nome       = body.nome.strip()
    tipo       = body.tipo.strip().lower() if body.tipo else None

    if not unidade_id:
        raise HTTPException(status_code=422, detail="unidade_id não pode ser vazio.")
    if not nome:
        raise HTTPException(status_code=422, detail="nome não pode ser vazio.")
    if tipo and tipo not in _TIPOS_UNIDADE:
        raise HTTPException(
            status_code=422,
            detail=f"Tipo inválido: '{tipo}'. Permitidos: {sorted(_TIPOS_UNIDADE)}",
        )

    uid = str(uuid.uuid4())
    agora = _agora()

    with get_tx() as conn:
        prestador = _prestador_ou_404(conn, org_id)

        existente = conn.execute(
            "SELECT id FROM unidades WHERE prestador_id = ? AND unidade_id = ?",
            (prestador["id"], unidade_id),
        ).fetchone()
        if existente:
            raise HTTPException(
                status_code=409,
                detail=f"unidade_id '{unidade_id}' já existe no prestador '{org_id}'.",
            )

        conn.execute(
            """
            INSERT INTO unidades (id, prestador_id, unidade_id, nome, tipo, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (uid, prestador["id"], unidade_id, nome, tipo, agora),
        )

    return {
        "ok":           True,
        "id":           uid,
        "prestador_org_id": org_id,
        "unidade_id":   unidade_id,
        "nome":         nome,
        "tipo":         tipo,
        "ativo":        True,
        "criado_em":    agora,
    }


# ---------------------------------------------------------------------------
# GET /prestadores/{org_id}/unidades  — listar unidades
# ---------------------------------------------------------------------------

@router.get("/{org_id}/unidades", summary="Listar unidades do prestador")
def listar_unidades(org_id: str, _=Depends(require_role("admin"))):
    with get_tx() as conn:
        prestador = _prestador_ou_404(conn, org_id)
        rows = conn.execute(
            """
            SELECT id, unidade_id, nome, tipo, ativo, criado_em
            FROM unidades
            WHERE prestador_id = ?
            ORDER BY criado_em ASC
            """,
            (prestador["id"],),
        ).fetchall()
    return {
        "prestador_org_id": org_id,
        "unidades": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# GET /prestadores/{org_id}/unidades/{unidade_id}  — obter unidade
# ---------------------------------------------------------------------------

@router.get("/{org_id}/unidades/{unidade_id}", summary="Obter unidade")
def obter_unidade(org_id: str, unidade_id: str, _=Depends(require_role("admin"))):
    with get_tx() as conn:
        prestador = _prestador_ou_404(conn, org_id)
        row = conn.execute(
            """
            SELECT id, unidade_id, nome, tipo, ativo, criado_em
            FROM unidades
            WHERE prestador_id = ? AND unidade_id = ?
            """,
            (prestador["id"], unidade_id),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Unidade '{unidade_id}' não encontrada no prestador '{org_id}'.",
            )
        return dict(row)
