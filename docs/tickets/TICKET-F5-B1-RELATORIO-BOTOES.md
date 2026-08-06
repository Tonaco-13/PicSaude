# TICKET-F5-B1 — Botões de Relatório Consolidado + SNGPC (CSV/PDF) no cabeçalho da fila

> **⚙️ STATUS — ✅ Implementado (2026-07-11).**
> Commit `2e7ffda` · PR #91 (ver §10 do parent `TICKET-F5-FATIA-B-FRONTEND-DISPENSADOR.md`).
> Espec abaixo preservada como **registro histórico**; não reabrir sem evidência de regressão ao vivo.
>
> **Verificado contra `main` em 2026-07-25 (Z AI):**
> - Botões presentes em `dispensador.html:442-444` (`Relatório Consolidado`, `SNGPC CSV`, `SNGPC PDF`).
> - Handlers `abrirRelatorioConsolidado()` (`:1759`) e `exportarSngpc()` (`:1721`) respondem ao clique.
> - `#print-area` (`:2736`) presente; view consolidada alimentada pelo mesmo endpoint.
> - **Pendente:** browser-E2E `test_f5_b1_relatorio_botoes.py` (§6) — não há arquivo em `backend/tests/browser/`.

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — Fatia B, ticket 1 de 3 |
| **Classe** | `module` (frontend puro, consome endpoints já mergeados da Fatia A — PR #88) |
| **Para** | Revisor de tickets (code/app) → Conselheiro → engenheiro → gate + browser-E2E → martelo Fabiano |
| **Origem** | TICKET-F5-RELATORIO-SNGPC §4 (stub da Fatia B) + TICKET-COER2-POS-MERGE-DIAGNOSTICO §6 (bug do botão "Relatório Consolidado" não responde ao clique) |
| **Pré-requisito** | `main` atual (pós-merge #120); endpoints da Fatia A em produção |

## §1 Contexto (não reabrir)

A Fatia A (backend do relatório SNGPC do dispensador) está mergeada — `GET /dispensadores/relatorio.{csv,pdf}` funcionam, travados ao CNPJ do JWT, com escrituração por movimento (incluindo estornos), `saldo_escriturado_item` com corte temporal, e PII-EXAUSTIVIDADE verificada. Esta fatia (B1) é só o frontend que consome esses endpoints — **nenhum backend novo**.

Bug atual identificado pelo teste manual (TICKET-COER2-POS-MERGE-DIAGNOSTICO §6): o botão "🖨️ Relatório Consolidado" hoje **não responde ao clique**. Provável handler ausente ou quebrado. Este ticket conserta ao implementar o handler correto (não é bug isolado, é feature faltante).

## §2 Invariantes (não-negociáveis)

- **R1 (reprodutibilidade):** o relatório é projeção do ledger; a UI não computa nada, só exibe o que o backend retorna.
- **§10 (PII):** fetch com Bearer JWT, **nunca** `<a href>` com URL exposta (PII do comprador/paciente/prescritor).
- **R3 (linhagem-mãe):** se `protocolo_raiz` já estiver no CSV (depende de R3-PROTOCOLO-RAIZ estar mergeado), exibir como coluna; se não, não mostrar — decisão de produto adiada.

## §3 Contrato (endpoints reais — já em produção)

```
GET /dispensadores/relatorio.csv?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
GET /dispensadores/relatorio.pdf?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
Auth: JWT role=dispensador (Authorization: Bearer …)
Default sem filtros: últimos 30 dias
PDF limitado a 1000 registros (com aviso de truncamento quando exceder)
```

Colunas do CSV já definidas na Fatia A — não modificar.

## §4 Spec de implementação

### 4.1 Arquivos tocados
- `dispensador.html` — adicionar 2 botões no cabeçalho da fila (`.fila-card-head`, ~linha 418 ao lado do `↻ Atualizar`); implementar handlers `baixarRelatorioCSV()`, `baixarRelatorioPDF()`, `imprimirRelatorioConsolidado()`; reusar `_baixarBlob(nome, url)` existente.

### 4.2 Botões no cabeçalho

Posição conforme `dispensador.txt` (v27 referencial de UX):
- `🖨️ Relatório Consolidado` → abre view de impressão `#print-area`
- `SNGPC (CSV)` → download do CSV
- `SNGPC (PDF)` → download do PDF (alternativa: um botão "SNGPC" com submenu CSV/PDF — decisão do engenheiro)

### 4.3 Seletor de período

2 inputs `data_inicio` / `data_fim` (já existem no HTML — confirmar), default 30 dias. Aplicar a ambos CSV e PDF.

### 4.4 View de impressão consolidada

Usar padrão `#print-area` + `@media print` do v27. **Sem segunda query divergente** — alimentada pelo mesmo endpoint (decisão do engenheiro: parse do CSV baixado, ou formato JSON opcional do mesmo endpoint). Critério: uma única fonte de verdade.

### 4.5 Aviso de truncamento de PDF

Quando o PDF vier truncado em 1000 registros, exibir aviso visível no header/rodapé do PDF ou no modal de download. **Nunca truncamento silencioso.**

### 4.6 Erro legível

`_extrairMsgErro` (portado no P0.5) cobre `detail.mensagem`. Aplicar nos handlers — **nunca** `[object Object]`, **nunca** tela branca. 401/403 → `tratarSessaoExpirada()`.

## §5 Critérios de aceite

1. Os 3 botões (Consolidado, CSV, PDF) respondem ao clique (corrige bug atual)
2. CSV baixa via `fetch` + Bearer + blob, nome `dispensacoes_sngpc_{data_fim}.csv`
3. PDF baixa via `fetch` + Bearer + blob, nome `dispensacoes_sngpc_{data_fim}.pdf`
4. **NUNCA** existe `<a href>` apontando direto pro endpoint (grep: `rg -n 'href.*relatorio' dispensador.html` retorna zero)
5. View de impressão consolidada abre no `#print-area`, alimentada pelo **mesmo** endpoint (sem query divergente)
6. PDF truncado (>1000) exibe aviso visível
7. Trocar JWT (dispensador B) → CSV/PDF não contém movimento do dispensador A
8. Erro do backend renderiza `detail.mensagem` legível
9. **Browser-E2E obrigatório**: teste automatizado que clica nos 3 botões e valida download (ou abertura de print) — ver §6

## §6 Browser-E2E (obrigatório no aceite)

Adicionar a `tests/browser/test_f5_b1_relatorio_botoes.py`:

```python
def test_b1_botoes_relatorio_funcionam(browser_demo):
    """Os 3 botões no cabeçalho da fila respondem ao clique."""
    # Login demo dispensador
    # Snapshot do cabeçalho da fila
    # Clicar em "SNGPC CSV" → validar que fetch foi feito com Bearer
    #   (intercept network; assert request tem header Authorization)
    # Clicar em "SNGPC PDF" → idem
    # Clicar em "Relatório Consolidado" → validar #print-area visível
    # Trocar JWT para dispensador_norte → CSV vem vazio (sem movimento)
```

Crítico: o E2E **deve afirmar sobre a seção específica** (cabeçalho da fila), não sobre "botão existe em algum lugar da página" — lição do COER2-POS-MERGE.

## §7 Fora de escopo

- Backend (já mergeado na Fatia A)
- R3 (protocolo_raiz) — entra quando o ticket R3-PROTOCOLO-RAIZ for mergeado
- XML SNGPC oficial (bloqueado até G4A)
- Atualização da visão do auditor (`/relatorios/*`) — dívida separada
- Polish visual (transições animadas, cores, etc.) — frente de UX separada

## §8 Fluxo de aprovação

1. Revisor de tickets (code/app) revisa escopo e contratos
2. Conselheiro dá parecer (verde / verde-com-notas / bloqueio)
3. Engenheiro implementa + browser-E2E
4. Gate CI verde (PG + SQLite)
5. Browser-E2E verde
6. Martelo do Fabiano + merge

## §9 Não fazer

- Não adicionar coluna nova ao CSV/PDF (backend pronto)
- Não implementar sem o browser-E2E (é critério obrigatório)
- Não usar `<a href>` com URL do endpoint (PII vazaria sem auth)
- Não criar query divergente pra view de impressão (uma fonte de verdade)
