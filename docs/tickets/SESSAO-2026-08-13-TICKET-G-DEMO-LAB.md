# Sessão 2026-08-13 — Engenheiro: Ticket G (UI de laudo estruturado — pedra angular)

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator deste registro |
| **Arquiteto** | Z AI — autor do ticket |
| **Escopo** | Ticket G (`module`, frontend) — depende de C ✅ e F ✅ |
| **Branch** | `docs/sessoes-11-12-agosto` — **sem commit**, trabalho na árvore |
| **Estado** | Implementado; verde no gate unitário, de integração e de navegador |

---

## §1 Resumo em uma frase

O `clinica.html` deixou de registrar um **texto solto de resultado** e passou a produzir um **laudo
estruturado** que é assinado em nome do RT e vai à **custódia do cidadão** — com a ciência dele
refluindo para a tela do laboratório.

---

## §2 O que entrou

### G1 — o gatilho é do PEDIDO, não do item

`🔬 Produzir laudo (N exames)` aparece no rodapé do card "Exames Solicitados" **quando há ≥1 item em
`em_analise`**. Um laudo cobre o pedido; botão por item sugeriria o contrário.

O critério não é cosmético — é o mesmo do backend, e é ele que **resolve o risco de laudo duplicado**
declarado no ticket: concluído o ciclo, os itens saem de `em_analise` e o gatilho **desaparece
sozinho**. Não precisou de flag nem de consulta extra.

### G2 — editor inline

Pré-preenchido com os itens na bancada. Por exame: `nome_exame` e códigos (TUSS/SIGTAP) em leitura,
mais três entradas do operador — **resultado**, **conclusão** (select com as quatro conclusões
válidas do backend) e **valor de referência**.

Bloco do **Responsável Técnico** em destaque, com a frase que o ticket pede que não se perca: *"A
unidade produz em nome dele — o CNPJ fica registrado no ledger como produtor, nunca como autor."*
CNS e nome vêm pré-preenchidos de `DEMO.prescritor` (config.js) — **fonte única de identidades**,
nenhum literal novo na tela, guarda `test_guardrail_identidades_demo` intocada. Campos seguem
editáveis: em produção o RT é o profissional do laboratório, não o prescritor do seed.

### G3 — `produzirLiberarLaudo()`

Encadeia `POST /laudos` → `assinar` → `liberar` → `/resultado` por item → `recarregarPedido`.

Três decisões de robustez além da letra do ticket:

1. **Retry não recria o laudo.** `laudoDoPedido` guarda o protocolo; se a etapa 4 falhar, o novo
   clique **reaproveita** o laudo em vez de emitir outro. O ticket aceitava o duplicado como
   compensação — mas laudo é objeto sanitário, não rascunho, e duplicá-lo por falha de rede seria
   sujeira permanente no ledger.
2. **`assinar`/`liberar` toleram 422 no retry** (significa "já assinado"/"já liberado") e seguem
   adiante, em vez de travar o fluxo num estado meio-feito.
3. **O erro nomeia a etapa.** "Falha ao criar o laudo" ≠ "Falha ao liberar o laudo" — sem isso o
   operador vê `422` e não sabe se o laudo existe.

O corpo de `liberar` vai **vazio de propósito**: o CNPJ vem do JWT (Ticket C). Posse provada, não
declarada.

### G4 — acompanhamento da ciência

Painel com as três etapas (`Liberado → Ciência do cidadão → Encerrado`), a alcançada em verde, mais
o botão de PDF do laudo. Reatualiza a cada `recarregarPedido()` — é por ali que a ciência do cidadão
chega à tela do laboratório.

### G5 — não implementado (opcional no ticket)

O botão de laudo no header foi descartado: o ticket condiciona a "só se ajudar a narrativa", e o
painel já oferece o PDF no contexto certo. Um segundo caminho para a mesma coisa no header seria
ruído.

### Higiene de estado

`_limparEstadoLaudo()` roda em `buscarPedido` e `novaBusca`. Sem isso, trocar de pedido deixaria o
painel do laudo anterior na tela e — pior — o retry reaproveitaria **um laudo de outro paciente**.

---

## §3 Bloqueio encontrado e resolvido — o pedido não sabe quem é o paciente

**O ticket assume** (G3) que `cpf_paciente`/`nome_paciente` saem "do pedido". **Não saem.**
`GET /pedidos-exame/{proto}` devolve as colunas de `pedidos_exame`, que tem `paciente_id` — **não o
CPF nem o nome**. E o `POST /laudos` exige os dois, além de conferir que o paciente do laudo é o do
pedido vinculado (`vinculo_pedido_invalido`).

