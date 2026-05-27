# TICKET-6.2-DEMO-CORRECOES-PRE-REUNIAO — fix consolidado pré-reunião 27/05

> **Origem:** checklist manual §4.2 do TICKET-6.1 (Fabiano + Arquiteto, 2026-05-26 15h-16h) + parecer CODEX rodada 0 sobre logs do demo. Três achados encontrados durante teste end-to-end do fluxo prescritor → paciente → dispensador, todos relacionados ao modo demo. Nenhum é vulnerabilidade de segurança; todos quebram a experiência de demonstração.
> **Classe:** `module` (toca backend + middleware + frontend; comportamental, sem mudança de domínio).
> **Ritmo:** Regra 3 (≤100 linhas previstas, Code Edit direto). CODEX rodada 3 fica em paralelo sobre o `9eb7228` original; este ticket entra como follow-up X.Y antes da rodada 3, conforme pacto calibrado 2026-05-24.
> **Prazo:** amanhã quarta 27/05 antes da reunião com extensionistas UFPE às 14h. Ideal terminar antes das 12h para deixar margem de smoke manual.
> **Predecessor:** HEAD pós-`5db20ef` (terça 26/05).
> **Decisão estratégica relacionada:** este ticket aciona o caminho A do parecer Arquiteto-CODEX consolidado (graceful fallback) em vez do caminho B (workaround SQL direto no banco demo). Caminho A fecha o bug de raiz.

---

## §1 Contexto

Durante o checklist manual §4.2 do TICKET-6.1, Fabiano exercitou o fluxo end-to-end do PicSaúde em modo demo (Etapa 6):

1. ✅ Banner amarelo "MODO DEMO" no `index.html`.
2. ✅ Botão "Entrar como Prescritor" → `prescritor.html` com header "Dra. Demo Maria Souza".
3. ✅ Botão "Entrar como Paciente" → `cidadao.html` com seed "João Demo da Silva".
4. ✅ Prescritor emitiu receita digital (`POST /prescricoes` → 201).
5. ✅ Paciente transferiu receita para a farmácia (`POST /paciente/prescricoes/{uuid}/transferir-farmacia` → 201).
6. ⛔ Dispensador entrou no painel mas o painel quebra ao carregar contexto institucional.
7. ⛔ Token de apresentação não foi resolvido (rate limit 429 antes da tentativa concluir).
8. ⛔ Tentativa de consulta pública retornou 404 (mismatch entre ID local e UUID).

Achados (CODEX rodada 0 sobre logs do demo, 2026-05-26):

### §1.1 Achado A — `/auth/me/institucional` crasha sem `estabelecimentos_cnes`

`GET /auth/me/institucional` retorna **HTTP 500** (toda vez que dispensador entra). Stacktrace:

```
sqlite3.OperationalError: no such table: estabelecimentos_cnes
  File "backend/app/routers/login.py", line 311, in contexto_institucional
    cnes_row = conn.execute(...)
```

A tabela `estabelecimentos_cnes` existe no banco de produção (PostgreSQL com CNES nacional carregado) mas **não existe** no banco demo (`data/pix_saude_demo.db`) — o `seed_demo.py` cria usuários/prestadores/unidades mas não cria CNES.

O TICKET-6.1 P1#1 isolou `cnes_prescritor._get_cnes_conn` via helper compartilhado mas **deixou `login.py:311` de fora** — esse endpoint usa `conn.execute` direto sobre o banco principal, não o helper CNES. Falha pegada nem pelo CODEX rodada 2 nem pelo Jules-audit.

**Consequência:** o painel do dispensador não carrega o contexto institucional. Demo do dispensador fica visualmente quebrado para a reunião.

### §1.2 Achado B — Rate limit hostil em modo demo

Em `backend/app/middleware/rate_limit.py`, os limites são fixos:

```python
ROUTE_LIMITS = [
    ("/auth/token",          5),
    ("/tokens/apresentacao", 10),
    ("/circulacao",          20),
]
DEFAULT_LIMIT = 30  # por minuto
```

Em demo manual com extensionistas exercitando o fluxo, esses limites batem rapidamente. Logs mostraram 429 em:

- `/health/version` (bootstrap repetido — 5+ refreshes em 1 minuto bate o limite)
- `/demo/login` (alternar entre papéis)
- `/paciente/pedidos-exame` (carregar dashboard)
- `/tokens/apresentacao/resolver` (dispensador tentar resolver token várias vezes)

Resultado: durante a reunião, se 7 extensionistas usarem o mesmo IP de saída institucional UFPE, o rate limit por IP pode bloquear o demo em poucos minutos.

