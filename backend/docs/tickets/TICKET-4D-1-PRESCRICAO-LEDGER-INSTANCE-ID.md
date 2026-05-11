# TICKET 4D.1 — Integrar `instance_id` no ledger de prescrição

> **Sub-tarefa 4D.1 do plano de produção** (`docs/PLANO-PRODUCAO-V2.md` §4)
> **Classe (AGENTS.md §10):** `core` — toca ledger imutável (`prescricao_eventos`)
> **Pacto:** Regra 2 estrita (ticket → CODEX → Claude Code → validação)
> **Predecessores:** 4A (`app/instance.py`), 4B (`4b1ce80a017d`), 4C (`registrar_evento_ledger`)
> **Sucessoras:** 4D.2 (subdomínios exame/laudo/agendamento/circulação), 4E (testes E2E), Etapa 8 / Task #5 (drift restante de models). **4D.3 dissolvida** — seus 2 sites em `auth.py` migraram para a 4D.1 por coerência de subdomínio.
> **Data:** 2026-05-10
> **Escopo final:** 7 routers, 21 sites (atualizado pós-rodada 3 — ver §10)

---

## 1. Contexto e objetivo

A 4C entregou o helper central `registrar_evento_ledger(conn, ..., instance_id=...)`
e a variante transacional `get_instance_id_conn(conn)`. A lacuna atual está nos
routers: os endpoints ainda fazem `INSERT INTO prescricao_eventos` manualmente,
sem preencher `instance_id`.

Esta sub-tarefa integra **somente o subdomínio prescrição**:

- tabela alvo: `prescricao_eventos`
- objeto sanitário do helper: `objeto_tipo="prescricao"`
- routers alvo: **7** (atualizado rodada 3 — `auth.py` adicionado)
- sites alvo: **21 `INSERT INTO prescricao_eventos`** (atualizado rodada 3 —
  Code descobriu 2 sites adicionais em `auth.py` via verificação automatizada
  do §6; classe de correção idêntica à §4.4, mesmo subdomínio)
- outbox: somente chamadas `registrar_outbox(...)` já adjacentes devem receber
  o mesmo `instance_id`

Não fazer backfill de eventos antigos. Backfill continua fora da Etapa 4D e fica
para a Etapa 8 antes do deploy público.

---

## 2. Decisão sobre os 4 models principais

**Não alinhar nesta sub-tarefa** os models principais:

- `Prescricao`
- `PedidoExame`
- `Laudo`
- `Agendamento`

Motivo: a 4D.1 escreve apenas no ledger (`prescricao_eventos`) e no outbox
adjacente. Ela não altera inserts das tabelas principais. Alinhar esses models
agora aumenta o escopo sem ganho funcional para 4D.1.

Registrar o drift restante para a **Etapa 8 / Task #5**, junto com o saneamento
consolidado model vs Alembic.

---

## 3. Regra de implementação

Em cada transação que grava evento no ledger:

```python
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn

instance_id = get_instance_id_conn(conn)

registrar_evento_ledger(
    conn,
    objeto_tipo="prescricao",
    objeto_id=prescricao_id,
    tipo_evento="...",
    instance_id=instance_id,
    payload={...},
    ator_tipo="...",
    ator_id="...",
)
```

Regras obrigatórias:

1. Chamar `get_instance_id_conn(conn)` **uma vez por transação clínica** que
   escreve no ledger.
2. Passar o mesmo `instance_id` para todas as chamadas
   `registrar_evento_ledger(...)` daquela transação.
3. Passar o mesmo `instance_id` para cada `registrar_outbox(...)` já existente
   na mesma transação.
4. Não adicionar outbox novo nesta sub-tarefa. Se algum router hoje não espelha
   no outbox, isso é débito G4A separado.
5. Não editar `prescricao_eventos` por SQL manual em nenhum dos 21 sites.
6. Não mudar semântica de estado, vocabulário de eventos, payloads ou regras de
   custódia/dispensação.
7. Não capturar/silenciar exceção do helper de ledger. Falha no ledger deve
   abortar a transação clínica.

---

## 4. Mapa completo dos 21 sites (rodada 3 — atualizado de 19)

### 4.1 `backend/app/routers/prescricoes.py` — 6 sites

