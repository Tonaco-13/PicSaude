# DESENHO — Encaminhamento Vivo: a Receita Viva na terceira circulação (UI do prescritor)

| Campo | Valor |
|---|---|
| **Origem** | `DESPACHO-KIMI3-009-ENXAME-DEMAIS-OBJETOS.md` (Trilha N — Encaminhamento) + **evidência própria de uso real na vitrine** (22/09/2026, §1) |
| **Classe** | `module` — **PROPOSTA** (mesma correção que o arquiteto aplicou à Receita Viva: é o produto, não customização institucional). Semântica clínica intacta — ledger, custódia, estados e API intocados |
| **Régua** | **REGRA ZERO** aplicada à tela que origina o objeto: no papel, o encaminhamento existe *durante* o ato; na tela atual, ele só nasce um passo antes do ponto de não-retorno — e morre um passo depois |
| **Estado** | 🟡 **PROPOSTA — aguarda visto do arquiteto.** Nada de PR, nada de engenheiro antes do visto |
| **Executor** | Engenheiro (após visto) |
| **Referência normativa** | `conceitos-encaminhamento/` (moc navegável + PDF de referência + capturas) — a estética segue o adendo A1–A6 do DESPACHO-ENG-020 |

---

## §1 O defeito, com evidência do uso real

Emiti **um encaminhamento de verdade** na vitrine pública
(`picsaude.com.br/prescritor.html`, DEMO, 22/09/2026, via navegador
automatizado): paciente canônico João Demo da Silva (123.456.789-09),
finalidade *Avaliação especializada*, especialidade **CARDIOLOGIA** pelo
typeahead CBO, CNS destino `980 0011 1222 3335`, justificativa de 164
caracteres. **Protocolo emitido: `12e1bf3f-d47c-4054-a66b-b3ec0e7455fd`.**

Medições e achados, todos reproduzíveis:

- **O formulário é um túnel de coluna única** — 7 campos visíveis em 3 seções
  (Paciente, Destino, Conteúdo clínico), **852 px de altura de formulário,
  725 px de rolagem** entre o primeiro campo (`enc-pac-nome`) e o botão
  "Revisar documento →". O form vive em `#form-enc-main`
  (`prescritor.html:1173-1253`), dentro do `#submod-encaminhamento`
  (`prescritor.html:1151`).
- **O documento só existe numa janela estreita entre dois apagões.** O
  `.enc-doc` (`#enc-doc-corpo`, `prescritor.html:1259`; CSS em
  `prescritor.html:429-432`) só é montado pela `revisarEncaminhamento()`
  (`prescritor.html:1848-1880`, documento em `1867-1876`) **depois do submit**
  — e é escondido de novo logo após a emissão (`emitirEncaminhamento()`:
  `form.reset()` em 1921, `voltarAoFormularioEnc()` em 1923, troca de aba em
  1926). Antes da revisão, nada; depois da emissão, **uma linha de lista**
  ("João Demo da Silva · CARDIOLOGIA · protocolo · Emitido · com o cidadão").
  O encaminhamento tem menos existência visual que a receita: nem tela de
  sucesso ele tem.
- **Encaminhamento não tem impressão própria hoje.** Verificado em runtime e
  por leitura estática: `#print-area` (`prescritor.html:~1299`) é da receita;
  dentro do submódulo de encaminhamento não há print-area, botão de imprimir
  ou PDF (`enc_tem_print_proprio: false`). O documento é montado, confirmado,
  hasheado — e nunca impresso.
- **O destino "some" na interface.** Após a escolha no typeahead, a
  especialidade vira texto morto no input de busca + valor oculto
  (`enc-especialidade`); o código CBO (`2251-20`) que estava no chip do
  painel desaparece da tela. O CNS do destinatário é uma sequência de 15
  dígitos sem máscara. O *destinatário* — a pessoa para quem o documento
  inteiro aponta — não tem nenhum lugar na interface que o trate como tal.

Capturas da evidência (vitrine, prefixo `vitrine-`):
`conceitos-encaminhamento/capturas/vitrine-04-formulario-preenchido.png` (o
túnel), `vitrine-03-typeahead-especialidade.png` (o painel CBO),
`vitrine-05-revisao-documento.png` (o documento na janela estreita),
`vitrine-06-apos-emissao.png` (o apagão pós-emissão).

## §2 O conserto: a folha ao lado da pena — anatomia própria

