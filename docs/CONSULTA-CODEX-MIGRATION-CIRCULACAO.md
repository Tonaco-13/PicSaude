# Consulta CODEX — Migration de regularização: subdomínio circulação diagnóstica

> **Data:** 2026-05-08
> **Contexto:** Etapa 4B do plano de produção PicSaúde
> **Objetivo:** validar plano de migration intermediária antes de implementar

---

## Contexto

O PicSaúde está implementando a Etapa 4 do plano de produção
(`docs/PLANO-PRODUCAO-V2.md` §4): adição de coluna `instance_id VARCHAR(36) NULL`
em 10 tabelas, para marca d'água de rastreabilidade de exfiltração
(`DATA-PROTECTION.md` §4.2).

A migration 4B (`alembic/versions/4b1ce80a017d_etapa4b_add_instance_id.py`)
foi escrita seguindo o padrão `op.batch_alter_table` para cada uma das 10
tabelas. Os testes da migration foram criados em
`tests/test_migration_4b_instance_id.py` (5 cenários: upgrade, downgrade,
idempotência, tipo VARCHAR(36) nullable, head correto).

Ao rodar `pytest tests/test_migration_4b_instance_id.py`, todos os 5 testes
falharam com:

```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError)
no such table: circulacao_diagnostica_eventos
```

---

## Achado — dívida técnica pré-existente

Investigamos e descobrimos **4 tabelas órfãs** no projeto: o model SQLAlchemy
existe, mas nenhuma migration alembic as cria.

| Tabela | Subdomínio | Bloqueia 4B? |
|---|---|---|
| `circulacoes_diagnosticas` (mãe) | Circulação diagnóstica | Sim — alvo indireto (FK target da próxima) |
| `circulacao_diagnostica_eventos` (filha, FK) | Circulação diagnóstica | **Sim — alvo direto da 4B** |
| `circulacao_diagnostica_itens` (filha, FK) | Circulação diagnóstica | Não, mas mesma família |
| `unidades` | Org institucional | Não |

**Causa raiz:** alguém criou os models e usou `init_tables.py`
(`Base.metadata.create_all()`) em vez de criar migration alembic — comportamento
explicitamente desaconselhado pelo docstring do próprio `init_tables.py`:

> "NÃO adicione novas tabelas ou colunas aqui — crie uma migration Alembic"

**Consequência:** o banco do desenvolvedor (Mac) tem essas tabelas porque ele
rodou `init_tables.py` em algum momento. Mas **qualquer ambiente novo** (CI,
deploy no Render, contribuidor que clona o repo) **não vai ter essas tabelas**.
A cadeia alembic está quebrada para qualquer ambiente que não seja o do dev.

---

## Decisão proposta (Engenheiro-Chefe)

Criar migration intermediária entre `e2e98a4780e4` (ticket21_prescritor_certificados,
atual head antes da 4B) e `4b1ce80a017d` (etapa4b) que cria as **3 tabelas do
subdomínio circulação diagnóstica** numa única migration, usando `_table_exists()`
guard (mesmo padrão do baseline manual `037d38d98806`).

Cadeia resultante:

```
e2e98a4780e4 (ticket21)
  → NEW: <hash>_add_circulacao_diagnostica  ← cria 3 tabelas
  → 4b1ce80a017d (etapa4b)                  ← down_revision atualizado
```

`unidades` fica como **TODO separado** (não bloqueia 4B, e tratá-la junto
expandiria escopo demais).

**Classe de mudança (CLAUDE.md §10):** `core` — toca o ledger
(`circulacao_diagnostica_eventos` é `*_eventos`). Mas é regularização de
débito técnico, não introdução de novo objeto sanitário.

---

## Models das 3 tabelas alvo

### `circulacoes_diagnosticas` (mãe)

```python
class CirculacaoDiagnostica(Base):
    __tablename__ = "circulacoes_diagnosticas"

    id                    = Column(Integer, primary_key=True, index=True)
    protocolo             = Column(String, unique=True, nullable=False, index=True)   # UUID
    chave_circulacao      = Column(String, unique=True, nullable=False, index=True)
    pedido_id             = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=False, index=True)
    paciente_id           = Column(Integer, ForeignKey("pacientes.id"), nullable=False, index=True)
    org_id                = Column(Text, nullable=False, index=True)
    unidade_id            = Column(Text, nullable=False, index=True)
    data_hora_proposta    = Column(Text, nullable=True)
    local_texto           = Column(Text, nullable=True)
    instrucoes_preparo    = Column(Text, nullable=True)
    observacao            = Column(Text, nullable=True)
    status                = Column(String(30), nullable=False, default="selecionado")
    tipo_emissao          = Column(String(20), nullable=False, default="novo")
    origem_circulacao_id  = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=True)
    validade              = Column(Text, nullable=False)
    criado_por            = Column(Text, nullable=False)
    criado_em             = Column(Text, nullable=False)
```

### `circulacao_diagnostica_eventos` (filha) — **alvo direto da 4B**

