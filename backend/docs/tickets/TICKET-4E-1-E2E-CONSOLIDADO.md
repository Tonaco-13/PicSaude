# TICKET 4E.1 — Testes E2E consolidados da Etapa 4

> **Sub-tarefa 4E.1 do plano de produção** (`docs/PLANO-PRODUCAO-V2.md` §4)
> **Classe (CLAUDE.md §10):** `module` — adiciona testes E2E novos; não altera código de produção
> **Pacto:** Regra 2 estrita (ticket → CODEX → Code → CODEX pós-impl)
> **Predecessores:** 4A `d8abf7e`, 4B `89f064a`, 4C `2fbcf43` + `983359f`, 4D.1 `60382d2` + `0056c93`, 4D.2 `3db4060` + `79f2f4f`, Task #8 `d2f016b`, OTP fix `5fa6902` + `a44582b`
> **Sucessora:** 4E.2 (Regra 5 — CODEX+Jules sobre diff acumulado)
> **Data:** 2026-05-13
> **Escopo:** 1 arquivo novo de teste (`tests/integration/test_4e_e2e_consolidado.py`), estimativa 200–300 linhas
> **Redigido por:** Arquiteto (rodada 0). Aguarda revisão CODEX (rodada 1).

---

## §1 Contexto e objetivo

A Etapa 4 entregou o `instance_id` canônico — marca d'água da instalação PicSaúde (UUID v4 inalterável, persistido em `meta_instalacao` + `.instance_id`, conforme `DATA-PROTECTION.md §4.2`). Os entregáveis foram:

| Sub-tarefa | Entrega | Commit |
|---|---|---|
| 4A | Helper `app/instance.py` | `d8abf7e` |
| 4B | Migration que adiciona `instance_id VARCHAR(36) NULL` em 10 tabelas (5 ledgers + 5 objetos principais) | `89f064a` |
| 4C | Helper `registrar_evento_ledger(..., instance_id=...)` em `app/domain/ledger.py` | `2fbcf43` + `983359f` |
| 4D.1 | 21 sites migrados em 7 routers (prescrição) | `60382d2` + `0056c93` |
| 4D.2 | 13 sites migrados em 4 routers (exame, laudo, agendamento, circulação) | `3db4060` + `79f2f4f` |

A cobertura de testes hoje:

| Arquivo | Cobertura |
|---|---|
| `tests/test_instance_id.py` | Helper `app/instance.py` em isolamento |
| `tests/test_migration_4b_instance_id.py` | Migration alembic em isolamento |
| `tests/test_ledger_helper.py` | Helper `registrar_evento_ledger` em isolamento |
| `tests/integration/test_4d1_instance_id_ledger.py` | Prescrição (ledger + outbox + transação) |
| `tests/integration/test_4d2_instance_id_ledger.py` | Exame, laudo, agendamento, circulação (ledger + outbox + transação) |

**Lacuna que a 4E.1 fecha:** cobertura **transversal entre subdomínios**. Os testes existentes validam invariantes **dentro** de cada objeto sanitário. Falta validar que numa cadeia clínica multi-objeto (ex: prescrição + pedido de exame + agendamento + laudo numa mesma sessão de paciente), o `instance_id` se comporta corretamente entre objetos — isto é, **todos os eventos da instância compartilham o mesmo `instance_id`**, e ledger/outbox permanecem coerentes.

---

## §2 Decisão sobre escopo

### §2.1 Não alterar código de produção

A 4E.1 toca **apenas `backend/tests/`**. Nenhuma alteração em `backend/app/`, `backend/alembic/`, ou `frontend/`. Mudanças em código de produção que surgirem do feedback CODEX rodada 1 (ex: lapidação P3 de `outbox.py` já identificada no briefing v2) entram na onda de lapidações da 4E.2, não aqui.

### §2.2 `instance_id` operacional em ledger/outbox, não em objetos principais

A migration 4B (`4b1ce80a017d`) adicionou `instance_id` em **10 tabelas** (corrigido em rodada 1 CODEX — ver §10):

- **6 tabelas de eventos/outbox** (ledgers + outbox): `prescricao_eventos`, `pedido_exame_eventos`, `laudo_eventos`, `agendamento_eventos`, `circulacao_diagnostica_eventos`, **`eventos_publicacao` (outbox)**
- **4 objetos principais**: `prescricoes`, `pedidos_exame`, `laudos`, `agendamentos`

Os 5 ledgers + outbox recebem preenchimento via helper desde a 4D.1/4D.2.

Os **4 objetos principais** (`Prescricao`, `PedidoExame`, `Laudo`, `Agendamento`) **ainda não mapeiam** `instance_id` nos models ORM nem o preenchem nos INSERTs de criação. Isso é dívida documentada da **Etapa 8** (pré-deploy público, junto com backfill de eventos antigos).

**Consequência para a 4E.1:** os cenários testam `instance_id` em rows de **ledger e outbox**, não em rows de objetos principais. Asserções que parecerem exigir `SELECT instance_id FROM prescricoes` (etc.) devem ser refatoradas para `SELECT instance_id FROM prescricao_eventos` (etc.).

**Atenção schema do outbox:** `eventos_publicacao` **não tem coluna `protocolo`**. O protocolo é armazenado em `objeto_id` (ver `app/domain/outbox.py:64` e `app/models/evento_publicacao.py:22`). Queries no outbox devem usar `WHERE objeto_tipo = %s AND objeto_id = %s`, nunca `WHERE protocolo = %s`. Correção da rodada 1 CODEX (P1.2).

### §2.3 Fora do escopo (lista negativa)

Não fazer:

- Refatorar `tests/integration/conftest.py`
- Criar fixtures globais novas (extensão de fixture local é OK)
- Cobrir tokens de apresentação ou dispensação além do mínimo do C2
- Cobrir Etapa 5+ (Fix B1, DEMO_MODE, Docker, deploy)
- Alterar payloads, schemas, vocabulário de eventos
- Adicionar migration ou alterar `models/`
- Testar `instance_id` em objetos principais (Etapa 8)

---

## §3 Semântica de `instance_id` (fundamento dos cenários)

> Esta seção é o contrato semântico que os testes devem validar. **Corrigida em rodada 1 do CODEX sobre o briefing v1** (ver §11) — `instance_id` é a **marca d'água da instalação**, não um ID de transação.

### §3.1 Contrato

```
instance_id ≡ UUID v4 inalterável que identifica univocamente uma instalação
              PicSaúde, gerado no primeiro boot, persistido em meta_instalacao
              (fonte de verdade) + .instance_id (espelho/cache).
```

Referências:

- `backend/app/instance.py` (linhas 1–38)
- `DATA-PROTECTION.md §4.2`
- `TICKET-4C-HELPER-LEDGER-INSTANCE-ID.md §1`

### §3.2 As cinco invariantes (I1–I5)

