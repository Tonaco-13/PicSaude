# TICKET 19 — REGRAS DE VALIDADE E EMISSÃO DE RECEITUÁRIOS

## Contexto regulatório

Cada tipo de receituário regulatório tem um prazo de validade específico, definido pela RDC Anvisa 1.000/2025 e portarias relacionadas:

- **Notificação de Receita A (Amarela)**: 30 dias
- **Notificação de Receita B (Azul)**: 30 dias  
- **Receita de Controle Especial (Branca)**: 30 dias
- **Notificação de Receita Especial (Talidomida/Retinoides)**: 30 dias (pode variar para Talidomida — TODO regulatório)
- **Receita com Retenção (RDC 471/2021)**: 10 dias para antimicrobianos
- **Receita Simples**: sem validade definida (NULL)

A emissão de PDF (download) de um receituário só é permitida se:
1. O status autoriza geração de PDF (`numerado_stub`, `numerado`, `nao_requer_sncr`, `emitido`)
2. O receituário NÃO expirou (exceto re-download de status `emitido`)
3. Outras regras de emissão específicas do tipo são atendidas

## Objetivos

1. Criar um módulo centralizado de regras operacionais (`app/domain/regras_receituario.py`)
2. Adicionar coluna `data_validade` à tabela `receituarios`
3. Calcular e preencher `data_validade` no endpoint POST /gerar
4. Validar regras antes de gerar PDF no endpoint GET /pdf
5. Permitir re-download de receituários já emitidos (status=emitido), mesmo expirados
6. Documentar regulatória com TODO_REGULATORIO onde houver incerteza

## Escopo

### ENTRA

- [ ] Módulo `app/domain/regras_receituario.py` com dataclass `RegraReceituario`
- [ ] Funções auxiliares: `obter_regra_receituario()`, `calcular_data_validade()`, `receituario_expirado()`, `validar_emissao_receituario()`
- [ ] Coluna `data_validade` em `receituarios` (migration Alembic)
- [ ] Modelo SQLAlchemy atualizado com `data_validade`
- [ ] Endpoint POST `/gerar` calcula e preenche `data_validade`
- [ ] Endpoint GET `/pdf` valida regras antes de emitir
- [ ] Testes unitários das regras
- [ ] Testes de integração do fluxo end-to-end
- [ ] Esta documentação

### NÃO ENTRA

- Alteração na integração SNCR (já suporta receituários com diferentes prazos)
- Alteração no PDF (já suporta `data_validade`)
- Validação de prazo diferenciado para Talidomida (futuro — TODO_REGULATORIO)
- Validação de prazo diferenciado para GLP-1 (futuro — TODO_REGULATORIO)

## Implementação

### 1. Módulo de regras (`app/domain/regras_receituario.py`)

Dataclass imutável `RegraReceituario`:

```python
@dataclass(frozen=True)
class RegraReceituario:
    tipo_receituario: str
    validade_dias: int | None       # None = sem validade
    vias: int
    retencao_farmacia: bool
    requer_sncr: bool
    assinatura_minima: str
    permite_reemissao_pdf: bool = True
    observacao: str | None = None
```

Mapa imutável `REGRAS_RECEITUARIO`: todos os 6 tipos com suas regras.

Funções:

- `obter_regra_receituario(tipo_receituario: str) -> RegraReceituario`  
  Levanta `ValueError` se tipo desconhecido.

- `calcular_data_validade(data_emissao: datetime, tipo_receituario: str) -> datetime | None`  
  Retorna `data_emissao + validade_dias`, ou `None` se sem validade.

- `receituario_expirado(data_validade: datetime | None, agora: datetime | None = None) -> bool`  
  Retorna `True` se `data_validade < agora`. `None` sempre retorna `False`.

- `assinatura_atende_minimo(nivel_presente: str | None, nivel_exigido: str) -> bool`  
  Valida hierarquia: `qualificada >= avancada >= nenhuma`.

- `status_permite_pdf(status: str) -> bool`  
  Retorna `True` se status está em `{numerado_stub, numerado, nao_requer_sncr, emitido}`.

- `validar_emissao_receituario(...) -> tuple[bool, list[str]]`  
  Valida todas as regras de emissão. Retorna `(válido, lista_de_motivos)`.  
  Lista vazia = válido.

### 2. Migration Alembic

Arquivo: `alembic/versions/c3d7a8b9e1f2_ticket19_add_data_validade_to_receituarios.py`

```python
def upgrade() -> None:
    op.add_column(
        "receituarios",
        sa.Column("data_validade", sa.DateTime(), nullable=True)
    )
```

Idempotente via `_column_exists()`.

### 3. Modelo SQLAlchemy

Em `app/models/receituario.py`:

```python
data_validade = Column(DateTime, nullable=True)
```

### 4. Endpoint POST `/prescricoes/{protocolo}/receituarios/gerar`

Após criar cada receituário, calcular `data_validade`:

```python
data_validade = calcular_data_validade(agora, dto.tipo)
```

Incluir no INSERT:

```sql
INSERT INTO receituarios (..., data_validade)
VALUES (..., ?)
```

Incluir na resposta JSON:

```json
{
  "receituarios": [
    {
      "id": 123,
      "tipo": "notificacao_receita_b",
      "data_validade": "2026-05-26T10:00:00",
      ...
    }
  ]
}
```

### 5. Endpoint GET `/prescricoes/{protocolo}/receituarios/{id}/pdf`

Antes de gerar PDF, validar regras:

```python
valido, motivos = validar_emissao_receituario(
    tipo_receituario=receituario["tipo_receituario"],
    status=status_atual,
    data_validade=receituario.get("data_validade"),
    ...
)

# Se inválido E NÃO é re-download (status != "emitido")
if not valido and status_atual != "emitido":
    raise HTTPException(status_code=422, detail="; ".join(motivos))
```

**Importante**: Re-download de status `emitido` nunca é bloqueado por expiração, mesmo que `data_validade < agora`.

Usar `data_validade` do receituário (não da prescrição) ao chamar `gerar_pdf_receituario()`:

```python
data_val_receitua = receituario.get("data_validade")
pdf_bytes = gerar_pdf_receituario(
    ...,
    data_validade=str(data_val_receitua) if data_val_receitua else None,
    ...
)
```

## Testes

### Unitários (1-12)

Arquivo: `tests/integration/test_regras_receituario.py`

1. `test_regras_tipos_conhecidos`: todos os 6 tipos existem
2. `test_validade_notificacao_b_30_dias`: B = 30 dias
3. `test_validade_receita_retencao_10_dias`: retenção = 10 dias
4. `test_receita_simples_sem_validade`: simples = None
5. `test_calcular_data_validade`: cálculo correto
6. `test_receituario_expirado_helper`: lógica de expiração
7. `test_assinatura_atende_minimo`: hierarquia de assinatura
8. `test_status_permite_pdf`: quais status permitem PDF
9. `test_validar_emissao_receituario_ok`: validação com sucesso
10. `test_validar_emissao_expirado_bloqueia`: receituário expirado bloqueado
11. `test_validar_emissao_status_invalido`: status inválido bloqueado
12. `test_obter_regra_tipo_invalido`: tipo desconhecido levanta erro

### Integração (13-15)

13. `test_gerar_receituario_preenche_data_validade`: POST /gerar → data_validade presente
14. `test_pdf_receituario_expirado_bloqueia_422`: receituário expirado em status numerado → 422
15. `test_reemissao_pdf_emitido_sempre_permitida`: status=emitido expirado → 200 OK

## TODO regulatório

### TODO_REGULATORIO: Prazo da Notificação Especial (Talidomida)

A RDC 471/2021 menciona que Talidomida (D1) pode exigir prazo específico.  
Confirmar com Anvisa se é 30 dias (como as outras Notificações) ou diferente.

**Localização**: `regras_receituario.py`, campo `observacao` de `notificacao_receita_especial`.

### TODO_REGULATORIO: Prazo de GLP-1 na IN 360/2025

A IN 360/2025 incluiu agonistas GLP-1 (semaglutida, liraglutida, etc.) na RDC 471/2021.  
Confirmar se seguem os mesmos 10 dias (como antimicrobianos) ou têm prazo próprio.

**Localização**: `regras_receituario.py`, campo `observacao` de `receita_retencao`.

## Conformidade regulatória

- **RDC Anvisa 1.000/2025**: Define prazos para Notificações A, B, Especial (30 dias)
- **Portaria SVS/MS 344/1998**: Define classes A, B, C, D
- **RDC 471/2021 + IN 83/2021**: Define prazo de 10 dias para antimicrobianos
- **IN 360/2025**: Incluiu agonistas GLP-1 em RDC 471/2021

## Verificação

```bash
cd /sessions/cool-focused-knuth/mnt/backend

# Executar migration (dry-run)
alembic upgrade --sql af5133f5f172:c3d7a8b9e1f2

# Executar testes unitários
python -m pytest tests/integration/test_regras_receituario.py::test_regras_tipos_conhecidos -v

# Executar testes de integração
python -m pytest tests/integration/test_regras_receituario.py::test_gerar_receituario_preenche_data_validade -v

# Executar todos os testes de Ticket 19
python -m pytest tests/integration/test_regras_receituario.py -v

# Verificar que testes antigos ainda passam
python -m pytest tests/integration/test_receituarios.py -v
python -m pytest tests/integration/test_pdf_receituario.py -v
```

## Notas de implementação

- O cálculo de `data_validade` acontece no endpoint, não no banco, para garantir que sempre use `created_at` da criação do receituário.
- O campo `data_validade` é `NULL` para receita_simples, não 0 ou data fictícia.
- A validação em `/pdf` sempre permite re-download (`status=emitido`), mesmo que expirado, para não impedir acesso a receituários já emitidos.
- A hierarquia de assinatura é: `qualificada (2) > avancada (1) > nenhuma (0)`.
- Todos os valores de regra (vias, requer_sncr, assinatura_minima) são derivados do motor regulatório (Ticket 15), mas re-documentados aqui para clareza operacional.

## Referências

- Ticket 15: Motor Regulatório RDC 1.000/2025
- Ticket 16A: Adapter SNCR (Stub)
- Ticket 17: PDF Receituários Anvisa V2
- Ticket 18: Grupo Retenção (Antimicrobianos/GLP-1)