O padrão Receita Viva inteiro, remontado na anatomia do encaminhamento
(que **não** é a da receita — template próprio, §3.c):

- **Split pena/papel.** À esquerda, o formulário; à direita, o
  encaminhamento se escrevendo a cada tecla — no layout do documento final.
- **O DESTINATÁRIO em destaque é a assinatura deste papel.** Caixa azul de
  dois fios com a especialidade em corpo maior, a finalidade e o CNS do
  executor — o documento inteiro aponta para ele, e a folha diz isso à
  primeira vista. É o equivalente deste objeto ao "fármacos numerados" da
  receita.
- **A frase que define o documento é gerada e visível** ("Encaminho o(a)
  paciente X para *finalidade* em *ESPECIALIDADE*.") — já nasce na folha
  durante a escrita, não só na revisão (§5 do DESENHO-ENCAMINHAMENTO-UX:
  cabeçalho gerado, fora da caixa de texto).
- **Itens numerados** com procedimento + motivo (a especialidade é a do
  destinatário) — a anatomia real de `encaminhamento_itens`
  (`especialidade` NOT NULL, `procedimento`, `motivo`;
  `backend/app/models/encaminhamento_item.py:20-22`; o endpoint já aceita os
  três campos — `routers/encaminhamentos.py:69-70,573-577`).
- **Lacunas pontilhadas** em todo campo vazio que o documento final exibe;
  **tinta por `data-bloco`** a cada edição.
- **O fecho do arco:** ao emitir, protocolo + hash **carimbam a mesma folha
  que estava à vista** — sem navegação, sem render novo. E a folha **congela**:
  emitido não se edita (a imutabilidade do §1 do AGENTS.md virando
  comportamento de tela).
- **Selo de custódia rotacionado ~-8°** pós-emissão (redação em §3.b).
- **Mobile (< 980px):** FAB "📄 Ver o encaminhamento", que se recolhe por
  IntersectionObserver quando o botão de emitir está à vista — nunca o cobre.
- **Estética A1–A6 obrigatória** (palco creme `#F7F5EF`; serif no documento /
  sans na UI; papel com borda quente `#D9D2C0` + sombra; lacuna legível;
  painel do papel ≥ 40% em 1366px+).

Protótipo navegável verificado em navegador: `conceitos-encaminhamento/index.html`
(W≡Y verificado ao vivo: folha ≡ print-area → `true`; folha congelada
pós-emissão → `true`; FAB visível/recolhido → ok; zero erros JS; desktop
1440px e mobile 390px). Capturas: `conceitos-encaminhamento/capturas/`
(`01-desktop-pena-e-papel.png`, `02-desktop-emitido-carimbo.png`,
`03-mobile-fab.png`). **Régua pós-engenheiro:**
`conceitos-encaminhamento/documento-referencia.pdf` — o papel canônico do
encaminhamento emitido, gerado do próprio moc.

## §3 PONTOS DE DECISÃO — PROPOSTAS, não decisões (caneta do arquiteto/Fabiano)

### (a) O alvo Y — qual é o documento final espelho do encaminhamento

**O que mapeei no uso real:** o encaminhamento **não tem** print-area,
impressão ou PDF próprios hoje. O único "documento" é o `.enc-doc` da
revisão — transitório, montado só entre o submit e a confirmação, sem
protocolo e sem hash. O documento canônico de verdade vive no backend:
`_documento_canonico_encaminhamento()` (`routers/encaminhamentos.py:197-256`,
v2 com finalidade) — é ele que o SHA-256 congela, e é sobre ele que o
destinatário um dia dará ciência. O DESENHO-ENCAMINHAMENTO-UX §10 coloca
"PDF/QR público do encaminhamento" **fora do escopo** do MVP.

**PROPOSTA:** o Y é o **documento canônico v2 promovido a papel** — a folha
do moc (`documento-referencia.pdf` como régua visual), que espelha um a um os
campos do hash (protocolo, origem, destino, paciente, especialidade, CID,
justificativa, itens, finalidade). A onda cria o alvo de impressão que o
objeto nunca teve, a partir do gerador único — sem endpoint novo, sem PDF/QR
público (que segue fora de escopo).

**Pergunta escrita ao arquiteto:** confirma que o Y é o documento canônico v2
no layout do moc? Ou o "documento final" do encaminhamento deve esperar o
PDF/QR público (fora de escopo hoje), e esta onda entrega só a folha viva +
carimbo, sem alvo de impressão? — no moc entreguei os dois, mas o ticket
precisa dizer qual é o compromisso.

### (b) A redação do selo de custódia

**PROPOSTA:** **"✓ EMITIDO · CUSTÓDIA AO CIDADÃO"**. Justificativa: na
emissão digital do encaminhamento, a custódia **abre no cidadão** — motivo
canônico `emissao_digital` (AGENTS.md, tabela de gestos do encaminhamento;
DESENHO-ENCAMINHAMENTO-UX §1a). É a tradução exata do "✓ TRANSMITIDA ·
CUSTÓDIA AO PACIENTE" da receita para o objeto em que o portador ativo é o
próprio cidadão desde o primeiro instante — e combina com o selo da lista
("com o cidadão", verificado ao vivo pós-emissão).

**Variante:** "EMITIDO · COM O CIDADÃO" (espelho literal do selo da aba
Encaminhados). Mantive "custódia ao cidadão" por nomear o fato jurídico do
ledger, não a etiqueta da lista. **Pergunta:** qual redação leva o martelo?

### (c) O que sobe ao núcleo compartilhado vs o que fica em `encaminhamento.js`

Seguindo o adjudicado no parecer pós-Kimi (§5: um gerador por documento +
núcleo compartilhado) e a frase-lei do §5 do meu parecer de uso real —
*"duas anatomias numa função só é a dupla posse pela porta dos fundos"*:

**PROPOSTA — sobe ao núcleo compartilhado** (extração do que `receituario.js`
já tem host-agnostic):

- lacuna pontilhada (vocabulary-driven: campo vazio que o documento exibe);
- tinta por `data-bloco` (diff por região);
- W≡Y — o contrato `montar(estado, modo)` / `textoDoDocumento` / `MODOS`;
- carimbo de protocolo+hash na mesma folha e o **congelamento do estado
  emitido**;
- FAB mobile com IntersectionObserver.

**PROPOSTA — fica em `encaminhamento.js`** (a anatomia deste objeto):

- o layout do papel: emitente-origem, paciente, **DESTINATÁRIO em destaque**,
  frase gerada, selo de CID, justificativa, itens
  especialidade/procedimento/motivo;
- os catálogos (CBO 21 especialidades, mini-CID, finalidades — já versionados
  em `catalogos-encaminhamento.js`);
- a máscara de CNS;
- a redação do selo de custódia deste objeto (§3.b).

**Pergunta:** o núcleo vira um `documento-nucleo.js` novo (do qual
`receituario.js` e `encaminhamento.js` puxam), ou `receituario.js` doa por
extração nesta onda? Minha leitura segue a do parecer: gerador por documento,
núcleo magro — mas o nome e a casa do núcleo são do arquiteto.

## §5 ACs (numerados, testáveis)

1. **A folha se escreve a cada tecla** — finalidade (incl. "outra"→texto),
   especialidade (escolha no typeahead e escape OUTRA→texto), CNS do
   destinatário, CID (painel e escape), justificativa e cada
   procedimento/motivo de cada item refletem na folha no evento de input,
   com delegação robusta a adicionar/remover itens.
2. **Lacuna pontilhada legível** (A5) para todo campo vazio que o documento
   final exibe; nenhum placeholder de formulário vaza para a folha como
   texto definitivo; a lacuna tem contraste suficiente para ler-se como
   convite (referência: `capturas/01-desktop-pena-e-papel.png`).
3. **W≡Y com guarda própria do objeto:** folha viva e alvo de impressão são
   renders da mesma função geradora (`montar(estado, modo)`); teste que
   falha se os dois alvos divergirem no mesmo estado — no estado emitido,
   `textoDoDocumento(folha) === textoDoDocumento(print)` → `true` (o gancho
   `__weqy()` do moc é o esboço da guarda).
4. **O carimbo não troca o layout:** protocolo e hash são lacunas/"— gerado
   na emissão —" até a emissão; ao emitir, carimbam **a mesma folha à
   vista**, sem navegar; **o documento emitido congela** — edição posterior
   no formulário não altera a folha (verificado ao vivo no moc).
5. **A pena não é engolida pela folha:** painel do papel ≥ ~40% da largura
   em 1366px+ (A6); typeaheads de especialidade/CID, sugestões e botões
   seguem legíveis na coluna esquerda.
6. **A especialidade reflete o valor canônico escolhido** — o hidden do
   typeahead (o `titulo`, conforme a decisão já tomada de que o valor que
   viaja é o nome), não o texto digitado; o escape OUTRA e o CID "não
   listado" seguem funcionais e caem na folha como texto digitado.
7. **M-D e A2 sobrevivem:** lock readonly dos campos do paciente no cidadão
   canônico (João Demo da Silva / 123.456.789-09) intocado; máscaras leves
   (CPF, CNS `000 0000 0000 0000`, CID em caixa-alta) seguem valendo.
8. **Mobile:** FAB "📄 Ver o encaminhamento" visível em < 980px e **nunca
   cobre o botão de emitir** — recolhimento por IntersectionObserver sobre o
   botão (verificado ao vivo no moc, 390px).
9. **O fluxo de emissão não muda:** revisão → confirmar → `POST
   /encaminhamentos` com o mesmo payload; a folha emitida e o selo convivem
   com a aba Encaminhados; nenhuma mudança de API, estados, ledger ou
   custódia. Suítes existentes do ENG-016 verdes sem adaptação de roteiro.
10. **Estética A1–A6** (adendo ENG-020): palco creme `#F7F5EF`; documento em
    serif / UI em sans; papel com borda quente `#D9D2C0` + sombra; selo de
    custódia verde rotacionado ~-8° **só no estado emitido** (conteúdo do
    estado, não cromo de modo — W≡Y intocado); nenhuma promessa
    gov.br/"em breve" no HTML.

## §6 Fora de escopo (declarado)

- **Mudanças de API, estados, ledger e custódia** — o padrão é frontend puro
  (o endpoint já aceita `procedimento`/`motivo` por item; nenhum campo novo
  no backend).
- **PDF/QR público do encaminhamento** — fora de escopo do MVP por decisão
  já tomada (DESENHO-ENCAMINHAMENTO-UX §10); o alvo de impressão desta onda
  é o da §3.a, se o arquiteto o ratificar.
- **Contrarreferência** — objeto derivado com custódia própria (Fork 3); sua
  "vida" em tela é onda própria.
- **Sugestão de destino** ("já atenderam este paciente") — componente
  existente, fora desta onda; convive com a folha, não entra no papel.
- **Regulação** — `em_regulacao` segue badge honesto sem engine.
- **Fluxo físico de encaminhamento** — não existe no objeto (estados do
  AGENTS.md); nada a preservar aqui, ao contrário da receita.

## §7 Referências

| Artefato | Caminho |
|---|---|
| Moc navegável | `conceitos-encaminhamento/index.html` |
| PDF de referência (régua pós-engenheiro) | `conceitos-encaminhamento/documento-referencia.pdf` |
| Capturas do moc | `conceitos-encaminhamento/capturas/01-…`, `02-…`, `03-…` |
| Capturas da vitrine (evidência §1) | `conceitos-encaminhamento/capturas/vitrine-*.png` |
| A lei do padrão | `docs/tickets/DESENHO-RECEITA-VIVA.md` |
| Adendo estético normativo A1–A6 | `docs/tickets/DESPACHO-ENG-020-RECEITA-VIVA-POLIMENTO.md` |
| Insumos adjudicados (gerador por documento + núcleo; W≡Y com guarda própria) | `docs/tickets/PARECER-KIMI-RECEITA-VIVA-USO-REAL-2026-09-21.md` §5 |
| Anatomia e leis de UX do objeto | `docs/tickets/DESENHO-ENCAMINHAMENTO-UX.md` · `docs/tickets/DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md` · seção Encaminhamento do `AGENTS.md` |
| Âncoras de código | `prescritor.html:1151,1173-1253,1259,1848-1880,1888-1932` · `backend/app/models/encaminhamento_item.py:20-22` · `backend/app/routers/encaminhamentos.py:69-70,197-256,573-577` |

---

*PROPOSTA redigida por Kimi (Trilha N do enxame KIMI3-009), 22/09/2026, com
evidência de uso real (protocolo `12e1bf3f-d47c-4054-a66b-b3ec0e7455fd`).
O encaminhamento é o objeto cujo papel inteiro aponta para alguém — e hoje
esse alguém não aparece em lugar nenhum da tela. A folha ao lado da pena o
devolve: o destinatário em destaque, a cada tecla, antes do ponto de
não-retorno. Aguarda visto do arquiteto — os três pontos de decisão do §3
são da caneta dele e do Fabiano.*
