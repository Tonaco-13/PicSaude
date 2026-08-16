# Ticket C — RBAC do laudo estendido ao dispensador ⚠️ CORE

| Campo | Valor |
|---|---|
| Classe | `core` (RBAC) — **aprovado pelo arquiteto (Fabiano)** |
| Depende de | — |
| Esforço | Médio–alto (exige testes de ownership rigorosos) |

## Contexto

Decisão #5: o operador do `clinica.html` entra como `dispensador` (CNPJ da unidade), mas o laudo
exige um **Responsável Técnico** com CNS. Solução: o dispensador produz/assina/libera o laudo
**declarando o CNS do RT**; o RT continua sendo `autor_id`. O ownership do dispensador deriva da
**custódia do pedido vinculado** — **sem nova coluna, sem migration**.

> ⚠️ Este ticket toca RBAC (núcleo, AGENTS.md §10). Aprovação central já concedida. **Testes de
> ownership são obrigatórios** — uma unidade não pode operar laudo de outra.

## Princípio

- O `autor_id` do laudo é **sempre** o RT (resolvido via `cns_autor`).
- O dispensador (CNPJ) é **produtor em nome do RT** — fica registrado no evento `laudo_criado`
  (`produzido_por_cnpj`) e, na liberação, em `laudo_custodia (de=cnpj_prestador)`.
- Ownership do dispensador = **o laudo está vinculado a um pedido cuja custódia ATUAL é deste CNPJ**.

## Arquivo

- `backend/app/routers/laudos.py` — todos os endpoints abaixo.
- Testes: suite de laudos (mesmo padrão dos testes existentes de `criar`/`assinar`/`liberar`).

## Novo helper (sem schema change)

Reaproveitar a semântica de `_assert_dispensador_dono_pedido` (`pedidos_exame.py`) e da query
`_SQL_ITENS_DO_CNPJ` (`clinicas.py:108`) — a custódia ATUAL nível-pedido é o `MAX(id)` com
`item_id IS NULL` e `para = CNPJ`:

```python
def _assert_dispensador_dono_laudo_via_pedido(conn, laudo: dict, ident_cnpj: str) -> None:
    """O dispensador só opera laudo vinculado a pedido sob sua custódia ATUAL.
    Laudo sem pedido_id → 403 (só prescritor/admin operam laudo standalone)."""
    if not laudo.get("pedido_id"):
        _assert_or_403(False, codigo="laudo_sem_pedido_vinculado",
            mensagem="Laudo sem pedido vinculado: operação restrita ao prescritor/admin.")
    row = conn.execute(
        "SELECT para FROM pedido_exame_custodia "
        "WHERE pedido_id = ? AND item_id IS NULL AND id = ("
        "  SELECT MAX(id) FROM pedido_exame_custodia WHERE pedido_id = ? AND item_id IS NULL)",
        (laudo["pedido_id"], laudo["pedido_id"]),
    ).fetchone()
    _assert_or_403(
        row is not None and row["para"] == ident_cnpj,
        codigo="nao_e_dono_do_laudo",
        mensagem="Este laudo pertence a um pedido sob custódia de outra unidade.",
    )
```

## Endpoints a tocar

Adicionar `"dispensador"` ao `require_role` e ramo de ownership. Para cada um, o fluxo é:
`papel, ident = _normalizar_identidade_jwt(usuario)`; se `papel == "admin"` → bypass; se
`"prescritor"` → lógica atual; se `"dispensador"` → `_assert_dispensador_dono_laudo_via_pedido`.

| Endpoint (linha) | `require_role` atual | Mudança dispensador |
|---|---|---|
| `criar_laudo` (`:317`) | prescritor, admin | + dispensador. **Pula** o assert `ident == cns` (`:339`). **Exige** `pedido_protocolo` + asserta custódia do dispensador sobre **esse pedido** (`_assert_dispensador_dono_pedido`). Registra `"produzido_por_cnpj": ident` no evento `laudo_criado` (`:431`). |
| `assinar_laudo` (`:591`) | prescritor, admin | + dispensador via `_assert_dispensador_dono_laudo_via_pedido`. |
| `liberar_laudo` (`:651`) | prescritor, admin | + dispensador via-pedido; `cnpj_prestador` assume o `ident` do dispensador (ignora/sobrescreve o payload). |
| `encerrar_laudo` (`:819`), `cancelar_laudo` (`:866`) | prescritor, admin | + dispensador via-pedido. |
| `get_laudo` (`:538`), `pdf_laudo` (`:931`), `qr_laudo` (`:1017`) | prescritor, admin | + dispensador via-pedido (para o clínica ver status de ciência e pré-visualizar o laudo). |

