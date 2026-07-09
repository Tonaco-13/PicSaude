# PicSaúde — Princípios arquiteturais obrigatórios

> Este arquivo é lido automaticamente pelo Claude Code a cada sessão.
> Qualquer desenvolvedor ou agente que atue neste projeto deve seguir
> estas regras antes de qualquer decisão de implementação.

---

## MAPA RÁPIDO

| Tópico | Seção |
|---|---|
| Regras invioláveis (imutabilidade, ledger, custódia, dispensação parcial) | 1 · 2 · 3 · 4 |
| Estados de prescrição física vs digital | 5 |
| Referência completa de estados (prescrição e item) | 5a |
| Contrato de Estados (invariantes + fonte de verdade) | 5b |
| Emissão exclusivamente física + fire-and-forget | 6 |
| Convenções técnicas (CPF sentinela) | 6a |
| Escopo institucional (org_id + unidade_id) — convenção e guardrail | 6b |
| Modelo generalizável + Núcleo Sanitário (exames, laudos, internações…) | 7 |
| Estrutura de arquivos do projeto | 8 |
| Criar tabelas novas | 9 |
| Taxonomia de contribuição — classificação obrigatória de mudanças | 10 |

---

## 1. Objetos sanitários são imutáveis após emissão

**Regra:** Nunca editar uma prescrição (ou qualquer objeto sanitário) já emitida.
Qualquer alteração gera um **novo objeto derivado**, com `origem_prescricao_id` apontando para o anterior.

```
REC-001 (original) ← REC-002 (correção) ← REC-003 (renovação)
```

Isso vale para: correções, renovações, reemissões, ajustes terapêuticos.

**Violação proibida:** `UPDATE prescricoes SET ... WHERE id = X` após emissão.
**Correto:** `INSERT INTO prescricoes (..., tipo_emissao='correcao', origem_prescricao_id=X)`

---

## 2. O ledger é imutável

A tabela `prescricao_eventos` nunca recebe `UPDATE` nem `DELETE`.
Todo evento de negócio relevante deve gerar um INSERT nessa tabela.

Vocabulário de eventos conhecido:

| Evento | Quando ocorre |
|---|---|
| `prescricao_emitida` | Emissão digital (POST /prescricoes) |
| `prescricao_renovada` | Derivação por renovação |
| `prescricao_corrigida` | Derivação por correção |
| `prescricao_impressa` | **Fluxo físico** — ato de impressão pelo prescritor |
| `encerrada_localmente` | **Fluxo físico** — transição de estado: sem cadeia digital |
| `custodia_transferida` | Transferência entre detentores de custódia |
| `dispensacao_registrada` | Dispensação registrada (total) |
| `dispensacao_parcial` | Dispensação parcial de um item |
| `item_dispensado` | Item individual entregue ao paciente |
| `item_devolvido_paciente` | Item devolvido por abandono de compra |
| `item_devolvido_prescritor` | Item devolvido por erro clínico |
| `erro_prescricao_identificado` | Erro identificado no balcão |
| `pagamento_nao_concluido` | Falha de pagamento no balcão |
| `assinatura_registrada` | Metadados de assinatura digital declarados pelo prescritor (stub MVP) |
| `decisao_clinica_avaliada` | **Camada 3** — trilha de auditoria do semáforo: sinal + versão da regra por item, gravado na emissão (não-bloqueante; só com a flag `PICSAUDE_DECISAO_CLINICA` ativa e `codigo_cid` presente). Ver `docs/EXPLICABILIDADE_DECISAO_CLINICA.md` §11 |
| `pdf_assinado_pades` | Geração de PDF com assinatura ICP-Brasil PAdES-B (cofre server-side). Emitido pela prescrição comum (`POST /prescricoes/{proto}/pdf-assinado`) e pelo receituário. Payload: hash do PDF + serial do certificado |
| `estorno_registrado` | **T2** — reversão de uma dispensação registrada. O estorno é um **objeto sanitário derivado e imutável** (`estornos`, padrão `origem_dispensacao_id`), **não** uma transição de estado do item (a `dispensacoes` original permanece intocada). Efeito contábil: saldo efetivo do item = Σ dispensado − Σ estornado. Emitido por `POST /dispensacoes/{id}/estornar`. Payload: `estorno_id` + `estorno_protocolo` + `origem_dispensacao_id` + `item_id` + `quantidade_estornada` + `motivo` (enum `MOTIVOS_ESTORNO`). Ver `docs/tickets/TICKET-ESTORNO-OBJETO-DERIVADO.md` |

