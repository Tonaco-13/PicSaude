# TICKET 20 — CATÁLOGO REGULATÓRIO DE SUBSTÂNCIAS

## Problema

Hoje o PicSaúde depende de dois campos **declarados pelo prescritor** no nível do item de prescrição:

- `classe_controle` (Portaria 344/1998) — ex.: "B1", "A1", "D1"
- `tipo_retencao` (RDC 471/2021) — ex.: "antimicrobiano", "glp1_agonista"

O motor regulatório (`motor_regulatorio.py`) confia nesses valores para rotear cada item ao grupo regulatório correto. Não existe validação cruzada: se o prescritor informar `classe_controle = NULL` e `tipo_retencao = NULL` para amoxicilina, o sistema classifica como Receita Simples — **erro regulatório grave** que expõe a plataforma a risco de autuação pela Anvisa.

Além disso:

1. **A lista de substâncias GLP-1** (`SUBSTANCIAS_GLP1_IN360` em `retencao.py`) existe apenas como documentação — não é usada na lógica.
2. **Antimicrobianos** não têm nenhuma lista — a IN 83/2021 enumera centenas de substâncias, mas o PicSaúde não as conhece.
3. **Classes da Portaria 344** (A1, B1, C5, D1) são validadas apenas como strings — não há vínculo substância → classe.
4. **Nenhum alerta** é emitido se o prescritor omitir ou errar a classificação de um medicamento controlado.

## Objetivo

Criar um catálogo local de substâncias reguladas, indexado por DCB (Denominação Comum Brasileira), que permita:

1. **Sugerir** classificação regulatória ao prescritor (autocomplete no frontend)
2. **Validar** a coerência entre substância e classificação declarada
3. **Alertar** quando uma substância conhecida está sem classificação ou com classificação divergente
4. **Bloquear** emissão quando a divergência representar risco regulatório crítico (opcional — pode ser configurável)

## Contexto regulatório

### Portaria SVS/MS 344/1998
Mantém listas de substâncias sujeitas a controle especial (A1, A2, A3, B1, B2, C1–C5, D1, D2). A lista é atualizada periodicamente pela Anvisa via Resoluções de Diretoria Colegiada (RDC).

### RDC 471/2021 + IN 83/2021
Lista de antimicrobianos sujeitos à retenção de receita. A IN 83/2021 enumera as substâncias (centenas de DCBs).

### IN 360/2025 (vigente desde 23/06/2025)
Inclui 5 agonistas de GLP-1 na RDC 471/2021:
- semaglutida, liraglutida, dulaglutida, tirzepatida, lixisenatida
- Exenatida **excluída** — sem registro válido no Brasil.

### DEF (futuro)
Denominação Farmacêutica Brasileira da Anvisa/GGMED. Quando disponível em formato estruturado, poderá substituir o catálogo local como fonte-de-verdade.

## Escopo

### ENTRA

- [ ] Tabela `catalogo_substancias` no banco de dados
- [ ] Modelo SQLAlchemy `CatalogoSubstancia`
- [ ] Migration Alembic para criação da tabela
- [ ] Módulo `app/domain/catalogo_regulatorio.py` com lógica de lookup e validação
- [ ] Seed inicial com substâncias GLP-1 (5 da IN 360/2025)
- [ ] Seed inicial com subset de antimicrobianos mais prescritos (top 30 da IN 83/2021)
- [ ] Seed inicial com substâncias Portaria 344 mais comuns (top 20 por lista)
- [ ] Endpoint auxiliar `GET /catalogo/substancias?q=<termo>` para autocomplete
- [ ] Função de validação cruzada: substância × classificação declarada
- [ ] Integração com `POST /gerar`: alerta (warning) quando divergência detectada
- [ ] Integração com circulação atomizada: validação cruzada em `eh_item_atomizavel()` / `motivo_nao_atomizavel()` como salvaguarda contra `classe_controle` declarado incorretamente
- [ ] Campo `severidade` nos alertas regulatórios (`info` | `warning` | `critical`)
- [ ] Normalização robusta de DCB: acentos, caixa, espaços, hífen e combinações com `+`
- [ ] Testes unitários do módulo de catálogo
- [ ] Testes de integração do endpoint e da validação cruzada
- [ ] Documentação do ticket

### NÃO ENTRA (futuros)

