# TICKET-5C-BIS-C — Autorização mínima de ownership em `agendamentos.py`

| Campo | Valor |
|---|---|
| **Status** | **CODEX rodada 1 integrada (martelos P1 + D1–D6) — apta para implementação.** |
| **Classe** | `module` (estende agendamentos com semântica de autorização) |
| **Volume estimado** | ~260 linhas (código + testes), 8 endpoints |
| **Base da leitura** | `main` em `c6529e6` |
| **Predecessores** | 5C-BIS-A (pedidos_exame) · 5C-BIS-B (laudos) · ADR-002 |

> **[VERIFICADO]** = lido em `c6529e6`. **[DECIDIDO]** = martelo CODEX rodada 1.

---

## §1 Contexto e complexidade central
Terceiro da série (após A/B). 8 endpoints; hoje **6 descartam o usuário** e **2 (`criar`, `remarcar`) capturam `usuario` mas não validam ownership** (bug ativo, ADR-002 §1.1).

**O que torna C diferente:** o **prestador** (role `dispensador`) é **institucional** — liga-se ao agendamento por **`org_id`**, não por CNPJ direto. O JWT do dispensador traz CNPJ; a ponte é `prestadores.cnpj → org_id` (two-hop "Helper-3-like"). Agendamento é **objeto leve**: sem custódia, sem assinatura → anti-escopo R6 trivial.

## §2 Realidade do schema [VERIFICADO]
- `agendamentos`: FKs `pedido_id`, `paciente_id` + `org_id`/`unidade_id` (Text NOT NULL) + `criado_por` (CNS/CPF, **informativo**). Sem cns/cpf → JOIN.
- `prestadores`: `org_id` (UNIQUE), `cnpj` (**nullable**, gravado stripped mas **não digit-normalizado**, `prestadores.py:103`), `ativo` (Integer). `unidades`: `prestador_id`, `unidade_id`, `ativo`.

## §3 Escopo de arquivos
| Arquivo | Mudança |
|---|---|
| `app/routers/agendamentos.py` | Ownership inline nos **8/8** endpoints; 4 resolvers + asserts locais |
| `tests/integration/test_agendamentos_autorizacao.py` | **Criar** — suíte de ownership |

**NÃO toca:** `helpers.py` (globais já em `main`), `states_agendamento.py`, `prestadores.py` (normalizar-on-write é **follow-up**, §D2), pedido/laudo.

## §4 Invariantes
1. Backend é fonte de verdade; ownership por JWT × banco.
2. Ledger imutável; 403 antes de qualquer escrita.
3. Estados só de `states_agendamento.py`.
4. **`require_role` preservado** [VERIFICADO].
5. `criado_por` é informativo — **nunca** chave de ownership (§D6).
6. Contrato de erro `{codigo, mensagem}` em PT.

## §5 Mapa dos 8 endpoints [VERIFICADO]
| # | Rota | require_role | Ownership | Sobre |
|---|---|---|---|---|
| 1 | POST `/agendamentos` (criar) | prescritor,paciente,admin,dispensador | prescritor(pedido) ∨ paciente(pedido) ∨ dispensador(org==`payload.org_id`) | PEDIDO |
| 2 | GET `/agendamentos/{p}` | prescritor,paciente,admin,dispensador | prescritor ∨ paciente ∨ dispensador(org==ag.org_id) | agendamento |
| 3 | GET `/pedidos-exame/{p}/agendamentos` (listar) | prescritor,paciente,admin,dispensador | prescritor(pedido) ∨ paciente(pedido); **dispensador → 403** (§D4) | PEDIDO |
| 4 | POST `/{p}/confirmar` | prescritor,admin,dispensador | prescritor ∨ dispensador(org) | agendamento |
| 5 | POST `/{p}/realizar` | prescritor,admin,dispensador | prescritor ∨ dispensador(org) | agendamento |
| 6 | POST `/{p}/cancelar` | prescritor,paciente,admin,dispensador | prescritor ∨ paciente ∨ dispensador(org) | agendamento |
| 7 | POST `/{p}/nao-compareceu` | prescritor,admin | prescritor | agendamento |
| 8 | POST `/{p}/remarcar` | prescritor,paciente,admin | prescritor ∨ paciente | agendamento; sem dispensador |

`admin` bypassa em todos.

## §6 Helpers (§D + "helper shape")
**Globais (reuso):** `_assert_or_403`, `_normalizar_identidade_jwt`.

