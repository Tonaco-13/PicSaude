# PLANO DE EXECUÇÃO — Demo: Circulação de Objetos Sanitários (Módulo Dispensador)

> Conselheiro (cowork/MS), 2026-07-05 — **v1.1** (incorpora as 5 flags da revisão
> do Z AI; aprovado por ele condicionado a elas). Substitui as §6–7 de
> `BRIEFING_P05_DEMO.md`. Base: escopo v27 (registro Gemini), orientações Z AI,
> **inventário de invariantes verificado em código** (evidência arquivo:linha —
> não reinvestigar).

## 0. Decisão de prioridade (registro)

**2026-07-05, Fabiano:** avançar o módulo dispensador — "circulação perfeita dos
objetos sanitários". Logins fora de escopo. **Substitui** a decisão de 2026-07-04
(R6 prioritário). R6 permanece bloqueador absoluto do piloto; apenas sai da fila
desta semana. Retomada do R6 = próxima decisão explícita.

## 1. Objetivo da demo

Um visitante acompanha o ciclo completo do objeto sanitário, sem quebra de invariante:

```
emissão (prescritor) → posse do paciente → token de apresentação
  → retenção pela farmácia (em_custodia) → dispensação parcial (Σ respeitado)
  → devolução (posse VOLTA ao paciente) → re-apresentação em outra farmácia
  → estorno de dispensação registrada → relatório reconciliado com o ledger
```

## 2. Inventário de invariantes (fechado em 2026-07-05)

| # | Invariante | Estado | Evidência |
|---|---|---|---|
| 1 | Posse transferida ativamente (`em_custodia`) | ✅ existe | `domain/states.py:73-120`; `custodia.py:371` (transferir), `:542` (dispensar), `:239` (guarda de detenção) |
| 2 | Token de apresentação | ✅ existe | `tokens.py` (resolve com estados válidos); UI cidadão Ticket 25 |
| 3 | Σ dispensado ≤ prescrito | ⚠️ app-level | `custodia.py` (SUM + 409/422 em transação); DDL:301 sem constraint de soma |
| 4 | Devolução → controle volta ao paciente | ❌ quebrado | `custodia.py:829` — `_fechar_custodia_ativa` sem `_abrir_custodia(paciente)`; item fica **sem detentor** (viola CLAUDE.md §3) |
| 5 | Estorno pós-dispensação | ❌ inexistente | estado `estornado` declarado (`states.py:117`); sem rota; sem evento no vocabulário CLAUDE.md §2 |
| 6 | Comprovante COMPRADOR × PACIENTE | ⚠️ parcial | `dispensacoes.py:277` (PDF existe); campo comprador ausente do DDL/payload/UI |
| 7 | Relatório derivado do ledger | ⚠️ diverge | `relatorios.py:79-88` lê `dispensacoes` (JOIN), não `prescricao_eventos` |
| 8 | Fila do dispensador | ❌ inexistente | nenhum endpoint lista custódia ativa por detentor-estabelecimento |

## 3. Fase 0 — Ratificações (Fabiano, antes de codar)

1. **Fonte dos relatórios (item 7).** Divergência fundamentada com o guardrail do
   Z AI ("rejeitar se não ler `prescricao_eventos`"): `dispensacoes` é tabela de
   fatos, escrita **exclusivamente** pelo endpoint oficial na **mesma transação**
   que grava o evento no ledger (`custodia.py:542+`). Ler dela não quebra "ledger
   como fonte da verdade"; parsear payload JSON de eventos seria mais frágil
   (payload não é contrato estável). **Recomendação do Conselheiro:** manter a
   fonte atual + **teste automatizado de reconciliação** (Σ eventos de dispensação
   ≡ Σ linhas de `dispensacoes`, por protocolo e agregado). Ratificar ou reverter.
2. **Estorno entra no vocabulário do ledger (item 5).** Novo(s) evento(s) — p.ex.
   `dispensacao_estornada` — é mudança classe `core` (CLAUDE.md §10: ledger).
   Ratificar nome do evento e semântica: estorno repõe saldo Σ e é **distinto**
   de devolução (devolução = item ainda não entregue; estorno = reverte
   dispensação registrada). **Recomendação de desenho do Conselheiro:** estorno
   como **registro próprio append-only** (tabela referenciando `dispensacao_id`),
   nunca UPDATE/DELETE em `dispensacoes`; Σ efetivo = dispensado − estornado.
   **SLA (Flag 1 Z AI): ratificação em <24h.** Sem resposta, T2 fica em standby
   e T1/T3 avançam — eles **não** dependem do nome do evento.
