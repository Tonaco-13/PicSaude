# REGISTRO — a nona row do J44 não existe na fonte

| Campo | Valor |
|---|---|
| **Despacho** | `DESPACHO-ENG-025-RETOMADA.md` §B |
| **GO** | Fabiano, 23/09/2026: *"manda a caneta da nona row com o PCDT 2021"* |
| **Classe** | `curadoria` — dados + guardas, zero `backend/app` |
| **Veredito** | **PARADA DECLARADA** (§B.5 do despacho) — o PCDT 2021 **também** não traz dose |
| **Row escrita** | **nenhuma** |

---

## §1 O que se foi buscar

`fumarato de formoterol + budesonida` em **J44** (DPOC) — a nona das rows
exiladas de J44/I50, a única que não voltou ao `posologia_sugerida.csv` quando
o #269 religou a chave composta `(ativo, CID)`. Não voltou porque **nenhuma
fonte consultada trazia posologia**, e a régua da casa é: *sem dose na fonte,
não se escreve row*.

O registro de 13/09 deixou três saídas e uma recomendação:

> **(C)** ← *recomendada* — estagiar o **PCDT DPOC 2021**, "versão em que
> LABA+ICS ainda era opção inicial e **que deve trazer o esquema**".

O Fabiano martelou a (C). Este documento é o resultado de executá-la.

## §2 A hipótese da saída (C) era falsa

**O PCDT DPOC 2021 não traz o esquema.** A suposição de que a edição anterior
teria a posologia da dupla LABA+ICS não se sustenta contra o documento.

O 2021 foi estagiado como adendo (§4 abaixo) e lido inteiro. O seu
**§7.5 — Esquemas de administração, Quadro F (p. 16–18)** é exaustivo, e as
classes que ele cobre são:

| # | Classe no Quadro F (2021) | Tem esquema? |
|---|---|---|
| 1 | Broncodilatadores beta-2 de **curta** ação (salbutamol, fenoterol) | sim |
| 2 | Antimuscarínicos de curta ação (brometo de ipratrópio) | sim |
| 3 | Broncodilatadores beta-2 de **longa** ação **isolados** (salmeterol, formoterol) | sim |
| 4 | **LABA + LAMA** (umeclidínio+vilanterol · tiotrópio+olodaterol) | sim |
| 5 | **Terapia tripla** (ICS + LAMA + LABA) | sim |
| 6 | Corticosteroides inalatórios **isolados** (budesonida, beclometasona) | sim |
| 7 | Corticosteroides sistêmicos (prednisona, prednisolona, hidrocortisona) | sim |
| — | **LABA + ICS (dupla)** | **NÃO EXISTE A LINHA** |

A mesma ausência, com a mesma forma, no **PCDT DPOC 2025**, Quadro 6
(p. 19–22): SABA · SAMA · LABA · LABA+LAMA · ICS · LABA+LAMA+ICS · corticoide
sistêmico. **Nenhuma linha LABA+ICS.**

### O que as duas edições DE FATO dizem sobre a dupla

Em **ambas**, a única menção com números é a **apresentação**, não a
posologia — quais concentrações o SUS dispensa:

> **2021, §7.4 Fármacos, p. 15, verbatim:**
> *"Formoterol + budesonida: cápsula ou pó para inalação de 6 mcg + 200 mcg e
> de 12 mcg + 400 mcg."*

> **2025, §7.2.1 Medicamentos, p. 19, verbatim:**
> *"- fumarato de formoterol + budesonida: cápsula ou pó para inalação de
> 6 mcg + 200 mcg e de 12 mcg + 400 mcg;"*

Apresentação responde *"o que vem na caixa"*. Posologia responde *"quanto, com
que frequência, por quanto tempo"*. Escrever uma row de posologia a partir de
uma linha de apresentação seria inventar o intervalo e a duração — exatamente
a costura que a saída (B) propunha e que a casa recusou.

Fora do elenco, a dupla aparece no 2021 só em **tabelas de evidência**
(Quadros 15 e 20, p. 49 e 51 — comparações LABA/LAMA *versus* LABA/ICS para
mortalidade cardiovascular e pneumonia) e no **Termo de Esclarecimento e
Responsabilidade** (p. 27–28, lista de caixas a marcar). Em nenhuma delas há
esquema de administração.

### A ausência é substantiva, não lacuna editorial

As duas edições e o GOLD dizem a mesma coisa por caminhos diferentes:

- **PCDT 2021, p. 17 · PCDT 2025, p. 21** (verbatim, idêntico nas duas):
  *"Não se preconiza o uso isolado de corticoide inalatório (como monoterapia)
  na DPOC."* — o ICS entra **acompanhado**, e a forma acompanhada que os dois
  protocolos esquematizam é a **tripla**, não a dupla.
- **GOLD 2025, Fig. 3.20** (verificado em 23/09, ver §5): *"We do not encourage
  the use of a LABA+ICS combination in COPD."*

Três fontes independentes, a mesma direção. A dupla está no elenco porque
pacientes chegam em uso dela e porque ela é objeto da evidência comparada —
não porque algum protocolo a prescreva como esquema.

## §3 Conclusão — e o que NÃO foi feito

**Nenhuma row foi escrita.** O `posologia_sugerida.csv` fica como está, com as
sete rows de J44 do `posologia_j44_v1_2026-09` intocadas.

