# TICKET-DX-PRE-EXTENSAO — guardar Day 1 dos 7 extensionistas

> **Origem:** Jules — auditoria de DX da Etapa 6 (2026-05-25), achados P2#10 (conftest crash em SQLite) e P2#4 (ISSUEs sem instrução Windows).
> **Achado P1#1 do Jules (silenciamento de IA no prescritor.html) NÃO está neste ticket** — já resolvido em `f796f56` (frente A#1 do briefing Jules-audit DX). Verificação inline em §6.
> **Classe:** `module` (frontend off-scope; tests/config + docs).
> **Ritmo:** Regra 3 (≤100 linhas, Edit direto pelo Code, sem CODEX rodada 1). CODEX rodada 2 se aplicar é em fim-de-etapa, junto do fechamento da Etapa 6.
> **Prazo:** quarta 27/05 antes da reunião de 14h com os 7 extensionistas UFPE.

---

## §1 Contexto

A reunião com os 7 extensionistas é amanhã (27/05). Eles vão clonar o repositório, instalar dependências e rodar `pytest` em ambientes mistos (provavelmente Windows com SQLite, alguns macOS, talvez WSL). Sem este ticket, dois caminhos quebram no Day 1:

1. **`pytest backend/tests/`** em Windows sem `DATABASE_URL=postgresql://...test...` faz `backend/tests/integration/conftest.py` levantar `RuntimeError` no nível do módulo (linha 50-54 do conftest atual), interrompendo a coleta de toda a árvore de testes. O extensionista vê uma cratera no primeiro `pytest` da vida dele no projeto.

2. **Os dois ISSUEs good-first-issue** (`docs/issues/ISSUE-seed-common-helper.md` e `docs/issues/ISSUE-extrair-demo-bootstrap-js.md`) só dão exemplos de execução em bash/Linux (`PICSAUDE_DEMO_MODE=true uvicorn ...`). Quem está em Windows não vai saber traduzir, e a barreira inicial fica artificialmente alta.

Ambos são DX puro — não afetam a essência clínica do PicSaúde nem o demo público. Mas afetam diretamente a experiência dos extensionistas no primeiro dia. Custo de fix ≈ 30 linhas; custo de não fixar ≈ Day 1 frustrante para 7 pessoas que estão chegando pela primeira vez.

## §2 Escopo

- **3.1** — `backend/tests/integration/conftest.py` — guard de plataforma posicionado ANTES dos imports pesados (psycopg2, alembic), para skipar o módulo inteiro quando PostgreSQL não está configurado. Sem remover o guardrail rígido contra rodar em banco não-teste (mantido como segunda barreira).
- **3.2** — `docs/issues/ISSUE-seed-common-helper.md` e `docs/issues/ISSUE-extrair-demo-bootstrap-js.md` — bloco "Como rodar em diferentes sistemas" (PowerShell / CMD / Bash WSL).

Volume estimado: ~30 linhas total. Um único commit.

## §3 Sub-itens detalhados

### §3.1 Guard de plataforma em `conftest.py`

**Estado atual** (linhas 39-54 do `backend/tests/integration/conftest.py`):

```python
import os
import sys

DATABASE_URL_TEST = os.environ.get("DATABASE_URL", "")
if "test" not in DATABASE_URL_TEST.lower():
    raise RuntimeError(
        "ABORTANDO: DATABASE_URL não contém 'test'. "
        "Recuse-se a rodar testes de integração fora do banco de teste. "
        f"DATABASE_URL atual: {DATABASE_URL_TEST[:60]}..."
    )

# Imports da aplicação — seguros agora que DATABASE_URL foi validada
import itertools
import threading
import uuid
from datetime import datetime
from pathlib import Path

import psycopg2
import psycopg2.extensions
import pytest
```

**Problema:** o `RuntimeError` dispara antes do `import pytest`. Quem roda em Windows com SQLite (sem `DATABASE_URL` apontando para PG) bate no `RuntimeError` durante a coleta do pytest, e a árvore inteira (`backend/tests/`) crasha — mesmo os testes unitários que não dependem de PG.

**Mudança proposta:** posicionar o `pytest.skip(allow_module_level=True)` ANTES do `RuntimeError` e ANTES dos imports pesados. O `RuntimeError` permanece como segunda barreira para o caso de alguém configurar PG mas apontar para um banco que não é de teste.

