# Jules — revisão de fim de etapa do TICKET-6 (DEMO_MODE)

> **Data:** 2026-05-24
> **Commit alvo:** `94f73cd feat(6): demo mode com sessões pré-semeadas + isolamento DB + 7 decisões`
> **Branch:** `main` (origin/main = `94f73cd`, em sincronia com local)
> **Pacto:** Regra 5 — Jules entra em fim de etapa, junto com CODEX.
> **Lente Jules (canônica):** qualidade de código — complexidade, duplicação, naming, tech debt, comentários, testabilidade, **DX para extensionistas**.
> **Path local do repo (Jules):** `/Users/fabianotonacoborges/PicSaude_Dev/`

---

## §1 Contexto

Você é o Jules. Sua lente é **complementar ao CODEX**, não redundante.

- **CODEX** está rodando agora em paralelo sobre o mesmo commit `94f73cd`, atacando: segurança, RBAC, owner check, bypass, vulnerabilidades, ledger/auditoria. Briefing dele em `backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md`.
- **Você (Jules)** ataca: qualidade de código, complexidade, duplicação, naming, tech debt, type hints, comentários, testabilidade, padrões inconsistentes — e, novidade nesta rodada, **DX para extensionistas** (ver §1.2).

Se você encontrar uma vulnerabilidade de segurança, reporte (uma cabeça a mais é bem-vinda), mas saiba que CODEX já está vasculhando essa superfície — concentre seu fogo onde CODEX não vai olhar.

### §1.1 Contexto do TICKET-6 (resumo)

Etapa 6 do PicSaúde: DEMO_MODE público com personas pré-semeadas. Tese central: "modo explícito, safe-by-default off, que substitui login real por sessões demo pré-semeadas e reversíveis, sem admin público e sem dados reais." Volume: 1.217 inserções, 11 deleções, 19 arquivos (13 backend + 6 frontend). Testes: 25 focais novos, 27→27 falhas pré-existentes (zero regressão).

Ticket completo em `backend/docs/tickets/TICKET-6-DEMO-MODE.md`. Você não precisa reler o ticket inteiro — basta as decisões §3 e a spec §4.

### §1.2 Mudança de contexto importante (2026-05-24)

O PicSaúde foi **aprovado como projeto de extensão UFPE-CTG hoje**. Na **terça 26/05** (em 48h) há a primeira reunião com **7 extensionistas de formações distintas**. Alguns serão técnicos (info/eng), outros leigos (medicina/farmácia/direito/comunicação).

**Implicação para sua revisão:** o código a partir de agora não é mais leitura solo do Fabiano + Code + você + CODEX. Pode ser leitura de um aluno de 4º período de informática que vai abrir o primeiro PR da vida dele. Inclua **DX (developer experience) para extensionistas iniciantes** como categoria explícita nos seus achados (ver §3.7).

---

## §2 Escopo de revisão — onde olhar no commit `94f73cd`

19 arquivos. Mapa rápido (linhas pós-impl):

### §2.1 Backend (13 arquivos)

| Arquivo | Mudança |
|---|---|
| `config.py:48-60` | 3 novas vars (`PICSAUDE_DEMO_MODE`, `PICSAUDE_DEMO_ADMIN`, `PIX_SAUDE_DEMO_DB`) + comentário sobre `PICSAUDE_INSTANCE_ID` reusado |
| `database.py:21,39,246` | Helper `_resolve_sqlite_db_path()` compartilhado |
| `main.py:94-122` | Guardrail `_validate_demo_mode_at_boot` (mesmo padrão do `_validate_jwt_secret_at_boot` do 5D) |
| `routers/demo.py` (novo, ~162 linhas) | `/demo/login` + `/demo/info` + `_papeis_demo_disponiveis` + `_proximo_reset_horario` |
| `routers/config_publico.py` (novo, ~64 linhas) | `/config/public` com `Cache-Control: no-store` |
| `routers/auth.py:14,26-31,57,100` | Helper local `_reject_if_demo()` em 2 endpoints OTP legados |
| `routers/login.py:40,50-55,103,146,180,193,338,383` | Helper local `_reject_if_demo()` em 6 endpoints OTP/login |
| `routers/prescricoes.py:1000-1016` | Passa `is_demo=PICSAUDE_DEMO_MODE` ao gerador de PDF |
| `domain/pdf_prescricao.py:312-313,492-507` | Novo param `is_demo` + callbacks `onFirstPage/onLaterPages` do ReportLab |
| `seed_demo.py` (novo, ~219 linhas) | 3 personas canônicas + paciente em `pacientes` (sem `usuarios` por KISS) |
| `scripts/reset_demo_db.py` (novo, ~77 linhas) | Drop + recreate + seed; guard prod/sem-flag |
| `tests/test_demo_mode.py` (novo, ~287 linhas) | 20 testes focais |
| `tests/test_config_guards.py` (+29 linhas) | 5 testes do guard `_validate_demo_mode_at_boot` |

