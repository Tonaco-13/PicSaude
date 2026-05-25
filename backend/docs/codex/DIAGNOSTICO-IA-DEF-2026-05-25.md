# Diagnóstico tri-revisor — IA farmacêutica (DEF) reportada como "não funcionando"

> **Data:** 2026-05-25 (segunda)
> **Reportado por:** Fabiano (coordenador), durante teste manual do DEMO_MODE
> **Commit alvo:** `ecf669a` (HEAD `origin/main`)
> **Branch:** `main`
> **Path local:** `/Users/fabianotonacoborges/PicSaude_Dev/`
> **Pacto:** diagnóstico ad-hoc (não é rodada formal). Os 3 revisores atacam em paralelo com lentes diferentes.

---

## §1 Sintoma

Em sessão de teste manual do DEMO_MODE em 2026-05-25 às ~10h, Fabiano reportou:

> "A IA do DEF não está funcionando desde o início."

Log do servidor mostrou **6 chamadas** ao endpoint `POST /ia/medicamentos/sugerir` durante a sessão, todas com **status 200 OK** e latência 3-8ms:

```
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 8.76}
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 3.85}
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 3.34}
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 3.74}
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 3.48}
{"path": "/ia/medicamentos/sugerir", "method": "POST", "status": 200, "latency_ms": 3.69}
```

O backend respondeu sempre. O conteúdo da resposta não foi inspecionado pelo coordenador. O que ele percebe como "não funciona" é a experiência de uso no frontend (`prescritor.html`), não o status HTTP.

## §2 Contexto técnico

A "IA do DEF" é, apesar do nome, **lookup determinístico**:

- **Base de dados:** `data/def_medicamentos.csv` — 41 medicamentos, schema `principio_ativo, nome_normalizado, forma_farmaceutica, unidade_dispensavel, concentracao_texto, via_administracao, aliases, fonte, versao_base`.
- **Lookup:** `backend/app/ai/lookup_def.py` — pipeline `exato → alias → rapidfuzz WRatio ≥ 82 → nenhum`.
- **Lógica principal:** `backend/app/ai/ia_farmaceutica.py` — função `sugerir_medicamento()`.
- **Router:** `backend/app/routers/ia.py` — endpoint `POST /ia/medicamentos/sugerir` exige `require_role("prescritor", "dispensador", "admin")`.
- **Frontend chamador:** `prescritor.html` (provavelmente também `dispensador.html`).
- **Modelo declarado:** `"lookup + regras (v1 — sem ML)"`.

Cobertura de testes: `backend/tests/test_ia_farmaceutica.py` existe (não verifiquei conteúdo).

## §3 Hipóteses (ordem de probabilidade — Arquiteto, sem evidência)

1. **Frontend não renderiza a resposta.** Backend responde com `match_tipo: "exato"` + sugestões, mas a UI não exibe os campos preenchidos. Diagnóstico exige inspecionar resposta crua + comportamento do JS.
2. **Coordenador testou com nomes fora da base.** A base de 41 não cobre tudo (cobre: amoxicilina, metformina, losartana, dipirona, paracetamol, ibuprofeno, omeprazol, insulinas, atorvastatina, sinvastatina, fluoxetina, clonazepam, ciprofloxacino, azitromicina, tramadol, salbutamol, etc; NÃO cobre: rivotril, diazepam, captopril, anlodipino com Z, etc).
3. **Bug em runtime no lookup/normalização** — improvável (testes existem) mas possível com algum estado novo do demo (ex: cwd diferente afetando path do CSV).
4. **Expectativa de "IA" generativa.** Coordenador (ou usuários demo) esperam comportamento de GPT/Copilot ("digite qualquer coisa e a IA inventa"), mas é lookup contra CSV. Percepção de "não funciona" = "não age como ChatGPT".

## §4 Diagnóstico mínimo (todos podem rodar; Code roda em definitivo)

