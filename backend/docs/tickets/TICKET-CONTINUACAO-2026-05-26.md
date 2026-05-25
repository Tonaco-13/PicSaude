# TICKET CONTINUAÇÃO — retomar 2026-05-26 (terça)

> **Para o Arquiteto (Opus 4.7) que abrir a próxima sessão.**
> Cole o PROMPT-OPUS-4.7-ARQUITETO.md como primeira mensagem (padrão), depois leia este arquivo antes de qualquer ação. Estado real do repo abaixo é a verdade — memória da sessão de 25/05 pode ter ficado stale.
> **Lição aprendida 2026-05-25:** sempre rodar `git log --oneline -10` + `ls backend/docs/tickets/TICKET-*.md` na primeira chamada de ferramenta. Memórias `picsaude_estado_*.md` desatualizam em horas; o repo é a fonte de verdade.

---

## §1 Por que este documento existe

Sessão de 25/05 foi intensa (10+ commits, diagnóstico tri-revisor da IA, expansão da base DEF, materiais para extensão UFPE, fix de bug grave do WRatio descoberto pelo Code+Jules em convergência). Reunião com 7 extensionistas postergada de 26/05 → **27/05 (quarta)**, então temos terça inteira para polir antes.

Este ticket é o handoff: o que está fechado, o que está em curso, o que precisa atacar amanhã. Fabiano vai trazer o relatório do Jules (auditoria DX que ele iniciou no fim de 25/05) — esse é o ponto natural de início.

## §2 Estado do repo (snapshot ao fechar 25/05)

Branch `main` = `origin/main` (sincronizado). Últimos commits:

```
1d1bde4 docs(ia): fechar §11 expansao DEF + atualizar contagem 41->81 + 2o bullet GFI #62
579b619 data(ia): expandir def_medicamentos de 41 para 81 entradas (hotfix pre-reuniao extensao)
2589c26 data(branding): logo PicSaude otimizada (3.6MB->31KB) + favicon
c548be5 fix(ia): elevar THRESHOLD_APROXIMADO 82 -> 88 corrige falso positivo grave
4e089ea fix(ia): feedback visual para sugestao vazia + aviso_base farmaceutico
ecf669a docs(coordenacao): calibrar prompts pos-pacto 2026-05-24 (Arquiteto-Coordenador) + renumeracao no PROMPT-CODE
2f16898 docs(extensao): materiais para reuniao UFPE de 2026-05-26
a01fec6 docs(6): arquivar TICKET-6, TICKET-6.1 e briefings CODEX/Jules com renumeração #56-58 -> #59-61
9eb7228 fix(6.1): isolamento CNES + hidratação demo no frontend + guard JWT hermético
94f73cd feat(6): demo mode com sessões pré-semeadas + isolamento DB + 7 decisões
```

Working tree limpo. Branch local = remoto. Nada untracked relevante.

## §3 O que foi fechado em 25/05

**Etapa 6 (DEMO_MODE)** — implementação completa do TICKET-6 e TICKET-6.1 no repo, fixes pós-impl aplicados, briefings de revisão arquivados. Falta apenas:
- Checklist manual §4.2 (4 itens — ver §4 abaixo) — bloqueador formal do fechamento
- CODEX rodada 3 sobre `origin/main` consolidado — ainda não rodada
- Preenchimento §11 do TICKET-6 + atualização de PLANO + PROMPT-OPUS — depende dos 2 anteriores

**Diagnóstico tri-revisor da IA farmacêutica** (CODEX + Jules + Code) descobriu bug grave do WRatio (`fuzz.WRatio` empatava em 85.5 para `"X N mg"` vs qualquer `"Y M mg"` porque tokens `"mg"`/`"comprimido"` são comuns à base — `process.extractOne` desempatava pela primeira linha do CSV, gerando sugestão de classe terapêutica errada para 5 queries comuns testadas). Resolvido em `c548be5` (threshold 82→88) + `4e089ea` (feedback DX neutro quando "nenhum") + `579b619` (expansão da base 41→81, eliminando 5 falsos positivos). Diagnóstico arquivado em `backend/docs/codex/DIAGNOSTICO-IA-DEF-2026-05-25.md`. Fechamento em `§11` do `TICKET-IA-EXPANSAO-DEF-HOTFIX.md`.

