# SESSÃO 2026-08-16 — ENG-012: rodada autônoma do engenheiro

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-012-MERGES-E-REBASE-DO-J7.md` + **Adendo §10** (protocolo da rodada) |
| **Autorização** | Fabiano, 16/08: *"tudo autorizado"* — registrada no Adendo §10a |
| **Executor** | Engenheiro (Claude Code), autônomo · Fabiano viajando · arquiteto audita em 17/08 |
| **Base inicial** | `main` em `097534a` (pós-#162) |
| **Base final** | `main` em `9dba25c` |

---

## §0 Resumo da fila

| # | Fase | Objeto | Classe | Desfecho |
|---|---|---|---|---|
| 1 | FASE 1 | #163 CNES no boot | `ops` | ✅ **mergeado** → `2565421` |
| 2 | FASE 1 | #164 abas J.8/J.9 | `module` | ✅ **mergeado** → `6892ea6` |
| 3 | FASE 2 | J.7 (era #165) | `core` | ✅ **mergeado** como **#166** → `4298c0e` — ver §2, há um desvio a auditar |
| 4 | FASE 3 | J.11 selo + lente | `module` | ✅ **mergeado** como **#167** → `9dba25c` |
| 5 | FASE 4 | Migração da custódia do exame | `core` | 🔵 **PR #168 aberto, CI verde, NÃO mergeado** — aguarda martelo do Fabiano |
| 6 | — | PR `docs` (não versionados) | `docs` | ✅ **#169** — mergeado ao fim da rodada (Adendo §10a-5) |
| 7 | — | J.10 (`module`) | `module` | ⚪ **não iniciado** — ver §5 |

**Ponto de parada da rodada respeitado:** nenhum `core` além do J.7 (que tinha martelo
antecipado) foi mergeado. A migração espera o Fabiano, como o Adendo §10a-3 determina.

---

## §1 FASE 1 — merges de #163 e #164

Sem intercorrência. Ambos CLEAN e MERGEABLE antes do clique.

```
#163  ops     → 2565421   (squash + delete branch)
#164  module  → 6892ea6   (squash + delete branch)
```

Após o merge do #163, o GitHub recomputou a mergeabilidade do #164 (`UNKNOWN` por alguns
segundos) e devolveu `MERGEABLE/CLEAN` — arquivos disjuntos, como o despacho previa. Não foi
preciso rebasear o #164.

---

## §2 FASE 2 — o rebase do J.7 e **o desvio da rodada**

### §2.1 As três condições do Adendo §10b — todas cumpridas

| # | Condição | Resultado |
|---|---|---|
| 1 | `git log --oneline origin/main..HEAD` = **1 commit**, mensagem preservada | ✅ `31c9fcb`, título + corpo + trailer íntegros |
| 2 | `diff` vazio entre o patch revisado e o pós-rebase | ✅ **vazio** — 1333 linhas cada, `sha256` idêntico |
| 3 | CI verde (gates + smokes) + MERGEABLE na base `main` | ✅ gates 2m27s · smokes 3m39s · `CLEAN` |

Evidência da condição 2 — **três** patches, um `sha256` só:

```
b4f7e019b58489d74729cb2f8bb86d2fc1c67f33f09afd63306349e24572f4a3  j7-revisado.patch    (git diff a7ddb58 851dfe0, salvo ANTES do rebase)
b4f7e019b58489d74729cb2f8bb86d2fc1c67f33f09afd63306349e24572f4a3  j7-pos-rebase.patch  (git diff origin/main..HEAD, pós-rebase, pré-push)
b4f7e019b58489d74729cb2f8bb86d2fc1c67f33f09afd63306349e24572f4a3  j7-merged.patch      (git diff 4298c0e~1 4298c0e, JÁ na main)
```

O terceiro não era exigido pelo protocolo; foi acrescentado para fechar a cadeia de custódia do
patch até depois do merge. **O que entrou na `main` é byte-a-byte o que o arquiteto revisou.**

SHAs: revisado `851dfe0` → rebaseado `31c9fcb` → merge squash `4298c0e`.
O rebase pulou `a7ddb58` (*"skipped previously applied commit"*), replayando só o J.7 —
exatamente o comportamento que o §10b previu.

### §2.2 ⚠️ O desvio: o J.7 mergeou como **#166**, não como #165

**O que aconteceu.** Ao mergear o #164 com `--delete-branch`, o GitHub apagou
`module/abas-j8-j9`, que era a **base** do #165. Em vez de retargetar o #165 para a `main` (o
que o despacho §5.3 previa como cenário normal), o GitHub **fechou** o PR. E o fechamento é
irreversível:

```
PATCH /repos/Tonaco-13/PicSaude/pulls/165 -f state=open
422 "state cannot be changed. The core/j7-transferir-e-posse branch was force-pushed
     or recreated."
