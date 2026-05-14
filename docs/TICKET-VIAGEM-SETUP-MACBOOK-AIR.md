# TICKET — Setup do MacBook Air para trabalho remoto na viagem

> **Classe (CLAUDE.md §10):** `ops` (infraestrutura/setup) — Regra 4 (Edit direto, sem revisão CODEX)
> **Data:** 2026-05-14
> **Contexto:** Fabiano vai viajar — transição do Mac mini para o MacBook Air para continuar trabalho de Arquitetura (Cowork) durante a viagem. Sub-tarefa imediata a executar no Air: 4E.2 (Regra 5 — análise estática consolidada da Etapa 4).
> **Redigido por:** Arquiteto

---

## §1 Objetivo

Garantir que o MacBook Air esteja pronto para:

1. Receber o repositório PicSaúde em estado canônico (clone via GitHub, não iCloud)
2. Permitir que o Cowork (Arquiteto) leia e edite arquivos do projeto
3. Executar a sub-tarefa 4E.2 (disparo da Regra 5 — CODEX + Jules sobre diff acumulado)

A 4E.2 fecha a Etapa 4 (instance_id canônico). É **processo, não código** — não exige PostgreSQL local, venv, ou pytest no Air.

---

## §2 Decisão arquitetural — NÃO usar iCloud sync para o repo

`iCloud Drive > Desktop & Documents` é prático para arquivos pessoais, mas é uma armadilha para repositórios git. A fonte de verdade do PicSaúde é o GitHub (`Tonaco-13/PicSaude`), não o filesystem sincronizado.

**Sintomas conhecidos quando se confia em sync de filesystem para git:**

- `.git/index.lock` órfão entre máquinas
- arquivos `.DS_Store` proliferando
- conflitos de merge falsos
- corrupção do índice git em raros casos
- latência de sincronização (commits podem demorar minutos para aparecer)

**Regra:** repositório git é sincronizado **apenas via git** (`git pull`/`push`). iCloud, Dropbox, Google Drive, OneDrive — não para o repo.

---

## §3 Pré-requisitos no MacBook Air

Confirmar que existem (ou instalar):

| Item | Como verificar | Como instalar |
|---|---|---|
| Git | `git --version` (já vem com macOS) | Já presente |
| Homebrew | `brew --version` | `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"` |
| GitHub CLI (`gh`) | `gh --version` | `brew install gh` |
| App Cowork (Claude) | Aplicação aberta | Mesma instalação já usada no Mac mini |

**Não instalar (não precisa para 4E.2):**

- ❌ Python / venv
- ❌ PostgreSQL
- ❌ Banco `picsaude_test`
- ❌ Claude Code (sessão VS Code)

Esses só viram se a 4E.2 produzir achados que exijam implementação durante a viagem (improvável — análise estática produz na maioria das vezes lapidações P3 textuais ou tickets para depois).

---

## §4 Procedimento de setup (executar no MacBook Air)

### §4.1 Limpar pasta sincronizada (se houver)

```bash
# Se iCloud Drive sincronizou uma cópia da pasta:
ls ~/Desktop/PicSaude_Dev 2>/dev/null && echo "EXISTE — limpar primeiro"

# Se a saída foi "EXISTE — limpar primeiro":
rm -rf ~/Desktop/PicSaude_Dev
```

A cópia sincronizada **não é canônica** — pode estar incompleta, corrompida ou desatualizada.

### §4.2 Instalar Homebrew + GitHub CLI (se ainda não tiver)

```bash
# Verificar Homebrew
which brew

# Se não tiver, instalar:
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Depois (ou se já tinha Homebrew):
brew install gh
```

### §4.3 Autenticar no GitHub

```bash
gh auth login
#   Escolher: GitHub.com
#   Escolher: HTTPS
#   Autenticar via browser (mais simples — abre janela do Safari/Chrome)

# Confirmar
gh auth status
# Esperado: "Logged in to github.com as Tonaco-13"
```

### §4.4 Clonar o repositório

```bash
cd ~/Desktop

gh repo clone Tonaco-13/PicSaude PicSaude_Dev

cd ~/Desktop/PicSaude_Dev
```

### §4.5 Verificar estado canônico

```bash
git status
# Esperado: "On branch main / Your branch is up to date with 'origin/main'. /
#           nothing to commit, working tree clean"

git log --oneline -5
```

**Saída esperada do `git log`:**

```
0f87a2b  docs: marca 4E.1 como fechada (65181dc + a53d5ba); 4E.2 é o próximo passo
a53d5ba  docs(4e): briefing v2 + ticket completo + prompt-code da 4E.1
65181dc  test(4e.1): testes E2E consolidados da Etapa 4 (instance_id canônico)
a44582b  docs: marca OTP como resolvido (5fa6902) + versiona PROMPT-D
5fa6902  fix(security): OTP usa secrets + guard print por PICSAUDE_ENV (pré-Etapa 8)
```

Se a saída for diferente, **parar e escalar para o Arquiteto** antes de prosseguir.

### §4.6 Configurar workspace folder no Cowork

1. Abrir o app Cowork no MacBook Air (mesma conta usada no Mac mini)
2. Quando o Cowork pedir a workspace folder, selecionar manualmente `~/Desktop/PicSaude_Dev` (a pasta clonada agora — **não** a sincronizada por iCloud, se existir)
3. Confirmar que o Arquiteto consegue ler arquivos pedindo: *"Leia as primeiras 5 linhas do `backend/CLAUDE.md`"* — se conseguir, o setup está completo

