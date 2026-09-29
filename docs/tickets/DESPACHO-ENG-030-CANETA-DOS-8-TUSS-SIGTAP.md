# DESPACHO ENG-030 — A caneta dos 8 (os pares ambíguos + a US morfológica)

**Data:** 29/09/2026, noite · **Emissão:** arquiteto Z, por delegação do assinante
**Classe:** `module` (catálogo de exames em código — sem toque em núcleo, estados,
ledger, custódia ou itens emitidos)

> **ESTADO: CANETA DADA — verbatim do assinante lavrado no §8, 29/09/2026.**
> O despacho segue à engenharia. A tabela §2 É a caneta; o desenho §3 da US é
> parte da caneta ("chave honesta").

---

## §0 O que já está feito (não repetir)

- **#281** (`fb52a6c`) — caneta dos 38: TUSS de `_BASE_RAW` + seed oficiais.
- **#282** (`cae8390`) — ENG-029: índice do mapa normalizado (`_chave_sigtap`,
  uma função, dois lados) + sentido inverso com colapso. Base 1.114 ·
  fundidos 669 (60,5%) · só-TUSS 9 · só-SIGTAP 436.
- A mesa dos 8 nasceu do §6 do ENG-029 (7 ambíguos) + o achado do #282
  (US obstétrica, único par cruzado da casa).

## §1 O que esta caneta resolve

São os casos em que o mapa oficial oferece **mais de um SIGTAP** para o TUSS
curado — a ambiguidade é semântica de verdade (o TUSS fundiu na terminologia
oficial coisas que o SIGTAP publica separadas), e escolher é curadoria, não
engenharia. Mais o caso estrutural da US morfológica, em que **nenhuma**
fonte sustenta o par que o join por nome criou.

**Leitura de fundamento (para o registro):** em 6 dos 7, o texto oficial
decide sozinho — o termo TUSS do hemograma já declara plaquetas dentro;
glicose sinovial é outro sítio; índice de T4 é cálculo, não dosagem; o nome
curado diz lombossacra e crânio; o termo TUSS da urina é a descrição literal
do EAS. O oitavo caso não é escolha: é desfazer um par que mente.

## §2 A tabela da caneta — 7 pares

| # | curado (`nome_busca`) | TUSS | SIGTAP canetado | nome SIGTAP | o fundamento (citado) |
|---|---|---|---|---|---|
| 1 | hemograma completo c/ plaquetas | `40304361` | **`0202020380`** | HEMOGRAMA COMPLETO | termo TUSS: "com contagem de plaquetas ou frações (eritrograma, leucograma, plaquetas)" — pegar os dois seria faturar o componente duas vezes; CONTAGEM DE PLAQUETAS `0202020029` segue linha própria do catálogo |
| 2 | glicose glicemia de jejum | `40302040` | **`0202010473`** | DOSAGEM DE GLICOSE | o outro (`0202090124`) é glicose no LÍQUIDO SINOVIAL E DERRAMES — sítio diferente, exame diferente |
| 3 | tiroxina livre | `40316491` | **`0202060381`** | DOSAGEM DE TIROXINA LIVRE (T4 LIVRE) | o outro (`0202060012`) é ÍNDICE de tiroxina livre (FTI/T7) — cálculo derivado, não dosagem |
| 4 | tomografia computadorizada do cranio | `41001010` | **confirma `0206010079`** | TOMOGRAFIA COMPUTADORIZADA DO CRANIO | fusão por nome existente, endossada pelo mapa — a caneta é a CONFIRMAÇÃO; sela túrcica (`0206010060`) é região outra |
| 5 | ressonancia magnetica da coluna lombossacra | `41101227` | **`0207010048`** | RESSONANCIA MAGNETICA DE COLUNA LOMBO-SACRA | o nome curado diz lombossacra; cervical/pescoço (`0207010030`) é outro |
| 6 | urina tipo i | `40311210` | **`0202050017`** | ANALISE DE CARACTERES FISICOS, ELEMENTOS E SEDIMENTO DA URINA | o termo TUSS `40311210` é a descrição LITERAL do EAS: "Rotina de urina (caracteres físicos, elementos anormais e sedimentoscopia)" |
| 7 | parasitologico de fezes | `40303110` | **`0202040127`** | PESQUISA DE OVOS E CISTOS DE PARASITAS | o EPF de rotina; pesquisa de LARVAS (`0202040089`) fica linha bare para quem pedir |

## §3 A US morfológica — solta, chave honesta

O registro curado carrega hoje TUSS `40901262` ("US - Obstétrica morfológica")
fundido por nome ao SIGTAP `0205020143` (ULTRASSONOGRAFIA OBSTÉTRICA, a
simples) — **par cruzado desmentido nas duas pontas**: a morfológica não tem
par NENHUM no mapa, e a simples aponta para `40901238`. O SIGTAP 202606 não
tem linha morfológica própria. A raiz da colisão: `nome_busca` do curado é
`"ultrassonografia obstetrica"` — genérico, resíduo histórico (a palavra
"morfológica" só vive nos aliases).

