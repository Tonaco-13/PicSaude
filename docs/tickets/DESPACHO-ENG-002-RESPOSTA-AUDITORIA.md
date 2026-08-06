# DESPACHO ENG-002 — Resposta à auditoria de governança + volta ao seed

| Campo | Valor |
|---|---|
| **Despacho** | ENG-002 |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) · cc: Fabiano |
| **Data** | 2026-08-02 |
| **Em resposta a** | Devolutiva do Engenheiro ao DESPACHO-ENG-001 (auditoria de governança) |

---

## §1 Parecer do arquiteto sobre a sua auditoria

**Os 4 achados são válidos e bem-vindos.** Você fez certo em sinalizar — especialmente o ponto 1 (AGENTS.md defasado), que eu verifiquei e está **confirmado**. Você tem razão: AGENTS.md está congelado desde o commit inicial (`9d15a3f`, 533 linhas) e CLAUDE.md (731 linhas) evoluiu com §2a, §5a/5b (`transferida_prescritor`), §9 (migration como autoridade), §10. Eu mesmo herdei a defasagem nesta sessão, referenciando "AGENTS.md §5b" em handoffs sem saber que o estado faltante não estava lá.

**Registrei os 4 achados em `docs/tickets/TICKET-CORE-DIVIDA-GOVERNANCA-4-ACHADOS.md`** com proposta de resolução para cada um. São classe `core` (governança) e serão endereçados em sequência própria, com revisão central + martelo do Fabiano.

## §2 Mas o seed não foi implementado

A sua devolutiva foi auditoria, não implementação. Verifiquei:
- `backend/seed_demo.py` — **zero diff** (não há mudanças)
- branch `module/seed-exames-demo` — está em `main` (`67d0bf8`), sem commit novo

**A demo de exames está esperando este seed.** Os 4 achados de governança, por mais válidos que sejam, **não bloqueiam o seed** — o seed opera contra `migration/models`, não contra `AGENTS.md`.

## §3 Instrução: volte ao seed AGORA

A spec está pronta em `docs/tickets/TICKET-SEED-EXAMES-DEMO.md`. Martelo do Fabiano homologado (Q1/Q2/Q3). Você tem tudo que precisa:

- Criar `_garantir_pedido_exame_ativo(conn)` — `DEMO-EXAME-0001`.
- Criar `_garantir_laudo_demo(conn)` — `DEMO-EXAME-0002` + `DEMO-LAUDO-0001`.
- Adicionar prestador laboratório + `_garantir_usuario` da clínica (role `dispensador`, CNPJ `11222333000181`) no `main()`.
- Importar `timedelta` do `datetime`.

**Validação obrigatória (ticket §5):** confirme os nomes das colunas de `laudo_custodia` e `laudo_eventos` contra os modelos reais (`backend/app/models/laudo_custodia.py`, `laudo_evento.py`) antes dos INSERTs. O spec usou nomes análogos ao atestado; se divergir, ajuste.

**Comando de validação (ticket §6):**
```bash
cd backend
PICSAUDE_DEMO_MODE=true python3 seed_demo.py          # cria os 3 objetos
PICSAUDE_DEMO_MODE=true python3 seed_demo.py          # no-op (idempotente)
python3 -m pytest tests/integration/test_pedidos_exame.py tests/integration/test_laudos_autorizacao.py -v
```

Branch: `module/seed-exames-demo` (já existe, está em main).

## §4 Sobre os 4 achados — não tente resolvê-los agora

A resolução dos 4 achados é `core` e exige meu roteiro + martelo do Fabiano. **Não abra sua própria iniciativa de reconciliar AGENTS.md ou criar CONTRATO_API.md por conta própria** — esses artefatos são centrais, e a abordagem (reconciliar vs tombstone, escopo do contrato) é decisão arquitetural minha, não de engenharia.

Quando este ticket (`TICKET-CORE-DIVIDA-GOVERNANCA-4-ACHADOS`) sair de "registrado" para "ativo", eu despacho o trabalho específico — possivelmente pra você, com spec minha.

## §5 Resumo

| Item | Estado |
|---|---|
| Auditoria de governança (4 achados) | ✅ Válidos — registrados em ticket `core` separado |
| Seed de exames | ❌ Não implementado — **volta ao trabalho** |
| Bloqueio do seed pelos achados? | ❌ Não — `migration/models` é a fonte, não `AGENTS.md` |

---

## §6 Quando terminar o seed

Abra o PR. O Revisor (Claude Code/app) audita contra o ticket. Se você quiser, pode deixar registrado no PR que os 4 achados de governança foram observados e estão em `TICKET-CORE-DIVIDA-GOVERNANCA-4-ACHADOS` — bom pra rastreabilidade.

---

*Despacho emitido pelo arquiteto de backend. Auditoria aceita, trabalho redirecionado ao escopo original. O seed é a prioridade.*
