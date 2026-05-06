# RT-002 — Bugs conhecidos antes do primeiro commit

| Campo | Valor |
|---|---|
| **Status** | 🟡 OPEN (backlog) |
| **Criado em** | 2026-05-05 |
| **Autor** | Claude Opus (Cowork) com base em sessão de teste E2E |
| **Solicitante** | Fabiano Tonaco Borges |
| **Decisão** | Bugs aceitos como dívida técnica — viram issues no GitHub assim que o repositório for criado (Etapa 2) |

---

## Contexto

Durante 2 dias de sessão de setup + teste E2E (2026-05-04 e 2026-05-05), foram identificados múltiplos bugs no estado atual do PicSaúde. **Não são introduzidos pela sessão** — são pré-existentes ou de integração entre tickets. A decisão foi prosseguir com o cronograma de produção (Etapas 1-9 do plano original), tratando estes bugs como **backlog público** após o repositório estar criado.

Este RT-002 lista todos os bugs encontrados, classifica gravidade e estima esforço, pra orientar:
1. Qual virar `good first issue` para os 7 estudantes de extensão
2. Qual virar issue `bug` priorizada pelo coordenador
3. Qual virar `enhancement` pra futuro

---

## Bugs identificados

### 🔴 Críticos (afetam fluxo principal)

#### B1 — Carteira digital silencia entrega quando paciente é novo
**Localização:** `backend/app/routers/prescricoes.py:547`
**Sintoma:** Prescrição emitida com `enviar_ao_paciente: true` para CPF nunca cadastrado fica em `pendente`. A custódia não é criada e não há aviso ao prescritor.
**Causa:** `if payload.enviar_ao_paciente and paciente_existia` — ignora quando paciente acabou de ser criado.
**Impacto:** Receita não aparece na carteira do paciente. Frustra a "ideia central" do PicSaúde (paciente como detentor).
**Esforço:** Médio. Decisões de design: (a) sempre entregar mesmo se paciente novo, ou (b) avisar explicitamente que o paciente precisa fazer onboarding antes.
**Sugestão de label:** `bug`, `regulatorio`

#### B2 — JWT só em memória, perde ao mudar de página
**Localização:** `prescritor.html:760`, `cidadao.html:371`, `dispensador.html`, `clinica.html`
**Sintoma:** Usuário loga, navega para outra página/módulo, e volta — está deslogado. Tem que logar de novo.
**Causa:** `let jwtAccessToken = null;  // Bearer token em memória (não persiste em localStorage)` — escolha intencional de design (segurança contra XSS), mas sem refresh token funcional não há persistência.
**Impacto:** Em janela única dentro do mesmo módulo, OK. Em fluxos cross-módulo (prescritor → paciente → dispensador), exige re-login a cada troca.
**Esforço:** Médio. Implementar refresh token via httpOnly cookie ou aceitar localStorage com sanitização CSP.
**Sugestão de label:** `bug`, `security`

#### B3 — IA DEF retorna sugestões pobres
**Localização:** `data/def_medicamentos.csv` (42 linhas) + `backend/app/ai/lookup_def.py`
**Sintoma:** Ao digitar medicamento na IA do prescritor, sugere apresentação mas não preenche dose/forma/posologia. Em alguns casos não retorna nada.
**Causa:** Base CSV tem só 42 medicamentos. DEF brasileiro real tem ~70k registros.
**Impacto:** IA farmacêutica fica de demonstração apenas. Não dá pra prescrever a maioria dos medicamentos com sugestão automática.
**Esforço:** Médio-alto. Importar DEF completo (Anvisa) ou TUSS-MED (~50k itens).
**Sugestão de label:** `feature`, `enhancement`

#### B4 — DEV_PRESET_CONTEXT com senha hardcoded
**Localização:** `prescritor.html:2853`, `dispensador.html:1829`, `clinica.html:2116`
**Sintoma:** Senha fica fixa no código JS. Qualquer reset de senha no banco quebra o auto-login de teste.
**Causa:** Convenção informal de dev. Foi corrigido manualmente nesta sessão (senha alinhada com `seed_dev.py`), mas continua frágil.
**Impacto:** Setup de novos devs/estudantes fica frágil — basta alguém rodar `seed_dev.py` com outra senha que tudo quebra.
**Esforço:** Baixo. Criar `dev-credentials.json` (gitignored) que seed_dev e os HTMLs leem.
**Sugestão de label:** `bug`, `dx` (developer experience)

### 🟡 Importantes (UX, regulatório)

#### B5 — Validação de CPF no frontend
**Localização:** `prescritor.html` (campo `pac-chave`), antes era `replace(/\D/g, '')` sem checagem de comprimento.
**Status:** ✅ **CORRIGIDO nesta sessão** — adicionada validação de 11 dígitos rígida.
**Aprendizado:** Aplicar regra de "input strip + validação obrigatória" em todos os campos de identificadores (CPF, CNS, CNPJ).
**Sugestão de label:** `good first issue` (fazer o mesmo em outros campos)

#### B6 — Padronização de máscara CPF
**Status:** ✅ **CORRIGIDO nesta sessão** — `formatarCPF()` e `aplicarMascaraCPF()` no `config.js`, aplicados em prescritor + cidadão.
**Pendente:** Aplicar em `dispensador.html` e `clinica.html` (busca de paciente).
**Esforço:** Trivial. Adicionar classe `cpf-input` aos inputs.
**Sugestão de label:** `good first issue`

