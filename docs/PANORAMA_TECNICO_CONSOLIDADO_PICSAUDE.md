# Panorama Técnico Consolidado — PicSaúde

> **Gerado em:** 2026-04-05
> **Base:** código real do repositório (`backend/app/`, `*.html`, `docs/`, `tests/`, `seed_dev.py`, `init_tables.py`)
> **Metodologia:** leitura direta de arquivos — nenhuma métrica ou capacidade foi inventada
> **Classificações usadas:** `[IMPLEMENTADO]` · `[PARCIAL]` · `[APENAS DOC/PLANEJADO]` · `[NÃO CONFIRMADO]`

---

## 1. Visão Geral do Sistema

### O que é o PicSaúde

O PicSaúde é uma **infraestrutura de rastreamento de objetos sanitários** — prescrições, pedidos de exame, laudos e agendamentos de coleta. Não é um prontuário eletrônico nem um sistema de gestão hospitalar. É uma plataforma de **custódia sanitária digital**: rastreia quem emite, quem carrega e quem executa cada objeto de cuidado, garantindo imutabilidade, auditabilidade e circulação controlada.

### Problema que resolve

- Prescrições em papel não têm rastreabilidade de entrega ao paciente
- Dispensação farmacêutica sem confirmação de identidade do prescritor
- Ausência de cadeia de custódia para objetos sanitários (exames, laudos)
- Falta de canal formal para circulação diagnóstica (pedido → laboratório → resultado)

### Escopo do MVP atual

`[IMPLEMENTADO]`
- Prescrição digital com custódia (emissão → paciente → dispensação)
- Emissão exclusivamente física (fire-and-forget, sem cadeia digital)
- Pedido de exame com custódia e agendamento de coleta
- Laudo laboratorial com cadeia de custódia
- Circulação diagnóstica (paciente seleciona exames, negocia com laboratório)
- Token de apresentação (QR Code + código curto) para dispensação sem autenticação
- Dispensação hospitalar (farmácia hospitalar com contexto org_id + unidade_id)
- Validação documental em 5 camadas (pública)
- IA farmacêutica passiva (alertas de interação, posologia)
- IA de normalização (CID-10, exames TUSS, medicamentos, atestados)
- Score composto de confiança do cuidado
- API Keys institucionais (G4B) para adapters externos
- Event publishing via outbox (G4A) — polling de eventos

`[APENAS DOC/PLANEJADO]`
- Integração ICP-Brasil real (placeholder documentado)
- Adapter HIS/TISS/HL7/e-SUS (requer G4A completo)
- Dashboard analítico
- Score probabilístico por ML

### Atores do sistema

| Ator | Role RBAC | Acesso principal |
|---|---|---|
| **Prescritor** (médico/odontólogo) | `prescritor` | Emite prescrições e pedidos de exame |
| **Cidadão** (paciente) | `cidadao` | Gerencia suas prescrições e exames |
| **Clínica / Laboratório** | não confirmado como role distinto | Agenda coletas, emite laudos via CNPJ |
| **Dispensador** (farmácia/hospital) | `dispensador` | Dispensa medicamentos |
| **Admin** | `admin` | Gestão de usuários, API keys |
| **Auditor** | `auditor` | Leitura de relatórios e histórico |
| **Integrador** | `integrador` | Acesso via API Key (adapters externos) |

> Nota: o role `prestador_exame` aparece na documentação de endpoints mas a confirmação de que existe como role RBAC formal no arquivo `domain/roles.py` não foi verificada diretamente. Ver seção 15.

---

## 2. Stack Técnica Real

### Backend

| Componente | Versão | Status |
|---|---|---|
| FastAPI | 0.128.8 | `[IMPLEMENTADO]` |
| Uvicorn (ASGI) | 0.39.0 | `[IMPLEMENTADO]` |
| SQLAlchemy (ORM) | 2.0.41 | `[IMPLEMENTADO]` |
| python-jose (JWT) | 3.5.0 | `[IMPLEMENTADO]` |
| passlib + bcrypt | 1.7.4 | `[IMPLEMENTADO]` |
| reportlab (PDF) | 4.4.10 | `[IMPLEMENTADO]` |
| qrcode + pillow | 8.2 / 11.3.0 | `[IMPLEMENTADO]` |
| httpx | ≥ 0.27.0 | `[IMPLEMENTADO]` (cliente HTTP para adapters) |
| python-multipart | 0.0.20 | `[IMPLEMENTADO]` |

### Banco de dados

| Item | Valor | Status |
|---|---|---|
| Banco ativo | SQLite | `[IMPLEMENTADO]` |
| Path | `data/pix_saude_pe.db` | `[IMPLEMENTADO]` |
| Env override | `PIX_SAUDE_DB` | `[IMPLEMENTADO]` |
| DDL PostgreSQL | `docs/picsaude_ddl_postgres_v1.sql` | `[APENAS DOC/PLANEJADO]` |
| Concorrência | SQLite (sem WAL verificado) | `[NÃO CONFIRMADO]` |

### Frontend

| Arquivo | Propósito | Status |
|---|---|---|
| `prescritor.html` | Módulo prescritor (emissão, IA, derivações) | `[IMPLEMENTADO]` |
| `dispensador.html` | Módulo farmácia (dispensação, token, hospitalar) | `[IMPLEMENTADO]` |
| `cidadao.html` | Módulo paciente (prescrições, exames, laudos) | `[IMPLEMENTADO]` |
| `clinica.html` | Módulo clínica/laboratório (pedidos, laudos, agendamentos) | `[IMPLEMENTADO]` |
| `validar.html` | Validação pública (protocolo + hash SHA-256) | `[IMPLEMENTADO]` |
| `index.html` | Portal de acesso (links aos módulos) | `[IMPLEMENTADO]` |

