# PicSaúde — Arquitetura do Objeto Sanitário Agendamento

> **Status:** Documento arquitetural ativo — v1.0
> **Ticket:** 28
> **Pré-requisitos:** NUCLEO_SANITARIO.md v1.1, ARQUITETURA_EXAMES.md,
> CLAUDE.md §6b (subdomínios institucionais), Tickets 14–17 (exame), 19–21 (laudo)
> **Propósito:** Definir o Agendamento como objeto sanitário leve do PicSaúde,
> fechando o elo entre pedido de exame, execução e laudo.

---

## Mapa rápido

| Tópico | Seção |
|---|---|
| Classificação no domínio PicSaúde | 1 |
| Relação com Pedido de Exame | 2 |
| Contrato do objeto Agendamento | 3 |
| Máquina de estados | 4 |
| Custódia — decisão e justificativa | 5 |
| Ledger de eventos | 6 |
| Integração com Exame — direção causal | 7 |
| Escopo institucional (org_id / unidade_id) | 8 |
| O que o Agendamento NÃO é | 9 |
| Fora do MVP | 10 |
| Checklist de aderência ao NUCLEO_SANITARIO.md | 11 |
| Conclusão — classificação final | 12 |
| Definição do Ticket 29 | 13 |

---

## 1. Classificação no domínio PicSaúde

**O Agendamento é um objeto sanitário leve.**

Esta é uma nova categoria no modelo de domínio do PicSaúde — distinta dos objetos sanitários completos (prescrição, pedido de exame, laudo) e dos subdomínios operacionais (dispensação hospitalar).

### Comparativo de categorias

| Dimensão | Objeto completo (ex: prescrição) | Objeto leve (ex: agendamento) | Subdomínio operacional (ex: disp. hospitalar) |
|---|---|---|---|
| Identidade própria (UUID) | ✓ | ✓ | ✗ — herda do objeto pai |
| Máquina de estados | ✓ | ✓ | ✗ — usa estados do pai |
| Ledger de eventos | ✓ | ✓ (simplificado) | ✗ — eventos no ledger do pai |
| Custódia explícita | ✓ | ✗ — exceção documentada | ✗ |
| Conteúdo clínico próprio | ✓ | ✗ — referencia objeto pai | ✗ |
| Assinatura/hash | ✓ | ✗ (MVP) | ✗ |
| Tabela de itens | ✓ | ✗ (MVP) | ✗ |
| org_id / unidade_id | Incremental | Obrigatório | Obrigatório |

**Definição formal:**

> Um **objeto sanitário leve** é um artefato rastreável com identidade e ciclo de vida próprios, mas sem conteúdo clínico autônomo. Ele existe para representar um **compromisso operacional** entre partes, vinculado a um objeto sanitário pai.

O Agendamento é o primeiro objeto leve do PicSaúde. Outros objetos futuros desta categoria: autorização de procedimento, reserva de leito, credenciamento de acesso.

### Por que não é um subdomínio operacional?

O subdomínio operacional (ex: dispensação hospitalar) não tem identidade própria — é apenas contexto adicional de um fluxo existente. O Agendamento tem:
- UUID próprio (`protocolo_agendamento`)
- Estados que evoluem de forma independente do exame
- Eventos próprios no ledger (não mistura com `pedido_exame_eventos`)
- Possibilidade de ser remarcado, criando cadeia de derivação

Portanto, é mais que subdomínio — é objeto com identidade rastreável.

### Por que não é objeto completo?

Os objetos completos carregam **conteúdo clínico autônomo**: a prescrição especifica o medicamento, o pedido especifica o exame, o laudo contém o resultado. O Agendamento não tem conteúdo clínico próprio — é um compromisso sobre **quando** e **onde** um conteúdo já existente (o pedido) será executado.

Não tem assinatura/hash (não é documento clínico que requer validade jurídica) e não tem tabela de itens própria no MVP (referencia os itens do pedido).

---

