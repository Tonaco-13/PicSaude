# TICKET IA-EXPANSAO-DEF (hotfix antes da reunião 2026-05-27)

> **Classe (CLAUDE.md §10):** `local-extension` — só dados (CSV), nenhum código de lógica/contrato/estado/ledger.
> **Pacto:** Regra 3 — volume ~40 linhas em CSV; Edit direto pelo Code, sem necessidade de CODEX pré-impl.
> **Data:** 2026-05-25
> **Predecessor:** `c548be5 fix(ia): elevar THRESHOLD_APROXIMADO 82 -> 88` (a ser pushado nesta sessão)
> **Sucessor:** GFI #62 (expansão definitiva para 200 entradas pelos extensionistas — esse ticket é hotfix temporário até GFI fechar).
> **Redigido por:** Arquiteto, em 2026-05-25 à noite. Reunião de extensão UFPE postergada para quarta 2026-05-27 — temos terça inteira para polir.

---

## §1 Contexto

Base atual: **41 medicamentos** em `data/def_medicamentos.csv` (~28 princípios ativos cobertos). Cobertura inicial do MVP foi calibrada para os mais comuns, mas várias classes terapêuticas ficaram parciais (anti-hipertensivos, IBP, psicotrópicos, antibióticos).

O fix do threshold 82→88 (commit `c548be5`) eliminou os 5 falsos positivos críticos (`diazepam`, `captopril`, `pantoprazol`, `sertralina`, `metoclopramida` viravam "amoxicilina"). Mas o **comportamento agora é "nenhuma sugestão"** para esses mesmos termos — o que, depois do fix DX do `_renderizarSugestaoIA` (commit `4e089ea`), aparece no frontend como bloco neutro "Sem correspondência na base".

Para a reunião com os 7 extensionistas em **2026-05-27**, esse bloco aparecendo em metade das queries que extensionistas de medicina/farmácia vão testar dá péssima primeira impressão.

Este ticket adiciona **~40 medicamentos** à base, dobrando a cobertura sem mudar nenhuma linha de código. Trabalho 100% de dados.

## §2 Tese central

> **Cobrir os princípios ativos mais comuns que o ciclo cross-revisor confirmou como falsos positivos + os 35 mais comuns no Brasil que sabemos faltar, sem mexer em código.**

A expansão definitiva (200 entradas, RENAME completa) fica para a GFI #62 que será atacada por extensionista da área de saúde.

## §3 Inventário — 40 entradas em 5 lotes

Cada lote tem ~8 entradas. **Aplicar lote a lote, validando entre cada um** (ver §5).

### §3.1 Lote 1 — Psicotrópicos (7 entradas)

| Princípio ativo | Apresentação | Aliases sugeridos |
|---|---|---|
| diazepam | 5 mg comprimido | valium 5\|diazefar 5\|noan 5 |
| diazepam | 10 mg comprimido | valium 10\|diazefar 10 |
| sertralina | 50 mg comprimido | zoloft 50\|tolrest 50\|assert 50 |
| sertralina | 100 mg comprimido | zoloft 100\|tolrest 100 |
| escitalopram | 10 mg comprimido | lexapro 10\|exodus 10\|reconter 10 |
| escitalopram | 20 mg comprimido | lexapro 20\|exodus 20 |
| alprazolam | 1 mg comprimido | frontal 1\|alpraz 1\|tranquinal 1 |

### §3.2 Lote 2 — Anti-hipertensivos (8 entradas)

| Princípio ativo | Apresentação | Aliases sugeridos |
|---|---|---|
| captopril | 25 mg comprimido | capoten 25\|captosen 25 |
| captopril | 50 mg comprimido | capoten 50 |
| anlodipino | 5 mg comprimido | amlodipino 5\|norvasc 5\|presilam 5\|anlo 5 |
| anlodipino | 10 mg comprimido | amlodipino 10\|norvasc 10 |
| valsartana | 80 mg comprimido | diovan 80\|valpression 80 |
| valsartana | 160 mg comprimido | diovan 160 |
| atenolol | 50 mg comprimido | angipress 50\|atenoltrat 50 |
| furosemida | 40 mg comprimido | lasix 40\|neosemid 40 |