**Materiais para a reunião com extensionistas UFPE** atualizados: README.md (testes 146→1267, demo "em preparação"→"implementado", `DEMO_MODE`→`PICSAUDE_DEMO_MODE`, novas seções "O que esperar no demo" e "Para extensionistas UFPE"), `CONTRIBUTING-EXTENSAO.md` (criado — 250+ linhas, seção sobre "IA = lookup, não generativa"), `docs/HOMOLOGACAO-DEMO.md` (criado — roteiro do Jules adaptado ao código real, 6 cenários divididos em 2 trilhas), GFI #62 atualizada com 2 bullets (atenção ao teste de regressão + consolidação anlodipino/amlodipino).

**Branding** — logo recebida de Fabiano, otimizada 3.6MB→31KB, salva como `logo-picsaude.png` na raiz; favicon 6.9KB multi-size gerado e salvo. Resolveu os 2 únicos 404s cosméticos do log.

## §4 Pendências para terça 26/05 (priorizadas)

### §4.1 Manual — Fabiano (cedo, antes de qualquer trabalho com agentes)

**Checklist §4.2 do TICKET-6.1** — 4 itens manuais que estão bloqueando CODEX rodada 3:

1. Clicar Prescritor na tela inicial → `prescritor.html` deve carregar já logado como "Dra. Demo Maria Souza" (sessão hidratada via `sessionStorage`, sem fluxo OTP).
2. Clicar Dispensador → `dispensador.html` logado como "Farmácia Demo Central".
3. Clicar Cidadão → `cidadao.html` logado como "João Demo da Silva".
4. Em aba anônima (sem token no `sessionStorage`): confirmar que fluxo normal de OTP/DEV_PRESET_CONTEXT continua funcionando (regressão).

Itens 1-3 foram testados parcialmente em 25/05 (Prescritor ✅ confirmado pelo log do servidor — `/prescritor/solicitacoes-renovacao` retornou 200, endpoint protegido respondeu). Faltam Dispensador, Cidadão, regressão OTP.

Tempo estimado: 15-30 min. Se passar todos: autorizar CODEX rodada 3.

### §4.2 Arquiteto — processar retorno do Jules

Fabiano vai trazer o output do Jules logo no início da próxima sessão. Briefing enviado em 25/05 noite priorizando 3 frentes:

- §A DX-extensionista (PRIMÁRIA) — silêncios estruturais nos 5 frontends análogos ao `_renderizarSugestaoIA` já corrigido
- §B Bug latente do WRatio em `ia_cid.py` / `ia_exames.py` / `ia_documental.py` (SECUNDÁRIA)
- §C Naming híbrido pt-BR / en — mapeamento sistemático (TERCIÁRIA)

Anti-escopo: segurança/RBAC (CODEX), Etapa 6 (já revisada).

**O que fazer com o retorno:** classificar P1/P2/P3, mapear contra trabalho já planejado, decidir destinos (fix imediato hoje / spec ticket / dívida §11 / GFI). Se houver P1 estrutural (ex: bug latente do WRatio confirmado em outra IA), pode virar trabalho de Code para amanhã antes da reunião.

### §4.3 Arquiteto — spec do seed Cidadão demo

Trabalho prometido em 25/05. O Cidadão demo (João Demo da Silva) hoje entra no `cidadao.html` mas tem zero prescrições para mostrar. Para demo realista, precisamos:

- 2-3 prescrições pré-criadas em nome dele, com medicamentos diferentes (idealmente: 1 antibiótico curso curto, 1 contínuo crônico, 1 receita controlada para mostrar fluxo de retenção)
- Estado das prescrições variado (1 já dispensada, 1 em custódia do paciente, 1 expirada — mostra histórico completo)
- Prescritor associado = Dra. Demo Maria Souza (consistência)

