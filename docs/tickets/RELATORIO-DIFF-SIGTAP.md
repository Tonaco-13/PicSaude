# RELATORIO-DIFF-SIGTAP.md — TICKET-FILA-7

Gerado por `backend/scripts/importar_snapshot_sigtap.py`. Competência: 202606.

## Whitelist aplicada (LITERAL — grupo + todos os subgrupos)

Grupo `02` — "Procedimentos com finalidade diagnóstica" — 14 subgrupos, todos incluídos ("diagnósticos amplos", recomendação §6.2 do ticket):

- `02.01` — Coleta de material
- `02.02` — Diagnóstico em laboratório clínico
- `02.03` — Diagnóstico por anatomia patológica e citopatologia
- `02.04` — Diagnóstico por radiologia
- `02.05` — Diagnóstico por ultrasonografia
- `02.06` — Diagnóstico por tomografia
- `02.07` — Diagnóstico por ressonância magnética
- `02.08` — Diagnóstico por medicina nuclear in vivo
- `02.09` — Diagnóstico por endoscopia
- `02.10` — Diagnóstico por radiologia intervencionista
- `02.11` — Métodos diagnósticos em especialidades
- `02.12` — Diagnóstico e procedimentos especiais em hemoterapia
- `02.13` — Diagnóstico em vigilância epidemiológica e ambiental
- `02.14` — Diagnóstico por teste rápido

## Contagem

- Total de procedimentos na Tabela Unificada: **4994**
- Total após o corte (grupo 02): **1105**
- Curadoria manual atual (`tuss_base.py::_BASE_RAW`): **38** (o ticket citava "~35" no §1; recontagem real na execução deu 38 — registrado, não substituído em silêncio)
- Múltiplo: **29.1x** a curadoria atual (AC2 do ticket exige ≥ dezenas×)

## Nenhum código foi excluído por nome

O corte é 100% por `(CO_GRUPO, CO_SUB_GRUPO)` lido do próprio dump — nenhuma linha entrou ou saiu por a descrição "parecer" exame.
