# INTENSIVO PCDT — sessão automática do arquiteto, 14–18/09/2026

| Campo | Valor |
|---|---|
| **Janela** | seg 14/09 → sex 18/09/2026, 1 disparo/dia às 09:01 BRT (automação `automation-b49a5414-2742-4c8d-bdca-ca3cdd84b8d9`, finita, maxRuns 5) |
| **Autorização** | Fabiano, 13/09/2026 — mensagem de dois gestos (criar INTENSIVO + deletar zumbi da agenda de 05–06/09), ambos executados e confirmados com IDs |
| **Papel do agente** | RASCUNHISTA assistido — prepara levanturas, **NUNCA assina** |
| **Manual** | Este arquivo. **R1 o criou**; toda rodada lê antes e acrescenta sua seção ao final |

## Mapa das 5 rodadas

| Rodada | Dia | Papel |
|---|---|---|
| R1 | seg 14/09 | Cria o manual · sanidade · 2 condições (seeds E78 + K21) |
| R2 | ter 15/09 | Auto-resgate R1 · 2 condições (E03 + regra (b)) |
| R3 | qua 16/09 | Auto-resgate R2 · 2 condições (regra (b)) |
| R4 | qui 17/09 | Auto-resgate R3 · 2 condições (regra (b)) |
| R5 | sex 18/09 | **FECHO**: relatório final + nota no FILA-VIVA + mensagem de segunda |

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
9. AUTO-RESGATE antes de qualquer coisa nova (cron que falha em silêncio, lição 06/09).
10. Seleção: (a) seeds validadas não-exaustivas — E78, K21, E03, nesta ordem;
    (b) depois, prevalência APS com PCDT no corpus. PULAR: exaustivos, CIDs com
    RASCUNHO-* existente, F41 (engenheiro, despachada 13/09).
11. Sanidade leve por rodada: `curl -s https://picsaude.com.br/health` — esperado
    `{"ok":true}`; falha vira 🚨 no topo deste manual.
12. FILA-VIVA.md: reler do disco antes; colisão com sessão viva → registra só aqui.

## Pilha de assinatura (a mesa do Fabiano)

| Rascunho | Rodada | Estado |
|---|---|---|
| RASCUNHO-E78-DUPLO-PCDT-2026.md | R1 | ⏳ aguardando assinatura (self-check 7/7 ✅) |
| RASCUNHO-F17-DUPLO-PCDT-2026.md | R1 | ⏳ aguardando assinatura (self-check 7/7 ✅) |
| RASCUNHO-R52-DUPLO-PCDT-2026.md | R2 | ⏳ aguardando assinatura (self-check 7/7 ✅) |
| RASCUNHO-M81-DUPLO-PCDT-2026.md | R2 | ⏳ aguardando assinatura (self-check 7/7 ✅, 1 correção de página aplicada) |
| RASCUNHO-G40-DUPLO-PCDT-2026.md | R3→R4* | ⏳ aguardando assinatura (self-check 6/6 ✅) |
| RASCUNHO-L20-DUPLO-PCDT-2026.md | R3→R4* | ⏳ aguardando assinatura (self-check 5/5 ✅) |
| RASCUNHO-A30-DUPLO-PCDT-2026.md | R4 | ⏳ aguardando assinatura (self-check 6/6 ✅) |
| RASCUNHO-G30-DUPLO-PCDT-2026.md | R4 | ⏳ aguardando assinatura (self-check 6/6 ✅) |

\* resgatados pela R4 (a R3 não disparou — ver abaixo).

---

## Rodada 1 — 2026-09-14 09:01 BRT

**Sanidade:** `curl https://picsaude.com.br/health` → `{"ok":true}` ✅ (12:03 UTC).

**Terreno mapeado** (`date` → seg 14 = R1):
- CSV `decisao_semaforo.csv` (87 rows): exaustivos = E11, F32, I10, I50, J44, J45, N39.0;
  seeds não-exaustivas = **E78, K21, E03** (+ F41, do engenheiro — pulada).
- Rascunhos existentes em `docs/tickets/`: E11, F32, F41, I50, J44, J45, N39 — nenhuma
  colisão com E78/K21/E03.