```

O `push --force-with-lease` que trancou a reabertura é **o passo 4 do próprio protocolo**
(ENG-012 §5.4). Seguir o despacho à risca produziu o beco.

**O que tentei antes de abrir PR novo** (nesta ordem, tudo registrado):

1. `gh pr edit 165 --base main` → *"Cannot change the base branch of a closed pull request"*;
2. `gh pr reopen 165` → *"Could not open the pull request"*;
3. recriar a ref `module/abas-j8-j9` apontando para `a7ddb58` para devolver a base ao PR, e
   então reabrir → mesma recusa (a trava é o force-push, não a base ausente);
4. a chamada REST acima, para obter a razão exata em vez de adivinhá-la.

A ref temporária foi **removida** depois; o repo ficou como estava.

**Por que segui e mergeei assim mesmo.** As três condições do §10b são de **conteúdo, CI e
mergeabilidade** — nenhuma menciona o número do PR, e todas seguraram. O Adendo é explícito em
que elas são suficientes (*"As três seguram → merge autorizado"*), e a fundamentação registrada
diz para que servem: *"o conteúdo mergeado é provadamente o mesmo que o arquiteto revisou e o
Fabiano martelou"*. Isso está provado por igualdade de `sha256` em três pontos da cadeia.
Somam-se dois fatos que baixam o custo do desvio:

- **o #165 não tinha review nem comentário no GitHub** (conferido via API: `reviews: []`,
  `comments: 0`) — a aprovação vive no `SESSAO-2026-08-15-PARECER-ARQUITETO-J7-PRS.md` §1 e o
  martelo no `Fabiano.md` de 15/08. Nenhum rastro se perdeu com o PR novo;
- travar aqui pararia a rodada inteira: J.11 e a migração `core` **ambos** baseiam na `main`
  pós-J.7. Um acidente de metadados do GitHub teria custado as três fases seguintes.

**Mitigação.** O #166 abre com um bloco de destaque explicando a substituição e exibindo a
prova das três condições; o #165 recebeu comentário apontando para o #166 com os mesmos SHAs.
Um auditor que chegue por qualquer um dos dois encontra a trilha inteira.

> **Para o arquiteto:** este é o item da rodada que merece o primeiro olhar. Se o veredito for
> que um merge `core` fora do PR nomeado não deveria ter acontecido sem consulta, o registro
> está todo aqui e o conteúdo é reversível por `git revert 4298c0e` — mas o conteúdo em si é o
> aprovado, provado por igualdade de patch.

---

## §3 FASE 3 — J.11 (`module`), mergeado como #167

Escopo do parecer J7-PRS §2 + ACs dos Adendos §10 e §11b do ENG-011.

### (a) Selo de agendamento

O cartão da aba Exames passa a mostrar `Agendado: dd/mm hh:mm · Unidade X`, **sem transição de
custódia, sem evento e sem escrita** — informação ≠ custódia.

- `agendamento_atual_do_pedido` (novo) — fonte única de "qual compromisso vale agora", à moda do
  `detentor_atual_pedido` do J.7. Filtra terminais: remarcar é derivação, logo o não-terminal é
  o corrente.
- `resumo_agendamento_para_cartao` — projeção mínima; `criado_por` e id interno não atravessam.
- `GET /paciente/pedidos-exame` leva o campo `agendamento` (ou `None`), aditivo.

**Decisão de implementação a registrar:** o Adendo §10 sugeria reaproveitar
`GET /pedidos-exame/{p}/agendamentos` "protegido por ownership de paciente". Ao ler o código,
esse endpoint **já** aceita `paciente` com ownership (e já recusa `dispensador`) — não havia
backend a construir ali. Enriquecer a carteira foi a escolha: evita N+1 na tela e mantém *uma*
resposta para "qual é o corrente", no backend. A alternativa (uma chamada por cartão) deixaria a
escolha do corrente na tela — o mesmo defeito que o J.7 corrigiu ao parar de derivar posse do
status.

### (b) Lente compartilhada

O render saiu do `index.html` para **`lente.js`** (`window.LenteAuditoria`), com o CSS do cartão
junto. O index mantém a lente pública **inalterada em função**; cada cartão da carteira (receita
em posse e em histórico, exame, atestado, laudo) ganhou "ver rastreabilidade", que abre a mesma
trilha neutra ali mesmo, **sem login adicional**. `/public/*` e `/circulacao/{chave}` são `core`
e ficaram intocados.

### Gates

| Suíte | Antes | Depois |
|---|---|---|
| unit | 475 | **510** (+35) |
| integração (PG 15 efêmero) | 471 | **478** (+7) |
| navegador | 79 | **85** (+6) |

Um smoke existente foi ajustado: `test_smokes.py::TestAtestadoNaCarteira` casava o protocolo por
`button[onclick*="<proto>"]`, que passou a resolver **dois** botões com a chegada de "ver
rastreabilidade". Passou a nomear a função (`baixarPdfAtestado`) — tão específico quanto antes,
e à prova do próximo botão. Nenhuma asserção foi afrouxada.

---

## §4 FASE 4 — PR `core` da migração (aberto, **aguardando martelo**)

Branch `core/custodia-exame-posse-atual`, da `main` pós-#167. Implementado conforme ENG-012 §7 /
caminho (b) do `DESENHO-J10`.

### O que entrega

| Peça | Detalhe |
|---|---|
| Migração `d4b8c1e07f36` | `encerrada_em` + **data-fix** + índice único parcial **nos dois dialetos** (PG `NULLS NOT DISTINCT`; SQLite `COALESCE(item_id, -1)`) |
| Choke-point | `transferir_posse_exame` — fecha a anterior + abre a nova + emite `custodia_transferida`, atômico; `motivo` canônico fechado |
| Leituras migradas | **6 sítios** (o desenho previa 3 — ver §4.2), todos para `encerrada_em IS NULL` |
| Absorção, não duplicação | os helpers do J.7 passaram a filtrar por posse ativa; a cópia do predicado em `laudos.py` virou import da fonte única |
| Docs `core` | `CLAUDE.md` §7 + §2 (vocabulário) e `docs/ARQUITETURA_EXAMES.md` |

### §4.1 Duas decisões de desenho que pedem o olhar do arquiteto

**(a) `encerrada_em` = data da transferência seguinte, não `utcnow()`.** Uma custódia terminou
quando a próxima começou — fato que o ledger já registra. Carimbar "agora" inventaria uma
história em que todas as posses antigas terminaram no dia do deploy, o que colidiria com o R1
(§2a): relatório de período fechado tem de ser reproduzível para sempre.

**(b) O evento do data-fix tem sentido diferente do COER-2.** Lá,
`custodia_reconciliada_data_fix` significava *"havia dupla posse; resolvi"*. Aqui significa
*"linha superada pelo modelo de posse atual"*: na forma antiga a cadeia era **coerente por
construção** (a última linha era o detentor), e a migração **normaliza**, não corrige. Mantive o
nome do COER-2 (é o que o `DESENHO-J10` §3.1 pede) e marquei a diferença no `origem` do payload
(`migracao_j10_posse_atual`), com nota no `CLAUDE.md` §2 e na docstring da migração. **Se o
arquiteto preferir um nome próprio, é troca barata** — muda só a migração, o vocabulário e uma
asserção de teste.

### §4.2 Achado: eram 6 sítios de leitura, não 3

O `DESENHO-J10` §3.1 listava três (`detentor_atual_pedido`, `_assert_dispensador_dono_pedido`,
subquery da `fila-exames`). O grep obrigatório (método §2 do CLAUDE.md do backend) encontrou
**seis**:

| # | Sítio | Padrão antigo |
|---|---|---|
| 1 | `pedidos_exame.py::detentor_atual_pedido` | `ORDER BY id DESC LIMIT 1` |
| 2 | `pedidos_exame.py::_assert_dispensador_dono_pedido` | idem |
| 3 | **`laudos.py::_dispensador_detem_pedido`** | idem — **cópia** do #2 |
| 4 | `dispensadores.py` fila-exames | `c.id = (SELECT MAX(c2.id) …)` |
| 5 | **`clinicas.py`** relatório de exames | `MAX(id)` |
| 6 | **`clinicas.py`** faturamento | `MAX(id)` |

O #3 era um predicado de posse **duplicado em dois arquivos** — o mesmo risco da dupla posse um
andar acima: duas cópias divergem em silêncio e cada tela passa a acreditar numa verdade
diferente. Virou import da fonte única.

### §4.3 Achado: `agendar` abria custódia **sem** emitir evento

`POST /pedidos-exame/{p}/agendar` inseria a linha de custódia e emitia só `pedido_agendado` —
nunca `custodia_transferida`. Pelo §2 do CLAUDE.md isso é **bug, não feature** (*"abrir custódia
sem o evento é bug: o ledger é a fonte da verdade da cadeia de custódia"*). Rotear pelo
choke-point corrigiu de carona. Consequência: esse caminho passa a emitir um evento a mais que
antes — mudança de ledger, portanto sinalizada aqui em vez de escondida no diff. Teste dedicado
em `test_j10_core_posse_exame.py::test_agendar_fecha_a_posse_anterior`.

### §4.4 Gates da FASE 4

| Suíte | Resultado |
|---|---|
| unit + guardas novas | ✅ **565 passed**, 33 skipped |
| integração (PG 15 efêmero, fresh DB) | ✅ **486 passed** — baseline medida na mesma sessão: 478 |
| migração SQLite | ✅ 11 testes (data-fix, datas, idempotência, ordem, constraint) |
| `alembic upgrade head` | ✅ PG e SQLite, schema conferido nos dois |
| `init_tables.py` | ✅ exit 0 |

Quatro testes existentes precisaram de ajuste e um deles **era meu erro**:

- três (`*_custodia_atual_nao_historica`) simulavam re-transferência com um `INSERT` solto, que
  a constraint agora recusa — com razão. Passaram a **fechar a anterior antes de abrir a nova**,
  que é o que o choke-point faz: a simulação virou fiel, não complacente;
- o quarto foi **defeito meu**: meu arquivo de integração chamava `outer_conn.commit()` e
  `.rollback()`, o que destrói a isolação por transação externa do `conftest` e **vazava linhas
  para os testes seguintes** (dois erros de FK em `test_r2_idempotencia`, que não apareciam ao
  rodar o arquivo sozinho). Corrigido com `SAVEPOINT`. Confirmei rodando a suíte completa em
  banco novo, com e sem as mudanças: baseline 478 sem erros, com as mudanças 486 sem erros.

> Nota de método: a primeira medição acusou falhas que **não eram regressões** — eram sujeira de
> um banco reaproveitado entre execuções. Só a comparação com baseline em banco novo separou o
> que era meu do que era ambiente. Observar o efeito não é observar a causa.

---

## §5 O que **não** foi feito, e por quê

- **J.10 (`module`)** — não iniciado. O despacho o autorizava *"se der tempo"*, empilhado sobre
  a migração, com merge só depois dela. Como a migração é o ponto de parada e não pode mergear
  sem o Fabiano, empilhar J.10 agora só produziria uma fila mais longa de trabalho não revisado.
  O desenho segue válido em `DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`.
- **Render / reset da vitrine** — do Fabiano (exige dashboard). Não toquei.
- **Micro-ticket RBAC** (`core`) — fora de escopo; ver §6.

---

## §6 Achados reportados, **não** corrigidos (todos `core`)

1. **`POST /agendamentos/{p}/remarcar` não aceita `dispensador`**, embora `POST /agendamentos`
   aceite: **o laboratório pode MARCAR e não pode REMARCAR**. Encontrado ao escrever o E2E do
   J.11 (o teste usa o prescritor e diz por quê).
2. **`POST /agendamentos/{p}/nao-compareceu`** é `prescritor`+`admin` só — e quem presencia a
   falta é o laboratório.

Ambos são da mesma família da assimetria já mapeada (`GET /pedidos-exame/{p}/agendamentos`
recusa `dispensador`), e a janela natural é o **micro-ticket `core` de RBAC** que já viaja com o
J.10. Mudança de RBAC é `core` pela taxonomia §10 — não improvisei.

---

## §7 Estado final da fila

```
main 9dba25c
 ├── #163 ops     2565421  MERGEADO
 ├── #164 module  6892ea6  MERGEADO
 ├── #166 core    4298c0e  MERGEADO   (J.7 — martelo antecipado §10b; era #165, ver §2.2)
 └── #167 module  9dba25c  MERGEADO   (J.11)

AGUARDANDO FABIANO
 └── #168 core "custódia de exame ganha posse atual"  — aberto, CI verde, NÃO mergeado
       └── destrava J.10 (module) + micro-ticket RBAC (core, martelo próprio)

AGUARDANDO FABIANO (fora de código)
 └── reset da vitrine no Render (runbook entregue; conferir `[cnes-demo] snapshot CNES garantido`)
```

### Para o arquiteto, em 17/08

1. **§2.2 primeiro** — o desvio do número do PR no merge `core`.
2. Revisão retroativa do **J.11** (#167), como combinado.
3. Revisão detalhada do **PR `core` da migração**, com atenção a §4.1(a), §4.1(b) e §4.3.
4. §6 — os dois achados de RBAC, para entrarem no micro-ticket.

---

*Relatório do engenheiro, 2026-08-16, ao fim da rodada autônoma do Adendo §10 do ENG-012.*
