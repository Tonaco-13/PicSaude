# Sessão 2026-08-13 — Engenheiro: commits da demo laboratório (2 PRs)

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator |
| **Origem** | `SESSAO-2026-08-13-PARECER-ARQUITETO-FGH.md` §4 (estratégia de commit/PR) |
| **Branch de partida** | `docs/sessoes-11-12-agosto` |
| **Estado** | Dois PRs abertos. **Zero arquivos não relacionados** commitados. |

---

## §1 Os dois PRs

| PR | Título | Classe | Link |
|---|---|---|---|
| **1** | `feat(laudo): dispensador produz laudo em nome do RT [core]` | `core` | https://github.com/Tonaco-13/PicSaude/pull/159 |
| **2** | `feat(demo): módulo laboratório — laudo cidadão + bancada leve [module]` | `module` | https://github.com/Tonaco-13/PicSaude/pull/160 |

O PR 2 foi aberto com **`--base feat/laudo-dispensador-rt`**, e não contra `main`. Assim o diff que o
revisor vê é **só o que é `module`** — o `core` do PR 1 não aparece duas vezes. Após o merge do #159,
o #160 rebaseia para `main`.

---

## §2 Passo 0 — `.gitignore`

`.zcode/` e `inbox/` adicionados. Confirmado que sumiram da lista de untracked logo em seguida — era
exatamente o risco que o despacho apontava: bandeja local disputando espaço no `git add`.

> **Nota de escopo:** o `.gitignore` **não constava** de nenhuma das duas listas de stage do
> despacho. Incluí no PR 2 porque deixá-lo fora anularia o propósito do passo 0 — a mudança ficaria
> pendurada na árvore e o lixo voltaria a aparecer no próximo `git add`. É a única adição minha às
> listas dadas.

---

## §3 PR 1 — conferência do stage

```
$ git diff --cached --name-only
backend/app/routers/laudos.py
backend/tests/integration/test_laudos_dispensador_autorizacao.py
```

**Dois arquivos, exatamente os do despacho.** Commit `e51935a` — 2 arquivos, +554/−27.

Conteúdo: Ticket C (RBAC do laudo estendido ao dispensador) e os 16 testes de autorização. Nada de
frontend, nada de docs, nada de outro ticket.

---

## §4 PR 2 — conferência do stage

```
$ git diff --cached --name-only
.github/workflows/gates.yml
.gitignore
backend/app/domain/pdf_relatorio_exames.py
backend/app/routers/clinicas.py
backend/app/routers/dispensadores.py
backend/app/routers/pedidos_exame.py
backend/seed_demo.py
backend/tests/browser/test_bancada_clinica.py
backend/tests/browser/test_demo_lab_e2e.py
backend/tests/browser/test_laudo_clinica_cidadao.py
backend/tests/integration/test_4d2_instance_id_ledger.py
backend/tests/integration/test_faturamento_exames_clinica.py
backend/tests/integration/test_fila_exames_dispensador.py
backend/tests/integration/test_pedidos_exame.py
backend/tests/integration/test_pedidos_exame_bancada.py
backend/tests/integration/test_regras_receituario.py
backend/tests/unit/test_clinicas_periodo_fuso.py
backend/tests/unit/test_frontend_acao_sem_silencio.py
clinica.html
docs/ARQUITETURA_EXAMES.md
docs/ARQUITETURA_LAUDO.md
docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md
docs/ROTEIRO_DEMO_LABORATORIO.md
docs/tickets/SESSAO-2026-08-13-DESCRITIVOS-MODULOS-DEMO.md
docs/tickets/SESSAO-2026-08-13-PARECER-ARQUITETO-B-C.md
docs/tickets/SESSAO-2026-08-13-PARECER-ARQUITETO-FGH.md
docs/tickets/SESSAO-2026-08-13-PARECER-ARQUITETO-PACOTE-ADE.md
docs/tickets/SESSAO-2026-08-13-TICKET-F-DEMO-LAB.md
docs/tickets/SESSAO-2026-08-13-TICKET-G-DEMO-LAB.md
docs/tickets/SESSAO-2026-08-13-TICKET-H-DEMO-LAB.md
docs/tickets/SESSAO-2026-08-13-TICKET-I-POLIMENTO-DEMO-LAB.md
docs/tickets/SESSAO-2026-08-13-TICKETS-B-C-DEMO-LAB.md
```