#### B7 — `requirements.txt` sub-declarado (deps transitivas escondidas)
**Status:** ✅ **CORRIGIDO nesta sessão** — adicionados `pyhanko==0.34.1`, `cryptography==44.0.0`, `rapidfuzz>=3.5,<4`, `pydantic>=2.0,<3`, `argon2-cffi>=23.1`. Antes só tinha `passlib[bcrypt]` mas o código usa argon2.
**Aprendizado:** Auditar pin/extras a cada release. Manter changelog do `requirements.txt`.
**Sugestão de label:** `docs`, `ops`

#### B8 — `seed_dev.py` desatualizado em relação a `GUIA_TESTE_CAMPO.md`
**Localização:** `backend/seed_dev.py` (senha real `Teste@2024`) vs `GUIA_TESTE_CAMPO.md` (senha documentada `Prescritor2026!`).
**Status:** ✅ **CORRIGIDO nesta sessão** — `prescritor.html` agora usa `Teste@2024`, banco resetado.
**Pendente:** Atualizar `GUIA_TESTE_CAMPO.md` com a senha real.
**Sugestão de label:** `docs`

### 🟢 Pequenos (cosméticos / DX)

#### B9 — `logo-picsaude.png` 404
**Sintoma:** Cabeçalho dos HTMLs tenta carregar `/logo-picsaude.png` que não existe.
**Causa:** Arquivo nunca foi commitado.
**Impacto:** Apenas estético — `onerror` esconde elemento. Mas log fica poluído com 404s.
**Esforço:** Trivial. Criar logo simples ou remover referência.
**Sugestão de label:** `good first issue`, `frontend`

#### B10 — CSP estrita bloqueia inline em dev
**Status:** ✅ **CORRIGIDO nesta sessão** — middleware `security_headers.py` agora gateia por `PICSAUDE_ENV`. Em prod mantém estrita.
**Pendente:** Migrar para CSP com nonces (corrigir limitação estrutural).
**Sugestão de label:** `security`, `enhancement`

#### B11 — Pacientes duplicados/inválidos no banco
**Sintoma:** Banco real tinha pacientes com CPF 10 dígitos, vazio, etc. — lixo de testes anteriores.
**Status:** ✅ Parcialmente limpo nesta sessão. Pacientes válidos mantidos. Lixo deixado por causa do ledger imutável (não permitia deletar prescrições associadas).
**Aprendizado:** Importante ter script de "limpar dados de teste" que respeite o ledger.
**Sugestão de label:** `enhancement`, `dev-tools`

### ⚙️ Arquiteturais (transição em andamento)

#### B12 — Dois modelos coexistindo: custódia tradicional vs carteira digital
**Localização:** `prescricao_custodia` (modelo tradicional) vs flag `enviar_ao_paciente: true` (Ticket 63 - carteira).
**Sintoma:** Lógica de transferência ao paciente parcialmente duplicada. Comportamentos divergentes.
**Esforço:** Alto. Requer decisão arquitetural: unificar ou manter separados com contrato claro.
**Sugestão de label:** `architecture`, `discussion`

---

## Bugs já corrigidos nesta sessão (resumo)

| # | Bug | Arquivo |
|---|---|---|
| ✅ | requirements.txt sub-declarado (5 deps) | `requirements.txt` |
| ✅ | config.js apontava p/ porta 8000 | `config.js` |
| ✅ | StaticFiles não montado em dev | `backend/app/main.py` |
| ✅ | CSP bloqueava inline em dev | `backend/app/middleware/security_headers.py` |
| ✅ | Senhas em formato bcrypt (deveria argon2) | banco — reset via script |
| ✅ | DEV_PRESET_CONTEXT com senha errada | `prescritor.html` |
| ✅ | Validação CPF inexistente | `prescritor.html` |
| ✅ | Máscara CPF inexistente | `config.js`, `prescritor.html`, `cidadao.html` |
| ✅ | Banco SQLite errado (vazio) sendo usado | `.env` |
| ✅ | catalogo_substancias vazio | seed rodado |
| ✅ | Rate limit travando dev | `RATE_LIMIT_DISABLED=1` no `.env` |

---

## Plano de transformação em GitHub Issues

Quando a Etapa 2 completar (repositório criado), cada bug acima vira issue:

- **`good first issue`** (estudantes): B5, B6, B8, B9
- **`bug`** (coordenador / time core): B1, B2, B4
- **`feature`** / **`enhancement`**: B3, B10, B11
- **`architecture`** (discussão de design): B12

---

## Status do sandbox no momento do commit

✅ Backend roda local (`./subir-local.sh`)
✅ Frontend integrado (StaticFiles mount em dev)
✅ Login dos 4 perfis piloto funciona
✅ OTP do paciente funciona
✅ Emissão de prescrição grava no banco
⚠️ Carteira digital não recebe automaticamente (B1)
⚠️ IA DEF retorna sugestões pobres (B3)
⚠️ Sessão perde ao trocar de aba (B2)
✅ Cert ICP-Brasil A1 do Fabiano (Serpro) preservado em `.sandbox/private/`
✅ Sandbox e secrets gitignored

**Conclusão:** sistema operacional para demonstração com dados reais (17k estabelecimentos, 40k profissionais), com bugs conhecidos e documentados. Pronto pra subir para versionamento e colaboração.
