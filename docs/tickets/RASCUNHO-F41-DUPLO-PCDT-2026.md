# RASCUNHO F41 DUPLO — semáforo dos Transtornos Ansiosos (v2, levantura dual)

| Campo | Valor |
|---|---|
| **Origem** | Despacho 13/09 ("limpar a mesa", item 3) → **martelo do Fabiano 13/09**: *"Concordo com os três: segunda fonte na ordem SBP/AMB → NICE → mhGAP, citações falsas dobradas no flip, escopo F41 puro. Caça a diretriz."* |
| **Rascunhista** | Engenheiro — **nunca flipa** `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Estado** | 🟡 **RASCUNHO v2 — SEM FLIP.** A autorização verbal de 13/09 ("Merge e canetas autorizados") cobriu **J44 e I50**; F41 **não tem caneta** |
| **Fontes (sha256 conferido contra o MANIFEST)** | **RENAME 2024** (`rename/rename-2024.pdf`, 254 p.) · **AMB/CFM 2008** (`diretrizes/amb-ansiedade-2008.pdf`, 15 p., `2eb7d0df…`) · **ABP/TAG 2024** (`diretrizes/abp-tag-2024.pdf`, 5 p., `20e9d955…`) |

> **Errata da v1:** a v1 (PR #262) afirmou "não há diretriz de ansiedade
> estagiada". Era verdade quando escrita, e **deixou de ser** no mesmo dia: o
> arquiteto caçou e estagiou as duas acima. Esta v2 faz a levantura que a v1
> não podia fazer.

---

## §0 Escopo: F41 PURO

CID-10: **F41 = "Outros transtornos ansiosos"**, e a AMB 2008 organiza as
recomendações **por transtorno**, o que torna o recorte mecânico:

| Dentro (F41) | Fora |
|---|---|
| **F41.0** transtorno de pânico | **F40.1** transtorno de ansiedade social (AMB p. 7, 9) |
| **F41.1** transtorno de ansiedade generalizada (TAG) | **F40.0** agorafobia · **F42** TOC (AMB p. 7-8, 9) |

O recorte não é opinião: o **algoritmo da p. 9** da AMB tem uma linha por
transtorno, e basta ler qual. Duas consequências saem só disso, e nenhuma
delas estava prevista no despacho — ver §2.

---

## §1 A tabela dual (RENAME × AMB 2008 × ABP 2024)

Critério estrito da casa (sinal verde I10 v2): **🟢 = reconhecido _e_
disponível no SUS.** "Reconhecido" = recomendado por diretriz **para um
transtorno de F41**; "disponível" = consta da RENAME 2024.

| Substância | AMB 2008 — escopo F41 | ABP 2024 (TAG) | RENAME 2024 | Estrito |
|---|---|---|---|---|
| **clonazepam** | pânico, 3ª linha, 2–4 mg/dia (p. 6, 9) | BZD, curto prazo (p. 4, genérico) | **p. 94, 130** | **🟢** |
| **clomipramina** | pânico, 2ª linha, 100–150 mg/dia (p. 5, 9) | — | **p. 95, 130** | **🟢** ⚠️ ver §2.1 |
| sertralina | pânico 1ª (50 mg) · TAG 2ª (50–200 mg) (p. 6, 8, 9) | 1ª escolha (p. 3) | **ausente** | 🟡 |
| paroxetina | pânico 1ª (20 mg) · TAG 2ª (20–40 mg) (p. 6, 9) | 1ª escolha (p. 3) | **ausente** | 🟡 |
| escitalopram | — | 1ª escolha (p. 3) | **ausente** | 🟡 |
| venlafaxina | pânico 1ª · TAG 1ª (75–150 mg) (p. 6, 8, 9) | eficaz (p. 4) | **ausente** | 🟡 |
| duloxetina | — | eficaz (p. 4) | **ausente** | 🟡 |
| imipramina | pânico, 2ª linha, 150–200 mg/dia (p. 5, 9) | — | **ausente** | 🟡 |
| alprazolam | pânico, 3ª linha, 2–4 mg/dia (p. 6, 9) | — | **ausente** | 🟡 |
| **fluoxetina** | **só TOC** (p. 9) — **fora de F41** | — | p. 95, 131 | 🟡 ⚠️ ver §2.2 |
| **diazepam** | não nomeado (só "BZD" genérico na TAG) | idem | **p. 98, 133** | ⚠️ ver §2.3 |
| bromazepam | **só ansiedade social** (p. 7) — fora de F41 | — | ausente | 🟡 |

### Elenco estrito proposto: **2 substâncias**

**clonazepam** · **clomipramina** — as únicas que a diretriz recomenda para um
transtorno de F41 **e** que o SUS entrega pela RENAME 2024.

> **O elenco é pequeno e isso é o achado, não um defeito da varredura.** Das 9
> substâncias que as diretrizes recomendam para pânico e TAG, **7 não constam
> da RENAME 2024** — inclusive todas as de primeira linha (sertralina,
> paroxetina, escitalopram, venlafaxina). O que sobra no SUS é um
> benzodiazepínico de 3ª linha e um tricíclico de 2ª. **Marcar isso como 🟡
> honesto é exatamente o serviço que o semáforo presta**: o prescritor de APS
> vê que a 1ª linha do livro não está na prateleira dele.

---

## §2 Três pontos de decisão (só o Fabiano)

### 2.1 Clomipramina — o despacho diz para tirar; **a fonte diz o contrário**

O despacho instruiu: *"clomipramina sai do elenco candidato — seu próprio
achado"*. O achado era meu e estava **incompleto**: eu escrevi na v1 que
clomipramina "é clássica em TOC, que é outro capítulo do CID". É verdade — e
não é só isso.

**A AMB 2008 recomenda clomipramina para TRANSTORNO DE PÂNICO**, que é
**F41.0**, dentro do escopo puro:

> *"A eficácia da clomipramina também foi demonstrada, em menor número de
> ensaios duplo-cego, placebo-controlados"* (p. 5, seção TRANSTORNO DE PÂNICO)

e o algoritmo da p. 9 a lista como **2ª linha do pânico, 100–150 mg/dia** —
dose distinta da do TOC (300 mg/dia), o que confirma que são indicações
diferentes, não a mesma citação contada duas vezes.

Como **consta da RENAME 2024** (p. 95, 130), pelo critério estrito ela é 🟢.

**Não a retirei por conta própria.** A regra do próprio despacho é que na
dúvida entre incluir e não incluir eu marque ponto de decisão em vez de
decidir — e aqui não é nem dúvida minha: é a fonte contradizendo a premissa da
instrução. **Decisão:** entra como 🟢 (recomendação do rascunho, pelo critério
estrito) ou sai por decisão clínica de escopo?

### 2.2 Fluoxetina — seed atual que a diretriz **não** sustenta em F41

`fluoxetina` é uma das 5 seeds vigentes de F41. No algoritmo da AMB (p. 9) ela
aparece **apenas na linha do Transtorno Obsessivo-Compulsivo** (60 mg/dia) —
**nenhuma menção para pânico ou TAG**. A ABP 2024 também não a cita.

Ela **consta da RENAME** (p. 95, 131), então não é caso de indisponibilidade: é
caso de **indicação fora do escopo**. Pelo critério estrito ela seria 🟡 em
F41 — uma **terceira excomunhão**, além das duas que o despacho já previa.

**Decisão:** fluoxetina sai do elenco de F41 (recomendação do rascunho) ou o
escopo F41 admite o uso off-label consagrado em ansiedade?

### 2.3 Diazepam — seed atual que **nenhuma das duas** diretrizes nomeia

`diazepam` é seed vigente e **consta da RENAME** (p. 98, 133). Mas a AMB nunca
o nomeia, e a linha de TAG do algoritmo diz genericamente **"BZD: prazos
curtos"**, sem princípio ativo. A ABP também fala em "benzodiazepínicos" como
classe.

Manter diazepam exigiria ler a classe genérica como endosso nominal — e com
benzodiazepínico no jogo, **"close enough" não é opção** (o aviso é da v1 deste
próprio rascunho, e o despacho o reafirmou).

**Decisão:** diazepam entra por leitura de classe, sai por falta de citação
nominal, ou fica como 🟡 até uma diretriz o nomear?

---

## §3 Excomunhões já decididas (dobradas no flip)

O martelo de 13/09 decidiu: *"citações falsas dobradas no flip"*.

| Seed | `fonte` declarada hoje | Verificação |
|---|---|---|
| **sertralina** | `RENAME/PCDT (APS)` | **NÃO CONSTA da RENAME 2024** — nenhuma das 254 páginas |
| **escitalopram** | `RENAME/PCDT (APS)` | **NÃO CONSTA da RENAME 2024** — nenhuma das 254 páginas |

Mesmo defeito que o F32 excomungou em 02/09: a semeadura de junho citou
"RENAME/PCDT (APS)" em bloco. As duas viram **🟡 com causa** (`não consta da
RENAME 2024`) no ato da caneta — o que é orientação **correta** para o
prescritor de APS: são 1ª linha no livro e não estão na prateleira do SUS.

---

## §4 Nota sobre a força das fontes

Registro para o assinante, porque muda o peso do que está sendo citado:

- **AMB/CFM 2008** é diretriz primária do Projeto Diretrizes, com algoritmo
  próprio e graus de evidência por recomendação. É a fonte forte aqui. Tem
  **17 anos** — a ordem que o martelo fixou (AMB → NICE → mhGAP) prevê
  camadas mais novas, ainda não estagiadas.
- **ABP/TAG 2024** é, pelo próprio texto, uma **revisão sistemática _sobre_ as
  diretrizes da ABP** publicada no *Archives of Health* — não a diretriz da ABP
  em si (ela cita "ABP, 2020" como fonte). Serve como camada moderna e
  corroborante; **não substitui** uma diretriz primária. Usei-a só para
  corroborar, nunca como única sustentação de uma substância.
- **NICE e mhGAP não foram caçados** — a ordem do martelo os coloca depois da
  AMB, e as duas primeiras já bastaram para a levantura. Se o Fabiano quiser a
  camada internacional antes de assinar, é novo gesto de estagiamento.

---

## §5 O que este rascunho NÃO faz

- **Não flipa nada.** Nenhuma linha dos CSVs muda nesta PR. As 5 seeds seguem
  `exaustivo=false`; fora do elenco continua **neutro**, não amarelo.
- **Não resolve os três pontos do §2.** Dois deles (clomipramina, fluoxetina)
  contrariam premissas do despacho, e é justamente por isso que sobem para o
  Fabiano em vez de descerem para o meu julgamento.

## §6 O flip, quando houver caneta

Com o *"concordo com o elenco"* do Fabiano (verbatim, citado no corpo da PR):

- versão: `semaforo_f41_exaustiva_v1_2026-09`;
- rows `validado` + `exaustivo=true`, `validado_por = Fabiano Tonaco Borges`,
  fonte com **página** nas três obras que sustentam cada uma;
- sertralina e escitalopram dobradas no mesmo ato;
- guarda no padrão `test_semaforo_flip_*`, com o elenco, as excomunhões e a
  não-contaminação com F32 (fluoxetina é 🟢 em depressão e seguirá assim).

---

*Lavrado em 13/09/2026 pelo engenheiro. Varredura mecânica (pypdf) da RENAME
2024 (254 p.), da AMB 2008 (15 p.) e da ABP 2024 (5 p.); sha256 das três
conferido contra os MANIFESTs antes da leitura. Nenhuma linha de dado curado
foi tocada.*