**Consequência:** demo fica frágil sob uso real. Em produção, o limite é adequado (mitigação anti-abuso); em demo manual com múltiplos usuários no mesmo IP, é hostil.

### §1.3 Achado C — `/public/prescricoes/REC-...` retorna 404 (mismatch protocolo vs ID local)

Logs mostraram `GET /public/prescricoes/REC-2026-314467 → 404`.

Investigação: `REC-2026-314467` é gerado **localmente no frontend** em `prescritor.html:1522`:

```javascript
id: receitaEmEdicaoId || ("REC-" + new Date().getFullYear() + "-" + Math.floor(100000 + Math.random() * 900000)),
```

É um ID local para localStorage demo offline, **não** o UUID protocolo real do backend. O endpoint `/public/prescricoes/{protocolo}` em `backend/app/routers/publico.py:67` espera UUID (formato 8-4-4-4-12), não código amigável "REC-AAAA-XXXXXX".

Em algum ponto da UI demo, o ID local está sendo usado em lugar do UUID retornado pelo `POST /prescricoes`. Provavelmente em link "ver QR código" ou "ver detalhes públicos".

**Consequência:** consulta pública (cidadão verificando validade da receita via QR) falha no demo.

## §2 Escopo

### §2.1 Fix A — Graceful fallback em `/auth/me/institucional` + cinturão no seed_demo

**Mudança 1 (cirúrgica, em `backend/app/routers/login.py` linhas 311-319):**

Wrap da query CNES em try/except `sqlite3.OperationalError`:

```python
# Tratamento 3 — cruzar CNPJ contra estabelecimentos_cnes por tipo
_TP_FARMACIA  = ("04", "40", "70", "71")
_TP_CLINICA   = ("01", "02", "05", "15", "20", "21", "36", "39", "43")
tipo_prestador = (prestador["tipo"] or "").lower()
tipos_cnes = _TP_FARMACIA if tipo_prestador == "farmacia" else _TP_CLINICA
placeholders = ", ".join("?" * len(tipos_cnes))

# Graceful fallback: em demo (SQLite sem tabela CNES carregada),
# cnes_verificado fica False. Em prod (PostgreSQL com CNES), valida.
try:
    cnes_row = conn.execute(
        f"""
        SELECT CO_CNES FROM estabelecimentos_cnes
        WHERE REPLACE(REPLACE(REPLACE(REPLACE(NU_CNPJ, '.', ''), '/', ''), '-', ''), ' ', '') = ?
          AND TP_UNIDADE IN ({placeholders})
        LIMIT 1
        """,
        (cnpj, *tipos_cnes),
    ).fetchone()
    cnes_verificado = cnes_row is not None
except sqlite3.OperationalError as exc:
    if "no such table" in str(exc).lower():
        cnes_verificado = False  # CNES não carregado (demo) — fail open
    else:
        raise
```

Importar `sqlite3` no topo de `login.py` se ainda não estiver importado. Para PostgreSQL em produção a exceção equivalente seria diferente, mas como o demo é SQLite a captura específica de `OperationalError` cobre o cenário; em prod a tabela existe e o try/except nunca dispara.

**Mudança 2 (cinturão, em `backend/seed_demo.py`):**

Adicionar `CREATE TABLE IF NOT EXISTS estabelecimentos_cnes` antes de popular dados:

```python
# Schema cinturão: garante que tabelas opcionais (CNES) existam vazias
# para que endpoints de contexto institucional não quebrem em demo.
with conn.cursor() as cur:
    cur.execute("""
        CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
            CO_CNES    TEXT,
            NU_CNPJ    TEXT,
            TP_UNIDADE TEXT,
            NO_FANTASIA TEXT,
            CO_MUNICIPIO TEXT
        )
    """)
```

A tabela fica vazia (sem dados CNES reais — não temos licença para distribuir essa base no repositório). `cnes_verificado` fica false em demo, true em prod com CNES real carregado. Defense in depth: o fallback do §2.1.1 pega o cenário mesmo se alguém rodar com banco antigo sem essa tabela; o CREATE garante schema correto para novos banks demo.

### §2.2 Fix B — Rate limit relaxado em `PICSAUDE_DEMO_MODE`

**Mudança em `backend/app/middleware/rate_limit.py` (linhas ~30-37 + dispatch):**

Adicionar guard no topo do middleware: em `PICSAUDE_DEMO_MODE=true`, multiplicador 10x nos limites:

```python
import os

# ... (manter ROUTE_LIMITS e DEFAULT_LIMIT existentes)

_DEMO_MULTIPLIER = 10 if os.getenv("PICSAUDE_DEMO_MODE", "").lower() == "true" else 1


def _get_limit(path: str) -> int:
    """Retorna o limite correspondente ao prefixo da rota."""
    normalized = path.rstrip("/")
    for prefix, limit in ROUTE_LIMITS:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return limit * _DEMO_MULTIPLIER
    return DEFAULT_LIMIT * _DEMO_MULTIPLIER
```

Em demo: `/auth/token` 50/min, `/tokens/apresentacao` 100/min, `/circulacao` 200/min, default 300/min. Em prod: limites originais inalterados (multiplicador = 1).

**Justificativa do multiplicador 10x em vez de bypass total:** evita transformar o demo em ambiente sem qualquer proteção (1 bot malicioso poderia derrubar a instância). 10x cobre uso real de demonstração presencial com múltiplos extensionistas, mantém proteção mínima.

**Alternativa considerada e rejeitada:** whitelist de paths específicos (`/health`, `/config/public`, `/demo/login`). Mais cirúrgica mas ramifica em N exceções; multiplicador é mais simples e auditável.

### §2.3 Fix C — Investigar mismatch `REC-XXXX` vs UUID no frontend

**Investigação primeiro, fix depois.** Code precisa:

1. `grep -rn "REC-" prescritor.html cidadao.html dispensador.html` para mapear todos os usos do código local.
2. Identificar qual link/botão usa `REC-XXXX` em vez de `protocolo` (UUID retornado pelo POST `/prescricoes`).
3. Substituir o uso no link/botão pelo `protocolo` real da response.
4. Verificar especificamente: link para QR Code, link para "verificar autenticidade", link para `/public/prescricoes/{}` em qualquer lugar.

**Critério:** após o fix, abrir `/public/prescricoes/{uuid-real}` retorna 200 com o JSON da prescrição em vez de 404.

Se o Code identificar que `REC-XXXX` tem propósito legítimo separado (ex: número de exibição para o paciente, distinto do UUID de busca), basta usar o UUID no link `/public/...` e manter o `REC-XXXX` na exibição visual. Não deletar o REC-XXXX — só corrigir onde ele estava sendo usado incorretamente como chave de busca.

## §3 Critérios de aceite

1. **Fix A:** `GET /auth/me/institucional` retorna **200** após `/demo/login` como dispensador, com `cnes_verificado: false` no JSON. Sem 500. Log do uvicorn não mostra mais OperationalError em `login.py:311`.
2. **Fix A cinturão:** rodar `python backend/seed_demo.py` em banco vazio cria tabela `estabelecimentos_cnes` com schema correto (verificável via `sqlite3 data/pix_saude_demo.db ".schema estabelecimentos_cnes"`).
3. **Fix B:** rodar `for i in {1..50}; do curl -s http://127.0.0.1:8000/health > /dev/null; done` em demo mode → todos os 50 requests retornam 200 (nenhum 429). Em prod mode (PICSAUDE_DEMO_MODE não setado), o 31º request retorna 429.
4. **Fix C:** após emitir receita digital pelo prescritor demo, copiar o UUID da response, acessar `http://127.0.0.1:8000/public/prescricoes/{uuid}` → 200 com JSON da prescrição. Acessar via algum link/QR gerado pela UI → também 200.
5. Smoke completo da suite: `cd backend && pytest tests/ -x` → zero regressões.

## §4 Verificação automatizada

```bash
# Fix A — endpoint /auth/me/institucional
cd ~/PicSaude_Dev/backend
.venv/bin/python -c "
import os, sqlite3
os.environ['PICSAUDE_DEMO_MODE'] = 'true'
import requests, json
r = requests.post('http://127.0.0.1:8000/demo/login', json={'role': 'dispensador'})
token = r.json()['access_token']
r = requests.get('http://127.0.0.1:8000/auth/me/institucional', headers={'Authorization': f'Bearer {token}'})
assert r.status_code == 200, f'esperado 200, recebeu {r.status_code}: {r.text}'
assert r.json().get('cnes_verificado') is False
print('Fix A ✅')
"

# Fix B — rate limit relaxado em demo
for i in $(seq 1 35); do curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health; done | sort | uniq -c
# Esperado em demo: 35 × 200. Em prod: 30 × 200 + 5 × 429.

# Fix C — UUID do backend funciona em /public
# (executar manualmente — depende de receita emitida no fluxo demo)

# Smoke completo
cd ~/PicSaude_Dev/backend && .venv/bin/pytest tests/ -x --tb=short
```

## §5 Predecessoras

