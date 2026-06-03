# TICKET-5C-BIS-B — Autorização mínima de ownership em `laudos.py`

| Campo | Valor |
|---|---|
| **Status** | Rodada 0 (spec) — martelos da revisão CODEX integrados; aguarda CODEX rodada 1 antes de qualquer código |
| **Classe** | `module` (estende o módulo de laudos com semântica de autorização) |
| **Volume estimado** | ~300 linhas (código + testes), 12 endpoints |
| **Base da leitura** | `main` em `1b68ad7` (leitura de sanidade do Engenheiro-executor) |
| **Predecessores** | TICKET-5C-BIS-A (`pedidos_exame`, mergeado) · ADR-002 (helpers) |
| **Decisões de design** | Fechadas na revisão CODEX (ver §8) |

> **Convenção de honestidade:** **[VERIFICADO]** = lido no código em `1b68ad7`.
> **[DECIDIDO]** = martelo da revisão CODEX (§8). Sem **[PROPOSTA]** pendente nesta spec.

---

## §1 Contexto e a complexidade central
Segundo ticket da série A–E (ADR-002). Fecha o subdomínio **laudos** — 12 endpoints, hoje **11 descartam o usuário** (`_=Depends`) e **1 (`ciencia-paciente`) captura mas não valida** (bug ativo, ADR-002 §1.1).

**O que torna laudos diferente do A:** o papel `prescritor` cobre **dois atores legítimos distintos**:
- **Autor / responsável técnico** — produziu o laudo (`laudos.autor_id → prescritores`). Dono de assinar/liberar/cancelar/encerrar.
- **Prescritor solicitante** — emitiu o pedido vinculado (`laudo.pedido_id → pedidos_exame.prescritor_id → prescritores`). Dono de `ciencia-prescritor`.
- **Leitura** (GET/pdf/qr/custodia): **ambos** leem.

Não há `dispensador` em nenhum endpoint de laudo → **não há branch de ownership por CNPJ** (mais simples que o A nesse eixo). [VERIFICADO]

## §2 Cláusula anti-escopo R6 (inegociável)
`assinar` aqui é **transição de estado** (`em_producao → assinado`), **não** assinatura PAdES. Este ticket **não toca**: `app/domain/documento_canonico.py`, `app/domain/assinatura.py`, `app/domain/pdf_laudo.py`, `_calcular_hash` de `laudos.py`, nem qualquer fluxo ICP/gov.br. Ownership opera sobre identidade JWT × registro no banco. Se parecer precisar mexer em serialização/assinatura, **pare e suba ao Conselheiro**.

## §3 Escopo de arquivos
| Arquivo | Mudança |
|---|---|
| `app/routers/laudos.py` | Ownership inline nos **12/12** endpoints (`_=`/`usuario=` → `usuario=`); 3 helpers locais; guards de `origem_laudo_id` e `pedido_protocolo` na criação |
| `tests/integration/test_laudos_autorizacao.py` | **Criar** — suíte de ownership (mirror do A) |

**NÃO toca:** `helpers.py` (helpers globais já existem, mergeados do A), `states_laudo.py` (estados intocados), `prescricoes.py`/`pedidos_exame.py`, tudo do §2.

## §4 Invariantes
1. Backend é fonte de verdade — ownership por JWT × banco, nunca por payload.
2. Ledger imutável — 403 roda antes de qualquer escrita; acesso negado não gera evento.
3. Estados só de `states_laudo.py` — nenhum estado/transição novo.
4. **Conjunto de papéis (`require_role`) preservado** [VERIFICADO] — só adiciona ownership dentro do conjunto já permitido.
5. **Doutrina autor ≠ solicitante** — responsável técnico e destinatário clínico são atores distintos; nunca usar um como fallback do outro (§8.1).
6. Contrato de erro `{codigo, mensagem}` em PT (estilo 5C; reuso de `nao_e_dono_do_laudo` / `autor_mismatch`).

## §5 Mapa real dos 12 endpoints [VERIFICADO em `1b68ad7`]
| # | Rota | require_role | Ownership | Padrão |
|---|---|---|---|---|
| 1 | POST `` (criar) | prescritor,admin | `cns_autor` payload == JWT (admin bypassa) | A |
| 2 | POST `/fisica` | prescritor,admin | idem | A |
| 3 | GET `/{p}` | prescritor,admin | autor **OU** solicitante | B/D |
| 4 | GET `/{p}/custodia` | prescritor,admin,paciente | autor∨solicitante · paciente CPF | D |
| 5 | POST `/{p}/assinar` | prescritor,admin | **autor** | E |
| 6 | POST `/{p}/liberar` | prescritor,admin | **autor** | E |
| 7 | POST `/{p}/ciencia-paciente` | paciente,admin | **paciente CPF** | E |
| 8 | POST `/{p}/ciencia-prescritor` | prescritor,admin | **solicitante** (sem pedido → 403) | E |
| 9 | POST `/{p}/cancelar` | prescritor,admin | **autor** | E |
| 10 | POST `/{p}/encerrar` | prescritor,admin | **autor** | E |
| 11 | GET `/{p}/pdf` | prescritor,admin,paciente | autor∨solicitante · paciente CPF | C/D |
| 12 | GET `/{p}/qr` | prescritor,admin,paciente | autor∨solicitante · paciente CPF | B/D |

