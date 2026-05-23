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

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.validacao_documental import validar_prescricao
from app.utils.helpers import normalize_cns

router = APIRouter(prefix="/prescricoes", tags=["validacao"])


@router.get("/{protocolo}/validacao")
def get_validacao(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "dispensador", "admin")),
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
        if relatorio.resultado_geral == "invalido":
            est = relatorio.camadas.get("estrutural", {})
            if not est.get("prescricao_existe", type("", (), {"ok": True})()).ok:
                raise HTTPException(
                    status_code=404,
                    detail=f"Prescrição '{protocolo}' não encontrada.",
                )

        # V7 (TICKET-5C §4.7) — owner check apenas para role 'prescritor'.
        # Dispensador e admin passam direto (validação como parte do balcão /
        # fiscalização).
        if usuario["role"] == "prescritor":
            owner = conn.execute(
                """
                SELECT 1
                  FROM prescricoes p
                  JOIN prescritores pr ON pr.id = p.prescritor_id
                 WHERE p.protocolo = ? AND pr.cns = ?
                """,
                (protocolo, normalize_cns(usuario["sub"])),
            ).fetchone()
            if not owner:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "codigo": "nao_e_dono_da_prescricao",
                        "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                    },
                )

    return relatorio.to_dict()
