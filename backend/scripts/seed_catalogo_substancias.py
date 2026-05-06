"""
seed_catalogo_substancias.py
============================
Aplica o seed inicial do catálogo regulatório (Ticket 20).

Uso
---
    DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_dev \\
        python3 backend/scripts/seed_catalogo_substancias.py

Idempotente: pode ser executado várias vezes sem efeitos colaterais.
"""
from __future__ import annotations

import os
import sys

# Garante que `app` seja importável quando executado da raiz do projeto.
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.database import get_conn
from app.domain.catalogo_seed import aplicar_seed_catalogo


def main() -> None:
    conn = get_conn()
    try:
        contagens = aplicar_seed_catalogo(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Catálogo regulatório atualizado:")
    for chave, valor in contagens.items():
        print(f"  {chave:>18}: {valor}")


if __name__ == "__main__":
    main()