3. **Nota normativa (rotulagem "SNGPC") — NÃO bloqueia a 0.2.** O status
   operacional do SNGPC/ANVISA mudou nos últimos anos [verificar norma vigente
   antes do rótulo]. Até lá, rotular o relatório como "escrituração — Portaria
   SVS/MS nº 344/1998" e tratar "SNGPC" como pendência de verificação normativa.
   O Conselheiro pode fazer essa verificação com fontes oficiais sob demanda.

## 4. Fase 1 — Integridade da circulação (code/MS · classe core · portão + Jules)

Sem isso a demo mente. Tudo via PR; nada de push direto.

| Ticket | Escopo | Classe | Esforço |
|---|---|---|---|
| **T0.5 — Segunda farmácia no seed** (Flag 3 Z AI) | `seed_demo.py`: adicionar `Farmácia Demo Norte`, CNPJ `99999999000272` (DVs válidos — verificados) + usuário dispensador. Sem ela, o gate da Fase 4 dá **falso verde** no ramo "re-apresentação em outra farmácia". Booleans como `True` (lição do Fix 6); testar contra Postgres | ops/demo | S |
| **T0.6 — Persona Farmácia Norte no /demo/login** ✅ | Persona `dispensador_norte` (CNPJ `99999999000272`) no `POST /demo/login` — habilita o ciclo A→B sem senha. Papel `dispensador` único (só muda o CNPJ). | ops/demo | S |
| **T1 — Devolução reabre custódia ao paciente** | Em `devolver_item` (para=paciente): `_abrir_custodia(paciente)` na mesma transação; `GET /custodia` passa a mostrar o paciente como detentor. Teste: devolver → detentor=paciente → re-reter em **outro CNPJ** (usa T0.5) | core (custódia) | S–M |
| **T1.5 — Detenção prévia no dispensar** ✅ (ratificado 2026-07-09) | `dispensar_item` exige que o estabelecimento **detenha** o item. **Produção:** 409 `item_nao_retido` (retenção é pré-requisito). **Demo:** **auto-retenção** — abre custódia e **emite `custodia_transferida`** (auto-retenção sem o evento = bug — CLAUDE.md §2). **Decisão ratificada por Fabiano:** auto-retenção **substitui** a "Opção B / 2 telas" (1 caminho no backend; feedback pedagógico vem da UI da Fase 4: banner de retenção + linha na fila). Condição do PR#76 (409 `item_retido_por_outro`) preservada, roda antes. | core (custódia) | S–M |
| **T2 — Endpoint de estorno** ✅ | `POST /dispensacoes/{id}/estornar`: exige dispensação registrada do próprio CNPJ; **reposição de saldo Σ efetivo = dispensado − estornado**. **Implementado como OBJETO SANITÁRIO DERIVADO e imutável** (`estornos`, `origem_dispensacao_id`) — **não** transição `dispensado → estornado`: o item **não é mutado**, a reversão vive no objeto-estorno, conforme `TICKET-ESTORNO-OBJETO-DERIVADO.md` (martelo Fabiano 2026-06-15). Nunca UPDATE/DELETE em `dispensacoes`. Evento: `estorno_registrado` (CLAUDE.md §2). | core (ledger + estados) | M |
| **T3 — Constraint Σ no banco** | Trigger PostgreSQL sobre o **Σ efetivo = dispensado − estornado** (Flag 2 Z AI: trigger que só some INSERTs de `dispensacoes` impediria o T2 de repor saldo — desenhar T3 já ciente do modelo de estorno da Fase 0.2). CHECK não faz agregado. Manter validação app (mensagem amigável); trigger é a rede. Testar contra Postgres do Render, não SQLite | core-adjacente (DDL clínico) | S–M |

Gate de aceite da Fase 1 (Conselheiro): rastro de custódia sem buraco em nenhum
momento do ciclo; ledger append-only intocado; paridade de comportamento
SQLite×Postgres testada.

## 5. Fase 2 — Circulação visível (code/MS backend + Z AI validação UI↔invariante)

