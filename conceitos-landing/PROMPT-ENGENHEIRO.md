# Prompt para o Engenheiro — análise estática do conceito de abertura

> Data: 2026-08-30 · Autor da exploração: Fabiano + Kimi (conversa de design)
> Natureza: **exploração conceitual fora do código de produção.**
> Nada aqui é pedido de implementação. É pedido de **opinião fundamentada**
> com olhar de engenharia de front-end. O arquiteto já deu parecer de domínio
> (aplicado); agora a pergunta é outra: **isso está bem construído?**

---

## 1. O que você deve analisar

| Artefato | Caminho |
|---|---|
| Conceito de landing (HTML puro, autocontido, ~770 linhas) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/index.html` |
| Fontes self-hosted (woff2, subset latin) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/fonts/` |
| PDF renderizado da página (8 páginas, A4) | `/Volumes/fabianotonaco/Developer/PicSaude_Dev/conceitos-landing/picsaude-conceito-abertura.pdf` |
| Parecer do arquiteto (já aplicado) | ver seção 2 abaixo |

**Modo de trabalho pedido:** análise estática e somente leitura. Não altere
nenhum arquivo — nem no conceito, nem (sob nenhuma hipótese) no código de
produção. Se quiser ver no ar, `npm run dev` dentro de `conceitos-landing/`
sobe um preview estático (vite), mas isso é opcional — a leitura do HTML basta.

---

## 2. Contexto: o que já foi decidido e o que o arquiteto já revisou

O conceito propõe a página pública de abertura do PicSaúde. Decisões de design
já marteladas pelo Fabiano (não estão em discussão): manchete *"O cuidado
precisa de trilhos."*, selo *"Infraestrutura de Custódia Sanitária Digital"*,
estações como pílulas no header (Consultório · Farmácia · Carteira Cidadã ·
Clínica / Laboratório) ao lado do Entrar, reveals estilo Apple a partir de
"A jornada do objeto", assinatura *"PicSaúde. Feito para o SUS."*, frases
curtas, zero travessões.

O arquiteto fez análise estática de **fidelidade ao domínio** e pediu correções,
já aplicadas:

1. **Estados no trilho:** as estações exibem palavras-arco em prosa
   (`emitido` · `com o cidadão` · `com quem executa` · `entregue`); o chip mono
   com o estado real da máquina (`emitido`/`em_custodia`/`liberado`) vive no
   card, trocando junto com o objeto. Fundamento: cada `states*.py` é contrato
   por objeto (AGENTS.md §5a).
2. **Lente:** removida a linha "6 gestos no ledger" (o `/public` não devolve
   contagem de eventos).
3. **Faixa de números:** "1 disciplina de ledger" (são 8 famílias de ledger; a
   disciplina é uma só). "7 tipos de objeto" e "0 papel obrigatório" confirmados.
4. **Fecho da jornada:** lista os 7 objetos, incluindo Contrarreferência e
   Circulação diagnóstica.
5. **Fontes:** self-hosted, sem Google Fonts (página SUS-facing).
6. **Mobile:** as pílulas de estação rolam na horizontal em vez de sumir.

Sua análise **não precisa repetir o domínio**. O que pedimos é o olhar que
falta: engenharia de front-end.

---

## 3. O que pedimos da sua análise

### 3.1 Qualidade do HTML/CSS/JS
- Semântica e acessibilidade: hierarquia de headings, landmarks, `aria-*`,
  contraste, navegação por teclado, foco visível. A página se sustenta para
  leitor de tela? (É para o SUS: acessibilidade não é detalhe, é requisito.)
- O CSS é sustentável? ~300 linhas de custom properties e seções nomeadas.
  Algo que vai virar dívida se crescer?

### 3.2 Performance e peso
- A página é um único HTML + 3 woff2 (~200 KB total) + 1 PNG de logo. Zero
  dependências, zero frameworks. Esse minimalismo é o certo para uma abertura
  pública SUS-facing (3G, aparelho modesto), ou esconde custo?
- O trilho roda num loop `requestAnimationFrame` permanente
  (`performance.now() % 16000`). Vale pausar quando a aba está oculta
  (`document.hidden`) ou quando o hero sai da viewport (IntersectionObserver)?
  Custo real de bateria/CPU ou preciosismo?
- As fontes usam `font-display: swap` com fallbacks de sistema. O flash de
  troca é aceitável? Falta `preload`?

### 3.3 Resiliência
- Sem JS: todo o conteúdo nasce visível (reveals são camada extra via
  `body.js-reveal`). O trilho, sem JS, fica parado no primeiro objeto. Correto?
- `prefers-reduced-motion`: desliga trilho e reveals. Suficiente?
- Se um woff2 falhar, o fallback degrada com dignidade?

### 3.4 Responsividade
- Breakpoints: 980px (pílulas viram trilho rolável), e os layouts internos usam
  `clamp()`/`grid` fluidos. Há viewport real onde quebra (tablet em retrato,
  celular 320px, desktop ultralargo)?
- A máscara de fade na rolagem das pílulas (`mask-image`) é elegante ou
  truque frágil? O `Entrar` fixo fora do scroll está certo?

### 3.5 Se um dia virar produção
Hipotético, sem compromisso: o que este arquivo precisaria ganhar para virar a
abertura real do picsaude.com.br? Pense em: SEO e meta tags (OG/Twitter),
CSP, SRI se um dia houver CDN, estratégia de i18n (pt-BR só?), build/deploy,
e como conviveria com o `index.html` atual da raiz (fachada de serviço).
Liste como "o dia que virar real, não esquecer de…".

### 3.6 Opinião livre do engenheiro
O que está errado, frágil ou feio no código. O que você faria diferente. Se
implementaria assim ou de outro jeito — e por quê.

---

## 4. Formato da resposta pedida

Relatório curto, em português, um veredito por seção (3.1 a 3.6):
**OK / OK COM RESSALVA / PROBLEMA**, seguido de justificativa com referência
à linha ou bloco do `index.html`. Fechar com um parecer de uma frase:
*"este conceito está / não está pronto para o dia em que virar real."*
