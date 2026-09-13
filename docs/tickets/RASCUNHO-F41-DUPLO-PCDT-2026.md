# RASCUNHO F41 DUPLO — semáforo dos Transtornos Ansiosos (para revisão e assinatura)

| Campo | Valor |
|---|---|
| **Origem** | Despacho do arquiteto 13/09 ("limpar a mesa"), item 3 |
| **Rascunhista** | Engenheiro — **nunca flipa** `validado`/`exaustivo` |
| **Assinante** | **Fabiano** |
| **Estado** | 🟡 **RASCUNHO — SEM FLIP.** Este item **não tem autorização**: a caneta de 13/09 cobriu J44 e I50, não F41 |
| **Fonte estagiada** | **RENAME 2024** (`fontes-oficiais/rename/rename-2024.pdf`, 254 p., sha256 no MANIFEST) |
| **Segunda fonte** | ⛔ **NÃO EXISTE AINDA** — ver §0 |

---

## §0 A levantura é DUPLA por desenho, e hoje só um lado é possível

O padrão da casa cruza **duas** fontes: o protocolo clínico (o que a medicina
recomenda) e a **RENAME** (o que o SUS entrega). O F32 teve as duas — AMB/ABP
Depressão 2009 + Guia Fiocruz APS, ambas estagiadas.

**Para transtornos ansiosos não há nenhuma das duas:**

1. **Não existe PCDT da CONITEC para ansiedade.** Varri o corpus inteiro
   (`fontes-oficiais/pcdt/corpus-conitec-2026-08-30/`, 242 PDFs): há
   esquizoafetivo, bipolar tipo I e TDAH — **nenhum de transtornos ansiosos**.
   O despacho pedia "padrão corpus-PCDT"; o corpus não tem o protocolo, então
   o padrão aplicável é o do **F32** (diretriz + RENAME), não o do J44/I50.
2. **Não há diretriz de ansiedade estagiada.** O guia Fiocruz do corpus é
   *depressão unipolar* (40 p.; "ansiedade" aparece 1 vez, "transtorno de
   ansiedade" nenhuma). A AMB/ABP estagiada também é de depressão.

**Consequência honesta:** o lado RENAME deste rascunho está **completo e
verificável** (§2). O lado clínico **não pode ser levantado sem uma fonte
estagiada**, e não se inventa elenco de memória. É o mesmo muro que o §1.1 do
DESENHO-TALAO-DIGITAL-SNCR descreveu para a Portaria 344: o gesto que falta é
humano — escolher e estagiar a diretriz.

---

## §1 O achado principal: duas das cinco seeds citam RENAME que não as contém

As 5 rows de F41 hoje (`semaforo_seed_v1_2026-06`, `exaustivo=false`) declaram
`fonte = RENAME/PCDT (APS)`. Varredura das 254 páginas da RENAME 2024:

| Seed atual | RENAME 2024 | Situação |
|---|---|---|
| clonazepam | **p. 94, 130** | ✅ consta |
| diazepam | **p. 98, 133** | ✅ consta |
| fluoxetina | **p. 95, 131** | ✅ consta |
| **sertralina** | — | ❌ **NÃO CONSTA — nenhuma página** |
| **escitalopram** | — | ❌ **NÃO CONSTA — nenhuma página** |

**É exatamente o mesmo defeito que o F32 encontrou** (§1 do
`RASCUNHO-F32-DEPRESSAO-2026.md`): a semeadura de junho citou "RENAME/PCDT
(APS)" em bloco, e sertralina/escitalopram não estão na RENAME. As duas seeds
já foram excomungadas do F32 por este motivo, e continuam de pé no F41 — a
mesma citação falsa, na mesma base, sobrevivendo em outra condição.

---

## §2 O que a RENAME 2024 tem, entre os candidatos de ansiedade

Varredura mecânica, com página. **Consta:**

| Princípio ativo | RENAME 2024 (págs.) | Comentário |
|---|---|---|
| clonazepam | 94, 130 | benzodiazepínico, seed atual |
| diazepam | 98, 133 | benzodiazepínico, seed atual |
| clobazam | 94, 182 | benzodiazepínico |
| midazolam | 101, 141 | benzodiazepínico (uso hospitalar/sedação) |
| fluoxetina | 95, 131 | ISRS, seed atual |
| amitriptilina | 94, 130 | tricíclico |
| nortriptilina | 97, 132 | tricíclico |
| clomipramina | 95, 130 | tricíclico (clássico em TOC) |
| bupropiona | 95, 147 | componente Estratégico (nota do F32) |
| propranolol | 43, 133 | betabloqueador (ansiedade de desempenho) |

**Não consta** (nenhuma página): sertralina · escitalopram · alprazolam ·
bromazepam · lorazepam · buspirona · hidroxizina · paroxetina · citalopram ·
venlafaxina · duloxetina · imipramina · mirtazapina.

> ⚠️ **Estar na RENAME não é indicação para ansiedade.** Midazolam consta e
> obviamente não é fármaco de F41 ambulatorial; clomipramina consta e é
> clássica em TOC, que é outro capítulo do CID. **Quem separa o que é elenco
> de F41 do que é apenas "disponível no SUS" é a diretriz clínica — a fonte
> que falta.** Por isso §2 é levantamento, não proposta de elenco.

---

## §3 O que este rascunho NÃO faz

- **Não propõe elenco.** Propor elenco com meia fonte seria o "close enough"
  que a casa recusa — e num CID de saúde mental, onde benzodiazepínico tem
  risco de dependência, o erro não é cosmético.
- **Não flipa `exaustivo`.** As 5 seeds seguem `exaustivo=false`: fora do
  elenco continua NEUTRO, não amarelo. Nenhuma linha de CSV muda nesta PR.
- **Não corrige as duas citações falsas.** Retirar sertralina/escitalopram do
  F41 é ato de curadoria e precisa da caneta — mesmo tendo a varredura pronta
  e o precedente do F32 apontando para lá.

---

## §4 Pontos de decisão (só o Fabiano)

1. **A segunda fonte.** Qual diretriz de transtornos ansiosos estagiar? O
   precedente F32 usou AMB/ABP + Fiocruz APS. Sem ela, o F41 não fecha.
2. **As duas citações falsas** (sertralina, escitalopram): seguem o destino do
   F32 (🟡 com causa "não consta da RENAME 2024") ou há razão para tratar
   ansiedade diferente de depressão? Recomendo o mesmo destino — a citação é
   falsa do mesmo jeito nos dois CIDs.
3. **Escopo do CID.** F41 é "outros transtornos ansiosos"; TOC (F42) e fobias
   (F40) são capítulos vizinhos. Clomipramina puxa para TOC. Vale decidir se o
   elenco cobre só F41 ou a família.
4. Versão na assinatura, se e quando houver: `semaforo_f41_exaustiva_v1_2026-XX`.

---

*Lavrado em 13/09/2026 pelo engenheiro, a pedido do despacho do arquiteto.
Varredura mecânica da RENAME 2024 (254 p., pypdf) e do corpus CONITEC (242
PDFs). Nenhuma linha de dado curado foi tocada.*