Volume estimado: ~50 linhas adicionadas ao `seed_demo.py`. Classe `module` (Pacto Regra 3 — Edit direto pelo Code).

**Aproveitar para juntar com:** atualização do `aviso_base` em `routers/ia.py:211` ("41 medicamentos" → "81") — Code não tocou em 25/05 por anti-escopo do TICKET-IA-EXPANSAO §8. Vai junto neste commit do Code.

### §4.4 Validação visual completa do demo

Arquiteto roda servidor + curls + abre PDFs em sandbox e reporta:

- Banner amarelo aparece em todos os HTMLs (sem flicker)
- Logo carrega em `index.html`, `clinica.html`, `dispensador.html`
- Cards do seletor mostram 3 personas (Prescritor / Dispensador / Cidadão) — Admin não aparece (anti-leak)
- Login real bloqueado em demo (POST `/auth/token` → 403 `demo_mode_ativo`)
- `/demo/login` com `role=admin` sem `PICSAUDE_DEMO_ADMIN` → 403, `role=auditor`/`integrador` → 422
- PDF de prescrição renderizado em demo tem marca d'água "DEMO" diagonal
- IA do DEF: smoke das 13 queries do §5 do TICKET-IA-EXPANSAO continua válido após push do `579b619`
- `GET /ia/status` reporta `total_registros: 81`, `versao_base: "2026-05"`

Tempo estimado: 1 hora.

### §4.5 PowerPoint da reunião

`docs/extensao/PicSaude_Extensao_2026_05_26.pptx` foi nomeado com data de 26/05 — **renomear para 2026_05_27**. Também: inserir a logo nos slides de capa + atualizar quaisquer datas/numerações dentro. Trabalho de ~15 min em LibreOffice/Keynote/PowerPoint pelo Fabiano (não toco binário direto), ou eu posso reescrever via spec se ele preferir.

### §4.6 CODEX rodada 3 (acionar depois que checklist passar)

Fabiano aciona via interface CODEX usual com briefing tipo:

> Rodada 3 sobre `origin/main` consolidado (HEAD = `1d1bde4`). Critério: zero P1. Foco em validar fixes pós-impl da Etapa 6 (commits `9eb7228` + `4e089ea` + `c548be5` + `579b619` + `1d1bde4`). Anti-escopo: tudo de Etapas 1-5 já fechadas. Lente segurança/RBAC/bypass como sempre.

### §4.7 Fechar Etapa 6 (depois de CODEX rodada 3 zero P1)

Arquiteto faz:
- Preencher §11 do `TICKET-6-DEMO-MODE.md` com resumo dos achados pós-impl (CODEX rodada 2 + Jules + rodada 3)
- Atualizar `docs/PLANO-PRODUCAO-V2.md` marcando Etapa 6 ✅, Etapa 7 (Dockerfile) ⛔ próxima
- Atualizar `backend/docs/PROMPT-OPUS-4.7-ARQUITETO.md` no estado atual (Etapa 5 fechada → Etapa 6 fechada)
- Gerar relatório HTML de fechamento de etapa para audiência humana (padrão híbrido md↔html — primeira aplicação real do padrão registrado em `decisao_artefatos_md_vs_html`)

## §5 Estado dos 4 agentes da equipe

| Agente | Status final 25/05 | Próxima ação (26/05) |
|---|---|---|
| **Code** (VS Code) | Ciclo IA-EXPANSAO encerrado em `579b619`. Aguarda nova spec. | Aplicar seed do Cidadão demo + atualizar `aviso_base` em `ia.py:211` (spec do Arquiteto na fila) |
| **Jules** | Iniciou auditoria geral em 25/05 noite. Briefing entregue com 3 frentes priorizadas. | Entregar achados — Fabiano traz no início da sessão |
| **CODEX** | Rodada 2 sobre Etapa 6 entregue em 24/05 (6 achados, 3 P1 fechados em `9eb7228`). | Rodada 3 sobre `origin/main` consolidado, após checklist §4.1 passar |
| **ChatGPT, Z AI, Gemini** | Sem acionamento previsto para a semana. | — |

