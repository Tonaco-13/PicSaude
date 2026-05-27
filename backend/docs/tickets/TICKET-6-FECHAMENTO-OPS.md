# TICKET-6-FECHAMENTO-OPS — orquestrar fechamento formal da Etapa 6

> **Origem:** decisão de 2026-05-26 (Arquiteto + Fabiano) — fechar Etapa 6 hoje à tarde, antes da reunião com extensionistas amanhã 27/05.
> **Classe:** `ops` (commit + push + handoff para CODEX rodada 3; sem código novo).
> **Ritmo:** Regra 3 (ops, sem CODEX rodada 1).
> **Atores:** Fabiano (precondição manual) → Code (este ticket, §2) → Arquiteto (briefing CODEX) → CODEX rodada 3 → Arquiteto (§11 + docs + HTML).

---

## §1 Contexto

A Etapa 6 (DEMO_MODE + seletor de papéis) está em fechamento. Implementação inteira já pushada em origin/main:

- TICKET-6 ✅ `94f73cd` (feat(6) demo mode + 7 decisões)
- TICKET-6.1 ✅ `9eb7228` (fix(6.1) isolamento CNES + hidratação demo + guard JWT)
- Arquivamento ✅ `a01fec6` (docs(6) arquivar TICKET-6/6.1 + renumeração #56-58 → #59-61)
- TICKET-DX-PRE-EXTENSAO ✅ `5db20ef` (Jules P2#4 + P2#10)

HEAD atual de origin/main: `5db20ef` (terça 26/05).

**Working tree atual** (verificado em 2026-05-26 13:30):

```
 M docs/PLANO-PRODUCAO-V2.md
?? backend/docs/tickets/TICKET-5C-BIS-0-HELPER-OWNERSHIP.md
?? backend/docs/tickets/TICKET-6-FECHAMENTO-OPS.md    ← este ticket
```

**Briefings CODEX existentes** em `backend/docs/codex/`:

- `CODEX-RODADA-2-5C-POSTIMPL.md` (5C, fechado)
- `CODEX-RODADA-2-6-POSTIMPL.md` (Etapa 6 rodada 2 — já existente)
- `DIAGNOSTICO-IA-DEF-2026-05-25.md`
- `JULES-RODADA-FIM-ETAPA6.md`

**Não existe** ainda `CODEX-RODADA-3-6-POSTIMPL.md` — Arquiteto cria depois deste ticket fechar.

## §2 Escopo do Code (cirúrgico)

Este ticket pede ao Code **apenas** os passos de ops abaixo. Não há código novo a escrever, não há teste novo a rodar além do smoke.

### §2.1 Pre-flight

Confirmar estado:

```bash
cd ~/PicSaude_Dev
git status -sb   # deve mostrar: ## main...origin/main + 2 untracked + 1 modified
git log --oneline -3 origin/main   # confirma HEAD = 5db20ef
```

Se algo divergir (commits locais pendentes, modificações inesperadas), parar e reportar a Fabiano antes de prosseguir.

### §2.2 Smoke local

```bash
cd ~/PicSaude_Dev
pytest backend/tests/ -x --tb=short
```

Deve retornar zero falhas. Se houver regressão inesperada, parar e reportar.

### §2.3 Commit dos 2 untracked + 1 modificado

```bash
cd ~/PicSaude_Dev
git add docs/PLANO-PRODUCAO-V2.md \
        backend/docs/tickets/TICKET-5C-BIS-0-HELPER-OWNERSHIP.md \
        backend/docs/tickets/TICKET-6-FECHAMENTO-OPS.md

git commit -m "docs(plano): inserir Etapa 5C-bis entre 6 e 7 + spike v0.2 com CODEX rodada 0

- PLANO-PRODUCAO-V2 -> v2.1 (2026-05-26): MVP estendido (autorização
  nos 5 subdomínios sucessores) antes do deploy público; Etapa 5C-bis
  entre 6 e 7 + 5 tickets paralelos (A pedidos, B laudos, C agendamentos,
  D circulação, E hospitalar) + spike TICKET-5C-BIS-0.
- TICKET-5C-BIS-0-HELPER-OWNERSHIP v0.2: spike avaliativo do helper
  compartilhado de ownership (CODEX rodada 0 integrada — 0 P1 + 6 P2
  + 4 P3 aceitos; cenário mais provável: C \"_assert_or_403 + queries
  locais\").
- TICKET-6-FECHAMENTO-OPS: orquestração final da Etapa 6 (precondição
  Fabiano §4.2 + Code commit/push/smoke + Arquiteto briefing CODEX
  rodada 3 + §11 + relatório HTML).

Decisão MVP estendido: coerência com a definição do PicSaúde como
plataforma de circulação de objetos sanitários (receitas + agendamentos
+ pedidos de exame), não só ambulatorial."
```

### §2.4 Push

```bash
git push origin main
```

### §2.5 Confirmação

```bash
git log --oneline -3 origin/main
git status -sb
# Esperado: ## main...origin/main (sem ahead/behind) + working tree clean
```

## §3 Anti-escopo do Code

- **NÃO rodar o checklist §4.2 do TICKET-6.1.** É teste manual no browser (banner amarelo, redirect dos botões cidadão/prescritor/dispensador, tokens no DevTools, regressão de fluxo OTP). Fabiano roda antes de autorizar este ticket; o Code não tem como rodar headless sem Playwright.
- **NÃO redigir o briefing CODEX rodada 3.** É trabalho do Arquiteto, próximo passo do fluxo.
- **NÃO preencher §11 do TICKET-6** nem do TICKET-6.1. É trabalho do Arquiteto após CODEX rodada 3 voltar.
- **NÃO atualizar `PROMPT-OPUS-4.7-ARQUITETO.md` ou `CLAUDE.md`.** Arquiteto faz junto com o §11.
- **NÃO gerar o relatório HTML de fechamento.** Arquiteto faz como aplicação do padrão `decisao_artefatos_md_vs_html`.
- **NÃO commitar nada além dos 3 arquivos listados em §2.3.** Se aparecer modificação inesperada no working tree, parar e reportar.

## §4 Atores e ordem do fluxo de fechamento

Este ticket é uma das etapas; documento aqui o fluxo inteiro para o Code entender onde se encaixa.

| # | Ator | Tarefa | Output |
|---|---|---|---|
| 0 | **Fabiano** (precondição) | Roda checklist manual §4.2 do TICKET-6.1 — 7 itens no browser com `PICSAUDE_DEMO_MODE=true` | "Passa" (autoriza §1 deste ticket) ou "Falha" (Code redige TICKET-6.2 X.Y, ver §5 deste ticket) |
| 1 | **Code** (este ticket) | §2.1 → §2.5: pre-flight + smoke + commit + push + confirmação | Working tree limpo, origin/main com commit do plano |
| 2 | **Arquiteto** (Opus 4.7) | Redige `backend/docs/codex/CODEX-RODADA-3-6-POSTIMPL.md` apontando para HEAD pós-commit | Briefing pronto para acionamento CODEX |
| 3 | **CODEX** | Rodada 3 pós-impl sobre TICKET-6.1 — confirma se os 3 P1 da rodada 2 estão fechados em `9eb7228` | Parecer P1/P2/P3 (esperado: zero P1) |
| 4 | **Arquiteto** | Se zero P1: preenche §11 do TICKET-6 + atualiza PROMPT-OPUS-4.7-ARQUITETO.md + atualiza Etapa 6 no PLANO para ✅ + gera relatório HTML de fechamento (`docs/relatorios/RELATORIO-FECHAMENTO-ETAPA-6.html`). Se vier P1: aciona §5 deste ticket. | Etapa 6 fechada formalmente |

## §5 Plano B — se §4.2 ou CODEX rodada 3 falhar

Se Fabiano rodar §4.2 e algum item falhar:

- Code redige TICKET-6.2-FRONTEND-FIX em `backend/docs/tickets/` seguindo o pacto calibrado 2026-05-24 (Code redige X.Y após falha frontend manual ou CODEX P1).
- Spec do 6.2 deve cobrir o item específico que falhou (qual botão não redirecionou, qual token não apareceu, etc.) + critério de aceite + verificação automatizada se possível.
- Fluxo de fechamento da Etapa 6 reabre após 6.2 mergeado, voltando ao §4 deste ticket.

Se CODEX rodada 3 vier com P1:

- Code redige TICKET-6.3 (ou usa o slot 6.2 se ainda livre) seguindo mesma calibração.
- Arquiteto coordena cross-revisor se houver achados em paralelo.

## §6 Critérios de aceite (Code)

1. `git status -sb` após §2.5 mostra `## main...origin/main` sem ahead/behind e working tree limpo.
2. `git log --oneline -1 origin/main` mostra commit cuja mensagem começa com `docs(plano): inserir Etapa 5C-bis`.
3. `pytest backend/tests/ -x` em §2.2 retornou zero falhas.
4. Os 3 arquivos listados em §2.3 estão no commit (verificável via `git show HEAD --stat`).

## §7 Verificação automatizada (Code roda ao final)

```bash
cd ~/PicSaude_Dev
git status -sb                                    # ## main...origin/main + clean
git log --oneline -1 origin/main | grep "5C-bis"  # match
git show HEAD --stat | grep -E "PLANO-PRODUCAO|5C-BIS-0|FECHAMENTO-OPS"  # 3 arquivos
```

## §8 Predecessoras

- HEAD pré-commit deste ticket: `5db20ef`.
- TICKET-DX-PRE-EXTENSAO já em main desde 26/05 (`5db20ef`).
- TICKET-6 e TICKET-6.1 já em main desde 24/05.
- Checklist §4.2 do TICKET-6.1 ✅ por Fabiano **antes** de Code iniciar §2.

## §9 Classe, volume, ritmo

- **Classe:** `ops` (commit + push + smoke; sem código novo).
- **Volume:** 1 commit em 3 arquivos.
- **Ritmo:** Regra 3 — Code Edit/Bash direto, sem CODEX rodada 1 sobre este ticket.

## §10 Prompt sugerido ao Code

Você pode executar este ticket sequencialmente: §2.1 → §2.2 → §2.3 → §2.4 → §2.5. Verificação em §7 ao final. Spec auto-contida; anti-escopo em §3 evita expansão; plano B em §5 para caso algo falhar antes ou depois.

**Importante:** este ticket roda **apenas após Fabiano confirmar que §4.2 do TICKET-6.1 passou**. Sem essa autorização, parar.

Após você fechar §2.5, Arquiteto entra com o próximo passo (briefing CODEX rodada 3 em `backend/docs/codex/`).

---

## §11 Reservado — output do Code

*Preenchido pelo Code ao fechar §2.5: HEAD pós-commit, output do smoke, qualquer observação inesperada.*
