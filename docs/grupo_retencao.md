# Grupo Retenção — Ticket 18

> Antimicrobianos (RDC 471/2021 + IN 83/2021) e agonistas de GLP-1
> (IN 360/2025) — sistema regulatório **independente** da Portaria
> SVS/MS 344/1998.

## 1. Justificativa regulatória

A Portaria SVS/MS nº **344/1998** classifica substâncias por **listas**
(A, B, C, D). É o sistema histórico para entorpecentes, psicotrópicos,
retinoides e talidomida.

A RDC Anvisa nº **471/2021** (sucessora da RDC 20/2011) classifica
medicamentos sujeitos à retenção por **substância** (DCB), fora do
escopo da Portaria 344. A IN nº **83/2021** detalha antimicrobianos.
A IN nº **360/2025** (vigente desde 23/06/2025) incluiu agonistas de
GLP-1.

| Aspecto | Portaria 344/1998 | RDC 471/2021 |
|---|---|---|
| Classifica por | Lista (A1, B1, C5, D1...) | Substância (DCB) |
| Campo no PicSaúde | `classe_controle` | `tipo_retencao` |
| Código SNGPC | "2" | "1" (apenas referência documental) |
| SNCR obrigatório | Sim | **Não** (premissa provisória) |
| Assinatura mínima | Qualificada (ICP-Brasil) | Avançada (gov.br aceita) |
| Vias | 2 ou 3 | 2 |
| Receituário | Amarelo / Azul / Branco | Branco com retenção |

> ⚠️ **Premissa provisória sobre SNCR:** a RDC 471 não tem ferramenta
> SNCR definida hoje. O motor usa `requer_sncr=False` e o endpoint
> `/gerar` registra um `todo_regulatorio` no ledger
> (`motivo: "requer_sncr_retencao_provisorio"`) para reavaliação
> quando a Anvisa publicar API.

## 2. Decisão arquitetural — campo separado

### Por que `tipo_retencao` em vez de novos códigos em `classe_controle`?

| Abordagem | Problema |
|---|---|
| Inventar `"C6"` para antimicrobianos | Conflita dois sistemas normativos. `"C6"` não existe na legislação. |
| Inventar `"E1"` para GLP-1 | Mesmo problema. Cria ficção regulatória. |
| **Campo `tipo_retencao` separado** ✅ | Respeita que são sistemas regulatórios independentes com vocabulários e regras próprias. |

### Regra de prioridade

Quando ambos os campos estão preenchidos, **a Portaria 344 prevalece**
(é o sistema mais restritivo):

```
1. classe_controle ∈ Portaria 344  → grupo da Portaria 344
2. tipo_retencao  ∈ RDC 471        → GRUPO_RETENCAO
3. classe_controle desconhecida    → ValueError
4. tipo_retencao  desconhecido     → ValueError (não silenciar — risco regulatório)
5. ambos vazios/NULL               → GRUPO_SIMPLES
```

Implementado em [`app/domain/motor_regulatorio.py`](../backend/app/domain/motor_regulatorio.py)::`grupo_regulatorio()`.

## 3. Valores aceitos

Definidos em [`app/domain/retencao.py`](../backend/app/domain/retencao.py):

| `tipo_retencao` | Escopo | Vigência |
|---|---|---|
| `"antimicrobiano"` | RDC 471/2021 + IN 83/2021 | Em vigor |
| `"glp1_agonista"` | IN 360/2025 | Desde 23/06/2025 |
| `NULL` | Não sujeito a retenção por RDC 471 | — |

### Substâncias GLP-1 (IN 360/2025) — referência documental

Não validamos por DCB hoje (não temos catálogo no banco). O prescritor
declara `tipo_retencao` no nível do item.

| Substância | DCB |
|---|---|
| Semaglutida | 09417 |
| Liraglutida | 08197 |
| Dulaglutida | 10267 |
| Tirzepatida | 12621 |
| Lixisenatida | 10266 |

> **Exenatida** é agonista GLP-1 mas foi **excluída** da IN 360/2025
> por não haver registro válido no Brasil. Monitorar caso a Anvisa
> atualize.

## 4. Fluxo no motor regulatório

```
item = {classe_controle: ?, tipo_retencao: ?}
            │
            ▼
     ┌──────────────────────────────────────┐
     │ classe_controle ∈ {A1,A2,A3,B1,B2,   │
     │                    C5,D1,D2}?        │
     └──────────────────────────────────────┘
            │ sim                  │ não
            ▼                      ▼
     ┌──────────────┐   ┌──────────────────────┐
     │ GRUPO_A/B/C/D│   │ tipo_retencao        │
     │ (Portaria    │   │ ∈ {antimicrobiano,   │
     │  344)        │   │    glp1_agonista}?   │
     └──────────────┘   └──────────────────────┘
                          │ sim         │ não
                          ▼             ▼
                  ┌────────────────┐ ┌──────────────┐
                  │ GRUPO_RETENCAO │ │ GRUPO_SIMPLES│
                  │ (RDC 471/2021) │ │              │
                  └────────────────┘ └──────────────┘
```

### Exemplos

| Item | `classe_controle` | `tipo_retencao` | Grupo resultante |
|---|---|---|---|
| Diazepam (psicotrópico) | `B1` | NULL | `notificacao_receita_b` |
| Amoxicilina | NULL | `antimicrobiano` | `receita_retencao` |
| Semaglutida | NULL | `glp1_agonista` | `receita_retencao` |
| Talidomida (D1) hipotético com retenção | `D1` | `antimicrobiano` | `notificacao_receita_especial` (Portaria 344 prevalece) |
| Dipirona | NULL | NULL | `receita_simples` |
| Item com tipo_retencao desconhecido | NULL | `"bogus"` | **ValueError** (422 no endpoint) |

