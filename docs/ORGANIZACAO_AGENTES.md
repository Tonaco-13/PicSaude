# ORGANIZAÇÃO DOS AGENTES — PicSaúde

> **Aviso geral.** Define papéis, responsabilidades e fluxo de coordenação entre
> os agentes que atuam no PicSaúde.
>
> Vigência: 2026-08-02. Redigido pelo arquiteto de backend.
> Decisão humana final: dono do produto.

---

## 1. Papéis

| Agente | Papel | Escopo primário | Não faz |
|---|---|---|---|
| **GLM-5.2 (ZCode)** | Arquiteto de backend + escritor de tickets de backend + **dono do contrato de API** | Domínio, estados, ledger, custódia, RBAC, endpoints FastAPI, guardião do `AGENTS.md`/`NUCLEO_SANITARIO` | Implementar frontend |
| **Claude Fable 5** | Conselheiro estratégico | Sanity check de decisões arquiteturais; riscos; trade-offs; validação contra os princípios | Implementar código ou editar tickets diretamente |
| **Claude Code (no app)** | Revisor de tickets | Auditoria de cada ticket contra `AGENTS.md`, invariantes (§5b) e taxonomia de contribuição (§10) **antes** da implementação | Definir arquitetura sozinho; implementar |
| **Claude Code (no terminal)** | Engenheiro / Implementador backend | Implementa o código backend após revisão aprovada; executa scripts, migrações, testes. Atua em classes `module`/`adapter`/`local-extension`/`ops` | Implementar mudança `core` sem revisão central aprovada; alterar o contrato de API; mexer no frontend |
| **Kime 3** | Arquiteto de frontend + programador | `prescritor.html`, `dispensador.html`, UX, consumo do contrato de API | Definir/alterar o contrato de API; mexer no backend |

---

## 2. Fronteira técnica — o contrato de API é a costura

- O **contrato de API** (rotas, payloads, estados, eventos do ledger) é desenhado e mantido pelo **arquiteto de backend (GLM-5.2)**.
- O **frontend (Kime 3) consome** esse contrato; nunca o inventa nem o contorna.
- Qualquer mudança no contrato = mudança de classe **`core`** → exige revisão (Claude Code) + parecer (Fable 5).

---

## 3. Fluxo de trabalho

1. **Decisão arquitetural** → GLM-5.2 propõe; **Fable 5** opina (sanity check).
2. **Ticket de backend** → GLM-5.2 redige (com classe de contribuição §10 e invariantes afetados).
3. **Revisão** → **Claude Code (no app)** audita o ticket contra `AGENTS.md` / `NUCLEO_SANITARIO`. *Gate bloqueante*: não implementa sem passar.
4. **Implementação backend** → **Claude Code (no terminal)**, a partir do ticket revisado.
5. **Implementação frontend** → **Kime 3**, consumindo a API já revisada e implementada.
6. **Integração** → confere contrato × consumo.

---

## 4. Governança — quem aprova mudança `core`

Mudanças `core` (AGENTS.md, máquinas de estados, ledger, custódia, documento canônico, RBAC, endpoints `/public/*`) exigem:

- **Revisão central:** Claude Code (auditoria técnica) **+** Fable 5 (parecer estratégico).
- **Autoridade final:** dono do produto (humano).

> Regra do projeto (AGENTS.md §10) mantida: nenhuma mudança `core` sem revisão central.

---

## 5. Princípios de convivência

- Nenhum agente implementa mudança `core` sem revisão.
- Frontend nunca burla endpoints oficiais nem cria estados paralelos.
- Conselheiro aconselha; **não implementa**.
- Toda divergência que toque invariantes (AGENTS.md §5b) volta ao arquiteto de backend.

### Procedimento de encaminhamento (adotado 2026-08-02)

Todo handoff ou despacho a outro agente é acompanhado de uma **mensagem curta de encaminhamento** — não do documento inteiro. A mensagem aponta o documento-fonte, diz por onde começar e o que já está desbloqueado.

**Exemplos de estilo:**

> *"Leia o despacho KIMI3-001 e o handoff. Comece pelos itens A, B e os testes E2E B1/B2. O item C e a demo sem login já estão desbloqueados com spec."*

> *"Leia o DIAGNÓSTICO-FABLE5-EXAMES-DEMO. Opine sobre as 3 questões do §3 (Q1 papel da clínica, Q2 escopo, Q3 DDL legado). O resto é factual."*

A mensagem é o que o agente destinatário lê primeiro; o documento é a referência profunda.

---

## 6. Ponto a confirmar (recomendação do arquiteto)

- **Escopo de "arquiteto":** proponho **backend-arquiteto** (GLM-5.2, +dono do contrato de API) e **frontend-arquiteto** (Kime 3), com a API como fronteira.
  *Alternativa:* arquiteto-chefe único (GLM-5.2) com Kime 3 como lead de frontend.

---

*Documento vivo. Atualizar sempre que houver reposicionamento de papéis.*
