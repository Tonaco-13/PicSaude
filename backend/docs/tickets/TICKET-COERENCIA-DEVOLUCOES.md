# TICKET-COERENCIA-DEVOLUCOES — devolução ao paciente devolve a POSSE (status + custódia)

| Campo | Valor |
|---|---|
| **Dono** | Engenheiro-Chefe |
| **Classe (CLAUDE.md §10)** | **`core`** — máquina de estados + cadeia de custódia (`prescricao_custodia`). Portão de core + auditoria. |
| **Data** | 2026-07-22 (reescrito pelo arquiteto contra a `main` no ar) |
| **Origem** | Diagnóstico do Engenheiro-Chefe (sessão VS Code) **ratificado e corrigido** pelo arquiteto contra `~/Developer/PicSaude_Dev` @ `main` `a68bfa0`. O diagnóstico original foi feito contra um checkout **17 dias velho** (`~/Dev`, branch `feat/circulacao-t1-devolucao`, já mergeada #76) — as âncoras foram reescritas e o Problema 2 (fila do dispensador) foi corrigido. |
| **Decisão de design** | Fabiano, 2026-07-22: **Opção A — reusar `transferida_paciente`** (sem estado novo). |
| **Esforço** | S–M (~40 linhas produção + ~110 linhas teste). |

> ⚠️ **CHECKOUT CANÔNICO:** implementar em **`~/Developer/PicSaude_Dev`**, branch **nova a
> partir da `main` atual**. NÃO usar `~/Dev/PicSaude_Dev` (arquivado — stale, não deploya).

---

## §1 Problema — um bug, DUAS manifestações (ambas ratificadas contra a main no ar)

**Sintoma reportado (Fabiano):** depois que a receita vai ao dispensador, ela **não volta ao
paciente** no abandono/devolução — e, por consequência, **não volta ao prescritor**. E **o botão
"↻ Atualizar" do dispensador não funciona** (a receita não sai da fila).

**A causa é única, no backend — e explica os DOIS sintomas:**

1. `devolver_item(para=paciente)` já reabre custódia **de item** no nome do paciente (T1,
   `custodia.py:1003-1010`) — isso funciona. Mas logo chama `_recalcular_status_prescricao`
   (`custodia.py:1013`), que é **puramente contábil** (`custodia.py:195-224`): `devolvido_paciente`
   **não** está no conjunto `encerrados` (`custodia.py:212-213`) → conta como item ativo com
   `dispensados == 0` → cai no ramo `novo_status = "em_custodia"` (`custodia.py:221`).
   **Resultado:** item devolvido ao paciente → prescrição volta a `em_custodia`.
2. `devolver_item` **só fecha a custódia de ITEM** (`custodia.py:998`). O registro de custódia de
   **prescrição inteira** (`item_id IS NULL`) aberto na apresentação permanece **ativo e obsoleto**
   no nome do dispensador.

### Manifestação A — app do PACIENTE ("não volta ao paciente / ao prescritor")
- `em_custodia` cai no balde `_HISTORICO` (`auth.py:184,189`) → sai da posse.
- A UI só renderiza ações (devolver-ao-médico, re-apresentação) em `posse`
  (`cidadao.html::renderizarPosse`); histórico é read-only. **A receita "some".**
- Gates `devolver_prescritor` (`auth.py:303`) e `transferir-farmacia` exigem
  `transferida_paciente`/`pendente` → com `em_custodia` retornam **409**. Daí "não volta ao
  prescritor" e "não re-apresenta".

### Manifestação B — app do DISPENSADOR ("↻ Atualizar não funciona") — **a que o diagnóstico velho não viu**
- A fila do dispensador (`GET /dispensadores/fila`, `dispensadores.py:112-127`) seleciona por
  **custódia ativa do dispensador**: `FROM prescricao_custodia WHERE detentor_tipo='dispensador'
  AND detentor_id=? AND encerrada_em IS NULL`.
- Como o registro de **prescrição inteira** obsoleto (item 2 acima) segue ativo no nome do
  dispensador, **a receita permanece na fila** por mais que se aperte "↻ Atualizar" — o backend
  ainda mostra o dispensador detendo a prescrição.
- **`carregarFila` não é falha silenciosa** (`dispensador.html:1272-1280` tem try/catch + feedback).
  O botão "funciona"; é o **dado do backend** que está errado.

> **Por que passou verde:** `tests/integration/test_custodia_devolucao.py` só verifica custódia
> **item-level** e `status_item`; **nunca** o `status` da prescrição, os endpoints do paciente, nem
> `GET /dispensadores/fila`. O E2E de re-apresentação contorna `transferir-farmacia` chamando
> `dispensar` direto na Farmácia B. Os caminhos que os apps do paciente E do dispensador realmente
> usam não têm cobertura.

---

## §2 Decisão de design — Opção A (ratificada por Fabiano, 2026-07-22)

Devolução ao paciente resolve para **`transferida_paciente`** (reusa estado existente). A máquina
**já prevê** a transição: `TRANSICOES_PRESCRICAO["em_custodia"]` inclui `transferida_paciente`
(`states.py:76`) e `EVENTOS_PRESCRICAO[("em_custodia","transferida_paciente")] =
"custodia_transferida"` (`states.py:180`). **Nenhum estado novo, nenhum DDL, nenhuma mudança em
`CLAUDE.md §5a/§5b`.**

Dispensação parcial prévia (ex.: 4/10 já entregues) fica no **ledger e no saldo**, não no `status`.
A prescrição volta à posse para re-apresentar o restante — coerente com o §1 do
`PLANO_DEMO_CIRCULACAO.md`.

**Efeito dominó (por isso a Opção A é enxuta):** com `transferida_paciente`, os gates e buckets **já
corretos** aceitam automaticamente — `transferir-farmacia`, `devolver_prescritor` e `_EM_POSSE`
(`auth.py:183`) **não mudam**. E a fila do dispensador (`§1 B`) some sozinha, porque o §4.2 fecha a
custódia que a alimentava.

---

## §3 Escopo

### §3.1 Arquivos tocados (produção)
- `backend/app/routers/custodia.py` — `_recalcular_status_prescricao` (§4.1) + `devolver_item` ramo
  `para=paciente` (§4.2)

### §3.2 Arquivos que **NÃO** serão tocados
- `backend/app/domain/states.py` — transição/evento já previstos; **atualizar apenas a NOTA**
  (§4.3) registrando que o ramo `paciente` foi resolvido. Ramo `prescritor` segue como está (§8).
- `backend/app/routers/auth.py` — buckets e gates **já aceitam** `transferida_paciente`; **confirmar
  por leitura** (`_EM_POSSE` `:183`; gate `devolver_prescritor` `:303`; gate `transferir-farmacia`),
  não editar. Se algum **não** aceitar, **parar e escalar** ao arquiteto (o desenho pressupõe que sim).
- `backend/app/routers/dispensadores.py` — a fila (`§1 B`) se conserta sozinha via §4.2; **não editar**.
- `backend/app/routers/hospitalares.py` — recalc duplicado (`:219`); fluxo hospitalar **não gera**
  `devolvido_paciente` → o ramo novo nunca dispara ali → **não tocar**.
- Frontend (`cidadao.html`, `dispensador.html`) — nenhuma mudança; o fix é 100% backend.
- `CLAUDE.md`, DDL Postgres — sem estado novo.

### §3.3 Arquivos de teste
- `backend/tests/integration/test_custodia_devolucao.py` — novos cenários COER-1..COER-8 (§6).

---

## §4 Spec de implementação (âncoras contra a `main` no ar)

### §4.1 `_recalcular_status_prescricao` — ramo de posse (`custodia.py:195-224`)

Adicionar duas contagens e **um** ramo, **antes** de `dispensados == 0`:

```python
    total = len(rows)
    dispensados         = sum(1 for r in rows if r["status_item"] == "dispensado")
    retidos_farmacia    = sum(1 for r in rows if r["status_item"] == "em_custodia")
    devolvidos_paciente = sum(1 for r in rows if r["status_item"] == "devolvido_paciente")
    encerrados          = sum(1 for r in rows if r["status_item"] in
                              {"cancelado", "estornado", "devolvido_prescritor", "encerrado_fisico"})
    ativos              = total - encerrados

    if ativos == 0:
        novo_status = "cancelada"
    elif retidos_farmacia == 0 and devolvidos_paciente > 0:
        # Posse voltou integralmente ao paciente (abandono no balcão): nenhum item retido na
        # farmácia + ao menos um devolvido. em_custodia→transferida_paciente já previsto
        # (states.py:76,180). Parcial prévia fica no ledger/saldo, não no status
        # (Fabiano 2026-07-22, Opção A).
        novo_status = "transferida_paciente"
    elif dispensados == 0:
        novo_status = "em_custodia"
    elif dispensados >= ativos:
        novo_status = "dispensada"
    else:
        novo_status = "parcialmente_dispensada"
```

**Não-regressão:** o ramo só dispara com `devolvidos_paciente > 0`. Todo fluxo sem
`devolvido_paciente` (inclusive `dispensar_item`, que deixa itens em `em_custodia` →
`retidos_farmacia ≥ 1`) mantém comportamento idêntico.

### §4.2 `devolver_item` — reconciliar custódia de prescrição inteira (`custodia.py:936`, após o `_recalcular` em `:1013`)

No ramo `para=paciente`, o `paciente_row` já é buscado em `:1004-1006` e o `_recalcular` é chamado
em `:1013`. **Logo após** o `_recalcular`, quando a posse voltou integralmente
(`novo_status_prescricao == "transferida_paciente"`), fechar o registro de prescrição-inteira
obsoleto e reabrir no nome do paciente, **na mesma transação**:

```python
        novo_status_prescricao = _recalcular_status_prescricao(conn, presc["id"], agora)

        # Coerência da cadeia (TICKET-COERENCIA-DEVOLUCOES): quando a devolução devolve a POSSE
        # INTEGRAL (recalc → transferida_paciente), o registro de custódia de PRESCRIÇÃO INTEIRA
        # (item_id IS NULL) aberto na apresentação segue ativo e obsoleto no nome do dispensador.
        # É ele que (a) faz status transferida_paciente mentir contra GET /custodia.custodia_ativa e
        # (b) mantém a receita na fila do dispensador (dispensadores.py:112-127). Fechar + reabrir
        # no paciente resolve os dois.
        if payload.para == "paciente" and novo_status_prescricao == "transferida_paciente":
            _fechar_custodia_ativa(conn, presc["id"], None, agora)   # nível prescrição (item_id=None)
            _abrir_custodia(conn, presc["id"], None, "paciente",
                            normalize_cpf(paciente_row["cpf"]),
                            "Devolução integral ao paciente (abandono no balcão)", agora)
```

**Ordem canônica dentro de `devolver_item` (Opção A do §8 — evento aqui):** `ator_tipo`/`ator_id`
são definidos hoje **depois** (`:1022-1023`); **mover** para antes do bloco de reconciliação. A ordem
final, na mesma transação, é:

```
1. _recalcular_status_prescricao(...)                          → novo_status_prescricao
2. ator_tipo = usuario["role"]; ator_id = usuario["sub"]       (mover para cá)
3. if para == "paciente" and novo_status == "transferida_paciente":
     _fechar_custodia_ativa(conn, presc["id"], None, agora)    (prescrição-inteira, dispensador)
     _abrir_custodia(conn, presc["id"], None, "paciente", cpf, "devolucao_integral_paciente", agora)
     _gravar_evento(conn, presc["id"], "custodia_transferida", ator_tipo, ator_id,
                    {"de":"dispensador","para":"paciente","nivel":"prescricao",
                     "motivo":"devolucao_integral_paciente"}, agora, instance_id=iid)
```

> **`_fechar_custodia_ativa` com `item_id=None` está correto** — verificado pelo arquiteto
> (`custodia.py:136,141`): usa `WHERE ... item_id IS NULL`, não `= NULL`. (Nota Z AI 1.1 — classe de
> bug válida de checar; aqui o código já está certo.)

### §4.3 NOTA em `states.py`
Marcar que a incoerência do ramo **paciente** foi resolvida (recalc → `transferida_paciente`;
custódia de prescrição-inteira reconciliada). Manter a observação sobre o ramo **prescritor** (§8).

---

## §5 Critérios de aceite

### §5.1 Funcionais
1. `devolver_item(para=paciente)` de prescrição cujos itens ativos voltam todos ao paciente →
   `status_prescricao == "transferida_paciente"` (era `em_custodia`).
2. `GET /paciente/prescricoes` lista a prescrição em **`posse`** (não `historico`).
3. `POST /paciente/prescricoes/{proto}/devolver-prescritor` → **201** (era 409).
4. `POST /paciente/prescricoes/{proto}/transferir-farmacia` re-apresenta (aceita `transferida_paciente`).
5. `GET /{proto}/custodia`: `custodia_ativa` (nível prescrição) passa a ser **paciente**.
6. **`GET /dispensadores/fila` (JWT do dispensador que atendeu) NÃO lista mais a receita** — ela saiu
   da custódia dele. *(É o sintoma "Atualizar não funciona", provado no backend autoritativo.)*
7. Payload e shape de resposta de `devolver_item` **inalterados** (sem breaking no frontend).

### §5.2 Não-regressão
8. `dispensar_item` parcial ainda produz `em_custodia`; total ainda produz `dispensada`.
9. Suíte focal + custódia/dispensação verdes (§7).
10. Nenhum `UPDATE`/`DELETE` em `prescricao_eventos` (ledger append-only, §2 CLAUDE.md).

---

## §6 Testes (estender `tests/integration/test_custodia_devolucao.py`)

O arquivo já tem `_seed_prescricao_com_itens_em_custodia`, `_jwt_dispensador`, `_jwt_prescritor`,
`_custodia_ativa_item`. Adicionar `_jwt_paciente` e helper de custódia de prescrição-inteira
(`item_id IS NULL`). Cada cenário monta o próprio setup; asserções filtradas pelo `prescricao_id`.

- **COER-1 — status volta à posse:** `devolver(para=paciente)` → `status_prescricao == "transferida_paciente"` + `SELECT status FROM prescricoes` idem.
- **COER-2 — custódia de prescrição inteira reconciliada (+ coexistência, nota Z AI 1.2):**
  a custódia ativa **de prescrição-inteira** (`item_id IS NULL`) vira `("paciente", CPF)`; a do
  **dispensador** (`item_id IS NULL`) está **encerrada**. Assere também a **coexistência esperada**:
  as custódias **item-level** reabertas pelo T1 (`item_id = X`, `paciente`) continuam ativas — elas
  não conflitam (diferem no `item_id`) e **não** afetam a fila do dispensador (são `detentor_tipo =
  'paciente'`). `COUNT(custódia ativa do dispensador nesta prescrição) == 0`.
- **COER-3 — volta ao prescritor:** após devolver-paciente, `devolver-prescritor` (JWT paciente) → **201** (trava do 409).
- **COER-4 — re-apresentação:** `transferir-farmacia` → **201**.
- **COER-5 — bucket posse:** `GET /paciente/prescricoes` → protocolo em `posse`, não `historico`.
- **COER-6 — não-regressão dispensar:** parcial → `em_custodia`; total → `dispensada`.
- **COER-7 — parcial + abandono (posse ≠ saldo, nota Z AI 3):** dispensa 4/10 (Farmácia A) →
  `devolver(para=paciente)` → asserir explicitamente:
  - `status_prescricao == "transferida_paciente"` (a parcial NÃO trava a volta à posse);
  - `Σ dispensado do item == 4` (ledger imutável — NÃO zerou) e `Σ estornado == 0`;
  - **`saldo_efetivo do item == 6`** (= prescrito 10 − Σ dispensado 4). **Devolução devolve a POSSE,
    não o SALDO:** o prescrito NÃO volta a 10, e re-dispensar aceita **até 6**. (Evita que alguém
    implemente "devolução repõe saldo" — que seria a Opção B do B0, já rejeitada no estorno.)
- **COER-8 — 🎯 fila do dispensador limpa (o sintoma reportado) — padrão ANTES/DEPOIS (nota Z AI 2):**
  - **COER-8a (pré-condição):** ANTES de devolver, `GET /dispensadores/fila` (JWT do dispensador que
    detém) **LISTA** a receita. *(Sem isso, o teste passaria mesmo se a fila sempre voltasse vazia —
    falso-positivo.)*
  - **COER-8b:** DEPOIS de `devolver(para=paciente)`, a mesma chamada **NÃO retorna** a receita.
    Trava de regressão da Manifestação B — é o que o diagnóstico velho não cobriu.

**Paridade SQLite × Postgres** é gate da Fase 1: os cenários de status também na camada SQLite
(`tests/`) se a integração não cobrir.

---

## §7 Verificação no terminal (Engenheiro-Chefe executa em `~/Developer`)

```bash
cd ~/Developer/PicSaude_Dev/backend

# 0. Confirmar âncoras na main atual (as do diagnóstico velho diferem)
grep -n "_recalcular_status_prescricao" app/routers/custodia.py app/routers/hospitalares.py   # esperado ~195, ~1013 (call), 219 (hosp)
grep -nE "\"em_custodia\"|'em_custodia'" app/routers/auth.py                                    # buckets/gates
grep -nE "detentor_tipo = 'dispensador'|encerrada_em IS NULL" app/routers/dispensadores.py       # fila por custódia (§1 B)

# 1. Suíte focal (nova cobertura, inclui COER-8) — Postgres de teste
#    export DATABASE_URL=postgresql://<user>:<senha>@localhost/picsaude_test
python3 -m pytest tests/integration/test_custodia_devolucao.py -v

# 2. Regressão custódia / dispensação
python3 -m pytest tests/test_dispensacao_atomizada.py tests/test_atomizacao.py \
                  tests/test_dispensacao_hospitalar.py tests/test_integration.py -v

# 3. Guard append-only — zero UPDATE/DELETE novo no ledger
grep -rnE "UPDATE\s+prescricao_eventos|DELETE\s+FROM\s+prescricao_eventos" app/   # esperado: ZERO
```

---

## §8 Fora de escopo + coordenação

**Não fazer aqui:** ramo devolução ao **prescritor** (segue como está; correção formal —
`transferida_prescritor` — é item separado da NOTA `states.py`); `dispensar_item`; estado novo/DDL.

**Coordenação com `TICKET-LEDGER-COMPLEMENTAR-CUSTODIA.md`:** este ticket introduz uma nova
transição de posse (dispensador→paciente, nível prescrição, §4.2). **Decisão de fronteira:**
- **Opção A (recomendada, ratificada pelo arquiteto) — emitir o evento aqui.** Um
  `custodia_transferida` (`de=dispensador`, `para=paciente`, nível prescrição) na mesma transação.
  PR auto-coerente; sem transição sem rastro. O ticket de ledger cobre então só os caminhos
  item-level (evitar dupla emissão).
  - **Requisito de auditabilidade (nota Z AI 4):** o `motivo` deve ser **`devolucao_integral_paciente`**,
    **distinto** do `custodia_transferida` do T1.5 (auto-retenção demo) e do T1 (reabertura de item).
    Sem `motivo` distinto, o histórico (T6) renderiza vários `custodia_transferida` indistinguíveis e
    o auditor não separa "auto-retenção demo" de "devolução integral" de "reabertura de item".
- **Opção B — PR mínimo** (só §4.1+§4.2, sem evento); o evento inteiro fica no ticket de ledger,
  mas entre merges a transição fica sem rastro.

Sem decisão explícita, seguir **Opção A**.

---

## §9 Commit message canônico

```
fix(custodia): devolução ao paciente devolve a posse (status + custódia + fila)

- _recalcular_status_prescricao: ramo de posse — itens devolvido_paciente sem
  retenção na farmácia → transferida_paciente (Opção A, reusa estado existente)
- devolver_item(para=paciente): reconcilia custódia de prescrição inteira
  (fecha registro obsoleto do dispensador, reabre no paciente) na mesma transação
  → resolve TAMBÉM a fila do dispensador (GET /dispensadores/fila)
- NOTA states.py: ramo paciente resolvido; ramo prescritor segue registrado
- testes: caminho do app do paciente (posse, devolver-prescritor 201, re-apresentação,
  parcial+abandono) + COER-8 (fila do dispensador limpa)

Refs: TICKET-COERENCIA-DEVOLUCOES.md · Decisão: Fabiano 2026-07-22 (Opção A)
Coordena: TICKET-LEDGER-COMPLEMENTAR-CUSTODIA.md
```

---

## §10 Portões (core — merge só com martelo do Fabiano)

1. Engenheiro-Chefe implementa em **`~/Developer/PicSaude_Dev`, branch nova a partir da `main` atual**
   (NÃO em `~/Dev` / `feat/circulacao-t1-devolucao` — stale, arquivado). §4 + §6.
2. Verificação §7 **verde** (SQLite × Postgres).
3. Revisão pós-implementação (diff real) + auditoria de invariante de custódia.
4. **Fabiano aprova + merge.** Não é mergeado sem o martelo.
