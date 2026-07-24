# TICKET-DEMO-RESET-PG — Rebuild do banco demo no Render (PostgreSQL-capaz)

| Campo | Valor |
|---|---|
| **Classe** | `ops` — com toque `core`: toca §9 (autoridade de schema). Revisão central obrigatória sobre o SHA do PR (CLAUDE.md §10). |
| **Para** | code/app (engenheiro) → parecer Conselheiro → Fabiano |
| **Origem** | Despacho do Conselheiro 2026-07-24; issue-marcador GitHub **#124**; micro-arco do "fantasma" 2026-07-23 |
| **Base** | `main` |
| **Estado** | 🔲 Pendente de implementação (parecer Conselheiro incorporado) |
| **Parecer Conselheiro** | ✅ **APROVO** (main `2dfe15f`, 2026-07-24 — 21 âncoras conferidas). Diagnóstico e §3.2 endossados sem ressalva. 2 endurecimentos incorporados (§3.3 + AC 8/9/10). |

---

## §1 — Contexto (não reabrir)

A documentação afirma que "rebuild do demo = drop schema + migrate + seed" (ver
`backend/docs/tickets/TICKET-COER2-POS-MERGE-FIX.md` §3.4 e `docs/LEARNINGS.md`,
entrada 2026-07-23). **Mas nenhum script faz isso contra PostgreSQL.** O único
candidato, `backend/scripts/reset_demo_db.py`, é SQLite-only:

- **`reset_demo_db.py:53`** — `db_path = Path(PIX_SAUDE_DEMO_DB).resolve()` opera
  sobre um **arquivo** SQLite. Em PG não há arquivo.
- **`reset_demo_db.py:57-60`** — `db_path.unlink()` apaga um arquivo SQLite. Em PG
  é um **no-op** (não há arquivo para remover); não emite `DROP SCHEMA`.
- **`reset_demo_db.py:68`** — `Base.metadata.create_all(bind=engine)` **só cria
  tabelas faltantes; nunca emite `DROP`**. Contra o PG do Render, não limparia os
  dados existentes — o estado acumula.
- Não há ramo de dialeto, não há `DATABASE_URL`, não há `engine.dispose()`.

Conclusão verificada: **o demo do Render (PG, persistente) não tem como ser
resetado hoje.** O `seed_demo.py` é UPSERT idempotente (SELECT → INSERT/UPDATE das
personas canônicas; **não apaga** artefatos criados via API — ver `seed_demo.py`
helpers `_garantir_*`). O `predeploy.sh:16,19` só faz `alembic upgrade head` +
`python3 seed_demo.py` — **sem `drop` nem `rm`**.

### Por que importa

Demo compartilhado que nunca reseta = **todo teste manual na vitrine é
confundível**. Já custou um ciclo: o "fantasma" de 2026-07-23 era o próprio
Fabiano circulando uma receita numa sessão anterior — **contaminação de estado,
não bug** — mas levou uma investigação inteira para descartar (`docs/LEARNINGS.md`,
entrada "fantasma"). Enquanto não houver reset, **todo relatório de bug na vitrine
carrega a ressalva de contaminação**, e a validação manual da Fatia B herda o
mesmo risco.

> **Régua de leitura (registrada no LEARNINGS):** achado só na vitrine, não
> reproduzível em banco limpo = suspeitar de contaminação de estado antes de caçar
> regressão.

### Nota lateral (confirmado: não é bug)

`predeploy.sh:19` invoca `python3 seed_demo.py` sem exportar
`PICSAUDE_DEMO_MODE=true`, e `seed_demo.main()` aborta (`exit 1`) sem essa flag
(ver guardas em `seed_demo.py`). **Isso parecia um bug paralelo, mas está
resolvido:** o `render.yaml:47-48` seta `PICSAUDE_DEMO_MODE: "true"` no **nível do
serviço**, e o `preDeployCommand` do Render herda os envVars do serviço — logo o
`seed_demo.py` do predeploy **recebe a flag do ambiente** e não aborta.

> Resolução do parecer Conselheiro (2026-07-24): a pergunta "não está claro se o
> Render injeta" está respondida — injeta, por herança de envVars do serviço.

---

## §2 — Escopo

Tornar `reset_demo_db.py` capaz de operar contra **PostgreSQL** (o dialeto do
Render) preservando o comportamento atual para SQLite (dev). O script passa a ser
o mecanismo oficial e versionado de rebuild do banco demo.

