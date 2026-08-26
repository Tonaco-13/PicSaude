# CONSULTA-UX-001 — percurso do exame: fundir ou separar "Realizar"?

| Campo                      | Valor                                                                                                                                                                                                                                     |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **De**                     | Kimi (consultoria UX, a pedido do Fabiano)                                                                                                                                                                                                |
| **Para**                   | Engenheiro (implementa) — encaminhado pelo Fabiano                                                                                                                                                                                        |
| **Emitido**                | 2026-08-26                                                                                                                                                                                                                                |
| **Método**                 | **Uso real da UI** — demo pública picsaude.com.br, persona demo, via Chromium/Playwright. 3 pedidos de exame emitidos e percorridos ponta a ponta até o Histórico. 39 screenshots em `gui-test-screenshots/consulta-ux-exame-2026-08-26/` |
| **Classificação proposta** | `module` — telas e gatilhos da clínica. **Nenhuma emenda toca máquina de estados, ledger ou custódia**; o único ponto que pode virar `core` é o E2×laudo (item 3.5), sinalizado ao arquiteto                                              |
| **Referências de código**  | `clinica.html` v27 (cópia local de 25/08) — linhas aproximadas, o engenheiro confere no HEAD                                                                                                                                              |

***

## 0. Os 3 percursos executados (evidência)

| Pedido | Perfil                                                              | Protocolo                              | Desfecho observado                                                                                                 |
| ------ | ------------------------------------------------------------------- | -------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **A**  | Walk-in, leitura imediata — glicemia capilar (E1+E2)                | `d5a3ac8a-5f01-4a7b-bd4d-f5fdc850f37e` | Encerrado por ciência do cidadão — **sem laudo**                                                                   |
| **B**  | Agendado — hemograma + TSH                                          | `c86e7ddd-78a4-4cac-b0a5-70e04b6785a6` | Encerrado; laudo `f875e8eb…` com selo **"👁️ Lido em 26/08 19:08"**                                                |
| **C**  | Recusa parcial — eletroforese recusada, hemograma + glicemia seguem | `4847e631-3b47-476c-bd16-a58dbefb3d24` | Laudo `e7f48780…` com ciência; pedido **segue ativo** com a eletroforese de volta ao cidadão (correto pelo modelo) |

***

## 1. Veredito: **FUNDIR — mas o botão passa a dizer o fato**

**Manter o "Realizar" da Recepção como a própria coleta** (um clique, `pendente→coletado`), com três condições:

1. **Renomear para "Coletar agora".** Hoje o rótulo "▶️ Executar agora" mente — quem nomeia o fato real é o `confirm` ("*Registrar a coleta de 1 exame(s) agora, sem agendamento?*"). A verdade não pode morar no diálogo.
2. **Adiar a separação (despacho→Realização→coleta do técnico) até existir papel de técnico no RBAC.** O argumento pró-separar é autoria do evento — mas a demo tem **uma** persona `dispensador` para recepção, coleta, bancada e laudo. Separar hoje adiciona um clique sem adicionar verdade: o evento continuaria carregando o mesmo autor.
3. **Registrar que a separação já existe e é vestigial.** O gesto separado "Registrar coleta" por item existe na Realização (ENG-015 §2, `clinica.html:2789-2796`) — mas o percurso feliz o pula **nos dois fluxos**: o walk-in coleta pela Recepção, o agendado coleta pelo "▶️ Executar" do compromisso. A casa 🧪 Realização não foi visitada em nenhum dos 3 percursos.

**Por que não separar agora:** a coreografia "um clique por casa" já está quebrada em lugares mais graves (a agenda coleta todos os itens num clique; o E2 pula a Bancada). Exigir adjacência estrita só no walk-in é coreografia seletiva. No laboratório pequeno — persona majoritária da vitrine — o clique extra é atrito puro, e a Regra Zero (§7 do AGENTS.md) pesa.

**Gatilho de revisão:** quando o RBAC tiver `tecnico_laboratorio` distinto de `recepcao`, a separação vira óbvia — aí o clique extra carrega informação (autoria do `pedido_coletado`).

***

## 2. Onde a UI contradiz o modelo de casas (não-conformidades, com evidência)

**NC-1 — A casa Realização é fantasma nos fluxos principais** *(pedidos A e B)*
Coleta acontece na Recepção (`executarAgoraDaFila`) ou na Agenda (`realizarAgendamento`, `clinica.html:~2695` — "*Isso registrará a coleta de todos os itens agendados*"). A 🧪 Realização só mostra conteúdo se o pedido for aberto em foco **antes** de qualquer gesto.

