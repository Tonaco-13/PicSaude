# TICKET-5C-BIS-E — Ownership mínimo na dispensação hospitalar (`hospitalares.py`)

| Campo | Valor |
|---|---|
| **Status** | **Martelo de escopo cravado (Fabiano) — apto para rodada 1 do CODEX.** |
| **Classe** | `module` — extensão do subdomínio dispensação + ownership de mutação clínica. Checklist NUCLEO + revisão 5C-BIS. **Não** é `core`: não toca ledger, estados, custódia, serialização/assinatura. |
| **Origem** | Varredura 5C-BIS (A·B·C·C.1·D fechados). E é a última peça clínica. |
| **Base** | `main` em `4ade8fa` (já com C.1 + C + D). |
| **Janela** | CODEX disponível ~2 dias — E é o menor módulo da varredura (1 endpoint, 1 assert). |

---

## §1 Problema

`hospitalares.py` tem **uma única superfície mutante**:

```
POST /prescricoes/{protocolo}/itens/{item_id}/dispensar/hospitalar   (dispensador|admin)
```

A assinatura é `_=Depends(require_role("dispensador", "admin"))` — **descarta o usuário**.
Não há captura de identidade nem ownership. Hoje, qualquer dispensador autenticado
registra dispensação hospitalar sob **qualquer `org_id`/`unidade_id` que ele declare no
payload** (`DispensarHospitalarIn.org_id` / `.unidade_id`).

**Vetor:** fraude de atribuição institucional — um dispensador do hospital X grava
dispensação na conta do hospital Y (`payload.org_id = "org-Y"`), poluindo o escopo
institucional de outra org com um registro clínico real (`dispensacoes` +
`dispensacoes_hospitalares` + evento no ledger + custódia hospitalar).

### A torção do E (por que não é cópia literal de C/D)
Em C/D o `org_id` vinha **do objeto** (agendamento/circulação) e o dispensador era
confrontado contra ele. No E o `org_id`/`unidade_id` são **auto-declarados no payload**.
Logo o ownership é **Padrão A puro (payload-vs-JWT)**: a org que o CNPJ do dispensador
resolve precisa bater com o `payload.org_id` declarado. Não há `org_id` em `prescricoes`
(§6b: rollout incremental — `prescricoes` ainda não migrada), então **não** se vincula a
prescrição a uma org; o ownership é a **autoconsistência institucional do dispensador**.

---

## §2 Decisões (martelo Fabiano)

1. **Enforcement só no nível da ORG.** Assert único: `org` resolvida do CNPJ do
   dispensador `== payload.org_id`. **`unidade_id` segue gravada como contexto
   declarado, sem verificação.** O vínculo dispensador↔unidade individual fica para a
   fase de **enforcement via JWT institucional** (§6b — "Enforcement via JWT (fase
   futura)"). Espelha C/D exatamente; não usa a tabela `unidades` neste ticket.
   *(Alternativa "org + unidade existe na org" — habilitada pelo C.1 — foi
   deliberadamente descartada: exigiria onboarding prévio das unidades e bloquearia
   dispensação hospitalar até o cadastro existir. Registrada como follow-up §7.)*
2. **Reusar o resolver provado de C/D** (`_org_id_do_dispensador`, versão pós-C.1 com
   `ativo = true`), **copiado local** em `hospitalares.py` — sem refatorar o código que
   já roda em C/D (§"não refatore sem autorização"). A duplicação tripla
   (agendamentos · circulacao_diagnostica · hospitalares) vira follow-up de extração
   para `helpers.py` (§7), fora deste ticket.
3. **`admin` faz bypass** do assert (igual a toda a varredura).
4. **Ledger intocado.** O `ator_id` do evento permanece `payload.unidade_id` (semântica
   atual). Trocar para o CNPJ do dispensador é mudança de semântica de ledger (`core`) —
   **fora de escopo**; registrar como observação (§7), não alterar aqui.

---

## §3 Especificação

### Captura de identidade
- Trocar `_=Depends(require_role("dispensador", "admin"))` por
  `usuario=Depends(require_role("dispensador", "admin"))`.
- Derivar `(papel, ident) = _normalizar_identidade_jwt(usuario)` (helper global). Para
  dispensador, `ident` = CNPJ normalizado (remove máscara e sufixo `.0`).

### Resolver institucional (copiar local, idêntico ao pós-C.1 de C/D)
```python
def _org_id_do_dispensador(conn, cnpj_norm: str) -> str | None:
    # prestadores.cnpj (gravado cru) → org_id. Normaliza READ-SIDE; só ativo;
    # org única (0 ou >1 ambíguo → None → 403). Fail-closed se schema ausente.
    if len(cnpj_norm) != 14:
        return None
    try:
        rows = conn.execute(
            "SELECT org_id, cnpj FROM prestadores WHERE cnpj IS NOT NULL AND ativo = true"
        ).fetchall()
    except Exception:
        return None
    orgs = {r["org_id"] for r in rows if normalize_cnpj(r["cnpj"]) == cnpj_norm}
    return orgs.pop() if len(orgs) == 1 else None
```
> ⚠️ Usar `ativo = true` (Boolean pós-C.1) — **nunca** `ativo = 1` (daria
> DatatypeMismatch na PG e fail-closed silencioso permanente; foi o bug pego no C).