- Corpus CONITEC (240 PDFs) + catálogo aberto MS (snapshot 08/2025) varridos por condição.

**Slot 1 — E78 Dislipidemia:** PCDT localizado — **Portaria Conjunta SAES/SCTIE nº 8,
de 30/07/2019** (`pcdt_dislipidemia.pdf`, 29 págs., sha256 `70224304…`), com versão-livro
ISBN 2020 conferida (elenco idêntico; divergência menor no ácido nicotínico, registrada
como §4.1). Catálogo aberto lista "Em atualização" — 8/2019 segue vigente. Rascunho
lavrado: elenco de **9 fármacos** (3 estatinas + 5 fibratos + ácido nicotínico), exclusões
citadas (ezetimiba p. 9, PCSK9 p. 9, rosuvastatina ausente do elenco p. 7), 9 rows de
semáforo + 9 de posologia propostas (CSVs NÃO tocados).

**Slot 2 — K21 DRGE: ⚠️ SEM PCDT.** Varredura completa dos 240 PDFs do corpus e do
catálogo aberto: **não existe PCDT de DRGE/refluxo gastroesofágico** (nenhuma entrada).
A seed cita "RENAME/PCDT (APS)", mas o PCDT não existe — a fonte real é a RENAME.
**Pendência P-1** para o Fabiano: decidir destino da seed K21 (permanece não-exaustiva
fonte-RENAME, ou promover rascunho de outra origem oficial fora do padrão corpus).
Nenhum rascunho lavrado — fabricar citação de PCDT inexistente violaria o rito.

**Slot 2 (substituto) — E03 Hipotireoidismo: ⚠️ SÓ CONGÊNITO.** O único PCDT de
hipotireoidismo no corpus (e nos livros históricos de 2010/2018) é o **congênito**
(Portaria Conjunta nº 05/2021; `pcdt_resumido_do_hipotireoidismo.pdf` tem nome enganoso
— é o resumido do congênito). A seed E03 (adulto, APS, levotiroxina) não pode ser
draftada do congênito (população/posologia incompatíveis). **Pendência P-2**: decidir —
E03 permanece não-exaustiva fonte-RENAME, ou rascunho E03.1 congênito com escopo
declarado. Slot 2 foi então para a regra (b).

**Slot 2 (efetivo, regra (b)) — F17 Tabagismo:** prevalência APS altíssima com PCDT
próprio — **Portaria Conjunta SCTIE/SAES nº 10, de 16/04/2020** (`pcdt_tabagismo.pdf`,
67 págs., sha256 `bd3476aa…`), confirmada pelo resumido oficial 2021. Rascunho lavrado:
elenco de **4 itens** (bupropiona 150 mg LP; nicotina adesivo 7/14/21 mg, goma 2 mg,
pastilha 2 mg), exclusão citada da **vareniclina** (p. 41–42 + Portaria 41/SCTIE/2019),
esquemas completos da Tabela 1 (p. 37–38). Ponto de decisão relevante: chave única
`nicotina` vs. rows por forma farmacêutica (§4.1).

**Achado lateral — E66 Obesidade (regra (b), não draftada):** o PCDT de Sobrepeso e
Obesidade em Adultos (**Portaria SCTIE/MS nº 53/2020**, 391 págs.) **não incorpora
nenhum fármaco** — orlistate e sibutramina receberam decisão de não incorporação
(Portarias SCTIE 14 e 15, de 24/04/2020; p. 13 do PCDT). Elenco vazio não gera
rascunho-duplo; registrado aqui como **P-3**: se o Fabiano quiser, um mini-rascunho
"E66×qualquer-fármaco = 🟡 não incorporado" pode ser lavrado sob demanda.

**SELF-CHECK executado na mesma rodada:** 14 citações reabertas contra os PDFs —
E78 7/7 ✅, F17 7/7 ✅ (a citação da vareniclina atravessa a quebra p. 41→42; o rascunho
cita "41–42", correto). Registrado nos rodapés dos dois rascunhos.