| Linha atual | Evento | Ator | Observação |
|---:|---|---|---|
| 530 | `prescricao_emitida` | `prescritor` / `cns` | Também há `registrar_outbox`; passar `instance_id` para ambos |
| 566 | `custodia_transferida` | `prescritor` / `cns` | Entrega direta para carteira digital na emissão |
| 762 | `prescricao_impressa` | `prescritor` / `cns` | Fluxo físico; também há `registrar_outbox` |
| 779 | `encerrada_localmente` | `prescritor` / `cns` | Fluxo físico; também há `registrar_outbox` |
| 1120 | `circulacao_atomizada_ativada` | `paciente` / `cpf_paciente` | Tokenização atomizada |
| 1138 | `token_item_emitido` | `paciente` / `cpf_paciente` | Dentro de loop; reutilizar o mesmo `instance_id` da transação |

Notas específicas:

- `criar_prescricao` usa `conn = get_conn()` com `commit/rollback` manual. Obter
  `instance_id` dentro do `try`, depois de abrir a conexão e antes dos eventos.
- `criar_prescricao_fisica` e `ativar_circulacao_atomizada` usam `get_tx()`.
- No fluxo físico, os dois eventos (`prescricao_impressa` e
  `encerrada_localmente`) devem compartilhar o mesmo `instance_id`.

**Ordem exata em `criar_prescricao` (linha ~530)** — *adição rodada 2*:

```python
conn = get_conn()
try:
    # ... operações iniciais (INSERT em prescricoes, prescricao_itens, etc.)

    # Obter instance_id UMA VEZ, dentro do try, antes de qualquer evento.
    # Se get_conn falhou antes deste ponto, o try não é alcançado.
    instance_id = get_instance_id_conn(conn)

    # Primeiro evento (substitui linha 530):
    registrar_evento_ledger(conn, objeto_tipo="prescricao",
                            objeto_id=prescricao_id,
                            tipo_evento="prescricao_emitida",
                            instance_id=instance_id, ...)
    registrar_outbox(conn, ..., instance_id=instance_id)

    # Segundo evento, se carteira digital existir (substitui linha 566):
    if paciente_tem_wallet:
        registrar_evento_ledger(conn, ..., instance_id=instance_id, ...)

    conn.commit()
except Exception:
    conn.rollback()
    raise
finally:
    conn.close()
```

A chamada `get_instance_id_conn(conn)` **não** deve ficar antes do `try` (escapa
do escopo transacional) nem dentro de um `except` (não há transação ativa).

### 4.2 `backend/app/routers/receituarios.py` — 8 sites

| Linha atual | Evento | Ator | Observação |
|---:|---|---|---|
| 392 | `receituarios_gerados` | `prescritor` / `cns_token` | Persistência inicial dos receituários regulatórios |
| 424 | `todo_regulatorio` | `prescritor` / `cns_token` | Loop para `receita_retencao` |
| 698 | `receituarios_numerados` | `prescritor` / `cns_token` | Só quando `mudancas > 0` |
| 714 | `todo_regulatorio` | `prescritor` / `cns_token` | Loop de pendências de assinatura |
| 985 | `receituario_emitido` | `prescritor` / `cns_token` | Primeiro download/emissão lógica |
| 1012 | `todo_regulatorio` | `prescritor` / `cns_token` | Apenas adapter real |
| 1032 | `receituario_pdf_acessado` | `prescritor` / `cns_token` | Re-download; auditoria leve |
| 1261 | `pdf_assinado_pades` | `prescritor` / `cns_token` | Assinatura PAdES do PDF |

Notas específicas:

- Obter `instance_id` uma vez no início de cada bloco `with get_tx() as conn`
  que pode gravar evento.
- Nos loops de `todo_regulatorio`, não chamar `get_instance_id_conn` dentro do
  loop.

### 4.3 `backend/app/routers/assinaturas.py` — 1 site

| Linha atual | Evento | Ator | Observação |
|---:|---|---|---|
| 333 | `assinatura_registrada` | `prescritor` / `meta.get("assinatura_modo") or "sem_modo"` | Manter comportamento atual do `ator_id`, embora ele seja semanticamente fraco |

Nota específica:

- Não corrigir semântica do `ator_id` nesta sub-tarefa. O objetivo da 4D.1 é
  apenas substituir o INSERT pelo helper e preencher `instance_id`.

### 4.4 `backend/app/routers/solicitacoes.py` — 2 sites divergentes

Hoje estes 2 sites usam colunas que não existem no schema real de
`prescricao_eventos`:

```sql
INSERT INTO prescricao_eventos
       (prescricao_id, tipo_evento, dados_json, criado_em)
```

