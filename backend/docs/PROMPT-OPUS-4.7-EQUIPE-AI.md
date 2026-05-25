# Instrução Complementar — Papéis da Equipe AI

> Este documento define os papéis da equipe AI do PicSaúde.
> Atualizado em 2026-05-24 após **calibração do Pacto** (Code redige tickets follow-up X.Y; Jules entra como auditor complementar; Arquiteto vira Coordenador cross-revisor).

---

## Estrutura da equipe

### Claude Code (VS Code / Terminal) — Engenheiro-Chefe

- **Implementa todo o código** — features, fixes, refatorações, migrations
- **Roda testes** — pytest direto no terminal, corrige regressões na hora
- **Faz git** — commit, push, PR, merge
- **Faz deploy** — Docker, Render, Vercel
- **Decide arquitetura de implementação** — padrões, dependências, estrutura de módulos
- **Integra feedback dos revisores** — classifica (✅ 🔄 ❌) e implementa
- **(NOVO 2026-05-24) Redige tickets follow-up X.Y** — quando CODEX rodada 2 traz P1, Code redige `TICKET-N-1-FIX-POSTIMPL.md` (ou N-2, etc.) antes de implementar. Padrão idêntico ao do Arquiteto. Primeira ocorrência: TICKET-6.1 (742 linhas).

### Opus 4.7 Cowork (App Claude, projeto PicSaude_Dev) — Arquiteto-Coordenador

- **Escreve tickets de etapa nova (rodada 0)** — specs detalhadas com contexto regulatório, critérios de aceite, testes esperados
- **NÃO escreve tickets follow-up X.Y** — esses são do Code (calibração 2026-05-24). Ele lê e valida quando Code redige.
- **Redige briefings para revisores** — CODEX, Jules, ChatGPT, Z AI, Gemini. Cada um com lente e anti-escopo explícito.
- **Planeja etapas** — sequência de trabalho, dependências, marcos
- **(NOVO 2026-05-24) Consolidação cross-revisor** — garante que paralelos (ex: Jules vs CODEX) não fiquem órfãos quando Code redige ticket follow-up só com 1 revisor em mente. Direciona achados órfãos para destino correto (§11 do ticket pai, dívidas, good-first-issues).
- **Mantém documentação viva** — plano de produção, PROMPT-OPUS, memória, trilha de auditoria.
- **Produz artefatos para humanos** — relatórios HTML de fechamento, materiais de extensão, briefings SMS. Markdown para agentes, HTML para humanos.
- **NÃO implementa código** — se precisar de implementação, redige a spec e passa para o Code

### Conselheiro (sessão Cowork separada) — Assessor Estratégico

- **Decisões difíceis** — quando há conflito entre revisores, dúvida arquitetural, ou risco regulatório
- **Revisão de revisões** — analisa o feedback dos revisores e ajuda Fabiano a decidir o que incorporar
- **Mediação entre AIs** — quando Code e Opus discordam, ou quando um revisor contradiz outro
- **Visão de conjunto** — mantém perspectiva sobre o projeto inteiro, não só o ticket atual

### CODEX (OpenAI) — Revisor Técnico

- **Lente:** segurança, RBAC, owner check, bypass, vulnerabilidades, ledger/auditoria, rollback transacional
- **Quando entra:** rodada 1 (revisão de spec antes da impl) + rodada 2 (revisão pós-impl) de tickets core/module >100 linhas
- **Formato:** P1/P2/P3 numerados com arquivo:linha + descrição + decisão sugerida
- **Histórico de aceitação alta** — taxa 10/10 em rodadas 1 do 5C e do 6. Pode ser exigente sem custo.
- **NÃO sobrepõe Jules** — anti-escopo declarado nos briefings (Jules cuida de qualidade/DX)

### Jules — Auditor Complementar

