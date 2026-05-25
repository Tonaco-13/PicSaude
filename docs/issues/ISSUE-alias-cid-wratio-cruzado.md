# GFI #63 — alias da base CID dispara WRatio cruzado entre categorias

> **Tipo:** good-first-issue
> **Origem:** Observação colateral do hotfix JULES-AUDIT 2026-05-25 (commit `f796f56`). Não bloqueou o demo porque o top-1 estava correto, mas é o mesmo pattern do bug fechado em `c548be5` (WRatio + tokens comuns + base não-disjunta).
> **Labels sugeridas:** `good-first-issue`, `dados`, `ia`, `cid`.
> **Perfil ideal:** alguém com formação em saúde (medicina, enfermagem, farmácia) que conheça a estrutura do CID-10. Auditoria manual + 1 teste de regressão; **não precisa saber Python avançado** (basta editar CSV/dict e rodar pytest).

---

## Sintoma

Smoke pós-hotfix `f796f56` mostra que `buscar_cid("dor de cabeca")` retorna:

```
R51    Cefaleia                                  score 1.00   ✅ correto, top-1
G43.9  Enxaqueca não especificada                score 0.90   ✅ defensável
I48    Fibrilação e flutter atrial               score 0.90   ❌ clinicamente errado
```

`I48` é uma categoria CID-10 do capítulo IX (doenças do aparelho circulatório), completamente disjunta de `R51` (capítulo XVIII — sintomas/sinais). Não há relação clínica entre cefaleia e fibrilação atrial. O match aparece porque `WRatio` empata em 0.90 contra algum alias da base CID que compartilha tokens com a query normalizada `"dor de cabeca"` ou com `"cefaleia"`.

**Por que não vexa o demo (e portanto é P3, não P1):** o `R51` aparece em **primeiro lugar** com score 1.00. O usuário do demo lê a primeira sugestão e ignora as demais. Mas se a base CID crescer (próxima rodada de expansão), o padrão pode se inverter — `R51` cair de 1.00 (alias exato) e algum falso positivo subir.

## Causa provável

Mesmo pattern do bug fechado em `c548be5`:

1. WRatio (do `rapidfuzz`) usa um agregado de scorers (`ratio`, `partial_ratio`, `token_set_ratio`, `token_sort_ratio`) e devolve o **máximo**.
2. Quando dois textos compartilham um único token comum mas distintivo (ex: alguma palavra como "atrial", "aguda", "crônica", "9" etc.), `partial_ratio` ou `token_set_ratio` infla artificialmente.
3. Resultado: secundárias com score idêntico (0.90) e ordenação dependente de detalhes da base.

A correção foi feita para o caso simétrico em farmacêutica (threshold de 82 → 88) e parcialmente para CID em `f796f56` (0.75 → 0.88), mas o threshold global não resolve casos onde o falso positivo natural já é 0.90.

## O que você vai fazer

### Parte 1 — Auditoria manual da base CID

Localizar a base: `backend/app/ai/base_cid.py` (busque pela estrutura `_REGISTROS_CID` ou similar). Cada registro tem `codigo_cid`, `descricao`, e `aliases` (lista de strings).

Para cada categoria de capítulo CID-10 representada na base, **revisar os aliases procurando "tokens-veneno"**:

- Palavras genéricas que aparecem em múltiplas categorias: `aguda`, `cronica`, `geral`, `nao especificada`, `outras`, `local`.
- Números soltos em aliases: ex. `"9"` ou `"0"` (terminações típicas de subcategoria como `.9`).
- Abreviações ambíguas: `crm`, `dst`, `tu`, etc.

Para cada token-veneno identificado, decidir:
- **Remover do alias** — se não traz valor semântico (ex: remover "9" solto, manter "9 dias" se for clínico).
- **Ancorar com mais tokens** — em vez de `"aguda"` solto, usar `"aguda apendice"` se for sobre apendicite.

### Parte 2 — Mudança no scoring de secundárias

Em `backend/app/ai/base_cid.py`, a função `buscar(...)` itera resultados aproximados e os agrega via `process.extract` ou similar. Considerar adotar dois cortes:

- **Top-1** (sugestão principal): mantém `threshold = 0.88` (atual).
- **Secundárias** (sugestões 2-N): `score_cutoff_secundarias = 0.92` (mais agressivo).

Pseudo-código sugerido:

```python
def buscar(texto, max_resultados=5, threshold=0.88, threshold_secundarias=0.92):
    # ... fluxo existente ...
    if not resultados:
        return []

    top = resultados[0]
    secundarias = [r for r in resultados[1:] if r.score >= threshold_secundarias]
    return [top] + secundarias[:max_resultados - 1]
```

Justificativa: o top-1 é fortemente prioritário e tende a ser o match correto (alias exato ou substring). Secundárias com score baixo (0.88-0.92) são as que geralmente trazem falsos positivos — barrar essas reduz ruído sem perder cobertura útil.

### Alternativa: filtro por capítulo CID-10 (em vez de — ou complementando — threshold duplo)

A primeira letra do código CID-10 codifica capítulo clínico amplo:
- **R** = sintomas/sinais (ex: R51 Cefaleia)
- **I** = doenças do aparelho circulatório (ex: I48 Fibrilação atrial)
- **G** = sistema nervoso (ex: G43 Enxaqueca)
- **A/B** = doenças infecciosas e parasitárias

