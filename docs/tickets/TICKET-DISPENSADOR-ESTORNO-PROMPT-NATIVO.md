# TICKET-DISPENSADOR-ESTORNO-PROMPT-NATIVO — Substituir prompt() nativo do estorno por modal HTML

| Campo | Valor |
|---|---|
| **ID** | TICKET-DISPENSADOR-ESTORNO-PROMPT-NATIVO |
| **Classe** | `module` (robustez de UI no `dispensador.html` — não toca estados/custódia/ledger) |
| **Estado** | 🟡 **REGISTRADO** — aguarda sequenciamento |
| **Para** | Engenheiro (frontend) |
| **Origem** | Teste de UI do `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO` (10/08). Sintoma "depois caiu" relatado pelo Fabiano. |
| **Severidade** | Média — não bloqueia o core; afeta a experiência de estorno no balcão |

> **Desmembrado de** `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO` §9 (que é `core` de estados;
> este é `module` de UI — independentes).

---

## §1 Problema

O handler `estornarDispensacao` (`dispensador.html:1496`) usa `prompt()` nativo do JavaScript
para pedir o motivo do estorno (número 1–4):

```js
const escolha = prompt(`Estornar a dispensação #${dispensacaoId} — motivo:\n${opts}\n\nDigite o número (1-4):`);
```

Durante o teste de UI (IAB/navegador), este `prompt()`:

1. **Bloqueia** a execução do `click()` por até 32s (timeout do autômato), sem ser interceptável
   via `getJsDialog()`.
2. Pode ser a causa do sintoma **"depois caiu"** relatado pelo Fabiano — se o `prompt()` falha ou
   o usuário o descarta sem digitar, o handler retorna silenciosamente (`if (!escolha.trim())`)
   deixando a dúvida "estornei ou não?" sobre um registro de ledger.

O `prompt()`/`alert()`/`confirm()` nativos são frágeis em webviews/IAB e inconsistentes entre
navegadores. O projeto já tem padrão melhor: o modal HTML `_abrirLoteFila` (`dispensador.html:1363`)
para a dispensação.

## §2 Solução proposta

Substituir o `prompt()` por um **modal HTML** (mesmo padrão de `#modal-lote-fila`):

- Mostra os 4 motivos como botões/cards selecionáveis (não exige digitar número).
- Confirmação explícita antes de POSTar.
- Feedback de sucesso/erro no próprio modal (`_filaMsg` já existe).
- Estado desabilitado enquanto o POST está em vôo (evita duplo-submit — reforça R2).

## §3 Fora de escopo

- A lógica de backend do estorno — é o `TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO` (core).
- Outros `prompt()`/`alert()` do `dispensador.html` — avaliar em follow-up se houver.

## §4 Critérios de aceite

1. Clicar em "⏪ Estornar" abre um modal HTML (não `prompt()` nativo).
2. Motivo é selecionado por clique (4 opções), não por digitação.
3. Confirmação POSTa e mostra feedback no modal.
4. Duplo-click durante o POST não dispara segundo estorno (R2).
5. Funciona em IAB sem travar (teste de UI reproduz o caminho sem timeout de 32s).