| Ticket | Escopo | Classe | Esforço |
|---|---|---|---|
| **T4 — Fila do dispensador** | `GET /dispensadores/fila` (ou equivalente): prescrições/itens com custódia ativa do CNPJ do JWT. **Guardrail:** a query filtra por detentor real na cadeia de custódia (nunca view sem state machine — critério Z AI mantido); polling no front basta para a demo | module | M |
| **T5 — Comprovante com COMPRADOR** | Coluna(s) opcionais em `dispensacoes` (nome/documento do comprador, NULL default — `local-extension` conforme CLAUDE.md §10), payload no dispensar, seção no PDF do comprovante. **LGPD:** minimização — só o exigido pela escrituração; nunca expor em endpoint público | local-extension + module | M |
| **T6 — Histórico por receita (endpoint + UI)** | **Flag 4 Z AI confirmada em código:** `routers/eventos.py` é a G4A (fila `eventos_publicacao` p/ integradores, com ack) — **não** serve trilha por protocolo, e não existe rota de eventos por prescrição. Escopo real: novo `GET /prescricoes/{proto}/eventos` **read-only** sobre `prescricao_eventos` (RBAC: detentor/autor; jamais escrita) + view no dispensador. **Nunca SQL direto do front** | module (leitura de ledger) + local-extension | M |

## 6. Fase 3 — Relatórios (code/MS)

| Ticket | Escopo | Classe | Esforço |
|---|---|---|---|
| **T7 — Teste de reconciliação ledger × dispensacoes** | Automatizado (CI): para cada protocolo, eventos de dispensação/estorno ≡ estado agregado. É o guardrail que substitui "ler do ledger" (Fase 0.1). **Cenários mínimos obrigatórios (Flag 5 Z AI):** (a) fluxo normal sem estorno; (b) estorno completo de item; (c) estorno parcial seguido de **nova dispensação** do saldo reposto. Os três verdes ou T7 não fecha | module (teste) | S–M |
| **T8 — CSV: BOM UTF-8 + botão na UI** | Ajuste no `/relatorios/dispensacoes.csv` + exportação visível no dispensador. **LGPD idem T5:** se o comprador entrar no CSV, mesma minimização — e o download exige o RBAC do estabelecimento, nunca rota pública | local-extension | S |

## 7. Fase 4 — Gate de demo ponta-a-ponta

1. **Gate programático** (python3 + urllib, nunca curl): script executa o ciclo
   completo do §1 em produção via API e verifica, a cada passo, status da
   prescrição/item, **detentor de custódia** e evento correspondente no ledger.
2. **Teste manual humano** (Fabiano, janela anônima): mesmo ciclo pelos cards
   demo. Gate programático é necessário, não suficiente.
3. **Auditoria Jules**: cada PR das Fases 1–3 + parecer final sobre invariantes.

## 8. Papéis

| Quem | Responsabilidade |
|---|---|
| **code/MS** | Implementa T1–T8 (Fase 1 primeiro, sequencial; Fases 2–3 paralelizáveis) |
| **Conselheiro (cowork/MS)** | Portão de core (T1–T3), aceite por invariante, dono deste plano |
| **Jules** | Auditoria de cada PR + pendência herdada: auditoria pós-fato do `879c7db` (P0) |
| **Z AI** | Validação UI↔invariante (Fase 2), apoio de priorização |
| **Fabiano** | Ratificações da Fase 0, testes manuais, decisão de retomada do R6 |

## 9. Fora de escopo (explícito)

- Login manual / correção do `[object Object]` — backlog (ver `BRIEFING_P05_DEMO.md` §4.1).
- Push em tempo real (WebSocket) — polling atende a demo.
- `PICSAUDE_DECISAO_CLINICA` permanece desligada.
- R6 pausado por decisão do §0 — não abrir trabalho de serialização nesta frente.

## 10. Ordem de execução sugerida

```
Fase 0 (Fabiano, SLA <24h) → T0.5 ∥ T1 → T2 → T3 (portão+Jules em cada)
  → T4 ∥ T5 ∥ T6 → T7 ∥ T8 → Fase 4 (gate + manual) → demo pronta
```

**Por que T1 primeiro dentro da Fase 1:** sem devolução íntegra não há o que
re-apresentar, e sem dispensação/devolução corretas T2 não tem o que estornar
nem T3 o que proteger. T1 é o caminho crítico do caminho crítico. Se a Fase 0.2
atrasar além do SLA, T0.5/T1/T3-desenho avançam e **só T2 espera**.

Estimativa total de code/MS: ~2–3 dias úteis. O caminho crítico é a Fase 1 —
sem ela, fila e comprovante exibiriam uma circulação que viola os invariantes
que a demo existe para provar.
