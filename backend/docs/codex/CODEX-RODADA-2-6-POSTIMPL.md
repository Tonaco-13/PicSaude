# CODEX rodada 2 — TICKET-6 (revisão pós-implementação)

> **Data:** 2026-05-24
> **Commit alvo:** `94f73cd feat(6): demo mode com sessões pré-semeadas + isolamento DB + 7 decisões`
> **Branch:** `main` (origin/main = `94f73cd`, em sincronia com local)
> **Pacto:** Regra 2 estrita — esta é a quarta rodada do TICKET-6 (rodada 0 + rodada 1 + impl + rodada 2 agora).
> **Critério de fechamento:** zero P1. P2/P3 aceitáveis (vão para §11 do ticket como dívida ou follow-up).
> **Path local do repo (CODEX):** `/Users/fabianotonacoborges/PicSaude_Dev/`

---

## §1 Contexto

Você (CODEX) participou de uma rodada pré-impl deste ticket em 2026-05-24:

- **Rodada 1** — revisou a spec rodada 0 e retornou **3 P1 + 4 P2 + 3 P3** (taxa de aceitação Arquiteto: **10/10**). Achados centrais:
  - P1#1: `database.py` engine vs `get_conn()` resolviam `DB_PATH` separadamente → demo continuaria lendo prod sem helper compartilhado
  - P1#2: endpoints OTP inventados na spec — inventário real é 8 endpoints em `login.py` + `auth.py`
  - P1#3: "`instance_id` específico de demo" não estava garantido — `demo-...` é UUID inválido; reusar env vars existentes do `instance.py`

**Todos os 10 achados foram integrados no ticket** (§10 + §10.1) e implementados pelo Code no commit `94f73cd`.

**Esta rodada 2 é pós-impl.** O ticket está fechado para escopo — não estamos rediscutindo as 7 decisões nem as 10 lapidações. Estamos validando que o código entregue:

(a) implementa fielmente cada um dos 3 P1 + 7 P2/P3 especificados em §3-§5;
(b) não introduziu regressão (suite reporta 27→27 falhas pré-existentes inalteradas; +19 passes novos);
(c) não deixou bypass residual (DB demo pode vazar para prod via algum caminho não-coberto? login real continua bloqueado em todos paths? `/demo/login` pode emitir JWT inválido?);
(d) preserva o contrato de erro padronizado (`codigo` + `mensagem` em português, status 403/404 conforme §3.5 do TICKET-5C reaproveitado).

### §1.1 Auto-relato do Code (entregue em 2026-05-24)

| Métrica | Valor |
|---|---|
| Testes focais novos | 25 (20 em `test_demo_mode.py` + 5 em `test_config_guards.py`) |
| Suite delta | 1245 → 1264 passes (+19); 27 → 27 falhas (zero regressão) |
| Verificações §6 do ticket | todas ✅ (grep PICSAUDE_DEMO_MODE, novos arquivos, demo_mode_ativo, _resolve_sqlite_db_path) |
| KISS §3.7.1 (sem refresh) | preservado — `/demo/login` retorna apenas access_token; `/auth/refresh` bloqueado |
| `role="paciente"` (não `cidadao`) | preservado; `domain/roles.py` aceita ambos |
| PDF watermark | `is_demo` runtime via `PICSAUDE_DEMO_MODE`; ReportLab callback `onFirstPage/onLaterPages` |

### §1.2 Trade-offs declarados pelo Code (verificação manual)

§5.6 isolamento DB, §5.8 banner UI render, §5.9 instance_id no ledger ficaram em **verificação manual** — precisam subprocess + ambiente DB completo. As outras 7 cenas cobrem o crítico (helper rejection, JWT format, config public contract, admin gating, PDF watermark estrutural).

**Implicação para sua revisão:** vale especial atenção a esses 3 pontos não cobertos por teste automatizado — são exatamente onde regressões silenciosas se escondem.

---

## §2 Escopo de revisão — onde olhar no commit `94f73cd`

19 arquivos tocados (13 backend + 6 frontend). Mapa de linhas pós-impl:

### §2.1 Backend

