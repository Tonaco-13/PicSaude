# PENDÊNCIAS — a caneta em lote (ENG-025 §C)

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-025-RETOMADA.md` §C |
| **Autorização** | Fabiano, 24/09/2026: *"Vamos lá prosseguir com 1, 2 e 3."* |
| **Regra seguida** | §C.2 — *"seguir a recomendação registrada no próprio rascunho (precedente #261 §4); rascunho sem recomendação num ponto → **pendência escrita de volta ao Fabiano, nunca adjudicada pela engenharia**"* |
| **Destinatário** | Fabiano (as 6 decisões) · Arquiteto (as 5 conferências) |

---

## Parte A — as 6 decisões que voltam, por não terem recomendação

Cada uma é um ponto de decisão onde o rascunho **apresentou as opções e não
escolheu**, ou onde escolheu antes de um cruzamento que só agora foi feito.
Nenhuma foi adjudicada. Onde havia um caminho seguro e reversível, ele foi
tomado e está dito — mas a palavra final é do Fabiano.

### A1 · A30 — B92 (sequelas de hanseníase)

> Rascunho §4.1, verbatim: *"**B92 (sequelas)** — sem fármaco no escopo; fora
> do semáforo ou row neutra — **decidir**."*

**O que foi feito:** nada. B92 não recebeu row nenhuma; o semáforo fica
**neutro** nele (não há lista exaustiva declarada), que é o silêncio honesto.

**O que falta:** dizer se B92 deve ganhar uma linha própria declarando "sem
fármaco no escopo" — hoje ele é indistinguível de qualquer CID que a casa
simplesmente ainda não curou.

### A2 · G30 — alias F00 (demência na doença de Alzheimer)

> Rascunho §4.1: *"Proposta: rows sob **G30** + **avaliar** alias F00."*

**O que foi feito:** as 4 rows estão em **G30**, como a proposta diz.

**O que falta:** o "avaliar" do F00. O prescritor pode codificar F00 (demência
na DA) em vez de G30 — e a cadeia do semáforo **não** sobe de F00 para G30
(são categorias distintas, não subcategoria e categoria). Hoje quem codifica
F00 recebe **neutro**. Espelhar o elenco em F00 dobra 4 rows; não espelhar
deixa um caminho de codificação legítimo sem sinal.

### A3 · G40 — valproato em mulheres em idade fértil

> Rascunho §4.2: *"manter row única com observação forte, **ou** row separada —
> **decisão de produto**."*

**O que foi feito:** **row única com observação**. A observação do ácido
valproico carrega *"Mulher em idade fértil e gestante: caso especial do PCDT
(teratogenicidade)"*.

**O que falta:** se a teratogenicidade merece mais que uma observação. O
semáforo não tem metadado de população — hoje a informação chega como texto,
não como sinal.

### A4 · IST — A53 (sífilis não especificada)

> Rascunho §4.2: *"Se o seletor do prescritor oferecer 'A53 sífilis não
> especificada' (família P-6), **decidir** se A53 entra como row-espelho."*

**O que foi feito:** A51 e A52 entraram; **A53 não**. Quem codifica A53 recebe
neutro.

**O que falta:** a decisão. Nota de conferência: a base CID-10 da casa
(`data/cid10.csv`) confirma **A53 = "Outras formas e as não especificadas da
sífilis"** — existe e é codificável.

### A5 · M81 — romosozumabe

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

### A6 · L20 — mometasona e dupilumabe ⚠️ (a mais consequente)

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

*Lavrado em 24/09/2026, junto com a PR do lote. As 6 decisões da Parte A não
bloqueiam o merge — o que elas mudam é uma linha de CSV e uma de teste cada,
e a A6 é a única que muda contagem (L20: 6 rows hoje, 8 se o Fabiano disser).*
