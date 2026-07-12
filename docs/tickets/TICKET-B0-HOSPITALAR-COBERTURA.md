# TICKET-B0-HOSPITALAR — mesma dispensabilidade-por-saldo no fluxo hospitalar

| Campo | Valor |
|---|---|
| **Classe** | `module` (guard de dispensação hospitalar) |
| **Prioridade** | **Backlog — FORA do caminho crítico da demo.** A vitrine é ambulatorial (Central/Norte); o fluxo hospitalar não entra na demo V27. |
| **Origem** | Achado do engenheiro no PR #90 (B0): `hospitalares.py:45` tem `_BLOQUEADOS_DISPENSAR` próprio **com `'dispensado'`** — o **mesmo furo** que o B0 corrigiu no ambulatorial. |
| **Depende de** | B0 mergeado (já criou a fonte única `BLOQUEADOS_HARD_DISPENSA` em `domain/states.py`). |

## Problema

O B0 corrigiu o guard ambulatorial para derivar dispensabilidade do **saldo efetivo**, não do rótulo
`status_item='dispensado'`. O fluxo **hospitalar** (`hospitalares.py`) mantém `_BLOQUEADOS_DISPENSAR`
próprio incluindo `'dispensado'` → **a mesma dispensação-total→estorno→re-dispensar bate em 409** no
balcão hospitalar. É a mesma violação de invariante (§10/§2a R1: verdade do ledger, não do rótulo),
num subdomínio diferente.

## Correção (barata — B0 já pavimentou)

- Substituir o `_BLOQUEADOS_DISPENSAR` local de `hospitalares.py` pela constante única
  `BLOQUEADOS_HARD_DISPENSA` (`domain/states.py`) e aplicar o **mesmo guard saldo-primeiro** do B0
  (`custodia.py`).
- Se o fluxo hospitalar tiver estorno próprio, replicar a reabertura de custódia + `custodia_transferida`
  na mesma lógica do B0 (§3.2). Verificar se `dispensacoes_hospitalares` fecha custódia ao zerar saldo.
- Testes espelhando §6 do B0, contra PG, no contexto hospitalar (`org_id`+`unidade_id`).

## Por que backlog, não agora

A demo não exercita o balcão hospitalar. Registrar para não perder o achado (disciplina LEARNINGS:
diagnóstico/entrega revela achado adjacente → ticket próprio, não reabrir o atual). Puxar **depois** da
Fatia F5, quando a máquina de circulação ambulatorial estiver fechada.

> **Nota de generalização:** este é o 2º sítio do mesmo princípio (ambulatorial=B0, hospitalar=aqui).
> Se aparecer um 3º guard de dispensação com rótulo terminal como critério, é sinal de que a régua
> "dispensabilidade = saldo efetivo" merece um teste transversal único sobre todos os guards.