**Fluxo físico emite DOIS eventos em sequência:**
1. `prescricao_impressa` — ato de impressão (quem, quando, quantos itens)
2. `encerrada_localmente` — transição de estado (motivo: emissão exclusivamente física)

Nunca criar endpoints que apaguem ou alterem eventos.

**Invariante de retenção (ratificado por Fabiano, 2026-07-09):** toda retenção de
custódia — **inclusive a auto-retenção** do T1.5 em modo demo — DEVE emitir
`custodia_transferida`. Abrir custódia (`_abrir_custodia`) sem o evento é **bug,
não feature**: o ledger é a fonte da verdade da cadeia de custódia (§3). Em
produção não existe auto-retenção — item não retido → 409 `item_nao_retido`.

---

## 3. Custódia é explícita, granular e rastreável

Cada prescrição tem um **detentor de custódia** a cada momento.
A cadeia de custódia é registrada em `prescricao_custodia`.

Transições permitidas (implementadas em `routers/custodia.py`):
```
prescritor  → paciente       (emissão digital)
paciente    → dispensador    (apresentação no balcão)
dispensador → paciente       (abandono/devolução parcial)
dispensador → prescritor     (erro de prescrição)
paciente    → prescritor     (devolução voluntária)
```

Granularidade: a custódia pode ser por **prescrição inteira** (`item_id = NULL`)
ou por **item individual** (`item_id = X`).

---

## 4. Dispensação parcial é suportada e não invalida a prescrição

A impossibilidade de pagar um item no balcão **não cancela a prescrição**.
O item volta ao estado `pendente` e pode ser dispensado em outra farmácia.

A soma de `quantidade_dispensada` nas `dispensacoes` de um item nunca pode
superar `prescricao_itens.quantidade`.

---

## 5. Estados de prescrição física vs digital

### Fluxo digital

```text
pendente
  -> transferida_paciente
  -> em_custodia
  -> parcialmente_dispensada | dispensada
  -> cancelada   (revogação clínica dentro do fluxo digital)
```

- Itens nesse fluxo participam de custódia e dispensação.
- `cancelada` = decisão clínica ou operacional. Nunca usar para emissão física.

### Fluxo físico

```text
impressa
  -> encerrada_localmente
     -> itens: encerrado_fisico
```

- `encerrado_fisico` = emitido em papel; nunca inserido no ciclo digital.
- Prescrição física não gera custódia.
- Prescrição física não entra no fluxo de dispensação digital.

### Regra semântica obrigatória

```
encerrado_fisico  =  emitido em papel, nunca entrou no ciclo digital   (status de item)
cancelada         =  revogação clínica dentro do fluxo digital          (status de prescrição)
cancelado         =  revogação clínica dentro do fluxo digital          (status de item)
```

---

## 5a. Referência completa de estados

### Prescrição (`prescricoes.status`)
```
pendente                 ← emitida digitalmente, aguarda transferência
transferida_paciente     ← em custódia do cidadão
em_custodia              ← dispensador reteve a prescrição
parcialmente_dispensada  ← ao menos um item dispensado
dispensada               ← todos os itens ativos dispensados
cancelada                ← revogação clínica ou todos os itens encerrados
expirada                 ← data_validade ultrapassada
encerrada_localmente     ← emissão exclusivamente física (terminal)
```

### Item (`prescricao_itens.status_item`)
```
pendente              ← estado inicial do ciclo digital
em_custodia           ← dispensador reteve para dispensação
dispensado            ← entregue ao paciente (terminal)
devolvido_paciente    ← abandono de compra; disponível para nova tentativa
devolvido_prescritor  ← erro identificado; aguarda correção (terminal*)
cancelado             ← revogação clínica (terminal)
estornado             ← dispensação revertida após registro (terminal)
encerrado_fisico      ← emissão física; sem ciclo digital (terminal)
```

`(*)` devolvido_prescritor aguarda nova prescrição derivada com `origem_prescricao_id`.

> ⚠️ **Governança:** Estados de prescrição e de item são parte do modelo de domínio.
> Não criar novos estados sem atualizar esta seção, o DDL em `docs/picsaude_ddl_postgres_v1.sql`
> **e** as constantes em `backend/app/domain/states.py`.

