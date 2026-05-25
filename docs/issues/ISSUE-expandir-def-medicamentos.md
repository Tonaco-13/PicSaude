# GFI #62 — Expandir `def_medicamentos.csv` para top-200 RENAME

> **Tipo:** good-first-issue
> **Origem:** Diagnóstico tri-revisor IA-DEF de 2026-05-25 (Code §5 achado #2, antecipado pelo Arquiteto no §9 do diagnóstico).
> **Labels sugeridas:** `good-first-issue`, `dados`, `ia`, `documentacao`.
> **Perfil ideal:** alguém com formação em saúde (farmácia, medicina, enfermagem) ou estudante que se sinta confortável com planilha/CSV. **Não precisa saber Python.**

---

## Contexto

O PicSaúde tem um endpoint `POST /ia/medicamentos/sugerir` que, apesar do nome, **não usa modelo de linguagem** — é lookup determinístico contra a base local `data/def_medicamentos.csv`. Veja a seção "Sobre a IA do PicSaúde" no `CONTRIBUTING-EXTENSAO.md` para o porquê dessa escolha.

A base atual tem **41 medicamentos** (subset MVP). Cobre os mais comuns (amoxicilina, metformina, losartana, dipirona, paracetamol, insulinas, etc.) mas omite vários igualmente comuns no Brasil: **diazepam, captopril, anlodipino, loratadina, rosuvastatina, pantoprazol, sertralina, metoclopramida**, entre outros.

Resultado prático: quando um prescritor (real ou demo) digita um desses, o backend responde `match_tipo: "nenhum"` e o frontend mostra mensagem amigável "nenhuma sugestão na base local" (fix aplicado em ~2026-05-25 — veja commit `fix(ia): feedback visual...`). Tecnicamente o sistema está correto, mas a experiência é frustrante e não convence ninguém de que a IA "funciona".

## O que você vai fazer

Expandir `data/def_medicamentos.csv` para conter os **top 200 medicamentos da RENAME** (Relação Nacional de Medicamentos Essenciais do SUS, edição vigente), mantendo o schema atual e enriquecendo com aliases comerciais reconhecidos.

## Schema do CSV (não mudar)

```
principio_ativo, nome_normalizado, forma_farmaceutica, unidade_dispensavel,
concentracao_texto, via_administracao, aliases, fonte, versao_base
```

Exemplo de linha existente (formato de referência):

```
amoxicilina,amoxicilina 500 mg capsula,capsula,capsula,500 mg,oral,amoxicilina 500|amoxil 500|amoxifar 500,DEF/BASE_LOCAL,2026-03
```

Campos:

- `principio_ativo` — DCB/DCI em português, minúsculo, sem acento (ex: `clonazepam`).
- `nome_normalizado` — chave de busca exata (ex: `clonazepam 2 mg comprimido`). Lowercase, sem acento, com unidade e forma.
- `forma_farmaceutica` — comprimido, capsula, solucao oral, suspensao, aerossol, etc.
- `unidade_dispensavel` — como vem ao paciente (comprimido, frasco, ampola, blister).
- `concentracao_texto` — ex: `2 mg`, `100 mg/ml`, `500+125 mg`.
- `via_administracao` — oral, injetavel, inalatorio, topica, etc.
- `aliases` — pipe-separados (`|`), incluindo nomes comerciais conhecidos: `rivotril|frisium|epileptil`. Lowercase, sem acento. **Crítico para a busca encontrar o medicamento mesmo quando o prescritor usa o nome comercial.**
- `fonte` — sempre `DEF/BASE_LOCAL` (sem mudar).
- `versao_base` — bump para a data da sua atualização: `2026-XX` (mês da entrega do PR).

## Como escolher os 200

Use a **RENAME edição vigente** ([acesso no site do Ministério da Saúde](https://www.gov.br/conitec/pt-br/midias/protocolos/rename)) como fonte primária. Critério de priorização:

1. Todos os 41 que já estão na base — não remover (compatibilidade).
2. Top 100 mais prescritos no SUS (referência: TabNet/DATASUS ou estudos publicados).
3. Cobertura de classes terapêuticas faltantes na base atual: anti-hipertensivos completos (captopril, anlodipino), benzodiazepínicos (diazepam, alprazolam), antidepressivos (sertralina, escitalopram), inibidores de bomba de prótons (pantoprazol, esomeprazol), anti-histamínicos (loratadina, desloratadina), etc.

## Critérios de aceite

Antes de abrir o PR, confira:

- [ ] CSV continua com o mesmo cabeçalho (linha 1 sem mudança).
- [ ] Total ≥ 200 linhas de dados (sem contar o cabeçalho).
- [ ] Cada `nome_normalizado` é único na coluna.
- [ ] Aliases incluem ao menos um nome comercial conhecido por linha (quando aplicável).
- [ ] `versao_base` em todas as linhas atualizada para o mês da entrega.
- [ ] Rodar `pytest backend/tests/test_ia_farmaceutica.py -v` — deve continuar verde (testes existentes não fixam tamanho da base).
- [ ] Manual: subir o servidor (`PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py && PICSAUDE_DEMO_MODE=true uvicorn app.main:app --reload --app-dir .`), chamar `GET /ia/status` e confirmar `total_registros >= 200`.
- [ ] Manual: testar 5 medicamentos que estavam fora antes (ex: diazepam, captopril, anlodipino, pantoprazol, sertralina) e confirmar que retornam `match_tipo: "exato"` ou `"alias"`.

## O que NÃO está no escopo (não faça)

- **Não tocar no código** (`backend/app/ai/lookup_def.py`, `ia_farmaceutica.py`, etc.). É 100% trabalho de dados.
- **Não adicionar medicamentos fora da RENAME** sem discussão prévia (issue). Cobertura comercial completa é fora do MVP.
- **Não mudar threshold do fuzzy match** (`THRESHOLD_APROXIMADO=82` em `lookup_def.py`). Outra discussão.
- **Não traduzir nem editar o aviso na resposta** (`_AVISO_FIXO` em `ia_farmaceutica.py`). É contrato regulatório.

## Tempo estimado

- Levantamento dos 200 (consulta RENAME + curadoria): **4-6 horas**.
- Edição do CSV (linha por linha, atenção a typos e duplicatas): **2-4 horas**.
- Teste manual + ajustes: **1 hora**.

Total: **~1 dia útil**. Trabalho que pode ser feito em casa, no horário que você preferir.

## Suporte

- Dúvida sobre alguma escolha de princípio ativo / forma farmacêutica: abra comentário na issue ou contate o coordenador (`fabianotonaco@gmail.com`).
- Dúvida sobre git/PR: leia `CONTRIBUTING-EXTENSAO.md` seção "Como abrir um Pull Request".

## Aviso

Esse trabalho é **alto valor com baixa fricção técnica** — você não precisa saber programar, mas o resultado dobra (quase) o que a IA do PicSaúde consegue sugerir. Bom primeiro PR para qualquer extensionista de área de saúde.
