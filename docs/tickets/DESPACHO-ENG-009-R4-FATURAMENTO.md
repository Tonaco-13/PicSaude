# DESPACHO ENG-009 — R4: faturamento (projeção interna read-only do ledger de exames)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-009 (backend novo — endpoints em `/clinicas`, R4 do arco V2) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Revisor · Conselheiro · Fabiano |
| **Data** | 2026-08-07 |
| **Origem** | `TICKET-MODULO-CLINICA-V2.md` §6 (R4) |
| **Classe** | `module` (projeção read-only sobre ledger existente; sem schema, sem estado novo) |
| **Pré-requisito** | `main` atual (`3162af9`). **Recomendado** executar após ENG-008 (mesmo router `/clinicas`). **Não** depende de G4A. |

---

## §1 Contexto — por que este ticket existe

A clínica/laboratório precisa de uma **visão de faturamento** dos exames realizados. **Decisão
cravada (ratificada pelo conselheiro e pela doc):** faturamento = **relatório interno** — projeção
read-only do ledger de exames (`pedido_exame_eventos`), no espelho do SNGPC do dispensador.
**Não** é guia TISS; **não** publica nada a sistema externo; logo **não depende de G4A**.

> **Invariante decisório (§10 da governança):** *nenhum estado novo, nenhuma escrita no ledger, nem
> em custódia.* Faturamento aqui é **contabilidade interna** (quantos exames de cada procedimento
> foram concluídos no período), **não** integração com operadora.