| Bloco | Arquivo:linha | Resumo |
|---|---|---|
| **P1#1** Helper compartilhado | `database.py:21` (def), `:39` (engine top-level), `:246` (get_conn) | `_resolve_sqlite_db_path()` usado nos 2 pontos críticos — sem isso, demo vaza para prod |
| **P1#2** Bloqueio OTP `login.py` | `login.py:50` (helper `_reject_if_demo`), `:103,146,180,193,338,383` (6 chamadas) | `/auth/token`, `/auth/refresh`, `/auth/registrar`, `/auth/bootstrap`, `/auth/paciente/{solicitar,validar}-codigo` |
| **P1#2** Bloqueio OTP `auth.py` | `auth.py:26` (helper local), `:57,100` (2 chamadas) | `/auth/paciente/{enviar,validar}-codigo` (legados) |
| **P1#3** Instance_id | `config.py:58-60` (comentário orientador) | Reusa `PICSAUDE_INSTANCE_ID` + `PICSAUDE_INSTANCE_ID_PATH` (vars já existentes em `instance.py:97/253`) |
| Guardrail prod+demo | `main.py:94` (def `_validate_demo_mode_at_boot`), `:122` (call site) | Padrão idêntico ao `_validate_jwt_secret_at_boot` do 5D |
| `/demo/login` (sem refresh) | `demo.py:102` | KISS §3.7.1; retorna apenas access_token |
| `/demo/info` | `demo.py:148` | Personas canônicas + próximo reset |
| `/config/public` + Cache-Control | `config_publico.py:41` (handler), `:55` (header) | P3#10 — `no-store` para banner não atrasar |
| PDF watermark | `pdf_prescricao.py:312` (param `is_demo`), `:492-507` (callbacks ReportLab), `prescricoes.py:1000-1016` (passa `PICSAUDE_DEMO_MODE`) | KISS P2#6 — runtime flag, sem JOIN extra |
| Seeds canônicos | `seed_demo.py:39` (CNS `980001112223334`), `:45` (CNPJ `99999999000191`), `:56` (CPF `12345678909`), `:148` (paciente NÃO entra em `usuarios`) | P3#8 (IDs diferentes do `seed_dev.py`) + P2#5 (sem refresh = paciente sem `usuarios`) |
| Reset horário | `scripts/reset_demo_db.py` (novo, ~77 linhas) | Cron real entra no Dockerfile (Etapa 7) |

### §2.2 Frontend (6 HTMLs)

| Arquivo | Mudança |
|---|---|
| `index.html:341-371` | Boot script `/config/public`, banner "MODO DEMO", intercepta cards de role → `/demo/login` → grava `access_token` em `sessionStorage` |
| `prescritor.html:241-251` | Banner permanente + leitura de `sessionStorage` |
| `dispensador.html:279-289` | Espelho |
| `cidadao.html:266-276` | Espelho |
| `clinica.html:439-465` | P2#7 — banner + redirect para `index.html` (não tenta login via `/auth/token`) |
| `validar.html:143-146` | Boot script para selo "DEMO" condicional |

### §2.3 Testes

| Arquivo | Cenários (subset listado) |
|---|---|
| `test_demo_mode.py` | `demo_info_disponivel_com_flag`, `demo_info_404_sem_flag`, `demo_login_emite_jwt_correto[role]` (parametrizado), `demo_login_sem_flag_retorna_404`, `reject_if_demo_bloqueia_login_helper`, `handlers_login_chamam_reject_if_demo`, `config_public_com_demo_mode_{true,false}`, `admin_{fora_do_demo,dentro_do_demo_admin}`, `pdf_marca_dagua_demo_quando_is_demo_{true,false}` |
| `test_config_guards.py` | 5 testes da função pura `_validate_demo_mode_at_boot` (prod+demo → raise; prod sem demo → OK; dev+demo → OK; etc.) |

---

## §3 Perguntas direcionadas

Estas são as perguntas que esperamos que você ataque. Não precisa responder em ordem — priorize achados graves.

### §3.1 Fidelidade ao spec

- Cada um dos 3 P1 corresponde ao que §4.3/§4.6/§4.1 do ticket especifica? (helper compartilhado nos 2 pontos; 8 endpoints com `_reject_if_demo` ANTES de qualquer leitura/escrita; comentário orientador em `config.py` sobre env vars existentes)
- Os 7 P2/P3 entregues batem com §10.2 do ticket? (KISS sem refresh, `role="paciente"`, PDF runtime, clinica.html banner+redirect, validar.html selo, seeds canônicos novos, Cache-Control no-store)
- O `codigo` e `mensagem` do payload de erro batem com a tabela §3.5? (em demo: `demo_mode_ativo`; em owner check do 5C: mantidos os códigos antigos)

### §3.2 Bypass residual — DB

- **P1#1 crítico:** `get_conn()` chama `_resolve_sqlite_db_path()` na linha 246. Existe **algum outro caminho de acesso ao SQLite** que ainda importe `DB_PATH` diretamente? (Buscar `from app.config import DB_PATH` em todo o repo. Se existir, é vazamento de prod silencioso.)
- O `database_tx.py` (`get_tx`) usa internamente `get_conn()` ou tem path próprio? Confirmar.
- O `init_tables.py` que cria tabelas — em demo, deve criar no DB demo. Confirmar.
- Modo PostgreSQL: o spec deixou explícito que isolamento PG fica para Etapa 8 via `search_path=demo`. Confirmar que nada em produção PG vai quebrar pelo simples fato de `PICSAUDE_DEMO_MODE` existir no config.

