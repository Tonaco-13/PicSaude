# RELATÓRIO — a curadoria TUSS contra a Tabela 22 oficial

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-027-TUSS-SIGTAP-HIPER.md` §2 |
| **Autorização** | Fabiano, 28/09/2026: *"vamos ter que montar um hiper intensivo começando agora para TUSS e Sigtap"* |
| **Fonte de conferência** | ANS/TISS — Tabela 22, competência **201606** (pacote de mapeamento 2017-04), `sha256 b365e36d…`, ver `data/fontes-oficiais/tuss/MANIFEST.md` |
| **Veredito** | ⚠️ **36 dos 38 códigos TUSS curados não correspondem ao exame que nomeiam** |
| **Corrigido nesta PR?** | **NÃO.** Medido, nomeado e travado por guarda. A caneta é do Fabiano |

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

*Lavrado em 28/09/2026 pelo engenheiro, na execução do ENG-027. Guarda:
`backend/tests/unit/test_tuss_base_oficial.py::TestAReconciliacaoEstaMedida`.*
