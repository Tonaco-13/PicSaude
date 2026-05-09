# TICKET 4C — Helper de inserção no ledger com `instance_id`

> **Sub-tarefa 4C do plano de produção** (`docs/PLANO-PRODUCAO-V2.md` §4)
> **Classe (CLAUDE.md §10):** `core` — toca o ledger imutável
> **Pacto:** Regra 2 estrita (ticket → CODEX → Claude Code → validação)
> **Predecessores:** 4A (`app/instance.py`), 4B-prequel (`a3f5c8d9e1b2`), 4B (`4b1ce80a017d`)
> **Sucessoras:** 4D (integração nos endpoints), 4E (testes E2E)
> **Data:** 2026-05-08
> **Revisado por:** CODEX (2026-05-08) — 13 pontos integrados (ver §5)

---

## 1. Contexto e motivação

A Etapa 4 entrega a **marca d'água de rastreabilidade da instância PicSaúde** —
um UUID v4 (`instance_id`) embutido em cada evento do ledger e em cada
objeto sanitário, usado como prova forense em caso de exfiltração de dados
(`DATA-PROTECTION.md` §4.2).

Estado em 2026-05-09:

| Sub-tarefa | Status | Entrega |
|---|---|---|
| 4A | ✅ commitada | `app/instance.py` — helper `get_instance_id(session)` |
| 4B-prequel | ✅ commitada | `a3f5c8d9e1b2` — regulariza 3 tabelas órfãs |
| 4B | ✅ commitada | `4b1ce80a017d` — coluna `instance_id VARCHAR(36) NULL` em 10 tabelas |
| **4C** | **🟡 este ticket** | **Helper centralizado de inserção no ledger** |
| 4D | ⏳ futuro | Integração nos endpoints (preencher `instance_id` em registros novos) |
| 4E | ⏳ futuro | Testes E2E |

**Por que 4C existe:** a 4B adicionou a coluna física, mas **inserts atuais
não preenchem** `instance_id`. Sem o helper, cada router precisaria carregar
o `get_instance_id(session)` manualmente — risco alto de esquecimento + duplicação
de lógica + falta de uniformidade.

A 4C estabelece um **fluxo centralizado** que:

1. **Obtém** o `instance_id` via `get_instance_id_conn(conn)` (variante
   raw-conn, sem commit interno).
2. **Recusa** inserção no ledger se o `instance_id` não for fornecido —
   o helper levanta `TypeError` em chamadas sem o argumento (parâmetro
   keyword-only obrigatório, sem default).

A explicitness é deliberada: substitui "magic" (helper auto-detecta) por
contrato claro (caller é responsável pelo `instance_id`, em troca ganha
controle sobre a transação clínica). Isso elimina o risco do
`session.commit()` antecipado dentro de fluxo clínico.

**Importante (clarificação CODEX):**

> 4C fecha a lacuna no nível de **API de domínio** — cria o helper, expõe a
> assinatura correta, encapsula o drift de schema. **A 4D fecha a lacuna no
> runtime dos endpoints** — substitui os `INSERT INTO ... ` raw nos routers
> pelo helper. Só após 4D + deploy é que **eventos novos** ganham `instance_id`
> automaticamente.

Backfill de eventos pré-existentes é responsabilidade da **Etapa 8** (pré-deploy
público), não desta sub-tarefa nem da 4D.

---

## 2. Estado atual mapeado

### 2.1 Padrão de escrita no ledger hoje

Cada router faz **duas escritas** por evento:

```python
# 1. Ledger interno do subdomínio (varia por subdomínio)
conn.execute(
    """
    INSERT INTO prescricao_eventos
      (prescricao_id, tipo_evento, ator_tipo, ator_id, payload_json, created_at)
    VALUES (?, 'prescricao_emitida', 'prescritor', ?, ?, ?)
    """,
    (prescricao_id, cns, json.dumps(payload, ensure_ascii=False), agora),
)

# 2. Outbox externo (uniforme — já é helper)
registrar_outbox(conn, "prescricao_emitida", "prescricao", protocolo, payload)
```

`registrar_outbox()` em `app/domain/outbox.py` é o precedente arquitetural:
helper único que isola a escrita em `eventos_publicacao`. **Funciona, e
nunca quebra fluxo clínico** (try/except com log de warning — princípio G4A §2.4).

### 2.2 Drift severo entre as 6 tabelas de eventos

Levantamento direto dos models (`app/models/*evento*.py`):

| Tabela | "tipo" | "payload" | "data" | Ator |
|---|---|---|---|---|
| `prescricao_eventos` | `tipo_evento` | `payload_json` | `created_at` (DateTime) | `ator_tipo`, `ator_id` |
| `pedido_exame_eventos` | `tipo_evento` | `dados_json` | `criado_em` (DateTime) | — |
| `laudo_eventos` | `tipo_evento` | `dados_json` | `criado_em` (DateTime) | — |
| `agendamento_eventos` | `evento` ⚠️ | `payload` | `criado_em` (Text) | — |
| `circulacao_diagnostica_eventos` | `tipo_evento` | `dados_json` | `criado_em` (Text) | — |
| `eventos_publicacao` (outbox) | `tipo_evento` | `payload` | `criado_em` (Text) | + `org_id`, `unidade_id` |