## 2. Relação com Pedido de Exame

### O pedido de exame é imutável após emissão

O agendamento **nunca altera** o pedido de exame. Este permanece como emitido, com seus itens, sua data de validade e seus campos clínicos intocados.

O que o agendamento faz:
- Registra **quando** e **onde** o pedido será executado
- Atualiza o `status_item` dos itens vinculados (de `pendente` para `agendado`)
- Quando realizado, atualiza os itens para `coletado`

O que o agendamento **não** faz:
- Não modifica `pedido_exame_itens.nome_exame`, `quantidade`, `prioridade`
- Não modifica `pedidos_exame.data_emissao`, `data_validade`, `assinatura_hash`
- Não cancela o pedido (cancelamento do agendamento devolve os itens a `pendente`)

### Um pedido pode ter múltiplos agendamentos?

**Sim — mas apenas um ativo por vez.**

Regra: para um dado conjunto de itens do pedido, pode existir no máximo um agendamento com status ≠ `cancelado` ou `nao_compareceu`.

Situações em que múltiplos agendamentos existem para o mesmo pedido:
1. Remarcação: o agendamento anterior é cancelado e um novo é criado
2. Agendamento parcial: apenas um subconjunto dos itens do pedido é agendado em uma sessão (ex: exames laboratoriais e de imagem no mesmo pedido, com prestadores diferentes)

No MVP: um pedido tem no máximo um agendamento ativo — cobrindo todos os itens. O agendamento parcial (por subconjunto de itens) é fora do MVP.

### Remarcação: novo objeto ou novo estado?

**Novo objeto — seguindo o padrão de derivação do PicSaúde.**

Quando um agendamento é remarcado:
1. O agendamento existente recebe status `cancelado` com `motivo = 'remarcado'`
2. Um novo agendamento é criado com `tipo_emissao = 'remarcacao'` e `origem_agendamento_id` apontando para o anterior

```
AG-001 (criado 10h do dia 5)
  → cancelado (motivo: remarcado)
AG-002 (criado com nova data, origem_agendamento_id = AG-001)
  → confirmado
  → realizado
```

**Por que não é um estado?**

O estado `remarcado` criaria a situação de um objeto único carregando dados de dois momentos temporais distintos — o horário original e o novo. Isso viola o princípio de imutabilidade: a data_hora do agendamento deveria ser imutável após criação.

A derivação preserva o histórico completo: sabemos que a data original era X e o novo é Y, quem remarcou e quando.

### Cancelamento do agendamento altera o pedido?

**Não — o pedido permanece válido.** Os itens do pedido retornam a `pendente` (disponíveis para novo agendamento). O pedido pode ser agendado novamente com outro prestador ou outra data.

Exceção: se a validade do pedido expirar antes de novo agendamento, o pedido transita para `expirado` pelo mecanismo já existente.

---

## 3. Contrato do objeto Agendamento

### Tabela principal: `agendamentos`

```sql
CREATE TABLE agendamentos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo             TEXT UNIQUE NOT NULL,     -- UUID, identidade pública
    pedido_exame_id       INTEGER REFERENCES pedidos_exame(id) NOT NULL,
    paciente_id           INTEGER REFERENCES pacientes(id) NOT NULL,

    -- Prestador (contexto institucional obrigatório)
    org_id                TEXT NOT NULL,            -- organização do prestador
    unidade_id            TEXT NOT NULL,            -- unidade de coleta/execução

    -- Dados do compromisso
    tipo_agendamento      TEXT NOT NULL DEFAULT 'exame',  -- exame | consulta (futuro)
    data_hora             TEXT NOT NULL,            -- ISO 8601 datetime do compromisso
    local_texto           TEXT,                     -- descrição livre do local (MVP)
    observacao            TEXT,

    -- Rastreabilidade e derivação
    status                TEXT NOT NULL DEFAULT 'criado',
    tipo_emissao          TEXT NOT NULL DEFAULT 'novo',   -- novo | remarcacao
    origem_agendamento_id INTEGER REFERENCES agendamentos(id),  -- se remarcacao

    -- Quem criou
    criado_por            TEXT NOT NULL,            -- CNS do prescritor ou CPF do paciente
    criado_em             TEXT NOT NULL             -- ISO 8601 datetime
);
```

