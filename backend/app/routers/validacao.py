"""
validacao.py
============
Endpoint de validação documental das prescrições PicSaúde.

GET /prescricoes/{protocolo}/validacao

Roles autorizados: prescritor, dispensador, admin.

O dispensador precisa validar antes de dispensar.
O prescritor precisa validar sua própria emissão.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.validacao_documental import validar_prescricao

router = APIRouter(prefix="/prescricoes", tags=["validacao"])


@router.get("/{protocolo}/validacao")
def get_validacao(
    protocolo: str,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
    """
    Executa todas as camadas de validação documental da prescrição.

    Camadas executadas
    ------------------
    1. estrutural        — existência, estados reconhecidos, itens presentes
    2. integridade       — hash SHA-256 do documento canônico recomputado
    3. cfm               — campos obrigatórios da Resolução CFM 2.299/2021
    4. assinatura_digital — metadados em prescricao_assinatura + coerência de hash
    5. icp_brasil        — verificação criptográfica (stub MVP — sempre pendente)

    Cada verificação retorna:
      ok         → bool
      aplicavel  → bool (False quando não se aplica ao tipo de prescrição)
      detalhe    → string explicativa (ou null)

    resultado_geral:
      invalido            — falha em estrutural ou integridade
      valido_fisico       — física com estrutura ok
      valido_estrutural   — digital sem modo CFM, estrutura + integridade ok
      valido_cfm_stub     — CFM ok, metadados presentes, ICP-Brasil pendente (MVP)
      valido_cfm_completo — (futuro) ICP-Brasil verificado

    HTTP 404 é retornado se o protocolo não existir no banco.
    """
    with get_tx() as conn:
        relatorio = validar_prescricao(conn, protocolo)

    # 404 se não encontrado (camada estrutural captura, mas retornamos 404 HTTP)
    from fastapi import HTTPException
    if relatorio.resultado_geral == "invalido":
        est = relatorio.camadas.get("estrutural", {})
        if not est.get("prescricao_existe", type("", (), {"ok": True})()).ok:
            raise HTTPException(
                status_code=404,
                detail=f"Prescrição '{protocolo}' não encontrada.",
            )

    return relatorio.to_dict()
