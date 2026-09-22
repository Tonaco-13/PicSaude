# DESENHO — Pedido de Exame Vivo: a folha ao lado da pena, remontada para o exame (UI do prescritor)

| Campo | Valor |
|---|---|
| **Origem** | `DESPACHO-KIMI3-009-ENXAME-DEMAIS-OBJETOS.md` (Trilha E) + **evidência própria de uso real** na vitrine (22/09/2026 — dois pedidos emitidos de verdade, medidas e capturas abaixo) |
| **Classe** | `module` — **proposta** (mesma correção que o arquiteto fez na receita): o Pedido de Exame Vivo altera o `prescritor.html` para todo uso; semântica clínica intacta — ledger, custódia, estados e API intocados |
| **Régua** | **REGRA ZERO** aplicada à tela que origina o pedido de exame: no papel, o pedido existe *durante* o ato; na tela atual, ele **nem documento tem** antes do ponto de não-retorno |
| **Estado** | 🟡 **PROPOSTA — aguarda visto do arquiteto** (nada de PR, nada de engenheiro) |
| **Executor** | Engenheiro (após visto) |

---

## §1 O defeito, com evidência

Kimi (Trilha E) emitiu **dois pedidos de exame reais** na vitrine
(`picsaude.com.br/prescritor.html`, 22/09/2026, cidadão canônico João Demo da
Silva · CPF 123.456.789-09, indicação "Lombalgia persistente há 3 meses; anemia
à investigar" + CID M54.5, 2 exames — hemograma completo e radiografia de
coluna lombar):

- Protocolo `6658c65c-1b92-4377-bbaf-31f211878a1e` — "entregue à carteira digital"
- Protocolo `43d5ba91-0f77-404b-bb46-f77c9141de01` — "entregue à carteira digital"

O que o uso real e a leitura estática mediram:

- **O formulário é um túnel de coluna única.** `#form-pedido-exame-main`
  (`prescritor.html:895`) dentro de `#submod-exames` (`:890`): Dados do Paciente
  (`:898`) → Exames Solicitados (`:922`) → Emissão do Pedido (`:930`). Entre o
  primeiro campo (`#exam-pac-nome`, `:900`) e o botão de emitir (`:935`):
  **654 px** de rolagem com o form vazio (1 card de exame) e **1094 px** em uso
  real (2 exames + blocos de IA + chips de CID), viewport 1440×900.
- **O pedido de exame não tem documento nenhum na tela — nem depois de emitir.**
  A receita tinha o `#print-area` preenchido só na tela-sucesso; o exame é pior:
  **não existe print-area nem preview do pedido**. O `#print-area` único da
  página (`:1303`) contém apenas o template do RECEITUÁRIO — o próprio comentário
  de `imprimirPedidoFisico` (`:4667–4670`) confessa: *"como #print-area só contém
  o template do RECEITUÁRIO, a impressão do pedido saía sem documento"*. O
  documento oficial do exame só existe como **PDF gerado no servidor**
  (`baixarPdfExame`, `:4597–4610` → `GET /pedidos-exame/{proto}/pdf`), atrás de
  um botão, depois da emissão. "O documento só existe depois do ponto de
  não-retorno" — no exame, ele sequer aparece na página.
- **O protocolo nasce fora da vista.** Após clicar em Emitir, a mensagem com o
  protocolo (`#pedido-exame-status-msg`, `:893`) aparece **650 px acima** do
  viewport de quem acabou de emitir — quem clica no fim do túnel não vê o
  resultado do próprio gesto. E o formulário é limpo em seguida (`:4573–4585`):
  o prescritor perde de vista tudo o que escreveu.
- **O CID some de verdade — nem viaja no pedido.** O CID escolhido vira um chip
  roxo (captura `vitrine-03`) gravado no hidden `#exam-cid-escolhido` (`:916`,
  escrito pelo typeahead em `:4218`), que é **limpo pós-emissão (`:4584`) sem
  jamais ser lido no payload** (`:4529–4540`): o payload leva
  `indicacao_clinica` mas nenhum CID. Na receita o CID some da interface; no
  exame ele some **do objeto** (acha­do separado, ver §6).
- **Os exames viram cards de inputs + chips azuis.** Cada exame é um
  `.exame-card` (`adicionarExame`, `:4267`) com nome + quantidade; a
  normalização IA rende chips "TUSS 40301079 · hematologia" (captura
  `vitrine-03`). Nada se parece com o pedido que o cidadão apresenta ao
  laboratório.
