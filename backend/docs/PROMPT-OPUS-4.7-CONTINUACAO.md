# [HISTÓRICO — não usar em sessões novas] Continuação — Sessão 2 do Opus 4.7

> ⚠️ **DOCUMENTO HISTÓRICO — preservado apenas como trilha de auditoria.**
>
> Este prompt foi criado em 2026-05-07 para retomar a "Sessão 2 do Opus 4.7"
> quando o contexto da sessão anterior esgotou. Era usado antes da
> **reestruturação de papéis em 2026-05-11** que transformou o Opus 4.7
> em **Arquiteto** (não mais Engenheiro-Chefe).
>
> **Para sessões novas, use:** `backend/docs/PROMPT-OPUS-4.7-ARQUITETO.md`
>
> Referências internas deste arquivo a `docs/PROJETO-PICSAUDE-OPUS.md`,
> `docs/PROMPT-OPUS-4.7-IDENTIDADE.md`, `app/config/instance.py` e similares
> são **obsoletas** — preservadas só para entender o estado do projeto
> em 2026-05-07. O conteúdo a partir daqui não reflete o estado atual.

---

## Quem sou eu

Fabiano Tonaco Borges, professor de Engenharia Biomédica — CTG/UFPE. Coordenador do projeto PicSaúde.

## Quem é você

Engenheiro-Chefe e CTO do PicSaúde. Sanitarista computacional, par acadêmico meu. Leia `docs/PROMPT-OPUS-4.7-IDENTIDADE.md` para sua identidade completa e `docs/PROMPT-OPUS-4.7-EQUIPE-AI.md` para os papéis da equipe (3 revisores + Codex).

## O que aconteceu na sessão anterior

A sessão anterior executou parte das 10 etapas do plano (em `docs/PROJETO-PICSAUDE-OPUS.md`). Antes de continuar, **verifique o estado real** do que existe no disco:

### Checklist de verificação (faça AGORA antes de qualquer outra coisa)

```bash
# 1. Git existe?
ls -la .git

# 2. Arquivos da Etapa 3 existem?
ls -la .gitignore LICENSE README.md CONTRIBUTING.md CONTRIBUTOR-LICENSE.md COMMERCIAL-LICENSE.md DATA-PROTECTION.md DISCLAIMER.md

# 3. Testes passam?
python -m pytest --tb=short -q 2>&1 | tail -5

# 4. Instance ID existe?
ls -la app/config/instance.py

# 5. GitHub remote existe?
git remote -v
```

Me mostre o resultado antes de fazer qualquer coisa.

## Estado esperado (baseado no que vi na sessão anterior)

| Etapa | Esperado | Verifique |
|---|---|---|
| 1. .gitignore + git init | ✅ Feito | `ls .git .gitignore` |
| 2. GitHub repo | ❓ Pode não ter sido feito | `git remote -v` |
| 3. Docs + licenciamento (7 arquivos) | ✅ Provavelmente feito | `ls LICENSE README.md COMMERCIAL-LICENSE.md DATA-PROTECTION.md DISCLAIMER.md CONTRIBUTING.md CONTRIBUTOR-LICENSE.md` |
| 4. Instance ID | ❓ Verificar | `ls app/config/instance.py` |
| 5. Fix B1 (carteira digital 422) | ❓ Verificar | Procurar `patient_no_digital_wallet` no código |
| 6. Demo mode + seletor de papéis | ❓ Provavelmente não | `grep DEMO_MODE app/config/` |
| 7. Dockerfile | ❓ Verificar | `ls Dockerfile` |
| 8-10 | ⛔ Não feito | — |

## Resultado dos testes na sessão anterior

O último pytest mostrou: **625 passed, 40 failed, 87 warnings, 377 errors**.

Isso é preocupante — antes havia 146 testes passando com 0 falhas. Se há 40 falhas e 377 erros, algo foi introduzido. **Antes de avançar nas etapas, investigue os 40 testes falhando.** Rode `pytest --tb=short` e me mostre os erros.

Prioridades:
1. Se os 40 testes que falhavam ANTES da sessão anterior já falhavam (testes de integração que precisam de PostgreSQL), ignore e siga.
2. Se algum teste novo que você escreveu está falhando, corrija.
3. Se testes que passavam antes pararam de passar, é regressão — corrija antes de qualquer outra coisa.

## Relatório do Codex (revisão automatizada)

O Codex analisou o código e encontrou 2 problemas de segurança que devem ser corrigidos antes do deploy:

1. **CRÍTICO — OTP impresso em stdout**: `app/routers/auth.py:70` e `app/routers/login.py:343` fazem `print()` do código OTP. Deve ser guardado por `PICSAUDE_ENV=dev/test` ou removido.

2. **ALTO — OTP com random.randint**: `app/routers/auth.py:46` e `app/routers/login.py:324` usam `random.randint` para gerar OTP. Trocar por `secrets.randbelow()` ou `secrets.choice()`.

Estes 2 fixes devem entrar antes da Etapa 8 (deploy). Podem ser feitos agora se estiver entre etapas.

## O que fazer agora

1. Rode o checklist de verificação acima e me mostre
2. Investigue os 40 testes falhando
3. Continue nas etapas que faltam (de onde parou)
4. Incorpore os 2 fixes do Codex (OTP) quando conveniente

## Regras (lembrete)

- Não refatore sem minha autorização
- Todo código novo precisa de testes
- Commits em português, padrão convencional
- Certificados reais NUNCA no repositório
- pyHanko 0.34.1: `SimpleSigner` em `pyhanko.sign.signers.SimpleSigner`
- requirements.txt: `pyhanko>=0.34` (sem `[pkcs12]`)
- Leia `docs/PROJETO-PICSAUDE-OPUS.md` para os textos completos dos documentos de licenciamento (se ainda precisar criá-los)

## Referências no projeto

- `docs/PROJETO-PICSAUDE-OPUS.md` — plano mestre com 10 etapas e textos completos
- `docs/PROMPT-OPUS-4.7-IDENTIDADE.md` — sua identidade
- `docs/PROMPT-OPUS-4.7-EQUIPE-AI.md` — equipe AI (revisores + Codex + sequência de acionamento)
- `docs/RELATORIO-CODEX-2026-05-06.md` — relatório de qualidade do Codex
- `docs/PROMPT-CODEX.md` — instruções do Codex