**Não é** data-fix retroativo no ledger (§2 do CLAUDE.md): não altera registros
clínicos existentes — **apaga todo o schema e o recria do zero**. É ação destrutiva
e irreversível por design.

---

## §3 — Requisitos

### §3.1 — Bifurcação por dialeto

O script decide o dialeto **reusando a lógica já existente em `app/database.py:42`**
(`_USE_SQLITE = not DATABASE_URL`) — **não inventar nova detecção**, sob pena de
divergir do resto da aplicação. A partir do `engine` importado de `app.database`:

```
PG   (engine.dialect.name == "postgresql"):
    1. DROP SCHEMA public CASCADE; CREATE SCHEMA public;
       (ou o schema efetivo em uso — confirmar contra a DATABASE_URL da vitrine)
    2. alembic upgrade head
    3. seed_demo.main()

SQLite (engine.dialect.name == "sqlite"):
    1. db_path.unlink()      [comportamento atual, linhas 57-60]
    2. alembic upgrade head  [SUBSTITUI o create_all da linha 68 — ver §3.2]
    3. seed_demo.main()
```

### §3.2 — `alembic upgrade head`, NÃO `Base.metadata.create_all()` (REGRA DE OURO)

**O `create_all` da linha 68 é removido e substituído por `alembic upgrade head`.**

**Rationale arquitetural (load-bearing):** `create_all` reproduz o schema a partir
dos **modelos ORM** do metadata — e os modelos **não contêm** os 17 triggers de
banco (eles vivem só nas migrações `f2b7c1d0a4e5` e `c3d4e5f6a7b8`). Um rebuild
via `create_all` recriaria as tabelas **sem os triggers**, reproduzindo
**exatamente o defeito que a migração `f2b7c1d0a4e5:9-11` documenta ter corrigido**
— a saber: *"o `predeploy.sh` do Render NUNCA chama `init_tables.py`. Resultado
medido: em PostgreSQL os triggers nunca existiram."*

Em outras palavras: `create_all` **burla o §9** (a migração é a única autoridade de
schema). Esse desvio só não mordeu até hoje porque era SQLite de dev. No PG do
Render, um rebuild via `create_all` produziria um banco estruturalmente diferente
do `alembic head` — o oposto do que um "reset limpo" promete.

> Portanto: **toda recriação de schema, em qualquer dialeto, passa pela migração.**
> O `alembic upgrade head` é o único caminho.

### §3.3 — Confirmação do ALVO como código (não só procedimento)

> Endurecimento 1 do parecer Conselheiro (2026-07-24): invariante executável, não
> memória do revisor.