**Cuidado especial:** `anlodipino` com **N** é variação ortográfica brasileira comum (DCB original) — incluir como princípio ativo principal e listar `amlodipino` (com **M**) como alias. Isso evita o falso positivo legítimo que o Code testou ("anlodipino 5mg" tem 84.6 vs "amlodipino 5" — com threshold 88, **vai dar nenhum hoje**, então adicionar como alias direto resolve).

### §3.3 Lote 3 — IBP + Antieméticos + Anti-histamínicos (8 entradas)

| Princípio ativo | Apresentação | Aliases sugeridos |
|---|---|---|
| pantoprazol | 20 mg comprimido | pantozol 20\|peprazol 20 |
| pantoprazol | 40 mg comprimido | pantozol 40\|eupantol 40 |
| esomeprazol | 20 mg comprimido | nexium 20 |
| esomeprazol | 40 mg comprimido | nexium 40 |
| metoclopramida | 10 mg comprimido | plasil 10\|eucil 10 |
| ondansetrona | 4 mg comprimido | zofran 4\|vonau 4\|nausedron 4 |
| loratadina | 10 mg comprimido | claritin 10\|alergaliv 10\|histadin 10 |
| desloratadina | 5 mg comprimido | desalex 5\|leg 5 |

### §3.4 Lote 4 — Antibióticos + Antifúngicos + Antivirais (8 entradas)

| Princípio ativo | Apresentação | Aliases sugeridos |
|---|---|---|
| cefalexina | 500 mg capsula | keflex 500\|keflin 500 |
| sulfametoxazol + trimetoprima | 400 mg + 80 mg comprimido | bactrim\|bacteracin\|sulfatrim |
| clindamicina | 300 mg capsula | clindacin 300\|dalacin 300 |
| doxiciclina | 100 mg comprimido | vibramicina 100\|doxiclat 100 |
| fluconazol | 150 mg capsula | zoltec 150\|fluzol 150\|candinaten 150 |
| nistatina | 100000 ui/ml suspensao oral | micostatin\|candistat |
| aciclovir | 200 mg comprimido | zovirax 200 |
| aciclovir | 400 mg comprimido | zovirax 400 |

### §3.5 Lote 5 — Diabetes + Estatinas + Cardio + Corticoides (9 entradas)

| Princípio ativo | Apresentação | Aliases sugeridos |
|---|---|---|
| glibenclamida | 5 mg comprimido | daonil 5\|glimaxol 5 |
| gliclazida | 30 mg comprimido | diamicron 30 |
| gliclazida | 60 mg comprimido | diamicron 60 |
| empagliflozina | 10 mg comprimido | jardiance 10 |
| empagliflozina | 25 mg comprimido | jardiance 25 |
| rosuvastatina | 10 mg comprimido | crestor 10\|vivacor 10 |
| rosuvastatina | 20 mg comprimido | crestor 20 |
| aas | 100 mg comprimido | acido acetilsalicilico 100\|aspirina prevent 100\|somalgin 100 |
| clopidogrel | 75 mg comprimido | plavix 75\|iscover 75 |

**Total: 40 entradas adicionadas → base passa de 41 para 81.**

## §4 Schema do CSV (não mudar)

```
principio_ativo, nome_normalizado, forma_farmaceutica, unidade_dispensavel,
concentracao_texto, via_administracao, aliases, fonte, versao_base
```

Regras de cada coluna:

- `principio_ativo` — DCB/DCI em português, **minúsculo, sem acento**. Para combinações: `principio1 + principio2`.
- `nome_normalizado` — chave de busca exata. Formato: `<principio> <concentração> <forma>`. Minúsculo, sem acento. **Único na coluna.**
- `forma_farmaceutica` — `comprimido | capsula | solucao oral | suspensao oral | aerossol | injetavel | colirio | po para suspensao oral`
- `unidade_dispensavel` — geralmente igual a `forma_farmaceutica`, exceto quando vem em embalagem (`frasco`, `blister`, `ampola`).
- `concentracao_texto` — ex: `25 mg`, `100 mg/ml`, `400 mg + 80 mg`. **Espaço entre número e unidade** (consistente com base atual).
- `via_administracao` — `oral | injetavel | inalatorio | topica | oftalmica | retal`.
- `aliases` — pipe-separados (`|`). Lowercase, sem acento. Incluir nome comercial conhecido + variações do princípio ativo. **Sempre incluir o princípio ativo seguido da concentração curta** (ex: `losartana 50`) — é como o prescritor digita.
- `fonte` — sempre `DEF/BASE_LOCAL`.
- `versao_base` — **bump para `2026-05`** em TODAS as linhas (existentes inclusive). Indica que a base teve atualização.