O schema/model correto usa `payload_json` e `created_at`, além de
`ator_tipo` obrigatório. A substituição pelo helper corrige esse bug latente.

| Linha atual | Evento | Ator proposto | Observação |
|---:|---|---|---|
| 104 | `renovacao_solicitada` | `paciente` / `cpf` | Paciente autenticado solicita renovação |
| 250 | `renovacao_atendida` ou `renovacao_recusada` | `prescritor` / `cns` | Só se `sol["prescricao_id"]` existir |

Critério explícito para os 2 sites:

- Remover o SQL manual divergente.
- Usar `payload={...}` com o mesmo conteúdo atual.
- Usar `ator_tipo`/`ator_id` conforme a tabela acima.
- Adicionar teste que falharia no comportamento antigo, verificando que o evento
  é persistido em `prescricao_eventos` com `payload_json`, `created_at`,
  `ator_tipo`, `ator_id` e `instance_id`.

### 4.5 `backend/app/routers/custodia.py` — 1 site físico, 3 eventos de negócio

| Linha atual | Evento | Ator | Observação |
|---:|---|---|---|
| 163 | variável em `_gravar_evento(...)` | parâmetros do helper local | Substituir corpo de `_gravar_evento` por `registrar_evento_ledger` |

Callers atuais:

| Linha atual | Evento | Ator |
|---:|---|---|
| 334 | `custodia_transferida` | `payload.de` / `de_id` |
| 540 | `item_dispensado` | `dispensador` / `cnpj` |
| 592 | `item_devolvido` | `dispensador` / `"sistema"` |

Implementação recomendada:

- Alterar assinatura de `_gravar_evento(...)` para receber `instance_id`.
- Cada endpoint que chama `_gravar_evento(...)` deve obter `instance_id` uma vez
  dentro do respectivo `with get_tx() as conn`.
- Não alterar a lógica de recalcular status, saldo ou custódia.

### 4.6 `backend/app/routers/hospitalares.py` — 1 site físico, 1 evento de negócio

| Linha atual | Evento | Ator | Observação |
|---:|---|---|---|
| 180 | variável em `_gravar_evento(...)` | parâmetros do helper local | Substituir corpo de `_gravar_evento` por `registrar_evento_ledger` |

Caller atual:

| Linha atual | Evento | Ator |
|---:|---|---|
| 401 | `dispensacao_hospitalar_registrada` | `dispensador` / `payload.unidade_id` |

Implementação recomendada:

- Alterar assinatura de `_gravar_evento(...)` para receber `instance_id`.
- No endpoint hospitalar, obter `instance_id` uma vez dentro do `with get_tx()`
  e repassar ao helper local.
- Preservar o guardrail institucional existente em `dispensacoes_hospitalares`
  (`org_id`/`unidade_id` obrigatórios). Não adicionar `org_id` ao ledger.

### 4.7 `backend/app/routers/auth.py` — 2 sites divergentes (adição rodada 3)

**Descoberto pelo Claude Code via verificação automatizada do §6** durante a
implementação. Mesma classe de bug latente que §4.4 (`solicitacoes.py`):
schema divergente que viola `ator_tipo NOT NULL` em produção.

Hoje estes 2 sites usam colunas que não existem no schema real de
`prescricao_eventos`:

```sql
INSERT INTO prescricao_eventos
       (prescricao_id, tipo_evento, dados_json, criado_em)
```

O schema/model correto usa `payload_json` e `created_at`, além de
`ator_tipo` obrigatório. A substituição pelo helper corrige o bug latente:
em produção, ambos os endpoints **falham transacionalmente** sob
`with get_tx() as conn` — `IntegrityError` propaga e a transação é
revertida (refinamento textual da rodada 4 — "silenciosamente" era
impreciso; sob `get_tx()` o erro é propagado, não silenciado).

**Ambos os endpoints são do app cidadão** (`require_role("paciente")`) e
estão **quebrados em produção hoje** — qualquer paciente que tente
"transferir para farmácia" ou "devolver para prescritor" falha.

**Drift adicional em `prescricao_custodia` (CODEX rodada 4 — P1.2).**
Antes do INSERT no ledger, ambos os endpoints inserem em
`prescricao_custodia` usando coluna inexistente `iniciada_em`
(linhas 221 e 292 em `auth.py`). O schema real tem `transferida_em`,
`encerrada_em`, `motivo`, `created_at` — não `iniciada_em`.

