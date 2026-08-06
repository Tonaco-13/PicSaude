# DESPACHO ENG-006 — Rebase do PR #130 (remoção do seed órfão + regra de fronteira)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-006 |
| **De** | Arquiteto (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) — despachar handoff ao Kimi 3 |
| **Data** | 2026-08-04 |
| **Origem** | Martelo do Fabiano: ordem de merge aprovada (`#131 → #132 → #129/#133/#134 → #130 pós-rebase`); acréscimo do Conselheiro: causa-raiz do 🔴 é fronteira (PR de frontend carregando seed de backend) |
| **Parecer Fable 5** | VERMELHO por §2/§3 (objeto órfão sem elo de origem) — ratificado pelo arquiteto em `TICKET-REVIEW-RATIFICACAO-PR129-134` |

---

## §1 O que houve (verificação independente do arquiteto)

O PR **#130** (`local-extension/demo-ux-logo-a11y-autologin`, Kimi 3) carrega **duas funções de seed de backend** em `backend/seed_demo.py`:

- `_garantir_pedido_exame_ativo` (linha 363)
- `_garantir_laudo_demo` (linha 445)

Estas funções **duplicam** o trabalho do PR **#131** (`module/seed-exames-demo`) — os mesmos 3 protocolos sentinela (`DEMO-EXAME-0001`, `DEMO-EXAME-0002`, `DEMO-LAUDO-0001`).

E pior: a versão do #130 é **pré-errata** — falta-lhe o **elo de origem** `pedido_exame_custodia (de='prescritor', para='paciente')` que a errata `ec2708c` do #131 adicionou. Sem esse elo, o `DEMO-EXAME-0002` nasce **órfão** (CLAUDE.md §2/§3: objeto sem elo de origem é órfão).

Confirmação por contagem de INSERTs de custódia na função `_garantir_laudo_demo`:

| Branch | `pedido_exame_custodia` | `laudo_custodia` |
|---|---|---|
| #131 (canônico) | `prescritor→paciente` **+** `paciente→laboratório` (2) | `prestador→paciente` (1) |
| #130 (órfão) | só `paciente→laboratório` (1) | `prestador→paciente` (1) |

O delta é **uma linha** — o elo de origem. Isso é exatamente o que `ec2708c` corrigiu.

## §2 Causa-raiz (acréscimo do Conselheiro)

**Fronteira violada.** O #130 é um PR de **frontend** (Kimi 3, `local-extension`) carregando funções de **seed de backend**. As duas branches implementaram o mesmo seed independentemente a partir de `main` (que não tem o seed) — a versão do #130 é pré-errata porque foi cortada antes de `ec2708c`.