**NC-2 — Contadores das casas mudam de significado com o foco** *(A e C)*
Sem pedido em foco: Recepção mostra a fila global (2–4) e as demais casas marcam 0 **mesmo havendo itens coletados/em\_análise na unidade**. Com foco: as mesmas casas mostram itens do pedido. A Bancada sem foco exibe "*Nenhum pedido em foco*" — a casa não é fila, é contexto. A metáfora "fila de casas adjacentes" quebra exatamente nos contadores.

**NC-3 — Quatro nomes para o mesmo fato (coleta)** *(A, B)*
"Executar agora" (card da fila) · "Registrar coleta" (item, Realização) · "▶️ Executar agendado" (card da agenda) · "▶️ Executar" (compromisso em foco). O comentário ENG-015 §2 (`clinica.html:2840-2846`) já admite que são dois botões para o mesmo gesto — na tela viraram quatro.

**NC-4 — "Não realizamos" tem duas granularidades conforme o lugar do clique** *(C)*
No card da fila, `naoRealizamosDaFila` (`clinica.html:2033`) devolve **TODOS** os itens `pendente/agendado` do pedido (loop em `:2046-2076`) — o operador que quiser recusar um item devolve o pedido inteiro. A recusa por item existe, mas só no pedido em foco, aba Recepção ("O QUE EU DECIDO", `:2769-2781`, `devolverItemExame` `:2896`). Mesmo rótulo, dois alcances.

**NC-5 — E2 termina sem laudo** *(A — o achado mais grave)*
"Registrar resultado" (`registrarResultado`, `:3361`) leva `coletado → resultado_disponivel`, mas o gatilho "🔬 Produzir laudo" só existe para itens `em_analise` (`_itensNaBancada`, `:2975`; guarda em `abrirEditorLaudo`, `:2999-3003`). O Pedido A encerrou por ciência do cidadão e entrou em "EXAMES CONCLUÍDOS" **sem nunca ter laudo** — enquanto a carteira prometia "*o laudo é liberado pelo laboratório e aparece aqui*". Sem laudo: sem âncora de faturamento (martelo ENG-014(b)), sem selo "Lido em", sem artefato clínico. A exceção E2 foi concebida como "pular `em_analise`", não como "viver sem laudo" — mas é o que ela produz hoje.

**NC-6 — Ciência em duplicidade, e ciência sem leitura** *(B)*
O card do pedido na carteira oferecia "✓ Confirmo ciência do resultado" **antes** de o laudo ser aberto, ao lado do "📖 Abrir laudo". Isso contraria o martelo ENG-014(a) (*abrir é dar ciência*): o cidadão fecha o ciclo sem ler. E são dois ciclos independentes — a ciência do laudo não encerra o pedido, o cidadão precisa dos dois gestos.

**NC-7 — Fatos clínicos em `prompt()`/`confirm()` nativos, com vazio aceito** *(A, C)*
Motivo da devolução (`:2897`), resumo do resultado (`:3362`), setor da bancada — todos em diálogos nativos. O de resultado aceita **string vazia** (`:3363` só barra `null`): registrei um resultado `""` sem validação, e o item avançou para `resultado_disponivel`.

**NC-8 — O diálogo de ciência promete laudo inexistente no E2** *(A)*
"*O laudo continua na sua carteira*" — no Pedido A não havia laudo. O texto é estático e mente no único percurso em que a afirmação é falsa.

**Registrado como fato, não como defeito:** executei como "realizado" um agendamento marcado para 27/08 09:30 no dia 26/08 às 19h, sem aviso. **É decisão declarada** (ENG-014 PR A: "*sem janela de horário*"). Observado em uso: a vitrine não sinaliza "agendado para outro dia". Deliberação do arquiteto se merece selo visual — não emenda.

***

## 3. O que o modelo de casas não cobre (informação para o arquiteto)

* **3.1 — Pedido em duas casas ao mesmo tempo** *(C)*: após a recusa parcial, a carteira mostrou "🔬 HEMOGRAMA — com 11.222.333/…" ao lado de "ELETROFORESE — COM VOCÊ". O pedido não está numa casa; **os itens estão**. O modelo de casas vale por item — e é o contador por pedido que quebra a metáfora.

* **3.2 — Histórico da unidade nunca fecha o pedido dividido** *(C)*: correto pelo modelo (a eletroforese circula a outro CNPJ), mas a unidade não tem sinalização de "devolvi 1 de 3" na sua casa Histórico — a devolução está no ledger, não na tela.

* **3.3 — E2 sem artefato**: ver NC-5. É a única exceção declarada que produz ciclo fechado sem objeto derivado.

***

## 4. Emenda proposta — PRs e critérios de aceite

**Ordem sugerida:** PR 1 primeiro (é o ciclo quebrado; os demais são cosméticos ou de consistência).

### PR 1 \[module] — E2 gera laudo (o ajuste de maior impacto)

