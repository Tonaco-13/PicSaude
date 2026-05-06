# PicSaúde — Arquitetura da Farmácia Hospitalar

> **Status:** Documento arquitetural ativo — v1.0
> **Ticket:** 26
> **Pré-requisitos:** NUCLEO_SANITARIO.md v1.1, CLAUDE.md §6b (subdomínios institucionais),
> Tickets 1–25 (prescrição, dispensação ambulatorial, token de apresentação)
> **Propósito:** Definir a Farmácia Hospitalar como subdomínio operacional da dispensação,
> sem implementar backend neste ticket.

---

## Mapa rápido

| Tópico | Seção |
|---|---|
| Classificação no domínio PicSaúde | 1 |
| Diferenciação: hospitalar vs. ambulatorial | 2 |
| Cadeia de custódia hospitalar | 3 |
| Novos atores e contextos — classificação | 4 |
| Dispensação hospitalar — modelagem | 5 |
| Escopo institucional (org_id / unidade_id) | 6 |
| Papel vs. contexto — dispensador permanece único | 7 |
| Fora do MVP | 8 |
| Checklist de aderência ao NUCLEO_SANITARIO.md | 9 |
| Recomendação — Ticket 27 | 10 |

---

## 1. Classificação no domínio PicSaúde

**A Farmácia Hospitalar é um subdomínio operacional da dispensação.**

Não é:
- Um novo objeto sanitário (não satisfaz o checklist do NUCLEO_SANITARIO de forma independente)
- Um produto separado
- Um novo papel RBAC
- Uma extensão do modelo de prescrição

É:
- O mesmo fluxo de dispensação com contexto operacional diferente
- Granularidade distinta (dose unitária, fracionamento)
- Cadeia de custódia adaptada ao ambiente de internação
- Atores operacionais adicionais (unidade de enfermagem, leito) que são contexto, não identidade sanitária

**Analogia:**
Assim como o CPF sentinela `'00000000000'` não criou um novo tipo de paciente — apenas formalizou um contexto (emissão física sem identificação digital) — a Farmácia Hospitalar não cria um novo tipo de dispensação. Formaliza o contexto em que ela ocorre.

**Princípio:**
> O objeto clínico rastreado continua sendo o item da prescrição.
> O que muda é o percurso institucional da dispensação.

---

## 2. Diferenciação: hospitalar vs. ambulatorial

### O que é igual

| Aspecto | Ambulatorial | Hospitalar |
|---|---|---|
| Objeto clínico | Item de prescrição | Item de prescrição |
| Identidade | Protocolo UUID | Protocolo UUID |
| Ledger | prescricao_eventos | prescricao_eventos |
| Regra de quantidade | Σ dispensado ≤ prescrito | Σ dispensado ≤ prescrito |
| Papel do dispensador | dispensador | dispensador |
| Validação da prescrição | GET /prescricoes/{proto} | GET /prescricoes/{proto} |
| IA farmacêutica | alertas na dispensação | alertas na dispensação |
| Imutabilidade | prescrição imutável | prescrição imutável |

### O que muda

| Aspecto | Ambulatorial | Hospitalar |
|---|---|---|
| Destino da dispensação | Paciente diretamente | Unidade de enfermagem / setor |
| Paciente como detentor intermediário | Sim (custódia paciente→dispensador) | Não — paciente é beneficiário, não portador |
| Granularidade mínima | Item completo ou parcial | Pode ser dose unitária |
| Fracionamento | Não previsto | Previsto (múltiplas entregas do mesmo item ao longo da internação) |
| Contexto de entrega | CNPJ do estabelecimento | CNPJ + unidade + setor + leito |
| Token de apresentação | Gerado pelo paciente | Desnecessário — prescr. segue o paciente internado |
| Controle de substâncias | Regra geral | Reforçado (psicotrópicos, opioides) — fora do MVP |
| `org_id` / `unidade_id` | Opcional (contexto ambulatorial) | Obrigatório (contexto hospitalar exige rastreabilidade institucional) |

### O que é realmente novo no domínio

1. **A unidade de enfermagem como destino operacional** — a dispensação não termina com o paciente recebendo o medicamento nas mãos; termina com a entrega ao setor que administrará.

2. **Dispensação fracionada ao longo da internação** — o mesmo item de prescrição pode ser dispensado em múltiplos eventos (dia 1: 10 doses, dia 3: 10 doses), todos contabilizados contra a `quantidade` prescrita.