---

## 5b. Contrato de Estados (invariantes)

**Este contrato é a fonte de verdade para estados de prescrição.**

### Estados permitidos

```
Fluxo digital — prescrição:
  pendente | transferida_paciente | em_custodia
  parcialmente_dispensada | dispensada | cancelada

Fluxo físico — prescrição:
  encerrada_localmente

Estados de item:
  pendente | em_custodia | dispensado
  devolvido_paciente | devolvido_prescritor
  cancelado | estornado | encerrado_fisico
```

### Estados terminais

```
Prescrição:  dispensada · cancelada · encerrada_localmente · expirada
Item:        dispensado · devolvido_prescritor · cancelado · estornado · encerrado_fisico
```

### Invariantes

- Prescrições físicas não entram em custódia digital
- Itens `encerrado_fisico` não voltam ao fluxo digital
- `cancelada/cancelado` = revogação clínica; nunca usar para fluxo físico
- Transições válidas estão declaradas em `backend/app/domain/states.py`

---

## 6. Emissão exclusivamente física

Quando o prescritor imprime sem iniciar cadeia digital:
- Status final da prescrição: `encerrada_localmente`
- Status de cada item: `encerrado_fisico`
- Evento no ledger: `prescricao_impressa`
- Sem cadeia de custódia (nenhum registro em `prescricao_custodia`)
- Sem transferência ao paciente

**Trade-off documentado (fire-and-forget):**
O frontend envia o POST `/prescricoes/fisica` sem aguardar resposta (`fire-and-forget`).
Se o backend estiver offline, a impressão ocorre normalmente e o registro fica
apenas no `localStorage`. Consequência aceita: pode haver impressões sem
persistência central. Para rastreabilidade completa, o backend deve estar acessível.

---

## 6a. Convenção técnica — CPF sentinela

O CPF `'00000000000'` é reservado para prescrições físicas sem identificação
digital do paciente. É matematicamente inválido (dígitos verificadores inválidos)
e nunca representa um cidadão real.

Regras de uso:
- Queries analíticas devem excluir: `WHERE cpf != '00000000000'`
- Nunca expor em relatórios de auditoria como identificação real
- Constante no código: `_CPF_NAO_IDENTIFICADO = "00000000000"` em `prescricoes.py`

---

## 6b. Escopo institucional — `org_id` e `unidade_id`

O PicSaúde opera como plataforma multi-institucional. O princípio central é:

> **O objeto clínico é global e neutro. A operação é contextual.**

### Identidade vs. contexto

| Campo | Papel |
|---|---|
| `protocolo` (UUID) | Identidade sanitária global — único, imutável, independente de instituição |
| `org_id` | Entidade jurídica ou rede (ex: hospital X, rede de farmácias Y) |
| `unidade_id` | Unidade operacional física (ex: filial 123, UTI, farmácia hospitalar) |

`org_id` e `unidade_id` **nunca substituem** o protocolo como chave principal.
São usados apenas como: escopo de consulta, filtro de acesso, contexto operacional.

### Convenção de campo vazio (NULL)

```
org_id    = NULL  →  objeto sem escopo institucional obrigatório
unidade_id = NULL →  objeto sem escopo institucional obrigatório
```

`NULL` significa ausência de vínculo institucional — não "público" nem "interno".
Objetos legados (anteriores à adoção de subdomínios) permanecem com `NULL`.

Não criar valor sentinela para org/unidade ausente.

### Rollout incremental

`org_id` e `unidade_id` **não são adicionados em todas as tabelas de uma vez.**
Cada tabela recebe esses campos somente quando um caso de uso real exigir.

Tabelas com escopo institucional ativo:
- `dispensacoes_hospitalares` — `org_id` + `unidade_id` obrigatórios (Ticket 27)
- `prescricao_custodia` — `unidade_id` nullable + `contexto_operacional` nullable (Ticket 27, contexto hospitalar)

Tabelas com exceção documentada (não recebem `org_id`):
- `tokens_apresentacao` — token agnóstico de instituição; contexto entra no uso (ver abaixo)
- `prescricao_itens` — herda contexto via prescrição (JOIN); sem denormalização
- `prescricoes` — rollout incremental; migrar somente quando caso real exigir

### Guardrail obrigatório para queries com escopo institucional

Toda tabela que contiver `org_id` segue esta regra:

> Toda query de leitura ou escrita que opere em contexto institucional **deve**
> incluir `WHERE org_id = ?` (ou equivalente). Se o filtro não se aplicar,
> justificar com comentário inline.

**Violação proibida:** `SELECT * FROM tabela_com_org_id WHERE ...` sem filtro de `org_id`
quando o endpoint tem contexto institucional definido.

**Correto:**
```sql
SELECT * FROM dispensacoes
WHERE org_id = ?       -- escopo institucional obrigatório
  AND protocolo = ?
```

### Tokens de apresentação — exceção documentada

`tokens_apresentacao` **não recebe `org_id`**: o token é emitido pelo paciente e é
agnóstico de instituição (token aberto por decisão do Ticket 24). O contexto
institucional aparece no uso do token, não na emissão — campo `cnpj_estabelecimento`
em `tokens_apresentacao_usos` é suficiente.

### Enforcement via JWT (fase futura)

Na fase atual, `org_id`/`unidade_id` podem entrar pelo payload da request.
Enforcement via JWT (token carregando `org_id` + `unidade_id`) exige fluxo de
onboarding institucional — implementar quando esse fluxo existir.

---

## 7. O modelo é generalizável

A arquitetura de custódia não é exclusiva de prescrições.
Qualquer objeto assistencial futuro deve seguir o mesmo padrão:

| Objeto | Estados típicos |
|---|---|
| Exame | emitido → agendado → coletado → em_analise → resultado_disponivel → encerrado |
| Agendamento | solicitação → reserva → confirmação → comparecimento |
| Laudo | produção → assinatura → liberação → ciência |
| Internação | indicação → autorização → admissão → alta |

Nunca criar tabelas ou endpoints que violem esse modelo de estados.

### Estados do módulo de Pedido de Exame (Tickets 14–17)

Pedido (`pedidos_exame.status`):
```
emitido · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · expirado · encerrado_fisico
```

Item (`pedido_exame_itens.status_item`):
```
pendente · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · encerrado_fisico
```

Custódia: `prescritor → paciente → prestador_exame → paciente`

> Arquitetura completa em `docs/ARQUITETURA_EXAMES.md`

### Estados do módulo de Agendamento (Ticket 28 — arquitetura / Ticket 29 — implementação)

Classificação: **objeto sanitário leve** — tem identidade própria (UUID), estados e ledger, mas sem conteúdo clínico autônomo, sem custódia e sem assinatura. É o elo entre pedido de exame e coleta.

Agendamento (`agendamentos.status`):
```
criado · confirmado · realizado · cancelado · nao_compareceu
```

Regras fundamentais:
- Remarcação = novo objeto derivado (`origem_agendamento_id`), nunca estado `remarcado`
- `agendamento_criado` → itens do pedido: `pendente → agendado`
- `agendamento_realizado` → itens do pedido: `agendado → coletado` *(simplificação MVP)*
- `agendamento_cancelado` / `nao_compareceu` → itens voltam a `pendente`
- `org_id` e `unidade_id` são obrigatórios (NOT NULL) em `agendamentos`
- Sem cadeia de custódia (compromisso bilateral — exceção documentada ao NUCLEO_SANITARIO)

**Nota MVP:** a equivalência `realizado → coletado` é simplificação do MVP. Em contexto real, comparecimento e coleta efetiva podem ser eventos distintos.

> Arquitetura completa em `docs/ARQUITETURA_AGENDAMENTO.md`

### Estados do módulo de Laudo (Tickets 19–21)

Laudo (`laudos.status`):
```
em_producao · assinado · liberado · ciencia_paciente · ciencia_prescritor
encerrado · cancelado · expirado · encerrado_fisico
```

Item (`laudo_itens.status_item`):
```
em_producao · concluido · cancelado · encerrado_fisico
```

Custódia: `prestador_exame → paciente | prescritor`
Origem: responsável técnico (patologista / bioquímico / médico laboratorista)
Ciência: opera no nível do laudo inteiro (exceção documentada ao núcleo)

> Arquitetura completa em `docs/ARQUITETURA_LAUDO.md`

### Estados do módulo de Atestado (objeto sanitário MONOLÍTICO)

Classificação: **objeto sanitário monolítico** — um documento único, **sem itens**
(diferente de prescrição/exame); status direto, não derivado. Tem identidade
(UUID), estados, ledger, custódia e assinatura ICP-Brasil.