**32 arquivos** = os 31 do despacho + `.gitignore` (§2). Commit — 32 arquivos, +4211/−57.

### Varredura da lista proibida — executada antes do commit

```
$ git diff --cached --name-only | grep -E "^\.zcode/|^inbox/|^planejamento/|RELATORIO-DEMO-2026-08-05|
  fig3_pre_estorno|SESSAO-2026-08-06|DESPACHO-CI-GATES|PARECER-REVISOR-CI|TICKET-CANON|VAGAO-CURADORIA"
OK — nenhum item proibido no stage
```

---

## §5 O que ficou de fora, e continua na árvore

```
?? docs/RELATORIO-DEMO-2026-08-05.md
?? docs/paper/fig3_pre_estorno.png
?? docs/tickets/DESPACHO-CI-GATES-BROWSER-ESTORNO-2026-08-12.md
?? docs/tickets/PARECER-REVISOR-CI-VERMELHA-POS-150.md
?? docs/tickets/SESSAO-2026-08-06-ENTREGAS-ENGENHEIRO.md
?? docs/tickets/TICKET-CANON-ATIVO-DOSE-SUFFIX.md
?? docs/tickets/VAGAO-CURADORIA-SEMAFORO.md
?? planejamento/
```

Todos de outras sessões ou de outro escopo. **Nenhum entrou.** `.zcode/` e `inbox/` já nem aparecem
— o passo 0 resolveu.

> `planejamento/demo-laboratorio-laudo-cidadao/` (os tickets A–H originais) ficou de fora: o §4 do
> parecer deixou a inclusão dele a critério do Fabiano. Basta um `git add` do diretório no PR 2 se
> quiser versionar o plano junto.

---

## §6 Limpeza do diff do #159 — Opção B (aprovada pelo Fabiano)

As duas branches partiam de `docs/sessoes-11-12-agosto`, que estava **2 commits à frente da `main`**
(`666b61b` diário + `95f3536` descritivos do Kimi). Nenhum é desta demo, mas ambos apareciam no diff
do PR 1 — justamente o que vai ao martelo.

**Solução escolhida:** levar os dois commits de docs à `main` por **fast-forward**, em vez de
rebasear as branches de feature. Sem `force-push`, sem reescrever história publicada.

### Verificações antes de tocar na `main`

```
$ git log --oneline origin/main..docs/sessoes-11-12-agosto
95f3536 docs: descritivos dos módulos demo (...)
666b61b docs(diário): registra as sessões de 11 e 12 de agosto

$ git log --oneline docs/sessoes-11-12-agosto..origin/main
(vazio — a main não divergiu)
```

Também confirmei que **`e51935a` (o core) NÃO está** na branch de docs: 0 ocorrências. O
fast-forward leva docs, e só docs.

### Execução

```
$ git push origin docs/sessoes-11-12-agosto:main
   ef1692b..95f3536  docs/sessoes-11-12-agosto -> main
```

Aceito de primeira — não há proteção de branch bloqueando, então o fallback de PR não foi
necessário.

> **Efeito colateral esperado:** o PR **#158** (`docs/sessoes-11-12-agosto` → `main`) tinha
> exatamente esses dois commits. Com eles na `main`, o GitHub o fecha como mergeado — o conteúdo
> chegou ao destino pelo mesmo caminho que aquele PR propunha.

---

## §7 Verificação obrigatória — o #159 depois da limpeza

Localmente, imediatamente após o fast-forward:

```
$ git log --oneline origin/main..origin/feat/laudo-dispensador-rt
e51935a feat(laudo): dispensador produz/assina/libera laudo em nome do RT [core]

$ git diff origin/main...origin/feat/laudo-dispensador-rt --name-only
backend/app/routers/laudos.py
backend/tests/integration/test_laudos_dispensador_autorizacao.py
```

**Um commit, dois arquivos** — exatamente o alvo.

