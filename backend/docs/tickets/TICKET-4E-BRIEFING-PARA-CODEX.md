# Briefing para CODEX redigir TICKET 4E

> Cole este briefing no CODEX e peça para ele redigir o **ticket completo
> da sub-tarefa 4E** seguindo o formato da 4D.2.
>
> Após CODEX devolver o ticket, o Arquiteto (Opus 4.7) valida, adiciona
> §10/§11/§12 conforme rodadas, e passa para o Code implementar a 4E.1.
> A 4E.2 (Regra 5) é disparada por Fabiano após 4E.1 fechar.
>
> **Data:** 2026-05-13
> **Classe:** `module` — adiciona testes E2E novos (sem alterar core)
> **Pacto:** Regra 2 estrita aplicada à Peça A; Peça B é disparo da Regra 5

---

## §1 Objetivo da 4E

Fechar a **Etapa 4 — `instance_id` canônico** com duas peças sequenciais:

| Peça | Conteúdo | Pacto |
|---|---|---|
| **4E.1** — Testes E2E consolidados | Novo arquivo `tests/integration/test_4e_e2e_consolidado.py` com 4–6 cenários que atravessam subdomínios + runbook de regressão consolidada da Etapa 4 | Regra 2 estrita (ciclo completo) |
| **4E.2** — Análise estática consolidada | Fabiano dispara CODEX + Jules sobre o diff acumulado da Etapa 4 (de `d8abf7e^` até HEAD pós-4E.1); Arquiteto integra feedback; Code aplica fixes finais; etapa marcada ✅ | Regra 5 (disparo, não código) |

A 4E.1 cobre a lacuna que sobrou após 4D.1 e 4D.2: cobertura **intra-subdomínio** (ledger + outbox + transação por objeto) existe; cobertura **transversal entre subdomínios** (cadeia clínica multi-objeto) ainda não.

A 4E.2 é o checkpoint formal previsto na Regra 5 do pacto (ver `workflow_pacto_desenvolvimento.md`): análise estática só faz sentido sobre sistema integrado, ao fim de cada etapa.

---

## §2 Predecessoras (commits acumulados da Etapa 4)

| Sub-tarefa | Commit | Conteúdo |
|---|---|---|
| 4A | `d8abf7e` | Helper `app/instance.py` (296 linhas, instance_id base) |
| 4B-prequel | `2dce4f8` + `1470224` | Consulta CODEX + docs |
| 4B | `89f064a` | Migration `_4b_instance_id` + colunas em todas as ledgers |
| 4C | `2fbcf43` + `983359f` | Helper `registrar_evento_ledger` + 6 models alinhados |
| 4D.1 | `60382d2` + `0056c93` | Migração de 21 sites em 7 routers (prescrição) |
| 4D.2 | `3db4060` + `79f2f4f` | Migração de 13 sites em 4 routers (exame, laudo, agendamento, circulação) |
| Task #8 | `d2f016b` | Saneamento de fixtures legadas |
| OTP fix (segurança) | `5fa6902` + `a44582b` | Guard PICSAUDE_ENV + `secrets.randbelow` + higiene |

Para o disparo da Regra 5 (Peça B), o range completo do diff é:

```bash
git log d8abf7e^..HEAD --oneline
git diff d8abf7e^..HEAD --stat
git diff d8abf7e^..HEAD -- backend/app backend/tests
```

---

## §3 Peça A — 4E.1: Testes E2E consolidados

### §3.1 Motivação

Os testes existentes cobrem invariantes **dentro de cada subdomínio**:

| Arquivo | Cobertura |
|---|---|
| `tests/test_instance_id.py` | Helper `app/instance.py` (4A) |
| `tests/test_migration_4b_instance_id.py` | Migration que adicionou as colunas (4B) |
| `tests/test_ledger_helper.py` | Helper `registrar_evento_ledger` (4C) |
| `tests/integration/test_4d1_instance_id_ledger.py` | Prescrição: ledger + outbox + transação por objeto (4D.1) |
| `tests/integration/test_4d2_instance_id_ledger.py` | Exame, laudo, agendamento, circulação: ledger + outbox + transação por objeto (4D.2) |