Logo, esses fluxos falham ANTES de chegar no INSERT em
`prescricao_eventos` que esta sub-tarefa migra. Sem fix em
`prescricao_custodia`, o teste E2E do paciente continuaria quebrado
mesmo após a migração ao helper — corrigir só `prescricao_eventos`
seria fix incompleto.

**Fix mínimo de schema** (escopo bem delimitado, mesma classe):

- Renomear `iniciada_em` → `transferida_em` nos 2 INSERTs em
  `prescricao_custodia` (linhas 221 e 292 em `auth.py`).
- **Não tocar** em outras colunas, lógica de custódia, ou regras de
  estado. Só renomear a coluna para o nome real do schema.
- Esta correção fica neste mesmo ticket (não vira sub-ticket) porque
  é o mesmo subdomínio, mesma classe de bug, e bloqueia o E2E que
  precisamos para validar a migração ao helper.

| Linha atual | Endpoint | Evento | Ator |
|---:|---|---|---|
| 233 | `POST /paciente/prescricoes/{proto}/transferir-farmacia` | `custodia_transferida` | `paciente` / `cpf` (do `usuario["sub"]`) |
| 313 | `POST /paciente/prescricoes/{proto}/devolver-prescritor` | `custodia_transferida` | `paciente` / `cpf` (do `usuario["sub"]`) |

**Critério explícito para os 2 sites:**

- Remover o SQL manual divergente.
- Usar `registrar_evento_ledger(conn, objeto_tipo="prescricao", ...)` com o
  mesmo conteúdo do `payload` (transferir: `{"de", "de_id", "para",
  "para_id", "origem"}`; devolver: idem + `"motivo"`).
- Usar `ator_tipo="paciente"`, `ator_id=cpf` em ambos.
- Ambos os endpoints rodam dentro de `with get_tx() as conn` — obter
  `instance_id = get_instance_id_conn(conn)` uma vez no início de cada
  bloco.
- **Sem outbox novo** — esses 2 endpoints não têm `registrar_outbox`
  adjacente hoje. Adicionar outbox aqui é débito G4A separado, fora do
  escopo da 4D.1.
- **Adicionar teste E2E** para ambos os endpoints, verificando que o
  evento é persistido com `payload_json`, `created_at`, `ator_tipo`,
  `ator_id` e `instance_id` UUID v4. Sem este teste, o bug latente que
  estamos corrigindo passa despercebido.

---

## 5. Escopo fora deste ticket

Não fazer nesta sub-tarefa:

- Backfill de `instance_id` em eventos pré-existentes.
- Alinhamento dos 4 models principais (`Prescricao`, `PedidoExame`, `Laudo`,
  `Agendamento`).
- Padronização global de nomes de colunas dos outros ledgers
  (`dados_json`/`payload`, `criado_em`/`created_at`, `evento`/`tipo_evento`).
- Adição de outbox em routers que hoje não chamam `registrar_outbox`.
- Alteração de vocabulário de eventos.
- Alteração de regras de estado, custódia, dispensação parcial ou fluxo físico.
- Alteração de assinatura pública de `registrar_evento_ledger`,
  `get_instance_id_conn` ou `registrar_outbox`.

---

## 6. Critérios de aceitação

### Geral

- Não resta nenhum `INSERT INTO prescricao_eventos` manual nos 7 routers alvo.
  **Verificação automatizada** (adição rodada 2, refinada rodada 4):
  ```bash
  # Restringe a .py e ignora __pycache__ (CODEX rodada 4 P2 —
  # versão anterior pegava binários .pyc):
  grep -RInI --include='*.py' --exclude-dir='__pycache__' \
    "INSERT INTO prescricao_eventos" backend/app/routers/
  ```
  Equivalente com `ripgrep` (preferido se disponível):
  ```bash
  rg -n --glob '*.py' 'INSERT INTO prescricao_eventos' backend/app/routers
  ```
  Esperado: zero matches. Esta verificação é um **passo obrigatório do
  procedimento** antes de declarar verde.
- Todo evento novo em `prescricao_eventos` criado pelos endpoints da 4D.1 tem
  `instance_id` não nulo e UUID v4 válido.
- Todos os eventos de uma mesma transação clínica compartilham o mesmo
  `instance_id`. Coberto pelos testes "Invariantes transacionais" em §7.
