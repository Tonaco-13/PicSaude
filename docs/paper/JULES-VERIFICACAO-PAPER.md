# Tarefa Jules — verificação independente dos números do paper CEBEB

> **Cole isto na interface do Jules** (repo: `Tonaco-13/PicSaude`, branch `main`).
> Objetivo: **teste de redundância** — confirmar (ou refutar) cada número que o paper
> afirma, de forma **independente** dos autores.

---

## Prompt para o Jules

Você é um **verificador independente**. O artigo em `docs/paper/CEBEB_PicSaude_IEEEtran.tex`
(seções VI "Implementation" e VII "Robustness Evaluation", incluindo a Table III) faz uma
série de afirmações numéricas sobre o código deste repositório. Sua tarefa é **conferir cada
afirmação contra o código-fonte e dizer se bate**.

**Regras (importante para a validade do teste):**
1. **Derive cada número você mesmo**, a partir do código. Você PODE ler os scripts dos autores
   (`docs/paper/count_states.py`, `docs/paper/experiments/robustness_eval.py`) para entender a
   intenção, mas **não confie neles nem apenas os execute** — o ponto é uma checagem independente.
2. Para cada item, responda: **MATCH** (com o valor que você obteve) ou **MISMATCH** (com o seu
   valor e a causa provável).
3. **Sinalize sutilezas de contagem.** Ex.: conjuntos de estado auxiliares devem entrar no total?
   "Ledger próprio" são 7 ou 8 tabelas `*_eventos`? Diga o que você contou e por quê.
4. Entregue uma **tabela final**: Claim → valor no paper → seu valor → veredito → nota.

**Afirmações a verificar:**

| # | Afirmação do paper | Onde conferir |
|---|---|---|
| 1 | ~31.700 linhas de código de aplicação | `backend/app/**.py` (sem testes) |
| 2 | 32 routers | `backend/app/routers/*.py` (excl. `__init__`) |
| 3 | 43 models ORM | `backend/app/models/*.py` (excl. `__init__`) |
| 4 | 137 endpoints | decoradores `@router.(get|post|put|patch|delete)` em `backend/app/routers/` |
| 5 | 15 migrations Alembic | `backend/alembic/versions/*.py` |
| 6 | **7 famílias** de objeto sanitário com máquina de estados própria | `backend/app/domain/states_*.py` |
| 7 | **78 estados** e **99 transições** (máquinas de objeto + item) | somar `ESTADOS_*`/`TRANSICOES_*` nos `states_*.py`. **Atenção:** o `ESTADOS_SOLICITACAO_RENOVACAO` (auxiliar) deve ser **excluído** — confirme que excluí-lo dá 78 e incluí-lo daria 82 |
| 8 | **7** famílias com ledger append-only próprio **+ 1 outbox** de publicação | `backend/app/models/*evento*.py` (espera-se 8 arquivos: 7 ledgers de família + `EventoPublicacao`); cruze com `_LEDGER_SCHEMA` em `backend/app/domain/ledger.py` (espera-se 7 subdomínios) |
| 9 | **5** famílias com cadeia de custódia | `backend/app/models/*custodia*.py` |
| 10 | **1.341** funções de teste em **73** arquivos | `backend/tests/**/test_*.py` |
| 11 | (§VII-A) **11 máquinas** obj+item; **3 de 4** propriedades universais; **2 terminais não-absorventes** | verifique as 4 propriedades nos `states_*.py`: (P1) todo destino de transição é estado declarado; (P2) todo terminal não tem saída; (P3) terminais ⊆ estados; (P4) todo não-terminal tem saída. **Quais terminais têm saída?** |
| 12 | (§VII-B) hash do documento canônico: **determinístico** e **12/12 campos** (7 cabeçalho + 5 item) com tamper-evidence | `backend/app/domain/documento_canonico.py` (`montar_documento`); mude cada campo e veja se o `hash_sha256` muda |
| 13 | (§VII-C) **96 cenários** de autorização em **9 famílias**, todos passam no PostgreSQL, ordem **404→403→409** | `backend/tests/integration/*autorizacao*.py` (conte funções `def test_`); rode contra Postgres se puder |
| 14 | (§VII-D) **2 defeitos** "boolean gravado como inteiro" pegos no Postgres, invisíveis no SQLite | histórico git: procure os fixes de `dose_unitaria` e `ativo` (PRs do 5C-BIS-E e C.1) |
| 15 | (§VII-E) **0 de 5** endpoints `GET /public/*` projetam campo clínico | `backend/app/routers/publico.py` — as 5 funções `consulta_publica*`; olhe **só o SQL e o return**, não a docstring (a docstring lista campos clínicos como "nunca retorna") |

**Entregue também:** qualquer afirmação **não-numérica** que você ache incorreta ou exagerada
(ex.: "non-repudiable audit trail", "ownership from creation") — diga se o código sustenta.

---

## Como vou usar o retorno do Jules

Quando o Jules devolver, eu **comparo** com a nossa verdade-base e classifico cada divergência
✅ confirma / 🔄 ajusto o paper / ❌ Jules errou (com motivo). Pontos de maior interesse —
onde a redundância mais vale:
- **#7 (78 vs 82):** o Jules cai na mesma sutileza? (nós só achamos o 78 ao auditar o script).
- **#11:** o Jules acha **exatamente** `resultado_disponivel` e `dispensado`? (replicação cega dos
  achados SM1/SM2).
- **#8 (7 vs 8 ledgers):** o Jules concorda com "7 ledgers + 1 outbox"?
- **#15:** o Jules evita o falso-positivo da docstring (que nos pegou na primeira tentativa)?

Concordância nesses quatro = alta confiança no paper. Divergência = achamos algo a corrigir antes do envio.
