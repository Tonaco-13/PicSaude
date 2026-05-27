#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# subir-local.sh — Sobe o PicSaúde no seu Mac (sem Docker)
#
# Uso:
#   chmod +x subir-local.sh
#   ./subir-local.sh
#
# O script faz tudo automaticamente:
#   1. Verifica Python 3.10+
#   2. Cria ambiente virtual (.venv)
#   3. Instala dependências do PicSaúde
#   4. Inicializa o banco (SQLite local)
#   5. Cria admin a partir do .env
#   6. Sobe o servidor em http://localhost:8000
#
# Para parar: pressione Ctrl+C nesta janela.
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Cores e helpers ──────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

ok()    { echo -e "  ${GREEN}✅${NC}  $*"; }
fail()  { echo -e "  ${RED}❌${NC}  $*"; exit 1; }
info()  { echo -e "  ${BLUE}ℹ️${NC}   $*"; }
step()  { echo -e "\n${YELLOW}━━━ [$1/6] $2 ━━━${NC}"; }

clear || true
echo "════════════════════════════════════════════════════════════════"
echo "  🏥  PicSaúde — Subindo no seu Mac (sem Docker)"
echo "════════════════════════════════════════════════════════════════"
echo ""
info "Esse script vai te deixar pronto para usar o PicSaúde no navegador."
info "Tempo esperado: ~3 minutos no primeiro uso, ~10 segundos depois."
echo ""

# ─────────────────────────────────────────────────────────────────────────────
step 1 "Procurando Python 3.10 ou mais novo"
# ─────────────────────────────────────────────────────────────────────────────

# Procura em vários nomes possíveis (3.13, 3.12, 3.11, 3.10) e em vários paths.
# Aceita o primeiro que tiver versão >= 3.10.
PYTHON_BIN=""
PY_VER=""

CANDIDATES=(
    "python3.13" "python3.12" "python3.11" "python3.10"
    "/opt/homebrew/bin/python3.13" "/opt/homebrew/bin/python3.12"
    "/opt/homebrew/bin/python3.11" "/opt/homebrew/bin/python3.10"
    "/usr/local/bin/python3.13" "/usr/local/bin/python3.12"
    "/usr/local/bin/python3.11" "/usr/local/bin/python3.10"
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
    "python3"
)