```python
import os
import sys
import pytest  # importado cedo para permitir skip module-level

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Skip de plataforma — extensionistas Windows/SQLite sem PostgreSQL
# (Jules audit P2#10, 2026-05-25). Posicionado ANTES dos imports pesados
# (psycopg2, alembic) para não exigir que sejam instaláveis em todas as
# plataformas. Quem quiser rodar os testes de integração precisa de PG.
# ---------------------------------------------------------------------------
if not DATABASE_URL.startswith("postgresql"):
    pytest.skip(
        "backend/tests/integration/ requer PostgreSQL. "
        "Configure DATABASE_URL=postgresql://user:senha@localhost/picsaude_test "
        "ou rode pytest excluindo essa pasta: "
        "pytest --ignore=backend/tests/integration/",
        allow_module_level=True,
    )

# ---------------------------------------------------------------------------
# Guardrail rígido — recusar rodar fora do banco de teste
# (passou pelo skip acima, então PostgreSQL está configurado — falta
# garantir que o banco aponta para o ambiente de teste).
# ---------------------------------------------------------------------------
if "test" not in DATABASE_URL.lower():
    raise RuntimeError(
        "ABORTANDO: DATABASE_URL não contém 'test'. "
        "Recuse-se a rodar testes de integração fora do banco de teste. "
        f"DATABASE_URL atual: {DATABASE_URL[:60]}..."
    )

# ---------------------------------------------------------------------------
# Imports da aplicação — seguros agora que DATABASE_URL foi validada
# ---------------------------------------------------------------------------
import itertools
...
```

**Notas:**

- Renomeie `DATABASE_URL_TEST` (variável local enganosa) para `DATABASE_URL` para alinhar com o nome real da env var. Outros usos da variável no conftest seguem o mesmo nome.
- O docstring no topo do arquivo permanece intacto.
- A ordem é importante: `import pytest` antes do skip; psycopg2/alembic depois.

### §3.2 Bloco Windows/PowerShell nos 2 ISSUEs

Adicionar o seguinte bloco em `docs/issues/ISSUE-seed-common-helper.md` e `docs/issues/ISSUE-extrair-demo-bootstrap-js.md`, na seção "Cuidados" ou logo antes de "Critério de aceite" (escolha do Code, mantendo coerência entre os 2 arquivos):

```markdown
## Como rodar em diferentes sistemas

Os exemplos com `PICSAUDE_DEMO_MODE=true uvicorn ...` assumem bash (Linux/macOS/WSL). Em Windows nativo, use uma das variantes abaixo:

**PowerShell (Windows):**
```powershell
$env:PICSAUDE_DEMO_MODE="true"
uvicorn app.main:app --reload
```

**CMD (Windows):**
```cmd
set PICSAUDE_DEMO_MODE=true
uvicorn app.main:app --reload
```

**Bash (Linux / macOS / WSL):**
```bash
PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload
```

Para desligar o modo demo, feche o terminal ou faça `unset PICSAUDE_DEMO_MODE` (bash) / `Remove-Item Env:PICSAUDE_DEMO_MODE` (PowerShell) / `set PICSAUDE_DEMO_MODE=` (CMD).
```

Mesmo conteúdo nos 2 arquivos. Sem reescrita do resto.

## §4 Critérios de aceite

1. Executar `pytest backend/tests/` em ambiente sem `DATABASE_URL` configurado → testes da `integration/` aparecem como SKIPPED (com mensagem do skip visível), demais testes rodam normalmente. Sem `RuntimeError`, sem crash no nível de coleta.
2. Executar `pytest backend/tests/` com `DATABASE_URL=postgresql://user:senha@localhost/picsaude_test` → testes da `integration/` rodam, comportamento idêntico ao atual.
3. Executar `pytest backend/tests/` com `DATABASE_URL=postgresql://user:senha@localhost/picsaude_prod` (sem "test") → `RuntimeError` segue disparando, comportamento idêntico ao atual.
4. `docs/issues/ISSUE-seed-common-helper.md` contém a string `PowerShell`.
5. `docs/issues/ISSUE-extrair-demo-bootstrap-js.md` contém a string `PowerShell`.
6. Suite completa (`pytest backend/tests/`) com PG configurado: zero regressões.

## §5 Verificação automatizada