**Invariantes:**
- `protocolo` gerado pelo backend (nunca pelo frontend)
- `data_hora` é imutável após INSERT — remarcação cria novo objeto
- `origem_agendamento_id` obrigatório quando `tipo_emissao = 'remarcacao'`
- `org_id` e `unidade_id` são obrigatórios (agendamento é inherentemente institucional)
- Não há `assinatura_hash` no MVP (exceção documentada — seção 11)

### Tabela de ledger: `agendamento_eventos`

```sql
CREATE TABLE agendamento_eventos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    agendamento_id   INTEGER REFERENCES agendamentos(id) NOT NULL,
    tipo_evento      TEXT NOT NULL,
    ator_tipo        TEXT,                          -- quem gerou: paciente | prestador | sistema
    ator_id          TEXT,                          -- CPF, CNPJ, CNS
    payload_json     TEXT,                          -- dados contextuais do evento
    criado_em        TEXT NOT NULL
);
```

**Regra:** imutável — sem UPDATE, sem DELETE (mesma regra do ledger de prescrições).

### Sem tabela de custódia

O Agendamento não tem tabela de custódia. Justificativa completa na seção 5.

### Sem tabela de itens (MVP)

Para o MVP, o agendamento cobre todos os itens ativos do `pedido_exame_id` referenciado. Não há `agendamento_itens`. Esta simplicidade é possível porque:
- Um agendamento de coleta normalmente cobre todos os exames de um pedido
- Casos de agendamento parcial (por subconjunto) são raros no SUS e fora do MVP

**Evolução futura:** `agendamento_itens` pode ser adicionada quando um caso real exigir (ex: pedido com exames em laboratórios diferentes).

---

## 4. Máquina de estados

### Estados do agendamento

```
criado
  → confirmado         (prestador confirma a reserva)
  → cancelado          (paciente ou prestador cancela — ver detalhes abaixo)
  → nao_compareceu     (paciente não compareceu — terminal)

confirmado
  → realizado          (paciente compareceu e exame foi coletado/iniciado — terminal*)
  → cancelado
  → nao_compareceu

cancelado              (terminal — mas o pedido permanece ativo)
realizado              (terminal — dispara atualização nos itens do pedido)
nao_compareceu         (terminal — pedido retorna a pendente)
```

`*` `realizado` é terminal para o agendamento. Não para o pedido de exame — que prossegue para `em_analise` e `resultado_disponivel`.

### Estados terminais

```
realizado · cancelado · nao_compareceu
```

### Tabela de transições válidas

| De | Para | Quem |
|---|---|---|
| `criado` | `confirmado` | prestador |
| `criado` | `cancelado` | paciente ou prestador |
| `confirmado` | `realizado` | prestador (ato de coleta) |
| `confirmado` | `cancelado` | paciente ou prestador |
| `confirmado` | `nao_compareceu` | prestador (após horário) |

### `remarcado` não é estado

Conforme decisão da seção 2: remarcação cria novo objeto derivado. O agendamento original transita para `cancelado` com `motivo = 'remarcado'`. Não existe estado `remarcado`.

### Impacto nos itens do pedido de exame

| Transição do agendamento | Transição do `pedido_exame_itens.status_item` |
|---|---|
| `criado` (novo agendamento) | `pendente` → `agendado` |
| `confirmado` (sem impacto nos itens) | sem mudança |
| `realizado` | `agendado` → `coletado` |
| `cancelado` | `agendado` → `pendente` |
| `nao_compareceu` | `agendado` → `pendente` |

Esta tabela é a **especificação de integração** entre agendamento e pedido de exame.

---

