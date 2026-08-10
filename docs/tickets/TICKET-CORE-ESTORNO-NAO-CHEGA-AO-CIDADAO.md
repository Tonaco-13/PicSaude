# TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO — Estorno não devolve custódia ao cidadão

| Campo | Valor |
|---|---|
| **ID** | TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO |
| **Classe** | **`core`** — altera máquina de estados (`domain/states.py`) + cadeia de custódia + emenda spec ratificada (`TICKET-B0`). **Revisão central obrigatória** (CLAUDE.md §10). |
| **Estado** | 🟢 **PRONTO PARA O ENGENHEIRO** — spec v2 (Arquiteto) + martelo Fabiano dado em §3.2 (10/08): `pagamento_nao_concluido → cidadão`. Aguarda implementação (Claude Code/terminal) com revisão central obrigatória. |
| **Para** | Engenheiro (Claude Code/terminal) |
| **Origem** | Teste de UI por ZCode (agente black-box) em picsaude.com.br, 10/08/2026. Bug relatado por Fabiano ("tentei estornar e não chegou ao cidadão o estorno. Depois caiu"). |
| **Histórico** | v1 (ZCode, 10/08) → parecer `PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` (Revisor, 10/08, **destoa** → volta ao Arquiteto) → **v2 (Arquiteto, este documento)** |

> **Parecer do Revisor:** [`PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md`](PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md) —
> veredito "destoa, volta ao Arquiteto" (o fix v1 reverte `TICKET-B0` e contradiz invariante do
> CLAUDE.md). O Revisor rascunhou a Opção Y no Apêndice A; o Arquiteto ratifica, refina e sobrepõe
> neste documento. **Artifact-irmão:** `docs/RELATORIO-BUG-ESTORNO-CIDADAO-2026-08-10.md` (repro +
> 17 screenshots).

---

## §1 Contexto — o bug é real, mas o "fix óbvio" reverte uma decisão ratificada

### 1.1 O bug (confirmado em código + reproduzido a vivo)

Após estornar uma dispensação **total**, a prescrição **não volta à carteira do cidadão** e o
cidadão **não consegue devolvê-la ao prescritor** (única via regulatória, §3 do CLAUDE.md). A
carteira fica vazia (`posse: []`) e o `devolver-prescritor` retorna 409. Reprodução 100% em
picsaude.com.br (10/08), com 2 prescrições estornadas — ver `RELATORIO-BUG-ESTORNO-CIDADAO-2026-08-10.md`.

### 1.2 Por que o "fix óbvio" (v1 deste ticket) está errado

A v1 propunha uma regra cega "estorno sempre devolve ao paciente". O Revisor mostrou — e o Arquiteto
confirmou no código — que isso **reverte o `TICKET-B0`** (decisão Opção A, martelada pelo Fabiano):

> **TICKET-B0 §3.2:** *"Reabrir custódia do item para o **dispensador** que estorna (o
> estabelecimento retém o item de novo para re-dispensação)"* · **§6.2:** *"Após estorno total, a
> prescrição **reaparece na fila** com saldo reposto; ledger tem um `custodia_transferida` novo
> (retenção pelo dispensador)."*

E contradiz o contrato de estados em **4 pontos** (conflitos A–D do parecer), listados em §5.

### 1.3 O que o `TICKET-B0` resolveu — e o que ele deixou em aberto (o nosso alvo)

O `TICKET-B0` resolveu corretamente um problema: **re-dispensar o saldo reposto na mesma farmácia**
após um estorno (sem isso, o item `dispensado` terminal travava a re-dispensação mesmo com saldo).
A decisão foi derivar a dispensabilidade do **saldo efetivo**, não do rótulo — correta e preservada.

Mas o `TICKET-B0` **otimizou só o caminho "mesma farmácia re-dispensa"** e ignorou dois caminhos
legítimos do cidadão:

- **Retry em outra farmácia** — o cidadão leva a receita para outro estabelecimento.
- **Devolução ao prescritor** — `paciente → prescritor`, a única via de correção clínica (§3).

O próprio teste do `TICKET-B0` reconhece a lacuna. O docstring de
`test_redispensa_apos_estorno_usa_saldo_reposto` (`tests/integration/test_estorno.py:147`) diz
textualmente:

> *"Dispensação TOTAL levaria o item a `dispensado` terminal e o estorno, por ser objeto derivado,
> não o reabre — **fork #1 do ticket**. Por isso a reposição operacional é no caminho parcial."*