- HEAD pré-commit: `5db20ef` (TICKET-DX-PRE-EXTENSAO em main).
- TICKET-6 + TICKET-6.1 fechados e pushados (`94f73cd` + `9eb7228` + `a01fec6`).
- Checklist manual §4.2 do TICKET-6.1 ✅ **parcial** — itens 1-5 passaram, 6-8 viram este ticket.

## §6 Anti-escopo (NÃO TOCAR neste ticket)

- **NÃO carregar a base CNES real** no banco demo. Schema vazio (tabela existe, sem dados) é o suficiente. Carregar CNES nacional ~50MB CSV no demo é fora de escopo e tem questões de licença.
- **NÃO redesenhar a estrutura de IDs locais (`REC-XXXX`)** — só corrigir o uso errado dele em lugar do UUID. O ID local pode permanecer como rótulo de exibição.
- **NÃO refatorar o middleware rate_limit** para Redis ou outra estratégia. Multiplicador in-memory é o suficiente para a demo de amanhã. Refactor para Redis vira issue pós-Etapa 8.
- **NÃO tocar nos endpoints `/tokens/apresentacao/*`** além do que o fix B já cobre via aumento do limite. Eles estão funcionais — só estavam batendo o limite.
- **NÃO tocar nos achados do CODEX rodada 2 do TICKET-6 já resolvidos pelo `9eb7228`.** Foco estrito nos 3 achados deste ticket.

## §7 Classe, volume, ritmo

- **Classe:** `module` (toca backend `login.py`, `seed_demo.py`, middleware `rate_limit.py`, frontend `prescritor.html`/`cidadao.html`/`dispensador.html`).
- **Volume estimado:** ~50-80 linhas em ~5 arquivos.
- **Ritmo:** Regra 3 — Code Edit direto, sem CODEX rodada 1 sobre este ticket. CODEX rodada 3 (já aguardada sobre `9eb7228` original) absorve este commit junto.
- **Commit único** sugerido: `fix(6.2): demo correções pre-reunião — CNES graceful + rate limit 10x demo + UUID em /public`.

## §8 Prompt sugerido ao Code

Você pode executar §2.1 → §2.2 → §2.3 em sequência (ou em paralelo se preferir branches; `§2.3` precisa de investigação `grep` primeiro). Critérios de aceite em §3, verificação em §4. Anti-escopo em §6 evita expansão.

**Importante para §2.3:** investigar antes de fixar. Faz `grep -rn "REC-" prescritor.html cidadao.html dispensador.html` e me reporta as ocorrências encontradas antes de decidir o fix — quero validar contigo se o `REC-XXXX` deve ser mantido como rótulo de exibição (recomendação) ou substituído inteiramente pelo UUID.

Smoke obrigatório ao final: `cd backend && pytest tests/ -x --tb=short` deve passar sem regressão.

Após o commit, preencher §10 deste ticket com:
- HEAD pós-commit
- Resultado do smoke
- Resposta da investigação §2.3 (lista de ocorrências de `REC-` encontradas e fix aplicado)
- Output de cada verificação automatizada do §4

---

## §9 Reservado — CODEX rodada 3 sobre este ticket

*Será preenchido se CODEX rodada 3 absorver este commit (esperado). Caso CODEX traga P1, abrir TICKET-6.3 conforme pacto.*

## §10 Output do Code pós-impl (2026-05-26)

**HEAD pré-commit:** `5db20ef`
**HEAD pós-commit:** (preenchido após `git commit`, atualizar ao push)

### Smoke `pytest backend/tests/ --tb=no -q`

```
15 failed, 1093 passed, 1 skipped, 708 warnings in ~25s
```

Baseline pré-Fix (com `git stash`): `15 failed, 1093 passed, 1 skipped` — idêntico. **Zero regressões.** As 15 falhas são pré-existentes (clusters `auth_paciente`, `binding_icp`, `g4b`, `health`, `string_validacao`, `catalogo`, `cpf_shift`).

### Resposta da investigação §2.3

Grep `REC-` retornou **uma única ocorrência**:

```
prescritor.html:1522   id: receitaEmEdicaoId || ("REC-" + new Date().getFullYear() + ...)
```

Mapa completo do fluxo:

