# TICKET-REVIEW-RATIFICACAO-PR129-134 — Ratificação do arquiteto aos 6 PRs

| Campo | Valor |
|---|---|
| **ID** | TICKET-REVIEW-RATIFICACAO-PR129-134 |
| **Classe** | `module` (documentação de governança — não afeta produção) |
| **Estado** | 🟢 **RATIFICADO** (arquiteto, 2026-08-04) |
| **De** | Arquiteto (GLM-5.2) |
| **Origem** | Review do Revisor (Claude Code) emitida em 2026-08-04 contra §5b (invariantes) + §10 (taxonomia) da constituição viva (`CLAUDE.md`, 23/jul) |
| **Método** | Verificação independente — leitura dos diffs reais, não rubber-stamp do parecer do Revisor |

---

## §1 Escopo auditado

6 PRs abertos, todos CI verde, todos `mergeable=MERGEABLE`:

| PR | Branch | Classe declarada | Título |
|---|---|---|---|
| #129 | `module/f5-b1-b2-browser-e2e` | `module` | test(f5): browser-E2E B1 (botões relatório) + B2 (ciclo pós-dispensação) |
| #130 | `local-extension/demo-ux-logo-a11y-autologin` | `local-extension` | feat(demo-ux): logo clicável + a11y de obrigatórios + auto-login demo |
| #131 | `module/seed-exames-demo` | `module` | feat(demo): seed de exames + laudo + persona clínica no /demo/login |
| #132 | `local-extension/persona-clinica-portal` | `local-extension` | feat(portal): persona clínica no seletor demo |
| #133 | `module/f5-c3-cidadao` | `module` | F5-C1/C2/C3 — UX do cidadão |
| #134 | `ops/infra-teste-externo` | `ops` | Infra de teste externo (F5-B5) — marker `external` + fixtures |

## §2 Matriz de vereditos (Revisor + ratificação arquiteto)

| PR | Revisor | Arquiteto (ratificação) | Bloqueios |
|---|---|---|---|
| **#129** | ✅ Aprovado | ✅ **Ratificado** | — |
| **#131** | ✅ Aprovado (1 obs.) | ✅ **Ratificado** (2 acréscimos) | — |
| **#132** | ✅ Aprovado (ordem) | ✅ **Ratificado** | Depende do **#131** (persona `clinica`) |
| **#133** | ✅ Aprovado | ✅ **Ratificado** | — |
| **#134** | ✅ Aprovado | ✅ **Ratificado** | — |
| **#130** | 🔴 Mudanças solicitadas | 🔴 **Ratificado bloqueio** | Rebase + remoção do seed órfão (ver §4) |

## §3 Achados confirmados no código real (não descrições)

### #131 — pontos de backend (verificação independente)

**Sem ciclo de import** ✓ — confirmado:
- `backend/app/routers/demo.py` importa de `app.config` e `app.auth.jwt` (módulos folha).
- `backend/app/routers/config_publico.py:33` importa `_papeis_demo_disponiveis` de `demo.py`.
- A seta é **mão única** (`config_publico → demo`); não há `demo → config_publico`.

**Elo de origem do DEMO-EXAME-0002 presente** ✓ — confirmado (`seed_demo.py:514`):
```python
INSERT INTO pedido_exame_custodia (..., de='prescritor', para='paciente', motivo='emissao')
```
A cadeia de custódia é completa: `prescritor → paciente → laboratório` (pedido) e `laboratório → paciente` (laudo).

**Sem role RBAC nova** ✓ — a persona `clinica` anda no plumbing do `/demo/login` (payload.role), não em `require_role`. O role `core` está explicitamente deferido (`demo.py:69`, `TICKET-CORE-ROLE-PRESTADOR-EXAME`).

### #130 — o 🔴 confirmado por contagem de INSERTs de custódia

Em `_garantir_laudo_demo` (linha 445+ de `backend/seed_demo.py`):

| Branch | `pedido_exame_custodia` (linhas na função) | `laudo_custodia` | Ledger inclui `prescritor→paciente`? |
|---|---|---|---|
| **#131** | `prescritor→paciente` + `paciente→laboratório` (2) | `prestador→paciente` (1) | ✅ sim |
| **#130** | só `paciente→laboratório` (1) | `prestador→paciente` (1) | ❌ omite |

