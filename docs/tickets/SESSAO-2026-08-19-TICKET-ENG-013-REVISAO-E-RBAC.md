# SESSÃO 2026-08-19 — ENG-013: revisão do #170 + micro-ticket RBAC

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-013` (retorno da sessão do arquiteto + fila J.10/migração) |
| **Executor** | Engenheiro · **NÃO versionado** (o despacho é explícito: "docs sem ordem não se commitam") |
| **Base** | `main` em `9c4d348` |

---

## §0 Estado da fila

| Fase | O quê | Situação |
|---|---|---|
| **FASE 1** | Dança da pilha (#168 → #170) | ⛔ **BLOQUEADA** — gatilho não ocorreu: o #168 segue **aberto**, sem o martelo do Fabiano |
| **FASE 2** | Revisão retroativa do #170 | ✅ **entregue** — 2 achados reproduzidos e **corrigidos em #172** (empilhado no #170) |
| **FASE 3** | Micro-ticket `core` de RBAC | ✅ **PR #171 aberto**, CI verde (gates + smokes), MERGEABLE, **não mergeado** (martelo do Fabiano) |

Nada foi mergeado nesta sessão. Nenhum `core` se auto-mergeou.

---

## §1 FASE 1 — por que não executei

O gatilho declarado é *"Fabiano martela e mergeia o #168"*. Verificado no início e no fim da
sessão: **#168 continua OPEN** (`MERGEABLE/CLEAN`). Sem o merge da base não há pilha para
dançar. Os passos 1–3 seguem prontos para execução imediata quando o martelo vier — e o passo 4
(merge do #170) está **retido pelos achados da FASE 2**, o que é stop-condition do §3.

---

## §2 FASE 2 — revisão do #170 (código do arquiteto)

Revisado o commit único `a30630c` sobre a base `f50beb3`. Gates reproduzidos localmente:
**unit 529** · **integração 498** (486 da base + 12 novas) · guard-rails verdes.

O desenho §3.3–§3.6 está implementado com fidelidade: a explosão de granularidade, o `de == para`
marcado com `reexpressao_nivel_item`, o anti-vazamento da fila e a escopagem por
`.closest('.exame-card')` no frontend estão corretos.

### 🔴 Achado 1 — `clinicas.py` ficou para trás (relatório e faturamento)

O #168 migrou **6 sítios** de leitura de posse. O #170 estendeu ao nível-item os de
`pedidos_exame.py` e `dispensadores.py`, mas **não os dois de `clinicas.py`**, que seguem com
`AND c.item_id IS NULL`. Como a parcial **fecha a linha de nível-pedido**, as duas queries
deixam de casar qualquer linha.

Reprodução (3 itens, 2 transferidos ao lab A):

```
relatorio de A ANTES da parcial:  pedido presente = True
relatorio de A DEPOIS da parcial: pedido presente = False
fila de A ainda ve?               True
faturamento (item coletado + resultado registrado): 0 linhas
```

**A fila mostra o trabalho, a unidade executa, e o faturamento não registra.** Perda de receita
silenciosa — e nenhum teste acusa.

É a **mesma classe** do achado que o arquiteto já deixou no PR sobre `laudos.py`. Enumerei a
classe inteira: **3 membros** — `clinicas.py` relatório, `clinicas.py` faturamento (ambos
perdidos) e `laudos.py` (já nomeado). Os dois esquecidos são os que mexem em dinheiro.

### 🟠 Achado 2 — ordem anti-leak (#52) invertida em 3 endpoints — **regressão**

Em `coletar`, `em-analise` e `resultado`, o guard do dispensador saiu do bloco inicial e passou
para depois do `404` do item — e, com ele, para depois do `422` de pedido terminal.

| endpoint | base `f50beb3` | `a30630c` |
|---|---|---|
| `coletar` | **403** | **422** |
| `em-analise` | **403** | **422** |
| `resultado` | **403** | **422** |

Um CNPJ que não detém nada passa a aprender pelo código de status que o pedido está terminal.
Verificado nos dois lados: a base devolve 403 nos três.

É inconsistente dentro do próprio PR — o `devolver_item_exame` novo documenta *"404 → 403 → 422
(anti-leak #52)"* e implementa a ordem certa.

**Por que a suíte não pegou:** `test_disp_resultado_403_precede_422_de_estado` cobre o 422 de
estado do **ITEM** (que continua correto, porque vem depois do guard). O 422 de **pedido
terminal** é o que passou à frente, e não há teste para ele nesses três endpoints.

Ambos os achados foram publicados no #170 com reprodução e sugestão de forma.

### Correção — **PR #172**, empilhado no #170

Por ordem posterior, os dois foram corrigidos numa branch de fix. O #170 fica **intocado**: a
FASE 1 confere que *"o diff do PR == `a30630c`"*, e essa igualdade é a prova de que o rebase foi
replay limpo — alterar o #170 anularia a verificação.

| Achado | Antes | Agora |
|---|---|---|
| relatório após parcial | pedido some | mostra os itens que a unidade detém |
| faturamento após parcial | 0 linhas | conta o item detido |
| relatório de outro detentor | vazaria pelo `JOIN` | só o que a unidade detém |
| `coletar`/`em-analise`/`resultado` a não-dono em pedido terminal | 422 | **403** |

- **Fix 1:** `_SQL_DETENTOR_DO_ITEM` — o predicado de `detentor_atual_item` escrito em SQL e
  compartilhado pelas duas queries. Corrige os dois sentidos: a unidade volta a ver o que
  detém e deixa de ver o que não detém.
- **Fix 2 e 3:** guarda **grossa** (`dispensador_tem_algo_no_pedido`) logo depois do 404 do
  pedido, nos QUATRO gestos por item — o que corrige tanto o 422-antes-do-403 (achado 2) quanto
  o 404-do-item-antes-do-403 no `devolver` (achado 3, corrigido por pedido posterior):

  ```
  404 do pedido → 403 GROSSO (sou parte?) → 404 do item → 403 FINO (é meu?) → 422 de estado
  ```

  **As duas camadas guardam coisas diferentes, e isso quase passou batido.** Tentei dispensar a
  grossa e só promover a fina ao topo — ela recebe o `item_id` da ROTA, não precisa do item
  carregado, então a justificativa que eu escrevera para a grossa estava ERRADA. A suíte do
  próprio #170 recusou: `test_devolucao_guardas` exige que o custodiante PARCIAL que erra o id
  receba **404**, e com só a fina no topo ele recebia 403 (a posse de um item inexistente recai
  na do pedido, que a explosão já fechou). Forma final: estranho → 403 na grossa e não aprende
  nada; parte → passa e recebe respostas honestas, inclusive o 404; parte operando item alheio →
  barrada pela fina.
- **Guardas:** 13 testes de integração + 2 estáticos; o estático foi conferido **por mutação**.
- **Trade-off declarado no código:** o predicado por item custa duas subqueries correlacionadas
  por linha e não usa índice. Preferi a clareza (idêntico ao domínio) num relatório sob demanda
  e escopado por CNPJ; a forma indexável fica registrada em comentário.

Gates do #172: unit **531** · integração **516** (498 do #170 + 18) · navegador **86**. CI verde,
`MERGEABLE`.

**Ordem de merge (lição do #165):** ao mergear o #170, **não usar `--delete-branch`** — deletar
a base fecha o PR empilhado em vez de retargetá-lo, e depois do force-push a reabertura é
impossível. Mergear #170 → `gh pr edit 172 --base main` → rebase → conferir → só então deletar.

**Nota de método:** o terceiro caso (`devolver`) foi primeiro registrado como observado-e-não-
alterado, para não ampliar escopo por conta própria; entrou depois, por pedido. Foi ao corrigi-lo
que a premissa errada da guarda grossa apareceu — e foi um teste do arquiteto, não meu, que a
derrubou.

---

## §3 FASE 3 — micro-ticket `core` de RBAC (**PR #171**, aguardando martelo)

`remarcar` e `nao-compareceu` não aceitavam `dispensador`, embora `POST /agendamentos`
aceitasse: **o laboratório marcava e não podia remarcar**, e quem presencia a falta não podia
registrá-la.

**O achado mais forte apareceu na revisão:** `docs/ARQUITETURA_AGENDAMENTO.md` **já atribuía os
dois atos ao prestador** (§Transições: *"prestador (após horário)"*; §Eventos: *"prestador"*).
O documento dizia prestador; o código não deixava. Não foi decisão — foi papel esquecido em duas
listas. O PR faz o código obedecer ao desenho.

- **Duas linhas** de mudança de comportamento; o resto é teste, guarda e documentação.
- **Ownership inalterado:** `_assert_ag_owner` já cobria o papel por `org_id` (fail-closed §D1).
- `paciente` segue fora de `nao-compareceu` — o ticket acrescentou **um** papel, não abriu o endpoint.
- **RBAC congelado por valor** nos 8 endpoints: a assimetria durou meses porque nada a vigiava.
- O smoke do J.11 passou a remarcar como **laboratório** — o ator real. O comentário que
  documentava a limitação virou o registro de que ela foi fechada.

Gates locais: unit **516** (510 + 6) · integração **484** (478 da `main` + 6) · navegador **85**.
CI do PR: gates ✅ 2m27s · smokes ✅ 6m05s · `MERGEABLE/CLEAN` na base `main`.

---

## §4 Pendências e observações

1. **Martelo do Fabiano no #168** — destrava FASE 1 inteira.
2. **Martelo do Fabiano no #171** (`core`, não se auto-mergeia).
3. **Os 2 achados do #170** — corrigidos em **#172** (`module`, merge sob ordem geral, depois do #170).
4. **Nota de governança:** a ordem de *abertura* da FASE 3 veio do arquiteto (ENG-013), não do
   Fabiano. Se ele entender que implementar `core` também pedia martelo prévio, o trabalho está
   inteiro no PR e nada foi mergeado.
5. **Ambiente:** `colima`/`docker` não estão no PATH desta sessão — usei o PG efêmero por
   `initdb`/`pg_ctl` (receita da sessão de 22/07), que resolveu sem depender do container.
6. **Assimetria remanescente, não tocada:** `GET /pedidos-exame/{p}/agendamentos` aceita
   `dispensador` no `require_role` mas o recusa no ownership (§D4, decisão deliberada em código).
   O ENG-013 nomeou apenas `remarcar`/`nao-compareceu`; não ampliei escopo de `core` por conta
   própria. Fica registrado para decisão.

---

## §5 Parecer do arquiteto (20/08) e ensaio da pilha

**Veredito:** #172 APROVADO (`module`) · #171 APROVADO para martelo do Fabiano (`core`). Nada a
corrigir em nenhum dos dois. Os três achados foram confirmados como reais; o do `clinicas.py` é o
mais grave pela categoria — perda silenciosa no faturamento.

O arquiteto **endossou como PADRÃO DA CASA** a ordem que saiu do vaivém da guarda grossa, para
todo gesto por item:

```
404 do pedido → 403 GROSSO (sou parte?) → 404 do item → 403 FINO (é meu?) → 422 de estado
```

> Registro dele, que vale guardar: *"invariante executável > memória de revisor — desta vez o
> teste do arquiteto segurou o erro do engenheiro, na direção inversa da usual."*

**Retenção da FASE 1 LEVANTADA.** A fila volta a ser 3 níveis:

1. Fabiano martela **#168** e **#171** (dois martelos `core`; o #171 é independente da pilha);
2. dança do **#170**: retarget → `main`, rebase, conferir diff == `a30630c`;
3. dança do **#172**: retarget → `main`, rebase, conferir, merge sob ordem geral;
4. só então deletar as branches da pilha, **de cima para baixo**.

### Ensaio da pilha (20/08) — feito antes do martelo, em worktree descartável

Simulei os três níveis sem tocar em branch nenhuma (`git worktree` + branches `tmp/`):

| Passo | Resultado |
|---|---|
| squash do #168 na `main` | limpo |
| rebase do #170 `--onto` a main simulada | **1 commit**, mensagem preservada, patch `sha256` **idêntico** ao `a30630c` |
| squash do #170 + rebase do #172 | **1 commit**, patch **idêntico** ao `6183b06` |
| gates no estado final combinado | unit **531** · integração **516** · navegador **86** |

Conclusão: **as duas danças replayam sem conflito e sem hun a mais ou a menos**, e a pilha
inteira fica verde junta — não só cada PR isolado. O ensaio foi descartado; nenhuma ref remota
foi tocada.

---

## §6 MARTELO DO FABIANO — registro (protocolo `core`)

| Campo | Valor |
|---|---|
| **Autor** | Fabiano Tonaco Borges |
| **Data** | 2026-08-20 |
| **Canal** | chat do arquiteto, repassado no despacho de execução da fila |
| **Objeto** | **#168** (`core` — custódia de exame ganha posse atual) e **#171** (`core` — o prestador remarca e registra falta) |
| **Verbatim** | *"Da minha parte, martelado"* |

Registrado ANTES de qualquer merge, como manda o padrão da casa: `core` não se
auto-mergeia, e o martelo precisa existir em documento antes do clique. Os dois PRs
tinham parecer favorável do arquiteto (20/08) e CI verde.

### Execução da fila

Ordem recebida: registrar martelo → merge #168 (squash, **sem** `--delete-branch`,
porque o #170 está empilhado) → merge #171 (squash, `--delete-branch` liberado) →
dança do #170 → dança do #172 → deletar as branches de cima para baixo.

Regra vinculante do despacho: **divergência do ensaio em qualquer passo = STOP**,
mesmo que o resultado pareça melhor — *mergeia-se o que foi auditado*.

### Execução — evidências (20/08)

**SHAs antes:** `main` `9c4d348` · #168 `f50beb3` · #170 `a30630c` · #172 `6183b06`

| # | Passo | Resultado |
|---|---|---|
| 2 | merge #168 (squash, **sem** `--delete-branch`) | `6429007` — branch preservada, #170 seguiu OPEN |
| 3 | merge #171 (squash, `--delete-branch`) | `0d09c80` |
| 4 | dança do #170: retarget → `main`, rebase `--onto` | 1 commit `5a10ad9`, mensagem preservada |
| 4 | **conferência** patch vs `a30630c` | `sha256` **3dcda226…** nos dois — **IDÊNTICO**, igual ao ensaio |
| 4 | CI + merge #170 (squash, sem delete) | gates 2m25s · smokes 3m37s · `57c8569` — #172 seguiu OPEN |
| 5 | dança do #172: retarget → `main`, rebase `--onto` | 1 commit `db8d1c7`, mensagem preservada |
| 5 | **conferência** patch vs `6183b06` | `sha256` **015603fd…** nos dois — **IDÊNTICO**, igual ao ensaio |
| 5 | CI + merge #172 | gates 5m06s · smokes 3m36s · `08eb2b2` |
| 6 | deleção das branches, de cima para baixo | `fix/j10…` → `module/j10…` → `core/custodia…`, após conferir que nenhum PR aberto dependia delas |
| 8 | guarda estática da ordem (#173) | `5a8bfb5` — conferida por mutação |

**Zero divergência do ensaio em qualquer passo.** As duas igualdades de patch bateram com as
medidas na véspera, o que era a condição de parada do despacho.

**Gates na `main` aterrissada:** unit **537** · integração **522** (antes do #173);
com o #173, unit **546**.

**`main` final:** `5a8bfb5`

```
5a8bfb5 test(exames): congela a ordem das guardas nos gestos por item [module] (#173)
08eb2b2 fix(exames): relatório/faturamento por item + ordem anti-leak no J.10 [module] (#172)
57c8569 feat(exames): J.10 — custódia parcial por item [module] (#170)
0d09c80 feat(core): o prestador remarca e registra falta no agendamento [core] (#171)
6429007 feat(core): custódia de exame ganha posse atual — encerrada_em + unicidade [core] (#168)
```

### Destravado

Com a pilha na `main`, o **reset da vitrine (Render)** deixa de estar bloqueado — runbook com o
Fabiano. `laudos.py` (desenho laudo × item) segue com o arquiteto.

---

*Relatório do engenheiro, 2026-08-19, com adendos de 20/08. Não versionado por ordem do ENG-013.*
