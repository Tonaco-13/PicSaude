# Roteiro de homologação manual — Modo DEMO

> **Origem:** revisão de fim de etapa (Jules, lente §3.6 + §3.7 do briefing) sobre o commit `94f73cd feat(6): demo mode com sessões pré-semeadas`, adaptado pelo Arquiteto à luz do código real (`94f73cd` + `9eb7228`) em 2026-05-25.
> **Público:** os 7 extensionistas UFPE — equipe interprofissional (info / saúde / direito / comunicação).
> **Quando:** primeiro exercício prático da reunião de abertura (2026-05-26) e tarefa contínua de QA da equipe.
> **Objetivo:** validar o comportamento do PicSaúde em ambiente real de DEMO, **caçando falhas que os testes automatizados (pytest) não enxergam** — testes de UX, rede, navegador, regra de negócio.

> ⚠️ **Dados são efêmeros:** o banco demo é resetado **a cada hora cheia** (`scripts/reset_demo_db.py` via cron, ver Cenário 2). Um teste deixado pela metade pode não estar lá após a virada da hora. Conclua cada cenário de uma vez ou anote o que precisa preservar.

---

## Como funciona

A equipe se divide em **duas trilhas** segundo afinidade. Cada cenário tem objetivo claro, passo a passo e critério de sucesso. Quem encontrar bug:

1. Reproduz uma segunda vez para confirmar (não é flutuação)
2. Abre **issue no GitHub** com:
   - Título: `[homologação] cenário N: <resumo de 1 linha>`
   - Corpo: o que esperava ver, o que viu, navegador + versão, passo de reprodução
   - Label: `bug` (se quebra função) ou `ux` (se é estranho mas funciona)
3. Marca o item correspondente abaixo como **❌ encontrei bug — issue #XX**

A intenção é declaratória: **a meta de vocês hoje é tentar bugar essa tela**. Cada bug encontrado por extensionista é uma issue a menos para o coordenador descobrir depois em produção.

---

## Pré-requisitos

Você completou o setup do [`CONTRIBUTING-EXTENSAO.md`](../CONTRIBUTING-EXTENSAO.md) e tem o backend rodando localmente em `http://localhost:8000` com banner amarelo "MODO DEMO" visível.

Se não tem, faça o setup antes — sem o demo no ar, não há o que homologar.

---

## 🧑‍💻 Trilha 1 — Infraestrutura e Rede

**Perfil sugerido:** estudantes/profissionais de informática, engenharia, sistemas. Você vai mexer com DevTools, throttling de rede, requisições HTTP cruas.

### Cenário 1 — Teste do "Flicker" (latência de rede)

**Hipótese:** o banner "MODO DEMO" é renderizado via JavaScript que busca `/config/public` de forma assíncrona. Em rede lenta, pode haver janela onde a tela inicial aparece SEM banner antes do JS resolver. Visitante mal-intencionado poderia clicar em algo nessa janela.

**Como testar:**
1. Abra `http://localhost:8000`
2. Pressione `F12` para abrir DevTools
3. Aba **Network** → mude o seletor "No throttling" para **"Slow 3G"**
4. Recarregue a página sem cache (`Ctrl+Shift+R` ou `Cmd+Shift+R` no Mac)

**O que procurar:** a tela de seleção de personas aparece imediatamente sem banner amarelo? Você consegue clicar em algum card antes que a tela "pisque" e o banner apareça?

**Critério de sucesso:** ou o banner aparece junto da tela (sem flicker visível), ou o flicker é tão curto que não dá tempo de clicar em nada. Falha grave: tela funcional sem banner por mais de 1 segundo.

**Resultado:** ⬜ passou ⬜ ❌ bug #__

### Cenário 2 — Reset Horário (concorrência — opcional/assíncrono)

**Hipótese:** o reset do banco demo acontece a cada hora cheia (definido pelo `scripts/reset_demo_db.py` rodado via cron na Etapa 8). Se um usuário está no meio de uma operação no momento exato do reset, o que acontece?

**Como testar:**

*Versão presencial (rápida):* abra o backend localmente, derrube o banco demo via `PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py` em outro terminal **enquanto** você tem uma sessão aberta no navegador. Tente clicar em algo. Veja se o sistema retorna erro amigável ou explode com 500 silencioso.

