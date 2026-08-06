# TICKET-RASTREABILIDADE-POR-OBJETO — Medicamento como objeto sanitário rastreável e imutável

| Campo | Valor |
|---|---|
| **Classe** | `core` (mudança de paradigma — reescrita de máquina de estados) |
| **Estado** | ⏸️ **BACKLOG — adiado para pós-piloto** (decisão Fabiano + Z AI, 2026-07-22) |
| **Pré-requisitos** | (1) Piloto validado com modelo atual (quantidade); (2) decisão explícita de reativação; (3) arquiteto + Conselheiro estimam escopo real |
| **Não iniciar antes de** | Piloto em produção com ≥ 100 dispensações reais + decisão de produto baseada em demanda validada |
| **Decisão registrada** | Caminho B — adiar para pós-piloto (ver §1) |

---

## §1 Decisão de produto — Caminho B (adiar)

**Data:** 2026-07-22 · **Quem:** Fabiano (product owner) + Z AI (copiloto de estratégia)

### 1.1 Visão original (Fabiano)

> "Nosso plano original é permitir tanto o estorno parcial quanto a dispensação parcial. Cada medicamento vira em si um objeto sanitário rastreável e imutável. O mesmo objeto não pode ser dispensado (medicamento) 2 vezes."

A visão está **arquiteturalmente correta** e alinha com a tese R1-R4 do §2a do CLAUDE.md (verdade deriva do ledger, nunca de rótulo editável). É o diferencial competitivo do PicSaúde vs SNC digital genérico. **Como visão de produto, aprovada.**

### 1.2 Por que adiar (Caminho B)

Razões estruturais que justificam o adiamento:

1. **Demanda não validada.** ANVISA exige rastreabilidade por **lote**, não por unidade. Rastrear por unidade é mais granular que o regulatório exige — pode ser diferencial de produto, mas é hipótese arquitetural, não demanda confirmada por parceiro/cliente/ANVISA.
2. **Piloto existe para validar demanda.** O propósito do piloto é testar hipóteses de produto antes de investir em arquitetura. Decidir o paradigma antes do piloto inverte a ordem.
3. **T2 já entrega parte do valor.** Estorno como objeto-derivado imutável (já em produção) dá rastreabilidade regulatória aceitável: append-only ledger, saldo efetivo, evento de estorno. Provavelmente passa em auditoria ANVISA.
4. **Custo de migração cresce, mas não explode.** Migrar de "quantidade" para "objeto" com 100 dispensações de piloto = ~1 dia. Com 10.000 em produção = ~1 semana. A diferença não justifica antecipar.
5. **Demo atual não perde a promessa.** No modelo atual, o "objeto sanitário" é a **dispensação** (linha em `dispensacoes`), não o comprimido individual. A circulação (dispensar → estornar → re-dispensar) funciona. O visitante vê o ciclo.

### 1.3 Critérios de reativação (gatilhos)

O ticket só sai do backlog quando **um dos 3 gatilhos** abaixo acontecer:

- **G1 — Demanda regulatória explícita.** ANVISA ou vigilância sanitária estadual exige rastreabilidade por unidade em processo formal.
- **G2 — Demanda de cliente/parceiro.** Parceiro estratégico (operadora, hospital, rede de farmácias) exige rastreabilidade por unidade como pré-requisito de contrato.
- **G3 — Caso de uso real no piloto.** Piloto identifica cenário onde rastreabilidade por unidade resolve problema que o modelo por quantidade não resolve (ex.: recalls de lote específico, divergência de inventário por unidade).

**Sem gatilho**, o ticket permanece em backlog. Reativação sem gatilho = decisão explícita de Fabiano com estimativa atualizada do arquiteto.

### 1.4 Granularidade a definir quando reativar

Quando o ticket for reativado, a primeira decisão é a granularidade do "objeto sanitário". Três interpretações possíveis:

| Interpretação | Exemplo | Volume | Alinhamento ANVISA |
|---|---|---|---|
| **(a) Por unidade** | 1 comprimido = 1 UUID | 10 comprimidos = 10 objetos | Over-engineering — ANVISA exige por lote |
| **(b) Por frasco/caixa** | 1 frasco com 30 comprimidos = 1 UUID | 1 frasco = 1 objeto | Alinhado com prática da indústria |
| **(c) Por lote+quantidade** | "Lote X, 4 unidades" = 1 objeto agregado | Híbrido | Alinhado, mais simples |

**Recomendação preliminar (Z AI):** (b) por frasco/caixa. Razão: alinha com ANVISA (rastreio por lote), controla volume, faz sentido para farmácia ambulatorial. Mas decisão final é de produto, com input do arquiteto sobre custo real de cada opção.

---

## §2 Impacto no que já existe (mapeamento)

Quando o ticket for reativado, os artefatos abaixo precisam ser refatorados. Mapeamento para estimativa futura:

| Artefato | Estado atual | Impacto da mudança | Classe |
|---|---|---|---|
| **T2 (estorno objeto-derivado)** | ✅ Em produção | `estornos.quantidade` deixa de fazer sentido; vira transferência de N objetos específicos | `core` |
| **T3 (trigger Σ no Postgres)** | ✅ Em produção | **Invalidado** — conceito de Σ some; vira COUNT de objetos + constraint UNIQUE em `objeto_id` | `core` |
| **T1.5 (detenção prévia)** | ✅ Em produção | "Detenção" vira "objeto está comigo" — lógica muda | `core` |
| **B0 (guard por saldo)** | ✅ Em produção | Saldo vira COUNT de objetos em posse; guard muda | `core` |
| **T5 (comprador)** | ✅ Em produção | Comprador vira "detentor de N objetos específicos" | `module` |
| **T6 (histórico)** | ✅ Em produção | Linhagem por objeto, não por prescrição | `module` |
| **R3 (protocolo_raiz)** | 🔴 Não implementado | **Mantém** — linhagem da prescrição-mãe independe de granularidade de objeto | `module` |
| **F5 (relatório SNGPC)** | ✅ Em produção | Escrituração por objeto, não por movimento de quantidade | `module` |
| **COERENCIA-DEVOLUCOES** | 🟡 Ticket aberto | Devolução vira transferência de objetos, não de posse abstrata | `core` |
| **R2 (unicidade de identificadores)** | 🟡 Ticket aberto | Ganha nova dimensão — `objeto_id` como identificador único | `core` |

**Resumo:** 7 artefatos `core` + 3 `module` afetados. Estimativa preliminar (sem ver código): **2-3 semanas de esforço de engenharia**, sem contar ciclos de portão + Jules em `core`.

---

## §3 Os 3 caminhos considerados (registro histórico)

Para referência futura, os 3 caminhos analisados na decisão de 2026-07-22:

### Caminho A — Adotar agora (paralisa demo)
- **Custo:** 2-3 semanas de reescrita. T2, T3, B0, T5, T6, F5, COERENCIA todos refator. Migração de dados em T2 (já tem dispensações com `quantidade`).
- **Benefício:** alinha imediatamente com visão; não acumula dívida.
- **Risco:** demo atrasa; pode descobrir que modelo atual era suficiente.
- **Rejeitado por:** demanda não validada (§1.2 ponto 1).

### Caminho B — Adiar para pós-piloto (ESCOLHIDO)
- **Custo:** zero agora; vira migração maior depois (com dados de piloto).
- **Benefício:** demo não atrasa; piloto valida demanda antes de investir.
- **Risco:** migração depois é mais cara (mais dados).
- **Aceito por:** razões §1.2.

### Caminho C — Híbrido (compromisso)
- **Custo:** 3-5 dias adicionais na frente atual.
- **Benefício:** ganha rastreabilidade por objeto sem invalidar o que existe.
- **Risco:** complexidade de 2 modelos coexistindo; pode virar dívida permanente.
- **Como:** manter `dispensacoes.quantidade` (agregado) + adicionar tabela `dispensacao_objetos` (1 linha por objeto UUID) vinculada à dispensação. Constraint UNIQUE em `objeto_id` em dispensações ativas. Estorno transfere objetos específicos de volta.
- **Rejeitado por:** complexidade de coexistência sem demanda que justifique.