Todos os frontends são **vanilla JS** — sem framework (React, Vue, Angular). Comunicação via `fetch()` ao backend FastAPI. Estado local em `localStorage`.

### Testes

| Framework | Status |
|---|---|
| pytest | `[IMPLEMENTADO]` |
| anyio (plugin) | `[IMPLEMENTADO]` |
| httpx (cliente de teste) | `[IMPLEMENTADO]` |

### Infraestrutura

| Componente | Evidência | Status |
|---|---|---|
| Dockerfile | `Dockerfile` presente no raiz | `[IMPLEMENTADO]` |
| docker-compose | `docker-compose.yml` presente | `[IMPLEMENTADO]` |
| healthcheck | `healthcheck.sh` presente | `[IMPLEMENTADO]` |
| bootstrap | `bootstrap.sh` presente | `[IMPLEMENTADO]` |
| CI/CD pipeline | não encontrado no repositório | `[NÃO CONFIRMADO]` |
| Kubernetes / cloud deploy | não encontrado | `[NÃO CONFIRMADO]` |

---

## 3. Arquitetura Real do Sistema

### Estrutura de pastas

```
PicSaude_Dev/
├── backend/
│   ├── app/
│   │   ├── auth/           ← JWT, RBAC, dependências FastAPI
│   │   ├── routers/        ← 24+ arquivos de endpoints
│   │   ├── models/         ← SQLAlchemy ORM (35+ tabelas)
│   │   ├── domain/         ← Lógica de domínio pura (sem FastAPI)
│   │   ├── ai/             ← Drivers IA generativa
│   │   ├── ai_documental/  ← IA para atestados
│   │   ├── utils/          ← helpers (normalize_cpf, normalize_cns, ...)
│   │   ├── config.py       ← DB_PATH, JWT_SECRET, CNES_SNAPSHOT_*
│   │   ├── database.py     ← engine SQLAlchemy + get_conn() raw SQL
│   │   └── main.py         ← FastAPI app + inclusão de routers
│   ├── tests/              ← Suite pytest
│   ├── scripts/            ← importar_cnes_pe.py, importar_cnes_br.py
│   ├── init_tables.py      ← Criação idempotente de todas as tabelas
│   └── seed_dev.py         ← Dados de teste (prescritor, farmácia, hospital, USF)
├── docs/                   ← 18 documentos .md + DDL PostgreSQL
├── data/
│   └── pix_saude_pe.db     ← SQLite (CNES snapshot + dados da aplicação)
├── prescritor.html         ← Frontend prescritor
├── dispensador.html        ← Frontend dispensador
├── cidadao.html            ← Frontend cidadão
├── clinica.html            ← Frontend clínica/laboratório
├── validar.html            ← Frontend validação pública
└── index.html              ← Portal de entrada
```

### Camadas

| Camada | Localização | Responsabilidade |
|---|---|---|
| **Routers** | `app/routers/` | Endpoints HTTP, validação Pydantic, controle de acesso |
| **Domain** | `app/domain/` | Lógica pura (máquinas de estado, score, hash, PDF) |
| **Models** | `app/models/` | SQLAlchemy ORM — definição de tabelas |
| **Auth** | `app/auth/` | JWT, RBAC, API Key dupla |
| **AI** | `app/ai/` | Drivers IA (farmacêutica, CID, exames, documental) |
| **Utils** | `app/utils/` | Normalização de CPF, CNS, CNPJ, nome |
| **Config** | `app/config.py` | Variáveis de ambiente centralizadas |
| **Database** | `app/database.py` | Engine SQLAlchemy + `get_conn()` para raw SQL |

### Padrões observados

- **Event sourcing interno**: todo evento de negócio gera INSERT no ledger (`*_eventos`) — imutável
- **CQRS informal**: leitura por raw SQL (`get_conn()`), escrita mista (ORM + raw SQL)
- **Objeto derivado**: prescrição/pedido nunca é editado após emissão — cria-se novo com `origem_*_id`
- **Outbox pattern**: `app/domain/outbox.py` — fila para publicação de eventos externos (G4A)
- **RBAC via dependency injection**: `require_role("prescritor")` como `Depends()` do FastAPI

### Separação frontend/backend

- Backend: FastAPI em `http://127.0.0.1:8000` (hardcoded no frontend — ver seção 12)
- Frontend: arquivos HTML estáticos servidos diretamente (sem servidor de frontend dedicado)
- Comunicação: `fetch()` REST JSON
- Estado local: `localStorage` (prescrições pendentes, contexto institucional)

---

## 4. Módulos Funcionais Implementados

### 4.1 Prescritor

**Propósito:** Emissão digital e física de prescrições, derivações (correção/renovação), IA de suporte.

**Endpoints principais:**

| Método | Rota | Status |
|---|---|---|
| POST | `/prescricoes` | `[IMPLEMENTADO]` |
| POST | `/prescricoes/fisica` | `[IMPLEMENTADO]` |
| GET | `/prescricoes/{proto}` | `[IMPLEMENTADO]` |
| GET | `/prescricoes/{proto}/pdf` | `[IMPLEMENTADO]` |
| GET | `/prescricoes/{proto}/documento` | `[IMPLEMENTADO]` |
| GET | `/prescricoes/{proto}/validacao` | `[IMPLEMENTADO]` |
| GET/POST | `/prescricoes/{proto}/assinatura` | `[IMPLEMENTADO]` |
| POST | `/solicitacoes/renovacao/{id}/atender` | `[IMPLEMENTADO]` |

**Estado de implementação:** `[IMPLEMENTADO]`

