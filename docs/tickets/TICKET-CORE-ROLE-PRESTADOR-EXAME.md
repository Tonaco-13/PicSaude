# TICKET-CORE-ROLE-PRESTADOR-EXAME — Introduzir role `prestador_exame` (sai da sobrecarga de `dispensador`)

| Campo | Valor |
|---|---|
| **ID** | TICKET-CORE-ROLE-PRESTADOR-EXAME |
| **Classe** | `core` (toca RBAC — território central, exige revisão central obrigatória) |
| **Estado** | 🟡 **AGENDADO** — condição de saída da Q1 (parecer Fable 5, ratificado 2026-08-02) |
| ** Gatilho duro** | Nenhum prestador real onboarda antes desta role existir |
| **Para** | Arquiteto (spec) → Revisor central → Conselheiro → Fabiano (martelo) |
| **Origem** | Parecer Fable 5 Q1 (DESPACHO 2026-08-02): "a role `prestador_exame` entra como ticket `core` agendado para logo após a demo de exames ficar de pé" |

---

## §1 Contexto (decisão de duas fases)

**Fase atual (demo):** a clínica loga como `dispensador` (role compartilhada), separada por CNPJ próprio (`11222333000181` — constante `CLINICA`). Decisão Q1=(a), ratificada. Aceitável porque o banco demo é resetável e não há dado real a migrar.

**Fase seguinte (este ticket):** introduzir a role `prestador_exame`, já nomeada em AGENTS.md §7 ("Custódia: prescritor → paciente → prestador_exame → paciente"). A clínica passa a logar com sua role semântica correta.

> **Por que `core`:** RBAC é território central (AGENTS.md §10 — "RBAC e autenticação (`auth/`)"). Qualquer mudança de role exige revisão central obrigatória. Não pode ser `local-extension`.

---

## §2 Por que não adiar indefinidamente

O Fable 5 estabeleceu **gatilho duro**: nenhum prestador real onboarda antes da role existir. Ou seja:

- **Demo/piloto interno:** `dispensador` reusado serve. Ledger registra ações de lab sob role `dispensador` — aceitável em ambiente controlado.
- **Piloto real com laboratório externo:** esta role é pré-requisito. Sem ela, o ledger mistura ações de farmácia e laboratório sob o mesmo rótulo — inaceitável para auditoria sanitária real.

O custo de adiar é ~zero enquanto só há dado resetável. Cresce no momento em que existe dado de produção — exatamente o gatilho.

---

## §3 Escopo técnico (a detalhar quando o ticket for ativado)

Quando este ticket sair de "agendado" para "ativo", o spec completo cobre:

1. **`auth/` (RBAC):**
   - Adicionar `prestador_exame` ao conjunto de roles válidas.
   - Ajustar `require_role(...)` nos endpoints de exame/laudo/agendamento que hoje aceitam `dispensador` para também aceitar `prestador_exame` (ou substituir, dependendo da decisão).
   - Migrar a persona demo da clínica de `dispensador` → `prestador_exame` em `demo.py` `_PERSONAS`.

2. **`clinica.html` (frontend):**
   - Ajustar gate de role (`clinica.html:881` hoje só aceita `dispensador`/`admin`) para aceitar `prestador_exame`.

3. **Seed (`seed_demo.py`):**
   - `_garantir_usuario` da clínica passa a usar role `prestador_exame`.

4. **Ledger / auditoria:**
   - Eventos de laboratório passam a registrar `ator_tipo='prestador_exame'` em vez de `'dispensador'`.
   - Decisão: retroativo (migrar eventos demo existentes) ou só a partir da ativação? (Provável: só a partir — demo é resetável.)

5. **Documentação:**
   - Atualizar AGENTS.md §7 se necessário (a role já está nomeada lá).
   - `docs/ARQUITETURA_EXAMES.md` confirma a custódia `prestador_exame`.

---

## §4 Invariantes a preservar (quando ativado)

- **Matriz de ownership (5C):** a nova role precisa encaixar na matriz prescritor/paciente/dispensador sem abrir buraco de autorização. Os testes `test_pedidos_exame_autorizacao.py` (21 testes) e `test_laudos_autorizacao.py` (16 testes) são o gate.
- **Ledger imutável:** adicionar role não muta eventos passados (decisão §3.4 — só a partir da ativação).
- **Guardrail de boot (`main.py:94-122`):** nenhuma implicação direta, mas confirmar.

---

## §5 Dependências e coordenadas

| Artefato | Relação |
|---|---|
| Parecer Fable 5 Q1 | Origem da condição |
| `TICKET-SEED-EXAMES-DEMO` | Fase atual (demo com `dispensador` reusado) |
| `demo.py:39` (`_PERSONAS`) | Migrar persona clínica quando este ticket ativar |
| `clinica.html:881` | Gate de role a ajustar |
| AGENTS.md §7 | Role já nomeada na arquitetura |
| `TICKET-GAP-1-UI-LAUDO-CLINICA` §3 | Decisão Opção B (antecipar esta role) é alternativa ao estender `dispensador` |

### ⚠️ Observação de segurança (Fable 5, parecer PR #131/#132 §5)

Com role compartilhada e chaves de sessionStorage comuns (`picsaude_demo_*`), **um token demo da clínica é aceito por `dispensador.html`** se navegado na mesma aba (e vice-versa: token da Farmácia Norte na clínica). Padrão pré-existente (vale igualmente para a Farmácia Norte desde o T0.5), consequência conhecida da Q1=(a) — role compartilhada significa aceitação cruzada entre módulos que esperam essa role.

**Comportamento residual aceito** na fase demo: o sessionStorage é efêmero (por aba), e a separação por estabelecimento (CNPJ no `sub`) blinda a nível de dado (ownership valida `sub`). **Morre quando `prestador_exame` entrar** — cada role terá seu escopo de gates, e a aceitação cruzada desaparece. Registrar este item como resolvido no momento da ativação do ticket.

---

## §6 Não fazer (enquanto agendado)

- Não implementar antes do gatilho (piloto real).
- Não introduzir a role parcialmente sem cobrir toda a matriz de ownership.
- Não migrar eventos passados do ledger (imutabilidade).

---

*Ticket `core` agendado pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Condição de saída da Q1 (parecer Fable 5 ratificado). Ativa quando o piloto real com laboratório externo for autorizado.*