---

## §4 Coordenadas com tickets ativos

Este ticket **não bloqueia** nenhum ticket atualmente em andamento. Coordenadas específicas:

- **COERENCIA-DEVOLUCOES (em andamento):** implementa no modelo atual (quantidade + posse). Quando este ticket for reativado, COERENCIA precisará refator — mas o fix atual entrega valor real agora e não pode esperar.
- **R3 (protocolo_raiz):** independe de granularidade de objeto. Pode ser implementado no modelo atual sem retrabalho quando este ticket for reativado.
- **R2 (unicidade):** quando reativado, ganha `objeto_id` como nova dimensão de unicidade. O guard-rail test atual (`HAVING COUNT(*) > 1` em `dispensacao_id`) permanece; adiciona guard-rail em `objeto_id`.
- **TICKET-LEDGER-COMPLEMENTAR-CUSTODIA (em andamento):** implementa no modelo atual. Quando reativado, eventos de custódia ganham `objeto_id` no payload.

---

## §5 Quando reativar — checklist de abertura

Antes de remover este ticket do backlog, confirmar:

- [ ] Um dos 3 gatilhos (G1/G2/G3 do §1.3) aconteceu
- [ ] Decisão de produto documentada com data e rationale
- [ ] Granularidade (a/b/c do §1.4) decidida
- [ ] Arquiteto estimou os 7 artefatos `core` + 3 `module` do §2
- [ ] Conselheiro confirmou que migração de dados de T2 é viável
- [ ] Plano de migração de produção existe (não pode ser big-bang)
- [ ] Cronograma de piloto revisado — reativação não pode quebrar piloto em andamento

Sem esses 7 itens, o ticket permanece em backlog.

---

## §6 Lição registrada (LEARNINGS.md)

> **Adiar decisão arquitetural não-validada é decisão, não omissão.**
>
> Quando uma visão arquitetural (rastreabilidade por objeto) colide com deadline de piloto, a escolha de adiar **é** uma decisão de produto — não é "deixar pra depois". O critério para reativar fica explícito (gatilhos G1/G2/G3), e o ticket entra no backlog com mapeamento de impacto completo.
>
> Razão: adiar sem critério vira dívida invisível. Adiar com critério vira dívida gerenciada. A diferença é o §5 checklist de abertura — sem ele, ninguém sabe quando o ticket pode ser reativado.
>
> Ref: decisão Fabiano + Z AI, 2026-07-22. Padrão aplicável a outras visões arquiteturais não-validadas (ex: push WebSocket, XML SNGPC oficial, etc.).

---

## §7 Não fazer agora

- **Não** criar branch para este ticket
- **Não** estimar em horas (estimativa muda com código que entra entre agora e reativação)
- **Não** desenhar schema de `dispensacao_objetos` (decisão de granularidade vem primeiro)
- **Não** abrir PR preditivo (sem implementação, sem PR)
- **Não** adicionar a sprint atual

---

## §8 Referências

- **Visão original:** mensagem Fabiano, 2026-07-22 ("cada medicamento vira em si um objeto sanitário rastreável e imutável")
- **Análise dos 3 caminhos:** Z AI copiloto, 2026-07-22 (resposta no chat)
- **Decisão:** Caminho B — adiar para pós-piloto
- **Critérios de reativação:** §1.3 (G1/G2/G3)
- **Mapeamento de impacto:** §2
- **Padrão aplicável:** §6 (LEARNINGS.md)

---

> **Este ticket é um marcador de decisão, não um ticket de implementação.**
> Existe para que a decisão de adiar não vire esquecimento. Quando um dos gatilhos acontecer,
> este ticket é reativado e vira implementação — com estimativa atualizada, schema desenhado
> e plano de migração. Até lá, permanece neste estado.