O que falta é a camada **transversal**: cenários em que **a mesma sessão de paciente** gera múltiplos objetos sanitários, validando que `instance_id` se comporta corretamente entre objetos e entre transações.

### §3.2 Semântica correta de `instance_id` (fundamento para os cenários)

> **Nota crítica (corrigida em rodada 1, ver §10):** `instance_id` é a
> **marca d'água da instalação PicSaúde** — UUID v4 inalterável, gerado
> no primeiro boot, persistido em `meta_instalacao` + `.instance_id`
> (DATA-PROTECTION.md §4.2). **Não é um ID de transação.** Em uma única
> instalação, **todos** os eventos do ledger compartilham o mesmo
> `instance_id`. A função do campo é forense: identificar de qual
> instância PicSaúde um row vazado se originou.

Invariantes que o helper `registrar_evento_ledger` garante:

| # | Invariante | Origem |
|---|---|---|
| I1 | Todo evento novo no ledger tem `instance_id` UUID v4 não nulo | Helper recusa chamada sem o argumento (`TypeError`) |
| I2 | Em uma mesma instância PicSaúde, **todos** os eventos têm o mesmo `instance_id` | `app.instance.get_instance_id_conn()` retorna o valor canônico estável |
| I3 | Em uma transação clínica, ledger e outbox adjacente compartilham `instance_id` | Caller passa o mesmo valor a `registrar_evento_ledger` e `registrar_outbox` |
| I4 | Eventos da mesma transação compartilham o `instance_id` obtido na transação | Caller usa `get_instance_id_conn(conn)` uma vez |
| I5 | O outlier de schema em `agendamento_eventos` (coluna `evento`, `payload`) preserva I1–I4 | `_LEDGER_SCHEMA` encapsula o drift em `app/domain/ledger.py` |

### §3.3 Cenários propostos (4–6, calibrar com CODEX)

**C1 — Cadeia clínica completa em uma sessão de paciente**

- Prescritor emite prescrição para paciente X
- Mesmo prescritor emite pedido de exame para paciente X
- Prestador cria agendamento vinculado ao pedido
- Prestador realiza o agendamento (transita itens do pedido para `coletado`)
- Prestador emite laudo

Invariantes verificadas:

- Cada evento gerado satisfaz I1 (UUID v4 presente)
- O `instance_id` de **todos os eventos das 5 transações** é idêntico e igual ao retorno de `app.instance.get_instance_id_conn(conn)` (I2)
- Dentro de cada transação clínica, ledger + outbox compartilham o mesmo `instance_id` (I3)
- Os 5 objetos permanecem ligados ao mesmo paciente (CPF normalizado), e a cadeia clínica não vaza protocolos entre objetos (ex: `protocolo` da prescrição não aparece em laudo, pedido_exame.protocolo ≠ laudo.protocolo)
- Estados dos objetos transitam coerentemente entre subdomínios (ex: itens do pedido transitam `pendente → agendado → coletado`)

**C2 — Múltiplas transações no mesmo objeto**

- Prescritor emite prescrição
- Paciente apresenta no balcão; dispensador retém custódia
- Dispensador registra dispensação parcial

Invariantes verificadas:

- I1 em todos os eventos gerados
- I2: as 3 transações geram eventos com o **mesmo** `instance_id` (não diferente — esse era o erro da rodada 0)
- O protocolo da prescrição é estável nas 3 transações
- Em cada transação isolada, eventos da mesma transação compartilham o `instance_id` obtido localmente (I4)

**C3 — Cadeia diagnóstica completa (agendamento → pedido → laudo)**

- Pedido de exame emitido
- Agendamento criado vinculado ao pedido
- Agendamento realizado (itens transitam `agendado → coletado`)
- Laudo criado e liberado

Invariantes verificadas:

- I1 em todos os eventos gerados nos 3 ledgers (`agendamento_eventos`, `pedido_exame_eventos`, `laudo_eventos`)
- I2: os 3 ledgers recebem o mesmo `instance_id` (validar via `SELECT DISTINCT instance_id FROM <tabela>` retornando uma única linha)
- I5: `agendamento_eventos.evento` continua transparente — o `SELECT evento, instance_id FROM agendamento_eventos` mostra coerência

**C4 — Remarcação derivada preserva invariantes**

- Criar agendamento original
- Remarcar → gera novo objeto derivado (transação com 3 eventos no ledger antigo + criação do novo)

Invariantes verificadas:

- I1, I2, I4 em todos os eventos da remarcação
- O `instance_id` é o mesmo nos 3 eventos da remarcação E no `agendamento_criado` do novo objeto derivado E no `agendamento_criado` do objeto original (todos da mesma instância)
- `origem_agendamento_id` aponta corretamente ao agendamento antigo
- O fluxo de remarcação não introduz row com `instance_id` NULL

**C5 — Smoke test agregado de toda a Etapa 4 (invariante de instância única)**

Num único teste, criar exemplares dos **5 tipos de objetos sanitários** já tocados:

- 1 prescrição emitida
- 1 pedido de exame emitido
- 1 agendamento criado
- 1 laudo criado
- 1 circulação diagnóstica criada

Invariante crítica (forma correta):

```sql
-- Esperado: COUNT = 1, e o valor é igual ao retorno de
-- app.instance.get_instance_id_conn(conn)
SELECT COUNT(DISTINCT instance_id) FROM (
    SELECT instance_id FROM prescricao_eventos               WHERE criado_em > <t0>
    UNION ALL
    SELECT instance_id FROM pedido_exame_eventos             WHERE criado_em > <t0>
    UNION ALL
    SELECT instance_id FROM laudo_eventos                    WHERE criado_em > <t0>
    UNION ALL
    SELECT instance_id FROM agendamento_eventos              WHERE criado_em > <t0>
    UNION ALL
    SELECT instance_id FROM circulacao_diagnostica_eventos   WHERE criado_em > <t0>
) AS uniao;
```

Outras checagens:

- Nenhum row de evento novo tem `instance_id IS NULL` em nenhum dos 5 ledgers (I1 universal)
- O valor único do `SELECT DISTINCT` é UUID v4 válido
- O valor é igual ao retornado por `app.instance.get_instance_id_conn(conn)` na fixture de teste

**C6 (opcional) — Coerência ledger+outbox em cadeia multi-objeto**

Quando uma transação gera evento em ledger E outbox (`eventos_publicacao`), confirmar que o `instance_id` é idêntico nos dois — mesmo em cadeia onde o outbox de um objeto pode ser intercalado com ledger de outro. Validar especificamente que:

- `eventos_publicacao` para todos os `objeto_tipo` gerados na sessão tem `instance_id` igual ao do `*_eventos` correspondente
- Não há vazamento entre transações (cada `eventos_publicacao.protocolo` tem `instance_id` coerente com o `*_eventos` do mesmo protocolo)

### §3.4 Decisões de implementação (validar com CODEX)

- **Arquivo único**: `backend/tests/integration/test_4e_e2e_consolidado.py`
- **Reutilizar fixtures**: `client`, `outer_conn`, seeds em `tests/integration/conftest.py` (mesmo padrão de 4D.1/4D.2)
- **Sem novos endpoints**: 4E.1 não altera código de produção, só consome a superfície atual
- **Sem novos helpers**: se for tentador extrair helpers de queries SQL, deixar inline neste arquivo — clareza > DRY em testes E2E
- **Estimativa**: 150–250 linhas
- **Runbook consolidado** (sub-entregável): comando shell ou Makefile target que roda os 6 pytest da Etapa 4 em sequência:

  ```bash
  cd backend
  python3 -m pytest \
      tests/test_instance_id.py \
      tests/test_migration_4b_instance_id.py \
      tests/test_ledger_helper.py \
      tests/integration/test_4d1_instance_id_ledger.py \
      tests/integration/test_4d2_instance_id_ledger.py \
      tests/integration/test_4e_e2e_consolidado.py \
      -v
  ```

