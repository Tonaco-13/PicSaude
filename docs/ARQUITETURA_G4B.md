# G4B — Adapter Layer

**Classificação:** `module` — nova camada de integração; não altera núcleo, ledger ou máquina de estados.
**Pré-requisito:** G4A (outbox + polling), Ticket 30 (prestadores formalizados).

---

## 1. Essência

A Adapter Layer no PicSaúde é:

> **Um consumidor institucional de eventos que traduz o modelo sanitário do PicSaúde para modelos operacionais externos — sem tocar no núcleo.**

---

## 2. Fluxo

```
PicSaúde Core
    ↓
eventos_publicacao  (outbox — imutável)
    ↓
GET /eventos        (API pública, filtrada por org_id)
    ↓
Adapter             (por prestador — consome, transforma, envia)
    ↓
Sistema externo     (HIS / LIS / TISS / e-SUS / etc.)
```

**Princípio:** 1 adapter por prestador (`org_id`). Adapters não compartilham credencial.

---

## 3. Autenticação institucional

### 3.1 Role `integrador`

Novo papel no RBAC, escopo por `org_id`:

| Role | Acesso a `/eventos` | Filtro de org_id |
|---|---|---|
| `admin` | Todos os eventos | Opcional (diagnóstico) |
| `integrador` | Apenas seu `org_id` | Obrigatório e imutável |

### 3.2 API Key institucional

Tabela `api_keys`:
```
id, org_id, nome, chave_hash (sha256), ativo, criado_em, criado_por
```

- Chave gerada com `secrets.token_urlsafe(32)` — retornada uma única vez na criação
- Armazenada como `sha256(chave)` — nunca em texto claro
- Autenticação via header: `X-Api-Key: <chave>`
- Criação e revogação: apenas `admin`

### 3.3 Fluxo de autenticação dupla

```
Request para /eventos ou /eventos/{id}/ack
    │
    ├─ X-Api-Key presente? → validar contra api_keys → role=integrador, org_id fixo
    │
    └─ Authorization: Bearer → JWT → role=admin ou role=integrador
```

---

## 4. Componentes do Adapter

### Obrigatórios (MVP)

| Componente | Responsabilidade |
|---|---|
| **Consumidor** | Polling em `GET /eventos?org_id=X&desde=<cursor>` |
| **Motor de idempotência** | Tabela local `eventos_processados` — chave: `evento_id` |
| **Transformador (mapper)** | Traduz payload canônico → formato externo por `tipo_evento` |
| **Conector de saída** | HTTP / arquivo / fila local — entrega ao sistema externo |
| **Log técnico** | Registra: sucesso, falha, tentativas, timestamps |

### Adapter de referência (implementado neste ticket)

**Adapter JSON Local:**
- Consome `/eventos` com API Key
- Salva eventos em arquivo JSON por org_id
- ACK correto após persistência
- Idempotência via SQLite local
- Executável standalone: `python3 adapter.py`

---

## 5. Ciclo de vida do evento

```
[1] Buscar evento          GET /eventos?org_id=X&desde=<cursor>
[2] Verificar idempotência evento_id em eventos_processados?
[3] Transformar            mapper(evento) → payload externo
[4] Enviar                 conector → sistema externo
[5] Registrar resultado    INSERT INTO eventos_processados
[6] ACK                    POST /eventos/{id}/ack
```

**Regra de ouro:** ACK só acontece DEPOIS de envio bem-sucedido.

---

## 6. Política de falha

| Situação | Ação |
|---|---|
| Falha no sistema externo | NÃO dar ack — evento permanece disponível |
| Falha de rede | Retry na próxima execução |
| Falha permanente | Log + intervenção humana |
| Evento inválido/desconhecido | Log + skip controlado (não travar) |

O PicSaúde:
- Não faz retry
- Não sabe do erro externo
- **Isso é proposital** — falha de integração não pode impactar fluxo clínico

---

## 7. Idempotência

**Chave:** `evento_id`

Tabela local do adapter (`eventos_processados`):
```sql
CREATE TABLE IF NOT EXISTS eventos_processados (
    evento_id     TEXT PRIMARY KEY,
    processado_em TEXT NOT NULL,
    resultado     TEXT NOT NULL    -- 'ok' | 'erro' | 'ignorado'
)
```

Se `evento_id` já existe → ignorar silenciosamente (não reprocessar).

---

## 8. Limites absolutos

```
Adapter NUNCA:
  ❌ escreve no banco do PicSaúde
  ❌ altera ledger (*_eventos)
  ❌ altera estados clínicos de objetos sanitários
  ❌ acessa SQLite diretamente
  ❌ compensa erro externo no core
  ❌ consome eventos de outro org_id

Adapter SEMPRE:
  ✅ consome via API (GET /eventos)
  ✅ ACK via API (POST /eventos/{id}/ack)
  ✅ mantém persistência local própria
  ✅ filtra por org_id
  ✅ é observável (log técnico)
  ✅ é idempotente
```

---

## 9. Vínculo com prestadores (Ticket 30)

- Cada adapter pertence a um `org_id` (formalmente cadastrado em `prestadores`)
- Pode filtrar opcionalmente por `unidade_id`
- API key é criada por admin vinculada ao `org_id` do prestador
- Um adapter nunca consome eventos de outro prestador

---

## 10. Tipos de adapter

### MVP implementado
- **JSON Local** — consome eventos, salva em arquivo JSON por org_id, ACK correto

### Futuros (implementar apenas quando houver caso de uso real)
- HIS hospitalar (ex: MV, Tasy)
- LIS laboratorial
- TISS/faturamento
- e-SUS / RNDS
- Exportação CSV

---

## 11. Classificação por tipo de mudança

| Componente | Classe |
|---|---|
| `api_keys` table + endpoints | `module` |
| Role `integrador` | `core` (RBAC) — revisão obrigatória neste ticket |
| Adapter JSON local | `adapter` — código isolado |
| Atualização do `/eventos` para integrador | `module` |

**Nota sobre role `integrador`:** embora seja `core` (RBAC), a adição é puramente aditiva — não modifica roles existentes, não altera contratos de endpoints existentes. Risco mínimo.
