"""
routers/catalogo.py
===================
Ticket 20 — Endpoints do catálogo regulatório de substâncias.

Endpoints
---------
GET /catalogo/substancias?q=<termo>&limit=<n>
    Busca substâncias por prefixo na DCB normalizada. Usado pelo
    frontend para autocomplete no campo "nome do medicamento".

Auth
----
Bearer token, qualquer role (prescritor, dispensador, admin, auditor).
O catálogo é público para todos os usuários autenticados — não há
informação sensível, apenas dados regulatórios já publicados pela Anvisa.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.dependencies import get_current_user
from app.database_tx import get_tx
from app.domain.catalogo_regulatorio import buscar_substancias_similar


router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.get(
    "/substancias",
    summary="Busca substâncias do catálogo regulatório por prefixo (autocomplete)",
)
def listar_substancias(
    q: str = Query(..., min_length=1, max_length=100, description="Termo de busca (prefixo)"),
    limit: int = Query(10, ge=1, le=20),
    usuario: dict = Depends(get_current_user),
):
    """Retorna substâncias cujo DCB normalizado começa com o termo `q`.

    Resposta:
      {
        "resultados": [
          {
            "dcb": "semaglutida",
            "dcb_display": "Semaglutida",
            "classe_controle": null,
            "tipo_retencao": "glp1_agonista",
            "fonte": "in_360_2025"
          }
        ]
      }

    Comportamento:
      - Termos vazios ou muito curtos → 422 (validado por Query).
      - Match case-insensitive e accent-insensitive (via normalização
        no domínio).
      - Substâncias com `ativo=False` são ignoradas.
    """
    if not q.strip():
        raise HTTPException(status_code=422, detail="Parâmetro 'q' não pode ser vazio.")

    with get_tx() as conn:
        substancias = buscar_substancias_similar(q, conn, limit=limit)

    return {
        "resultados": [
            {
                "dcb":             s.dcb,
                "dcb_display":     s.dcb_display,
                "classe_controle": s.classe_controle,
                "tipo_retencao":   s.tipo_retencao,
                "fonte":           s.fonte,
                "observacao":      s.observacao,
            }
            for s in substancias
        ],
    }