Match secundário cross-capítulo em score moderado é, na esmagadora maioria, ruído de token-veneno: a queixa "dor de cabeça" não tem rota plausível para diagnóstico circulatório como I48. No caso descoberto no smoke, top-1 R51 está em capítulo R e I48 está em capítulo I — bloqueado naturalmente pelo filtro.

**Vantagem sobre threshold duplo:** captura "match clinicamente inverossímil" sem precisar calibrar 0.92 vs 0.91 — o critério é semântico (categoria do CID), não estatístico, e tende a envelhecer melhor conforme a base cresce.

**Implementação aproximada (5-10 linhas):**

```python
def _filtrar_secundarias_por_capitulo(top1, secundarias):
    capitulo_top1 = top1.codigo[0]  # primeira letra do código CID-10
    return [
        s for s in secundarias
        if s.codigo[0] == capitulo_top1 or s.score >= 0.95
    ]
```

O extensionista escolhe entre as duas abordagens (ou combina) durante a auditoria — esta GFI não prescreve.

### Parte 3 — Teste de regressão

Em `backend/tests/test_ia_cid.py`, adicionar:

```python
def test_secundarias_nao_pertencem_a_capitulo_distinto_do_top1(self):
    """Regressão GFI #63: 'dor de cabeca' tinha R51 (top-1 correto)
    + I48 Fibrilação atrial (secundária errada, capítulo distinto).
    Após threshold de secundárias mais agressivo, capítulos devem
    convergir."""
    casos = [
        ("dor de cabeca", "R51"),    # cap XVIII (sintomas)
        ("pressao alta",  "I10"),    # cap IX (circulatório)
        ("diabetes",      "E11"),    # cap IV (endócrino)
    ]
    for query, top_esperado in casos:
        r = buscar_cid(query)
        sugestoes = r.get("cid_sugeridos", [])
        assert sugestoes, f"{query} não retornou sugestões"
        assert sugestoes[0]["codigo"].startswith(top_esperado[0]), \
            f"top-1 de {query} = {sugestoes[0]['codigo']}, esperado começar com {top_esperado[0]}"
        # Capítulo CID = primeira letra do código
        cap_top = sugestoes[0]["codigo"][0]
        for s in sugestoes[1:]:
            assert s["codigo"][0] == cap_top, \
                f"{query}: top-1 {sugestoes[0]['codigo']} (cap {cap_top}), " \
                f"mas secundária {s['codigo']} é de capítulo {s['codigo'][0]}"
```

A heurística "capítulo = primeira letra do código" não é universalmente correta (capítulos II usam C/D, etc.), mas serve como aproximação útil para o subset MVP. Refinar conforme necessário.

## Critério de aceite

- [ ] Auditoria manual feita; lista de tokens-veneno encontrados documentada na PR.
- [ ] Mudança no `buscar(...)` da base CID com `threshold_secundarias`.
- [ ] Teste de regressão acima passa (e nenhum outro teste de CID quebra).
- [ ] Smoke das 3 queries do JULES-AUDIT (`dor de cabeca`, `infeccao urinaria`, `rx` — esta última é TUSS, não CID, então só validar as 2 primeiras) continua correto.
- [ ] Secundárias retornadas não atravessam capítulo CID-10 quando `score < 0.95` (filtro por capítulo) OU `score < 0.92` (threshold duplo) — extensionista escolhe; teste de regressão valida a escolha.
- [ ] PR descreve as queries de teste manuais utilizadas.

## Anti-escopo

- **Não tocar a base farmacêutica** — já fechada em `c548be5` + `579b619`.
- **Não tocar a base TUSS / `ia_exames.py`** — já fechada em `f796f56` com guard de length.
- **Não tocar `_norm` / `normalizar_texto_clinico`** sem motivo direto — mudanças no normalizador têm efeito amplo e podem mascarar outros bugs.
- **Não mudar threshold global do top-1** (0.88) — fixar a separação top-1 vs secundárias é a abordagem proposta.

## Tamanho estimado

- Auditoria manual da base CID + curadoria de aliases: **45-60 min** (depende do tamanho da base no momento da issue).
- Mudança em `buscar(...)` + teste de regressão: **30-45 min**.
- **Total: 1-2h** de trabalho do extensionista.

## Referências

- `c548be5` — fix análogo na base farmacêutica (threshold 82 → 88).
- `f796f56` — fix análogo na base CID (threshold 0.75 → 0.88) + guard de length em TUSS. Esta issue é o follow-up natural para o caso onde 0.88 não é suficiente porque o falso positivo já nasce em 0.90.
- `docs/HOMOLOGACAO-DEMO.md` — roteiro de QA. Considerar adicionar este caso quando o fix for aplicado.
- `CONTRIBUTING-EXTENSAO.md` § "Sobre a IA do PicSaúde" — explica o porquê do lookup determinístico vs LLM (e por que esses bugs de threshold são esperados em base pequena).

---

*Issue aberta como follow-up do hotfix JULES-AUDIT 2026-05-25. Não bloqueia a reunião de extensão 2026-05-27 — top-1 está correto. Atacar quando houver tempo.*