### §3.3 Bypass residual — Login real

- Os **8 endpoints listados** estão TODOS com `_reject_if_demo()` no topo? Cruzar com a tabela §3.7 do ticket. Especial atenção a: `/auth/refresh` (linha 146) — bloqueado por KISS; algum cliente legado pode quebrar?
- Existem **outros endpoints de criação de sessão** no projeto que o ticket não listou? (Buscar `criar_access_token` no projeto inteiro — todo chamador deveria estar bloqueado em demo OU ser o próprio `/demo/login`.)
- `/auth/me/institucional` (login.py:246) — permitido em demo. Confirmar que não vaza nada (rota autenticada, JWT demo bate, retorna contexto da persona demo, OK).

### §3.4 Bypass residual — `/demo/login`

- `/demo/login` aceita `{role}` e emite JWT. Validação de role acontece? (Ver `_papeis_demo_disponiveis()` em demo.py:68 + `role_valido` validator em demo.py:90.)
- Pode pedir `role="auditor"` ou `role="integrador"`? Tabela §3.2 do ticket diz que esses NÃO entram nem em `DEMO_ADMIN=true`. Confirmar que retorna 422 ou equivalente.
- Pode pedir `role="admin"` com `DEMO_ADMIN=false`? Deve retornar 422.
- JWT emitido tem TTL? Qual? Se for o `JWT_ACCESS_TTL_MINUTES` padrão (15min), está coerente com KISS sem refresh — usuário faz `/demo/login` de novo.

### §3.5 Rollback de escrita + ledger

- `/demo/login` emite evento no ledger? **Não deveria** — login é sessão, não objeto sanitário. Confirmar que `prescricao_eventos` não cresce ao chamar `/demo/login`.
- `seed_demo.py` emite eventos? **Não deveria** — seed é setup, não ato clínico. Confirmar.
- `reset_demo_db.py` aborta se `PICSAUDE_ENV=prod`? (Spec §4.9 exigia esse guard.)

### §3.6 Regressão silenciosa em testes pré-existentes

- O commit adicionou +19 passes (25 focais - regressões). Confirmar que nenhum teste pré-existente passou a passar por motivo errado (false-green) — especial atenção a testes que tocam `database.py` (mudou linha 21+) ou `pdf_prescricao.py` (mudou assinatura com novo param).
- `test_assinatura_icp.py`, `test_cnes_prescritor.py`, `test_eventos_publicacao.py`, `test_string_validacao.py` foram realinhados no commit `01c67fa` (5C) — algum deles quebra agora por causa do TICKET-6?

### §3.7 Higiene de schema (latente)

- Marca d'água PDF: bytes do PDF agora contêm texto "DEMO" quando `is_demo=true`. Algum sistema downstream parse texto do PDF? (Improvável, mas se houver, vai ver "DEMO" misturado.)
- `seed_demo.py` insere paciente com `ativo=true`. O 5A reconhece isso como "tem carteira"? Spec §4.8 dependia disso — confirmar funcional.

### §3.8 Verificação manual declarada (§1.2)

Você reproduz uma das 3 verificações manuais não-cobertas por teste?

- **§5.6** Isolamento DB: criar `pix_saude_pe.db` com dado fake, setar `DEMO_MODE=true`, rodar app, conferir que dado real não aparece e dado demo não vaza para o DB de prod.
- **§5.8** Banner UI: subir o backend com `DEMO_MODE=true`, abrir `index.html` no navegador, conferir que banner amarelo aparece **antes** do primeiro paint (sem flash).
- **§5.9** Instance_id no ledger: criar prescrição via demo, conferir que linha em `prescricao_eventos` tem `instance_id` igual ao `PICSAUDE_INSTANCE_ID` configurado para demo.

---

## §4 Anti-escopo (NÃO atacar nesta rodada)