```bash
cd ~/PicSaude_Dev

# Servidor já está rodando em http://localhost:8000 em DEMO_MODE
# Se não estiver:
#   cd backend && source .venv/bin/activate
#   PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py
#   PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload --app-dir .

# 1. Pegar token demo
TOKEN=$(curl -s -X POST http://localhost:8000/demo/login \
  -H "Content-Type: application/json" \
  -d '{"role":"prescritor"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Status da base
curl -s http://localhost:8000/ia/status \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# 3. Match exato esperado
curl -s -X POST http://localhost:8000/ia/medicamentos/sugerir \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nome_medicamento":"dipirona 500"}' | python3 -m json.tool

# 4. Match aproximado esperado (typo)
curl -s -X POST http://localhost:8000/ia/medicamentos/sugerir \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nome_medicamento":"dipirana"}' | python3 -m json.tool

# 5. Match nenhum esperado (fora da base)
curl -s -X POST http://localhost:8000/ia/medicamentos/sugerir \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nome_medicamento":"rivotril 2mg"}' | python3 -m json.tool
```

Saídas esperadas:
- `/ia/status` → `farmaceutica.base_carregada: true`, `total_registros: 41`.
- `dipirona 500` → `match_tipo: "exato"` ou `"alias"`, score ≥ 0.95, sugestão preenchida.
- `dipirana` → `match_tipo: "aproximado"`, score 0.82-0.95.
- `rivotril 2mg` → `match_tipo: "nenhum"`, score 0.0, sugestão nula.

Se o backend retornar conforme esperado, **o problema é no frontend** (hipótese 1). Se retornar `nenhum` para `dipirona 500`, **o problema é no lookup** (hipótese 3).

---

## §5 Para o **Code** (Engenheiro-Chefe — VS Code)

**Lente:** implementação, reprodução de bug, fix mínimo.

**Faça:**
1. Rode o diagnóstico §4 e cole as 4 respostas no seu retorno.
2. Se hipótese 1 (frontend) confirmar-se: localize em `prescritor.html` onde a resposta do `/ia/medicamentos/sugerir` é consumida; identifique por que os campos sugeridos não chegam à UI. Propor fix mínimo (provavelmente 5-30 linhas em vanilla JS).
3. Se hipótese 3 (lookup) confirmar-se: investigue `lookup_def.py:_BASE_CSV` path resolution; reproduza com `pytest tests/test_ia_farmaceutica.py -v` para isolar.
4. **Estimativa volume + classe (CLAUDE.md §10).** Se for `core/module >100 linhas`, redija TICKET-6.2 follow-up; se for `<100 linhas` e classe `module`, Edit direto.

**Não faça:**
- Não opine sobre o naming "IA do DEF" / expectativa do usuário — Jules cobre §6.
- Não revise segurança/RBAC do endpoint — CODEX cobre §7.

## §6 Para o **Jules** (Auditor — qualidade, DX, naming)

**Lente:** o sintoma "não funciona" pode ser **expectativa errada**, não bug. Sua especialidade.

**Faça:**
1. Leia `routers/ia.py:85-120` (handler `/medicamentos/sugerir`) + `ia_farmaceutica.py:_AVISO_FIXO` + `routers/ia.py:status_ia` (`"modelo": "lookup + regras (v1 — sem ML)"`).
2. **Disparidade nome ↔ comportamento:** o endpoint se chama `ia/medicamentos/sugerir`, o módulo é `ia_farmaceutica.py`, o status retorna "IA farmaceutica". Tudo isso vendendo "IA" — mas é CSV lookup de 41 linhas. Para o extensionista (e até para o coordenador), isso causa expectativa de comportamento generativo. **Isso é P1 de DX/copy ou aceitável?**
3. **Frontend deveria sinalizar "nenhuma sugestão encontrada"?** Se a UI fica silenciosa quando `match_tipo: "nenhum"`, parece bug mas é "comportamento esperado para fora da base".
4. **Base de 41 documentada como subset?** Existe aviso visível ao usuário ("base inicial, em expansão") ou só na docstring do endpoint?
5. **Naming `DEF/BASE_LOCAL`:** "DEF" é jargão técnico (Dicionário de Especialidades Farmacêuticas). Extensionista de informática vai entender? E o de medicina, vai validar se está completo?

**Não faça:**
- Não rode diagnóstico técnico (Code cobre §5).
- Não opine sobre RBAC/auth (CODEX cobre §7).
- Não revise código de outras IAs (`ia_cid.py`, `ia_exames.py`, `ia_documental.py`) a menos que veja o mesmo padrão se propagando.