### 4.2 Cidadão / Paciente

**Propósito:** Acesso do paciente às suas prescrições, geração de token de apresentação, gestão de exames e laudos.

**Endpoints principais:**

| Método | Rota | Status |
|---|---|---|
| GET | `/pacientes/{cpf}` | `[IMPLEMENTADO]` |
| POST | `/tokens/apresentacao` | `[IMPLEMENTADO]` |
| GET | `/tokens/apresentacao/{codigo}/qr` | `[IMPLEMENTADO]` |
| DELETE | `/tokens/apresentacao/{codigo}` | `[IMPLEMENTADO]` |
| POST | `/solicitacoes/renovacao` | `[IMPLEMENTADO]` |
| GET | `/pedidos-exame/{proto}` | `[IMPLEMENTADO]` |
| POST | `/circulacoes-diagnosticas` | `[IMPLEMENTADO]` |
| POST | `/circulacoes-diagnosticas/{chave}/confirmar` | `[IMPLEMENTADO]` |

**Estado de implementação:** `[IMPLEMENTADO]`

### 4.3 Clínica / Laboratório

**Propósito:** Emissão de pedidos de exame, agendamento de coleta, emissão de laudos.

**Endpoints principais:**

| Método | Rota | Status |
|---|---|---|
| POST | `/pedidos-exame` | `[IMPLEMENTADO]` |
| GET | `/pedidos-exame/{proto}` | `[IMPLEMENTADO]` |
| GET | `/pedidos-exame/{proto}/pdf` | `[IMPLEMENTADO]` |
| POST | `/agendamentos` | `[IMPLEMENTADO]` |
| POST | `/agendamentos/{id}/confirmar` | `[IMPLEMENTADO]` |
| POST | `/agendamentos/{id}/marcar-realizado` | `[IMPLEMENTADO]` |
| POST | `/laudos` | `[IMPLEMENTADO]` |
| POST | `/laudos/{proto}/assinar` | `[IMPLEMENTADO]` |
| POST | `/laudos/{proto}/liberar` | `[IMPLEMENTADO]` |
| GET | `/laudos/{proto}/pdf` | `[IMPLEMENTADO]` |

**Estado de implementação:** `[IMPLEMENTADO]` (backend); `[PARCIAL]` (frontend `clinica.html` cobre pedidos e agendamentos; laudo via clinica.html não confirmado com leitura direta)

### 4.4 Dispensador

**Propósito:** Dispensação de medicamentos por item, modo hospitalar, token de apresentação, alertas IA.

**Endpoints principais:**

| Método | Rota | Status |
|---|---|---|
| POST | `/tokens/apresentacao/resolver` | `[IMPLEMENTADO]` |
| POST | `/prescricoes/{proto}/itens/{id}/dispensar` | `[IMPLEMENTADO]` |
| POST | `/prescricoes/{proto}/itens/{id}/devolver` | `[IMPLEMENTADO]` |
| POST | `/prescricoes/{proto}/custodia/transferir` | `[IMPLEMENTADO]` |
| POST | `/hospitalares/dispensacoes` | `[IMPLEMENTADO]` |

**Estado de implementação:** `[IMPLEMENTADO]`

### 4.5 IA / Validação

**Propósito:** Suporte clínico passivo — alertas de interação, normalização, sugestões.

| Módulo | Rota | Status |
|---|---|---|
| IA Farmacêutica | `POST /ia/farmaceutica` | `[IMPLEMENTADO]` |
| Normalização CID | `POST /ia/cid` | `[IMPLEMENTADO]` |
| Normalização Exames | `POST /ia/exames` | `[IMPLEMENTADO]` |
| IA Documental (atestado) | `POST /ia/atestado` | `[IMPLEMENTADO]` |
| Score de Confiança | calculado em `domain/confianca_cuidado.py` | `[IMPLEMENTADO]` |
| Validação CNES Prescritor | calculado em `domain/cnes_prescritor.py` | `[IMPLEMENTADO]` |
| Validação Documental 5 camadas | `GET /prescricoes/{proto}/validacao` | `[IMPLEMENTADO]` |

> Todos os drivers de IA são **baseados em regras e busca em base local** (não há integração com LLM externo confirmada no repositório).

### 4.6 Custódia / Circulação

**Propósito:** Rastreamento explícito da posse de objetos sanitários.

| Funcionalidade | Status |
|---|---|
| Custódia de prescrição (prescritor → paciente → dispensador) | `[IMPLEMENTADO]` |
| Custódia granular por item (`item_id`) | `[IMPLEMENTADO]` |
| Circulação atomizada (token por item) | `[IMPLEMENTADO]` |
| Custódia de pedido de exame | `[IMPLEMENTADO]` |
| Circulação diagnóstica (seleção de exames) | `[IMPLEMENTADO]` |
| Custódia de laudo | `[IMPLEMENTADO]` |
| Custódia hospitalar (farmácia → unidade de enfermagem) | `[IMPLEMENTADO]` |

---

## 5. Fluxos Ponta a Ponta (E2E)

### 5.1 Prescrição

#### Fluxo Digital

