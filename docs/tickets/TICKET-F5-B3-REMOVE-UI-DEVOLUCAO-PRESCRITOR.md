# TICKET-F5-B3 — Remover UI de devolução ao prescritor (endpoint e badges permanecem)

> **⚙️ STATUS — ✅ Implementado (2026-07-11).**
> Commit `9062513` · PR #94 (ver §10 do parent `TICKET-F5-FATIA-B-FRONTEND-DISPENSADOR.md`).
> Espec abaixo preservada como **registro histórico**; não reabrir sem evidência de regressão ao vivo.
>
> **Verificado contra `main` em 2026-07-25 (Z AI):**
> - **Critério §4.5 verde:** `grep -nE "devolverPrescritor|toggleMotivoPrescritor|devolverItemPrescritor|✕ Prescritor|Dev\. ao Prescritor" dispensador.html` retorna **zero** (zero botões de AÇÃO).
> - **Opção A do §4.4 aplicada:** o ramo `'prescritor'` de `_devolverFila` foi removido; `_devolverFila` (`:1438`) segue genérico, usado só para devolução ao paciente (`_devolverPacienteFila` `:1453`).
> - Badges de ESTADO `devolvido_prescritor` permanecem renderizando (`:923`, `:1291`).
> - Endpoint backend **não** é do dispensador: `POST /paciente/prescricoes/{proto}/devolver-prescritor` em `auth.py:257` (role `paciente`) — resíduo de comentário no ticket será alinhado.
> - **Pendente:** browser-E2E `test_f5_b3_remove_ui_devolucao_prescritor.py` (§6) — não há arquivo em `backend/tests/browser/`.

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — Fatia B, ticket 3 de 3 |
| **Classe** | `module` (frontend puro, **remoção** de UI; nenhum backend novo) |
| **Para** | Revisor de tickets → Conselheiro → engenheiro → gate + browser-E2E → martelo Fabiano |
| **Origem** | Despacho antigo do Fabiano: remover resíduo de UI de devolução ao prescritor do dispensador (a devolução ao médico é fluxo do paciente, não do farmacêutico) |
| **Pré-requisito** | `main` atual; TICKET-COER2-POS-MERGE-DIAGNOSTICO fechado (para não conflitar com investigação em andamento) |

## §1 Contexto (não reabrir)

A devolução ao prescritor é **fluxo do cidadão** (paciente identifica erro e devolve ao médico pelo módulo cidadão). Hoje o módulo dispensador também tem UI de ação pra isso (botão `✕ Prescritor` na fila, bloco de motivo no painel por prescrição). É resíduo de UX — o farmacêutico não devolve receita ao médico; o paciente é quem devolve.

**Decisão de produto (Fabiano, despacho antigo):** remover **apenas a UI de ação** do dispensador. O endpoint de backend e os badges de estado (`devolvido_prescritor`) **permanecem** — porque o dispensador precisa continuar **vendo** que uma receita foi devolvida ao médico (status vindo do backend).

### Por que separar num ticket próprio

Aparenta ser ticket pequeno (só remover botões), mas tem 3 armadilhas:
1. **Diferenciar UI de AÇÃO vs UI de ESTADO.** Botões de ação saem; badges de estado ficam. Confundir os dois remove informação valiosa do farmacêutico.
2. **Código morto silencioso.** Se a função `_devolverPrescritorFila` ficar sem chamador após remover o botão, vira dívida invisível. Decisão explícita: remover o ramo `'prescritor'` ou deixar comentado com referência ao ticket.
3. **Não conflita com o COER2-POS-MERGE.** Esse ticket investiga por que a devolução ao prescritor não chega no painel **do prescritor** (módulo diferente). Aqui, removemos a UI de **disparo** no **dispensador**. São camadas distintas — não há sobreposição, mas convém não rodar simultaneamente pra evitar confusão de teste.

## §2 Invariantes (não-negociáveis)

- **§1 (imutabilidade):** endpoint de backend permanece — apenas UI de ação é removida.
- **§6b (Regra de Ouro):** protocolo permanece visível; badges de estado `devolvido_prescritor` permanecem renderizando corretamente.
- **R1 (reprodutibilidade):** nenhuma mudança no ledger ou em `prescricao_custodia` — só UI.

## §3 Contrato (endpoints que PERMANECEM)

Estes endpoints **não mudam** neste ticket:

```
POST /dispensadores/{proto}/devolver-prescritor  # endpoint PERMANECE
GET  /dispensadores/fila                          # continua retornando status dos itens
                                                    (incluindo 'devolvido_prescritor')
```

A UI de ação que **dispara** o POST acima é removida. Se um item chegar como `devolvido_prescritor` (terminal), a fila continua mostrando badge (já coberto pelo Escopo A do TICKET-F5-B2 — fila só dispensáveis).

## §4 Spec de implementação

### 4.1 Arquivos tocados
- `dispensador.html` — remover botões e handlers; manter badges de estado.

### 4.2 O que REMOVER (ação)

| Onde | O que remover |
|---|---|
| Fila, botão `✕ Prescritor` (~linha 1249) | Botão de ação |
| `_devolverPrescritorFila` (~linha 1365) | Handler; ver §4.4 sobre código morto |
| Painel por prescrição, botão `✕ Dev. ao Prescritor` (~linha 1675) | Botão de ação |
| `toggleMotivoPrescritor` (~linha 1702) | Toggle do bloco de motivo |
| `devolverItemPrescritor` (~linha 1934) | Handler de submissão do motivo |