- **Etapa 5** (5A/5B/5C/5D) — já fechada em `2bf5e7d`. Achados sobre `prescricoes.py`, `custodia.py`, etc. fora do escopo do TICKET-6 vão como follow-up separado.
- **Cron real no servidor** — entra no Dockerfile (Etapa 7).
- **Schema `demo` em PostgreSQL** — entra em provisionamento (Etapa 8).
- **Tabela `carteiras_digitais` formal** (Dívida B-Carteira #36) — escopo pós-MVP.
- **Validator de CPF nos schemas** (#44) — domínio separado.
- **Múltiplas personas por papel** — anti-escopo §7.
- **Refresh em demo** (KISS §3.7.1) — anti-escopo §7. Só abrir P1 se descobrir que `/demo/login` ESTÁ emitindo refresh por engano.
- **Cluster auth eventos #41, catálogo #39, /health/db #40, órfão auth_paciente #42, CPF-shift #35** — todos cluster próprio.
- **Follow-ups TICKET-5C #52/#53/#54** — não tocar.

---

## §5 Verificação automatizada (você pode rodar localmente)

Estes greps reproduzem §6 do ticket sobre o commit aplicado:

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Helper compartilhado usado nos 2 pontos (P1#1)
grep -n "_resolve_sqlite_db_path" backend/app/database.py
# Esperado: 3 matches (def + engine + get_conn)

# 2. Zero importações diretas de DB_PATH fora do helper (P1#1 — bypass detection)
grep -rn "from app.config import.*DB_PATH" backend/app/ --include='*.py'
# Esperado: apenas dentro do _resolve_sqlite_db_path (linha 26 de database.py)

# 3. 8 endpoints bloqueados (P1#2)
grep -c "_reject_if_demo()" backend/app/routers/login.py backend/app/routers/auth.py
# Esperado: 6 (login.py) + 2 (auth.py) = 8

# 4. Comentário orientador do instance_id (P1#3 — sem flag nova)
grep -n "PICSAUDE_INSTANCE_ID" backend/app/config.py
# Esperado: comentário (sem definição de var nova)

# 5. PICSAUDE_DEMO_MODE não vaza para módulos que não deveriam
grep -rn "PICSAUDE_DEMO_MODE" backend/app/ --include='*.py' | wc -l
# Esperado: ~10-15 ocorrências (config, main, database, demo, config_publico, auth, login, prescricoes, pdf)

# 6. Suite focal — 25/25 verdes
cd backend
pytest tests/test_demo_mode.py tests/test_config_guards.py -v
# Esperado: 25/25 pass

# 7. Suite completa — sem regressão
pytest -q
# Esperado: 1264 passed + 27 failed (mesmos pré-existentes)
```

O Code já rodou (6) e (7) e reportou: 25/25 verdes, 27→27 falhas inalteradas. Você reproduz e cruza.

---

## §6 Formato esperado da sua resposta

Padrão dos ciclos anteriores: `P1 / P2 / P3` numerados, com:

```
N. [Severidade] <Vulnerabilidade ou arquivo:linha>
   <descrição do achado>
   Decisão sugerida: <fix | follow-up | aceitar como dívida>
```

Critério de fechamento da Etapa 6:

- **Zero P1** → fechamos TICKET-6. Eu preencho §11 do ticket com o resumo dos achados P2/P3 (aceitos ou diferidos), atualizo `PLANO-PRODUCAO-V2.md` (Etapa 6 ✅, Etapa 7 ⛔ próxima), `PROMPT-OPUS-4.7-ARQUITETO.md`, e Etapa 6 está formalmente encerrada. Code engata Etapa 7 (Dockerfile).
- **≥ 1 P1** → Code abre follow-up commit antes de fechar. Volta para você uma rodada 2.5.

P2 aceitos viram §11; P2 diferidos viram task pendente com origem rastreada. P3 normalmente vai para §11 como lapidação ou viram backlog.

---

## §7 Histórico cumulativo de aceitação (TICKET-6)

Para você calibrar o que é alto-sinal vs ruído:

| Rodada | P1 | P2 | P3 | Aceitos integralmente |
|---|---|---|---|---|
| 6 rodada 1 (pré-impl) | 3 | 4 | 3 | 10/10 |

Sua taxa de aceitação no TICKET-6 é **100%** (todos os achados absorvidos como mudanças concretas na spec). Sinal: você pode ser exigente nesta rodada 2 — não há custo em apontar P2/P3 sutis. Em particular, os 3 P1 da rodada 1 eram não-óbvios (race de DB resolver, endpoints inventados, UUID inválido) — fique atento a categoria similar agora (interação entre módulos, suposições silenciosas, defaults perigosos).

### Comparativo com o 5C (calibração)

| Ticket | Rodada 2 P1 | Rodada 2 P2 | Rodada 2 P3 |
|---|---|---|---|
| 5C | 0 | 1 | 2 |

TICKET-6 é mais novo e tem mais surface (frontend + DB + auth + PDF). Razoável esperar 0-2 P2 + 1-3 P3 nesta rodada 2. Se vier zero achado, vale uma segunda passada por curiosidade — algo sutil pode estar passando.

---

*Aguardando seu retorno. Obrigado.*
— Arquiteto (Opus 4.7)