## 5. Diferenças em relação aos outros grupos

| Campo | `notificacao_receita_a/b` / `controle_especial` / `notificacao_receita_especial` | `receita_retencao` |
|---|---|---|
| `assinatura_minima` | `qualificada` (ICP-Brasil) | `avancada` (gov.br aceita) |
| `vias` | 2 ou 3 | 2 |
| `requer_sncr` | `True` | **`False`** (premissa provisória) |
| `retencao_farmacia` | `True` | `True` |
| Numeração | `STUB-...-NRA/NRB/RCE/NRE-...` | Nenhuma — status `nao_requer_sncr` |
| PDF abrev | `NRA/NRB/RCE/NRE` | **`RRT`** |

## 6. Discrepância de abreviação corrigida

Antes do Ticket 18:
- `sncr_stub.py` usava `"RTC"` para `receita_retencao`
- `pdf_receituario.py` usava `"RRT"` para o mesmo tipo

Padronizado para **`RRT`** (Receita Retenção) em ambos. O nome do
arquivo PDF é `receituario-RRT-{id}.pdf`.

## 7. Atomização (circulação atomizada — Ticket 44)

`eh_item_atomizavel()` agora bloqueia AMBOS os caminhos:

```python
classe_controle ∈ CLASSES_CONTROLE_ESPECIAL  → não atomizável (já era)
tipo_retencao   ∈ TIPOS_RETENCAO_VALIDOS     → não atomizável (Ticket 18)
```

Justificativa: receita com retenção exige rastreabilidade do canhoto
físico, incompatível com tokens fracionados de circulação atomizada.

## 8. Esquema de banco

Migration: [`alembic/versions/af5133f5f172_ticket18_add_tipo_retencao_to_.py`](../backend/alembic/versions/af5133f5f172_ticket18_add_tipo_retencao_to_.py)

```sql
ALTER TABLE prescricao_itens
  ADD COLUMN tipo_retencao VARCHAR(30);   -- NULL = não sujeito a retenção
```

`classe_controle` (Ticket 44) e `tipo_retencao` (Ticket 18) coexistem.
Nenhum deles é índice de busca — são metadados de roteamento
consumidos pelo motor regulatório.

## 9. Cobertura de testes

[`backend/tests/integration/test_grupo_retencao.py`](../backend/tests/integration/test_grupo_retencao.py) — 15 testes:

1. Antimicrobiano → `receita_retencao`
2. GLP-1 → `receita_retencao`
3. Mistura B1 + antimicrobiano + simples → 3 receituários distintos
4. Portaria 344 prevalece sobre RDC 471
5. `tipo_retencao` inválido → `ValueError` no motor
6. `tipo_retencao` inválido → 422 no endpoint
7. Assinatura `gov_br_nuvem` aceita para retenção
8. Assinatura `icp_brasil_local` também aceita
9. Fluxo completo `gerar` → `numerar` (`nao_requer_sncr`) → `pdf` (`emitido`)
10. Itens com `tipo_retencao` não são atomizáveis
11. `GRUPO_RETENCAO.status_implementacao == "ativo"`
12. `TODO_REGULATORIO` registrado no ledger ao gerar `receita_retencao`
13. Abreviação `RRT` consistente em stub e PDF
14. Schema da API normaliza `tipo_retencao` (case-insensitive)
15. Schema rejeita `tipo_retencao` inválido (Pydantic `ValidationError`)

```bash
export DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test
cd backend && pytest tests/integration/test_grupo_retencao.py -v
```

Suite completa: **75 testes passando** (zero regressão).

## 10. Escopo futuro

- **Catálogo DCB de antimicrobianos**: ✅ **Implementado parcialmente no Ticket 20** — catálogo local com top 30 antimicrobianos + 5 GLP-1 + 20 da Portaria 344. Valida coerência entre declaração e referência regulatória, emite alertas (info/warning/critical). Não bloqueia em fase 1. Carga completa da IN 83/2021 fica em ticket futuro. Ver [`TICKET-20`](tickets/TICKET-20-CATALOGO-REGULATORIO-SUBSTANCIAS.md).
- **Validação de prazo diferenciado**: 10 dias (antimicrobianos) vs 90 dias (controlados) — Ticket futuro.
- **Integração SNGPC**: o código SNGPC "1" é referência apenas; integração real é Ticket separado.
- **SNCR para retenção**: se a Anvisa publicar ferramenta, reavaliar `requer_sncr=False` (TODO_REGULATORIO já marca essa pendência no ledger a cada `receita_retencao` gerada).
- **Exenatida**: incluída se Anvisa publicar atualização da IN 360/2025.

## 11. Salvaguardas implementadas

- `documento_canonico.py` não inclui `tipo_retencao` (mesmo padrão de `classe_controle` — metadados de roteamento, não conteúdo clínico do hash)
- Tabela `receituarios` não foi alterada (já suportava `receita_retencao`)
- `pdf_receituario.py` não foi alterado (`RRT` já existia)
- `sncr_interface.py` não foi alterado (contrato preservado)
- `tipo_retencao=NULL` continua funcionando como antes (`GRUPO_SIMPLES`)
- Migration idempotente (verifica `_column_exists`)
- 75/75 testes passam — testes existentes não regridem