- Catálogo completo da IN 83/2021 (centenas de substâncias — requer carga automatizada)
- Integração com DEF/GGMED quando disponível
- Bloqueio hard de emissão por divergência (fase 1 = apenas warning)
- Frontend de administração do catálogo (CRUD web)
- Sincronização automática com publicações da Anvisa

## Design da tabela

```sql
CREATE TABLE catalogo_substancias (
    id              SERIAL PRIMARY KEY,
    dcb             VARCHAR(200) NOT NULL,          -- DCB legível (pode ter acentos e "+" em combinações)
    dcb_normalizada VARCHAR(250) NOT NULL UNIQUE,   -- DCB normalizada: lowercase, sem acentos, "+" padronizado, sem espaços extras
    dcb_display     VARCHAR(200) NOT NULL,          -- DCB com capitalização para exibição
    classe_controle VARCHAR(10),                    -- NULL se não é Portaria 344
    tipo_retencao   VARCHAR(30),                    -- NULL se não é RDC 471
    fonte           VARCHAR(100) NOT NULL,          -- "portaria_344", "in_83_2021", "in_360_2025"
    observacao      TEXT,                           -- notas regulatórias
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,  -- soft delete
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_catalogo_dcb_trgm ON catalogo_substancias
    USING gin (dcb_normalizada gin_trgm_ops);  -- busca por similaridade (pg_trgm)
```

### Normalização de DCB

A coluna `dcb_normalizada` é gerada pela função `normalizar_dcb()`:

```python
import unicodedata
import re

def normalizar_dcb(dcb: str) -> str:
    """Normaliza DCB para lookup e unicidade.
    
    Regras:
    - Remove acentos (NFD + strip combining marks)
    - Lowercase
    - Substitui espaços múltiplos por espaço único
    - Padroniza separador de combinações: " + " (com espaços)
    - Strip de espaços nas extremidades
    
    Exemplos:
    - "Amoxicilina" → "amoxicilina"
    - "Sulfametoxazol+Trimetoprima" → "sulfametoxazol + trimetoprima"
    - "Amoxicilina + Clavulanato" → "amoxicilina + clavulanato"
    - "Isotretinoína" → "isotretinoina"
    """
    # Remove acentos
    nfkd = unicodedata.normalize("NFKD", dcb)
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Lowercase + normaliza espaços ao redor de "+"
    resultado = sem_acentos.strip().lower()
    resultado = re.sub(r"\s*\+\s*", " + ", resultado)
    resultado = re.sub(r"\s+", " ", resultado)
    return resultado
```

A UNIQUE constraint em `dcb_normalizada` garante que "sulfametoxazol+trimetoprima", "Sulfametoxazol + Trimetoprima" e "sulfametoxazol + trimetoprima" são tratadas como a mesma substância.

### Regras de integridade

- Cada substância tem **exatamente uma** entrada (unicidade por `dcb_normalizada`).
- `classe_controle` e `tipo_retencao` são mutuamente **não exclusivos** — uma substância pode estar tanto na Portaria 344 quanto na RDC 471 (embora na prática a Portaria 344 prevalece no roteamento).
- O campo `fonte` indica a norma de origem para rastreabilidade.
- `ativo = FALSE` permite desativar substâncias sem deletar (ex.: exenatida excluída da IN 360).

## Módulo `catalogo_regulatorio.py`

```python
@dataclass(frozen=True)
class SubstanciaCatalogo:
    dcb: str
    dcb_display: str
    classe_controle: str | None
    tipo_retencao: str | None
    fonte: str

@dataclass
class ResultadoValidacaoCatalogo:
    substancia_encontrada: bool
    classificacao_coerente: bool
    alertas: list[str]
    severidade: Literal["info", "warning", "critical"] = "info"
    sugestao_classe: str | None = None
    sugestao_tipo_retencao: str | None = None
```

### Funções principais

1. **`buscar_substancia(dcb: str) -> SubstanciaCatalogo | None`**
   Lookup direto por DCB normalizado.

2. **`buscar_substancias(termo: str, limit: int = 10) -> list[SubstanciaCatalogo]`**
   Busca por similaridade (trigram) para autocomplete.

