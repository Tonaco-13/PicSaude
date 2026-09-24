# DESENHO — Atestado Vivo: a frase que se escreve com o prescritor (UI do prescritor)

| Campo | Valor |
|---|---|
| **Origem** | `DESPACHO-KIMI3-009` (Trilha T — o degenerado monolítico) + **evidência própria de uso real na vitrine (22/09/2026)**: três atestados emitidos de verdade no DEMO, medidas do túnel, capturas e o PDF oficial baixado do servidor |
| **Classe** | `module` — **proposta** (mesma correção de classe que o arquiteto aplicou à Receita Viva: é o produto, não customização institucional). Frontend puro — ledger, custódia, estados, API e `texto_atestado.py` intocados |
| **Régua** | **REGRA ZERO** aplicada ao objeto monolítico: no papel, o atestado existe *durante* o ato — a frase se completa a cada palavra da caneta; na tela atual, ele só nasce depois do ponto de não-retorno |
| **Estado** | 🟡 **PROPOSTA — aguarda visto do arquiteto** (nada de PR, nada de engenheiro) |
| **Executor** | Engenheiro, após visto |

---

## §1 O defeito, com evidência

Kimi emitiu **três atestados reais** na vitrine (`picsaude.com.br/prescritor.html`,
DEMO) em 22/09/2026 — protocolos `488d2eea-…`, `66dfa45a-…` e
`dc97c35d-045e-4202-89d1-65800b02e1a1` (válido até 25/09/2026) — e mediu o túnel:

- **O formulário é um túnel de 18 campos.** O submódulo `#submod-atestado`
  (`prescritor.html:958–1141`) tem 18 inputs/selects/textareas e 14 rótulos em
  1.194 px de altura; o botão `🔏 Emitir atestado digital` (`:1121`) senta a
  1.048 px do topo do submódulo — **1.104 px de rolagem real** em viewport de
  900 px entre o primeiro campo e a emissão.
- **O atestado só existe depois do ponto de não-retorno.** Não existe print-area
  de atestado na página — a `#print-area` que há é da receita (Receita Viva, já
  em produção) e `tem_atestado: false`. O documento oficial nasce no servidor:
  `POST /atestados` (`:5617`) → protocolo → botão "📄 Baixar PDF"
  (`GET /atestados/{proto}/pdf`, `:5720`). Até ali, **nenhum pixel** do layout
  final aparece na tela. O PDF baixado da vitrine está em
  `conceitos-atestado/capturas/vitrine-atestado-oficial.pdf` — é o Y real.
- **O único texto pré-emissão exige um clique e avisa que não é o documento.**
  "Validar atestado" (`:4979`) chama a IA Documental e mostra o corpo numa caixa
  carimbada **"RASCUNHO PARA CONFERÊNCIA — SEM VALIDADE LEGAL"** (`:5133`),
  sem cabeçalho institucional, sem blocos PROFISSIONAL/PACIENTE, sem o título
  "ATESTADO MÉDICO" (proibido no rascunho por decisão do Fabiano — ver
  `test_atestado_espelho.py` §4). É um espelho correto de *texto* que se
  apresenta vestido de "não sou o atestado" — captura `vitrine-04-rascunho-validacao.png`.
- **Onde finalidade, CID e dias "somem":** a finalidade vira um `<select>`
  ("Trabalhista") que no documento entra **flexionado dentro da frase**
  ("Atesto, para fins *trabalhistas*…"); o CID mora num hidden
  (`#atestado-cid`, `:1032`) com chips, e só existe no documento como
  `(CID J11)` no meio do parágrafo; os dias viram o trecho enfático
  "**3 dia(s)**". Nada disso é lido como documento até validar ou emitir.
  *(Achado menor: a busca de CID por "gripe" na vitrine respondeu "Nenhum CID
  encontrado" — a sugestão do typeahead está mais restrita que o vocabulário
  clínico comum; anotado, sem conclusão.)*
- **O lock M-D já vale aqui:** `atestado-paciente`/`atestado-cpf` readonly no
  cidadão canônico (João Demo da Silva · 123.456.789-09) — verificado ao vivo.

**Nuance que distingue este ticket do da receita:** o atestado já tem o espelho
de *texto* fechado no backend — `domain/texto_atestado.py` é fonte única da
frase e `test_atestado_espelho.py` prova rascunho ≡ PDF. O defeito aqui não é
divergência de texto; é **tempo e lugar**: o espelho existe, mas mora atrás de
um clique, vestido de não-documento, enquanto o ato clínico acontece no formulário.

