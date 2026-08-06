# HANDOFF — Frontend da demo (dispensador) para o Kimi 3

| Campo | Valor |
|---|---|
| **De** | GLM-5.2 (arquiteto de backend + dono do contrato de API) |
| **Para** | Kimi 3 (arquiteto de frontend + programador) |
| **Data** | 2026-08-02 |
| **Escopo** | Tickets da **família F5** — frontend do **`dispensador.html`** |
| **Classe** | `module` (todos — frontend de módulo de dispensação) |
| **Fora deste handoff** | `cidadao.html` (Etapa C, em pausa), `prescritor.html` (TICKET-DEV-MODE), análise do aluno (entra depois como anexo) |

---

## §0 Sumário executivo (leia primeiro)

A família F5 já está **implementada e mergeada** no `main` (commits de 2026-07-11). O trabalho que sobra pro Kimi 3 **não é implementar features** — é **fechar o critério de aceite que faltou**: os **testes browser-E2E** que os tickets B1 e B2 exigem como gate, e que **não existem** no repositório.

| O que | Status |
|---|---|
| Código de `dispensador.html` (B1/B2/B3) | ✅ Mergeado em `main` |
| Testes browser-E2E `test_f5_b1*` / `test_f5_b2*` | ❌ **Não existem** — é a sua entrega |
| Teste de regressão "Etapa C" (cidadao.html) | ⏸️ Em pausa, fora deste handoff |

**Sua missão:** escrever `backend/tests/browser/test_f5_b1_relatorio_botoes.py` e `test_f5_b2_ciclo_pos_dispensacao.py`, **no padrão do codebase**, fazendo-os passar contra `app_demo` local. Nada de mexer no código de produção sem evidência de regressão.

---

## §1 Sua fronteira (importante)

Pelo ORGANIZAÇÃO_AGENTES (§2):

> O contrato de API é desenhado e mantido pelo **arquiteto de backend**. O **frontend consome** esse contrato; nunca o inventa nem o contorna.

Praticamente:

1. **Os endpoints já existem e estão mergeados.** Você **consome**, não cria.
2. Se encontrar divergência entre o ticket e o comportamento real do backend, **não ajuste o frontend pra casar com a sua leitura** — abra um apontamento aqui neste handoff (ou me pergunte). A fonte de verdade é o backend.
3. Frontend nunca calcula estado que o backend já provê (`i.estornado`, `i.acionavel`, `saldo_efetivo`). Se o código de produção estiver fazendo isso, é bug — me acione, não corrija unilateralmente.

---

## §2 O que já está mergeado (referência, não trabalho novo)

Tudo abaixo está no `main`. Consulte como **referência do contrato**, não como pendência.

| Escopo | Commit | PR | Arquivo:âncora (verificado 2026-07-25) |
|---|---|---|---|
| **B0** — guard por saldo efetivo (backend) | `ea95bc4` | #90 | `backend/app/routers/custodia.py:33,737-743,867` |
| **§5.A** — comprovante expõe estorno (backend) | #92 | #92 | `backend/app/routers/dispensacoes.py:105,130` |
| **B1** — botões Relatório/SNGPC na fila | `2e7ffda` | #91 | `dispensador.html:442-444` (handlers `:1721`, `:1759`) |
| **B2** — ciclo pós-dispensação + remove dev. prescritor | `47239a5` | #93 | `dispensador.html:1299` (`_renderizarFila`), `:1308` (`p.itens.some(i => i.acionavel)`), `:1817` (`_renderHistorico`) |
| **B3** — carimbo ESTORNADO no comprovante | `9062513` | #94 | `dispensador.html:1545-1577` (`_renderComprovante`) |

**Tire um momento pra ver as âncoras no código** — elas são o ponto de partida dos testes que você vai escrever.

---

## §3 Sua entrega — os 2 testes browser-E2E faltantes

### 3.1 `test_f5_b1_relatorio_botoes.py`

**Ticket-fonte:** `docs/tickets/TICKET-F5-B1-RELATORIO-BOTOES.md` §6.

