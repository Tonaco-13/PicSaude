# TICKET-5C-BIS-F — Ownership em `custodia.py` (devolver + dispensar)

| Campo | Valor |
|---|---|
| **Status** | **Martelos cravados (Fabiano, 2026-06-14) — apto.** |
| **Classe** | **`core`** — cadeia de custódia (CLAUDE.md §10). Revisão central + merge só com go de Fabiano. |
| **Origem** | H5 da ultra-review 2026-06-14 (`TICKET-ULTRAREVIEW-2026-06-14-TRIAGEM`). |
| **Base** | `main` em `b297441`. |

## §1 Sanity-read — o que está coberto e o que não está
A varredura 5C-BIS (A–E) cobriu os objetos novos; o `custodia.py` (fluxo original da prescrição)
ficou de fora, mas **já tinha ownership próprio** num TICKET-5C anterior. Quadro dos 3 mutantes:

| Endpoint | Hoje | Veredito |
|---|---|---|
| `transferir` (346) | V6: prescritor-é-dono / dispensador-detém-custódia-ativa | ✅ coberto — **não toca** |
| `dispensar` (517) | V10: CNPJ declarado == JWT + token de item opcional | 🟡 parcial — **sem token, não exige custódia** |
| `devolver` (747) | só `require_role` | ❌ gap (H5) |

## §2 Decisões cravadas (Fabiano)
- **D1 — Escopo:** ~~fechar `devolver` **e** endurecer `dispensar`~~ → **revisto para `devolver`-só**
  (Fabiano, 2026-06-14). **Motivo:** endurecer o `dispensar` quebra o contrato de
  retrocompatibilidade nomeado `TestRetrocompat::test_dispensa_sem_token_funciona` — "dispensa sem
  token funciona" é comportamento **garantido**, não atalho de teste. Deprecá-lo é decisão de
  produto/regulatória própria (migração de ~17 testes + caminho de transição), **fora deste ticket**.
- **D2 — Regra:** espelhar o V6 do `transferir` — **dispensador → detém custódia ativa**;
  **prescritor → é o autor** da prescrição. `admin` bypass. Anti-leak **404 → 403 → 409**.

> **Follow-up registrado:** deprecação (ou não) da dispensação token-less direta — ticket próprio.

## §3 Especificação

### 2 helpers novos (sem refatorar o existente)
```python
def _dispensador_detem_custodia(conn, prescricao_id, item_id, cnpj) -> bool:
    # custódia ATIVA do dispensador: nível-prescrição (item_id IS NULL) OU nível-item.
    row = conn.execute(
        "SELECT 1 FROM prescricao_custodia "
        "WHERE prescricao_id = ? AND detentor_tipo = 'dispensador' AND detentor_id = ? "
        "AND encerrada_em IS NULL AND (item_id IS NULL OR item_id = ?) LIMIT 1",
        (prescricao_id, cnpj, item_id),
    ).fetchone()
    return row is not None

def _prescritor_e_autor(conn, prescricao_id, cns) -> bool:
    row = conn.execute(
        "SELECT 1 FROM prescricoes p JOIN prescritores pr ON pr.id = p.prescritor_id "
        "WHERE p.id = ? AND pr.cns = ? LIMIT 1",
        (prescricao_id, cns),
    ).fetchone()
    return row is not None
```

### `devolver_item` (747)
- `require_role("dispensador", "prescritor", "admin")` (+admin p/ bypass).
- Após o 404 do item, antes do 409 de status, inserir o assert (anti-leak):
  - `admin` → bypass.
  - `dispensador` → `_dispensador_detem_custodia(...)` senão **403** `nao_detem_custodia`.
  - `prescritor` → `_prescritor_e_autor(...)` senão **403** `nao_e_autor_da_prescricao`.

### ~~`dispensar_item` (517)~~ — **REMOVIDO do escopo** (ver §2 D1)
Endurecer o `dispensar` quebra o contrato `test_dispensa_sem_token_funciona`. Vira follow-up próprio.
`dispensar` permanece **inalterado** neste ticket.

## §4 NÃO toca
`transferir` (já coberto), schema/migration (nenhuma coluna muda), ledger, serialização/assinatura (R6),
fluxo paciente de `auth.py`.

## §5 Critérios de aceite (gate PG + SQLite)
1. **devolver** — dispensador que detém custódia → 200; dispensador sem custódia → 403; prescritor autor
   → 200; prescritor não-autor → 403; admin → 200; anti-leak (não-dono sobre item terminal → 403 antes do 409).
2. **Regressão:** suíte de custódia/dispensação existente verde (PG + SQLite); `transferir` e
   `dispensar` intactos (45 passed = baseline, confirmado).

---

*Sanity-read sobre `b297441` (verificou e corrigiu a estimativa inicial: transferir/dispensar já tinham
ownership). Martelos D1/D2 de Fabiano em 2026-06-14. Classe core — merge só com go.*
