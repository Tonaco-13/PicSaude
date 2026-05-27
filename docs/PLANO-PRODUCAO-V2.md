# Plano de Produção do PicSaúde — v2 (pós-revisão CODEX)

> Versão consolidada do plano de 10 etapas para subir o PicSaúde a produção, com integração das revisões do ciclo multi-AI.
>
> **Classe (CLAUDE.md §10):** `docs`
>
> **Versão:** 2.1 (2026-05-26 — Etapa 5C-bis inserida)

---

## Contexto

O PicSaúde tem backend funcional (146 testes passando) e precisa subir para URL pública demo + repositório GitHub aberto a contribuidores. O plano original tem 10 etapas. Esta v2 incorpora as revisões dos seguintes agentes:

- **Z AI** — UX clínica, integração frontend↔backend, faseamento de tickets
- **Engenheiro-Chefe (Claude)** — encaixe arquitetural, classificação de mudanças, ledger e custódia
- **CODEX** (novo no ciclo, 2026-05-06) — revisão estática do código backend; identifica vulnerabilidades, dívida técnica e cobertura de testes

A revisão CODEX expandiu **Etapa 5** (adicionou fixes de segurança crítica) e **Etapa 9** (expandiu de 7 para 12 issues `good-first-issue`).

---

## Status atual (2026-05-27)