## §5 Estratégia de validação por lote

**CRÍTICO:** o Code sinalizou margem apertada (`lantus 100UI` tem score 0.9 contra threshold 0.88). Adicionar medicamentos novos pode reduzir essa margem porque cada novo candidato entra no `_CANDIDATOS_FUZZY` e pode competir com matches existentes.

**Após cada lote:**

```bash
cd backend && pytest tests/test_ia_farmaceutica.py -v
```

Deve continuar **66/66 verde** (65 antigos + 1 do c548be5).

**Após cada lote, rodar smoke crítico** (Python ad-hoc):

```python
import sys; sys.path.insert(0, '.')
from app.ai.lookup_def import buscar_medicamento

# 8 matches válidos que NÃO podem regredir (preservados pelo Code em c548be5)
preservados = [
    ('rivotril 2mg', 'clonazepam'),
    ('novalgina 500', 'dipirona sodica'),
    ('lantus 100UI', 'insulina glargina'),   # ← margem apertada, atenção
    ('dipirona 500', 'dipirona sodica'),
    ('amoxicilina 500', 'amoxicilina'),
    ('metformina 850', 'metformina'),
    ('losartana 50', 'losartana potassica'),
    ('paracetamol 500', 'paracetamol'),
]

# 5 que eram falsos positivos antes do c548be5 — agora viram MATCH (estão na base)
novos_matches = [
    ('diazepam 5mg', 'diazepam'),
    ('captopril 25mg', 'captopril'),
    ('pantoprazol 40mg', 'pantoprazol'),
    ('sertralina 50mg', 'sertralina'),
    ('metoclopramida 10mg', 'metoclopramida'),
]

# 5 que continuam fora da base ampliada — devem dar "nenhum"
fora_da_base = [
    ('hidroxicloroquina 400mg', None),
    ('escitalopram 5mg', None),  # ← 10 e 20 estão no lote 1, 5mg não
    ('nimesulida 100mg', None),
    ('tadalafila 5mg', None),
    ('xyz inexistente 999', None),
]

for q, pa_esperado in preservados:
    r = buscar_medicamento(q)
    ok = r['principio_ativo'] == pa_esperado
    flag = '✅' if ok else '❌'
    print(f'{flag} PRESERVADO {q:25} → {r["principio_ativo"]} (esperado: {pa_esperado}) score={r["score"]:.2f}')

for q, pa_esperado in novos_matches:
    r = buscar_medicamento(q)
    ok = pa_esperado in (r['principio_ativo'] or '')
    flag = '✅' if ok else '❌'
    print(f'{flag} NOVO MATCH {q:25} → {r["principio_ativo"]} (esperado: {pa_esperado}) match_tipo={r["match_tipo"]}')

for q, _ in fora_da_base:
    r = buscar_medicamento(q)
    ok = r['match_tipo'] == 'nenhum'
    flag = '✅' if ok else '❌'
    print(f'{flag} FORA BASE  {q:25} → {r["principio_ativo"] or "nenhum"} match_tipo={r["match_tipo"]}')
```

**Critério de parada:** se algum `PRESERVADO` ou `FORA BASE` falhar, **parar a expansão** e me chamar (Arquiteto). Pode exigir subir threshold para 90 ou refatorar para `WRatio-by-token` (que o Code já antecipou como solução arquitetural).

**Não é necessário** validar `NOVO MATCH` lote a lote — só após o lote correspondente. Ex: após Lote 1 (psicotrópicos), `diazepam` e `sertralina` devem virar match; `captopril` ainda dá nenhum (entra no Lote 2).

## §6 Especificação de cada lote (passo a passo)

Para cada lote (1 a 5):

