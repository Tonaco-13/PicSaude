# Registro de Dívida Técnica — PicSaúde

> Atualizado em **2026-06-14**. Consolida o que foi **verificado** (não confiar em
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
| 🔴 | **SM1** terminal não-absorvente: item `resultado_disponivel` (pedido_exame) é terminal **e** transiciona p/ `encerrado` — **provável bug** (estado intermediário marcado terminal) | verificação formal (paper §VII) · `core` states_exame.py |
| 🟡 | **SM2** terminal não-absorvente: item `dispensado` → `estornado` (estorno) — tensão semântica "terminal=completo" × "terminal=absorvente"; intencional, formalização inconsistente | verificação formal (paper §VII) · `core` states.py |

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

---

## 7. Dívida de reuso / arquitetura
| | Item |
|---|---|
| 🔴 | **Hash canônico clonado 4×** (prescrição/laudo/encaminhamento/contrarreferência) em vez de `domain/documento_canonico.py` — chaves divergentes; é `core` (unificar com revisão central) |
| 🔴 | **M4 / resolver dispensador** faz `SELECT * prestadores` + filtra CNPJ em Python (não usa índice) **e** está duplicado em agendamentos/circulação/hospitalar/custódia — denormalizar/indexar + extrair p/ `helpers.py` |
| 🟡 | **M8** import local p/ evitar ciclo `medicamento↔catalogo_regulatorio` |
| 🟡 | `_cns_origem` recomputado no read (micro-opt) |
| 📋 | Cobertura focal de ledger (receituarios/hospitalares/assinaturas) | TICKET-COBERTURA-LEDGER-COMPLEMENTAR |
| ⚠️ | **Armadilha bool×integer** (coluna Boolean + literal `0/1`) passa em SQLite, quebra na PG — vigilância contínua; rodar gate PG nos 2xx |

---

## 8. Núcleo / pendências de plano (não-dívida, mas bloqueiam expansão)
- **Event Publishing Layer (G4A)** — `GET /eventos?since=…`, webhooks. Pré-requisito de **qualquer** adapter externo (HIS/TISS/HL7/e-SUS). Sem isso, adapters não têm onde conectar.
- **Enforcement via JWT institucional** (`org_id`/`unidade_id` no token) — habilita ownership nível-unidade (dispensação hospitalar, etc.).
- **Assinatura ICP-Brasil real** (hoje stub) — fronteira R6.
- **PDF da contrarreferência** (E2 follow-up — pura apresentação).

---

## 9. Verificados FALSOS na ultra-review 2026-06-14 (NÃO são dívida — não reabrir)
`C1` (deploy é Alembic) · `C4` (hash v1/v2 — premissa errada) · `H2` (XSS — valores não-controláveis) ·
`H3` (tokens commit-then-raise — só auditoria) · `H4` (`prescricoes` não tem `org_id`) ·
`H6` (NULL→409 explícito) · `H7` (sentinela é rejeitado na digital). Detalhe e prova em
`TICKET-ULTRAREVIEW-2026-06-14-TRIAGEM.md`.

---

*Mantido pelo Engenheiro-Chefe. Antes de agir em ❓, **verificar** (a ultra-review erra ~metade).
Antes de agir em 🔴 `core`, **martelo do Fabiano** + revisão central.*
