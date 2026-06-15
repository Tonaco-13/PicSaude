# TICKET-ESTORNO — Estorno de dispensação como objeto sanitário derivado

| Campo | Valor |
|---|---|
| **Status** | **Martelo de design cravado (Fabiano, 2026-06-15). Implementação adiada p/ pós-paper.** |
| **Classe** | **`core`** — máquina de estados + ledger + novo objeto derivado (CLAUDE.md §10). Revisão central. |
| **Origem** | Achado **SM2** da verificação formal (paper CEBEB §VII, P2 "terminais absorventes"). |
| **Não urgente** | Estorno **não está implementado** hoje — é só scaffolding. Nada quebra esperando. |

## §1 Decisão (martelo Fabiano)
O estorno (reversão de uma dispensação registrada) é uma **nova asserção clínica de um novo autor
e momento** → deve ser um **objeto sanitário derivado e imutável**, **não** uma transição de estado
que muta o item (`dispensado → estornado`). Fiel ao princípio §1 do CLAUDE.md (imutabilidade) e ao
padrão já provado de derivação (`origem_*_id`: laudo↔pedido_exame, contrarreferência↔encaminhamento,
correção↔prescrição).

## §2 Sanity-read [VERIFICADO 2026-06-15]
Estorno hoje é **só scaffolding**, sem operação:
- `estornado` é estado de item em `ESTADOS_ITEM` + `ESTADOS_TERMINAIS_ITEM` (states.py:41,105).
- transição `"dispensado": frozenset({"estornado"})` (states.py:117) + mapa
  `("dispensado","estornado"): "item_estornado"` (states.py:196).
- guards defensivos que listam `estornado` como bloqueado: custodia.py:203, hospitalares.py:233,
  tokens.py:615.
- **Nenhum endpoint `/estornar`.** Só `tests/test_states.py` exercita a transição (estrutural).

## §3 Mudança proposta

### 3a — Resolver o SM2 (a inconsistência formal)
Como o estorno passa a ser objeto derivado (não transição), o `dispensado` volta a ser **terminal
absorvente**:
- remover `"dispensado": frozenset({"estornado"})` → `frozenset()`;
- remover o mapa `("dispensado","estornado"): "item_estornado"`;
- `dispensado` deixa de ter saída → P2 satisfeita.

### 3b — Novo objeto derivado `estornos` (espelha contrarreferência/laudo)
```
estornos: id · protocolo (UUID) · origem_dispensacao_id (FK dispensacoes, NOT NULL)
          autor_* (quem estorna) · paciente_id · quantidade_estornada · motivo
          assinatura_hash · data_emissao · criado_em
estorno_eventos (ledger próprio) · evento `estorno_registrado` no ledger da prescrição
```
Endpoint `POST /dispensacoes/{id}/estornar` (ou similar): cria o objeto derivado; a `dispensacoes`
original permanece **imutável**.

## §4 Forks abertos (decidir no martelo de implementação)
1. **Estado do item após estorno:** o item permanece `dispensado` (a reversão vive só no objeto-estorno)
   **ou** reabre para `pendente`/`em_custodia` (re-dispensável)? — decisão clínica/contábil.
2. **`estornado` como estado de item:** manter (se o item muda de estado) ou **remover** (se o item fica
   `dispensado` e o estorno é puramente derivado)? Se remover, limpar os 3 guards (§2).
3. **Σ:** o estorno afeta a constraint `Σ dispensado ≤ prescrito`? (provavelmente devolve saldo).

## §5 Sequenciamento
- **Implementar pós-envio do paper.** Motivo: a §VII e o `robustness_eval.py` afirmam "**2** terminais
  não-absorventes"; corrigir o SM2 agora desincroniza o paper no meio do prazo. *(Alternativa, se
  decidirmos depois: corrigir SM2 **e** atualizar o paper para "2 achados; 1 resolvido por remodelagem
  em objeto derivado, 1 (A.1) rastreado" — narrativa até mais forte, mas com churn no prazo.)*
- SM1 (= TICKET-5C-BIS-A.1) é achado distinto e segue seu próprio rito.

---

*Martelo de design de Fabiano em 2026-06-15. Sanity-read confirma estorno não-implementado.
Implementação `core` adiada p/ pós-paper, com os forks do §4 a martelar.*