---

## §5 Verificação automatizada (idempotente)

Roda esses comandos para confirmar tudo no lugar antes de começar a 4E.2:

```bash
cd ~/Desktop/PicSaude_Dev

# 1. Estado git limpo
git status
# Esperado: "working tree clean" e "up to date with 'origin/main'"

# 2. HEAD correto
git rev-parse HEAD
# Esperado: 0f87a2b...

# 3. Tickets 4E presentes (sanidade)
ls backend/docs/tickets/ | grep 4E
# Esperado: 4 arquivos (briefing + 1-consolidado + 1-prompt-code + 1-relatorio-integrado quando 4E.2 começar)

# 4. Teste 4E.1 presente
test -f backend/tests/integration/test_4e_e2e_consolidado.py && echo OK
# Esperado: OK

# 5. Configuração local de identidade git (se for fazer commits do Air)
git config --get user.name
git config --get user.email
# Se vazio, configurar:
#   git config --global user.name "Fabiano Tonaco Borges"
#   git config --global user.email "fabianotonaco@gmail.com"
```

---

## §6 Primeiro trabalho no Air — disparar 4E.2

Quando setup estiver pronto e Cowork respondendo, o primeiro passo é **disparar a 4E.2 (Regra 5)**. O briefing canônico está em `backend/docs/tickets/TICKET-4E-BRIEFING-PARA-CODEX.md` §4.

Comandos para coletar material da revisão:

```bash
cd ~/Desktop/PicSaude_Dev

# Panorama de commits da Etapa 4
git log d8abf7e^..HEAD --oneline > /tmp/etapa4-commits.txt

# Footprint da Etapa 4
git diff d8abf7e^..HEAD --stat > /tmp/etapa4-stat.txt

# Diff completo (backend apenas)
git diff d8abf7e^..HEAD -- backend/ > /tmp/etapa4-diff.patch

# Lista de arquivos tocados
git diff d8abf7e^..HEAD --name-only -- backend/ > /tmp/etapa4-files.txt

# Confirmar
wc -l /tmp/etapa4-*.txt /tmp/etapa4-diff.patch
```

Depois:

1. Colar o briefing para CODEX (`§4.3` do briefing) no CODEX + colar o conteúdo do `.patch`
2. Colar o briefing para Jules (`§4.4` do briefing) no Jules + colar o conteúdo do `.patch`
3. Trazer ambas as respostas para o Cowork (Arquiteto) integrar em `backend/docs/tickets/TICKET-4E-2-RELATORIO-INTEGRADO.md`

---

## §7 Limitações conhecidas no MacBook Air

| Limitação | Impacto na 4E.2 | Mitigação se precisar |
|---|---|---|
| Sem PostgreSQL local + `picsaude_test` | Nenhum — 4E.2 não roda pytest | Se aparecer achado P1 que exija teste, esperar voltar da viagem ou instalar PG no Air |
| Sem venv Python configurado | Nenhum — 4E.2 não executa código | Instalar se aparecer achado que exija `py_compile`/`mypy` |
| `.instance_id` será diferente do Mac mini | Nenhum — arquivo não está no repo (correto, é por instância) | Ignorar |
| Sessão Claude Code não disponível | Nenhum — implementação de fixes pode esperar volta da viagem | Instalar Claude Code apenas se imprescindível |

---

## §8 Quando voltar da viagem (sincronizar Mac mini)

No Mac mini, quando voltar:

```bash
cd ~/Desktop/PicSaude_Dev
git pull origin main
```

Isso traz para o Mac mini qualquer commit feito do Air (ticket 4E.2 ou docs atualizados durante a viagem).

Se durante a viagem você instalou algo no Air (Homebrew, gh) e quiser ter no Mac mini também, isso é independente — não vem com `git pull`. Mas o Mac mini provavelmente já tem.

---

## §9 Fora do escopo deste ticket

- Instalação de Python, PostgreSQL, venv, Claude Code no Air → só se a 4E.2 produzir achado que exija; nesse caso, ticket separado
- Configuração SSH para Git → HTTPS via `gh` é suficiente
- Backup do `.instance_id` do Mac mini → não faz sentido (cada instância tem o seu)
- Configuração do iCloud Drive → não tocar; só evitar que sincronize a pasta do repo
- Setup do Claude Code (VS Code) no Air → adiar até voltar a viagem

---

## §10 Resumo executivo (TL;DR)

1. **Antes de fechar o Mac mini:** confirmar `git status` limpo e `git log` mostrando `0f87a2b` no topo (✅ já feito hoje)
2. **No MacBook Air, primeira vez:** `brew install gh` → `gh auth login` → `rm -rf ~/Desktop/PicSaude_Dev` (se houver cópia iCloud) → `gh repo clone Tonaco-13/PicSaude ~/Desktop/PicSaude_Dev`
3. **No Cowork:** selecionar `~/Desktop/PicSaude_Dev` como workspace folder
4. **Primeiro trabalho remoto:** disparar 4E.2 via comandos do §6 acima
5. **Ao voltar:** `cd ~/Desktop/PicSaude_Dev && git pull origin main` no Mac mini

---

*Boa viagem.*