3. **Dose unitária como subdivisão operacional** — a quantidade prescrita em unidades (ex.: 30 comprimidos) é dispensada em doses individuais para controle de administração.

4. **Internação como contexto implícito** — o paciente está "no sistema" de forma contínua; não apresenta prescrição proativamente como no ambulatorial.

### O que é apenas contexto operacional diferente

- O `dispensador` que opera na farmácia hospitalar não é um ator diferente — é o mesmo papel com `unidade_id` apontando para a farmácia hospitalar.
- O `leito` e o `setor` não alteram a semântica clínica dos eventos — são atributos operacionais do registro de dispensação.
- A validação da prescrição ocorre pelo mesmo endpoint público — o contexto institucional não muda o documento sanitário.

---

## 3. Cadeia de custódia hospitalar

### Fluxo ambulatorial (atual)

```
prescritor
    ↓ emissão digital
paciente                    ← detentor ativo (carrega a prescrição)
    ↓ apresentação no balcão
dispensador (farmácia)      ← recebe, valida, dispensa
    ↓ entrega
paciente                    ← detentor final (medicamento em mãos)
```

### Fluxo hospitalar (proposto)

```
prescritor (médico hospitalar)
    ↓ emissão digital (mesma rota POST /prescricoes)
farmacia_hospitalar          ← recebe diretamente (sem intermediário paciente)
    ↓ validação farmacêutica
farmacia_hospitalar          ← prepara / fraciona / dispensa
    ↓ dispensação para setor
unidade_enfermagem           ← contexto de entrega (setor/leito)
    ↓ administração pelo enfermeiro  [FORA DO MVP]
paciente                     ← beneficiário final (administração confirmada) [FORA DO MVP]
```

### Decisão crítica: o paciente não é detentor intermediário no fluxo hospitalar

No ambulatorial, o paciente ativa o fluxo: vai até a farmácia, apresenta a prescrição (ou token), recebe o medicamento. Ele é ator operacional.

No hospitalar, o paciente está internado e não age ativamente sobre a prescrição. A prescrição segue o paciente institucionalmente — não o contrário. O paciente permanece como **beneficiário clínico** (identificado no `paciente_id` da prescrição), mas não aparece como **detentor de custódia** na cadeia hospitalar.

**Transições de custódia válidas no contexto hospitalar:**

```
prescritor → farmacia_hospitalar       (emissão para internado — sem passar por paciente)
farmacia_hospitalar → dispensado_internacao  (dispensação registrada com contexto de unidade)
```

**Transições do modelo ambulatorial que não se aplicam no hospitalar:**

```
paciente → dispensador       ← não ocorre (paciente não "apresenta" prescrição)
dispensador → paciente       ← não ocorre como custódia; ocorre como administração
```

**Como implementar sem criar novo tipo de detentor:**

A transição `prescritor → farmacia_hospitalar` é mapeada como:

```
de_detentor:  prescritor
para_detentor: dispensador
contexto_operacional: hospitalar   ← novo campo em prescricao_custodia (MVP)
unidade_id: {id da farmácia hospitalar}
```

O `para_detentor` continua sendo `dispensador` — o campo `contexto_operacional` e `unidade_id` qualificam sem criar novo ator.

### Pergunta: a unidade de enfermagem é ator de custódia?

**Resposta para MVP:** não. É contexto operacional registrado no ato da dispensação.

**Razão:** Transformar `unidade_enfermagem` em ator de custódia exige que ela "aceite" a transferência, "devolva" em caso de problema, e tenha identidade rastreável no sistema. Isso implica cadastro de unidades, gestão de responsáveis, e endpoints de transferência intra-hospitalar — fora do escopo MVP.

**Evolução futura:** quando o PicSaúde avançar para rastreabilidade de administração à beira-leito, `unidade_enfermagem` torna-se ator de custódia com transição explícita:

```
farmacia_hospitalar → unidade_enfermagem → (administração confirmada)
```

### Pergunta: o leito é ator, contexto ou atributo?

**Resposta:** Atributo operacional da dispensação.

O leito identifica onde o paciente está no momento da dispensação. Não detém custódia, não transfere medicamento, não assina eventos. É o equivalente hospitalar do `cnpj_estabelecimento` ambulatorial — contextualiza onde ocorreu a operação.

---

## 4. Novos atores e contextos — classificação