### `criar_laudo` — detalhe do ramo dispensador

```python
papel, ident = _normalizar_identidade_jwt(usuario)
cns = normalize_cns(payload.cns_autor)
if papel == "prescritor":
    _assert_or_403(ident == cns, codigo="autor_mismatch", ...)
elif papel == "dispensador":
    # declara o RT; RT continua sendo o autor_id
    if not payload.pedido_protocolo:
        raise HTTPException(422, detail="dispensador deve vincular o laudo a um pedido (pedido_protocolo).")
    # a validação do pedido abaixo (laudos.py:360-379) já existe; adicionar:
    _assert_dispensador_dono_pedido(conn, pedido_id_resolvido, ident)
# admin: bypass (como hoje)
```
- No evento `laudo_criado` (`:431`), incluir `"produzido_por": papel` e, se dispensador,
  `"produzido_por_cnpj": ident`.

### `liberar_laudo` — detalhe do ramo dispensador

- `cnpj_prestador`: se `papel == "dispensador"`, usar `ident` (CNPJ da sessão) em vez do payload.
  Isso garante que a custódia registra a unidade autenticada, não um valor declarado.

## Inalterados (NÃO mexer)

- `ciencia_paciente` (`:708`) — paciente.
- `ciencia_prescritor` (`:763`) — prescritor **solicitante** (via pedido vinculado). O dispensador
  **não** dá ciência clínica; essa continua do prescritor solicitante.
- `criar_laudo_fisico` (`:454`) — fluxo físico (sem custódia); deixar como está.
- `_assert_autor_dono`, `_assert_solicitante`, `_assert_leitura_prescritor`, `_assert_paciente_dono`
  (`:212-275`) — preservar; o novo helper é **adicional**, não substituto.

## Guardrails

- **Sem nova coluna / sem migration.** Ownership via `pedido_exame_custodia` existente.
- **Laudo standalone** (`pedido_id IS NULL`) permanece restrito a prescritor/admin — o dispensador
  é negado (403). Isso é **correto**: laudo sem pedido não tem custódia de onde derivar ownership.
- Ledger INSERT-only. Eventos no vocabulário existente (`EVENTOS_LAUDO`).
- O RT é sempre o `autor_id`; o dispensador nunca se torna autor.

## Critérios de aceite

- [ ] Dispensador consegue `criar` laudo vinculado a pedido sob sua custódia (RT declarado).
- [ ] Dispensador consegue `assinar`, `liberar`, `encerrar`, `cancelar` laudo de pedido sob custódia.
- [ ] Dispensador consegue `GET`/`pdf`/`qr` desses laudos.
- [ ] Dispensador **não** consegue operar laudo de **outra** unidade → 403.
- [ ] Dispensador **não** consegue criar laudo **sem** `pedido_protocolo` → 422.
- [ ] Dispensador **não** consegue operar laudo **standalone** (sem pedido) → 403.
- [ ] Caminhos `prescritor` e `admin` **preservados** (testes existentes continuam verdes).
- [ ] `ciencia-paciente`/`ciencia-prescritor` **inalterados**.
- [ ] `autor_id` é sempre o RT (CNS declarado), nunca o CNPJ.
- [ ] Evento `laudo_criado` registra `produzido_por_cnpj` quando dispensador.
- [ ] `liberar` registra em `laudo_custodia` o CNPJ da sessão do dispensador.
- [ ] `pytest` verde (gates-browser).

## Testes exigidos

- Dispensador cria laudo (pedido sob custódia) → autor_id é o RT; evento tem `produzido_por_cnpj`.
- Dispensador assina/libera laudo próprio (OK) e de outra unidade (403).
- Dispensador cria laudo sem `pedido_protocolo` (422); laudo standalone (403).
- Prescritor cria/assina/libera laudo (caminho preservado).
- Admin bypassa (caminho preservado).
- `ciencia-paciente` por paciente e `ciencia-prescritor` pelo solicitante (inalterados).
