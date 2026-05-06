# Arquitetura de IA Farmacêutica — PicSaúde

> Documento oficial de arquitetura. Não contém implementação.
> Aprovado em revisão cruzada Claude Code + ChatGPT (2026-03-18).
> Fase de implementação: IA-1 (planejada após consolidação do Ticket 13).

---

## A. Papel da IA no PicSaúde

**Princípio contratual:** a IA é assistiva, nunca decisória.

Em farmácia regulatória, a responsabilidade legal da prescrição pertence ao CRM/prescritor.
A IA não pode ser fonte de verdade clínica.

| Função | Permitido | Proibido |
|---|---|---|
| Sugerir `unidade_quantidade` | ✓ | Preencher sem confirmação |
| Sugerir `forma_farmaceutica` | ✓ | Corrigir silenciosamente |
| Alertar incoerência | ✓ | Bloquear emissão |
| Normalizar nome do medicamento | ✓ | Alterar o que foi digitado |
| Explicar para o cidadão | ✓ | Dar orientação clínica |

**Decisão arquitetural fundamental:** a IA do PicSaúde é **lookup-based, não generativa**.

Essa não é uma limitação — é a escolha correta para o contexto sanitário.
Um sistema lookup não alucina. Cada sugestão tem rastreabilidade direta a uma entrada da DEF/RENAME.
Auditoria sanitária exige que "por que o sistema sugeriu X" tenha resposta determinística.

---

## B. Arquitetura Leve Proposta

### Stack

| Componente | Biblioteca | Justificativa |
|---|---|---|
| Normalização textual | `unidecode` + `re` | Acentos, abreviações, caixa |
| Fuzzy matching | `rapidfuzz` | CPU-only, sem dependência C pesada |
| Base estruturada | SQLite (já em uso) | Sem nova infraestrutura |
| Classificador leve | `scikit-learn` | Apenas v2+; v1 dispensa ML |
| Serialização de modelo | `joblib` | Padrão sklearn |
| Manipulação ETL | `pandas` | Apenas no pipeline offline, não em runtime |

`spaCy` **não é necessário** para o MVP. O PicSaúde recebe campos estruturados
(prescritor preenche `medicamento`, `forma`, `unidade` separadamente).
Fuzzy matching sobre string normalizada é suficiente.

### Base Farmacêutica Local — tabela `def_medicamentos`

```sql
principio_ativo       TEXT    -- nome canônico DEF (ex: AMOXICILINA)
nomes_comerciais      TEXT    -- JSON array (Amoxil, Amoxil BD, ...)
forma_farmaceutica    TEXT    -- canônico (COMPRIMIDO, CÁPSULA, SOLUÇÃO INJETÁVEL)
unidade_dispensavel   TEXT    -- vocabulário controlado (comprimido, mL, UI, mg, g...)
concentracao_padrao   TEXT    -- ex: "500 mg", "875+125 mg"
via_administracao     TEXT    -- ORAL, INTRAVENOSA, SUBCUTÂNEA
classe_terapeutica    TEXT    -- ATC code (ex: J01CA04)
aliases               TEXT    -- JSON array de variações de escrita
fonte                 TEXT    -- DEF | RENAME | CMED
versao_base           TEXT    -- data da publicação da fonte (ex: "2024-10")
ativo_anvisa          INTEGER -- 1 = ativo, 0 = retirado
```

Essa tabela fica no mesmo `pix_saude_pe.db`, lado a lado com o CNES —
padrão já estabelecido no projeto.

### Pipeline de Inferência

```
texto digitado pelo prescritor
        │
        ▼
[1] Normalização
    lowercase → unidecode → strip espaços
    expansão de abreviações (compdo→comprimido, inj→injetável)
        │
        ▼
[2] Lookup exato
    SELECT * FROM def_medicamentos WHERE principio_ativo = texto_normalizado
    ── hit → score_correspondencia = 1.0, match_tipo = "exato"
        │
        ▼ (se não encontrado)
[3] Fuzzy matching
    rapidfuzz.process.extract(texto, candidatos, scorer=token_sort_ratio)
    score ≥ 85 → sugestão normal
    score 70–84 → sugestão com aviso de baixa correspondência
        │
        ▼
[4] Enriquecimento por regras explícitas
    (arquivo domain/medicamento_regras.py — dados, não lógica de negócio)
    Se forma = "SOLUÇÃO INJETÁVEL" → unidade ∈ {mL, UI}
    Se forma = "COMPRIMIDO"        → unidade = comprimido
    Se princípio ativo ∈ insulinas → unidade = UI
        │
        ▼
[5] Saída estruturada
    {
      "sugestoes_unidade": ["comprimido"],
      "sugestoes_forma":   ["COMPRIMIDO REVESTIDO"],
      "alertas":           [],
      "fonte":             "DEF/RENAME 2024-10",
      "score_correspondencia": 0.97,
      "match_tipo":        "exato" | "fuzzy" | "regra",
      "motivo":            "Princípio ativo AMOXICILINA com forma COMPRIMIDO mapeia unidade dispensável 'comprimido' pela regra R-04",
      "aviso":             "Sugestão farmacológica auxiliar. Decisão clínica é do prescritor."
    }
```