```
1. Prescritor autentica (JWT)
2. POST /prescricoes
   ├── valida prescritor (CNS → CNES)
   ├── valida paciente (CPF)
   ├── calcula score_confianca
   ├── grava prescricao (status: pendente)
   ├── grava prescricao_itens (status_item: pendente)
   ├── grava evento: prescricao_emitida (ledger)
   └── retorna: protocolo, hash SHA-256, cnes_validacao, score_confianca

3. Paciente recebe protocolo (fora do sistema ou via app)

4. POST /prescricoes/{proto}/custodia/transferir
   ├── de: prescritor → para: paciente
   ├── grava prescricao_custodia
   ├── muda status → transferida_paciente
   └── grava evento: custodia_transferida

5. Paciente gera token (opcional):
   POST /tokens/apresentacao
   └── retorna: codigo_curto (8 dígitos) + QR Code PNG

6. Dispensador autentica (JWT)
7. Dispensador resolve token:
   POST /tokens/apresentacao/resolver
   └── retorna: protocolo prescrição

8. POST /prescricoes/{proto}/itens/{id}/dispensar
   ├── valida saldo (Σ dispensado ≤ prescrito)
   ├── grava dispensacoes (com origem_contexto, lote, fabricante)
   ├── atualiza status_item → {dispensado | em_custodia}
   ├── fecha custódia ativa do item
   ├── recalcula status prescricao
   ├── calcula score_confianca_dispensacao
   ├── grava evento: item_dispensado (ledger)
   └── retorna: saldo_restante, status_item, score_confianca
```

#### Fluxo Físico (fire-and-forget)

```
1. Prescritor autentica (JWT)
2. POST /prescricoes/fisica
   ├── CPF sentinela: '00000000000' (paciente não identificado)
   ├── grava prescricao (status: encerrada_localmente)
   ├── grava prescricao_itens (status_item: encerrado_fisico)
   ├── grava evento: prescricao_impressa (ledger)
   ├── grava evento: encerrada_localmente (ledger)
   └── SEM custódia digital (nenhum registro em prescricao_custodia)

3. Frontend: fire-and-forget (não aguarda resposta)
   └── Impressão ocorre independente do backend estar online
```

### 5.2 Pedido de Exame

```
1. Prescritor emite:
   POST /pedidos-exame
   └── status: emitido

2. Paciente acessa pedido, seleciona exames:
   POST /circulacoes-diagnosticas
   └── gera chave_circulacao

3. Laboratório consulta e propõe data/hora:
   POST /circulacoes-diagnosticas/{chave}/proposta
   └── status: proposto

4. Paciente confirma:
   POST /circulacoes-diagnosticas/{chave}/confirmar
   └── status: confirmado → cria agendamento
   └── itens do pedido: pendente → agendado

5. Agendamento realizado:
   POST /agendamentos/{id}/marcar-realizado
   └── itens do pedido: agendado → coletado
```

### 5.3 Circulação Diagnóstica

```
Pré-requisito: pedido_exame existente com itens em status pendente

1. Paciente cria circulação:
   POST /circulacoes-diagnosticas
   ├── seleciona itens do pedido
   ├── gera protocolo + chave_circulacao
   └── status: emitida

2. Laboratório resolve chave (via cidadao.html ou link):
   GET /circulacoes-diagnosticas/{chave}
   └── retorna: itens selecionados, paciente, exames

3. Proposta do laboratório:
   POST /circulacoes-diagnosticas/{chave}/proposta
   └── status: proposto

4. Confirmação do paciente:
   POST /circulacoes-diagnosticas/{chave}/confirmar
   └── status: confirmado → agendamento criado
```

### 5.4 Laudo (resultado de exame)

```
1. Laboratório cria laudo:
   POST /laudos
   └── status: em_producao

2. Laboratório assina laudo:
   POST /laudos/{proto}/assinar
   └── status: assinado

3. Laboratório libera resultado:
   POST /laudos/{proto}/liberar
   └── status: liberado

4. Paciente/Prescritor acessa resultado:
   GET /laudos/{proto}
   GET /laudos/{proto}/pdf
```

---

## 6. Entidades e Tabelas Principais

### `prescricoes`

Objeto central. Imutável após emissão. Derivações criam novo registro com `origem_prescricao_id`.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `protocolo` | TEXT UNIQUE | UUID gerado no backend — identidade sanitária global |
| `status` | TEXT | Máquina de estados (seção 7) |
| `tipo_emissao` | TEXT | `nova` \| `correcao` \| `renovacao` |
| `origem_prescricao_id` | FK NULLABLE | Rastreabilidade da cadeia de derivação |
| `indicacao_clinica` | TEXT NULLABLE | Hipótese diagnóstica |
| `codigo_cid` | TEXT NULLABLE | CID-10 |
| `assinatura_hash` | TEXT NULLABLE | SHA-256 do documento canônico |

### `prescricao_itens`

Um registro por medicamento por prescrição. Cada item tem status independente.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `nome_medicamento` | TEXT | Texto livre normalizado |
| `unidade_quantidade` | TEXT | Vocabulário controlado (mg, ml, cáps...) |
| `classe_controle` | TEXT NULLABLE | A1–D2; bloqueia atomização se presente |
| `status_item` | TEXT | Máquina de estados de item (seção 7) |

### `prescricao_custodia`

Cadeia de custódia sanitária. Cada linha registra quem detém o objeto e quando.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `item_id` | FK NULLABLE | NULL = prescrição inteira; NOT NULL = item específico |
| `detentor_tipo` | TEXT | `paciente` \| `dispensador` \| `prescritor` |
| `detentor_id` | TEXT | CPF \| CNPJ \| CNS (normalizado) |
| `encerrada_em` | DATETIME NULLABLE | NULL = custódia ativa |
| `contexto_operacional` | TEXT NULLABLE | `hospitalar` (Ticket 27) |
| `unidade_id` | TEXT NULLABLE | Unidade operacional (farmácia hospitalar) |

### `prescricao_eventos`

**Ledger imutável.** Nunca recebe UPDATE ou DELETE.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `tipo_evento` | TEXT | Vocabulário fixo (ver CLAUDE.md §2) |
| `ator_tipo` | TEXT | `prescritor` \| `paciente` \| `dispensador` \| `sistema` |
| `payload_json` | TEXT | JSON livre com contexto do evento |
| `created_at` | DATETIME | Imutável |

