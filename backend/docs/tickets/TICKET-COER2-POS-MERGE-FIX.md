# TICKET-COER2-POS-MERGE-FIX — Transição `devolvido_paciente → devolvido_prescritor`

**Classe:** `core` (máquina de estados de item + `auth.py::devolver_prescritor` + CLAUDE.md §5a/§5b)
**Ratificado por Fabiano / Conselheiro:** 2026-07-23 — Opção 1; portão de core **VERDE** (inclui o site extra de custódia)
**Origem:** Diagnóstico TICKET-COER2-POS-MERGE (2026-07-23) — hipótese A+B confirmada com experimento controlado
**Pai:** [TICKET-COERENCIA-DEVOLUCOES-2](TICKET-COERENCIA-DEVOLUCOES-2.md)

> Registro de implementação: causa raiz, o que mudou, a auditoria de exaustividade
> (Ajuste A) e a evidência de aceite (vermelho-antes-de-verde).

---

## Causa raiz (confirmada em código + banco ao vivo)

O COER-2 (PR #120) modelou a volta ao médico no **nível prescrição** (`transferida_prescritor`),
mas **não no nível item** para o caminho composto "voltou ao paciente e depois volta ao médico":

- `auth.py::devolver_prescritor` só virava itens `WHERE status_item = 'pendente'`. Um item em
  `devolvido_paciente` (rescaldo de estorno + devolução ao paciente) ficava intocado.
- `states.py` **não tinha** a transição `devolvido_paciente → devolvido_prescritor`.
- O painel do prescritor (`prescritor.py`, `tem_devolucao`) só enxerga item-level `devolvido_prescritor`.

Resultado: prescrição ia para `transferida_prescritor` (saía da carteira do cidadão) mas o item
ficava em `devolvido_paciente` — **contraditório e invisível** no painel de correções. Eco de
"dupla posse" no nível de estado. Confirmado ao vivo em `picsaude.com.br`: 5 receitas em
`transferida_prescritor` com item `devolvido_paciente` e `tem_devolucao=False`.

---

## O que mudou

1. **`domain/states.py`** — `TRANSICOES_ITEM["devolvido_paciente"]` += `devolvido_prescritor`;
   `EVENTOS_ITEM[("devolvido_paciente","devolvido_prescritor")] = "item_devolvido_prescritor"`;
   nota de governança citando este ticket.
2. **`routers/auth.py::devolver_prescritor`** — `WHERE status_item IN ('pendente', 'devolvido_paciente')`.
3. **`routers/auth.py::devolver_prescritor` (site EXTRA, ver Ajuste A)** — `_fechar_custodia_ativa`
   por item ao virar terminal, para não deixar custódia de item órfã.
4. **`CLAUDE.md` §5a/§5b** — transição documentada + invariante de coerência executável.
5. **Testes** — `tests/browser/test_coer2_fix.py` (novo, 6 testes); `tests/test_states.py` (+2 params).

---

## Ajuste A — auditoria de exaustividade de caminhos (rodada ANTES do código)

`rg -n "devolvido_prescritor"` + `rg -n "para.*prescritor"` sobre `routers/` e `domain/`.
**2 caminhos** transicionam item → `devolvido_prescritor`:

| Caminho | Âncora | Estados de origem aceitos | Ação |
|---|---|---|---|
| `auth.py::devolver_prescritor` (cidadão→médico) | `auth.py:300` | `pendente` **apenas** | **corrigido** → `pendente` + `devolvido_paciente` |
| `custodia.py::devolver_item(para=prescritor)` (dispensador→médico) | `custodia.py:1084` | qualquer não-terminal c/ saldo>0 (**block-guard**) | **já cobre** `devolvido_paciente` — sem mudança |

**Defeito adjacente que a auditoria destapou (fora do escopo do esboço, aprovado pelo Conselheiro):**
`auth.py::devolver_prescritor` **nunca fechava a custódia de ITEM**. Um item `devolvido_paciente`
carrega custódia de item ativa no nome do paciente (aberta em `custodia.py::devolver_item para=paciente`).
Ao virar terminal `devolvido_prescritor` sem fechá-la, ela ficava **órfã** — *item terminal + custódia
ativa* = a mesma dupla posse que o COER-2 mata. Corrigido com `_fechar_custodia_ativa(conn, pid, item_id)`
no loop, **espelhando** `custodia.py::devolver_item` (`para=prescritor` fecha e NÃO reabre: item
terminal aguarda prescrição derivada). No caminho fresh (item `pendente`) não há custódia de item →
no-op seguro (0 linhas). O `_fechar_custodia_ativa` faz `UPDATE` em `prescricao_custodia`, **não** no
ledger — **§2 preservado** (zero `UPDATE/DELETE` em `prescricao_eventos`).

---

## Evidência de aceite (vermelho-antes-de-verde)

- **`tests/browser/test_coer2_fix.py`** (6 testes, SQLite efêmero): **6/6 verdes** com o fix.
  **Prova anti-vácuo:** com `git stash` do fix, os **4 testes não-fresh FALHAM** — inclusive o guarda,
  que captura literalmente `prescrição … em transferida_prescritor com item devolvido_paciente`. Com o
  fix, passam. Régua vermelho→verde satisfeita.
- **COER-1..12 contra PostgreSQL efêmero:** **26 passed** (inclui `test_coer10_devolver_prescritor…`
  e o guarda da constraint de unicidade). Zero regressão.
- **Regressão unit:** 227 passed; a única falha (`test_demo_info_disponivel_com_flag`) é **pré-existente**
  (falha idêntica com o fix stashado; persona `dispensador` duplicada, sem relação com o fix).

---

## §3.4 — Reset dos artefatos da demo (CORRIGIDO — o esboço mentia)

> O esboço do ticket afirmava: *"re-rodar `seed_demo.py` no Render limpa os 5 artefatos"*. **FALSO.**

`seed_demo.py` é **UPSERT idempotente** (SELECT → UPDATE-ou-INSERT das personas canônicas); **não
apaga** prescrições/custódias/dispensações criadas via API. E `predeploy.sh` roda apenas
`alembic upgrade head` + `python3 seed_demo.py` — **sem `rm` nem `drop`**. No PostgreSQL do Render o
**banco demo persiste entre deploys**, então os artefatos contraditórios sobrevivem ao re-seed.

**A verdade:** limpar os artefatos exige um **rebuild real do banco demo** (drop schema → `alembic
upgrade head` → `seed_demo.py`) — ação de **ops**, martelo do Fabiano, **depois** do merge.
Respeita §2 (sem data-fix retroativo no ledger). Vale por serem **artefatos de TESTE** (5 pré-existentes
+ `FRESH-REPRO-COER2` / `NONFRESH-REPRO-COER2` criados ao reproduzir o diagnóstico). **Não bloqueia este PR.**

Localmente o rebuild é `rm` do SQLite + migrate + seed (ver `rebuild-banco-demo`); no Render, drop de schema.

---

## Invariantes tocados (checklist)

- **§1/§2** — ledger só recebe `INSERT` (`item_devolvido_prescritor`, `custodia_transferida`). Zero mutação.
- **§2 (vocabulário)** — `item_devolvido_prescritor` já existe; passa a ser emitido num novo caminho.
- **§5a/§5b** — transição nova em `TRANSICOES_ITEM` + `EVENTOS_ITEM`, documentada no CLAUDE.md.
- **COER-2 (choke-point)** — fecha o caminho que faltava; não abre exceção. O `_fechar_custodia_ativa`
  é fecha-sem-reabrir (não é transferência à mão — o guarda `test_coer2_chokepoint_guard` continua verde).