| # | Invariante | Como o sistema garante |
|---|---|---|
| **I1** | Todo evento novo em qualquer ledger da Etapa 4 tem `instance_id` UUID v4 **válido** (não nulo, não vazio, e formato UUID v4 — não apenas qualquer string) | `registrar_evento_ledger` recusa chamada sem o argumento (`TypeError` — keyword-only obrigatório sem default), E aplica `_validar_uuid_v4()` que rejeita string vazia, None e UUIDs malformados (ver `app/domain/ledger.py:167`) — 4C |
| **I2** | Em uma mesma instância PicSaúde, **todos** os eventos de **todas** as transações têm o **mesmo** `instance_id` | `app.instance.get_instance_id_conn(conn)` retorna o valor canônico estável (4A); a função forense do campo é identificar a instalação, não a transação |
| **I3** | Em uma transação clínica, ledger e outbox adjacente compartilham `instance_id` — **apenas nos subdomínios com outbox adjacente** (prescrição, pedido_exame, laudo, agendamento). Circulação diagnóstica **não tem outbox adjacente** na 4D.2 | Caller passa o mesmo valor a `registrar_evento_ledger` e `registrar_outbox` na mesma transação (4D.1/4D.2) |
| **I4** | Eventos múltiplos de uma mesma transação clínica compartilham o `instance_id` obtido nessa transação | Caller chama `get_instance_id_conn(conn)` uma vez e reutiliza (4D.1/4D.2) |
| **I5** | O outlier de schema em `agendamento_eventos` (coluna `evento`, `payload` em vez de `tipo_evento`, `dados_json`) preserva I1–I4 | `_LEDGER_SCHEMA` em `app/domain/ledger.py` encapsula o drift de naming (4C) |

### §3.3 Asserção fundamental

Em todo cenário da 4E.1 vale a fórmula:

```python
instance_id_canonico = get_instance_id_conn(conn)   # valor único da instância

# após qualquer cadeia clínica:
SELECT DISTINCT instance_id FROM <qualquer_ledger_da_etapa_4>
WHERE <evento gerado pelo teste>
→ retorna EXATAMENTE 1 linha
→ esse valor é igual a instance_id_canonico
→ esse valor é UUID v4 válido
```

---

## §4 Cenários propostos

### §4.1 C1 — Cadeia clínica completa em uma sessão de paciente

**Objetivo:** validar que objetos sanitários encadeados (prescrição → pedido de exame → agendamento → coleta → laudo) numa mesma sessão de paciente preservam I1–I5.

**Pré-condição:** fixture `client` + `outer_conn` + `seed_usuario` + `seed_paciente`, padrão dos testes 4D.

**Fluxo:**

1. `POST /prescricoes` com payload base (paciente X)
2. **Capturar `instance_id_canonico` lendo de `prescricao_eventos`** após a 1ª transação ter populado `meta_instalacao` (ver §5.3)
3. `POST /pedidos-exame` com mesmo paciente X (payload base de test_4d2)
4. `POST /agendamentos` vinculado ao pedido criado em (3)
5. Realizar o agendamento (transita itens do pedido para `coletado`)
6. `POST /laudos` para o paciente X com **`pedido_protocolo` apontando ao pedido criado em (3)** — garante cadeia real (correção P2.3 CODEX). Router laudos.py:100 suporta esse vínculo e grava `pedido_id`.
7. **Adicional pós-rodada 0.5 (absorção de C2):** ≥1 transação extra sobre o protocolo da prescrição criada em (1) — ex: `POST /prescricoes/{proto}/tokens/atomizar` com role paciente via `_override_role`, payload `{"validade_minutos": 60}` (confirmado pelo CODEX como suficiente para cobrir "múltiplas transações no mesmo protocolo")
8. Validar invariantes

**Invariantes verificadas:**

```python
# Após a 1ª transação (POST /prescricoes), capturar canônico:
instance_id_canonico = _instance_id_canonico_apos_primeira_transacao(outer_conn)
assert _eh_uuid_v4(instance_id_canonico)   # I1 forte (formato UUID v4)

# ... resto da cadeia ...

# I1 + I2: todos os ledgers tocados têm exatamente um instance_id distinto
# e ele é igual ao instance_id_canonico
for tabela in [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "agendamento_eventos",
    "laudo_eventos",
]:
    cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == instance_id_canonico

# I3: ledger e outbox compartilham instance_id — USAR objeto_id, NÃO protocolo
# (correção P1.2 CODEX — eventos_publicacao não tem coluna protocolo)
for objeto_tipo, objeto_id in [
    ("prescricao",   proto_prescricao),
    ("pedido_exame", proto_pedido),
    ("agendamento",  proto_agendamento),
    ("laudo",        proto_laudo),
]:
    cur.execute(
        """
        SELECT instance_id
          FROM eventos_publicacao
         WHERE objeto_tipo = %s AND objeto_id = %s
        """,
        (objeto_tipo, objeto_id),
    )
    for (instance_id_outbox,) in cur.fetchall():
        assert instance_id_outbox == instance_id_canonico

# Coerência clínica adicional:
# - protocolo da prescrição != protocolo do pedido != protocolo do laudo
# - paciente CPF é o mesmo em todos
# - laudo.pedido_id aponta ao pedido criado em (3) — cadeia real
```

**Tamanho estimado:** ~60 linhas (subiu de 50 por absorção de C2 + asserções de objeto_id).

### §4.2 C2 — Múltiplas transações no mesmo objeto

**Decisão Arquiteto pós rodada 0.5 (Code):** C2 é **degenerado por construção** dada I2 (igualdade universal de `instance_id` entre transações de uma mesma instância). O cenário fica **absorvido em C1** — em vez de criar um cenário separado, o C1 já valida múltiplas transações ao executar prescrição → pedido → agendamento → coleta → laudo (5 transações). Para cobrir adicionalmente "múltiplas transações no mesmo protocolo da prescrição", basta encadear no C1 uma 2ª transação sobre o protocolo da prescrição criada (transferência de custódia ou dispensação parcial).

**Não implementar C2 como função separada.** Adicionar 2–3 asserções extras dentro de C1 para cobrir "mesmo protocolo, ≥2 transações, ainda I2".

**Tamanho:** absorvido (0 linhas extras — C1 cresce ~10 linhas).

### §4.3 C3 — Cadeia diagnóstica (pedido → agendamento → coleta → laudo)

**Objetivo:** validar I5 explicitamente — o outlier `agendamento_eventos.evento`/`payload` continua transparente, e a cadeia diagnóstica completa preserva I1–I4.

**Pré-condição:** idem C1.

**Fluxo:**

1. `POST /pedidos-exame`
2. **Capturar `instance_id_canonico`** após (1) ter populado `meta_instalacao` (ver §5.3)
3. `POST /agendamentos` vinculado ao pedido
4. Realizar agendamento → itens do pedido transitam `agendado → coletado`
5. `POST /laudos` com **`pedido_protocolo` apontando ao pedido criado em (1)** (correção P2.3 CODEX — `laudos.py:100` grava `pedido_id` quando informado)

**Invariantes verificadas:**

