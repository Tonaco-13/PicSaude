"""
routers/pacientes.py
====================
Endpoints do módulo Paciente — acesso autenticado.

GET /pacientes/me              → dados do cidadão autenticado (role=paciente)
GET /pacientes/{cpf}/carteira  → verifica se CPF possui carteira digital (role=prescritor)
GET /pacientes                 → bloqueado (403) — não há listagem pública de pacientes
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.utils.helpers import normalize_cpf

router = APIRouter()


@router.get("/pacientes/me", summary="Dados do cidadão autenticado")
def paciente_me(usuario=Depends(require_role("paciente"))):
    """
    Retorna os dados básicos do cidadão autenticado.

    - CPF extraído do JWT (nunca via query param).
    - O cidadão só acessa seus próprios dados.
    - Retorna 404 se o paciente não existir no banco.
    """
    cpf = usuario["sub"]

    with get_tx() as conn:
        row = conn.execute(
            "SELECT cpf, nome, ativo FROM pacientes WHERE cpf = ?",
            (cpf,),
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")

    return {
        "cpf":   row["cpf"],
        "nome":  row["nome"],
        "ativo": bool(row["ativo"]),
    }


@router.get("/pacientes/{cpf}/carteira", summary="Verifica carteira digital do paciente")
def verificar_carteira(cpf: str, _=Depends(require_role("prescritor"))):
    """
    Consulta se um CPF possui conta ativa no PicSaúde (carteira digital).

    Usado pelo prescritor antes da emissão para decidir o modo de entrega:
      - tem_carteira = True  → paciente conhecido; objeto pode ser entregue diretamente
      - tem_carteira = False → paciente não cadastrado; frontend exibe link de acesso

    CPF sentinela '00000000000' sempre retorna tem_carteira=False (emissão física).
    """
    cpf_norm = normalize_cpf(cpf)
    if cpf_norm == "00000000000":
        return {"cpf": cpf_norm, "tem_carteira": False}
    with get_tx() as conn:
        row = conn.execute(
            "SELECT id FROM pacientes WHERE cpf = ? AND ativo = true", (cpf_norm,)
        ).fetchone()
    return {"cpf": cpf_norm, "tem_carteira": row is not None}


@router.get("/pacientes", include_in_schema=False)
def listar_pacientes():
    """Bloqueado — não há listagem pública de pacientes."""
    raise HTTPException(status_code=403, detail="Listagem de pacientes não disponível.")
