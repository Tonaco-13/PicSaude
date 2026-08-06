# TICKET-CORE-DIVIDA-GOVERNANCA-4-ACHADOS — Dívida de governança consolidada

| Campo | Valor |
|---|---|
| **ID** | TICKET-CORE-DIVIDA-GOVERNANCA-4-ACHADOS |
| **Classe** | `core` (governança central — documento-fonte do projeto, processo de revisão, contrato de API) |
| **Estado** | 🟡 **REGISTRADO** — aguarda sequenciamento do Fabiano |
| **Origem** | Devolutiva do Engenheiro (Claude Code/terminal) ao DESPACHO-ENG-001, 2026-08-02 |
| **Quem** | Arquiteto (GLM-5.2) ratifica + propõe solução; Revisor central + Fabiano martelam |

> **Contexto:** O Engenheiro, ao receber o `DESPACHO-ENG-001-SEED-EXAMES`, fez uma auditoria de governança em vez de implementar o seed. Os 4 achados são **válidos e importantes** — mas não bloqueiam o seed (que segue `migration/models`, não `AGENTS.md`). Este ticket consolida a dívida e propõe resolução. O seed foi despachado separadamente.

---

## §1 Por que importa agora

O harness do Codex lê `AGENTS.md` automaticamente a cada sessão (é o arquivo de instruções de workspace). Se ele está defasado, **todo agente opera com informação incompleta** — arquiteto, revisor, conselheiro, engenheiro. Não é dívida estética; é dívida que gera decisões erradas em cascata.

---

## §2 Os 4 achados (ratificados pelo arquiteto)

### Achado 1 — `AGENTS.md` defasado (🔴 mais urgente)

**Alegação:** AGENTS.md é a fonte de governança citada em 6+ lugares do projeto, mas está defasado em relação a `CLAUDE.md` (root).

**Verificação do arquiteto (2026-08-02) — CONFIRMADO:**

| Documento | Linhas | Último commit | Estado |
|---|---|---|---|
| `AGENTS.md` | 533 | `9d15a3f` (commit inicial "1.0.0") | **CONGELADO** — nunca atualizado desde o bootstrap |
| `CLAUDE.md` (root) | 731 | `061c78f` (COER-2 closeout) | **VIVO** — evolução contínua |

**Evidências da defasagem:**
- AGENTS.md **não tem** `transferida_prescritor` (0 ocorrências) — CLAUDE.md tem (4 ocorrências, §5a/5b, adicionado no COER-2).
- AGENTS.md **não tem** §2a (R1-R4, regras de ouro do relatório regulatório) — CLAUDE.md tem.
- AGENTS.md **não tem** §9 (migration como autoridade de schema) — CLAUDE.md tem, com commits dedicados.
- AGENTS.md **não cita** CLAUDE.md em nenhum lugar.

**Impacto concreto:** O próprio arquiteto (GLM-5.2), nesta sessão, referenciou "AGENTS.md §5b" e "AGENTS.md §10" em múltiplos documentos de handoff — herdando a defasagem sem saber. Exemplo: o estado `transferida_prescritor` (essencial ao COER-2) não está no contrato que o harness me serve.

### Achado 2 — Fluxo de revisão perdeu o portão contra código real

**Alegação:** O fluxo de tickets (escrito → revisa → implementa) perdeu o mecanismo de validação **pós-implementação contra código real**, não contra o relatório.

**Verificação do arquiteto — VÁLIDO:**

O incidente COER2-POS-MERGE é real: ticket estava correto, defeito só apareceu no código mergeado. O fluxo atual tem o gate **antes** do merge (revisão de spec), mas não tem gate **depois** (revisão contra o código implementado).

**Exemplo documentado:** Os tickets F5-B1/B2/B3 estavam "✅ implementados" (commits 2e7ffda etc.), mas o browser-E2E que validava o comportamento real nunca existiu — foi a dívida que o Kimi 3 acabou de fechar (`test_f5_b1/b2`).

### Achado 3 — Ambiguidades (parcialmente resolvido)

**Alegação:** Dois pontos menores, ambíguos.

**3a. "Claude Code" ambíguo.** Já parcialmente resolvido em `ORGANIZACAO_AGENTES.md` (diferenciei "no app" = revisor vs "no terminal" = engenheiro). **Mas** o fluxo §3 de qualquer handoff precisa deixar explícito: o implementador **não audita a própria mudança** — quem implementa é instância diferente de quem revisa. Falta formalizar isso no processo.

**3b. Apostadoria do Jules.** O Jules apareceu como auditor de PR em arquivos históricos (`docs/extensao/JULES-AUDIT-PR84.md`). Se há papel de auditor externo no processo, precisa estar no `ORGANIZACAO_AGENTES.md` ou ser explicitamente fora de escopo. **Decisão de processo do Fabiano.**

### Achado 4 — `CONTRATO_API.md` (excelente)

**Alegação:** "A fronteira só é fronteira se for diffável." A fronteira entre backend e frontend (declarada em `ORGANIZACAO_AGENTES.md` §2 — "frontend consome o contrato") é **aspiracional** sem um artefato versionado que a materialize.

