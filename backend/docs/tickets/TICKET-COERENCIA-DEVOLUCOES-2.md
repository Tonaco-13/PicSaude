# TICKET-COERENCIA-DEVOLUCOES-2 — Choke-point de posse + guarda de unicidade

**Classe:** `core` (máquina de estados + `prescricao_custodia` + constraint de banco)
**Ratificado por Fabiano:** 2026-07-23 — §9.1 = **Opção B**; §9.2 = **carona**
**Branch:** `fix/coerencia-devolucoes-2-chokepoint`

> A spec integral (Z AI → Arquiteto) está no corpo do PR. Este documento é o
> **registro de implementação**: decisões ratificadas, âncoras confirmadas contra a
> `main`, desvios do esboço §6, e evidência de aceite.

---

## Decisões ratificadas (§9)

- **§9.1 → Opção B:** novo estado de prescrição `transferida_prescritor`, ESPELHO de
  `transferida_paciente` (posse com o prescritor aguardando correção). Unifica os dois
  caminhos-espelho que discordavam (`auth.py`→`pendente` vs `custodia.py` recalc→`cancelada`).
  Custo real baixo: **não há CHECK em `prescricoes.status`** (a máquina de estados é só
  Python, `domain/states.py`) → sem migração de constraint para o estado.
- **§9.2 → carona:** o motivo digitado pelo cidadão não chegava ao prescritor. Corrigido
  neste PR.

## Causa-raiz de cada cenário (confirmada no código)

- **Cenário 1** (estorno + devolução ao paciente prende na fila): o guard de `devolver_item`
  barrava por **rótulo** (`status_item == 'dispensado' → 409`), não por **saldo**. Após um
  estorno, o item fica rotulado `dispensado` mas com saldo reposto → tinha posse a devolver,
  e o 409 a prendia. Além disso, a custódia de **prescrição inteira** obsoleta do dispensador
  seguia ativa (dupla posse cross-granularidade), mantendo a receita na fila.
- **Cenário 2** (devolução ao prescritor não sai da carteira; motivo some): status ia a
  `pendente` (ambíguo — colidia com "aguardando 1º envio ao paciente"), e a carteira do cidadão
  mostrava como "Documento Ativo". O motivo sumia porque `auth.py::devolver_prescritor` só
  emitia `custodia_transferida` de **nível-prescrição** (sem `item_id`), enquanto o painel do
  prescritor (`prescritor.py`) lê o motivo de eventos **`item_devolvido_prescritor`** por item.

## O que foi implementado (§4, na ordem)

1. **Guarda (Passo 1a)** — `tests/test_coer2_chokepoint_guard.py` (código) +
   `test_guarda_unicidade_custodia_ativa` (banco, PG).
2. **Choke-point** — `custodia.py::transferir_posse(...)`: fecha a custódia anterior + abre a
   nova + emite `custodia_transferida`, atômico. Motivo canônico por caminho.
3. **Roteamento dos caminhos** pelo choke-point: `transferir_custodia`, `dispensar_item`
   (auto-retenção demo + reconciliação parcial), `devolver_item` (reconciliação nível-prescrição),
   `auth.py::transferir_farmacia`, `auth.py::devolver_prescritor`, `dispensacoes.py` (estorno).
4. **Data-fix (§5)** — na migração `c0e2f1a3b4d5`, ANTES da constraint: reconcilia dupla-posse
   (mantém a mais recente por `created_at DESC, id DESC`) e emite `custodia_reconciliada_data_fix`.
5. **Constraint (Passo 1b)** — índice único parcial nos dois dialetos: PG `NULLS NOT DISTINCT`;
   SQLite `COALESCE(item_id, -1)`.

## Desvios do esboço §6 (âncoras confirmadas contra a `main`)

| Esboço §6 | Realidade / decisão |
|---|---|
| "5 caminhos" | São **6** escritores de `prescricao_custodia`. Os 2 do `auth.py` usavam **SQL inline** (roteados agora). O **hospitalar** (`hospitalares.py`) já fecha AMBAS as granularidades → constraint-safe; mantém helper próprio (contexto `unidade_id`), fora do choke-point genérico por design. |
| payload `de_tipo`/`para_tipo` | O vocabulário real do ledger é `de`/`para` (+ `de_id`/`para_id`). Mantido para não quebrar o T6 nem o teste 4D.1. |
| `devolver_item(para=paciente)` roteado inteiro | A custódia de **item** e o evento `item_devolvido_*` (payload especializado, consumido por `prescritor.py` + testes) permanecem; o choke-point cobre a **reconciliação nível-prescrição**. A constraint garante a unicidade. |
| motivo estorno `reabertura_pos_estorno` | → `estorno_reposicao_saldo` (canônico §6.2). |
| `encaminhamentos.py` tem `_fechar/_abrir` homônimos | São de OUTRA tabela (`encaminhamento_custodia`) — fora de escopo; o guard §8 é escopado a `prescricao_custodia`. |

## Motivos canônicos por caminho (T6)

`transferencia_farmacia` · `abandono_balcao` · `devolucao_integral_paciente` ·
`devolucao_ao_prescritor` · `estorno_reposicao_saldo` · `auto_retencao_demo` · `dispensacao`.
Texto livre do usuário → `motivo_detalhe` (nunca sobrescreve o canônico).

## Evidência de aceite

- `tests/integration/test_custodia_devolucao.py`: **26 verdes** (COER-1..8 + guarda +
  COER-9/10/11).
- Regressão PG: `tests/integration/` **349 passaram**; as 9 falhas são **pré-existentes**
  (catálogo/receituário/laudo — confirmado com as mudanças em `git stash`).
- Unit: `test_states.py` + `tests/unit/` **512 verdes**; guard `test_coer2_chokepoint_guard.py`
  **4 verdes**.
- Migração verificada nos 2 dialetos: ordem data-fix→constraint com violações pré-existentes
  (reconcilia, emite evento, cria índice); constraint rejeita dupla posse mesma-granularidade
  (inclusive `item_id IS NULL` via `NULLS NOT DISTINCT` / `COALESCE`).

## Fora de escopo (mantido)

XML SNGPC, WebSocket, polish de UX, botão Relatório Consolidado, verificação pública de
atestados, farmácia hospitalar (constraint-safe, helper próprio). Deleção de registro: proibida.