`laudos` não tem `cns_autor`/`cpf_paciente` — só FKs (`autor_id`, `paciente_id`, `pedido_id`). Ownership exige JOIN. [VERIFICADO]

## §6 Helpers
**Globais (já em `main`, reuso):** `_assert_or_403`, `_normalizar_identidade_jwt`.

**Locais em `laudos.py` (§7.0) — resolução das 3 chaves + asserts:**
```python
def _cns_autor(conn, protocolo):          # JOIN prescritores via autor_id → cns
def _cns_solicitante(conn, protocolo):    # JOIN pedidos_exame via pedido_id → prescritores.cns (None se sem pedido)
def _cpf_paciente_laudo(conn, protocolo): # JOIN pacientes via paciente_id → cpf

def _assert_autor_dono(conn, protocolo, ident):
    _assert_or_403(_cns_autor(conn, protocolo) == ident,
                   "nao_e_dono_do_laudo", "Este laudo foi emitido por outro responsável técnico.")

def _assert_solicitante(conn, protocolo, ident):
    cns = _cns_solicitante(conn, protocolo)
    _assert_or_403(cns is not None and cns == ident,
                   "nao_e_dono_do_laudo", "Apenas o prescritor solicitante pode dar ciência clínica.")

def _assert_leitura_prescritor(conn, protocolo, ident):   # autor OU solicitante
    _assert_or_403(ident in {_cns_autor(conn, protocolo), _cns_solicitante(conn, protocolo)} - {None},
                   "nao_e_dono_do_laudo", "Este laudo pertence a outro prescritor/serviço.")

def _assert_paciente_dono(conn, protocolo, ident):
    _assert_or_403(_cpf_paciente_laudo(conn, protocolo) == ident,
                   "nao_e_dono_do_laudo", "Este laudo pertence a outro paciente.")
```

