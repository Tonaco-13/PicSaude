# PARECER-REVISOR — Auditoria de implementação: TICKET-CORE-ESTORNO (spec v2)

| Campo | Valor |
|---|---|
| **Audita** | Implementação do `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO` (spec v2, Opção Y roteada por motivo) |
| **Parecer de origem** | `docs/tickets/PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` (revisão do ticket + Apêndice A) |
| **Papel** | Revisor — auditoria com **prova de execução** (o implementador não se auto-certifica) |
| **Data** | 2026-08-10 |
| **Veredito** | ✅ **Livre para o martelo do Fabiano + portão do Conselheiro** (classe `core`). Todos os achados endereçados; suíte PG **17/17 verde** verificada por mim. |

---

## §1 Método — prova de execução, não leitura

O ambiente do engenheiro não tinha PostgreSQL (Docker inativo) e os testes de integração são
PG-only. Subi um **PostgreSQL 15.18 efêmero SEM Docker**, com os binários Homebrew já presentes
(`initdb`/`pg_ctl` em `/usr/local/bin`), e rodei a suíte real contra ele. Receita reproduzível:

```bash
SCRATCH=<scratchpad>                 # caminho curto para o socket importa (ver gotcha 2)
export PGDATA="$SCRATCH/pgdata" PGPORT=5433
LC_ALL=C initdb --locale=C --encoding=UTF8 --auth-host=trust --auth-local=trust -U picsaude "$PGDATA"
LC_ALL=C pg_ctl -D "$PGDATA" -o "-p $PGPORT -k /tmp -c listen_addresses=127.0.0.1" -w start
createdb -h 127.0.0.1 -p $PGPORT -U picsaude picsaude_test
cd backend && DATABASE_URL=postgresql://picsaude:picsaude@127.0.0.1:5433/picsaude_test \
  LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 ../.venv-x86/bin/python -m pytest tests/integration/test_estorno.py -v
```

Gotchas descobertos (valem para o CI local de qualquer core PG):
1. `initdb` exige locale explícito no sandbox (`LC_ALL=C --locale=C`) — senão "invalid locale settings".
2. O socket Unix do PG tem limite de **103 bytes**; o scratchpad é longo demais → usar `-k /tmp`.
3. Para o pytest, **voltar a um locale UTF-8** (`LANG=en_US.UTF-8`): sob `LC_ALL=C`, o Alembic lê
   `alembic.ini` como ASCII e estoura `UnicodeDecodeError` no primeiro acento.
4. Usar `.venv-x86` (o `.venv`/`backend/.venv` não têm as deps — memória `ambiente-testes-local`).

## §2 Resultado

| Rodada | Resultado |
|---|---|
| `test_estorno.py` (1ª passada, pré-fix) | **14 passed / 1 failed** (§8.7 — ordem de evento) |
| Cenários ausentes Q2/Q3 (escritos por mim, descartados) | ✅ ambos passaram |
| `test_states.py` (contrato, sem DB) | ✅ **104 passed** |
| `test_estorno.py` (2ª passada, pós-fix + 2 testes novos do engenheiro) | ✅ **17 passed / 0 failed** |

## §3 O achado (§8.7) e sua resolução

- **Sintoma:** `test_estorno_total_ledger_sequencia_paciente` falhava. Ordem real emitida:
  `estorno_registrado → custodia_transferida(item) → custodia_transferida(prescrição) →
  item_devolvido_paciente`; o teste exigia `item_devolvido_paciente` **antes** de
  `custodia_transferida`.
- **Diagnóstico:** o handler emite o evento do item **depois** dos `transferir_posse`
  (`dispensacoes.py:690`), **idêntico ao precedente ratificado `devolver_item`**
  (`custodia.py:1148` reconciliação → evento). O **teste** era o outlier — pedia uma ordem que nem
  o código novo nem a devolução-ao-paciente existente usam.
- **Resolução (engenheiro):** corrigiu o **teste**, não o handler — asserção tolerante à ordem
  entre `item_devolvido_paciente` e `custodia_transferida`, mantendo só a causalidade
  (`estorno_registrado` antes de ambos). Docstring cita a auditoria e o `devolver_item`.
  **Verificado verde no PG.** Correto: mudar o handler divergiria do precedente.

## §4 As 3 perguntas do engenheiro — confirmadas com execução

- **Q1 — `uq_custodia_ativa_*` (unicidade):** ✅ O ramo paciente espelha `devolver_item`
  (item-level pelo choke-point + reconciliação nível-prescrição só ao virar `transferida_paciente`).
  Chaves `(pid,item)` e `(pid,NULL)` são distintas → sem colisão. Provado por
  `test_estorno_total_sem_custodia_orfa` + `test_estorno_total_multi_item_...` (COUNT=1 por chave,
  irmão com 0 ativas). Zero `IntegrityError` na suíte. *Nota:* dupla-cobertura cross-granularidade
  (item+prescrição no mesmo detentor) é padrão herdado do `devolver_item`, não novidade do estorno.
- **Q2 — multi-item → `transferida_paciente` com irmão `dispensado`:** ✅ Correto e funcional.
  Ressalva registrada no próprio teste: o status é **resumo lossy** — a entrega do irmão vive no
  `status_item`, não no status da prescrição.
- **Q3 — parcial-de-total → dispensador (B0):** ✅ `estorno_total = dispensado AND saldo_efetivo >=
  qtd_prescrita`; parcial-de-total dá saldo `< prescrito` → ramo dispensador, item não mutado (§3.4).

## §5 Contrato A–D — coerente e honesto

- **A** (colisão B0): roteamento por motivo — `erro_dispensacao` e parcial preservam B0. ✅
- **B** (estorno não muta item): CLAUDE.md §2 + `states.py:157` reescritas para "mutação condicional". ✅
- **C** (aresta `dispensado→devolvido_paciente`): em `TRANSICOES_ITEM` + `EVENTOS_ITEM`. ✅
- **D** (`dispensada`/`dispensado` terminal): §5b exceção nomeada + 2 testes de contrato emendados. ✅

## §6 Cobertura incorporada após a auditoria

Os 2 gaps que o PR original não testava foram incorporados pelo engenheiro com nomes **gateáveis**
(contêm "estorno", casam o `-k` do `gates.yml` — a armadilha "verde e não gateado apodrece"):

- `test_estorno_total_multi_item_irmao_dispensado_intacto` (Q2)
- `test_estorno_parcial_de_dispensacao_total_mantem_dispensador` (Q3)

Ambos **verificados verdes por mim no PG**.

## §7 Encaminhamento

- Bloqueador §8.7: **resolvido**. Gaps: **incorporados**. Contrato A–D: **coerente**. Suíte: **17/17**.
- **Livre para o martelo do Fabiano.** O Conselheiro confere o PR contra o código real no portão de
  `core` (verificação independente da minha — como manda o pacto). Jules só em marco/fase.
- **Não auditei a suíte SQLite inteira** — as ~54 falhas do `item_nao_retido` são WIP do Kimi, à
  parte; as 2 de `test_states.py` que o engenheiro tocou estão emendadas e verdes (104/104).
- No CI (`gates.yml`), o passo de integração PG roda `test_estorno.py` (o `-k` inclui `estorno`) em
  todo PR + push + nightly — é lá que estes 17 rodam na esteira oficial.