## §6 Artefatos novos no repo (criados em 25/05)

Para qualquer agente futuro entender o contexto sem ler git log inteiro:

- `CONTRIBUTING-EXTENSAO.md` (raiz) — onboarding para os 7 extensionistas, mapa do repo, GFIs sugeridas
- `docs/HOMOLOGACAO-DEMO.md` — roteiro de QA com 6 cenários
- `docs/issues/ISSUE-extrair-demo-bootstrap-js.md` — GFI #56
- `docs/issues/ISSUE-pydantic-response-models-demo.md` — GFI #57
- `docs/issues/ISSUE-seed-common-helper.md` — GFI #58
- `docs/issues/ISSUE-expandir-def-medicamentos.md` — GFI #62
- `backend/docs/tickets/TICKET-6-DEMO-MODE.md` — spec da Etapa 6 (commitada em `a01fec6`)
- `backend/docs/tickets/TICKET-6-1-FIX-POSTIMPL.md` — follow-up
- `backend/docs/tickets/TICKET-IA-EXPANSAO-DEF-HOTFIX.md` — spec + §11 fechado em 25/05
- `backend/docs/codex/CODEX-RODADA-2-6-POSTIMPL.md` — briefing CODEX rodada 2 Etapa 6
- `backend/docs/codex/JULES-RODADA-FIM-ETAPA6.md` — briefing Jules Etapa 6
- `backend/docs/codex/DIAGNOSTICO-IA-DEF-2026-05-25.md` — briefing tri-revisor IA
- `logo-picsaude.png`, `favicon.ico` — branding

## §7 Lições aprendidas em 25/05 (preservar para o Arquiteto de amanhã)

1. **Verificar repo ANTES de assumir estado** — desperdicei ~20 min de Fabiano fazendo 4 perguntas redundantes sobre decisões já implementadas porque confiei em memória `picsaude_estado_2026_05_24.md` sem rodar `git log`. Memórias `picsaude_estado_*.md` ficam stale em horas se Fabiano avança em outra sessão.
2. **Convergência cross-revisor é mais barata que conversação serial** — Code e Jules identificaram o MESMO problema (silêncio do `_renderizarSugestaoIA`) com lentes diferentes em paralelo. Code escalou para Jules respeitando anti-escopo §8 do briefing, Jules confirmou P1. Zero atrito.
3. **`fuzz.WRatio` é treacherous em domínio com tokens comuns** — empates artificiais em score causam falsos positivos. Threshold solto piora silenciosamente quando a base cresce. Pattern a procurar em `ia_cid.py` e `ia_exames.py` (Jules §B).
4. **Decisão de design "aceitar com aviso" pode contradizer design já implementado** — Fabiano respondeu 3 perguntas minhas em 25/05 com escolhas que contradiziam o TICKET-6 já implementado (reset diário vs horário, login com aviso vs bloqueado, escopo aberto vs decidido). Eu deveria ter checado o ticket antes de perguntar. Repetindo: **verificar repo primeiro**.
5. **Amend vs follow-up commit** — quando commit ainda não foi pushado, amend mantém história limpa (1 commit por ticket). Quando já foi pushado, follow-up commit é mais seguro. Code aplicou amend corretamente no `3a33cc6` → `579b619`.

## §8 Como retomar — primeiro passo concreto

```bash
# 1. Verificar estado real (lição §7.1)
cd ~/PicSaude_Dev
git log --oneline -10
git status
ls backend/docs/tickets/TICKET-*.md | tail -10

# 2. Cole o PROMPT-OPUS-4.7-ARQUITETO.md como primeira mensagem da sessão
#    (no Cowork — Fabiano sabe o procedimento)

# 3. Leia este arquivo (TICKET-CONTINUACAO-2026-05-26.md) inteiro
#    antes de tomar qualquer ação

# 4. Aguardar Fabiano apresentar o relatório do Jules — esse é o
#    ponto natural de início do trabalho do dia
```

---

*Fim do ticket de continuação. Boa sessão amanhã.*
— Arquiteto (Opus 4.7), 25/05/2026 19h