### 4.3 O que MANTER (estado)

| O que | Por quê |
|---|---|
| Badges de estado `devolvido_prescritor` em `_filaStatusInfo` / `statusBadge` | Farmacêutico precisa ver que receita foi devolvida (informação, não ação) |
| Endpoint backend `POST /dispensadores/{proto}/devolver-prescritor` | Cidadão ainda pode disparar devolução pelo módulo dele; endpoint permanece |
| Quaisquer testes que validem o endpoint | Endpoint não muda |

### 4.4 Código morto — decisão explícita

Após remover os 5 itens do §4.2, a função `_devolverFila(proto, item, 'prescritor', ...)` pode ficar sem chamador. **2 opções:**

- **(A) Remover o ramo `'prescritor'`** de `_devolverFila` (limpo, mas se alguém reativar a UI no futuro precisa reescrever)
- **(B) Deixar o ramo comentado com referência** a este ticket (preserva intent, mas pode virar código morto silencioso se ninguém ler o comentário)

**Recomendação Z AI: opção (A)** — remover. Razão: código morto é dívida. Se alguém reativar a UI, git blame mostra o ticket e a razão da remoção. Comentário com referência também entra no commit message.

Engenheiro decide A ou B, mas precisa justificar no PR.

### 4.5 Grep de confirmação (obrigatório)

Após implementar, rodar e colar output literal no PR:

```bash
grep -nE "devolverPrescritor|toggleMotivoPrescritor|devolverItemPrescritor|✕ Prescritor|Dev\. ao Prescritor" dispensador.html
```

**Esperado:** zero ocorrências de **ação**. Badges de estado que citam "prescritor" (sem ser botão) podem aparecer — distinguir.

## §5 Critérios de aceite

1. **Zero botões de AÇÃO** de devolução ao prescritor no `dispensador.html` (grep §4.5 retorna vazio)
2. **Badges de estado `devolvido_prescritor` continuam renderizando** (não remover informação visual de estado)
3. **Endpoint `POST /dispensadores/{proto}/devolver-prescritor` permanece funcional** (testado via curl/python3 com JWT)
4. **Receita devolvida pelo cidadão continua aparecendo no dispensador** com badge (não com botão de ação)
5. **Código morto tratado** (opção A ou B do §4.4, justificada no PR)
6. **Browser-E2E verde** — ver §6

## §6 Browser-E2E (obrigatório no aceite)

Adicionar `tests/browser/test_f5_b3_remove_ui_devolucao_prescritor.py`:

```python
def test_b3_sem_botao_devolucao_prescritor_na_fila(browser_demo):
    """Fila do dispensador não tem botão de devolução ao prescritor."""
    # Login demo dispensador
    # Renderizar fila com uma receita ativa
    # Assert: NÃO existe botão com texto "Prescritor" ou "Dev. ao Prescritor"
    # Assert: NÃO existe handler onclick chamando devolverPrescritorFila

def test_b3_badge_estado_permanece(browser_demo):
    """Item devolvido_prescritor ainda mostra badge (não botão)."""
    # Setup (via API ou seed): prescrição com item em estado devolvido_prescritor
    # Renderizar fila ou histórico
    # Assert: badge "Devolvido ao Prescritor" (ou similar) presente
    # Assert: NÃO existe botão de ação de devolução

def test_b3_endpoint_permanece_funcional(browser_demo):
    """Endpoint backend de devolução ao prescritor ainda responde."""
    # Via API (não UI): POST /dispensadores/{proto}/devolver-prescritor
    # com JWT de dispensador
    # Assert: 200 ou 409/422 esperado (não 404 — endpoint existe)
    # Nota: pode ser que o endpoint rejeite (porque dispensador não devolve),
    #        mas o importante é que NÃO é 404 (rota existe)
```

## §7 Fora de escopo

- Backend (endpoint permanece)
- Módulo cidadão (a devolução ao médico continua sendo pelo módulo do cidadão)
- COER2-POS-MERGE-DIAGNOSTICO (investigação separada do painel do prescritor — não mexer aqui)
- Reabrir a UI de devolução no futuro (decisão de produto posterior, se houver demanda)

## §8 Fluxo de aprovação

1. Revisor de tickets (code/app) revisa escopo e diferenciação ação vs estado
2. Conselheiro dá parecer (verde / verde-com-notas / bloqueio) — foco em: endpoint permanece, badges permanecem, só ação sai
3. Engenheiro implementa + browser-E2E
4. Gate CI verde
5. Browser-E2E verde
6. Martelo do Fabiano + merge

## §9 Não fazer

- Não remover o endpoint de backend
- Não remover badges de estado `devolvido_prescritor`
- Não tocar no módulo cidadão (devolução ao médico continua sendo pelo cidadão)
- Não implementar antes do COER2-POS-MERGE-DIAGNOSTICO fechar (evitar confusão de teste)
- Não deixar código morto silencioso (decidir A ou B do §4.4 e justificar)

## §10 Coordenadas com tickets existentes

| Ticket | Relação |
|---|---|
| **TICKET-F5-B1** (botões relatório) | Independente — pode rodar em paralelo |
| **TICKET-F5-B2** (ciclo pós-dispensação) | Toca o mesmo arquivo (`dispensador.html`); mergear B2 antes pra evitar conflito |
| **TICKET-COER2-POS-MERGE-DIAGNOSTICO** | Diagnóstico de bug do painel do prescritor (módulo diferente); este ticket não mexe no painel do prescritor, só no dispensador |