### §2.2 Frontend (6 HTMLs)

| Arquivo | Mudança |
|---|---|
| `index.html:341-371` | Boot script `/config/public`, banner, intercepta cards de role → `/demo/login` → `sessionStorage` |
| `prescritor.html:241-251`, `dispensador.html:279-289`, `cidadao.html:266-276` | Espelho — banner permanente + leitura de token |
| `clinica.html:439-465` | Banner + redirect para `index.html` (não tenta login via `/auth/token`) |
| `validar.html:143-146` | Boot script para selo "DEMO" condicional |

---

## §3 Perguntas direcionadas (lente Jules)

### §3.1 Complexidade e legibilidade

- `routers/demo.py:68` (`_papeis_demo_disponiveis`) e `:75` (`_proximo_reset_horario`): funções simples ou estão fazendo demais?
- `routers/demo.py:102` (`demo_login`): qual o tamanho real? Tem condicional aninhada? Validação de role acontece em quantos lugares (validator do Pydantic + handler + helper)?
- `domain/pdf_prescricao.py:312-313`: assinatura da função ganhou novo param `is_demo`. Quantos params a função tem agora? Está virando god-function? Vale extrair PDF-demo como subclasse/builder?
- `seed_demo.py` 219 linhas: tem funções repetidas com `seed_dev.py`? Vale helper compartilhado em `seed_common.py`?

### §3.2 Duplicação e consistência