### `pedidos_exame`

Análogo de `prescricoes` para o módulo de exames.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `protocolo` | TEXT UNIQUE | UUID — identidade sanitária |
| `status` | TEXT | Estados do módulo de exame (seção 7) |
| `prioridade` | TEXT | `urgente` \| `normal` \| `eletivo` |

### `pedido_exame_itens`

Item individual de exame. Status independente por item.

### `pedido_exame_custodia`

Cadeia de custódia do pedido de exame.

```
prescritor → paciente → prestador_exame → paciente
```

### `circulacoes_diagnosticas`

Objeto de seleção de exames. O paciente escolhe quais itens do pedido circular para um laboratório específico.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `chave_circulacao` | TEXT UNIQUE | Código de acesso (não é UUID completo) |
| `org_id` | TEXT | Laboratório de destino |
| `unidade_id` | TEXT | Unidade operacional |
| `origem_circulacao_id` | FK NULLABLE | Remarcação gera novo objeto derivado |

### `circulacao_diagnostica_itens`

Itens do pedido selecionados para esta circulação.

### `circulacao_diagnostica_eventos`

Ledger imutável da circulação diagnóstica.

### `pacientes`

| Campo-chave | Tipo | Notas |
|---|---|---|
| `cpf` | TEXT UNIQUE | Normalizado (11 dígitos sem pontuação) |
| `nome` | TEXT | Normalizado (uppercase, sem acentos) |

### `prestadores`

Entidades jurídicas ou redes que operam no sistema.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `org_id` | TEXT UNIQUE | Identificador institucional |
| `cnpj` | TEXT NULLABLE | CNPJ normalizado |
| `tipo` | TEXT | `farmacia` \| `hospital` \| `usf` \| `laboratorio` \| `clinica` |

### `unidades`

Unidades operacionais físicas vinculadas a um prestador.

| Campo-chave | Tipo | Notas |
|---|---|---|
| `prestador_id` | FK | Referencia `prestadores.id` |
| `unidade_id` | TEXT | Identificador da unidade |
| `tipo` | TEXT | `farmacia` \| `usf` \| `laboratorio` |

---

## 7. Máquinas de Estado

### Prescrição (`prescricoes.status`)

**Fonte de verdade:** `backend/app/domain/states.py`

```
ESTADOS:
  pendente              ← emitida digitalmente, aguarda transferência     [não terminal]
  transferida_paciente  ← em custódia do cidadão                          [não terminal]
  em_custodia           ← dispensador reteve a prescrição                 [não terminal]
  parcialmente_dispensada ← ao menos um item dispensado                   [não terminal]
  dispensada            ← todos os itens ativos dispensados               [TERMINAL]
  cancelada             ← revogação clínica dentro do fluxo digital       [TERMINAL]
  expirada              ← data_validade ultrapassada                      [TERMINAL]
  encerrada_localmente  ← emissão exclusivamente física                   [TERMINAL]

TRANSIÇÕES:
  pendente                → transferida_paciente | cancelada | expirada
  transferida_paciente    → em_custodia | cancelada | expirada
  em_custodia             → parcialmente_dispensada | dispensada | cancelada | transferida_paciente
  parcialmente_dispensada → dispensada | cancelada | expirada
```

### Item de Prescrição (`prescricao_itens.status_item`)

**Fonte de verdade:** `backend/app/domain/states.py`

```
ESTADOS:
  pendente              ← estado inicial do ciclo digital                 [não terminal]
  em_custodia           ← dispensador reteve para dispensação             [não terminal]
  dispensado            ← entregue ao paciente                            [TERMINAL]
  devolvido_paciente    ← abandono de compra; disponível para nova tentativa [não terminal]
  devolvido_prescritor  ← erro identificado; aguarda correção             [TERMINAL*]
  cancelado             ← revogação clínica                               [TERMINAL]
  estornado             ← dispensação revertida após registro              [TERMINAL]
  encerrado_fisico      ← emissão física; sem ciclo digital               [TERMINAL]

(*) devolvido_prescritor aguarda nova prescrição derivada com origem_prescricao_id

TRANSIÇÕES:
  pendente              → em_custodia | cancelado
  em_custodia           → dispensado | devolvido_paciente | devolvido_prescritor | cancelado
  devolvido_paciente    → em_custodia | cancelado
  dispensado            → estornado
```

### Pedido de Exame (`pedidos_exame.status`)

**Fonte de verdade:** `backend/app/domain/states_exame.py`

```
emitido · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · expirado · encerrado_fisico
```

### Item de Exame (`pedido_exame_itens.status_item`)

```
pendente · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · encerrado_fisico
```

### Agendamento (`agendamentos.status`)

**Fonte de verdade:** `backend/app/domain/states_agendamento.py`

```
criado · confirmado · realizado · cancelado · nao_compareceu
```

> Remarcação = novo objeto derivado (`origem_agendamento_id`) — sem estado `remarcado`.

### Laudo (`laudos.status`)

**Fonte de verdade:** `backend/app/domain/states_laudo.py`

```
em_producao · assinado · liberado · ciencia_paciente · ciencia_prescritor
encerrado · cancelado · expirado · encerrado_fisico
```

### Circulação Diagnóstica

**Fonte de verdade:** `backend/app/domain/states_circulacao_diagnostica.py`

```
[estados específicos não verificados diretamente — ver states_circulacao_diagnostica.py]
```

---

## 8. Validação Institucional

### CNES — Validação de Prescritor

`[IMPLEMENTADO]` — `backend/app/domain/cnes_prescritor.py`

