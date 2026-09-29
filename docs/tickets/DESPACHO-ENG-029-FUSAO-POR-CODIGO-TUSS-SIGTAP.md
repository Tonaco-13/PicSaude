# DESPACHO ENG-029 — A fusão por código (o zero à esquerda + o sentido inverso)

**Data:** 29/09/2026, tarde · **Emissão:** arquiteto Z, por delegação do assinante
**Classe:** `module` (catálogo de exames em código — sem toque em núcleo, estados,
ledger, custódia ou itens emitidos)

> **ANUÊNCIA do assinante, verbatim (29/09/2026):**
> *"Mergeado 281, vamos ao despachos degraus 1 e 2."*
> Não há micro-decisão de conteúdo neste despacho: tudo o que entra é par
> **unívoco da fonte oficial**. O que é escolha clínica ficou FORA (§6).

---

## §0 O que já está feito (não repetir)

- **#281 mergeada** (`fb52a6c`, 29/09 10:08 BRT) — caneta dos 38: todos os
  `codigo_tuss` de `_BASE_RAW` e do seed são oficiais e vigentes.
- **#279 mergeada** — mapa oficial ANS TUSS×SIGTAP estagiado
  (`data/tuss_sigtap_mapeamento.csv`, 4.270 pares, 2.911 SIGTAP distintos) e o
  sentido direto (SIGTAP→TUSS unívoco) implementado em `_construir_base`.
- **A vantage do arquiteto, 29/09** (este despacho nasce dela): medição com
  código normalizado revelou que a cobertura não está no teto que o código
  entrega — dois buracos, um diagnóstico.

## §1 O achado — 564 pares oficiais perdidos num zero à esquerda

**O bug.** O mapa da ANS mistura `codigo_sigtap` de 9 e 10 dígitos (2.829
linhas com 9 — zero inicial derrubado; 1.441 com 10). O CSV SIGTAP da casa usa
sempre 10. `_carregar_mapa_tuss_sigtap` (`tuss_base.py:655-659`) indexa com a
string crua do arquivo, e o lookup em `_construir_base` compara crua também:
**`get("0202010317")` nunca acha a chave `"202010317"`.** O resultado não é
rejeição — é silêncio. Dos **659** exames SIGTAP com par unívoco no mapa, só
**95** mordem (os que por acaso vieram com 10 dígitos). **564 pares unívocos
oficiais ignorados por formatação.**

