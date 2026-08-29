# TICKET-CANON-ATIVO-DOSE-SUFFIX — Strip de dose no `canon_ativo` (amarelo falso)

| Campo | Valor |
|---|---|
| **Semáforo** | 🟥 **Vermelho** — core-adjacente, exige teste próprio. Sem pressa, mas **não perder**. |
| **Classe** | `core` (motor clínico `semaforo_decisao.py` — canonicalização) |
| **De** | Arquiteto (Z), por registro do conselheiro (martelo 2026-08-07, item A) |
| **Para** | Engenheiro (quando a fila V2 esvaziar) · cc: Revisor (core → consultivo bloqueante) · Conselheiro · Fabiano |
| **Data** | 2026-08-07 |
| **Origem** | Conselheiro, item A do martelo: *"Losartana 50mg → amarelo falso"* |
| **Pré-requisito** | Nenhum. **Independente da fila V2.** |
| **Estado** | ⏳ Registrado (rascunho de ticket). Sem pressa — acende quando Fabiano agendar. |

---

## §1 Contexto — o bug

`canon_ativo` (`backend/app/domain/semaforo_decisao.py:159-175`) é a canonicalização do princípio
ativo: remove sal (prefixo/sufixo), acentos, caixa, espaços extras. **Mas não remove dose.**

```python
def canon_ativo(nome: str) -> str:
    s = _strip_acentos((nome or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    for pref in _SAIS_PREFIXO:       # ex.: "cloridrato de"
        if s.startswith(pref + " "):
            s = s[len(pref) + 1:]; break
    for suf in _SAIS_SUFIXO:         # ex.: "potássica"
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)]; break
    return s.strip()                 # ← "losartana 50mg" continua "losartana 50mg"
```

O lookup do semáforo é **exato por dict-key** (`:272-273`):

```python
for cid_k in cadeia:
    prov = aprovados.get((cid_k, ativo_k))   # ("I10", "losartana 50mg") ≠ ("I10", "losartana")
    if prov:
        return Avaliacao(SINAL_VERDE, ...)
```

Logo, `canon_ativo("Losartana 50mg")` → `"losartana 50mg"` → **miss** na chave → em CID exaustivo
vira **🟡 amarelo** (`causa=CAUSA_AMARELO`, "ausente_lista_exaustiva", `:288-299`). **Amarelo falso.**

### §1.1 Por que dói mais amanhã

Hoje só **I10** é exaustivo, então o bug só aparece lá. Mas o item B do martelo promove **E11** a
primeiro da fila de curadoria exaustiva (depois J45/F32/N39.0). Quando E11 virar exaustivo, **todo**
prescritor que digitar "Metformina 500mg" ou "Dapagliflozina 10mg" receberá amarelo falso. O bug
passa de caso isolado a **ruído sistemático** exatamente quando o semáforo ganha mais cobertura.

> **Dependência entre itens do martelo:** item B (curadoria E11) sem item A (strip de dose) =
> explosão de amarelos falsos. Recomenda-se executar A **antes ou junto** da primeira curadoria
> exaustiva pós-I10.

### §1.2 Mitigação parcial já em despacho

O microcopy "sem dose" no campo `.med-nome` (`DESPACHO-KIMI3-007 §8.6`, `prescritor.html:1747`)
reduz a frequência do erro de entrada, mas **não elimina** — um prescritor pode ignorar o hint. O
fix real é aqui.

---

## §2 O que fazer

Adicionar um passo de **strip de dose** em `canon_ativo` (`semaforo_decisao.py:159`), após o strip
de sal e antes do `return`. Padrões a cobrir (lista não-exaustiva, validar contra a base ANVISA):

```python
# Exemplo de implementação — validar intervalos reais antes de mergear
_DOSE_RE = re.compile(
    r"\s+\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|ug|g|ui|ufc|mmol|meq|miligrama[s]?|micrograma[s]?|grama[s]?|unidade[s]?\s+internacional(?:is|es)?)\b",
    flags=re.IGNORECASE,
)

def canon_ativo(nome: str) -> str:
    s = _strip_acentos((nome or "").lower())
    s = re.sub(r"\s+", " ", s).strip()
    for pref in _SAIS_PREFIXO:
        if s.startswith(pref + " "):
            s = s[len(pref) + 1:]; break
    for suf in _SAIS_SUFIXO:
        if s.endswith(" " + suf):
            s = s[: -(len(suf) + 1)]; break
    s = _DOSE_RE.sub("", s).strip()   # ← NOVO: strip de dose
    return s.strip()
```

