# TICKET 4D.2 — Integrar `instance_id` nos ledgers de exame, laudo, agendamento e circulação diagnóstica

> **Sub-tarefa 4D.2 do plano de produção** (`docs/PLANO-PRODUCAO-V2.md` §4)
> **Classe:** `core` — toca ledgers imutáveis (`*_eventos`)
> **Pacto:** Regra 2 estrita — ticket → Arquiteto valida → Code implementa → CODEX revisa
> **Data:** 2026-05-11
> **Escopo:** 4 routers, 13 sites SQL brutos, com helpers locais em 3 routers
> **Predecessoras:** 4A `d8abf7e`, 4B-prequel `2dce4f8`, 4B `89f064a`, 4C `2fbcf43` + `983359f`, 4D.1 `60382d2` + `0056c93`, Task #8 `d2f016b`
> **Revisado por:** CODEX (rodada 1) — ticket redigido; Arquiteto (rodada 2) — adições em §10

---

## §1 Contexto e objetivo

A 4C entregou o helper central:

```python
registrar_evento_ledger(conn, ..., instance_id=...)
```

e a variante transacional:

```python
get_instance_id_conn(conn)
```

A 4D.1 integrou o subdomínio **prescrição** ao helper, preenchendo `instance_id` no ledger e nos outboxes adjacentes.

A 4D.2 fecha os 4 subdomínios restantes da Etapa 4:

| Subdomínio | Router | Ledger | `objeto_tipo` |
|---|---|---|---|
| Pedido de exame | `backend/app/routers/pedidos_exame.py` | `pedido_exame_eventos` | `"pedido_exame"` |
| Laudo | `backend/app/routers/laudos.py` | `laudo_eventos` | `"laudo"` |
| Agendamento | `backend/app/routers/agendamentos.py` | `agendamento_eventos` | `"agendamento"` |
| Circulação diagnóstica | `backend/app/routers/circulacao_diagnostica.py` | `circulacao_diagnostica_eventos` | `"circulacao_diagnostica"` |

Objetivo: substituir todos os `INSERT INTO *_eventos` manuais desses subdomínios por `registrar_evento_ledger(...)`, garantindo `instance_id` UUID v4 em cada evento novo.

Pré-verificação CODEX nesta revisão: não há INSERTs dessas 4 tabelas em routers fora dos 4 alvos no estado atual do repo. **Confirmado pelo Arquiteto (rodada 2)** via `grep` em `app/routers/` inteiro.

---

## §2 Decisão sobre os 4 models principais

Não alinhar nesta sub-tarefa os models principais:

- `Prescricao`
- `PedidoExame`
- `Laudo`
- `Agendamento`

A 4D.2 escreve apenas em ledgers (`*_eventos`) e no outbox adjacente já existente. Alinhamento dos models principais permanece fora do escopo, como decidido na 4D.1, para Etapa 8 / Task #5.

---

## §3 Regra de implementação

Em cada transação clínica que grava evento no ledger:

```python
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn

instance_id = get_instance_id_conn(conn)

registrar_evento_ledger(
    conn,
    objeto_tipo="pedido_exame",
    objeto_id=pedido_id,
    tipo_evento="pedido_emitido",
    instance_id=instance_id,
    payload=ev_emitido,
)
```

Regras obrigatórias:

1. Chamar `get_instance_id_conn(conn)` uma vez por transação clínica que escreve no ledger.
2. Reutilizar o mesmo `instance_id` em todos os eventos da mesma transação.
3. Passar o mesmo `instance_id` para cada `registrar_outbox(...)` já adjacente.
4. Não adicionar outbox novo nesta sub-tarefa.
5. Não passar `ator_tipo` nem `ator_id` nos 4 subdomínios da 4D.2. O helper só aceita ator em `objeto_tipo="prescricao"`.
6. Não alterar vocabulário de eventos, payloads, estados, custódia ou regras clínicas.
7. Não silenciar falha do ledger. Exceção em `registrar_evento_ledger(...)` deve abortar a transação.

Particularidade obrigatória: `agendamento_eventos` é outlier de schema (`evento` e `payload`). O router/helper deve chamar a API uniforme com `tipo_evento=...`; o drift fica encapsulado em `app/domain/ledger.py`.