Hoje o percurso mais rápido da casa é o único que termina sem o artefato que ancora ciência e faturamento. Duas opções, **decisão do arquiteto**:

* **(a) Destravar o gatilho:** `_itensNaBancada` (`clinica.html:2975`) passa a aceitar `resultado_disponivel` além de `em_analise`; o editor de laudo cobre o item lido na hora; a etapa 4 de `produzirLiberarLaudo` (`:3213-3221`) vira no-op idempotente para esses itens.

* **(b) Laudo no ato:** `registrarResultado` (`:3361`) encadeia criação→assinar→liberar do laudo unitário (mesmo encadeamento de `produzirLiberarLaudo`, `:3126`), com o RT exigido na mesma tela.

ACs:

* (i) Pedido E2 (coleta→resultado direto) encerra **com laudo liberado** e selo "Lido em" no Histórico;

* (ii) a carteira nunca exibe "o laudo é liberado pelo laboratório e aparece aqui" para um pedido que não pode mais ter laudo;

* (iii) faturamento (critério liberação, ENG-014(b)) alcança o E2;

* (iv) retry não duplica laudo (mesma regra do `laudoDoPedido`, `:2942-2944`).

* ⚠️ Se a opção (b) alterar semântica de evento ou do elo `pedido_item_id`, reclassificar para `core` e abrir revisão central.

### PR 2 \[module] — Um fato, um nome

* Renomear "▶️ Executar agora" (fila) para **"Coletar agora"**; "▶️ Executar"/"▶️ Executar agendado" (agenda) para **"Realizar coleta"**.

* AC: o vocabulário da tela bate 1:1 com o vocabulário do ledger (`pedido_coletado`) — nenhum rótulo diz "executar/realizar" para o ato de coletar.

### PR 3 \[module] — Granularidade honesta do "Não realizamos"

* O gesto do card da fila (`naoRealizamosDaFila`, `:2033`) ganha confirm que **lista os N itens** que serão devolvidos ("Devolver 3 exames ao cidadão: Hemograma, Glicemia, Eletroforese?"), ou abre o pedido em foco na aba Recepção para seleção por item.

* AC: nenhum operador devolve mais itens do que pretende; o rótulo do botão indica o alcance ("Não realizamos estes exames (N)").

### PR 4 \[module] — Contadores das casas com semântica única

* Escolher: (a) contadores sempre globais da unidade (Bancada conta todo material `coletado/em_analise` sob custódia, com ou sem foco), ou (b) sempre do pedido em foco, com rótulo visual explícito ("deste pedido").

* AC: com 2 itens `em_analise` na unidade e nenhum pedido em foco, a casa Bancada não marca 0 (opção a) — ou marca com rótulo inequívoco (opção b).

### PR 5 \[module] — Ciência única, pelo gesto da abertura

* Quando houver laudo liberado e não aberto, o card do pedido **não** exibe "✓ Confirmo ciência do resultado"; a ciência do pedido deriva da abertura do laudo (martelo ENG-014(a) estendido ao pedido).

* O confirm de ciência deixa de prometer laudo quando não há (NC-8) — texto condicional.

* AC: impossível dar ciência de pedido laudado sem abrir o laudo; ciclo do laudo e do pedido fecham juntos ou em sequência explícita.

* ⚠️ Se a derivação mudar regra de transição de estado do pedido, reclassificar para `core`.

### PR 6 [module] — Fatos clínicos fora de `prompt()`/`confirm()`

* Substituir os diálogos nativos por modal próprio com **validação de não-vazio** para: resumo do resultado (`:3362`), motivo da devolução (`:2897` e `:2054`).

* AC: resultado vazio não avança o item; motivo vazio não devolve posse — e o motivo continua obrigatório na trilha.

***

## 5. Notas de UX por percurso

| Percurso           | Nota     | Comentário                                                                                                                                                         |
| ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| A (walk-in)        | **8/10** | Um clique, um confirm, ciclo em \~30 s. Perde pelo rótulo mentiroso (NC-3) e pelo desfecho sem laudo (NC-5)                                                        |
| B (agendado)       | **9/10** | Agenda→presença→executar→bancada→laudo→"Lido em" é a melhor sequência da vitrine. Perde pela ciência em duplicidade (NC-6)                                         |
| C (recusa parcial) | **7/10** | A divisão de custódia por item na carteira é o momento mais forte da sessão; mas a recusa por item está escondida no foco e o homônimo do card devolve tudo (NC-4) |

***

*Consulta respondida com uso real da interface em 26/08/2026. Evidência (39 screenshots) em
`gui-test-screenshots/consulta-ux-exame-2026-08-26/`. Nenhuma linha de código foi alterada —
este documento é proposta; a classificação final e a ordem de execução são do arquiteto.*    