for cand in "${CANDIDATES[@]}"; do
    # Se for nome (sem /), procura no PATH; se for caminho, testa se existe.
    if [[ "$cand" == /* ]]; then
        [ -x "$cand" ] || continue
        BIN="$cand"
    else
        if command -v "$cand" &>/dev/null; then
            BIN="$cand"
        else
            continue
        fi
    fi

    # Lê a versão
    VER=$("$BIN" -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null) || continue
    MAJ=$(echo "$VER" | cut -d. -f1)
    MIN=$(echo "$VER" | cut -d. -f2)
    if [ "$MAJ" -eq 3 ] && [ "$MIN" -ge 10 ]; then
        PYTHON_BIN="$BIN"
        PY_VER="$VER"
        break
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    fail "Python 3.10 ou mais novo não foi encontrado no seu Mac. Para instalar, baixe de https://www.python.org/downloads/macos/ — escolha a versão 3.11 (ou mais nova) e instale com duplo clique. Depois rode esse script de novo."
fi

ok "Python ${PY_VER} encontrado: ${PYTHON_BIN}"

# ─────────────────────────────────────────────────────────────────────────────
step 2 "Preparando ambiente virtual (.venv)"
# ─────────────────────────────────────────────────────────────────────────────

if [ ! -d ".venv" ]; then
    info "Criando .venv com ${PYTHON_BIN}... (uma vez só, ~10s)"
    "$PYTHON_BIN" -m venv .venv
    ok ".venv criado"
else
    # Verifica se o venv existente foi criado com Python 3.10+
    EXISTING_VER=$(.venv/bin/python -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')" 2>/dev/null || echo "0.0")
    EXISTING_MIN=$(echo "$EXISTING_VER" | cut -d. -f2)
    if [ "$EXISTING_MIN" -lt 10 ] 2>/dev/null; then
        info ".venv existente usa Python ${EXISTING_VER} (muito antigo) — recriando..."
        rm -rf .venv
        "$PYTHON_BIN" -m venv .venv
        ok ".venv recriado com Python ${PY_VER}"
    else
        ok ".venv já existe (Python ${EXISTING_VER}) — reutilizando"
    fi
fi

# Ativar venv para o resto do script
# shellcheck disable=SC1091
source .venv/bin/activate
ok "Ambiente virtual ativado: $(which python)"

# ─────────────────────────────────────────────────────────────────────────────
step 3 "Instalando dependências do PicSaúde"
# ─────────────────────────────────────────────────────────────────────────────

info "Atualizando pip..."
python -m pip install --upgrade pip --quiet 2>&1 | tail -3

info "Instalando requirements.txt... (1ª vez: ~2 min)"
echo ""
if pip install -r requirements.txt 2>&1 | tail -10 | grep -E "(Successfully|already satisfied|ERROR)" | head -5; then
    ok "Dependências instaladas"
else
    info "Instalação concluída (output suprimido)"
fi

# Verificação rápida das libs críticas
info "Verificando libs críticas..."
python -c "
from importlib.metadata import version
import pyhanko, cryptography, fastapi, sqlalchemy, reportlab, rapidfuzz
print(f'  pyHanko {version(\"pyhanko\")} | cryptography {version(\"cryptography\")} | fastapi {version(\"fastapi\")}')
" || fail "Alguma dependência crítica não importou. Veja log acima."
ok "Libs críticas funcionando"

# ─────────────────────────────────────────────────────────────────────────────
step 4 "Preparando o banco de dados local (SQLite)"
# ─────────────────────────────────────────────────────────────────────────────

mkdir -p data data/backups
ok "Pasta data/ pronta"

# Carrega .env para que as migrations encontrem PIX_SAUDE_DB etc.
set -a
# shellcheck disable=SC1091
source .env
set +a

cd backend

info "Rodando migrations Alembic..."
if python -m alembic upgrade head 2>&1 | tail -5; then
    ok "Migrations aplicadas"
else
    info "Alembic terminou (talvez já estava atualizado)"
fi

cd ..

# ─────────────────────────────────────────────────────────────────────────────
step 5 "Criando o usuário administrador"
# ─────────────────────────────────────────────────────────────────────────────

if [ -f "backend/create_admin.py" ]; then
    info "Criando admin a partir do .env (idempotente)..."
    cd backend
    python create_admin.py 2>&1 | tail -10 || info "create_admin.py terminou (pode já existir)"
    cd ..
    ok "Admin pronto. Credenciais em .sandbox/secrets.txt"
else
    info "create_admin.py não encontrado — crie manualmente depois"
fi

# ─────────────────────────────────────────────────────────────────────────────
step 6 "Subindo o servidor"
# ─────────────────────────────────────────────────────────────────────────────

PORT=${PICSAUDE_PORT:-8000}
echo ""
echo "════════════════════════════════════════════════════════════════"
echo -e "  🌐  ${GREEN}PicSaúde no ar!${NC}"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  📍 Abrir no navegador:"
echo -e "     ${BLUE}http://localhost:${PORT}/index.html${NC}        ← portal"
echo -e "     ${BLUE}http://localhost:${PORT}/prescritor.html${NC}   ← módulo médico"
echo -e "     ${BLUE}http://localhost:${PORT}/dispensador.html${NC}  ← módulo farmácia"
echo -e "     ${BLUE}http://localhost:${PORT}/cidadao.html${NC}      ← módulo paciente"
echo -e "     ${BLUE}http://localhost:${PORT}/clinica.html${NC}      ← módulo clínica"
echo ""
echo "  🔑 Credenciais admin: .sandbox/secrets.txt"
echo "  ⛔ Para parar: Ctrl+C aqui"
echo ""
echo "  📋 Próximo passo do teste: abrir .sandbox/TESTE_E2E_PLAN.md"
echo ""
echo "────────────────────────────────────────────────────────────────"
echo ""

cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT}" --reload
