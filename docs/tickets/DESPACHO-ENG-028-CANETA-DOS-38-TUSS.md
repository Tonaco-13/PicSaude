# DESPACHO ENG-028 — A caneta dos 38 TUSS (e os 2 do seed)

**Data:** 28/09/2026, tarde · **Emissão:** arquiteto Z, por delegação do assinante
**Classe:** `module` (curadoria de base de exames + seed + guards — sem toque no núcleo)

> **ESTADO: CANETA DADA — verbatim do assinante lavrado no §6, 28/09/2026.**
> O despacho segue à engenharia. A tabela §2 É a caneta; boundary de 28/09
> registrada: código com consequência financeira é caneta do Fabiano.

---

## §0 O que já está feito (não repetir)

- **#279 mergeada** — Tabela 22 oficial estagiada (`data/tuss_procedimentos.csv`,
  5.755 itens, pacote ANS gov.br, sha256 no MANIFEST).
- **#280 mergeada** — medição do retroativo (`MEDICAO-RETROATIVO-TUSS.md`):
  demo = 2 itens, zero dos 38; produção inalcançável da vantage, 3 queries prontas.
- O relatório `RELATORIO-TUSS-RECONCILIACAO.md` §4 mediu os 38 com candidatura
  por sobreposição de termos — **sugestão para poupar trabalho, não decisão**.

## §1 O arquiteto reabriu a tabela contra a fonte — 38/38 fecham

A heurística do relatório era sobreposição de string; a consulta direta à
Tabela 22 estagiada (vantage do arquiteto, 28/09 à tarde) mostra que:

- **27 linhas**: o candidato do relatório é o código certo (conferido por
  código exato, vigência aberta).
- **11 linhas**: o arquiteto **rejeitou** o candidato do relatório ou resolveu
  o "sem candidato" — seis sugestões eram armadilha (órgão/modidade/contexto
  errados), quatro "grupamentos sem item" têm item oficial sim, e uma
  (TC abdome) ganhou código mais fiel ao nome curado genérico.

Nenhuma linha ficou sem resolução. **Zero `codigo_tuss=None`** — os "10
grupamentos" do relatório era artefato da busca, não ausência na terminologia.

**Todos os 40 códigos desta caneta (38 + 2 do seed) foram verificados um a um
no CSV oficial: existem e estão com vigência aberta** (`vigencia_fim` vazio).

## §2 A tabela da caneta — 38 linhas + seed

### Bloco A — trocas diretas (27)

| # | Exame (curado) | Antigo | Oficial | 
|---|---|---|---|
| 1 | Hemograma completo c/ plaquetas | `40301079` | `40304361` |
| 2 | Reticulócitos | `40302264` | `40304558` |
| 3 | VHS | `40306150` | `40304370` |
| 6 | Hemoglobina glicada (HbA1c) | `40302523` | `40302075` |
| 7 | Creatinina | `40302272` | `40301630` |
| 8 | Ureia | `40302434` | `40302580` |
| 9 | Ácido úrico | `40302280` | `40301150` |
| 10 | TGO (AST) | `40302132` | `40302504` |
| 12 | Colesterol total | `40302027` | `40301605` |
| 13 | HDL | `40302035` | `40301583` |
| 14 | LDL | `40302043` | `40301591` |
| 15 | Triglicerídeos | `40302485` | `40302547` |
| 16 | Sódio | `40302450` | `40302423` |
| 17 | Potássio | `40302388` | `40302318` |
| 19 | TSH | `40302671` | `40316521` |
| 20 | T4 livre | `40302590` | `40316491` |
| 21 | T3 | `40302663` | `40316556` |
| 22 | RX tórax (2 inc.) | `40901060` | `40805026` |
| 25 | US obstétrica morfológica | `40901337` | `40901262` |
| 27 | Ecocardiograma transtorácico | `40801124` | `40901106` |
| 29 | TC crânio | `40403090` | `41001010` * |
| 30 | TC tórax | `40403082` | `41001079` |
| 32 | RM crânio | `40601078` | `41101014` |
| 33 | RM lombossacra | `40601086` | `41101227` * |
| 34 | Eletroencefalograma | `40311020` | `40103170` |
| 35 | Urina tipo I (EAS) | `40201030` | `40311210` |
| 36 | Parasitológico de fezes | `40205128` | `40303110` |

\* código oficial composto: `41001010` = "TC - Crânio **ou sela túrcica ou
órbitas**"; `41101227` = "RM - Coluna **cervical ou dorsal ou** lombar". É o
código oficial do segmento; a observação da base registra a composição.

### Bloco B — linhas reabertas pelo arquiteto (11, das quais 5 com micro-decisão)