## §2 O conserto: a frase se escrevendo na folha

- **Split pena/papel.** À esquerda, o formulário; à direita, o atestado se
  escrevendo a cada tecla — **no layout do PDF oficial** (cabeçalho PicSaúde +
  régua verde, título por conselho, blocos PROFISSIONAL/PACIENTE com CPF
  mascarado, corpo justificado, período de afastamento, local/data, linha de
  assinatura ICP, rodapé protocolo/hash).
- **A lacuna DENTRO da frase — o gesto característico deste objeto.** O
  atestado não tem itens numerados: tem *uma frase que o CFM manda fechar*. Os
  campos vazios aparecem como lacunas pontilhadas **inline no parágrafo**:
  "Atesto, para fins _finalidade_, que João Demo da Silva esteve sob cuidados
  médicos na data de …, devendo permanecer afastado(a) de suas atividades
  habituais por _nº de dias_ dia(s)…". O prescritor vê a frase se completar —
  e vê exatamente qual palavra falta.
- **Os dois ramos ao vivo.** Trocar o tipo (comparecimento ⇄ afastamento) troca
  a frase na folha na hora — "compareceu a atendimento médico…" ⇄ "esteve sob
  cuidados médicos… por **3 dia(s)**". A folha *ensina* a regra de domínio
  (comparecimento trava dias=0 e abre horas; afastamento o contrário).
- **Tinta por `data-bloco`** (cabeçalho, profissional, paciente, corpo,
  observação, período, local, rodapé — blocos *nomeados*, não lista).
- **O fecho do arco:** ao emitir, protocolo + hash carimbam **a mesma folha à
  vista**; a folha emitida **congela** (emitida não se edita — §1 do CLAUDE.md
  virando comportamento de tela, como na receita). Selo rotacionado ~-8°
  (redação em §3b).
- **Mobile (< 980px):** FAB "📄 Ver o atestado" que recolhe por
  IntersectionObserver quando o botão de emitir entra no viewport.
- **M-D e A2 permanentes:** campos do paciente readonly no cidadão canônico;
  máscaras leves (dias numérico, CID em caixa-alta).

Protótipo navegável verificado em navegador (fluxo inteiro: vazio → preencher →
emitir → carimbo; desktop 1440px e mobile 390px; console limpo):
`conceitos-atestado/index.html` — capturas em `conceitos-atestado/capturas/`,
régua pós-engenheiro em `conceitos-atestado/documento-referencia.pdf`.

## §3 Pontos de decisão (NÃO decididos — caneta do arquiteto/Fabiano)

### (a) O alvo Y do atestado

O atestado **não tem print-area própria** — a impressão física baixa o PDF do
servidor (`imprimirAtestadoFisico`, `:5647`) e o papel oficial nasce no
ReportLab. O W≡Y deste objeto precisa decidir o segundo alvo:

- **Proposta:** criar a print-area do atestado no frontend, render da **mesma
  função geradora** da folha viva — e ancorar a guarda no que já é fonte única:
  comparar o corpo da folha com o `corpo_documento` devolvido por
  `POST /ia/documentos/atestado/validar` para o mesmo estado. O backend já é
  dono da frase (`texto_atestado.py`); a folha monta a *apresentação* da frase
  — a guarda W≡Y do atestado é **folha ≡ fonte única do domínio**, não apenas
  folha ≡ print-area.
- **Pergunta escrita 1:** a print-area nova vira também o caminho do "imprimir
  físico" (hoje 100% servidor), ou segue sendo só o espelho de conferência e o
  papel oficial continua saindo do `pdf_atestado.py`? A segunda opção é a de
  menor atrito e mantém UM renderizador oficial — mas então o Y da guarda é o
  corpo do domínio, não um segundo HTML.
- **Pergunta escrita 2 (conflito aparente a adjudicar):** o rascunho da IA
  Documental é **proibido** de usar o título oficial ("ATESTADO MÉDICO" é marca
  do documento oficial — decisão do Fabiano registrada em
  `test_atestado_espelho.py` §4). A folha viva, pelo precedente adjudicado da
  Receita Viva ("Receituário Médico" desde a primeira tecla), **usa** o título
  oficial — porque ela não é papel de trabalho, é o documento se formando.
  Proponho folha viva com título oficial + manter a proibição no rascunho da
  IA (são artefatos de features diferentes). Confirmar.

### (b) A redação do selo — a pergunta mais afiada dos três objetos

"✓ TRANSMITIDA · CUSTÓDIA AO PACIENTE" traduz para quê no atestado?