**Régua (direto do ticket):**
```python
def test_b1_botoes_relatorio_funcionam(browser_demo):
    """Os 3 botões no cabeçalho da fila respondem ao clique."""
    # Login demo dispensador
    # Snapshot do cabeçalho da fila (.fila-card-head)
    # Clicar em "SNGPC CSV" → validar que fetch foi feito com Bearer
    #   (intercept network; assert request tem header Authorization)
    # Clicar em "SNGPC PDF" → idem
    # Clicar em "Relatório Consolidado" → validar #print-area visível
    # Trocar JWT para dispensador_norte → CSV vem vazio (sem movimento)
```

**Invariantes que o teste deve afirmar (critérios §5 do B1):**
- Os 3 botões (Consolidado, CSV, PDF) **respondem ao clique** — bug histórico era "Relatório Consolidado não responde".
- **Nunca** existe `<a href>` pro endpoint (PII vazaria sem auth). `rg -n 'href.*relatorio' dispensador.html` deve continuar zero.
- Trocar de dispensador (CNPJ B) → CSV não contém movimento do dispensador A (isolamento por CNPJ do JWT).
- Erro de backend renderiza `detail.mensagem` (não `[object Object]`).

> **Aviso do arquiteto:** o ticket B1 dizia "3 botões" mas o código real (`dispensador.html:442-444`) tem **3 botões** — `Relatório Consolidado`, `SNGPC CSV`, `SNGPC PDF`. Confirme o DOM real antes de codar o seletor.

### 3.2 `test_f5_b2_ciclo_pos_dispensacao.py`

**Ticket-fonte:** `docs/tickets/TICKET-F5-B2-CICLO-POS-DISPENSACAO.md` §6.

**5 cenários obrigatórios:**
```python
def test_b2_escopo_a_fila_so_dispensaveis(browser_demo):
    """Receita com todos os itens terminais não aparece na fila."""
    # Setup: prescrição com 1 item, dispensar total (saldo 0)
    # Assert: receita NÃO está na fila
    # Assert: receita ESTÁ no histórico

def test_b2_escopo_a_reentrada_por_estorno(browser_demo):
    """Após estornar dispensação total, receita reaparece na fila."""
    # Setup: dispensar total → receita sai da fila
    # Estornar a dispensação
    # Refresh da fila
    # Assert: receita VOLTOU pra fila com saldo > 0

def test_b2_escopo_b_botao_estorno_estado_do_backend(browser_demo):
    """Botão Estorno só habilitado se !i.estornado (do backend)."""
    # Histórico de dispensação estornada → badge "ESTORNADO", sem botão Estorno
    # Histórico de dispensação não estornada → botão Estorno habilitado

def test_b2_escopo_c_comprovante_estornado(browser_demo):
    """Comprovante de dispensação estornada tem carimbo."""
    # Dispensar → estornar → abrir comprovante
    # Assert: carimbo "DISPENSAÇÃO ESTORNADA" visível no topo
    # Assert: ref. estorno protocolo visível
    # Assert: dados originais (qtd, lote) permanecem (R1 — não edita)
    # Assert: protocolo_prescricao não mudou (§6b Regra de Ouro)

def test_b2_escopo_c_comprovante_nao_estornado(browser_demo):
    """Comprovante de dispensação não estornada permanece idêntico."""
    # Dispensar (sem estornar) → abrir comprovante
    # Assert: NÃO tem carimbo "ESTORNADO"
```

**Invariantes que o teste deve afirmar (do ticket B2 §5):**
- `grep -nE "i\.estornado\s*=\s*[^=]" dispensador.html` retorna **zero** — o cliente nunca calcula estornado. (Esse é um guarda estático, pode ser um teste unitário paralelo.)
- Comprovante **não apaga/edita** a dispensação original (R1).
- Protocolo da prescrição e `dispensacao_id` **idênticos** antes/depois do estorno em fila, histórico, comprovante (§6b — Regra de Ouro).
- **Nenhuma linha apagada** em `dispensacoes`/`estornos`/ledger (verificação por contagem antes/depois — lição do COER-2).

> **Lição crítica do codebase (LEARNINGS do COER-2):** o E2E **deve afirmar sobre o DOM renderizado**, não sobre respostas de API isoladas. Foi um agente navegando a demo que pegou os bugs de posse dupla que 22 testes PG não pegaram.

---

## §4 Padrões do codebase que você deve seguir