## 5. Custódia — decisão e justificativa

**O Agendamento não tem cadeia de custódia.**

### Por que a custódia não se aplica

A custódia no PicSaúde modela a **posse física** ou **responsabilidade de guarda** de um documento clínico:
- A prescrição é portada pelo paciente, entregue ao dispensador, devolvida ao prescritor
- O pedido de exame é portado pelo paciente, entregue ao laboratório

O Agendamento é um **compromisso bilateral** — não tem "portador". O paciente e o prestador têm acesso simultâneo a ele. Nenhum "entrega" o agendamento ao outro.

Não há handoff físico, não há transferência de responsabilidade de guarda — por isso a custódia não se aplica.

### O que substitui a custódia

O agendamento tem **papéis fixos** ao invés de cadeia de custódia:

```
paciente_id     → quem comparecerá
org_id          → organização responsável pela execução
unidade_id      → unidade específica de coleta
criado_por      → quem criou o compromisso (prescritor ou paciente)
```

Esses campos são imutáveis após criação. Se o prestador mudar (remarcação em outra unidade), cria-se novo agendamento derivado — não se transfere a custódia do original.

### Exceção documentada

```
NUCLEO_SANITARIO.md §4 — Custódia:
  Agendamentos não implementam prescricao_custodia nem tabela equivalente.
  Justificativa: compromisso bilateral sem transferência de posse.
  O contexto de responsabilidade é capturado por org_id + unidade_id + criado_por.
```

---

## 6. Ledger de eventos

### Vocabulário de eventos

| Evento | Quando ocorre | Ator principal |
|---|---|---|
| `agendamento_criado` | Criação do compromisso | prescritor ou paciente |
| `agendamento_confirmado` | Prestador confirma o slot | prestador |
| `agendamento_realizado` | Paciente compareceu e coleta iniciou | prestador |
| `agendamento_cancelado` | Cancelamento por qualquer parte | paciente ou prestador |
| `agendamento_nao_compareceu` | Registro de falta | prestador |
| `agendamento_remarcado` | Criação de remarcação (emitido no agendamento **antigo**) | paciente ou prestador |

### Regras do ledger

- Imutável: sem UPDATE, sem DELETE
- Cada evento é um INSERT em `agendamento_eventos`
- `payload_json` contém dados contextuais livres
- `agendamento_remarcado` é emitido no ledger do agendamento **cancelado** para garantir rastreabilidade da cadeia

### Exemplo de cadeia de eventos para remarcação

```
AG-001 ledger:
  1. agendamento_criado   {data_hora: "2026-04-10 09:00"}
  2. agendamento_confirmado
  3. agendamento_remarcado {novo_protocolo: "AG-002", motivo: "solicitação do paciente"}
  4. agendamento_cancelado {motivo: "remarcado", novo_protocolo: "AG-002"}

AG-002 ledger:
  1. agendamento_criado   {data_hora: "2026-04-14 14:00", origem: "AG-001"}
  2. agendamento_confirmado
  3. agendamento_realizado
```

---

## 7. Integração com Exame — direção causal

### Causalidade correta

```
Agendamento realizado  →  itens do pedido mudam para 'coletado'
(não o contrário)
```

O ato clínico é: o paciente comparece, o material é coletado (ou o exame é realizado). Quem registra esse fato é o prestador, no sistema, via `POST /agendamentos/{proto}/realizar`. Isso dispara a atualização dos itens do pedido.

**Não é o pedido de exame que aciona o agendamento.** O pedido é emitido pelo prescritor e aguarda agendamento — ele não cria agendamentos automaticamente.

### O estado `agendado` já existe no domínio de exame

Conforme `domain/states_exame.py` (Tickets 14–17), o `pedido_exame_itens.status_item` já inclui o estado `agendado`. Isso demonstra que a integração foi prevista desde a arquitetura do módulo de exames — o agendamento é o mecanismo que ativa essa transição.

### Fluxo completo do elo fechado