- **M-D já vale no exame** (confirmado ao vivo): `#exam-pac-nome` e
  `#exam-pac-cpf` readonly, travados no cidadão canônico
  (`_retravarCidadaoDemo('exam-pac-nome','exam-pac-cpf')`, `:4579`).
- **O Y de hoje** (régua real, baixada da vitrine): o PDF A4 do servidor
  (`conceitos-exame/pdf-vitrine-atual-6658c65c.pdf`) — cabeçalho institucional
  "PEDIDO DE EXAMES — ROTINA", blocos PRESCRITOR / PACIENTE (CPF mascarado) /
  INDICAÇÃO CLÍNICA / EXAMES SOLICITADOS numerados / IDENTIFICAÇÃO DO DOCUMENTO
  (protocolo, emissão, validade 30 dias, prioridade, status, hash SHA-256),
  aviso de validade e linha de assinatura.

Capturas da evidência: `conceitos-exame/capturas/vitrine-01-tunel-form.png`
(o túnel), `vitrine-03-pre-emissao-preenchido.png` (chips de CID/TUSS),
`vitrine-04-protocolo-pos-emissao.png` (o protocolo fora da vista),
`vitrine-02-documento-pos-emissao.png` (a tela pós-emissão — sem documento).

## §2 O conserto: a folha ao lado da pena — remontagem do padrão

O padrão Receita Viva inteiro, na anatomia do pedido de exame (que é a do PDF
real acima — **não** a do receituário):

- **Split pena/papel.** À esquerda, o formulário do exame; à direita, o pedido
  se escrevendo a cada tecla — **no layout do documento oficial do pedido**:
  cabeçalho com protocolo e **selo de prioridade** (ROTINA/URGENTE/URGENTÍSSIMO),
  blocos PRESCRITOR e PACIENTE, INDICAÇÃO CLÍNICA com **CID como selo**
  (`CID-10 M54.5`), **EXAMES SOLICITADOS numerados** (nome em caixa-alta feita
  *na função* — o W≡Y compara texto — com TUSS/SIGTAP/categoria e preparo em
  itálico quando padronizados), IDENTIFICAÇÃO DO DOCUMENTO (datas, prioridade,
  hash), aviso de validade e assinatura.
- **Lacunas pontilhadas** para todo campo vazio que o documento exibe
  (protocolo, datas, hash, exames, indicação).
- **Tinta** por `data-bloco` (cabecalho · paciente · indicacao · exames ·
  identificacao) — a guarda aponta a região, não o documento.
- **O fecho do arco:** ao emitir, protocolo + hash + datas **carimbam a mesma
  folha à vista**, com **selo de custódia rotacionado ~-8°** (redação proposta
  em §3-b) — sem navegação, sem render novo. Emitida, a folha **congela**:
  o estado emitido é o estado final.
- **Mobile (<980px):** FAB "📄 Ver o pedido" que se recolhe quando o botão de
  emitir entra em cena (IntersectionObserver) — nunca cobre o emitir.
- **M-D/A2 preservados:** paciente readonly no cidadão canônico; máscaras leves
  (`data-tipo`). **Nenhuma promessa gov.br/em-breve.**
- **Estética A1–A6 do ENG-020:** palco creme `#F7F5EF`, serif no documento /
  sans na UI, papel com borda quente `#D9D2C0` + sombra, lacuna legível, painel
  do papel ≥ ~40% em 1366px+.
- **W≡Y no espírito já no moc:** uma função geradora
  (`PedidoExame.montar(alvo, estado, modo)` + `textoDoDocumento` + `MODOS`)
  alimenta a folha viva (rascunho) e o `#print-area` do exame (carimbo) — **um
  template, dois alvos**. Verificado ao vivo no moc:
  `textoDoDocumento('folha-viva') === textoDoDocumento('print-area')` → `true`
  no rascunho e no carimbo (console do moc, sem erros JS).

Protótipo navegável verificado em navegador (desktop 1440 e mobile 390, fluxo
vazio→preencher→emitir→carimbo completo): `conceitos-exame/index.html`
(capturas `01`–`03` em `conceitos-exame/capturas/`). **Régua pós-engenheiro:**
`conceitos-exame/documento-referencia.pdf` (1 página A4, gerada do próprio moc
em modo carimbo).

## §3 Pontos de decisão — PROPOSTAS, não decididas (caneta do arquiteto/Fabiano)

### (a) O alvo Y do exame — onde o documento final mora no cliente