### 4.1 Ambiente de teste
- **Venv:** `~/picsaude-venv/bin/python3` (Python 3.12.8, pytest 9.1.1, playwright 0.8.0)
- **Workdir:** `backend/`
- **Rodar:** `cd backend && python -m pytest tests/browser/test_f5_b1_relatorio_botoes.py -v`
- **Conftest:** `backend/tests/browser/conftest.py` provê `app_demo`, `browser_demo`, helpers de login. **Leia antes de escrever.**
- **Marker `externo`** em `pytest.ini` — para testes que sobem contra `picsaude.com.br` (não é o caso destes dois; eles rodam locais contra `app_demo`).

### 4.2 Personas demo (já no seed)
| Papel | Identificador |
|---|---|
| Prescritor | CNS `980001112223334` (Dra. Demo Maria Souza) |
| Paciente | CPF `12345678909` |
| Farmácia Central | CNPJ `99999999000191` |
| Farmácia Norte | (outro CNPJ — confira no seed; usado no teste de isolamento) |

Login demo: `POST /demo/login` com `{"role": "dispensador"}` → `access_token`.

### 4.3 Convenções obrigatórias (do AGENTS.md)
- **R1 (reprodutibilidade):** comprovante/relatório são projeção do ledger. A UI não computa, só exibe.
- **§10 (estados computados não persistidos):** `i.estornado`, `i.acionavel`, `saldo_efetivo` vêm do backend. Teste deve **afirmar** que o cliente não recalcula.
- **§6b (Regra de Ouro):** protocolo e dispensacao_id são imutáveis e idênticos em qualquer tela.
- **PII-EXAUSTIVIDADE:** relatório é PII (comprador/paciente/prescritor). Sempre `fetch` + Bearer + blob. Teste deve afirmar o header `Authorization`.

---

## §5 Possíveis armadilhas (aviso do arquiteto)

1. **B1 "Relatório Consolidado" já quebrou antes** (não respondia ao clique). Seu teste é exatamente a proteção contra regressão desse bug. Se ele quebrar de novo, seu teste deve pegar — não afrouxe o seletor pra fazer passar.

2. **A asserção `#print-area` visível pode precisar de espera explícita** (não `networkidle`). Veja `TICKET-SMOKES-WAIT-PRIMITIVE.md` — o codebase está migrando de `networkidle` pra espera explícita. Use o padrão que o `conftest.py` atual preferir.

3. **B0 (guard por saldo) é backend.** Você não testa a lógica do B0 — você testa que o **frontend reflete** `i.acionavel` corretamente. Se o teste de "reentrada por estorno" falhar, o bug pode ser backend (B0) ou frontend (renderização). **Antes de alterar frontend, confirme comigo** — pode ser backend.

4. **`p.itens.some(i => i.acionavel)` é a regra de exibição da fila (B2 §4.1).** Não use `_FILA_TERMINAIS` sozinho pra decidir acionabilidade — um item `dispensado` com saldo reposto por estorno é **acionável** (esse é o ponto do B0). Seu teste de "fila só dispensáveis" deve refletir essa semântica.

5. **Contagem de linhas do ledger.** No teste de comprovante estornado, verifique que `SELECT count(*) FROM dispensacoes` e `FROM estornos` não diminuem. Isso protege o invariante do ledger imutável (AGENTS.md §2).

---

## §6 Fora de escopo (não fazer)

- **Não mexa em código de produção sem evidência de regressão.** Os PRs #90-94 estão mergeados. Se um teste falhar, **primeiro me pergunte** — pode ser bug legítimo (eu abro ticket `core`) ou pode ser teste errado (você ajusta).
- **Não reabra a implementação B1/B2/B3** sem regressão visual ao vivo.
- **Não toque em `cidadao.html`** (Etapa C, em pausa, handoff separado).
- **Não crie endpoints novos.** O contrato de API é meu.
- **Não reescreva `conftest.py`** sem conversar comigo.

---

## §7 Fluxo de aprovação

1. Você implementa os 2 testes → roda local → tudo verde contra `app_demo`.
2. Abre PR com branch `module/f5-b1-b2-browser-e2e`.
3. **Claude Code (app)** revisa contra os tickets B1/B2 §5-§6 (gate bloqueante).
4. **Claude Fable 5** dá parecer leve (só confirma padrão).
5. Eu ratifico.
6. Martelo do Fabiano + merge.

