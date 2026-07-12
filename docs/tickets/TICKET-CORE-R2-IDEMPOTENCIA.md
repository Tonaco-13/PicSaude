# TICKET-CORE-R2 — Idempotência de mutação + guard-rail de unicidade no gate

| Campo | Valor |
|---|---|
| **Fase** | 5 — primeiro da sequência-mestre (único `core`) |
| **Classe** | **`core`** (protege o ledger contra duplicidade de movimento; enforcement de R2/§2a). **Revisão central + Jules por PR** (CLAUDE.md §10). |
| **Para** | code/MS (engenheiro) — martelo Fabiano dado (2026-07-11) |
| **Origem** | §2a R2 (eureka Fabiano) · achado #2 do diagnóstico #88 (double-submit sem lock pode gravar movimento duplicado) · parecer Z AI verde |
| **Enforça** | CLAUDE.md **§2a R2**: cada movimento (`dispensacao_id`, `estorno_protocolo`) aparece **exatamente uma vez** no relatório. Duplicidade = **alarme de fraude**. |
| **Leva de carona** | **Fix M1** — token com `expira_em` malformado (`custodia.py:732-733`) hoje **segue sem rejeitar**; passa a **rejeitar**. |

---

## §1 Contexto (o furo que fecha)

O diagnóstico do #88 encerrou "não era bug", mas apontou (achado #2) que um **double-submit
concorrente** da mesma dispensação, **sem lock**, pode gravar **dois movimentos** — e ambos
apareceriam no relatório SNGPC. R2 transforma esse risco de "boa prática" em **invariante
falsificável**: o relatório **não pode** ter identificador de movimento duplicado, verificado por
teste permanente no gate. Este ticket entrega (a) a **proteção de concorrência** nas mutações que
criam movimento e (b) o **guard-rail test**.

## §2 Escopo

Mutações que criam **movimento de relatório** (o que R2 protege):
- **Dispensação** — `POST` que grava em `dispensacoes` (`custodia.py:dispensar_item`).
- **Estorno** — `POST /dispensacoes/{id}/estornar` (`dispensacoes.py:estornar_dispensacao`).

> Emissão de prescrição e transferências de custódia **não** criam linha de movimento no relatório
> SNGPC do dispensador — ficam **fora** do escopo de R2 nesta fatia (idempotência ampla é dívida
> registrável, não deste ticket). Foco: os dois geradores de movimento.

## §3 Requisitos

### 3.1 Proteção contra duplo-submit (idempotência/serialização)

Nas duas mutações do §2, garantir que **duas requisições concorrentes idênticas gravem no máximo um
movimento**. O engenheiro escolhe o mecanismo, desde que atômico na camada `database.py` (PG + SQLite):

- **Opção recomendada — lock de linha:** `SELECT … FOR UPDATE` na linha do `prescricao_itens`
  (e/ou da `dispensacoes` de origem, no estorno) dentro da transação `get_tx()`, serializando as
  concorrentes. Em SQLite a transação já serializa; em PG o `FOR UPDATE` é o que fecha a janela.
- **Alternativa — idempotency-key** por operação (header/campo), com unique constraint. Mais robusto
  para retry de rede, mais invasivo no contrato. Só se o engenheiro julgar necessário.

Requisito de comportamento: a **segunda** requisição concorrente **não** cria segundo movimento —
retorna o resultado idempotente **ou** erro claro (`409`), nunca uma segunda linha. O saldo efetivo
(Σ dispensado − Σ estornado) permanece coerente após a corrida.

### 3.2 Guard-rail test permanente no gate (enforcement de R2)

Teste no espírito do `test_guardrail_sem_monetizacao` (falsificável, permanente):

```sql
-- Nenhum dispensacao_id aparece mais de uma vez no relatório
SELECT dispensacao_id, COUNT(*) FROM (<projeção do relatório do dispensador>)
 WHERE tipo_movimento = 'dispensacao'
 GROUP BY dispensacao_id HAVING COUNT(*) > 1;      -- deve vir VAZIO

-- Nenhum estorno_protocolo aparece mais de uma vez
SELECT estorno_protocolo, COUNT(*) FROM (<projeção do relatório>)
 WHERE tipo_movimento = 'estorno'
 GROUP BY estorno_protocolo HAVING COUNT(*) > 1;   -- deve vir VAZIO
```

**Frequência (nota Z AI, §2a R2):** rodar em **todo PR que toque `dispensacoes`, `estornos` ou
`prescricao_itens`** e **nightly** (captura duplicidade introduzida por migração/data-fix, não só por
código de PR). Documentar o gatilho no CI.

### 3.3 Fix M1 — token com `expira_em` malformado (carona)

`custodia.py:732-733`: hoje `except (ValueError, TypeError): pass  # segue sem rejeitar`. Passa a
**rejeitar** — token com `expira_em` inválido é token não-confiável: `410`/`422` com mensagem clara,
**não** dispensar. Teste dedicado.

> **Não substitui** ticket próprio: se houver token malformado já persistido em produção, é preciso
> varredura + rota de invalidação (registrar em `DIVIDA-TECNICA.md`, ver DOCS-DELTAS). O fix M1 aqui é
> só a **porta de escrita** + teste.

## §4 Invariantes

- **Ledger append-only** (§2) — R2 não altera semântica de evento; só impede duplicidade.
- **§2a R2** — passa a ser enforçado por teste. **Nenhum estado novo.**
- **Estorno-objeto-derivado** intacto — o lock serializa, não muta o objeto.
- Determinismo preservado — locks não mudam `ORDER BY`.
- **PG ≠ SQLite** — testar o caminho de concorrência **contra PG** (o `FOR UPDATE` só tem efeito lá);
  gate roda predeploy.

## §5 [PII-EXAUSTIVIDADE]

Nenhuma coluna PII adicionada ou exposta. R2 é mecanismo de concorrência + teste. Rotas tocadas
(`dispensar`, `estornar`) mantêm `require_role('dispensador','admin')` inalterado.

## §6 Critérios de aceite

1. **Concorrência (central):** duas requisições concorrentes idênticas de dispensação do mesmo item
   gravam **um** movimento; a segunda retorna idempotente ou `409`. Idem para estorno. Teste
   **contra PG**.
2. **Guard-rail:** os dois `HAVING COUNT(*) > 1` vêm **vazios** após um ciclo
   dispensar→estornar→dispensar; o teste está no gate com o gatilho do §3.2.
3. **M1:** dispensação com token de `expira_em` malformado é **rejeitada** (não segue); teste verde.
4. Suíte completa verde **contra PG** + predeploy no gate.
5. `docs/CLAUDE.md §2a` já mergeado (a proposta core) — R2 referencia R2/§2a como norma enforçada.

## §7 Fora de escopo

- Idempotência de emissão de prescrição e de transferências de custódia (dívida registrável).
- Varredura/invalidação de tokens malformados já persistidos (ticket próprio — DIVIDA-TECNICA).
- Qualquer mudança de estado ou de contrato de relatório.

## §8 Revisão

`core` → **Jules por PR** (auditoria independente sobre o SHA do PR) + revisão central. Commit separado:
código num commit, ticket/docs noutro (método code/MS).
