# TICKET-T2 — Endpoint de estorno de dispensação

| Campo | Valor |
|---|---|
| **Status** | **Implementado** (2026-07-08). Aguarda portão do Conselheiro + auditoria Jules antes do merge. |
| **Classe** | **`core`** — ledger + novo objeto derivado (CLAUDE.md §10). Revisão central. |
| **Origem** | `docs/PLANO_DEMO_CIRCULACAO.md` §4 (T2) + handoff Conselheiro→Code (2026-07-07). |
| **Design-lock** | **Opção B** (martelo Fabiano, 2026-07-07): estorno é objeto derivado imutável, **não** transição de estado. |
| **Depende de** | T1 (PR #76, mergeado) — devolução reabre custódia; base da circulação. |
| **Bloqueia** | T3 (constraint Σ no banco) — desenhar já ciente do Σ efetivo deste ticket. |

> Reconstrução do ticket detalhado citado no handoff (o arquivo original não
> existia em nenhuma branch). Consolida o §4 do plano, o `TICKET-ESTORNO-OBJETO-DERIVADO.md`
> (mecanismo) e as ratificações de Fabiano.

## §1 Decisão de design (Opção B)

A reversão de uma dispensação registrada é **nova asserção clínica de novo autor
e momento** → **objeto sanitário derivado e imutável** (`estornos`,
`origem_dispensacao_id`), fiel à imutabilidade (CLAUDE.md §1) e ao padrão
`origem_*_id` (laudo↔pedido_exame, contrarreferência↔encaminhamento).

Consequências:
- `dispensacoes` permanece **intocada** (nunca UPDATE/DELETE).
- O item permanece `dispensado`; **não** se usa a transição `dispensado → estornado`
  nem o estado `estornado` de item (segue como scaffolding — o fix SM2 que o remove
  é pós-paper, ver `TICKET-ESTORNO-OBJETO-DERIVADO.md` §5). Blast radius menor:
  **`states.py` não é tocado neste ticket.**
- Saldo reposto por cálculo: **Σ efetivo = Σ dispensado − Σ estornado**.

## §2 Endpoint

```
POST /dispensacoes/{id}/estornar        (RBAC: dispensador dono | admin)
body: { quantidade_estornada: int>0, motivo: enum, motivo_detalhe?: str }
```

- **Ownership**: dispensador só estorna a própria dispensação (JWT.sub == CNPJ da
  dispensação); admin passa. Anti-leak **404 → 403 → 409/422**.
- **Saldo estornável** = `quantidade_dispensada − Σ já estornado desta dispensação`.
  `≤ 0` → 409 `dispensacao_ja_estornada`; `quantidade > saldo` → 422
  `quantidade_supera_saldo_estornavel`.
- **`motivo`** (enum ratificado por Fabiano, 2026-07-08):
  `falha_pagamento · desistencia · erro_dispensacao · outro`. `outro` exige
  `motivo_detalhe` (422 `motivo_detalhe_obrigatorio`). Enforced em 3 camadas:
  Pydantic + CheckConstraint no model + CheckConstraint na migração (paridade).

## §3 Objeto derivado + ledger

`estornos`: `id · protocolo(UUID) · origem_dispensacao_id(FK NOT NULL) · autor_tipo ·
autor_id · paciente_id · quantidade_estornada · motivo · motivo_detalhe ·
assinatura_hash(SHA-256 canônico) · instance_id · data_emissao · criado_em`.

**Ledger DUPLO** (arch §8):
- `estorno_registrado` no ledger próprio (`estorno_eventos`, INSERT-only + trigger de imutabilidade).
- `dispensacao_estornada` (com `motivo`) no ledger da prescrição (`prescricao_eventos`).

`dispensacao_id` passa a ser **devolvido** por `POST /prescricoes/{proto}/itens/{item}/dispensar`
(antes não era) — pré-requisito para o cliente referenciar a dispensação no estorno/comprovante.

## §4 Σ efetivo em `dispensar_item`

O guard de saldo passa a subtrair o estornado:
`saldo = prescrito − (Σ dispensado − Σ estornado)`. Isso permite **redispensar o
saldo reposto** quando o item ainda não é terminal (cenário T7c). Nota para o **T3**:
o trigger de banco deve validar o **Σ efetivo**, não a soma bruta de `dispensacoes`
(senão impede a reposição) — ver plano §4/Flag 2 Z AI.

## §5 Testes (obrigatórios)

- Integração (Postgres — paridade, gate real, `-k estorno`): estorno completo;
  estorno parcial + **nova dispensação do saldo reposto**; negar estorno de
  dispensação de outro CNPJ (403); `> saldo` (422); ledger duplo; `dispensacoes` intocada.
- Unit (SQLite): imutabilidade de `estorno_eventos` (UPDATE/DELETE bloqueados);
  regras de `motivo`.

## §6 Conformidade CLAUDE.md

- §1 imutabilidade ✓ (objeto derivado; `dispensacoes` intocada)
- §2 ledger append-only ✓ (`dispensacao_estornada` + `estorno_registrado`; §2 atualizado)
- §4 Σ ✓ (Σ efetivo ≤ prescrito preservado)
- §10 core classificado ✓ (portão + Jules antes do merge)

---

*Design-lock Opção B (Fabiano, 2026-07-07). Enum ratificado (Fabiano, 2026-07-08).*