---

## §8 Quando me acionar (sem hesitar)

- Qualquer divergência entre o ticket e o comportamento real do backend.
- Qualquer bug que suspeite ser de backend (B0, comprovante, estorno).
- Qualquer tentação de "afrouxar" um seletor ou asserção pra fazer passar.
- Se `conftest.py` não der um helper que você precisa (pode ser gap de infra — me chame antes de duplicar).

---

## §9 Anexo pendente

**Análise do aluno** — entregue (ver §10 abaixo). Resolvido.

---

## §10 Achados de UX do extensionista (anexo do Fabiano, 2026-08-02)

> O Fabiano trouxe 3 observações de um extensionista/aluno sobre a demo, mais uma imagem de referência (formulário "DADOS CLÍNICOS DO PACIENTE"). Fiz **triagem arquitetural**: cada achado tem classe e responsável distintos. **2 dos 3 têm camada de backend que é minha, não do Kimi 3.**

### Achado A — "A logo do PicSaúde poderia voltar ao menu principal" 🟢 **FRONTEND (Kimi 3)**

**Hoje:** a logo é decorativa (não clicável) em todos os módulos. O "voltar ao portal" é um `<a href="index.html">← Portal</a>` pequeno e cinza (`#64748b`, 12px) ao lado da logo.

| HTML | Logo (linha) | "← Portal" (linha) | Obs. |
|---|---|---|---|
| `index.html` | 419 | — (é o portal) | — |
| `prescritor.html` | 325 | 328 | |
| `dispensador.html` | 346 | 350 | |
| `cidadao.html` | 295 | 298 | |
| `clinica.html` | 467 | 472 | |
| `validar.html` | 160 | 163 | |
| `guia.html` | ❌ sem logo | ❌ sem botão | **exceção** — só header textual |

**Implementação (Kimi 3):** envolver a `<img class="header-logo">` num `<a href="index.html" aria-label="Voltar ao portal PicSaúde">`. Adicionar affordance (cursor pointer, `:hover` sutil). **Não remover** o "← Portal" existente — manter ambos (a logo como affordance primário, o texto como secundário).

**Fronteira:** zero backend. `class: local-extension` (UI pura, sem impacto clínico). **Fora do escopo:** decidir se `guia.html` ganha header de portal (é exceção por design — explicar página pública, não é módulo operacional).

---

### Achado B — "Cor do asterisco + mensagem de destaque pra campos obrigatórios (acessibilidade)" 🟢 **FRONTEND (Kimi 3)**

**Hoje (`prescritor.html`):**
- O asterisco `*` é **texto literal colado no `<label>`** (`<label class="form-label">Nome Completo *</label>`), sem `<span>`, sem classe própria.
- CSS `.form-label` (linha 26): `color: #475569` (cinza-escuro). **O asterisco herda essa cor** — não tem destaque.
- Sem `aria-required`, sem `:invalid`, sem borda vermelha, sem mensagem inline. A validação depende **só do balão nativo do browser** no `submit`.

**Implementação (Kimi 3):**
1. **Acessibilidade semântica (prioritária):** adicionar `aria-required="true"` nos inputs obrigatórios (hoje só têm `required` HTML). Leitor de tela hoje lê "asterisco" sem semântica.
2. **Cor do asterisco:** encapsular o `*` num `<span class="obrigatorio" aria-hidden="true">*</span>` e estilizar com cor de destaque (ex.: `#dc2626` vermelho) — visível sem depender de leitor.
3. **Feedback visual de erro:** ao submeter com campo obrigatório vazio, aplicar classe `.input-erro` (borda vermelha) + mensagem inline abaixo do campo. Preferir `reportValidity()` customizado ou interceptar o `submit` antes do nativo.

**Fronteira:** zero backend. `class: local-extension` (UI/UX). **Padrão a definir:** se Kimi 3 criar `.obrigatorio` e `.input-erro`, aplicar de forma **consistente** em todo o prescritor (não só no bloco "Dados Clínicos"). Pode estender a `cidadao.html`/`dispensador.html` depois — mas escopo inicial é `prescritor.html`.