Evidência de que é lacuna do backend, e não desenho: o `renderizarPedido` **já procura esses campos**
(`p.paciente_nome || p.paciente?.nome`, `p.cpf_paciente || p.paciente?.cpf`) desde antes desta
sessão. A tela foi escrita esperando dados que o endpoint nunca mandou — hoje ela mostra
"Paciente: —" quando um pedido é aberto.

**Como resolvi, sem tocar no backend:** a identidade vem da **fila**
(`/dispensadores/fila-exames`), que já a expõe. É correto **por construção** neste fluxo: para
laudar é preciso ter item em `em_analise`, e item na bancada é acionável (Ticket B) — logo o pedido
está na fila. Se ainda assim não estiver, a função **falha com voz** ("abra o pedido pela Fila de
Exames") em vez de mandar CPF vazio e colher um 422 obscuro.

> **Para o arquiteto decidir (não implementei):** adicionar `paciente_cpf`, `paciente_nome`,
> `prescritor_cns` e `prescritor_nome` ao `GET /pedidos-exame/{proto}` é ~4 linhas, é
> retrocompatível (só acrescenta campos), não introduz vazamento (o ownership já é validado antes do
> retorno, e o mesmo ator já enxerga itens e eventos) — e **consertaria de quebra o
> "Paciente: —"** do painel de detalhes. Deixei fora porque é mudança de contrato de backend num
> ticket declarado frontend-only. Candidato a ticket próprio.

---

## §4 Arquivos

| Arquivo | Δ | Papel |
|---|---|---|
| `clinica.html` | +~330 / −6 | markup do card, CSS do editor/painel, gatilho, editor, orquestração, painel de ciência, higiene de estado |
| `backend/tests/unit/test_frontend_acao_sem_silencio.py` | +7 / −2 | registro de `produzirLiberarLaudo` (19 → 20) |
| `backend/tests/browser/test_laudo_clinica_cidadao.py` | novo, 268 linhas | 3 smokes do arco completo |

`cidadao.html` **não foi tocado**, conforme o contrato da demo.

---

## §5 Gates

| Gate | Resultado |
|---|---|
| Smoke novo do Ticket G | **3 passed** |
| `tests/browser` (completo) | **60 passed** (era 57 após F) |
| `tests/unit` | **414 passed** (era 413 após F) |
| Integração (seleção `-k` da CI) | **326 passed** — sem regressão |

### O que o smoke da pedra angular prova

`test_clinica_produz_laudo_cidadao_recebe_e_da_ciencia` percorre **duas telas em dois contextos de
navegador**: a clínica produz e libera; o cidadão recebe, vê e dá ciência; a ciência reflui. As
asserções que valem por si:

- **O conteúdo estruturado viaja:** `conclusao == "normal"` chega na carteira do cidadão — não só um
  resumo solto.
- **O autor é o RT, não a unidade:** `autor_nome == "Dra. Demo Maria Souza"` mesmo com o operador
  autenticado como `dispensador` (CNPJ). É o Ticket C visto pela tela.
- Os outros dois casos travam as fronteiras: sem item na bancada **não há gatilho**; cancelar o
  editor **não cria objeto sanitário**.

### Dois defeitos de teste que eu mesmo introduzi e corrigi

Registro porque relatório que só mostra verde não ajuda ninguém:

1. Li a carteira do cidadão como lista; o endpoint devolve `{disponiveis, historico}`. Era bug do
   meu teste, não do produto — o laudo estava lá.
2. Assertei "a lista não tem mais 'Dar ciência'", mas o **seed** traz outro laudo pendente. Escopei
   ao card do protocolo em questão. A asserção larga mediria o vizinho.

---

## §6 Estado

- Nada commitado. Trabalho na árvore de `docs/sessoes-11-12-agosto`.
- **Próximo:** Ticket H (roteiro E2E + verificação), que depende de F ✅ e G ✅.
- Achado do §3 aguarda decisão do arquiteto; **não bloqueia** o Ticket H — o fluxo funciona.

---

*Registro emitido pelo Engenheiro em 2026-08-13. Classe `module` (frontend). Atenção do revisor ao
§3: o Ticket G foi entregue sem mudar backend, mas a lacuna do `GET /pedidos-exame/{proto}` continua
lá e afeta o painel de detalhes desde antes desta sessão.*