- Busca do CNS do prescritor em snapshot CNES carregado em `data/pix_saude_pe.db`
- Snapshot importado por `scripts/importar_cnes_pe.py` (Pernambuco) e `scripts/importar_cnes_br.py` (Brasil)
- **Correspondência de nome:** normalização NFD + uppercase + colapso de espaços → match `exato | parcial | divergente`
- **CBO prescritivo:** prefixos 2251\* (médico), 2252\* (cirurgião), 2232\* (odontólogo)
- **Conselho:** "71" (CRM), "75" (CRO), "26" (CRM legado)
- **Vínculo institucional:** cruzamento org_id → prestadores.cnpj → estabelecimentos_cnes → relacao_prof_estab
- **Resultado:** `nivel_validacao_cnes = forte | parcial | divergente | nao_encontrado`
- **Snapshot auditável:** campos `snapshot_ref`, `snapshot_mes`, `validado_em`
- **Não bloqueia emissão:** resultado enriquece evento e resposta, mas não impede emissão

### CNES — Verificação de Prestador (Dispensador)

`[IMPLEMENTADO]` — `backend/app/routers/login.py`

- Calcula `cnes_verificado` dinamicamente no login: cruza CNPJ do prestador com `estabelecimentos_cnes` por tipo compatível
- Tipos farmácia: `("04", "40", "70", "71")`
- Tipos clínica: `("01", "02", "05", "15", "20", "21", "36", "39", "43")`
- Resultado disponível via `GET /login/me/institucional`
- **Não persistido** na tabela `prestadores` — calculado a cada sessão

### Contexto Institucional

`[IMPLEMENTADO]` — Tickets 45, 46

- `origem_contexto`: `cnes_verificado` | `manual` — registrado em cada dispensação
- `contexto_confirmado_manual`: gate leve para operação manual (Ticket 46)
- Banner de risco no frontend quando contexto não verificado
- Contexto carregado via `GET /login/me/institucional` após autenticação

### Score de Confiança do Cuidado

`[IMPLEMENTADO]` — `backend/app/domain/confianca_cuidado.py` (Ticket 50)

**Pontuação base: 30 pontos.** Contribuições por regras determinísticas:

| Sinal | Pontos |
|---|---|
| Prescritor forte (CNES) | +40 |
| Prescritor parcial (CNES) | +20 |
| Prescritor divergente (CNES) | −30 |
| Prescritor não encontrado (CNES) | −15 |
| Conselho habilitado | +10 |
| Vínculos institucionais ≥ 1 | +5 |
| Por divergência CNES (cap −15) | −5 |
| Prestador CNES verificado | +25 |
| Prestador manual confirmado | −10 |
| Prestador manual não confirmado | −20 |

**Níveis:** `alto` (70–100) · `medio` (40–69) · `baixo` (10–39) · `critico` (< 10)

Retorno sempre inclui `fatores` (lista explicável) e `resumo` (string auditável).
Calculado e registrado no ledger de `prescricao_emitida` e `item_dispensado`.

---

## 9. Segurança e Controle

### Autenticação

`[IMPLEMENTADO]`

- **JWT** com claims: `{sub, role, nome, tipo: "access", exp}`
- **Algoritmo:** HS256 (`JWT_SECRET` via env)
- **Access Token TTL:** 15 min (padrão; env `PICSAUDE_JWT_TTL_MIN`)
- **Refresh Token TTL:** 24h (padrão; env `PICSAUDE_JWT_REFRESH_MIN`)
- **Hash de senha:** argon2 via passlib

- **OTP para cidadão:** `[IMPLEMENTADO]` — tabela `codigos_login`, geração e validação de código temporário (sem senha fixa para o cidadão)

- **API Key institucional:** `[IMPLEMENTADO]` (G4B) — `X-Api-Key` header; lookup por `chave_hash` SHA-256; retorna `role: integrador` com `org_id`

- **Autenticação dupla:** `get_current_user_or_api_key()` — aceita Bearer JWT ou X-Api-Key no mesmo endpoint

### Autorização (RBAC)

`[IMPLEMENTADO]`

Roles confirmados no código:
- `prescritor` — emissão, renovação, correção
- `dispensador` — dispensação, devolução, resolução de token
- `cidadao` — acesso ao próprio histórico, tokens, circulação
- `auditor` — leitura de relatórios e histórico
- `admin` — gestão de usuários e API keys
- `integrador` — acesso via API Key a endpoints G4A

Implementado via `Depends(require_role("role"))` em cada endpoint.

### Privacidade

`[PARCIAL]`

- CPF sentinela `'00000000000'` para prescrições físicas sem identificação — `[IMPLEMENTADO]`
- Queries analíticas devem excluir o CPF sentinela — convenção documentada em CLAUDE.md
- Mascaramento de CPF no frontend validar.html — `[IMPLEMENTADO]`
- Criptografia em trânsito (HTTPS/TLS): `[NÃO CONFIRMADO]` — Dockerfile e configuração de TLS não verificados diretamente

### Ledger / Eventos

`[IMPLEMENTADO]`

- Tabelas `*_eventos` são imutáveis por convenção: apenas INSERT
- Sem mecanismo de banco de dados impedindo UPDATE/DELETE (SQLite sem trigger de proteção — ver seção 12)
- Payload JSON de cada evento contém contexto completo (auditável)

---

## 10. ICP-Brasil — Estado Atual Real

`[APENAS DOC/PLANEJADO]`

