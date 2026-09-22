# PLANO — Curadoria PCDT automática (a trilha paralela)

| Campo | Valor |
|---|---|
| **O que é** | Plano-mestre do trabalho automático de rascunhos PCDT: intensivos seg–sex por automação, caneta do Fabiano em lote, PR de curadoria pelo canal oficial |
| **Classe** | curadoria clínica — os runs produzem `docs/` apenas; dados curados só mudam no canal de curadoria (PR com caneta citada) |
| **Criado** | 20/09/2026, a pedido do Fabiano ("plano paralelo para trabalho automático PCDTs") |
| **Estado** | 🟢 Ativo — semana 21–25/09 em curso (`automation-0f3c49ba-7bb4-4fba-9e25-63f0833eb998`) |
| **Irmãos** | `VAGAO-CURADORIA-SEMAFORO.md` (fila-mãe) · `DESENHO-ONDA-PCDT.md` (corpus → extração → curadoria) · manuais `SESSAO-*-INTENSIVO-PCDT.md` (diário de cada semana) |

---

## §1 Por que paralelo (e por que agora)

Duas trilhas, nenhum cruzamento de superfície:

- **Trilha A — UI** (Receita Viva → Encaminhamento → Atestado → Exames): mora no
  `prescritor.html`; consome Kimi + engenheiro + martelo do Fabiano.
- **Trilha B — PCDT** (este plano): mora em `docs/tickets/RASCUNHO-*`; consome rodadas
  automáticas do arquiteto + caneta do Fabiano.

O único recurso compartilhado é **o tempo do Fabiano** (canetas, merges, colagens de
despacho). Este plano existe para que B nunca bloqueie A nem vice-versa — e para que a
caneta chegue **em lote**, não em gotejamento.

A semana-piloto (14–18/09) provou o ritmo: 8 rascunhos self-checkados em 4 rodadas
efetivas, com o cron falhando em silêncio 2× (qua 16 e sex 18 — R3 e R5 perdidas) e o
auto-resgate cobrindo a primeira. As lições dela estão incorporadas aqui.

## §2 A régua do rascunho (inviolável, toda rodada)

