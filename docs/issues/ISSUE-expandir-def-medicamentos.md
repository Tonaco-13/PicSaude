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

## ⚠️ Atenção crítica antes de adicionar entradas (atualizado 2026-05-25)

Existe um teste de regressão chamado `test_query_fora_da_base_nao_retorna_falso_positivo` em `backend/tests/test_ia_farmaceutica.py` que protege contra o bug do `WRatio` que estava confundindo classes terapêuticas (corrigido em `c548be5`).

Esse teste contém uma lista de medicamentos **plausíveis** que devem continuar retornando `match_tipo: "nenhum"` mesmo depois da expansão da base. Lista atual (após hotfix 2026-05-25):

```
tadalafila 5mg, sildenafila 50mg, hidroxicloroquina 400mg,
glucosamina 1500mg, vitamina B12 1000mcg
```

**Antes de adicionar qualquer medicamento ao CSV:** rode `grep -i "<medicamento>" backend/tests/test_ia_farmaceutica.py` para confirmar que ele não está na lista de "fora-da-base esperado".

Se uma das suas adições colidir com a lista do teste:
- **NÃO remova o teste** — ele protege contra bug crítico já reportado.
- **NÃO troque a lista para junk** (`'xyz 999'`) — `test_nenhum_para_junk` já cobre isso.
- **SUBSTITUA** a query colidida por outra medicamento da MESMA categoria de "definitely-out" (ED, suplementos, anti-malárico especializado, etc).

Veja o histórico: no hotfix de 25/05, a lista original do teste (`diazepam, captopril, pantoprazol, sertralina, metoclopramida`) precisou ser renovada porque todos esses 5 entraram na base. Lista nova foi escolhida nas categorias acima por improbabilidade de entrar em rodadas próximas — mas o próximo grande aumento (esta GFI) precisa reverificar.

### Consolidação de entradas semanticamente próximas (segunda atenção)

A expansão de 25/05 (commit `579b619`) adicionou `anlodipino` (DCB brasileira, sem **M**) como princípio ativo principal, com `amlodipino` (com **M**) como alias. Mas a base já tinha a linha legada `amlodipino besilato 5 mg comprimido` (ID original do MVP). **Hoje a base tem 2 entradas semanticamente próximas convivendo**, uma puxando pela DCB nova brasileira e outra pelo nome antigo do princípio ativo + sal.

Isso é tolerável (lookup encontra ambos via aliases cruzados), mas é dívida arquitetural pequena. Ao trabalhar nesta GFI, considere:

1. **Auditar entradas duplicadas** — rodar `grep` por princípio ativo na coluna `nome_normalizado` e identificar onde há mais de uma entrada para o mesmo PA com forma+concentração diferentes (esperado: várias linhas legítimas) vs onde há entradas redundantes (mesmo PA + mesma forma + mesma concentração com naming diferente — caso do anlodipino).
2. **Decidir convenção** — para cada caso, escolher **uma** convenção de nome (preferência: DCB atual da Anvisa) e listar variações antigas como aliases.
3. **Não consolidar agressivamente** — entradas que servem propósitos clínicos diferentes (ex: amoxicilina vs amoxicilina+clavulanato) devem permanecer separadas. Consolidação só onde há clara redundância semântica.

Resultado esperado: base ≥ 200 entradas com **0 duplicatas semânticas redundantes**, mantendo riqueza de aliases para cobrir variações coloquiais e nomes comerciais.

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