---

## §4 Mapa completo dos sites

### §4.1 `backend/app/routers/pedidos_exame.py` — 10 sites SQL diretos

| Linha atual | Evento | Ator |
|---:|---|---|
| 304 | `pedido_emitido` | N/A — schema sem `ator_tipo` |
| 344 | `custodia_transferida` | N/A — ator permanece no payload (`de_id`, `para_id`) |
| 445 | `pedido_impresso` | N/A |
| 460 | `encerrado_localmente` | N/A |
| 633 | `pedido_agendado` | N/A |
| 708 | `pedido_coletado` | N/A |
| 773 | `pedido_cancelado` | N/A |
| 849 | `pedido_em_analise` | N/A |
| 883 | `resultado_registrado` | N/A |
| 955 | `pedido_encerrado` | N/A |

Outbox adjacente existente: linhas 310, 713, 778, 888, 960. Cada chamada deve receber o mesmo `instance_id` do evento ledger correspondente.

Notas:

- `criar_pedido_exame` tem 2 eventos possíveis na mesma transação: `pedido_emitido` e `custodia_transferida`; ambos devem compartilhar `instance_id`.
- `criar_pedido_exame_fisico` grava `pedido_impresso` + `encerrado_localmente`; ambos devem compartilhar `instance_id`.
- `registrar_resultado_item` pode gravar `pedido_em_analise` + `resultado_registrado`; ambos devem compartilhar `instance_id`.

### §4.2 `backend/app/routers/laudos.py` — 1 site SQL físico, 11 eventos de negócio

Site SQL bruto:

| Linha atual | Evento | Ator |
|---:|---|---|
| 213 | variável em `_evento(...)` | N/A — schema sem `ator_tipo` |

Callers atuais:

| Linha atual | Evento | Observação |
|---:|---|---|
| 308 | `laudo_criado` | com outbox via `protocolo` |
| 380 | `laudo_impresso` | sem outbox |
| 385 | `encerrado_localmente` | sem outbox |
| 482 | `laudo_assinado` | com outbox |
| 539 | `laudo_liberado` | com outbox |
| 580 | `ciencia_paciente` | com outbox |
| 586 | `laudo_encerrado` | condicional, mesma transação de `ciencia_paciente` |
| 627 | `ciencia_prescritor` | com outbox |
| 633 | `laudo_encerrado` | condicional, mesma transação de `ciencia_prescritor` |
| 670 | `laudo_encerrado` | encerramento direto |
| 724 | `laudo_cancelado` | com outbox |

Implementação recomendada:

- Manter `_evento(...)` como helper local fino, mas delegando para `registrar_evento_ledger(...)`.
- Alterar `_evento(...)` para receber `instance_id`.
- Quando `protocolo` for fornecido, chamar `registrar_outbox(..., instance_id=instance_id)`.
- Em fluxos com 2 eventos na mesma transação (`fisica`, ciências que encerram), reutilizar o mesmo `instance_id`.

### §4.3 `backend/app/routers/agendamentos.py` — 1 site SQL físico, 8 eventos de negócio

Site SQL bruto:

| Linha atual | Evento | Ator |
|---:|---|---|
| 119 | variável em `_gravar_evento_agendamento(...)` | N/A — schema sem `ator_tipo` |

Callers atuais:

| Linha atual | Evento | Observação |
|---:|---|---|
| 262 | `agendamento_criado` | com outbox |
| 352 | `agendamento_confirmado` | com outbox |
| 393 | `agendamento_realizado` | com outbox |
| 427 | `agendamento_cancelado` | com outbox |
| 460 | `agendamento_nao_compareceu` | com outbox |
| 506 | `agendamento_remarcado` | com outbox |
| 511 | `agendamento_cancelado` | mesma transação da remarcação |
| 537 | `agendamento_criado` | novo objeto derivado na remarcação |

Implementação recomendada:

- `_gravar_evento_agendamento(...)` deve delegar para `registrar_evento_ledger(...)` com `objeto_tipo="agendamento"`.
- O helper deve passar `tipo_evento=evento` ao helper central, apesar da tabela física usar coluna `evento`.
- `registrar_outbox(...)` dentro do helper deve receber `instance_id`.
- Em `remarcar_agendamento`, os 3 eventos da transação devem compartilhar o mesmo `instance_id`.

