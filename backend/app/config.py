from __future__ import annotations

import os
from typing import Tuple

# Caminho do banco SQLite (variável de ambiente ou padrão relativo ao projeto)
DB_PATH: str = os.getenv(
    "PIX_SAUDE_DB",
    os.path.join(os.path.dirname(__file__), "../../data/pix_saude_pe.db"),
)

# Prefixos CBO dos profissionais prescritores
CBO_PREFIXES: Tuple[str, ...] = ("2251", "2252", "2232")

# URL base pública do sistema (usada em QR Codes e links externos)
# Em produção: export PICSAUDE_BASE_URL=https://picsaude.saude.gov.br
BASE_URL: str = os.getenv("PICSAUDE_BASE_URL", "http://127.0.0.1:8000")

# ---------------------------------------------------------------------------
# Snapshot CNES — rastreabilidade de auditoria (Ticket 48)
# ---------------------------------------------------------------------------
# Identificador do snapshot DataSUS carregado nesta instância.
# Em produção: definir CNES_SNAPSHOT_REF e CNES_SNAPSHOT_MES ao importar a base.
CNES_SNAPSHOT_REF: str = os.getenv("CNES_SNAPSHOT_REF", "cnes_br_2025_12")
CNES_SNAPSHOT_MES: str = os.getenv("CNES_SNAPSHOT_MES", "2025-12")

# ---------------------------------------------------------------------------
# JWT — autenticação e autorização
# ---------------------------------------------------------------------------
# Em produção: gere um segredo forte e exporte como variável de ambiente.
#   python3 -c "import secrets; print(secrets.token_hex(32))"
#   export PICSAUDE_JWT_SECRET=<valor gerado>
JWT_SECRET: str    = os.getenv("PICSAUDE_JWT_SECRET", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32")
JWT_ALGORITHM: str = "HS256"
JWT_ACCESS_TTL_MINUTES: int  = int(os.getenv("PICSAUDE_JWT_TTL_MIN",  "15"))
JWT_REFRESH_TTL_MINUTES: int = int(os.getenv("PICSAUDE_JWT_REFRESH_MIN", str(24 * 60)))

# Paginação
DEFAULT_LIMIT: int = 20
MAX_LIMIT: int = 50

# ---------------------------------------------------------------------------
# Identificação da instância (G5-impl)
# ---------------------------------------------------------------------------
PICSAUDE_VERSION: str = os.getenv("PICSAUDE_VERSION", "1.0.0")
PICSAUDE_ENV: str = os.getenv("PICSAUDE_ENV", "dev")
PICSAUDE_INSTANCE_ORG_ID: str = os.getenv("PICSAUDE_INSTANCE_ORG_ID", "")

# Diretório dos HTMLs do frontend servidos pela própria casa (vitrine "uma casa só").
# Vazio = layout de dev (raiz do repo). No Docker, apontar para onde os HTMLs foram
# copiados (ex.: /app/frontend). Só tem efeito fora de prod — ver main.py.
PICSAUDE_FRONTEND_DIR: str = os.getenv("PICSAUDE_FRONTEND_DIR", "")

# ---------------------------------------------------------------------------
# DEMO_MODE (TICKET-6) — ambiente público de demonstração
# ---------------------------------------------------------------------------
# Safe-by-default off. Quando PICSAUDE_DEMO_MODE=true:
#   - /demo/* routers ativos; /auth/* OTP/login bloqueados (403 demo_mode_ativo)
#   - SQLite routado para PIX_SAUDE_DEMO_DB (isolamento físico vs prod)
#   - Guardrail em main.py aborta boot se PICSAUDE_ENV=prod simultâneo
#
# Para instance_id estável em demo, exportar (P1#3 — reusa env vars existentes
# em app/instance.py:97 e :253; NÃO criar PICSAUDE_DEMO_INSTANCE_ID nova):
#   PICSAUDE_INSTANCE_ID=00000000-0000-4000-8000-00000000d3d3
#   PICSAUDE_INSTANCE_ID_PATH=data/.instance_id.demo
PICSAUDE_DEMO_MODE:  bool = os.getenv("PICSAUDE_DEMO_MODE",  "").lower() == "true"
PICSAUDE_DEMO_ADMIN: bool = os.getenv("PICSAUDE_DEMO_ADMIN", "").lower() == "true"
PIX_SAUDE_DEMO_DB:   str  = os.getenv(
    "PIX_SAUDE_DEMO_DB",
    os.path.join(os.path.dirname(__file__), "../../data/pix_saude_demo.db"),
)
