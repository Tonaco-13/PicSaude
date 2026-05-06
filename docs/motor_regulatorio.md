# Motor Regulatório — RDC Anvisa 1.000/2025 (Ticket 15)

> Esta documentação descreve o **motor regulatório local** do PicSaúde: a
> camada de domínio que classifica itens de prescrição em grupos
> regulatórios, deriva receituários (amarela / azul / branca / simples) e
> valida se a assinatura presente atende ao nível exigido por cada grupo.
>
> Referências normativas: **RDC Anvisa nº 1.000/2025 (SNCR)**, **Portaria
> SVS/MS nº 344/1998**, **RDC Anvisa nº 471/2021**. Prazo de adequação ao
> SNCR: **1º de junho de 2026**.

---

## 1. Objetivo

Uma única prescrição clínica pode conter medicamentos de categorias
regulatórias distintas (psicotrópico + antimicrobiano + analgésico comum,
por exemplo). Para cada tipo de controle, a legislação exige um
**receituário diferente** — com cor, número de vias e exigência de
assinatura próprios.

O motor regulatório transforma **1 prescrição clínica → N receituários
regulatórios**, preservando rastreabilidade e auditoria. É o "cérebro" local
do PicSaúde para a conformidade com a RDC 1.000/2025; **não** é a integração
com a API SNCR (escopo do Ticket 16).

---

## 2. Mapeamento completo — classe × grupo × receituário

| Classe (`classe_controle`) | Grupo                                 | Tipo de receituário                  | Vias | Retenção | Assinatura mínima | SNCR  |
|---|---|---|---|---|---|---|
| A1, A2, A3                 | Notificação de Receita A (Amarela)    | `notificacao_receita_a`              | 3    | sim      | `qualificada`     | sim   |
| B1, B2                     | Notificação de Receita B (Azul)       | `notificacao_receita_b`              | 2    | sim      | `qualificada`     | sim   |
| C5                         | Receita de Controle Especial (Branca) | `receita_controle_especial`          | 2    | sim      | `qualificada`     | sim   |
| D1, D2                     | Notificação de Receita Especial       | `notificacao_receita_especial`       | 2    | sim      | `qualificada`     | sim   |
| _(pendente)_               | Receita com Retenção (RDC 471/2021)   | `receita_retencao`                   | 2    | sim      | `avancada`        | não   |
| NULL / vazio               | Receita Simples                       | `receita_simples`                    | 1    | não      | `nenhuma`         | não   |

**Nota — Grupo 3:** o prompt original deste ticket menciona C1 neste grupo.
`CLASSES_CONTROLE_ESPECIAL` em [`medicamento.py`](../backend/app/domain/medicamento.py)
**não inclui C1 hoje** — apenas C5. Mantemos C5 como única classe do grupo;
quando C1 for introduzido no modelo, basta adicioná-lo ao `frozenset`
`GRUPO_C.classes` em [`motor_regulatorio.py`](../backend/app/domain/motor_regulatorio.py).

**Nota — Grupo 5 (Retenção):** **ativo desde Ticket 18.** Roteado pelo
campo `tipo_retencao` (RDC 471/2021 + IN 83/2021 + IN 360/2025),
sistema regulatório independente da Portaria 344. Valores aceitos:
`"antimicrobiano"` e `"glp1_agonista"`. Ver
[`grupo_retencao.md`](grupo_retencao.md) para detalhes.

---

## 3. Fluxo de geração

```
POST /prescricoes/{protocolo}/receituarios/gerar
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 1. Carregar prescrição + itens       │
   │    (verificar posse pelo CNS do JWT) │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 2. agrupar_por_receituario()         │
   │    classe → grupo → bucket           │
   │    (ordenado por severidade)         │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 3. Para cada receituário:            │
   │    validar_assinatura_para_…()       │
   │    → valido? motivo_rejeicao?        │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 4. Idempotência:                     │
   │    snapshot existente == novo? →     │
   │       retornar existentes            │
   │    senão → marcar antigos como       │
   │       substituido_em e persistir     │
   │       novos                          │
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 5. INSERT em prescricao_eventos      │
   │    tipo_evento='receituarios_gerados'│
   └──────────────────────────────────────┘
              │
              ▼
   ┌──────────────────────────────────────┐
   │ 6. Resposta JSON com N receituários  │
   └──────────────────────────────────────┘
```

---

## 4. Regras de agrupamento

Implementadas em `agrupar_por_receituario()`:

1. Cada item da prescrição é roteado ao grupo de sua `classe_controle` via
   `grupo_regulatorio()`.
2. Itens do mesmo grupo permanecem juntos — um único receituário agrega
   todos os itens do grupo (ex.: 2×B1 + 1×B2 → 1 receituário `notificacao_receita_b`
   com 3 itens).