| Conceito | Classificação | Justificativa |
|---|---|---|
| `farmacia_hospitalar` | Contexto operacional do `dispensador` | O ator é `dispensador`; a farmácia hospitalar é o `unidade_id` dele |
| `unidade_enfermagem` | Contexto operacional da dispensação (MVP) / Futuro ator de custódia | No MVP: atributo do registro; no futuro: receptor da dispensação |
| `setor` | Atributo operacional da dispensação | Ex.: UTI, CCO, Oncologia — texto livre ou referência |
| `leito` | Atributo operacional da dispensação | Identificador do leito onde o paciente está; muda ao longo da internação |
| `internacao` | Contexto implícito (MVP) / Futuro objeto sanitário-adjacente | Agrupa as dispensações de um paciente internado; não é sanitary object completo |
| `responsavel_administracao` | Fora do MVP | Enfermeiro que administra — exige módulo próprio |

### O que não deve ser introduzido agora

- `farmaceutico_clinico` como papel RBAC — é um `dispensador` com qualificação implícita no contexto hospitalar
- `prescritor_hospitalar` como papel RBAC — é um `prescritor` com `unidade_id` hospitalar
- `paciente_internado` como subtipo — é o mesmo `paciente` com atributo de internação
- `receita_hospitalar` como objeto sanitário separado — é uma `prescricao` com contexto hospitalar

---

## 5. Dispensação hospitalar — modelagem

### Continua sendo "dispensação de item de prescrição"?

**Sim.** O item da prescrição permanece o objeto rastreado principal. A regra de negócio central não muda:

```
Σ quantidade_dispensada (todos os eventos para este item) ≤ prescricao_itens.quantidade
```

O que muda é como a quantidade é subdividida e para onde vai.

### Dose unitária como subdivisão operacional

Na farmácia hospitalar, a dose unitária é uma modalidade de dispensação em que o medicamento é entregue em doses individuais (1 comprimido, 1 frasco-ampola) por período de tempo, em vez da embalagem comercial completa.

Modelagem proposta:

```
dispensacoes (existente)
    id, protocolo, item_id, quantidade_dispensada, cnpj_estabelecimento, ...

dispensacoes_hospitalares (nova — contexto hospitalar da dispensação)
    id                   PK
    dispensacao_id       FK → dispensacoes.id  (liga ao registro base)
    org_id               TEXT NOT NULL          (obrigatório para hospitalar)
    unidade_id           TEXT NOT NULL          (farmácia hospitalar específica)
    unidade_enfermagem   TEXT                   (setor/ward destino)
    setor                TEXT                   (UTI, Clínica Médica, etc.)
    leito                TEXT                   (identificador do leito)
    modalidade           TEXT NOT NULL          (internacao | urgencia_emergencia | cirurgia)
    dose_unitaria        BOOLEAN DEFAULT FALSE  (TRUE = dispensado em doses)
    numero_doses         INTEGER                (quando dose_unitaria = TRUE)
    internacao_ref       TEXT                   (referência externa ao prontuário, nullable)
    observacao           TEXT
    criado_em            TEXT NOT NULL
```

**Por que tabela separada e não colunas extras em `dispensacoes`?**

- `dispensacoes` é uma tabela ambulatorial consolidada — adicionar campos hospitalares nulos em registros ambulatoriais seria ruído semântico
- A separação segue o princípio de subdomínio: o registro base vai para `dispensacoes` (mesma auditoria, mesmo ledger), o contexto hospitalar vai para a extensão
- Permite queries hospitalares sem varredura de toda a tabela de dispensações
- É reversível: se o modelo hospitalar evoluir substancialmente, a extensão pode ser refatorada sem afetar o ambulatorial

### Fracionamento ao longo da internação

O mesmo item de prescrição pode ser dispensado em múltiplos eventos:

```
Prescrição: AMOXICILINA 500mg, quantidade = 42 comprimidos (14 dias, 3x/dia)

Dia 1:  dispensacoes.quantidade_dispensada = 21   → dispensacoes_hospitalares.numero_doses = 21
Dia 7:  dispensacoes.quantidade_dispensada = 21   → dispensacoes_hospitalares.numero_doses = 21

Σ = 42 ≤ 42 ✓
```

A constraint de quantidade é verificada no mesmo ponto de sempre — antes do INSERT em `dispensacoes`.

### Unidade mínima rastreada

Para o MVP: o **item da prescrição** continua sendo a unidade mínima rastreada. A dose é um atributo quantitativo, não uma entidade rastreável separada.

Evolução futura (fora do MVP): `doses_administradas` como tabela de confirmação de administração à beira-leito — mas isso exige módulo de enfermagem.

### Psicotrópicos e controle reforçado

