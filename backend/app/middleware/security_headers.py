"""
middleware/security_headers.py
================================
Adiciona headers HTTP de segurança básicos a todas as respostas.

Headers implementados:
  X-Content-Type-Options  — impede MIME sniffing
  X-Frame-Options         — impede clickjacking (iframe)
  Referrer-Policy         — limita vazamento de URL em requisições cross-origin
  Content-Security-Policy — varia por ambiente (ver lógica abaixo)
  Permissions-Policy      — desativa APIs sensíveis não utilizadas

CSP por ambiente
-----------------
- prod: `default-src 'self'` — restrição estrita (previne XSS por injeção).
- dev/hml: relaxado para permitir <style> e <script> inline, que os HTMLs
  do PicSaúde usam (index.html, prescritor.html, etc.). Isso é necessário
  para o frontend funcionar quando servido pelo próprio backend (StaticFiles
  mount em main.py — apenas em dev).

Decisão arquitetural: o ideal seria adotar CSP com nonces dinâmicos para
suportar os inlines mesmo em produção. Por enquanto, em prod o frontend
fica em servidor estático separado (Cloudflare Pages / Vercel) e o backend
só serve API, então a CSP estrita do backend não bloqueia nada.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


_AMBIENTE = os.getenv("PICSAUDE_ENV", "dev").strip().lower()

# Em produção: política estrita.
# Em dev/hml: permite inline para os HTMLs servidos pelo próprio backend
# via StaticFiles mount (ver main.py).
if _AMBIENTE == "prod":
    _CSP = "default-src 'self'"
else:
    _CSP = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response
