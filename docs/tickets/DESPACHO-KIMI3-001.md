# DESPACHO KIMI3-001 — Handoff frontend da demo para o Kimi 3

| Campo | Valor |
|---|---|
| **Despacho** | KIMI3-001 |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Kimi 3 (arquiteto frontend) · Com cc: Revisor (Claude Code/app) · Conselheiro (Fable 5) · Fabiano (martelo) |
| **Data** | 2026-08-02 |
| **Documento-fonte** | `docs/tickets/HANDOFF-FRONTEND-KIMI3.md` |
| **Estado** | 🟢 **DESPACHADO — Kimi 3 pode iniciar** |

---

## §1 Resumo executivo pra quem só lê isto

O Kimi 3 recebe o **frontend da demo do PicSaúde**. A missão principal é **fechar os testes browser-E2E** que faltam (B1/B2); os achados de UX do extensionista (logo, acessibilidade, renovação) e a decisão "demo sem login" vieram como **escopo adicional, já triado**. Há **decisões ratificadas** que desbloqueiam tudo.

---

## §2 Decisões ratificadas (leia antes de começar)

1. **Portal mantém o seletor de personas (1 clique).** A decisão "demo sem login" **não elimina** o seletor do `index.html`. O usuário escolhe o papel com 1 clique — sem digitar senha. Decisão do Fabiano com parecer verde do Conselheiro (2026-08-02).

2. **Item C (renovação pré-preenche paciente) → opção (c): cache no `localStorage` por CPF.** Registrada como **dívida técnica core** (persistência real virá depois). Decisão do Fabiano com parecer verde do Conselheiro (2026-08-02). **Kimi 3 já pode implementar C** — spec técnica está no §10.C do handoff.

3. **RBAC/auth não é tocado.** "Demo sem login" é **frontend puro** — replicar o `_autoLoginDemo` do dispensador em prescritor/cidadao. **Proibido** bypassar `require_role` em DEMO_MODE (seria `core`, abriria superfície de segurança).

---

## §3 O que o Kimi 3 PODE começar AGORA (sem blocker)

| # | Item | Classe | Doc | Esforço |
|---|---|---|---|---|
| **1** | Testes browser-E2E B1 + B2 (F5) | `module` | handoff §3 | Médio (principal) |
| **2** | Logo → voltar ao portal | `local-extension` | handoff §10.A | Pequeno |
| **3** | Acessibilidade: `aria-required` + cor do asterisco + feedback erro | `local-extension` | handoff §10.B | Pequeno-Médio |
| **4** | Demo sem login: `_autoLoginDemo` em prescritor/cidadao | `local-extension` | handoff §11 | Médio |
| **5** | Renovação: cache de paciente por CPF no `localStorage` | `local-extension` | handoff §10.C | Médio |

**Ordem sugerida:** 1 (principal) → 2 + 3 (rápidas e independentes) → 4 (portal já decidido) → 5 (spec do backend pronta).

---

## §4 O que NÃO é do Kimi 3 (fronteira)

- **Backend de renovação (endpoint, persistência real de paciente):** `core` — é meu. Dívida registrada em `docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md`.
- **Persona demo pra `clinica.html`:** se o Fabiano quiser, eu adiciono em `_PERSONAS` (`demo.py:39`).
- **Bypass de `require_role`:** proibido (§11 do handoff).
- **Endpoints novos:** o contrato de API é meu.

---

## §5 Fluxo de aprovação (regra do ORGANIZAÇÃO_AGENTES)

1. Kimi 3 implementa → roda local verde.
2. Abre PR com branch `module/...` ou `local-extension/...`.
3. **Claude Code (app)** revisa contra os tickets-fonte (gate bloqueante).
4. **Claude Fable 5** dá parecer.
5. Arquiteto (eu) ratifica.
6. Martelo do Fabiano + merge.

---

## §6 Quando acionar o arquiteto (sem hesitar)

- Divergência entre ticket e comportamento real do backend.
- Bug que suspeite ser de backend (B0, comprovante, estorno, renovação).
- Tentação de "afrouxar" seletor/asserção pra teste passar.
- `conftest.py` não der helper que você precisa (pode ser gap de infra).

---

## §7 Registro de mãos (checklist de transferência)

| Artefato | Caminho | Lido? |
|---|---|---|
| Handoff completo | `docs/tickets/HANDOFF-FRONTEND-KIMI3.md` | ⏳ (Kimi 3) |
| Organização dos agentes | `docs/ORGANIZACAO_AGENTES.md` | ⏳ (Kimi 3) |
| AGENTS.md (princípios) | `AGENTS.md` | ⏳ (Kimi 3) |
| Ticket B1 | `docs/tickets/TICKET-F5-B1-RELATORIO-BOTOES.md` | ⏳ (Kimi 3) |
| Ticket B2 | `docs/tickets/TICKET-F5-B2-CICLO-POS-DISPENSACAO.md` | ⏳ (Kimi 3) |
| Dívida core (renovação) | `docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md` | ⏳ (Kimi 3) — contexto, não trabalho |

---

*Despacho emitido pelo arquiteto de backend. Dúvida de contrato de API = comigo. Dúvida de padrão de teste = com o revisor (Claude Code/app). Decisão de produto = Fabiano.*
