# Bem-vindo, extensionista

Este guia é para os 7 estudantes/profissionais que entraram no PicSaúde como **projeto de extensão do CTG/UFPE** em 2026. Se você está chegando agora pela disciplina, pelo edital de extensão, ou foi convidado pelo Prof. Fabiano — este é o seu ponto de partida.

O PicSaúde é software livre (AGPL v3) para prescrição médica digital com assinatura ICP-Brasil. O objetivo da equipe de extensão é duplo:

1. **Despacho para os municípios.** Documentar, empacotar e oferecer o sistema para Secretarias Municipais de Saúde (SMS) começando por Recife/PE.
2. **Testar e aprimorar.** Validar o sistema em condições reais (rede UFPE, navegadores variados, perfis clínicos diversos) e contribuir com correções, melhorias de UX, documentação.

A equipe é interprofissional por design: você pode ter formação em informática, medicina, enfermagem, farmácia, direito, comunicação, gestão pública. Cada formação tem espaço — este guia te ajuda a achar o seu.

---

## Setup local — 10 minutos

### Pré-requisitos

- **Python 3.10 ou superior** (verifique com `python3 --version`)
- **git** (verifique com `git --version`)
- Um editor de código — recomendado: [VS Code](https://code.visualstudio.com/) (gratuito, multiplataforma)
- Um navegador moderno (Chrome, Firefox, Safari, Edge — qualquer versão dos últimos 2 anos)

Não precisa de Docker, PostgreSQL, ou nenhum banco de dados extra para o modo demo — usamos SQLite (arquivo local).

### Passo a passo

```bash
# 1. Clonar o repositório
git clone https://github.com/Tonaco-13/PicSaude.git
cd PicSaude/backend

# 2. Criar ambiente Python isolado
python3 -m venv .venv
source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate      # Windows PowerShell

# 3. Instalar dependências (vai baixar ~80MB, leva 1-2 min)
pip install -r requirements.txt

# 4. Criar e popular o banco demo
PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py
# Saída esperada: "✅ schema recriado" + "✅ seed demo concluído (3 personas)"

# 5. Subir o backend
PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload --app-dir .
# Saída esperada: "Uvicorn running on http://127.0.0.1:8000"

# 6. Abra o navegador em http://localhost:8000
# Você deve ver: banner amarelo "MODO DEMO" + 3 cards (Prescritor / Dispensador / Cidadão)
```

### Validar que está tudo no lugar

```bash
# Rodar a suíte de testes (deve passar 1267 + 27 falhas pré-existentes documentadas)
cd backend && pytest -q
```

Se rolou tudo certo, você está pronto. Se travou em algum passo, vá direto para a [seção FAQ](#faq) ou abra issue com label `docs`.

---

## Mapa do repositório — onde está o quê

Tem 20+ arquivos em `backend/app/routers/`. Para não se perder, este é o mapa de orientação rápida:

```
PicSaude/
├── README.md                       ← Visão geral pública
├── CLAUDE.md                       ← Princípios arquiteturais invioláveis (LEIA)
├── CONTRIBUTING.md                 ← Guia genérico para qualquer contribuidor
├── CONTRIBUTING-EXTENSAO.md        ← Este arquivo
├── LICENSE                         ← AGPL v3
├── *.html                          ← Frontends (vanilla JS, sem build step)
│
├── backend/
│   ├── CLAUDE.md                   ← Briefing para agentes Claude (foco no Code)
│   ├── requirements.txt            ← Dependências Python
│   │
│   ├── app/
│   │   ├── main.py                 ← Entry point FastAPI (rotas registradas aqui)
│   │   ├── config.py               ← Env vars (PICSAUDE_DEMO_MODE, JWT_SECRET, etc.)
│   │   ├── database.py             ← Conexão SQLAlchemy + helper _resolve_sqlite_db_path
│   │   ├── instance.py             ← instance_id canônico (por instalação)
│   │   │
│   │   ├── routers/                ← Endpoints HTTP (1 arquivo por área clínica)
│   │   │   ├── auth.py             ← Login OTP de paciente (legado)
│   │   │   ├── login.py            ← Login profissional (senha + OTP)
│   │   │   ├── demo.py             ← /demo/login e /demo/info (modo demo)
│   │   │   ├── config_publico.py   ← /config/public (banner, demo_mode, etc.)
│   │   │   ├── prescricoes.py      ← Emissão / consulta / impressão de receitas
│   │   │   ├── dispensacoes.py     ← Dispensação (farmácia)
│   │   │   ├── custodia.py         ← Transferências de custódia (prescritor↔paciente↔dispensador)
│   │   │   ├── assinaturas.py      ← Metadados de assinatura digital
│   │   │   ├── validacao.py        ← Validação documental em 5 camadas
│   │   │   └── …mais 10 arquivos para exames, laudos, agendamentos, etc.
│   │   │
│   │   ├── domain/                 ← Lógica de negócio pura (sem dependência de FastAPI)
│   │   │   ├── states.py           ← Máquina de estados de prescrição (CONTRATO oficial)
│   │   │   ├── ledger.py           ← Helper de escrita no ledger imutável
│   │   │   ├── pdf_prescricao.py   ← Geração do PDF institucional
│   │   │   ├── motor_regulatorio.py ← Regras RDC 1.000/2025
│   │   │   └── …
│   │   │
│   │   ├── models/                 ← Tabelas SQLAlchemy (1 arquivo por tabela)
│   │   ├── schemas/                ← Pydantic (validação de entrada/saída HTTP)
│   │   └── auth/                   ← JWT + RBAC (perfis: prescritor, dispensador, paciente, admin)
│   │
│   ├── tests/                      ← Pytest (test_<modulo>.py)
│   ├── scripts/
│   │   └── reset_demo_db.py        ← Reseta banco demo (rode antes de subir o demo)
│   ├── seed_demo.py                ← Popula 3 personas canônicas
│   └── seed_dev.py                 ← Popula dados de desenvolvimento (não use em demo)
│
└── docs/
    ├── PLANO-PRODUCAO-V2.md        ← Roadmap mestre do projeto (10 etapas)
    ├── NUCLEO_SANITARIO.md         ← Contrato obrigatório para novos objetos sanitários
    ├── ARQUITETURA_*.md            ← 1 arquivo por subdomínio (exames, laudos, agendamento, etc.)
    └── tickets/                    ← Specs de cada etapa implementada
```

**Regra mental rápida:** quando você vê uma URL `POST /prescricoes/...`, vai em `backend/app/routers/prescricoes.py`. Quando vê estado `em_custodia`, vai em `backend/app/domain/states.py`. Quando vê tabela `prescricao_eventos`, vai em `backend/app/models/`.

---

## Convenção de naming híbrido (pt-BR / en)

Você vai notar uma mistura no código:

```python
PICSAUDE_DEMO_MODE  = ...        # env vars: en (convenção 12-factor)
_papeis_demo_disponiveis()       # funções de domínio clínico: pt-BR
demo_login()                     # handlers HTTP: en (REST + Python idiomático)
prescricao_eventos               # tabelas SQL: pt-BR (vocabulário sanitário)
status_item = "em_custodia"      # estados de domínio: pt-BR
```

A regra implícita:

| Tipo | Idioma | Por quê |
|---|---|---|
| Vocabulário clínico/sanitário (estados, eventos, tabelas, modelos de negócio) | **pt-BR** | Honra o domínio nacional — saúde pública brasileira fala português |
| Infraestrutura técnica (env vars, handlers HTTP, helpers genéricos) | **en** | Honra a convenção da stack (FastAPI, Python, Docker, REST) |
| Documentação e comentários | **pt-BR** | Audiência primária é brasileira |
| Mensagens de commit | **pt-BR** | Trilha de auditoria nacional |

Não é uma regra rígida. Se ficar em dúvida, pergunte na issue ou no PR. O importante é manter a coerência local — se você está editando `prescricoes.py`, segue o estilo dele.

---

## Sobre a "IA" do PicSaúde — o que é e o que não é

O PicSaúde tem endpoints chamados `/ia/medicamentos/sugerir`, `/ia/cid/buscar`, `/ia/exames/normalizar` e `/ia/documentos/atestado/validar`. O nome induz expectativa de que existe um modelo de linguagem (tipo GPT/ChatGPT) por trás. **Não existe.**

A "IA" do PicSaúde é **lookup determinístico contra bases CSV locais**, com regras de fuzzy match (rapidfuzz). Mesma entrada → mesma saída, sempre. Sem chamadas externas, sem custo de API, sem aprendizado, sem alucinação.

| Endpoint | Base local | Tamanho atual (MVP) |
|---|---|---|
| `/ia/medicamentos/sugerir` | `data/def_medicamentos.csv` | 41 medicamentos (top RENAME) |
| `/ia/exames/normalizar` | `BASE_TUSS` (in-code) | 38 exames |
| `/ia/cid/buscar` | `BASE_CID` (in-code) | ~240 códigos CID-10 |
| `/ia/documentos/atestado/validar` | Regras determinísticas (sem base) | — |

**Quando o backend responde `match_tipo: "nenhum"`**, significa que o termo que você digitou não está na base. **Não é bug — é cobertura limitada do MVP.** Por exemplo, "rivotril" funciona (é alias de clonazepam, está na base); "diazepam" não funciona (não está na base inicial).

A primeira good-first-issue dessa categoria é a **GFI #62** (expandir `def_medicamentos.csv` para top-200 RENAME) — veja em `docs/issues/ISSUE-expandir-def-medicamentos.md`.

Por que escolhemos lookup determinístico em vez de LLM:

1. **Auditável.** Cada sugestão tem origem rastreável (linha do CSV, score do match) — exigência regulatória da Anvisa para prescrição digital.
2. **Determinístico.** Mesma entrada → mesma saída. Crítico para reproduzibilidade em saúde pública.
3. **Sem custo recorrente.** SMS rodando o sistema local não paga API.
4. **Sem alucinação.** LLM pode sugerir medicamento que não existe. Lookup nunca.

O preço pago: **base precisa ser expandida manualmente**, e a UX precisa sinalizar claramente quando "nenhum match" significa "não sabemos" em vez de "nada existe". Esse é o cuidado contínuo que esperamos da equipe.

---

## Primeiros tickets sugeridos (`good-first-issue`)

Três issues abertas e dimensionadas para primeira contribuição. Escolha **uma** para começar e comente "eu pego" na issue.

### Issue #56 — `js/demo-bootstrap.js` (extrair script duplicado)

**Diagnóstico:** os 5 frontends HTML (`index`, `prescritor`, `dispensador`, `cidadao`, `clinica`) têm trechos de boot script quase idênticos lendo `/config/public` e `sessionStorage`. A duplicação é tech debt aceito por KISS, mas vale extrair agora que a forma estabilizou.

**Escopo:**
1. Criar `js/demo-bootstrap.js` com a função compartilhada
2. Substituir os 5 trechos inline pela tag `<script src="js/demo-bootstrap.js"></script>` + chamada
3. Validar visualmente que cada uma das 5 páginas continua funcionando em modo demo

**Tamanho estimado:** 80-120 linhas modificadas. Tempo: 2-4 horas.

**Perfil ideal:** alguém com noção básica de JavaScript / vanilla DOM. Não exige Python.

### Issue #57 — Pydantic Response Models para `/demo/*` e `/config/public`

**Diagnóstico:** os handlers `/demo/login`, `/demo/info`, `/config/public` retornam `dict` genérico. Falta um modelo Pydantic explícito que documente o shape da resposta no Swagger (`/docs`) e dê type-safety no Python.

**Escopo:**
1. Criar classes Pydantic em `backend/app/schemas/demo.py` (`DemoLoginResponse`, `DemoInfoResponse`, `ConfigPublicResponse`)
2. Anotar os handlers com `response_model=...`
3. Confirmar que `pytest tests/test_demo_mode.py` continua verde (deve)
4. Conferir no `/docs` que o exemplo de resposta agora aparece bonito

**Tamanho estimado:** 50-80 linhas. Tempo: 2-3 horas.

**Perfil ideal:** alguém com Python básico interessado em type hints e contratos de API.

### Issue #58 — `seed_common.py` (helpers compartilhados entre seeds)

**Diagnóstico:** `seed_demo.py` e `seed_dev.py` têm funções `_garantir_usuario`, `_garantir_prestador`, etc. parcialmente duplicadas. Extrair helpers comuns reduz superfície para drift entre os dois.

**Escopo:**
1. Criar `backend/seed_common.py` com helpers idempotentes
2. Refatorar `seed_demo.py` e `seed_dev.py` para usar os helpers
3. Confirmar que `python3 scripts/reset_demo_db.py` continua funcionando e popula as 3 personas

**Tamanho estimado:** 100-150 linhas (mexer em 3 arquivos). Tempo: 4-6 horas.

**Perfil ideal:** alguém com Python intermediário, confortável com refactoring + testes.

---

## Roteiro de homologação manual

Para quem prefere validar o sistema sem programar (ou quer fazer isso como primeira contribuição), existe um roteiro de homologação manual dividido em 2 trilhas — uma técnica (infra/rede) e uma de regra de negócio (saúde/direito/comunicação).

Veja `docs/HOMOLOGACAO-DEMO.md` (gerado após a reunião de abertura do projeto de extensão em 26/05/2026).

A ideia: você abre o demo, segue o roteiro, anota cada quebra encontrada como issue no GitHub. Issues encontradas pela trilha de homologação são candidatas naturais a `good-first-issue` para outros extensionistas.

---

## Como abrir um Pull Request

1. **Antes de qualquer coisa:** assine o Termo de Contribuição em `CONTRIBUTOR-LICENSE.md`. Sem assinatura, PRs não são merged.
2. **Pegue uma issue.** Escolha `good-first-issue`, comente "eu pego".
3. **Crie branch** com nome descritivo: `feat/demo-bootstrap-extract` ou `fix/seed-demo-cnes`.
4. **Faça o trabalho.** Commits pequenos, mensagens em português no padrão convencional: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`.
5. **Rode `pytest -q` antes do PR.** Se quebrar testes que já estavam verdes, conserte antes de submeter.
6. **Abra o PR** com descrição clara: o que faz, por quê, qual issue fecha (use `Fixes #56`).
7. **Aguarde revisão.** Vou (Fabiano) ou outro revisor olhar em 1-3 dias úteis. Pode pedir ajustes — isso é normal.

---

## FAQ

**P: `pip install -r requirements.txt` está dando erro de versão do Python.**
R: Confirme `python3 --version` — precisa ser 3.10 ou superior. Se você tem Python mais antigo, instale uma versão recente via [pyenv](https://github.com/pyenv/pyenv) (macOS/Linux) ou direto do [python.org](https://www.python.org/downloads/) (Windows).

**P: Subi o backend mas `http://localhost:8000` mostra erro 404 ou tela em branco.**
R: Em modo demo o frontend mora no diretório-raiz do repo (não dentro de `backend/`). O comando do Quick Start usa `--app-dir .` para servir os HTMLs. Se você usou outro comando, abra direto `http://localhost:8000/index.html`.

**P: Não consigo fazer login. A tela só mostra os 3 cards.**
R: Isso é o comportamento correto em demo — login real está desabilitado. Clique em um dos 3 cards (Prescritor / Dispensador / Cidadão) e você entra direto como a persona pré-semeada.

**P: Quero ver dados reais ou meus próprios dados.**
R: Demo é demo. Não use seu CPF real, não cadastre dados que você não quer perder no próximo reset horário. Para desenvolvimento "normal" (sem demo), tire a env var `PICSAUDE_DEMO_MODE` e use `seed_dev.py` em vez do `reset_demo_db.py`.

**P: Quebrei alguma coisa rodando os testes. O que faço?**
R: Antes de assumir que é seu problema: 27 testes falham por motivos pré-existentes (documentados em `docs/PLANO-PRODUCAO-V2.md`). Verifique se a falha é uma das 27 conhecidas. Se for nova, **isso é um achado** — abra issue com a saída de `pytest -v` colada.

**P: Posso usar IA (Claude, ChatGPT, Copilot) para ajudar no meu PR?**
R: Sim, contanto que você entenda o código que está submetendo. Se a IA gerou algo que você não consegue explicar em uma revisão, refaça. PRs onde o autor não consegue defender as escolhas são rejeitados.

**P: Encontrei algo errado no `CLAUDE.md` ou na arquitetura. Posso propor mudança?**
R: Sim, mas com cuidado. Mudanças em `CLAUDE.md`, no ledger, em estados, ou em custódia são classe `core` (veja `CLAUDE.md` §10) e exigem revisão arquitetural. Abra issue primeiro com a proposta, discutimos antes de você gastar tempo implementando.

---

## Suporte

- **Coordenador do projeto:** Fabiano Tonaco Borges — `fabianotonaco@gmail.com`
- **Issues técnicas:** abra no GitHub com label `docs` ou `bug` (`https://github.com/Tonaco-13/PicSaude/issues`)
- **Dúvidas durante reuniões de extensão:** traga a tela / repo / erro abertos. Resolver presencialmente é mais rápido que via e-mail.

---

*Bem-vindo à equipe. O SUS é o maior sistema universal de saúde do mundo. Está nas suas mãos também — agora.*
