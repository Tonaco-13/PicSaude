# DESPACHO ENG-007 — R1: permitir que o dispensador (clínica/lab) registre o resultado do exame

| Campo | Valor |
|---|---|
| **Despacho** | ENG-007 (backend — enxerto RBAC mínimo, R1 do arco V2) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-07 |
| **Origem** | `TICKET-MODULO-CLINICA-V2.md` §3 (R1) |
| **Classe** | `module` (enxerto em rota existente; sem mudança de schema, sem estado novo) |
| **Pré-requisito** | `main` atual (`3162af9`). Sem dependência. Despacho autônomo (não bloqueia nem é bloqueado). |

---

## §1 Contexto — por que este ticket existe

Hoje a clínica/laboratório (role `dispensador`) pode **coletar** e **realizar** um exame, mas **não
pode registrar o resultado** — o endpoint que o faz exclui esse papel:

```python
# pedidos_exame.py:974-979  (main@3162af9)
@router.post("/{protocolo}/itens/{item_id}/resultado", status_code=201)
def registrar_resultado_item(
    ...
    usuario=Depends(require_role("prescritor", "admin")),  # ← sem dispensador
```

Comentário `:992-993`: *"só o prescritor dono registra resultado; admin bypassa. Conjunto de papéis
inalterado (§4.4/§8.3: sem dispensador aqui)."*

Isto quebra o ciclo operacional da clínica: ela coleta, realiza, mas precisa de um prescritor para
"bater o resultado" — fricção sem justificativa clínica, já que a **guarda de ownership por CNPJ
existe e está wired** em `coletar_item_exame` (`pedidos_exame.py:835-836`).

> **Nota de processo:** o briefing inicial do arquiteto tratou isto como "backend novo + martelo de
> ownership a construir". Verificação in-loco refutou: o martelo (`_assert_dispensador_dono_pedido`,
> `pedidos_exame.py:594-616`) **já existe**. Este despacho é um enxerto de ~4 linhas + teste.

---

## §2 O que fazer (arquivo único: `pedidos_exame.py`)

### 2.1 Estender o `require_role` (linha 979)

```python
# ANTES
usuario=Depends(require_role("prescritor", "admin")),
# DEPOIS
usuario=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (R1 V2)
```

### 2.2 Wire da guarda de ownership no corpo

Espelhar exatamente o padrão de `coletar_item_exame:825-836`. Hoje o corpo de
`registrar_resultado_item` faz (`:994-1001`):

```python
papel, ident = _normalizar_identidade_jwt(usuario)

with get_tx() as conn:
    pedido = _get_pedido_ou_404(conn, protocolo)

    if papel != "admin":
        if papel == "prescritor":
            _assert_prescritor_dono_pedido(conn, protocolo, ident)
        # ← falta o elif dispensador
```

Adicionar o `elif` (antes de qualquer devolutiva de conteúdo — anti-leak §7.2):

```python
    if papel != "admin":
        if papel == "prescritor":
            _assert_prescritor_dono_pedido(conn, protocolo, ident)
        elif papel == "dispensador":
            _assert_dispensador_dono_pedido(conn, pedido["id"], ident)
```

Atualizar o comentário `:992-993` para registrar a mudança de papéis (R1 V2).

---

## §3 Invariantes (não-negociáveis)

- **Ownership obrigatória para dispensador:** o `dispensador` só registra resultado de pedido
  **sob sua custódia atual** (custódia nível pedido, `item_id IS NULL`, `ORDER BY id DESC LIMIT 1`).
  Espelha `coletar_item_exame` — não inventar guarda nova.
- **Anti-leak §7.2:** ordem 404 → 403 → 422 de estado preservada. O 403 (não-dono) vem **antes**
  de devolver qualquer conteúdo do pedido.
- **Sem estado novo:** o ledger continua escrevendo `pedido_em_analise` (`:1039`) e
  `resultado_registrado` (`:1069`) exatamente como hoje. `_recalcular_e_atualizar_status_pedido`
  (`:627`) deriva o status do pedido inalterado.
- **Prescritor/admin inalterados:** nenhum comportamento existente muda para esses papéis.
- **Sem mudança de schema:** nenhuma tabela/coluna/migration.

---

## §4 Critérios de aceite

1. `dispensador` **dono** da custódia registra resultado → 201, ledger com `resultado_registrado`.
2. `dispensador` **não-dono** (custódia de outro CNPJ, ou sem custódia nível-pedido) → **403**
   `nao_e_dono_do_pedido_exame`, **sem** vazar conteúdo do pedido.
3. `prescritor` dono e `admin` continuam funcionando (regressão nula).
4. Item em estado que não permite resultado (não-`coletado`/`em_analise`) → 422 inalterado (`:1020`).
5. `_assert_dispensador_dono_pedido` chamado para `dispensador` — reusar a função existente,
   **não** duplicar lógica.
6. Teste novo: `tests/unit/test_registrar_resultado_dispensador.py` cobrindo casos 1 e 2 acima.

---

## §5 Verificação

```bash
cd backend

# Teste novo (deve ficar verde)
python -m pytest tests/unit/test_registrar_resultado_dispensador.py -v

# Regressão — coleta e consulta não podem quebrar
python -m pytest tests/unit/ -k "coletar or pedido_exame or dispensador_dono" -v

# Smoke manual (opcional): como dispensador clínica, registrar resultado de item coletado
curl -X POST "$BACKEND/pedidos-exame/$PROTO/itens/$ITEM_ID/resultado" \
  -H "Authorization: Bearer $TOKEN_DISPENSADOR" \
  -H "Content-Type: application/json" \
  -d '{"resultado_resumo": "Glicemia 92 mg/dL"}'
```

---

## §6 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add backend/app/routers/pedidos_exame.py backend/tests/unit/test_registrar_resultado_dispensador.py`
  — nunca `git add .` / `-A`.
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## §7 Fluxo

1. Implemente o enxerto (§2.1 + §2.2) + teste (§4.6).
2. Branch: `module/r1-resultado-dispensador`.
3. Confirme §5 verde.
4. PR → Revisor audita → Conselheiro ratifica → Fabiano martela.

---

*Despacho emitido pelo arquiteto. Escopo mínimo (enxerto RBAC + ownership reusada, sem estado novo
nem schema). Origem: TICKET-MODULO-CLINICA-V2 §3.*