- Toda chamada `registrar_outbox(...)` já existente nos sites alterados recebe
  o mesmo `instance_id` do ledger. Coberto pelo teste
  `test_ledger_e_outbox_compartilham_instance_id` em §7.
- Falha em `registrar_evento_ledger(...)` aborta a transação clínica.
- Payloads continuam serializados com `ensure_ascii=False` e preservam o mesmo
  conteúdo lógico.

### Por router

- `prescricoes.py`: 6 sites migrados; os 3 outboxes existentes recebem
  `instance_id`; fluxo físico mantém exatamente 2 eventos no ledger.
- `receituarios.py`: 8 sites migrados; loops reutilizam `instance_id` sem
  chamadas repetidas a `get_instance_id_conn`.
- `assinaturas.py`: 1 site migrado; comportamento de criação/atualização de
  metadados permanece igual.
- `solicitacoes.py`: 2 sites divergentes corrigidos; eventos de renovação passam
  a ser persistidos com schema real de `prescricao_eventos`.
- `custodia.py`: `_gravar_evento` usa o helper; os 3 callers passam
  `instance_id`.
- `hospitalares.py`: `_gravar_evento` usa o helper; o caller passa
  `instance_id`; nenhum guardrail institucional é relaxado.
- `auth.py` (rodada 3): 2 sites divergentes corrigidos; eventos
  `custodia_transferida` do app cidadão passam a ser persistidos com
  schema real (`payload_json`, `created_at`, `ator_tipo='paciente'`,
  `ator_id=cpf`, `instance_id`).

---

## 7. Testes obrigatórios

### Testes focados novos/ajustados

Adicionar ou ajustar testes que verifiquem `instance_id` em:

- `POST /prescricoes` → `prescricao_emitida`
- `POST /prescricoes/fisica` → `prescricao_impressa` e
  `encerrada_localmente`, ambos com o mesmo `instance_id`
- entrega direta à carteira digital → `custodia_transferida`
- atomização → `circulacao_atomizada_ativada` + N `token_item_emitido`, todos
  com o mesmo `instance_id`
- geração/numerização/emissão/acesso/assinatura de receituários, cobrindo ao
  menos um evento por bloco transacional
- `POST /prescricoes/{proto}/assinatura` → `assinatura_registrada`
- `solicitar_renovacao` → `renovacao_solicitada`
- `responder_solicitacao` → `renovacao_atendida` e/ou `renovacao_recusada`
- custódia/dispensação/devolução → eventos emitidos via `_gravar_evento`
- dispensação hospitalar → `dispensacao_hospitalar_registrada`
- **(rodada 3)** `POST /paciente/prescricoes/{proto}/transferir-farmacia`
  → `custodia_transferida` com `ator_tipo='paciente'`, `ator_id=cpf`,
  `payload_json` válido e `instance_id` UUID v4 (era bug latente em produção)
- **(rodada 3)** `POST /paciente/prescricoes/{proto}/devolver-prescritor`
  → idem (era bug latente em produção)

### Invariantes transacionais (CRÍTICO — adição rodada 2)

