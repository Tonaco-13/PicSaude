"""Decisão (pura) de servir o frontend pela própria casa — vitrine "uma casa só".

As telas do repo (index.html + prescritor/dispensador/cidadão/validar) e o
`config.js` usam `window.location.origin` como backend: quando a própria API as
serve via StaticFiles (mesma origem), o frontend aponta para si sozinho, sem CORS.

Esta lógica é isolada aqui (sem FastAPI/DB) para ser testável no gate unitário.
Em `prod` o backend expõe só a API; a vitrine pública roda em DEMO (PICSAUDE_ENV
!= prod) — e o guard de boot já proíbe prod+demo simultâneos.
"""
from __future__ import annotations

from pathlib import Path


def resolve_frontend_dir(env: str, override: str, base_default: Path) -> Path | None:
    """Retorna o diretório de HTMLs a servir, ou None se não deve servir.

    Regras:
      - `env == "prod"`  → None (prod expõe só a API).
      - `override` não-vazio (PICSAUDE_FRONTEND_DIR) tem prioridade — usado no
        empacotamento Docker, onde os HTMLs são copiados para uma pasta dedicada.
      - sem override → `base_default` (layout de dev: raiz do repositório).
      - só retorna o diretório se ele existe E contém `index.html` (porta de entrada).
    """
    if env == "prod":
        return None
    base = Path(override) if override else base_default
    if base.exists() and (base / "index.html").exists():
        return base
    return None