**Arquivos criados nesta rodada (somente docs, nenhum CSV/código/PR):**
- `docs/tickets/RASCUNHO-E78-DUPLO-PCDT-2026.md`
- `docs/tickets/RASCUNHO-F17-DUPLO-PCDT-2026.md`
- `docs/tickets/SESSAO-2026-09-14-18-INTENSIVO-PCDT.md` (este manual)

**Pendências acumuladas para o Fabiano:**
- **P-1** K21 sem PCDT existente — destino da seed.
- **P-2** E03 só tem PCDT congênito — destino da seed.
- **P-3** E66 elenco farmacológico vazio — mini-rascunho sob demanda.
- **P-4** (herdada, fora deste intensivo) assinaturas E78 e F17 quando quiser canetear.

**Próxima (R2, ter 15 09:01):** auto-resgate desta rodada (verificar que os 2 rascunhos
existem e estão íntegros) · seeds esgotadas no canal (a) → regra (b): candidatas de
prevalência APS com PCDT no corpus e sem rascunho — ex.: HAS já exaustiva; estudar
`dorcronica-1.pdf`, DRC, rinite/dermatite, AVC — seleção na hora com os critérios §10.

---

## Rodada 2 — 2026-09-15 09:01 BRT

**Sanidade:** `/health` → `{"ok":true}` ✅ (12:01 UTC). **Auto-resgate R1:**
rascunhos E78 e F17 presentes e íntegros (11.302/9.825 bytes, gravados 14/09 09:12) —
nada a resgatar. **Pilha intacta:** E78 segue com 2 rows (seeds) e F17 com 0 no CSV;
exaustivos inalterados (7); nenhum merge de curadoria desde ontem (HEAD `d320ae4`).

**Seleção:** canal (a) esgotado (E78 draftada ontem; K21/E03 sem PCDT — P-1/P-2).
Regra (b) por prevalência APS. Candidatas sondadas: dor crônica, incontinência
urinária, osteoporose, epilepsia, dermatite atópica.

**Slot 1 — R52 Dor Crônica:** PCDT localizado — **Portaria Conjunta SAES/SAPS/SECTICS
nº 1, de 22/08/2024** (`dorcronica-1.pdf`, 298 págs., sha256 `927f96a4…`) — o único
co-assinado pela **SAPS** entre os sondados, feito para a APS. Rascunho lavrado: elenco
de **16 fármacos** (6.2.6, p. 16–17) com Quadro 2 completo (p. 17–19), escopo CID
próprio (R52.1/R52.2, p. 3), **7 não-incorporações com portaria** (45/46/48/50/51/52/59
de 2021, p. 14), relaxantes musculares/condroitina/glucosamina/infiltrações excluídos
(p. 15). Dois pontos de decisão finos: (1) naproxeno com escopo PRÓPRIO M16/M17
(Portaria 53/2017) — propostas rows fora do R52; (2) **tensão codeína/morfina/metadona**
— no elenco com posologia (escada oncológica, p. 16) MAS citadas na lista de
"não recomendados" da Portaria 59 (p. 14); o próprio PCDT diverge sobre a DATA da
Portaria 59 (corpo: 20/07/2021; referência: 07/09/2021). Rascunhista recomenda incluir
com observação; a caneta decide.

**Slot 2 — primeira escolha CAIU:** incontinência urinária (Port. Conjunta nº 1,
09/01/2020, 168 págs.) — **elenco farmacológico VAZIO**: antimuscarínicos
(oxibutinina, tolterodina, solifenacina, darifenacina) e mirabegron **não incorporados**
(Portarias SCTIE/MS 33 e 34/2019, citadas na p. 19); tratamento é conservador +
fisioterapia (TMAP/biofeedback/estimulação do nervo tibial). CIDs R32/N39.3/N39.4
(p. 5). **Pendência P-5** (mesma família do P-3/E66): mini-rascunho
"N39.3/N39.4×antimuscarínico = 🟡 não incorporado" sob demanda.

