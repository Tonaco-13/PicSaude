# TICKET-5C-BIS-C.1 — Migrar schema institucional (`prestadores.org_id` + `unidades`) para PostgreSQL

| Campo | Valor |
|---|---|
| **Status** | **Martelos CODEX/Conselheiro integrados — apta para implementação.** |
| **Classe** | `ops`/`core` — migration de schema usado por código institucional + RBAC (login de prestador). **Revisão central.** |
| **Origem** | Gate PG do 5C-BIS-C/D (2026-06-03) |
| **Base** | `main` em `c6529e6` |

> **[VERIFICADO]** = confirmado com `alembic upgrade head` na PG. **[DECIDIDO]** = martelo.

---

## §1 Problema [VERIFICADO]
O schema institucional do **Ticket 30** (`prestadores.org_id` + `unidades`) **só foi aplicado via `init_tables.py` (SQLite)** — **nunca via Alembic**. Na PG (`alembic head`):
- `prestadores` = baseline `037d38d98806`: `id Integer serial`, `cnpj` UNIQUE NOT NULL, nome, tipo, `ativo Boolean`, created_at/updated_at — **sem `org_id`**.
- `unidades` = **não existe**.

Mas **todo o código usa o schema Ticket-30** (`org_id`/`unidades`): `login.py:288` (login de prestador), `prestadores.py` (CRUD `/prestadores`), `api_keys.py:61`, `cnes_prescritor.py:253`, `hospitalares.py` (Ticket 27), e a resolução do dispensador em **C e D** (hoje fail-closed por isso). → o subsistema institucional inteiro é **dev-only / quebrado na PG/prod**.

## §2 Decisões [DECIDIDO]
1. **C.1 antes do E** (o E depende deste schema).
2. **NÃO fundir `prestadores` com `estabelecimentos_proprios`** — são conceitos distintos hoje (`estabelecimentos_proprios` = farmácias próprias ligadas a `api_keys`, JOIN por `cnpj` em dispensações/relatórios). Fusão, se algum dia, é ticket de domínio próprio.
3. **drop+recreate com guarda contra destruição silenciosa** (idempotente):
   - `prestadores` **sem `org_id` e VAZIA** → dropa (com índices) e recria no schema Ticket-30 (§3).
   - `prestadores` **sem `org_id` e COM linhas** → **aborta a migration com erro explícito** pedindo backfill manual (nunca dropa dado em silêncio).
   - `prestadores` **já com `org_id`** → não dropa; **garante `unidades` + constraints/índices faltantes** (idempotência).
4. **`ativo` como Boolean.** O código executado usa `ativo = true` e insere `true` (`prestadores.py`). Migrar `ativo` como Integer na PG quebraria as queries. → **corrigir os models `Prestador`/`Unidade` (Integer→Boolean)** e migrar PG como Boolean — convergência real SQLite↔PG↔código.

## §3 Schema recomendado [DECIDIDO]
**`prestadores`**
| coluna | tipo |
|---|---|
| `id` | TEXT PK |
| `org_id` | TEXT NOT NULL **UNIQUE** |
| `nome` | TEXT NOT NULL |
| `tipo` | TEXT NOT NULL |
| `cnpj` | TEXT NULL |
| `ativo` | BOOLEAN NOT NULL DEFAULT true |
| `criado_em` | TEXT NOT NULL |

**`unidades`**
| coluna | tipo |
|---|---|
| `id` | TEXT PK |
| `prestador_id` | TEXT NOT NULL FK → `prestadores(id)` |
| `unidade_id` | TEXT NOT NULL |
| `nome` | TEXT NOT NULL |
| `tipo` | TEXT NULL |
| `ativo` | BOOLEAN NOT NULL DEFAULT true |
| `criado_em` | TEXT NOT NULL |
| | UNIQUE `(prestador_id, unidade_id)` |

**Índice de `cnpj`** (login de prestador resolve por CNPJ): **único parcial** `WHERE cnpj IS NOT NULL` é o ideal. Se for visto como política nova, ao menos **índice simples** e deixar a unicidade para follow-up. [DECIDIDO — preferência: parcial único; fallback: simples]

## §4 Escopo de arquivos
| Arquivo | Mudança |
|---|---|
| `alembic/versions/<nova>_*.py` | **Criar** — migration §2.3 (guarda) + §3 (schema) |
| `app/models/prestador.py` · `app/models/unidade.py` | `ativo` Integer → **Boolean** (§2.4) |
| `tests/integration/test_prestadores_institucional_pg.py` | **Criar** — gate PG (ver §5) |

**NÃO toca:** `estabelecimentos_proprios` (§2.2); `circulacao`/`agendamentos` (o positivo do dispensador re-acende sozinho quando o schema existir — §6); serialização/assinatura (R6 não se aplica).

## §5 Critérios de aceite (gate PG)
- `alembic upgrade head` em PG vazio → `\d prestadores` tem `org_id` (UNIQUE) + `ativo` Boolean; `\d unidades` existe com FK + UNIQUE `(prestador_id, unidade_id)`.
- **Guarda:** com `prestadores` populada sem `org_id`, a migration **aborta com erro claro** (teste do branch "com linhas").
- **Subsistema na PG:** CRUD `/prestadores` (criar/listar/obter), `/prestadores/{org_id}/unidades`, e **login de prestador** (`login.py`) funcionam (200/201) — antes quebravam.
- **Convergência:** SQLite (init_tables) e PG batem; suíte SQLite existente continua verde após `ativo`→Boolean.

## §6 Impacto / sequência
- **Destrava de uma vez:** login-prestador, CRUD prestadores/unidades, `api_keys`, `cnes`, hospitalar (Ticket 27), e o **dispensador positivo de C e D** (o `try/except` fail-closed para de capturar quando `org_id` existir — **sem mudar C/D**).
- **Pós-merge (C.1 + #9 + #10):** os testes positivos do dispensador (CNPJ mascarado→2xx, ambíguo→403, inativo→403, org match) entram — follow-up de teste, não de código.
- **Pré-requisito do E** (hospitalar, hop extra `unidade_id`).

---

*Martelos integrados em 2026-06-04 sobre `c6529e6`. **Apta para implementação.***
