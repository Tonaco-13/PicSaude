# Sessão 2026-07-25 — Entregas para despacho (arquiteto → conselheiro → engenheiro)

| Campo | Valor |
|---|---|
| **Arquiteto** | ZCode (esta sessão) |
| **Conselheiro** | Claude Cowork (parecer pendente) |
| **Engenheiro** | Claude/Code no terminal (execução pendente) |
| **Contexto** | Demo pública reconstruída no PG do Render em 2026-07-24 (PR #125, 17 triggers, 3 personas). Régua do fantasma suspensa. |

## Grupos de trabalho (PRs separados por classe)

A sessão produziu **três grupos** que devem entrar como PRs separados — não um só. A separação respeita a Taxonomia de Contribuição (AGENTS.md §10) e facilita o parecer do Conselheiro (cada PR tem uma classe, uma régua, um nível de escrutínio).

| Grupo | Classe | Risco | Parecer Conselheiro |
|---|---|---|---|
| **A. Documentação histórica** | `docs` | Baixo | Só consistência (tickets fechados com status) |
| **B. Infra de teste externo** | `ops` | Médio | Contrato de fixtures + marker |
| **C. Etapa C de UX do cidadão** | `module` | Médio-alto | Invariantes + regressão + adjacências |

---

## Grupo A — Documentação histórica (PR `docs/f5-b-tickets-historico`)

### Arquivos
- `docs/tickets/TICKET-F5-B1-RELATORIO-BOTOES.md` (novo, copiado da pasta externa, com bloco STATUS)
- `docs/tickets/TICKET-F5-B2-CICLO-POS-DISPENSACAO.md` (novo, idem)
- `docs/tickets/TICKET-F5-B3-REMOVE-UI-DEVOLUCAO-PRESCRITOR.md` (novo, idem)
- `docs/tickets/TICKET-F5-B5-GATE-EXTERNO.md` (novo — dívida de CI do teste externo)
- `docs/tickets/TICKET-F5-FATIA-B-FRONTEND-DISPENSADOR.md` (editado — bloco STATUS)

### PR description
```
docs(f5-b): arquivamento dos tickets B1/B2/B3 (implementados 2026-07-11) + B5 (gate de CI futuro)

Os três tickets F5-B1/B2/B3 já estavam mergeados desde 2026-07-11 (commits
2e7ffda, 47239a5, 9062513) mas não estavam arquivados em docs/tickets/. Este PR
traz os specs originais com bloco STATUS no topo apontando commits/PRs e
verificações contra main (2026-07-25).

Inclui TICKET-F5-B5-GATE-EXTERNO.md — dívida de CI deixada explícita pelo
arquivo de teste externo (test_f5_externo_picsaude.py): workflow nightly que
roda o teste contra picsaude.com.br pós-reset, com artefatos de falha
(screenshot + trace). Ainda NÃO implementado — só o ticket.

Nenhuma mudança de código. Classe: docs.
```

### Prompt para o Conselheiro Cowork
```
Revise o PR docs/f5-b-tickets-historico. Papel: Conselheiro (parecer verde /
verde-com-notas / bloqueio). Foco:

1. Os blocos STATUS nos 4 tickets (B1/B2/B3/B5) estão consistentes com o
   §10 do parent F5-FATIA-B? As âncoras arquivo:linha que cito estão corretas
   contra o main?
2. O TICKET-F5-B5-GATE-EXTERNO propor um workflow nightly é a decisão certa,
   ou deveria entrar no gates-browser.yml existente? (Minha tese: nightly
   porque depende de rede e a demo reseta diariamente — não belongs em PR gate.)
3. Há algum palpite de implementação que pareça promessa de código que o código
   não cumpre? (Régua do LEARNING 2026-07-23: doc que promete o que o código
   não faz é dívida.)

Verde = aprovo; verde-com-notas = aprovo com ajustes menores; bloqueio = não
deve mergear. Por favor,justifique.
```

---

## Grupo B — Infra de teste externo (PR `ops/teste-externo-picsaude`)

### Arquivos
- `backend/pytest.ini` (editado — registra marker `external`)
- `backend/tests/browser/conftest.py` (editado — fixtures `base_url` + `demo_externa_viva`)
- `backend/tests/browser/test_f5_externo_picsaude.py` (NOVO — 8 testes, 6 da Fatia B + 2 de circulação)

### PR description
```
ops(test): infra de teste browser contra picsaude.com.br + 8 testes (Fatia B + circulação)

Estabelece pela primeira vez no repo o padrão "teste browser contra URL
externa". Até aqui, todos os testes apontavam para o app_demo (subprocesso
efêmero contra SQLite). Este PR adiciona:

- Marker `@pytest.mark.external` registrado em pytest.ini.
- Fixtures `base_url` (env-driven, default https://picsaude.com.br) e
  `demo_externa_viva` (skip offline, function-scoped pro varrer markers).
- 8 testes em test_f5_externo_picsaude.py:
  - 6 da Fatia B (B1 relatórios, B2 ciclo pós-dispensação, B3 zero UI prescritor)
  - 2 de circulação (receita cadeia 3 hops + B0; atestado single-hop)

NÃO altera gates-browser.yml nem gates.yml — o gate de CI do teste externo
fica no TICKET-F5-B5-GATE-EXTERNO (PR separado). Aqui é só o arquivo + infra.

Classe: ops. Nenhuma mudança de domínio, ledger, custódia, ou produção.
```

### Prompt para o Conselheiro Cowork
```
Revise o PR ops/teste-externo-picsaude. Papel: Conselheiro. Foco:

1. A fixture `demo_externa_viva` é function-scoped (não session-scoped autouse)
   justamente pra não pular smokes locais quando a rede cai. Confirma que está
   certa a decisão? Ou vê problema em ela rodar httpx.get(/health) em cada
   teste externo?
2. Os 8 testes usam demo/login + personas canônicas. Eles ESCREVEM na demo
   pública (medicamentos marcados TESTE-F5B-<ts>). Risco: a demo acumula lixo
   até o próximo reset agendado (#124b pendente). Aceitável como dívida
   documentada, ou deveria ter游离 de mock?
3. O marker `external` registra sem warning. Confirma que `pytest -m "not
   external"` exclui corretamente a suíte local?

Verde = aprovo; verde-com-notas = aprovo com ajustes; bloqueio = justifique.
```

---

## Grupo C — Etapa C de UX do cidadão (PR `module/f5-c-ux-cidadao`) — **prioridade de parecer**

### Arquivos
- `cidadao.html` (editado — 148+/9-)
- `backend/tests/browser/test_f5_etapa_c_cidadao.py` (NOVO — 4 testes)
- `backend/tests/browser/test_smokes.py` (editado — 1 linha: seletor `.exame-card`→`.atestado-card`)
- `backend/tests/browser/test_f5_externo_picsaude.py` (editado — seletor `.exame-card`→`.atestado-card` no teste de circulação)

### PR description
```
feat(module): Etapa C de UX do cidadão — modal de transferência, polling da carteira, hierarquia visual do atestado

Três melhorias de UX no cidadao.html, baseadas em tropeços reais vistos
navegando a demo via Playwright nos testes de circulação. Classe: module.
Nenhum backend novo, nenhum endpoint novo, nenhuma mudança de domínio.

F5-C1 — Modal de confirmação pós-transferência:
  Substitui o desaparecimento silencioso do card. Após clicar "Transferir
  Custódia", modal mostra "Receita transferida para {farmácia} (CNPJ
  mascarado)" com botão "Ver no histórico" (scroll suave + destaque amarelo
  2s). Toast enriquecido com nome da farmácia (DEMO) ou CNPJ mascarado (prod).