Atestado (`atestados.status`):
```
emitido · assinado · cancelado · expirado · encerrada_localmente
```

Regras fundamentais:
- **Sem itens** (exceção documentada ao núcleo, como o agendamento)
- Assinar é marco de estado: `emitido → assinado` (PAdES via cofre)
- CPF do paciente **obrigatório** no digital; sentinela `00000000000` no físico
- `dias_afastamento` é opcional (nem todo atestado afasta — ex.: comparecimento)
- Custódia única: `prescritor → paciente` (emissão); físico não gera custódia
- Validação pública neutra (`GET /public/atestados/{proto}`): confirma existência/
  assinatura/vigência **sem** vazar finalidade, CID, indicação ou identidade

Custódia: `prescritor → paciente`
Eventos: `atestado_emitido · atestado_assinado · atestado_corrigido · atestado_cancelado · atestado_expirado · atestado_impresso · encerrada_localmente · custodia_transferida`

> Arquitetura completa em `docs/ARQUITETURA_ATESTADO.md`

### Farmácia Hospitalar (Ticket 26 — arquitetura / Ticket 27 — implementação)

Classificação: **subdomínio operacional da dispensação** — não é novo objeto sanitário, não é novo papel RBAC.

Regras fundamentais:
- O papel `dispensador` permanece único. O modo hospitalar é contexto operacional (`unidade_id`)
- O paciente não é detentor intermediário no fluxo hospitalar (é beneficiário clínico, não portador ativo)
- Cadeia de custódia hospitalar: `prescritor → farmacia_hospitalar → (unidade_enfermagem) → paciente`
- Dose unitária e fracionamento são modalidades operacionais, não novos objetos rastreados
- A constraint `Σ dispensado ≤ prescrito` permanece idêntica à dispensação ambulatorial
- `dispensacoes_hospitalares` é extensão de `dispensacoes` — não caminho paralelo

**Violação proibida:** criar `prescricao_hospitalar` como tabela separada, ou `dispensador_hospitalar` como papel RBAC.

> Arquitetura completa em `docs/ARQUITETURA_FARMACIA_HOSPITALAR.md`

---

### Núcleo genérico (Ticket 18)

O PicSaúde é uma **infraestrutura de objetos sanitários rastreáveis**, não apenas uma aplicação de prescrição. O padrão arquitetural comum a todos os objetos está formalizado em:

> **`docs/NUCLEO_SANITARIO.md`** — contrato obrigatório para qualquer novo objeto sanitário.

Todo novo objeto (laudo, agendamento, internação, autorização…) deve satisfazer esse contrato antes de ser implementado. O checklist de conformidade está na seção 11 do documento.

---

## 8. Estrutura do projeto

```
backend/
  app/
    models/                    ← SQLAlchemy ORM
      prescricao_assinatura.py ← Ticket 5: metadados de assinatura digital
    routers/                   ← FastAPI endpoints
      assinaturas.py           ← Ticket 5: GET+POST /prescricoes/{proto}/assinatura
      validacao.py             ← Ticket 6: GET /prescricoes/{proto}/validacao
    domain/                    ← Lógica de domínio pura (sem dependência de FastAPI)
      states.py                ← Contrato de estados (prescricoes + itens)
      assinatura.py            ← Modos, níveis formais, status de validação
      documento_canonico.py    ← Documento canônico + hash SHA-256
      pdf_prescricao.py        ← Geração do PDF institucional (Ticket 3)
      validacao_documental.py  ← Motor de validação em 5 camadas (Ticket 6)
    utils/helpers.py           ← normalize_cpf, normalize_cns, normalize_cnpj, normalize_nome
    config.py                  ← DB_PATH (env PIX_SAUDE_DB ou data/pix_saude_pe.db)
    database.py                ← get_conn() para raw SQL, engine/Base para ORM
  init_tables.py               ← rodar após qualquer novo model
data/
  pix_saude_pe.db              ← banco SQLite (CNES + aplicação)
docs/                          ← whitepaper, DDL PostgreSQL, arquitetura
prescritor.html                ← frontend (localStorage + chamadas ao backend)
dispensador.html               ← frontend dispensador
```

