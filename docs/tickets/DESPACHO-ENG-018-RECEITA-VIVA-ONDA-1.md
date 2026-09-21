# DESPACHO-ENG-018 — Receita Viva, onda 1: a folha ao lado da pena

| Campo | Valor |
|---|---|
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (Claude Opus 5) |
| **Data** | 21/09/2026 — martelo do Fabiano: *"simbora com a primeira leva da receita viva"* |
| **Classe** | `module` — altera o `prescritor.html` para **todo uso** (é o produto; NÃO é `local-extension`) |
| **Lei do ticket** | `docs/tickets/DESENHO-RECEITA-VIVA.md` (Kimi + parecer do arquiteto 13/09, RATIFICADO; as 4 marteladas estão embutidas nele) |
| **Referência visual** | `conceitos-prescritor/index.html` + `capturas/` — protótipo navegável, **não é código de produção**; em caso de dúvida, o DESENHO é a normativa |
| **Entrega** | 1 PR de feature, ACs mapeados no corpo (AC × teste × arquivo) |

---

## §1 O defeito, com a evidência

Kimi emitiu receitas reais e mediu: o formulário é um **túnel de coluna única**
(~100 linhas de rolagem entre o primeiro campo e o botão de emitir) e **a receita só
existe depois do ponto de não-retorno** — o documento (`#print-area`) só é preenchido na
tela de sucesso, *após* a emissão. No papel, a receita existe *durante* o ato. CID e
fármacos "somem" na interface (chip roxo de 12px, cards de inputs) — nada se parece com
o receituário que o cidadão recebe.

## §2 O conserto

Split **pena/papel**: formulário à esquerda; à direita, o receituário se escrevendo a
cada tecla, **no mesmo layout do documento final**. Campo vazio = **espaço pontilhado**
na folha (o branco do papel esperando a caneta — sem validação gritando). Cada edição
acende um brilho sutil na região correspondente. **CID como selo** (`CID-10 I10`) sob a
indicação clínica. Fármacos numerados, posologia em itálico. O fecho do arco: **ao
emitir, protocolo + hash carimbam a MESMA folha que estava à vista** — a tela não navega
para um render novo. Mobile (<980px): botão flutuante "📄 Ver a receita".

## §3 A peça central — template ÚNICO, dois alvos (martelada ② do arquiteto)

**UMA função geradora `renderReceituario(estado, modo)`, DOIS alvos de render:**
(a) a folha viva em modo *rascunho* (lacunas pontilhadas); (b) o `#print-area` em modo
*carimbo*. O `#print-area` deixa de ter marcação própria divergente — vira alvo da mesma
função. **Não duplique o template** (a duplicação deliberada proposta originalmente foi
sobreposta pelo arquiteto: dois templates do mesmo documento *vão* derivar, e o "zero
surpresa" vira mentira gradual — a pior espécie; o WYSIWYG só é promessa se W e Y nascem
da mesma função). Sugestão de casa: componente em arquivo próprio (padrão `lente.js` /
`submodulos.js`), mas a decisão de arquivo é sua — o invariante é UMA função, DOIS alvos.

## §4 ACs (todos obrigatórios — §5 do desenho)

1. **A folha se escreve a cada tecla** — nome, idade, CPF/CNI, telefone, endereço,
   complemento, CEP, cidade/UF, indicação, CIDs e cada campo de cada fármaco refletem
   na folha no evento de input (delegação, robusta a limpar/remover/recriar cards, como
   `_initBuscaMedDelegada`).
2. **Lacuna pontilhada** para todo campo vazio que o documento final exibe; nenhum
   placeholder de formulário vaza para a folha como texto definitivo.
3. **Template único por construção** — teste que falha se folha viva e `#print-area`
   divergirem no mesmo estado (W ≡ Y).
4. **O carimbo não troca o layout** — protocolo e hash são lacunas pontilhadas até a
   emissão; ao emitir, carimbam a mesma folha à vista, sem navegação para render novo.
5. **A pena não é engolida pela folha** — IA Farmacêutica, semáforo e sugestões legíveis
   na coluna esquerda em desktop comum (1366px+).
6. **O selo de CID reflete o valor canônico** — o hidden input do typeahead
   (`prescricao-cid-escolhido`), não o texto digitado na indicação.
7. **M-D e A2 sobrevivem** — lock readonly dos campos do paciente em DEMO (cidadão
   canônico) intocado; máscaras numéricas (`data-tipo`) valendo nos campos movidos
   (CPF/CNI sobe para "Identificação do paciente" — martelada ①; o campo é o mesmo
   `pac-chave`, a custódia mora no fluxo, não na seção).
8. **Mobile** — o botão flutuante não cobre o botão de emitir em viewport apertado.
9. **O fluxo físico não muda** — `imprimirDireto()` e a 2ª via continuam saindo pelo
   mesmo documento, agora gerado pela função única: suíte de browser da emissão verde
   **sem adaptação de roteiro**.

## §5 Âncoras no `prescritor.html` (leitura estática de 13/09 — RELOCALIZAR na base atual)

Campos ~609 (paciente) · ~634 (indicação/CID) · ~645 (prescrição terapêutica) · ~653
(modo de emissão); `#print-area` ~1148; `tela-sucesso` ~1122. Os números podem ter
andado — relocalize por conteúdo. Baseie a branch no `origin/main` atualizado.

## §6 Intocáveis

- **ZERO backend**: nenhum endpoint, estado, ledger, custódia, CSV, migração. É
  `module` de frontend.
- **`pdf_prescricao.py` (documento canônico/PDF institucional) FORA de escopo** — o PDF
  continua o mesmo; o que muda é o render HTML da tela.
- **Fluxo físico** (`imprimirDireto`, 2ª via) funcionalmente idêntico — só a origem do
  render muda (função única).
- **Lock M-D e máscaras A2 são ACs permanentes** da casa (junto com as chaves demo).

## §7 Guardas exigidas (vermelho-antes-do-verde)

- **W≡Y** (AC3): estado idêntico → os dois alvos renderizam equivalente; sabotar um
  alvo reprova o teste.
- **Tecla-a-tecla** (AC1) via delegação — remover/recriar card de fármaco não quebra.
- **Carimbo sem troca de layout** (AC4) e **lacunas** (AC2).
- **Mobile** (AC8) e **1366px** (AC5) como testes, não inspeção.
- **M-D/A2** (AC7) + **selo CID canônico** (AC6).
- **Suíte completa de browser** (o `prescritor.html` é página compartilhada — lição
  #253/#255: trocar tela compartilhada é mudança compartilhada) + CI `gates`+`smokes`.

## §8 Rito

1 PR. Corpo com AC × teste × arquivo. O arquiteto verifica de forma independente e emite
RATIFICADO ou BLOQUEADO (com arquivo:linha); **merge só com RATIFICADO + martelo do
Fabiano** — nunca merge próprio. Dúvida vira pergunta escrita no canal, não suposição.

## §9 Fora de escopo (§6 do desenho)

Número do talão na folha (futuro motor regulatório) · posologia em itálico como convite
à sugestão editável (`posologia_sugerida`) · **exame e atestado** (remontagens do padrão,
em ondas próprias).

---

*Despacho lavrado pelo arquiteto (Z) em 21/09/2026. A receita é o objeto sanitário; a
tela passa a tratá-la como tal — não como um formulário que por acaso a produz.*