```python
# I1 + I2: validar especificamente que agendamento_eventos.instance_id
# carrega o valor correto APESAR do outlier de naming (coluna `evento`)
cur.execute(
    """
    SELECT evento, instance_id
      FROM agendamento_eventos
     WHERE agendamento_id = %s
    """,
    (agendamento_id,),
)
for evento, instance_id in cur.fetchall():
    assert evento in {"agendamento_criado", "agendamento_realizado"}
    assert instance_id == instance_id_canonico
    assert _eh_uuid_v4(instance_id)   # I1 — UUID v4 válido

# I5: o JOIN entre as 3 tabelas (pedido, agendamento, laudo) preserva
# o mesmo instance_id em todos os rows de evento.

# Coerência clínica: laudo.pedido_id aponta ao pedido (cadeia real)
cur.execute("SELECT pedido_id FROM laudos WHERE protocolo = %s", (proto_laudo,))
assert cur.fetchone()[0] == pedido_id
```

**Tamanho estimado:** ~45 linhas.

### §4.4 C4 — Remarcação derivada preserva invariantes

**Objetivo:** validar que objeto derivado (via remarcação) carrega o `instance_id` correto, e que os eventos no ledger antigo + ledger do derivado compartilham o invariante.

**Pré-condição:** idem C1.

**Fluxo:**

1. `POST /agendamentos` (cria agendamento_original)
2. **Capturar `instance_id_canonico`** após (1)
3. `POST /agendamentos/{protocolo}/remarcar` com payload `{"data_hora": "2026-05-25T14:00:00"}` — resposta retorna `protocolo_novo` (endpoint confirmado pelo CODEX rodada 1; padrão idêntico ao usado em `test_4d2:465`)

**Invariantes verificadas:**

```python
# I1 + I2: todos os eventos gerados (do original + da remarcação) têm o
# mesmo instance_id = instance_id_canonico, com formato UUID v4 válido
cur.execute(
    """
    SELECT DISTINCT instance_id
      FROM agendamento_eventos
     WHERE agendamento_id IN (%s, %s)
    """,
    (agendamento_original_id, agendamento_derivado_id),
)
rows = cur.fetchall()
assert len(rows) == 1
assert rows[0][0] == instance_id_canonico
assert _eh_uuid_v4(rows[0][0])

# Coerência clínica (asserção robusta — correção P3.2 CODEX):
# - origem_agendamento_id do derivado aponta para o original
# - os eventos esperados da remarcação estão presentes
cur.execute(
    "SELECT origem_agendamento_id FROM agendamentos WHERE id = %s",
    (agendamento_derivado_id,),
)
assert cur.fetchone()[0] == agendamento_original_id

cur.execute(
    """
    SELECT evento FROM agendamento_eventos
     WHERE agendamento_id IN (%s, %s)
     ORDER BY criado_em
    """,
    (agendamento_original_id, agendamento_derivado_id),
)
eventos = [r[0] for r in cur.fetchall()]
assert "agendamento_criado" in eventos
assert "agendamento_remarcado" in eventos or "agendamento_cancelado" in eventos
# (vocabulário exato verificado contra agendamentos.py:506-537)
```

**Tamanho estimado:** ~40 linhas.

### §4.5 C5 — Smoke test agregado (invariante de instância única)

**Objetivo:** o cenário **mais forte** do conjunto — validar I1 + I2 simultaneamente sobre os 5 ledgers da Etapa 4 numa única asserção.

**Pré-condição:** idem C1.

**Fluxo:**

1. `POST /prescricoes` (1ª transação — popula `meta_instalacao` se vazio)
2. **Capturar `instance_id_canonico`** após (1)
3. `POST /pedidos-exame` (pedido_A — vai virar agendamento)
4. **`POST /pedidos-exame` (pedido_B — separado, item permanece `pendente` para a circulação)** — correção P2.2 CODEX. Razão: `POST /agendamentos` move itens do pedido_A para `agendado`, mas `POST /pedidos-exame/{proto}/circulacao` exige item `pendente` (ver `circulacao_diagnostica.py:250`).
5. `POST /agendamentos` vinculado ao **pedido_A**
6. `POST /laudos`
7. `POST /pedidos-exame/{proto_pedido_B}/circulacao` (cria circulação diagnóstica sobre pedido_B com item `pendente`)
8. Validar invariante crítica

**Invariante crítica:**

```sql
SELECT COUNT(DISTINCT instance_id) FROM (
    SELECT instance_id FROM prescricao_eventos
    UNION ALL
    SELECT instance_id FROM pedido_exame_eventos
    UNION ALL
    SELECT instance_id FROM laudo_eventos
    UNION ALL
    SELECT instance_id FROM agendamento_eventos
    UNION ALL
    SELECT instance_id FROM circulacao_diagnostica_eventos
) AS uniao;
-- Esperado: 1
```

```python
# I1 universal: nenhum row de evento tem instance_id IS NULL
for tabela in [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "agendamento_eventos",
    "circulacao_diagnostica_eventos",
]:
    cur.execute(f"SELECT COUNT(*) FROM {tabela} WHERE instance_id IS NULL")
    assert cur.fetchone()[0] == 0

# I2 + asserção contra valor canônico
cur.execute("""
    SELECT DISTINCT instance_id FROM (
        SELECT instance_id FROM prescricao_eventos
        UNION ALL
        SELECT instance_id FROM pedido_exame_eventos
        UNION ALL
        SELECT instance_id FROM laudo_eventos
        UNION ALL
        SELECT instance_id FROM agendamento_eventos
        UNION ALL
        SELECT instance_id FROM circulacao_diagnostica_eventos
    ) AS uniao
""")
rows = cur.fetchall()
assert len(rows) == 1
assert rows[0][0] == instance_id_canonico
assert _eh_uuid_v4(rows[0][0])
```

**Nota sobre isolamento de teste (confirmada em rodada 0.5 Code):** o conftest da `tests/integration/` (linhas 1–35) é explícito: cada teste vive numa outer tx aberta sobre `outer_conn`, com SAVEPOINT por request via TestClient; teardown faz `outer_conn.rollback()`, descartando tudo (inclusive seeds). **Consequência:** dentro do escopo de UM teste, `SELECT FROM <ledger>` via `outer_conn` retorna exatamente os rows que esse teste plantou. **Não é necessário filtro `criado_em > t0`.** Os rows de outros testes não vazam porque cada teste começa com `outer_conn` numa outer tx nova.

**Tamanho estimado:** ~45 linhas.

### §4.5b C5b — Override `PICSAUDE_INSTANCE_ID` em dev (OBRIGATÓRIO — confirmado CODEX rodada 1)

**Objetivo:** validar I2 contra um valor **constante conhecido** em vez de depender do `instance_id` real da instância de teste. Forma mais robusta de testar o invariante porque a asserção compara contra uma string explícita.

**Decisão CODEX rodada 1:** cenário **separado obrigatório** (não asserção extra no C5), porque o override altera a fonte efetiva do valor — usar o mesmo mecanismo no C5 padrão e no override misturaria contratos diferentes na mesma função de teste.

**Pré-condição:** `monkeypatch.setenv("PICSAUDE_ENV", "dev")` + `monkeypatch.setenv("PICSAUDE_INSTANCE_ID", "<UUID v4 conhecido>")` antes dos requests.

**Importante — não ler `meta_instalacao` neste cenário:** o override por env **não toca o DB** (contrato testado em `test_ledger_helper.py:674`). A comparação é direta contra o UUID forçado conhecido pelo teste.

**Fluxo:**