### §3.5 Critérios de aceitação da 4E.1

- Novo arquivo `tests/integration/test_4e_e2e_consolidado.py` com cenários C1–C5 (C6 opcional)
- Cada cenário verifica explicitamente as invariantes aplicáveis de §3.2 (I1–I5)
- Todos os pytest da Etapa 4 (6 arquivos) rodam verdes em sequência
- Nenhum endpoint de produção alterado
- Documentação dos cenários em docstring do módulo, citando o contrato semântico de `instance_id` (referência a `app/instance.py` + DATA-PROTECTION.md §4.2)
- Commit em PT-BR seguindo padrão convencional (`test:`)

### §3.6 Fora do escopo da 4E.1

- Não criar testes para Etapa 5+ (Fix B1, DEMO_MODE, etc.)
- Não cobrir tokens de apresentação nem dispensação além do mínimo da C2 (seria 4F ou Etapa 5)
- Não refatorar `tests/integration/conftest.py` (extensão se necessário, refactor não)
- Não adicionar fixtures globais novas — usar as existentes
- Não alterar payloads, schemas, vocabulário de eventos

### §3.7 Escopo do `instance_id` na Etapa 4 (registrado em rodada 1)

> Esta nota deixa explícito o que a Etapa 4 entrega e o que **fica para a Etapa 8** — alinhamento com o achado P2 da rodada 1 do CODEX.

A Etapa 4 deixa o `instance_id` canônico **operacional**:

- Nos **ledgers** dos 5 subdomínios tocados: `prescricao_eventos`, `pedido_exame_eventos`, `laudo_eventos`, `agendamento_eventos`, `circulacao_diagnostica_eventos`
- No **outbox** (`eventos_publicacao`)
- Como **marca d'água da instalação** (`meta_instalacao` + `.instance_id`)

A Etapa 4 **não** deixa o `instance_id` mapeado nos **models ORM dos objetos principais** (`Prescricao`, `PedidoExame`, `Laudo`, `Agendamento`). A migration 4B (`4b1ce80a017d`) adicionou a coluna física nessas tabelas, mas o preenchimento e o mapping ORM são tratados na **Etapa 8** (pré-deploy público, junto com o backfill de eventos antigos).

A 4E.1 **não** testa `instance_id` em rows de objetos principais — apenas em ledger e outbox. Cenários que parecerem exigir leitura de `prescricoes.instance_id` (etc.) devem ser refatorados para ler do `*_eventos` correspondente.

---

## §4 Peça B — 4E.2: Disparo da Regra 5

**Esta peça é processo, não código. Não há ticket de implementação — há protocolo de revisão.**

### §4.1 Pré-condição

4E.1 commitada, pushada e verde. HEAD do `main` reflete o estado completo da Etapa 4.

### §4.2 Comandos para Fabiano coletar o material da revisão

```bash
# 1. Panorama de commits da Etapa 4
git log d8abf7e^..HEAD --oneline > /tmp/etapa4-commits.txt

# 2. Footprint da Etapa 4
git diff d8abf7e^..HEAD --stat > /tmp/etapa4-stat.txt

# 3. Diff completo (backend apenas)
git diff d8abf7e^..HEAD -- backend/ > /tmp/etapa4-diff.patch

# 4. Lista de arquivos tocados
git diff d8abf7e^..HEAD --name-only -- backend/ > /tmp/etapa4-files.txt
```

### §4.3 Briefing para CODEX (Peça B)

Fabiano cola no CODEX:

> Análise estática consolidada da Etapa 4 do PicSaúde — `instance_id` canônico. Revise o diff completo (de `d8abf7e^` até HEAD) com foco em:
>
> 1. **Coerência de `instance_id`** — todos os callers de `registrar_evento_ledger` passam `instance_id`? Helpers locais propagam corretamente?
> 2. **Padrões repetidos** — algum router tem variação de padrão que possa virar bug? (ex: caller que esqueceu `get_instance_id_conn` mas o teste não pegou)
> 3. **Conformidade com `CLAUDE.md`** — ledger imutável (§2), custódia (§3), estados (§5b), núcleo sanitário (§7)
> 4. **Regressões latentes** — sites antigos que passaram a ter código morto ou caminho não-coberto
> 5. **Cobertura de teste** — gaps entre o que 4D.1+4D.2+4E.1 cobrem e o que a superfície real expõe
>
> Reporte achados classificados por severidade: **P1** (bloqueador), **P2** (relevante mas não bloqueador), **P3** (lapidação textual / sugestão).
>
> Não pedir refatoração ampla — qualquer sugestão `core` exige aprovação do Arquiteto antes de aplicar.

### §4.4 Briefing para Jules (Peça B)

Fabiano cola no Jules:

> Análise estática alternativa da Etapa 4 do PicSaúde — `instance_id` canônico. Sua lente é diferente do CODEX: foque em **simplicidade, legibilidade e pragmatismo**. Revise o diff (de `d8abf7e^` até HEAD) e responda:
>
> 1. **Há complexidade desnecessária** introduzida pelos 5 sub-tarefas? (helpers redundantes, abstrações que custam mais que entregam)
> 2. **A propagação de `instance_id`** poderia ser mais simples / mais óbvia? (ex: vale criar context manager, decorator, ou ficar como está?)
> 3. **Pontos de fragilidade** — o que mais provavelmente quebra na próxima sub-tarefa? Padrão que se desfaz se alguém esquecer uma convenção?
> 4. **Performance** — algum overhead introduzido? (ex: query extra por transação)
> 5. **Onboarding** — um desenvolvedor novo entenderia o que `instance_id` é e por quê em 5 minutos lendo `app/instance.py` + `app/domain/ledger.py`?
>
> Reporte achados em mesmo formato P1/P2/P3 que CODEX, para o Arquiteto integrar.

### §4.5 Integração de feedback (Arquiteto)

Arquiteto recebe os dois relatórios e produz:

```
docs/tickets/TICKET-4E-2-RELATORIO-INTEGRADO.md
```

Conteúdo:

- Tabela cruzada CODEX × Jules × Arquiteto (✅ aceito / 🔄 adaptado / ❌ rejeitado)
- Para cada P1: spec de fix curta passada ao Code (Regra 2 ou Regra 3 dependendo do tamanho)
- Para cada P2: decisão (aceitar agora, postergar como ticket separado, ou rejeitar com justificativa)
- Para cada P3: aceitos como melhoria textual em batch único

### §4.6 Itens já identificados para a 4E.2 (acumulados das rodadas)

Itens pré-classificados que o Arquiteto vai consolidar com o feedback final de CODEX+Jules na 4E.2:

| Item | Origem | Tipo | Tratamento previsto |
|---|---|---|---|
| Lapidar docstring de `backend/app/domain/outbox.py:6` — afirma que "todo router que inserir em `*_eventos` **deve** chamar `registrar_outbox()`". A 4D deliberadamente não criou outbox novo para eventos sem outbox adjacente. Ajustar para "quando houver evento publicável / outbox previsto", evitando falso requisito em revisões futuras. | CODEX rodada 1 P3 (sobre o briefing 4E) | Lapidação textual em código de produção | Regra 3 (ciclo simplificado) — Code aplica Edit pontual + commit `docs:` na onda de lapidações da 4E.2 |
| **210 rows com `instance_id IS NULL` em `eventos_publicacao` no banco `picsaude_test`** — todos `objeto_tipo='prescricao'` + `tipo_evento='prescricao_emitida'`. Os 5 ledgers principais (`prescricao_eventos`, `pedido_exame_eventos`, etc.) estão limpos (0 rows). Origem provável: pré-4D.1 (quando outbox.py não recebia `instance_id`) e/ou testes que commitaram sem usar SAVEPOINT (ex: `test_concorrencia.py` se cleanup falhou). **Não é bloqueador da 4E.1** — Code já mitigou no C6 filtrando por `objeto_id` específico do teste. Indica dívida operacional: banco de teste precisa de TRUNCATE periódico ou cleanup mais robusto. | 4E.1 implementação (Code, 2026-05-13) | Higiene operacional do banco de teste | Avaliar na 4E.2: TRUNCATE no setup global do conftest, ou ticket separado para Etapa 5 (pré-deploy) |