- **Fluxo digital** (`POST /atestados`, CPF obrigatório — a própria tela diz
  "obrigatório p/ atestado digital"): **proposta** —
  `✓ EMITIDO · CUSTÓDIA AO PACIENTE`.
- **Fluxo físico** (`POST /atestados/fisica` — a mensagem atual já é honesta:
  *"sem envio digital, sem custódia"*, `:5709`): **proposta** —
  `🖨 IMPRESSO · EMISSÃO FÍSICA — SEM CUSTÓDIA DIGITAL`, espelho do
  `rec-selo-fisica` da receita, com o hash virando a nota "não gerado —
  emissão física" em vez de lacuna que prometeria o que não vem.
- **Pergunta escrita 3:** o atestado **digital** tem custódia ao paciente *de
  fato* hoje? O ato de emitir responde "✓ Atestado emitido · válido até
  25/09/2026", mas eu **não verifiquei** se o objeto aparece na carteira do
  cidadão nem se há registro de custódia (o atestado é monolítico — nem tabela
  de custódia própria eu encontrei citada no fluxo). Se não houver custódia
  digital real, o selo honesto do digital seria apenas `✓ EMITIDO` — e a frase
  "custódia ao paciente" seria promessa, não fato. **Decidir com o fato na
  mesa, não com a metáfora.**

### (c) O que sobe ao núcleo compartilhado × o que fica em `atestado.js`

Adjudicado no parecer do arquiteto: um gerador por documento puxando do núcleo
a lacuna, a tinta por `data-bloco`, o W≡Y e o FAB. Aplicado aqui:

| Sobe ao núcleo (`documento.js` ou equivalente) | Fica em `atestado.js` |
|---|---|
| `MODOS`, contrato `montar(estado, modo)` / `textoDoDocumento` | A frase: os dois ramos (afastamento/comparecimento), a cláusula clínica nos quatro casos |
| Lacuna pontilhada (inline e de-campo) | Título por conselho (ATESTADO MÉDICO/ODONTOLÓGICO, CRM/CRO) |
| Tinta por `data-bloco` | CPF mascarado no documento (`123.***.***.09`) |
| Carimbo que congela o estado emitido | "Período de afastamento até data+dias" |
| FAB + IntersectionObserver sobre o emitir | Mapeamento dos campos do form ↔ estado |
| Escape, data ISO→BR | O selo (redação §3b, por fluxo) |

## §4 O que o degenerado ensina sobre o núcleo

O atestado é a prova de verdade da generalização porque **remove a estrutura
que a receita e o exame compartilham**: não há itens, não há lista, não há
quantidade. E o contrato fechou mesmo assim — porque:

1. **O núcleo não pode assumir "itens".** Os blocos do atestado são regiões
   *nomeadas* (`corpo`, `paciente`, `rodape`…), nenhuma é coleção. Se o núcleo
   de tinta/W≡Y tivesse nascido pensado como "diff de lista de itens", o
   degenerado o quebraria. O contrato certo é por **região nomeada** — a lista
   numerada da receita é o caso particular, não o geral.