E o mesmo pela API de **compare** do GitHub, que calcula ao vivo:

```
$ gh api repos/Tonaco-13/PicSaude/compare/main...feat/laudo-dispensador-rt
{"ahead": 1, "behind": 0,
 "files": ["backend/app/routers/laudos.py",
           "backend/tests/integration/test_laudos_dispensador_autorizacao.py"]}
```

### A verificação obrigatória do despacho

```
$ gh pr diff 159 --name-only
backend/app/routers/laudos.py
backend/tests/integration/test_laudos_dispensador_autorizacao.py
```

```
$ gh api repos/Tonaco-13/PicSaude/pulls/159
{"base_sha": "95f3536", "commits": 1, "changed_files": 2}
```

**Exatamente os 2 arquivos esperados.**

> **Nota de método — houve um intervalo enganoso, e uma atribuição errada minha.**
>
> Nos primeiros minutos após o fast-forward, o `gh pr diff 159` continuou listando os 10 arquivos
> antigos, e o registro do PR ainda trazia `base_sha: ef1692b`, `commits: 3`. O GitHub guarda a base
> do momento da abertura e a atualiza de forma preguiçosa.
>
> **O que separou "falhou" de "ainda não atualizou"** foi cruzar três fontes: `git diff
> origin/main...` (local), a API de **compare** (calcula ao vivo) e o registro do PR (cache). As duas
> primeiras já diziam 2 arquivos, `ahead 1 / behind 0` — ou seja, **o conteúdo estava certo desde o
> `git push`**, e só a vitrine (aba *Files changed*) estava velha. Essa checagem valeu: evitou
> concluir que o fast-forward tinha falhado e sair mexendo em history.
>
> **O que destravou a vitrine foi um `close`/`reopen`, executado pelo arquiteto (Z)** — não a
> reconciliação natural do GitHub, como este registro afirmou numa versão anterior. O histórico do
> #159 mostra os dois eventos (`closed` 21:40:19Z, `reopened` 21:40:21Z) e o comentário
> [`issuecomment-5286706452`](https://github.com/Tonaco-13/PicSaude/pull/159#issuecomment-5286706452):
> *"Reaberto para forçar o recálculo do base_sha…"*.
>
> **De onde veio o meu erro:** eu tinha deixado um polling em segundo plano esperando
> `changed_files == 2`. Ele disparou logo depois do reopen e eu li o resultado como reconciliação
> espontânea — atribuí a causa sem conferir o histórico do PR. Observar o efeito não é observar a
> causa; bastava um `gh api .../issues/159/events` para não errar.
>
> **O juízo que continua de pé:** o `close`/`reopen` mexe só na *apresentação*, não no conteúdo, e a
> reconciliação natural provavelmente resolveria em alguns minutos — então "não era estritamente
> necessário" segue defensável. O que não se sustenta é "não aconteceu".
>
> **Lição, reenquadrada:** as duas coisas são passos separados e de custo diferente. Provar o estado
> do **conteúdo** (as três fontes) é o passo caro e indispensável. Consertar a **vitrine** é barato,
> reversível e pode ser feito por quem estiver com o PR à mão — foi o que o arquiteto fez.

---

## §8 Estado final

- **`main`** em `95f3536` (fast-forward de docs; nenhum código da demo entrou por aqui).
- **#159** (`core`) — **1 commit, 2 arquivos**, base em `95f3536`. Diff limpo, confirmado.
  Aguarda o **martelo do Fabiano**.
- **#160** (`module`) — íntegro: base no #159, 2 commits, 33 arquivos (32 da demo + este registro).
  Rebaseia para `main` após o merge do #159.
- **#158** — fechado como **mergeado**, por consequência do fast-forward (mesmo conteúdo, mesmo
  destino).
- Gates locais no momento do commit: **integração 351 · unit 419 · browser 63**, verdes.

Nada pendente. O caminho até o merge é: martelo no #159 → merge → rebase do #160 → merge.

---

*Registro emitido pelo Engenheiro em 2026-08-13. Staging por caminho explícito em ambos os commits;
`git add -A`/`git add .` não foi usado em momento algum.*
