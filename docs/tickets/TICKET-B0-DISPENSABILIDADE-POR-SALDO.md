# TICKET-B0 — Dispensabilidade derivada do saldo efetivo (estorno total re-habilita o item)

| Campo | Valor |
|---|---|
| **Fase** | 5 — pré-requisito de backend da Fatia B |
| **Classe** | `module` (guard de dispensação + fila + reabertura de custódia no estorno). **Não** cria estado novo → não é `core` de máquina de estados. |
| **Para** | code/MS (engenheiro) — após martelo do Fabiano (Opção A) |
| **Origem** | Achado B0 (arquiteto, 2026-07-11) · recomendação convergente dos dois arquitetos · parecer Z AI: **Opção A, verde, com regra de fila explícita** |
| **Tese** | Caso concreto de R1/§2a e do §10: a dispensabilidade deriva do **saldo efetivo** (ledger), não do **rótulo** `status_item`. |
| **Depende de** | Nada (backend puro). **Destrava** a reentrada na fila da Fatia B (§4.1). |

---

## §1 Problema (o furo)

Item totalmente dispensado → `status_item='dispensado'` (terminal) + custódia fechada
(`custodia.py:787-796`). O estorno repõe o **saldo** mas — por design do objeto-derivado — **não muta o
item** (`dispensacoes.py:514-515`). A re-dispensação bate em
`_BLOQUEADOS_DISPENSAR = {'dispensado', …}` → **409**, com saldo efetivo > 0
(`custodia.py:737-743`). Resultado: "item volta a ser dispensável" (CLAUDE.md §4) **não é entregue** no
caminho dispensar-tudo → estornar → dispensar de novo.

## §2 Decisão (Opção A — martelo Fabiano)

O rótulo `status_item='dispensado'` permanece como **registro histórico**. A **dispensabilidade** passa
a ser derivada do **saldo efetivo** (Σ dispensado − Σ estornado). Nenhuma transição nova; o item **não
é mutado** pelo estorno (invariante do TICKET-ESTORNO preservado). O que muda é *quem lê a verdade*: o
guard e a fila passam a ler o saldo, não o rótulo.

## §3 Mudanças de backend

### 3.1 Guard de dispensação por saldo (`custodia.py` ~737-762)

Ordem correta do guard em `dispensar_item`:

1. Computar `saldo_efetivo = prescrito − (Σ dispensado − Σ estornado)` **primeiro** (já é computado
   logo abaixo, linhas 745-759 — apenas mover a checagem de saldo para antes do bloqueio por rótulo).
2. `saldo_efetivo <= 0` → **409 "Não há saldo disponível"**.
3. Bloquear por status **apenas** nos estados que impedem dispensação **independentemente do saldo**:
   `_BLOQUEADOS_HARD = {'cancelado', 'devolvido_prescritor', 'encerrado_fisico', 'estornado'}`.
   **`'dispensado'` SAI do conjunto de bloqueio** — com saldo>0 (pós-estorno) o item é dispensável.
4. Caso contrário → segue a dispensação.

> `'dispensado'` com saldo>0 é o estado "sem saldo no momento que foi reposto pelo estorno". O rótulo
> não é apagado; ele deixa de ser o *critério* de dispensabilidade.

### 3.2 Reabertura de custódia no estorno que repõe saldo (`dispensacoes.py`, endpoint estornar ~458-505)

Após inserir o objeto-estorno e recomputar `saldo_efetivo`, **se** o item ficou sem custódia ativa
(caso da dispensação total: custódia foi fechada em `custodia.py:796`) **e** `saldo_efetivo > 0`:

- **Reabrir custódia do item para o dispensador** que estorna (o estabelecimento retém o item de novo
  para re-dispensação) e **emitir `custodia_transferida`** — retenção sem o evento é bug (CLAUDE.md §2,
  invariante de retenção). Mesmo padrão de `_fechar_custodia_ativa`/`_abrir_custodia` já usado na
  dispensação parcial (`custodia.py:813-814`).
- **Só** quando não havia custódia ativa. No estorno **parcial** o item ainda estava `em_custodia` com
  custódia aberta → **nada a reabrir** (já dispensável).

> Isso **não** contradiz "estorno não muta o item": reabrir custódia é um **evento de custódia
> legítimo** (o saldo voltou, a farmácia detém o item de novo), registrado no ledger — não é a
> transição proibida `dispensado→estornado` nem edição da dispensação.

### 3.3 Fila expõe dispensabilidade derivada (`dispensadores.py`, `fila` ~129-166)

- Com 3.2, a prescrição com item re-habilitado **reaparece** na fila (custódia reaberta → a query de
  custódia ativa volta a trazê-la). Sem mudança na cláusula de custódia.
- **Fonte única da verdade para a UI:** cada item da fila passa a expor um booleano **`acionavel`**,
  computado **no backend**: `acionavel = saldo_efetivo > 0 AND status_item NOT IN _BLOQUEADOS_HARD`.
  A Fatia B (§4.2/§4.1) lê `i.acionavel` — **nunca** recalcula "terminal" no cliente (respeita "estado
  do backend, nunca local"). `saldo` continua exposto para exibição.

## §4 Invariantes

- **Preservados:** estorno não muta a dispensação nem cria transição `dispensado→estornado`
  (TICKET-ESTORNO); ledger append-only (§2); protocolo imutável (§6b).
- **Corrigido:** dispensabilidade deriva do saldo (§10 "estados computados não persistidos" · R1).
- **Reforçado:** toda reabertura de custódia emite `custodia_transferida` (§2, invariante de retenção).
- Determinismo: queries de saldo com `COALESCE(SUM(...),0)`; sem novos `ORDER BY` sem desempate.

## §5 [PII-EXAUSTIVIDADE]

Nenhuma coluna PII tocada. `fila` já expõe paciente nome/CPF sob `require_role('dispensador','admin')`
(inalterada). `acionavel` é booleano derivado. Nenhuma rota nova, nenhuma rota pública.

## §6 Critérios de aceite

1. Dispensar saldo total → estornar total → **nova dispensação do mesmo item é aceita** (não mais 409),
   respeitando `saldo_efetivo`.
2. Após estorno total, a prescrição **reaparece na fila** com o item `acionavel=true` e `saldo` reposto;
   ledger tem **um** `custodia_transferida` novo (retenção pelo dispensador).
3. Estorno **parcial** (item ainda `em_custodia`): saldo repõe, item segue `acionavel`, **nenhuma**
   custódia nova reaberta (não duplica custódia).
4. Item `cancelado`/`devolvido_prescritor`/`encerrado_fisico` **nunca** vira `acionavel`, mesmo com
   qualquer saldo (bloqueio hard preservado).
5. `status_item='dispensado'` **não é apagado** em nenhum caminho (registro histórico intacto);
   comprovante e relatório continuam mostrando a dispensação original.
6. Testes **verdes contra PG** (datetime; saldo por SUM) + gate com predeploy. Guard-rail de unicidade
   (R2) não acusa duplicidade após o ciclo dispensar→estornar→dispensar.

## §7 Fora de escopo

- Estado de item novo (não criar `re_disponivel` etc. — a dispensabilidade é derivada, não persistida).
- Mudança no relatório (Fatia A) — o saldo escriturado já subtrai estornos.
- Frontend — é a Fatia B (§4). Este ticket só entrega backend + o campo `acionavel`.
