# Ticket G — Frontend: UI de laudo estruturado no `clinica.html` (pedra angular)

| Campo | Valor |
|---|---|
| Classe | `module` (frontend) |
| Depende de | C (RBAC laudo-dispensador) |
| Esforço | Alto (é a peça central da demo) |

## Contexto

Decisão #1: a pedra angular. Hoje o `clinica.html` **não integra `/laudos`** (confirmado: só há
classes CSS `.laudo-*`, sem fetch). O backend do laudo está completo e o Ticket C abre o caminho
para o dispensador produzir/assinar/liberar. Este ticket constrói a UI que substitui o prompt livre
de resultado pela produção de um laudo estruturado que vai à **custódia do cidadão**.

> O lado cidadão já está pronto (`cidadao.html:693-756`). Ao liberar, o laudo aparece na carteira do
> cidadão e ele dá ciência. **Não mexer no `cidadao.html`.**

## Arquivo

- `clinica.html` — card "Exames Solicitados" (`:677-682`), `renderizarItens` (`:1620`),
  `atualizarStatusUI` (`:1747`), nova função `produzirLiberarLaudo()`.

## Padrão a espelhar

- Mutação POST: `registrarColeta` (`:1669`) / `registrarResultado` (`:1703`).
- Inline-form: `#form-agendar` (`:1440`) — modelo para o editor de laudo.
- Download autenticado: `_baixarArquivoClinica` (`:1813`).
- Auth: `authHeaders()` (`:763`); `jwtAccessToken` (`:712`); `pedidoAtual` (`:714`).
- Header buttons: bloco `.btn-rel` (`:537`).

## Tarefa

### G1. Gatilho "Produzir laudo do pedido"

- No card "Exames Solicitados" (`:677`), quando **≥1 item** está em `em_analise`, exibir botão
  **"🔬 Produzir laudo"** (nível pedido, não por item — um laudo cobre o pedido).
  - Computar em `renderizarItens`: se algum item tem `status_item === 'em_analise'`, renderizar o
    botão no rodapé do card.

### G2. Editor de laudo (modal ou inline-form)

Pré-preenchido a partir de `pedidoAtual.itens` filtrados por `em_analise`. Para cada item do laudo:
- `nome_exame` (readonly, do item), `codigo_tuss` (readonly).
- Inputs do operador:
  - `resultado_resumo` (texto curto, ex.: "Glicemia 92 mg/dL").
  - `conclusao` — **select**: `normal | alterado | indeterminado | inconclusivo` (espelha
    `_CONCLUSOES_VALIDAS` em `laudos.py:73`).
  - `valor_referencia` (texto, ex.: "70–99 mg/dL").
- Campos do **RT** (Responsável Técnico):
  - `cns_autor` + `nome_autor`. Pré-preencher com o RT demo da unidade quando disponível (painel
    "Chaves de acesso demo" / config); senão, campos editáveis.
  - O `cpf_paciente`/`nome_paciente` vem de `pedidoAtual`.

### G3. `produzirLiberarLaudo()` — orquestração (endpoints existentes)

Sequência encadeada (cada passo com tratamento de erro via `_extrairMsgErro`):

1. `POST /laudos` com:
   ```json
   {
     "cns_autor": "<RT>", "nome_autor": "<RT nome>",
     "cpf_paciente": "<do pedido>", "nome_paciente": "<do pedido>",
     "pedido_protocolo": "<pedidoAtual.protocolo>",
     "itens": [ { "nome_exame", "codigo_tuss", "resultado_resumo", "conclusao", "valor_referencia" } ]
   }
   ```
   → guarda `laudoProto = data.protocolo`.
2. `POST /laudos/{laudoProto}/assinar`.
3. `POST /laudos/{laudoProto}/liberar` com body `{ "cnpj_prestador": "<CNPJ da sessão>" }`
   (o Ticket C faz o dispensador usar o `ident` da sessão).
4. Para **cada item** `em_analise` do pedido: `POST /pedidos-exame/{proto}/itens/{id}/resultado`
   com `{ "resultado_resumo": <resumo do item> }` → item → `resultado_disponivel`.
   - (Isto move os itens; o laudo é o artefato clínico. É a "ponte item↔laudo" no frontend — ver
     Riscos.)
5. `recarregarPedido()`.

### G4. Feedback de ciência

- Após liberar, o pedido exibe o laudo na seção de itens (estado `resultado_disponivel`):
  "✓ Laudo liberado ao cidadão — aguardando ciência".
- Ler o status do laudo via `GET /laudos/{laudoProto}` (agora acessível ao dispensador via-pedido,
  Ticket C) e refletir: `liberado → ciencia_paciente → encerrado`.
  - Atualizar em `recarregarPedido` (e, opcional, um poll leve de ~30s como o da fila `:665`).
- Botão de download do PDF do laudo via `_baixarArquivoClinica('/laudos/{proto}/pdf', ...)`
  (opcional, para conferência do operador).

### G5. (Opcional) Botão no header

- Pré-visualizar/descarregar laudo a partir do header, ao lado de Faturamento (`:541`). Só se ajudar
  a narrativa da demo.

## Guardrails de UI

- `esc()` em toda interpolação; `_extrairMsgErro` para erros.
- 403 ≠ sessão expirada (não chamar `handleUnauthorized` em 403 — precedente `:1361`).
- O laudo é **sempre** atribuído ao RT (`autor_id`); o operador só declara o CNS.
- O resultado do item (`resultado_resumo`) é o **ponteiro/sumário**; o conteúdo estruturado vive no laudo.

## Riscos & compensações

- **Ponte item↔laudo no frontend:** a orquestração `liberar → /resultado por item` é no frontend
  (evita acoplamento cross-objeto no backend). Se falhar entre os passos, itens ficam em `em_analise`
  — **idempotente**: clicar "Produzir laudo" de novo reprocessa. (Acoplamento backend
  laudo-liberado ⇒ item-resultado fica como v2.)
- **Laudo já existe para o pedido:** se o operador re-clicar após um laudo criado, o backend cria
  outro laudo derivado. Para a demo, desabilitar o botão "Produzir laudo" quando já houver laudo
  liberado para o pedido (checar via `GET /laudos/{proto}` ou flag em `pedidoAtual`).

## Critérios de aceite

- [ ] Com ≥1 item `em_analise`, o botão "🔬 Produzir laudo" aparece.
- [ ] O editor abre pré-preenchido com os itens `em_analise` (nome/TUSS) e inputs de resultado.
- [ ] Submit produz laudo → assina → libera → marca itens `resultado_disponivel`.
- [ ] O laudo aparece na carteira do cidadão (`cidadao.html`) após liberação (verificação E2E).
- [ ] O cidadão dá ciência → o clínica vê o status progredir para `encerrado`.
- [ ] Sem XSS; erros tratados; 403 não derruba sessão.
- [ ] Botão "Produzir laudo" desabilita após liberação (evita laudo duplicado).

## Teste (web-gui-tester)

- Pedido com item `em_analise` → "Produzir laudo" → preencher → liberar.
- Trocar para o `cidadao.html` (outro perfil) → laudo na carteira → "Dar ciência" → baixar PDF.
- Voltar ao `clinica.html` → status mostra "encerrado"/"ciência registrada".
