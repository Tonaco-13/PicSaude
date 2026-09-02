# TICKET-CANON-CONCENTRACAO-SLASH — notação de concentração deixa sufixo órfão no `canon_ativo`

| Campo | Valor |
|---|---|
| **Origem** | Guarda do flip E11+J45 (31/08, `test_semaforo_flip_e11_j45.py`) — achado real no dia da assinatura |
| **Classe** | `core` — `canon_ativo` é canonização do motor clínico (`semaforo_decisao.py`), mesma peça do strip de dose (#220) |
| **Para** | Engenheiro · **exige martelo do Fabiano** (régua `core`) |
| **Estado** | ✔️ **FECHADO 31/08 — PR #239** (`b57b6a2`, squash — RATIFICADA pelo arquiteto + martelo do Fabiano). Ver `docs/tickets/FILA-VIVA.md` §C (onda PCDT — camada 2) para o registro completo |

---

## §1 O defeito (reproduzido)

```
canon_ativo("Insulina Humana Regular 100 UI/ml") → "insulina humana regular/ml"
                                                    ≠ chave "insulina humana regular"
```

O `_DOSE_RE` (herdado do #220) casa `100 UI` e o remove — mas o **sufixo de
concentração** `/ml` fica órfão no fim da string. O lookup exato por dict-key
perde a chave e o semáforo devolve **amarelo falso** — o mesmo sintoma que o
strip de dose (#220) existia para matar, agora pela porta da concentração.

Nota de ordem dos fatos: `canon_ativo` não remove sufixo depois do strip — e o
strip de SAL casa por `endswith`, então `"…regular/ml"` também nunca casaria
sal-sufixo nenhum. O caso cai no amarelo silencioso.

## §2 Casos reais que digitam concentração

- Insulinas: **"100 UI/ml"** (frasco-ampola), "200 UI/ml" (concentrada),
  "100 UI/3,15 ml" (caneta — também com vírgula decimal e múltiplo de ml);
- Xaropes/soluções: "5 mg/ml", "250 mg/5 ml";
- Inalatórios: "200/6 mcg" (o próprio J45 assinado usa a combinação
  "formoterol + budesonida 200/6 mcg" na linguagem clínica corrente).

## §3 O que fazer

Estender `_DOSE_RE` para consumir um **sufixo de concentração opcional** após
a unidade:

```
(?:\s*/\s*\d+(?:[.,]\d+)?\s*(?:ml|mg|mcg|g|ui)\b)?     # "/ml", "/5ml", "/3,15 ml"…
(?:\s*/\s*(?:ml|mg|mcg|g|ui)\b)?                        # "/ml" sem número
```

e o caso combinado duplo "200/6 mcg" (número/número + unidade) — avaliar se
entra no mesmo patch ou fica declarado fora de escopo com teste marcando o
comportamento ATUAL (honesto), para não inflar o core de uma vez.

## §4 Invariantes (os mesmos do #220)

1. **Nenhum canônico existente muda** — re-rodar a comparação das bases
   (`decisao_semaforo.csv` + `posologia_sugerida.csv`) antes/depois; diff byte
   a byte tem que ser vazio.
2. Vermelho-antes-do-verde com o caso do §1.
3. Cuidado com o escape: a barra dentro de character class não; no grupo,
   escapar `\ `/ — e o regex é raw-string multiline como o atual.

## §5 Por que não entrou na PR da assinatura

A PR do flip é **curadoria** (dados assinados); conserto de `canon_ativo` é
`core` e via pelo rito próprio — martelo do Fabiano, PR separada. A guarda do
flip ficou com os casos aterrados de hoje e um comentário apontando para este
ticket.
