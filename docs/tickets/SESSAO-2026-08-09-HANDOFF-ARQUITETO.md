# HANDOFF — Arquiteto (ZCode) para a sessão de 2026-08-10

> **Lê primeiro ao retomar.** Sessão de 09/08 (domingo) foi densa e corrigiu 3 diagnósticos
> defasados de terceiros. Este arquivo captura o que está **verificado** (não re-verificar) e
> a **fila**. Cota Lite — ser econômico em reconferência longa.
>
> **Dono do produto:** Fabiano (martelo final). **Eu:** arquiteto, guardião do `CLAUDE.md`.

---

## 1. Papel vigente (registrado em `docs/ORGANIZACAO_AGENTES.md §7`)

| Agente | Papel |
|---|---|
| **ZCode (eu, Lite)** | Arquiteto único + verificação in-loco + despachos. **Não** implemento. |
| Kimi 3 | **Full-stack** (frontend + backend) — mudou de 09/08 |
| Claude-app | **Só Revisor** (não implementa — reverteu) |
| Claude Code terminal | Commit físico (git/pytest/branch) |
| Opus (Fable 5) | Conselheiro sob demanda |

---

## 2. Estado verificado (commit `3ecb00e` = #146 mergeado; vitrine saudável)

**NÃO re-verificar amanhã — já provado in-loco:**

- ✅ **Vitrine 100% verde desde 04/08** — 11 deploys, zero `failed`. O "não sai do cidadão" era
  **DB local desatualizado**, NÃO bug. Vitrine: cidadão agenda com `201` (`POST /agendamentos`
  aceita `paciente`, `agendamentos.py:292`).
