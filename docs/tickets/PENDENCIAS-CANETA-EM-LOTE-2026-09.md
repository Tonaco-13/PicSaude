# PENDÊNCIAS — a caneta em lote (ENG-025 §C)

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-025-RETOMADA.md` §C |
| **Autorização** | Fabiano, 24/09/2026: *"Vamos lá prosseguir com 1, 2 e 3."* |
| **Regra seguida** | §C.2 — *"seguir a recomendação registrada no próprio rascunho (precedente #261 §4); rascunho sem recomendação num ponto → **pendência escrita de volta ao Fabiano, nunca adjudicada pela engenharia**"* |
| **Destinatário** | Fabiano (as 6 decisões) · Arquiteto (as 5 conferências) |
| **Estado** | ✔️ **TODAS RESOLVIDAS** — caneta do Fabiano em **28/09/2026**, executada no ENG-026 |

> ## ✔️ Caneta do Fabiano, 28/09/2026 — verbatim
>
> **"A1 fora · A2 espelha F00 · A3 mantém · A4 espelha A52 em A53 · A5 mantém ·
> A6 volta às 8 rows · K21 por diretriz · E03 semente."**
>
> As seis decisões da Parte A estão resolvidas abaixo, cada uma com o gesto que
> a executou. Três mexeram em dado (A2, A4, A6) e três não (A1, A3, A5) — e
> "não mexe em dado" é resolução igualmente, não pendência que sobrou.
>
> **O que a A6 mudou além de duas rows:** o critério do verde foi **refinado**
> e passa a valer para toda a casa —
> 🟢 = reconhecido no protocolo **E** disponível no SUS, com a disponibilidade
> atestada por **RENAME ∨ incorporação vigente que nomeie o fármaco**. A coluna
> `fonte` declara qual dos dois atesta. Citar a RENAME como se o fármaco lá
> estivesse continua sendo erro — e agora tem guarda própria
> (`test_a_fonte_do_verde_do_l20_nao_finge_rename`).
>
> O refinamento abriu a **P-11** (§ no fim deste documento): re-conferir sob o
> critério novo os excluídos-por-RENAME do J44 e do I50. Critério refinado que
> só vale onde foi aplicado é exceção sem regra.

---

## Parte A — as 6 decisões que voltam, por não terem recomendação

Cada uma é um ponto de decisão onde o rascunho **apresentou as opções e não
escolheu**, ou onde escolheu antes de um cruzamento que só agora foi feito.
Nenhuma foi adjudicada. Onde havia um caminho seguro e reversível, ele foi
tomado e está dito — mas a palavra final é do Fabiano.

### ✔️ A1 · A30 — B92 (sequelas de hanseníase) · **FORA**

> **Resolvido em 28/09:** *"A1 fora"*. B92 permanece **sem row e sem
> exaustividade** — neutro é o silêncio honesto para "sequelas sem escopo
> farmacológico". Exaustivo-com-zero-rows seria mecanismo novo para um canto, e
> não se gasta mecanismo em canto. **Nenhum gesto de dado.**


> Rascunho §4.1, verbatim: *"**B92 (sequelas)** — sem fármaco no escopo; fora
> do semáforo ou row neutra — **decidir**."*

**O que foi feito:** nada. B92 não recebeu row nenhuma; o semáforo fica
**neutro** nele (não há lista exaustiva declarada), que é o silêncio honesto.

**O que falta:** dizer se B92 deve ganhar uma linha própria declarando "sem
fármaco no escopo" — hoje ele é indistinguível de qualquer CID que a casa
simplesmente ainda não curou.

### ✔️ A2 · G30 — alias F00 (demência na doença de Alzheimer) · **ESPELHA**

> **Resolvido em 28/09:** *"A2 espelha F00"*. Entraram **4 rows de semáforo e 4
> de posologia** sob F00, espelho exato das de G30 (`semaforo_f00_alias_v1_2026-09`
> / `posologia_f00_alias_v1_2026-09`), e F00 entrou no conjunto exaustivo.
> Guarda: `test_semaforo_espelhos_2026_09.py::TestOEspelhoF00` — **espelho que
> deriva reprova**, no elenco e na posologia, caractere a caractere.


> Rascunho §4.1: *"Proposta: rows sob **G30** + **avaliar** alias F00."*

**O que foi feito:** as 4 rows estão em **G30**, como a proposta diz.

**O que falta:** o "avaliar" do F00. O prescritor pode codificar F00 (demência
na DA) em vez de G30 — e a cadeia do semáforo **não** sobe de F00 para G30
(são categorias distintas, não subcategoria e categoria). Hoje quem codifica
F00 recebe **neutro**. Espelhar o elenco em F00 dobra 4 rows; não espelhar
deixa um caminho de codificação legítimo sem sinal.

### ✔️ A3 · G40 — valproato em mulheres em idade fértil · **MANTÉM**

> **Resolvido em 28/09:** *"A3 mantém"*. Row única com observação forte
> permanece. **Nenhum gesto de dado.**
>
> **Encaminhamento registrado:** a camada de **metadados de população**
> (valproato em idade fértil, romosozumabe e o que vier) fica como candidata à
> trilha de explicabilidade — é **decisão de produto, não de curadoria**. O
> semáforo hoje não distingue população, e enquanto não distinguir a informação
> chega como texto na observação, que é onde ela pode chegar sem mentir.


> Rascunho §4.2: *"manter row única com observação forte, **ou** row separada —
> **decisão de produto**."*

**O que foi feito:** **row única com observação**. A observação do ácido
valproico carrega *"Mulher em idade fértil e gestante: caso especial do PCDT
(teratogenicidade)"*.

**O que falta:** se a teratogenicidade merece mais que uma observação. O
semáforo não tem metadado de população — hoje a informação chega como texto,
não como sinal.

### ✔️ A4 · IST — A53 (sífilis não especificada) · **ESPELHA A52**

> **Resolvido em 28/09:** *"A4 espelha A52 em A53"*. Entraram **2 rows de
> semáforo e 2 de posologia** sob A53, com o **esquema TARDIO**
> (`semaforo_a53_alias_v1_2026-09` / `posologia_a53_alias_v1_2026-09`), e A53
> entrou no conjunto exaustivo.
>
> **Por que o tardio e não o recente** — e esta é a afirmação clínica do
> espelho: o Quadro 15 (p. 23-24) define sífilis tardia como *"sífilis latente
> tardia (com mais de um ano de evolução) **ou latente com duração ignorada** e
> sífilis terciária"*, e a CID-10 chama A53.0 de *"sífilis latente, não
> especificada se recente ou tardia"*. Espelhar o A51 daria dose única a quem
> precisa de três semanas. Guarda:
> `TestOEspelhoA53::test_a_posologia_e_a_TARDIA_e_nao_a_recente`.
>
> Neurossífilis segue fora do escopo ambulatorial (Quadro 15 a trata com
> benzilpenicilina cristalina EV, 14 dias — internação).


> Rascunho §4.2: *"Se o seletor do prescritor oferecer 'A53 sífilis não
> especificada' (família P-6), **decidir** se A53 entra como row-espelho."*

**O que foi feito:** A51 e A52 entraram; **A53 não**. Quem codifica A53 recebe
neutro.

**O que falta:** a decisão. Nota de conferência: a base CID-10 da casa
(`data/cid10.csv`) confirma **A53 = "Outras formas e as não especificadas da
sífilis"** — existe e é codificável.

### ✔️ A5 · M81 — romosozumabe (e os 3 suplementos) · **MANTÉM**

> **Resolvido em 28/09:** *"A5 mantém"*. As rows ficam. O romosozumabe é
> **reconhecido** (elenco do PCDT) e **disponível** (passou no cruzamento da
> RENAME); a via especializada e a contraindicação cardíaca moram na
> observação, que é onde devem morar. Revisita no dia em que houver fluxo de
> dispensação distinto. **Nenhum gesto de dado.**


> Rascunho §2 propõe a row. Rascunho §4.3: *"Manter como row (leitura literal)
> com observação, **ou** deixar 🟡-neutro até haver fluxo de dispensação —
> **decisão de produto além da curadoria**."*

**O que foi feito:** a row **entrou**, seguindo o §2 (a proposta escrita do
rascunho), com observação de via especializada e a contraindicação de infarto
ou AVE no ano anterior.

**O que falta:** o §4.3 diz em letras claras que isso é decisão de produto.
Se a resposta for "🟡 até haver fluxo", sai uma linha do CSV e uma do teste.
Mesma pergunta se aplica, com menos força, aos 3 suplementos de cálcio/vitamina
D (§4.2 do mesmo rascunho: *"decidir se a caneta os quer no elenco exaustivo ou
apenas na posologia"*) — entraram no elenco, pela mesma leitura do §2.

### ✔️ A6 · L20 — mometasona e dupilumabe · **VOLTA ÀS 8 ROWS**

> **Resolvido em 28/09:** *"A6 volta às 8 rows"*. As duas entraram como 🟢, e
> **o L20 inteiro foi re-assinado em v2** (`semaforo_l20_exaustiva_v2_2026-09`
> / `posologia_l20_v2_2026-09`), no padrão do I10 v2: quando o elenco de uma
> condição muda, a condição inteira ganha versão nova.
>
> **O que sustenta o verde não é a RENAME — é a incorporação**, e a `fonte`
> das duas rows diz isso com todas as letras: *"incorporação vigente que nomeia
> o fármaco; RENAME 2024 (254 págs.) não alcança o protocolo (nov/2025)"*. Elas
> são as únicas rows do CSV que **não** citam a RENAME, e é de propósito.
>
> A guarda foi **invertida, não apagada** — e ganhou par:
> `test_mometasona_e_dupilumabe_sao_verdes_pela_incorporacao_declarada` exige o
> verde, e `test_a_fonte_do_verde_do_l20_nao_finge_rename` exige que a fonte
> **registre a ausência** em vez de fingir presença. A mesma guarda reafirma
> que a **fluticasona do J44 continua 🟡**: protocolo antigo recomendando
> fármaco que ninguém incorporou por nome não ganhou nada com o refinamento.


**Esta é a única em que a entrega DIVERGE do §2 do rascunho, e a divergência
tem causa verificável.**

O rascunho propôs 8 rows para L20. O cruzamento com a RENAME 2024 — que os
rascunhos adiavam para *"a sessão de assinatura"* e que foi executado nesta PR
— mostrou que **`furoato de mometasona` e `dupilumabe` têm ZERO ocorrências**
nas 254 páginas da RENAME 2024 (conferido também por `mometas`, `furoato` e
`dupilum` soltos). Os outros 6 estão lá.

Pelo critério estrito que a casa já aplicou e travou no J44 — **🟢 = reconhecido
no protocolo E disponível no SUS**, que deixou a fluticasona de fora com a razão
*"recomendada no PCDT, ausente da RENAME 2024"* — os dois ficaram **fora do
verde**. L20 tem 6 rows, não 8.

**Por que não adjudiquei para o outro lado:** o rascunho recomendou incluir,
mas recomendou **antes** do cruzamento, e ele mesmo adiou o cruzamento
justamente por ele poder mudar a resposta. Segui o precedente executável (J44)
em vez da recomendação feita sem o dado.

**Contexto que pode mudar a decisão:** o PCDT da dermatite atópica é de
**novembro de 2025** e a RENAME é de **2024** — a ausência pode significar
"a RENAME ainda não alcançou o protocolo", não "não está disponível". Se for
esse o entendimento, as duas rows voltam em uma linha cada, e a guarda
`TestOCruzamentoRenameMudouRows::test_mometasona_e_dupilumabe_ficaram_fora_do_verde_do_l20`
se inverte junto.

---

## Parte B — 5 conferências que mudaram a entrega (não são decisões, são fatos)

Estas **não voltam como pergunta**: são erros ou lacunas verificáveis,
corrigidos contra a fonte. Ficam aqui porque o arquiteto precisa saber que os
rascunhos mudaram, e porque o precedente da casa é o do typeahead (#216), onde
a conferência achou 4 erros numa whitelist rascunhada.

### B1 · A família IST tinha dois CIDs conflados — 11 viraram 12

O rascunho keava **"A58 — LGV/donovanose"** num código só. A base CID-10 da
casa separa: **A55 = "Linfogranuloma (venéreo) por clamídia"** · **A58 =
"Granuloma inguinal"** (donovanose). E o **Quadro 39 do PCDT (p. 72)** traz as
duas doenças em **linhas separadas, com esquemas diferentes** — a primeira
opção do LGV é doxiciclina 21 dias; a da donovanose é azitromicina semanal por
pelo menos 3 semanas. Split aplicado.

### B2 · O mapeamento de quadros do rascunho comprimido estava trocado

O §3 do rascunho IST resumia as posologias numa linha corrida, sem página por
row. Ao expandir, os quadros foram reabertos um a um, e o mapa real é:

| Quadro | Página | Assunto |
|---|---|---|
| 15 | 23 | sífilis |
| 31 | 60 | gonorreia e clamídia |
| **33** | **60** | **candidíase vulvovaginal** — *não* cancroide |
| 34 | 61 | vaginose bacteriana |
| 35 | 61 | tricomoníase |
| 38 | 71 | herpes genital |
| **39** | **72** | **cancroide, LGV e donovanose** |
| **44** | **77** | DIP — *não* p. 78 |

### B3 · O cruzamento RENAME desmentiu três suspeitas e confirmou uma ausência

Os rascunhos do E78, F17, G30, G40, L20, M81 e R52 diziam todos *"rascunhista
prepara o cruzamento na sessão de assinatura"*. Foi feito aqui, substância a
substância, contra `data/fontes-oficiais/rename/rename-2024.pdf`:

- **E78:** as suspeitas de ausência (etofibrato, genfibrozila, ácido nicotínico)
  eram **falsas** — os três estão lá (p. 44/190, 44/193, 41/165).
- **M81, R52, G40, F17, G30:** todos os elencos presentes.
- **G40/R52:** `valproato de sódio` **não aparece** em nenhuma das 254 páginas;
  só `ácido valproico` (p. 93 e 125). A row-alias entrou assim mesmo — ela
  existe porque `canon_ativo` resolve "valproato de sódio" para a chave
  `valproato`, distinta de `acido valproico`, e sem ela a grafia do próprio
  PCDT daria amarelo falso. Mas a **fonte da row registra a ausência** em vez
  de citar a RENAME como se ele estivesse lá.
- **L20:** ver A6.

### B4 · Quatro "rows-alias" propostas eram desnecessárias — o código já resolve

Os rascunhos propunham rows duplicadas para grafias com e sem sal. Conferido no
`canon_ativo`: o prefixo de sal **já é removido**.

| Proposto | Vira | Alias necessário? |
|---|---|---|
| `cloridrato de bupropiona` | `bupropiona` | **não** — e é a mesma chave do F32 |
| `cloridrato de donepezila` | `donepezila` | **não** |
| `bromidrato de galantamina` | `galantamina` | **não** |
| `cloridrato de memantina` | `memantina` | **não** |
| `ácido nicotínico` (acento) | `acido nicotinico` | **não** — acento é normalizado |
| `valproato de sódio` | `valproato` | **SIM** — chave de fato distinta |
| `genfibrozila` / `gemfibrozila` | chaves distintas | **SIM** — alias escrito |

Criar as desnecessárias teria produzido duas rows com a mesma chave, e a guarda
`len(idx) == len(rows)` teria reprovado — o defeito seria pego, mas depois.

O que o `canon_ativo` **não** normaliza é **forma farmacêutica**. Por isso o F17
tem as três formas da nicotina como rows próprias (`adesivo de nicotina`,
`goma de nicotina`, `pastilha de nicotina`), mais a âncora `nicotina`, como o
§4.1 daquele rascunho recomendou.

### B5 · Uma guarda mergeada partia de uma premissa que o dado real derrubou

`test_semaforo_flip_j44_i50.py::test_posologia_com_dois_cids_para_o_mesmo_ativo_agora_convive`
exigia que uma substância compartilhada tivesse posologia **diferente** em cada
CID — a distinção era usada como prova de que a chave discriminava.

Com o PCDT das IST a premissa caiu: o Quadro 31 (clamídia) e o Quadro 39
(cancroide) prescrevem o **mesmo** esquema de azitromicina. Texto igual ali é
fidelidade à fonte, não duplicação.

A exigência de distinção era um **proxy**; o que de fato prova que nada foi
engolido são as duas asserções vizinhas (o índice tem uma entrada por linha
validada; cada par devolve o **seu** CID). O proxy virou **lista declarada**
(`_REPETE_POR_PROTOCOLO`): repetição nova continua reprovando até alguém
escrevê-la ali com a página. Duas entradas hoje — azitromicina e naproxeno.

---

## Parte C — dois achados registrados, fora do escopo deste lote

### C1 · O N39.0 tem 8 substâncias no semáforo e 3 na posologia

O ciprofloxacino é 🟢 em N39.0 desde a caneta da ITU e agora também em A57 e
A58. No `posologia_sugerida.csv`, porém, o N39.0 só tem nitrofurantoína,
fosfomicina e cefalexina — faltam cinco, entre elas o ciprofloxacino.

**Não é regressão deste lote e não foi consertado aqui**: completar o elenco de
posologia do N39.0 é curadoria da ITU, com a sua fonte e a sua caneta. Está
travado como fato em
`test_semaforo_flip_lote_2026_09.py::test_o_ciprofloxacino_colide_no_semaforo_mas_o_n39_nao_tem_posologia`
para que a ausência não seja lida como efeito colateral das 143 rows novas.

### C2 · O naproxeno entrou sem exaustividade, de propósito

O PCDT da Dor Crônica manda o naproxeno para M16/M17 (Portaria SCTIE 53/2017,
p. 14) mas **não traz o elenco da osteoartrite**. Declarar M16/M17 exaustivos
faria o semáforo julgar o que a fonte não afirma — o paracetamol ficaria 🟡 na
gonartrose, o que é falso. As rows existem (o rascunho as propôs); o portão da
exaustividade mantém o silêncio honesto. Guarda:
`test_o_naproxeno_entrou_sem_declarar_exaustividade_em_m16_m17`.

---

## Parte D — P-11, a pendência que o refinamento do critério abriu

**Nomeada aqui, não adjudicada.** O §1 do ENG-026 refinou o critério do verde
(RENAME **∨** incorporação vigente que nomeie o fármaco). O refinamento nasceu
no L20 — mas um critério que vale só onde nasceu não é critério, é exceção.

**P-11 — re-conferência das exclusões gêmeas.** Quatro fármacos foram excluídos
do verde **por ausência na RENAME**, sob o critério anterior:

| CID | Fármaco | Razão registrada na época |
|---|---|---|
| J44 | fluticasona | *"recomendada no PCDT, ausente da RENAME 2024"* |
| J44 | glicopirrônio | *"LAMA citado no PCDT, ausente da RENAME 2024"* |
| I50 | bisoprolol | *"citado no PCDT, ausente da RENAME 2024"* |
| I50 | ivabradina | *"citada no PCDT, ausente da RENAME 2024"* |

Para cada um: procurar **portaria de incorporação que o nomeie para a
indicação**. Achando, a row volta pelo mesmo rito do L20 — `fonte` decorada
declarando o que atesta a disponibilidade, e guarda invertida. Não achando, a
razão da exclusão ganha o carimbo *"re-conferido 28/09 sob critério refinado"*,
e a exclusão passa a ser posição verificada em vez de herança.

Verificação de ~1h, na próxima sessão de curadoria. **Não é gesto desta PR** —
está aqui para que o refinamento não derive em silêncio por CID.

> Nota de método: a fluticasona do J44 já está travada como 🟡 pela guarda
> `test_mometasona_e_dupilumabe_sao_verdes_pela_incorporacao_declarada`, que
> assere as duas coisas ao mesmo tempo — o verde novo do L20 e o amarelo velho
> do J44. Se a P-11 concluir que a fluticasona tem incorporação, é essa
> asserção que muda, e o PR que a mudar terá de dizer por quê.

---

*Lavrado em 24/09/2026 junto com a PR do lote; **resolvido em 28/09/2026** pela
caneta do Fabiano, executada no ENG-026. Das 6 decisões, 3 mexeram em dado
(A2 · A4 · A6) e 3 fecharam sem mexer (A1 · A3 · A5). A Parte D é o que a
caneta abriu de novo.*