- **Duplicação real (P2 esperado):** `routers/login.py:50-55` e `routers/auth.py:26-31` definem **dois helpers `_reject_if_demo` separados**, idênticos. O ticket §4.6 explicitamente escolheu inline KISS porque eram 2 arquivos / 8 endpoints. Mas agora que está implementado: a duplicação ainda vale a pena, ou já é hora de extrair para `app/auth/dependencies.py` como `reject_if_demo` (dependency reusável)?
- `seed_dev.py` e `seed_demo.py`: helpers `_garantir_usuario`, `_garantir_prestador`, etc. estão duplicados? Quanto?
- Boot scripts dos 5 frontends (`index/prescritor/dispensador/cidadao/clinica.html`) — quantas linhas repetidas? Vale extrair `demo-bootstrap.js` compartilhado?
- `database.py:39` (engine) e `:246` (`get_conn`) chamam o helper. Algum **outro caminho** no projeto que ainda importe `DB_PATH` direto? (P1#1 do CODEX vai olhar isso pelo ângulo de segurança; você olhe pelo ângulo de manutenibilidade — se mais alguém vier criar um terceiro acesso ao DB, vai cair na mesma armadilha?)

### §3.3 Naming

- `_reject_if_demo()` — nome OK?
- `_papeis_demo_disponiveis()` — português OK, mas mistura com vars em inglês (`PICSAUDE_DEMO_MODE`, `demo_admin`). Convenção do projeto é mista — é proposital? Está documentada em algum lugar?
- `PIX_SAUDE_DEMO_DB` (config.py) vs `PICSAUDE_DEMO_MODE` (config.py) — prefixo inconsistente (`PIX_SAUDE_` vs `PICSAUDE_`). O `PIX_SAUDE_DB` herda do legado antes do projeto se chamar PicSaúde. Vale renomear ou documentar a convenção?
- `is_demo` (parâmetro do PDF) vs `demo_mode` (chave do `/config/public`) — variável local OK ser snake-case e curta, mas consistência?

### §3.4 Type hints e contratos

- `routers/demo.py:102` retorna `dict` (genérico). Vale `TypedDict` ou Pydantic response model? Mesmo para `demo_info()`.
- `routers/config_publico.py` mesma pergunta.
- `_resolve_sqlite_db_path()` retorna `str` — está bom; vale `Path`?
- Frontends não têm contrato tipado com backend (vanilla JS). Para extensionistas iniciantes, seria útil um `types.d.ts` documentando o shape de `/config/public` e `/demo/login`? Ou está fora do escopo?

### §3.5 Comentários e documentação

- Comentários `TICKET-6 P1#N` espalhados (vi em `database.py:15`, `auth.py:25`, `login.py:48`, `pdf_prescricao.py:312`, etc.). Bom para trilha de auditoria; ruído para leitor novo?
- Docstrings: `/demo/login`, `/demo/info`, `/config/public`, `seed_demo.py`, `reset_demo_db.py` — completas? Têm exemplos de uso? Têm "quando não usar"?
- README.md ou `docs/` foram atualizados explicando como rodar demo localmente? (Verificar — extensionistas vão precisar disso na terça.)

### §3.6 Testabilidade

- `test_demo_mode.py` tem 20 testes (paramétricos contam como 1). Os testes parametrizados (`test_demo_login_emite_jwt_correto[role]`) — cada role testada explicitamente?
- `test_handlers_login_chamam_reject_if_demo` (linha 148) — esse teste valida que o helper é chamado, ou valida o efeito (403 retornado)? Os dois?
- Mocks ou fixtures novos que escondem comportamento real? Especialmente: `monkeypatch` de `PICSAUDE_DEMO_MODE` no `test_reject_if_demo_bloqueia_login_helper` — está testando o módulo recarregado ou o estado importado?
- O Code declarou que §5.6 (isolamento DB), §5.8 (banner UI), §5.9 (instance_id no ledger) ficaram em **verificação manual**. Quais desses valeria automatizar agora (mesmo que custo médio)? Quais ficam dívida aceita?

### §3.7 DX para extensionistas (categoria nova)

Imagine um estudante de informática do 4º período, primeira contribuição open-source da vida. Ele recebe link do repo na terça. Vai tentar:

1. **Clonar e rodar localmente.** Quantos passos? README cobre? Tem `docker-compose` ou só instrução textual?
2. **Entender a estrutura.** Abre o repo na IDE — consegue mapear "onde está o que" em 10 minutos? Diretório `app/routers/` tem 20+ arquivos — algum índice/README?
3. **Achar uma boa-first-issue.** O Plano §9 prevê 12 issues `good-first-issue` (Etapa 9). Ainda não criadas. Mas considerando o TICKET-6: tem 1-3 mudanças no commit que **poderiam ter sido good-first-issues** (mudança pequena, escopo claro, baixa dependência)? Liste se vir.
4. **Rodar testes.** `pytest -q` funciona out-of-the-box? Precisa setar env var? Precisa do PostgreSQL ou SQLite serve?
5. **Entender naming híbrido pt-BR / en.** `_papeis_demo_disponiveis` vs `demo_login` — alguém de fora vai perguntar "por que essa mistura". Tem doc?

Não invente categoria de severidade nova só para esta seção — use P1/P2/P3 como nos outros. Mas marque com `[DX]` para destacar.

### §3.8 Padrões inconsistentes (Code seguiu, mas vale apontar?)

- Frontends têm boot scripts duplicados (§3.2). Code não extraiu por KISS. Vale apontar?
- `routers/demo.py` define `_papeis_demo_disponiveis` localmente. `config_publico.py` (linha ~29) usa a mesma lógica? Confere se há duplicação cross-arquivo.
- Outros routers (`prescricoes.py`, `dispensacoes.py`) usam helpers compartilhados em `app/auth/dependencies.py`. Por que `_reject_if_demo` não foi para lá? (Resposta: KISS por ser específico de demo. Mas valida.)

---

## §4 Anti-escopo (NÃO atacar nesta rodada)

CODEX está rodando em paralelo nestes pontos — não duplique:

- **Bypass de segurança em DB / login / `/demo/login`** — CODEX cobre §3.2-§3.4 do briefing dele.
- **Rollback de escrita + ledger** (`/demo/login` emite evento por engano? `seed_demo` emite?) — CODEX §3.5.
- **Verificação manual de isolamento DB / banner UI / instance_id no ledger** — CODEX §3.8.
- **Fidelidade aos 3 P1 e 7 P2/P3 do spec** — CODEX §3.1.

Você **pode** comentar se encontrar algo nesses pontos (CODEX agradece dupla checagem), mas concentre o esforço em qualidade/manutenibilidade/DX.

### Fora de qualquer rodada:

- **Etapa 5** (já fechada em `2bf5e7d`) — Tickets follow-up 5C #52/#53/#54 não tocar.
- **Etapas 7-8** (Dockerfile + deploy) — ainda não começaram.
- **Follow-ups do plano §9** (good-first-issues) — você pode SUGERIR candidatos a good-first-issue (categoria §3.7), mas não criar.

---

## §5 Verificação automatizada que você pode rodar

```bash
cd /Users/fabianotonacoborges/PicSaude_Dev

# 1. Complexidade ciclomática
pip install radon 2>/dev/null
radon cc backend/app/routers/demo.py backend/app/routers/config_publico.py \
         backend/app/routers/auth.py backend/app/routers/login.py \
         backend/seed_demo.py backend/scripts/reset_demo_db.py \
         -a -s

# 2. Métricas brutas (LOC, comentários)
radon raw backend/app/routers/demo.py backend/app/routers/config_publico.py \
          backend/seed_demo.py -s

# 3. Maintainability index
radon mi backend/app/routers/demo.py backend/app/routers/config_publico.py \
         backend/seed_demo.py -s

# 4. Duplicação simples (linhas idênticas em 2+ arquivos)
grep -c "_reject_if_demo" backend/app/routers/login.py backend/app/routers/auth.py
# Esperado: helpers locais; confirmar se a duplicação literal é só os 6 linhas do helper

# 5. Imports não usados (smell comum)
pip install pyflakes 2>/dev/null
pyflakes backend/app/routers/demo.py backend/app/routers/config_publico.py \
         backend/seed_demo.py backend/scripts/reset_demo_db.py

# 6. Suite focal (cross-check com CODEX)
cd backend && pytest tests/test_demo_mode.py tests/test_config_guards.py -v
```

---

## §6 Formato esperado da sua resposta

Padrão dos ciclos anteriores: `P1 / P2 / P3` numerados, com:

```
N. [Severidade] [Categoria opcional: DX | Dup | Naming | Type | Test | Doc]
   <arquivo:linha> — <descrição do achado>
   Decisão sugerida: <refactor | follow-up | aceitar como dívida>
```

Critério de fechamento da Etapa 6 (combinado CODEX + Jules):

- **CODEX zero P1** + **Jules sem P1 estrutural** → fechamos Etapa 6. Seus P2/P3 viram lapidações no §11 ou backlog.
- **CODEX P1** OU **Jules P1 estrutural** → follow-up commit antes de fechar.

Como você é complementar (não bloqueador principal), seu P1 só vira bloqueador real se for **estrutural** (ex: "essa duplicação vai causar bug daqui a 2 sprints porque..."). Achados de complexidade alta mas localizados normalmente são P2.

---

## §7 Histórico cumulativo (TICKET-6)

Esta é a **primeira rodada do Jules** no TICKET-6. Não há histórico de aceitação anterior para calibrar.

Contexto cumulativo do ticket inteiro:
- CODEX rodada 1 (pré-impl): 3 P1 + 4 P2 + 3 P3, taxa 10/10 (Arquiteto absorveu tudo).
- Code implementou em `94f73cd` seguindo spec à risca (auto-relato + verificação independente do Arquiteto).
- CODEX rodada 2 (pós-impl, em paralelo): em andamento agora.

**Sinal para você:** ticket já passou por revisão pré-impl. Achados estruturais grandes já foram capturados. Espere achados de granularidade fina — duplicação real entre os 5 frontends, complexidade de `/demo/login`, naming híbrido. **Não tenha medo de apontar P3 sutis** — é exatamente onde você adiciona valor sobre o CODEX.

### Atenção especial à categoria DX (§3.7)

Esta é a primeira rodada onde DX para extensionistas vira critério explícito. Sem histórico. Use o critério "estudante de 4º período de informática, primeira contribuição open-source da vida". Se você encontrar 3-5 atritos óbvios na onboarding, isso já é valor enorme.

---

*Aguardando seu retorno. Obrigado.*
— Arquiteto (Opus 4.7)
