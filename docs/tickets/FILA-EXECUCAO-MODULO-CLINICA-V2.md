# FILA-EXECUCAO — Módulo Clínica/Laboratório V2

| Campo | Valor |
|---|---|
| **Fila** | Arco V2 — R1/R2/R3/R4 (decidido 2026-08-07) |
| **Base** | `main@3162af9` (verificação in-loco pelo arquiteto) |
| **Visão de referência** | `TICKET-MODULO-CLINICA-V2.md` |
| **Estado da fila** | ⏳ Redigida. Aguardando ratificação do conselheiro + `/login` do Engenheiro. |

---

## Ordem de execução

| # | Despacho | Quem | Classe | Depende de | Esforço | Status |
|---|---|---|---|---|---|---|
| 1 | `DESPACHO-ENG-007` — R1: resultado p/ dispensador | Engenheiro | `module` (enxerto) | — | ~4 linhas + teste | ⏳ Ag. ratificação |
| 2 | `DESPACHO-ENG-008` — R3: relatório de exames | Engenheiro | `module` (router novo) | — | router `/clinicas` + 2 endpoints | ⏳ Ag. ratificação |
| 3 | `DESPACHO-ENG-009` — R4: faturamento (read-only) | Engenheiro | `module` | ENG-008 (mesmo router) | 2 endpoints + projeção ledger | ⏳ Ag. ratificação |
| 4 | `DESPACHO-KIMI3-007` — UI da clínica | Kimi 3 | `local-extension` | **ENG-007 + 008 + 009** (GATE DURO) | `clinica.html` | ⏳ Ag. ratificação |

---

## Caminho crítico / paralelismo

```
ENG-007 ┐
ENG-008 ├── independentes, podem correr em paralelo (após /login do Engenheiro)
ENG-009 ┘  (009 prefere 008 mergeado — mesmo arquivo clinicas.py)
   │
   └──► KIMI3-007 (UI) — GATE DURO: backend V2 mergeado na main
```

- **Gap 1 (ownership por CNPJ): fora da fila** — já existe e está wired
  (`_assert_dispensador_dono_pedido`, `pedidos_exame.py:594-616`).
- **R2 (aviso ao paciente): sem item próprio** — é polling por estado; entra como seção do
  KIMI3-007, sem backend novo.

---

## Próximas ações

1. **Conselheiro:** ratificar (ou vetar) a fila + as 4 decisões cravadas (§ abaixo).
2. **Fabiano:** `/login` no Engenheiro e despachar ENG-007/008/009 (paralelos).
3. **Kimi 3:** aguardar GATE DURO (backend V2 na main) antes de iniciar KIMI3-007.

---

## Decisões cravadas (para ratificação)

1. Faturamento (R4) = **relatório interno read-only**, não guia TISS; sem estado novo, sem escrita
   no ledger, sem dependência de G4A.
2. R2 = **polling por estado**, não push/outbox.
3. Router **`/clinicas` novo** (não misturar clínica/lab em `/dispensadores` = SNGPC/farmácia).
4. Role **`dispensador` = proxy clínica/lab** (sem criar role `prestador` agora).

---

## Fora de escopo (bloqueado / backlog)

- **Guia TISS** — bloqueado por G4A (`CLAUDE.md:731`).
- **Papel `prestador`** distinto de `dispensador`.
- **Seed/normalização TUSS** ampliada.

---

## Registro de divergências resolvidas (auditoria)

| Premissa do briefing inicial | Veredito in-loco |
|---|---|
| "Gap 1 = martelo a construir, caminho crítico" | ❌ FALSA — já existe wired |
| "`/realizar` não existe (R1 = backend novo)" | ❌ FALSA — existe em `agendamentos.py:493` |
| "R3 inexistente + precedentes em `dispensadores.py:452/483`" | ✅ confirmado |
| "R2 sem notificação" | ✅ (nuance: outbox é publicação de eventos, não user-facing) |
| "G4A bloqueia TISS" | ✅ confirmado |

*Fila emitida pelo arquiteto. Não commitada — aguarda ratificação do conselheiro.*