## §7 Para o **CODEX** (Revisor segurança/auth)

**Lente:** o endpoint retorna 200 OK; o sintoma pode esconder bypass ou vazamento.

**Faça:**
1. Verifique que `require_role("prescritor", "dispensador", "admin")` em `routers/ia.py:92` é honrado. Em demo, o `/demo/login` emite JWT com role correto. Algum caminho que bypassa?
2. **Vazamento de info:** a resposta inclui `principio_ativo`, `concentracao_texto`, `via_administracao` — para um endpoint público-autenticado em demo, isso revela quais medicamentos estão na base. Aceito como "MVP" ou risco?
3. **Rate limiting:** 6 chamadas em ~20 segundos no log. Endpoint não tem throttle. Em deploy público, scraping da base inteira seria trivial (chamar com cada nome do dicionário). Aceito (base é pública) ou abrir follow-up?
4. **DEMO_MODE bypass:** em demo, `/ia/*` continua exigindo role autenticado? Confirmar que não foi adicionado a alguma whitelist tipo "público em demo".

**Não faça:**
- Não opine sobre frontend (Code cobre §5).
- Não opine sobre naming/DX (Jules cobre §6).
- Não revise lookup interno (`lookup_def.py`) a menos que veja bypass de auth indireto.

---

## §8 Anti-escopo cruzado

| Categoria | Code (§5) | Jules (§6) | CODEX (§7) |
|---|:---:|:---:|:---:|
| Reproduzir bug + curl | ✅ | — | — |
| Fix de código | ✅ | — | — |
| Naming "IA"/"DEF" | — | ✅ | — |
| Expectativa do usuário | — | ✅ | — |
| Documentação visível | — | ✅ | — |
| RBAC / auth do endpoint | — | — | ✅ |
| Vazamento de info | — | — | ✅ |
| Rate limiting | — | — | ✅ |

Sobreposições propositais (cobertura dupla onde compensa):
- **Status code 200 com conteúdo "nenhum":** Code investiga se UI exibe; Jules investiga se UI deveria exibir "não encontrei" claramente.

## §9 Formato esperado de retorno

Padrão dos ciclos anteriores:

```
N. [Severidade P1/P2/P3] [Categoria]
   <arquivo:linha> — <descrição>
   Decisão sugerida: <fix | follow-up | aceitar como dívida | fora-do-escopo>
```

Critério de fechamento deste diagnóstico:

- **Causa raiz identificada por pelo menos 1 revisor** → Code aplica fix se trivial (classe `module`, ≤100 linhas, Edit direto pelo Pacto Regra 3) ou abre TICKET-6.2 follow-up.
- **Causa raiz é "expectativa de IA generativa"** (Jules) → entra como copy/UX no §11 do TICKET-6 + GFI #62 ("expandir def_medicamentos.csv para top 200 RENAME + atualizar disclaimer no frontend").
- **Múltiplas causas** → cada uma vai para o destino que faz sentido.

Prazo: idealmente antes da reunião com extensionistas (terça 2026-05-26, 14h). Se algum cenário do `docs/HOMOLOGACAO-DEMO.md` depender da IA estar funcional, isso vira bloqueador da reunião.

## §10 Contexto adicional

- A reunião de 2026-05-26 é a primeira do projeto de extensão UFPE-CTG. 7 extensionistas chegam. **O demo público é a primeira coisa que vão ver.** Se a IA é a primeira interação visível e parece quebrada, prejudica o primeiro contato.
- O bug (se for) foi descoberto **depois** que `9eb7228` (Etapa 6.1) já foi pushado para `origin/main`. CODEX rodada 3 sobre `origin/main` ainda não rodou. Se o problema for em `routers/ia.py` (que é Etapa 5C/anterior, NÃO Etapa 6), não bloqueia o fechamento da Etapa 6.
- Se o problema for de copy/expectativa (Jules), isso é trabalho de hoje à tarde — adicionar disclaimer no frontend + atualizar `CONTRIBUTING-EXTENSAO.md` para os extensionistas saberem que "IA" significa lookup.

---

*Aguardando retorno dos 3 em paralelo. Sem dependência de ordem entre vocês.*
— Arquiteto (Opus 4.7)