**Verificação do arquiteto — CONCORDO PLENAMENTE:**

Hoje o "contrato de API" é implícito — está espalhado entre `CLAUDE.md`, comentários em routers, tickets antigos. Não há fonte única. Qualquer mudança de endpoint exige caçar referências em N lugares.

**Proposta:** criar `docs/CONTRATO_API.md` como artefato versionado que lista (mínimo): endpoints ativos (método, rota, auth, payload-resumo), máquinas de estado (referência), e eventos do ledger. Mudanças de API = diff neste arquivo.

---

## §3 Proposta de resolução (do arquiteto)

### 3.1 Achado 1 — `AGENTS.md`

**Duas opções:**

- **(A) Reconciliar** — portar o que falta de CLAUDE.md (§2a, §5a/5b atualizada com `transferida_prescritor`, §9, §10 CLAUDE) para AGENTS.md. Mantém os dois como fontes paralelas.
- **(B) Unificar** — AGENTS.md vira **header tombstone** apontando para CLAUDE.md como fonte única ("este arquivo é obsoleto; a fonte de governança é CLAUDE.md"). O harness lê AGENTS.md → encaminha pra CLAUDE.md.

**Recomendação do arquiteto: (B).** Razão: manter duas fontes paralelas (A) é a mesma dívida que criou o problema — qualquer evolução futura esquece um dos dois. Unificar em CLAUDE.md elimina a bifurcação. O header tombstone já é o padrão que adotei no DDL legado (Q3 do parecer Fable 5).

> ⚠️ **Cuidado:** o harness lê AGENTS.md especificamente (é a convenção do Codex). Se AGENTS.md virar tombstone, preciso confirmar se o harness segue as referências (ex.: `@CLAUDE.md` no header) ou se o tombstone precisa duplicar o essencial. **Validar antes de implementar.**

### 3.2 Achado 2 — Portão pós-implementação

Adicionar ao fluxo de aprovação (ORGANIZACAO_AGENTES §3), depois de "Implementação backend/frontend":

- **Passo 6 (novo): Validação contra código real.** Revisor (Claude Code/app) audita o **código mergeado** contra o ticket — não só a spec. Gate: comportamento descrito no ticket existe no código? Testes que validam o comportamento existem e passam?
- **Passo 7 (novo): E2E de jornada.** Onde aplicável, browser-E2E que simula o fluxo do usuário deve existir e passar — não só testes de API isolados. (Lição COER-2: bugs de posse dupla escaparam de 22 testes PG.)

### 3.3 Achado 3 — Ambiguidades

- **3a:** formalizar no fluxo §3 que implementador ≠ revisor (instâncias diferentes do Claude Code).
- **3b:** decisão do Fabiano sobre apostadoria do Jules.

### 3.4 Achado 4 — `CONTRATO_API.md`

Criar `docs/CONTRATO_API.md` com:
- Lista de endpoints ativos (método, rota, auth exigida, payload-resumo, classe §10).
- Referência às máquinas de estado (`domain/states*.py`).
- Vocabulário de eventos do ledger (consolidado dos vários `states_*.py`).
- Régua de evolução: mudança de API = diff neste arquivo + migration se schema.

**Dono da primeira versão:** arquiteto (eu), após definição do escopo com o Fabiano.

---

## §4 Sequenciamento proposto

| Achado | Urgência | Esforço | Quando |
|---|---|---|---|
| **1 (AGENTS.md)** | Alta — todo agente lê | Médio (reconciliar ou tombstone) | Antes da próxima onda de tickets |
| **4 (CONTRATO_API.md)** | Alta — fronteira central | Médio | Logo após #1 |
| **2 (portão pós-impl)** | Média | Pequeno (texto de processo) | Junto com #1/#4 |
| **3a (Claude Code)** | Baixa — já parcial | Pequeno | Junto com #2 |
| **3b (Jules)** | Decisão de produto | — | Quando Fabiano quiser |

---

## §5 Não bloqueia

- **Seed de exames** (DESPACHO-ENG-001) — segue migration/models, não AGENTS.md. Despachado em paralelo.
- **Mock-sinalizado da clínica** (DESPACHO-KIMI3-004) — frontend puro.
- **Demo de exames** — pode ficar de pé enquanto esta dívida é resolvida.

---

## §6 Coordenadas

| Artefato | Caminho |
|---|---|
| Devolutiva do Engenheiro (origem) | print em 2026-08-02 (transcrito neste ticket) |
| `AGENTS.md` (defasado) | `AGENTS.md` (533 linhas, commit `9d15a3f`) |
| `CLAUDE.md` (vivo) | `CLAUDE.md` (731 linhas, commit `061c78f`) |
| Processo atual | `docs/ORGANIZACAO_AGENTES.md` §3 |
| Fronteira declarada | `docs/ORGANIZACAO_AGENTES.md` §2 |

---

*Ticket `core` registrado pelo arquiteto de backend (GLM-5.2) em 2026-08-02. Ratifica os 4 achados do Engenheiro. Propõe resolução. Aguarda sequenciamento do Fabiano.*