```
POST /pedidos_exame           → pedido.status = 'emitido'
                                itens.status_item = 'pendente'

POST /agendamentos            → agendamento.status = 'criado'
                                itens.status_item = 'pendente' → 'agendado'
                                evento: agendamento_criado

POST /agendamentos/{p}/confirmar → agendamento.status → 'confirmado'
                                   evento: agendamento_confirmado

POST /agendamentos/{p}/realizar  → agendamento.status → 'realizado'
                                   itens.status_item = 'agendado' → 'coletado'
                                   pedido.status recalculado
                                   evento: agendamento_realizado
                                   [prestador prossegue com análise → laudo]
```

### Comportamento em cancelamento

```
POST /agendamentos/{p}/cancelar  → agendamento.status → 'cancelado'
                                   itens.status_item = 'agendado' → 'pendente'
                                   pedido.status recalculado (pode voltar a 'emitido')
                                   evento: agendamento_cancelado
```

O pedido não é afetado estruturalmente — mantém `data_validade` e conteúdo clínico. Os itens voltam a `pendente`, disponíveis para novo agendamento.

### Sem acoplamento bidirecional

O módulo de pedidos de exame (`routers/pedidos_exame.py`) **não importa** nem **chama** nada do módulo de agendamentos. O acoplamento é unidirecional: o agendamento é que conhece o pedido (tem `pedido_exame_id`), não o contrário.

Isso garante que o módulo de exames continua funcionando sem o módulo de agendamentos implantado (é opcional, não obrigatório para a rastreabilidade básica).

---

## 8. Escopo institucional — `org_id` e `unidade_id`

### Obrigatórios em `agendamentos`

Diferente de objetos clínicos (prescrição, laudo), o agendamento é **sempre institucional** — não existe agendamento sem local definido.

```
org_id    = obrigatório (NOT NULL)
unidade_id = obrigatório (NOT NULL)
```

Exemplos:
- `org_id = 'LABX-PE'`, `unidade_id = 'LAB-RECIFE-CENTRAL'` — laboratório específico
- `org_id = 'CLINICA-ABC'`, `unidade_id = 'CLINICA-ABC-001'` — clínica

### `NULL` não é permitido em agendamentos

