# Ticket F — Frontend: gesto "Enviar à bancada" no `clinica.html`

| Campo | Valor |
|---|---|
| Classe | `module` (frontend) |
| Depende de | B (endpoint `/em-analise`) |
| Esforço | Pequeno |

## Contexto

Decisão #4 na tela. Hoje, em `renderizarItens` (`clinica.html:1632-1647`), o item `coletado` mostra
só "Registrar resultado"; `em_analise` mostra um `<span>` inerte "⏳ Em análise". Vamos adicionar o
gesto explícito "Enviar à bancada" (`coletado → em_analise`) chamando o endpoint do Ticket B.

## Arquivo

- `clinica.html` — `renderizarItens` (`:1620`), `atualizarStatusUI` (`:1747`), nova função
  `registrarBancada(itemId)`.

## Padrão a espelhar

Copiar a estrutura de `registrarColeta` (`clinica.html:1669-1696`):
`authHeaders()` → `fetch(BACKEND + path, {method, headers, body})` → 401/403 via
`handleUnauthorized()` (mas **403 de role não derruba sessão** — ver `:1361`) → `!resp.ok` com
`_extrairMsgErro` → sucesso `atualizarStatusUI` + `recarregarPedido()`.

## Tarefa

1. **Em `renderizarItens` (`:1632-1647`)**, ramo `'coletado'`:
   - Adicionar botão **"Enviar à bancada"** (`id="btn-bancada-{item.id}"`,
     `onclick="registrarBancada({item.id})"`) ao lado do "Registrar resultado".
   - Manter "Registrar resultado" (atalho direto para `resultado_disponivel` ainda é útil).
   - Ramo `'em_analise'` (`:1643`): trocar o `<span>` inerte por **"⏳ Na bancada — aguardando laudo"**
     + (deixar o botão de laudo para o Ticket G, que orquestra a produção do laudo a partir de `em_analise`).

2. **Nova função `registrarBancada(itemId)`** (espelhar `registrarColeta`):
   - Opcional: `const setor = prompt('Setor/bancada (opcional, ex.: bioquímica):') ?? null;` — se
     cancelar, aborta; se vazio, envia `{}` ou `{setor: null}`.
   - `POST /pedidos-exame/{protocolo}/itens/{itemId}/em-analise` com body `JSON.stringify({setor})`.
   - Em sucesso: `atualizarStatusUI(itemId, data.status_item || 'em_analise')` + `recarregarPedido()`.

3. **Espelhar em `atualizarStatusUI` (`:1747-1761`)** o ramo `em_analise` (classe de borda/badge
   consistente com os outros estados) e o novo botão de bancada no ramo `coletado`.

## Guardrails de UI

- `esc()` em toda interpolação de dados no HTML (anti-XSS) — já é convenção do arquivo.
- `_extrairMsgErro(err, String(resp.status))` para erros do FastAPI (`detail` string/array/object).
- 403 aqui é **role/custódia**, não expiração de sessão: **não** chamar `handleUnauthorized()` em
  403 (apenas em 401). Alinhar ao precedente de `carregarAgendamentos` (`:1361-1373`).

## Critérios de aceite

- [ ] Item `coletado` mostra "Enviar à bancada" + "Registrar resultado".
- [ ] Clicar "Enviar à bancada" leva o item a `em_analise` (UI atualiza e `recarregarPedido` confirma).
- [ ] Estado `em_analise` mostra "Na bancada — aguardando laudo".
- [ ] Erro do backend aparece via `alert(_extrairMsgErro(...))`; 403 não derruba sessão.
- [ ] Sem XSS (tudo passa por `esc()`).

## Teste (manual / web-gui-tester)

- Abrir pedido com item `coletado` → clicar "Enviar à bancada" → item vira "Na bancada".
- Cancelar o prompt de setor → nada é enviado.