**Todos os testes de estorno cobrem só o caso PARCIAL** (item fica `em_custodia`; `test_estorno.py`
linhas 99 e 147, ambas com dispensação de 4 em 10). O caso TOTAL — exatamente o do bug — é o "fork"
reconhecido mas não coberto. **Este ticket fecha esse fork.**

> **Consequência importante:** a v2 **não quebra nenhum teste verde** (o parcial é intocado — ver
> §4.3). O que ela faz é **emendar a spec do `TICKET-B0` §3.2/§6.2 para o caso total** — e isso
> exige o martelo do Fabiano, porque reverte uma decisão que ele ratificou.

---

## §2 Evidência (resumo — detalhes no relatório-irmão)

| Etapa | Ação | Resultado |
|---|---|---|
| T1–T2 | Prescritor emite P1 (Dipirona 20cp) + P2 (Amoxicilina 21cáp) | ✅ `82cdbb62…`, `478609db…` |
| T3 | Cidadão transfere as 2 à Farmácia Demo Central | ✅ saem da carteira ativa |
| T4 | Dispensador dispensa as 2 (saldo 0) | ✅ "Dispensação registrada" |
| T5 | Dispensador estorna as 2 (`desistencia_paciente`) | ⚠️ estorno registrado, **não chega ao cidadão** |
| T6 | Carteira do cidadão | ❌ "Nenhuma prescrição sob sua custódia" |

Resposta da API ao estornar (`POST /dispensacoes/7/estornar`): `"status_item": "dispensado"`,
`"status_prescricao": "dispensada"`, `"custodia_reaberta": true` (no dispensador). Carteira do
paciente: `"posse": []`. Os itens voltaram à **fila do dispensador** com saldo cheio (21/21, 20/20)
— comportamento exato do `TICKET-B0` §6.2.

---

## §3 Decisão (Arquiteto) — Opção Y, roteada por motivo

> **Ratifico a Opção Y do Revisor** (mutação de estado roteada por motivo), com três correções:
> (1) o roteamento é **por motivo**, não cego; (2) só o estorno **TOTAL** muta o item (parcial
> preserva o `TICKET-B0` integralmente); (3) a regressão do terminal `dispensada` é declarada como
> **exceção nomeada** (à moda do `COER2-POS-MERGE-FIX`), não afrouxamento geral.

### 3.1 Princípio

O estorno continua sendo **objeto sanitário derivado e imutável** (a `dispensacoes` original e a
`estornos` NÃO são mutadas — §1/§2a preservados). O saldo efetivo segue `Σ dispensado − Σ estornado`
(contábil, inalterado). O que muda é o **destino da posse e o estado do item após um estorno TOTAL**,
que passam a depender do **motivo**.

### 3.2 Tabela de roteamento por motivo — ✅ DECIDIDA (martelo Fabiano, 10/08)

| `motivo` | Destino da custódia (total) | `status_item` (total) | Racional |
|---|---|---|---|
| `desistencia_paciente` | **paciente** | `devolvido_paciente` | Cidadão desistiu → recupera a receita p/ retry ou devolver ao médico |
| `pagamento_nao_concluido` | **paciente** | `devolvido_paciente` | Pagamento falhou = produto não saiu = receita é do cidadão; retry na mesma farmávia preservado via re-apresentação. **Martelo Fabiano 10/08: cidadão.** |
| `erro_dispensacao` | **dispensador** (mantém `TICKET-B0`) | `dispensado` (não muta) | Erro de registro da própria farmácia → corrige e re-dispensa ali (preserva `TICKET-B0` onde faz sentido) |
| `outro` | **paciente** (default seguro) | `devolvido_paciente` | Default para o lado do cidadão (regulatoriamente conservador) |

**A régua resumida:** *"cidadão recupera, exceto erro operacional da farmácia."*

**O único ponto genuinamente ambíguo é `pagamento_nao_concluido`** — defesa clínica para os dois
lados (ver §3.3). Os outros três têm consenso Arquiteto+Revisor.

### 3.3 Justificativa da decisão `pagamento_nao_concluido → paciente` (martelo Fabiano)

- **A receita pertence ao cidadão.** Falha de pagamento = transação não concluída = cidadão não
  levou o produto. A receita volta com ele.
- **O caminho "retry na mesma farmácia" NÃO se perde:** se o destino é `paciente`, a prescrição vai
  a `transferida_paciente`, e `transferir_farmacia` (`auth.py:226`) aceita exatamente esse status.
  O cidadão re-apresenta à mesma farmácia em segundos. Custa um clique a mais; preserva a agência
  do cidadão e é regulatoriamente mais limpo.
