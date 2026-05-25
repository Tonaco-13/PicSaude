# Relatório de Auditoria — Jules (DX, Dívidas e Bugs Latentes)

**Destinatário:** Arquiteto (Opus 4.7) / Fabiano
**Data:** 2026-05-25
**Objetivo:** Auditoria focada na primeira impressão dos extensionistas UFPE-CTG (quarta-feira, 2026-05-27), abordando DX, bugs latentes de IA e naming.

---

## FRENTE A: DX para extensionistas (Frontends, Docs e Issues)

1. [P1] [DX | Frontend] `prescritor.html:2002`, `2164`, `2371` — Silenciamento completo de falhas de IA.
   Em caso de timeout, 500 ou indisponibilidade da IA, o `.catch(() => { ... innerHTML = ''; })` esvazia o container, sem dar feedback neutro/informativo ("IA indisponível"). Diferente da correção feita hoje no `match_tipo="nenhum"`. Isso frustra o aluno/usuário achando que clicou no vazio.
   Decisão sugerida: **fix imediato** (adicionar microcopy "IA indisponível").

2. [P2] [DX | Frontend] `dispensador.html:1607` e `prescritor.html:2629` — Silenciamento de `.catch(() => {})`.
   Existem blocos try/catch vazios e silenciosos, inclusive comentados justificando "a IA é acessória" ou "impressão não depende do backend". Para o estudante que está rastreando bugs (console limpo e nada acontece), a DX é péssima.
   Decisão sugerida: **follow-up** (adicionar `console.warn` em todos os `.catch` genéricos).

3. [P2] [DX | Doc] `CONTRIBUTING-EXTENSAO.md` — Risco de jargão elevado.
   O documento exige entendimento sólido imediato de termos como "ledger", "instance_id canônico", "vocabulário sanitário", e "transações". Faltou um glossário simplificado para o aluno do 4º período.
   Decisão sugerida: **aceitar como dívida** (criar um Ticket para "Glossário Básico PicSaúde" nas próximas semanas).

4. [P2] [DX | Issues] `ISSUE-seed-common-helper.md` e `ISSUE-extrair-demo-bootstrap-js.md`.
   O escopo e complexidade de extração em `seed-common` ou de refactor JS está exato para uma carga de 1 semana. Porém, as issues pedem comandos como `PICSAUDE_DEMO_MODE=true uvicorn backend.app.main:app --reload`. Estudantes costumam travar com injeções de ENV inline no Windows/Powershell.
   Decisão sugerida: **follow-up** (adicionar notas nas issues sobre como rodar ENVs no Windows/WSL ou atualizar para rodar o `.sh`).

---

## FRENTE B: IA-completa (Bugs Latentes de WRatio)

5. [P1] [Bug-latente | IA] `backend/app/ai/base_cid.py:548` — Threshold `fuzz.WRatio` frágil.
   O score mínimo (`0.75`) permite aproximações perigosas: "dor de cabeca" mapeia como `A09 - Diarreia e gastroenterite` com score 0.855; e "infeccao urinaria" bate em `A56.0 - Infecção por clamídia` (0.855). Isso replica exatamente o bug latente corrigido no `lookup_def.py`.
   Decisão sugerida: **fix imediato** (aumentar threshold padrão de 0.75 para > 0.88).

6. [P1] [Bug-latente | IA] `backend/app/ai/tuss_base.py:439` — Threshold `fuzz.WRatio` frágil.
   O score padrão (`0.80`) no lookup TUSS resultou num match falso (score 0.90) para "rx", mapeando cegamente para `40901060 - Radiografia do Tórax (2 incidências)`. Um exame simples acaba puxando um código equivocado.
   Decisão sugerida: **fix imediato** (aumentar threshold para no mínimo 0.88).

---

## FRENTE C: Naming pt-BR / en (Tech Debt Acumulado)

A convenção estipulada em `CONTRIBUTING-EXTENSAO.md` ("REST handlers: en, domínio: pt-BR") tem fortes violações, criando dívida técnica que confundirá os extensionistas.

| Arquivo:linha | Convenção esperada vs Real | Sugestão |
|---|---|---|
| `backend/app/routers/ia.py` | Esperado: en (`get_cid`, `post_atestado`). Real: pt-BR (`buscar_cid_endpoint`, `validar_atestado_endpoint`). | **aceitar como dívida** |
| `backend/app/routers/*.py` | Esperado: en ou pt-BR unificado. Real: Híbrido bizarro (`get_agendamento`, `get_pedido_exame`, `get_documento`). | **discutir** (padronizar prefixos REST) |
| `backend/app/routers/auth.py` | Esperado: en (`post_codigo`, `post_validar`). Real: pt-BR (`enviar_codigo`, `validar_codigo`). | **aceitar como dívida** |

---


## FRENTE ADICIONAL (Testes e Integração)

10. [P2] [DX | Tests] `backend/tests/integration/conftest.py` — Falha severa "out-of-the-box".
   Se o extensionista rodar `pytest` com `DATABASE_URL=sqlite:///./test.db`, o arquivo `conftest.py` estoura imediatamente devido a um wrapper explícito do `psycopg2.connect(DATABASE_URL_TEST)`. Não há graceful fallback para quem roda localmente com SQLite e não levantou o banco de dados. Isso bloqueará qualquer tentativa local de TDD no primeiro dia.
   Decisão sugerida: **follow-up** (adicionar um if-check `if "sqlite" in DATABASE_URL_TEST` ignorando transações pesadas ou avisando no console para ignorar a pasta `integration/`).