2. **A lacuna tem dois modos.** Na receita, a lacuna é de *campo* (um valor por
   região). No atestado, a lacuna é *inline* — mora **dentro da frase**, entre
   palavras definitivas, e precisa fechar a pontuação em volta ("por _nº de
   dias_ dia(s) a partir desta data."). Um núcleo de lacuna que só sabe
   substituir um campo inteiro não serve ao monolítico.
3. **A fonte única do texto já existia — no backend.** Na receita, o W≡Y guarda
   folha ≡ print-area (dois renders do mesmo frontend). No atestado, o texto
   canônico mora em `texto_atestado.py` e há teste que o protege; a guarda
   forte deste objeto é **folha ≡ domínio** (§3a). Lição para o núcleo: o Y
   de cada objeto é onde a verdade daquele documento mora — e isso varia.

## §5 ACs

Espelho dos AC1–AC9 da Receita Viva, adaptados ao monolítico, mais as guardas
próprias:

1. **A folha se escreve a cada tecla** — finalidade, tipo, dias, história
   clínica, CID, data, município, horas, observação, profissional, conselho,
   UF e registro refletem na folha no evento de input/change.
2. **Lacuna pontilhada inline** para todo campo vazio que o documento final
   exibe — dentro da frase, com a pontuação fechando em volta; nenhum
   placeholder de formulário vaza para a folha como texto definitivo.
3. **Template único por construção (W≡Y):** folha viva e o segundo alvo (§3a)
   são renders da mesma função geradora — teste que falha se os dois alvos
   divergirem no mesmo estado (comparação de texto normalizado), nos modos
   rascunho e carimbo.
4. **O carimbo não troca o layout:** protocolo e hash são lacunas pontilhadas
   até a emissão; ao emitir, carimbam a mesma folha à vista, sem navegação; e
   **emitida não se edita** — injetar valor no formulário após a emissão não
   muda a folha.
5. **A pena não é engolida pela folha:** painel do papel ≥ ~40% da largura em
   1366px+ (A6); formulário legível na coluna esquerda.
6. **Os dois ramos fecham como o domínio:** afastamento (dias > 0) e
   comparecimento (dias travado em 0, horas visíveis) produzem exatamente as
   frases de `corpo_atestado()` — incluindo a cláusula clínica nos quatro
   casos (história+CID, só história, só CID, nada) e a observação complementar
   como **acréscimo**, nunca substituição. Guarda: corpo da folha ≡
   `corpo_documento` do endpoint de validação para o mesmo estado.
7. **O conselho muda o documento inteiro:** CFO → título "Atestado
   Odontológico", "cuidados odontológicos", "CRO-UF"; CFM → médico/CRM. E o
   CPF sai mascarado no documento (`123.***.***.09`), como no PDF oficial.
8. **M-D e A2 sobrevivem:** lock readonly de `atestado-paciente`/
   `atestado-cpf` no cidadão canônico intocado; máscaras leves (dias numérico,
   CID caixa-alta) nos campos.
9. **Mobile:** o FAB "📄 Ver o atestado" recolhe quando o botão de emitir entra
   no viewport (IntersectionObserver) — nunca o cobre.
10. **O fluxo físico é honesto:** "Imprimir físico" carimba com o selo de
    emissão física (§3b) e o hash vira a nota "não gerado — emissão física";
    nenhuma promessa "gov.br"/"em breve" em nenhum estado (guarda estática,
    decisão em pé do ENG-020).
11. **O selo pós-emissão** segue a redação decidida em §3b, com rotação ~-8°,
    presente nos dois alvos (é conteúdo do estado emitido, não cromo de modo).

## §6 Fora de escopo

- **Mudanças de API, estados, ledger, custódia ou `texto_atestado.py`** — o
  padrão é frontend puro; a frase canônica continua nascendo no domínio.
- **O renderizador oficial da impressão** (`pdf_atestado.py`) e o endpoint de
  PDF — salvo decisão contrária na pergunta escrita 1.
- **A IA Documental** — a validação estrutural e o rascunho sob demanda
  permanecem; a folha viva convive com eles (e, se um dia os absorver, é
  decisão de outro ticket).
- **A busca de CID da vitrine** (achado §1: "gripe" sem sugestão) — débito do
  typeahead, não deste desenho.

## §7 Referências

| Artefato | Caminho |
|---|---|
| Protótipo navegável (verificado) | `conceitos-atestado/index.html` |
| Capturas do moc | `conceitos-atestado/capturas/01-desktop-pena-e-papel.png` · `02-desktop-emitido-carimbo.png` · `03-mobile-fab.png` |
| Régua pós-engenheiro (Y de referência) | `conceitos-atestado/documento-referencia.pdf` |
| Evidência da vitrine | `conceitos-atestado/capturas/vitrine-01…04-*.png` · `vitrine-atestado-oficial.pdf` (protocolo `dc97c35d-…`) |
| A lei do padrão | `docs/tickets/DESENHO-RECEITA-VIVA.md` |
| Adendo estético normativo A1–A6 | `docs/tickets/DESPACHO-ENG-020-RECEITA-VIVA-POLIMENTO.md` |
| Insumos adjudicados (§5) | `docs/tickets/PARECER-KIMI-RECEITA-VIVA-USO-REAL-2026-09-21.md` |
| O espelho que já existe (texto) | `backend/app/domain/texto_atestado.py` · `backend/tests/test_atestado_espelho.py` |
| O formulário medido | `prescritor.html:958–1141` (form) · `:4979–5350` (validação/rascunho) · `:5564–5760` (emissão/PDF/assinatura) |

---

*Redigido por Kimi (Trilha T do enxame, DESPACHO-KIMI3-009), 22/09/2026. O
atestado é o objeto que não tem onde se esconder: sem itens, sem lista, uma
frase. Se a folha viva fecha a frase diante do prescritor — e o carimbo cai na
mesma folha — o padrão deixou de ser o padrão da receita e virou o padrão da
casa.*