A correção pontual (adicionar o elo ao #130) **não resolve a causa-raiz** — apenas remendaria uma das duas cópias divergentes. O remédio é **remover o seed do #130** e herdar o canônico do #131 via rebase.

## §3 Estado atual (rebase já executado pelo Engenheiro, 2026-08-04)

O rebase **já foi feito** pelo Engenheiro nesta sessão. O estado é:

- **Branch rebaseada:** `local-extension/demo-ux-logo-a11y-autologin` → `9ceb54e` (era `56ae7a6`).
- **Backup preservado:** `backup/demo-ux-pre-rebase` (`56ae7a6`).
- **Base de integração:** `tmp/integration-131-132` (`38538c9`) = `origin/main` (`67d0bf8`) + merge de #131 (`2fa8a75`) + merge de #132 (`38538c9`).
- **Delta da branch contra a base:** 6 arquivos de UX, **zero backend clínico** (`seed_demo.py`/`demo.py`/`config_publico.py` byte-idênticos à base).

O que o Engenheiro fez (verificado independentemente pelo arquiteto):
- Removeu de `backend/seed_demo.py`: as 2 funções (`_garantir_pedido_exame_ativo`, `_garantir_laudo_demo`), suas 2 chamadas em `main()`, o dict `CLINICA` e o bloco prestador-clínica. O arquivo ficou byte-idêntico ao da base (canônico do #131, com o elo de origem).
- Não tocou em `demo.py` nem `config_publico.py` (vêm só do #131).
- Reconciliou `clinica.html`: banner demo + hidratação + `_autoLoginDemo` do #132; logo clicável + `.mock-tag` nos 3 `laudo-aguardo` do #130. Regiões disjuntas — auto-merge limpo.
- Amendou a mensagem do commit registrando a remoção do seed e a causa §3.

**Portanto, o trabalho de remoção do órfão está COMPLETO.** O que falta é o push pós-merge (§3.1 abaixo), com guarda específica para o estilo de merge (squash vs merge-commit) que o #131/#132 usarem.

### §3.1 Sequência de push pós-merge (a executar QUANDO #131 + #132 estiverem em `main`)

**Pré-condição bloqueante:** #131 + #132 mergeados em `main` E deploy confirmado no Render (status `live`).

O repositório usa **dois estilos de merge** (`#125` = merge commit; `#126`/`#127` = squash). A sequência abaixo trata os dois casos.

```bash
# 0. Branch de trabalho
git checkout local-extension/demo-ux-logo-a11y-autologin
git fetch origin

# 1. Rebasear contra a main atualizada (pós-merge do #131/#132)
git rebase origin/main
```

**O que esperar no passo 1 — duas bifurcações:**

- **Se #131/#132 entraram como merge commit:** o `rebase` detecta via patch-id que os 5 commits do #131/#132 já estão em `main` e os descarta automaticamente. Só replaya os 2 commits do #130 (`947aa6d`, `9ceb54e`). Limpo, sem intervenção.

- **Se #131/#132 entraram como squash:** o `rebase` pode **não reconhecer** os commits originais (patch-id mudou). Pode dar conflito em `backend/seed_demo.py` ou tentar reintroduzir os patches. **Neste caso:**
  - Se der conflito: **NÃO resolver sozinho**. Pausar e chamar o arquiteto. O conflito esperado é "both added" em `seed_demo.py` — a solução é aceitar a versão de `origin/main` (que já tem o elo), descartar a da branch.
  - Se tentar reintroduzir patches sem conflito (silently): o passo 2 abaixo pega.

```bash
# 2. Conferir o delta — CRÍTICO, é a guarda
git diff --stat origin/main HEAD
```

**Critério de aceite do passo 2** — deve mostrar EXATAMENTE estes 6 arquivos, nenhum outro:

```
backend/tests/browser/test_demo_sem_login.py | 69 ++++++++++++
cidadao.html                                 | 34 +++++-
clinica.html                                 | 22 +++-
dispensador.html                             |  5 +-
prescritor.html                              | 156 +++++++++++++++++++--------
validar.html                                 |  5 +-
```

**Se aparecer qualquer arquivo além desses 6 — especialmente `backend/seed_demo.py`, `backend/app/routers/demo.py` ou `backend/app/routers/config_publico.py` — PARAR e chamar o arquiteto antes do push.** Significa que o rebase reintroduziu patches do #131/#132 (caso squash).

```bash
# 3. Só então: push
git push --force-with-lease origin local-extension/demo-ux-logo-a11y-autologin
```

### §3.2 Por que `--force-with-lease` e não `--force`

`--force-with-lease` falha se alguém mais (outro agente, o Fabiano) tiver empurrado para a branch desde o seu último fetch. É a forma segura de reescrever histórico sem sobrescrever trabalho alheio. Em pasta compartilhada, isto é **defense in depth**.

### §3.3 Se o passo 2 falhar (delta sujo)

Cenário: o `git diff --stat` mostra `seed_demo.py` ou `demo.py` no delta. Significa: o squash do #131/#132 não foi reconhecido pelo rebase, e os patches originais foram replayed por cima do conteúdo já em `main`.

**Recuperação** (executar só com confirmação do arquiteto):

```bash
# Abortar o rebase se ainda em andamento
git rebase --abort

# Estratégia alternativa: cherry-pick só dos 2 commits do #130 sobre main limpa
git checkout -b local-extension/demo-ux-logo-a11y-autologin-2 origin/main
git cherry-pick 947aa6d 9ceb54e   # só os 2 commits de UX
# conferir delta (passo 2 de novo)
git diff --stat origin/main HEAD
# se limpo: trocar a branch de ponteiro
git branch -f local-extension/demo-ux-logo-a11y-autologin local-extension/demo-ux-logo-a11y-autologin-2
git push --force-with-lease origin local-extension/demo-ux-logo-a11y-autologin
```

Os 2 commits `947aa6d` e `9ceb54e` são **pura UX** (frontend + 1 arquivo de teste de browser) — cherry-pick limpo sobre `main` não toca backend.

## §4 ⚠️ NÃO fazer (cuidados explícitos)

**Já executado (estado atual):**
- ~~Remover adições de `seed_demo.py`~~ — FEITO pelo Engenheiro (byte-idêntico à base).
- ~~Reconciliar `clinica.html`~~ — FEITO (regiões disjuntas, auto-merge limpo).

**Ainda vigora:**
- **Não** empurrar antes de #131 + #132 estarem em `main` + deploy confirmado (reintroduz patches, ver §3.1).
- **Não** usar `git stash` (pasta compartilhada — ver TICKET-OPS-WORKTRES-POR-AGENTE).
- **Não** fazer reset da demo DB (isso é `DESPACHO-OPS-001`, depois do #131 em `main`).
- **Não** pular o passo 2 da §3.1 (a guarda do `git diff --stat`) — é a única barreira contra reintrodução silenciosa de patches em cenário squash.

## §5 Critérios de aceite

O trabalho de remoção do órfão está **CONCLUÍDO** (verificado pelo arquiteto contra a branch `9ceb54e`). O PR #130 estará pronto para merge quando:

1. ✅ #131 + #132 mergeados em `main` + deploy confirmado no Render.
2. ✅ Sequência §3.1 executada (rebase contra `origin/main` pós-merge).
3. ✅ `git diff --stat origin/main HEAD` mostra **exatamente** os 6 arquivos de UX (§3.1 passo 2). **Sem `seed_demo.py`, `demo.py` ou `config_publico.py`.**
4. ✅ `backend/seed_demo.py` na branch é byte-idêntico ao de `origin/main` (elo de origem herdado do #131).
5. ✅ `clinica.html` reconciliado com o #132 (sem perda de features do #132) — **verificado**, manter na conferência pós-push.
6. ✅ CI verde após o push.
7. ✅ UX do #130 preservada (logo clicável, a11y, auto-login demo, mock sinalizado de emissão de laudo).

## §6 Regra permanente de fronteira (incluir no handoff do Kimi 3)

> **`backend/seed_demo.py` (e qualquer arquivo sob `backend/`) nunca viaja em PR de `local-extension` cujo escopo seja UI.**
>
> A causa-raiz do órfão §3 no #130 foi a violação de fronteira: um PR de frontend implementando seed de backend, gerando uma cópia divergente (pré-errata) que bifurcou do canônico. Frontend consome o contrato; não o semeia.

Esta regra vale para **todos os PRs futuros de UI**, não apenas para o #130.

## §7 Protocolo de pasta compartilhada (regra permanente)

- **`git branch --show-current` antes de todo commit.**
- **`git add <arquivo>` sempre, nunca `git add .` / `-A`.**
- Trabalho alheio no seu caminho: pause e relate.

## §8 Após o push (fluxo de merge do #130)

O push é o **último passo antes do merge do #130** — vem depois de #131, #132, #129, #133, #134 já em `main`. Ordem ratificada pelo Fabiano (2026-08-04):

```
#131 → #132 → (#129, #133, #134) → [#3.1 deste despacho: rebase + conferir + push] → #130
```

1. #131 + #132 (+ #129/#133/#134) mergeados em `main`, deploy confirmado.
2. Executar §3.1 (fetch → rebase → **conferir delta = 6 arquivos** → `--force-with-lease`).
3. O PR #130 no GitHub passa a refletir só o delta UX limpo.
4. Aguardar novo review do Revisor + ratificação do arquiteto (rápido — delta só frontend).
5. Fabiano mergea o #130.
6. Executar `DESPACHO-OPS-001` (reset da demo DB) — este é o passo final, que põe a demo no ar atualizada.

## §9 Coordenadas

| Artefato | Caminho |
|---|---|
| Ratificação completa | `docs/tickets/TICKET-REVIEW-RATIFICACAO-PR129-134.md` |
| Seed canônico (a herdar) | #131 branch `module/seed-exames-demo` |
| Errata que adicionou o elo | commit `ec2708c` no #131 |
| Estados de exame/laudo | `CLAUDE.md` §5a/§5b |
| Worktrees por agente | `docs/tickets/TICKET-OPS-WORKTRES-POR-AGENTE.md` |

---

*Despacho emitido pelo arquiteto. Lista exata verificada contra diffs reais. Martelo do Fabiano recebido: ordem de merge aprovada.*