⚠️ **`agendamento_eventos` é o outlier**: usa `evento` em vez de `tipo_evento`.

Isso é débito técnico pré-existente. **A 4C não vai resolver o drift de
nomenclatura — vai conviver com ele**, encapsulando as diferenças no helper.
Padronização de schemas vira ticket separado (similar à Task #5 — drift de
`prestadores`).

### 2.3 Após 4B: todas as 6 tabelas têm `instance_id`

```python
# Acabou de entrar (commit 89f064a):
TABELAS_LEDGER = [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "circulacao_diagnostica_eventos",
    "agendamento_eventos",
    "eventos_publicacao",
]
# Cada uma agora tem coluna instance_id VARCHAR(36) NULL
```

Mas inserts atuais não preenchem. **Esta é a lacuna que 4C fecha.**

---

## 3. Decisões arquiteturais (3 caminhos a avaliar)

### Caminho A — Helper único `registrar_evento_ledger` + atualizar `registrar_outbox` (recomendado)

**Nota arquitetural (CODEX 2026-05-08):** o helper recebe `conn` raw (não
`Session`). O backend opera majoritariamente com `get_tx()` + `conn` raw, e
forçar `Session` aqui aumentaria muito o blast radius da 4D. Pior:
`get_instance_id(session)` chama `session.commit()` no first boot — risco de
commit antecipado dentro de transação clínica. Assinatura final usa `conn`.

```python
# app/domain/ledger.py (NOVO)

from typing import Literal

ObjetoSanitario = Literal[
    "prescricao",
    "pedido_exame",
    "laudo",
    "agendamento",
    "circulacao_diagnostica",
]


def registrar_evento_ledger(
    conn,
    *,
    objeto_tipo: ObjetoSanitario,
    objeto_id: int,
    tipo_evento: str,
    instance_id: str,                   # OBRIGATÓRIO (CODEX P1-2)
    payload: dict | None = None,
    ator_tipo: str | None = None,       # apenas prescricao_eventos usa
    ator_id: str | None = None,
) -> None:
    """
    Insere um evento no ledger interno do subdomínio.

    Encapsula o drift de schema entre as 5 tabelas de eventos clínicos:
    nomes de coluna, tipos de data, presença de ator.

    `instance_id` é parâmetro OBRIGATÓRIO — quem chama deve obter via
    `app.instance.get_instance_id_conn(conn)` UMA VEZ por transação e
    passar o mesmo valor para esta função e para `registrar_outbox`. Isso
    garante coerência (ledger e outbox referem-se à mesma instância) e
    evita múltiplas leituras de `meta_instalacao` na mesma operação.

    Levanta exceção em falha (diferente do outbox: ledger interno é fonte
    de verdade — falha precisa quebrar o fluxo clínico).
    """
```

**Fluxo idiomático nos routers (4D):**

```python
instance_id = get_instance_id_conn(conn)
registrar_evento_ledger(
    conn,
    objeto_tipo="prescricao",
    objeto_id=prescricao_id,
    tipo_evento="prescricao_emitida",
    instance_id=instance_id,
    payload=ev_payload,
    ator_tipo="prescritor",
    ator_id=cns,
)
registrar_outbox(
    conn,
    "prescricao_emitida", "prescricao", protocolo, ev_payload,
    instance_id=instance_id,
)
```

**Características:**

- Função única que dispatcha por `objeto_tipo` (mapping interno `_LEDGER_SCHEMA`)
- Sabe internamente o nome de coluna correto de cada tabela
- `instance_id` parâmetro obrigatório (caller controla)
- `Literal[...]` no `objeto_tipo` para type-checker + `ValueError` em runtime
  (defesa em camadas — `Literal` não protege chamadas dinâmicas)
- Levanta exceção em falha (ledger é fonte de verdade)
- `registrar_outbox` ganha parâmetro `instance_id` **opcional** (retrocompat
  com chamadas pré-4D que ainda não passam o valor — segue best-effort)

**Trade-off:** mais magia interna no helper (mapping de nomes), mas API
externa uniforme. Routers ficam mais limpos.

**Tamanho estimado:** ~150 linhas (helper) + ~50 linhas (`get_instance_id_conn`) + ~250 linhas (testes).

### Caminho B — Helper por subdomínio (5 helpers)

```python
# app/domain/ledger/prescricao.py
def registrar_evento_prescricao(session, prescricao_id, tipo_evento, payload, ator_tipo, ator_id):
    ...

# app/domain/ledger/agendamento.py
def registrar_evento_agendamento(session, agendamento_id, tipo_evento, payload):
    ...

# (mais 3)
```

- Cada helper tem assinatura específica do schema do subdomínio
- Sem magia interna
- Mais código, mais explícito

**Trade-off:** cada subdomínio tem sua função; padronização via convenção
(todos chamam internamente um `_writer` privado). Routers passam a ter
imports diferentes por subdomínio.

**Tamanho estimado:** ~300 linhas (5 helpers) + ~250 linhas (testes).

### Caminho C — Padronizar schemas primeiro (rejeitado)