As guardas de §5 inspecionam `PICSAUDE_ENV` e `PICSAUDE_DEMO_MODE` — **não** a
`DATABASE_URL**, que é o alvo real da destruição.** Um ambiente mal-configurado
com `DEMO_MODE=true` + `DATABASE_URL` apontando para o lugar errado passaria as
duas guardas e faria `DROP SCHEMA CASCADE` no alvo errado.

Logo, no **ramo PG**, **antes** de qualquer DROP, o script deve:

1. **Ecoar o alvo** — host + dbname extraídos da `DATABASE_URL`, **credencial
   mascarada** (reusar o padrão de `database.py:56`: `re.sub(r"://[^:@]+:[^@]+@", ...)`).
2. **Exigir confirmação explícita** — ou input digitado interativo, ou flag de
   assentimento tipo `--sim-eu-quero` (necessária para execução não-interativa,
   como um job no Render).

Sem a confirmação do alvo, aborta. A régua de §5 ("confirmação humana do alvo")
passa a ser **código que o próprio script executa**, não lembrança do operador.

### §3.4 — Schema efetivo + lifecycle da conexão

> Endurecimento 2 do parecer Conselheiro (2026-07-24).

- **Schema efetivo da vitrine** — não hardcodar `public` sem checar. Confirmar o
  `search_path` do PG do Render **antes** de cravar o nome do schema no
  `DROP ... CASCADE`. Pré-condição de implementação (o engenheiro confirma o
  schema real da vitrine contra a `DATABASE_URL` antes do primeiro rebuild real).
- **Lifecycle da conexão** — a DDL crua (`DROP SCHEMA` + `CREATE SCHEMA`) deve ser
  **commitada** e seguida de `engine.dispose()` **antes** de `alembic upgrade head`,
  para que a migração pegue uma conexão limpa (sem cursor stale sobre o schema
  recém-dropado). O §1 já notou a ausência de `dispose()` no script atual.

---

## §4 — Invariantes tocados (checklist)

- [x] **CLAUDE.md §2** — o ledger é imutável. O rebuild não toca registros: apaga
      o schema inteiro e o recria vazio. Não há `UPDATE`/`DELETE` seletivo em
      `*_eventos`.
- [x] **CLAUDE.md §9** — a migração é a autoridade de schema. Recriação via
      `alembic upgrade head`, nunca `create_all` (ver §3.2).
- [x] **CLAUDE.md §10** — classe `ops` com toque `core` (toca §9) ⇒ revisão
      central obrigatória.
- [x] **Confirmação do alvo como código** (§3.3) — as guardas de §5 protegem
      ambiente, não alvo. A confirmação do `DATABASE_URL` (host+dbname,
      mascarado) vira verificação executável no script.
- [ ] **Irreversibilidade** — `DROP SCHEMA ... CASCADE` é destrutivo. As duas
      guardas (§5) + confirmação do alvo como código (§3.3) + confirmação humana
      do operador são obrigatórias no aceite.

---

## §5 — Régua de segurança (defense-in-depth)

O `DROP SCHEMA` é **irreversível**. As guardas já existem no script
(`reset_demo_db.py:35-46`) e **devem ser preservadas e mantidas como pré-condição
de execução** — nunca contornadas, mesmo em automação:

1. **Aborta se `PICSAUDE_ENV=prod`** (`reset_demo_db.py:36-38`).
2. **Aborta se `PICSAUDE_DEMO_MODE != "true"`** (`reset_demo_db.py:40-46`).

> **Régua do Conselheiro (obrigatória no aceite):** NENHUM agente recebe a
> `DATABASE_URL` da vitrine. A execução no Render é do **Fabiano** (Render Shell)
> ou de um job **disparado por ele**. O script é versionado e testado; **a
> credencial não circula em chat.**

A confirmação humana do **alvo** (qual schema/banco o script vai destruir) é
exigida antes da execução real contra a vitrine.

---

## Critérios de aceite

1. **[PG-capaz]** `reset_demo_db.py` opera contra PostgreSQL: ramo
   `DROP SCHEMA ... CASCADE` + `CREATE SCHEMA` quando
   `engine.dialect.name == "postgresql"`, reusando a decisão de dialeto de
   `app/database.py` (sem detecção nova). Ramo SQLite preserva o `unlink` atual.

2. **[§9 — migração é a autoridade]** O `create_all` da linha 68 é **removido** e
   substituído por `alembic upgrade head` em ambos os dialetos. Justificativa no
   §3.2 (reproduziria o defeito que `f2b7c1d0a4e5` corrigiu).

3. **[Guardas preservadas]** As duas guardas (`reset_demo_db.py:35-46`) permanecem
   como pré-condição: aborta em `PICSAUDE_ENV=prod` e exige
   `PICSAUDE_DEMO_MODE=true`. Sem bypass, mesmo em automação.

4. **[Verde — rebuild de PG efêmero]** Contra um PG efêmero limpo, após o rebuild:
   - `alembic_version` aponta para `head` (a mesma revisão do `main`).
   - **17 triggers presentes**: os 16 de imutabilidade (8 tabelas × UPDATE/DELETE,
     `f2b7c1d0a4e5`) + 1 de saldo (`trg_check_saldo_efetivo`, `c3d4e5f6a7b8`,
     PG-only). **(Nota: o despacho original citava "14 triggers" — incorreto; o
     número verificado contra as migrações é 17.)**
   - As personas/artefatos canônicos semeados por `seed_demo.py` estão presentes.

5. **[Vermelho-antes-de-verde — prova anti-contaminação]** Contra um PG
   **previamente sujo** (com ≥1 artefato de sessão de teste injetado — ex.: uma
   dispensação criada via API), após o rebuild esse artefato **não existe mais**:
   `SELECT COUNT(*) FROM dispensacoes WHERE <marcador-da-sessão>` retorna 0, e o
   count total volta ao baseline determinístico que um rebuild de PG limpo produz.
   Esta é a prova de que o reset de fato limpa — não apenas acrescenta.

6. **[Idempotente]** Rodar o rebuild duas vezes seguidas produz o mesmo estado
   final (segunda execução não falha, não acumula).

7. **[SQLite regressivo]** O ramo SQLite continua funcionando (dev): após o
   rebuild, o banco local tem o mesmo shape (alembic head + triggers aplicáveis ao
   SQLite + personas). Sem regressão no fluxo de dev.

8. **[Confirmação do alvo (§3.3)]** No ramo PG, antes de qualquer DROP, o script
   ecoa host + dbname da `DATABASE_URL` (credencial mascarada, padrão
   `database.py:56`) e exige confirmação explícita — input interativo **ou** flag
   `--sim-eu-quero` (para execução não-interativa). Sem confirmação, aborta.

9. **[Alvo protegido]** Se rodado sem a confirmação do AC 8 (sem input e sem a
   flag), o script **aborta sem emitir nenhum DROP** — mesmo que `DEMO_MODE=true`
   e `PICSAUDE_ENV != prod`. (Vermelho: prova que as guardas de ambiente **não**
   bastam para autorizar a destruição.)

10. **[Schema efetivo + conexão (§3.4)]** O schema alvo é lido do `search_path` do
    PG (não hardcodar `public` sem confirmação), e a DDL crua é commitada +
    `engine.dispose()` executado **antes** de `alembic upgrade head`.

---

## Fora de escopo

- **#124(b) — Reset agendado / isolamento por testador.** Decisão futura; depende
  deste ticket existir primeiro. Não implementar cron, não implementar partição
  por testador aqui.
- **`predeploy.sh` + `PICSAUDE_DEMO_MODE`** (§1, nota lateral) — **resolvido pelo
  parecer Conselheiro**: o `render.yaml:47-48` seta a flag no nível do serviço e
  o `preDeployCommand` herda os envVars. Não é bug; não há trabalho aqui.
- **Reset de outras vitrines** além da demo do Render.

---

## Fluxo de aprovação

```
Este ticket (arquiteto/ZCode)
  → code/app (engenheiro) implementa
  → parecer do Conselheiro (reconferir âncoras contra o código)
  → Fabiano (decisão + execução no Render via Render Shell / job disparado por ele)