**`score_correspondencia`, `match_tipo`, `fonte` e `motivo` são obrigatórios na resposta.**
Sem esses quatro campos, a sugestão é "mágica". Com eles, é evidência computacional auditável.

> **Nota semântica:** o campo se chama `score_correspondencia`, não `confianca`.
> "Confiança" soa forte demais em contexto clínico. Correspondência é mais preciso:
> descreve a similaridade textual, não uma certeza sobre a indicação terapêutica.

### ETL offline da DEF/ANVISA

Script offline `scripts/importar_def.py` (não parte do runtime):

1. Lê XLS/CSV da DEF (GGMED/ANVISA — download público)
2. Normaliza e deduplica
3. Popula `def_medicamentos` no SQLite
4. Grava `versao_base` com a data da publicação

Fontes públicas relevantes:
- DEF (Denominação Farmacêutica) — GGMED/ANVISA
- RENAME (Relação Nacional de Medicamentos Essenciais)
- CMED (Câmara de Regulação do Mercado de Medicamentos)

Frequência de atualização recomendada: semestral (cadência da DEF).
Cada sugestão emitida pode referenciar qual `versao_base` estava ativa no momento.

---

## C. Casos de Uso Prioritários

Ordenados por relação valor/risco:

### 1. Normalização de nome do medicamento ← primeiro
Transformar "amoxilina 500" → "AMOXICILINA".
Fundação para tudo. Risco zero — não altera o campo, apenas usa internamente para lookup.

### 2. Sugestão de `unidade_quantidade` ← segundo
Campo e vocabulário controlado já existem em `domain/medicamento.py`.
Pipeline lookup + regras cobre ~85% dos casos.
Alto valor, baixo risco.

### 3. Validação de coerência medicamento × forma × unidade ← terceiro
Alertas não bloqueantes. "Insulina em comprimido" gera alerta, nunca bloqueia emissão.

### 4. Sugestão de `forma_farmaceutica` ← quarto
Mais variação de nomenclatura que unidade, mas mesmo pipeline.

### 5. Explicação simples para o cidadão ← fase posterior
Exige controle rigoroso de linguagem clínica. Fora do escopo do MVP de IA.

---

## D. Riscos e Salvaguardas

### Risco 1 — IA inventando formas farmacêuticas
**Causa:** usar LLM generativo ou classificador mal calibrado.
**Salvaguarda:** arquitetura lookup-only. Se não está na DEF, não é sugerido.
Nunca preencher campo com `score_correspondencia` abaixo do threshold configurável.

### Risco 2 — Excesso de confiança exposto ao usuário
**Causa:** frontend mostrando sugestão sem sinalizar origem.
**Salvaguarda:** toda sugestão exibe `match_tipo`, `fonte` e `motivo`.
UX diferencia visualmente "sugestão exata" de "sugestão aproximada" (fuzzy).

### Risco 3 — Acoplamento entre IA e emissão
**Causa:** backend recusar emissão sem validação da IA.
**Salvaguarda:** a IA é endpoint consultivo separado. O `POST /prescricoes` não depende dela.
Se o serviço de IA estiver offline, a prescrição ainda é emitida normalmente.

### Risco 4 — Staleness da base DEF
**Causa:** base desatualizada sugerindo apresentações retiradas do mercado.
**Salvaguarda:** `versao_base` visível no log de cada sugestão.
Alerta operacional se `versao_base` > 12 meses.

### Risco 5 — Uso em contexto clínico indevido
**Causa:** cidadão ou prescritor interpretando sugestão como indicação terapêutica.
**Salvaguarda:** campo `aviso` obrigatório em toda resposta da IA.
Aviso gravado no log junto com a sugestão (rastreável em auditoria).

### Risco 6 — Captura de aprendizado sem rastreabilidade
**Causa:** tabela de correções sem padrão de imutabilidade.
**Salvaguarda:** tabela `ia_correcoes` segue o padrão ledger do PicSaúde — INSERT only, nunca UPDATE.

```
ia_correcoes:
  campo                 -- "unidade_quantidade" | "forma_farmaceutica"
  medicamento_normalizado
  sugestao_ia
  valor_aceito_prescritor
  foi_correcao          -- boolean
  match_tipo            -- exato | fuzzy | regra
  score_correspondencia
  versao_base_def       -- qual versão da base estava ativa
  registrado_em
```

CNS do prescritor não entra nessa tabela — dados de melhoria de modelo não exigem identificação individual.

---

## Sequência de Implementação (Fase IA-1)

Quando aprovada a abertura da fase:

```
1. scripts/importar_def.py  →  tabela def_medicamentos
2. domain/ia_farmaceutica.py  →  normalização + lookup + regras
3. routers/ia.py  →  GET /ia/sugestao?medicamento=...
4. prescritor.html  →  debounce no campo medicamento → fetch → chips de sugestão
5. tabela ia_correcoes  →  registra aceitações e correções (ledger)
```

Stack total de produção: `rapidfuzz`, `unidecode`, `sqlite3` (já presente).
`scikit-learn` entra apenas em IA-2, se o volume de correções justificar classificador supervisionado.
Nenhuma dependência de GPU em nenhuma fase.
