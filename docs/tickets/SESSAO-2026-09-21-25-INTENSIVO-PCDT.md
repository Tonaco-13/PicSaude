# INTENSIVO PCDT — sessão automática do arquiteto, 21–25/09/2026

| Campo | Valor |
|---|---|
| **Janela** | seg 21/09 → sex 25/09/2026, 1 disparo/dia às 09:01 BRT (automação `automation-0f3c49ba-7bb4-4fba-9e25-63f0833eb998`, finita, maxRuns 5) |
| **Autorização** | Fabiano, 20/09/2026 — mensagem de dois gestos (criar este intensivo + deletar zumbi da agenda 05–06/09); o zumbi **já não existia** (deletado em 13/09, confirmado not-found), o intensivo criado e confirmado com ID |
| **Papel do agente** | RASCUNHISTA assistido — prepara levanturas, **NUNCA assina** |
| **Manual** | Este arquivo. **R1 o criou**; toda rodada lê antes e acrescenta sua seção ao final |
| **Plano-mestre** | Esta semana é a primeira sob o `PLANO-CURADORIA-PCDT-AUTOMATICA.md` (lavrado 20/09) |

## Mapa das 5 rodadas

| Rodada | Dia | Papel |
|---|---|---|
| R1 | seg 21/09 | Cria o manual · sanidade · 2 condições (regra (b): IST + L40) |
| R2 | ter 22/09 | Auto-resgate R1 · 2 condições (regra (b)) |
| R3 | qua 23/09 | Auto-resgate R2 · 2 condições (regra (b)) |
| R4 | qui 24/09 | Auto-resgate R3 · 2 condições (regra (b)) |
| R5 | sex 25/09 | **FECHO**: relatório final + nota no FILA-VIVA + mensagem de segunda |

## Regras (limites invioláveis, toda rodada)

1. **NUNCA flipa `exaustivo`/`validado`** — a caneta é do Fabiano, SEM exceção de
   delegação verbal neste intensivo (a autorização de 13/09 cobriu só J44/I50).
2. NÃO despacha nem cria trabalho para o engenheiro.
3. NÃO cria, altera ou deleta automações.
4. NÃO toca código. SEM PR. Só docs.
5. GitHub somente leitura.
6. Dúvida vira pendência escrita aqui, nunca pergunta ao usuário.
7. Padrão de rascunho: E11/J45 — extração pypdf **COM PÁGINAS**, elenco completo +
   exclusões explícitas citadas + `posologia_usual` citável por substância; formato do
   `RASCUNHO-E11-DUPLO` com pontos de decisão.
8. SELF-CHECK na mesma rodada (3+ citações por rascunho reabertas contra o PDF).
9. AUTO-RESGATE antes de qualquer coisa nova (cron que falha em silêncio — 06/09,
   16/09 e 18/09 são as lições pagas).
10. Seleção: (a) seeds validadas não-exaustivas — E78 (✅ rascunhada na semana passada),
    K21 e E03 (bloqueadas P-1/P-2, sem PCDT no corpus); (b) depois, prevalência APS com
    PCDT no corpus. PULAR: 8 exaustivas (I10 E11 J45 F32 N39.0 J44 I50 F41), CIDs com
    RASCUNHO-* existente, Chagas (P-8, stream corrompido).
11. Sanidade leve por rodada: `curl -s https://picsaude.com.br/health` — esperado
    `{"ok":true}`; falha vira 🚨 no topo deste manual.
12. FILA-VIVA.md: reler do disco antes; colisão com sessão viva → registra só aqui.

## Pilha de assinatura (a mesa do Fabiano)

| Rascunho | Rodada | Estado |
|---|---|---|
| E78 · F17 · R52 · M81 · G40 · L20 · A30 · G30 | semana 14–18 | ⏳ aguardando caneta (self-checks ✅) |
| RASCUNHO-IST-DUPLO-PCDT-2026.md | R1 desta semana | ⏳ aguardando caneta (self-check 11/11 ✅) |
| RASCUNHO-L40-DUPLO-PCDT-2026.md | R1 desta semana | ⏳ aguardando caneta (self-check 11/11 ✅) |

> **P-9 continua mandando na fila de flips:** L20/L40 (metotrexato) e IST
> (ciprofloxacino N39.0×A57/A58; metronidazol A59×N76.0) só flipam com a PR da
> posologia por `(ativo, CID)`. Sem compartilhamento: E78, F17, M81, G40, G30 e a
> maior parte do IST podem canetar antes.

---

## Rodada 1 — 2026-09-21 09:01 BRT