### §4.4 `backend/app/routers/circulacao_diagnostica.py` — 1 site SQL físico, 7 eventos de negócio

Site SQL bruto:

| Linha atual | Evento | Ator |
|---:|---|---|
| 168 | variável em `_gravar_evento(...)` | N/A — schema sem `ator_tipo` |

Callers atuais:

| Linha atual | Evento | Observação |
|---:|---|---|
| 326 | `circulacao_criada` | criação |
| 470 | `circulacao_proposta_recebida` | laboratório/admin no payload |
| 519 | `circulacao_confirmada_paciente` | paciente/admin no payload |
| 577 | variável: `circulacao_desmarcada_paciente` ou `circulacao_desmarcada_laboratorio` | depende do role |
| 623 | `circulacao_realizada` | laboratório/admin no payload |
| 671 | `circulacao_desmarcada_laboratorio` | remarcação, circulação antiga |
| 736 | `circulacao_criada` | remarcação, nova circulação derivada |

Implementação recomendada:

- `_gravar_evento(...)` deve delegar para `registrar_evento_ledger(...)` com `objeto_tipo="circulacao_diagnostica"`.
- Alterar o helper para receber `instance_id`.
- `remarcar_circulacao` grava 2 eventos na mesma transação; ambos devem compartilhar o mesmo `instance_id`.
- Não adicionar outbox novo em circulação diagnóstica nesta sub-tarefa.

---

## §5 Escopo fora deste ticket

Não fazer:

- Backfill de `instance_id` em eventos antigos.
- Alterar os 4 models principais.
- Padronizar nomes físicos de colunas (`evento` → `tipo_evento`, `payload` → `dados_json`).
- Adicionar outbox em eventos que hoje não têm outbox.
- Alterar estados, transições, payloads ou vocabulário de eventos.
- Adicionar `ator_tipo`/`ator_id` a ledgers sem essas colunas.
- Alterar assinatura pública de `registrar_evento_ledger`, `get_instance_id_conn` ou `registrar_outbox`.

---

## §6 Critérios de aceitação e verificação automatizada

### Geral

- Zero `INSERT INTO` manual para os 4 ledgers alvo em `backend/app/routers/`.
- Todo evento novo nos 4 ledgers tem `instance_id` UUID v4 válido.
- Eventos da mesma transação clínica compartilham o mesmo `instance_id`.
- Outboxes adjacentes recebem o mesmo `instance_id` do ledger.
- Nenhuma chamada da 4D.2 passa `ator_tipo` ou `ator_id`.
- Falha no helper de ledger aborta a transação.

### Verificação automatizada obrigatória

```bash
for tab in pedido_exame_eventos laudo_eventos agendamento_eventos circulacao_diagnostica_eventos; do
  grep -RInI --include='*.py' --exclude-dir='__pycache__' \
    "INSERT INTO $tab" backend/app/routers/
done
```

Esperado após implementação: zero matches.

A verificação deve rodar em `backend/app/routers/` inteiro, não só nos 4 arquivos, para capturar sites externos que apareçam no caminho.

---

## §7 Testes obrigatórios

Criar ou ajustar testes focados, preferencialmente em novo arquivo:

```text
backend/tests/integration/test_4d2_instance_id_ledger.py
```

Cobertura mínima:

- `POST /pedidos-exame` → `pedido_emitido` com `instance_id`.
- `POST /pedidos-exame/fisica` → `pedido_impresso` + `encerrado_localmente` com mesmo `instance_id`.
- `POST /pedidos-exame/{proto}/itens/{item_id}/resultado` → `pedido_em_analise` + `resultado_registrado` com mesmo `instance_id`; outbox de `resultado_registrado` com o mesmo valor.
- `POST /laudos` → `laudo_criado` com `instance_id` e outbox igual.
- `POST /laudos/fisica` → `laudo_impresso` + `encerrado_localmente` com mesmo `instance_id`.
- Fluxo de ciência de laudo que gere `ciencia_*` + `laudo_encerrado` na mesma transação, ambos com mesmo `instance_id`.
- `POST /agendamentos` → `agendamento_criado` no outlier `agendamento_eventos.evento`, com `instance_id` e outbox igual.
- `POST /agendamentos/{proto}/remarcar` → 3 eventos com mesmo `instance_id`, incluindo o novo agendamento derivado.
- `POST /pedidos-exame/{proto}/circulacao` → `circulacao_criada` com `instance_id`.
- `POST /circulacao/{chave}/remarcar` → `circulacao_desmarcada_laboratorio` + nova `circulacao_criada` com mesmo `instance_id`.