1. **Abrir** `data/def_medicamentos.csv` em editor de texto puro (não Excel — Excel quebra encoding/quote).
2. **Adicionar as linhas do lote** ao final do arquivo, respeitando o schema §4 (atenção a: espaços nas concentrações, aliases sem acento, pipes corretos).
3. **Atualizar `versao_base` de TODAS as linhas** (existentes + novas) para `2026-05`. Pode fazer via `sed -i '' 's/2026-03/2026-05/g' data/def_medicamentos.csv` (uma única passada antes do primeiro lote ou após o último — escolha sua, mas faça uma única vez).
4. **Rodar pytest** focal: `cd backend && pytest tests/test_ia_farmaceutica.py -v` — deve passar 66/66.
5. **Rodar smoke** §5 — deve dar todos ✅.
6. **Se 4 ou 5 falharem**, reverter o lote (`git checkout data/def_medicamentos.csv` ou desfazer manualmente) e me chamar antes de prosseguir.

## §7 Ao final dos 5 lotes — commit + push

```bash
git add data/def_medicamentos.csv
git commit -m "data(ia): expandir def_medicamentos de 41 para 81 entradas (hotfix pré-reunião extensão)

40 medicamentos novos em 5 lotes terapeuticos: psicotropicos (7),
anti-hipertensivos (8), IBP+antiemeticos+anti-histaminicos (8),
antibioticos+antifungicos+antivirais (8), diabetes+estatinas+cardio+
corticoides (9). versao_base bumped para 2026-05.

Origem: TICKET-IA-EXPANSAO-DEF-HOTFIX.md (Arquiteto, 2026-05-25).
Hotfix temporario ate GFI #62 (expansao para 200 entradas pelos
extensionistas) fechar.

Smoke validado: 8 matches preservados sem regressao, 5 ex-falsos-
positivos viram match correto, 5 fora-da-base continuam nenhum.
Lantus 100UI mantem score >= 0.88 (verificado ao final de cada lote).

pytest tests/test_ia_farmaceutica.py: 66/66 verde."

git push origin main
```

## §8 Anti-escopo

**NÃO TOCAR:**
- Código (`lookup_def.py`, `ia_farmaceutica.py`, `normalizacao_medicamento.py`, etc.). 100% trabalho de dados.
- Threshold (`THRESHOLD_APROXIMADO=88`). Se a margem do lantus cair abaixo de 0.88, **parar e chamar Arquiteto** — decisão arquitetural.
- `ia_exames.py`, `ia_cid.py`, `ia_documental.py` e respectivas bases. Outro escopo.
- Seed do demo (`seed_demo.py`). Próximo trabalho (spec separada).
- Testes além do `test_ia_farmaceutica.py`. Não há motivo para tocar outros.

## §9 Critério de fechamento

- [ ] 40 linhas novas no CSV, schema correto, 0 duplicatas.
- [ ] `versao_base` = `2026-05` em todas as 81 linhas.
- [ ] `pytest tests/test_ia_farmaceutica.py -v` → 66/66 verde.
- [ ] Smoke §5 — todos os 18 cenários ✅.
- [ ] `GET /ia/status` mostra `total_registros: 81`, `versao_base: "2026-05"`.
- [ ] Commit + push autorizados (mensagem padrão §7).

## §10 Volume estimado

- Curadoria dos aliases + edição CSV: **45-60 min**.
- Smoke validation a cada lote: **5 min × 5 = 25 min**.
- Commit + push: **5 min**.

**Total: ~1h30 de trabalho do Code.** Cabe folgado na noite de segunda ou manhã de terça.

---

## §11 Fechamento — 2026-05-25 (mesma noite)

Status: **fechado**. Implementação consolidada no commit `579b619` (após amend sobre `3a33cc6` para substituir `nimesulida 100mg` por `glucosamina 1500mg` no teste).

### §11.1 Commits envolvidos

| Commit | Conteúdo |
|---|---|
| `c548be5` | Pré-requisito — threshold 82→88 + teste de regressão original (queries: diazepam, captopril, pantoprazol, sertralina, metoclopramida) |
| `579b619` | Expansão — 41→81 entradas em 5 lotes + reformulação do teste (queries finais: tadalafila, sildenafila, hidroxicloroquina, glucosamina, vitamina B12) + bump `versao_base` 2026-03→2026-05 |

### §11.2 Resultados validados

