# Sessão 2026-08-13 — Arquiteto: parecer F/G/H + triagem + despacho de polimento + commit

| Campo | Valor |
|---|---|
| **Arquiteto** | Z AI — redator |
| **Engenheiro** | Claude Code no terminal — executou F/G/H (Dia 2 adiantado) |
| **Escopo** | Veredito de F/G/H (verificado no código) + triagem das 6 decisões + despacho de polimento + estratégia de commit/PR |
| **Estado** | F/G/H aprovados. Demo funcionalmente completa. Polimento (#2–#6) antes de commitar. |

> **Caminho:** confirmado que `/Volumes/fabianotonaco/Developer/PicSaude_Dev` (ambiente do arquiteto)
> e `/Users/fabianatonaco/Developer/PicSaude_Dev` (Terminal do engenheiro) são o **mesmo repositório**
> (sandbox bind-mount). Não há cópias separadas. Daqui em diante o engenheiro usa `/Users/...`.

---

## §1 Veredito F/G/H (verificado no código)

| Item | Classe | Veredito | Verificação |
|---|---|---|---|
| **F** (bancada na tela) | module | ✅ | Botão âmbar (verde = fecha ciclo); 403 não derruba sessão nas funções novas. |
| **G** (UI de laudo) | module | ✅ **endossado com força** | `if (!laudoDoPedido)` (`clinica.html:2035`) + `assinar`/`liberar` tolerantes a 422 → retry **nunca** recria laudo. Melhor que a letra do ticket: laudo é objeto sanitário, duplicar = sujeira permanente no ledger. |
| **H** (E2E) | ops/test | ✅ | `docs/ROTEIRO_DEMO_LABORATORIO.md` + `tests/browser/test_demo_lab_e2e.py` (encadeia 3 telas/2 perfis; prova que a ciência do cidadão reflui à clínica). |
| **Fix vitrine** (500 no faturamento) | module/bugfix | ✅ aprovado (escopo extra justificado) | `_como_datetime` (`clinicas.py:150`) normaliza tz-aware→naive-UTC no funil único; raiz certa (`seed_demo.py` com fuso × routers sem fuso × janela naive); pré-existente (git stash). |

Gates: browser 61 · unit 419 · integração 326 — verdes.

## §2 Triagem das 6 decisões acumuladas (fila do H)

| # | Assunto | Decisão do arquiteto |
|---|---|---|
| 1 | `web-gui-tester` inexistente (AC do H) | **(a) AC atendido pelo E2E de navegador.** A skill é plugin do ZCode (do arquiteto), não do Claude Code do engenheiro. Retiro o AC de `web-gui-tester` do Ticket H. Passada visual (GUI) só se o Fabiano quiser — aí **eu** rodo. Sem ação do engenheiro. |
| 2 | `GET /pedidos-exame/{proto}` não devolve paciente → "Paciente: —" | **CORRIGIR agora** (polimento pré-demo). Ticket I.1 abaixo. |
| 3 | Sem seletor `agrupar_por` na tela — SIGTAP só pela URL | **CORRIGIR agora** (serve a decisão #3: narrativa TUSS/SIGTAP). Ticket I.2. |
| 4 | `seed_demo.py` não preenche `codigo_sigtap` | **CORRIGIR agora** (vitrine senão mostra SIGTAP tudo "(não classificado)"). Ticket I.3. |
| 5 | `registrarColeta`/`registrarResultado` tratam 403 como sessão expirada | **CORRIGIR agora** (bug latente de UX: 403 de custódia desloga). Ticket I.4. |
| 6 | `test_regras_receituario` vermelho por data fixa (2026-05-26) | **CORRIGIR agora** (housekeeping; a suíte está vermelha há tempo). Ticket I.5. |

Nenhuma bloqueia a demo, mas #2/#3/#4 sustentam a narrativa de apresentação (decisão #3) e #5/#6
são dívida pequena e nomeada. Faço os cinco antes de commitar — sai mais barato que carregar.

---

## §3 Despacho — pacote de polimento "I" (engenheiro executa, em ordem)

**Branch:** continue em `docs/sessoes-11-12-agosto`. **Não commita** ainda (commit é §4, depois).
**Padrão:** espelhar o que já existe; `esc()` anti-XSS; 403 não derruba sessão; gates verdes ao fim.

### I.1 — Patient gap + endurecimento do G (`module`)  ← o "patient gap"
Em `backend/app/routers/pedidos_exame.py::get_pedido_exame` (`:643`):
- Enriquecer a resposta com **paciente**: `SELECT nome, cpf FROM pacientes WHERE id = ?` (pedido["paciente_id"]) → adicionar `paciente_nome`, `paciente_cpf` ao dict retornado. RBAC **inalterado** (já inclui dispensador).
- **Bônus que fecha o G:** trazer também o laudo vigente do pedido, se houver: `SELECT protocolo, status FROM laudos WHERE pedido_id = ? AND status NOT IN (terminais) ORDER BY id DESC LIMIT 1` → `laudo_protocolo`, `laudo_status` (ou `None`). Isso deixa o `clinica.html` **desabilitar "Produzir laudo" mesmo após reload** (hoje `laudoDoPedido` só vive na sessão JS — reload perderia e um 2º laudo poderia nascer).
- No `clinica.html`: deixar de usar o workaround frágil `_identidadePacienteDoPedido` (fila); ler `paciente_nome`/`paciente_cpf` de `pedidoAtual`. E usar `laudo_protocolo`/`laudo_status` para o gate do botão.
- **Teste:** afirmar que `GET /pedidos-exame/{proto}` agora traz `paciente_nome`; painel mostra o nome (não mais "—").

### I.2 — Seletor TUSS/SIGTAP na tela (`module`, frontend)
No `clinica.html`, ao lado do botão "💰 Faturamento" (`:541`), um seletor pequeno (radio/select:
**TUSS** | **SIGTAP**) que define `agrupar_por` e reconstrói a URL do `abrirFaturamento(fmt)`.
Default TUSS. Sem mudança no backend (o `?agrupar_por=` já existe).

### I.3 — `codigo_sigtap` no seed da vitrine (`ops`/seed)
No `seed_demo.py`, preencher `codigo_sigtap` nos itens (paralelo ao `codigo_tuss` que já existe).
O engenheiro estimou "duas linhas". **Atenção:** muda o banco de demo (vitrine) — é o objetivo, para
`?agrupar_por=sigtap` mostrar códigos reais, não "(não classificado)".

### I.4 — 403 em `registrarColeta`/`registrarResultado` (`module`, frontend)
Em `clinica.html`, alinhar `registrarColeta` (`:1669`) e `registrarResultado` (`:1703`) ao padrão
das funções novas (bancada/laudo): **401 → `handleUnauthorized()`; 403 → erro via `_extrairMsgErro`,
sessão preservada**. Hoje eles deslogam em qualquer 403.

### I.5 — Time-bomb do `test_regras_receituario` (`test`/housekeeping)
Em `backend/tests/integration/test_regras_receituario.py::test_validar_emissao_receituario_ok`,
trocar a `data_validade` hardcoded `2026-05-26` por data **relativa** (futura) via
`calcular_data_validade(...)` ou `date.today() + timedelta(...)`. Sem mexer em código de produção.

### Aceite do pacote I
- [ ] `GET /pedidos-exame/{proto}` devolve `paciente_nome`/`paciente_cpf` (+ `laudo_protocolo`/`laudo_status`).
- [ ] Painel do `clinica.html` mostra o nome do paciente; "Produzir laudo" fica desabilitado após liberação mesmo com reload.
- [ ] Seletor TUSS/SIGTAP funciona na tela.
- [ ] Vitrine: `?agrupar_por=sigtap` mostra códigos reais.
- [ ] 403 em coleta/resultado não desloga.
- [ ] `test_regras_receituario` verde (data relativa).
- [ ] Gates verdes: `-k` da CI (`gates.yml:101`) + `tests/browser` + `tests/unit`. **Incluindo agora `test_regras_receituario`** — considerar adicioná-lo ao `-k` também (data relativa não vence mais).
- [ ] Relatório de sessão em `docs/tickets/SESSAO-2026-08-13-TICKET-I-POLIMENTO-DEMO-LAB.md`.

---

## §4 Estratégia de commit/PR (depois do polimento verde)

**Sequência:** polimento (§3) verde → criar branch → staging cirúrgico → PRs.

1. **Branch:** `git checkout -b feat/demo-lab-laudo-cidadao` (carrega o trabalho não commitado).
2. **Staging cirúrgico — OBRIGATÓRIO, NUNCA `git add -A`/`git add .`:** a árvore de
   `docs/sessoes-11-12-agosto` tem arquivos **não relacionados** soltos de outras sessões
   (`inbox/`, `.zcode/`, `docs/RELATORIO-DEMO-2026-08-05.md`, tickets antigos, etc.). Stage só os
   arquivos da demo, por caminho explícito. O `95f3536` (Kimi) já está commitado — não re-add.
3. **PR 1 — `core` ISOLADO (gating, no martelo do Fabiano):** só `laudos.py` (Ticket C) + os 16
   testes de autorização (`test_laudos_dispensador_autorizacao.py`).
   - Sugestão de título: `feat(laudo): dispensador produz/assina/libera laudo em nome do RT [core]`.
   - **Bloqueia o PR 2** (o frontend G depende deste RBAC). Martelo do Fabiano aqui.
4. **PR 2 — demo laboratório (resto):** B (bancada) · D (faturamento TUSS/SIGTAP) · F · G · fix da
   vitrine (`clinicas.py`) · `dispensadores.py` (acionavel) · polimento I.1–I.5 · docs A/E ·
   `ROTEIRO_DEMO_LABORATORIO.md` · `POLITICA_CUSTODIA_CLINICA_LAUDO.md` · testes novos · `gates.yml`
   (ampliação do `-k`) · fix `test_4d2`.
   - Sugestão de título: `feat(demo): módulo laboratório — laudo cidadão + bancada leve [module]`.
5. **Após merge do PR 1:** o PR 2 rebaseia e segue. Registras o diário final em
   `docs/tickets/SESSAO-2026-08-14-FECHO-DEMO-LAB.md`.

> Os pareceres/relatórios em `docs/tickets/SESSAO-2026-08-13-*` e `planejamento/demo-laboratorio-laudo-cidadao/`
> podem entrar no PR 2 (documentação) ou ficar de fora — decisão do Fabiano.

---

## §5 Próximos passos

1. Engenheiro executa o **pacote I** (§3) e registra relatório.
2. Arquiteto (Z) verifica no código + gates.
3. Com verde, Fabiano dá o **martelo no PR 1 (core)**; engenheiro abre PR 1 e PR 2.
4. Demo pronta para apresentar com o roteiro (`docs/ROTEIRO_DEMO_LABORATORIO.md`).

---

*Parecer/despacho emitido pelo Arquiteto (Z AI) em 2026-08-13. F/G/H aprovados; polimento I antes
do commit; PR 1 (core C) isolado aguarda martelo do Fabiano.*