- ✅ **Arco V2 (clínica/lab) FECHADO em produção** — backend R1/R3/R4 (#141/#142/#145) +
  UI do Kimi (#146, deployado 09/08 15:42 BRT). Mock-tags removidos; `/clinicas/relatorio.*`,
  `/clinicas/faturamento.*`, botão "Registrar resultado" no ar.
- ✅ **G4A ~90% construído, NÃO greenfield.** `registrar_outbox` (`outbox.py:27`), `GET/POST
  /eventos` (`eventos.py:41/143`), auth G4B parcial (`dependencies.py:154`), `outbox_ativo:true`
  na vitrine. **1 gap real:** `custodia_transferida` (`custodia.py:171`) só vai ao ledger, nunca
  ao outbox. (v2 do ticket G4A tinha 2 falsos gaps — agendamento/laudo — corrigidos na v3.)
- ✅ **Catálogo DCB ativo** desde 07/08 (#137/#138) — o levantamento do Claude Pro que dizia
  "🔴 vazio, nada chama o seeder" estava **ERRADO**. Seeder em `seed_demo.py:137`. 56 substâncias.
- ✅ **Levantamento do Claude Pro (09/08):** 8/9 pontos corretos. Contagens confirmadas:
  medicamentos 5.656, CID-10 14.241, semáforo 109 pares/9 CIDs (I10=61,E11=26), determinístico
  sem LLM (`semaforo_decisao.py:14`), 🔴 vermelho = Fase 2.
- ⚠️ **Reset diário NÃO existe como automação** — handoff dizia "reset 12:00Z", mas o Render
  não tem cron job; só `predeploy.sh` roda no deploy. Vitrine acumula estado entre deploys.
  **Issue #124 confirmada como dívida real.**

---

## 3. A fila (priorizada por Fabiano)

| # | Tarefa | Classe | Quem |
|---|---|---|---|
| 0 | **Commitar meus docs órfãos** (G4A ticket v3 + ORGANIZACAO §7 + DESPACHO-KIMI3-007 revalidado) — regra "zero docs órfãos" | docs | terminal (git add por arquivo) |
| 1 | **Reset DB local** — `rm data/pix_saude_demo.db` + `cd backend && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py` | ops | Fabiano/terminal |
| 2 | **Parecer Opus sobre G4A** — encaminhamento já redigido (ver §5 abaixo) | consulta | Opus (Fabiano cola) |
| 3 | **Reset automático demo** (issue #124) — cron/job do reset_demo_db.py no Render | ops | arquiteto desenha + Fabiano executa |
| 4 | **Semáforo: 3-4 CIDs rasos → exaustivos** (J45/F32/N39.0) — curadoria clínica | ops/curadoria | Fabiano (validado_por) + Claude Pro (RENAME) |
| 5 | **G4A-cobertura** (custódia) → depois adapter TISS | module→adapter | Kimi (pós-parecer Opus) |

---

## 3a. PRÓXIMA FRENTE — Motores da prescrição (decidido por Fabiano na noite de 09/08)

> **Amanhã (10/08) começa por aqui.** Diagnóstico dos 5 motores — radiografia honesta do que
> está pronto vs. o que falta, **antes** de qualquer ticket.

| Peça | Estado verificado (09/08) | A diagnosticar amanhã |
|---|---|---|
| **Preenchimento de CID** | ✅ base completa 14.241 códigos (`cid10.csv`, `/ia/cid/buscar`) | UX do preenchimento |
| **Medicamentos + dose + apresentação comercial** | ✅ 5.655 ativos + 25.392 apresentações (`def` + `cmed`) | UX do autocomplete |
| **Posologia** | 🟡 só 11 linhas (`posologia_sugerida.csv`) | Quanto expandir |
| **Motor regulatório RDC 1.000** | ⚠️ **metade** — catálogo DCB ativo (56 substâncias, #137); classificação de controle (B1/B2/C1/C2/D1) precisa confirmar alcance | Até onde chega a classificação |
| **Motor de redundância clínica (semáforo)** | ✅ funciona, determinístico, sem LLM, não-bloqueante; 🟢/🟡 vivo | Confirmar "sem bloquear" + anti-fadiga |

### Invariante de produto (decisão Fabiano, não reabrir)

> **CID e hipótese clínica são SEMPRE opcionais.** O campo nunca vira obrigatório, mesmo que o
> semáforo o use como entrada. Verificar no diagnóstico se isto já é verdade hoje.

### Decisão sobre o 🔴 vermelho (muda o escopo)

**Fabiano decidiu: trazer o 🔴 vermelho pra perto** (sair de "Fase 2" e entrar no diagnóstico).
Custo de arquiteto registrado: o vermelho de contraindicação **exige fonte** (mesmo padrão do
verde/amarelo — `fonte` + `validado_por` em `decisao_semaforo.csv`). Não dá pra fazer "vermelho
achismo". **Na prática = curadoria clínica de contraindicações**, trabalho do Fabiano
(validado_por). O diagnóstico de amanhã precisa medir **quanto dado de contraindicação já
existe** vs. quanto falta.

---

## 4. Pendências / dívidas conhecidas (do handoff Fable 5)

- 2 testes vermelhos pré-existentes: `test_4d2_instance_id_ledger`, `test_regras_receituario`
  (não bloqueiam; G4A/KIMI3 não os tocam).
- TUSS raso (38 inline) → top-100 ANS (pós-MvP).
- Posologia (11) → pós-MvP.
- 🔴 vermelho do semáforo = Fase 2/core.

---

## 5. Encaminhamentos já redigidos (só colar quando retomar)

- **Para Opus (parecer G4A):** cole o corpo de `docs/tickets/TICKET-G4A-COBERTURA-E-TISS.md`
  (v3). Pontos a opinar: (1) gap é só custódia? (2) classe `adapter` pro TISS? (3)
  sequenciamento ENG-010→ENG-011?
- **PR #146:** MERGEADO por Fabiano às 18:41Z. Auditado por mim (diff + smoke pós-deploy
  verde). Revisor consultivo foi bypassado pelo martelo — função ok, registrar só.

---

## 6. Working tree (NÃO commitar junto do meu)

**Meus (a commitar — ver fila #0):**
- `docs/tickets/TICKET-G4A-COBERTURA-E-TISS.md` (v3)
- `docs/ORGANIZACAO_AGENTES.md` (§7 — Kimi full-stack, Claude-app Revisor)
- `docs/tickets/DESPACHO-KIMI3-007.md` (revalidado, já referenciado no #146)

**Alheio (NÃO tocar — `git add` por arquivo, nunca `-A`):**
- `AGENTS.md`, `docs/picsaude_ddl_postgres_v1.sql`, `docs/tickets/TICKET-F5-FATIA-B-...` (modificados)
- Untracked: `SESSAO-2026-08-06-ENTREGAS-ENGENHEIRO.md`, `TICKET-CANON-ATIVO-DOSE-SUFFIX.md`,
  `VAGAO-CURADORIA-SEMAFORO.md`, `inbox/`, `.zcode/`, `docs/RELATORIO-DEMO-2026-08-05.md`

---

## 7. Lição de processo desta sessão (eco do V2 §1.1)

Três diagnósticos defasados (despacho 25/07, levantamento do Claude, teste do Fabiano) —
**todos baseados em estado desatualizado**. Regime de prova: verificar in-loco contra a main
atual ANTES de planejar. Âncora `file:line` envelhece; heurística de grep curta engana (errei
2 falsos gaps no G4A v2). **O processo pegou cada erro — inclusive os meus.** Manter assim.

---

*Handoff emitido pelo arquiteto (ZCode), 2026-08-09 à noite. Retoma 10/08 pela manhã.*