**Mapeado no uso real:** o exame **não tem** print-area nem impressão própria
no cliente hoje. O documento oficial é o PDF do servidor
(`domain/pdf_pedido_exame.py`, Ticket 17); o fluxo físico já é "síncrono por
natureza" — baixa o PDF do servidor para imprimir (`:4661–4670`), justamente
porque o `#print-area` da página é da receita. Duas leituras possíveis:

- **Proposta da trilha (preferida):** o Y espelho é o **PDF institucional do
  exame** (já mapeado e reproduzido no moc/`documento-referencia.pdf`); o exame
  ganha um **print-area próprio** (ex.: `#print-area-exame`) alimentado pela
  mesma função geradora, e o fluxo físico passa a ter opção de impressão local
  idêntica à folha — sem tirar o caminho servidor (que é o oficial e deve
  seguir). O `#print-area` singular de hoje (`:1303`) vira um alvo por objeto,
  ou um print-area multi-objeto chaveado pelo submódulo ativo — **a escolha de
  mecanismo é do arquiteto**.
- **Alternativa conservadora:** o exame segue sem print-area local; a folha
  viva é só espelho de tela (rascunho), e o carimbo/impressão continuam
  saindo do PDF do servidor. O W≡Y então se mede contra o PDF de referência,
  não contra um segundo alvo em runtime.

### (b) A redação do selo de custódia do exame

**Proposta:** **"✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE"** — espelho da receita,
no masculino do objeto. Justificativa na arquitetura: a emissão digital do
exame abre custódia `prescritor → paciente` (`entrega_carteira_digital`,
`docs/ARQUITETURA_EXAMES.md` §Custódia) — quem nasce detendo o pedido é o
cidadão, que o leva ao prestador (J.7: custódia é posse; o selo nomeia a posse
que nasce, não o destino). Alternativa considerada e **não** proposta:
"TRANSMITIDO · RUMO AO PRESTADOR" — o prestador só entra na cadeia quando o
cidadão entrega; o selo anteciparia um fato que ainda não ocorreu (a lição do
`pedido_agendado` fantasma). Palavra final do Fabiano.

### (c) O que sobe ao núcleo compartilhado vs. o que fica em `pedidoexame.js`