| Etapa | Status | Notas |
|---|---|---|
| 1 — `.gitignore` + `git init` + commit inicial | ✅ Feito | commit inicial `9d15a3f` em 2026-05-06 |
| 2 — `gh repo create` | ✅ Feito | Remote `Tonaco-13/PicSaude` ativo (privado) |
| 3 — 7 arquivos de licenciamento | ✅ Feito | LICENSE (AGPL-3.0 + preâmbulo), README, CONTRIBUTING, CONTRIBUTOR-LICENSE, COMMERCIAL-LICENSE, DATA-PROTECTION, DISCLAIMER — todos na raiz |
| 4 — `instance_id` canônico | ✅ **Fechada (2026-05-21)** | **4A** ✅ `d8abf7e`, **4B-prequel** ✅ `2dce4f8`, **4B** ✅ `89f064a`, **4C** ✅ `2fbcf43`+`983359f`, **4D.1** ✅ `60382d2`+`0056c93`, **4D.2** ✅ `3db4060`+`79f2f4f`, **4E.1** ✅ `65181dc`+`a53d5ba`, **4E.2** ✅ `ab1c897` (CODEX+Jules + tickets) + `9ef3bb2` (fix custódia, vocabulário canônico + ator JWT) + `9cc339f` (batch lapidações pós-Regra 5). Critérios §7 do `TICKET-4E-2-RELATORIO-INTEGRADO.md` cumpridos. 124 testes verdes. |
| 5 — Bloqueadores pré-deploy | ✅ **Fechada (2026-05-24)** | **5A** ✅ `e09dc3e`+`66547e4`+`f82b0da`, **5B** ✅ `5fa6902`, **5C** ✅ `01c67fa`+`b020770` (CODEX rodada 2 zero P1; 3 follow-ups #52/#53/#54 em §11 do ticket), **5D** ✅ `6ff6910`. Ver §5 abaixo. |
| 6 — `DEMO_MODE` + seletor de papéis | ✅ **Fechada (2026-05-27)** | **TICKET-6** ✅ `94f73cd` (feat demo mode + 7 decisões), **TICKET-6.1** ✅ `9eb7228` (3 P1 + 2 P2 da CODEX rodada 2), arquivamento `a01fec6`, **TICKET-DX-PRE-EXTENSAO** ✅ `5db20ef` (Jules audit P2#4 + P2#10), **TICKET-6.2** ✅ `6c0da36` (3 fixes pré-reunião: CNES graceful + rate limit demo + UUID/REC no comprovante). CODEX rodada 3 zero P1; 1 P2 de calibração documental do Fix C (não bug — fire-and-forget). Ver §11 do TICKET-6. |
| 5C-bis — Autorização nos 5 subdomínios sucessores | ⛔ **Próximo bloqueador** | **Decisão de 2026-05-26.** MVP ampliado para incluir exames, agendamentos, laudos, hospitalar e circulação antes do deploy público. Spike TICKET-5C-BIS-0 (v0.2 após CODEX rodada 0) + 5 tickets A-E paralelos. Ver §5C-bis abaixo. |
| 7 — Dockerfile | ⛔ Não feito | |
| 8 — Deploy Render + frontend Cloudflare | ⛔ Não feito | |
| 9 — Labels + issues `good-first-issue` | ⛔ Não feito | **Expandido para 12 issues — ver §9 abaixo** |
| 10 — Teste E2E URL pública | ⛔ Não feito | |
| TICKET-PACIENTES-CARTEIRA-INFO-DISCLOSURE | ⛔ Pré-Etapa 8 | Information disclosure em `/pacientes/{cpf}/carteira` (qualquer prescritor autenticado descobre se CPF tem conta). Fora do 5C-bis (LGPD/UX, não ownership clínico). Fecha antes da URL pública. |

---

## Decisões consolidadas (não reabrir)

- **TICKET-70 spec v1.5** congelada em `docs/TICKET-70-SPEC.md`. Implementação só após Etapa 4 concluída e MVP no ar.
- **AGPL-3.0 pura na LICENSE.** Restrições de dados ficam fora — em DATA-PROTECTION.md e contrato comercial.
- **Sem vínculo formal com UFPE.** Projeto é propriedade pessoal de Fabiano Tonaco Borges. UFPE pode entrar futuramente como hospedeira/operadora, não como co-titular.
- **Seletor de papéis (Demo) sem credenciais hardcoded.** Variável `DEMO_MODE=true` é único gatilho.
- **Fix B1 (carteira digital):** retorna 422 com `{detail: "patient_no_digital_wallet", ...}`. Sem silenciamento.
- **CPF sentinela `00000000000`** + máscara de CPF: issue redigida em `docs/issues/ISSUE-mascara-cpf.md`.
- **Modelo de licenciamento comercial:** Caminho 2 (Opção A fixa por porte + Opção B com piso R$15k/teto R$600k + 7 sub-cláusulas de salvaguarda).
- **MVP estendido antes do deploy público (2026-05-26):** o deploy do Render (Etapa 8) incluirá autorização mínima fechada nos 5 subdomínios sucessores do 5C (exames, laudos, agendamentos, circulação diagnóstica, hospitalar), não apenas o ambulatorial. Coerência com a essência do PicSaúde como plataforma de circulação de objetos sanitários (receitas + agendamentos + pedidos de exame). Operacionalizada na **Etapa 5C-bis** (entre Etapa 6 e Etapa 7). Carteira de paciente fica como ticket independente entre Etapas 7 e 8.

---

## Etapa 5 — Bloqueadores pré-deploy (expandida)

A Etapa 5 agora consolida **três fixes obrigatórios** antes do deploy público (Etapa 8). Todos foram identificados como bloqueadores reais — pelo plano original (B1) e pela revisão CODEX (5B, 5C).

### 5A — Falhar explicitamente entrega digital solicitada sem carteira do paciente — ✅ RESOLVIDO em `e09dc3e` + `66547e4` (2026-05-21) + P2 follow-up `f82b0da` (2026-05-23)

**Problema:** frontend envia `enviar_ao_paciente=true` e backend silencia quando paciente não tem carteira digital. Viola rastreabilidade RDC 1.000/2025 e o princípio `CLAUDE.md §3` (backend é fonte de verdade).

**Decisão semântica (corrigida em 2026-05-22):** `HTTP 422 patient_no_digital_wallet` é **rejeição da emissão**, não aviso. O `HTTPException` faz rollback efetivo: nenhuma prescrição/pedido é gravado, nenhum paciente novo é auto-criado. O frontend exibe escolha consciente: (a) re-emitir com `enviar_ao_paciente=false`; ou (b) cadastrar/vincular o paciente antes.

**Escopo:** o mesmo padrão silencioso aparece em `POST /prescricoes` E em `POST /pedidos_exame` — ambos endereçados no mesmo ticket (`backend/docs/tickets/TICKET-5A-CARTEIRA-DIGITAL-422.md`).

**Fix:**

```python
# Logo após determinar paciente_existia, antes do INSERT OR IGNORE em pacientes:
if payload.enviar_ao_paciente and not paciente_existia:
    raise HTTPException(
        status_code=422,
        detail={
            "codigo": "patient_no_digital_wallet",
            "patient_id": cpf,
            "message": (
                "Paciente sem carteira digital disponível. "
                "Emissão rejeitada porque a entrega digital solicitada não é possível. "
                "Reemita com enviar_ao_paciente=false ou cadastre o paciente antes."
            ),
        },
    )
```

**Inferência atual** (CLAUDE.md §3.1 do ticket 5A): "paciente sem carteira digital" = `paciente_existia == False`. Quando o modelo de carteira digital evoluir (autenticação, vínculo verificável), revisitar.

**Testes obrigatórios (6 — 3 prescricoes + 3 pedidos_exame):**
- Paciente novo + `enviar_ao_paciente=true` → 422 com payload correto; zero linhas em `prescricoes`/`pedidos_exame` e zero linhas novas em `pacientes` (prova de rollback).
- Paciente cadastrado + `enviar_ao_paciente=true` → 200 (entrega ocorre, custódia criada).
- Paciente novo + `enviar_ao_paciente=false` → 200 (paciente auto-criado normalmente, sem tentar entregar).

### 5B — Fix segurança OTP (CRÍTICO + ALTO 1 do CODEX) — ✅ RESOLVIDO em `5fa6902` (2026-05-12)

**Status:** ambos os achados fechados via Regra 3 (Edit direto), com 2 rodadas
de revisão CODEX (4 achados rodada 1 + 4 da rodada 2, sobrepostos parcialmente).
Bloqueador pré-Etapa 8 **removido**.

**Como foi resolvido:**

- **CRÍTICO**: guard `if os.getenv("PICSAUDE_ENV") in ("dev", "test"):` em
  `auth.py:74` e `login.py:345`. **Sem fallback `"dev"`** (safe-by-default —
  deploy sem env configurada NÃO vaza OTP em stdout — lapidação CODEX rodada 2).
- **ALTO**: `random.randint(100000, 999999)` substituído por
  `secrets.randbelow(900000) + 100000` em `auth.py:48` e `login.py:324`
  (mesmo range 100000-999999, mesma cardinalidade, PRNG criptográfico).
- **Cobertura**: 3 testes novos em `tests/test_auth_paciente.py::TestOtpPrintGuard`:
  `test_otp_nao_imprime_em_prod`, `test_otp_nao_imprime_sem_env`,
  `test_otp_imprime_em_dev`.

**Problemas identificados (histórico):**

1. **CRÍTICO:** `auth.py:70` e `login.py:343` — OTP impresso em `stdout` sem guard de ambiente. Em produção, vai para os logs do Render — qualquer pessoa com acesso ao painel captura código de autenticação ativo.

2. **ALTO:** `auth.py:46` e `login.py:324` — OTP gerado com `random.randint`, PRNG não-criptográfico, previsível com sementes recuperáveis.

**Fix CRÍTICO:**

```python
# Antes:
print(f"OTP gerado para {cpf_mascarado}: {otp}")

# Depois:
if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
    print(f"[DEV] OTP gerado para {cpf_mascarado}: {otp}")
# Em produção: enviar via canal real (SMS/email) ou logger configurado a só emitir em DEBUG
```

**Fix ALTO:**

```python
# Antes:
import random
otp = str(random.randint(100000, 999999))

# Depois:
import secrets
otp = str(secrets.randbelow(900000) + 100000)
```

**Testes obrigatórios:**
- OTP gerado em ambiente de produção **não** aparece em `stdout`
- OTP gerado tem entropia criptográfica (validar com `secrets.SystemRandom` ou medir colisões em N=10000)
- Guard de ambiente respeita `PICSAUDE_ENV` corretamente (dev/test → imprime, prod → silencia)

### 5C — Autorização mínima em endpoints clínicos centrais — ✅ RESOLVIDO em `01c67fa` + `b020770` (2026-05-23/24)

**Reformulação importante (2026-05-23):** a auditoria de gap do plano original revelou que **o problema não era cobertura de teste faltante — eram vulnerabilidades ativas de autorização** em 11 endpoints clínicos centrais. A maioria descartava o `usuario` (`_=Depends(require_role(...))`), 1 não tinha autenticação (`GET /custodia`), e 1 capturava o usuário mas não fazia owner check antes de upsert + evento de ledger (`POST /assinatura`).

**Achado central CODEX:** "O maior gap não é 'transição inválida', é endpoint crítico ignorando o ator autenticado."

**Resultado:** ticket `TICKET-5C-AUTORIZACAO-MINIMA.md` redigido com 11 vulnerabilidades (V1-V11) em 5 routers (`prescricoes`, `custodia`, `validacao`, `assinaturas`, `dispensacoes`), 17 cenários de teste, 3 ciclos CODEX integrados antes do Code (rodada 1 + varredura `_=Depends` + rodada 1.5) e CODEX rodada 2 (pós-impl) zero P1.

**Implementação:**
- `01c67fa` — fix de produção + 17 testes (1.207 inserções, 31 deleções, 15 arquivos)
- `b020770` — ticket consolidado pós-impl com §11 preenchido

**Follow-ups abertos:** #52 (P2 info disclosure 400 vs 403 em prescrição física), #53 (P3 V6 instance_id antes dos checks), #54 (P3 V9 TOCTOU teórico). Nenhum bloqueia deploy ambulatorial.

**Tickets sucessores abertos** (fora do MVP ambulatorial): #47 exames+agendamentos, #48 laudos, #49 hospitalar, #50 circulação diagnóstica, #51 carteira paciente.

**Critério de aceitação atingido:** 5 routers críticos com owner check inline; 17/17 testes focais verdes; suite completa sem regressão; CODEX rodada 2 zero P1.

### 5D — Guard de produção para JWT_SECRET (descoberto em 2026-05-06)

**Problema identificado** durante o dry-run de privacidade pré-commit inicial:

`backend/app/config.py` linha ~33:

```python
JWT_SECRET: str = os.getenv("PICSAUDE_JWT_SECRET", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32")
```

A string default `"TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"` é claramente marcada como placeholder, mas vai para o GitHub junto com o código. Se o operador deployar em produção esquecendo de setar `PICSAUDE_JWT_SECRET`, o sistema roda com essa chave pública — qualquer pessoa que clone o repositório pode **forjar tokens JWT válidos** para qualquer usuário/papel.

**Não bloqueia o commit inicial** (repo é privado, default é claramente placeholder). **Bloqueia o deploy público (Etapa 8).**

**Fix:**

```python
# backend/app/config.py

JWT_SECRET: str = os.getenv("PICSAUDE_JWT_SECRET", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32")

# Guard de produção: aborta boot se em prod com chave default
if os.getenv("PICSAUDE_ENV") == "prod" and JWT_SECRET.startswith("TROQUE_EM_PRODUCAO"):
    raise RuntimeError(
        "PICSAUDE_JWT_SECRET não pode ser a chave padrão em produção. "
        "Gere com: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    )
```

**Testes obrigatórios:**

- Boot com `PICSAUDE_ENV=prod` e `PICSAUDE_JWT_SECRET` não definida → `RuntimeError`
- Boot com `PICSAUDE_ENV=prod` e `PICSAUDE_JWT_SECRET="TROQUE_EM_PRODUCAO_..."` → `RuntimeError`
- Boot com `PICSAUDE_ENV=prod` e `PICSAUDE_JWT_SECRET=<32-byte-hex>` → sucesso
- Boot com `PICSAUDE_ENV=dev` e default → sucesso (silencioso)
- Boot com `PICSAUDE_ENV=test` e default → sucesso (silencioso)

**Estimativa original:** 5D trivial (~30 minutos); 5B trivial (~2h); 5C ~1 dia; Etapa 5 inteira ~2 dias.

**Realidade (fechamento 2026-05-24):** 5B fechado em 12/05 (`5fa6902`); 5D fechado em 22/05 (`6ff6910`); 5A fechado em 21/05 + P2 follow-up em 23/05; 5C consumiu 3 dias (23–24/05) por causa da reformulação semântica de "cobertura de teste" para "vulnerabilidades ativas" — 11 vulnerabilidades cobertas, 3 ciclos CODEX pré-impl + rodada 2 pós-impl, zero P1 na entrega.

**Etapa 5 fechada em 2026-05-24. Etapa 6 fechada em 2026-05-27.** Próximos bloqueadores em ordem: **Etapa 5C-bis** (autorização nos 5 subdomínios sucessores — decisão 2026-05-26) → Etapa 7 (Dockerfile) → Etapa 8 (Deploy Render) → Etapa 9 (labels + issues) → Etapa 10 (E2E URL pública).

---

## Etapa 5C-bis — Autorização mínima nos 5 subdomínios sucessores (decidida 2026-05-26)

A Etapa 5C fechou autorização mínima no MVP **ambulatorial** (11 endpoints clínicos em `prescricoes`, `custodia`, `validacao`, `assinaturas`, `dispensacoes`). Os endpoints equivalentes em **exames, laudos, agendamentos, circulação diagnóstica e hospitalar** seguem com o padrão vulnerável (`_=Depends(require_role(...))`) — 30 endpoints distribuídos em 5 routers, identificados em varredura de 2026-05-26.

### Motivação da inserção entre Etapa 6 e Etapa 7

A definição operacional do PicSaúde formalizada por Fabiano em 2026-05-26 é **plataforma de circulação de objetos sanitários (receitas, agendamentos, pedidos de exame) com normalização na ponta, auditável e 100% transparente, onde a beleza é o retorno integral ou atômico**. Subir o demo público (Etapa 8) com exames, agendamentos e laudos visíveis na UI mas com autorização semi-aberta seria incoerente com essa definição. Decisão: fechar autorização nos 5 sucessores antes do deploy.

### Estrutura: spike + 5 tickets paralelos

| Ticket | Subdomínio | Volume estimado | Status |
|---|---|---|---|
| **TICKET-5C-BIS-0** | Spike avaliativo do helper compartilhado de ownership | ~150 linhas de ADR | 🔄 v0.2 (CODEX rodada 0 integrada 2026-05-26); amadurece quinta 28/05 com leitura concreta dos 5 routers |
| TICKET-5C-BIS-A | `pedidos_exame.py` | 11 endpoints | ⛔ Após spike fechar |
| TICKET-5C-BIS-B | `laudos.py` | 11 endpoints | ⛔ Após spike (paralelo a C) |
| TICKET-5C-BIS-C | `agendamentos.py` | 6 endpoints | ⛔ Após spike (paralelo a B) |
| TICKET-5C-BIS-D | `circulacao_diagnostica.py` | 1 endpoint + auditoria de matriz | ⛔ Após spike (pode rodar com C) |
| TICKET-5C-BIS-E | `hospitalares.py` | 1 endpoint + absorve TICKET-5C-FOLLOWUP-CUSTODIA-HOSPITALAR (§7.1 do 5C) | ⛔ Último — complexidade `detentor_id = unidade_id` |

Carteira de paciente (`/pacientes/{cpf}/carteira`) **não entra no 5C-bis** — é information disclosure (LGPD/UX), não ownership clínico. Ticket próprio entre Etapa 7 e Etapa 8.

### Spike TICKET-5C-BIS-0 — decide A/B/C

O spike avalia se faz sentido extrair um helper compartilhado de ownership (`_assert_or_403` ou similar) ou se cada subdomínio deve manter checagem local. Output é a `ADR-002-OWNERSHIP-HELPER.md` (cria a pasta `backend/docs/decisoes/` no commit; ADR-001 está embutida no relatório 4E-2).

Três opções estruturadas:
- **A — helper completo** (atende ≥ 4 classes de operação com ≤ 2 parâmetros por classe)
- **B — manter local** (helper viraria builder)
- **C — helper mínimo** (`_assert_or_403` compartilhado + queries locais de ownership) — registrado como **cenário mais provável** pelo parecer CODEX rodada 0 de 2026-05-26

A decisão é vinculante para os 5 tickets A-E e não revisitada.

### Participação dos extensionistas UFPE

Os 7 extensionistas (reunião 27/05) entram no 5C-bis como atividade real de QA + validação semântica desde a semana 1, com calibração por formação:

- **Sanitaristas júnior (sem código)** — papel pleno em QA: rodar testes, ler reviews CODEX, discutir matriz de ownership com perspectiva clínica (quem deve ler um laudo, em que momento, sob qual vínculo).
- **Quem programa** — após decisão A/B/C, pode pegar endpoints individuais sob mentoria sincronizada (Arquiteto + Code revisam JUNTOS antes do CODEX), limitado a 1-2 endpoints por extensionista programador, nunca em transferência de custódia ou metadados de assinatura.

Calibração precisa fechar após reunião 27/05 quando as formações dos 7 forem conhecidas.

### Estimativa

O 5C levou ~5-7 dias úteis (rodada 0 + 3 ciclos CODEX pré-impl + impl + rodada 2 zero P1). O 5C-bis tem 3x o volume mas herda padrão estabelecido — estimativa: **2-3 semanas** para fechar os 5 tickets, com extensionistas integrados a partir da semana 2.

---

## Etapa 9 — Labels + issues `good-first-issue` (expandida)

A Etapa 9 agora cria **12 issues** (eram 7), das quais **5 são novas a partir da revisão CODEX**.

### Issues do plano original

| # | Título | Tipo |
|---|---|---|
| 1 | Adicionar máscara de CPF (XXX.XXX.XXX-XX) com tratamento do sentinela de não-identificação | UI puro — ideal first PR (issue já redigida em `docs/issues/ISSUE-mascara-cpf.md`) |
| 2 | Adicionar validação de dígitos verificadores de CPF no formulário de paciente | Backend simples |
| 3 | Escrever teste para prescrição com medicamento não encontrado no catálogo | pytest, caminho infeliz |
| 4 | Criar página estática "Sobre o PicSaúde" | HTML/CSS — first PR ideal para quem nunca usou Git |
| 5 | Adicionar loading spinner nos botões de emissão/dispensação | Estados de UI |
| 6 | Adicionar contador de prescrições emitidas no dashboard do prescritor | Query agregada + UI |
| 7 | Melhorar mensagens de erro em português nos endpoints | Middleware |

### Issues novas da revisão CODEX

| # | Título | Origem | Dificuldade |
|---|---|---|---|
| 8 | **Limpeza:** remover 66 imports não utilizados em `backend/` (`ruff check --fix --select F401`) | CODEX INFO 4 | Trivial — first PR ideal |
| 9 | Adicionar cobertura de testes para `routers/laudos.py` | CODEX ALTO 2 | Médio |
| 10 | Adicionar cobertura de testes para `routers/relatorios.py`, `routers/assinaturas.py` e `routers/validacao.py` | CODEX ALTO 2 | Médio |
| 11 | Adicionar cenários negativos (401/403/422/409) em `tests/test_prescricoes_contexto_clinico.py` | CODEX MÉDIO 2 | Trivial |
| 12 | Refactor `except Exception` em `assinatura_icp.py:214`, `pdf_assinatura.py:164`, `prescricoes.py:622` — substituir por exceções específicas | CODEX MÉDIO 1 | **Avançado — `module`, não `good-first-issue`** |

### Labels

```bash
gh label create "good first issue" --color 7057ff --description "Bom para estudantes iniciantes"
gh label create "bug" --color d73a4a
gh label create "feature" --color 0075ca
gh label create "docs" --color 0e8a16
gh label create "frontend" --color f9d0c4
gh label create "backend" --color 1d76db
gh label create "security" --color b60205 --description "Segurança — requer revisão do coordenador"
gh label create "regulatorio" --color fbca04 --description "Conformidade regulatória (Anvisa, LGPD)"
gh label create "module" --color 5319e7 --description "Toca módulo arquitetural — exige revisão central"
```

---

## Pós-implementação (não bloqueia MVP)

Itens identificados pelo CODEX que **não vão para issues agora**:

- Cobertura completa de testes para as 56 rotas sem teste — vira projeto de extensão futuro
- Refactor profundo dos 34 `except Exception` genéricos — issue isolada para revisão arquitetural depois
- Adicionar type hints completos nas 136 funções públicas que não têm — vira sweep coletivo após MVP estável

---

## Recomendações de processo multi-AI

A entrada do CODEX no ciclo de revisão evidenciou padrão útil: cada revisor tem lente diferente.

| Revisor | Lente | Quando consultar |
|---|---|---|
| **Engenheiro-Chefe (Claude)** | Encaixe arquitetural, classe de mudança, ledger/custódia | Sempre, em todo ciclo |
| **Z AI** | UX clínica, integração frontend↔backend, faseamento de tickets | Em desenho de feature antes de implementar |
| **ChatGPT (Senior)** | Segurança, jurídico, edge cases conservadores | Em mudanças jurídicas (licenças, CLA, contratos) |
| **Gemini 2.5 Pro** | Pragmatismo, performance, DX | Em decisões de stack ou simplificação |
| **CODEX** | Revisão estática de código, vulnerabilidades, cobertura | Após Etapa 5 (verificar fixes) e após Etapa 8 (verificar deploy) |

**Regra:** spec consolidada (como TICKET-70 v1.5) vira ponto de partida para revisores subsequentes — não repetem o caminho, só verificam buracos nas lentes deles.

---

## Histórico de revisão

| Versão | Data | Mudança |
|---|---|---|
| 1.0 | 2026-05-04 | Plano inicial de 10 etapas (prompt do Opus 4.7) |
| 1.1 | 2026-05-05 | Revisão Z AI — 8 pontos incorporados (B1 bloqueador, seletor de papéis, contrato carteira digital, etc.) |
| 1.2 | 2026-05-05 | TICKET-70 spec v1.5 consolidada |
| 1.3 | 2026-05-06 | Sem UFPE — projeto como propriedade pessoal de Fabiano |
| **2.0** | **2026-05-06** | **Revisão CODEX integrada — Etapa 5 expandida (B1 + Fix OTP + testes mínimos de autorização), Etapa 9 expandida (7 → 12 issues)** |
| **2.1** | **2026-05-26** | **Etapa 5C-bis inserida entre Etapa 6 e Etapa 7 — MVP estendido para incluir autorização nos 5 subdomínios sucessores (exames, laudos, agendamentos, circulação diagnóstica, hospitalar) antes do deploy público. Coerência com definição do PicSaúde como plataforma de circulação de objetos sanitários. Spike TICKET-5C-BIS-0 v0.2 (CODEX rodada 0 integrada) + 5 tickets A-E paralelos. Extensionistas UFPE entram como QA + validação semântica desde semana 1. Carteira de paciente vira ticket independente entre 7 e 8.** |
| **2.2** | **2026-05-27** | **Etapa 6 fechada formalmente.** 4 commits (`94f73cd` + `9eb7228` + `a01fec6` + `5db20ef` + `6c0da36`). 3 rodadas CODEX + Jules-audit + 3 ciclos de fix. Calibração P2 Fix C documentada como achado pedagógico (critério §3.4 do TICKET-6.2 incoerente com contrato fire-and-forget do CLAUDE.md §6 — corrigido). Relatório HTML em `docs/relatorios/RELATORIO-FECHAMENTO-ETAPA-6.html`. Próximo bloqueador: Etapa 5C-bis. |

---

## Apêndice — Relatório CODEX integral (2026-05-06)

```
CRÍTICO
1. backend/app/routers/auth.py:70 e backend/app/routers/login.py:343
   OTP de login impresso em stdout sem guard de ambiente.
   Sugestão: impedir execução fora de PICSAUDE_ENV=dev/test, ou usar canal real.

ALTO
1. backend/app/routers/auth.py:46 e backend/app/routers/login.py:324
   OTP gerado com random.randint, inadequado para autenticação.
   Sugestão: secrets.randbelow() ou secrets.choice().
2. Cobertura de endpoints incompleta: 56 de 117 rotas sem teste correspondente.
   Destaques: routers/laudos.py inteiro sem cobertura; também faltam assinaturas,
   validacao, relatorios, parte de custodia, pedidos_exame e endpoints públicos.

MÉDIO
1. 34 except Exception genéricos. Destaques: assinatura_icp.py:214,
   pdf_assinatura.py:164, prescricoes.py:622.
2. tests/test_prescricoes_contexto_clinico.py:91 — só cobre 201,
   sem 401/403/422/409.

INFORMATIVO
1. Sem .pfx/.p12/.pem/.key/.crt/.cer em backend/.
2. Sem import bugado pyhanko.sign.general.SimpleSigner.
3. requirements.txt usa pyhanko==0.34.1 sem extra [pkcs12], correto.
4. 66 imports possivelmente não utilizados (AST simples).

MÉTRICAS
- 182 arquivos Python (app: 136, tests: 46)
- 117 endpoints
- 56 endpoints sem teste correspondente
- 136 de 329 funções públicas sem type hints completos
- 34 except Exception genérico
- 1060 testes encontrados por análise textual
```

---

*"O SUS é o maior sistema universal de saúde do mundo. Merece software à altura."*