O delta é exatamente **uma linha**: o elo de origem `pedido_exame_custodia (de='prescritor', para='paciente')`. Sem ele, o `DEMO-EXAME-0002` nasce com proveniência iniciando mid-stream — o objeto é **órfão** conforme §2/§3 (CLAUDE.md).

**Causa-raiz (acréscimo do Conselheiro):** o #130 é um PR de **frontend** (Kimi 3) carregando funções de seed de **backend**. As duas branches implementaram o mesmo seed independentemente a partir de `main` (que não tem o seed) — a versão do #130 é **pré-errata** (não contém `ec2708c`, que adicionou o elo de origem). **Regra de fronteira** registrada em §6.

### #134 — guarda de CI

`-m "not external"` no `pytest.ini` **não desseleciona** nenhum teste de `tests/unit` (nenhum é marcado `external`). Os marcados `external` vivem só em `test_f5_externo_picsaude.py`. Marker registrado. **Guarda correta**: o gate de CI não escreve na vitrine.

### #129, #133 — consumo de contrato

Ambos apenas consomem endpoints existentes; nenhum introduz endpoint novo ou contorna contrato. A mudança do #133 em `test_smokes.py` **fortalece** a asserção (escopa ao protocolo, rejeita `.first`).

## §4 Bloqueio do #130 (detalhe operacional)

**Por que a colisão do seed será conflito visível, não override silencioso:** `main` não tem o seed; ambas as branches (#130 e #131) adicionam os mesmos 3 protocolos sentinela em linhas sobrepostas. O rebase do #130 sobre `main + #131` produzirá **conflito git explícito** na função `_garantir_laudo_demo` — isso é desejável (força reconciliação, não deixa o órfão passar).

**Prescrição de rebase** — formalizada em `DESPACHO-ENG-006`.

## §5 Ordem de merge ratificada (martelada pelo Fabiano, 2026-08-04)

```
1. #131  → canonicaliza o seed (com elo) + wired da persona clinica    [PRIMEIRO]
2. #132  → consome /demo/login + /config/public                         [dependência bloqueante do #131]
3. #129, #133, #134 → livres, qualquer ordem (independentes entre si)
4. #130  → 🔴 BLOQUEADO até rebase sobre main + (#131 + #132)
```

## §6 Dois acréscimos ao parecer do Revisor (observações do arquiteto)

1. **#131 — acoplamento de import privado (não-bloqueante).** `config_publico.py:33` importa `_papeis_demo_disponiveis` — função com underscore (`_`-privada) — atravessando módulo de router. A consolidação é **justificada e documentada** (corrige uma deriva real da lista `demo_roles` entre `/config/public` e `/demo/login`), mas é um cheiro de design leve. Registrado como dívida técnica: `DIVIDA-DESIGN-DEMO-PUB-IMPORT-PRIVADO` (a criar quando a dívida for Prioridade ≥ M).

2. **#130 — regra de fronteira permanente (acréscimo do Conselheiro).** PR de frontend (Kimi 3) **não deve carregar funções de seed de backend**. A causa-raiz do órfão é a violação de fronteira, não um esquecimento pontual. **Regra:** `backend/seed_demo.py` (e qualquer arquivo sob `backend/`) nunca viaja em PR de `local-extension` cujo escopo seja UI. Inclusa como regra permanente em `DESPACHO-ENG-006 §6` e no handoff do Kimi 3.

## §7 Não fazer

- Não mergear #130 antes de #131 + #132 (reintroduz o órfão §3).
- Não usar o seed do #130 como base — o canônico é o do #131 (com elo).
- Não fazer reset da demo DB antes do #131 estar em `main` (ver `DESPACHO-OPS-001`).

## §8 Coordenadas

| Artefato | Caminho |
|---|---|
| Constituição viva | `CLAUDE.md` (§2, §3, §5a/§5b, §7, §10) |
| Despacho de rebase do #130 | `docs/tickets/DESPACHO-ENG-006-REBASE-PR130.md` |
| Reset da demo DB (pós-merge) | `docs/tickets/DESPACHO-OPS-001-RESET-DEMO-DB.md` |
| Bot de Revisor (futuro) | `docs/tickets/TICKET-GOV-BOT-REVISOR.md` |
| Review original do Revisor | comentário de review no PR (corpo com veredito) |

---

*Ratificação emitida pelo arquiteto contra código real. Martelo do Fabiano recebido: Q1=(b) disciplina; Q2 reset pós-#131.*