### Endpoints ativos (resumo)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/prescricoes` | Emissão digital |
| POST | `/prescricoes/fisica` | Emissão física (fire-and-forget) |
| GET  | `/prescricoes/{proto}/documento` | Documento canônico + integridade |
| GET  | `/prescricoes/{proto}/pdf` | Receita em PDF institucional |
| GET  | `/prescricoes/{proto}/assinatura` | Consultar metadados de assinatura |
| POST | `/prescricoes/{proto}/assinatura` | Registrar metadados de assinatura |
| GET  | `/prescricoes/{proto}/validacao` | Validação documental em 5 camadas |

## 9. Comando para criar tabelas novas

Após criar qualquer novo `model/*.py`, adicionar o nome à lista em
`init_tables.py` e rodar:

```bash
cd backend && python3 init_tables.py
```

---

## 10. Taxonomia de contribuição — classificação obrigatória de mudanças

**Padrão Arquitetural (Jules, PR #84):** estados computados não são persistidos;
flag read-only deriva de fonte autoritativa. Ex.: `cnes_verificado` é derivado de
`estabelecimentos_cnes` em runtime — nunca gravado numa coluna que poderia divergir.

Toda mudança no PicSaúde deve ser classificada antes de ser implementada.
A classificação determina o nível de revisão exigido.

| Classe | O que é | Revisão exigida |
|---|---|---|
| `core` | Altera núcleo: NUCLEO_SANITARIO, ledger, máquina de estados, custódia, RBAC, documento canônico | **Revisão central obrigatória** |
| `module` | Novo objeto sanitário ou extensão de módulo existente (ex: novo endpoint de prescrição) | Checklist NUCLEO_SANITARIO + revisão |
| `adapter` | Integração com sistema externo — **nunca escreve diretamente no banco clínico** | Revisão de contrato de interface |
| `local-extension` | Customização institucional que não altera semântica clínica (ex: campo extra, relatório local) | Revisão de isolamento |
| `docs` | Documentação sem impacto em código executável | Revisão de consistência |
| `ops` | Infraestrutura, empacotamento, scripts, CI/CD | Revisão de segurança operacional |

### O que exige revisão central obrigatória (classe `core`)

Qualquer mudança nas seguintes áreas é `core` e **não pode ser feita sem aprovação**:
- `NUCLEO_SANITARIO.md`
- `CLAUDE.md`
- `ETHICS.md` — não-objetivos éticos (ex.: sem monetização de dado do paciente; ver guard-rail em `backend/tests/test_guardrail_sem_monetizacao.py`)
- Máquinas de estados oficiais (`domain/states*.py`)
- Ledger (`*_eventos` — qualquer nova tabela ou alteração de semântica)
- Cadeia de custódia (`prescricao_custodia` ou equivalente)
- Documento canônico e assinatura (`domain/documento_canonico.py`)
- Protocolos públicos (endpoints `/public/*`)
- RBAC e autenticação (`auth/`)

### Regra para adapters (classe `adapter`)

```
adapter NUNCA:
  - escreve diretamente em tabelas clínicas (prescricoes, dispensacoes, etc.)
  - emite eventos no ledger diretamente via SQL
  - bypassa endpoints oficiais
  - altera estados de objetos sanitários sem passar pela API

adapter SEMPRE:
  - consome eventos ou endpoints oficiais do PicSaúde
  - tem seu próprio banco ou store (se precisar de persistência)
  - é observável (logs, health check)
  - é versionado independentemente do núcleo
```

### Regra para extensões locais (classe `local-extension`)

```
local-extension NUNCA:
  - altera semântica clínica dos objetos (estados, ledger, custódia)
  - quebra contratos públicos existentes
  - adiciona campos obrigatórios a tabelas do núcleo

local-extension PODE:
  - adicionar campos opcionais com NULL default
  - criar tabelas auxiliares próprias
  - customizar UI sem alterar API
  - adicionar relatórios e dashboards
```

### Nota sobre a camada de publicação de eventos (G4)

O PicSaúde é atualmente **event-sourced internamente** (ledger imutável) mas **não é event-driven externamente** — não há mecanismo de publicação de eventos para consumo externo.

Antes de qualquer adapter real ser construído, é necessário implementar a **Event Publishing Layer (G4A)**:
- Endpoints de polling de eventos: `GET /eventos?since=...&org_id=...`
- Registro de webhooks por org_id (futuro)
- Formato canônico de evento externo

**Sem G4A, adapters não têm onde se conectar.** Não iniciar adapter de HIS, TISS, HL7, e-SUS, ou qualquer sistema externo antes de G4A existir.
