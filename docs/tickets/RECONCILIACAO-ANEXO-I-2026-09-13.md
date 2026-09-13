# Reconciliação — catálogo curado × Anexo I oficial (13/09/2026)

> **AC5 do `DESENHO-TALAO-DIGITAL-SNCR.md` §1.1**, que esperava desde 28/08:
> *"as 56 curadas atuais migram/reconciliam contra a lista oficial —
> divergências relatadas, NÃO silenciosas"*. Este é o relatório.
> Reproduzível: `backend/scripts/reconciliar_catalogo_344.py`.

## A fonte

| | |
|---|---|
| Documento | Anexo I da Portaria SVS/MS 344/1998, texto **consolidado** |
| Versão | Atualização nº 101 — RDC 1.036/2026 (09/07/2026) |
| Origem | Anvisa Legis, exportação interativa 13/09/2026 |
| PDF | 57 páginas · sha256 `58e88fd05cee24ac03c85f3222e7947e235303dfa22d73cff6e8a7607f233d98` |
| Transcrição | `backend/scripts/transcrever_portaria_344.py` (pypdf, offline) |
| Snapshot | `data/fontes-oficiais/anvisa-controlados-2026-08-28/anexo-i-consolidado.json` |

O PDF **não é versionado** (4,8 MB de corpus-fonte); o que entra no repo é a
transcrição, com o sha256 amarrando as duas no `MANIFEST.md`.

## O que foi transcrito

476 substâncias das nove listas **prescritíveis**, mais 21 designações
alternativas que a própria fonte declara (ver adiante):

| Lista | Título formal | Substâncias |
|---|---|---|
| A1 | Substâncias entorpecentes | 94 |
| A2 | Entorpecentes de uso permitido em concentrações especiais | 13 |
| A3 | Substâncias psicotrópicas | 14 |
| B1 | Substâncias psicotrópicas | 95 |
| B2 | Psicotrópicas anorexígenas | 8 |
| C1 | Outras substâncias sujeitas a controle especial | 213 |
| C2 | Substâncias retinoicas | 5 |
| C3 | Substâncias imunossupressoras | 3 |
| C5 | Substâncias anabolizantes | 31 |

**Fora do catálogo de prescrição, por decisão declarada:** D1 (precursores),
D2 (insumos químicos), E (plantas proscritas) e F1–F4 (proscritas). Proscrito
não é "controlado com receita" — marcá-lo como classe faria o semáforo sugerir
que existe receituário para ele.

## As três divergências

Todas as 20 curadas da Portaria 344 resolvem na lista oficial. **Nenhuma
ausente.** Três estavam com a classe errada:

| Substância | Classe curada | Classe oficial | Consequência |
|---|---|---|---|
| **Tramadol** | B1 | **A2** | muda o receituário: A2 é Notificação de Receita "A" |
| **Isotretinoína** | D1 | **C2** | D1 é precursor; isotretinoína é retinoica |
| **Talidomida** | D1 | **C3** | D1 é precursor; talidomida é imunossupressora |

As três **migram sozinhas** no import: o snapshot faz upsert por
`dcb_normalizada` e a classe oficial substitui a curada. A guarda
`test_toda_divergencia_migra_no_upsert` prova que a chave existe — sem isso a
row curada sobreviveria com a classe antiga ao lado da oficial, que é classe
contraditória dentro de um catálogo carimbado.

**As outras seeds não são tocadas:** antimicrobianos (IN 83/2021) e GLP-1
(IN 360/2025) não são da Portaria 344 e sobrevivem intactos ao snapshot.

## Dois achados sobre a própria fonte

**1. Talidomida não está na Lista A1.** O `MANIFEST.md` registra, entre as
provas de captura do courier, `TALIDOMIDA (Lista A1) ✓`. **Está errado.** No
consolidado, talidomida aparece nas listas de substância **uma única vez**, na
**Lista C3**, sob o nome químico: `1.Ftalimidoglutarimida (talidomida)`
(p. 31). As demais ocorrências (p. 47–49) estão nos **anexos** do Termo de
Esclarecimento ao usuário, que não são lista de substância. Conferido linha a
linha no PDF, que é o juiz nessas divergências.

**2. O código da lista está no PDF.** O briefing previa que o consolidado
traria apenas títulos formais ("LISTA DAS SUBSTÂNCIAS PSICOTRÓPICAS"), e que o
importador teria de mapear título→classe. O texto traz **os dois**: o código
(`LISTA - B1`) e o título. E o código é indispensável, porque **o título não é
chave única** — A3 e B1 compartilham exatamente "LISTA DAS SUBSTÂNCIAS
PSICOTRÓPICAS". Mapear por título teria colapsado as duas listas.

## As 21 designações alternativas

O consolidado nomeia parte das substâncias pelo nome químico com o usual entre
parênteses — `Ftalimidoglutarimida (talidomida)`, `Canabidiol (CBD)`,
`Prasterona (deidroepiandrosterona - DHEA)` — ou por dois nomes ligados por
" ou ". O lookup do catálogo chaveia por `normalizar_dcb`, e `talidomida` **não
casa** com `ftalimidoglutarimida (talidomida)`.

Sem emitir a designação alternativa, quem digitasse "Talidomida" erraria a row
oficial C3 e acertaria a curada antiga D1 — o catálogo carimbado conteria a
contradição que o carimbo promete não ter. Cada alternativa entra como linha
própria, com a mesma classe, e **marcada na `observacao`** com a designação
canônica entre colchetes: é linha de lookup, não substância a mais da lista.
O texto sai do próprio Anexo I; o que se acrescenta é a linha, não o fato.

## O que o carimbo passa a afirmar

Com a base carimbada, `validar_classificacao` inverte o princípio da cautela.
Verificado ao vivo contra banco limpo:

```
sem carimbo:  Dipirona → (silêncio)
com carimbo:  Dipirona → "não consta na base regulatória completa
              (Anexo I Portaria 344/98 consolidada, Atualização nº 101 —
              RDC 1.036/2026, Anvisa Legis 13/09/2026, versão
              RDC 1.036/2026 (Atualização nº 101), 2026-09-13)
              — não-controlado."
```

**Vermelho-antes-de-verde:** removido o carimbo, a afirmação volta a ser
silêncio na mesma chamada. A inversão é gated by design e continua sendo.

## Verificação da transcrição

As listas do Anexo I são numeradas de 1..N sem buraco. O transcritor confere
essa continuidade lista a lista e **recusa emitir o snapshot** se alguma
quebrar — é o que pega item perdido ou linha capturada indevidamente, que
leitura por amostra não pega. Nas nove listas prescritíveis: numeração
contínua.

A ordem alfabética também é conferida, mas como **aviso**: a fonte tem quebras
reais (`9. Bezitramida` antes de `10. Benzetidina`, na A1), então ordem
quebrada é sinal para olhar, não veredito.

Guarda permanente: `backend/tests/unit/test_anexo_i_transcrito.py` — contagens
congeladas por lista, ausência de ligadura tipográfica, ausência de cláusula de
ADENDO capturada como substância, e o conjunto de divergências acima. Uma
divergência nova aparecendo ali é achado regulatório, e o teste manda relatar
neste documento.