A pendência do registro de 13/09 **não continua de pé**: ela foi respondida.
A saída (C) foi executada até o fim e devolveu *não*. O que resta é a saída
**(A) — nenhuma row**, agora por **fato verificado na fonte primária**, e não
por fonte não consultada. É uma diferença que importa: o silêncio do CSV
deixou de ser uma lacuna e virou uma **posição**.

Levar isto adiante exigiria escolher uma fonte que não é nenhuma das três
(bula do fabricante, sociedade de especialidade, extrapolação da asma) — e
essa é decisão do arquiteto e do Fabiano, não da engenharia. Fica escrita
aqui, não adjudicada.

## §4 O que ficou no disco como prova

`data/fontes-oficiais/pcdt/adendos-pos-batch/pcdt-da-doenca-pulmonar-obstrutiva-cronica-2021.pdf`

- **Portaria Conjunta SAES/SCTIE nº 19, de 16 de novembro de 2021** · 72 pág.
- sha256 `86448b826799ad98ee5f05634fa3bbb25c9e94f5af8dd01627c8cd70ec60cc2c`
- Procedência, corroboração independente e a razão de vir do Internet Archive:
  entrada própria em `data/fontes-oficiais/pcdt/MANIFEST.md`.

O PDF fica estagiado **mesmo sem row**: é a evidência de que a pergunta foi
feita à fonte primária, e é o que permite a qualquer revisor reabrir o Quadro F
e conferir a ausência com os próprios olhos.

### A data da portaria, resolvida pelo documento

A casa vinha citando *"nº 19, de 22/11/2021"*; o despacho pediu que **o PDF
fosse o juiz**. Ele é, e desempata sem culpados: o art. 4º do PCDT 2025 diz as
duas datas na mesma frase — *"Portaria Conjunta nº 19, de **16** de novembro de
2021, publicada no Diário Oficial da União (DOU) nº 218, em **22** de novembro
de 2021, seção 1, página 210"* — e a capa do 2021 estagiado confirma
**"DE 16 DE NOVEMBRO DE 2021"**. **Assinada em 16/11, publicada em 22/11.**
A casa citava a data de publicação.

## §5 Fontes consultadas, e o que cada uma respondeu

| Fonte | Onde | Traz dose da dupla? |
|---|---|---|
| PCDT DPOC **2025** (Port. Conj. SAES/SCTIE 29, 27/11/2025) | corpus 30/08, `0cb3c41b…`, Quadro 6 p. 19–22 | **não** — sem linha LABA+ICS |
| PCDT DPOC **2021** (Port. Conj. SAES/SCTIE 19, 16/11/2021) | adendo 24/09, `86448b82…`, Quadro F p. 16–18 | **não** — sem linha LABA+ICS |
| **GOLD 2025** (referência 2 do próprio PCDT) | `diretrizes/gold-2025-report.pdf`, `a1a47993…` | **não** — Fig. 3.18/Tab. 3.3 não têm coluna de dose; **zero** ocorrências de mcg/µg em 215 páginas |
| **GOLD 2023** | conferido em 23/09 | **não** — mesma estrutura |

Nenhuma das quatro. A conferência de 23/09 (GOLD) está registrada na
`FILA-VIVA.md`; a de 24/09 (PCDT 2021) é este documento.

## §6 Uma observação que a leitura levantou — para o arquiteto, não adjudicada

Com **uma única** posologia curada no CSV inteiro, `posologia_sugerida.sugerir`
entra no caminho do **ativo unívoco** quando a requisição **não informa CID**
(`posologia_sugerida.py`, docstring do `sugerir`: *"substância unívoca →
retrocompat preservada"*). Hoje `fumarato de formoterol + budesonida` tem
exatamente uma row — a de **asma (J45)**, com a estratégia AIR/MART.

Consequência, verificada e travada por guarda (§7):

- `sugerir(par, "J44")` → **`None`**. A dose de asma **não** vaza para a DPOC
  quando o CID está declarado. É o que o despacho §B.4 mandou provar, e passa.
- `sugerir(par, None)` → **a row de ASMA**, pelo caminho do unívoco.

O segundo caso é comportamento **declarado** do módulo, não defeito de
execução: a regra do unívoco existe e está documentada. Mas nesta substância
específica ela serve uma estratégia *asma-específica* a quem não codificou o
CID — e a dupla está no elenco da DPOC. Escrever a row do J44 fecharia isso por
efeito colateral (dois candidatos ⇒ silêncio sem CID); como a row não existe,
a questão fica aberta e **é de curadoria, não de engenharia**. Registrada aqui
para não ficar só na conversa.

## §7 Guarda executável

`backend/tests/unit/test_semaforo_flip_j44_i50.py::TestNonaRowNaoExiste` —
quatro asserções que fazem deste registro um fato que o gate cobra:

1. **não existe** row `(fumarato de formoterol + budesonida, J44)` no
   `posologia_sugerida.csv`;
2. `sugerir(par, "J44")` devolve `None` — a dose de asma não vaza (§B.4);
3. a row de **asma** (J45) segue intacta — a parada não apagou dado curado;
4. a dupla continua **🟢 no semáforo** de J44 — elenco e posologia respondem
   perguntas diferentes, e a ausência de dose não rebaixa o sinal.

A guarda morde nos dois sentidos: se alguém escrever a row sem passar pelo
arquiteto, (1) reprova; se o vazamento da asma voltar, (2) reprova.

---

*Lavrado em 24/09/2026. O GO foi "manda a caneta"; a fonte respondeu que não
há o que canetar. Registrar o não é o mesmo trabalho que registrar o sim —
e é o que impede a pergunta de ser refeita daqui a três meses.*
