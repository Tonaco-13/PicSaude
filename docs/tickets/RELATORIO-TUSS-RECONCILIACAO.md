# RELATÓRIO — a curadoria TUSS contra a Tabela 22 oficial

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-027-TUSS-SIGTAP-HIPER.md` §2 |
| **Autorização** | Fabiano, 28/09/2026: *"vamos ter que montar um hiper intensivo começando agora para TUSS e Sigtap"* |
| **Fonte de conferência** | ANS/TISS — Tabela 22, competência **201606** (pacote de mapeamento 2017-04), `sha256 b365e36d…`, ver `data/fontes-oficiais/tuss/MANIFEST.md` |
| **Veredito** | ⚠️ **36 dos 38 códigos TUSS curados não correspondem ao exame que nomeiam** |
| **Corrigido nesta PR?** | **NÃO.** Medido, nomeado e travado por guarda. A caneta é do Fabiano |
| **Estado** | ✔️ **RESOLVIDO** — caneta dada em 28/09/2026, executada no **ENG-028** |

> ## ✔️ A caneta veio — 28/09/2026
>
> Verbatim do assinante: *"As 27 diretas entram · Glicose pura · TGP geral ·
> US total · US superior · ECG convencional · Holter digital · PCR
> quantitativa · Coprocultura padrão · Coagulograma oficial com nota · TC
> abdome total · seed alinha aos mesmos"*.
>
> **Os 38 foram trocados** (`DESPACHO-ENG-028-CANETA-DOS-38-TUSS.md`), mais as
> 3 ocorrências do `seed_demo.py`. A divergência deste relatório é **zero** a
> partir daí, e a guarda inverteu junto: `TestACanetaDos38` agora exige que
> **todo** código curado seja oficial.
>
> **Duas correções que este relatório precisa assumir sobre si mesmo:**
>
> 1. **Os "10 grupamentos sem candidato" eram artefato da minha busca, não
>    ausência na terminologia.** O arquiteto reabriu contra a fonte e achou
>    item oficial para todos — o coagulograma tem `40304922`, a urocultura
>    tem `40310213`. Nenhuma linha ficou em `codigo_tuss=None`.
> 2. **Seis dos meus candidatos eram armadilha.** A candidatura por
>    sobreposição de string sugeriu *Holter CEREBRAL* para o Holter 24h (75%
>    de sobreposição), *US de mamas* para o abdome total, *TC* no lugar de US,
>    *ECG de alta resolução*, *TGP hemoterápico* e *glicemia pós-sobrecarga*.
>    O §4 avisava que era sugestão e não veredito; o arquiteto rejeitou as
>    seis contra a fonte. **É a prova, no próprio corpo deste documento, de
>    que string não é identidade** — a mesma razão pela qual o mapeamento
>    TUSS↔SIGTAP da #279 foi tirado da ANS e não de heurística nossa.
>
> Guarda que impede as seis de voltarem por um "conserto" distraído:
> `TestACanetaDos38::test_as_armadilhas_que_o_arquiteto_rejeitou_nao_entraram`.

---

## §1 O que se foi conferir, e por que agora

O despacho chamou a TUSS de *"a única perna sem fonte oficial — ~35
procedimentos hardcoded"*, e tinha razão: CID-10, SIGTAP, RENAME, CBO, RDC e
PCDT já tinham procedência; a TUSS era um punhado de códigos digitados à mão
em `backend/app/ai/tuss_base.py`, sem nada atrás.

Com a Tabela 22 oficial estagiada, a pergunta ficou respondível pela primeira
vez: **os códigos que a casa usa existem?**

## §2 A resposta, em três números

| | |
|---|---|
| códigos TUSS curados em `_BASE_RAW` | **38** |
| que **existem** na Tabela 22 oficial | **2** |
| que **não existem** | **36** |

E o caso que mais importa não é nenhum dos 36.

> ### O pior caso é um dos 2 que "existem"
>
> `40301079` está curado como **"Hemograma completo com contagem de
> plaquetas"**. O código **existe** na Tabela 22 — e significa
> **"Ácido beta hidroxi butírico - pesquisa e/ou dosagem"**.
>
> Um código inexistente é rejeitado no faturamento e o erro aparece. Um código
> **válido apontando para outro exame** é aceito — e fatura a coisa errada, em
> silêncio. O hemograma completo é `40304361` na terminologia oficial.

## §3 Não é dígito verificador — a hipótese foi testada e caiu

À primeira vista os códigos pareciam variantes de dígito: curado `40302019`
contra oficial `40302016`; curado `40302027` contra `40302024`. Se fosse isso,
a correção seria mecânica.

Não é. Os nomes desmentem:

| curado | nome curado | oficial de mesma raiz | o que esse código realmente é |
|---|---|---|---|
| `40302019` | Glicose (Glicemia de Jejum) | `40302016` | **Gasometria** (pH, pCO2, SA, O2…) |
| `40302272` | Creatinina | `40302270` | **Osmolalidade** |
| `40302434` | Ureia | `40302431` | **Succinil acetona** |
| `40302132` | Aspartato Aminotransferase (TGO) | `40302130` | **Amilase, isoenzimas** |

Raiz igual, exame diferente. A proximidade numérica é coincidência de
sequencial dentro do mesmo subgrupo, não parentesco.

## §4 A tabela completa — 38 linhas, uma por código curado

A coluna de candidato é **sugestão por sobreposição de termos**, para poupar
trabalho de quem vai canetar. **Não é decisão** — sobreposição alta não prova
identidade clínica (a lição de que "biopsia" ≈ "biopsia" não é o mesmo exame),
e a caneta confere uma a uma.

| # | código curado | nome curado | consta na Tabela 22? | candidato oficial (SUGESTÃO) |
|---|---|---|---|---|
| 1 | `40301079` | Hemograma completo com contagem de plaquetas | ✅ **sim** — Ácido beta hidroxi butírico - pesquisa e/ou dosagem | — |
| 2 | `40302264` | Reticulócitos | ❌ não | `40304558` — Reticulócitos, contagem *(sobrep. 50%)* |
| 3 | `40306150` | Velocidade de Hemossedimentação (VHS) | ❌ não | `40304370` — Hemossedimentação, (VHS) - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 4 | `40306117` | Coagulograma (TAP + TTPa + Fibrinogênio) | ❌ não | fraco: `40304264` — Fibrinogênio, teste funcional, dosagem *(sobrep. 17%)* |
| 5 | `40302019` | Glicose (Glicemia de Jejum) | ❌ não | fraco: `40302032` — Glicemia após sobrecarga com dextrosol ou glicose - pesquisa e/ou dosagem *(sobrep. 33%)* |
| 6 | `40302523` | Hemoglobina Glicada (HbA1c) | ❌ não | `40302075` — Hemoglobina glicada (A1 total) - pesquisa e/ou dosagem *(sobrep. 67%)* |
| 7 | `40302272` | Creatinina | ❌ não | `40301630` — Creatinina - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 8 | `40302434` | Ureia | ❌ não | `40302580` — Uréia - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 9 | `40302280` | Ácido Úrico | ❌ não | `40301150` — Ácido úrico - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 10 | `40302132` | Aspartato Aminotransferase (TGO/AST) | ❌ não | fraco: `40302504` — Transaminase oxalacética (amino transferase aspartato) - pesquisa e/ou dosagem *(sobrep. 14%)* |
| 11 | `40302140` | Alanina Aminotransferase (TGP/ALT) | ❌ não | fraco: `40403840` — Transaminase pirúvica - TGP ou ALT por componente hemoterápico - pesquisa e/ou dosagem *(sobrep. 33%)* |
| 12 | `40302027` | Colesterol Total | ❌ não | `40301605` — Colesterol total - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 13 | `40302035` | HDL Colesterol | ❌ não | `40301583` — Colesterol (HDL) - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 14 | `40302043` | LDL Colesterol | ❌ não | `40301591` — Colesterol (LDL) - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 15 | `40302485` | Triglicerídeos | ❌ não | `40302547` — Triglicerídeos - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 16 | `40302450` | Sódio | ❌ não | `40302423` — Sódio - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 17 | `40302388` | Potássio | ❌ não | `40302318` — Potássio - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 18 | `40308030` | Proteína C Reativa (PCR) | ✅ **sim** — Fator reumatóide, teste do látex (qualitativo) - pesquisa | — |
| 19 | `40302671` | TSH (Hormônio Tireoestimulante) | ❌ não | `40316521` — Tireoestimulante, hormônio (TSH) - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 20 | `40302590` | T4 Livre (Tiroxina Livre) | ❌ não | `40316491` — T4 livre - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 21 | `40302663` | T3 (Triiodotironina) | ❌ não | `40316556` — Triiodotironina (T3) - pesquisa e/ou dosagem *(sobrep. 100%)* |
| 22 | `40901060` | Radiografia do Tórax (2 incidências) | ❌ não | `40805026` — RX - Tórax - 2 incidências *(sobrep. 100%)* |
| 23 | `40801019` | Ultrassonografia do Abdome Total | ❌ não | fraco: `40901114` — US - Mamas *(sobrep. 33%)* |
| 24 | `40801027` | Ultrassonografia do Abdome Superior | ❌ não | `41001109` — TC - Abdome superior *(sobrep. 40%)* |
| 25 | `40901337` | Ultrassonografia Obstétrica (Morfológica) | ❌ não | `40901262` — US - Obstétrica morfológica *(sobrep. 100%)* |
| 26 | `40311012` | Eletrocardiograma (ECG) | ❌ não | fraco: `40101029` — ECG de alta resolução *(sobrep. 33%)* |
| 27 | `40801124` | Ecocardiograma Transtorácico | ❌ não | fraco: `40901106` — Ecodopplercardiograma transtorácico *(sobrep. 33%)* |
| 28 | `40311071` | Holter 24 Horas | ❌ não | `20102135` — Holter cerebral *(sobrep. 75%)* |
| 29 | `40403090` | Tomografia Computadorizada do Crânio | ❌ não | `41001010` — TC - Crânio ou sela túrcica ou órbitas *(sobrep. 50%)* |
| 30 | `40403082` | Tomografia Computadorizada do Tórax | ❌ não | `41001079` — TC - Tórax *(sobrep. 100%)* |
| 31 | `40403104` | Tomografia Computadorizada do Abdome | ❌ não | `41001109` — TC - Abdome superior *(sobrep. 75%)* |
| 32 | `40601078` | Ressonância Magnética do Crânio | ❌ não | `41101014` — RM - Crânio (encéfalo) *(sobrep. 75%)* |
| 33 | `40601086` | Ressonância Magnética da Coluna Lombossacra | ❌ não | `41101227` — RM - Coluna cervical ou dorsal ou lombar *(sobrep. 43%)* |
| 34 | `40311020` | Eletroencefalograma (EEG) | ❌ não | `40103170` — EEG de rotina *(sobrep. 50%)* |
| 35 | `40201030` | Urina Tipo I (EAS — Elementos Anormais e Sedimento) | ❌ não | fraco: `40311210` — Rotina de urina (caracteres físicos, elementos anormais e sedimentoscopia) *(sobrep. 30%)* |
| 36 | `40205128` | Exame Parasitológico de Fezes | ❌ não | `40303110` — Parasitológico - nas fezes *(sobrep. 50%)* |
| 37 | `40205020` | Coprocultura com Antibiograma | ❌ não | fraco: `40310426` — Antibiograma automatizado *(sobrep. 33%)* |
| 38 | `40201048` | Urocultura com Antibiograma | ❌ não | fraco: `40310426` — Antibiograma automatizado *(sobrep. 33%)* |

<!-- existe=2 sugerido=26 sem=10 total=38 -->
**Leitura da tabela:** 2 constam (um deles com o significado errado, §2) · 26
têm candidato com sobreposição ≥ 34% · 10 não têm candidato razoável — vários
por serem **grupamentos** que a TUSS não tem como item único (o "Coagulograma
(TAP + TTPa + Fibrinogênio)" da curadoria é, na terminologia oficial, três
procedimentos separados).

## §5 O que esta PR fez — e o que deliberadamente NÃO fez

**Fez:**
1. Estagiou a fonte oficial com sha256 e MANIFEST.
2. Gerou `data/tuss_procedimentos.csv` (5.755 procedimentos) e
   `data/tuss_sigtap_mapeamento.csv` (4.270 pares) por script de import que
   roda **offline** — nunca pela aplicação.
3. Ligou o loader: **95 procedimentos de exame que só tinham SIGTAP ganharam
   `codigo_tuss` oficial**, pelo mapeamento da ANS, só quando o par é unívoco.
4. Travou este relatório por guarda, com os números como fato.

**Não fez — e o "não" é a parte importante:**

**Nenhum código de `_BASE_RAW` foi trocado.** Esses códigos alimentam
`pedido_exame_itens.codigo_tuss` e o faturamento pelos dois códigos. Trocar
código de faturamento é decisão de curadoria com consequência financeira e
regulatória — é exatamente o tipo de coisa que a engenharia mede e devolve,
nunca adjudica. A régua da casa: *dúvida vira pendência escrita de volta*.

## §6 O que a caneta precisa decidir

| # | Pergunta | Observação |
|---|---|---|
| 1 | Os 36 códigos são corrigidos para os oficiais? | A tabela do §4 dá o candidato; a conferência é uma a uma |
| 2 | E o `40301079`, que é válido mas significa outro exame? | O mais urgente: hoje ele fatura ácido beta hidroxi butírico no lugar de hemograma |
| 3 | Os 10 sem candidato (grupamentos como o coagulograma) viram vários códigos, ou ficam sem TUSS? | Sem TUSS é honesto; inventar um código único para um grupamento não é |
| 4 | A Tabela 22 de **201606** é aceitável como régua, ou espera-se extração mais nova? | A API da ANS não respondeu a esta vantage — pendência no MANIFEST. A idade está declarada em toda row |

> **Enquanto não houver caneta, nada quebra:** a curadoria continua servindo
> aliases, preparo e alertas exatamente como antes, e os 95 códigos oficiais
> novos entraram **por cima** das linhas que não tinham nenhum. O que mudou é
> que agora a divergência tem tamanho, nome e teste.

---

*Lavrado em 28/09/2026 pelo engenheiro, na execução do ENG-027; **resolvido no
mesmo dia pela caneta do assinante**, executada no ENG-028. A guarda que travava
a divergência virou a guarda que a proíbe:
`backend/tests/unit/test_tuss_base_oficial.py::TestACanetaDos38`.*

---

# §7 A fusão por código — e os 564 pares que um zero à esquerda escondia

*Acrescentado em 29/09/2026, na execução do ENG-029 (degraus 1 e 2). Anuência
do assinante, verbatim: **"Mergeado 281, vamos ao despachos degraus 1 e 2."***

## §7.1 O bug: o silêncio de um índice

O mapa oficial da ANS **mistura dois formatos** de código SIGTAP: **2.829
linhas trazem 9 dígitos** (o zero inicial caiu em alguma planilha do caminho)
e **1.441 trazem os 10** do SIGTAP. O catálogo desta casa usa sempre 10.

`_carregar_mapa_tuss_sigtap` indexava com a string crua e o lookup comparava
crua também. `get("0202010317")` nunca achava a chave `"202010317"`.

**E o resultado não era erro — era silêncio.** Nada falhava, nada logava. Dos
**659** exames com par unívoco na fonte, só **96** mordiam: os que por acaso
vieram completos. **563 pares oficiais ignorados por formatação.**

| | antes | depois |
|---|---|---|
| exames com par unívoco **alcançado** | 96 | **659** |
| registros com TUSS do mapa oficial | 95 | **666** |

A correção é ter **uma** função de chave (`_chave_sigtap`), usada pelo índice
**e** pelo lookup. Duas normalizações "equivalentes" em pontos diferentes é
exatamente como o defeito nasceu.

> ### Por que o §4.6 do ENG-028 não viu a subida
>
> Ao medir a cobertura pós-caneta, relatei que ela não se movera, e expliquei:
> *"o join por nome não mudou"*. A explicação estava **correta e incompleta**.
> A subida existia — estava presa no índice, e era invisível sem normalizar o
> código. Ninguém errou; a medição certa só não tinha sido feita ainda.

## §7.2 O sentido inverso: o mapa responde duas perguntas, a casa fazia uma

O mesmo arquivo serve `SIGTAP → TUSS` e `TUSS → SIGTAP`. Para **26** registros
curados sem par por nome, o TUSS aponta para **exatamente um** SIGTAP presente
no catálogo. Fundiram — e a linha bare correspondente **morreu** (colapso), em
vez de conviver como duplicata do mesmo procedimento.

> **A caneta dos 38 (#281) é pré-requisito LITERAL deste degrau.** Rodado
> contra a `main` anterior a ela, o mesmo levantamento acha **um** casável — e
> era o `40308030`, o fator reumatóide que se passava por PCR. Teria fundido o
> exame errado, com o código oficial, com convicção e sem alarme.

### Os 9 monodirecionais

Em 9 dos 26, o SIGTAP de destino também recebe outro TUSS: **ambíguo em
`s→t`, unívoco em `t→s`**. Fundem mesmo assim, e a assimetria fica registrada
na `fonte` do registro. Não é a ambiguidade que o ENG-027 recusa — aquela é
escolher entre dois TUSS ao preencher um; aqui não se preenche TUSS nenhum, e
a afirmação `t→s` é da fonte e não tem alternativa.

O exemplo canônico é a **urocultura**: o TUSS "cultura de urina com contagem
de colônias" aponta para o SIGTAP genérico "CULTURA DE BACTÉRIAS P/
IDENTIFICAÇÃO", que também recebe outros TUSS.

## §7.3 O resultado

| métrica | antes | depois |
|---|---|---|
| registros na base | 1.140 | **1.114** (26 colapsos) |
| fundidos (TUSS **e** SIGTAP) | 98 (8,9%) | **669 (60,5%)** |
| curados só-TUSS | 35 | **9** |
| SIGTAP sem TUSS | 1.007 | **436** |

Os 5 números foram conferidos contra os declarados no despacho, um a um.

## §7.4 Três achados que a execução trouxe

**1. A US obstétrica morfológica está pareada com o exame errado — e não foi
este despacho que a pareou.** O registro curado "Ultrassonografia Obstétrica
(Morfológica)" fundiu **por nome** com o SIGTAP `0205020143` = "ULTRASSONOGRAFIA
OBSTETRICA" — a simples. O mapa oficial diz que esse SIGTAP é o TUSS
`40901238` ("US - Obstétrica"), enquanto a caneta deu ao registro o
`40901262` ("US - Obstétrica **morfológica**").

Os dois códigos estão certos sobre coisas diferentes; quem errou foi o **join
por nome**, que casou a morfológica (rastreio detalhado de anomalias) com a
obstétrica de rotina. São procedimentos e preços distintos. A regra protegeu o
dado (o mapa nunca sobrescreve curadoria), mas o par segue inconsistente.
**Não corrigido** — desfazer a fusão ou trocar o código é escolha clínica, e
vai para a mesa do §6 do despacho.

**2. 47 códigos TUSS aparecem em dois registros cada — e é fidelidade.** A
metodologia da ANS (item 3) mapeia "de um ou vários para um ou vários", nos
dois sentidos: o TUSS de "dosagem de fosfatase alcalina" cobre o SIGTAP
simples **e** o "no esperma". Nos **47 casos, sem exceção**, é o mapa que põe
o código nos dois lugares. A guarda, portanto, não proíbe a repetição — exige
que **toda repetição tenha origem na fonte**.

**3. O teto recalculado.** Dos 1.105 exames, **436** seguem sem TUSS: **182
ambíguos** (menos 9 absorvidos pelo sentido inverso) e **264 fora do mapa de
2017-04**. Os ambíguos não se resolvem por engenharia; os 264 só se resolvem
com uma edição mais nova do mapeamento oficial, se existir — e procurá-la é
despacho próprio. **Não se inventa par.**

## §7.5 O que continua na mesa (§6 do ENG-029)

Sete casos são escolha **clínica**, e nenhum entrou: hemograma (se o completo
já traz plaquetas, contar plaquetas à parte é duplo faturamento), glicose
(jejum ou líquido sinovial), T4 livre (dosagem ou índice), TC crânio, RM
lombossacra (lombar ou cervical), urina tipo I (EAS ou contagem global),
parasitológico (ovos/cistos ou larvas). Mais a US obstétrica do §7.4.

Guarda: `test_fusao_por_codigo.py::TestOAmbiguoNaoEntra` — é ela que mantém a
mesa aberta até a caneta.