- Existe stub em `domain/assinatura.py` que reconhece o modo `cfm` e o nível formal `cfm_pendente`
- A validação documental em 5 camadas inclui "camada ICP-Brasil" como placeholder — não executa verificação criptográfica real
- Não há integração com AC-Raiz ICP-Brasil, OCSP, CRL ou TSP no repositório
- Não há biblioteca de verificação de certificado digital ICP-Brasil (ex: `pyhanko`, `certvalidator`) em `requirements.txt`
- O campo `status_validacao` em `prescricao_assinatura` registra o estado declarado pelo prescritor — não é verificado pelo backend

**Conclusão:** ICP-Brasil existe apenas como espaço reservado na arquitetura. A verificação criptográfica real não está implementada.

---

## 11. Testes Existentes

### Estrutura

| Arquivo | Testes confirmados | Áreas cobertas |
|---|---|---|
| `test_cnes_prescritor.py` | **57** (verificado — 100% passando) | Validação CNS × CNES: helpers CBO, normalização de nome, match, cálculo de nível, vínculo com prestador, divergências, integração HTTP |
| `test_confianca_cuidado.py` | **39** (verificado — 100% passando) | Score de confiança: estrutura de retorno, níveis, fatores, clamping, retrocompatibilidade, resumo |
| Demais arquivos de teste | **não contado diretamente** | Ver nota abaixo |

> **Nota sobre demais testes:** os arquivos `test_states.py`, `test_ia_farmaceutica.py`, `test_integration.py`, `test_agendamentos.py`, `test_dispensacao_atomizada.py`, `test_dispensacao_hospitalar.py`, `test_tokens_apresentacao.py`, `test_circulacao_diagnostica.py`, `test_g4b.py`, `test_eventos_publicacao.py`, `test_prestadores.py`, `test_auth_paciente.py`, `test_health.py`, `test_ia_exames.py`, `test_ia_cid.py`, `test_ia_documental.py` estão presentes no repositório mas seus conteúdos não foram lidos diretamente nesta sessão. Número exato de testes nesses arquivos: `[NÃO CONFIRMADO]`.

### Tipos de teste encontrados

- **Testes unitários de domínio:** `test_cnes_prescritor.py`, `test_confianca_cuidado.py` — sem banco, sem FastAPI
- **Testes de integração HTTP:** presente em `test_cnes_prescritor.py` (4 testes com `TestClient`)
- **Fixtures:** `conftest.py` com banco SQLite in-memory para testes isolados

### Áreas com cobertura confirmada

- Validação CNES do prescritor (57 testes)
- Score composto de confiança (39 testes)

### Áreas sem cobertura confirmada

- Fluxo completo E2E (emissão → dispensação)
- Agendamento de coleta
- Circulação diagnóstica
- Farmácia hospitalar
- Token de apresentação

---

## 12. Riscos Técnicos Observáveis

### `[CRÍTICO]` — Imutabilidade do ledger sem enforcement de banco

**Problema:** As tabelas `*_eventos` são imutáveis por **convenção de código** — não há trigger de banco nem constraint SQL impedindo `UPDATE` ou `DELETE`. Um bug de lógica ou acesso direto ao banco pode corromper o ledger.

**Evidência:** SQLite sem triggers de proteção; imutabilidade mantida apenas pela disciplina de não usar UPDATE/DELETE nos routers.

---

### `[CRÍTICO]` — Backend hardcoded no frontend

**Problema:** `http://127.0.0.1:8000` está hardcoded em múltiplos arquivos HTML (`prescritor.html`, `dispensador.html`, `cidadao.html`, `clinica.html`). Em ambiente de produção ou rede diferente, todos os frontends quebram.

**Evidência:** constante `BACKEND = "http://127.0.0.1:8000"` nos arquivos HTML.

---

### `[ALTO]` — Concorrência em SQLite

**Problema:** SQLite com múltiplos workers Uvicorn pode ter condição de corrida na verificação de saldo disponível para dispensação (`SELECT saldo → INSERT dispensacao`). Não há `SELECT ... FOR UPDATE` (SQLite não suporta) nem transação serializable explícita confirmada.

**Evidência:** `dispensar_item` em `custodia.py` faz `SELECT COALESCE(SUM(...))` seguido de `INSERT` sem lock explícito.

---

### `[ALTO]` — Ausência de limite de taxa (rate limiting)

**Problema:** Nenhum rate limiting identificado nos endpoints públicos (`GET /validar/{protocolo}`, `POST /tokens/apresentacao/resolver`). Endpoint de resolução de token pode ser usado em força bruta contra códigos de 8 dígitos.

**Evidência:** nenhum middleware de rate limiting em `main.py` ou routers.

---

### `[ALTO]` — TLS / HTTPS não confirmado

**Problema:** Não foi verificado se o Dockerfile ou docker-compose configuram TLS. Dados sensíveis (CPF, CNS, JWT) transitam em texto plano se HTTPS não for configurado externamente.

**Evidência:** `[NÃO CONFIRMADO]` no repositório.

---

### `[MÉDIO]` — Estado localStorage sem cifração

**Problema:** Dados de prescrições (incluindo CPF do paciente e CNS do prescritor) ficam em `localStorage` do navegador. Em dispositivos compartilhados, esses dados ficam expostos.

**Evidência:** `localStorage.setItem(...)` em múltiplos pontos de `prescritor.html`, `dispensador.html`, `cidadao.html`.

---

### `[MÉDIO]` — Cobertura de testes incompleta

**Problema:** Fluxos críticos (dispensação, agendamento, circulação diagnóstica) têm arquivos de teste presentes mas seus conteúdos não foram verificados diretamente. A cobertura real é desconhecida.

---

### `[MÉDIO]` — Snapshot CNES desatualizado

**Problema:** A validação de prescritor usa snapshot CNES configurado por `CNES_SNAPSHOT_REF` e `CNES_SNAPSHOT_MES`. Sem atualização periódica do snapshot, prestadores novos ou alterações de CBO/conselho não serão detectadas.