1. Forçar `instance_id` via env com UUID v4 conhecido
2. Executar 3 a 5 fluxos curtos que toquem ledgers distintos (ex: prescrição, pedido_exame, laudo)
3. Validar que todos os `*_eventos.instance_id` são iguais ao valor forçado — sem leitura de `meta_instalacao`

**Invariante verificada:**

```python
INSTANCE_ID_FORCADO = "deadbeef-dead-4eef-beef-deadbeefcafe"

monkeypatch.setenv("PICSAUDE_ENV", "dev")
monkeypatch.setenv("PICSAUDE_INSTANCE_ID", INSTANCE_ID_FORCADO)

# ... 3-5 fluxos curtos ...

# Comparar DIRETO contra o UUID forçado, NÃO contra meta_instalacao
for tabela in [
    "prescricao_eventos", "pedido_exame_eventos", "laudo_eventos",
]:
    cur.execute(f"SELECT DISTINCT instance_id FROM {tabela}")
    rows = cur.fetchall()
    if rows:
        assert rows[0][0] == INSTANCE_ID_FORCADO
        assert _eh_uuid_v4(rows[0][0])
```

**Atenção:** `app/instance.py:25-27` — override é respeitado APENAS se `PICSAUDE_ENV != "prod"`. `monkeypatch` tem escopo de função, então não interfere com outros testes.

**Tamanho estimado:** ~30 linhas (subiu de 25 — implementação curta e explícita, 3 a 5 fluxos como o CODEX sugeriu).

### §4.6 C6 — Coerência ledger+outbox em cadeia multi-objeto (OPCIONAL — CODEX rodada 1)

**Decisão CODEX rodada 1:** C6 fica **opcional**. C1 + testes 4D já cobrem I3 suficientemente. Se entrar, limitar a `prescricao`, `pedido_exame`, `laudo`, `agendamento` — **não esperar outbox de circulação** (subdomínio circulação não tem outbox adjacente; ver I3 refinada em §3.2).

**Objetivo (caso entre):** validar I3 explicitamente em cadeia transversal — coerência `instance_id` entre cada ledger e o outbox correspondente, usando o schema correto do outbox (`objeto_id`, não `protocolo` — correção P1.2).

**Pré-condição:** idem C1.

**Fluxo:**

1. Cadeia: prescrição → pedido_exame → laudo → agendamento (4 objetos com outbox)
2. Capturar `instance_id_canonico` após a 1ª transação
3. Para cada `eventos_publicacao` gerado dos 4 `objeto_tipo`, validar que o `instance_id` é igual ao do `*_eventos` correspondente

**Invariante verificada:**

```python
TABELA_LEDGER_POR_TIPO = {
    "prescricao":   "prescricao_eventos",
    "pedido_exame": "pedido_exame_eventos",
    "laudo":        "laudo_eventos",
    "agendamento":  "agendamento_eventos",
    # circulacao_diagnostica NÃO entra — sem outbox adjacente
}

cur.execute(
    """
    SELECT objeto_tipo, objeto_id, instance_id
      FROM eventos_publicacao
     WHERE objeto_tipo IN ('prescricao', 'pedido_exame', 'laudo', 'agendamento')
    """
)
for objeto_tipo, objeto_id, instance_id_outbox in cur.fetchall():
    tabela_ledger = TABELA_LEDGER_POR_TIPO[objeto_tipo]
    cur.execute(
        f"SELECT DISTINCT instance_id FROM {tabela_ledger} "
        f"WHERE protocolo = %s",
        (objeto_id,),  # objeto_id no outbox = protocolo no ledger
    )
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == instance_id_outbox == instance_id_canonico
```

**Tamanho estimado:** ~30 linhas.

---

## §5 Regra de implementação

### §5.1 Arquivo único

Criar **um único arquivo**:

```
backend/tests/integration/test_4e_e2e_consolidado.py
```

Estrutura interna sugerida:

```python
"""
tests/integration/test_4e_e2e_consolidado.py
============================================

Sub-tarefa 4E.1 — testes E2E consolidados da Etapa 4 (instance_id canônico).

Valida 5 invariantes do contrato instance_id (I1-I5) sobre cadeias
clínicas multi-objeto que atravessam os 5 subdomínios tocados na Etapa 4
(prescrição, pedido_exame, laudo, agendamento, circulação diagnóstica).

Referências:
  - app/instance.py            — contrato semântico do instance_id
  - app/domain/ledger.py       — helper registrar_evento_ledger
  - DATA-PROTECTION.md §4.2    — marca d'água da instalação
  - TICKET-4E-1-E2E-CONSOLIDADO.md — spec deste arquivo
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.instance import get_instance_id_conn
from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)

# ... payloads compartilhados, helpers, e 5–6 funções test_*
```

### §5.2 Reutilizar primitives existentes

- **Payloads canônicos:** importar/copiar de `tests/integration/test_4d2_instance_id_ledger.py` (`_PAYLOAD_PEDIDO`, `_PAYLOAD_LAUDO`) e `tests/integration/test_4d1_instance_id_ledger.py` (`_PAYLOAD_BASE` para prescrição). Se forem idênticos, considerar consolidar em local helper *neste* arquivo — não tocar test_4d1/test_4d2.
- **Helpers:** `_headers(token)`, `_eh_uuid_v4(s)` — copiar localmente. Clareza > DRY em testes.
- **Override de role:** se precisar de role diferente do prescritor (ex: paciente, dispensador), copiar `_override_role(...)` do test_4d2 — não importar entre arquivos de teste.
- **Fixtures:** `client`, `outer_conn`, `seed_usuario`, `seed_paciente` — vêm do `conftest.py`. Não criar fixtures globais novas.

### §5.3 Como obter `instance_id_canonico` no teste (corrigido em rodada 1 CODEX — P1.1)

**Problema descoberto na rodada 1:** o `backend/conftest.py:37` desliga `_lifespan_bootstrap`, e o bootstrap em `app/main.py:75` é justamente quem preencheria `meta_instalacao` no startup. Portanto, **antes da primeira transação clínica, `meta_instalacao.instance_id` pode não existir** — minha proposta da rodada 0.5 de ler antes dos requests teria falhado.

**Decisão Arquiteto:** adotar **estratégia "ler após primeira transação clínica"** (opção B do CODEX). O helper `get_instance_id` é chamado dentro de `registrar_evento_ledger` na primeira transação que grava ledger, e nesse momento popula `meta_instalacao` se vazio. Depois disso, leitura é segura.

```python
def _instance_id_canonico_apos_primeira_transacao(outer_conn) -> str:
    """Retorna o instance_id_canonico, lido após a primeira transação clínica
    ter populado meta_instalacao via get_instance_id().

    USAR APENAS APÓS o primeiro POST que grava em qualquer *_eventos.
    Em test_4e_e2e_consolidado, isso significa: executar pelo menos uma
    cadeia (ex: POST /prescricoes) e DEPOIS chamar este helper para
    capturar o valor canônico que servirá de referência das asserções.
    """
    cur = outer_conn.cursor()
    cur.execute(
        "SELECT valor FROM meta_instalacao WHERE chave = 'instance_id'"
    )
    row = cur.fetchone()
    assert row is not None, (
        "meta_instalacao.instance_id ausente — esperado preenchido pela "
        "primeira chamada a registrar_evento_ledger. Confirmar que o "
        "POST anterior grava em algum *_eventos."
    )
    return row[0]
```

