# Plano de Produção do PicSaúde — v2 (pós-revisão CODEX)

> Versão consolidada do plano de 10 etapas para subir o PicSaúde a produção, com integração das revisões do ciclo multi-AI.
>
> **Classe (CLAUDE.md §10):** `docs`
>
> **Versão:** 2.0 (2026-05-06)

---

## Contexto

O PicSaúde tem backend funcional (146 testes passando) e precisa subir para URL pública demo + repositório GitHub aberto a contribuidores. O plano original tem 10 etapas. Esta v2 incorpora as revisões dos seguintes agentes:

- **Z AI** — UX clínica, integração frontend↔backend, faseamento de tickets
- **Engenheiro-Chefe (Claude)** — encaixe arquitetural, classificação de mudanças, ledger e custódia
- **CODEX** (novo no ciclo, 2026-05-06) — revisão estática do código backend; identifica vulnerabilidades, dívida técnica e cobertura de testes

A revisão CODEX expandiu **Etapa 5** (adicionou fixes de segurança crítica) e **Etapa 9** (expandiu de 7 para 12 issues `good-first-issue`).

---

## Status atual (2026-05-21)

| Etapa | Status | Notas |
|---|---|---|
| 1 — `.gitignore` + `git init` + commit inicial | ✅ Feito | commit inicial `9d15a3f` em 2026-05-06 |
| 2 — `gh repo create` | ✅ Feito | Remote `Tonaco-13/PicSaude` ativo (privado) |
| 3 — 7 arquivos de licenciamento | ✅ Feito | LICENSE (AGPL-3.0 + preâmbulo), README, CONTRIBUTING, CONTRIBUTOR-LICENSE, COMMERCIAL-LICENSE, DATA-PROTECTION, DISCLAIMER — todos na raiz |
| 4 — `instance_id` canônico | ✅ **Fechada (2026-05-21)** | **4A** ✅ `d8abf7e`, **4B-prequel** ✅ `2dce4f8`, **4B** ✅ `89f064a`, **4C** ✅ `2fbcf43`+`983359f`, **4D.1** ✅ `60382d2`+`0056c93`, **4D.2** ✅ `3db4060`+`79f2f4f`, **4E.1** ✅ `65181dc`+`a53d5ba`, **4E.2** ✅ `ab1c897` (CODEX+Jules + tickets) + `9ef3bb2` (fix custódia, vocabulário canônico + ator JWT) + `9cc339f` (batch lapidações pós-Regra 5). Critérios §7 do `TICKET-4E-2-RELATORIO-INTEGRADO.md` cumpridos. 124 testes verdes. |
| 5 — Bloqueadores pré-deploy | ⛔ Não feito | **Expandido — ver §5 abaixo** |
| 6 — `DEMO_MODE` + seletor de papéis | ⛔ Não feito | Bloqueador do deploy |
| 7 — Dockerfile | ⛔ Não feito | |
| 8 — Deploy Render + frontend Cloudflare | ⛔ Não feito | |
| 9 — Labels + issues `good-first-issue` | ⛔ Não feito | **Expandido para 12 issues — ver §9 abaixo** |
| 10 — Teste E2E URL pública | ⛔ Não feito | |

---

## Decisões consolidadas (não reabrir)

- **TICKET-70 spec v1.5** congelada em `docs/TICKET-70-SPEC.md`. Implementação só após Etapa 4 concluída e MVP no ar.
- **AGPL-3.0 pura na LICENSE.** Restrições de dados ficam fora — em DATA-PROTECTION.md e contrato comercial.
- **Sem vínculo formal com UFPE.** Projeto é propriedade pessoal de Fabiano Tonaco Borges. UFPE pode entrar futuramente como hospedeira/operadora, não como co-titular.
- **Seletor de papéis (Demo) sem credenciais hardcoded.** Variável `DEMO_MODE=true` é único gatilho.
- **Fix B1 (carteira digital):** retorna 422 com `{detail: "patient_no_digital_wallet", ...}`. Sem silenciamento.
- **CPF sentinela `00000000000`** + máscara de CPF: issue redigida em `docs/issues/ISSUE-mascara-cpf.md`.
- **Modelo de licenciamento comercial:** Caminho 2 (Opção A fixa por porte + Opção B com piso R$15k/teto R$600k + 7 sub-cláusulas de salvaguarda).

---

## Etapa 5 — Bloqueadores pré-deploy (expandida)

A Etapa 5 agora consolida **três fixes obrigatórios** antes do deploy público (Etapa 8). Todos foram identificados como bloqueadores reais — pelo plano original (B1) e pela revisão CODEX (5B, 5C).

### 5A — Fix B1: contrato carteira digital → 422

**Problema:** frontend envia `enviar_ao_paciente=true` e backend silencia quando paciente não tem carteira digital. Viola rastreabilidade RDC 1.000/2025.

**Fix:**

```python
# Se enviar_ao_paciente=true e paciente sem wallet:
raise HTTPException(
    status_code=422,
    detail={
        "detail": "patient_no_digital_wallet",
        "patient_id": "...",
        "message": "Paciente não possui carteira digital. Prescrição emitida mas não entregue digitalmente."
    }
)
```

Frontend exibe escolha consciente ao prescritor.

**Testes obrigatórios:**
- Paciente novo + `enviar_ao_paciente=true` → 422 com payload correto
- Paciente com wallet + `enviar_ao_paciente=true` → 200 (entrega ocorre)
- Paciente sem wallet + `enviar_ao_paciente=false` → 200 (sem tentar entregar)

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

### 5C — Testes mínimos de autorização em rotas sensíveis (subset ALTO 2 do CODEX)

**Problema identificado:** 56 de 117 rotas do backend não têm cobertura de teste. Cobertura completa não bloqueia deploy, mas **rotas sensíveis** (auth, login, prescrições, dispensações, custódia) precisam ter pelo menos teste de autorização e isolamento.

**Cenários mínimos por router crítico:**

- `routers/auth.py` e `routers/login.py`:
  - 401 sem token
  - 403 com token de papel incorreto
  - OTP expirado → 401
  - OTP usado duas vezes → 401

- `routers/prescricoes.py`:
  - Prescritor A não acessa prescrição emitida pelo prescritor B (cross-tenant)
  - Prescrição encerrada localmente não pode ser editada (estado terminal)
  - Tentativa de `UPDATE` direto retorna 405 (operação proibida arquiteturalmente)

- `routers/dispensacoes.py`:
  - Soma de quantidades dispensadas nunca excede prescrito
  - Dispensador sem custódia retorna 403
  - Dispensação parcial não invalida prescrição

- `routers/custodia.py`:
  - Transição inválida (paciente → outro paciente) retorna 422
  - Custódia transferida emite evento no ledger

**Critério de aceitação 5C:** os 5 routers acima passam a ter pelo menos 80% de cobertura. Demais rotas (laudos, relatórios, validação, etc.) ficam para Etapa 9 como `good-first-issue`.

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

**Estimativa:** 5D é trivial (~30 minutos). 5B é trivial (~2h). 5C consome ~1 dia. Etapa 5 inteira passa de "1 dia" para "~2 dias".

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