| Critério §9 | Estado |
|---|---|
| 40 linhas novas no CSV, schema correto, 0 duplicatas | ✅ |
| `versao_base` = `2026-05` em todas as 81 linhas | ✅ |
| `pytest tests/test_ia_farmaceutica.py -v` verde | ✅ — 65/65 (correção da §11.4 abaixo) |
| Smoke §5 — todos os 18 cenários ✅ | ✅ — 8 preservados + 5 novos matches + 5 fora-da-base |
| `GET /ia/status` mostra `total_registros: 81`, `versao_base: "2026-05"` | ✅ |
| Commit + push autorizados (mensagem padrão §7) | ✅ |

### §11.3 Cuidados do Code que merecem registro

- **Margem do `lantus 100UI` preservada em 0.020 do início ao fim** da expansão. Score 0.9 mantido contra threshold 0.88 em todos os 5 lotes (esperado risco de queda, não materializou).
- **Decisão correta de amend (vs commit follow-up)** após escolha final da query substituta — commit `3a33cc6` original nunca foi pushado, então amend manteve história limpa em um commit por ticket.
- **Anlodipino DCB convivendo com amlodipino besilato** registrado como observação não-bloqueante. Vira 2º bullet da GFI #62 (consolidação semântica).

### §11.4 Erro do Arquiteto (mea culpa pequeno)

§5 do ticket estimava `pytest` em **66/66** após o ciclo. Real foi **65/65**. Causa: presumi que o teste `test_query_fora_da_base_nao_retorna_falso_positivo` seria *adicionado* na expansão, mas ele já existia desde `c548be5` (Arquiteto também). O ciclo apenas *reformulou* as queries do teste existente, não adicionou um teste novo. **+0 contagem, não +1.** Não afeta funcionamento — só aritmética narrativa. Registrado aqui para futura calibração quando especificar tickets que tocam testes pré-existentes.

### §11.5 Achado bloqueador resolvido durante o ciclo (Opção A do Arquiteto)

Durante o Lote 1, o Code identificou que as 5 queries do teste de regressão (`diazepam`, `captopril`, `pantoprazol`, `sertralina`, `metoclopramida`) eram exatamente os medicamentos que o ticket adicionaria à base — invariante do teste ficava logicamente impossível. Code reverteu o lote, reportou e pediu decisão.

Arquiteto decidiu **Opção A** (atualizar queries do teste, preservar invariante semântica): substituir as 5 queries por medicamentos plausíveis em categorias "definitely-out" do MVP ambulatorial (ED, anti-malárico especializado, suplementos). Code aplicou após validar com grep contra base completa que nenhuma substituta colidia.

Refinamento posterior do Arquiteto: trocar `nimesulida 100mg` (sugestão inicial — Code apontou risco de inevitabilidade por ser top-3 AINE prescrito no Brasil) por `glucosamina 1500mg` (suplemento articular não-prescrição-controlada — categoria coerente com vitamina B12). Aplicado via amend.

### §11.6 Itens deferidos

- **`aviso_base` em `routers/ia.py:211`** ainda diz "41 medicamentos" — Code respeitou §8 anti-escopo ("NÃO TOCAR código"). Vai junto com a spec do seed do Cidadão demo (próxima rodada).
- **GFI #62 atualizado** com 2 bullets: (a) atenção ao teste de regressão antes de expandir; (b) consolidação de entradas semanticamente próximas (anlodipino × amlodipino besilato).
- **`CONTRIBUTING-EXTENSAO.md` atualizado** — referência mudou de "41 medicamentos" para "81 medicamentos (subset MVP estendido — expansão completa via GFI #62)".
- **Estratégia de teste "fora-da-base"** monitorada como dívida arquitetural longa: enquanto ED, anti-malárico especializado e suplementos permanecerem fora do escopo do MVP ambulatorial, queries são robustas. Se algum desses entrar por demanda regulatória futura, repensar para gerar queries aleatórias a partir de whitelist "definitely-out" mantida separadamente do CSV.

### §11.7 Próximos passos imediatos

1. Code aplica `aviso_base` "41 → 81" em commit junto com seed do Cidadão demo (spec na fila).
2. Quando CODEX rodada 3 sobre `origin/main` consolidado entregar zero P1, Etapa 6 fecha formalmente. Este ticket de hotfix é satélite da Etapa 6 — não bloqueia o fechamento dela.
— Arquiteto (Opus 4.7)