Migration que renomeia `evento` → `tipo_evento` em `agendamento_eventos`,
unifica `dados_json`/`payload_json`/`payload` → `payload`, etc. Depois
helper único.

**Por que rejeito agora:**
- Toca 6 tabelas via `ALTER TABLE RENAME COLUMN` (requer SQLite ≥3.25 e PostgreSQL — OK)
- Quebra qualquer query SQL raw existente que use o nome antigo (busca exaustiva no código)
- Vira blocker maior que a Etapa 4 inteira
- Padronização é débito técnico válido, mas merece **ticket separado** (similar à Task #5)

### Recomendação do Engenheiro-Chefe

**Caminho A** — helper único com dispatch interno.

Motivos:
1. **Centralização do `instance_id`** é o objetivo da 4C — um único ponto de
   inserção é o jeito mais robusto de garantir que **nenhum evento sai sem `instance_id`**.
2. **Precedente:** `registrar_outbox` já usa esse padrão (helper único, sem magia
   excessiva). Funciona há tempo.
3. **Mapping interno é pequeno** (5 entradas). Custo de manutenção baixo.
4. **Testes podem cobrir todos os 5 subdomínios** sem duplicação.

---

## 4. Plano de implementação (Caminho A)

### 4.1 Novo arquivo `app/domain/ledger.py`

Estrutura interna:

```python
# Mapping (privado) das diferenças de schema entre tabelas.
# Encapsula o drift pré-existente — padronização vira ticket separado.
_LEDGER_SCHEMA = {
    "prescricao": {
        "tabela": "prescricao_eventos",
        "coluna_fk": "prescricao_id",
        "coluna_tipo": "tipo_evento",
        "coluna_payload": "payload_json",
        "coluna_data": "created_at",
        "tem_ator": True,
    },
    "pedido_exame": {
        "tabela": "pedido_exame_eventos",
        "coluna_fk": "pedido_id",
        "coluna_tipo": "tipo_evento",
        "coluna_payload": "dados_json",
        "coluna_data": "criado_em",
        "tem_ator": False,
    },
    "laudo": {
        "tabela": "laudo_eventos",
        "coluna_fk": "laudo_id",
        "coluna_tipo": "tipo_evento",
        "coluna_payload": "dados_json",
        "coluna_data": "criado_em",
        "tem_ator": False,
    },
    "agendamento": {
        "tabela": "agendamento_eventos",
        "coluna_fk": "agendamento_id",
        "coluna_tipo": "evento",          # ← outlier: usa "evento", não "tipo_evento"
        "coluna_payload": "payload",
        "coluna_data": "criado_em",
        "tem_ator": False,
    },
    "circulacao_diagnostica": {
        "tabela": "circulacao_diagnostica_eventos",
        "coluna_fk": "circulacao_id",
        "coluna_tipo": "tipo_evento",
        "coluna_payload": "dados_json",
        "coluna_data": "criado_em",
        "tem_ator": False,
    },
}


def registrar_evento_ledger(
    conn,
    *,                                  # tudo após este ponto é keyword-only
    objeto_tipo: ObjetoSanitario,
    objeto_id: int,
    tipo_evento: str,
    instance_id: str,                   # OBRIGATÓRIO
    payload: dict | None = None,
    ator_tipo: str | None = None,
    ator_id: str | None = None,
) -> None:
    """[docstring detalhada — ver §3 Caminho A]"""

    # 1. Validação de objeto_tipo (defesa em runtime, complementar ao Literal)
    if objeto_tipo not in _LEDGER_SCHEMA:
        raise ValueError(
            f"objeto_tipo '{objeto_tipo}' inválido. "
            f"Permitidos: {sorted(_LEDGER_SCHEMA.keys())}"
        )

    schema = _LEDGER_SCHEMA[objeto_tipo]

    # 2. Validação de ator (consistência com schema)
    if not schema["tem_ator"] and (ator_tipo or ator_id):
        raise ValueError(
            f"objeto_tipo '{objeto_tipo}' não suporta ator_tipo/ator_id. "
            f"Apenas 'prescricao' tem essa coluna."
        )
    if schema["tem_ator"] and not ator_tipo:
        raise ValueError(
            f"objeto_tipo '{objeto_tipo}' exige ator_tipo (ex: 'prescritor')."
        )

    # 3. Preparação dos valores
    agora = datetime.now(timezone.utc).isoformat()
    payload_json = json.dumps(payload or {}, ensure_ascii=False)

    # 4. INSERT dinâmico respeitando schema do subdomínio
    #    Compatível com SQLite e PostgreSQL via wrapper _PgConnection.
    if schema["tem_ator"]:
        sql = f"""
            INSERT INTO {schema["tabela"]}
              ({schema["coluna_fk"]}, {schema["coluna_tipo"]},
               ator_tipo, ator_id,
               {schema["coluna_payload"]}, {schema["coluna_data"]}, instance_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params = (objeto_id, tipo_evento, ator_tipo, ator_id,
                  payload_json, agora, instance_id)
    else:
        sql = f"""
            INSERT INTO {schema["tabela"]}
              ({schema["coluna_fk"]}, {schema["coluna_tipo"]},
               {schema["coluna_payload"]}, {schema["coluna_data"]}, instance_id)
            VALUES (?, ?, ?, ?, ?)
        """
        params = (objeto_id, tipo_evento, payload_json, agora, instance_id)

    # 5. Execução — falha levanta exceção (ledger é fonte de verdade)
    conn.execute(sql, params)
```

### 4.1-bis Adição em `app/instance.py` — `get_instance_id_conn(conn)`

Variante do `get_instance_id(session)` que opera com `conn` raw em vez de
`Session` SQLAlchemy. Necessária porque:

1. Os routers operam com `conn = get_conn()` (não `Session`).
2. `get_instance_id(session)` faz `session.commit()` no first boot — risco
   de commit antecipado dentro de transação clínica (CODEX P1-1).
3. O wrapper `_PgConnection.execute()` em `database.py:173` adiciona
   `RETURNING id` automaticamente em INSERTs sem RETURNING — quebraria em
   `meta_instalacao` (PK é `chave`, não `id`) (CODEX P2-1).

```python
def get_instance_id_conn(conn) -> str:
    """
    Variante de get_instance_id() para uso com conn raw (não Session).

    Padrão: SELECT primeiro → INSERT idempotente → SELECT autoritativo.

    Decisões de portabilidade (CODEX 2026-05-08):
      - Não dependemos do valor retornado pelo INSERT. O SELECT
        subsequente é a fonte de verdade — funciona idêntico em SQLite
        e PostgreSQL.
      - RETURNING chave aparece no SQL apenas para passar pelo wrapper
        _PgConnection (que adiciona RETURNING id automático em INSERTs
        sem RETURNING — quebraria em meta_instalacao, cuja PK é chave).
        Em SQLite, RETURNING é no-op para nós.

    Não comita — o caller é responsável pelo commit/rollback da
    transação clínica que envolve esta chamada.
    """
    # 1. SELECT primeiro (caso comum: instance_id já existe)
    row = conn.execute(
        "SELECT valor FROM meta_instalacao WHERE chave = ?",
        ("instance_id",),
    ).fetchone()
    if row:
        valor = row[0] if isinstance(row, tuple) else row["valor"]
        return _validar_uuid_v4(valor)

    # 2. First boot: gera novo + INSERT idempotente (race-safe)
    novo = str(uuid.uuid4())
    agora = datetime.now(timezone.utc).isoformat()

    # SQLite: INSERT OR IGNORE; PostgreSQL: ON CONFLICT DO NOTHING.
    # RETURNING chave só serve para satisfazer o wrapper PG —
    # NÃO confiamos no valor retornado (ver SELECT no passo 3).
    if _is_sqlite_conn(conn):
        sql = (
            "INSERT OR IGNORE INTO meta_instalacao (chave, valor, criado_em) "
            "VALUES (?, ?, ?) RETURNING chave"
        )
    else:
        sql = (
            "INSERT INTO meta_instalacao (chave, valor, criado_em) "
            "VALUES (?, ?, ?) ON CONFLICT (chave) DO NOTHING RETURNING chave"
        )
    conn.execute(sql, ("instance_id", novo, agora))

    # 3. SELECT autoritativo (fonte de verdade — race-safe).
    #    Se outro processo venceu a race, retornamos o valor dele;
    #    caso contrário, o nosso. Não há ambiguidade.
    row = conn.execute(
        "SELECT valor FROM meta_instalacao WHERE chave = ?",
        ("instance_id",),
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "Falha ao persistir instance_id no DB durante first boot via conn."
        )
    valor = row[0] if isinstance(row, tuple) else row["valor"]
    return _validar_uuid_v4(valor)
```

**Importante:** o env override (`PICSAUDE_INSTANCE_ID`) e a sincronização com
o arquivo `.instance_id` permanecem APENAS na variante `get_instance_id(session)`
— porque a variante `_conn` é chamada dentro de transações clínicas (cada
prescrição), onde I/O em arquivo seria contraproducente. O arquivo é populado
no boot da aplicação (lifespan startup), via `get_instance_id(session)`.

### 4.2 Atualizar `app/domain/outbox.py`

```python
def registrar_outbox(
    conn,
    tipo_evento: str,
    objeto_tipo: str,
    objeto_id: str,
    payload: dict[str, Any],
    org_id: str | None = None,
    unidade_id: str | None = None,
    instance_id: str | None = None,   # ← NOVO
) -> str | None:
    """..."""
    # INSERT atualizado para incluir instance_id na coluna correspondente
```

**NÃO** chamar `get_instance_id` dentro de `registrar_outbox` — passamos
explicitamente. Por quê:
- `registrar_outbox` recebe `conn` (raw SQLite), não `session` (SQLAlchemy)
- `get_instance_id` precisa de `session` para ler `meta_instalacao`
- Resolver isso forçaria `outbox.py` a depender de SQLAlchemy — overkill

O chamador (router ou `registrar_evento_ledger`) chama `get_instance_id`
uma vez e passa para ambos.

### 4.3 Não tocar nos routers nesta sub-tarefa

A migração dos routers (substituir `conn.execute("INSERT INTO ... ")` por
`registrar_evento_ledger(...)`) é responsabilidade da **4D**.

Esta separação evita PR gigante e permite:
- 4C ter testes unitários focados (sem fixtures de router)
- 4D ser revisado endpoint a endpoint

### 4.4 Critérios de aceitação

1. ✅ Arquivo `app/domain/ledger.py` criado com `registrar_evento_ledger`
2. ✅ `app/instance.py` atualizado com `get_instance_id_conn(conn)` — sem
   commit interno, com `RETURNING chave` explícito (passa pelo wrapper
   `_PgConnection` sem ser interceptado)
3. ✅ `app/domain/outbox.py` atualizado com parâmetro `instance_id` opcional
4. ✅ `Literal["prescricao", ...]` no `objeto_tipo` para type-checker
5. ✅ Validação de `objeto_tipo` em runtime (raise se inválido)
6. ✅ Validação de `ator_tipo`/`ator_id` (raise se inconsistente com schema)
7. ✅ `instance_id` é parâmetro **obrigatório** do helper (caller controla)
8. ✅ Falha em INSERT no ledger levanta exceção (ledger é fonte de verdade);
   outbox segue best-effort (silencia)
9. ✅ Testes unitários cobrem os 5 subdomínios
10. ✅ Testes verificam que `instance_id` aparece no banco após cada insert
11. ✅ Testes negativos: `objeto_tipo` inválido, ator inconsistente
12. ✅ Testes de invariantes transacionais: rollback remove ledger+outbox;
   ledger e outbox compartilham o mesmo `instance_id`; first boot não
   comita dados clínicos parcialmente
13. ✅ Compatível com SQLite (dev) e PostgreSQL (prod) — incluindo o wrapper
   `_PgConnection`

### 4.5 Testes obrigatórios (`tests/test_ledger_helper.py`)

**Setup (CODEX P2-3):** os testes **NÃO** podem usar `Base.metadata.create_all()`
puro — a coluna `instance_id` vem só por Alembic (4B). Usar
`alembic upgrade head` em SQLite temporário (mesmo padrão de
`tests/test_migration_4b_instance_id.py` e
`tests/test_migration_regulariza_circulacao_diagnostica.py`).

**Cobertura por subdomínio (5 testes — happy path):**

```
test_registrar_evento_prescricao_preenche_instance_id
test_registrar_evento_pedido_exame_preenche_instance_id
test_registrar_evento_laudo_preenche_instance_id
test_registrar_evento_agendamento_preenche_instance_id  # outlier "evento"
test_registrar_evento_circulacao_diagnostica_preenche_instance_id
```

**Validação de entrada (3 testes — negative path):**

```
test_objeto_tipo_invalido_raise_value_error
test_prescricao_sem_ator_raise_value_error
test_outros_subdominios_com_ator_raise_value_error
```

**Outbox e retrocompatibilidade (2 testes):**

```
test_outbox_aceita_instance_id_opcional
test_outbox_sem_instance_id_continua_funcionando_silencioso  # retrocompat
```

**Invariantes transacionais (4 testes — adicionados por CODEX resp. 7):**

```
test_rollback_da_transacao_remove_ledger_e_outbox
  # garante que ledger + outbox são gravados na MESMA transação
  # (cenário: pagamento falha após emissão → rollback limpa tudo)

test_ledger_e_outbox_recebem_o_mesmo_instance_id
  # invariante crítica: dados em ambas as tabelas devem ter o mesmo
  # UUID — caso contrário, a marca d'água perde a correspondência
  # forense entre ledger interno e outbox externo

test_payload_none_inserido_como_dict_vazio
  # semântica de payload=None: helper insere "{}" no banco (não NULL)
  # — evita ambiguidade entre "sem payload" e "payload ausente"

test_first_boot_nao_antecipa_commit_de_dados_clinicos
  # Teste de regressão para o bug que motivou a §4.1-bis (CODEX P1-1):
  # get_instance_id(session) chamava session.commit() em first boot,
  # antecipando commit de qualquer coisa pendente na transação clínica.
  #
  # Cenário (refinado por CODEX 2026-05-08):
  #   1. with get_tx() as conn:                         # transação clínica aberta
  #   2.   conn.execute("INSERT INTO prescricoes ...")  # grava dado clínico
  #   3.   instance_id = get_instance_id_conn(conn)     # first boot — INSERT em meta_instalacao
  #   4.   registrar_evento_ledger(conn, ...)           # grava evento no ledger
  #   5.   raise RuntimeError("simulando falha")        # força exceção
  #   # → with sai com rollback (get_tx faz isso por contrato)
  #
  # Assertivas (em ordem de criticidade):
  #   - prescricoes está VAZIA (rollback funcionou no clínico)            ← invariante crítica
  #   - prescricao_eventos está VAZIA (rollback funcionou no ledger)
  #   - meta_instalacao pode estar com instance_id ou vazia (design choice
  #     — o ponto é não ter ANTECIPADO commit do clínico)
```

**Compatibilidade DB (1 teste):**

```
test_get_instance_id_conn_funciona_com_pgconnection_wrapper
  # via mock do wrapper _PgConnection: confirma que SELECT/INSERT
  # com RETURNING chave NÃO é interceptado pela auto-adição de
  # RETURNING id em INSERTs sem RETURNING (linha 173 de database.py)
```

**Total: 15 testes** (era 11 no rascunho original; CODEX adicionou 4 de
invariantes transacionais).

---

## 5. Decisões consolidadas após revisão CODEX (2026-05-08)

Resumo do ciclo de revisão:

| Categoria | Aceito | Adaptado | Rejeitado |
|---|---|---|---|
| Achados de risco (rodada 1) | 5 | 0 | 0 |
| Respostas a perguntas (rodada 1) | 8 | 0 | 0 |
| Notas menores (rodada 1) | 0 | 1 (data) | 0 |
| **Lapidações finais (rodada 2)** | **3** | **0** | **0** |
| **Total** | **16** | **1** | **0** |

**Status: ticket aprovado pelo CODEX.** Pronto para passo 6 do ciclo Regra 2
(Claude Code implementa).

### 5.1 Achados de risco incorporados

1. **[P1] `Session` → `conn` raw** + criar `get_instance_id_conn(conn)`.
   *Razão*: `session.commit()` no first boot pode antecipar commit dentro
   de transação clínica. Refatorar todos os routers para `Session`
   aumentaria o blast radius da 4D desnecessariamente.
   *Implementação*: §3 Caminho A (assinatura final) + §4.1-bis
   (`get_instance_id_conn`).

2. **[P1] `instance_id` parâmetro obrigatório do helper.** Caller chama
   `get_instance_id_conn(conn)` UMA VEZ por transação e passa para ledger
   + outbox. Garante coerência (mesma instância em ambas as tabelas) e
   evita múltiplas leituras de `meta_instalacao`.
   *Implementação*: §3 Caminho A + fluxo idiomático §3.

3. **[P2] Workaround para wrapper PostgreSQL.** O `_PgConnection.execute()`
   em `database.py:173` adiciona `RETURNING id` automático em INSERTs
   sem RETURNING — quebraria em `meta_instalacao` (PK é `chave`).
   *Implementação*: SQL do `get_instance_id_conn` usa `RETURNING chave`
   explícito, forçando o caminho `has_returning=True` (§4.1-bis).

4. **[P2] Clarificação textual.** "4C fecha a lacuna no nível de **API de
   domínio**; 4D fecha no **runtime dos endpoints**." Aplicado em §1.

5. **[P2] Testes não dependem de `Base.metadata.create_all()`.** A coluna
   `instance_id` vem só por Alembic. Usar `alembic upgrade head` em
   SQLite temporário (padrão da 4B/regulariza). Aplicado em §4.5.

### 5.2 Respostas técnicas incorporadas

1. **API do helper**: `conn` + opcionais keyword-only, sem `**kwargs`.
   Subdomínios futuros com campos exclusivos evoluem o `_LEDGER_SCHEMA`,
   não a assinatura.

2. **Validação `objeto_tipo`**: defesa em camadas — `Literal[...]` para
   type-checker + `ValueError` em runtime (chamadas dinâmicas).

3. **`registrar_outbox(instance_id=None)` retrocompat**: aceitável.
   Outbox segue best-effort (não aborta). Em 4D, testes exigem que
   chamadas novas passem o valor.
   *Correção textual*: backfill é responsabilidade da Etapa 8
   (pré-deploy), não da 4D.

4. **Falha no ledger interno raise**: confirmado. Silenciar violaria a
   propriedade de fonte de verdade do ledger. Outbox pode falhar sem
   quebrar fluxo; ledger não.

5. **Não refatorar routers para `Session`**: helper raw-conn transacional,
   no estilo do `outbox.py`.

6. **Drift de nomenclatura encapsulado** no `_LEDGER_SCHEMA`. Padronização
   (renomear colunas) viraria migration `core` maior — fica como ticket
   futuro, separado da Etapa 4.

7. **Testes — adicionar 4 invariantes transacionais**:
   - rollback remove ledger + outbox
   - ledger e outbox compartilham mesmo `instance_id`
   - `payload=None` tem semântica definida (insere `"{}"`, não NULL)
   - first boot não comita dados clínicos parcialmente
   *Implementação*: §4.5 — total 15 testes (era 11).

8. **Estrutura monolítica** (`app/domain/ledger.py`) OK para 150 linhas.
   Pacote vira opção quando crescer.

### 5.3 Adaptação leve

- Data do ticket: **2026-05-09 → 2026-05-08** (estava como rascunho-amanhã).

### 5.4 Lapidações finais (rodada 2 — CODEX aprovou com 3 ajustes)

1. **Padrão "INSERT idempotente + SELECT autoritativo" no
   `get_instance_id_conn`**, em vez de confiar no valor retornado pelo
   `RETURNING`. O `RETURNING chave` permanece no SQL apenas para passar
   pelo wrapper `_PgConnection`, mas o valor não é lido — o `SELECT`
   subsequente é a fonte de verdade. *Razão*: portabilidade idêntica
   entre SQLite e PostgreSQL.
   *Implementação*: §4.1-bis (atualizada).

2. **Linguagem precisa**: substituir "helper preenche `instance_id`
   automaticamente" por "fluxo centralizado obtém via
   `get_instance_id_conn(conn)` e helper recusa inserção sem ele". A
   decisão de `instance_id` obrigatório é explicitness, não magic.
   *Implementação*: §1 (reescrito).

3. **Teste transacional refinado** — `test_first_boot_nao_antecipa_commit_de_dados_clinicos`:
   dentro de `with get_tx()`, gravar dado clínico + chamar
   `get_instance_id_conn` + gravar ledger + forçar exceção. Verificar
   que **dado clínico E ledger deram rollback**. A linha em
   `meta_instalacao` é livre (design choice). É o teste de regressão
   para o bug que motivou a §4.1-bis.
   *Implementação*: §4.5 (atualizado).

### 5.5 Ajustes pós-implementação (rodada 3 — CODEX revisou o código entregue)

Após Claude Code entregar 38/38 testes verdes, CODEX revisou o código em
disco e levantou 3 pontos antes de aprovar o commit. Todos aceitos.

1. **[P1] Validar `instance_id` em runtime no `registrar_evento_ledger`.**
   *Achado*: o contrato "ledger não aceita evento sem `instance_id` válido"
   só pegava ausência (`TypeError` via keyword-only sem default), não
   invalidez (`None` explícito, `""`, lixo, UUID v1). Caller poderia
   passar valor inválido e o helper insertaria.
   *Fix*: `_validar_uuid_v4(instance_id)` no início, antes de qualquer
   outra validação. Reusa helper já existente em `instance.py`.
   *Testes adicionais*: 3 negativos (`None`, `""`, string não-UUID).

2. **[P2-A] Startup hook + nuance do env override (Fabiano apontou).**
   *Achado base*: `get_instance_id_conn(conn)` ignora env override e
   arquivo `.instance_id`. Em ambiente novo/restaurado, primeira
   transação clínica cria valor no DB sem sincronizar arquivo —
   divergência que `get_instance_id(session)` rejeitaria depois com
   `RuntimeError`.
   *Achado complementar (Fabiano)*: `get_instance_id(session)` retorna
   cedo se `PICSAUDE_INSTANCE_ID` existe em dev/test, sem persistir
   DB/arquivo. Logo, startup hook sozinho não garante coerência se a
   app roda com env override + `_conn` é chamado depois.
   *Fix duplo*:
   - Adicionar `lifespan` (asynccontextmanager) em `app/main.py` que
     abre `SessionLocal()`, chama `get_instance_id(session)`, fecha,
     `yield`. Garante DB↔arquivo↔env coerentes ANTES do primeiro request.
   - Em `get_instance_id_conn(conn)`, **respeitar env override em
     dev/test** (mesma regra de `get_instance_id(session)` linhas 226-238):
     se `PICSAUDE_INSTANCE_ID` setado e `PICSAUDE_ENV != "prod"`, retornar
     `_validar_uuid_v4(env_id)` ANTES do SELECT no DB. Em prod, raise
     se env override estiver setado.

3. **[P2-B] SQLite sem `RETURNING` no `get_instance_id_conn`.**
   *Achado*: `RETURNING chave` no caminho SQLite só existia para
   defensividade contra o wrapper PG, mas reduz compatibilidade a
   SQLite ≥ 3.35 (o RETURNING não é necessário em SQLite nativo).
   *Fix*: split de branches:
   - **SQLite**: `INSERT OR IGNORE ... VALUES (?, ?, ?)` (sem RETURNING)
     + SELECT autoritativo
   - **PG (wrapper)**: `INSERT ... ON CONFLICT DO NOTHING ... RETURNING chave`
     + SELECT autoritativo (RETURNING chave permanece para evitar
     interceptação automática do wrapper)

**Resumo da rodada 3**: 3 aceitos, 0 adaptados, 0 rejeitados.
**Total acumulado das 3 rodadas**: 19 aceitos + 1 adaptado + 0 rejeitados.

### 5.6 Regressão fora da suíte-alvo (rodada 4 — CODEX rodou pytest amplo)

Com 43/43 verdes na suíte-alvo (rodadas 1-3), CODEX rodou pytest em
toda a árvore e encontrou 1 regressão crítica + 2 pontos menores.
Todos aceitos.

1. **[P1] Drift de schema model vs Alembic.**
   *Achado*: a 4B adicionou `instance_id` via Alembic em 10 tabelas,
   mas os models SQLAlchemy não foram alinhados. `registrar_outbox`
   agora sempre insere `instance_id`; em fixtures que usam
   `Base.metadata.create_all()` (que lê models, não Alembic), a
   coluna não existe → INSERT falha silenciosamente (try/except do
   outbox).
   *Reproduzido em*: `test_eventos_publicacao.py::TestRegistrarOutbox::test_insere_evento_corretamente`.
   *Fix (escopo conservador)*: alinhar 6 models — os que
   `registrar_evento_ledger` + `outbox` escrevem (`EventoPublicacao`
   + 5 ledger). Os 4 objetos sanitários principais (`Prescricao`,
   `PedidoExame`, `Laudo`, `Agendamento`) ficam para 4D.

2. **[P2] Lifespan toca DB real durante TestClient.**
   *Achado*: `with TestClient(app):` aciona lifespan, que abre
   `SessionLocal` global e chama `get_instance_id(session)` —
   tocando `data/pix_saude_pe.db` (não o tmp do teste).
   *Fix*: env override `PICSAUDE_INSTANCE_ID` em fixture
   session-scope autouse no conftest raiz → lifespan curto-circuita
   sem tocar DB.

3. **[P3] Docstring obsoleta** em `get_instance_id_conn` —
   atualização textual.

**Resumo da rodada 4**: 3 aceitos, 0 adaptados, 0 rejeitados.

### 5.7 Reescrita do P2 (rodada 5 — CODEX detectou bug no delta-2)

Antes do delta-2 ser executado, CODEX revisou o prompt e detectou
que o P2 da rodada 4, como escrito, quebraria o teste 15 da 4C.

1. **[P1 da rodada 5] Fixture autouse com `PICSAUDE_INSTANCE_ID`
   global quebra teste 15.**
   *Achado*: `get_instance_id_conn` curto-circuita SEMPRE quando o
   env override está setado. O teste 15
   (`test_get_instance_id_conn_funciona_com_pgconnection_wrapper`)
   espera capturar o `INSERT ... RETURNING chave` no fake PG. Sem
   INSERT, `assert len(insert_sqls) == 1` falha.
   *Fix*: substituir env override global por **lifespan injetável**:
   - Refatorar `app/main.py` extraindo `_lifespan_bootstrap()` como
     função module-level patchável.
   - Conftest raiz patcha `app.main._lifespan_bootstrap` para no-op
     em fixture autouse — neutraliza só o startup, sem tocar
     `PICSAUDE_INSTANCE_ID`.

2. **[P2 da rodada 5] Guard de prod em import-time bypassa
   fixture autouse.**
   *Achado*: `app/main.py:32` tem `if PICSAUDE_ENV == "prod" and
   _USE_SQLITE: raise RuntimeError(...)` em import-time. Fixtures
   autouse só executam após coleta — não pegam.
   *Fix*: `os.environ.setdefault("PICSAUDE_ENV", "test")` no
   top-level do `backend/conftest.py`, antes de qualquer import.

3. **[P3.1 da rodada 5] Exemplo de `EventoPublicacao` no delta-2
   estava desatualizado.**
   *Achado*: o model real tem `publicado_em` depois de `criado_em`.
   *Fix*: corrigir exemplo no prompt-delta — `instance_id` vai
   após `publicado_em`, não após `criado_em`.

4. **[P3.2 da rodada 5] Imports de `String` faltando em 3 arquivos.**
   *Achado*: `evento_publicacao.py`, `agendamento_evento.py`,
   `circulacao_diagnostica_evento.py` só importam `Text`. Adicionar
   `String` ao `from sqlalchemy import` de cada um antes de
   adicionar a coluna.
   *Fix*: instruções explícitas no prompt-delta-3.

5. **[P3.3 da rodada 5] Declarar classe `core` no prompt-delta.**
   *Achado*: AGENTS.md exige declaração de classe antes de
   implementação. Toca ledger + identidade + lifespan.
   *Fix*: cabeçalho do prompt-delta-3 declara `core`.

**Resumo da rodada 5**: 5 aceitos, 0 adaptados, 0 rejeitados.

**Total acumulado das 5 rodadas**: 27 aceitos + 1 adaptado + 0 rejeitados.

---

## 6. Bloqueadores não resolvidos por esta sub-tarefa

- **Drift de nomenclatura entre tabelas de eventos** — débito técnico
  pré-existente. Vira ticket separado (similar à Task #5 — drift
  `prestadores`). 4C convive com o drift via `_LEDGER_SCHEMA`.
- **Refatoração dos routers** para usar o helper — escopo da 4D.
- **Backfill de `instance_id` em registros pré-existentes** — escopo da
  **Etapa 8 (pré-deploy público)**, não da 4D.

---

## 7. Próximos passos (status do ciclo Regra 2)

| # | Passo | Status |
|---|---|---|
| 1 | Engenheiro-Chefe redige ticket | ✅ feito |
| 2 | Fabiano cola no CODEX | ✅ feito (2026-05-08) |
| 3 | Engenheiro-Chefe classifica feedback (aceito/adaptado/rejeitado) | ✅ feito (12+1+0 — §5) |
| 4 | Engenheiro-Chefe integra feedback ao ticket | ✅ feito (revisão atual) |
| 5 | **Fabiano aprova plano final** | ⏳ **próximo** |
| 6 | Claude Code implementa em ambiente local | ⏳ |
| 7 | Engenheiro-Chefe valida output (testes verdes, padrões, classe correta) | ⏳ |
| 8 | Commit + push canônico | ⏳ |
| 9 | (No fim da Etapa 4) Análise estática consolidada CODEX + Jules | ⏳ |

---

## 8. Referências

- `docs/PLANO-PRODUCAO-V2.md` §4 — sub-tarefas da Etapa 4
- `app/instance.py` — helper `get_instance_id(session)` (4A)
- `app/domain/outbox.py` — precedente arquitetural (`registrar_outbox`)
- `DATA-PROTECTION.md` §4.2 — motivação regulatória
- `CLAUDE.md` §10 — taxonomia de contribuição
- `workflow_pacto_desenvolvimento.md` (memória) — Regra 2 estrita
