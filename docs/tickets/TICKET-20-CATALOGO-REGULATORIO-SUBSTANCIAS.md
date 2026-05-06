# TICKET 20 — Catálogo regulatório de substâncias

> Camada transversal de validação que confronta a classificação
> declarada pelo prescritor (`classe_controle` / `tipo_retencao`)
> contra a classificação publicada pela Anvisa, indexada por DCB.

## 1. Problema

Antes do T20, o motor regulatório (T15/T18) confiava cegamente na
classificação declarada pelo prescritor:

- `classe_controle` (Portaria 344/1998) — A1, B1, C5, D1, …
- `tipo_retencao` (RDC 471/2021) — antimicrobiano, glp1_agonista

Se o prescritor omitia ou errava a classificação, o sistema podia
classificar uma amoxicilina como receita simples — **erro regulatório
crítico** que expõe a plataforma a autuação Anvisa.

## 2. Solução

Catálogo local indexado por DCB, agindo como **oráculo de validação**:

- **Sugere** classificação ao prescritor (autocomplete)
- **Valida** coerência da classificação declarada
- **Alerta** divergências, com severidade `info` / `warning` / `critical`

> ⚠️ **Fase 1 = alertas, não bloqueios.** O catálogo é parcial por
> natureza. Bloquear emissão com base em catálogo incompleto geraria
> falsos negativos. Escalação para bloqueio será avaliada quando a
> cobertura for > 90% das substâncias prescritas.

## 3. Arquitetura

```
                         ┌──────────────────────────────┐
   POST /prescricoes  ───│ prescricao_itens             │
   (prescritor)          │   classe_controle (T44)      │
                         │   tipo_retencao   (T18)      │  ← FONTE-DE-VERDADE
                         └──────────────────────────────┘  para o motor regulatório
                                       │
                                       ▼
                         ┌──────────────────────────────┐
                         │ POST /receituarios/gerar     │
                         │   motor_regulatorio          │  ← roteia receituários
                         │   catalogo_regulatorio       │  ← oráculo de validação
                         └──────────────────────────────┘
                                       │
                            ┌──────────┴──────────┐
                            ▼                     ▼
                    receituarios          alertas_regulatorios
                                                 (info/warning/critical)
```

O catálogo **NÃO é fonte primária** — é uma camada de validação
auxiliar. Os campos declarados no item da prescrição continuam
governando o roteamento.

## 4. Componentes criados

### 4.1 Esquema de banco

Tabela `catalogo_substancias` ([migration 0c8654f77baf](../../backend/alembic/versions/0c8654f77baf_ticket20_catalogo_substancias.py)):

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | INT | PK |
| `dcb` | VARCHAR(200) | DCB original (com acentos e capitalização) |
| `dcb_normalizada` | VARCHAR(250) | UNIQUE — chave de lookup |
| `dcb_display` | VARCHAR(200) | DCB para exibição |
| `classe_controle` | VARCHAR(10) | NULL se não é Portaria 344 |
| `tipo_retencao` | VARCHAR(30) | NULL se não é RDC 471 |
| `fonte` | VARCHAR(100) | "portaria_344", "in_83_2021", "in_360_2025", combinações |
| `observacao` | TEXT | Notas regulatórias |
| `ativo` | BOOL | Soft delete (ex.: exenatida) |

**Decisão sobre busca por similaridade:** ILIKE + btree em vez de
`pg_trgm`. O `pg_trgm` não está disponível no `pgserver` embarcado
deste projeto; a alternativa é simples e suficiente para 50–200
substâncias. Quando a base crescer (> 1000 registros), criar GIN
index em migration adicional.

### 4.2 Domain module

[`app/domain/catalogo_regulatorio.py`](../../backend/app/domain/catalogo_regulatorio.py):

| Função | Responsabilidade |
|---|---|
| `normalizar_dcb(dcb)` | Normalização robusta: acentos, caixa, espaços, "+", combinações |
| `buscar_substancia(dcb, conn)` | Lookup direto |
| `buscar_substancia_por_nome(nome, conn)` | Heurística (DCB inteira → primeira palavra) |
| `buscar_substancias_similar(termo, conn, limit)` | Autocomplete por prefixo |
| `validar_classificacao(substancia, classe, tipo_ret, ...)` | Confronta declarado vs. catálogo |
| `validar_itens_prescricao(itens, conn)` | Validação em batch (lista de alertas) |

#### Severidade dos alertas

