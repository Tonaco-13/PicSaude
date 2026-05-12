# Prompt-D — Fix de segurança OTP (pré-Etapa 8)

> Cole o bloco abaixo no Claude Code (VS Code).
>
> **Regra 3 — Edit direto.** Classe `core` <100 linhas isolada, sem ticket
> formal. Autorizado por Fabiano em 2026-05-12. Bloqueador pré-Etapa 8
> (deploy) identificado pelo CODEX em 2026-05-06.

---

```
=== FIX OTP — segurança pré-Etapa 8 (Regra 3, sem ticket formal) ===

CONTEXTO

2 bugs de segurança identificados pelo CODEX em 2026-05-06:

  CRÍTICO — OTP em print() (auth.py:72, login.py:343):
    Em produção, OTP vai para logs do Render. Qualquer pessoa com
    acesso ao painel captura código de autenticação ativo.

  ALTO — OTP gerado com random.randint (auth.py:48, login.py:324):
    PRNG não-criptográfico, previsível com sementes recuperáveis.
    Inadequado para autenticação.

CLASSE: core (~10-15 linhas de mudança). Regra 3 — Edit direto.
Bloqueador da Etapa 8 (deploy).

DIRETÓRIO:
  /Users/fabianotonacoborges/Desktop/PicSaude_Dev/backend

NÃO comitar antes de validação do Arquiteto.

--------------------------------------------------
FIX 1 — secrets.randbelow no lugar de random.randint
--------------------------------------------------

Arquivo: app/routers/auth.py
Linha 48 (atualmente):
  codigo = str(random.randint(100000, 999999))

Substituir por:
  codigo = str(secrets.randbelow(900000) + 100000)

Adicionar `import secrets` ao topo do arquivo (verificar se já está
presente — provavelmente não).

REMOVER o `import random` se for o único uso restante. Verificar
com: grep -n "random\." app/routers/auth.py

Arquivo: app/routers/login.py
Linha 324 (atualmente):
  codigo = str(_random.randint(100000, 999999))

Substituir por:
  codigo = str(secrets.randbelow(900000) + 100000)

Adicionar `import secrets` ao topo. Tratar o `_random` (alias)
similarmente: se for o único uso de `import random as _random`,
remover o import-as.

NOTA SOBRE EQUIVALÊNCIA: random.randint(a, b) inclui ambos os
limites; secrets.randbelow(N) retorna [0, N-1]. Logo:
  random.randint(100000, 999999)         → 100000..999999
  secrets.randbelow(900000) + 100000     → 100000..999999
Mesmo range, mesma cardinalidade (900_000 valores).

--------------------------------------------------
FIX 2 — Guard de print() por PICSAUDE_ENV
--------------------------------------------------

Arquivo: app/routers/auth.py
Linha 72 (atualmente):
  print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

Substituir por (SEM default — safe-by-default, CODEX rodada 2 [ALTO]):
  # Print OTP no stdout APENAS em dev/test — em produção (Render),
  # OTP nunca aparece nos logs. Bloqueador de segurança CODEX 2026-05-06.
  # SEM default: PICSAUDE_ENV ausente é tratado como "não-dev/test",
  # então deploy sem env configurada NÃO vaza OTP.
  if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
      print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

Verificar se `import os` já está no topo. Se não, adicionar.

Arquivo: app/routers/login.py
Linha 343 (atualmente):
  print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

Substituir por (mesmo padrão, SEM default):
  if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
      print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

NOTA SOBRE AUSÊNCIA DE DEFAULT (CODEX rodada 2 P1): se PICSAUDE_ENV
não estiver setada (cenário de deploy mal configurado), `os.getenv()`
retorna None, e `None in ("dev", "test")` é False — OTP NÃO é
impresso. Em produção bem configurada (PICSAUDE_ENV=prod), idem.
Apenas dev/test explicitamente setado imprime. Para rodar testes
locais com OTP visível, é responsabilidade do dev setar
PICSAUDE_ENV=dev no ambiente. O conftest da Task #8 já seta
PICSAUDE_ENV=test autouse session-scope, então pytest continua OK.

--------------------------------------------------
FIX 3 — Testes obrigatórios do guard (CODEX rodada 2 [ALTO])
--------------------------------------------------

O plano de produção (PLANO-PRODUCAO-V2.md §5B) exige cobertura
explícita do guard. Adicionar 3 testes (preferencialmente em
tests/test_auth_paciente.py — já tem fixtures de login OTP).

Padrão recomendado (capsys captura stdout, monkeypatch controla env):

  def test_otp_nao_imprime_em_prod(client, monkeypatch, capsys):
      """Em PICSAUDE_ENV=prod, OTP nunca aparece em stdout."""
      monkeypatch.setenv("PICSAUDE_ENV", "prod")
      # ... disparar fluxo que gera OTP (POST /auth/iniciar ou similar)
      captured = capsys.readouterr()
      assert "[PICSAUDE-OTP]" not in captured.out
      assert "[PICSAUDE-OTP]" not in captured.err

  def test_otp_nao_imprime_sem_env(client, monkeypatch, capsys):
      """Sem PICSAUDE_ENV setada (cenário deploy mal configurado),
      OTP NÃO vaza em stdout — safe-by-default."""
      monkeypatch.delenv("PICSAUDE_ENV", raising=False)
      # ... disparar fluxo
      captured = capsys.readouterr()
      assert "[PICSAUDE-OTP]" not in captured.out

  def test_otp_imprime_em_dev(client, monkeypatch, capsys):
      """Em PICSAUDE_ENV=dev, OTP aparece em stdout (UX de debug)."""
      monkeypatch.setenv("PICSAUDE_ENV", "dev")
      # ... disparar fluxo
      captured = capsys.readouterr()
      assert "[PICSAUDE-OTP]" in captured.out

NOTA: o conftest da Task #8 (commit d2f016b) seta PICSAUDE_ENV=test
autouse session-scope. monkeypatch.setenv tem precedência sobre
isso dentro da função do teste — funciona normalmente.

NOTA 2: cada teste precisa disparar UM fluxo que gera OTP. Identificar
a rota correta (POST /auth/iniciar, POST /login/cidadao, similar)
verificando o código atual. Se houver inferno de fixtures, pode-se
testar diretamente a função geradora de OTP (chamando o handler ou
helper isoladamente), sem cliente HTTP.

--------------------------------------------------
PROCEDIMENTO
--------------------------------------------------

1. Aplicar FIX 1 em auth.py (random -> secrets).
2. Aplicar FIX 1 em login.py.
3. Aplicar FIX 2 em auth.py (guard de print SEM default).
4. Aplicar FIX 2 em login.py.
5. Aplicar FIX 3 em tests/test_auth_paciente.py (3 testes novos).

6. Verificação automatizada (segurança):
     grep -nE "random\.randint|^import random" app/routers/auth.py app/routers/login.py
   Esperado: zero matches.

     # CODEX rodada 2 [MÉDIO]: usar [[:space:]] em vez de \s
     # (\s não é portátil entre BSD/macOS grep e GNU grep).
     grep -nE "^[[:space:]]*print.*(OTP|CODIGO)" app/routers/auth.py app/routers/login.py
   Esperado: matches APENAS dentro de blocos com guard PICSAUDE_ENV
   (inspecionar contexto via `grep -B 2 ...` se necessário).

7. Rodar testes que tocam OTP/auth/login (existentes + 3 novos):
     pytest tests/test_auth_paciente.py tests/test_g4b.py -v
   Esperado: testes existentes continuam verdes + 3 testes novos
   do FIX 3 passing.

8. Regressão geral (rápida):
     pytest tests/test_ledger_helper.py \
            tests/integration/test_4d1_instance_id_ledger.py \
            tests/integration/test_4d2_instance_id_ledger.py
   Esperado: continuam verdes (não tocamos esses fluxos).

9. Reportar:
   - Output dos passos 6, 7, 8
   - Diff dos arquivos (esperado: ~10-15 linhas em prod + ~30-40 linhas
     dos 3 testes novos)
10. NAO COMITAR. Aguardar validação do Arquiteto.

--------------------------------------------------
RESTRIÇÕES
--------------------------------------------------

- Não mudar lógica de geração de OTP (validade, formato 6 dígitos,
  expiração 5min — preservar).
- Arquivos permitidos para tocar nesta rodada:
    app/routers/auth.py
    app/routers/login.py
    tests/test_auth_paciente.py   (apenas para ADICIONAR 3 testes novos)
  Qualquer outro arquivo: PARAR e escalar para o Arquiteto.
- IMPORTANTE: `backend/docs/tickets/PROMPT-D-OTP-FIX-PRE-ETAPA-8.md`
  existe untracked no repo. NÃO incluir no commit do fix de segurança
  (CODEX rodada 2 [BAIXO]). Fica para o próximo commit "docs".
- Verificar `.git/index.lock` antes de qualquer git (padrão
  recorrente das últimas sessões).
```

---

## Notas para Fabiano

- **Tamanho previsto:** ~10-15 linhas total entre 2 arquivos.
- **Critério de aceite:** 5 verificações que vou rodar quando Code reportar (grep × 2 + 3 suítes pytest).
- **Commit canônico previsto após verde:**
  `fix(security): OTP usa secrets + guard print por PICSAUDE_ENV (pré-Etapa 8)`
- Se algum teste de auth depender de `print` ativo, o conftest da Task #8 já seta `PICSAUDE_ENV=test` autouse — guard permite `print` em test. Code só precisa confirmar.
