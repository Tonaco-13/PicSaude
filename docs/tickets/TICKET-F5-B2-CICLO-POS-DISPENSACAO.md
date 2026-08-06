# TICKET-F5-B2 — Ciclo pós-dispensação: fila só dispensáveis + histórico com comprovante ESTORNADO

> **⚙️ STATUS — ✅ Implementado (2026-07-11).**
> Commit `47239a5` · PR #93 (ver §10 do parent `TICKET-F5-FATIA-B-FRONTEND-DISPENSADOR.md`).
> Espec abaixo preservada como **registro histórico**; não reabrir sem evidência de regressão ao vivo.
>
> **Verificado contra `main` em 2026-07-25 (Z AI):**
> - `_renderizarFila` (`:1299`) usa `p.itens.some(i => i.acionavel)` (`:1308`) + `_FILA_TERMINAIS` (`:1285`) — Escopo A OK.
> - Histórico `_renderHistorico` (`:1817`) mostra Comprovante + Estorno; `i.estornado` vem do backend (`dispensadores.py:271`) — Escopo B OK.
> - **Critério §5 n.4 verde:** `grep -nE "i\.estornado\s*=\s*[^=]" dispensador.html` retorna zero (não se calcula estorno no cliente).
> - **Pendente:** browser-E2E `test_f5_b2_ciclo_pos_dispensacao.py` (§6) — não há arquivo em `backend/tests/browser/`.

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — Fatia B, ticket 2 de 3 |
| **Classe** | `module` (frontend puro em `dispensador.html`, consome endpoints já mergeados) |
| **Para** | Revisor de tickets → Conselheiro → engenheiro → gate + browser-E2E → martelo Fabiano |
| **Origem** | TICKET-F5-RELATORIO-SNGPC §4 + teste manual pós-merge #120 (Fabiano + Z AI, 2026-07-23) |
| **Pré-requisito** | `main` atual (pós-merge #120 — COER-2 com estado `transferida_prescritor`); T5 (comprador) e T6 (histórico) mergeados |

## §1 Contexto (não reabrir)

O ciclo de dispensação hoje funciona no backend (T2 estorno, B0 guard-por-saldo, T1.5 detenção prévia, COER-2 unicidade de posse — todos em produção). O bug é de **renderização da UI**: a fila mostra itens que não deveriam aparecer (terminais), e o comprovante de uma dispensação estornada não exibe o carimbo ESTORNADO de forma inequívoca.

3 escopos acoplados num único ticket porque compartilham o mesmo rendering em `dispensador.html` — separar viraria merge hell (3 PRs tocando as mesmas linhas).

### Escopos cobertos (3 em 1)

**A. Fila mostra só dispensáveis.** Hoje a fila mostra itens terminais com badge; o teste manual (Fabiano) confirmou que isso confunde o operador. **Receita com todos os itens não-acionáveis sai da fila** e vai pro histórico.

**B. Ciclo pós-dispensação: item dispensado → histórico com 🧾 Comprovante + ⏪ Estorno.** Botão Estorno só habilita se a dispensação **não** foi estornada — estado vindo do backend (`i.estornado`), **nunca** calculado no cliente.

**C. Comprovante marca ESTORNADO.** Quando uma dispensação foi estornada, o comprovante exibe carimbo inequívoco "⏪ DISPENSAÇÃO ESTORNADA — ref. estorno {protocolo}". Nunca some, nunca é editado.

## §2 Invariantes (não-negociáveis)

- **§10 (estados computados não persistidos):** `i.estornado` vem do backend (`dispensadores.py:253` — `q_est > 0 and q_est >= q_disp`). **Nunca** calcular "já estornado" no cliente.
- **R1 (reprodutibilidade):** comprovante é projeção do ledger. Estorno **carimba** (adiciona seção), **nunca apaga/edita** a dispensação original.
- **§6b (Regra de Ouro):** protocolo da prescrição e nº da dispensação são **imutáveis** e aparecem idênticos em fila, histórico, comprovante, CSV — antes e depois do estorno.
- **R3 (linhagem-mãe):** se `protocolo_raiz` disponível, exibir no comprovante (não-blocking se R3 ainda não mergeado).

## §3 Contratos (endpoints reais — já em produção)

```
GET /dispensadores/fila
Auth: JWT role=dispensador
Retorna: prescrições com itens em custódia ativa do CNPJ do JWT,
         cada item com status, saldo, etc.

GET /dispensadores/historico
Auth: JWT role=dispensador
Retorna: dispensações desta unidade, cada uma com:
  - dispensacao_id, protocolo_prescricao
  - comprador (nome, documento, eh_paciente)
  - medicamentos[] com qtd dispensada, qtd estornada
  - estornado (bool — DERIVADO DO BACKEND, §10)
  - estornos[] (lista de estornos com protocolo, motivo, data)

GET /dispensacoes/{id}/comprovante
Auth: JWT role=dispensador (CNPJ deve bater com o que dispensou)
Retorna JSON (e PDF via mesmo endpoint com Accept header):
  - dispensacao_id, protocolo_prescricao, data
  - comprador (nome, documento, eh_paciente)
  - paciente (nome, documento)
  - medicamento (nome, qtd, lote, fabricante, validade)
  - estabelecimento (cnpj)
  - estorno { estornado, estorno_total, quantidade_estornada,
              quantidade_restante, estornos[] }  # já mergeado (B3 do TICKET-F5-FATIA-B)
```

## §4 Spec de implementação

### 4.1 Arquivos tocados
- `dispensador.html` — função `_renderizarFila`, `_renderHistorico`, `_renderComprovante`, helpers auxiliares. **Não** tocar no backend.

### 4.2 Escopo A — Fila mostra só dispensáveis

**Critério "não-acionável" (regra de apresentação derivada do backend):** uma receita **não é renderizada na fila** quando **todos** os seus itens estão em estado terminal (`dispensado`, `cancelado`, `devolvido_paciente`, `devolvido_prescritor`) **OU** com `saldo_efetivo <= 0`.

**Implementação:**
- Em `_renderizarFila`, filtrar prescrições onde `itens.every(i => _FILA_TERMINAIS.has(i.status_item) || i.saldo_efetivo <= 0)`
- Não adicionar cálculo de estado no cliente — usar só os campos `status_item` e `saldo_efetivo` que o backend já retorna
- Reentrada por estorno (B0): quando estorno repõe saldo, o backend já retorna o item com `saldo_efetivo > 0` → receita reaparece na fila automaticamente (sem código extra no front)

### 4.3 Escopo B — Ciclo pós-dispensação + botão Estorno

**Renderização do histórico:**
- Cada dispensação no histórico mostra:
  - Paciente + Protocolo + Comprador (se `comprador_eh_paciente=false`, destacar)
  - Medicamento + qtd dispensada + qtd estornada
  - Botão `🧾 Comprovante` → chama `verComprovante(dispensacao_id)`
  - Botão `⏪ Estorno` → **só habilitado se `!i.estornado`** (campo do backend, §10)
  - Se `i.estornado === true`: badge "ESTORNADO" no lugar do botão (já existe, confirmar)

**Handler de estorno:**
- `estornarDispensacao(id)` já existe — confirmar que chama `POST /dispensacoes/{id}/estornar`
- Após sucesso: refresh do histórico (não reload da página) + feedback "✓ Estorno registrado. Saldo reposto: N"
- Modal de motivo: dialog nativo ou modal custom — manter o que existe

### 4.4 Escopo C — Comprovante ESTORNADO

**Em `_renderComprovante` (modal):**

Quando `c.estorno?.estornado === true`:
- **Carimbo no topo** do modal: "⏪ DISPENSAÇÃO ESTORNADA"
- Subtítulo: `ref. estorno {estorno_protocolo}` (primeiro da lista, ou "múltiplos estornos" se >1)
- Se `estorno_total === false`: "parcialmente estornado — N un. restante"
- Estilo destacado (faixa vermelha, ícone, padding) — acima dos blocos COMPRADOR/PACIENTE

**Quando `c.estorno?.estornado === false`:**
- Comprovante permanece **idêntico** ao comportamento atual (sem carimbo)

**Nunca:**
- Apagar/editar dados da dispensação original (R1)
- Esconder o comprovante (sempre pode abrir, mesmo estornado)
- Recalcular `estornado` no cliente (§10)

### 4.5 PDF do comprovante

Se o usuário clicar "📄 BAIXAR PDF" no comprovante estornado, o PDF também deve conter o carimbo "DISPENSAÇÃO ESTORNADA — ref. {protocolo}". O backend já faz isso (B3 do TICKET-F5-FATIA-B) — confirmar que o frontend passa o Accept header correto.

## §5 Critérios de aceite

### Escopo A — Fila
1. Receita com todos os itens terminais (ex.: dispensação total sem estorno) **não aparece** na fila
2. Receita com 1 item terminal + 1 item `em_custodia` com saldo > 0 **aparece** na fila
3. Após estornar uma dispensação total, a receita **reaparece** na fila com saldo reposto (B0 funcionando)
4. `grep -nE "i\.estornado\s*=\s*[^=]" dispensador.html` retorna **zero** — nunca calcular estornado no cliente

### Escopo B — Ciclo
5. Item dispensado aparece no histórico com botões 🧾 Comprovante + ⏪ Estorno
6. Botão Estorno **desabilitado/badge** quando `i.estornado === true` (do backend)
7. Após estornar, histórico atualiza sem reload de página
8. Feedback "✓ Estorno registrado. Saldo reposto: N" aparece

### Escopo C — Comprovante ESTORNADO
9. Comprovante de dispensação estornada exibe carimbo "⏪ DISPENSAÇÃO ESTORNADA — ref. {protocolo}"
10. Comprovante de dispensação parcialmente estornada exibe "parcialmente estornado — N un. restante"
11. Comprovante de dispensação **não** estornada permanece idêntico (sem carimbo)
12. Protocolo da prescrição e dispensação_id **idênticos** antes/depois do estorno em fila, histórico, comprovante (R3/§6b)
13. Nenhuma linha apagada/editada em `dispensacoes`/`estornos`/ledger (verificação por contagem antes/depois)

### Browser-E2E (obrigatório)
14. `tests/browser/test_f5_b2_ciclo_pos_dispensacao.py` verde — ver §6

## §6 Browser-E2E (obrigatório no aceite)

Adicionar `tests/browser/test_f5_b2_ciclo_pos_dispensacao.py`:

```python
def test_b2_escopo_a_fila_só_dispensaveis(browser_demo):
    """Receita com todos os itens terminais não aparece na fila."""
    # Setup: prescrição com 1 item, dispensar total (saldo 0)
    # Ir ao dispensador
    # Assert: receita NÃO está na fila
    # Assert: receita ESTÁ no histórico

def test_b2_escopo_a_reentrada_por_estorno(browser_demo):
    """Após estornar dispensação total, receita reaparece na fila."""
    # Setup: dispensar total → receita sai da fila
    # Estornar a dispensação
    # Refresh da fila
    # Assert: receita VOLTOU pra fila com saldo > 0

def test_b2_escopo_b_botao_estorno_estado_do_backend(browser_demo):
    """Botão Estorno só habilitado se !i.estornado (do backend)."""
    # Renderizar histórico de uma dispensação estornada
    # Assert: badge "ESTORNADO" presente, botão Estorno ausente/desabilitado
    # Renderizar histórico de uma dispensação não estornada
    # Assert: botão Estorno habilitado

def test_b2_escopo_c_comprovante_estornado(browser_demo):
    """Comprovante de dispensação estornada tem carimbo."""
    # Dispensar → estornar → abrir comprovante
    # Assert: carimbo "DISPENSAÇÃO ESTORNADA" visível no topo
    # Assert: ref. estorno protocolo visível
    # Assert: dados da dispensação original (qtd, lote) permanecem visíveis (R1)
    # Assert: protocolo_prescricao não mudou (§6b)

def test_b2_escopo_c_comprovante_nao_estornado(browser_demo):
    """Comprovante de dispensação não estornada permanece idêntico."""
    # Dispensar (sem estornar) → abrir comprovante
    # Assert: NÃO tem carimbo "ESTORNADO"
    # Assert: demais dados idênticos ao comportamento atual
```

Crítico: o E2E **deve afirmar sobre o DOM renderizado**, não sobre respostas de API isoladas. Foi um agente navegando a demo que pegou os bugs de posse dupla que 22 testes PG não pegaram (LEARNINGS do COER-2).

## §7 Fora de escopo

- Backend (todos os endpoints já estão mergeados)
- Botões de relatório (TICKET-F5-B1)
- Remoção de UI de devolução ao prescritor (TICKET-F5-B3)
- Comprovante com `protocolo_raiz` (depende de R3-PROTOCOLO-RAIZ)
- Polish visual (transições animadas, cores) — frente de UX separada

## §8 Fluxo de aprovação

1. Revisor de tickets (code/app) revisa escopo e contratos
2. Conselheiro dá parecer (verde / verde-com-notas / bloqueio) — foco em §10 (estado do backend, não do cliente) e R1 (comprovante não edita)
3. Engenheiro implementa + browser-E2E
4. Gate CI verde (PG + SQLite) — suíte existente + novos testes
5. Browser-E2E verde (5 cenários do §6)
6. Martelo do Fabiano + merge

## §9 Não fazer

- Não calcular `estornado` no cliente (§10)
- Não apagar/editar dados da dispensação original no comprovante (R1)
- Não usar `<a href>` para endpoints (sempre fetch com Bearer)
- Não implementar sem o browser-E2E (5 cenários obrigatórios)
- Não tocar no backend (todos os endpoints já existem)
- Não adicionar botão de devolução ao prescritor (é o TICKET-F5-B3 que **remove**)