> Nota: o script **aborta com exit 1** se você esquecer `PICSAUDE_DEMO_MODE=true`. Isso é proposital — defesa em profundidade contra reset acidental do banco de dev/prod (guard duplo introduzido em TICKET-6.1 P2#5).

*Versão assíncrona (precisa de tempo):* faltando alguns minutos para virar a hora (ex: 14:55), comece a preencher uma prescrição como Prescritor. **Exatamente às 15:00:00** (no momento que o cron rodar — em produção real), clique em "Emitir prescrição". Veja o que acontece.

**Critério de sucesso:** frontend lida com 401/403/500 de forma elegante, idealmente com mensagem "Sessão expirada — dados do demo foram resetados" ou similar. Falha grave: tela quebrada sem feedback, ou pior, dados parcialmente persistidos com IDs inválidos.

**Resultado:** ⬜ passou ⬜ ❌ bug #__

### Cenário 3 — Cache-busting do `/config/public`

**Hipótese:** o endpoint `/config/public` retorna o cabeçalho `Cache-Control: no-store` justamente para que proxies/CDNs/navegadores nunca cachem a resposta. Mas e se algum proxy intermediário ignorar esse cabeçalho?

**Como testar:**

```bash
# Em um terminal:
curl -I http://localhost:8000/config/public
```

Confira que a resposta contém:
- `Cache-Control: no-store`
- `Content-Type: application/json`

Depois abra `http://localhost:8000` no navegador, anote o horário do reset no banner ("Reset em XX min"). Feche a aba. Espere 5 minutos. Reabra a aba e veja o horário do banner.

**Critério de sucesso:** o horário do reset deve estar sempre correto (próximo ao horário real da hora cheia), nunca um horário do passado.

**Resultado:** ⬜ passou ⬜ ❌ bug #__

---

## 🧑‍⚕️ Trilha 2 — Experiência e Regra de Negócio

**Perfil sugerido:** estudantes/profissionais de saúde, direito, comunicação, gestão. Você não precisa de DevTools — vai testar como usuário real.

### Cenário 4 — Caixa de Areia (isolamento de dados + marca d'água)

**Hipótese:** o sistema demo tem 3 personas pré-criadas. Uma prescrição emitida pela Dra. Demo Maria Souza deve aparecer no histórico do paciente João Demo da Silva quando ele entrar como cidadão. O PDF gerado tem que ter marca d'água "DEMO" diagonal — sem isso o PDF poderia ser confundido com receita válida.

**Como testar:**

1. Abra `http://localhost:8000`. Clique no card **Prescritor** (Dra. Demo Maria Souza)
2. Emita uma prescrição com um medicamento bem estranho (ex: "Xarope de morcego 500mg", "Pó de unicórnio 1cp")
3. Vá ao Cidadão (botão de logout / volta para tela inicial → card Cidadão)
4. Verifique que a prescrição emitida aparece na lista do João Demo da Silva
5. Abra a versão PDF dessa prescrição

**Critério de sucesso:**
- O cidadão vê a prescrição na lista ✅
- O PDF tem marca d'água "DEMO" diagonal grande no fundo, em cinza, atravessando todo o documento ✅
- O texto da prescrição continua legível mesmo com a marca d'água ✅
- Cabeçalho do PDF é claramente identificado como Dra. Demo Maria Souza ✅

Falha grave: PDF sem marca d'água (poderia ser confundido com receita real) ou prescrição que não aparece no cidadão.

**Resultado:** ⬜ passou ⬜ ❌ bug #__

### Cenário 5 — Login real está bloqueado (mas o sistema responde com clareza)

**Hipótese:** em modo demo, os endpoints de login real (`/auth/token`, `/auth/registrar`, OTP de paciente) estão desativados — devem retornar HTTP 403 com código `demo_mode_ativo`. Não pode ser 401 "Not authenticated" genérico, nem 500.

**Como testar:**

*Via interface:* na tela inicial, em modo demo, você só vê os 3 cards de persona — não há formulário de login real. Confira que **não existe** botão "Entrar com CPF/senha" ou similar.

*Via API direta (precisa de curl):*

```bash
# Tentar login profissional real
curl -i -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=qualquer&password=qualquer"

# Tentar OTP paciente
curl -i -X POST http://localhost:8000/auth/paciente/solicitar-codigo \
  -H "Content-Type: application/json" \
  -d '{"cpf":"12345678901","telefone":"81999999999"}'
```

**Critério de sucesso:** ambos devem retornar **HTTP 403** com corpo JSON contendo `codigo: "demo_mode_ativo"` ou similar. Não pode ser 200 (login real funcionou — vazamento), não pode ser 401, não pode ser 500.

**Resultado:** ⬜ passou ⬜ ❌ bug #__

### Cenário 6 — Admin não aparece no demo público

**Hipótese:** o sistema tem perfil `admin` para gestão interna (criar usuários, ver logs, etc.). Em modo demo público, **o card de Admin não deve aparecer** — só aparece se uma flag extra (`PICSAUDE_DEMO_ADMIN=true`) for explicitamente habilitada. Auditor e Integrador também ficam de fora.

**Como testar:**

1. Na tela inicial, confira a contagem de cards visíveis: deve ser exatamente **3** (Prescritor, Dispensador, Cidadão)
2. Tente forçar via URL: acesse `http://localhost:8000/?demo_role=admin` — deve falhar ou ignorar o parâmetro
3. Via API direta:

```bash
curl -i -X POST http://localhost:8000/demo/login \
  -H "Content-Type: application/json" \
  -d '{"role":"admin"}'

curl -i -X POST http://localhost:8000/demo/login \
  -H "Content-Type: application/json" \
  -d '{"role":"auditor"}'
```

**Critério de sucesso:**

- Tela inicial: exatamente 3 cards, sem opção Admin ✅
- API: `/demo/login` com `role=admin` retorna **HTTP 403** com `{"codigo":"papel_demo_indisponivel", ...}` — admin existe como conceito mas não está disponível no demo público (handler valida `PICSAUDE_DEMO_ADMIN`) ✅
- API: `role=auditor` ou `role=integrador` retorna **HTTP 422** (erro de validação do Pydantic — esses papéis não são aceitos pelo schema do endpoint, nem com flag admin) ✅

| Role testada | Status esperado | Origem |
|---|---|---|
| `admin` (sem `PICSAUDE_DEMO_ADMIN=true`) | **403** `papel_demo_indisponivel` | Handler `demo.py` |
| `auditor` | **422** validation error | Pydantic schema `DemoLoginIn` |
| `integrador` | **422** validation error | Pydantic schema `DemoLoginIn` |

A diferença é semântica: 403 ("admin existe mas você não pode") vs 422 ("auditor/integrador não é input válido aqui"). Marque cada cenário como passou apenas se o status code bate exatamente.

Falha grave: admin aparece como card público, ou `/demo/login` retorna 200 (login real funcionou — vazamento de RBAC), ou retorna 500 (handler quebrou).

**Resultado:** ⬜ passou ⬜ ❌ bug #__

---

## Após o roteiro

Reuna a turma e faça **5 minutos de retrospectiva**:

- Quantos cenários passaram? Quantos falharam?
- Cada falha virou issue?
- Há algo que vocês notaram fora do roteiro? (UX confusa, texto mal escrito, layout quebrado em mobile, etc.) — abrir como `enhancement` no GitHub
- O que vocês usariam diferente se vocês fossem o Prescritor de verdade? (input para próximas iterações)

A meta da primeira reunião não é fechar 0 bugs. É **engajar vocês como QA ativos** do projeto — daqui em diante, cada vez que vocês mexerem com o demo, vão estar caçando bugs por reflexo.

---

## Para o coordenador (Fabiano)

Issues encontradas pelos extensionistas têm 3 destinos possíveis:

| Tipo | Destino | Quem trata |
|---|---|---|
| Bug funcional (quebra fluxo) | `bug` + label `etapa-6-1-hotfix` se bloquear push do `9eb7228` | Code (no Cowork de desenvolvimento) |
| UX/copy estranho | `enhancement` + label `good-first-issue` se simples | Próximo extensionista que pegar |
| Achado arquitetural | `discussion` no GitHub + escalar para você | Você decide se vira ticket formal ou §11 |

Para os extensionistas: o ciclo "encontrar → reportar → ver corrigido em poucos dias" é o reforço positivo mais poderoso. Tente garantir que as primeiras issues que eles abrirem sejam triadas e respondidas no mesmo dia.

---

*"Cada bug encontrado em homologação é um paciente que não vai sofrer com bug em produção."*
