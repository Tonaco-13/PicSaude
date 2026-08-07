# DESPACHO ENG-008 — R3: relatório de exames do próprio prestador (CSV/PDF)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-008 (backend novo — router `/clinicas`, R3 do arco V2) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-07 |
| **Origem** | `TICKET-MODULO-CLINICA-V2.md` §5 (R3) |
| **Classe** | `module` (router novo; sem mudança de schema, sem estado novo, sem escrita) |
| **Pré-requisito** | `main` atual (`3162af9`). Sem dependência de outros despachos. |

---

## §1 Contexto — por que este ticket existe

A clínica/laboratório não tem como extrair um **relatório dos exames sob sua responsabilidade**.
Hoje só a farmácia tem esse tipo de extração (`GET /dispensadores/relatorio.{csv,pdf}`,
`dispensadores.py:452/483` — escrituração SNGPC), e o router `/dispensadores` é **específico de
farmácia** (não de clínica/lab). Inventário dos 12 routes de `pedidos_exame.py` confirma: só há
PDFs **por protocolo** (ex.: `:1175`), nenhum relatório agregado.

A clínica/lab compartilha o role `dispensador` mas tem **contexto de dados de exames**. Logo o
relatório mora num novo router `/clinicas`, não em `/dispensadores`.

> **Decisão de morada (ratificada):** router novo `clinicas.py` (prefix `/clinicas`). O domínio
> clínica/lab tende a crescer (R4 faturamento, TUSS, futuras integrações); acumulá-lo em
> `/dispensadores` repetiria o custo já visto lá. O `/clinicas` também abrigará o R4 (DESPACHO-ENG-009).

---

## §2 O que fazer

### 2.1 Novo router `backend/app/routers/clinicas.py`

```python
from fastapi import APIRouter, Depends, Query
from typing import Optional

router = APIRouter(prefix="/clinicas", tags=["clinicas"])
```

Espelhar a estrutura de `dispensadores.py:452-517` (auth, scoping, periodo, resposta).

### 2.2 `GET /clinicas/relatorio.csv`

```python
@router.get("/relatorio.csv", summary="Relatório de exames do prestador (CSV)")
def relatorio_exames_csv(
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    data_fim:    Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    usuario=Depends(require_role("dispensador")),
):
    cnpj = normalize_cnpj(usuario["sub"])                 # padrão dispensadores.py:460
    dt_inicio, dt_fim, _ = _janela_periodo(data_inicio, data_fim)  # default 30 dias
    ...
```

**Scoping (read-only):** derivar os pedidos sob custódia **atual** do CNPJ:

```sql
SELECT pe.protocolo, pei.id AS item_id, pei.codigo_tuss, pei.status_item,
       ... (ver §2.4 para colunas)
FROM pedido_exame_custodia c
JOIN pedidos_exame     pe  ON pe.id = c.pedido_id
JOIN pedido_exame_itens pei ON pei.pedido_id = c.pedido_id
WHERE c.item_id IS NULL
  AND c.id = (
      SELECT MAX(id) FROM pedido_exame_custodia
      WHERE pedido_id = c.pedido_id AND item_id IS NULL
  )  -- custódia ATUAL nível-pedido (espelha _assert_dispensador_dono_pedido)
  AND c.para = ?   -- :cnpj
```

Filtrar por período (`dt_inicio`/`dt_fim`) sobre a data relevante do item. **Nenhum INSERT/UPDATE**.

### 2.3 `GET /clinicas/relatorio.pdf`

Mesmo scoping; PDF com helper estilo `gerar_pdf_sngpc` (`dispensadores.py:505-510`). Truncagem em
`_MAX_REGISTROS_PDF = 1000` com aviso visível (padrão `dispensadores.py:500-503`).

### 2.4 Cabeçalho CSV

```
protocolo,item_id,codigo_tuss,status_item,data_coleta,data_resultado,data_agendamento
```

### 2.5 Registro no `main.py`

```python
# backend/app/main.py — adicionar import (linha ~17) e include (após dispensadores, ~216)
from app.routers import ..., clinicas, ...
app.include_router(clinicas.router)   # DESPACHO-ENG-008 — relatórios da clínica/lab
```

---

## §3 Invariantes (não-negociáveis)

- **Escopo = CNPJ do próprio prestador:** `cnpj = normalize_cnpj(usuario["sub"])`. A clínica **só
  vê exames sob sua custódia atual** (mesma semântica de `_assert_dispensador_dono_pedido`).
  **Nunca** expor exames de outro CNPJ.
- **Read-only:** nenhum INSERT/UPDATE/DELETE em qualquer tabela. Classe `module`, não `core`.
- **Sem estado novo, sem escrita no ledger.**
- **Anti-leak:** não há nada a vazar aqui além do próprio CNPJ (relatório é self-service), mas o
  scoping por `c.para = cnpj` é a guarda — sem `c.para = ?` o endpoint não pode existir.
- **Role:** `dispensador` apenas. Sem `auditor`/`admin` aqui (visão cross-establishment é
  `/relatorios/*`, escopo do auditor — `relatorios.py:123/210`, **não** mexer).

---

## §4 Critérios de aceite

1. `GET /clinicas/relatorio.csv` retorna **apenas** exames sob custódia atual do CNPJ do JWT.
2. Query params `data_inicio`/`data_fim` funcionam; default = últimos 30 dias.
3. Cabeçalho CSV conforme §2.4; linhas com `csv.QUOTE_ALL` (padrão `dispensadores.py`).
4. `GET /clinicas/relatorio.pdf` gera PDF; >1000 registros → truncagem com aviso visível.
5. Clínica A (CNPJ X) **não vê** exames da clínica B (CNPJ Y) — teste de isolamento.
6. `Content-Disposition: attachment; filename="relatorio_exames_{data}.csv"`.
7. Sem escrita em `pedido_exame_eventos`, `pedido_exame_custodia`, `pedido_exame_itens`.
8. Router registrado em `main.py`; `/docs` (OpenAPI) lista as 2 rotas sob tag `clinicas`.

---

## §5 Verificação

```bash
cd backend

# Teste de isolamento (novo) — clínica A não vê exames da clínica B
python -m pytest tests/unit/test_relatorio_exames_isolamento.py -v

# Smoke manual
curl "$BACKEND/clinicas/relatorio.csv" -H "Authorization: Bearer $TOKEN_CLINICA"
curl "$BACKEND/clinicas/relatorio.pdf?data_inicio=2026-01-01" -H "Authorization: Bearer $TOKEN_CLINICA" -o /tmp/rel.pdf

# Confirmar que clínica não enxerga exame de outro CNPJ (deve retornar 0 linhas ou só as suas)
```

---

## §6 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add backend/app/routers/clinicas.py backend/app/main.py backend/tests/unit/test_relatorio_exames_isolamento.py`
  — nunca `git add .` / `-A`.
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## §7 Fluxo

1. Crie `clinicas.py` (router + 2 endpoints), registre em `main.py`, adicione teste.
2. Branch: `module/r3-relatorio-exames`.
3. Confirme §5 verde.
4. PR → Revisor audita → Conselheiro ratifica → Fabiano martela.

---

*Despacho emitido pelo arquiteto. Backend novo (router `/clinicas`), read-only, sem estado novo nem
schema. Origem: TICKET-MODULO-CLINICA-V2 §5. Precedente: `dispensadores.py:452/483`.*