- **O argumento "fica na farmácia"** só vale se o produto físico nunca saiu do balcão — mas a
  *receita* é do cidadão, e retê-la na farmácia após falha de pagamento **tranca** o cidadão (não
  pode levar a outra, não pode devolver ao médico) — exatamente a dor do bug.

> Se o Fabiano preferir manter `pagamento_nao_concluido → dispensador` (fast-path de retry no
> balcão), a régua muda só essa linha e o restante da spec é idêntico.
>
> **DECIDIDO (10/08):** Fabiano martelou `paciente`. Régua final: 3 dos 4 motivos vão ao cidadão;
> só `erro_dispensacao` retém na farmácia.

### 3.4 Estorno parcial — não muta (preserva `TICKET-B0` integralmente)

`status_item` é enum único; estorno é por quantidade. Um item com 21 dispensados e 10 estornados
não pode ser "dispensado" e "devolvido_paciente" ao mesmo tempo. **Regra:**

- **Estorno PARCIAL** (`Σ estornado do item < Σ dispensado`): **NÃO muta `status_item`** — segue
  `dispensado` (ou `em_custodia`, conforme o caso); a fração revertida vive só no saldo efetivo.
  Custódia e fila seguem o comportamento `TICKET-B0` (re-dispensável na farmácia). **Nenhuma
  mudança vs. hoje.**
- **Estorno TOTAL** (`Σ estornado do item == Σ dispensado`, i.e., saldo efetivo volta ao total
  prescrito): aplica a coluna `status_item` da tabela §3.2 para os motivos "cidadão recupera".

> Isto é o que garante que **nenhum teste verde do `TICKET-B0` quebra**: os testes existentes são
> todos parciais (`test_estorno.py:99, 147`); a mutação só dispara no total.

---

## §4 Conflitos com invariantes (A–D) e como esta spec os resolve

O Revisor identificou 4 conflitos. A v2 os resolve **todos no mesmo PR**:

| # | Conflito (parecer) | Resolução nesta spec |
|---|---|---|
| **A** | Reverte `TICKET-B0` ratificado/testado | **Martelo Fabiano §3.** Refinamento: só o caso TOTAL é emendado; o parcial (que é o testado) fica intocado. Reverter a *spec* §3.2/§6.2 para o caso total, preservando-a para o parcial e para `erro_dispensacao`. |
| **B** | CLAUDE.md §2 + `states.py:157` dizem "estorno NÃO é transição de estado do item" | **Emendar** `states.py:157-162` e CLAUDE.md §2: o estorno permanece objeto derivado, **mas** nos motivos "cidadão recupera" + caso total, ele **dispara** a transição `dispensado → devolvido_paciente`. A transição `dispensado → estornado` segue scaffolding dormente (não usada). |
| **C** | Aresta `dispensado → devolvido_paciente` não existe (`states.py:147`) | **Criar** a aresta: `"dispensado": frozenset({"estornado", "devolvido_paciente"})` + mapear evento `("dispensado","devolvido_paciente") → "item_devolvido_paciente"` em `EVENTOS_ITEM`. |
| **D** | `dispensada` é terminal (§5b, `states.py:84`) | **Declarar a regressão pós-estorno como exceção nomeada** (à moda do `COER2-POS-MERGE-FIX`, que já criou exceção `devolvido_paciente → devolvido_prescritor`). `dispensada` permanece terminal no caso geral; a regressão a `transferida_paciente` via `_recalcular` é a única brecha legítima, documentada em `states.py` + CLAUDE.md §5b. |

> Sem emendar A–D **no mesmo PR**, o contrato de estados fica auto-contraditório — exatamente o
> tipo de dívida que o §9/§2a existem para impedir.

---

## §5 Edições de contrato exigidas (todas no MESMO PR)

1. **`states.py` — `TRANSICOES_ITEM["dispensado"]`** (linha 147):
   `frozenset({"estornado"})` → `frozenset({"estornado", "devolvido_paciente"})`.
2. **`states.py` — `EVENTOS_ITEM`** (linha 248): adicionar
   `("dispensado", "devolvido_paciente"): "item_devolvido_paciente"`.
3. **`states.py:157-162`** (nota do estorno): reescrever — o item passa a mutar para
   `devolvido_paciente` nos motivos "cidadão recupera" + caso total; `dispensado → estornado`
   segue dormente.