Ao contrário da diretriz geral (onde `NULL = ausência de vínculo), em agendamentos `NULL` nos campos institucionais invalida o registro. Um agendamento sem prestador identificado não é agendamento — é apenas uma intenção.

### Impacto em tabelas existentes

Nenhuma tabela existente é migrada. `pedidos_exame` continua sem `org_id` (o pedido é global, o agendamento é contextual). `pedido_exame_itens` herda via JOIN.

---

## 9. O que o Agendamento NÃO é

### Não é um sistema de agenda

O PicSaúde **não cria** neste ticket:
- Grade de horários disponíveis
- Verificação de disponibilidade de slots
- Conflito de horários
- Agenda do profissional de saúde
- Lista de espera

O sistema **registra** um compromisso — não **gerencia** a agenda. A disponibilidade de horários é responsabilidade de um sistema externo (ou do operador que cria o agendamento no frontend).

**Analogia:** assim como o PicSaúde não gerencia o estoque de medicamentos (só rastreia a dispensação), o PicSaúde não gerencia a agenda do prestador (só rastreia o compromisso).

### Não é autorização de procedimento

O Agendamento não substitui TISS/APAC nem autoriza cobertura de plano. É rastreabilidade sanitária, não faturamento.

### Não é prontuário

O Agendamento não contém anamnese, evolução, diagnóstico ou prescrição resultante da consulta.

---

## 10. Fora do MVP

| Item | Motivo |
|---|---|
| Grade de horários / agenda médica | Sistema de agenda externo — adapter layer |
| Verificação de disponibilidade | Requer integração com agenda do prestador |
| Agendamento parcial (por subconjunto de itens) | Baixa frequência no SUS; requer `agendamento_itens` |
| Encaixe / overbooking | Lógica de agenda, não sanitária |
| Fila de espera | Objeto próprio (posição na fila, prioridade) |
| Confirmação por SMS/WhatsApp | Integração de notificações externa |
| Integração com CNES (unidades credenciadas) | ETL separado; unidade_id é texto livre no MVP |
| Autorização TISS/APAC | Faturamento — fora do núcleo sanitário |
| Agendamento de consultas | Tipo_agendamento = 'consulta' reservado; sem objeto pai de consulta ainda |
| Assinatura do agendamento | Compromisso não é documento clínico; sem requisito legal de assinatura |
| QR Code / validação pública | Agendamento não é documento público (dados sensíveis de data/local) |
| PDF de comprovante | Útil, mas não crítico para MVP do elo |

---

## 11. Checklist de aderência ao NUCLEO_SANITARIO.md

### O que herda integralmente

| Contrato | Status | Observação |
|---|---|---|
| Protocolo UUID como identidade global | ✓ | `protocolo` em `agendamentos` |
| Ledger imutável | ✓ | `agendamento_eventos` — sem UPDATE/DELETE |
| Imutabilidade após criação | ✓ | `data_hora`, `pedido_exame_id` não recebem UPDATE |
| Derivação com `origem_id` | ✓ | `origem_agendamento_id` para remarcação |
| `tipo_emissao` no objeto principal | ✓ | `novo` ou `remarcacao` |
| `status` com máquina de estados declarada | ✓ | seção 4 deste documento |
| Estados terminais explícitos | ✓ | `realizado`, `cancelado`, `nao_compareceu` |
| RBAC em todos os endpoints | ✓ | `require_role("prescritor","paciente","admin")` |
| `org_id` + `unidade_id` presentes | ✓ | Obrigatórios em `agendamentos` |

### Exceções documentadas

| Contrato | Decisão | Justificativa |
|---|---|---|
| Custódia explícita | **Exceção** | Compromisso bilateral; sem transferência de posse |
| `assinatura_hash` | **MVP sem hash** | Não é documento clínico que exige validade jurídica |
| Tabela de itens | **MVP sem itens** | Agendamento cobre todos os itens do pedido |
| PDF institucional | **MVP sem PDF** | Fora do escopo mínimo do elo |
| QR Code + validação pública | **Fora do MVP** | Dados sensíveis (data/local); sem requisito de acesso público |

### O que exigiria revisão futura do núcleo

| Situação | Quando revisar |
|---|---|
| Agendamento de consulta (sem pedido de exame) | Quando consulta tiver objeto pai próprio |
| Agendamento parcial por itens | Quando caso real exigir `agendamento_itens` |
| Assinatura eletrônica do compromisso | Se regulação exigir validade jurídica do agendamento |
| Custódia parcial (agendamento com responsável único) | Se surgir caso de transferência entre prestadores |

### Invariantes que não podem ser violadas

```
✗ PROIBIDO: UPDATE agendamentos SET data_hora = ... (imutável após criação)
✗ PROIBIDO: alterar pedido_exame ao criar ou cancelar agendamento
✗ PROIBIDO: estado 'remarcado' — remarcação cria novo objeto derivado
✗ PROIBIDO: agendamento sem org_id ou unidade_id
✗ PROIBIDO: acoplamento bidirecional (pedido não importa agendamento)
✗ PROIBIDO: dois agendamentos ativos para o mesmo conjunto de itens do mesmo pedido
```

---

## 12. Conclusão — classificação final

**O Agendamento é um objeto sanitário leve.**

Não é:
- Objeto sanitário completo — não tem conteúdo clínico autônomo, custódia ou assinatura
- Subdomínio operacional — tem identidade própria, estados, ledger e cadeia de derivação
- Sistema de agenda — não gerencia disponibilidade ou grade de horários

É:
- O **elo operacional** entre pedido de exame e coleta
- Um **compromisso bilateral rastreável** entre paciente e prestador
- O **mecanismo de ativação** que move itens de `pendente` para `agendado` para `coletado`
- O **primeiro objeto leve** de uma nova categoria no domínio PicSaúde

**Impacto na arquitetura do sistema:**

```
Antes do Ticket 28:
  pedido_exame (emitido) ──────────────────────────────→ coletado
  (transição dependia de chamada direta em pedidos_exame.py)

Após o Ticket 29:
  pedido_exame (emitido)
    → agendamento criado   (itens: pendente → agendado)
    → agendamento realizado (itens: agendado → coletado)
    → pedido prossegue para em_analise → resultado_disponivel
    → laudo emitido
```

O elo `pedido_exame → execução → laudo` fica completamente fechado e rastreável.

---

## 13. Definição do Ticket 29 — Implementação do Agendamento (MVP)

### O que o Ticket 29 deve implementar

#### Backend

**Tabelas novas:**
```
agendamentos          ← objeto principal (seção 3)
agendamento_eventos   ← ledger imutável
```

**Domain:**
```
backend/app/domain/states_agendamento.py  ← estados, terminais, transições, derivação
```

**Endpoints mínimos:**

| Método | Rota | Descrição |
|---|---|---|
| POST | `/agendamentos` | Criar agendamento vinculado a pedido_exame |
| GET | `/agendamentos/{proto}` | Consultar agendamento |
| POST | `/agendamentos/{proto}/confirmar` | Prestador confirma (criado → confirmado) |
| POST | `/agendamentos/{proto}/realizar` | Prestador registra execução (→ realizado + itens coletado) |
| POST | `/agendamentos/{proto}/cancelar` | Cancelar (→ cancelado + itens pendente) |
| POST | `/agendamentos/{proto}/nao_compareceu` | Registrar falta (→ nao_compareceu + itens pendente) |
| POST | `/agendamentos/{proto}/remarcar` | Criar derivação + cancelar atual |
| GET | `/pedidos_exame/{proto}/agendamentos` | Histórico de agendamentos de um pedido |

**Ledger:**
- Evento `agendamento_criado` em `agendamento_eventos`
- Todos os outros eventos conforme seção 6

**Integração:**
- Ao criar agendamento: `pedido_exame_itens.status_item` `pendente → agendado`
- Ao realizar: `pedido_exame_itens.status_item` `agendado → coletado` + recalcular status do pedido
- Ao cancelar/nao_compareceu: `pedido_exame_itens.status_item` `agendado → pendente`

#### Frontend mínimo (cidadao.html ou prescritor.html)

- Botão "Agendar" na carteira do paciente (após exibir pedido de exame ativo)
- Campos: `org_id`, `unidade_id` (ou nome do prestador), `data_hora`
- Exibição do agendamento ativo na carteira

#### Testes

- Mínimo 15 casos cobrindo: criação, confirmação, realização, cancelamento, não comparecimento, remarcação, duplo agendamento ativo (deve ser rejeitado), impacto nos itens do pedido

### O que o Ticket 29 NÃO deve implementar

- Sistema de agenda / grade de horários
- Agendamento de consultas (sem objeto pai ainda)
- Agendamento parcial por itens
- PDF de comprovante
- Notificações / lembretes

---

## Referências internas

| Documento | Relevância |
|---|---|
| `docs/NUCLEO_SANITARIO.md` | Contrato base — exceções documentadas neste arquivo |
| `docs/ARQUITETURA_EXAMES.md` | Máquina de estados do pedido de exame |
| `backend/app/domain/states_exame.py` | Estado `agendado` já previsto nos itens |
| `docs/ARQUITETURA_LAUDO.md` | Próximo objeto após coleta |
| `CLAUDE.md §6b` | Diretriz de org_id / unidade_id |

---

*v1.0 — Ticket 28. Agendamento classificado como objeto sanitário leve. Elo pedido → execução → laudo fechado arquiteturalmente. Sem implementação neste ticket.*