## §7 Especificação por endpoint
**Ordenação (anti-leak #52):** 404 → 403 → 422 de estado, em todos os endpoints de fluxo.

### §7.1 Padrão A — criar (1) e fisica (2)
`usuario=Depends(require_role("prescritor","admin"))`. **admin bypassa o `cns_autor==JWT`, mas NÃO bypassa invariantes de domínio** (§8.3):
```python
papel, ident = _normalizar_identidade_jwt(usuario)
cns_autor = normalize_cns(payload.cns_autor)
if papel != "admin":
    _assert_or_403(ident == cns_autor, "autor_mismatch",
                   "CNS do autor não coincide com o responsável técnico autenticado.")
# ... dentro do get_tx, ANTES de inserir o laudo:
# (a) origem (correcao) — DECISÃO §8.3: origem.autor.cns == cns_autor (mesmo p/ admin)
if payload.origem_laudo_id is not None:
    origem_cns = conn.execute(
        "SELECT pr.cns FROM laudos l JOIN prescritores pr ON pr.id=l.autor_id WHERE l.id=?",
        (payload.origem_laudo_id,)).fetchone()
    if origem_cns is None: raise 404
    _assert_or_403(origem_cns["cns"] == cns_autor, "nao_e_dono_do_laudo",
                   "O laudo de origem foi emitido por outro responsável técnico.")
# (b) pedido vinculado — guard obrigatório §8.4 (P1 CODEX): paciente do pedido == paciente do laudo
if payload.pedido_protocolo:
    ped = conn.execute(
        "SELECT pa.cpf FROM pedidos_exame pe JOIN pacientes pa ON pa.id=pe.paciente_id "
        "WHERE pe.protocolo=?", (payload.pedido_protocolo,)).fetchone()
    if ped is None: raise 404
    _assert_or_403(ped["cpf"] == cpf, "vinculo_pedido_invalido",
                   "O pedido vinculado pertence a outro paciente.")
```
(`fisica` não tem `pedido_protocolo`/`origem` no schema — só o check de `cns_autor`.)

### §7.2 Esqueleto canônico (matriz, bypass admin) — GET(3) · custodia(4) · assinar(5) · liberar(6) · ciencia-prescritor(8) · cancelar(9) · encerrar(10) · pdf(11) · qr(12)
```python
papel, ident = _normalizar_identidade_jwt(usuario)
laudo = _get_laudo_ou_404(conn, protocolo)        # 404 primeiro
if papel != "admin":
    if papel == "prescritor":
        <ramo conforme o endpoint>
    elif papel == "paciente":
        _assert_paciente_dono(conn, protocolo, ident)
# 403 resolvido → só então transição/estado 422
```
Ramo prescritor por endpoint:
- **Leitura** (3,4,11,12): `_assert_leitura_prescritor` (autor∨solicitante).
- **Autor-only** (5,6,9,10): `_assert_autor_dono`.
- **ciencia-prescritor (8):** `_assert_solicitante` — **sem pedido vinculado → 403** (§8.1, opção a).
- Cada endpoint instancia só os ramos do seu `require_role` (paciente só em 4,7,11,12).

### §7.3 ciencia-paciente (7) — fecha o BUG ATIVO
`usuario=Depends(require_role("paciente","admin"))` já captura `usuario`; hoje **não usa**. Adicionar:
```python
papel, ident = _normalizar_identidade_jwt(usuario)
laudo = _get_laudo_ou_404(conn, protocolo)
if papel != "admin":
    _assert_paciente_dono(conn, protocolo, ident)   # cpf == laudo.paciente
```

## §8 Decisões — RESOLVIDAS na revisão CODEX
1. **§8.1 `ciencia-prescritor` sem `pedido_id` → opção (a): 403.** [DECIDIDO] Sem solicitante, prescritor não-autor recebe 403. **Não** usar autor como fallback (mistura responsável técnico com destinatário clínico).
2. **§8.2 `encerrar` → autor apenas** (admin bypass). [DECIDIDO] Solicitante usa `ciencia-prescritor`; `encerrar` é fechamento operacional do produtor.
3. **§8.3 `criar/fisica` com admin → bypass do `cns_autor==JWT`, mas NÃO de invariantes.** [DECIDIDO] Mesmo admin criando em nome de alguém, `origem_laudo_id` deve pertencer ao mesmo `cns_autor` do payload.
4. **§8.4 `pedido_protocolo` é guard obrigatório, não só existência.** [DECIDIDO — P1 CODEX] Ao vincular, validar `pedido.paciente.cpf == laudo.cpf_paciente`. **Não** exigir `cns_autor == pedido.prescritor` (autor técnico ≠ solicitante são distintos). Vínculo errado concederia leitura/ciência ao prescritor errado.

## §9 Critérios de aceite (testes PG — `test_laudos_autorizacao.py`)
- **A (criar/fisica):** autor-A declarando CNS-B → `403 autor_mismatch` + rollback.
- **Origem (correcao):** origem de outro autor → `403 nao_e_dono_do_laudo` + rollback; origem própria → 201. (mesmo p/ admin criando)
- **Pedido vinculado (P1 §8.4):** vincular pedido cujo paciente ≠ paciente do laudo → `403 vinculo_pedido_invalido` + rollback; paciente igual → 201.
- **Leitura (3,4,11,12):** prescritor que é **autor** → 2xx; que é **solicitante** → 2xx; terceiro prescritor → 403; paciente dono → 2xx (onde aplicável); paciente não-dono → 403.
- **Autor-only (5,6,9,10):** solicitante (não-autor) → 403; autor → 2xx.
- **ciencia-prescritor (8):** solicitante → 2xx; autor (não-solicitante) → 403; **laudo sem pedido → 403**.
- **ciencia-paciente (7) — BUG ATIVO:** paciente ≠ dono → 403; paciente dono → 2xx.
- **admin:** 2xx sem ownership em todos os endpoints que aceitam admin, **sem** quebrar invariantes de domínio (origem/pedido continuam validados).
- **Anti-leak #52:** não-dono recebe 403 antes do 422 de estado.

## §10 Verificação automatizada
```bash
grep -nE '_=Depends\(require_role' backend/app/routers/laudos.py            # → VAZIO
grep -c '_normalizar_identidade_jwt(usuario)' backend/app/routers/laudos.py  # → 12
grep -nE 'def _assert_(autor_dono|solicitante|leitura_prescritor|paciente_dono)' backend/app/routers/laudos.py  # → 4
# gate PG:
DATABASE_URL=postgresql://.../picsaude_test pytest tests/integration/test_laudos_autorizacao.py -q
```

---

*Rodada 0 redigida em 2026-06-03 pelo Engenheiro-executor sobre `1b68ad7`, com os martelos da revisão CODEX integrados. Aguarda CODEX rodada 1 antes da implementação.*