**Fora do MVP** (documentado na seção 8). A arquitetura não impede — o campo `categoria_controle_sanitario` pode ser adicionado a `prescricao_itens` futuramente, com lógica específica na camada de dispensação hospitalar para exigir dupla validação.

---

## 6. Escopo institucional — `org_id` e `unidade_id`

Seguindo a diretriz §6b do CLAUDE.md (rollout incremental, sem migração prematura):

### Tabelas que nascem com `org_id` + `unidade_id` (Ticket 27+)

| Tabela | `org_id` | `unidade_id` | Justificativa |
|---|---|---|---|
| `dispensacoes_hospitalares` | Obrigatório | Obrigatório | Contexto hospitalar sem org é inválido |
| `unidades_enfermagem` (se criada) | Obrigatório | — | Referência de unidades da organização |
| `internacoes` (se criada, futuro) | Obrigatório | Obrigatório | Internação é por definição institucional |

### Tabelas que NÃO recebem `org_id` agora

| Tabela | Razão |
|---|---|
| `prescricoes` | Diretriz §6b — migração incremental; a prescrição hospitalar usa o mesmo endpoint |
| `dispensacoes` | Tabela existente ambulatorial — não contaminar |
| `tokens_apresentacao` | Exceção documentada — token é agnóstico de instituição |
| `prescricao_itens` | Herda contexto via prescrição (JOIN) |
| `prescricao_custodia` | Custódia é do objeto, não da instituição; adicionar `contexto_operacional` e `unidade_id` como campos nullable é suficiente |

### Como `prescricao_custodia` absorve o contexto hospitalar

Em vez de criar nova tabela de custódia hospitalar, adicionar dois campos nullable à tabela existente:

```sql
ALTER TABLE prescricao_custodia ADD COLUMN contexto_operacional TEXT;  -- 'ambulatorial' | 'hospitalar' | 'urgencia'
ALTER TABLE prescricao_custodia ADD COLUMN unidade_id TEXT;             -- FK lógica para unidade hospitalar
```

`NULL` em ambos = comportamento ambulatorial existente (compatibilidade total).

### Como `org_id` chega ao contexto hospitalar

Fase atual (Ticket 27): `org_id` e `unidade_id` entram pelo payload da request de dispensação hospitalar.

```json
POST /prescricoes/{proto}/itens/{id}/dispensar/hospitalar
{
  "quantidade_dispensada": 21,
  "cnpj_estabelecimento": "12345678000195",
  "org_id": "HOSP-ALBERT-EINSTEIN",
  "unidade_id": "FARM-HOSP-CENTRAL",
  "unidade_enfermagem": "UTI-ADULTO",
  "leito": "12A",
  ...
}
```

Fase futura: `org_id` + `unidade_id` virão do JWT do usuário autenticado (onboarding institucional).

---

## 7. Papel vs. contexto — dispensador permanece único

### Declaração formal

O papel RBAC `dispensador` é **único e indivisível** no PicSaúde.
Não existe `dispensador_hospitalar`, `farmaceutico_clinico`, `dispensador_ambulatorial`.

O modo hospitalar é um **contexto operacional**, não um papel.

### O que isso implica

**Para o backend:**
- Todos os endpoints de dispensação verificam `require_role("dispensador", "admin")`
- O contexto hospitalar é identificado pelo payload (presença de `unidade_id` hospitalar) ou por header de contexto, não pelo papel no JWT
- A autorização de acesso a uma unidade hospitalar específica — quando implementada — será verificada contra `unidade_id` no payload vs. unidades permitidas no JWT, sem criar novo papel

**Para o frontend:**
- O `dispensador.html` não precisa de uma "versão hospitalar" separada — ele pode renderizar formulários adicionais condicionalmente baseado em `modalidade: "hospitalar"`
- O token de apresentação não muda — o farmacêutico hospitalar pode usá-lo se o paciente gerá-lo, mas na internação o fluxo típico é direto por protocolo
- A IA farmacêutica já passa `contexto="dispensacao"` — pode evoluir para `contexto="dispensacao_hospitalar"` sem mudança de papel

**Para auditoria:**
- Todos os eventos no ledger (`prescricao_eventos`) mantêm o mesmo vocabulário
- O contexto hospitalar aparece em `dispensacoes_hospitalares` para rastreabilidade específica
- Relatórios de auditoria institucional filtram por `org_id` / `unidade_id`, não por papel do dispensador

### Por que isso é importante