**Proposta (alinhada ao parecer adjudicado — "duas anatomias numa função só é
a dupla posse pela porta dos fundos"):** `receituario.js` **não** vira
`documento.js` parametrizado. Cada documento tem seu gerador com sua anatomia.

Sobem ao **núcleo compartilhado** (extração de `receituario.js`, semântica
intacta): `lacuna`/`esc`, a **tinta por `data-bloco`**, o contrato **W≡Y**
(`montar`/`textoDoDocumento`/`MODOS`), o **FAB mobile** com recolhimento por
IntersectionObserver, e as máscaras leves.

Ficam em **`pedidoexame.js`**: os blocos anatômicos do pedido (cabeçalho com
selo de prioridade, prescritor, paciente, indicação+CID, exames numerados com
TUSS/SIGTAP/preparo, identificação do documento, aviso de validade), o **selo
de custódia do exame** (§3-b) e a guarda W≡Y **própria do objeto**
(`PedidoExame.textoDoDocumento` + teste que falha se os dois alvos divergirem).

## §5 ACs

1. **A folha se escreve a cada tecla** — prioridade, indicação, CIDs escolhidos
   e cada campo de cada exame (nome, quantidade, nome padronizado aceito)
   refletem na folha no evento de input, com delegação robusta a
   adicionar/remover/recriar cards (o padrão de `adicionarExame`/`removerExame`).
2. **Lacuna pontilhada** para todo campo vazio que o documento final exibe
   (protocolo, data de emissão, validade, hash, exames, indicação); nenhum
   placeholder de formulário vaza para a folha como texto definitivo.
3. **W≡Y por construção, com guarda própria do objeto:** folha viva e
   print-area do exame são renders da mesma função geradora; teste de browser
   falha se `PedidoExame.textoDoDocumento('folha-viva') !==
   PedidoExame.textoDoDocumento(alvo-carimbo)` no mesmo estado — **inclusive no
   estado emitido**.
4. **O carimbo não troca o layout:** protocolo, datas e hash são lacunas
   pontilhadas até a emissão; ao emitir, carimbam **a mesma folha à vista**,
   sem navegar; **pedido emitido não se edita** — o estado emitido congela a
   folha (edição posterior no formulário não altera o documento).
5. **A pena não é engolida pela folha:** os blocos de normalização IA por exame
   e as sugestões de CID seguem legíveis na coluna esquerda em desktop comum
   (1366px+); o painel do papel ocupa ≥ ~40% da largura (A6).
6. **O selo de CID reflete o valor canônico escolhido** — o hidden
   `exam-cid-escolhido`, não o texto digitado na indicação.
7. **M-D e A2 sobrevivem:** `exam-pac-nome`/`exam-pac-cpf` readonly no cidadão
   canônico em DEMO (lock intocado); máscaras `data-tipo` seguem valendo.
8. **Mobile:** o FAB "📄 Ver o pedido" aparece em <980px e **nunca cobre o
   botão de emitir** (recolhimento por IntersectionObserver sobre o emitir).
9. **O fluxo físico não muda:** `imprimirPedidoFisico()` continua síncrono via
   servidor (PDF oficial gerado no backend, falha legível offline); nenhum
   endpoint, estado, evento de ledger ou regra de custódia é tocado — o padrão
   é **frontend puro**.
10. **Selo de custódia pós-emissão (A4):** após emitir, a folha recebe o selo
    verde rotacionado ~-8° com a redação decidida em §3-b; o selo é conteúdo do
    **estado emitido** (nasce no carimbo, vale nos dois alvos; no rascunho não
    existe).

## §6 Fora de escopo

- **Qualquer mudança de API, estados, ledger ou custódia** — o padrão é
  frontend puro; `pedidos_exame.status`, `pedido_exame_eventos` e
  `pedido_exame_custodia` intocados.
- **O CID do exame não viaja no payload** (achado §1: `exam-cid-escolhido`
  escrito e limpo sem nunca ser lido). É defeito de **contrato** — registrar
  como ticket próprio (pergunta escrita ao arquiteto abaixo), não consertar
  nesta onda.
- **Preparo editável na folha** — o equivalente do débito `posologia_sugerida`
  da receita: o preparo do exame (jejum etc.) entra na folha como informativo
  da normalização; sugestão editável fica para onda futura.
- **Agendamento, coleta, bancada, custódia parcial (J.10)** — intocados; a
  folha termina na emissão, onde o padrão mora.
- **Número de talão/regulatório de exames** — não se aplica hoje; se um dia
  houver motor regulatório de exames, a ponta visual é a folha (mesma nota da
  receita).

## §7 Referências

| Artefato | Caminho |
|---|---|
| Protótipo navegável (verificado, desktop+mobile) | `conceitos-exame/index.html` |
| Capturas do moc | `conceitos-exame/capturas/01-desktop-pena-e-papel.png` · `02-desktop-emitido-carimbo.png` · `03-mobile-fab.png` |
| **PDF de referência (régua pós-engenheiro)** | `conceitos-exame/documento-referencia.pdf` |
| PDF real da vitrine (o Y de hoje, protocolo `6658c65c…`) | `conceitos-exame/pdf-vitrine-atual-6658c65c.pdf` |
| Capturas da evidência de uso real | `conceitos-exame/capturas/vitrine-01…04-*.png` |
| A lei do padrão | `docs/tickets/DESENHO-RECEITA-VIVA.md` |
| Adendo estético normativo (A1–A6) | `docs/tickets/DESPACHO-ENG-020-RECEITA-VIVA-POLIMENTO.md` |
| Insumos adjudicados (gerador por documento + núcleo) | `docs/tickets/PARECER-KIMI-RECEITA-VIVA-USO-REAL-2026-09-21.md` §5 |
| Arquitetura do objeto (estados, custódia, J.7/J.10) | `docs/ARQUITETURA_EXAMES.md` |

## Perguntas escritas ao arquiteto (dúvidas, não suposições)

1. **Print-area:** o exame ganha `#print-area-exame` próprio, ou o `#print-area`
   singular vira multi-objeto chaveado pelo submódulo? (§3-a — mecanismo é seu.)
2. **CID no payload:** o `exam-cid-escolhido` nunca ser lido em
   `emitirPedidoExame` é intenção do MVP ou defeito a abrir como ticket
   separado (contrato/backend, fora desta onda)?
3. **Selo:** "✓ TRANSMITIDO · CUSTÓDIA AO PACIENTE" (proposta) ou outra
   redação? (§3-b — palavra do Fabiano.)

---

*Rascunho redigido por Kimi (Trilha E do DESPACHO-KIMI3-009) com evidência de
uso real em 22/09/2026. A receita provou a mecânica; o exame — o quase-isomorfo
— é onde o padrão prova que é uma família, não um acaso bonito. Estado:
PROPOSTA — aguarda visto do arquiteto antes de qualquer despacho ao engenheiro.*