3. Grupos distintos geram receituários distintos.
4. A lista de saída é ordenada por **severidade regulatória crescente**
   (campo `severidade` no `GrupoRegulatorio`): Grupo A (1) → Grupo B (2)
   → Grupo C (3) → Grupo D (4) → Retenção (5) → Simples (99).
5. Classe desconhecida ⇒ `ValueError` (endpoint retorna HTTP 422).
6. Cada receituário herda: `prescricao_id`, `protocolo_prescricao`, os
   itens do grupo, o nível de assinatura mínima, número de vias,
   retenção e exigência SNCR.

**Numeração SNCR** (`numeracao_sncr`) fica `NULL` neste ticket — será
preenchida no Ticket 16 via integração com a API do SNCR.

---

## 5. Validação de assinatura

Hierarquia (forte → fraca):

```
qualificada  (ICP-Brasil, assinatura_modo='icp_brasil_local')
   │
   ▼
avancada     (gov.br, assinatura_modo='gov_br_nuvem')
   │
   ▼
nenhuma      (assinatura_modo=None ou vazio)
```

Um nível presente **atende** a qualquer nível exigido de mesma ou menor
força. Exemplos:

| `assinatura_modo` da prescrição | Grupo exige | Resultado                |
|---|---|---|
| `icp_brasil_local`              | qualificada | ✅ válido                |
| `icp_brasil_local`              | avancada    | ✅ válido                |
| `gov_br_nuvem`                  | qualificada | ❌ rejeitado (motivo explicado) |
| `gov_br_nuvem`                  | avancada    | ✅ válido                |
| `None`                          | qualificada | ❌ rejeitado             |
| qualquer                        | nenhuma     | ✅ válido                |

**A validação é informativa, não bloqueia a geração.** O campo
`receituarios.assinatura_valida` é persistido com o resultado; o consumidor
do endpoint decide se usa o receituário (ex.: emissão para farmácia) ou se
trava o fluxo. Esse desacoplamento evita regressão no fluxo existente de
emissão de prescrição (Ticket 1–14).

---

## 6. Modelo de dados

### `receituarios`

| Coluna               | Tipo         | Nullable | Observação |
|---|---|---|---|
| `id`                 | Integer PK   | não      | — |
| `prescricao_id`      | Integer FK   | não      | → `prescricoes.id` |
| `tipo_receituario`   | String(50)   | não      | slug do tipo (ver § 2) |
| `grupo_id`           | String(50)   | não      | id do grupo regulatório |
| `grupo_nome`         | String(100)  | não      | nome humano |
| `assinatura_minima`  | String(20)   | não      | `qualificada` / `avancada` / `nenhuma` |
| `assinatura_valida`  | Boolean      | não      | default `false` |
| `vias`               | Integer      | não      | — |
| `retencao_farmacia`  | Boolean      | não      | default `false` |
| `requer_sncr`        | Boolean      | não      | default `false` |
| `numeracao_sncr`     | String(50)   | sim      | `NULL` (Ticket 16) |
| `status`             | String(20)   | não      | `gerado` → `numerado` → `emitido` |
| `substituido_em`     | DateTime     | sim      | soft-replace para regeneração |
| `created_at`         | DateTime     | não      | `utcnow` |

**Unicidade:** `UNIQUE (prescricao_id, tipo_receituario, substituido_em)`.
Postgres trata `NULL` como distinto em UNIQUE; assim coexistem receituários
antigos (marcados com `substituido_em != NULL`) e o novo ativo (`NULL`).

### `receituario_itens`

| Coluna                | Tipo        | Nullable | Observação |
|---|---|---|---|
| `id`                  | Integer PK  | não      | — |
| `receituario_id`      | Integer FK  | não      | → `receituarios.id` |
| `prescricao_item_id`  | Integer FK  | não      | → `prescricao_itens.id` |
| `created_at`          | DateTime    | não      | `utcnow` |

**Unicidade:** `UNIQUE (receituario_id, prescricao_item_id)` — um item só
aparece uma vez por receituário.

Migration: [`alembic/versions/a5472d975fc5_add_receituarios_e_receituario_itens_.py`](../backend/alembic/versions/a5472d975fc5_add_receituarios_e_receituario_itens_.py).

---

## 7. Exemplo — prescrição mista → 3 receituários

Prescrição clínica original:

| Item | Medicamento      | `classe_controle` |
|---|---|---|
| 1    | Morfina 10 mg    | A1                |
| 2    | Clonazepam 2 mg  | B1                |
| 3    | Dipirona 500 mg  | `NULL`            |

**Resultado** do `POST /prescricoes/{proto}/receituarios/gerar`:

```json
{
  "prescricao_protocolo": "…",
  "total_receituarios": 3,
  "todos_assinatura_valida": true,
  "idempotente": false,
  "receituarios": [
    {
      "tipo": "notificacao_receita_a",
      "grupo_nome": "Notificação de Receita A (Amarela)",
      "assinatura_minima": "qualificada",
      "assinatura_valida": true,
      "vias": 3, "retencao_farmacia": true, "requer_sncr": true,
      "numeracao_sncr": null, "status": "gerado",
      "itens": [ { "prescricao_item_id": 1, "nome_medicamento": "…", "classe_controle": "A1" } ]
    },
    {
      "tipo": "notificacao_receita_b",
      "grupo_nome": "Notificação de Receita B (Azul)",
      "assinatura_minima": "qualificada",
      "assinatura_valida": true,
      "vias": 2, "retencao_farmacia": true, "requer_sncr": true,
      "itens": [ { "prescricao_item_id": 2, "nome_medicamento": "…", "classe_controle": "B1" } ]
    },
    {
      "tipo": "receita_simples",
      "grupo_nome": "Receita Simples (sem controle regulatório)",
      "assinatura_minima": "nenhuma",
      "assinatura_valida": true,
      "vias": 1, "retencao_farmacia": false, "requer_sncr": false,
      "itens": [ { "prescricao_item_id": 3, "nome_medicamento": "…", "classe_controle": null } ]
    }
  ]
}
```

E uma entrada correspondente no ledger:

```
prescricao_eventos:
  tipo_evento    = 'receituarios_gerados'
  ator_tipo      = 'prescritor'
  ator_id        = <CNS do prescritor>
  payload_json   = {
    "quantidade": 3,
    "tipos": ["notificacao_receita_a", "notificacao_receita_b", "receita_simples"],
    "itens_por_receituario": { "...": [ids dos itens] },
    "validacao_assinatura": { "...": { "valido": true, "nivel_exigido": "...", ... } },
    "regenerado": false,
    "ticket_referencia": "TICKET-15"
  }
```

---

## 8. Limitações atuais e débitos técnicos

1. **Grupo 5 (Retenção) — ativo (Ticket 18).** Implementado via campo
   separado `tipo_retencao` em `prescricao_itens`. Cobre antimicrobianos
   (RDC 471/2021 + IN 83/2021) e agonistas de GLP-1 (IN 360/2025).
   Premissa provisória: `requer_sncr=False` (RDC 471 não tem ferramenta
   SNCR definida hoje); cada `receita_retencao` gerada registra
   `todo_regulatorio` no ledger para reavaliação. Ver
   [`grupo_retencao.md`](grupo_retencao.md).
2. **C1 não modelado.** Quando incluído em `CLASSES_CONTROLE_ESPECIAL`,
   adicionar em `GRUPO_C.classes`.
3. **Numeração SNCR não implementada** — campo `numeracao_sncr` fica `NULL`.
   Escopo do Ticket 16 (integração com API externa).
4. **PDF dos receituários** — não implementado (Ticket 17 previsto).
5. **Validação criptográfica real do certificado ICP-Brasil** (CRL/OCSP)
   continua sendo stub no MVP — o motor apenas consulta `assinatura_modo`,
   confiando na camada de emissão. Validação forte continua sendo decisão
   de ticket específico de assinatura.
6. **Base legal (LGPD × RDC × CFM 1.821)** — ver [politica_dados.md](politica_dados.md).
   O motor regulatório é um dos insumos necessários à conformidade SNCR;
   não substitui análise jurídica formal.

---

## 9. Referências normativas

- **RDC Anvisa nº 1.000/2025** — Sistema Nacional de Controle de Receituários
  (SNCR). Prazo de adequação: 01/06/2026.
- **Portaria SVS/MS nº 344/1998** — Listas A, B, C, D de substâncias
  sujeitas a controle especial.
- **RDC Anvisa nº 471/2021** — retinoides sistêmicos e talidomida.
- **RDC Anvisa nº 471/2021 + IN 83/2021** — antimicrobianos com retenção (Grupo 5).
- **IN Anvisa nº 360/2025** — agonistas de GLP-1 (Grupo 5).
- **Lei nº 13.787/2018** — guarda mínima de 20 anos do prontuário
  eletrônico (contexto de retenção).

---

## 10. Mapa de arquivos

| Arquivo | Papel |
|---|---|
| [backend/app/domain/motor_regulatorio.py](../backend/app/domain/motor_regulatorio.py) | Lógica pura: grupos, agrupamento, validação. |
| [backend/app/models/receituario.py](../backend/app/models/receituario.py) | Models ORM `Receituario` e `ReceituarioItem`. |
| [backend/alembic/versions/a5472d975fc5_add_receituarios_e_receituario_itens_.py](../backend/alembic/versions/a5472d975fc5_add_receituarios_e_receituario_itens_.py) | Migration de schema. |
| [backend/app/routers/receituarios.py](../backend/app/routers/receituarios.py) | Endpoint `POST /prescricoes/{proto}/receituarios/gerar`. |
| [backend/tests/integration/test_receituarios.py](../backend/tests/integration/test_receituarios.py) | 10 testes de integração (PostgreSQL real). |
