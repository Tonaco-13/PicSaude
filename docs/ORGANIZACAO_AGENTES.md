# ORGANIZAÇÃO DOS AGENTES — PicSaúde

> **Aviso geral.** Define papéis, responsabilidades e fluxo de coordenação entre
> os agentes que atuam no PicSaúde.
>
> Vigência: 2026-08-06 (refinamento dos papéis pelo dono do produto).
> Redigido pelo arquiteto (ZCode).
> Decisão humana final: dono do produto (Fabiano).

---

## 1. Papéis

> **Princípio da separação mãos × olhos:** só um agente edita código (Engenheiro);
> os demais pensam, redigem ou revisam. Ninguém implementa pelo atalho.

| Agente | Papel | Escopo primário | Não faz |
|---|---|---|---|
| **ZCode (GLM-5.2)** | **Arquiteto** — redige tickets, dono do contrato de API | Define arquitetura; escreve tickets de backend **e** frontend; despacha instruções ao Kimi 3; ratifica PRs | Editar código (não é o Engenheiro) |
| **Claude Code (no app)** | **Revisor** — os olhos do código | Auditoria de cada ticket contra `CLAUDE.md`, invariantes (§5b) e taxonomia (§10). **Revisão consultiva** (opina; não bloqueia o Engenheiro) | Editar código; definir arquitetura sozinho |
| **Kimi 3** | **Frontend** — recebe instrução do Arquiteto | Implementa frontend (`*.html`, UX) a partir dos despachos KIMI3-* do Arquiteto. Consome o contrato de API | Definir/alterar contrato de API; mexer no backend |
| **Claude Code (no terminal Mac Air)** | **Engenheiro** — as mãos, **único que edita código** | Implementa backend + ops + testes a partir de tickets revisados; executa scripts, migrações, testes | Implementar `core` sem revisão central; alterar contrato de API; implementar frontend (papel do Kimi 3) |
| **Claude Fable 5** | **Conselheiro** — para dúvidas do dono do produto | Sanity check de decisões arquiteturais; riscos; trade-offs. **Acionado sob demanda** pelo Fabiano | Implementar código; editar tickets; estar no fluxo de todo ticket |

---

## 2. Fronteira técnica — o contrato de API é a costura

- O **contrato de API** (rotas, payloads, estados, eventos do ledger) é desenhado e mantido pelo **arquiteto de backend (GLM-5.2)**.
- O **frontend (Kime 3) consome** esse contrato; nunca o inventa nem o contorna.
- Qualquer mudança no contrato = mudança de classe **`core`** → exige revisão (Claude Code) + parecer (Fable 5).

---

## 3. Fluxo de trabalho

> **Resumo de uma linha:** ticket → revisão → implementação.

1. **Ticket** → o **Arquiteto (ZCode)** redige (com classe de contribuição §10 e invariantes afetados). Ticket de backend vai ao Engenheiro; ticket de frontend vira despacho KIMI3-* para o Kimi 3.
2. **Revisão** → o **Revisor (Claude Code no app)** audita o ticket contra `CLAUDE.md` / `NUCLEO_SANITARIO`. **A revisão é consultiva**: opina, mas não bloqueia o Engenheiro. **Volta ao Arquiteto somente se destoante do pedido** — apontamentos cosméticos não retornam.
3. **Implementação** → o **Engenheiro (Claude Code no terminal Mac Air)** — único que edita código — implementa a partir do ticket.
4. **Conselheiro (Fable 5)** entra **sob demanda**, quando o Fabiano leva uma dúvida. Não está no fluxo padrão de todo ticket.

> **Mudança vs. versão anterior (2026-08-02):** a revisão deixou de ser gate
> bloqueante e passou a consultiva; o Conselheiro deixou de estar no fluxo de
> toda decisão e passou a sob demanda. Decisão do dono do produto em 2026-08-06.

### 3.1 Timing do parecer do Revisor (adotado 2026-08-09)

A revisão é **consultiva** (não bloqueia), mas o **timing** do martelo importa conforme o
que o PR toca:

- **PR de baixo risco** (`local-extension` de frontend, `docs`, `ops` leve): o martelo pode
  correr **em paralelo** ao parecer do Revisor. Se a auditoria chegar pós-merge e achar
  regressão, vira heads-up pra reverter. Aceitável — o custo de reverter é baixo.
- **PR que toca invariante sensível** (RBAC em `auth/`, ledger `*_eventos`, custódia
  `prescricao_custodia`, máquinas de estados `domain/states*.py`, endpoints `/public/*`):
  **esperar o parecer do Revisor ANTES do merge**, mesmo sendo consultivo. O custo de
  reverter um invariante violado é alto; o Parecer pré-merge é barato.

> **Origem:** alerta do Revisor (Claude-app) no PR #146 — a auditoria entrou pós-merge.
> Como o #146 era `local-extension` de frontend (baixo risco) e não achou regressão, virou
> ratificação retroativa. Mas o princípio fica: invariante sensível espera parecer.