**Alternativa equivalente:** ler de qualquer `*_eventos` recém-criado:

```python
cur.execute(
    "SELECT instance_id FROM prescricao_eventos "
    "WHERE protocolo = %s LIMIT 1",
    (proto_primeira_prescricao,),
)
instance_id_canonico = cur.fetchone()[0]
```

Ambas dão o mesmo valor (por I2). Usar a forma que for mais clara no contexto do cenário.

**Exceção — C5b:** o cenário do override `PICSAUDE_INSTANCE_ID` **não lê `meta_instalacao`**. O override por env não toca o DB (contrato já testado em `test_ledger_helper.py:674`). A comparação é direta contra o UUID forçado conhecido pelo teste.

**Referência canônica do helper:** teste #15 da 4C (`test_get_instance_id_conn_funciona_com_pgconnection_wrapper`) — não precisamos repetir aqui.

### §5.4 Decisões fechadas

- **Sem refactor**: extensão de fixture ou helper local OK, refactor de conftest NÃO
- **Sem fixtures globais novas**
- **Sem import de testes legados** (cada teste é autocontido)
- **Sem alteração de payloads/schemas/vocabulário**
- **Sem cobertura de objetos principais (instance_id em prescricoes/pedidos_exame/etc.)** — Etapa 8

### §5.5 Estimativa de tamanho (atualizada rodada 1 CODEX)

- C1 (absorvendo C2 com atomização mínima): ~60 linhas
- C3: ~45 linhas
- C4: ~40 linhas
- C5 (com pedido_B separado para circulação): ~50 linhas
- **C5b OBRIGATÓRIO** (override env, 3–5 fluxos curtos): ~30 linhas
- C6 (opcional, sem outbox de circulação): ~30 linhas
- Boilerplate (imports, docstring, helpers `_instance_id_canonico_apos_primeira_transacao`, `_headers`, `_eh_uuid_v4`, `_override_role`): ~35 linhas

**Total estimado:** 260–310 linhas (sem C6); até 340 linhas com C6.

---

## §6 Critérios de aceitação e verificação automatizada

### §6.1 Geral (atualizada rodada 1 CODEX)

- Novo arquivo `backend/tests/integration/test_4e_e2e_consolidado.py` criado
- **Cenários obrigatórios (final pós rodada 1 CODEX):** C1 (absorvendo C2 com atomização mínima), C3, C4, C5, **C5b**
- **Cenário opcional:** C6 (coerência ledger+outbox, sem outbox de circulação)
- Cada cenário verifica explicitamente as invariantes aplicáveis de I1–I5:
  - C1/C3/C4/C5/C6: capturar `instance_id_canonico` lendo de qualquer `*_eventos` **após a 1ª transação clínica** (ver §5.3)
  - C5b: comparar contra UUID forçado conhecido pelo teste, sem ler `meta_instalacao`
- Outbox queries usam `eventos_publicacao.objeto_id` (não `protocolo`)
- Docstring do módulo cita o contrato semântico (referência a `app/instance.py` + DATA-PROTECTION.md §4.2 + este ticket)
- Nenhum arquivo em `backend/app/` modificado
- Commit em PT-BR seguindo padrão convencional (`test:`)

### §6.2 Verificação automatizada obrigatória

```bash
cd backend

# 1. Confirmar que nenhum INSERT manual em *_eventos foi reintroduzido
for tab in prescricao_eventos pedido_exame_eventos laudo_eventos \
           agendamento_eventos circulacao_diagnostica_eventos; do
  grep -RInI --include='*.py' --exclude-dir='__pycache__' \
    "INSERT INTO $tab" app/routers/
done
# Esperado: zero matches

# 2. Confirmar que o novo arquivo existe e tem cenários nomeados
test -f tests/integration/test_4e_e2e_consolidado.py
grep -E "^def test_(cadeia_clinica|cadeia_diagnostica|remarcacao|smoke_agregado|override_instance_id_env|ledger_outbox_multiobjeto)" \
     tests/integration/test_4e_e2e_consolidado.py
# C1, C3, C4, C5, C5b são obrigatórios — devem aparecer. C6 é opcional.

# 2b. Confirmar que nenhuma query no novo arquivo usa coluna errada do outbox
# (correção P1.2 CODEX: eventos_publicacao não tem coluna `protocolo`)
grep -E "FROM eventos_publicacao.*WHERE.*protocolo" \
     tests/integration/test_4e_e2e_consolidado.py
# Esperado: zero matches. Queries no outbox devem usar objeto_id.

# 3. Rodar o regression suite completo da Etapa 4
python3 -m pytest \
    tests/test_instance_id.py \
    tests/test_migration_4b_instance_id.py \
    tests/test_ledger_helper.py \
    tests/integration/test_4d1_instance_id_ledger.py \
    tests/integration/test_4d2_instance_id_ledger.py \
    tests/integration/test_4e_e2e_consolidado.py \
    -v
# Esperado: todos verdes
```

### §6.3 Asserções mínimas por cenário

Cada cenário **deve** ter pelo menos:

- 1 asserção de I1 (UUID v4 presente, não nulo)
- 1 asserção de I2 (igualdade entre subdomínios e/ou contra `instance_id_canonico`)
- 1 asserção clínica de coerência (CPF/protocolo correto, transição de estado válida, etc.) — para garantir que o teste exerce realmente o fluxo, não só o invariante

---

## §7 Testes obrigatórios (regressões)

Após implementar a 4E.1, rodar regressões consolidadas:

```bash
cd backend

# Testes da Etapa 4 (5 + 1 da 4E.1)
python3 -m pytest tests/test_instance_id.py
python3 -m pytest tests/test_migration_4b_instance_id.py
python3 -m pytest tests/test_ledger_helper.py
python3 -m pytest tests/integration/test_4d1_instance_id_ledger.py
python3 -m pytest tests/integration/test_4d2_instance_id_ledger.py
python3 -m pytest tests/integration/test_4e_e2e_consolidado.py

# Regressões em routers tocados pela Etapa 4
python3 -m pytest tests/test_eventos_publicacao.py
python3 -m pytest tests/test_agendamentos.py
python3 -m pytest tests/test_circulacao_diagnostica.py
python3 -m pytest tests/test_circulacao_ticket54.py
python3 -m pytest tests/integration/test_prescricoes.py
python3 -m pytest tests/test_atomizacao.py
python3 -m pytest tests/test_dispensacao_atomizada.py
python3 -m pytest tests/test_dispensacao_hospitalar.py

# Smoke geral
python3 -m pytest
```

**Esperado:** todos verdes.

---

## §8 Perguntas abertas — todas respondidas pela CODEX rodada 1

> Status pós rodada 1: **zero perguntas abertas**. Resumo das respostas integradas:

| # | Pergunta | Resposta CODEX | Onde foi aplicada |
|---|---|---|---|
| 1 | I1–I5 capturam o contrato corretamente? | ✅ Sim, com 2 ajustes: I1 inclui validação UUID inválido via `_validar_uuid_v4`; I3 vale só para subdomínios com outbox adjacente (circulação fora) | §3.2 — refinado |
| 2 | C1+C3+C4+C5 cobrem "E2E consolidado"? | ✅ Sim, após correções P1/P2 aplicadas | §4.1, §4.3, §4.4, §4.5 |
| 3 | C5b obrigatório separado, asserção extra, ou opcional? | ✅ **Cenário separado obrigatório** — override altera fonte efetiva do valor | §4.5b — promovido a obrigatório |
| 4 | C6 obrigatório ou opcional? | ✅ **Opcional** — C1 + 4D já cobrem I3. Se entrar, sem outbox de circulação | §4.6 — opcional |
| 5 | Atomização: payload e role corretos? | ✅ `POST /prescricoes/{proto}/tokens/atomizar` com role `paciente` via `_override_role`, payload `{"validade_minutos": 60}`. Não precisa fluxo completo dispensação | §4.1 passo 7 |
| 6 | Endpoint de remarcação correto? | ✅ `POST /agendamentos/{protocolo}/remarcar`, payload `{"data_hora": "2026-05-25T14:00:00"}`, retorno `protocolo_novo`. Padrão de `test_4d2:465` | §4.4 |
| 7 | Cobrir dispensação atomizada completa ou remarcação de circulação? | ✅ **Não obrigatório** — 4D.1/4D.2 já cobrem. Bastam atomização mínima no C1 e criação de circulação no C5 | §6 fora do escopo |
| 8 | Estimativa de tamanho recalibrada? | ✅ 260–310 linhas sem C6; até 340 com C6 | §5.5 — atualizada |

**Não há perguntas abertas. Próximo passo: Arquiteto redige `TICKET-4E-1-PROMPT-CODE.md` (se CODEX rodada 2 não pedir nada material) ou rodada 2 do ticket se houver achados P1 novos.**

---

## §9 Prompt sugerido para implementação (Code) — atualizado rodada 1 CODEX

```markdown
Implementar TICKET-4E-1-E2E-CONSOLIDADO.md (rodada 1 CODEX integrada).
Classificação: module (testes E2E). Regra 2 estrita.

Escopo OBRIGATÓRIO:
- criar backend/tests/integration/test_4e_e2e_consolidado.py
- implementar cenários C1, C3, C4, C5, C5b (5 obrigatórios)
- C6 OPCIONAL — só implementar se sobrar tempo após os 5 verdes

Contratos críticos da rodada 1:
- instance_id é marca d'água da INSTALAÇÃO, não da transação (§3)
- meta_instalacao NÃO está populado antes da 1ª transação clínica
  (lifespan desligado em conftest.py:37). Por isso C1/C3/C4/C5/C6
  capturam instance_id_canonico DEPOIS do 1º POST que grava ledger
  (helper _instance_id_canonico_apos_primeira_transacao do §5.3,
  ou leitura direta de qualquer *_eventos recém-criado)
- C5b é EXCEÇÃO: usa monkeypatch.setenv("PICSAUDE_INSTANCE_ID", ...)
  e compara contra UUID forçado, SEM ler meta_instalacao
- eventos_publicacao NÃO tem coluna `protocolo` — usar
  `WHERE objeto_tipo = ... AND objeto_id = ...`
- C5 precisa de DOIS pedidos de exame: pedido_A (vira agendamento),
  pedido_B (item permanece pendente para circulação)
- C1/C3: laudo deve usar `pedido_protocolo` para encadear de verdade

Reutilizar payloads e helpers de tests/integration/test_4d2_*.py
(cópia local, não import cruzado). Não criar fixtures globais; usar
client, outer_conn, seed_usuario, seed_paciente do conftest existente.
NÃO TOCAR app/, alembic/, frontend/.

Procedimento:

0. (Pré-implementação) Rodar verificação automatizada §6.2.1 e §6.2.2:
   - zero INSERT manual em *_eventos nos routers
   - arquivo test_4e_e2e_consolidado.py NÃO existe ainda

1. Criar arquivo com docstring de módulo conforme §5.1, citando
   contrato semântico, referências, e a estratégia "capturar
   instance_id_canonico após 1ª transação".

2. Implementar helpers locais:
   - _headers, _eh_uuid_v4 (cópia de test_4d2)
   - _instance_id_canonico_apos_primeira_transacao(outer_conn) (§5.3)
   - _override_role (cópia de test_4d2 — necessário para C1
     atomização e potencialmente C5/C5b)
   - payloads canônicos copiados

3. Implementar cenários na ordem:
   3.a  C1 (cadeia clínica completa + atomização do mesmo protocolo)
        - 1º POST: /prescricoes
        - capturar instance_id_canonico
        - POST /pedidos-exame (com mesmo CPF)
        - POST /agendamentos vinculado ao pedido
        - PATCH /agendamentos/{proto}/realizar (ou endpoint equivalente
          que move item para coletado — verificar contra agendamentos.py)
        - POST /laudos com pedido_protocolo apontando ao pedido
        - POST /prescricoes/{proto_prescricao}/tokens/atomizar
          com _override_role("paciente") e payload {"validade_minutos": 60}
        - asserir I1, I2, I3 nos 4 ledgers + outbox com objeto_id
        - rodar pytest do arquivo

   3.b  C3 (cadeia diagnóstica)
        - 1º POST: /pedidos-exame
        - capturar instance_id_canonico
        - POST /agendamentos vinculado
        - PATCH /agendamentos/{proto}/realizar
        - POST /laudos com pedido_protocolo apontando ao pedido
        - asserir I1, I2, I5 (outlier agendamento_eventos.evento)
        - validar laudo.pedido_id aponta ao pedido
        - rodar pytest

   3.c  C5 (smoke agregado com 2 pedidos)
        - 1º POST: /prescricoes
        - capturar instance_id_canonico
        - POST /pedidos-exame (pedido_A — para agendamento)
        - POST /pedidos-exame (pedido_B — para circulação, item fica pendente)
        - POST /agendamentos vinculado ao pedido_A
        - POST /laudos
        - POST /pedidos-exame/{proto_pedido_B}/circulacao
        - asserir SELECT DISTINCT instance_id sobre UNION dos 5 ledgers
          retorna 1 valor = instance_id_canonico
        - asserir UUID v4 válido
        - asserir COUNT(*) WHERE instance_id IS NULL = 0 em cada ledger
        - rodar pytest

   3.d  C4 (remarcação derivada)
        - 1º POST: /agendamentos
        - capturar instance_id_canonico
        - POST /agendamentos/{protocolo}/remarcar com
          payload {"data_hora": "2026-05-25T14:00:00"}
        - asserir I1, I2 no agendamento_eventos para ambos os IDs
        - asserir origem_agendamento_id do derivado = id do original
        - asserir vocabulário de eventos esperado
          (agendamento_criado + agendamento_remarcado/cancelado)
        - NÃO usar criado_em < 1s como asserção primária
        - rodar pytest

   3.e  C5b (override PICSAUDE_INSTANCE_ID — OBRIGATÓRIO)
        - INSTANCE_ID_FORCADO = "deadbeef-dead-4eef-beef-deadbeefcafe"
        - monkeypatch.setenv("PICSAUDE_ENV", "dev")
        - monkeypatch.setenv("PICSAUDE_INSTANCE_ID", INSTANCE_ID_FORCADO)
        - executar 3 a 5 fluxos curtos: prescrição + pedido_exame + laudo
        - asserir TODOS os *_eventos tocados têm instance_id = INSTANCE_ID_FORCADO
        - NÃO ler meta_instalacao (override não toca DB)
        - rodar pytest

   3.f  (OPCIONAL) C6 (coerência ledger+outbox em 4 objetos)
        - 1º POST: /prescricoes
        - capturar instance_id_canonico
        - executar cadeia transversal: prescrição + pedido + laudo + agendamento
        - para cada row em eventos_publicacao com objeto_tipo in
          {prescricao, pedido_exame, laudo, agendamento}, asserir
          que instance_id é igual ao do *_eventos correspondente
          (JOIN com objeto_id = ledger.protocolo)
        - NÃO incluir circulacao_diagnostica (sem outbox adjacente)

4. Rodar regression suite §7 e verificar que tudo está verde.

5. NÃO COMITAR antes de revisão do Arquiteto.

Não fazer:
- refactor de conftest;
- fixtures globais novas;
- alteração de payloads, schemas, vocabulário;
- alteração em backend/app/ ou backend/alembic/;
- cobertura de instance_id em objetos principais (Etapa 8);
- ler meta_instalacao em C5b (override não toca DB);
- usar coluna `protocolo` em queries de eventos_publicacao
  (não existe — usar objeto_tipo + objeto_id).
```

