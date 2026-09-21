## Parecer: o conceito está certo, é a Regra Zero dentro da tela — e eu assino embaixo dele com uma correção de classificação, uma sobreposição deliberação nas quatro questões, e um punhado de ACs que o protótipo ainda não promete

Primeiro, o crédito metodológico: Kimi emitiu receitas reais para achar o defeito, mediu o túnel (~100 linhas entre o primeiro campo e o botão), e nomeou a coisa que me convence — **no papel, a receita existe durante o ato; na nossa tela, ela só nasce depois do ponto de não-retorno**. Isso não é enfeite, é a mesma régua-mestra aplicada à tela que origina o objeto. E o "zero surpresa no pós-emissão" é honesto com o documento canônico: o que o médico vê escrevendo é o que o cidadão recebeu.

**A correção de classificação:** não é `local-extension` — aquele quadrado é *customização institucional* (um cliente, sua UI). A Receita Viva é o **produto**: altera o `prescritor.html` para todo uso, todo mundo. A classe certa é **`module`** (extensão de módulo existente, semântica clínica intacta — as NUNCA do §10 não são tocadas: ledger, custódia, estados, API, tudo intocado; isso o §4 do Kimi acertou em cheio). Mesma revisão, mas o rótulo certo importa na casa que indexa tudo.

**As quatro marteladas:**

1. **CPF sobe para Identificação — CONFIRMADO.** O campo é o mesmo (`pac-chave`, chave de custódia do Ticket 63); a custódia mora no fluxo de emissão, não na seção onde o input senta. Na folha impressa ele já é identificação do paciente — a caneta e o papel passam a morar juntos. **Duas guardas que viram AC:** o lock do M-D (em DEMO os 4 campos do paciente são readonly no cidadão canônico — a folha se preenche sozinha com João, sem edição) e as máscaras/disciplina da A2 seguem valendo.

2. **Template ÚNICO, dois alvos — aqui eu SOBREPONHO a proposta.** Kimi sugere duplicar deliberadamente o template (folha viva como elemento separado do `#print-area`). Não: **uma função geradora do receituário, dois alvos de render** (a folha viva em modo rascunho, com lacunas pontilhadas; o print-area em modo carimbo). A razão é a lição mais repetida da casa — *mesma língua por construção, não por disciplina*: dois templates do mesmo documento **vão** derivar, e quando derivarem o "zero surpresa" vira mentira gradual, que é a pior espécie. O WYSIWYG só é promessa se o W e o Y nascem da mesma função.

3. **Mobile: botão flutuante — CONFIRMADO.** A leitura dele está certa (a última milha do prescritor é desktop), e o botão é reversível. Só uma AC de cuidado: o botão não pode cobrir o botão de emitir em viewport apertado.

4. **Escopo: onda 1 só receita — CONFIRMADO.** E a razão arquitetural soma à dele: a receita tem o template institucional provado (print-area/PDF do documento canônico) — UM espelho para construir e validar. Exame e atestado, quando vierem, são **remontadas** do mesmo padrão, mais baratos por construção. Provar o padrão uma vez, depois multiplicar.

**ACs que acrescento à redação do ticket (o protótipo ainda não promete):**

- **O carimbo não troca o layout**: protocolo e hash são lacunas pontilhadas até a emissão; ao emitir, **carimbam a mesma folha que estava à vista** — a tela não navega para um render novo da receita (senão o "zero surpresa" quebra na primeira emissão).
- **A pena não é engolida pela folha**: painéis de IA Farmacêutica, semáforo e sugestões seguem legíveis na coluna esquerda em desktop comum (1366px+).
- **O selo de CID reflete o valor canônico escolhido** (o hidden input do typeahead), não o texto digitado.
- **M-D e A2 sobrevivem** (lock readonly em DEMO; máscaras numéricas).

**Notas de futuro (fora do escopo, anotadas):** quando um fármaco controlado estiver na receita, a folha um dia mostra o **número do talão** consumido — a ponta visual do motor regulatório; e a posologia em itálico na folha é o convite natural para a sugestão editável da `posologia_sugerida` — hoje chaveada por condição, graças ao ticket que o achado do I50/J44 acabou de gerar.

Com as quatro assim, manda o Kimi redigir o ticket — classe `module`, template único, onda receita. O conceito merece: é a primeira UI que trata a receita como o objeto sanitário que ela é, não como um formulário que por acaso a produz.