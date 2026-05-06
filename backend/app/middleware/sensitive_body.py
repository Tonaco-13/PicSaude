"""
middleware/sensitive_body.py
=============================
Ticket 21 — Marcação de rotas cujo body é sensível e nunca deve ser logado.

CONTEXTO
--------
O middleware principal de observabilidade
(`app/middleware/observabilidade.py`) já não loga bodies por design
("NÃO loga: Payload do body" — comentário de cabeçalho do módulo).

Este módulo COMPLEMENTA aquele guardrail explicitando, em um lugar
único, quais rotas carregam dados sensíveis no body. Qualquer ferramenta
de logging adicional (request inspector, dev console, APM, debug
middleware customizado) deve consultar `BODY_NUNCA_LOGAR` antes de
serializar bodies.

USO
---
Quando alguém adicionar um novo middleware que loga request bodies,
deve importar e respeitar a constante:

    from app.middleware.sensitive_body import rota_tem_body_sensivel

    if rota_tem_body_sensivel(request.url.path):
        body_str = "[REDACTED — sensitive endpoint]"
    else:
        body_str = await request.body()

Por que uma constante e não regex no middleware
------------------------------------------------
Uma lista explícita é auditável. Code review pode verificar a entrada
de uma rota nesta lista; regex genérico é fácil de quebrar com um
typo. As rotas aqui são poucas e estáveis.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Conjunto de rotas com body sensível.
# Comparação é por SUFIXO de path (suporta prefixos OpenAPI):
#   "/prescritor/certificado"            → upload .pfx + senha
#   "/pdf-assinado"                      → senha do .pfx no body
# ---------------------------------------------------------------------------

BODY_NUNCA_LOGAR: frozenset[str] = frozenset({
    "/prescritor/certificado",
    "/pdf-assinado",   # cobre qualquer rota que termine com /pdf-assinado
})


def rota_tem_body_sensivel(path: str) -> bool:
    """True se o body da rota nunca deve ser logado.

    Comparação por sufixo permite cobrir rotas com prefixo (e.g.
    `/prescricoes/{protocolo}/receituarios/{id}/pdf-assinado`).
    """
    if not path:
        return False
    p = path.rstrip("/")
    return any(p.endswith(suffix) for suffix in BODY_NUNCA_LOGAR)