**Evidência:** configuração em `config.py`; script de importação em `scripts/` existe mas não há cron/automação confirmada.

---

### `[BAIXO]` — Dois arquivos `app.py` (legacy) e `backend/app/main.py`

**Problema:** Existe um `app.py` no raiz do projeto (legado) em paralelo com `backend/app/main.py` (atual). Risco de confusão sobre qual é o entrypoint correto.

---

## 13. Limites Atuais do MVP

### O que NÃO está implementado

| Item | Status |
|---|---|
| Integração ICP-Brasil real (verificação criptográfica) | `[APENAS DOC]` |
| Adapter HIS, TISS, HL7, e-SUS | `[APENAS DOC]` (requer G4A completo) |
| Dashboard analítico | `[NÃO CONFIRMADO]` |
| Notificações push/SMS ao paciente | `[NÃO CONFIRMADO]` |
| Migração automática de schema (Alembic) | `[NÃO CONFIRMADO]` |
| Multi-tenant com JWT (org_id no token) | `[APENAS DOC]` — planejado após onboarding institucional |
| Score probabilístico por ML | explicitamente fora de escopo |
| Auditoria de acesso a dados (quem consultou o quê) | `[NÃO CONFIRMADO]` |

### Simplificações conscientes documentadas

- **Agendamento → coletado:** `realizado` em agendamento equivale a `coletado` em item de exame (simplificação MVP — "nota MVP" documentada em CLAUDE.md)
- **Ciência do laudo:** opera no nível do laudo inteiro, não por item (exceção documentada ao NUCLEO_SANITARIO)
- **Farmácia hospitalar:** dose unitária e fracionamento são modalidades operacionais, não novos objetos rastreados
- **Fire-and-forget físico:** emissão física pode ocorrer sem persistência central se backend estiver offline
- **Assinatura digital:** metadados registrados como declarados pelo prescritor (stub MVP) — sem verificação criptográfica
- **org_id/unidade_id:** rollout incremental — não estão em todas as tabelas

### Pontos frágeis

- Imutabilidade do ledger mantida por disciplina, não por constraint de banco
- Backend hardcoded no frontend impede deploy sem alteração de código
- Concorrência em SQLite não protegida contra race condition em dispensações simultâneas
- Snapshots CNES dependem de processo manual de importação

---

## 14. Estado de Prontidão

### Pronto para testes funcionais internos?

**Sim**, com ressalvas:
- Fluxos digitais (prescrição → dispensação) estão implementados e testados (96 testes confirmados)
- Frontend cobre todos os módulos principais
- Dados de teste disponíveis via `seed_dev.py`

### Pronto para ambiente real (produção)?

**Não**, pelos seguintes bloqueadores:

1. **Backend hardcoded no frontend** — impede deploy sem alteração de código
2. **SQLite em produção** — sem concorrência adequada para múltiplos usuários simultâneos; migração para PostgreSQL necessária (DDL existe em `docs/`)
3. **TLS não confirmado** — dados sensíveis podem transitar em texto plano
4. **ICP-Brasil não implementado** — assinatura digital não verificada
5. **Rate limiting ausente** — endpoints públicos vulneráveis a abuso
6. **Cobertura de testes de integração** — não confirmada nos fluxos críticos

### Precisa de ajustes?

Sim — os riscos classificados como `[CRÍTICO]` e `[ALTO]` na seção 12 devem ser endereçados antes de qualquer exposição a usuários reais.

---

## 15. Afirmações Não Confirmadas

Lista de itens que **não puderam ser comprovados por leitura direta do código** nesta sessão:

1. **Role `prestador_exame`** — mencionado na documentação de endpoints mas não verificado se existe em `domain/roles.py` como valor RBAC formal
2. **Número exato de testes** em `test_states.py`, `test_ia_farmaceutica.py`, `test_integration.py`, `test_agendamentos.py`, `test_dispensacao_atomizada.py`, `test_dispensacao_hospitalar.py`, `test_tokens_apresentacao.py`, `test_circulacao_diagnostica.py`, `test_circulacao_ticket54.py`, `test_g4b.py`, `test_eventos_publicacao.py`, `test_prestadores.py`, `test_auth_paciente.py`, `test_health.py`, `test_ia_exames.py`, `test_ia_cid.py`, `test_ia_documental.py`
3. **TLS/HTTPS** — Dockerfile e configuração nginx/proxy não verificados para confirmar HTTPS em produção
4. **WAL mode no SQLite** — não confirmado se `PRAGMA journal_mode=WAL` está ativo
5. **Estados exatos da circulação diagnóstica** — arquivo `states_circulacao_diagnostica.py` não lido diretamente
6. **Conteúdo completo de `clinica.html`** quanto à funcionalidade de laudo — frontend de laudo via clinica.html não verificado
7. **Funcionalidade real dos endpoints de auditoria** (`GET /relatorios/dispensacoes.csv`) — não verificados diretamente
8. **`meta_instalacao` e `evento_publicacao`** — tabelas listadas em models, conteúdo completo não verificado
9. **Rate limiting** — ausência confirmada por não encontrar middleware, mas pode existir em configuração de proxy externo
10. **CI/CD pipeline** — não encontrado no repositório; pode existir em sistema externo (GitHub Actions, GitLab CI)
11. **Cobertura real dos testes de IA** — arquivos existem mas testes individuais não foram lidos

---

*Documento gerado com base exclusiva no código real do repositório. Nenhuma afirmação foi extrapolada além do que é observável nos arquivos. Para o estado atualizado de qualquer item, ler o arquivo fonte correspondente indicado em cada seção.*