1. **NUNCA flipa** `exaustivo`/`validado` — a caneta é do Fabiano. SEM exceção de
   delegação verbal nos intensivos (o precedente de 13/09, "Merge e canetas
   autorizados", cobriu só J44/I50, naquele ato).
2. **SEM PR, SEM código, SEM CSV** — os runs lavram
   `docs/tickets/RASCUNHO-<CID>-DUPLO-PCDT-2026.md` e o manual da semana. Dados
   curados só mudam no canal de curadoria.
3. **A fonte é o PDF estagiado, COM PÁGINA** — corpus `data/fontes-oficiais/pcdt/`
   (MANIFEST/índice); o catálogo aberto é índice defasado, nunca fonte. Sem página,
   não é citação.
4. **Padrão E11/J45**: elenco completo + exclusões explícitas citadas +
   `posologia_usual` citável por substância + pontos de decisão (§4 do rascunho)
   para o Fabiano.
5. **Self-check na mesma rodada**: 3+ citações por rascunho reabertas contra o PDF;
   o conferido vai no rodapé do rascunho.
6. **Auto-resgate antes de tudo**: rodada anterior conferida no manual; rascunho
   faltante é executado antes de qualquer trabalho novo (o cron já falhou calado
   em 06/09, 16/09 e 18/09).
7. **Condição sem PCDT ou com elenco farmacológico vazio/negativo** → pendência P-N
   no manual, nunca rascunho fabricado. Família atual: K21 (P-1), E03-adulto (P-2),
   E66 (P-3), N39.3/N39.4 (P-5), DRC (P-7). Mini-rascunhos "🟡 não incorporado"
   só sob demanda do Fabiano.
8. **Dúvida vira pendência escrita** — nunca pergunta ao usuário.
9. **Sanidade leve** por rodada: `/health` da vitrine; falha vira 🚨 no topo do manual.

## §3 Cadência e continuidade da automação

- **Semana intensiva padrão**: seg–sex, 09:01 BRT, 5 disparos (sempre finita,
  maxRuns 5), 2 condições/dia, R5 = FECHO (relatório + pilha para a caneta + nota
  no FILA-VIVA).
- **Anti-chain (limitação da plataforma)**: UMA automação por sessão. A sessão que
  criou o intensivo não cria outra — **cada semana nova nasce de um seed block
  colado numa conversa NOVA** (padrão 13/09 → 20/09). Template no §8.
- **Renovação é gesto explícito**: nada perpétuo. A semana seguinte só existe se o
  Fabiano colar o seed; parar = não colar. Automação finda que sobrevive à sua
  janela vira zumbi com disparo recalculado para o ano seguinte — deletar ao
  perceber (caso `automation-b49a5414…`, 14–18/09).
- **Fecho documental**: os docs da semana (rascunhos + manual + notas) entram num PR
  de curadoria `docs` — registro viaja em PR, regra da casa. A semana 14–18 ainda
  aguarda o dela.

## §4 Seleção — a ordem canônica

1. **Seeds validadas não-exaustivas**: E78 → K21 → E03. Estado (20/09): E78
   rascunhada (na pilha); **K21 e E03 bloqueadas** em P-1/P-2 — não há PCDT no
   corpus para elas (ver §6).
2. **Regra (b)**: prevalência APS com PCDT no corpus estagiado, sem rascunho
   existente, não-exaustiva.
3. **PULAR sempre**: as 8 exaustivas (I10 · E11 · J45 · F32 · N39.0 · J44 · I50 ·
   F41); CIDs com `RASCUNHO-*` existente em `docs/tickets/`; **Chagas (P-8)** —
   stream corrompido quebra o pypdf, aguarda re-extração com ferramenta alternativa
   em sessão de curadoria.

A régua NÃO é varrer os ~240 PDFs — é **prevalência APS**; o corpus é a despensa,
não a meta.

## §5 A esteira da caneta

```
rodada automática → rascunho self-checkado → pilha no manual semanal
  → CANETA do Fabiano (lote; frase verbatim citada com data)
  → PR de curadoria (dados + docs) → ratificação do arquiteto → martelo/merge
```

- **Ritmo recomendado**: caneta em lote semanal (sex/seg). Pilha não passa de ~2
  semanas (≈20 rascunhos) — acima disso vira mural, e mural não se assina.
- **Dependência dura (P-9)**: flips de condições com **princípio ativo
  compartilhado** — L20 (metotrexato), A30 (prednisona), R52 (paracetamol/dipirona/
  ibuprofeno) — só saem **depois** da PR da posologia por condição
  (`DESENHO-POSOLOGIA-POR-CONDICAO.md`, chave `(ativo, CID)`). É a mesma razão das
  9 rows exiladas do I50/J44: sem a chave composta, a última row do CSV vence em
  silêncio — erro clínico calado. Condições sem compartilhamento (E78, F17, M81,
  G40, G30…) podem canetar antes.

## §6 Pendências abertas (só o Fabiano decide)

| # | Pendência | Origem | Opções |
|---|---|---|---|
| P-1 | K21 DRGE sem PCDT no corpus | R1, 14/09 | (a) permanece não-exaustiva fonte-RENAME; (b) levantura por diretriz estagiada (padrão F32/F41) |
| P-2 | E03 adulto só tem PCDT congênito | R1, 14/09 | (a) permanece fonte-RENAME; (b) rascunho E03.1 congênito com escopo declarado |
| P-3/P-5/P-7 | E66, incontinência (N39.3/N39.4), DRC — elenco vazio/negativo | R1/R2/R4 | mini-rascunho "🟡 não incorporado" sob demanda |
| P-6 | CIDs que o seletor do prescritor oferece (chaves R52.1×R52.2, M80×M81, G30×F00, L20.0×L20.8) | R2 | decidir antes dos flips correspondentes |
| P-8 | PDF de Chagas com stream corrompido | R4 | re-extração com ferramenta alternativa |

## §7 Números do terreno (20/09/2026)

- Corpus: ~240 PDFs CONITEC estagiados com sha256 (camada 0, 30/08).
- Semáforo: **8 exaustivas** — I10 · E11 · J45 · F32 · N39.0 · J44 · I50 · F41
  (F41 flipada em #266, elenco de dois).
- Rascunhos lavrados: 15 — 7 condições já flipadas + **8 na pilha** aguardando
  caneta: E78 · F17 · R52 · M81 · G40 · L20 · A30 · G30.
- Ritmo provado: 8 rascunhos/semana com 4 rodadas efetivas (2 cron-fails na semana).

## §8 Seed block — template da próxima semana

> **Como usar**: numa conversa NOVA com o arquiteto, cole o bloco abaixo preenchendo
> as datas «…». O texto integral do prompt de referência é o da automação da semana
> corrente (recuperável por `CronList` na sessão viva); as correções de sempre já
> estão listadas aqui para não congelar datas erradas no plano.

```
1. CRIE o INTENSIVO PCDT com estes parâmetros:

   Título: Intensivo PCDT — rascunhos duplos, seg–sex «DD–DD/MM/AAAA», 09:01 BRT
   Cron: 1 9 «D1,D2,D3,D4,D5» «M» *
   recurring: false · maxRuns: 5
   Prompt: idêntico ao da semana anterior (CronList da sessão viva ou último
   manual lavrado), com as correções de sempre:
   (a) mapa de rodadas: seg «D1»=R1 · ter «D2»=R2 · qua «D3»=R3 · qui «D4»=R4 ·
       sex «D5»=R5=FECHO;
   (b) manual em docs/tickets/SESSAO-«AAAA-MM-D1-a-D5»-INTENSIVO-PCDT.md;
   (c) datas da janela no cabeçalho, "Autorizado pelo Fabiano em «hoje»" e
       "R5 (sex «D5», FECHO)".
   Tudo o mais igual: seeds E78 → K21 → E03, pula exaustivos/rascunhados e os
   bloqueios vigentes do §4.3 do PLANO-CURADORIA-PCDT-AUTOMATICA.md, 2
   condições/dia com self-check, NUNCA flipa, só docs.

2. DELETE a automação da semana findada (zumbi de disparo recalculado).

3. Confirme ambos com os IDs.
```

## §9 Gatilhos de revisão deste plano

- PR da posologia por condição mergeada → §5 destrava os flips da pilha com
  princípio ativo compartilhado.
- Decisão P-1/P-2 → seeds K21/E03 voltam (ou não) à ordem de seleção.
- Corpus ganhar PCDT novo (portaria 2026+ na família `/midias/protocolos/`) →
  re-sondagem das bloqueadas.
- Pilha > 2 semanas sem caneta → pausar o seed seguinte até drenar.

---

*Plano lavrado pelo arquiteto (Z) em 20/09/2026. O rascunhista é automático;
a caneta nunca é.*
