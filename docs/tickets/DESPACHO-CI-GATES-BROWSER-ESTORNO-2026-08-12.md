# DESPACHO — CI `gates-browser` vermelha: commitar o fix do estorno (já implementado e auditado)

> ## ⚠️ RETIFICAÇÃO 2026-08-12 (sessão Claude Code/terminal — PR #155)
>
> **Este despacho errou a premissa do §3 e está SUPERADO.** Registrar as correções
> para não recontaminar a próxima frente:
>
> 1. **Não havia "Frente A" solta.** Os 6 arquivos têm **zero diff contra `origin/main`** —
>    o fix do estorno já estava mergeado (`c872b55`, PR #152). O `git status` mostrava
>    "modificado" porque o checkout estava em `docs/handoff-2026-08-09`, **atrás** da main.
>    Régua correta: `git diff origin/main -- <arquivo>`, não `git status`.
> 2. **Causa real do vermelho:** os 3 smokes estornavam com `desistencia_paciente`
>    (Opção B: posse volta ao cidadão **dentro** do estorno) e depois executavam à mão
>    o que o #152 automatizou — daí o 403 `nao_detem_custodia` (correto) e a fila vazia.
>    Corrigido no **PR #155** sem tocar produção: passos obsoletos substituídos por
>    asserções do efeito real + B2 parametrizado nos dois ramos do roteamento
>    (`tests/browser`: 54 passed; unit: 516 verdes).
> 3. **Opção B ratificada pelo Fabiano** (`outro` RETÉM na farmácia) — o §2 abaixo
>    reafirma a spec v2 (`outro → cidadão`), que **não** é o implementado nem o que
>    consta no CLAUDE.md. Registrado no parecer da sessão.
> 4. **§4.3 errado:** `test_states.py` (unit) e testes de integração na mesma
>    invocação pytest produzem 28 erros espúrios (conftests colidem) — rodar separados.
> 5. **`backend/.venv` quebrado neste Mac** (wheels arm64 × host) — usar `.venv-x86`.
> 6. **Lição de cadência (a mais cara):** o `gates-browser` só roda em nightly e em PR
>    que toca `.html`. O #152 mudou custódia sem tocar `.html`, entrou entre dois
>    nightlies e ficou 6 h invisível — o vermelho estourou num PR de frontend alheio
>    (#154) e foi lido como culpa dele. Sugestão registrada no #155: acrescentar
>    `backend/app/routers/**` e `backend/app/domain/states*.py` aos paths do workflow.
>
> O texto abaixo permanece como registro histórico da leitura feita às 15h — com as
> ressalvas acima.

---

| Campo | Valor |
|---|---|
| **De** | Kimi, a pedido do Fabiano |
| **Para** | Claude Code (terminal) |
| **Data** | 2026-08-12 |
| **Classe** | **`core`** — custódia, máquina de estados, ledger. **Revisão central obrigatória** (CLAUDE.md §10). |
| **Origem** | PR #154 (`feat(frontend): chaves demo só nos módulos + Lente de Auditoria`) — check `gates-browser / smokes` ❌. Confirmado **pré-existente na `main`** (último run do `gates-browser` na main também falhou). O PR #154 é 100% frontend e **não** é a causa. |
| **Resumo em 1 linha** | O fix já foi especificado (ticket v2, martelado), implementado e auditado — **mas nunca foi commitado**: está solto na árvore de trabalho. A tarefa é validar, separar por frente, commitar e mergear — **não re-implementar**. |

---

## §1 Sintoma na CI (evidência)

Job `gates-browser / smokes (pull_request)` → `python -m pytest tests/browser -q`
Resultado: **2 failed, 4 errors** (48 passed). Assinatura única: após **estorno total**, a custódia não é reaberta corretamente.

```
tests/browser/test_coer2_e2e.py (4 erros no fixture, linha ~97):
  coreografia: emite → transfere p/ farmácia → dispensa total → estorna →
  POST /prescricoes/{p}/itens/{iid}/devolver {"para": "paciente"}
  ESPERADO: 200 ("guard por SALDO, não 409 'já dispensado'")
  ATUAL:     403 {"codigo":"nao_detem_custodia",
                  "mensagem":"Dispensador não detém custódia ativa deste item."}

tests/browser/test_coer2_fix.py::test_nao_fresh_motivo_renderiza_na_caixa_de_correcoes
  → mesmo 403 no /devolver.

tests/browser/test_f5_b2_ciclo_pos_dispensacao.py::test_b2_escopo_a_reentrada_por_estorno
  → após estorno total, a receita NÃO reaparece em #fila-lista (só consta como
    "Estornado" no Histórico de Retenções). TICKET-B0 §6.2 exige reentrada na fila.
```

Log completo: anexo do Fabiano em 2026-08-12 (2m 8s, "EEEEF...F").

## §2 Causa raiz — já diagnosticada, não rediagnosticar

O handler de estorno não reabre custódia conforme o desenho ratificado. Leia **nesta ordem**:

1. `docs/tickets/TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` — **spec v2 (Arquiteto), martelo do Fabiano em §3.2 (10/08)**: roteamento por motivo — `desistencia_paciente`, `pagamento_nao_concluido`, `outro` → custódia volta ao **cidadão**; só `erro_dispensacao` retém na farmácia (preserva `TICKET-B0` onde ele faz sentido).
2. `docs/tickets/PARECER-REVISOR-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` — por que o "fix óbvio" (sempre ao paciente) é errado.
3. `docs/RELATORIO-BUG-ESTORNO-CIDADAO-2026-08-10.md` — repro black-box (17 screenshots).

## §3 O ponto central: o fix JÁ EXISTE na árvore (não-commitado)

`docs/tickets/SESSAO-2026-08-10-ESTORNO-CORE.md` registra o arco completo: implementação por ZCode (Engenheiro) em `states.py` + `dispensacoes.py` + `test_estorno.py` (9 testes) + `test_states.py` (2 emendados) + `CLAUDE.md` (§2/§3/§5a/§5b); auditoria independente do Revisor com **PostgreSQL 15.18 efêmero, 17 testes verdes** (`PARECER-REVISOR-ESTORNO-AUDITORIA-IMPL.md`); martelo do Fabiano: **"Pode mergear."**

**Mas `git log` mostra que isso nunca foi commitado.** O trabalho está solto na árvore:

```
 M backend/app/domain/states.py                  (+26)
 M backend/app/routers/dispensacoes.py           (+147)
 M backend/tests/integration/test_estorno.py     (+312)
 M backend/tests/test_states.py                  (+21)
 M backend/tests/integration/test_custodia_devolucao.py
 M CLAUDE.md  (emendas §2/§3/§5a/§5b da spec)
```

## §4 Tarefa

1. **Verificar identidade do WIP**: confira (via `git diff` e a sessão §2) que as mudanças soltas correspondem exatamente à spec v2 + auditoria. Se algo divergir, registre e pergunte antes de seguir.
2. **Separar as frentes — a árvore mistura pelo menos 3 trabalhos.** NÃO faça commit guarda-chuva. Mapa provável (validar antes de usar):
   - **Frente A (este despacho):** os arquivos do §3 acima.
   - **Frente B (fora de escopo):** `TICKET-DISPENSADOR-ESTORNO-PROMPT-NATIVO.md` (module) e o que for dele.
   - **Frente C (fora de escopo):** `TICKET-EXAME-TRANSFERENCIA-COMO-RECEITA.md` — `backend/app/routers/pedidos_exame.py` (+149), `backend/tests/browser/test_exame_transferencia_cidadao.py`, `backend/tests/integration/test_transferencia_exame_cidadao.py` (ambos untracked).
   - **⚠️ `AGENTS.md` está modificado mas é arquivo CONGELADO** (ver cabeçalho dele): verifique se a alteração pertence à Frente A ou deve ser revertida.
3. **Rodar os gates locais** (venv: `backend/.venv`):
   - `cd backend && ./.venv/bin/python -m pytest tests/integration/test_estorno.py tests/test_states.py tests/integration/test_custodia_devolucao.py -q`
   - `cd backend && ./.venv/bin/python -m pytest tests/browser -q` (o gate que falha na CI — exige playwright; se o ambiente não tiver, documente e cubra com os de integração)
   - Guard-rails: `tests/unit/test_guardrail_identidades_demo.py tests/unit/test_frontend_serving.py`
4. **Commit da Frente A em branch própria** (ex.: `core/estorno-devolve-cidadao`), staging seletivo, mensagem no padrão da casa (`fix(estorno): ...`), referenciando ticket, pareceres e sessão.
5. **PR com classe `core` → revisão central obrigatória** (CLAUDE.md §10). No corpo: linkar spec v2, martelo §3.2, auditoria PG do Revisor e este despacho.
6. **Após merge**: confirmar `gates-browser` verde na `main` e **re-rodar o check no PR #154** (fechamento do loop — o #154 só falhou por herdar o bug da main).

## §5 Restrições (inegociáveis)

- **Não re-implementar do zero.** O trabalho está feito e auditado; sua função é validar, isolar e mergear.
- **Não reverter `TICKET-B0`** além do roteamento martelado (estorno parcial e `erro_dispensacao` continuam retendo na farmácia).
- **Ledger imutável** (CLAUDE.md §2) — nada de UPDATE/DELETE em `*_eventos`.
- **Migração é a única autoridade de schema** (§9) — se o WIP tocar DDL, tem de ser via Alembic.
- **Não commitar WIP de outras frentes** nem arquivos congelados sem confirmação.

## §6 Critérios de aceite

- [ ] `test_coer2_e2e.py` (4 cenários) verde — `/devolver` p/ paciente retorna 200 pós-estorno total
- [ ] `test_coer2_fix.py::test_nao_fresh_motivo_renderiza_na_caixa_de_correcoes` verde
- [ ] `test_f5_b2_ciclo_pos_dispensacao.py::test_b2_escopo_a_reentrada_por_estorno` verde — receita reaparece na fila
- [ ] `tests/browser` inteiro verde na `main` (ou justificativa documentada do que não rodou local)
- [ ] Revisão central registrada (classe `core`) e martelo do Fabiano no merge
- [ ] Check do PR #154 re-rodado e verde