Regressões obrigatórias:

```bash
cd backend
python3 -m pytest tests/test_ledger_helper.py
python3 -m pytest tests/test_migration_4b_instance_id.py
python3 -m pytest tests/test_eventos_publicacao.py
python3 -m pytest tests/test_agendamentos.py
python3 -m pytest tests/test_circulacao_diagnostica.py
python3 -m pytest tests/test_circulacao_ticket54.py
python3 -m pytest tests/integration/test_4d1_instance_id_ledger.py
python3 -m pytest tests/integration/test_4d2_instance_id_ledger.py
```

Se existir teste legado que assuma `instance_id IS NULL` nos eventos novos desses subdomínios, atualizar a expectativa: comportamento correto pós-4D.2 é `instance_id` preenchido.

---

## §8 Perguntas para o Arquiteto/Fabiano

1. Confirmar que a 4D.2 deve manter helpers locais (`_evento`, `_gravar_evento_agendamento`, `_gravar_evento`) como wrappers finos do helper central. **Recomendação CODEX**: sim, para reduzir difusão da mudança.
2. Confirmar que não se deve adicionar outbox novo para eventos que hoje não têm outbox. **Recomendação CODEX**: não adicionar; isso é G4A separado.
3. Confirmar que atores de negócio em laudo/agendamento/circulação permanecem apenas no payload quando já existem. **Recomendação CODEX**: sim; não adicionar `ator_tipo`/`ator_id`.
4. Confirmar que a contagem oficial da 4D.2 é "13 sites SQL brutos", mas a implementação deve atualizar também os callers dos helpers locais para propagar `instance_id`.

**Respostas do Arquiteto (rodada 2):**

| # | Resposta | Razão |
|---|---|---|
| 1 | ✅ **Sim** — manter helpers locais como wrappers finos | Mesmo padrão da 4D.1 (`_gravar_evento` em custodia.py e hospitalares.py). Reduz difusão da mudança. |
| 2 | ✅ **Não adicionar outbox novo** | Outbox adicional é G4A separado; fora do escopo da Etapa 4. |
| 3 | ✅ **Atores permanecem no payload** | Schema dos 4 ledgers não tem coluna ator. Não modificar schema agora. |
| 4 | ✅ **13 sites SQL é métrica oficial** | Mas implementação propaga `instance_id` aos callers dos helpers (na prática, ~36 eventos de negócio). Ver §10.C abaixo. |

---

## §9 Prompt sugerido para implementação

```markdown
Implementar TICKET-4D.2-LEDGER-INSTANCE-ID-SUBDOMINIOS.md.
Classificação: core. Regra 2 estrita.

Escopo:
- migrar os 13 INSERTs manuais em:
  - pedido_exame_eventos
  - laudo_eventos
  - agendamento_eventos
  - circulacao_diagnostica_eventos
- usar registrar_evento_ledger(..., instance_id=...) com:
  - objeto_tipo="pedido_exame"
  - objeto_tipo="laudo"
  - objeto_tipo="agendamento"
  - objeto_tipo="circulacao_diagnostica"
- chamar get_instance_id_conn(conn) uma vez por transação clínica que grava ledger;
- passar o mesmo instance_id para registrar_outbox já existente;
- não passar ator_tipo/ator_id nesses 4 subdomínios;
- ajustar helpers locais para receber instance_id e delegar ao helper central;
- adicionar testes de instance_id e invariantes transacionais conforme §7.

Procedimento antes de declarar verde:

0. (Adição §10.A) Antes de tocar código, rodar a verificação automatizada do §6
   e confirmar 13 matches iniciais (10 + 1 + 1 + 1 = 13 SQL diretos), todos
   distribuídos apenas nos 4 routers alvo. Se aparecer site fora dos 4 routers
   ou contagem diferente, parar e escalar para o Arquiteto antes de implementar
   (alguém pode ter commitado INSERT novo entre a pré-verificação CODEX e o
   início da implementação).
1. Adicionar imports de registrar_evento_ledger e get_instance_id_conn nos 4 routers necessários.
2. Migrar pedidos_exame.py: 10 INSERTs diretos + 5 outboxes adjacentes.
3. Migrar laudos.py: helper _evento + todos os callers.
4. Migrar agendamentos.py: helper _gravar_evento_agendamento + todos os callers, respeitando outlier evento/payload.
5. Migrar circulacao_diagnostica.py: helper _gravar_evento + todos os callers.
6. Rodar a verificação automatizada do §6. Esperado: zero matches.
7. Rodar testes focados e regressões do §7.
8. NÃO COMITAR antes de revisão do Arquiteto.

Não fazer:
- backfill;
- alteração dos 4 models principais;
- outbox novo;
- renomeação de eventos;
- padronização física das colunas dos ledgers;
- mudança de estados, payloads, custódia ou semântica clínica.
```