### O assert (Padrão A) + bypass admin
```python
if papel != "admin":
    org_disp = _org_id_do_dispensador(conn, ident)
    _assert_or_403(
        org_disp is not None and org_disp == payload.org_id,
        codigo="dispensador_de_outra_org",
        mensagem="Dispensação sob org distinta da do dispensador.",
    )
```
- `org_disp is None` (sem prestador / CNPJ inválido / ambíguo / schema ausente) → **403
  fail-closed**.
- `org_disp != payload.org_id` → **403 cross-org**.

### Ordenação anti-leak (404 → 403 → 409 → 422)
O assert institucional **não depende da prescrição** (é sobre o dispensador), mas, pela
convenção 5C-BIS, **não 403 sobre recurso inexistente**. Sequência:

```
1. _get_prescricao  → 404 se não existe
2. ASSERT institucional (org)  → 403            ← inserir AQUI, logo após o 404
3. status terminal da prescrição → 409
4. item inexistente → 404
5. item bloqueado → 409
6. saldo insuficiente → 422
```
→ um dispensador de outra org recebe **403 antes** de qualquer 409/422 (não vaza estado
da prescrição, existência de item, nem saldo a quem não é da org).

### Guardrail §6b
A leitura de `prestadores` no resolver é leitura institucional — manter o comentário
inline justificando (já presente no padrão C/D). As queries em
`dispensacoes_hospitalares` já filtram `org_id` (inalteradas).

---

## §4 Escopo de arquivos
| Arquivo | Mudança |
|---|---|
| `app/routers/hospitalares.py` | captura `usuario`; resolver local; 1 assert; reordenar o 403 p/ logo após o 404 da prescrição |
| `tests/integration/test_hospitalares_autorizacao.py` | **criar** — gate PG (§5) |

**NÃO toca:** ledger / `prescricao_eventos`, máquina de estados, `prescricao_custodia`
(custódia hospitalar inalterada), `dispensacoes` / `dispensacoes_hospitalares` (schema),
serialização/assinatura (R6 não se aplica), `unidades` (decisão §2.1).

---

## §5 Critérios de aceite (gate PG)
Setup: emitir uma prescrição digital `pendente` com ≥1 item (POST `/prescricoes`); semear
prestador (`org_id` + `cnpj`) via CRUD `/prestadores`. Casos:

1. **Positivo** — dispensador cujo CNPJ resolve p/ `payload.org_id` correto → **201**;
   `dispensacoes` + `dispensacoes_hospitalares` recebem 1 linha cada (Σ ≤ prescrito).
2. **Cross-org** — dispensador resolve p/ `org-X`, `payload.org_id = "org-Y"` → **403**
   (`dispensador_de_outra_org`); **zero** linhas gravadas (rollback).
3. **Fail-closed** — dispensador **sem** prestador cadastrado → **403**.
4. **CNPJ mascarado** no cadastro, limpo no JWT → resolve (normalize read-side) → **201**.
5. **admin bypass** → **201** independentemente de prestador.
6. **Anti-leak** — dispensador de outra org sobre prescrição **terminal** (ou item sem
   saldo) → **403 institucional ANTES** do 409/422.
7. **Convergência** — suíte SQLite hospitalar existente (`test_*hospital*`,
   `test_circulacao_ticket*` se tocar) continua verde.

CI: a seleção do gate (`-k "autorizacao or institucional or test_pedidos_exame"`) deve
pegar o novo arquivo pelo sufixo `autorizacao`.

---

## §6 O que NÃO toca (invariantes preservados)
- Σ `quantidade_dispensada` ≤ `prescricao_itens.quantidade` (inalterado).
- Prescrição imutável após emissão; ledger append-only.
- Custódia hospitalar (`prescritor → farmacia_hospitalar → … → paciente`) inalterada.
- Papel RBAC único `dispensador` (sem `dispensador_hospitalar`).

---

## §7 Follow-ups (fora de escopo)
- **Extração do resolver** `_org_id_do_dispensador` para `helpers.py` (hoje triplicado:
  agendamentos · circulacao_diagnostica · hospitalares). Cleanup, não-bloqueante.
- **Enforcement de `unidade_id`** (payload.unidade ∈ unidades da org, via tabela
  `unidades` do C.1) — quando o onboarding institucional / JWT com unidade existir (§6b).
- **`ator_id` do evento hospitalar** = CNPJ do dispensador em vez de `unidade_id`
  (mudança de semântica de ledger → ticket `core` próprio).
- **`cnpj_estabelecimento` auto-declarado** no registro base `dispensacoes`
  (`cnpj_base = payload.cnpj_estabelecimento or payload.org_id`) — outra auto-asserção;
  avaliar consistência com a org resolvida em ticket futuro.

---

*Sanity-read sobre `4ade8fa`. Martelo de escopo (só org, espelho de C/D) cravado por
Fabiano em 2026-06-08. Apto para rodada 1 do CODEX.*