---

## §10 Adições Arquiteto (rodada 0.5 — Code, integrada em 2026-05-13)

Antes do CODEX revisar a rodada 0, o Code (sessão VS Code) leu o ticket completo e devolveu 4 observações como input pré-CODEX ("rodada 0.5"). Arquiteto integrou:

| # | Observação Code (rodada 0.5) | Decisão Arquiteto | Onde aplicado |
|---|---|---|---|
| 1 | §4.5 (C5) — hipótese sobre `outer_conn` sem filtro `criado_em > t0` precisa validação contra `tests/integration/conftest.py:1-35` | 🔄 **Adaptado.** Arquiteto leu o conftest (linhas 1–35 explicam a arquitetura SAVEPOINT por request + rollback no teardown) e confirmou a hipótese. Nota refinada com referência explícita à arquitetura de isolamento. | §4.5 — nota substituída |
| 2 | §5.3 — `get_instance_id_conn(outer_conn)` com raw psycopg2: teste #15 da 4C já cobre via mock | ✅ **Aceito + adaptado.** Em vez de exercitar o helper na fixture de integração (que tem caminho de INSERT first-boot e pode interferir com outer tx), ler direto de `meta_instalacao` via `outer_conn`. Mais robusto. Teste #15 da 4C continua sendo a referência canônica para o helper. | §5.3 — implementação trocada |
| 3 | §4.2 (C2) — degenerado com I2 universal; recomenda descartar e absorver "múltiplas transações" dentro de C1 | ✅ **Aceito integralmente.** C2 absorvido. C1 ganha 2–3 asserções para cobrir múltiplas transações no mesmo protocolo. | §4.2 — cenário removido como função separada |
| 4 | §8 pergunta 8 — override `PICSAUDE_INSTANCE_ID` em dev é mais robusto que depender do valor real | ✅ **Aceito + promovido.** Elevado de pergunta para cenário C5b com proposta concreta de implementação. CODEX decide na rodada 1 se C5b é obrigatório, asserção extra no C5, ou opcional. | §4.5b — novo sub-cenário; §8 pergunta 3 |

**Resultado:** ticket passou de rodada 0 para rodada 0.5. As 4 observações do Code resolveram 4 das 10 perguntas originais ao CODEX. Restam **8 perguntas abertas** em §8 — todas respondidas posteriormente pela rodada 1 CODEX.

### §10.2 Rodada 1 CODEX (2026-05-13 ~15h, integrada em 2026-05-13)

CODEX revisou o ticket pós rodada 0.5 e devolveu **7 achados** (2 P1, 3 P2, 2 P3) + respostas para as 8 perguntas abertas. Arquiteto classificou e integrou:

| # | Achado | Severidade | Decisão | Onde aplicado |
|---|---|---|---|---|
| P1.1 | §5.3 — leitura de `meta_instalacao` antes da 1ª transação não é segura: `conftest.py:37` desliga `_lifespan_bootstrap`, e o bootstrap em `app/main.py:75` é quem preencheria a linha. Para C1/C3/C4/C5: ler após a 1ª transação. Para C5b: comparar contra UUID forçado, não ler meta_instalacao | P1 — Bloqueador | ✅ **Aceito integralmente** | §5.3 reescrito com estratégia "ler após 1ª transação"; cada cenário (C1, C3, C4, C5) ajustado; C5b mantém comparação direta |
| P1.2 | §4.1/§4.6/§9 — `eventos_publicacao` não tem coluna `protocolo`; o outbox usa `objeto_id` (ver `outbox.py:64` e `models/evento_publicacao.py:22`). Trocar para `WHERE objeto_tipo = ... AND objeto_id = ...` | P1 — Bloqueador | ✅ **Aceito integralmente** | §4.1, §4.6, §9 com queries corrigidas; §2.2 com nota sobre schema; §6.2 com grep de proteção contra regressão |
| P2.1 | §2.2 — contagem imprecisa: migration 4B afeta 6 tabelas de eventos/outbox + 4 objetos principais, não "5+5". `eventos_publicacao` é outbox, não objeto principal | P2 — Relevante | ✅ **Aceito** | §2.2 reescrito com 6+4 |
| P2.2 | C5 — circulação diagnóstica precisa item ainda `pendente`. `POST /agendamentos` move itens para `agendado`, mas `circulacao_diagnostica.py:250` exige `pendente`. Usar pedido separado | P2 — Relevante | ✅ **Aceito** | §4.5 (C5) com pedido_A e pedido_B separados |
| P2.3 | C1/C3 — para a cadeia ser realmente encadeada, o laudo deve usar `pedido_protocolo` (suportado em `laudos.py:100`) | P2 — Relevante | ✅ **Aceito** | §4.1 (C1) e §4.3 (C3) com `pedido_protocolo` |
| P3.1 | I1 — acrescentar que `registrar_evento_ledger` rejeita UUID inválido via `_validar_uuid_v4` (`ledger.py:167`), não só ausência | P3 — Lapidação | ✅ **Aceito** | §3.2 I1 refinada |
| P3.2 | C4 — asserção `criado_em < 1s` é frágil; preferir evento esperado + IDs corretos + `origem_agendamento_id` | P3 — Lapidação | ✅ **Aceito** | §4.4 (C4) com asserção robusta |

**Respostas às 8 perguntas abertas (§8):**

