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

## §7 Nota de direção — "treinar a IA do sinal" (anotada 28/08, para depois das bases)

> Martelo do Fabiano: **anotar somente** — a conversa volta depois da onda de bases de
> referência (CID completo, SIGTAP). Nada abaixo abre sem gatilho dele.

**O que o semáforo é** (lembrança de código, `semaforo_decisao.py`): motor de regras
determinístico e explicável — sem ML. Portão da exaustividade → 🟢/🟡 com causa estável.
O "treinamento" que existe é **curadoria** (este vagão).

**Quatro trilhas, quando a conversa voltar:**

- **A — Curadoria** (o treino real de hoje): fila deste vagão — E11 → J45/F32/N39.0.
- **B — Código destravador**: strip de dose no `canon_ativo`
  (`TICKET-CANON-ATIVO-DOSE-SUFFIX`) — pré-requisito do flip do E11.
- **C — Fundação de dados já gravada** (achado 28/08): a trilha de auditoria da camada 3
  (`prescricoes.py:597-619`) registra no ledger, na emissão, o sinal de cada item + versão
  de regra; como vai junto dos itens emitidos, o **override do prescritor** (sinal 🟡,
  item emitido mesmo assim) já é derivável do ledger. Se um dia houver modelo, três
  condições: volume real (piloto — dado de vitrine demo não é realidade clínica); mora
  **fora do núcleo** (adapter consumindo G4A, nunca escrevendo em tabela clínica); papel
  = ranquear sugestões — **o veredito continua regra curada assinada** (ML propõe,
  curadoria dispõe).
- **D — Régua de melhoria**: cobertura de CIDs exaustivos ao longo do tempo (golden set
  = a própria CSV), não "acurácia de modelo".

Paralelo imediato quando reabrir: A + B.

**Adendo §7.1 (Fabiano, 29/08): aprender com concordância/discordância —
"aprender não é coletar dado".** Verbatim da sessão: *"podemos aprender com a
concordância/discordância do prescritor, uma vez que não é bloqueante. Aprender
não é coletar dado. Princípio do aprendizado federado."* Parecer do arquiteto,
com verificação in-loco na mesma data:

- **A fundação já existe por desenho** (trilha C confirmada no código):
  `prescricoes.py:595-617` + `auditoria_decisao.py` gravam por item emitido o
  `sinal · causa · exaustiva · versao_regra · fonte` no ledger, append-only e
  não-bloqueante. Item emitido com 🟡 É a discordância — nada novo a coletar.
- **Rótulo fraco:** discordância ≠ verdade. Quatro explicações convivem
  (curadoria incompleta · exceção clínica · hábito/ancoragem · CID grosso).
  O alvo do aprendizado é **priorizar a curadoria** (ranquear o que investigar),
  nunca mudar sinal — ML propõe, curadoria dispõe. Loop de feedback
  auto-referente é o risco declarado.
- **Federado de verdade** tem encaixe (`org_id`/`unidade_id` já existem; "o
  dado fica na casa, o aprendizado sai") mas exige **G4A + volume real de
  piloto + múltiplas orgs** — nenhum existe hoje. Segue parqueado, gatilhos
  idem §7. Uso imediato quando houver tráfego real: relatórios de override
  CID×ativo×versão alimentando a fila de investigação deste vagão.
- **Fronteira declarada:** abandono pré-emissão (viu 🟡, apagou antes de
  emitir) NÃO é capturado — seria coleta nova, fora do princípio.

## §8 Despacho — o momento da posologia: JUNTO com cada levantura (Fabiano, 28/08)

> Pergunta: *"qual o momento para avançarmos na posologia?"* — resposta do arquiteto,
> aceita por continuidade (mesma lógica do §7: curation-paced, não code-paced).

**A engine não pede nada.** `posologia_sugerida.py` + `POST /ia/posologia/sugerir`
estão prontos, flag on, editáveis, com proveniência por linha. Expandir cobertura =
**linhas validadas no CSV** — zero código novo. O CSV já semeia a família E11
(metformina, glibenclamida entre as 12 validadas).

**Brief duplo a partir do E11:** a mesma levantura dos alunos (mesmas fontes — RENAME
2024 + PCDT, mesma assinatura do Fabiano) entrega **dois artefatos**: as rows
CID×princípio ativo do semáforo **e** os rascunhos de `posologia_usual` por substância.
Uma passada de pesquisa, dois produtos, um ato de assinatura — mais barato que duas
ondas separadas, proveniência idêntica. Saúde mental (F32) idem quando chegar a vez.

**Pré-requisito de código compartilhado:** o **strip de dose** no `canon_ativo`
(trilha B / TICKET-CANON-ATIVO-DOSE-SUFFIX) vale para os DOIS — sem ele, "Metformina
500mg" digitada não casa com a chave "metformina" (semáforo e posologia usam a mesma
função). Slot do engenheiro: pequeno, logo após a PR 2 do typeahead.

**Bulário não é fonte** (precisão registrada no FILA-VIVA): posologia é dado clínico
curado e assinado; bulário é ponte (apoio à curadoria, exibição, tripwire).

**Adendo §8.1 — sem alunos agora (Fabiano, 28/08): rascunho assistido, assinatura
intacta.** Quem prepara muda de mãos, a régua não: o **arquiteto** pode rascunhar a
levantura E11 direto do PCDT oficial (estagiado em
`data/fontes-oficiais/pcdt/PCDT-diabete-melito-tipo-2-2026.pdf` — Portaria SCTIE/MS
nº 13/2026, 80 págs., sha256 no manifesto), **cada row com citação precisa**
(portaria, seção/tabela) e status `rascunho`. A linha vermelha do vagão estende-se a
agentes: **rascunhista nunca flipa `validado`/`exaustivo`** — o gesto continua do
Fabiano, único assinante. Fontes: PCDT + RENAME 2024, como §1.1 sempre pediu.

---

*Fila registrada pelo arquiteto a partir do item B do martelo do conselheiro (2026-08-07). Trabalho
humano (aluno+Fabiano), não despacho de código — mas com dependência dura no item A (strip de dose).*
*Nova de direção §7 em 28/08 (Fabiano: "anote somente; depois das bases"). Despacho §8 em 28/08
(momento da posologia: brief duplo por levantura).*