Criar `dispensador_hospitalar` como papel separado causaria:
- Duplicação de todos os endpoints de dispensação
- Complexidade de JWT crescente (papéis específicos de contexto)
- Impossibilidade de um farmacêutico operar em ambos os contextos sem dois logins
- Divergência com o princípio do NUCLEO_SANITARIO: "abstrair estrutura, não vocabulário"

---

## 8. Fora do MVP

Os itens abaixo são reconhecidos como relevantes para uma Farmácia Hospitalar completa, mas **não entram no MVP** do PicSaúde. São documentados aqui para informar decisões futuras sem contaminar o escopo atual.

### Integrações externas

| Item | Motivo da exclusão |
|---|---|
| Integração com HIS/prontuário (MV, Tasy, Soul MV) | Requer adapter layer + mapeamento de IDs externos |
| Integração com estoque/almoxarifado | Módulo logístico independente do sanitário |
| Integração com faturamento/APAC/TISS | Requer domínio regulatório específico |
| Integração com INCA/RENAME/REMUME | Referências de medicamentos hospitalares — ETL separado |

### Fluxos clínicos avançados

| Item | Motivo da exclusão |
|---|---|
| Aprazamento (scheduling de doses) | Requer módulo de programação com tempo — novo objeto |
| Confirmação de administração à beira-leito | Requer ator enfermeiro + app de beira-leito |
| Reconciliação medicamentosa | Requer comparação entre prescrições — lógica complexa |
| Revisão farmacêutica clínica (farmacêutico clínico) | Requer workflow de aprovação — novo papel funcional |
| Devolução de medicamento não administrado | Requer rastreabilidade de dose — fora do modelo atual |

### Controle de substâncias reforçado

| Item | Motivo da exclusão |
|---|---|
| Psicotrópicos (Portaria SVS/MS 344/98) | Exige: dupla assinatura, escrituração, SNGPC |
| Opioides (controle nível 2) | Exige: receituário específico, rastreabilidade de lote |
| Imunobiológicos | Rastreabilidade de temperatura (cold chain) |
| Hemoderivados | Domínio próprio (ANVISA + hemovigilância) |

### Objetos sanitários novos (não implementar ainda)

| Item | Observação |
|---|---|
| `internacao` como objeto sanitário | Satisfaria NUCLEO_SANITARIO? Sim, parcialmente. Mas o caso de uso hospitalar não exige isso no MVP — internação é contexto, não objeto rastreado |
| `dose_administrada` como entidade rastreável | Só faz sentido quando confirmar administração for um requisito |
| `unidade_enfermagem` como ator de custódia | Implica onboarding de unidades, responsáveis, endpoints de transferência intra-hospitalar |

---

## 9. Checklist de aderência ao NUCLEO_SANITARIO.md

A Farmácia Hospitalar **não é um novo objeto sanitário** — por isso o checklist do NUCLEO_SANITARIO não precisa ser satisfeito integralmente. O que deve ser verificado é a aderência como extensão de subdomínio.

### O que herda integralmente do núcleo

| Contrato | Como herda |
|---|---|
| Protocolo como identidade global | A prescrição hospitalar usa o mesmo `protocolo` UUID |
| Ledger imutável | `prescricao_eventos` — sem alteração |
| Imutabilidade do objeto principal | Prescrição hospitalar nunca editada após emissão |
| Estados e transições | `prescricao_itens.status_item` — mesma máquina |
| Constraint de quantidade | Σ dispensado ≤ prescrito — idêntica |
| PDF institucional | Mesmo endpoint — contexto hospitalar não muda o documento canônico |
| Validação pública | Mesmo endpoint `/public/prescricoes/{proto}` |
| RBAC | `dispensador` — sem alteração de papel |

### O que entra como contexto operacional (extensão)

| Aspecto | Extensão proposta |
|---|---|
| Destino da dispensação | `dispensacoes_hospitalares.unidade_enfermagem + leito + setor` |
| Granularidade de dispensação | `dose_unitaria + numero_doses` em `dispensacoes_hospitalares` |
| Contexto institucional | `org_id + unidade_id` obrigatórios em `dispensacoes_hospitalares` |
| Custódia sem intermediário paciente | `contexto_operacional` em `prescricao_custodia` |
| Fracionamento ao longo da internação | Múltiplos registros em `dispensacoes` + `dispensacoes_hospitalares` |

### O que exigiria futura revisão do núcleo