3. **`validar_classificacao(dcb: str, classe_declarada: str | None, tipo_retencao_declarado: str | None) -> ResultadoValidacaoCatalogo`**
   Confronta a classificação declarada pelo prescritor com o catálogo. Cenários:

   | Cenário | Severidade | Resultado |
   |---------|:----------:|-----------|
   | Substância não encontrada no catálogo | — | `substancia_encontrada=False`, sem alerta (catálogo incompleto não deve bloquear) |
   | Encontrada, classificação coerente | — | `coerente=True`, sem alerta |
   | Encontrada, classe_controle divergente | `critical` | `coerente=False`, alerta com sugestão |
   | Encontrada, tipo_retencao divergente | `critical` | `coerente=False`, alerta com sugestão |
   | Encontrada, classificação ausente (NULL) para substância controlada | `warning` | `coerente=False`, alerta: "substância requer classificação X" |
   | Encontrada, classificação ausente (NULL) para substância de retenção | `critical` | `coerente=False`, alerta: risco de emissão como receita simples |

4. **`validar_itens_prescricao(itens: list[dict], conn) -> list[ResultadoValidacaoCatalogo]`**
   Validação em batch de todos os itens de uma prescrição.

## Integração com fluxo existente

### Endpoint `POST /gerar`

No loop de persistência (linha ~271 de `receituarios.py`), após calcular `data_validade`, chamar a validação do catálogo:

```python
# Ticket 20 — validação cruzada com catálogo
alertas_catalogo = validar_itens_prescricao(dto.itens, conn)
# Alertas são incluídos na resposta, mas NÃO bloqueiam (fase 1)
```

A resposta do endpoint ganha um campo opcional `alertas_regulatorios`:

```json
{
  "total_receituarios": 2,
  "receituarios": [...],
  "alertas_regulatorios": [
    {
      "item": "amoxicilina 500mg",
      "severidade": "critical",
      "alerta": "Substância consta no catálogo como antimicrobiano (IN 83/2021) mas tipo_retencao não foi informado. Risco: emissão como receita simples.",
      "sugestao_tipo_retencao": "antimicrobiano"
    }
  ]
}
```

### Integração com circulação atomizada

A circulação atomizada (`medicamento.py::eh_item_atomizavel()`) hoje depende exclusivamente de `classe_controle` e `tipo_retencao` declarados pelo prescritor para rejeitar itens controlados. Se o prescritor omitir esses campos, o item é tratado como atomizável — risco regulatório idêntico ao do motor regulatório.

O catálogo deve ser usado como salvaguarda adicional:

```python
# Em medicamento.py — Ticket 20
def eh_item_atomizavel(item: dict, conn=None) -> bool:
    # Regra existente: campos declarados
    classe = (item.get("classe_controle") or "").strip().upper()
    if classe in CLASSES_CONTROLE_ESPECIAL:
        return False
    tipo_ret = (item.get("tipo_retencao") or "").strip().lower()
    if tipo_ret in TIPOS_RETENCAO_VALIDOS:
        return False

    # Ticket 20 — salvaguarda via catálogo (se conn disponível)
    if conn is not None:
        from app.domain.catalogo_regulatorio import buscar_substancia_por_nome
        substancia = buscar_substancia_por_nome(
            item.get("nome_medicamento"), conn,
        )
        if substancia and (substancia.classe_controle or substancia.tipo_retencao):
            return False  # catálogo indica controle, mesmo sem declaração

    return True
```

A assinatura de `eh_item_atomizavel()` ganha `conn=None` como parâmetro opcional, preservando compatibilidade com chamadas existentes. Quando `conn` não é fornecido, o comportamento é idêntico ao atual.

### Endpoint `GET /catalogo/substancias`

```
GET /catalogo/substancias?q=sema&limit=5

200 OK
{
  "resultados": [
    {
      "dcb": "semaglutida",
      "dcb_display": "Semaglutida",
      "classe_controle": null,
      "tipo_retencao": "glp1_agonista",
      "fonte": "in_360_2025"
    }
  ]
}
```

Requer autenticação (Bearer token). Sem paginação — `limit` máximo = 20.

## Seed inicial

### GLP-1 (IN 360/2025) — 5 substâncias

| DCB | tipo_retencao | fonte |
|-----|---------------|-------|
| semaglutida | glp1_agonista | in_360_2025 |
| liraglutida | glp1_agonista | in_360_2025 |
| dulaglutida | glp1_agonista | in_360_2025 |
| tirzepatida | glp1_agonista | in_360_2025 |
| lixisenatida | glp1_agonista | in_360_2025 |

### Antimicrobianos mais prescritos (IN 83/2021) — top 30

A lista completa da IN 83/2021 será carregada em ticket futuro. Para fase 1, incluir os 30 antimicrobianos mais prescritos na atenção primária brasileira:

amoxicilina, azitromicina, cefalexina, ciprofloxacino, sulfametoxazol+trimetoprima, metronidazol, amoxicilina+clavulanato, doxiciclina, levofloxacino, norfloxacino, nitrofurantoína, ceftriaxona, clindamicina, eritromicina, gentamicina, ampicilina, cefalotina, cefazolina, cefuroxima, claritromicina, fluconazol (se classificado como antimicrobiano na IN 83), moxifloxacino, oxacilina, penicilina benzatina, penicilina V, rifampicina, tetraciclina, tobramicina, vancomicina, sulfadiazina.

> **Nota**: A classificação individual de cada DCB precisa ser conferida contra a IN 83/2021 durante a implementação. Alguns podem ter dupla classificação (ex.: rifampicina está na Portaria 344 como C1 E na IN 83 como antimicrobiano).

### Portaria 344/1998 — top 20 mais prescritos

| DCB | classe_controle | fonte |
|-----|----------------|-------|
| clonazepam | B1 | portaria_344 |
| diazepam | B1 | portaria_344 |
| alprazolam | B1 | portaria_344 |
| bromazepam | B1 | portaria_344 |
| fluoxetina | C1 | portaria_344 |
| sertralina | C1 | portaria_344 |
| escitalopram | C1 | portaria_344 |
| venlafaxina | C1 | portaria_344 |
| duloxetina | C1 | portaria_344 |
| amitriptilina | C1 | portaria_344 |
| codeína | A2 | portaria_344 |
| tramadol | B1 | portaria_344 |
| zolpidem | B1 | portaria_344 |
| fenobarbital | B1 | portaria_344 |
| metilfenidato | A3 | portaria_344 |
| lisdexanfetamina | A3 | portaria_344 |
| isotretinoína | D1 | portaria_344 |
| talidomida | D1 | portaria_344 |
| morfina | A1 | portaria_344 |
| fentanila | A1 | portaria_344 |

> **Nota**: Classificações devem ser verificadas contra a versão vigente da Portaria 344 durante a implementação. A lista C1 é extensa e contém muitos antidepressivos — incluímos apenas os mais prescritos.

## Testes

### Unitários (sem banco)
1. `test_buscar_substancia_encontrada` — lookup direto por DCB
2. `test_buscar_substancia_nao_encontrada` — retorna None
3. `test_validar_classificacao_coerente` — substância + classe corretas
4. `test_validar_classificacao_divergente_classe` — classe errada gera alerta com severidade `critical`
5. `test_validar_classificacao_divergente_retencao` — tipo_retencao errado gera alerta com severidade `critical`
6. `test_validar_classificacao_ausente_controlada` — substância controlada sem classificação → `warning`
7. `test_validar_classificacao_ausente_retencao` — substância de retenção sem tipo_retencao → `critical`
8. `test_validar_substancia_desconhecida_nao_bloqueia` — catálogo incompleto não gera falso positivo
9. `test_buscar_substancias_similaridade` — autocomplete por trigram
10. `test_normalizar_dcb_acentos` — "Isotretinoína" → "isotretinoina"
11. `test_normalizar_dcb_combinacao_com_mais` — "Sulfametoxazol+Trimetoprima" → "sulfametoxazol + trimetoprima"
12. `test_normalizar_dcb_espacos_extras` — espaços múltiplos colapsam

### Integração (com PostgreSQL)
13. `test_endpoint_catalogo_autocomplete` — GET /catalogo/substancias?q=sema retorna semaglutida
14. `test_gerar_receituario_com_alerta_catalogo` — POST /gerar com antimicrobiano sem tipo_retencao retorna alerta `critical`
15. `test_gerar_receituario_sem_alerta_quando_coerente` — classificação correta não gera alerta
16. `test_catalogo_nao_bloqueia_emissao` — alertas são informativos, não bloqueiam (fase 1)
17. `test_atomizacao_bloqueada_por_catalogo` — `eh_item_atomizavel()` retorna False quando catálogo identifica substância controlada sem classe_controle declarada
18. `test_atomizacao_sem_conn_ignora_catalogo` — sem `conn`, `eh_item_atomizavel()` mantém comportamento atual

## Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|:------------:|:-------:|-----------|
| Catálogo incompleto gera falsa sensação de segurança | Alta | Médio | Documentar claramente que o catálogo é parcial. Campo `ativo` + fonte para rastreabilidade. Não usar ausência no catálogo como prova de que a substância é livre. |
| Substância com dupla classificação (344 + 471) | Baixa | Alto | Modelo permite ambos os campos preenchidos. Motor regulatório já resolve prioridade (344 prevalece). |
| Atualização de norma Anvisa invalida dados do catálogo | Média | Alto | Campo `fonte` + `updated_at` para auditoria. Ticket futuro para sincronização automatizada. |
| Performance do autocomplete com trigram em tabela pequena | Baixa | Baixo | pg_trgm é eficiente mesmo para 100–200 registros. Índice GIN criado na migration. |

## Dependências

- **Ticket 18** (concluído): define `TIPOS_RETENCAO_VALIDOS` e `SUBSTANCIAS_GLP1_IN360` — o catálogo absorve essas constantes em formato persistido.
- **Ticket 19** (concluído): define `VALIDADE_POR_TIPO_RETENCAO` — o catálogo não altera a lógica de validade, apenas valida a classificação de entrada.
- **pg_trgm**: extensão PostgreSQL para busca por similaridade. Já disponível no PostgreSQL padrão, mas precisa ser habilitada (`CREATE EXTENSION IF NOT EXISTS pg_trgm`).

## Decisões de design

1. **Fase 1 = alertas, não bloqueios.** O catálogo é parcial por natureza. Bloquear emissão com base em catálogo incompleto geraria falsos negativos (substância correta mas ausente do catálogo → bloqueio indevido). A escalação para bloqueio será avaliada quando o catálogo atingir cobertura > 90% das substâncias prescritas.

2. **DCB como chave, não nome comercial.** Nomes comerciais são ambíguos e variáveis. A DCB é o padrão Anvisa para identificação unívoca de substâncias. O prescritor digita o nome comercial ou DCB no campo `nome_medicamento` — o autocomplete faz o match.

3. **Tabela no banco, não constantes em código.** Diferente de `TIPOS_RETENCAO_VALIDOS` (2 valores estáveis) ou `CLASSES_CONTROLE_ESPECIAL` (8 valores), o catálogo terá 50–200+ registros com atualizações regulatórias periódicas. Persistir no banco permite atualização sem deploy.

4. **Não substituir os campos existentes.** `prescricao_itens.classe_controle` e `prescricao_itens.tipo_retencao` continuam sendo a fonte-de-verdade para o motor regulatório. O catálogo é um **oráculo de validação**, não a fonte primária de classificação. Isso preserva a autonomia do prescritor e evita acoplamento perigoso.

5. **Severidade tripartite nos alertas.** O campo `severidade` (`info` | `warning` | `critical`) separa decisão técnica de decisão regulatória. Na fase 1, nenhuma severidade bloqueia emissão. Na fase futura de bloqueio configurável, a aplicação pode optar por bloquear apenas `critical` — ex.: substância de retenção emitida como receita simples. A classificação de severidade é determinística e documentada na tabela de cenários acima.

6. **Catálogo como camada transversal.** O catálogo não é apenas autocomplete — é uma salvaguarda que protege tanto o motor regulatório (classificação de receituários) quanto a circulação atomizada (elegibilidade de itens). Qualquer fluxo que dependa de `classe_controle` ou `tipo_retencao` declarados pelo prescritor deve ser protegido pelo catálogo.

## Cadência de execução

Recomendação: implementar em 2 fases dentro do mesmo ticket:

**Fase A** (estrutura): tabela + modelo + migration + seed + módulo de validação + testes unitários.

**Fase B** (integração): endpoint autocomplete + integração no POST /gerar + testes de integração.

## Arquivos a criar/modificar

| Arquivo | Ação |
|---------|------|
| `app/domain/catalogo_regulatorio.py` | CRIAR — lógica de lookup e validação |
| `app/models/catalogo_substancia.py` | CRIAR — modelo SQLAlchemy |
| `alembic/versions/xxxx_ticket20_catalogo_substancias.py` | CRIAR — migration |
| `app/routers/catalogo.py` | CRIAR — endpoint GET /catalogo/substancias |
| `app/routers/receituarios.py` | MODIFICAR — adicionar alertas_regulatorios na resposta do /gerar |
| `app/domain/medicamento.py` | MODIFICAR — `eh_item_atomizavel()` ganha salvaguarda via catálogo |
| `tests/integration/test_catalogo_regulatorio.py` | CRIAR — testes |
| `docs/tickets/TICKET-20-CATALOGO-REGULATORIO-SUBSTANCIAS.md` | CRIAR — esta documentação |
