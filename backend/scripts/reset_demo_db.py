"""
scripts/reset_demo_db.py
========================
TICKET-6 — script idempotente para resetar o DB demo a cada hora cheia
(agendamento via cron entra na Etapa 7/8 — Dockerfile/deploy).

Uso manual:
    cd backend && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py

Uso cron sugerido (Etapa 8):
    0 * * * * cd /app && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py \\
              >> /var/log/picsaude/demo-reset.log 2>&1

Comportamento:
1. Aborta se PICSAUDE_ENV=prod (defesa em profundidade — demo não pode
   subir em produção; ver também guardrail em app/main.py).
2. Aborta se PICSAUDE_DEMO_MODE != "true" (impede reset acidental do
   DB de produção/dev quando o script é rodado sem a flag).
3. Remove o arquivo SQLite demo se existir.
4. Recria schema via `Base.metadata.create_all(engine)`.
5. Roda `seed_demo.main()` para popular as 3 personas canônicas.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Permite executar do dir backend/ direto.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))


def main() -> None:
    env = os.getenv("PICSAUDE_ENV", "")
    if env == "prod":
        print("❌ ABORTANDO: reset_demo_db.py NUNCA pode rodar em PICSAUDE_ENV=prod.")
        sys.exit(1)

    demo = os.getenv("PICSAUDE_DEMO_MODE", "").lower()
    if demo != "true":
        print(
            "❌ ABORTANDO: PICSAUDE_DEMO_MODE precisa ser 'true' para o reset.\n"
            "   Isso evita derrubar acidentalmente o DB de dev/prod."
        )
        sys.exit(1)

    # Imports tardios para honrar as env vars setadas acima.
    from app.config import PIX_SAUDE_DEMO_DB
    from app.database import Base, engine
    import app.models  # noqa: F401 — registra modelos no metadata

    db_path = Path(PIX_SAUDE_DEMO_DB).resolve()
    print(f"\n=== reset_demo_db.py — TICKET-6 ===")
    print(f"DB demo: {db_path}\n")

    # 1. Remove o arquivo SQLite (se existir).
    if db_path.exists():
        db_path.unlink()
        print(f"🗑️  arquivo removido: {db_path}")
    else:
        print(f"·  arquivo não existia: {db_path} (será criado)")

    # 2. Garante dir pai.
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # 3. Recria schema.
    Base.metadata.create_all(bind=engine)
    print("✅ schema recriado")

    # 4. Roda seed.
    import seed_demo
    seed_demo.main()


if __name__ == "__main__":
    main()
