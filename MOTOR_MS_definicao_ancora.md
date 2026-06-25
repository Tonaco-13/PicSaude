# Motor de Busca Clínica (Instância MS) — Texto-âncora do conceito

> Definição canônica para o contrato, o disclaimer da interface e o briefing do code/MS.
> Classe: `core` — **contrato de domínio**. Não edita ledger, custódia, assinatura
> nem máquina de estados; mas **vincula todos os tickets futuros do motor** — define
> o que ele pode e não pode fazer. Por isso exige ratificação central (Chefe), como
> qualquer decisão de núcleo, ainda que não toque em código de núcleo.
> Status: **PROPOSTA — pendente ratificação**. Ao ser ratificado, torna-se
> `docs/MOTOR_BUSCA_CLINICA.md`.

## O que o motor é

O motor é um **índice navegável dos protocolos clínicos públicos do SUS**. Dado
um CID ou uma indicação, ele filtra e organiza os medicamentos exatamente como
as fontes oficiais (PCDT/CONITEC, RENAME, ANVISA/CMED) os associam e
hierarquizam àquela condição: **lista completa, na ordem que o documento
estabelece, com a procedência visível em cada item**. Ele não avalia, não
pontua e não recomenda. Onde a fonte não hierarquiza, o motor não hierarquiza.

Analogia: a RENAME e os PCDTs tornados pesquisáveis por CID — um
bulário/formulário navegável, não um conselheiro.

## O que o motor NÃO é

- Não é recomendação terapêutica nem apoio que substitua o juízo do prescritor.
- Não usa IA, modelo de linguagem ou inferência. É **determinístico**.
- Não pontua nem ordena por evidência apreciada por ele. A apreciação de
  evidência é da CONITEC/MS; o motor só reflete a ordem que elas publicaram.
- Não esconde opções. A lista é sempre completa; o que muda é **ordem e
  agrupamento**, ambos vindos da fonte.

## A régua da linha citável

Para cada destaque, agrupamento ou ordem exibidos na tela, vale uma única
pergunta:

> **"Consigo apontar a linha do documento oficial que justifica esta posição?"**

- **Sim** → apresentação fiel (permitido).
- **Não** → recomendação do sistema (proibido no MVP).
- **Fonte não estabelece ordem** → ordem neutra (alfabética), sem destaque de
  "melhor".

Toda priorização tem uma fonte citável atrás dela, ou não existe.
`linha_terapia` / `ordem_fonte` é **dado capturado do documento (com página),
nunca inferido**.

## Fontes

**Permitidas (espinha oficial do SUS):** PCDT/CONITEC, RENAME, ANVISA/CMED,
portarias e atos oficiais do MS e suas agências.

**Fallback, só onde não existe PCDT:** diretrizes de sociedades reconhecidas
(ex.: SBC, SOBED), **explicitamente rotuladas como tal**. São um degrau abaixo
do protocolo oficial e nunca sobrepõem um protocolo do SUS quando este existe —
o motor serve a dispensação no SUS, então a ordem do SUS prevalece.

**Proibidas como base de ordenação/seleção:** PubMed, bases de evidência,
ensaios clínicos e **qualquer apreciação de evidência feita pelo próprio
sistema**. Ranqueamento por evidência apreciada = Fase F, `core`,
pós-regulatório.

## Posologia — referência, não default

A posologia segue a mesma régua da linha citável, mas com uma diferença que
**inverte o default**: o semáforo se exibe; a posologia se **cita ao lado do
campo**, e quem escreve a dose é o prescritor.

Por que é mais estrita que o semáforo:

- A resposta do semáforo é completa no nível populacional; a da posologia não é
  — "dose usual" não é a dose do paciente sem ajuste renal/hepático/idade/peso.
- Campo pré-preenchido é aceito por default. Pré-popular a dose é o nudge mais
  forte possível, no campo onde "aceito sem ler" atinge o paciente.
- A posologia aceita entra no documento assinado (ICP-Brasil) — vira conteúdo
  do objeto canônico, não metadado consultivo como o semáforo.
- No MVP não há ajuste (renal/hepático/pediátrico = posologia v2, Fase F). Sem o
  dado para ajustar, não se pré-preenche: dose não ajustada num paciente renal é
  dano que o sistema causou.

**Comportamento MVP:**

- **Mostrar** a posologia usual como referência **ao lado** do campo, sourced
  (bula ANVISA / PCDT) + a fronteira populacional explícita ("adulto, função
  normal — bula X").
- **Vazio** quando ambíguo ou ausente; nunca texto incerto.
- O prescritor **transcreve/confirma por ato consciente** — a dose entra na
  prescrição por decisão dele, não por default do sistema.

**Proibido no MVP:** pré-preencher o campo como default editável; qualquer dose
calculada ou ajustada pelo sistema (renal/peso/idade); posologia de fonte
não-oficial.

**Granularidade:** posologia é **por apresentação** (concentração/forma), não
por ativo. Um CSV chaveado por ativo é simplificação documentada que quebra em
fármacos com múltiplas concentrações/formas (ex.: insulinas) — amarrar a linha à
apresentação + à bula que a justifica.

**Validação:** mesmo regime do semáforo — conformidade à fonte + currency. O
validador atesta que a linha reflete a posologia oficial e que o recorte
populacional foi capturado; não julga "é a dose certa".

## Uma linha para o disclaimer da interface

> "Esta tela reflete os protocolos clínicos públicos do SUS (PCDT, RENAME,
> ANVISA) para o CID selecionado, na ordem definida por essas fontes. Não
> constitui recomendação de tratamento. A decisão é do prescritor."

## Por que isso protege o projeto

Toda ordem influencia — não há apresentação neutra. A defesa não é "não
influenciamos", é **"a influência exibida é a do próprio Ministério, citada e
verificável"**. Transparência de procedência converte *nudge* em reflexo
honesto, e mantém o enquadramento regulatório na faixa informacional de menor
risco (a confirmar pelo jurídico — RDC 751/2022 + 657/2022).
