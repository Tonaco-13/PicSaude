# VAGAO-CURADORIA-SEMAFORO — Fila de curadoria exaustiva CID×princípio ativo

| Campo | Valor |
|---|---|
| **Semáforo** | 🟨 **Âmbar** — trabalho humano (aluno prepara, Fabiano valida+assina), não código. |
| **Classe** | curadoria clínica (dados em `data/decisao_semaforo.csv`) |
| **De** | Arquiteto (Z), por registro do conselheiro (martelo 2026-08-07, item B) |
| **Para** | Fabiano (valida+assina) · alunos (preparam listas) · cc: Conselheiro |
| **Data** | 2026-08-07 |
| **Origem** | Conselheiro, item B do martelo: *"E11 promovido a 1º da fila ... depois J45/F32/N39.0"* |
| **Estado** | ⏳ Fila reordenada. E11 aguardando lista do aluno. |

---

## §1 Contexto — como o semáforo acende

A engine do semáforo (`semaforo_decisao.py`) só "julga" (🟢/🟡) para CIDs marcados **exaustivos**.
Para os demais, retorna **NEUTRO** (silencioso) — o "portão da exaustividade" (`:257-268`):

```python
cid_exaustivo = next((c for c in cadeia if c in cids_exaustivos), None)
if cid_exaustivo is None:
    return Avaliacao(SINAL_NEUTRO, "sem curadoria exaustiva...", causa=CAUSA_NAO_EXAUSTIVA)
```

Hoje **só I10 é exaustivo**. As seeds E11/J45/F32/N39.0 estão em `data/decisao_semaforo.csv` com
`exaustivo=false` → **sempre neutro**. É por isso que "diabetes dá neutro sempre" (observação do
conselheiro, confirmada no código).

### §1.1 Workflow de curadoria (linha vermelha)

- **Alunos** preparam a lista CID×princípio ativo, fontes **RENAME 2024 / PCDT** (padrão já usado
  em I10 — `data/decisao_semaforo.csv`, coluna `fonte`).
- **Fabiano valida e assina** — só `status_curadoria=validado` é servido pelo motor
  (`TICKET-MOTOR-CLINICO-MS.md:46-48`; `ARQUITETURA_DECISAO_CLINICA.md:206`).
- Alunos **nunca** flipam `validado`/`exaustivo` (`ONBOARDING_code_MS.md:73-75`).
- Quando a lista está completa, Fabiano flipa `exaustivo=true` **em todas as rows daquele CID**
  (regra de unicidade: exaustividade é per-CID, `TICKET-MOTOR-CLINICO-MS.md:79-81`).

---

## §2 Fila reordenada (decisão do conselheiro, 2026-08-07)

| Ordem | CID | Condição | Estado hoje | Seed na CSV |
|---|---|---|---|---|
| **1** | **E11** | Diabetes mellitus tipo 2 | seed, `exaustivo=false` | rows 63-67 + rascunhos 90-110 |
| 2 | J45 | Asma | seed, `exaustivo=false` | rows 68-71 |
| 3 | F32 | Episódio depressivo | seed, `exaustivo=false` | rows 75-78 |
| 4 | N39.0 | Infecção urinária | seed, `exaustivo=false` | rows 81-84 |

**Já exaustivo (não entra na fila):** I10 (Hipertensão, rows 2-62, 61 fármacos).

> **Por que E11 primeiro:** o caso de demonstração ao vivo (item C do martelo) é
> **I10×dapagliflozina** vs **E11×dapagliflozina**. Dapagliflozina está na seed de E11 (row 67) mas
> só acende 🟢 quando E11 virar exaustivo. Sem E11 exaustivo, a demonstração "reforça a prioridade"
> sem poder mostrá-la aceso. (Hoje I10×dapagliflozina é 🟡 — não está na lista de HAS; o contraste
> didático vem quando E11 acende 🟢.)

---

## §3 Dependência com o item A (strip de dose)

⚠️ **Antes de flipar E11 (ou qualquer CID) para `exaustivo=true`, o `TICKET-CANON-ATIVO-DOSE-SUFFIX`
deve estar mergeado.** Razão: sem strip de dose em `canon_ativo`, prescritores que digitarem
"Metformina 500mg" / "Dapagliflozina 10mg" receberão **amarelo falso sistemático** assim que E11
acender. Hoje o bug é mascarado por E11 ser neutro; virar exaustivo o expõe em larga escala.

**Recomendação:** item A (código) **antes** do flip de E11 (curadoria).

---

## §4 Estrutura esperada da entrega (por CID)

Para cada CID da fila, a entrega do aluno deve incluir:

1. **Lista exaustiva de princípios ativos** aprovados para a condição, segundo RENAME 2024 + PCDT
   (+ diretrizes da especialidade, no padrão de I10 = SBC/SBH/SBN).
2. Preenchimento das colunas canônicas da CSV: `codigo_cid`, `condicao_nome`, `principio_ativo`,
   `fonte`, `status_curadoria`, `validado_por`, `versao`, `exaustivo`.
3. Fabiano revisa → assina (`validado_por=Fabiano Tonaco Borges`) → flipa `exaustivo=true` em todas
   as rows do CID → bump de `versao` (padrão: `semaforo_<sigla>_exaustiva_v1_<aaaa-mm>`).

---

## §5 Caso de demonstração (item C do martelo)

| Combinação | Hoje (I10 exaustivo, E11 não) | Após E11 exaustivo |
|---|---|---|
| **I10 × sinvastatina** | 🟡 (sinvastatina ∉ HAS — roteiro) | 🟡 (idem) |
| **I10 × dapagliflozina** | 🟡 (não é de 1ª linha em HAS) | 🟡 (idem) |
| **E11 × dapagliflozina** | **NEUTRO** (E11 não-exaustivo) | **🟢** (dapagliflozina ∈ E11) |

A demonstração ao vivo (E11×dapagliflozina 🟢) só brilha **após E11 virar exaustivo** — reforça a
prioridade do item 2 desta fila.

---

## §6 Âncoras (verificado `3162af9`)

| Item | Arquivo:linha |
|---|---|
| Gate de exaustividade (NEUTRO se não-exaustivo) | `backend/app/domain/semaforo_decisao.py:257-268` |
| Construção de `cids_exaustivos` (set) | `semaforo_decisao.py:365-366` |
| Dados (110 rows; só I10 exaustivo) | `data/decisao_semaforo.csv` |
| Schema/contrato | `backend/docs/tickets/TICKET-MOTOR-CLINICO-MS.md:46-48, 77, 79-81` |
| Modelo incremental seed→exaustivo | `docs/EXPLICABILIDADE_DECISAO_CLINICA.md:130-132` |
| Workflow aluno/Fabiano | `docs/ARQUITETURA_DECISAO_CLINICA.md:206`, `ONBOARDING_code_MS.md:73-75` |

---

*Fila registrada pelo arquiteto a partir do item B do martelo do conselheiro (2026-08-07). Trabalho
humano (aluno+Fabiano), não despacho de código — mas com dependência dura no item A (strip de dose).*
