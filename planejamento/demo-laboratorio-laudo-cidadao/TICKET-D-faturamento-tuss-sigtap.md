# Ticket D — Faturamento por TUSS **e** SIGTAP

| Campo | Valor |
|---|---|
| Classe | `module` |
| Depende de | — |
| Esforço | Pequeno |

## Contexto

Decisão #3: demonstrar agregação TUSS (plano de saúde) **e** SIGTAP (SUS). Hoje o faturamento
agrega **só por TUSS** (`clinicas.py:227-263`), embora `codigo_sigtap` já exista e esteja populado
em `pedido_exame_itens` (`models/pedido_exame_item.py:26`). É um caminho paralelo — **sem schema
change**. Permanece **contabilidade interna read-only**; **não há transmissão** a operadora/SUS
(adapter → depende de G4A, fora de escopo).

## Arquivo

- `backend/app/routers/clinicas.py` — parametrizar a agregação.

## Tarefa

1. **Query param** nos 4 endpoints de faturamento (`/clinicas/faturamento.csv` `:361` e
   `/clinicas/faturamento.pdf` `:395`):
   ```python
   agrupar_por: str = Query("tuss", description="Critério de agregação: tuss | sigtap")
   ```
   - Valores válidos: `{"tuss", "sigtap"}`; inválido → 422 (`codigo: "agrupar_por_invalido"`).

2. **Generalizar** a consulta e a agregação. Hoje:
   - `_SQL_FATURAMENTO_DO_CNPJ` (`:227`) seleciona `codigo_tuss`.
   - `_agregar_por_tuss` (`:247`) agrupa por `codigo_tuss`, rótulo `(não classificado)`.
   - Refatorar para uma função genérica que recebe a coluna (`codigo_tuss` | `codigo_sigtap`) e o
     rótulo de "sem classificação". Ou dois helpers paralelos (`_agregar_por_sigtap` espelhando
     `_agregar_por_tuss`). Manter o desempate estável (qtd desc, código asc) — é requisito de
     reprodutibilidade (`:262`).

3. **PDF** (`gerar_pdf_faturamento` em `domain/pdf_relatorio_exames.py`): o rótulo do agrupamento
   deve refletir o critério (ex.: "Faturamento por SIGTAP" no cabeçalho quando `agrupar_por=sigtap`).
   - Passar o critério para o gerador de PDF (parâmetro novo ou nos `filtros`).

4. **CSV**: o cabeçalho hoje é `codigo_tuss,qtd,...` (`CABECALHO_FATURAMENTO_CSV` `:353`). Quando
   `agrupar_por=sigtap`, usar `codigo_sigtap`. (Parametrizar o cabeçalho ou gerar dois.)

## Guardrails

- **Read-only.** Nenhum INSERT/UPDATE/DELETE, nada no ledger (o router já é read-only — `clinicas.py` docstring).
- **Escopo = CNPJ do JWT**, pela custódia ATUAL nível-pedido (semântica já em `_SQL_FATURAMENTO_DO_CNPJ`).
- **Âncora de cobrança inalterada:** `pedido_exame_itens.resultado_em` (decisão documentada em
  `clinicas.py:214-224`). Não casar por JSON do evento.
- **Sem transmissão externa** — TUSS/SIGTAP aqui são classificação/contagem, não guia TISS/APAC.

## Critérios de aceite

- [ ] `GET /clinicas/faturamento.csv?agrupar_por=tuss` (default) — comportamento atual preservado.
- [ ] `GET /clinicas/faturamento.csv?agrupar_por=sigtap` — agrega por `codigo_sigtap`.
- [ ] `GET /clinicas/faturamento.pdf?agrupar_por=sigtap` — PDF com rótulo correto.
- [ ] `agrupar_por=invalido` → 422.
- [ ] Itens sem o código da coluna escolhida caem em rótulo "(não classificado)".
- [ ] Igualdade ledger↔faturamento preservada para TUSS (teste `test_faturamento_equivale_ao_ledger`).
- [ ] `pytest` verde (gates-browser).

## Testes exigidos

- TUSS (default) idêntico ao de hoje (regressão).
- SIGTAP agrega corretamente por `codigo_sigtap`.
- Valor inválido → 422.
- Período (`data_inicio`/`data_fim`) continua funcionando com ambos os critérios.
- Escopo por CNPJ preservado (outra unidade não vê os dados).
