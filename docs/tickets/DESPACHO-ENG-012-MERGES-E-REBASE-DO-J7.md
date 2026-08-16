# DESPACHO ENG-012 — Fase de merges da série J: #163/#164 → rebase do #165 (J.7) → J.11 · migração da custódia (condicionada)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-012 (orquestração da fila de merges pós-série J) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Fabiano (martelos pendentes, §2) |
| **Data** | 2026-08-16 |
| **Origem** | Handoff de 15/08 · parecer `SESSAO-2026-08-15-PARECER-ARQUITETO-J7-PRS.md` · bloco Fabiano.md de 15/08 (fecho) |
| **Base** | `main` em `097534a` (pós-merge #162). PRs #163 (`ops`) · #164 (`module`) · #165 (`core`, base no #164) — todos OPEN, CI verde (gates + smokes), MERGEABLE. Nada mergeado desde #162. |
| **Classes** | #165/J.7 = **`core`** (martelo no PR pendente) · J.11 = `module` · migração da custódia = **`core`** (martelo de abertura pendente) · J.10 = `module` (sobre a migração) |

---

## §1 Contexto — estado verificado pelo arquiteto em 16/08

Série J completa e entregue em PRs. O caminho crítico agora **não passa pelo engenheiro**:
passa pelos martelos do Fabiano (§2). Este despacho organiza a fila para que, a cada merge
dele, você execute o passo seguinte sem esperar nova ordem — cada fase abaixo tem gatilho
explícito.

## §2 O que está com quem

| Item | Classe | Estado | Quem detém |
|---|---|---|---|
| #163 (CNES no boot) | `ops` | Aprovado (ENG-011-REVISÃO) | **Fabiano** — ordem/merge |
| #164 (abas J.8/J.9 + 403) | `module` | Aprovado (idem) | **Fabiano** — ordem/merge |
| #165 (J.7, core) | `core` | Aprovado pelo arquiteto (J7-PRS §1) | **Fabiano** — martelo no PR (após rebase, §5) |
| Migração "custódia ganha posse atual" | `core` | Desenho pronto, caminho (b) aprovado | **Fabiano** — martelo de abertura (§7) |
| J.10 (custódia parcial) | `module` | Desenhado (`DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`) | Bloqueado pela migração acima |
| Micro-ticket RBAC agendamentos | `core` | Formulação pronta | Martelo no combo do J.10 |

## §3 Regra do Fabiano (vale como em ENG-010/011)

> *"Na implementação, o engenheiro deve avaliar os fixes propostos. Se discordar de algum
> ponto técnico, não segue em frente — retorna o problema ao arquiteto para reavaliação
> antes de qualquer alteração no código."*

Vale para §5–§7. E o corolário operacional deste despacho: **conflito de rebase não
trivial = para e reporta** — nada de resolução criativa em branch `core`.

## §4 FASE 1 — merges de #163 e #164 (Fabiano)

Nada para você aqui. **Proibido:** mergear, rebasear, fazer push ou "ajudar" nestes PRs.
Depois do merge do #164 (squash, como o resto do histórico), siga direto para §5.

## §5 FASE 2 — a dança do rebase do #165 (gatilho: #164 mergeado)

Mesma dança do #162. Objetivo: PR `core` #165 passa a basear na `main` com **exatamente o
mesmo conteúdo** que o arquiteto revisou (`851dfe0`).

1. `git fetch origin --prune`
2. `git checkout core/j7-transferir-e-posse && git rebase origin/main`
   - Esperado: o rebase **pula** o commit do #164 (já aplicado upstream via squash) e
     replays **apenas** o commit J.7. Resultado: um commit, mensagem preservada.
3. Se o GitHub não retargetar sozinho (deleção de `module/abas-j8-j9` normalmente faz):
   `gh pr edit 165 --base main`
4. `git push --force-with-lease origin core/j7-transferir-e-posse`
5. Conferir: CI (gates + smokes) verde, base `main`, MERGEABLE, e o diff do PR ==
   conteúdo do `851dfe0` (nenhum hun a mais ou a menos). Rodar gates locais antes de
   reportar, como de costume.
6. Reportar e **PARAR**. O merge é somente após martelo do Fabiano **no PR** (padrão
   `core`); se ele ordenar, você executa o clique sob ordem dele.

**Stop conditions (para e devolve ao arquiteto):** conflito que não seja trivial;
rebase que altere conteúdo além do replay (huns extras/sobrando); testes que pipocam
sem causa óbvia pós-rebase.

## §6 FASE 3 — J.11 (`module`), gatilho: #165 mergeado

Já despachado no parecer J7-PRS §2, ACs dos Adendos §10/§11b do ENG-011 aplicáveis
integralmente. Recapitulando o escopo:

1. **Selo de agendamento** no cartão do exame (aba Exames do `cidadao.html`): leitura com
   papel `paciente`, agendamento ATIVO, remarcação = derivado mostra o corrente. Zero
   transição de custódia, zero evento novo, zero escrita.
2. **Lente compartilhada:** extrair o render da Lente de Auditoria (`index.html`) em
   componente compartilhado; index intocado na função; "ver rastreabilidade" por cartão via
   `/public/*` (intocados — são `core`).

PR `module` próprio, base na `main` pós-#165. Gates completos + E2E browser cobrindo
cidadão transfere → laboratório agenda → cidadão vê data/hora/unidade no cartão sem sair
da aba.

## §7 FASE 4 — PR `core` "custódia de exame ganha posse atual" (CONDICIONADO a martelo)

**Não inicia sem martelo explícito do Fabiano** registrado (migrar cadeia de custódia é
`core`, taxonomia §10). Formulação travada com o desenho do J.10 (caminho (b), aprovado):

- `encerrada_em` em `pedido_exame_custodia` + **índice único parcial** (uma posse ativa
  por item/pedido) **nos dois dialetos** (SQLite + PostgreSQL do DDL-doc);
- **data-fix na migração** (fechar linhas históricas conforme posse corrente);
- **choke-point** `transferir_posse_exame` (toda escrita de custódia de exame passa por ele);
- migrar os **3 sítios de leitura "última linha"** para a nova semântica (inclui os helpers
  que o J.7 introduziu — `detentor_atual_pedido`/`posse_do_cidadao` — que hoje varrem o
  ledger; baseia-se na `main` pós-#165 para não retrabalhar).

Branch da `main` **após o merge do #165`** (evita pilha e choque nos mesmos sítios).
Pode correr em paralelo com o J.11 (áreas distintas), a seu critério de ritmo.

Sobre ele empilha o **J.10** (`module`: `itens:[...]` opcional no
`transferir-laboratorio`, `/devolver` por item, fila por custódia com anti-vazamento
entre prestadores — AC (vi)), que viaja com o **micro-ticket `core`** do RBAC assimétrico
(`GET /pedidos-exame/{p}/agendamentos` recusa `dispensador`; POST aceita) — este com
martelo próprio no PR. Detalhes: `DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`.

## §8 Render / vitrine

Reset da vitrine é do Fabiano (runbook entregue; hora certa: após merge do #163 no
mínimo). Sua parte: prontidão para conferir com ele a linha
`[cnes-demo] snapshot CNES garantido` no log de boot pós-redeploy. **Nunca mais re-rodar
o snippet CNES à mão** — o boot recria sozinho (lição do #163).

## §9 Registro, limites e pendências

- Relatório em `docs/tickets/SESSAO-2026-08-16-TICKET-ENG-012-*.md` (padrão da casa),
  com evidências (SHA antes/depois do rebase, links de CI, diffs conferidos).
- **Não commita sem ordem** — inclui os docs não versionados (Fabiano.md, pareceres,
  despachos, `planejamento/`): aguardam decisão dele sobre quem commita.
- Fora do escopo (constar apenas): 401 "Signature verification failed" na vitrine
  (vigilância); `test_concorrencia.py` que não coleta (dívida conhecida da main).

---

*Despacho emitido pelo arquiteto (Z) em 2026-08-16, na sequência do parecer J7-PRS e do
handoff de 15/08. Martelos pendentes do Fabiano: (1) ordem/merge de #163+#164; (2) martelo
no PR #165 pós-rebase; (3) martelo de abertura da migração `core` da custódia (§7).*

---

## §10 Adendo (2026-08-16, mesmo dia) — Fabiano autoriza TUDO e viaja: rodada autônoma do engenheiro

> Registro do martelo: em 16/08, às vésperas de viajar, o Fabiano respondeu **"tudo
> autorizado"** aos três martelos pedidos pelo arquiteto (chat do arquiteto). Este adendo
> é o registro durável dessa autorização e define o protocolo de execução autônoma.

### (a) O que foi autorizado

1. **Merges de #163 e #164** — executados pelo **engenheiro** (squash + delete branch),
   sob ordem explícita. Nenhum é `core`.
2. **Martelo antecipado no #165 (J.7, `core`)** — merge autorizado **condicionado ao
   protocolo (b) abaixo**. A condição substitui o "martelo no PR" presencial: o conteúdo
   mergeado é provadamente o mesmo que o arquiteto revisou e o Fabiano martelou (15/08,
   regra do J.7).
3. **Abertura da migração `core` da custódia (§7)** — implementação liberada. **O MERGE
   desse PR futuro NÃO está autorizado**: pede martelo próprio do Fabiano no PR, no
   retorno dele. É o ponto de parada da rodada autônoma.
4. **J.11 (`module`)** — execução e merge sob a ordem geral (module não pede martelo),
   com **revisão retroativa** do arquiteto na sessão seguinte; achado vira ticket de
   correção (fix-forward).
5. **PR `docs`** — commit dos arquivos não versionados (despachos, pareceres, relatórios,
   `Fabiano.md`, `planejamento/`, incluído este despacho e adendo).

### (b) Protocolo do #165 — green light do arquiteto PRÉ-DADO, de forma mecânica

Fundamentação (verificada pelo arquiteto em 16/08): #163, #164 e o delta do #165 são cada
um **exatamente 1 commit**; a interseção de arquivos entre o J.7 e o #163 é **vazia**;
o squash de #164 single-commit produz árvore idêntica à de `a7ddb58`. Logo, um rebase
limpo tem resultado determinístico — e a prova é verificável por igualdade de patch.

Condições CUMULATIVAS para o merge do #165 (todas precisam constar do relatório):

1. `git log --oneline origin/main..HEAD` pós-rebase = **exatamente 1 commit**, mensagem
   do J.7 preservada (replay puro, sem squash/reescrita);
2. `diff` **vazio** entre `git diff a7ddb58 851dfe0` (patch revisado, salvar ANTES de
   rebasear) e `git diff origin/main..HEAD` (pós-rebase, pré-push);
3. CI verde (gates + smokes) e PR MERGEABLE na base `main`.

**As três seguram → merge autorizado (martelo antecipado). Qualquer uma falha → NÃO
mergeia**, deixa o PR pronto com a evidência da divergência e reporta — sem improvise.

### (c) Limites inalterados da rodada

- Regra §3 (discordância técnica = para e devolve) vale o tempo todo.
- Nenhum merge `core` fora do protocolo (b); migração e J.10 **não** se auto-mergeiam.
- Render/reset da vitrine: **fica para o Fabiano** (exige dashboard; a vitrine pode
  esperar a volta dele).
- Relatório único da rodada em `SESSAO-2026-08-16-TICKET-ENG-012-*.md`, com SHAs
  antes/depois, os dois patches comparados, links de CI e o estado final da fila.