A guia TISS (adapter externo) está **bloqueada por G4A** (`CLAUDE.md:731`: *"Sem G4A, adapters não
têm onde se conectar. Não iniciar adapter de ... TISS ..."*) — explicitamente fora de escopo V2.

---

## §2 O que fazer

### 2.1 Endpoints no router `/clinicas` (criado em ENG-008)

Se ENG-008 ainda não foi mergeado, criar o router aqui (§2.1 do ENG-008) e incluir estes endpoints.
Se já existe, **adicionar a estes** `clinicas.py`:

```python
@router.get("/faturamento.csv", summary="Faturamento de exames do prestador (CSV)")
def faturamento_exames_csv(
    data_inicio: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    data_fim:    Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    usuario=Depends(require_role("dispensador")),
):
    cnpj = normalize_cnpj(usuario["sub"])
    ...
```

E análogo `/faturamento.pdf`.

### 2.2 Projeção (read-only)

Âncora de cobrança = item com `resultado_registrado` (evento de conclusão) no período. Agregar por
procedimento (TUSS):

```sql
SELECT pei.codigo_tuss,
       COUNT(*)                        AS qtd,
       MIN(ev.criado_em)               AS primeira,
       MAX(ev.criado_em)               AS ultima
FROM pedido_exame_eventos ev
JOIN pedido_exame_itens   pei ON pei.id = ev.dados_json->'item_id'   -- ou via pedido_id+item
JOIN pedido_exame_custodia c ON c.pedido_id = ev.pedido_id
WHERE ev.tipo_evento = 'resultado_registrado'
  AND ev.criado_em BETWEEN ? AND ?
  AND c.item_id IS NULL
  AND c.id = (SELECT MAX(id) FROM pedido_exame_custodia
              WHERE pedido_id = c.pedido_id AND item_id IS NULL)
  AND c.para = ?   -- :cnpj
GROUP BY pei.codigo_tuss
ORDER BY qtd DESC
```

> **Nota de implementação:** o join exato de `pedido_exame_eventos` → item depende de como
> `resultado_registrado` grava o `item_id` em `dados_json` (ver `pedidos_exame.py:1069` e o payload
> montado em `:1031-1069`). Confirmar a coluna/JSON-key antes de escrever a query — **não assumir**.
> Se o `item_id` não estiver no payload, derivar via `_recalcular` ou varrer `pedido_exame_itens`
> por `pedido_id` filtrando `status_item = 'resultado_disponivel'`.

### 2.3 Cabeçalho CSV

```
codigo_tuss,qtd,primeiro_resultado,ultimo_resultado
```

### 2.4 PDF

Mesma agregação; helper estilo `gerar_pdf_sngpc`. Sem truncagem agressiva (volume de faturamento é
tipicamente pequeno — agregação por TUSS), mas manter `_MAX_REGISTROS_PDF` como teto defensivo.

---

## §3 Invariantes (não-negociáveis)

- **Read-only absoluto:** nenhum INSERT/UPDATE/DELETE em qualquer tabela. Isto é uma **projeção**
  sobre `pedido_exame_eventos` + `pedido_exame_custodia` + `pedido_exame_itens`.
- **Nenhum estado novo** em `ESTADOS_PEDIDO_EXAME` (`states_exame.py:49-59`).
- **Nenhuma escrita no ledger** (`pedido_exame_eventos`) nem em custódia.
- **Escopo = CNPJ do próprio prestador** (`c.para = normalize_cnpj(usuario["sub"])`). A clínica só
  fatura o que está sob **sua** custódia atual.
- **Classe `module`, não `core`.** Não depende de G4A (nada é publicado externamente).
- **Não é guia TISS:** nenhum schema TUSS/TISS, nenhuma chamada a operadora.

---

## §4 Critérios de aceite

1. `GET /clinicas/faturamento.csv` retorna agregação por `codigo_tuss` dos itens com
   `resultado_registrado` no período, **apenas do CNPJ do JWT**.
2. Query params `data_inicio`/`data_fim`; default últimos 30 dias.
3. Clínica A **não vê** faturamento da clínica B — teste de isolamento.
4. Nenhuma escrita em `pedido_exame_eventos`/`pedido_exame_custodia`/`pedido_exame_itens`
   (assertar no teste que row-count não muda antes/depois).
5. Nenhum estado novo adicionado a `ESTADOS_PEDIDO_EXAME`.
6. `/docs` lista `/clinicas/faturamento.csv` e `.pdf` sob tag `clinicas`.

---

## §5 Verificação

```bash
cd backend

# Teste de isolamento + read-only (novo)
python -m pytest tests/unit/test_faturamento_exames.py -v

# Confirmar que não há escrita (row-count do ledger inalterado antes/depois do GET)
# — o teste deve assertar isto explicitamente.

# Smoke manual
curl "$BACKEND/clinicas/faturamento.csv?data_inicio=2026-01-01&data_fim=2026-12-31" \
  -H "Authorization: Bearer $TOKEN_CLINICA"
```

---

## §6 Fora de escopo (bloqueado / decidido)

- **Guia TISS / adapter operadora** — bloqueado por G4A. Hoje o outbox (`outbox.py:27`) escreve em
  `eventos_publicacao` mas **não tem dispatcher/consumer** (só polling em `eventos.py:51`).
  `CLAUDE.md:731` + `ETHICS.md:57-59`.
- **Seed/normalização TUSS ampliada** — backlog; `codigo_tuss` hoje é nullable com base curada
  de ~35 proc (`tuss_base.py`). Itens sem TUSS aparecem como `(não classificado)`.

---

## §7 Pasta compartilhada (regra permanente)

- `git branch --show-current` antes de commitar.
- `git add backend/app/routers/clinicas.py backend/tests/unit/test_faturamento_exames.py`
  (e `main.py` se ENG-008 ainda não tiver registrado o router).
- Trabalho alheio no seu caminho: pause e relate.
- Sem cirurgia de ponteiros sem falar com o arquiteto.

---

## §8 Fluxo

1. Confirme se ENG-008 já criou `clinicas.py`; se não, crie (§2.1 do ENG-008).
2. Adicione `/faturamento.csv` e `/faturamento.pdf` + teste.
3. Branch: `module/r4-faturamento`.
4. Confirme §5 verde (inclusive assert read-only de row-count).
5. PR → Revisor audita → Conselheiro ratifica → Fabiano martela.

---

*Despacho emitido pelo arquiteto. Backend novo (projeção read-only do ledger), sem estado novo, sem
escrita, sem dependência de G4A. Origem: TICKET-MODULO-CLINICA-V2 §6.*