**Locais — 4 resolvers + asserts:**
```python
def _cns_prescritor_de_pedido(conn, pedido_id):   # pedido → prescritores.cns
def _cpf_paciente_de_pedido(conn, pedido_id):     # pedido → pacientes.cpf
def _org_id_ag(conn, protocolo):                  # agendamentos.org_id (ou usar ag["org_id"])

def _org_id_do_dispensador(conn, cnpj_norm):      # two-hop, fail-closed (§D1/D2)
    # cnpj de prestadores é cru → normalizar READ-SIDE; ativo=1; org único.
    rows = conn.execute(
        "SELECT org_id, cnpj FROM prestadores WHERE cnpj IS NOT NULL AND ativo = 1"
    ).fetchall()
    orgs = {r["org_id"] for r in rows if normalize_cnpj(r["cnpj"]) == cnpj_norm}
    return orgs.pop() if len(orgs) == 1 else None   # 0 ou >1 (ambíguo) → None → 403
```
Asserts (deny explícito para papel sem ramo):
```python
def _assert_ag_owner(conn, ag, papel, ident):       # endpoints 2,4,5,6,7,8
    if papel == "prescritor":  cond = ident == _cns_prescritor_de_pedido(conn, ag["pedido_id"])
    elif papel == "paciente":  cond = ident == _cpf_paciente_de_pedido(conn, ag["pedido_id"])
    elif papel == "dispensador":
        org = _org_id_do_dispensador(conn, ident)
        cond = org is not None and org == ag["org_id"]
    else: cond = False                              # papel sem ramo → deny
    _assert_or_403(cond, "nao_e_dono_do_agendamento", "<msg por papel>")

def _assert_pedido_owner_criar(conn, pedido, papel, ident, payload_org):  # endpoint 1
    if papel == "prescritor":  cond = ident == _cns_prescritor_de_pedido(conn, pedido["id"])
    elif papel == "paciente":  cond = ident == _cpf_paciente_de_pedido(conn, pedido["id"])
    elif papel == "dispensador":
        org = _org_id_do_dispensador(conn, ident); cond = org is not None and org == payload_org
    else: cond = False
    _assert_or_403(cond, "nao_e_dono_do_pedido", "<msg>")
# listar (3): só prescritor/paciente do pedido; dispensador → deny.
```

## §7 Ordenação (P1 anti-leak) [DECIDIDO]
**Não usar `_transicionar()` antes do ownership.** Hoje ele faz 404 + valida transição 409. A implementação deve, em `confirmar/realizar/cancelar/nao-compareceu`:
```
ag = _get_agendamento_ou_404(conn, protocolo)   # 404
papel, ident = _normalizar_identidade_jwt(usuario)
if papel != "admin": _assert_ag_owner(conn, ag, papel, ident)   # 403
_transicionar(conn, protocolo, novo, agora)     # 409 (transição) + update
```
(Re-fetch do `_transicionar` é redundância aceitável; ou refatorar para receber `ag`.) No `criar`: pedido 404 → ownership 403 → duplicidade/status 409. No `remarcar`: agendamento 404 → ownership 403 → regra de estado 409.

## §8 Decisões — RESOLVIDAS (CODEX rodada 1)
- **§D1 [DECIDIDO]** dispensador **fail-closed 403** via `prestadores.cnpj → org_id`; ownership **org-level** (JWT não carrega `unidade_id`). CNPJ ausente/NULL/inativo/ambíguo (→ >1 org) → 403.
- **§D2 [DECIDIDO]** normalizar **read-side** no helper (`normalize_cnpj(row["cnpj"])`). Normalizar-on-write em `prestadores.py` é **follow-up** separado.
- **§D3 [DECIDIDO]** `criar`: prescritor/paciente devem ser donos do **pedido**; dispensador deve resolver para **`payload.org_id`**; admin bypassa. `remarcar`: prescritor/paciente donos do agendamento (via pedido); admin bypassa; **sem** dispensador (RBAC não inclui).
- **§D4 [DECIDIDO]** `listar` por pedido: **dispensador → 403** (pedido não tem `org_id`; lista histórico inteiro).
- **§D5 [DECIDIDO]** validar existência de `org_id/unidade_id` = integridade institucional, **não** ownership → follow-up (exceto a resolução do dispensador, que exige prestador ativo).
- **§D6 [DECIDIDO]** `criado_por` é só informativo; fora do ownership.

## §9 Critérios de aceite (testes PG — `test_agendamentos_autorizacao.py`)
- **Dispensador:** CNPJ **não cadastrado** em prestadores → 403; CNPJ **mascarado** no banco e/ou JWT, mesmo prestador → 2xx (prova da normalização read-side); CNPJ que **normaliza para ≥2 orgs distintas** → 403; prestador **inativo** → 403.
- **criar:** por prescritor/paciente **donos do pedido** → 201; por dispensador cujo org == `payload.org_id` → 201; por **não-dono** (prescritor/paciente de outro pedido, ou dispensador de outra org) → **403 + rollback**.
- **listar por pedido:** prescritor/paciente do pedido → 200; **dispensador → 403**.
- **transições (confirmar/realizar/cancelar/nao-compareceu):** não-dono → 403; dono (prescritor ∨ dispensador-org ∨ paciente onde aplicável) → 2xx.
- **remarcar:** não-dono → 403; dono → 201.
- **admin:** 2xx sem ownership em todos.
- **Anti-leak (§7):** não-dono recebe **403 antes do 409** de estado.

## §10 Verificação automatizada
```bash
grep -nE '_=Depends\(require_role' backend/app/routers/agendamentos.py   # → VAZIO
grep -c '_normalizar_identidade_jwt(usuario)' backend/app/routers/agendamentos.py  # → 8
grep -nE 'def _(cns_prescritor_de_pedido|cpf_paciente_de_pedido|org_id_ag|org_id_do_dispensador)' backend/app/routers/agendamentos.py  # → 4
DATABASE_URL=postgresql://.../picsaude_test pytest tests/integration/test_agendamentos_autorizacao.py -q
```

## §11 Follow-ups (fora de escopo)
- Normalizar `cnpj` **on-write** em `prestadores.py` (§D2).
- Validar existência institucional de `org_id`/`unidade_id` no `criar` (§D5).

---

*Rodada 0 + martelos da CODEX rodada 1 integrados em 2026-06-03 sobre `c6529e6`. **Apta para implementação.***