**Slot 2 (efetivo) — M81 Osteoporose:** PCDT localizado — **Portaria Conjunta
SAES/SECTICS nº 22, de 22/10/2025** (`portaria-no-22-pcdt-da-osteoporose.pdf`, 98
págs., sha256 `7b1db154…`) — edição novíssima. Rascunho lavrado: elenco de **12
medicamentos** (7.2.7, p. 12) com esquemas (7.2.8, p. 12–13); preferencial
cálcio+colecalciferol+bisfosfonato oral (p. 9); **teriparatida EXCLUÍDA** (revisão
07/2024, p. 11) e denosumabe ausente do elenco (Relatório 742/2022 no apêndice);
calcitonina/calcitriol/pamidronato com indicações estritas citadas; escopo CID
M80.x/M81.x/M82.x (p. 3) — chave M81 proposta com ponto de decisão.

**SELF-CHECK executado na mesma rodada:** 14 citações reabertas — R52 7/7 ✅;
M81 6/7 na primeira passada + **1 correção de página aplicada** (exclusão da
teriparatida: citada p. 9, o PDF traz p. 11 — corrigida no documento) → 7/7 ✅
pós-correção. Registrado nos rodapés dos dois rascunhos.

**Arquivos criados nesta rodada (somente docs):**
- `docs/tickets/RASCUNHO-R52-DUPLO-PCDT-2026.md`
- `docs/tickets/RASCUNHO-M81-DUPLO-PCDT-2026.md`

**Pendências acumuladas:** P-1, P-2, P-3 (R1) + **P-5** incontinência urinária elenco
vazio + **P-6** conferir quais CIDs o seletor de condição do prescritor oferece
(afeta R52.1×R52.2 e M80×M81×M82 — citado nos dois rascunhos §4.1).

**Próxima (R3, qua 16 09:01):** auto-resgate R2 · regra (b): epilepsia (Port.
Conjunta 17/2018), dermatite atópica (Port. Conjunta 28/2025), hanseníase e DRC são as
candidatas restantes de maior prevalência — sondar frescor e elenco na hora.

---

## Rodada 3 — qua 16/09/2026, 09:01 BRT — 🚨 CRON FALHOU EM SILÊNCIO

O disparo de qua 16 **não aconteceu**. Diagnóstico (coletado pela R4 via
`CronList`, somente leitura): `runCount: 3` com o terceiro run em qui 17 09:01 —
os runs são R1 (seg 14), R2 (ter 15) e R4 (qui 17); o dia 16 simplesmente não
disparou. `nextRunAt` segue armado para sex 18 09:01 (R5/FECHO). **O trabalho da R3
foi executado integralmente pela R4, abaixo, como resgate** — a lição de 06/09
aplicada: auto-resgate antes de qualquer coisa nova. Nenhuma seção de rodada 3
existia no manual até a R4 escrever esta.

---

## Rodada 4 — 2026-09-17 09:01 BRT (executando também o resgate da R3)

**Sanidade:** `/health` → `{"ok":true}` ✅ (12:01 UTC). **Pilha intacta:** exaustivos
seguran 7; nenhum merge de curadoria (HEAD `d320ae4` inalterado desde ter).

**RESGATE R3 (executado antes de tudo, regra §9 do manual):**

- **G40 Epilepsia** — Portaria Conjunta nº 17/2018 (59 págs., sha256 `26ddc586…`), com
  as alterações pós-publicação embutidas no PDF (topiramato <6a em abr/2026; Angelman
  jul/2025; levetiracetam 500/1.000 mg pela Portaria SCTIE 67/2021 — Apêndice 3, p. 44).
  Elenco de **13 antiepilépticos** (item 7.3, p. 23–27; TER p. 39–40 — a "citação
  tripla" do rito). Exclusões com âncora: **oxcarbazepina** (p. 45, sem evidência de
  superioridade sobre carbamazepina) e **lacosamida** (Relatório 353/2018). Achado de
  leitura: o próprio PCDT diz que a APS controla 50% dos pacientes em monoterapia
  (§9, p. 30) — reforço de que G40 pertence ao semáforo. Curiosidade registrada (sem
  peso): a p. 3 traz resíduo de template ("síndrome de Turner") antes da lista G40.