| Cenário | Severidade |
|---|:---:|
| Substância **não encontrada** no catálogo | — (sem alerta — cautela) |
| Coerente | — (sem alerta) |
| Substância da Portaria 344 com classe **divergente** ou **ausente** | `warning` |
| Substância da RDC 471 com tipo_retencao **divergente** ou **ausente** | `critical` |
| `tipo_retencao` declarado **fora do vocabulário** | `critical` |

A diferença de severidade reflete o risco regulatório: emitir
antimicrobiano como receita simples (RDC 471 viola retenção) é mais
grave que classificar diazepam como B2 em vez de B1 (ambos retidos
em receituário azul).

### 4.3 Endpoint de autocomplete

```
GET /catalogo/substancias?q=<termo>&limit=<n>
```

- **Auth:** Bearer (qualquer role autenticada)
- **`q`:** termo de busca (mínimo 1 char, máximo 100)
- **`limit`:** 1–20 (default 10)
- **Resposta:** lista de substâncias com `dcb`, `dcb_display`,
  `classe_controle`, `tipo_retencao`, `fonte`, `observacao`
- Substâncias com `ativo=False` são omitidas

Implementado em [`app/routers/catalogo.py`](../../backend/app/routers/catalogo.py).

### 4.4 Integração no `POST /receituarios/gerar`

Resposta agora inclui `alertas_regulatorios`:

```json
{
  "total_receituarios": 1,
  "receituarios": [...],
  "alertas_regulatorios": [
    {
      "item_id": 42,
      "nome_medicamento": "AMOXICILINA",
      "severidade": "critical",
      "alerta": "'AMOXICILINA' consta no catálogo como antimicrobiano (RDC 471/2021) mas tipo_retencao não foi informado. Risco: emissão como receita simples para item sujeito a retenção.",
      "sugestao_classe": null,
      "sugestao_tipo_retencao": "antimicrobiano"
    }
  ]
}
```

Alertas são informativos. **Não bloqueiam emissão.** Aparecem tanto no
caminho fresh (geração nova) quanto no caminho idempotente (re-chamada).

### 4.5 Salvaguarda na atomização

[`eh_item_atomizavel(item, conn=None)`](../../backend/app/domain/medicamento.py):

- **Sem `conn`** (compatibilidade) → comportamento idêntico ao pré-T20
- **Com `conn`** → consulta catálogo; se substância está controlada
  no catálogo (mesmo sem declaração do prescritor), bloqueia atomização

Isso fecha o buraco onde um prescritor distraído poderia emitir
diazepam atomizado por omitir `classe_controle="B1"`.

## 5. Seed inicial

[`app/domain/catalogo_seed.py`](../../backend/app/domain/catalogo_seed.py) — 56 substâncias:

| Categoria | Quantidade | Fonte |
|---|---:|---|
| Agonistas de GLP-1 | 5 | IN 360/2025 |
| Antimicrobianos (top 30 da AP) | 30 | IN 83/2021 |
| Portaria 344 (top prescritos) | 20 | Portaria SVS/MS 344/1998 |
| Inativos (exenatida) | 1 | Histórico |

> ⚠️ **A classificação individual de cada DCB precisa ser conferida
> contra a versão vigente das normas Anvisa antes de uso em produção.**
> O seed marca casos especiais (rifampicina dupla, fluconazol
> incerto) com o campo `observacao`.

### Casos especiais documentados no seed

- **Rifampicina** — Portaria 344 (C1) **e** IN 83/2021 (antimicrobiano).
  Catálogo registra ambos os campos preenchidos. Motor regulatório
  resolve por prevalência: Portaria 344 prevalece (T18).
- **Fluconazol** — antifúngico; pode não estar listado entre os
  antimicrobianos da IN 83/2021. Marcado para revisão regulatória.
- **Exenatida** — agonista GLP-1 excluído da IN 360/2025 (sem registro
  válido no Brasil). Mantida com `ativo=False` para histórico.

### Aplicação do seed

```bash
DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_dev \
    python3 backend/scripts/seed_catalogo_substancias.py
```

Idempotente — pode rodar várias vezes.

## 6. Cobertura de testes

[`backend/tests/integration/test_catalogo_regulatorio.py`](../../backend/tests/integration/test_catalogo_regulatorio.py) — **23 testes**.

**Unitários** (10):
- 3× normalização (acentos, "+", espaços extras)
- 7× cenários de validação cruzada (cobre todas as severidades)

**Integração** (13):
- Autocomplete (semaglutida, amoxicilina, q vazio, inativo, sem auth)
- Alertas em `/gerar` (critical, warning, sem alerta, não bloqueia, desconhecida)
- Atomização (bloqueio via catálogo, fallback sem conn, GLP-1)