**O sentido faltante.** O mapa funciona nos dois sentidos; a casa usa um. Dos
38 TUSS curados (pós-#281), **26 sem fusão por nome** têm exatamente UM
SIGTAP no mapa, presente no CSV: casáveis por código, sem heurística nenhuma.
Na main pré-#281 o mesmo levantamento acha **1** casável — e era `40308030`,
o fator reumatóide disfarçado de PCR. **A caneta dos 38 é pré-requisito
literal desta fusão.**

**Por que o §4.6 do ENG-028 esperava subida e não viu:** a explicação do
engenheiro ("o join por nome não mudou") estava correta e incompleta — a
subida existia e estava presa no índice. Ninguém errou; o buraco era invisível
sem normalizar.

**Alcance verificado por simulação (a implementação de referência rodou na
árvore da main pós-#281):**

| métrica | hoje | pós degraus 1+2 |
|---|---|---|
| registros na base | 1.140 | **1.114** (26 colapsos) |
| fundidos (TUSS+SIGTAP) | 98 (8,9%) | **669 (60,5%)** |
| curados só-TUSS | 35 | **9** |
| SIGTAP sem TUSS | 1.007 | **436** (182 ambíguos† − 9 absorvidos + 264 fora) |

† dos 182 ambíguos, 9 eram ambíguos só no sentido SIGTAP→TUSS — ver §3.

## §2 Degrau 1 — consertar o índice (bug, não curadoria)

1. `_carregar_mapa_tuss_sigtap` indexa por `codigo_sigtap` **normalizado**
   (mesma função dos dois lados: `strip()` + `lstrip("0")`, chave canônica
   sem zero à esquerda — ou zfill(10) dos dois lados, o que for; UMA só).
2. O consumidor em `_construir_base` normaliza antes do lookup.
3. Regra atual mantida integralmente: **o mapa nunca sobrescreve TUSS de
   curadoria** — só preenche `None`; ambíguo (2+ TUSS) continua sem par e
   contado no relatório.
4. Efeito esperado: 95 → 659 unívocos mapeados. **Se a execução medir outro
   número, STOP & report** — não ajustar silenciosamente.

## §3 Degrau 2 — o sentido inverso, com colapso

**A regra:** para cada curado de `_BASE_RAW` **sem** fusão por nome, olhar o
mapa pelo `codigo_tuss` dele; se apontar para **exatamente um** SIGTAP
presente no CSV de exames → **fundir**. Não há escolha em nenhum passo — ou o
par é unívoco da fonte, ou não entra.

**O colapso:** a linha bare correspondente **morre**; o registro curado
absorve `codigo_sigtap`, `subgrupo` e fonte composta (citando o mapeamento
oficial e o grau de equivalência, como o sentido direto já faz). O nome
SIGTAP normalizado entra em `aliases` se ainda não estiver — quem buscava
"DOSAGEM DE CREATININA" continua achando.

**Os 9 monodirecionais (†).** Em 9 casos o TUSS do curado aponta para um
SIGTAP que também casa com outro TUSS (ambíguo em `s→t`, unívoco em `t→s`).
**FUNDEM MESMO ASSIM**: a afirmação `t→s` é da fonte oficial e sem alternativa;
a assimetria fica registrada na fonte do registro e nominada no relatório
(urocultura vira o exemplo canônico: TUSS "cultura de urina" ↔ SIGTAP
"cultura de bactérias p/ identificação", genérico). Não é a ambiguidade que
o ENG-027 recusa — aquela é `s→{t, t'}` ao **preencher** TUSS; aqui não se
preenche TUSS nenhum.

### A tabela dos 26 (o fingerprint deste degrau)

| curado (`nome_busca`) | TUSS | SIGTAP | nome SIGTAP | subgrupo |
|---|---|---|---|---|
| ácido úrico | `40301150` | `0202010120` | DOSAGEM DE ACIDO URICO | lab clínico |
| alanina aminotransferase (TGP) | `40302512` | `0202010651` | DOSAGEM DE TRANSAMINASE GLUTÂMICO-PIRÚVICA (TGP) | lab clínico † |
| aspartato aminotransferase (TGO) | `40302504` | `0202010643` | DOSAGEM DE TRANSAMINASE GLUTÂMICO-OXALACÉTICA (TGO) | lab clínico |
| colesterol total | `40301605` | `0202010295` | DOSAGEM DE COLESTEROL TOTAL | lab clínico |
| creatinina | `40301630` | `0202010317` | DOSAGEM DE CREATININA | lab clínico |
| ecocardiograma transtorácico | `40901106` | `0205010032` | ECOCARDIOGRAFIA TRANSTORÁCICA | ultrassonografia |
| eletroencefalograma | `40103170` | `0211050040` | EEG EM VIGÍLIA E SONO ESPONTÂNEO C/ OU S/ FOTOESTÍMULO | métodos diagnósticos † |
| hemoglobina glicada | `40302075` | `0202010503` | DOSAGEM DE HEMOGLOBINA GLICOSILADA | lab clínico † |
| HDL colesterol | `40301583` | `0202010279` | DOSAGEM DE COLESTEROL HDL | lab clínico |
| holter 24 horas | `20102020` | `0211020044` | MONITORAMENTO PELO SISTEMA HOLTER 24 HS (3 CANAIS) | métodos diagnósticos † |
| LDL colesterol | `40301591` | `0202010287` | DOSAGEM DE COLESTEROL LDL | lab clínico |
| potássio | `40302318` | `0202010600` | DOSAGEM DE POTÁSSIO | lab clínico |
| proteína C reativa | `40308391` | `0202030083` | DETERMINAÇÃO QUANTITATIVA DE PROTEÍNA C REATIVA | lab clínico |
| radiografia do tórax | `40805026` | `0204030153` | RADIOGRAFIA DE TORAX (PA E PERFIL) | radiologia |
| ressonância magnética do crânio | `41101014` | `0207010064` | RESSONANCIA MAGNETICA DE CRANIO | ressonância † |
| reticulócitos | `40304558` | `0202020037` | CONTAGEM DE RETICULOCITOS | lab clínico |
| sódio | `40302423` | `0202010635` | DOSAGEM DE SODIO | lab clínico |
| tireoestimulante (TSH) | `40316521` | `0202060250` | DOSAGEM DE HORMONIO TIREOESTIMULANTE (TSH) | lab clínico † |
| TC de tórax | `41001079` | `0206020031` | TOMOGRAFIA COMPUTADORIZADA DE TORAX | tomografia |
| triglicerídeos | `40302547` | `0202010678` | DOSAGEM DE TRIGLICERIDEOS | lab clínico |
| triiodotironina (T3) | `40316556` | `0202060390` | DOSAGEM DE TRIIODOTIRONINA (T3) | lab clínico † |
| US abdome superior | `40901130` | `0205020038` | ULTRASSONOGRAFIA DE ABDÔMEN SUPERIOR | ultrassonografia |
| US abdome total | `40901122` | `0205020046` | ULTRASSONOGRAFIA DE ABDOMEN TOTAL | ultrassonografia † |
| ureia | `40302580` | `0202010694` | DOSAGEM DE UREIA | lab clínico |
| urocultura | `40310213` | `0202080080` | CULTURA DE BACTÉRIAS P/ IDENTIFICAÇÃO | lab clínico † |
| VHS | `40304370` | `0202020150` | DETERMINAÇÃO DE VELOCIDADE DE HEMOSSEDIMENTAÇÃO | lab clínico |

† monodirecional (o SIGTAP também casa com outro TUSS) — funde, com a
assimetria registrada na fonte do registro (§3).

## §4 Execução

1. **Arquivo único de produção:** `backend/app/ai/tuss_base.py`
   (`_carregar_mapa_tuss_sigtap` + `_construir_base`). Degrau 1 primeiro,
   degrau 2 em cima.
2. **Retroativo intocado.** A guarda da árvore do #281 continua valendo
   (nenhum `UPDATE` reescreve `codigo_tuss`/`codigo_sigtap` que faturou).
   Este despacho mexe em **catálogo em código** — item emitido não passa por
   aqui; a máquina de estados segue livre (`UPDATE ... SET status_item` é
   legítimo, o teste-par do #281 é o juiz).
3. **Medição antes/depois com worktree de `origin/main`** (padrão do #281):
   regressão idêntica lista-a-lista (`comm` vazio nos dois sentidos) + as
   contagens novas. Números esperados — **se divergirem, STOP & report**:
   `669` fundidos · `9` só-TUSS · `436` só-SIGTAP · base `1.114`.
4. **Relatório**: `RELATORIO-TUSS-RECONCILIACAO.md` ganha a seção da fusão
   por código (a descoberta do índice, os 9 monodirecionais nomeados, o teto
   recalculado: 182 ambíguos − 9 absorvidos, 264 fora do mapa).

## §5 Guardas (vermelho-antes-do-verde — Python + assert, lição ENG-027)

1. **Par de 9 dígitos morde**: a creatinina (`40301630` ↔ `202010317` cru)
   funde. Sabotagem: remover a normalização do índice → reprova.
2. **Piso declarado**: unívocos mapeados ≥ 600 (piso, não contagem exata —
   não quebra a cada competência nova, mas pega qualquer regressão do índice).
3. **A tabela dos 26 é fingerprint**: teste nomeado confere os 26 pares
   (mesma disciplina do `test_as_armadilhas...` do #281).
4. **Ambíguo não entra**: hemograma, glicose, T4 livre, RM lombossacra, urina
   tipo I e parasitológico **seguem sem** `codigo_sigtap` até caneta do
   assinante (§6). Sabotagem: simular par ambíguo entrando → reprova.
5. **TUSS do mapa é vigente na T22**: guarda nova — qualquer par apontando
   TUSS fora da tabela 22 com vigência aberta reprova (hoje são 0; é a guarda
   que impede um mapa futuro de apontar código morto).
6. **Alias absorvido**: creatinina passa a responder por
   `dosagem de creatinina` sem perder os aliases curados.
7. **O colapso é colapso**: 26 fusões, não 26 fusões + 26 linhas órfãs — a
   cardinalidade da base é `1.114`, e a linha bare do SIGTAP absorvido não
   existe duas vezes.

## §6 O que este despacho NÃO faz (a mesa que continua aberta)

- **Os 7 ambíguos são caneta do assinante**, um a um, fonte aberta — a mesa:
  hemograma (HEMOGRAMA COMPLETO vs CONTAGEM DE PLAQUETAS — se o completo
  já traz plaquetas, o segundo é duplo faturamento), glicose (jejum vs
  líquido sinovial), T4 livre (dosagem vs índice), TC crânio (já fundiu por
  nome — a caneta é confirmar), RM lombossacra (lombar vs cervical),
  urina tipo I (EAS vs contagem global), parasitológico (ovos/cistos vs
  larvas). Este despacho não escolhe nenhum.
- **182 − 9 ambíguos bare** seguem sem TUSS por desenho (não se escolhe).
- **264 fora do mapa 2017-04**: única porta é fonte mais nova do mapeamento
  oficial, se existir — pesquisa de fonte, despacho próprio. Não se inventa par.
- **Nomes de exibição**: intocados (martelo do #281: `nome_busca` é
  infraestrutura; terminologia oficial vive em `termo_oficial`).

## §7 Prazo

PR ≤ **02/10** · RATIFICADO do arquiteto com guardas re-rodadas · os 7 da
mesa do §6 seguem para o assinante em paralelo, sem segurar este PR.

## §8 A anuência — verbatim do assinante

Lavrada nesta conversa, 29/09/2026, sem ajustes:

> **"Mergeado 281, vamos ao despachos degraus 1 e 2."**

Despacho segue à engenharia.