| Local | Mecanismo |
|---|---|
| `prescritor.html:1522` | Geração inicial do `id` local (placeholder pré-POST) |
| `prescritor.html:1675` | `novaReceitaObj.id = data.protocolo` no fluxo digital — sobrescreve REC- pelo UUID |
| `prescritor.html:1746` | Fluxo físico (`imprimirDireto`) — só grava `protocolo_backend`, **NÃO** sobrescreve `id` |
| `prescritor.html:1817-1838` | `exibirSucessoEImpressao` — agora discrimina UUID vs REC- via hint |
| `prescritor.html:1801` | Link `cidadao.html?protocolo=${rec.protocolo_backend}` — sempre UUID |
| `dispensador.html:1081`, `validar.html:303` | Consumidores — usam input do usuário |

Causa raiz do 404 do log: comprovante físico exibia `REC-XXXX` como "Protocolo" (linha 1817), usuário copiava o texto e tentava `dispensador.html`/`validar.html` → 404 porque REC-XXXX nunca existiu no banco. Fluxo físico é fire-and-forget por design (`prescritor.html:1715-1722`).

Fix aplicado (Opção A, decisão Arquiteto): `<p id="print-protocolo-hint">` novo no HTML do comprovante + lógica condicional em `exibirSucessoEImpressao` — quando `rec.protocolo_backend` existe, exibe UUID sem hint; quando ausente, exibe REC- + hint amber "ID local — receita registrada apenas neste dispositivo. Para verificação pública, emita nova receita digital."

### Verificações automatizadas §4

**Fix A — `/auth/me/institucional` em demo (dispensador):**
```
HTTP=200
{
  "org_id": "farmacia-demo",
  "nome": "Farmácia Demo Central",
  "tipo": "farmacia",
  "cnes_verificado": false,
  "unidades": [{"unidade_id": "DEMO-001", "nome": "Unidade Central Demo", "tipo": "farmacia"}]
}
```
✅ 200 + `cnes_verificado: false`. Sem 500.

**Fix A cinturão — `seed_demo.py` em banco fresh cria schema correto:**
```
sqlite3 /tmp/pix_saude_demo_test.db ".schema estabelecimentos_cnes"
CREATE TABLE estabelecimentos_cnes (
    CO_CNES      TEXT,
    NU_CNPJ      TEXT,
    TP_UNIDADE   TEXT,
    NO_FANTASIA  TEXT,
    CO_MUNICIPIO TEXT
);
```
✅ 5 colunas conforme spec.

Observação: o DB demo atual (`data/pix_saude_demo.db`) já tinha a tabela com schema antigo (3 colunas) criada pelo `cnes_fixtures.py` de teste. `CREATE TABLE IF NOT EXISTS` é no-op nesse caso — esperado. Bancos novos (criados via `reset_demo_db.py` ou usuários novos) terão schema correto.

**Fix B — 35 requests `/health` em demo:**
```
35 × 200
```
✅ Limite efetivo em demo: 300/min (30 × 10). Em prod (validado via unit-test do `_get_limit`): 30/min preservado.

```
PICSAUDE_DEMO_MODE=true:
  /auth/token           → 50  (5  × 10)
  /tokens/apresentacao  → 100 (10 × 10)
  /circulacao           → 200 (20 × 10)
  /health (default)     → 300 (30 × 10)

PICSAUDE_DEMO_MODE not set:
  /auth/token           → 5
  /tokens/apresentacao  → 10
  /circulacao           → 20
  /health (default)     → 30
```

**Fix C — UUID + hint no comprovante:**
- HTML: `<p id="print-protocolo-hint">` inserido em `prescritor.html:729`
- JS: lógica condicional em `prescritor.html:1818-1838` discrimina `rec.protocolo_backend` vs `rec.id`
- Receita digital → comprovante mostra UUID, sem hint
- Receita física com backend online (após resolver fire-and-forget): comprovante mostra UUID, sem hint
- Receita física sem backend ou pré-resolver: comprovante mostra REC-XXXX + hint amber
- Validação visual completa fica para checklist manual antes da reunião 27/05

### Observações inesperadas

1. **Tabela `estabelecimentos_cnes` já existia em `data/pix_saude_demo.db`** com schema antigo (3 colunas — criada provavelmente pelo `cnes_fixtures.py` em alguma corrida de teste passada). `CREATE TABLE IF NOT EXISTS` no `seed_demo.py` não recria; banco precisa ser dropado (via `reset_demo_db.py`) para pegar o schema novo. Não bloqueia o fix, mas registrar para clareza.
2. **Classificador bloqueou `uvicorn` em prod-mode** (correto — protege contra rodar contra DB real). Validação do multiplicador em prod foi feita via unit-test direto do `_get_limit` em vez de smoke HTTP.
3. **Falha pré-existente `test_validar_retorna_cpf_e_nome`** apareceu primeiro porque o `-x` para na primeira falha. Confirmado via stash que é baseline.