```bash
# Verificação 1 — Windows/SQLite sem PG, sem crash
unset DATABASE_URL
pytest backend/tests/ -x --collect-only 2>&1 | grep -i "error\|abort" | grep -v "deprecation"
# Esperado: vazio

# Verificação 2 — skip aparece como expected
unset DATABASE_URL
pytest backend/tests/integration/ -v 2>&1 | grep -E "SKIPPED|requer PostgreSQL"
# Esperado: mensagem do skip presente

# Verificação 3 — bloco Windows nos 2 ISSUEs
grep -l "PowerShell" docs/issues/ISSUE-seed-common-helper.md docs/issues/ISSUE-extrair-demo-bootstrap-js.md
# Esperado: ambos os arquivos listados
```

## §6 Predecessoras

- HEAD atual de `main`: `3005b27` (terça 26/05, "docs(continuacao): registrar GFI 63 no handoff noturno").
- Achado P1#1 do Jules (silenciamento IA prescritor.html) **já resolvido** em `f796f56` (frente A#1) — verificável por:

```bash
grep -nE "ia-bloco-neutro|IA indisponível" prescritor.html
# Esperado: matches em ~99 (CSS), ~2005 e ~2174 (substituição do .catch silente)
```

- Achados P1#5/P1#6 do Jules (thresholds CID 0.75 e TUSS 0.80) **já resolvidos** em `f796f56` (frentes B#5 e B#6):

```bash
grep -n "0.88" backend/app/ai/base_cid.py backend/app/ai/tuss_base.py
# Esperado: linha 506 (CID) e linha 430 (TUSS) com comentário "JULES-AUDIT — subido de..."
```

## §7 Anti-escopo (NÃO TOCAR neste ticket)

- **Não atacar Frente C do Jules (naming pt-BR/en)** — Fabiano faz doc fix em `CONTRIBUTING-EXTENSAO.md` direto, fora deste ticket. Convenção em transição, não refactor.
- **Não procurar `.catch(() => {})` silentes em outros arquivos** — vira good-first-issue para extensionistas (cards de boas-vindas, fase pós-reunião).
- **Não criar glossário no `CONTRIBUTING-EXTENSAO.md`** — primeira atividade colaborativa dos extensionistas. Ironia útil.
- **Não tocar em prescritor.html** — `f796f56` já corrigiu o achado P1#1 da auditoria. Verificação inline em §6.
- **Não tocar em qualquer router de autorização** — esses são domínio do 5C-bis (próxima etapa após fechar Etapa 6).

## §8 Classe, volume e ritmo

- **Classe:** `module` (frontend off-scope; afeta apenas test config e docs de contribuição).
- **Volume:** ~30 linhas em 3 arquivos.
- **Ritmo:** Regra 3 do pacto — Edit direto pelo Code, sem CODEX rodada 1. CODEX rodada 2 pós-implementação só se entrar em fim-de-etapa junto com Etapa 6.
- **Commit único** sugerido: `fix(dx): conftest skip module-level sem PG + bloco Windows nos ISSUEs (Jules P2#4 + P2#10)`.

## §9 Prompt sugerido ao Code

Você pode executar este ticket como Regra 3 (Edit direto, sem CODEX pré-impl). Spec completa em §3, critérios em §4, verificação em §5, anti-escopo em §7. Predecessoras em §6 incluem grep que confirma que P1#1/P1#5/P1#6 da auditoria Jules já estão fechados no `f796f56` — nada a tocar lá. Commit único conforme §8.

Se rodar smoke local em macOS (PG disponível): verifique também a verificação 1 do §5 forçando `unset DATABASE_URL`. Se rodar via Docker em CI: garantir que a env var não é setada antes do `pytest --ignore=backend/tests/integration/` para o cenário de extensionista Windows.

Ao terminar, encadear com o checklist §4.2 do TICKET-6.1 (validação manual frontend pendente) — sem dependência mas otimiza o fechamento da Etapa 6 antes da reunião.

---

## §10 Reservado para CODEX rodada 2 (se aplicar)

*Preenchido só se este ticket entrar em fim-de-etapa com CODEX/Jules em rodada 2 junto com o fechamento da Etapa 6. Se Code fizer commit isolado pré-reunião e CODEX não revisar até quarta de manhã, esta seção fica vazia e o ticket é arquivado.*

## §11 Reservado para lapidações pós-impl

*Preenchido após execução, com achados secundários se aparecerem (deve ficar vazio dado o escopo cirúrgico).*