**⚠️ Não fazer:** não inventar estados de validação que escondam o feedback nativo do browser sem substituí-lo por algo equivalente ou melhor.

---

### Achado C — "Renovação devia pré-preencher os dados do paciente" 🟢 **FRONTEND (Kimi 3)** — DESBLOQUEADO

> **Decisão ratificada (Fabiano + parecer verde Fable 5, 2026-08-02):** opção **(c)** — cache de paciente por CPF no `localStorage` do `prescritor.html`. Classe `local-extension`. **Kimi 3 pode implementar.** Dívida core registrada em `docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md`.

**O que acontece hoje (`prescritor.html`):**
- A função `renovarReceita(id)` (linha 2293) **chama `_preencherFormularioReceita(r)`** (linha 1518) que **pré-preenche** nome, idade, telefone, endereço, CEP, cidade/UF e medicamentos. **A intenção de pré-preencher já existe.**
- **Porém:** o objeto `r` vem de `_receitaDoBackend(pres)` (linha 1489), que do backend só tira `paciente_nome`, `paciente_cpf` e `itens`. Os outros campos (idade, telefone, endereço, CEP, cidade/UF) **só aparecem se** houver uma cópia física da receita no `localStorage` (`pix_saude_db_v27`). Para uma **prescrição digital** (fonte de verdade = backend), **esses 5 campos ficam em branco** na renovação → prescritor redigita.

**Causa-raiz (documentada, não reabrir):** a tabela `pacientes` (DDL `docs/picsaude_ddl_postgres_v1.sql:90-100`) só persiste `cpf`, `nome`, `telefone`, `ativo`. Não há colunas de idade/endereço/CEP/cidade. Persistência real é `core` e fica como dívida.

### Spec técnica do paliativo (opção c) — Kimi 3 implementa

**Mecanismo:** cache de dados do paciente no `localStorage`, **indexado por CPF normalizado**.

**1. Quando gravar (write-through na emissão):**
- Ao emitir (ou renovar) uma receita **digital**, após o `POST /prescricoes` retornar sucesso, gravar no `localStorage` um registro sob a chave `pix_saude_pacientes_cache` (objeto JSON mapeando `cpf → dados`):
  ```js
  {
    "12345678909": {
      "nome": "...", "idade": "...", "telefone": "...",
      "endereco": "...", "complemento": "...", "cep": "...",
      "cidade": "...", "uf": "PE",
      "atualizado_em": "2026-08-02T..."
    }
  }
  ```
- Usar CPF **normalizado** (só dígitos, via `normalize_cpf` ou equivalente) como chave — nunca o CPF formatado.
- Também gravar no fluxo **físico** (que já usa `pix_saude_db_v27`) — unificar ou manter consistência entre os dois (decisão do Kimi 3; documentar no PR).

**2. Quando ler (pré-preencher na renovação):**
- Em `_receitaDoBackend(pres)` (`prescritor.html:1489`), **antes** de cair no fallback de `pix_saude_db_v27`, tentar o cache por CPF:
  ```js
  const cache = JSON.parse(localStorage.getItem('pix_saude_pacientes_cache') || '{}');
  const cached = cache[normalizeCpf(pres.paciente_cpf)] || {};
  // usar cached.idade, cached.telefone, cached.endereco, etc. quando o backend não prover
  ```
- A precedência é: (1) backend (se algum dia prover) > (2) cache por CPF (`pix_saude_pacientes_cache`) > (3) receita física local (`pix_saude_db_v27`) > (4) vazio.

**3. Higiene:**
- **Não crescer indefinidamente.** Limitar o cache aos últimos N pacientes (ex.: 50) por LRU, ou por data (`atualizado_em`). Decisão do Kimi 3 — documentar o critério de despejo no PR.
- **PII em `localStorage`:** aceitável para demo/local. Registrado como trade-off na dívida core.

**Critérios de aceite:**
1. Após emitir uma receita digital, abrir a renovação dela → **todos** os campos do paciente (nome, idade, telefone, endereço, complemento, CEP, cidade, UF) vêm pré-preenchidos.
2. Renovar uma receita de um paciente cujos dados só existem no cache → pré-preenchimento funciona (não depende de `pix_saude_db_v27`).
3. A chave do cache é o CPF **normalizado** (só dígitos) — testar com CPF formatado e sem formatação.
4. Cache tem limite (LRU ou data) — documentado no PR.