4. **CLAUDE.md §2** (linha do `estorno_registrado`): emendar o trecho "**não** uma transição de
   estado do item" para refletir a mutação condicional por motivo + caso total.
5. **CLAUDE.md §5a/§5b**: registrar a transição `dispensado → devolvido_paciente` e a exceção
   nomeada de regressão do terminal `dispensada` (conflito D).
6. **DDL** (`docs/picsaude_ddl_postgres_v1.sql`): verificar se há CHECK/enum de transição afetado
   (provável que não — estados são validados em código, não em constraint de banco; confirmar).

---

## §6 Mudança no handler (`dispensacoes.py:488-657`)

Após criar o objeto-estorno e computar `saldo_efetivo` (já existe, linhas 596-606), ramificar por
motivo **e** por total/parcial:

```python
estorno_total = (saldo_efetivo == disp["qtd_prescrita"])   # saldo voltou integral ao prescrito
destino, novo_status_item = _rota_estorno(payload.motivo)  # tabela §3.2

if destino == "dispensador":
    # comportamento TICKET-B0 (intacto): re-retém p/ a farmácia, item NÃO muta
    # ... bloco 619-642 atual (transferir_posse → dispensador) ...

elif destino == "paciente" and estorno_total:
    # NOVO: devolve ao cidadão
    _transicionar_item(conn, disp["item_id"], "devolvido_paciente")   # valida via TRANSICOES_ITEM
    registrar_evento_ledger(conn, objeto_id=disp["prescricao_id"],
                            tipo_evento="item_devolvido_paciente", ...)
    # CPF do paciente é necessário — ver §6.1 (JOIN em pacientes)
    transferir_posse(conn, disp["prescricao_id"], disp["item_id"],
                     de_tipo="dispensador", de_id=disp["cnpj_estabelecimento"],
                     para_tipo="paciente", para_id=cpf_paciente,
                     motivo="devolucao_pos_estorno", agora, ...)        # choke-point (COER-2)
    _recalcular_status_prescricao(conn, disp["prescricao_id"], agora)  # → transferida_paciente

elif destino == "paciente" and not estorno_total:
    # PARCIAL cidadão-recupera: NÃO muta item (§3.4); comportamento atual preservado.
    # (Posse só volta ao paciente quando o saldo retorna integralmente.)
    ... bloco TICKET-B0 atual (dispensador) ...
```

### 6.1 Pré-requisito: CPF do paciente no lookup

A query do handler (`dispensacoes.py:520-532`) seleciona `p.paciente_id` (FK), **não o CPF**.
`transferir_posse` com `para_tipo="paciente"` exige o CPF como `detentor_id` (`_normalizar_id`,
`custodia.py:311-313`). **Adicionar JOIN** `pacientes pa ON pa.id = p.paciente_id` e selecionar
`pa.cpf`. (O `paciente_id` já vem; só falta o CPF.)

### 6.2 Disciplina de choke-point

- **Toda transição de posse pelo choke-point `transferir_posse`** — nunca `_fechar`+`_abrir` à mão
  (COER-2). Novo motivo canônico: `devolucao_pos_estorno` (o T6/histórico separa de
  `estorno_reposicao_saldo`, que fica para o ramo dispensador).
- **Item que deixa `dispensado` → sem custódia órfã.** O `_fechar` interno do choke-point encerra a
  custódia do dispensador; o `_abrir` abre a do paciente. Testar unicidade (`uq_custodia_ativa_*`).

### 6.3 Retorno da API (`dispensacoes.py:644-657`)

`status_item` e `status_prescricao` passam a refletir o **novo** estado (hoje ecoam o velho). Novo
campo informativo `destino_custodia` (`"paciente"` | `"dispensador"`) para o frontend decidir a
mensagem (ex.: "sua receita voltou à sua carteira").

---

## §7 Read-side (por que o frontend quase não muda)

A carteira (`auth.py:184`) decide por `p.status`: `_EM_POSSE = {"transferida_paciente","pendente"}`.
Com a mutação do item → `devolvido_paciente` + `_recalcular` → `transferida_paciente` (confirmado em
`custodia.py:290-296`: `retidos_farmacia==0 and devolvidos_paciente>0`), a prescrição **reaparece
naturalmente em POSSE**. E `devolver-prescritor` (`auth.py`) já aceita `devolvido_paciente`
(`COER2-POS-MERGE-FIX`). Logo:

- Cidadão vê a receita de volta na carteira. ✅
- Cidadão pode `devolver-prescritor` (via §3 destravada). ✅
- Cidadão pode re-`transferir-farmacia` (retry em outra farmácia, ou na mesma). ✅

