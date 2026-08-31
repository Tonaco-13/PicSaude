# Mensagem ao Arquiteto — entrega do conceito de abertura

> Data: 2026-08-30 · De: Fabiano (com Kimi, conversa de design)
> Assunto: **o conceito de abertura está entregue. Vou disparar a mudança.**

---

Arquiteto,

as duas passadas chegaram, foram lidas uma a uma e aplicadas no arquivo.
O conceito que você viu por leitura estática agora carrega o seu parecer de
domínio e o parecer de engenharia que você ratificou. Este é o livro-caixa
da entrega.

## 1. O seu parecer de domínio — aplicado

| Ponto | Estado |
|---|---|
| Trilho com palavras-arco em prosa (`emitido` · `com o cidadão` · `com quem executa` · `entregue`) e chip mono no card com o estado real de cada máquina (`emitido` / `emitido` / `em_custodia` / `liberado`) | Aplicado. Cada objeto percorre o mesmo trilho falando a própria língua. Validado ao longo da viagem no navegador |
| Card "Rastreável": "auditável por quem tem papel na jornada" | Aplicado |
| Lente sem a linha "6 gestos no ledger" | Removida. O `/public` não devolve contagem, a página não promete |
| "1 disciplina de ledger. Todo gesto é fato imutável." | Aplicado. As 8 famílias, uma disciplina |
| Fecho da jornada com os 7 objetos (entram Contrarreferência e Circulação diagnóstica) | Aplicado. Casa com a lente |
| "0 papel obrigatório" | Intocado. A palavra "obrigatório" segue blindada |
| Fontes self-hosted, zero Google Fonts | Aplicado (woff2 subset latin em `conceitos-landing/fonts/`, com `font-display: swap` e preload) |
| Pílulas no celular | Não somem mais: rolam na horizontal, com o Entrar sempre visível |

**Ficou com a casa, como combinado:** o docstring de `publico.py` (linha 19)
que promete "itens (nome + dose)". Conserto `docs` do seu lado. Não tocamos
em nada do código de produção.

## 2. O parecer de engenharia ratificado por você — aplicado

**O relógio único.** O `@keyframes viajar` saiu do CSS. Uma única tabela no
JS (`quadros`: percentual do ciclo × posição) é agora o único dono do tempo e
do espaço: posição do card, sinais verdes e troca de objeto derivam dela, no
mesmo `requestAnimationFrame`. A classe de dívida que você nomeou (dois
relógios sincronizados por disciplina do autor) virou impossível por
construção. O bônus que você previu se cumpriu: sem JS, tudo parado na
estação 1, do card ao rótulo.

**Contraste.** `--ink-faint` de `#8a94a6` (2.81:1) para `#5f6b7d` (4.96:1,
calculado). A hierarquia visual se manteve. Verificamos antes que a variável
só vive sobre fundos claros.

**O 320px foi renderizado de verdade** (emulador por iframe, porque o
headless tem largura mínima de 500px). Três achados na conferência:

1. O card agora tem a posição clampeada dentro do trilho. Nada nasce cortado,
   em nenhuma largura. O `overflow:hidden` não tem mais o que disfarçar.
2. Um bug que nenhuma das duas revisões viu: a regra que escondia as
   palavras-arco abaixo de 640px perdia por especificidade (`.rail-label span`
   contra `.rail-label .arco`) e nunca havia funcionado.
3. Corrigida a especificidade, os quatro nomes de estação não cabiam em
   280px sem se atropelar. A solução: no celular, o nome da estação viaja com
   o objeto. Só a estação onde o card está aparece, com a palavra-arco dela.
   No desktop, nada mudou.

**As baratas, todas dentro:** preload das fontes, rAF pausado com aba oculta
ou hero fora da tela (`document.hidden` + IntersectionObserver no
`.objeto-stage`), e `:focus-visible` com anel em tudo que é clicável. A lente
ganhou anel verde sobre o azul-noite, depois do `outline:none` na cascata.

**Sua errata, registrada em reciprocidade:** a resiliência sem-JS que você
elogiou em bloco agora é verdade plena. Sem JS, o card não desliza mais com o
texto congelado. As duas passadas se afiaram mutuamente também aqui.

## 3. Estado e artefatos

O conceito está como o seu veredito combinado pediu: as três correções que o
distanciavam de pronto-de-verdade estão dentro.

| Artefato | Caminho |
|---|---|
| Conceito (HTML puro, autocontido) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/index.html` |
| Fontes self-hosted | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/fonts/` |
| PDF renderizado (8 páginas, A4) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/picsaude-conceito-abertura.pdf` |
| Prompts das duas revisões | `PROMPT-ARQUITETO.md` e `PROMPT-ENGENHEIRO.md` na mesma pasta |

## 4. A decisão aberta é minha e está sendo disparada

A convivência da abertura com a fachada de serviço atual (o portal some?
vira `/entrar`?) ficou registrada como decisão do Fabiano. Estou disparando a
mudança. Quando o flip acontecer, a disciplina de paridade de imagem do repo
se aplica, e a lição dos assets 404 não se repete.

A casa viu o conceito pelas duas lentes que importam. A porta está à altura
do picsaude.com.br.

Obrigado pelo cuidado com o domínio.

— Fabiano
