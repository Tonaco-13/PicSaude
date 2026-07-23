# Registro de Dívida Técnica — PicSaúde

> Atualizado em **2026-07-16**. Consolida o que foi **verificado** (não confiar em
> alegação de revisor automático — a ultra-review de 2026-06-14 teve 54% de falso-positivo
> nos críticos/altos). Cada item tem status e fonte.

**Legenda:** ✅ resolvido · 📋 ticketado · 🟡 by-design/aceito · 🔴 aberto-real ·
❓ alegado-não-verificado · ❌ falso (registrado p/ não reabrir)

---

## 0. Resolvido recentemente (sessões de junho/2026)
- ✅ Varredura de ownership **5C-BIS A–E** (pedido_exame, laudo, agendamento, circulação, hospitalar)
- ✅ **C.1** — schema institucional (`prestadores.org_id` + `unidades`) migrado p/ PG
- ✅ **E1/E2** — módulo Encaminhamento (referência + contrarreferência) completo
- ✅ **#15** — neutralização dos 4 `GET /public/*` (vazamento clínico LGPD Art. 11)
- ✅ **H5 / #18** — ownership em `devolver_item` (custodia.py)
- ✅ **H8 / #17** — outbox preserva traceback no swallow

---

## 1. Segurança / Ownership
| | Item | Fonte |
|---|---|---|
| 🔴 | **dispensa token-less direta**: `dispensar_item` não exige custódia quando não há token (só CNPJ==JWT). **Deprecar?** É decisão de produto/regulatória — `test_dispensa_sem_token_funciona` é contrato garantido | 5C-BIS-F §2 follow-up |
| 🟡 | **H1** `DEV_PRESET_CONTEXT=true` nos 3 HTML — auto-login dev (real, contra seed; JWT só em memória), mas flag **hardcoded** → prod exige flip manual | Etapa 6 (DEMO_MODE) |
| 🔴 | **Idempotência/lock** nas mutações de objetos sanitários — leitura-então-escrita sem `SELECT … FOR UPDATE`; double-submit concorrente pode duplicar (E1/E2/custódia). Cross-cutting | /code-review E2 |
| 🔴 | **`custodia.py:766`** — a reabertura de custódia na dispensação parcial (`_abrir_custodia(dispensador, "dispensacao_parcial")`) **não emite `custodia_transferida`** → abre custódia sem rastro no ledger. O **T6** (PR #84) CONTORNA lendo o histórico de `dispensacoes`/`estornos` (não de `prescricao_custodia`), então a dívida não sangra no histórico determinístico — **mas a dívida original segue aberta**. Solução definitiva: emitir `custodia_transferida` nesse caminho, mesmo padrão do fix T1.5 (`785aec4`). Não bloqueia a Fase 4. ⚠️ **`prescricao_custodia` NÃO está deprecated** — é fonte válida; o T6 apenas escolheu fonte alternativa por determinismo. | portão #83 + #84 |

- 📋 **Auditoria de tokens malformados (pós-R2).** O R2 passa a rejeitar `expira_em` malformado na
  escrita, mas não sana tokens já persistidos. Abrir ticket próprio: varredura + rota de invalidação
  de `tokens_apresentacao` com `expira_em` inválido. Não bloqueia R2. Origem: obs. transversal Z AI,
  parecer F5 2026-07-11.

---

## 2. Bloqueadores de deploy (`docs/PLANO-PRODUCAO-V2.md`)
| | Item |
|---|---|
| 🔴 | **Etapa 5** — Fix B1 (carteira digital 422) |
| 🔴 | **Etapa 6** — DEMO_MODE + seletor de papéis (resolve H1) |
| 🔴 | **Etapas 7–10** — Dockerfile · Deploy Render · Labels/issues · Teste E2E |
| 🔴 | **`estabelecimentos_cnes` ausente na PG** — login-prestador (caminho 200, cruzamento CNES) quebra; precisa carga/migração ou degradação graciosa | C.1 §7 |
| 🔴 | **DDL legado** `picsaude_ddl_postgres_v1.sql` diverge do Alembic (enums vs String). Deploy é Alembic (doc não quebra deploy), mas o `.sql` **engana** — marcar deprecado ou alinhar | C1 (triagem) |

---

## 3. Proteção de dados / LGPD
| | Item |
|---|---|
| ✅ | `/public/*` neutro (#15) |
| 🟡 | **H9** localStorage guarda objeto clínico completo (CPF, medicamentos) em claro — inerente ao fire-and-forget §6 (demo MVP); **revisitar antes de prod real** |
| ❓ | **M6** sem CSP headers nos HTML — frontend (Z AI) |
| 🟢 | Linha ética: **nunca** monetização de dado do paciente (guard-rail em `test_guardrail_sem_monetizacao.py`) — manter |

---

## 4. Correção / coerência de domínio
| | Item | Fonte |
|---|---|---|
| 📋 | **C2/C3** devoluções pulam `em_custodia` (pendente→devolvido_prescritor direto) | TICKET-COERENCIA-DEVOLUCOES · states.py:153 |
| 🔴 | **M1** `expira_em` malformado de token → `except (ValueError, TypeError): pass` trata como **não-expirado** (custodia.py:614) — **verificado real** | ultra-review |
| ❓ | **M2** `cancelada` auto quando todos itens terminais — conflata revogação clínica × término natural |
| ❓ | **M3** CNES indisponível → as 5 camadas de validação caem como `invalido` (sem degradação graciosa) |
| 📋 | **A.1** coerência `resultado→encerrado` (pedido_exame) | TICKET-5C-BIS-A.1 |
| 📋 | **B.1** correção de laudo cross-patient | TICKET-5C-BIS-B.1 |
| 📋 | **SM1 = TICKET-5C-BIS-A.1** — `resultado_disponivel` terminal torna `encerrar` inalcançável. **Corroborado independentemente** pela verificação formal (paper §VII, propriedade P2) — duas detecções por métodos distintos (gate PG + checagem de absorvência) | TICKET-5C-BIS-A.1 · `core` states_exame.py |
| 📋 | **SM2 → TICKET-ESTORNO-OBJETO-DERIVADO** — martelo de Fabiano (2026-06-15): estorno vira **objeto derivado** imutável (não transição `dispensado→estornado`). Resolve o SM2 tornando `dispensado` absorvente. Implementação `core` **adiada p/ pós-paper** (forks de domínio + desincronia com a §VII) | TICKET-ESTORNO-OBJETO-DERIVADO · `core` states.py |
| 🔴 | **CSV do auditor perde a unidade** (achado da triagem 2026-07-16, ao verificar o #96): `_SQL_BASE` **seleciona** `i.unidade_quantidade` (relatorios.py:57), o **PDF** a exibe em coluna própria (`Unidade` → "cápsula"), mas o **CSV** a descarta — `_CABECALHO` (relatorios.py:94) não tem a coluna e o `writerow` não a emite. Resultado: CSV traz `"21"` sem dizer 21 de quê, **divergindo do PDF gerado da mesma query**. Não é dado faltando no banco (o seed grava a unidade desde o #96) — é coluna perdida na serialização. Fix é aditivo (1 coluna no `_CABECALHO` + 1 campo no `writerow`), mas muda o contrato do CSV → merece a mesma fatia do DIVIDA-RELATORIO-AUDITOR abaixo, que já reescreve esse endpoint | triagem 2026-07-16 · relatorios.py:57,94 |
| 🔴 | **DIVIDA-RELATORIO-AUDITOR** (severidade **ALTA** — risco regulatório; registrado por parecer Z AI 2026-07-10): a visão do auditor `/relatorios/dispensacoes.{csv,pdf}` é **pré-T2/T5** — emite comprador=paciente (ignora `dispensacoes.comprador_*`) e **ignora `estornos`**, mostrando dispensação estornada como saída plena = **escrituração incorreta**. Enquanto coexistirem 2 endpoints de escrituração (dispensador correto pós-F5, auditor incorreto), o auditor confia no errado. Corrigir na fatia seguinte ao TICKET-F5-RELATORIO-SNGPC, reusando a mesma semântica de movimento/corte temporal | TICKET-F5-RELATORIO-SNGPC §1/§6 · relatorios.py:106,179 |

---

## 5. Saúde dos testes
| | Item |
|---|---|
| 🔴 | **~16 testes SQLite pré-existentes falhando** (confirmado com git stash, alheios às mudanças recentes): `test_binding_icp` (8 — parsing cert ICP), `test_g4b::TestEventosAutenticacao` (5 — integrador/api-key), `test_health`, `test_migration_4b_instance_id`, `test_string_validacao` |
| 🔴 | **`test_concorrencia.py`** — import quebrado (`DATABASE_URL_TEST` inexistente) → `--ignore` no CI |
| 🟡 | CI roda só `tests/unit` + seleção de integração; a suíte ampla SQLite **não** está no gate (por isso as ~16 falhas passam despercebidas) |

---

## 6. Observabilidade / ops
| | Item |
|---|---|
| ✅ | H8 outbox traceback (#17) |
| 🔴 | **M7** pool de DB hardcoded (`pool_size=10`, `max_overflow=20`) — não configurável por env (database.py) |
| ✅ | **Banco demo fora do controle de migração (#98)** — pago em 2026-07-19. `alembic/env.py` passou a resolver o path SQLite por `database._resolve_sqlite_db_path()`, honrando `PICSAUDE_DEMO_MODE` **e** `PIX_SAUDE_DB`. O demo nasce de `alembic upgrade head` (`alembic_version = f2b7c1d0a4e5`, 16 triggers do ledger). Ver "Como foi pago", abaixo. Origem: triagem 2026-07-16 |

**Detalhe do drift do banco demo** (verificado 2026-07-16 — registro histórico do defeito):

- `alembic/env.py:67-77` resolve o fallback SQLite com o path **hardcoded**
  `data/pix_saude_pe.db`, e **nunca** chama `database._resolve_sqlite_db_path()`.
  O comentário em `env.py:59` diz *"mesma lógica de database.py, sem duplicar código"* —
  mas ele **duplica** a lógica, e duplica **errado**: `database.py:27` devolve
  `PIX_SAUDE_DEMO_DB if PICSAUDE_DEMO_MODE else DB_PATH`; o `env.py` só conhece `DB_PATH`.
- Consequência medida: `pix_saude_pe.db` está em `alembic_version = d4e5f6a7b8c9`;
  `pix_saude_demo.db` **não tem a tabela** — o Alembic nunca o tocou. O schema do demo
  existe hoje por `init_tables.py` (`create_all` do ORM) + `CREATE TABLE IF NOT EXISTS`
  no próprio `seed_demo.py`, **não** pelas migrações.
- Por que arde: `create_all` reproduz o **estado final** dos models, mas não o que a
  migração faz **além** do DDL (backfill, transformação de dado, constraint via `op.execute`).
  Migração com data-fix não roda no demo — e o gate não pega, porque o gate roda em PG.
- Reparo (quando for a hora): fazer `env.py` importar `_resolve_sqlite_db_path()` em vez de
  reimplementá-la, e carimbar `alembic stamp head` no banco demo. É `ops`.

**Como foi pago** (2026-07-19):

- `env.py` importa `_resolve_sqlite_db_path()`. O comentário que prometia "sem duplicar
  código" desde sempre passou a ser verdade — era duplicação **com** divergência, o pior tipo.
- O defeito era **mais largo** do que a triagem mapeou: o `env.py` ignorava **duas**
  variáveis, não uma. `PIX_SAUDE_DB=/tmp/x.db alembic upgrade head` também migrava o banco
  de **dev**, em silêncio — quem rodava achando que mexia num efêmero mutava o dev real
  (aconteceu no TICKET-LEDGER-TRIGGERS-MIGRACAO).
- Precedência preservada, a de `database.py`: `DATABASE_URL` vence sempre. Produção a define
  e nunca entra no ramo SQLite — a mudança é prod-safe **por construção**, não por cuidado.
- `alembic stamp head` no demo **não foi necessário**: o demo é reconstruído do zero pela
  migração, que é mais forte que carimbar (carimbar afirmaria um schema que ninguém aplicou).
- Receita de reconstrução do demo, agora sem contorno manual:
  ```bash
  rm -f data/pix_saude_demo.db
  cd backend
  PICSAUDE_DEMO_MODE=true alembic upgrade head   # schema + 16 triggers do ledger
  PICSAUDE_DEMO_MODE=true python3 seed_demo.py
  ```
  `init_tables.py` continua opcional no meio, como **checagem** — não cria mais nada (§9).
- Travado por `tests/unit/test_alembic_env_resolve_db.py`: afirma o **destino** da migração
  nos quatro casos. Um path cravado de volta no `env.py` não vira erro — vira o banco errado
  sendo escrito, que só um teste de destino pega.

**Resíduo conhecido** (não bloqueia): o comentário em
`alembic/versions/a7b8c9d0e1f2_atestado_conformidade_cfm_cfo.py:39` ainda diz que "o banco
demo é create_all (dívida #98)". Migração mergeada **não se edita** (CLAUDE.md §9), nem para
corrigir comentário — o defensivo `_column_exists()` que ele justifica continua correto e
inofensivo.

---

## 7. Dívida de reuso / arquitetura
| | Item |
|---|---|
| 🔴 | **Hash canônico clonado 4×** (prescrição/laudo/encaminhamento/contrarreferência) em vez de `domain/documento_canonico.py` — chaves divergentes; é `core` (unificar com revisão central) |
| 🔴 | **M4 / resolver dispensador** faz `SELECT * prestadores` + filtra CNPJ em Python (não usa índice) **e** está duplicado em agendamentos/circulação/hospitalar/custódia — denormalizar/indexar + extrair p/ `helpers.py` |
| 🟡 | **M8** import local p/ evitar ciclo `medicamento↔catalogo_regulatorio` |
| 🟡 | `_cns_origem` recomputado no read (micro-opt) |
| 📋 | Cobertura focal de ledger (receituarios/hospitalares/assinaturas) | TICKET-COBERTURA-LEDGER-COMPLEMENTAR |
| 📋 | **`protocolo_raiz` (R3) só para prescrição** — a walk de linhagem-mãe (`origem_prescricao_id`) só é projetada no relatório SNGPC. Laudo/encaminhamento/contrarreferência **têm** `origem_*_id`, mas **nenhum relatório** hoje. Generalizar a resolução de raiz (motor `resolver_protocolo_raiz` + fetch de fecho transitivo) para os demais objetos é **ticket próprio** quando cada um ganhar relatório. Ref: TICKET-R3-PROTOCOLO-RAIZ |
| ⚠️ | **Armadilha bool×integer** (coluna Boolean + literal `0/1`) passa em SQLite, quebra na PG — vigilância contínua; rodar gate PG nos 2xx |

---

## 7-A. Aguardando norma externa (não é dívida de código — é dívida regulatória)
| | Item | Fonte |
|---|---|---|
| 📋 | **Atestado de enfermagem (COFEN)** — `domain/conselho_profissional.py` nasce com **CFM** e **CFO** apenas. Enfermagem ficou **deliberadamente fora** do TICKET-ATESTADO-CONFORMIDADE (decisão do Fabiano): a norma que define competência e alcance do atestado de enfermagem está pendente, e implementar antes dela seria inventar regra sanitária no código. Quando a norma sair, o custo é **uma entrada** em `CONSELHOS` (id `COFEN`, sigla `COREN`, título e adjetivos) — sem migração, sem tocar PDF nem tela, porque ambos já perguntam ao catálogo. Nota: o cadastro do profissional **já aceita** `COREN` em `TIPOS_CONSELHO` (prescritor.html); nesse caso o seletor de conselho do atestado fica em branco e o documento sai como legado (ATESTADO MÉDICO) — comportamento intencional até a norma existir | TICKET-ATESTADO-CONFORMIDADE · `domain/conselho_profissional.py` |

---

## 8. Núcleo / pendências de plano (não-dívida, mas bloqueiam expansão)
- **Event Publishing Layer (G4A)** — `GET /eventos?since=…`, webhooks. Pré-requisito de **qualquer** adapter externo (HIS/TISS/HL7/e-SUS). Sem isso, adapters não têm onde conectar.
- **Enforcement via JWT institucional** (`org_id`/`unidade_id` no token) — habilita ownership nível-unidade (dispensação hospitalar, etc.).
- **Assinatura ICP-Brasil real** (hoje stub) — fronteira R6.
- **PDF da contrarreferência** (E2 follow-up — pura apresentação).

---

## 8-A. Falhas de integração PRÉ-EXISTENTES (ambiente/seed — não são regressão)

Registradas no COER-2 (2026-07-23): ao rodar `tests/integration/` contra PG efêmero, **9 testes
falham independentemente das mudanças** (provado com `git stash` — falham idênticos na `main`
`005ae9b`). Não são bug de código; dependem de **seed de catálogo regulatório / numeração SNCR /
estado de laudo** que o PG efêmero não popula. Documentado aqui para o gate não confundir com
regressão nem re-descobrir a cada PR.

| Teste | Causa provável |
|---|---|
| `test_catalogo_regulatorio.py::test_endpoint_catalogo_autocomplete_semaglutida` | catálogo regulatório não seedado (semaglutida/amoxicilina ausentes) |
| `test_catalogo_regulatorio.py::test_endpoint_catalogo_autocomplete_amoxicilina` | idem |
| `test_catalogo_regulatorio.py::test_gerar_inclui_alerta_critical_quando_antimicrobiano_sem_classificacao` | idem (alertas dependem do catálogo) |
| `test_catalogo_regulatorio.py::test_gerar_alerta_warning_para_classe_344_ausente` | idem |
| `test_catalogo_regulatorio.py::test_catalogo_nao_bloqueia_emissao` | idem |
| `test_catalogo_regulatorio.py::test_atomizacao_bloqueada_por_catalogo` | idem |
| `test_catalogo_regulatorio.py::test_atomizacao_glp1_bloqueada_por_catalogo` | idem |
| `test_regras_receituario.py::test_validar_emissao_receituario_ok` | numeração SNCR / regra de receituário |
| `test_4d2_instance_id_ledger.py::test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` | fluxo de laudo/ciência (seed) |

> Colateral: `tests/integration/test_concorrencia.py` tem **erro de coleta** pré-existente
> (`ImportError: DATABASE_URL_TEST`) — importa símbolo que não existe no `conftest`. Também na `main`.
> Ação futura (fora do COER-2): corrigir o import ou remover o teste órfão.

---

## 9. Verificados FALSOS na ultra-review 2026-06-14 (NÃO são dívida — não reabrir)
`C1` (deploy é Alembic) · `C4` (hash v1/v2 — premissa errada) · `H2` (XSS — valores não-controláveis) ·
`H3` (tokens commit-then-raise — só auditoria) · `H4` (`prescricoes` não tem `org_id`) ·
`H6` (NULL→409 explícito) · `H7` (sentinela é rejeitado na digital). Detalhe e prova em
`TICKET-ULTRAREVIEW-2026-06-14-TRIAGEM.md`.

---

*Mantido pelo Engenheiro-Chefe. Antes de agir em ❓, **verificar** (a ultra-review erra ~metade).
Antes de agir em 🔴 `core`, **martelo do Fabiano** + revisão central.*