| # | Exame | Antigo | Oficial | Candidato do relatório | Veredito do arquiteto |
|---|---|---|---|---|---|
| 5 | Glicose (jejum) | `40302019` | `40302040` | `40302032` pós-sobrecarga ✗ | **REJEITADO** — jejum ≠ sobrecarga; o certo é a glicose pura |
| 11 | TGP (ALT) | `40302140` | `40302512` | `40403840` hemoterápico ✗ | **REJEITADO** — hemoterapia; o geral é `40302512` |
| 23 | US abdome total | `40801019` | `40901122` | `40901114` US MAMAS ✗ | **REJEITADO** — órgão absurdo; item oficial existe |
| 24 | US abdome superior | `40801027` | `40901130` | `41001109` TC ✗ | **REJEITADO** — modidade errada; item oficial existe |
| 26 | ECG | `40311012` | `40101010` | `40101029` alta resolução ✗ | **REJEITADO** — rotina é convencional ≤12 derivações |
| 28 | Holter 24h | `40311071` | `20102020` | `20102135` **HOLTER CEREBRAL** ✗ | **REJEITADO** — órgão errado com 75% de sobreposição: a prova de que string não é identidade |
| 31 | TC abdome | `40403104` | `41001095` | `41001109` só superior | **REFINADO** — nome curado é genérico; o total cobre o pedido — **MICRO-DECISÃO 3** |
| 4 | Coagulograma | `40306117` | **`40304922`** | sem candidato | item oficial existe: TS, TC, prova do laço, retração, plaquetas, **TAP, TTPa**; fibrinogênio é item separado (`40304264`) quando pedido — **MICRO-DECISÃO 5** |
| 18 | PCR | `40308030` | **`40308391`** | sem candidato | quantitativa (rotina clínica); alt: `40308383` qualitativa — **MICRO-DECISÃO 1** |
| 37 | Coprocultura c/ ATB | `40205020` | **`40310183`** | `40310426` antibiograma ✗ | cultura de fezes padrão; alt: `40310175` ampliada (campylobacter + EHEC); antibiograma fatura à parte — **MICRO-DECISÃO 4** |
| 38 | Urocultura c/ ATB | `40201048` | **`40310213`** | `40310426` antibiograma ✗ | "Cultura, urina com contagem de colônias"; antibiograma à parte (nota) |

### Bloco C — seed_demo (a terceira fonte)

| Arquivo:linha | Exame | Antigo | Oficial |
|---|---|---|---|
| `backend/seed_demo.py:559` | Hemograma completo | `40301107` (inventado) | `40304361` |
| `backend/seed_demo.py:654,741` | Glicemia de jejum | `40302055` (inventado) | `40302040` |

O hemograma anda com **três** códigos na casa (`40301079` na base + os dois do
seed, nenhum existente); pós-caneta fica com **um**, o oficial.

## §3 As cinco micro-decisões (com recomendação do arquiteto)

1. **PCR**: quantitativa `40308391` **(rec)** — é a de rotina clínica — vs
   qualitativa `40308383`.
2. **Holter 24h**: digital 3 canais `20102020` **(rec)** — padrão atual — vs
   analógico 2+ canais `20102011`.
3. **TC abdome** (nome curado genérico): total `41001095` **(rec)** — cobre o
   pedido sem qualificar — vs superior `41001109`.
4. **Coprocultura**: padrão `40310183` **(rec)** vs ampliada `40310175`.
5. **Coagulograma**: item oficial `40304922` **com observação de composição**
   **(rec)** — cobre TAP+TTPa, excede em TS/TC/prova do laço, e não traz
   fibrinogênio explícito — vs `None` até decisão de decomposição.

## §4 Execução

1. `backend/app/ai/tuss_base.py` `_BASE_RAW`: **38 trocas** de código; onde o
   escopo oficial difere do nome curado (coagulograma, RM coluna, TC crânio,
   culturas, TGO/TGP por nomenclatura oficial), a observação da base registra
   a composição oficial — o nome exibido pode adotar a terminologia oficial,
   e o PR body lista cada renomeação.
2. `backend/seed_demo.py`: as três ocorrências trocam conforme Bloco C.
3. **Guards**: `test_os_38_curados` flipa com a caneta (fingerprint — de
   "existem na T22" para "todos os curados são oficiais"); **guarda nova**:
   todo `codigo_tuss` de `_BASE_RAW` **e** de `seed_demo` deve existir no CSV
   estagiado com vigência aberta — bite test: código fabricado reprova.
4. **RETROATIVO**: histórico é imutável — itens já emitidos mantêm o código
   que faturaram; a medição do #280 é o registro da exposição. **Proibido
   UPDATE retroativo em `pedido_exame_itens`.**
5. **STOP & report**: se qualquer código desta caneta não bater no CSV na
   execução, parar e reportar — não improvisar, não "corrigir" a caneta.
6. PR body re-reporta a cobertura oficial do catálogo pós-caneta (104/1.105
   sobe — o número exato é consequência, não meta).

## §5 Prazo

PR ≤ 30/09 · RATIFICADO do arquiteto com guards re-rodados · martelo do
assinante na sequência — **os 2 válidos-errados não passam a semana de 02/10**
(boundary declarada 28/09).

## §6 A caneta — verbatim do assinante

Lavrada pelo assinante nesta conversa, 28/09/2026, sem ajustes:

> **As 27 diretas entram · Glicose pura · TGP geral · US total · US superior ·
> ECG convencional · Holter digital · PCR quantitativa · Coprocultura padrão ·
> Coagulograma oficial com nota · TC abdome total · seed alinha aos mesmos**

As cinco micro-decisões (§3) ficam resolvidas pelas recomendações: PCR
quantitativa `40308391` · Holter digital 3 canais `20102020` · TC abdome total
`41001095` · Coprocultura padrão `40310183` · Coagulograma oficial `40304922`
com observação de composição. Despacho segue à engenharia.
