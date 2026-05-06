# G4A — Event Publishing Layer (Publicação de Eventos)

**Classificação:** `module` — nova capacidade de infraestrutura; não altera ledger, núcleo nem semântica clínica.

**Pré-requisito cumprido:** PicSaúde possui múltiplos objetos sanitários com ledger imutável
(prescrição, custódia, pedido de exame, laudo, agendamento). A G4A expõe esses eventos externamente
de forma controlada.

---

## 1. Problema

O PicSaúde é **event-sourced internamente** (ledger imutável em `*_eventos`) mas
**não é event-driven externamente** — não há mecanismo de consumo externo.

Sem G4A, qualquer adapter (HIS, LIS, TISS, HL7, e-SUS, farmácias) precisaria:
- Acesso direto ao banco (violação do §10/adapter)
- Polling de tabelas clínicas (violação do §10/adapter)
- Integração ad-hoc sem contrato estável

**G4A resolve isso** expondo eventos via API HTTP controlada com formato canônico.

---

## 2. Princípios obrigatórios

1. **Núcleo não depende de consumidores externos** — falha de publicação nunca impacta fluxo clínico
2. **Outbox é append-only** — sem UPDATE, sem DELETE em `eventos_publicacao`
3. **Publicação é assíncrona** — ledger interno é a fonte de verdade; outbox é derivação
4. **Adapters nunca escrevem no banco clínico** — G4A é saída, não entrada
5. **Escopo por org_id** — evento de uma organização nunca vaza para outra
6. **Sem fila pesada no MVP** — polling HTTP simples (Kafka/Redis = G4B)

---

## 3. Padrão: Outbox + Polling HTTP

```
┌─────────────────────────────────────────────────────────────────┐
│                         PicSaúde Core                           │
│                                                                 │
│  [router action]                                                │
│       ├── INSERT → prescricao_eventos (ledger imutável)         │
│       └── INSERT → eventos_publicacao (outbox)                  │
│                           │                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                     GET /eventos?org_id=...&desde=...
                            │
               ┌────────────▼────────────┐
               │    Adapter externo      │
               │  (HIS / LIS / e-SUS…)  │
               │                        │
               │  POST /eventos/{id}/ack │
               └─────────────────────────┘
```

---

## 4. Tabela `eventos_publicacao`

```sql
CREATE TABLE eventos_publicacao (
    id           TEXT PRIMARY KEY,          -- "evt_" + UUID
    tipo_evento  TEXT NOT NULL,             -- ex: "agendamento_realizado"
    objeto_tipo  TEXT NOT NULL,             -- prescricao | pedido_exame | agendamento | laudo
    objeto_id    TEXT NOT NULL,             -- protocolo UUID do objeto
    payload      TEXT NOT NULL,             -- JSON com contexto do evento
    org_id       TEXT,                      -- NULL = sem escopo institucional
    unidade_id   TEXT,                      -- NULL = sem escopo de unidade
    publicado    INTEGER NOT NULL DEFAULT 0, -- 0 = pendente, 1 = consumido
    tentativas   INTEGER NOT NULL DEFAULT 0,
    criado_em    TEXT NOT NULL,             -- ISO 8601 UTC
    publicado_em TEXT                       -- NULL até ack
);
```

**Invariantes:**
- `id` nunca muda após inserção
- `publicado` vai de 0 → 1 via `POST /eventos/{id}/ack` — nunca volta
- Sem UPDATE de conteúdo, sem DELETE
- `org_id = NULL` em eventos de objetos sem escopo institucional obrigatório (ex: prescrições legadas)

---

## 5. Payload canônico

```json
{
  "id":          "evt_<uuid>",
  "tipo_evento": "agendamento_realizado",
  "objeto": {
    "tipo": "agendamento",
    "id":   "<protocolo_uuid>"
  },
  "org_id":      "LAB-TESTE",
  "unidade_id":  "UNIDADE-001",
  "timestamp":   "2026-03-20T14:00:00Z",
  "payload":     { ... }
}
```

---

## 6. Endpoints

### `GET /eventos`

Retorna eventos pendentes (ou todos, se `incluir_consumidos=true`) para o org_id do chamador.

**Query params:**

| Param | Tipo | Default | Descrição |
|---|---|---|---|
| `org_id` | string | obrigatório* | Filtro institucional |
| `desde` | ISO 8601 | nenhum | Retorna eventos após este timestamp |
| `limite` | int | 100 | Máximo 500 |
| `incluir_consumidos` | bool | false | Inclui eventos já acked |
| `objeto_tipo` | string | nenhum | Filtro por tipo de objeto |

*Admin pode omitir `org_id` para consulta global.

**Segurança MVP:** requer role `admin`.
**Segurança G4B:** role `integrador` com `org_id` derivado do JWT (onboarding institucional).

**Resposta:**
```json
{
  "eventos": [ ... ],
  "total": 42,
  "proximo_cursor": "2026-03-20T14:30:00Z"
}
```

### `POST /eventos/{id}/ack`

Marca evento como consumido. Idempotente — ack duplo não gera erro.

**Resposta:** `200 { "ok": true, "publicado_em": "..." }`

---

## 7. Cobertura de eventos no MVP

| Objeto | Eventos publicados no outbox |
|---|---|
| `prescricao` | `prescricao_emitida`, `prescricao_impressa`, `encerrada_localmente` |
| `custodia` | `custodia_transferida` |
| `pedido_exame` | `pedido_emitido`, `pedido_coletado`, `resultado_registrado`, `pedido_cancelado`, `pedido_encerrado` |
| `laudo` | `laudo_emitido`, `laudo_assinado`, `laudo_liberado`, `ciencia_registrada`, `laudo_encerrado` |
| `agendamento` | todos os 7 eventos (criado, confirmado, realizado, cancelado, nao_compareceu, remarcado + criado-remarcacao) |

---

## 8. Decisões de design

| Decisão | Justificativa |
|---|---|
| Polling em vez de webhook | Simples para MVP; adapter controla cadência |
| Outbox separado (`eventos_publicacao`) | Não toca ledger clínico; falha de outbox é isolada |
| Ack manual pelo consumidor | Consumidor controla o que já processou |
| `publicado=0/1` sem re-entrega | MVP; at-least-once delivery = G4B |
| Sem `DELETE` | Auditoria completa; rastreabilidade de consumo |
| `org_id` nullable | Eventos de objetos sem escopo institucional (prescrições legadas) ficam acessíveis a admin |
| Role `admin` no MVP | Onboarding institucional não existe ainda; role `integrador` = G4B |

---

## 9. Fora de escopo (G4B)

- Webhooks por org_id (push)
- Retry automático com backoff
- At-least-once delivery garantida
- Role `integrador` com JWT institucional
- Streaming (SSE, WebSocket)
- Transformação para TISS / HL7 / FHIR
- Filas (Kafka, Redis, SQS)
- UI de integração

---

## 10. Impacto arquitetural

Com G4A, o PicSaúde passa de:

> "sistema que registra eventos internamente"

para:

> "infraestrutura que distribui eventos com governança"

Adapters podem ser construídos **sem acesso ao banco clínico**, respeitando o
contrato do §10 (`adapter NUNCA escreve diretamente em tabelas clínicas`).