> **ERRATA (arquiteto, 29/08, na auditoria da #220):** a ordem do exemplo acima está ERRADA e
> foi invertida na implementação — o strip de dose vem **ANTES** do strip de sal. O motivo: o
> sal-sufixo casa por `s.endswith(" " + suf)`; com dose no fim (`"losartana potassica 50mg"`),
> a string termina em "50mg", o sufixo nunca casa, e o sal sobrevive — o exemplo do §2 não
> satisfazia o AC4 do próprio ticket (§4). O rascunho era internamente inconsistente; o
> engenheiro achou o caso combinado na execução e invertemos a ordem. Verificado pelo arquiteto
> na #220: vermelho-antes-do-verde confirmado em `main` (os 5 testes novos falham), e o
> invariante §3 provado por diff direto — 120 chaves canônicas (semáforo + posologia)
> byte-idênticas entre `main` e a PR, e nenhum `principio_ativo` da base contém dígito.

> **Atenção (core):** este regex é o ponto crítico do ticket. Um regex guloso pode comer nomes
> legítimos (ex.: não há princípio ativo com "mg" no nome, mas confirmar contra a base). Testar
> contra **todos** os `principio_ativo` de `data/decisao_semaforo.csv` + base ANVISA — nenhum nome
> canônico pode ser alterado pelo regex.

---

## §3 Invariantes (não-negociáveis)

- **Core-adjacente:** `semaforo_decisao.py` é o motor clínico. Mudança **exige teste próprio** e
  revisão do Revisor (consultivo bloqueante em core, por governança).
- **Nenhum nome canônico existente pode mudar:** o regex só pode remover tokens de dose que aparecem
  **depois** do nome. Rodar `canon_ativo` sobre todos os `principio_ativo` da CSV antes/depois —
  diff deve ser **vazio**.
- **Posologia também consome `canon_ativo`** (`posologia_sugerida.py:62, :93`). Confirmar que o
  strip de dose não quebra a chave de posologia (que pode, legítimamente, carregar a dose no nome
  de apresentação — verificar).
- **Sem mudança de comportamento para entradas limpas:** `"Losartana"` continua `"losartana"`.

---

## §4 Critérios de aceite

1. `canon_ativo("Losartana 50mg") == "losartana"` (o caso canônico do conselheiro).
2. `canon_ativo("Metformina 1.000mg") == "metformina"`.
3. `canon_ativo("Dapagliflozina 10 mg") == "dapagliflozina"`.
4. `canon_ativo("Losartana Potássica 50mg") == "losartana"` (sal + dose).
5. `canon_ativo("Escitaloprama") == "escitaloprama"` (entradas limpas inalteradas).
6. **Regressão de base:** rodar `canon_ativo` sobre todos os 110 `principio_ativo` de
   `data/decisao_semaforo.csv` — nenhum valor canônico muda (diff vazio).
7. Testes novos em `tests/unit/test_semaforo_decisao.py` cobrindo casos 1–5.
8. Semáforo: `Losartana 50mg` em I10 retorna **🟢 verde** (não mais 🟡) se losartana ∈ aprovados(I10).
9. Posologia não quebra (`posologia_sugerida.py` lookup ainda resolve).

---

## §5 Verificação

```bash
cd backend

# Testes novos + regressão
python -m pytest tests/unit/test_semaforo_decisao.py -v

# Regressão de base (script ad-hoc) — diff deve ser vazio
python -c "
import csv
from app.domain.semaforo_decisao import canon_ativo
with open('../../data/decisao_semaforo.csv', encoding='utf-8') as f:
    rows = list(csv.DictReader(f))
changed = [(r['principio_ativo'], canon_ativo(r['principio_ativo'])) for r in rows
           if canon_ativo(r['principio_ativo']) != canon_ativo(r['principio_ativo'])]
# (ajustar: comparar contra baseline antes do PR — nenhum nome canônico pode mudar)
print('nomes alterados:', len(changed))
"

# Smoke do semáforo ponta-a-ponta
curl -X POST "$BACKEND/ia/decisao/validar" \
  -H "Content-Type: application/json" \
  -d '{"codigo_cid":"I10","principio_ativo":"Losartana 50mg"}'
# → esperado verde (se losartana aprovada em I10), não amarelo
```

---

## §6 Fluxo

1. Implementar `_DOSE_RE` + passo em `canon_ativo` (§2).
2. Escrever testes (§4.1–4.5) + regressão de base (§4.6).
3. Confirmar posologia (`posologia_sugerida.py`) intacta.
4. Branch: `core/canon-ativo-strip-dose`.
5. PR → **Revisor audita (consultivo bloqueante — core)** → Conselheiro ratifica → Fabiano martela.

---

## §7 Âncoras (verificado `3162af9`)

| Item | Arquivo:linha |
|---|---|
| `canon_ativo` (função) | `backend/app/domain/semaforo_decisao.py:159-175` |
| salt lists `_SAIS_PREFIXO`/`_SAIS_SUFIXO` | `semaforo_decisao.py:139-151` |
| lookup exato por dict-key | `semaforo_decisao.py:272-273` |
| gate exaustividade (I10 exaustivo; E11/J45/etc não) | `semaforo_decisao.py:257-268` |
| amarelo falso path | `semaforo_decisao.py:288-299` |
| teste `canon_ativo` existente (2 casos, sem dose) | `backend/tests/unit/test_semaforo_decisao.py:46-52` |
| `canon_ativo` consumido por posologia | `backend/app/domain/posologia_sugerida.py:62, :93` |
| endpoint `/ia/decisao/validar` | `backend/app/routers/ia.py:543-577` |
| campo `.med-nome` (microcopy §8.6) | `prescritor.html:1747` |
| dados (110 rows; só I10 exaustivo) | `data/decisao_semaforo.csv` |

---

*Ticket registrado pelo arquiteto a partir do item A do martelo do conselheiro (2026-08-07). Sem
pressa, mas com dependência registrada: deve preceder ou acompanhar a primeira curadoria exaustiva
pós-I10 (item B do martelo).*