- **L20 Dermatite Atópica** — Portaria Conjunta nº 28/2025 (56 págs., sha256
  `8751987f…`), edição de 27/11/2025. Elenco de **8 medicamentos** (6.4, p. 21;
  Quadros 8–9 por gravidade/idade, p. 14–16). Exclusão fina com âncora:
  **dupilumabe e upadacitinibe NÃO incorporados para adultos/idosos** (Portaria
  SECTICS 53/2025, p. 21) — as rows verdes valem só para 6m–<12a e 12–<18a
  refratárias. Ponto de decisão crítico: metotrexato 15–25 mg/SEMANA colide com o
  índice por princípio ativo (lição do #261 — chave composta do
  DESENHO-POSOLOGIA-POR-CONDICAO antes do flip).

**Trabalho próprio da R4:**

- **A30 Hanseníase** — Portaria SCTIE/MS nº 67/2022 (107 págs., sha256 `9bbca96f…`).
  PQT-U completa (Quadro 1, p. 34–35: rifampicina+clofazimina+dapsona; MB 12 doses/PB
  6 doses), reações tipo 1 (prednisona 45–60 mg por peso, p. 36) e tipo 2 (talidomida
  100–400 mg/dia, p. 37), 2ª linha nos Quadros 4–6 (p. 52–53). Ponto de decisão:
  reações e 2ª linha no MESMO CID A30 ou elenco exaustivo só-PQT.
- **Substituição do segundo slot:** a **DRC** (Port. Conjunta SAES/SECTICS nº 11,
  16/09/2024, 68 págs.) é protocolo de **estratégias assistenciais** — varredura das
  45 primeiras páginas: ZERO elenco farmacológico → **pendência P-7** (mesma família
  de P-3/P-5), não rascunho. O **PDF de Chagas** (Portaria nº 57/2018) tem página com
  stream corrompido que quebra o pypdf (exceção no meio da extração) → **pendência
  P-8** (re-extrair com ferramenta alternativa quando houver sessão de curadoria; o
  rito de self-check exige re-extração confiável). Substituto escolhido:
- **G30 Doença de Alzheimer** — Portaria Conjunta SAES/SCTIE nº 27/2025 (90 págs.,
  sha256 `b9e1715d…`, edição de 27/11/2025 — mesma data da L20). Elenco de
  **4 medicamentos** (donepezila, galantamina, rivastigmina — cápsula e adesivo —,
  memantina; 6.2.2, p. 12; Quadro 5, p. 13). Exclusão citada: **memantina solução
  oral/orodispersível não incorporada** (disfagia, p. 12). Ponto de decisão: chave
  G30 × F00 (o PCDT lista ambos — mesmo dilema do P-6).

**SELF-CHECK executado na mesma rodada:** **23 citações reabertas, 23 ✅ na primeira
passada** (G40 6/6 · L20 5/5 · A30 6/6 · G30 6/6) — nenhuma correção de página
necessária desta vez. Registrado nos rodapés dos quatro rascunhos.

**Arquivos criados nesta rodada (somente docs):**
- `docs/tickets/RASCUNHO-G40-DUPLO-PCDT-2026.md` (resgate R3)
- `docs/tickets/RASCUNHO-L20-DUPLO-PCDT-2026.md` (resgate R3)
- `docs/tickets/RASCUNHO-A30-DUPLO-PCDT-2026.md`
- `docs/tickets/RASCUNHO-G30-DUPLO-PCDT-2026.md`

**Pendências acumuladas:** P-1…P-6 (anteriores) + **P-7** DRC sem elenco farmacológico
(protocolo de estratégias) + **P-8** PDF de Chagas com stream corrompido (pypdf quebra;
re-extração pendente) + **P-9** (nova, transversal): os rascunhos desta semana
derramam para o mesmo dilema do P-6 — chaves CID compostas (R52.1/R52.2, M80/M81,
G30/F00, L20.0/L20.8, A30+B92) e colisões de princípio ativo compartilhado
(metotrexato L20; prednisona A30; paracetamol/dipirona/ibuprofeno R52) — a decisão do
DESENHO-POSOLOGIA-POR-CONDICAO (chave composta) ganhou urgência com a pilha inteira.

**Próxima (R5, sex 18 09:01, FECHO):** relatório final no manual (tabela condições ×
rodada × self-checks; pilha de 8 rascunhos na mesa; pendências P-1…P-9), nota de fecho
no FILA-VIVA, e a mensagem final É o relatório para a segunda — curto, com a pilha.