F5-C2 — Polling da carteira (30s + pause em aba oculta):
  Cidadão não precisa mais clicar "Atualizar" pra ver receita nova chegar.
  30s (metade do dispensador — consumer esporádico, não workstation). Pausa
  em aba oculta via visibilitychange. Importante: corrige 2 bugs conhecidos
  do dispensador que NÃO foram portados: (a) _pararCarteiraPoll limpa o timer
  no sair() — dispensador não limpa _filaPollTimer → storm de alerts; (b)
  visibilitychange pausa em aba oculta — dispensador não tem, gasta bateria.

F5-C3 — Hierarquia visual do atestado:
  Atestado deixa de usar .exame-card (classe dos exames). Nova .atestado-card
  (fundo verde-50, border-left verde-600) + badge "ATESTADO" verde sólido +
  título 16px verde-900. Seção "Atestados" subiu acima de "Pedidos de Exame"
  (documento final > intermediário). Laudos e exames continuam com .exame-card
  intocados.

Regressão: 31 verdes (27 smokes + 4 Etapa C) contra app_demo local, zero erro
de console. Gate de browser verde.
```

### Prompt para o Conselheiro Cowork — **PRIORITÁRIO**
```
Revise o PR module/f5-c-ux-cidadao. Papel: Conselheiro (parecer verde /
verde-com-notas / bloqueio). Este é o PR com maior impacto de UX — merece
escrutínio real. Invariantes e adjacências que preciso que você verifique:

## 1. Invariantes do AGENTS.md que podem ser tocados

- **R1 (reprodutibilidade):** o polling é LEITURA — nunca computa status no
  cliente, só renderiza o que o backend retorna. Verifique `_pollCarteira`
  chama só `carregarCarteira` (que é GET). Nada de estado client-side que
  simule domínio.
- **§10 (PII):** o modal de transferência (F5-C1) mostra CNPJ mascarado. Em
  DEMO, mostra nome da farmácia (DEMO.farmacia.nome). Confirme que NÃO vaza
  PII do paciente/comprador — só CNPJ da farmácia.
- **Classe module:** confirmar que NÃO toquei em AGENTS.md, NUCLEO_SANITARIO,
  states.py, ledger, custódia, ou endpoints públicos. Só cidadao.html + testes.

## 2. Bug conhecido do dispensador que alego ter corrigido

Alego que o C2 corrige 2 bugs do dispensador (timer não limpo no sair → storm
de alerts; sem visibilitychange). Verifique no código:
- `_pararCarteiraPoll` é chamado em `sair()`?
- `_pararCarteiraPoll` é chamado no `apiFetch` quando 401/403?
- visibilitychange chama `_pararCarteiraPoll` quando hidden, `_iniciarCarteiraPoll` + `_pollCarteira` quando visible?
Se algum desses faltar, é bloqueio.

## 3. Adjacência (o ponto que mais pegou bugs no histórico do projeto)

O LEARNING 2026-07-23 (COER2-POS-MERGE) diz que o grep antes de codar acha o
defeito adjacente. Aqui, minhas mudanças podem ter adjacências:
- O polling chama `carregarCarteira` que é fire-and-forget em 3 sub-loaders
  (atestados, exames, laudos). Verifique se o poll empilha esses chamados
  (re-entrância via `_carteiraPollAtiva` está protegida?).
- O modal de transferência retarda o `carregarCarteira` até o usuário fechar.
  Isso é compatível com o polling? (Sim — poll chama carregarCarteira
  independentemente; o card some e o modal continua aberto. Aceitável ou
  bug?)
- O `.atestado-card` reutiliza `.exame-card-header` (só o layout interno).
  Verifique que a renderização de laudos (que usa `.exame-card` completo) não
  foi afetada.

## 4. Testes

- 31 verdes (27 smokes + 4 Etapa C) contra app_demo local.
- O teste de circulação de atestado em test_f5_externo_picsaude.py (contra a
  demo pública) VAI FALHAR até o deploy — a demo pública ainda tem a versão
  antiga (.exame-card). É esperado ou é bug eu ter atualizado o teste antes
  do deploy?

Verde = aprovo merge; verde-com-notas = aprovo com ajustes menores que peço
ao engenheiro; bloqueio = não deve mergear — justifique.
```

---

## Ordem de merge sugerida

1. **Grupo A** (docs) — sem dependência, pode entrar primeiro
2. **Grupo B** (infra de teste) — sem dependência de código de produção
3. **Grupo C** (UX) — depende que A e B estejam em main pra o teste de circulação funcionar

## O que ficou de fora destes PRs (dívida explícita)

- **Deploy da Etapa C**: depois do merge do grupo C, o `cidadao.html` modificado precisa ir ao Render. Sem isso, o teste externo de circulação falha.
- **Reset agendado (#124b)**: fora de escopo desta sessão. A demo acumula lixo dos testes até o cron existir.
- **3 inconsistências core** (`AGENTS.md:65`, `CLAUDE.md:68`, `assinatura.py` vs `atestados.py`): pendência da sessão de rebuild, mini-ticket futuro.

## Responsabilidade do Arquiteto (eu)

- Não commerto martelo sem parecer verde do Conselheiro em C
- Se o Conselheiro bloquear, reescrevo a spec e reenvio
- Acompanho a execução do Engenheiro (clareando dúvidas da spec, não executando)