**Fronteira:** `local-extension` (não toca backend, não toca núcleo). **Não criar endpoint.** Dívida core (persistência real) está registrada e é minha — Kimi 3 não se preocupa com ela.

**⚠️ Achado adjacente (registrado, fora deste escopo):** `renovarAtestado` **não existe** em lugar nenhum, e o backend de atestados (`atestados.py:66`) só aceita `tipo_emissao ∈ {"nova","correcao"}` — **atestados não suportam renovação**. Se houver decisão de suportar, é outro ticket (frontend + backend).

---

### Resumo da triagem (§10)

| Achado | Classe | Quem implementa | Pré-requisito |
|---|---|---|---|
| **A** — Logo → portal | `local-extension` | **Kimi 3** (frontend puro) | Nenhum |
| **B** — Acessibilidade asterisco/erro | `local-extension` | **Kimi 3** (frontend puro) | Nenhum |
| **C** — Renovação pré-preenche paciente | `local-extension` (paliativo) | **Kimi 3** | ✅ **Decidido** (opção c) — pode implementar |

> **Achado C desbloqueado em 2026-08-02** (Fabiano + parecer Fable 5). Persistência real no backend é `core` e ficou como dívida (`docs/dividas/DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO.md`).

---

## §11 DEMO SEM LOGIN — decisão do Fabiano (2026-08-02)

> "Para a demo não vamos ter login (continuar sem login)."

**Decisão ratificada (Fabiano + parecer verde Fable 5, 2026-08-02):**
- ✅ **Portal mantém o seletor de personas (1 clique).** "Sem login" significa **sem digitar senha** — o usuário escolhe o papel com 1 clique no card e é redirecionado autenticado. **O seletor NÃO é removido.**
- ✅ **RBAC/auth não é tocado.** "Demo sem login" é **frontend puro** — o backend já emite JWT real via `POST /demo/login`, e o `require_role` não sabe que é demo.

**Triagem arquitetural: a decisão cai majoritariamente no frontend, sem tocar o core de RBAC.** O backend já foi projetado pra isso (TICKET-6) — o `POST /demo/login` emite JWT real (assinado com o mesmo `JWT_SECRET`), e o `require_role` não sabe que é demo. **Eu (backend) não preciso mexer em `auth/dependencies.py` nem em `auth/jwt.py`.**

### Estado atual (como a demo autentica hoje)

| Ponto de entrada | O que o usuário vê | Auto-logado? |
|---|---|---|
| **Portal `index.html`** (canônico) | Seletor de personas (cards "Entrar como Prescritor/Dispensador/Cidadão") | Após **1 clique** no card → redireciona autenticado |
| **`dispensador.html` direto** | Dashboard direto | ✅ **Sim** — tem `_autoLoginDemo` (`:2598`) |
| **`prescritor.html` direto** | Tela de login/OTP | ❌ **Fica preso** (só tem `_hidratarSessaoDemo`) |
| **`cidadao.html` direto** | Tela de CPF → OTP | ❌ **Fica preso** (só tem `_hidratarSessaoDemo`) |
| **`clinica.html` direto** | Banner "sem persona demo" | ❌ Sem caminho |

Ou seja: "demo sem login" hoje é **parcial** — só o dispensador via URL é transparente. Pelo portal exige 1 clique no card; pelos outros módulos diretos, o usuário vê tela de login e trava.

### O que muda (escopo Kimi 3 — frontend puro)

**Replicar o padrão `_autoLoginDemo` do `dispensador.html:2598-2621` em `prescritor.html` e `cidadao.html`:**
- Cada módulo, ao carregar, se `cfg.demo_mode === true` e sem sessão hidratada, chama `POST /demo/login` com sua role (`prescritor` / `paciente`) e pula a tela de login/OTP direto pro dashboard/carteira.
- `prescritor.html`: hoje `:4055-4073` só tem `_hidratarSessaoDemo`. Adicionar `_autoLoginDemo` (análogo ao dispensador) que chama `POST /demo/login {role:'prescritor'}`.
- `cidadao.html`: hoje `:1923-1942` só tem `_hidratarSessaoDemo`. Adicionar `_autoLoginDemo` com `{role:'paciente'}` que pula `tela-acesso`/`tela-validacao` e chama `entrarNaCarteira()`.
- **Decisão de produto (Fabiano, ratificada 2026-08-02):** o portal (`index.html`) **mantém** o seletor de personas (1 clique). "Sem login" = sem digitar senha, não sem o clique. O suporte a `?demo_role=X` (`:402-407`) permanece como atalho opcional para deep-linking.

