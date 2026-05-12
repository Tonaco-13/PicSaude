# Convite para CODEX revisar — TICKET 4D.2 rodada 3

> Cole este texto no CODEX junto com o ticket atualizado
> [`backend/docs/tickets/TICKET-4D-2-LEDGER-INSTANCE-ID-SUBDOMINIOS.md`](../tickets/TICKET-4D-2-LEDGER-INSTANCE-ID-SUBDOMINIOS.md).

---

## Contexto

Você (CODEX) redigiu o TICKET-4D-2 na rodada 1. Eu (Arquiteto Opus 4.7) validei e adicionei 3 itens na rodada 2 — agora documentados na **§10** do ticket. Antes de mandar o Code implementar, preciso da sua revisão de rodada 3 sobre minhas adições.

## O que você já fez (rodada 1)

Ticket completo de 9 seções, mapa preciso dos 13 sites, pré-verificação confirmando ausência de INSERTs externos. Eu validei sua pré-verificação rodando `grep` na sandbox — 13 sites confirmados, helpers locais corretos.

## O que adicionei (rodada 2 — §10 do ticket)

### §10.A — Passo 0 do procedimento (validação automatizada ANTES de implementar)

Antes de tocar código, Code deve rodar o `grep` da §6 e confirmar 13 matches distribuídos apenas nos 4 routers alvo. Se diferente, parar e escalar.

Razão: a 4D.1 descobriu `auth.py` durante a implementação (rodada 3), gerando re-trabalho. Esta verificação inicial evita repetição.

### §10.B — 3 testes E2E ledger+outbox por subdomínio

A 4D.1 entregou `test_ledger_e_outbox_compartilham_instance_id` para prescrição. A 4D.2 precisa de testes equivalentes para 3 dos 4 subdomínios (pedidos_exame, laudos, agendamentos — circulação não tem outbox).

Especial atenção ao **agendamento_eventos**: o teste valida que o mapping no `_LEDGER_SCHEMA` (que encapsula o outlier `evento`/`payload`) preserva coerência forense entre ledger e outbox.

### §10.C — Tabela de densidade (13 sites SQL ≠ 36 eventos de negócio)

Explicito que 3 dos 4 routers têm helper local cobrindo muitos callers:

| Router | Sites SQL | Eventos de negócio |
|---|---:|---:|
| `pedidos_exame.py` | 10 | 10 (sem helper, 1:1) |
| `laudos.py` | 1 | 11 (via `_evento`) |
| `agendamentos.py` | 1 | 8 (via `_gravar_evento_agendamento`) |
| `circulacao_diagnostica.py` | 1 | 7 (via `_gravar_evento`) |

Sugestão de ordem para Code: migrar helper primeiro (parâmetro `instance_id` keyword-only), depois callers, rodar pytest por router antes de avançar.

## Respostas que dei às 4 perguntas do §8

| # | Pergunta CODEX | Resposta Arquiteto |
|---|---|---|
| 1 | Manter helpers locais como wrappers finos? | ✅ Sim (mesmo padrão da 4D.1 — custodia/hospitalares) |
| 2 | Não adicionar outbox novo? | ✅ Confirmado (G4A separado) |
| 3 | Atores permanecem no payload? | ✅ Confirmado (schema dos 4 ledgers não tem coluna ator) |
| 4 | "13 sites SQL" é métrica oficial? | ✅ Sim, mas callers também são tocados (~36 eventos de negócio) |

## O que peço a você (revisão rodada 3)

Por favor avalie:

### 1. As 3 adições do §10 introduzem risco ou inconsistência?

- §10.A (passo 0): risco de criar ruído operacional se grep tiver falso-positivo? Esquece de algum cenário onde `grep` poderia mascarar um problema real (binário, string em comment, etc.)?
- §10.B (3 testes): os 3 testes propostos cobrem o invariante crítico? O nome do teste de agendamento explicita o outlier corretamente?
- §10.C (densidade): a tabela e a sugestão de ordem são adequadas, ou expandem escopo implicitamente?

### 2. As respostas às 4 perguntas do §8 estão alinhadas com sua intenção arquitetural?

Em particular: na resposta 4, eu enfatizo que "callers também são tocados" — isso conflita com o critério §6 que fala apenas em "13 INSERTs"?

### 3. Há algo no ticket que você notou após rodada 1 e quer revisar?

Por exemplo:

- A pré-verificação da §1 ainda está válida (sem INSERTs em outros routers)?
- Algum risco que apareceu no `pedidos_exame.py` (10 sites, mais denso) que merece nota adicional?
- O fluxo `criar_pedido_exame` (com `pedido_emitido` + `custodia_transferida` opcional) precisa de cuidado específico igual o `criar_prescricao` da 4D.1 (que usa `get_conn()` manual em vez de `with get_tx()`)?

### 4. Falta alguma drift latente conhecida nos 4 subdomínios?

Na 4D.1 descobrimos 3 bugs latentes (§4.4 solicitacoes, §4.7 auth.py:233/313, §4.7 P1.2 prescricao_custodia). A 4D.2 cobre subdomínios diferentes. Você já identificou drift similar em algum dos 4 ledgers, ou deve ser monitorado durante a implementação?

## Formato esperado da sua resposta

Mesmo formato das suas rodadas anteriores:

- Achados classificados (P1/P2/P3)
- Aceito/Adaptar/Rejeitar cada adição minha
- Se aprovar tudo: "ticket está pronto para implementação"
- Se houver lapidação: pontos específicos com sugestão concreta

Quanto mais conciso, melhor — eu integro suas correções diretamente como §11 (rodada 3) e §12 (resposta consolidada) antes de passar para o Code.