**Sanidade:** `/health` → `{"ok":true}` ✅ (09:03 BRT / 12:03 UTC). Árvore estável
(main, sem nova contenção; mesmos arquivos não commitados de 20/09).

**Notas de terreno desta semana:**
- A `main` local segue **4 commits atrás** do origin (F41 v2 + flip + fechos, #264–#267).
  Consequência para o rascunhista: o CSV local mostra F41 `exaustivo=false` — **o
  registro de verdade (origin) mostra F41 exaustiva com 2 rows**, e foi contra o origin
  que a seleção pulou F41. O PR de docs + `pull --ff-only` seguem pendentes (ritual de
  higiene lavrado no FILA-VIVA em 20/09).
- A semana 14–18 fechou **sem R5** (3º cron-fail da casa): o fecho/relatório ficou
  devendo — a pilha de 8 e as pendências P-1…P-9 estão registradas no manual antigo;
  nada a re-executar aqui (auto-resgate cobre rodadas DESTE manual).

**Terreno mapeado** (`date` → seg 21 = R1):
- Seeds: E78 com rascunho existente (pula); K21/E03 sem PCDT no corpus (P-1/P-2,
  aguardam decisão — não mudou desde a semana passada). Canal (a) esgotado → regra (b).
- Candidatas sondadas no corpus + catálogo aberto 08/2025: **esquizofrenia** (só o livro
  2013; catálogo diz "Em atualização" — fresco duvidoso), **artrite reumatoide**
  ("Aprovado*", mas especializada e carregada de metotrexato — P-9 em cima de P-9),
  **glaucoma** ("Em atualização", prescrição oftalmológica), **Parkinson** ("Aprovado*",
  reserva para rodada futura), **Chagas** (P-8 bloqueada). Escolhidas as duas de maior
  volume APS×prescritor:

**Slot 1 — IST (11 CIDs, rascunho por CID):** PCDT-IST — **Portaria SCTIE/MS nº 12, de
19/04/2021** (112 págs.; o nome do arquivo no corpus diz "588" — o documento é o juiz).
Cobertura: sífilis (Quadro 15, p. 23–24 — benzatina DU/3 sem + doxiciclina alt.),
gonorreia/clamídia (Quadro 31, p. 60 — terapia dupla ceftriaxona+azitromicina),
candidíase (33), vaginose (34), tricomoníase (35), herpes genital (38 — aciclovir),
cancroide/LGV/donovanose (39) e DIP ambulatorial (44). 26 rows propostas em 11 CIDs
(A51, A52, A54, A56, A57, A58, A59, A60, B37.3, N76.0, N73). **Achado P-9 reforçado:**
ciprofloxacino já exaustivo em N39.0 colide (doses distintas em A57/A58) e o
metronidazol tem dupla indicação DENTRO da família (A59 2 g DU × N76.0 500 2x/d 7d) —
o IST é o pôster perfeito da PR da posologia composta.

**Slot 2 — L40 Psoríase:** PCDT da Psoríase — **Portaria Conjunta SAES/SCTIE nº 18, de
14/10/2021** (78 págs., com alterações pós-publicação 2025 embutidas: risanquizumabe
150 mg/mL/Rename). Elenco de **13 substâncias** (TECI p. 42): 5 tópicos (ácido
salicílico, alcatrão, calcipotriol, clobetasol, dexametasona) + 3 sistêmicos
(acitretina, metotrexato, ciclosporina) + 5 biológicos incorporados (adalimumabe,
etanercepte, secuquinumabe, ustequinumabe, risanquizumabe). **Exclusão com relatoria:
infliximabe NÃO incorporado** (p. 47); associação calcipotriol+betametasona pedida em
enquete e não incorporada — o esteroide de pregas do protocolo é dexametasona. CID-10 do
protocolo: L40.0/.1/.4/.8 (p. 4). Metotrexato colide com L20 (P-9) — flip gated.

**SELF-CHECK executado na mesma rodada:** **22 citações reabertas contra os dois PDFs
(extração fresca) — 22/22 ✅ de primeira**, zero correções de página (uma precisão
aplicada no L40: a alteração do risanquizumabe mora na p. 46, não 47). Registrado nos
§5 dos dois rascunhos.

**Arquivos criados nesta rodada (somente docs, nenhum CSV/código/PR):**
- `docs/tickets/RASCUNHO-IST-DUPLO-PCDT-2026.md`
- `docs/tickets/RASCUNHO-L40-DUPLO-PCDT-2026.md`
- `docs/tickets/SESSAO-2026-09-21-25-INTENSIVO-PCDT.md` (este manual)

**Pendências (herdadas + desta rodada):**
- P-1 (K21) e P-2 (E03) — decisão do Fabiano sobre as seeds sem PCDT.
- P-3/P-5/P-7 — família "elenco vazio" (E66, N39.3/4, DRC): mini-rascunhos sob demanda.
- P-6 (reforçada): o IST propõe **11 CIDs de uma vez** — o que o seletor de condição do
  prescritor oferece decide A51×A52×A53 e N73; mesma família que R52.1/M80/G30×F00.
- P-8 — Chagas (stream corrompido) segue bloqueada.
- P-9 (reforçada): metotrexato L20×L40; ciprofloxacino N39.0×A57/A58; metronidazol
  A59×N76.0 — a PR da posologia `(ativo, CID)` é o destravador de quase toda a pilha.

**Próxima (R2, ter 22 09:01):** auto-resgate desta rodada (verificar IST + L40 no
disco) · regra (b): candidatas de maior prevalência APS restantes — Parkinson (G20,
"Aprovado*"), espondiloartrite axial, artrite reumatoide (metotrexato — pesar P-9),
anemia ferropriva (se houver PCDT no corpus — sondar), síndrome dos ovários
policísticos — sondar frescor e elenco na hora com os critérios §10.

---

## Diário da sessão-hospedeira — 21/09 tarde (arquiteto, fora do intensivo)

*(O intensivo dispara dentro desta conversa; os eventos de UI/curadoria do dia
ficam registrados AQUI porque o FILA-VIVA está em contenção com a sessão viva do
engenheiro — ritual #6. Re-lavrar no FILA-VIVA quando a árvore desempatar.)*

1. **Receita Viva onda 1 — CICLO COMPLETO**: DESPACHO-ENG-018 (manhã) → PR #268
   (Opus 5) → RATIFICADO com prova própria (CI verde, 15/15 guardas estáticas
   re-rodadas em worktree, backend intocado) → martelo do Fabiano ("concordo
   manter — W≡Y") → merge `45a7dae` → **NO AR** (deploy <2 min, verificado ao
   vivo). CID no papel mantido por martelo.
2. ⚠️ **Divergência visual confirmada ao vivo pelo arquiteto** — o Fabiano
   apontou; verificação própria em 1440px (evidência:
   `conceitos-prescritor/capturas-producao/01-desktop-estado-vazio-2026-09-21.png`).
   **Os 9 ACs comportamentais verdes; a ALMA do conceito não cruzou**: fundo
   cinza frio × creme; sem serif no documento; papel sem borda quente/sombra/selo
   rotacionado; lacunas sem pontilhado visível; proporções espremidas; 1 bug
   pequeno ("DDD + Númer…" truncado). **Causa raiz é do despacho** (protótipo
   declarado "referência visual, não normativa"; ACs codificaram comportamento).
   Encaminhamento: parecer KIMI3-008 → adendo estético NORMATIVO ao desenho →
   PR de polimento. Sem hot-fix antes do parecer.
3. **DESPACHO-KIMI3-008** (avaliação da Receita Viva em produção) na mão do
   Fabiano — Kimi trabalhando.
4. **DESPACHO-ENG-019 (posologia `(ativo, CID)`) na mão do Fabiano → colado** —
   engenheiro AO VIVO no branch `eng019-posologia-por-condicao` desta árvore
   (posologia_sugerida.py, ia.py, CSV, testes, prescritor.html em movimento;
   ~15 arquivos). **Aguardar a PR antes de qualquer gesto na árvore.**
5. **Perda registrada (ritual #2, 5ª vez)**: a limpeza de árvore do engenheiro
   restaurou o FILA-VIVA e levou as seções 20–21/09 (sessão do arquiteto, R1,
   despachos, RATIFICADO, martelo/merge). Conteúdo preservado NESTE diário;
   re-lavrar pós-PR. **Lições**: (a) docs PR da curadoria segue urgente; (b)
   registrar no manual primeiro, FILA-VIVA só em janela desempatada.
6. **Parecer Kimi RECEBIDO (21/09 tarde)** — onda 1 RATIFICADA PELO USO (emissão
   real, W≡Y em runtime, suíte 15/15 na máquina dela). Meu parecer lavrado:
   `PARECER-ARQ-RECEITA-VIVA-POS-KIMI-2026-09-21.md` (reconciliação das duas
   almas; correção à minha auditoria: lacunas pontilhadas EXISTEM em runtime —
   rebaixado a "sutileza"; endosso a gerador-por-documento + núcleo compartilhado;
   **recomendação de ordem ao Fabiano: Receita → Exame → Encaminhamento →
   Atestado** — martelo dele).
7. **DESPACHO-ENG-020 (polimento onda 1.1) LAVRADO** — na mão do Fabiano, colar
   APÓS a ENG-019 pousar: plural da unidade (Kimi §4.1), adendo estético
   normativo A1–A6 (palco creme, serif, papel, selo de custódia rotacionado como
   CONTEÚDO do estado emitido, lacuna legível, proporções), DDD truncado, flag
   do conselho da Dra. Demo. **Emendado 21/09 (martelo do Fabiano): §1.3 — o
   bloco gov.br Nuvem sai da vitrine por ora** (só apresentação; domínio
   `gov_br_nuvem`, endpoints e ledger intocados; certificado ICP fica; volta no
   dia do Ticket 21; guarda estática de "nenhuma promessa gov.br/em breve no
   HTML servido").
8. **PRs #269/#270 RATIFICADAS pelo arquiteto (21/09 tarde)** — posologia com
   prova de domínio nas mãos do arquiteto (losartana I10×I50, colisão cala,
   cadeia, nona row honesta); polimento com 18/18 guardas re-rodadas.
   Aguardam martelo do Fabiano (qualquer ordem; sem colisão entre si).

---

## Rodada 2 — 2026-09-22 09:01 BRT

**Sanidade:** `/health` → `{"ok":true}` ✅ (09:01 BRT). Árvore calma (main @45a7dae,
só o FILA-VIVA com as seções reconstituídas; #269/#270 OPEN aguardando martelo —
conferido no GitHub).

**Auto-resgate R1:** rascunhos IST e L40 presentes no disco — nada a resgatar.

**Sonda de seleção:** anemia ferropriva — catálogo "Aprovado*" mas **PDF AUSENTE
do corpus** (só há ferro-na-IRC, hemolítica, sobrecarga) → não rascunhável pelo
rito; registrada como pendência de courier (P-10 abaixo). Esquizofrenia segue
descartada (livro 2013 + "Em atualização"). Candidatas restantes fortes:
Parkinson e SOP — escolhidas.

**Slot 1 — G20 Parkinson:** PCDT — **Portaria Conjunta SAES/SECTICS nº 16, de
01/08/2025** (edição novíssima, Rel. 957/2024; 77 págs.). Elenco de **10
substâncias** (TECI p. 29) com esquemas POR FASE no Quadro 5 (p. 15–17).
Achados finos: **selegilina descontinuada no Brasil** (p. 10, migra p/
rasagilina); **rotigotina avaliada no Apêndice (Questão 1) e NÃO incorporada**
(custo +R$ 93 mi/5 anos, p. 35/51) — 🟡 com relatoria. CID único G20 — sem
dilema de chave. **Flip sem dependência P-9** (nenhum dos 10 ativos está no CSV).

**Slot 2 — E28 SOP:** PCDT — **Portaria Conjunta SAES/SCTIE nº 6, de 02/07/2019**
(188 págs.; corpus traz resumido + ISBN para conferência). Elenco de **6
fármacos** (§7 p. 9–10 + TECI p. 21): EE+levonorgestrel, AMP, noretisterona,
ciproterona, metformina. **CID DUPLA: E28.2 + L68.0** (p. 2) — ponto de decisão.
Exclusões citadas: tiazolidinedionas (p. 9); espironolactona/flutamida só no
apêndice; letrozol ausente. **P-9: metformina E28.2×E11 — flip GATED no merge
do #269** (RATIFICADO, aguarda martelo).

**SELF-CHECK executado na mesma rodada:** **17 citações reabertas contra os dois
PDFs — 17/17 ✅ de primeira**, zero correções (Parkinson 9/9 · SOP 8/8).

**Arquivos criados nesta rodada (somente docs):**
- `docs/tickets/RASCUNHO-G20-DUPLO-PCDT-2026.md`
- `docs/tickets/RASCUNHO-E28-DUPLO-PCDT-2026.md`

**Pendências acumuladas:** P-1…P-9 (anteriores) + **P-10: anemia ferropriva —
PCDT "Aprovado*" no catálogo aberto mas AUSENTE do corpus estagiado; courier
pode baixar/estagiar com sha256 (não é decisão clínica, é gap de staging)**.

**Pilha do Fabiano: agora 12 rascunhos** (8 da semana 14–18 + IST + L40 + G20 +
E28). P-9 gates: L20/L40/IST/E28 dependem do merge #269; G20 e os 8 antigos não
colidentes podem canetar antes.

**Próxima (R3, qua 23 09:01):** auto-resgate R2 (G20 + E28) · regra (b):
candidatas restantes — espondiloartrite axial (M45, "Aprovado*"), artrite
reumatoide (M06, P-9-carregada), glaucoma (oftalmo — pesar), doença falciforme
(relevância regional PE), brucelose — sondar frescor e elenco na hora.