```

A `DATABASE_URL` da vitrine **não entra no fluxo de revisão** — fica com o Fabiano.

---

## Anexo — âncoras de código (verificadas em 2026-07-24, branch `main`)

| Item | Arquivo:linha |
|---|---|
| Guarda `PICSAUDE_ENV=prod` (abort) | `backend/scripts/reset_demo_db.py:35-38` |
| Guarda `PICSAUDE_DEMO_MODE="true"` (abort) | `backend/scripts/reset_demo_db.py:40-46` |
| `db_path` SQLite (no-op em PG) | `backend/scripts/reset_demo_db.py:53` |
| `unlink()` do arquivo SQLite (no-op em PG) | `backend/scripts/reset_demo_db.py:57-60` |
| `create_all()` — **a remover** (§9 desvio) | `backend/scripts/reset_demo_db.py:68` |
| `seed_demo.main()` | `backend/scripts/reset_demo_db.py:72-73` |
| predeploy: `alembic upgrade head` | `backend/predeploy.sh:16` |
| predeploy: `python3 seed_demo.py` | `backend/predeploy.sh:19` |
| Decisão de dialeto (`_USE_SQLITE = not DATABASE_URL`) | `backend/app/database.py:42` |
| `DATABASE_URL` lida do ambiente | `backend/app/database.py:34` |
| Normaliza `postgres://` → `postgresql://` | `backend/app/database.py:39-40` |
| Máscara de credencial na URL (reusar em §3.3) | `backend/app/database.py:56` |
| Alembic lê `DATABASE_URL` (fallback SQLite) | `backend/alembic/env.py:90,96-108` |
| `PICSAUDE_DEMO_MODE: "true"` no serviço (fecha nota lateral) | `render.yaml:47-48` |
| `preDeployCommand` herda envVars do serviço | `render.yaml:41,42-48` |
| Docstring "16 triggers (8 tabelas × UPDATE/DELETE)" | `backend/alembic/versions/f2b7c1d0a4e5_ledger_triggers_imutabilidade.py:13` |
| `TABELAS_CONGELADAS` (8 tabelas) | `backend/alembic/versions/f2b7c1d0a4e5_ledger_triggers_imutabilidade.py:66-75` |
| Trigger de saldo **PG-only** (early return) | `backend/alembic/versions/c3d4e5f6a7b8_t3_trigger_saldo_efetivo.py:56-57` |
| `CREATE TRIGGER trg_check_saldo_efetivo` | `backend/alembic/versions/c3d4e5f6a7b8_t3_trigger_saldo_efetivo.py:63` |
| `seed_demo.py` UPSERT idempotente (não limpa) | `backend/seed_demo.py` (helpers `_garantir_*`) |
| Contexto do fantasma + contaminação | `docs/LEARNINGS.md` (entrada 2026-07-23, origem "#124") |