### O que NÃO muda (backend — meu, e fica como está)

- **NÃO** criar bypass de `require_role` em DEMO_MODE. Tocar `auth/dependencies.py` = `core`, abriria superfície de segurança. O guardrail de boot (`main.py:94-122`) já sinaliza: demo é sandbox, não relaxamento de RBAC.
- **NÃO** criar middleware que injete JWT default. O padrão atual (cada módulo chama `/demo/login`) é mais limpo e rastreável.

### Pontos de atenção (Kimi 3)

1. **Persona do cidadão é `role: 'paciente'`** (não `'cidadao'`) — `demo.py:60-66`, por compatibilidade com routers reais. Usar `'paciente'` no body do `/demo/login`.
2. **`clinica.html` não tem persona demo.** Decisão de produto necessária: ganha persona, ou continua bloqueada na demo? Se ganhar, eu (backend) adiciono entrada em `_PERSONAS` (`demo.py:39`).
3. **`prescritor.html` tem lógica `DEV_TOKEN`** (`:1308-1317`, `DEV_MODE=false` hard-coded) — **não confundir** com fluxo demo. `DEV_TOKEN` é atalho offline-only; o `/demo/login` é o caminho real.
4. **`DEV_PRESET_CONTEXT`** em `clinica.html:639` (`true`) é login real automático (`Demo@2024`) — em demo mode o backend rejeita. Esse caminho morre em demo; não é relevante.

### Fronteira resumida (§11)

| Componente | Classe | Quem |
|---|---|---|
| `_autoLoginDemo` em prescritor/cidadao | `local-extension` | **Kimi 3** |
| Decisão sobre portal `index.html` (manter seletor vs. redirect direto) | produto | **Fabiano** |
| Persona demo pra `clinica.html` (se quiser) | `module` (backend) | **GLM-5.2** |
| Bypass de `require_role` em DEMO_MODE | ❌ **proibido** — `core` | (nenhum) |

---

## §12 Priorização consolidada pro Kimi 3

> 🟢 **Todos os itens abaixo estão DESBLOQUEADOS** (decisões ratificadas em 2026-08-02: portal mantém seletor; item C = opção c).

| # | Item | Classe | Quem | Estado |
|---|---|---|---|---|
| 1 | Testes E2E B1/B2 (§3) | `module` | Kimi 3 | 🟢 **prioridade 1 — entrega principal** |
| 2 | Logo → portal (§10.A) | `local-extension` | Kimi 3 | 🟢 pronto pra ir |
| 3 | Acessibilidade asterisco/erro (§10.B) | `local-extension` | Kimi 3 | 🟢 pronto pra ir |
| 4 | Demo sem login — auto-login nos módulos (§11) | `local-extension` | Kimi 3 | 🟢 portal decidido (mantém seletor 1-clique) |
| 5 | Renovação: cache paciente por CPF no `localStorage` (§10.C) | `local-extension` | Kimi 3 | 🟢 desbloqueado (opção c ratificada) |

**Ordem sugerida:** 1 (principal) → 2 + 3 (rápidas e independentes) → 4 (portal decidido) → 5 (spec pronta). Todas podem rodar em paralelo se o Kimi 3 preferir.

**Fora do escopo Kimi 3 (são meus ou são dívida):**
- Persistência real de dados do paciente no backend → `core` (dívida `DIVIDA-CORE-PACIENTE-DADOS-RENOVACAO`).
- Persona demo pra `clinica.html` (se o Fabiano quiser) → eu adiciono em `_PERSONAS`.
- Bypass de `require_role` → **proibido**.

---

*Handoff redigido pelo arquiteto de backend (GLM-5.2). Dúvida técnica sobre o contrato de API = comigo. Dúvida sobre padrão de teste = com o revisor (Claude Code/app). Decisão de merge = Fabiano.*