---

## §10 Adições Arquiteto (rodada 2 — 2026-05-11)

Após CODEX redigir o ticket (rodada 1), o Arquiteto validou a pré-verificação via `grep` (confirmou 13 sites e 0 INSERTs externos) e adicionou 3 itens. Pontos para Code aplicar:

### §10.A — Validação automatizada pré-implementação obrigatória

A 4D.1 descobriu na rodada 3 (durante implementação) que `auth.py` tinha 2 sites adicionais não mapeados pelo CODEX. Para evitar repetição:

**Antes de tocar código**, o Code deve rodar a verificação automatizada do §6 e confirmar:

- Total: **13 matches** (10 em pedidos_exame.py + 1 em laudos.py + 1 em agendamentos.py + 1 em circulacao_diagnostica.py)
- Distribuição: **apenas nos 4 routers alvo**

Se aparecer site fora dos 4 routers (ou contagem diferente), **parar e escalar para o Arquiteto** antes de implementar. Provavelmente alguém commitou INSERT novo entre a pré-verificação CODEX e o início da implementação.

Esta verificação inicial é o **passo 0** do procedimento §9 (adicionado nesta rodada).

### §10.B — Testes E2E ledger+outbox por subdomínio

A 4D.1 entregou `test_ledger_e_outbox_compartilham_instance_id` para o subdomínio prescrição (invariante forense: mesma instância na ledger e no outbox). A 4D.2 precisa de testes equivalentes para 3 dos 4 subdomínios que têm outbox:

```
test_pedido_exame_ledger_e_outbox_compartilham_instance_id
  # POST /pedidos-exame → pedido_emitido tem mesmo instance_id no
  # outbox eventos_publicacao com objeto_tipo='pedido_exame'

test_laudo_ledger_e_outbox_compartilham_instance_id
  # POST /laudos → laudo_criado tem mesmo instance_id no outbox

test_agendamento_ledger_e_outbox_compartilham_instance_id
  # POST /agendamentos → agendamento_criado tem mesmo instance_id no
  # outbox (importante porque agendamento_eventos é o outlier do schema —
  # validar que o mapping no _LEDGER_SCHEMA preserva coerência forense)
```

**Circulação diagnóstica não tem outbox adjacente** (§4.4) — não precisa deste teste para o subdomínio circulação.

São 3 testes a mais (totalizando ~13 testes obrigatórios contra os ~10 listados no §7 original).

### §10.C — Densidade do escopo: 13 sites SQL ≠ 13 eventos de negócio

A contagem oficial é **13 sites SQL brutos** (métrica de migração), mas a 4D.2 tem distribuição assimétrica de complexidade entre os 4 routers:

| Router | Sites SQL | Eventos de negócio totais | Razão |
|---|---:|---:|---|
| `pedidos_exame.py` | 10 | 10 | 1:1 (sem helper local) |
| `laudos.py` | 1 | 11 | via `_evento` |
| `agendamentos.py` | 1 | 8 | via `_gravar_evento_agendamento` |
| `circulacao_diagnostica.py` | 1 | 7 | via `_gravar_evento` |
| **Total** | **13** | **36** | — |

