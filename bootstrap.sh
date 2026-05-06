#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# bootstrap.sh — Inicialização da instância PicSaúde (G5-impl)
#
# Uso:
#   chmod +x bootstrap.sh
#   ./bootstrap.sh
#
# Pré-requisito: .env preenchido a partir de .env.example
# Resultado: instância operacional em < 5 minutos
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

BOOTSTRAP_VERSION="1.0.0"
ENV_FILE=".env"
COMPOSE_CMD="docker compose"

# Verifica se docker-compose (v1) está disponível como fallback
if ! docker compose version &>/dev/null 2>&1; then
    if command -v docker-compose &>/dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        echo "❌ Docker Compose não encontrado. Instale o Docker Desktop ou o plugin compose."
        exit 1
    fi
fi

# ── Cores ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ok()   { echo -e "  ${GREEN}✅${NC}  $*"; }
fail() { echo -e "  ${RED}❌${NC}  $*"; exit 1; }
warn() { echo -e "  ${YELLOW}⚠️${NC}   $*"; }
step() { echo -e "\n${YELLOW}[$1/8]${NC} $2"; }

echo ""
echo "════════════════════════════════════════════════════════"
echo "  🏥  PicSaúde — Bootstrap v${BOOTSTRAP_VERSION}"
echo "════════════════════════════════════════════════════════"

# ─────────────────────────────────────────────────────────────────────────────
# [1/8] Pré-requisitos
# ─────────────────────────────────────────────────────────────────────────────
step 1 "Verificando pré-requisitos..."

command -v docker &>/dev/null || fail "Docker não encontrado. Instale o Docker Desktop."
ok "Docker disponível: $(docker --version)"

$COMPOSE_CMD version &>/dev/null || fail "Docker Compose não funcional."
ok "Docker Compose disponível"

[[ -f "${ENV_FILE}" ]] || fail "Arquivo .env não encontrado. Execute: cp .env.example .env — e preencha as variáveis."
ok "Arquivo .env encontrado"

# ─────────────────────────────────────────────────────────────────────────────
# [2/8] Validar variáveis obrigatórias
# ─────────────────────────────────────────────────────────────────────────────
step 2 "Validando variáveis de ambiente..."

# Carrega o .env (ignorando linhas de comentário e vazias)
set -a
# shellcheck disable=SC1090
source <(grep -v '^#' "${ENV_FILE}" | grep -v '^[[:space:]]*$')
set +a

ERROS=0

check_var() {
    local var="$1"
    local proibidos=("${@:2}")
    local val="${!var:-}"
    if [[ -z "$val" ]]; then
        warn "${var} não definida."
        ERROS=$((ERROS + 1))
        return
    fi
    for proib in "${proibidos[@]}"; do
        if [[ "$val" == "$proib" ]]; then
            warn "${var} contém o valor de exemplo ('${proib}'). Defina um valor real."
            ERROS=$((ERROS + 1))
            return
        fi
    done
    ok "${var} definida"
}

check_var "PICSAUDE_JWT_SECRET" \
    "TROCAR_POR_CHAVE_ALEATORIA_64_CHARS_HEX" \
    "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"

check_var "PICSAUDE_ADMIN_EMAIL"  ""
check_var "PICSAUDE_ADMIN_NOME"   ""
check_var "PICSAUDE_ADMIN_SENHA"  "TROCAR_IMEDIATAMENTE" "TROQUE_IMEDIATAMENTE"
check_var "PICSAUDE_INSTANCE_ORG_ID" "TROCAR_POR_CODIGO_INSTITUCIONAL"
check_var "PICSAUDE_BASE_URL"     ""

if [[ $ERROS -gt 0 ]]; then
    echo ""
    fail "${ERROS} variável(is) inválida(s). Corrija o .env e execute novamente."
fi

# ─────────────────────────────────────────────────────────────────────────────
# [3/8] Criar estrutura de diretórios
# ─────────────────────────────────────────────────────────────────────────────
step 3 "Criando estrutura de diretórios..."

# Diretórios locais de suporte (fora do container)
mkdir -p data backups
ok "Diretórios criados: data/ backups/"

# ─────────────────────────────────────────────────────────────────────────────
# [4/8] Inicializar banco de dados
# ─────────────────────────────────────────────────────────────────────────────
step 4 "Inicializando banco de dados (init_tables.py)..."

$COMPOSE_CMD run --rm \
    -e PIX_SAUDE_DB="${PIX_SAUDE_DB:-/data/picsaude.db}" \
    picsaude-backend \
    python3 init_tables.py \
    || fail "Falha na inicialização do banco. Verifique os logs acima."

