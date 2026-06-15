# TICKET-5C-BIS-A.1 — Coerência de domínio: `resultado_disponivel → encerrado` torna o passo de ciência (`encerrar`) inalcançável

| Campo | Valor |
|---|---|
| **Status** | Aberto (follow-up) — **não implementar sem revisão central** |
| **Classe provável** | `core` (toca máquina de estados / semântica de ciência de exames) — investigação primeiro |
| **Origem** | Descoberto pelo Engenheiro-executor no **gate PostgreSQL do TICKET-5C-BIS-A** (2026-05-31) |
| **Não bloqueia** | O 5C-BIS-A (ownership) — gate fechou 22/22; este achado é de **domínio**, ortogonal a autorização |
| **Commit de leitura** | `842c985` |
| **Corroboração independente** | A verificação formal exaustiva das máquinas de estado (paper CEBEB §VII, propriedade P2 "terminais são absorventes") **redescobriu este mesmo achado** por método distinto do gate PG (2026-06-15). Duas detecções independentes → alta confiança de que é real. |

> **Por que existe este ticket:** ao escrever o happy-flow de ownership do 5C-BIS-A, o teste tropeçou
> numa semântica de domínio **pré-existente**. Em vez de "consertar domínio dentro de um ticket de
> autorização" (mistura de classes), o teste foi reduzido ao escopo de ownership e a inconsistência
> registrada aqui. Decisão de governança de Fabiano (2026-05-31).

---

## §1 Evidência [VERIFICADO em `842c985`]

1. `resultado_disponivel` é **terminal de item**: está em `ESTADOS_TERMINAIS_ITEM_EXAME`
   ([states_exame.py:100-106](../../app/domain/states_exame.py)).

2. `derivar_status_pedido` ([states_exame.py:158-187](../../app/domain/states_exame.py)) **filtra**
   `resultado_disponivel` de `ativos_sem_resultado` (por ser terminal). Consequências:
   - Pedido com **todos** os itens em `resultado_disponivel` → cai no ramo "todos terminais" → retorna
     **`encerrado`**.
   - O status de pedido **`resultado_disponivel` nunca é produzido** — o `_PRIORIDADE_ESTADO` lista
     `resultado_disponivel`, mas ele já foi removido de `ativos_sem_resultado` antes do laço, então
     o laço nunca o alcança.

3. O endpoint `encerrar` ([pedidos_exame.py:1103](../../app/routers/pedidos_exame.py)) exige
   `pedido["status"] == "resultado_disponivel"`. Como esse status **nunca existe**, a precondição é
   **inalcançável** → `encerrar` retorna **sempre 422** → é, na prática, **endpoint morto**.

4. Isso **contradiz**:
   - `CLAUDE.md §7` (exames): *"resultado_disponivel: laudo pronto, aguarda ciência"* ≠ *"encerrado:
     ciência registrada"* — dois estados distintos com um passo de **ciência** entre eles.
   - A própria docstring do `encerrar` ([pedidos_exame.py:1082-1086](../../app/routers/pedidos_exame.py)):
     *"resultado_disponivel e encerrado NÃO são o mesmo estado"*.

---

## §2 Impacto

- **Ciência formal não acontece.** O `resultado` já leva o pedido direto a `encerrado`; o passo de
  ciência (`encerrar` → evento `pedido_encerrado`, `motivo: ciencia_registrada`) **nunca é exercido**.
  O ledger não registra a ciência como ato distinto — perde-se rastreabilidade que a doutrina do
  módulo previa.
- **Cobertura de teste bloqueada.** O `owner-2xx` de `encerrar` (e o **paciente-dono → 2xx** do §9 do
  5C-BIS-A) é **intestável** enquanto o pedido nunca chega a `resultado_disponivel`. Gap documentado,
  não esquecido — quando este ticket fechar, adicionar o teste de ciência (dono → 2xx) à suíte de
  ownership.

---

## §3 Opções (NÃO decididas — para Arquiteto/Conselheiro)

| Opção | Ideia | Risco |
|---|---|---|
| **A** | Remover `resultado_disponivel` de `ESTADOS_TERMINAIS_ITEM_EXAME` → o pedido passa a assumir `resultado_disponivel`; `encerrar` volta a ser alcançável. | Muda terminalidade/agregação — auditar **todos** os consumidores de `derivar_status_pedido` / `eh_terminal_item_exame`. |
| **B** | Assumir `resultado = fim` e **depreciar** `encerrar`. | Perde o passo de ciência — avaliar peso regulatório (CFM/laudo, contrarreferência futura). |
| **C** | Separar **terminalidade de item** da **agregação de pedido**: introduzir status de pedido `resultado_disponivel` explícito, distinto do item terminal. | Mais correto, mais invasivo — mexe na máquina de estados e no `CLAUDE.md §5a/§7`. |

> **Preferência da revisão CODEX (rodada 2, 2026-05-31):** **opção C** — pedido com
> todos os itens em `resultado_disponivel` deriva `resultado_disponivel`; só `encerrar`
> leva a `encerrado` + evento `pedido_encerrado`. Decisão final permanece `core`.

---

## §4 Governança

- **Classe provável `core`** (máquina de estados oficial — `domain/states_exame.py`). Por `CLAUDE.md §10`,
  exige **revisão central obrigatória**; qualquer mudança de estados atualiza também `CLAUDE.md §5a/§7`
  e o DDL.
- **Não implementar junto do 5C-BIS-A.** Este ticket é o registro honesto da inconsistência; a correção
  é trabalho próprio, sequenciado após decisão de Arquiteto/Conselheiro.

---

*Registrado em 2026-05-31 pelo Engenheiro-executor, a partir do gate PostgreSQL do 5C-BIS-A.*