**Frontend do dispensador:** o item estornado ao cidadão **sai da fila** (custódia do dispensador
encerrada). O `acionavel`/saldo segue computado no backend (sem mudança de regra).

---

## §8 Cobertura de teste exigida (dois dialetos — SQLite + PG)

1. `desistencia_paciente` **total** → item `devolvido_paciente`, prescrição `transferida_paciente`,
   custódia ATIVA do **paciente**, carteira mostra em POSSE, `devolver-prescritor` aceita.
2. `desistencia_paciente` **total** → cidadão consegue re-`transferir-farmacia` (retry).
3. `erro_dispensacao` **total** → comportamento `TICKET-B0` **intacto** (item `dispensado`,
   re-dispensável, custódia do dispensador) — **regressão**.
4. `pagamento_nao_concluido` total → conforme martelo §3.2 (caso paciente: igual a 1; caso
   dispensador: igual a 3).
5. Estorno **parcial** de qualquer motivo → item **não muta**, saldo efetivo reposto, fila
   dispensador — **regressão do comportamento atual** (protege `TICKET-B0`).
6. Sem custódia órfã (unicidade `uq_custodia_ativa_*`) em todos os ramos.
7. Ledger em sequência correta: `estorno_registrado` + `item_devolvido_paciente` +
   `custodia_transferida` (`devolucao_pos_estorno`) no ramo paciente; só `estorno_registrado` +
   `custodia_transferida` (`estorno_reposicao_saldo`) no ramo dispensador.
8. Guard-rail R2 (unicidade de movimento) não acusa duplicidade após dispensar→estornar→re-dispensar.

> **Testes existentes a manter verdes:** `test_estorno_cria_objeto_derivado_e_repoe_saldo`
> (`test_estorno.py:99`) e `test_redispersa_apos_estorno_usa_saldo_reposto` (`:147`) — ambos
> parciais, ambos devem permanecer idênticos.

---

## §9 Desmembramento — ticket de frontend (`module`)

O `prompt()` nativo em `dispensador.html:1496` (pede o motivo do estorno) **bloqueia** a execução
no IAB/navegador por 32s e pode ser a causa do "depois caiu" relatado. É defeito real, mas
**separado** — é robustez de UI, não `core` de estados. **Criar ticket `module` próprio:**
trocar o `prompt()` por um modal HTML (mesmo padrão de `_abrirLoteFila`). A repro do bug de backend
usou REST direta, então o `core` não depende deste desmembramento.

---

## §10 Fora de escopo

- **Opção X (posse computada pela custódia + saldo, sem mutar item):** rejeitada no primeiro corte.
  Honra o derived-object/R1/§10 e resolve o parcial de graça, mas exige reescrever a carteira +
  guards perto do choke-point de custódia (risco de dupla posse). Registrada como alternativa.
- **Estado de item novo (`re_disponivel` etc.):** não criar. A dispensabilidade segue derivada do
  saldo (`TICKET-B0`); a novidade é só a transição `dispensado → devolvido_paciente` no total.
- **Relatório SNGPC:** o saldo escriturado já subtrai estornos; sem mudança (Fatia A).

---

## §11 Checklist de implementação (pós-martelo §3)

- [x] **Martelo Fabiano** em `pagamento_nao_concluido` (§3.2) — ✅ decidido: `paciente` (10/08)
- [ ] R1 — `states.py`: aresta `dispensado → devolvido_paciente` + evento mapeado (§5.1, §5.2)
- [ ] R2 — `states.py:157-162`: reescrever nota do estorno (§5.3)
- [ ] R3 — CLAUDE.md §2 + §5a/§5b: emendar (§5.4, §5.5)
- [ ] R4 — `dispensacoes.py`: JOIN pacientes p/ CPF + ramificação por motivo/total (§6, §6.1)
- [ ] R5 — retorno da API com `destino_custodia` (§6.3)
- [ ] Testes §8 (8 cenários, dois dialetos)
- [ ] Testes existentes (§8 nota) seguem verdes
- [ ] DDL verificado (§5.6)
- [ ] PR `core` — revisão central obrigatória

---

> **Estado do processo:** spec v2 (Arquiteto) concluída + **martelo Fabiano dado (10/08, §3.2)**.
> Pronta para o Engenheiro (Claude Code/terminal) com **revisão central obrigatória** (classe
> `core`, emenda a `TICKET-B0` §3.2/§6.2 + CLAUDE.md §2/§5a/§5b + `states.py`).