### §4.7 Critérios de fechamento da 4E.2

- Relatórios CODEX e Jules arquivados em `docs/revisoes/`
- Todos os P1 resolvidos (commit no `main`) ou justificados
- P2 com decisão registrada (aceitos, postergados ou rejeitados)
- P3 aceitos em commit único de lapidação (incluindo o item de `outbox.py` registrado em §4.6)
- `docs/PLANO-PRODUCAO-V2.md` atualizado com:
  - Etapa 4 marcada ✅ Fechada
  - Nota de fechamento com hashes finais
- Memória `picsaude_estado_<DATA>.md` atualizada com snapshot pós-Etapa 4
- Avaliação do pacto (próximo marco de revisão previsto em `workflow_pacto_desenvolvimento.md`) — as 6 regras se sustentaram na prática? Há ajuste a fazer antes da Etapa 5?

---

## §5 Decisões para CODEX validar na rodada 2 (sobre Peça A, após correção semântica)

1. As invariantes I1–I5 em §3.2 capturam corretamente o contrato do `instance_id` e do helper `registrar_evento_ledger`? Algo a adicionar/remover?
2. Os cenários C1–C5 reescritos com a semântica correta (todos os eventos compartilham `instance_id` em uma instância única) cobrem o que se espera de "E2E consolidado"?
3. C6 deve entrar como obrigatório ou opcional?
4. Faz sentido um único arquivo `test_4e_e2e_consolidado.py` ou separar por cenário (`test_4e_c1_cadeia_clinica.py`, etc.)?
5. A estimativa de 150–250 linhas continua calibrada após a reescrita (que tendeu a simplificar — menos asserções de "≠" e mais asserções de "= esperado")? Algum cenário vai estourar?
6. O smoke test C5 deve usar `t0 = datetime.utcnow()` para filtrar eventos da rodada de teste, ou usar SAVEPOINT por request (já presente em `tests/integration/conftest.py`) é suficiente? Em PostgreSQL com isolation por SAVEPOINT, todos os rows do teste somem no rollback — basta contar tudo da fixture.
7. Há cenário de **dispensação atomizada** ou **circulação diagnóstica em remarcação** que vale a pena cobrir explicitamente, dado que ambos viraram fonte de bugs latentes na 4D.1/4D.2?
8. Vale incluir um cenário (ou asserção numa C5 estendida) que valida explicitamente o **override em dev** (`PICSAUDE_INSTANCE_ID` env var) — confirmando que se o teste forçar um valor conhecido via env, todos os eventos gerados carregam esse valor? Isso seria a forma mais robusta de testar I2 sem depender do `instance_id` real da instância de teste.

---

## §6 Fora do escopo da 4E (inteira)

- Não tocar `app/` (código de produção) na 4E.1 — só `tests/`
- Não introduzir nova migration de banco
- Não cobrir Etapa 5+ (Fix B1, DEMO_MODE, Docker, deploy)
- Não escrever testes E2E para tokens de apresentação além do mínimo
- Não fazer refactor de helper, conftest ou fixture existente
- Não alterar vocabulário de eventos, payloads, estados, custódia ou regras clínicas
- Na 4E.2: não aceitar sugestão de refatoração `core` sem aprovação explícita de Fabiano

---

## §7 Sucesso da Etapa 4

A Etapa 4 fecha quando:

1. 4A, 4B, 4C, 4D.1, 4D.2, Task #8, OTP fix — ✅ (todos já commitados, pushados, verdes)
2. 4E.1 — ✅ (commit verde, regressão consolidada passa)
3. 4E.2 — ✅ (CODEX + Jules feedback integrado, P1 resolvidos, plano atualizado)
4. Memória atualizada
5. Avaliação do pacto registrada

Próxima etapa após 4E: **Etapa 5 — Fix B1 (carteira digital 422)** + bloqueadores pré-deploy.

---

## §10 Rodada 1 CODEX — feedback integrado (2026-05-13)

CODEX revisou o briefing v1 (rodada 0 do Arquiteto) e devolveu 3 achados. Classificação e integração pelo Arquiteto:

| # | Achado | Severidade | Decisão | Justificativa / Ação |
|---|---|---|---|---|
| 1 | `instance_id` foi tratado como ID de transação em C1–C5 (linhas 82, 94, 116, 139 do briefing v1). O contrato real (app/instance.py:4 + TICKET-4C §1) é UUID v4 inalterável, marca d'água da instalação. Testes assim falhariam ou empurrariam o código para semântica errada. | P1 — Bloqueador | ✅ **Aceito integralmente** | Erro material do Arquiteto. Reescrito §3 inteiro: adicionado §3.2 com semântica correta (5 invariantes I1–I5) e reescritos os cenários C1–C5 com invariantes que exigem `instance_id` **igual** entre transações de uma mesma instância, não diferente. C5 reformulado para validar `COUNT(DISTINCT instance_id) = 1` numa UNION dos 5 ledgers. |
| 2 | A migration 4B (`4b1ce80a017d`) adiciona `instance_id` em `prescricoes`, `pedidos_exame`, `laudos`, `agendamentos`, mas os models ORM (`prescricao.py:11`, `agendamento.py:9`, etc.) não mapeiam esse campo. Dívida documentada para Etapa 8, mas vale registrar explicitamente que a Etapa 4 deixa `instance_id` operacional nos ledgers/outbox, não nos objetos principais. | P2 — Relevante | ✅ **Aceito** | Adicionado §3.7 "Escopo do `instance_id` na Etapa 4" deixando explícito o que fica operacional na Etapa 4 e o que vai para Etapa 8. Alinha com decisão já registrada em 4D.1 e 4D.2. |
| 3 | Docstring de `backend/app/domain/outbox.py:6` afirma que "todo router que inserir em `*_eventos` **deve** chamar `registrar_outbox()`". A 4D deliberadamente não criou outbox novo para eventos sem outbox adjacente. Vale ajustar a docstring para "quando houver evento publicável / outbox previsto" para evitar falso requisito em revisões futuras. | P3 — Lapidação | ✅ **Aceito** (para a 4E.2, não 4E.1) | Mudança em código de produção (não em testes), fora do escopo estrito da 4E.1. Registrado em §4.6 como item pré-identificado para a onda de lapidações da 4E.2 (Regra 3). |

**Verificações independentes do CODEX (rodada 1):**

- `INSERT INTO *_eventos` manual em `backend/app`: zero (só sobrou em teste de imutabilidade, que é esperado) ✅
- `registrar_outbox()` em routers migrados passa `instance_id` ✅
- `registrar_evento_ledger()` em `backend/app` passa `instance_id` ✅
- pytest não executado nesta rodada (análise estática via `git diff` / `rg` / leitura)

**Status do briefing:** rodada 1 aceita pelo Arquiteto, integrada. Briefing pronto para ser usado como base do ticket completo da 4E.1 — próximo passo: Fabiano cola este briefing atualizado no CODEX para que ele redija o ticket completo (formato análogo a `TICKET-4D-2-LEDGER-INSTANCE-ID-SUBDOMINIOS.md`).

| Rodada | Origem | Pontos | Aceitos | Adaptados | Rejeitados |
|---|---|---|---|---|---|
| 0 | Arquiteto redigiu briefing v1 | — | — | — | — |
| 1 | CODEX revisou briefing v1 | 3 | 3 | 0 | 0 |
