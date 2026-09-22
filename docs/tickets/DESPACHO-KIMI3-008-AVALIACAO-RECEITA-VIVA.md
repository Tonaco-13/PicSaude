# DESPACHO-KIMI3-008 — Avaliação da Receita Viva EM PRODUÇÃO (pré-onda 2)

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Kimi 3 — análise de uso real |
| **Data** | 21/09/2026 — martelo do Fabiano: *"Vamos pedir a opinião do Kimi antes de passarmos aos outros objetos"* |
| **Objeto** | **Receita Viva onda 1, NO AR** desde 21/09 ~15:02 BRT (PR #268, merge `45a7dae`, deploy Render <2 min) |
| **Entrega** | Parecer com evidência + insumos para a onda 2 |

---

## §1 O que pousou — contexto mínimo

- **Ao vivo**: `https://picsaude.com.br/prescritor.html` — split pena/papel: formulário à
  esquerda; à direita, o receituário se escrevendo a cada tecla no layout do documento
  final. Campo vazio = lacuna pontilhada. Ao emitir, protocolo + hash **carimbam a mesma
  folha à vista** — sem trocar de tela. Indicação clínica + selo de CID **no papel**
  (mantidos por martelo do Fabiano, 21/09: *"concordo manter — W≡Y"*).
- **Lei do ticket**: `docs/tickets/DESENHO-RECEITA-VIVA.md` (agora no repo, entrou com o
  #268). Implementação: PR #268 — `receituario.js` como **gerador único**
  (`renderReceituario(estado, modo)`, dois alvos: `#folha-viva` rascunho /
  `#print-area` carimbo; guarda W≡Y).
- **Seu protótipo de referência**: `conceitos-prescritor/` (+ `capturas/`) — o conceito
  que você validou. Uma das perguntas é justamente: o que prometia × o que pousou.
- Mobile: botão flutuante "Ver a receita" (<980px). Fluxo físico e 2ª via saem pelo
  mesmo documento, agora gerado pela função única.

## §2 O que eu peço — seu método, contra o ar

1. **Emissões reais na vitrine**: digital e física (impressão/2ª via), desktop **e**
   mobile — como no levantamento original, agora contra a produção. A vitrine é DEMO
   com reset diário 04:00 BRT: emissões de teste são seguras e efêmeras.
2. **Veredito de USO para cada um dos 9 ACs** do desenho — não o que o teste prova, o
   que o prescritor sente.
3. **Atritos que teste nenhum pega**: cadência de digitação × repintar da folha, a
   tinta (brilho por edição — percebida sem distrair?), a lacuna convidando a preencher
   (ou gritando?), leitura da folha em uma passada.
4. **A decisão mantida** (indicação + CID no papel impresso) — sua leitura de UX no
   uso real, agora com a receita circulando.
5. **Insumos para a onda 2 (Encaminhamento)** — o item mais valioso: o que do padrão
   é da **FAMÍLIA** (folha viva ao lado da pena, carimbo sem navegação, lacunas,
   template único por objeto) e o que é da **RECEITA** (layout do receituário,
   fármacos numerados, posologia em itálico). Onde o `renderDocumento` de
   Encaminhamento/Atestado/Exames vai querer divergir — e onde divergir seria o
   "mentira gradual" de novo.
6. **Surpresas** — boas e más: o que o conceito não previu e o ar mostrou.

## §3 Limites

- Repo **somente leitura** para você; NÃO toca código, PR, flip, dados curados.
- Entrega: `docs/tickets/PARECER-KIMI-RECEITA-VIVA-ONDA-1-2026-09.md` (formato livre,
  evidência obrigatória: capturas numeradas; se gravar assets,
  `conceitos-prescritor/capturas-producao/`) + **mensagem curta de volta ao
  arquiteto** (o Fabiano cola — ele é o correio).
- Dúvida vira pergunta escrita na sua mensagem, nunca suposição silenciosa.

---

*O conceito nasceu do seu levantamento contra o túnel velho. Agora o ar é o juiz —
e o seu parecer é a porta da onda 2.*