---

## 4. Governança — quem aprova mudança `core`

> **Exceção ao fluxo consultivo:** mudanças `core` têm escrutínio reforçado. A revisão
> consultiva (§3) vale para o fluxo padrão; `core` é o patamar acima.

Mudanças `core` (`CLAUDE.md`, `NUCLEO_SANITARIO.md`, máquinas de estados, ledger, custódia, documento canônico, RBAC, endpoints `/public/*`) exigem:

- **Revisão central:** Revisor (Claude Code, auditoria técnica) **+** Conselheiro (Fable 5, parecer estratégico). Para `core`, **ambos são bloqueantes**.
- **Autoridade final:** dono do produto (Fabiano).

> Regra do projeto (`CLAUDE.md` §10) mantida: nenhuma mudança `core` sem revisão central.

---

## 5. Princípios de convivência

- **Só o Engenheiro edita código.** Os demais pensam (Arquiteto), olham (Revisor) ou opinam (Conselheiro) — nada de implementar pelo atalho.
- Nenhum agente implementa mudança `core` sem revisão central (§4).
- O Kimi 3 só implementa frontend a partir de despacho do Arquiteto — nunca inventa contrato de API.
- Frontend nunca burla endpoints oficiais nem cria estados paralelos.
- Conselheiro aconselha; **não implementa**.
- Toda divergência que toque invariantes (`CLAUDE.md` §5b) volta ao Arquiteto.

### Procedimento de encaminhamento (adotado 2026-08-02)

Todo handoff ou despacho a outro agente é acompanhado de uma **mensagem curta de encaminhamento** — não do documento inteiro. A mensagem aponta o documento-fonte, diz por onde começar e o que já está desbloqueado.

**Exemplos de estilo:**

> *"Leia o despacho KIMI3-001 e o handoff. Comece pelos itens A, B e os testes E2E B1/B2. O item C e a demo sem login já estão desbloqueados com spec."*

> *"Leia o DIAGNÓSTICO-FABLE5-EXAMES-DEMO. Opine sobre as 3 questões do §3 (Q1 papel da clínica, Q2 escopo, Q3 DDL legado). O resto é factual."*

A mensagem é o que o agente destinatário lê primeiro; o documento é a referência profunda.

---

## 6. Resolução do ponto aberto (2026-08-06)

> **Decidido pelo dono do produto.** O ponto que estava em aberto na versão anterior
> ("backend-arquiteto + frontend-arquiteto" vs. "arquiteto-chefe único") fica resolvido:

- **Arquiteto único: ZCode (GLM-5.2).** Redige tickets de backend **e** frontend; despacha instruções ao Kimi 3; é dono do contrato de API.
- **Kimi 3: frontend sob instrução.** Não é "arquiteto de frontend" autônomo — implementa a partir dos despachos KIMI3-* que recebe do Arquiteto.
- A fronteira continua sendo o **contrato de API**: o Arquiteto desenha, o frontend consome.

---

## 7. Reposicionamento de papéis (2026-08-09)

> **Decidido pelo dono do produto.** Expandir a capacidade de implementação do time,
> mantendo o princípio da separação mãos × olhos (§1) e a fronteira do contrato de API (§2).

Mudanças vigentes a partir de 2026-08-09:

- **Kimi 3 passa a engenheiro full-stack.** Deixa de ser exclusivamente frontend: implementa
  **backend** também (a partir dos despachos do Arquiteto, respeitando o contrato de API).
  O §5 ("Kimi 3 só implementa frontend") fica **revogado** nesta parte — Kimi agora edita
  backend + frontend sob instrução do Arquiteto.
- **Claude Code (app) permanece Revisor (sem mudança).** Os olhos do código: audita PRs
  contra `CLAUDE.md`, invariantes (§5b) e taxonomia (§10). Revisão consultiva — opina, não
  bloqueia o implementador. Não edita código (mantém o §1).
- **Claude Code (terminal Mac Air) permanece o commit físico.** Mesmo quando Kimi
  "implementa" a lógica, quem roda `git add`/`pytest`/abre branch é o terminal (ou o
  Fabiano colando o roteiro no Terminal, como o handoff descreve). A física do commit não
  muda — só a autoria da lógica.
- **ZCode (GLM-5.2) permanece Arquiteto único e guardião do `CLAUDE.md`.** Sem mudança.
- **Fable 5 / Conselheiro permanece sob demanda.** Sem mudança.

> **Nota de processo:** esta seção existe para que o próximo handoff **não herde contradição**
> — é a lição dos "36 docs órfãos" aplicada à governança. Toda mudança de papel entra aqui,
> com data e decisão do dono, antes de qualquer despacho sob o novo arranjo.

---

*Documento vivo. Atualizar sempre que houver reposicionamento de papéis.
Última revisão: 2026-08-09 (reposicionamento: Kimi full-stack; Claude-app segue só Revisor; commit físico no terminal).*