```python
class CirculacaoDiagnosticaEvento(Base):
    __tablename__ = "circulacao_diagnostica_eventos"

    id             = Column(Integer, primary_key=True, index=True)
    circulacao_id  = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=False, index=True)
    tipo_evento    = Column(Text, nullable=False)
    dados_json     = Column(Text, nullable=True)
    criado_em      = Column(Text, nullable=False)
```

### `circulacao_diagnostica_itens` (filha)

```python
class CirculacaoDiagnosticaItem(Base):
    __tablename__ = "circulacao_diagnostica_itens"

    id                    = Column(Integer, primary_key=True, index=True)
    circulacao_id         = Column(Integer, ForeignKey("circulacoes_diagnosticas.id"), nullable=False, index=True)
    pedido_exame_item_id  = Column(Integer, ForeignKey("pedido_exame_itens.id"), nullable=False, index=True)
    nome_exame            = Column(String(200), nullable=False)
    criado_em             = Column(Text, nullable=False)
```

---

## Padrão de idempotência (do baseline)

```python
def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(name)


def upgrade() -> None:
    if not _table_exists("circulacoes_diagnosticas"):
        op.create_table(
            "circulacoes_diagnosticas",
            sa.Column("id", sa.Integer(), nullable=False),
            # ... resto das colunas
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["pedido_id"],   ["pedidos_exame.id"]),
            sa.ForeignKeyConstraint(["paciente_id"], ["pacientes.id"]),
            sa.ForeignKeyConstraint(["origem_circulacao_id"], ["circulacoes_diagnosticas.id"]),
        )
        op.create_index(...)

    if not _table_exists("circulacao_diagnostica_eventos"):
        op.create_table(...)

    if not _table_exists("circulacao_diagnostica_itens"):
        op.create_table(...)


def downgrade() -> None:
    op.drop_table("circulacao_diagnostica_itens")
    op.drop_table("circulacao_diagnostica_eventos")
    op.drop_table("circulacoes_diagnosticas")
```

---

## Snippet relevante da migration 4B (que vai ser destravada)

```python
TABELAS_LEDGER = [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "circulacao_diagnostica_eventos",   # ← falha sem a migration intermediária
    "agendamento_eventos",
    "eventos_publicacao",
]
TABELAS_PRINCIPAIS = ["prescricoes", "pedidos_exame", "laudos", "agendamentos"]

def upgrade() -> None:
    for tabela in TABELAS_LEDGER + TABELAS_PRINCIPAIS:
        with op.batch_alter_table(tabela) as batch_op:
            batch_op.add_column(
                sa.Column("instance_id", sa.String(length=36), nullable=True)
            )
```

---

## Perguntas específicas para CODEX

1. **Pattern de idempotência (`_table_exists`)** — o baseline manual usa esse
   guard porque o banco de dev pode já ter as tabelas. Em uma migration nova,
   é defensivo demais? Ou é justificado enquanto o projeto ainda mantém
   `init_tables.py` em paralelo? Há contraindicação para repetir esse padrão?

2. **Encadeamento alembic** — alterar `down_revision` da 4B (atualmente
   `e2e98a4780e4`) para apontar para a nova migration intermediária é seguro?
   A 4B já está no disco mas **ainda não foi commitada**. Há risco se outro
   colaborador já tiver feito `alembic stamp 4b1ce80a017d` em algum ambiente?

3. **Escopo da migration intermediária** — faz sentido criar as 3 tabelas
   do subdomínio numa única migration (são família semântica) ou é melhor
   separar a mãe em uma migration e as 2 filhas em outra (princípio: cada
   migration faz uma coisa)?

4. **Dívida residual (`unidades`)** — a tabela `unidades` continua órfã.
   Qual o critério recomendado: criar nova migration agora ou marcar como
   TODO em `docs/PLANO-PRODUCAO-V2.md`? Ela não bloqueia a 4B mas é
   inconsistência de schema futura.

5. **Riscos não detectados** — há algum risco arquitetural que esta
   abordagem esconde? Em particular: como o model nunca passou por uma
   migration formal, é possível que o schema "real" no banco do dev
   tenha drift do model atual (ex: índices, constraints, tipos sutis de
   coluna). Há jeito barato de detectar drift antes de implementar?

6. **Nomeação da migration** — sugestão de nome que comunique a natureza
   "regularização de débito técnico" e não "nova feature"? Cogitamos
   `<hash>_add_circulacao_diagnostica_subdominio` mas talvez algo como
   `<hash>_regulariza_circulacao_diagnostica` seja mais claro
   semanticamente.

---

## O que NÃO precisamos do CODEX

- Validação do schema dos models (já confirmado lendo direto do código)
- Decisão entre Opção A (criar migration) vs B (remover tabela da 4B) vs C
  (skip-if-not-exists na 4B) — já decidimos pela A com Fabiano
- Revisão da migration 4B em si (já passou por revisão CODEX em 2026-05-06)

---

## Próximo passo após resposta do CODEX

1. Engenheiro-Chefe consolida feedback do CODEX (aceito / adaptado / rejeitado)
2. Implementa a migration intermediária
3. Atualiza `down_revision` da 4B
4. Atualiza `tests/test_migration_4b_instance_id.py` se necessário
5. Fabiano roda pytest → 5 verdes esperados
6. Commitar 3 arquivos: nova migration + 4B + teste