| Aspecto | Quando revisar |
|---|---|
| `unidade_enfermagem` como ator de custódia | Quando administração à beira-leito for implementada |
| `internacao` como objeto sanitário-adjacente | Quando internação precisar de ledger e estados próprios |
| Dose como unidade mínima rastreada | Quando confirmação de administração for requisito |
| Novo vocabulário de eventos no ledger | `dispensacao_hospitalar_registrada`, `dose_unitaria_dispensada` — quando o MVP hospitalar for implementado |

### Invariantes que não podem ser violadas

```
✗ PROIBIDO: criar prescricao_hospitalar como tabela separada
✗ PROIBIDO: criar dispensador_hospitalar como papel RBAC
✗ PROIBIDO: contornar a constraint Σ dispensado ≤ prescrito para doses unitárias
✗ PROIBIDO: criar eventos de ledger genéricos como objeto_dispensado
✗ PROIBIDO: adicionar org_id em tokens_apresentacao
✗ PROIBIDO: migrar prescricoes com org_id antes de um caso real exigir
```

---

## 10. Recomendação — Ticket 27

### O que o Ticket 27 deve implementar

**A menor implementação correta para a Farmácia Hospitalar no MVP:**

#### 1. Campos nullable em `prescricao_custodia`

```sql
ALTER TABLE prescricao_custodia
    ADD COLUMN contexto_operacional TEXT DEFAULT NULL;  -- 'ambulatorial' | 'hospitalar'
ALTER TABLE prescricao_custodia
    ADD COLUMN unidade_id TEXT DEFAULT NULL;
```

Isso permite registrar a transferência direta `prescritor → dispensador` com contexto hospitalar, sem criar nova tabela de custódia.

#### 2. Nova tabela `dispensacoes_hospitalares`

Tabela de extensão que acompanha qualquer registro de `dispensacoes` com contexto hospitalar. O registro base continua sendo criado em `dispensacoes` (mesma lógica, mesma auditoria).

Campos obrigatórios: `dispensacao_id`, `org_id`, `unidade_id`, `modalidade`, `criado_em`
Campos opcionais: `unidade_enfermagem`, `setor`, `leito`, `dose_unitaria`, `numero_doses`, `internacao_ref`, `observacao`

#### 3. Novo endpoint de dispensação hospitalar

```
POST /prescricoes/{proto}/itens/{id}/dispensar/hospitalar
```

Aceita o payload base de dispensação + campos hospitalares. Internamente:
1. Valida prescrição e item (mesma lógica)
2. Cria registro em `dispensacoes` (mesma tabela, mesma auditoria)
3. Cria registro em `dispensacoes_hospitalares` (contexto)
4. Registra custódia com `contexto_operacional = 'hospitalar'`
5. Emite evento no ledger: `dispensacao_hospitalar_registrada`

#### 4. Extensão do `dispensador.html`

Formulário condicional: quando `modalidade = "hospitalar"` selecionado, exibir campos de `unidade_enfermagem`, `setor`, `leito`. Nenhum campo hospitalar é obrigatório para a dispensação ambulatorial existente.

### O que o Ticket 27 NÃO deve implementar

- Módulo de internação
- Confirmação de administração
- Psicotrópicos
- Fracionamento automatizado
- Integração com HIS

### Sequência recomendada

```
Ticket 27: Backend + Frontend — Dispensação Hospitalar (MVP)
    │
    ├── migration: ALTER TABLE prescricao_custodia (2 colunas)
    ├── model: dispensacoes_hospitalares (novo)
    ├── router: POST /prescricoes/{proto}/itens/{id}/dispensar/hospitalar
    ├── frontend: dispensador.html — formulário condicional hospitalar
    └── tests: suite hospitalar (≥ 15 testes)

Ticket 28 (futuro): Rastreabilidade de administração / dose_administrada
Ticket 29 (futuro): internacao como objeto de contexto
Ticket 30 (futuro): Psicotrópicos — controle reforçado
```

---

## Referências internas

| Documento | Relevância |
|---|---|
| `CLAUDE.md §6b` | Diretriz de org_id / unidade_id — rollout incremental |
| `docs/NUCLEO_SANITARIO.md` | Contrato de objeto sanitário — base desta arquitetura |
| `docs/ARQUITETURA.md` | Visão arquitetural completa do sistema |
| `backend/app/routers/dispensacoes.py` | Implementação atual da dispensação ambulatorial |
| `backend/app/domain/states.py` | Estados de prescrição e item — não alterar para hospitalar |

---

*v1.0 — Ticket 26. Farmácia Hospitalar classificada como subdomínio operacional da dispensação. Sem implementação neste ticket.*