ok "Banco inicializado"

# ─────────────────────────────────────────────────────────────────────────────
# [5/8] Criar admin inicial
# ─────────────────────────────────────────────────────────────────────────────
step 5 "Criando administrador inicial (create_admin.py)..."

$COMPOSE_CMD run --rm \
    -e PIX_SAUDE_DB="${PIX_SAUDE_DB:-/data/picsaude.db}" \
    -e PICSAUDE_ADMIN_EMAIL="${PICSAUDE_ADMIN_EMAIL}" \
    -e PICSAUDE_ADMIN_NOME="${PICSAUDE_ADMIN_NOME}" \
    -e PICSAUDE_ADMIN_SENHA="${PICSAUDE_ADMIN_SENHA}" \
    -e PICSAUDE_VERSION="${PICSAUDE_VERSION:-1.0.0}" \
    -e PICSAUDE_INSTANCE_ORG_ID="${PICSAUDE_INSTANCE_ORG_ID}" \
    -e PICSAUDE_INSTANCE_NAME="${PICSAUDE_INSTANCE_NAME:-}" \
    -e PICSAUDE_BOOTSTRAP_VERSION="${BOOTSTRAP_VERSION}" \
    picsaude-backend \
    python3 create_admin.py \
    || fail "Falha na criação do admin. Verifique os logs acima."

ok "Admin configurado"

# ─────────────────────────────────────────────────────────────────────────────
# [6/8] Verificar integridade do banco
# ─────────────────────────────────────────────────────────────────────────────
step 6 "Verificando integridade do banco..."

INTEGRITY=$($COMPOSE_CMD run --rm \
    -e PIX_SAUDE_DB="${PIX_SAUDE_DB:-/data/picsaude.db}" \
    picsaude-backend \
    python3 -c "
import sys, os
sys.path.insert(0, '.')
from app.database import get_conn
conn = get_conn()
result = conn.execute('PRAGMA integrity_check').fetchone()[0]
conn.close()
print(result)
")

if [[ "$INTEGRITY" != "ok" ]]; then
    fail "PRAGMA integrity_check retornou: ${INTEGRITY}"
fi
ok "Banco íntegro (integrity_check: ok)"

# ─────────────────────────────────────────────────────────────────────────────
# [7/8] Subir a stack
# ─────────────────────────────────────────────────────────────────────────────
step 7 "Subindo a stack..."

$COMPOSE_CMD up -d || fail "Falha ao subir docker-compose. Verifique os logs."

ok "Stack iniciada"

# ─────────────────────────────────────────────────────────────────────────────
# [8/8] Verificar saúde
# ─────────────────────────────────────────────────────────────────────────────
step 8 "Verificando saúde da instância..."

BASE_URL="http://localhost:${PICSAUDE_PORT:-8080}"
MAX_TENTATIVAS=12
TENTATIVA=0

echo "  Aguardando backend ficar pronto..."
while [[ $TENTATIVA -lt $MAX_TENTATIVAS ]]; do
    if curl -sf "${BASE_URL}/health" >/dev/null 2>&1; then
        break
    fi
    TENTATIVA=$((TENTATIVA + 1))
    sleep 5
done

if [[ $TENTATIVA -ge $MAX_TENTATIVAS ]]; then
    fail "Backend não respondeu em 60s. Verifique: docker-compose logs picsaude-backend"
fi
ok "/health → OK"

if curl -sf "${BASE_URL}/health/db" >/dev/null 2>&1; then
    ok "/health/db → OK"
else
    warn "/health/db retornou erro — verifique após a inicialização"
fi

if curl -sf "${BASE_URL}/health/version" >/dev/null 2>&1; then
    ok "/health/version → OK"
fi

# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo -e "  ${GREEN}🎉  PicSaúde inicializado com sucesso!${NC}"
echo "════════════════════════════════════════════════════════"
echo ""
echo "  URL:     ${BASE_URL}"
echo "  Admin:   ${PICSAUDE_ADMIN_EMAIL}"
echo "  Org:     ${PICSAUDE_INSTANCE_ORG_ID}"
echo "  Versão:  ${PICSAUDE_VERSION:-1.0.0}"
echo ""
echo "  ⚠️  TROQUE A SENHA DO ADMIN no primeiro login."
echo ""
echo "  Logs:    docker compose logs -f picsaude-backend"
echo "  Parar:   docker compose down"
echo "════════════════════════════════════════════════════════"
echo ""