**Implicação prática para o Code:**

- Em `pedidos_exame.py` (sem helper), cada SQL é uma migração independente. Se algum INSERT for esquecido, o `grep` da §6 pega na verificação final.
- Em `laudos.py`, `agendamentos.py`, `circulacao_diagnostica.py`, a migração do **único INSERT** dentro do helper local automaticamente afeta todos os callers do helper. Mas **cada caller** precisa ser atualizado para passar `instance_id` ao helper. Sem isso, o helper recebe `None` ou erro de assinatura.

Risco: aplicar fix em `_evento(...)` mas esquecer de atualizar 11 callers. O linter/type-checker (se ativo) deve pegar — mas vale o Code rodar `pytest` cedo durante a implementação para detectar callers órfãos.

**Sugestão de ordem do passo 1 do procedimento §9:**

```text
Para cada um dos 4 routers:
  1.a  Adicionar imports
  1.b  (Se tem helper local) Migrar o helper PRIMEIRO,
       adicionando parâmetro instance_id keyword-only
  1.c  Atualizar TODOS os callers do helper para passar instance_id
  1.d  Rodar pytest do router (rápido) para detectar callers órfãos
       antes de prosseguir ao próximo router
```

---

## §11 Ciclo da 4D.2 (rastreabilidade)

| Rodada | Origem | Pontos | Aceitos | Adaptados | Rejeitados |
|---|---|---|---|---|---|
| 1 | CODEX redigiu ticket completo (9 seções) | — | — | — | — |
| 2 | Arquiteto validou + adicionou §10 (3 itens) | 3 + 4 respostas §8 | 7 | 0 | 0 |
| 3 | CODEX revisou rodada 2 — aprovou com 1 lapidação P1 textual | 1 | 0 | 1 | 0 |
| **Total acumulado** | — | — | **7** | **1** | **0** |

---

## §12 Aprovação CODEX rodada 3 (2026-05-11)

CODEX revisou as adições §10 do Arquiteto e aprovou o ticket para
implementação com 1 lapidação P1 textual e nenhum achado material.

### Lapidação aplicada

**[P1 textual]** O passo 0 do §9 dizia "confirmar **14** matches iniciais"
quando a contagem correta é **13** (10 + 1 + 1 + 1). Risco: se Code seguir
literalmente "contagem diferente = parar", pararia indevidamente diante
do resultado correto.

**Aplicado** no §9 nesta rodada: "14" → "13" + reescrita do parágrafo
para deixar a regra clara (contagem 13, distribuição nos 4 routers
alvo, escalar para Arquiteto se diferente).

### Avaliação das adições §10 (rodada 2 do Arquiteto)

| Item | Decisão CODEX | Comentário |
|---|---|---|
| §10.A — passo 0 pré-implementação | ✅ Aceito (com lapidação textual acima) | `grep` adequado: `.py`, ignora `__pycache__`, roda em `routers/` inteiro |
| §10.B — 3 testes ledger+outbox | ✅ Aceito | Cobre o invariante crítico; teste de agendamento explicita bem o outlier |
| §10.C — densidade 13 SQL ≠ 36 eventos | ✅ Aceito | Não expande escopo; alinhado com a implementação real |

### Confirmações independentes do CODEX

- Pré-verificação refeita: **13 matches**, todos nos 4 routers alvo
- Nenhum INSERT externo em outros routers
- Nenhum drift latente novo identificado nos 4 ledgers (único outlier
  é `agendamento_eventos`, já tratado pelo `_LEDGER_SCHEMA`)
- `criar_pedido_exame` usa `with get_tx()` — **não precisa snippet
  especial** como `criar_prescricao` da 4D.1 (que usava `get_conn()`
  manual). Basta obter `instance_id` dentro do `with`, antes do
  primeiro evento.

### Veredito CODEX

> "Aplicar a lapidação P1 (`14` → `13`) e liberar para implementação.
> Depois disso: **ticket está pronto para implementação**."

### Status

**Ticket aprovado para implementação.** Próximo passo: Arquiteto redige
prompt para Code (`TICKET-4D-2-PROMPT-CODE.md`).
