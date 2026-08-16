# Ticket B — Endpoint "Enviar à bancada" (`coletado → em_analise`)

| Campo | Valor |
|---|---|
| Classe | `module` |
| Depende de | — |
| Esforço | Pequeno–médio |

## Contexto

Decisão #4: o gesto "enviar à bancada". Hoje `em_analise` é um **estado fantasma** — declarado em
`states_exame.py:88`, aceito como entrada por `/resultado` (`pedidos_exame.py:1176`), logado como
evento `pedido_em_analise` (`:134`), **mas nenhum endpoint persiste `status_item='em_analise'`**. O
endpoint `/resultado` colapsa `coletado → resultado_disponivel` numa tacada. Este ticket
**materializa a transição** que o contrato já prevê.

## Arquivos

- `backend/app/routers/pedidos_exame.py` — adicionar endpoint (espelhar `coletar` em `:960`).
- Teste: adicionar caso no suite de exames (mesmo padrão dos testes de `coletar`/`resultado`).

## Tarefa

Implementar `POST /pedidos-exame/{protocolo}/itens/{item_id}/em-analise`:

1. **RBAC:** `require_role("dispensador", "admin")` (a unidade envia à bancada; prescritor não precisa).
   - Observar convenção do módulo: "dispensador = clínica/lab MVP".
2. **Ownership:** reusar o assert de custódia do dispensador sobre o pedido (mesma semântica de
   `_assert_dispensador_dono_pedido` usado em `coletar`/`resultado`). 404 → 403 → 422.
3. **Guarda de estado:** exigir `item["status_item"] == "coletado"`; senão 422 com mensagem clara.
   - A transição `coletado → em_analise` já está na lista branca (`states_exame.py:115`).
4. **Schema de entrada** (Pydantic):
   ```python
   class EmAnaliseIn(BaseModel):
       setor: Optional[str] = None   # work-area leve; NÃO modelar máquinas/técnicos (fronteira LIMS)
   ```
5. **Mutação:**
   - `UPDATE pedido_exame_itens SET status_item = 'em_analise' WHERE id = ?`.
   - Emitir evento `pedido_em_analise` no ledger com `dados_json = {"item_id": item_id, "setor": setor}`.
     - Reusar o helper de evento do módulo (`registrar_evento_ledger` + `instance_id` via
       `get_instance_id_conn(conn)` — mesmo padrão de `coletar`).
6. **Re-derivar** o status do pedido: `_recalcular_e_atualizar_status_pedido(conn, pedido_id)`
   (mesmo padrão do `coletar`, `pedidos_exame.py:1011`).
7. **Resposta (200):** `{"protocolo": ..., "item_id": ..., "status_item": "em_analise", "status_pedido": ...}`.

## Fronteira LIMS (guardrail)

**NÃO** modelar: analisador, técnico, fila de equipamento, lote. `setor` é texto livre opcional
para visibilidade operacional ("na bancada de bioquímica"). Se virar fila de máquina, virou LIMS —
outro produto.

## Critérios de aceite

- [ ] `POST .../itens/{id}/em-analise` leva `coletado → em_analise`.
- [ ] De `agendado` (ou outro estado) → 422 com mensagem.
- [ ] RBAC: dispensador/admin OK; paciente/prescritor-sem-custódia → 403.
- [ ] Evento `pedido_em_analise` gravado no ledger com `item_id` e `setor`.
- [ ] Status do pedido re-derivado corretamente (ex: pedido vira `em_analise`).
- [ ] Ledger permanece INSERT-only (nenhum UPDATE/DELETE em `pedido_exame_eventos`).
- [ ] `pytest` verde (gates-browser).

## Testes exigidos

- Caminho feliz: item `coletado` → POST → `em_analise` + evento presente.
- Transição inválida: item `agendado` → POST → 422.
- RBAC: paciente tentando → 403; dispensador de outra unidade (sem custódia) → 403.
- (Opcional) após `em-analise`, chamar `/resultado` leva a `resultado_disponivel` (confirma o
  encadeamento que o Ticket G usa).