**A execução da caneta:**

1. `nome_busca` do curado passa a `"ultrassonografia obstetrica morfologica"`
   — a chave honesta do que ele é. Aliases atuais permanecem.
2. O join por nome deixa de casar (não existe linha SIGTAP com esse nome).
3. O curado fica **só-TUSS** — como coagulograma, TC abdome, coprocultura.
4. A linha bare simples (`0205020143`) **sobrevive** e ganha `40901238`
   pelo mapa sozinha (unívoca).
5. Resultado: **três registros honestos** onde hoje há um híbrido —
   simples (40901238+0205020143), doppler colorido (já existente),
   morfológica (40901262, SIGTAP=None, com alerta de que o SUS não publica
   linha morfológica própria).

E a defesa geral, para a US não voltar por outro nome: **guarda par-cruzado**
— o join por nome não casa quando o mapa desmente (o SIGTAP pareado declara
TUSS unívoco que não é o do curado). Regra geral, não patch pontual; prova
exaustiva do arquiteto (29/09): os outros 29 fundidos são todos endossados
pelo mapa nas duas pontas, a US é o único cruzado da casa.

## §4 Execução

1. **Arquivo único de produção:** `backend/app/ai/tuss_base.py`. Os 7 pares
   entram como escolha declarada (estrutura de caneta no `_BASE_RAW` ou no
   construtor — a forma é da engenharia, o registro da ESCOLHA com seu
   fundamento citado é obrigatório).
2. **Guarda par-cruzado** no construtor, com teste-par: par endossado
   continua casando (TC crânio, ECG, US simples pós-rename); par cruzado
   não casa (a US é o caso nominal; sabotagem com par fabricado reprova).
3. **Retroativo intocado** — a guarda da árvore do #281/#282 continua
   valendo; caneta mexe em catálogo, não em item emitido.
4. **Medição antes/depois com worktree de `origin/main`** (padrão #281/#282):
   regressão idêntica lista-a-lista + os números novos. **Se divergirem,
   STOP & report:** base **1.109** · fundidos **671 (60,7%)** · só-TUSS
   **4** · só-SIGTAP **434**.
5. **Relatório** (`RELATORIO-TUSS-RECONCILIACAO.md`): seção da caneta dos 8
   com os fundamentos citados e o teto final — 173 ambíguos bare contados,
   264 fora do mapa 2017-04.

**Aviso de leitura (para o PR não prometer o que a caneta não entrega): as
canetas quase não movem a contagem de fundidos (+2 líquido).** Em 4 dos 6
casos o par já existia numa linha bare sem curadoria — a caneta **transfere
o dono**: o SIGTAP passa a morar no registro curado, com aliases, preparo e
alertas. O ganho é o par viajar junto da curadoria (e o typeahead achar o
exame certo), não o número.

## §5 Guardas (vermelho-antes-do-verde — Python + assert, lição ENG-027)

1. **Fingerprint dos 8**: teste nomeado confere os 7 pares da tabela §2 e o
   estado final da US (§3, os três registros).
2. **Par-cruzado não casa**: TUSS `40901262` + SIGTAP `0205020143` juntos é
   estado PROIBIDO — nenhum registro da base pode carregar esse híbrido.
3. **Endossados continuam casando**: o teste-par do item 2 — TC crânio e os
   demais fundidos por nome não podem ser engolidos pela guarda nova.
4. **Os 4 só-TUSS nomeados**: coagulograma, TC abdome, coprocultura, US
   morfológica — cada um com `codigo_sigtap=None` e seu alerta de escopo.
5. **A linha simples da US existe e é fundida**: TUSS `40901238` +
   SIGTAP `0205020143`, por procedência do mapa.
6. **Sabotagem da guarda par-cruzado** (fabricar par cruzado) reprova;
   sabotar o endosso (desfazer um legítimo) reprova.
7. As guardas existentes do #281/#282 seguem verdes (a base inteira
   re-rodada, não só a suíte nova).

## §6 O que este despacho NÃO faz

- LARVAS (`0202040089`) fica linha bare — virar item curado próprio exige
  demanda clínica real, não completude de catálogo.
- 173 ambíguos bare seguem sem TUSS por desenho (não se escolhe).
- 264 fora do mapa 2017-04 seguem fora — única porta é fonte mais nova
  (pesquisa de fonte, despacho próprio).
- Nomes de exibição intocados (martelo do #281) — a ÚNICA exceção é a chave
  da US, que é correção de identidade, não renomeação cosmética.

## §7 Prazo

PR ≤ **05/10** · RATIFICADO do arquiteto com guardas re-rodadas · martelo do
assinante na sequência.

## §8 A caneta — verbatim do assinante

Lavrada nesta conversa, 29/09/2026, sem ajustes:

> **"Hemograma casa com o COMPLETO · Glicose do jejum · T4 por dosagem · TC
> crânio confirma · RM lombossacra · Urina pelo EAS · Parasitológico ovos e
> cistos · US morfológica solta, chave honesta"**

Despacho segue à engenharia.