A invariante §6.3 ("todos os eventos de uma mesma transação clínica
compartilham o mesmo `instance_id`") precisa de oráculo verificável. Sem
este teste, é possível que sites distintos chamem `get_instance_id_conn`
duas vezes na mesma transação (caso `_validar_uuid_v4` use semente aleatória
em first boot concorrente entre threads, por exemplo) e a invariante
quebre silenciosamente — o critério passa visualmente sem detecção.

Adicionar pelo menos **1 teste E2E por subdomínio com múltiplos eventos**:

1. **Atomização** (cenário mais denso — 1 + N eventos):
   ```python
   def test_atomizacao_eventos_compartilham_instance_id(client, db_path):
       """
       POST /prescricoes/{proto}/atomizar com 3 itens gera:
         - 1 evento 'circulacao_atomizada_ativada'
         - 3 eventos 'token_item_emitido'
       Todos os 4 eventos DEVEM ter o mesmo instance_id (invariante
       forense — preserva correspondência rastreável dentro de uma
       única operação clínica).
       """
       # ... emitir prescrição → ativar atomização com 3 itens
       eventos = conn.execute(
           "SELECT instance_id FROM prescricao_eventos "
           "WHERE prescricao_id = ? AND tipo_evento IN "
           "('circulacao_atomizada_ativada', 'token_item_emitido')",
           (prescricao_id,),
       ).fetchall()
       assert len(eventos) == 4
       iids = {e["instance_id"] for e in eventos}
       assert len(iids) == 1, (
           f"Invariante quebrada: eventos com instance_ids divergentes: {iids}"
       )
   ```

2. **Fluxo físico** (2 eventos em sequência — `prescricao_impressa` +
   `encerrada_localmente`):
   ```python
   def test_fluxo_fisico_dois_eventos_mesmo_instance_id(client, db_path):
       """POST /prescricoes/fisica grava 2 eventos no ledger. Ambos
       compartilham o mesmo instance_id."""
       # ... idem padrão acima
   ```

3. **Ledger + outbox** (invariante §6.4 — `registrar_outbox` recebe o mesmo
   `instance_id` do ledger):
   ```python
   def test_ledger_e_outbox_compartilham_instance_id(client, db_path):
       """
       Após POST /prescricoes, lê instance_id de prescricao_eventos +
       de eventos_publicacao para o mesmo objeto. Devem ser iguais.
       """
       iid_ledger = conn.execute(
           "SELECT instance_id FROM prescricao_eventos "
           "WHERE prescricao_id = ? AND tipo_evento = 'prescricao_emitida'",
           (prescricao_id,),
       ).fetchone()["instance_id"]
       iid_outbox = conn.execute(
           "SELECT instance_id FROM eventos_publicacao "
           "WHERE objeto_tipo = 'prescricao' AND objeto_id = ?",
           (protocolo,),
       ).fetchone()["instance_id"]
       assert iid_ledger == iid_outbox
   ```

### Regressões já existentes que devem continuar verdes

Rodar pelo menos:

```bash
cd backend
python3 -m pytest tests/test_ledger_helper.py
python3 -m pytest tests/test_migration_4b_instance_id.py
python3 -m pytest tests/test_eventos_publicacao.py
python3 -m pytest tests/integration/test_prescricoes.py
python3 -m pytest tests/test_atomizacao.py
python3 -m pytest tests/test_dispensacao_atomizada.py
python3 -m pytest tests/integration/test_receituarios.py
python3 -m pytest tests/integration/test_pdf_receituario.py
python3 -m pytest tests/integration/test_pdf_assinatura.py
python3 -m pytest tests/test_dispensacao_hospitalar.py
```

Se algum teste legado de `solicitacoes.py` assumia ausência de evento por causa
do SQL quebrado, atualizar a expectativa: o comportamento correto é persistir o
evento no ledger com o schema real.

---

## 8. Perguntas para CODEX

1. Confirmar se, em `assinaturas.py`, a 4D.1 deve preservar o `ator_id` atual
   (`meta.get("assinatura_modo") or "sem_modo"`) ou se já devemos corrigir para
   o CNS do prescritor autenticado. Recomendação deste ticket: preservar para
   manter escopo estrito.
2. Confirmar se eventos de `solicitacoes.py` devem entrar no outbox agora.
   Recomendação deste ticket: não adicionar outbox novo em 4D.1; corrigir
   apenas ledger + `instance_id`.
3. Confirmar se `item_devolvido` em `custodia.py` deve permanecer como está ou
   ser harmonizado futuramente com o vocabulário de AGENTS.md
   (`item_devolvido_paciente` / `item_devolvido_prescritor`). Recomendação:
   não renomear na 4D.1.
4. Confirmar que os 4 models principais ficam para Etapa 8 / Task #5, sem
   alteração nesta sub-tarefa.

---

## 9. Prompt sugerido para implementação

```
Implementar TICKET-4D-1-PRESCRICAO-LEDGER-INSTANCE-ID.md.

Classificação: core. Regra 2 estrita.

Escopo:
- migrar os 21 INSERTs manuais em prescricao_eventos nos 7 routers listados
  para registrar_evento_ledger(..., objeto_tipo="prescricao", instance_id=...);
- corrigir os 2 INSERTs em prescricao_custodia em auth.py (usam coluna
  inexistente `iniciada_em` — schema real é `transferida_em`); fix mínimo
  de schema, sem mudar semântica;
- chamar get_instance_id_conn(conn) uma vez por transação clínica que grava
  ledger;
- passar o mesmo instance_id para registrar_outbox já existente;
- corrigir os 2 INSERTs divergentes em solicitacoes.py usando ator_tipo/ator_id;
- adicionar/ajustar testes de instance_id conforme §7, incluindo os 3 testes
  de invariantes transacionais (atomização, fluxo físico, ledger+outbox).

Procedimento (antes de declarar verde):
1. Aplicar mudanças nos 7 routers + custodia._gravar_evento + hospitalares._gravar_evento + fix de schema em prescricao_custodia (auth.py:221, :292).
2. Rodar verificação automatizada (§6 Geral):
     grep -RInI --include='*.py' --exclude-dir='__pycache__' "INSERT INTO prescricao_eventos" backend/app/routers/
   Esperado: zero matches.
3. Rodar testes focados (§7) — incluindo os 3 testes de invariantes.
4. Rodar testes de regressão (§7) — todos verdes.
5. NÃO COMITAR. Engenheiro-Chefe valida o output antes do commit.

Não fazer:
- backfill;
- alterar os 4 models principais;
- adicionar outbox novo;
- renomear eventos;
- mudar regras de estados, custódia ou dispensação.
```

---

## 10. Adições Engenheiro-Chefe (rodada 2 — 2026-05-10)

Após CODEX redigir o ticket (rodada 1), o Engenheiro-Chefe validou e
adicionou 3 itens. Pontos para CODEX revisar nesta rodada 2:

| # | Adição | Onde |
|---|---|---|
| A | 3 testes E2E de **invariantes transacionais** (atomização / fluxo físico / ledger+outbox) com mesmo `instance_id` | §7, novo bloco "Invariantes transacionais (CRÍTICO)" |
| B | **Verificação automatizada** via `grep -rnE` no §6.1 + passo obrigatório no procedimento do §9 | §6 Geral + §9 Procedimento |
| C | **Snippet de ordem exata** em `criar_prescricao` (linha ~530) — `get_instance_id_conn` dentro do `try`, antes dos eventos | §4.1 Notas específicas |

**Pergunta para CODEX (rodada 2):**

1. Os 3 testes de invariantes em §7 cobrem o risco crítico? Falta algum
   cenário relevante (ex: receituarios.py com múltiplos eventos no mesmo
   `with get_tx`)?
2. O `grep` proposto no §6 filtra apenas comentários iniciados por `#`.
   Há risco de falso-positivo em strings/docstrings que mencionem
   `INSERT INTO prescricao_eventos`? Vale algum filtro adicional?
3. O snippet de ordem em §4.1 é suficiente, ou vale aplicar o mesmo padrão
   defensivo (`get_instance_id_conn` dentro do `try`) também em `criar_prescricao_fisica`
   e `ativar_circulacao_atomizada` (que usam `with get_tx()`)?

---

## 11. Ampliação de escopo (rodada 3 — 2026-05-10)

Durante a implementação, o Claude Code rodou a verificação automatizada
do §6 e descobriu **2 sites adicionais em `app/routers/auth.py`** não
mapeados na rodada 1. CODEX e Engenheiro-Chefe convergiram para
**ampliação 19 → 21 sites** (opção (a)).

### O que mudou nesta rodada

| Item | Antes (rodadas 1-2) | Agora (rodada 3) |
|---|---|---|
| Routers alvo | 6 | **7** (adiciona `auth.py`) |
| Sites alvo | 19 | **21** |
| 4D.3 (subdomínio "auth") | planejada | **dissolvida** — seus 2 sites são do subdomínio prescrição, vão para 4D.1 |
| Mapa | §4.1-§4.6 | + **§4.7 `auth.py`** (2 sites divergentes do app cidadão) |
| Bug em produção corrigido | apenas §4.4 (solicitacoes) | + §4.7 (transferir-farmacia, devolver-prescritor) |

### Por que ampliar é a opção correta (sumário dos argumentos)

- **Coerência de subdomínio.** Os 2 sites em `auth.py` escrevem em
  `prescricao_eventos`. Faseamento da 4D era por subdomínio, não por
  arquivo — o mapeamento original "auth = 4D.3 isolado" era erro de
  agrupamento.
- **Bug em produção é grave.** Ambos os endpoints (`/paciente/.../transferir-farmacia`
  e `/paciente/.../devolver-prescritor`) violam `ator_tipo NOT NULL` no
  schema real — usuário cidadão tem fluxos quebrados. Deixar para
  próxima fase é manter o impacto.
- **Mesma classe de fix que §4.4.** Schema divergente idêntico ao de
  `solicitacoes.py`. Aplicar o helper resolve os dois de uma vez —
  coerência, não extensão.
- **A verificação automatizada do §6 já presumia isso.** O `grep` cobre
  `backend/app/routers/` inteiro; excluir `auth.py` enfraqueceria o
  guardrail (rejeitamos opção (b) por isso).

### Resumo do ciclo da 4D.1

| Rodada | Origem | Pontos | Aceitos | Adaptados | Rejeitados |
|---|---|---|---|---|---|
| 1 | CODEX redigiu ticket original | Estrutura completa (9 seções) | — | — | — |
| 2 | Eng-Chefe validou e adicionou (A, B, C) | 3 adições | 3 | 0 | 0 |
| 3 | Code descobriu 2 sites via verificação §6 | Ampliação 19→21 | 1 | 0 | 0 |
| 4 | CODEX revisou ticket pós-ampliação | 4 ajustes (P1.1, P1.2, P2, P3) | 4 | 0 | 0 |
| **Total** | — | — | **8** | **0** | **0** |

---

## 12. Lapidações finais (rodada 4 — 2026-05-10)

CODEX revisou o ticket pós-rodada 3 (antes do Code prosseguir com os 21
sites) e detectou 4 ajustes. Todos aceitos.

### P1.1 — Contradições remanescentes

4 linhas ainda mencionavam "19 sites" ou "6 routers" mesmo após a
rodada 3:

| Linha | Antes | Depois |
|---|---|---|
| §3 Regra 5 | "nenhum dos 19 sites" | "nenhum dos 21 sites" |
| §6 Geral | "nos 6 routers alvo" | "nos 7 routers alvo" |
| §9 Escopo (prompt) | "19 INSERTs ... 6 routers listados" | "21 INSERTs ... 7 routers listados" |
| §9 Procedimento | "Aplicar mudanças nos 6 routers" | "nos 7 routers" |

### P1.2 — Drift adicional em `prescricao_custodia` (CRÍTICO)

Os 2 endpoints novos no escopo (`auth.py:221` e `:292`) inserem em
`prescricao_custodia` usando coluna inexistente `iniciada_em`. O schema
real tem `transferida_em` (verificado em `app/models/prescricao_custodia.py:37`).

**Impacto:** os 2 fluxos do app cidadão (transferir-farmacia,
devolver-prescritor) falham ANTES de chegar no INSERT em
`prescricao_eventos` que a 4D.1 migra. Sem fix em `prescricao_custodia`,
o E2E continua quebrado — corrigir só `prescricao_eventos` seria fix
incompleto.

**Aplicado em §4.7**: fix mínimo de schema (renomear `iniciada_em` →
`transferida_em` nos 2 INSERTs). Sem mudança em outra lógica, sem
alteração de regras de custódia. Mesma classe de bug que §4.4 e
§4.7 (drift schema), mesmo subdomínio.

### P2 — `grep` original podia pegar binários `.pyc`

Versão anterior:
```bash
grep -rnE "INSERT INTO prescricao_eventos" backend/app/routers/
```

Pegava arquivos binários em `__pycache__`. Substituído em §6 e §9 por:

```bash
grep -RInI --include='*.py' --exclude-dir='__pycache__' \
  "INSERT INTO prescricao_eventos" backend/app/routers/
```

Alternativa com `ripgrep`:
```bash
rg -n --glob '*.py' 'INSERT INTO prescricao_eventos' backend/app/routers
```

### P3 — "Silenciosamente" impreciso

§4.7 dizia que o bug em `auth.py` "dispara `IntegrityError`
silenciosamente". Sob `with get_tx() as conn`, o comportamento real é
**rollback + exceção propagada** — visível ao operador, não silenciado.
Reescrito em §4.7 para "falham transacionalmente".

### Respostas às perguntas da rodada 2 (consolidadas)

1. **Os 3 testes de invariantes cobrem o risco crítico?** Sim, segundo
   CODEX rodada 4. Adicionar 1 teste multi-evento em `receituarios.py`
   se for barato (loops de `todo_regulatorio`) — recomendado, não
   bloqueante.
2. **Falso-positivo do `grep` em docstrings/strings?** Resolvido pela
   versão refinada com `--include='*.py' --exclude-dir='__pycache__'`.
3. **Snippet de ordem para `get_tx()`?** Suficiente o que está em §4.1
   para `criar_prescricao` (que usa `get_conn()` manual). Para outros
   endpoints que usam `with get_tx()`, basta a regra "dentro do bloco
   `with`, antes do primeiro evento" — sem snippet adicional.
