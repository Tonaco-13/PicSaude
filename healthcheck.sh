#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# healthcheck.sh — Verificação de sanidade de uma instância PicSaúde (G5-impl)
#
# Uso:
#   ./healthcheck.sh                        # usa http://localhost:8080
#   ./healthcheck.sh http://192.168.1.10:8080
#
# Exit codes:
#   0 → instância saudável
#   1 → um ou mais checks falharam
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL="${1:-http://localhost:8080}"
FALHAS=0

ok()   { echo "  ✅  $*"; }
fail() { echo "  ❌  $*"; FALHAS=$((FALHAS + 1)); }

echo ""
echo "── PicSaúde Health Check ─────────────────────────────"
echo "   Instância: ${BASE_URL}"
echo "──────────────────────────────────────────────────────"

# /health — liveness
if curl -sf --max-time 5 "${BASE_URL}/health" > /tmp/picsaude_health.json 2>/dev/null; then
    ok "/health → $(cat /tmp/picsaude_health.json)"
else
    fail "/health → sem resposta (backend down?)"
fi

# /health/db — readiness
if curl -sf --max-time 5 "${BASE_URL}/health/db" > /tmp/picsaude_db.json 2>/dev/null; then
    DB_OK=$(python3 -c "import json,sys; d=json.load(open('/tmp/picsaude_db.json')); print(d.get('ok','?'))" 2>/dev/null || echo "?")
    if [[ "$DB_OK" == "True" ]]; then
        ok "/health/db → OK ($(python3 -c "import json; d=json.load(open('/tmp/picsaude_db.json')); print(d.get('tabelas','?'))" 2>/dev/null) tabelas)"
    else
        fail "/health/db → banco com problemas: $(cat /tmp/picsaude_db.json)"
    fi
else
    fail "/health/db → sem resposta"
fi

# /health/version — metadados
if curl -sf --max-time 5 "${BASE_URL}/health/version" > /tmp/picsaude_ver.json 2>/dev/null; then
    python3 -c "
import json
d = json.load(open('/tmp/picsaude_ver.json'))
print(f\"  ℹ️   versão:  {d.get('version','?')}  |  env: {d.get('env','?')}  |  org: {d.get('org_id','?')}  |  uptime: {d.get('uptime_s','?')}s\")
" 2>/dev/null || echo "  ℹ️   $(cat /tmp/picsaude_ver.json)"
    ok "/health/version → OK"
else
    fail "/health/version → sem resposta"
fi

echo "──────────────────────────────────────────────────────"
if [[ $FALHAS -eq 0 ]]; then
    echo "  ✅  Instância saudável."
else
    echo "  ❌  ${FALHAS} check(s) com falha."
fi
echo ""

exit $FALHAS