| # | Pergunta | Resposta CODEX | Aplicação |
|---|---|---|---|
| 1 | I1–I5 corretas? | ✅ Sim, com 2 ajustes: I1 UUID inválido, I3 só subdomínios com outbox | §3.2 refinada |
| 2 | C1+C3+C4+C5 cobrem "E2E consolidado"? | ✅ Sim após P1/P2 | — |
| 3 | C5b separado, asserção extra, ou opcional? | ✅ **Cenário separado obrigatório** | §4.5b promovido |
| 4 | C6 obrigatório ou opcional? | ✅ **Opcional**, sem circulação | §4.6 mantida opcional |
| 5 | Atomização payload/role? | ✅ `POST /prescricoes/{proto}/tokens/atomizar` + role paciente + `{"validade_minutos": 60}` | §4.1 passo 7 |
| 6 | Endpoint remarcação? | ✅ `POST /agendamentos/{protocolo}/remarcar` + `{"data_hora": ...}` (test_4d2:465) | §4.4 |
| 7 | Dispensação atomizada completa / remarcação circulação? | ✅ Não obrigatório | §6 |
| 8 | Estimativa recalibrada? | ✅ 260–310 sem C6 / até 340 com C6 | §5.5 |

**Validações independentes do CODEX rodada 1:**

- SAVEPOINT em `tests/integration/conftest.py:1-35` confirmado para isolamento entre testes ✅ — caveat: isolamento não cria `meta_instalacao.instance_id`
- §5.3 leitura direta de meta_instalacao rejeitada como estava (corrigida via P1.1)
- `rg` em `backend/app/routers/` confirma zero `INSERT INTO *_eventos` direto — guardrail da 4D continua coerente

**Resultado:** ticket fechou todas as 8 perguntas + 7 achados integrados. Pronto para Arquiteto redigir `TICKET-4E-1-PROMPT-CODE.md` ou submeter rodada 2 ao CODEX para confirmação.

---

## §11 Ciclo da 4E.1 (rastreabilidade)

| Rodada | Origem | Pontos | Aceitos | Adaptados | Rejeitados |
|---|---|---|---|---|---|
| 0 | Arquiteto redigiu ticket completo | — | — | — | — |
| 0.5 | Code (sessão VS Code) — 4 observações pré-CODEX | 4 | 3 | 1 | 0 |
| 1 | CODEX revisou ticket pós rodada 0.5 — 7 achados + 8 respostas | 7 + 8 | 15 | 0 | 0 |
| **Impl** | Code implementou `test_4e_e2e_consolidado.py` (780 linhas) — 6/6 cenários verdes + 64 regression Etapa 4 + 217 routers + 1 drift latente descoberto | — | — | — | — |
| 2 | CODEX revisão pós-implementação — 0 P1, 0 P2, 1 P3 (lapidação C5b: `set comprehension` no DISTINCT). Tamanho 780 linhas aprovado pelo CODEX como "forensic purpose". | 1 | 1 | 0 | 0 |
| **Total acumulado** | — | — | **19** | **1** | **0** |

**Nota sobre rodada 0:** o briefing v1 → v2 do `TICKET-4E-BRIEFING-PARA-CODEX.md` passou por uma rodada CODEX em 2026-05-13 e teve 3 achados aceitos (1 P1 bloqueador sobre semântica de `instance_id`, 1 P2 sobre escopo de objetos principais, 1 P3 sobre lapidação de `outbox.py`). Este ticket já incorpora essas correções como base.

**Nota sobre rodada 0.5:** Code identificou 4 pontos que faltavam validação ou refinamento. Arquiteto integrou todos (3 aceitos integralmente, 1 adaptado com leitura direta de `meta_instalacao`).

**Nota sobre rodada 1:** CODEX encontrou 2 P1 críticos que teriam quebrado a execução dos testes se o Code seguisse o texto da rodada 0.5 literalmente — (a) `meta_instalacao` não estar populado antes da 1ª transação (lifespan desligado em teste), e (b) outbox usar `objeto_id` em vez de `protocolo`. Ambos integrados. Os 3 P2 ajustam contagem, separação de pedidos para circulação, e encadeamento real do laudo. Os 2 P3 são lapidações textuais. Estimativa de tamanho subiu de 200–290 para 260–310 linhas.

**Nota sobre rodada Impl (Code, 2026-05-13):** 6 cenários implementados (5 obrigatórios + C6 opcional), todos verdes. Arquivo final tem **780 linhas** (vs. estimativa de 260–340) — desvio aceito pelo Arquiteto como padrão forense conforme Princípio 2 do projeto: asserções verbosas com valor real + esperado, docstrings com trilha de rodadas P1/P2/P3, blocks SQL nomeados no C6. Regressão da Etapa 4 verde (64 testes). Regressão dos routers tocados verde (217 testes). 49 fails do smoke geral confirmados pré-existentes (test_g4b, test_health, test_identidade_prescritor, test_cnes_prescritor, test_string_validacao) — independentes da 4E.1, validados por experimento de remoção do arquivo. Code descobriu drift latente: 210 rows com `instance_id IS NULL` em `eventos_publicacao` do `picsaude_test` (pré-4D.1, registrado para 4E.2). C6 mitigou filtrando por `objeto_id` específico do teste.

**Nota sobre rodada 2 (CODEX, 2026-05-13):** CODEX revisou implementação. **0 P1, 0 P2, 1 P3** — única lapidação no C5b (linha ~651): trocar verificação de `rows[0][0]` por `set(row[0] for row in rows) == {INSTANCE_ID_FORCADO}` para garantir que segundo valor divergente não se esconda atrás de ordenação. CODEX validou os 7 contratos críticos da rodada 1 implementados corretamente. Tamanho de 780 linhas aprovado: "verbosity is serving a forensic purpose: contract history, explicit SQL, expected/actual messages, and isolation notes". Sem alterações em `backend/app/`, `backend/alembic/`, `frontend/`. CODEX não rodou suite local (PG refused connection); validou sintaxe via `py_compile`. **P3 aplicada antes do commit canônico** para manter commit limpo.

---

## §12 Status de aprovação

**Status atual (pós rodada 2 CODEX, 2026-05-13):** 🟢 **APROVADO PARA COMMIT.** Ticket fechou 19 pontos aceitos + 1 adaptado + 0 rejeitados ao longo de 5 rodadas (0, 0.5, 1, Impl, 2).

**Caminho B (caminho seguido — Fabiano escolheu em 2026-05-13):**
- Arquiteto redigiu `TICKET-4E-1-PROMPT-CODE.md` direto após rodada 1 ✅
- Code implementou 6/6 cenários verdes ✅
- CODEX rodada 2 aprovou com 1 P3 não-bloqueador ✅

**Sequência final restante:**

1. Code aplica P3 da rodada 2 (lapidação C5b: `set comprehension` no DISTINCT)
2. Code roda pytest do arquivo para confirmar verde após lapidação
3. Arquiteto valida
4. Code commita test_4e_e2e_consolidado.py com mensagem canônica `test(4e.1):`
5. Code commita docs (tickets 4E + briefing) com mensagem `docs(4e):`
6. Code faz push origin main
7. 4E.1 fechada — atualizar `docs/PLANO-PRODUCAO-V2.md` e memória
8. Fabiano dispara 4E.2 (Regra 5 — CODEX + Jules sobre diff acumulado da Etapa 4)