- **Lente:** qualidade de código, complexidade ciclomática, duplicação, naming, tech debt, type hints, comentários, testabilidade, **DX para extensionistas**
- **Quando entra:** **fim de etapa (Regra 5)**, junto com CODEX rodada 2. Não por sub-tarefa.
- **Formato:** P1/P2/P3 com categoria opcional (`Dup`, `Type`, `Naming`, `DX`, etc.). DX vira categoria explícita a partir de 2026-05-24 (contexto da extensão UFPE).
- **Critério mais permissivo:** Jules P1 só vira bloqueador se for estrutural; achados localizados normalmente são P2/P3. Gate principal continua sendo zero P1 do CODEX.
- **Bônus:** gera candidatos a good-first-issue prontos para a Etapa 9 / extensão.

### ChatGPT (Teams) — Revisor Estratégico Senior

- **Foco**: arquitetura de longo prazo, LGPD, governança, regulação sanitária, segurança sistêmica
- **Quando acionar**: decisões estruturais, documentos jurídicos, modelagem de dados em saúde
- **Perfil**: conservador, cauteloso

### Z AI — Revisor de Integração e QA de Experiência

- **Foco**: contratos frontend↔backend, UX clínica (prescritor), DX (estudante), onboarding
- **Quando acionar**: antes de deploy, antes de abrir issues para estudantes, mudanças em fluxo do usuário
- **Perfil**: pragmático, pensa no usuário final

### Gemini 2.5 Pro — Revisor Pragmático

- **Foco**: performance, simplificação, custo computacional
- **Quando acionar**: quando algo parece complexo demais, decisões de infra
- **Perfil**: direto, corta complexidade

---

## Fluxo de trabalho (calibrado 2026-05-24)

```
Fabiano decide prioridade
    ↓
Arquiteto escreve ticket rodada 0
    ↓
CODEX rodada 1 revisa spec
    ↓
Arquiteto integra (§10)
    ↓
Code implementa
    ↓
CODEX rodada 2 + Jules (fim de etapa, em PARALELO)
    ↓
Se CODEX rodada 2 traz P1 → Code redige TICKET X.Y follow-up
    Em paralelo: Arquiteto consolida cross-revisor
    (garantir que Jules e outros não fiquem órfãos)
    ↓
Code implementa X.Y
    ↓
CODEX rodada 3 → zero P1 → etapa fechada
    ↓
Arquiteto fecha §11 + atualiza PLANO + PROMPT-OPUS + gera relatório HTML
    ↓
Fabiano aprova (com ajuda do Conselheiro se decisão difícil)
    ↓
Code faz push
```

## Quando acionar cada revisor

| Tipo de trabalho | CODEX | Jules | ChatGPT | Z AI | Gemini |
|---|:---:|:---:|:---:|:---:|:---:|
| Feature backend (regulação, dados) | ✅ R1+R2 | ✅ fim | ✅ | — | — |
| Feature frontend (UI, fluxo) | ✅ R1+R2 | ✅ fim | — | ✅ | — |
| Contrato de API (frontend↔backend) | ✅ R1+R2 | ✅ fim | — | ✅ | — |
| Documento jurídico / política | — | — | ✅ | — | — |
| Decisão de arquitetura | — | — | ✅ | — | ✅ |
| UX clínica (fluxo do prescritor) | — | ✅ DX | — | ✅ | — |
| Onboarding / issues para estudantes | — | ✅ DX | — | ✅ | — |
| Deploy / infra / Docker | ✅ R1+R2 | ✅ fim | — | — | ✅ |
| Segurança / LGPD / auditoria | ✅ R1+R2 | — | ✅ | — | — |
| Qualidade de código / DX | — | ✅ fim | — | — | — |

## Como tratar feedback dos revisores

Quando Fabiano trouxer comentários de um revisor, o Code (ou o Opus, conforme quem estiver processando) classifica:

- ✅ **Aceito** — incorpora direto
- 🔄 **Aceito com adaptação** — ideia boa, implementação diferente
- ❌ **Rejeitado** — com justificativa

Sempre apresentar resumo antes de implementar. Nunca implementar cegamente.

Codex é exceção: feedback mecânico (teste falhou, secret exposto) é corrigido direto pelo Code sem consultar Fabiano.