```bash
DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test \
    pytest tests/integration/test_catalogo_regulatorio.py -v
```

**Suite completa**: 120/120 testes passam (zero regressão), confirmado
em 2 rodadas consecutivas.

## 7. Decisões de design (revisado durante a implementação)

1. **Catálogo como oráculo, não como fonte.** Os campos declarados no
   item da prescrição (`classe_controle`, `tipo_retencao`) continuam
   sendo a verdade que o motor regulatório lê. O catálogo apenas
   confronta.

2. **Severidade tripartite.** Separa decisão técnica (gerar receita)
   de decisão regulatória (qual receita). Em fase futura, bloqueio
   configurável pode rejeitar apenas `critical`.

3. **Substância desconhecida não gera alerta.** Catálogo parcial
   exige cautela: alerta só quando há divergência, nunca por
   ausência. Caso contrário, qualquer DCB nova causaria falso
   positivo.

4. **DCB como chave, não nome comercial.** O campo
   `prescricao_itens.nome_medicamento` aceita qualquer string (livre
   para o prescritor). A heurística `buscar_substancia_por_nome`
   tenta DCB inteira → primeira palavra (cobre "AMOXICILINA 500mg").

5. **ILIKE + btree no lugar de pg_trgm.** A extensão pg_trgm não está
   disponível no `pgserver` embarcado. Para 50–200 registros, ILIKE
   por prefixo é suficiente. Migration adicional pode adicionar GIN
   index quando o catálogo crescer.

6. **`eh_item_atomizavel` com `conn` opcional.** Preserva
   compatibilidade com chamadas existentes. A salvaguarda do catálogo
   só ativa quando o caller passa `conn`. Ideal: callers que têm
   contexto transacional (POST /prescricoes, /circulacao) passam
   `conn`; callers em scripts ou helpers de teste continuam sem.

7. **Seed em módulo de domínio.** `catalogo_seed.py` vive em
   `app/domain/`, não em `scripts/`. Razão: as listas têm semântica
   regulatória (não são dados de teste). O script em `scripts/` é
   só o entry-point de aplicação.

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| Catálogo incompleto gera falsa segurança | Documentado como parcial. Ausência ≠ "substância livre". |
| Substância com dupla classificação | Modelo permite ambos os campos preenchidos. Motor resolve prioridade (T18). |
| Atualização Anvisa invalida dados do catálogo | Campo `fonte` + `updated_at` para auditoria. Ticket futuro para sincronização automatizada. |
| Performance de ILIKE com volume | Aceitável até ~1000 registros. Migration GIN+pg_trgm quando necessário. |

## 9. Escopo futuro

- **Carga completa da IN 83/2021** (centenas de antimicrobianos)
- **Catálogo da Portaria 344 completo** (~200 substâncias)
- **Sincronização automatizada** com publicações Anvisa (web scraping ou API DEF/GGMED)
- **GIN index com pg_trgm** quando volume crescer
- **Frontend admin** para CRUD do catálogo
- **Bloqueio configurável** baseado em severidade (ex.: rejeitar `critical` se `BLOQUEAR_CRITICAL_CATALOGO=1`)

## 10. Arquivos criados/modificados

| Arquivo | Ação |
|---|---|
| [`app/models/catalogo_substancia.py`](../../backend/app/models/catalogo_substancia.py) | criar |
| [`app/models/__init__.py`](../../backend/app/models/__init__.py) | adicionar import |
| [`alembic/versions/0c8654f77baf_ticket20_catalogo_substancias.py`](../../backend/alembic/versions/0c8654f77baf_ticket20_catalogo_substancias.py) | criar |
| [`app/domain/catalogo_regulatorio.py`](../../backend/app/domain/catalogo_regulatorio.py) | criar |
| [`app/domain/catalogo_seed.py`](../../backend/app/domain/catalogo_seed.py) | criar |
| [`scripts/seed_catalogo_substancias.py`](../../backend/scripts/seed_catalogo_substancias.py) | criar |
| [`app/routers/catalogo.py`](../../backend/app/routers/catalogo.py) | criar |
| [`app/routers/receituarios.py`](../../backend/app/routers/receituarios.py) | adicionar `alertas_regulatorios` |
| [`app/domain/medicamento.py`](../../backend/app/domain/medicamento.py) | `eh_item_atomizavel(conn=None)` |
| [`app/main.py`](../../backend/app/main.py) | incluir `catalogo.router` |
| [`tests/integration/test_catalogo_regulatorio.py`](../../backend/tests/integration/test_catalogo_regulatorio.py) | criar (23 testes) |
