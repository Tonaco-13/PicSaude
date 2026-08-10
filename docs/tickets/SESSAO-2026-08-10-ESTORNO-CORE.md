# Sessão 2026-08-10 — Registro: bug do estorno que não chega ao cidadão (core)

| Campo | Valor |
|---|---|
| **Arquiteto / Engenheiro** | ZCode (GLM-5.2) — redator, especulador, implementador |
| **Revisor** | Claude Code no terminal — auditoria independente com prova de execução PG |
| **Martelo** | Fabiano Tonaco Borges — §3.2 (roteamento) e merge final |
| **Contexto** | Bug reportado pelo Fabiano ("estornei e não chegou ao cidadão; depois caiu"). Resultou em mudança `core` que emenda decisão ratificada (`TICKET-B0`). |

---

## §1 O arco completo (cada papel cumpriu o seu; ninguém se auto-certificou)

| Fase | Quem | Saída |
|---|---|---|
| Teste de UI black-box (picsaude.com.br) | ZCode (agente de UI) | Bug reproduzido a vivo: estorno total não devolve a receita ao cidadão — carteira fica vazia (`posse: []`), `devolver-prescritor` retorna 409. 17 screenshots em `gui-test-screenshots/`. |
| Relatório + ticket v1 | ZCode (Arquiteto) | `RELATORIO-BUG-ESTORNO-CIDADAO-2026-08-10.md` + `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` v1 (proposta "sempre ao paciente"). |
| Parecer do Revisor | Revisor | `PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` — **destoa**: a v1 reverte `TICKET-B0` (ratificado/testado) e contradiz invariante do CLAUDE.md §2 sem reconhecer. Volta ao Arquiteto. |
| Spec v2 | ZCode (Arquiteto) | Reescrita: **Opção Y roteada por motivo** (Revisor ratificada + refinada). Achado-chave: o caso TOTAL é o "fork #1" reconhecido no docstring do teste — **nenhum teste verde o cobre**. |
| Martelo §3.2 | Fabiano | `pagamento_nao_concluido → cidadão`. Régua final: cidadão recupera em 3 dos 4 motivos; só `erro_dispensacao` retém na farmácia. |
| Implementação | ZCode (Engenheiro) | `states.py` + `dispensacoes.py` + `test_estorno.py` (9 testes) + `test_states.py` (2 emendados) + `CLAUDE.md` (§2/§3/§5a/§5b). Desmembrado: `TICKET-DISPENSADOR-ESTORNO-PROMPT-NATIVO.md` (module). |
| Auditoria independente | Revisor | **Subiu PostgreSQL 15.18 efêmero sem Docker** (o ambiente do engenheiro bloqueava) + rodou os 17 testes. `PARECER-REVISOR-ESTORNO-AUDITORIA-IMPL.md`. |
| Martelo de merge | Fabiano | "Pode mergear." |

## §2 O que a mudança faz (resumo técnico)

Estorno **TOTAL** nos motivos "cidadão recupera" (`desistencia_paciente`, `pagamento_nao_concluido`, `outro`) passa a:
- mutar o item `dispensado → devolvido_paciente` (aresta adicionada em `TRANSICOES_ITEM`);
- devolver a custódia ao paciente via choke-point `transferir_posse` (motivo canônico novo `devolucao_pos_estorno`);
- recalcular a prescrição a `transferida_paciente` + reconciliação cross-granularidade (à moda de `devolver_item`).

Destrava as duas vias do cidadão: **retry em outra farmácia** e **devolução ao prescritor** (§3 do CLAUDE.md, a única via de correção clínica).

**Preserva o `TICKET-B0` onde ele faz sentido:** estorno **parcial** (de qualquer motivo) e motivo `erro_dispensacao` (total) não mutam o item — seguem reabrindo ao dispensador para re-dispensação. O caso total é o "fork #1" reconhecido no `test_redispensa_apos_estorno_usa_saldo_reposto` (docstring), agora fechado.

## §3 Conflitos A–D (todos endereçados no mesmo PR)

| # | Conflito | Resolução |
|---|---|---|
| A | Reverte `TICKET-B0` ratificado | Roteamento por motivo + gate estorno-total. Só o total "cidadão recupera" emenda o B0. Martelo Fabiano §3.2. |
| B | CLAUDE.md §2 / `states.py:157` diziam "estorno NÃO é transição de item" | Emendados: mutação **condicional** (só total + motivo cidadão). `dispensado → estornado` segue dormente. |
| C | Aresta `dispensado → devolvido_paciente` não existia | Adicionada em `TRANSICOES_ITEM` + mapeada em `EVENTOS_ITEM`. |
| D | `dispensada`/`dispensado` são terminais | Exceção nomeada declarada (§5b), à moda do COER2-POS-MERGE-FIX. |

## §4 Prova de execução (Revisor, PG real)

- `test_estorno.py` — **17/17** (9 novos + regressão).
- `test_states.py` — **104/104** (contrato A–D).
- Q1 (unicidade `uq_custodia_ativa_*`), Q2 (multi-item, irmão intacto), Q3 (parcial-de-total → B0) — provados no PG, não só lidos.
- **Bloqueador encontrado e resolvido:** o §8.7 (ordem do ledger) falhou na 1ª rodada — o teste pedia `item_devolvido` antes de `custodia_transferida`, mas o handler (como `devolver_item`) emite custódia antes. **Corrigido o teste**, não o handler (consistência com o precedente).

## §5 Lições de processo

- **Implementador não se auto-certifica.** O engenheiro (eu) não pôde rodar PG; declarei isso honestamente e o Revisor fechou a lacuna subindo um cluster efêmero. Foi o Revisor quem achou a falha no §8.7 — exatamente o tipo de coisa que a auto-certificação esconderia.
- **PG efêmero sem Docker é factível** (Homebrew + `initdb`/`pg_ctl`, socket em `/tmp`, `LC_ALL=C` no server vs UTF-8 no pytest). Reaparece como bloqueador em várias sessões; a memória `ambiente-testes-local` tem a receita.
- **Verificar no código real, não na descrição de terceiros** — vale para Arquiteto (verifiquei o Revisor) e para Revisor (verificou o ticket). O achado do "fork #1 não testado" só apareceu lendo o docstring do teste.
- **Estorno é objeto derivado, mas a posse não é derivada.** O registro contábil (`estornos`) está correto e intocável; a lacuna era só na **propagação** pós-INSERT (estado do item + custódia). Decisão de design preservada; gap fechado.

## §6 Artefatos da sessão

- `docs/RELATORIO-BUG-ESTORNO-CIDADAO-2026-08-10.md` (repro + 17 screenshots)
- `docs/tickets/TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` (spec v2)
- `docs/tickets/PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` (parecer spec, destoa)
- `docs/tickets/PARECER-REVISOR-ESTORNO-AUDITORIA-IMPL.md` (parecer impl, 17/17 PG)
- `docs/tickets/TICKET-DISPENSADOR-ESTORNO-PROMPT-NATIVO.md` (module desmembrado)
- Código: `backend/app/domain/states.py`, `backend/app/routers/dispensacoes.py`, `backend/tests/integration/test_estorno.py`, `backend/tests/test_states.py`, `CLAUDE.md`

## §7 Estado final

**Martelado pelo Fabiano para merge.** Classe `core` → o Conselheiro faz a verificação independente no portão (a auditoria do Revisor soma, não substitui). O `prompt()`/"caiu" ficou como ticket `module` separado (não bloqueia o core).
