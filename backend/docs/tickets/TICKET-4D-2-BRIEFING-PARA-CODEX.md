# Briefing para CODEX redigir TICKET 4D.2

> Cole este briefing no CODEX e peça para ele redigir o **ticket completo
> da sub-tarefa 4D.2** seguindo o formato da 4D.1.
>
> Após CODEX devolver o ticket, o Arquiteto (Opus 4.7) valida, adiciona
> §10/§11/§12 conforme rodadas, e passa para o Code implementar.

---

## Objetivo da 4D.2

Integrar `instance_id` no ledger dos **4 subdomínios restantes** da Etapa 4
(exame, laudo, agendamento, circulação diagnóstica), substituindo os INSERTs
raw em `*_eventos` pelo helper `registrar_evento_ledger` da 4C.

A 4D.1 (commits `60382d2` + `0056c93`) já fez isso para o subdomínio
**prescrição** (21 sites em 7 routers). A 4D.2 fecha os 4 subdomínios
restantes.

## Escopo

| Router | Sites estimados | Tabela ledger | `objeto_tipo` no helper |
|---|---|---|---|
| `app/routers/pedidos_exame.py` | 10 | `pedido_exame_eventos` | `"pedido_exame"` |
| `app/routers/laudos.py` | 1 | `laudo_eventos` | `"laudo"` |
| `app/routers/agendamentos.py` | 1 | `agendamento_eventos` ⚠️ outlier | `"agendamento"` |
| `app/routers/circulacao_diagnostica.py` | 1 | `circulacao_diagnostica_eventos` | `"circulacao_diagnostica"` |
| **Total** | **13 sites em 4 routers** | — | — |

## Particularidade crítica — outlier `agendamento_eventos`

O `_LEDGER_SCHEMA` da 4C (em `app/domain/ledger.py`) encapsula um drift de
nomenclatura no subdomínio `agendamento`:

```python
"agendamento": {
    "tabela":          "agendamento_eventos",
    "coluna_fk":       "agendamento_id",
    "coluna_tipo":     "evento",        # ← OUTLIER: usa "evento" em vez de "tipo_evento"
    "coluna_payload":  "payload",       # ← OUTLIER: usa "payload" em vez de "dados_json"
    "coluna_data":     "criado_em",
    "tem_ator":        False,
},
```

O helper `registrar_evento_ledger` já lida com isso internamente — o
caller só passa `tipo_evento=...` (string do evento) e o helper sabe que
no `agendamento_eventos` essa string vai para a coluna `evento`.

**Para a 4D.2:** os routers chamam a API uniforme (`tipo_evento=`) sem
precisar conhecer o outlier. O drift fica encapsulado.

## Padrão estabelecido pela 4D.1 (replicar)

Em cada transação clínica que grava evento no ledger:

```python
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn

instance_id = get_instance_id_conn(conn)   # uma vez por transação

registrar_evento_ledger(
    conn,
    objeto_tipo="pedido_exame",   # ou "laudo", "agendamento", "circulacao_diagnostica"
    objeto_id=...,
    tipo_evento="...",
    instance_id=instance_id,
    payload={...},
    # ator_tipo/ator_id apenas em "prescricao" — outros subdomínios NÃO aceitam
)

registrar_outbox(conn, ..., instance_id=instance_id)   # se adjacente
```

**Regras invioláveis da 4D.1 que valem aqui:**

1. `get_instance_id_conn(conn)` uma vez por transação clínica.
2. Mesmo `instance_id` para todas as chamadas `registrar_evento_ledger` da
   mesma transação.
3. Mesmo `instance_id` para cada `registrar_outbox` adjacente.
4. `ator_tipo`/`ator_id` **NÃO aceitos** em `pedido_exame`, `laudo`,
   `agendamento`, `circulacao_diagnostica` (apenas `prescricao` tem ator
   no schema). O helper levanta `ValueError` se forem passados.
5. Falha no ledger aborta a transação (raise — não silenciar).

## Estado das predecessoras

| Sub-tarefa | Commit | Entrega |
|---|---|---|
| 4A | `d8abf7e` | `get_instance_id(session)` + `get_instance_id_conn(conn)` |
| 4B-prequel | `2dce4f8` | regulariza_circulacao_diagnostica (3 tabelas via Alembic) |
| 4B | `89f064a` | coluna `instance_id VARCHAR(36) NULL` em 10 tabelas |
| 4C | `2fbcf43` + `983359f` | `registrar_evento_ledger` + 6 models de evento alinhados |
| 4D.1 | `60382d2` + `0056c93` | subdomínio prescrição (21 sites em 7 routers) |
| Task #8 | `d2f016b` | Saneamento de fixtures legadas — 331 testes passing agora |

## Decisão sobre 4 models principais (manter da 4D.1)

**Não alinhar** os models `Prescricao`, `PedidoExame`, `Laudo`,
`Agendamento` nesta sub-tarefa. A 4D.2 escreve apenas no ledger
(`*_eventos`) e no outbox adjacente. Fica para Etapa 8 / Task #5.

## Riscos conhecidos (heads-up para CODEX investigar)

1. **Drift latente de schema** — a 4D.1 descobriu 3 sites com INSERTs
   manuais usando colunas inexistentes (§4.4 solicitacoes + §4.7 auth +
   P1.2 prescricao_custodia). Investigar se há drift similar em
   `pedidos_exame.py`, `laudos.py`, `agendamentos.py` ou
   `circulacao_diagnostica.py` antes do Code começar.

2. **Helpers locais `_gravar_evento`** — a 4D.1 descobriu 2 helpers
   locais (custodia.py, hospitalares.py). Verificar se algum dos 4
   routers da 4D.2 tem helper local similar e propor refator igual.

3. **Endpoints com `get_conn()` manual vs `get_tx()`** — a 4D.1
   precisou de snippet específico para `criar_prescricao` (usa
   `get_conn()` com `commit/rollback` manual). Verificar se algum dos
   13 sites da 4D.2 está no padrão antigo.

4. **Pedidos de exame têm 10 sites** — é o router com mais densidade de
   eventos. Provável variedade alta de `tipo_evento` (emitido, agendado,
   coletado, em_analise, resultado_disponivel, encerrado, etc.). Mapear
   cada um.

## Estrutura esperada do ticket (espelhar 4D.1)

Por favor, redija o ticket com as **9 seções padrão da 4D.1**:

1. Contexto e objetivo
2. Decisão sobre os 4 models principais
3. Regra de implementação (padrão `get_instance_id_conn` + `registrar_evento_ledger`)
4. Mapa completo dos 13 sites — uma sub-seção por router, com linha + evento + ator
5. Escopo fora deste ticket
6. Critérios de aceitação (geral + por router + **verificação automatizada via grep**)
7. Testes obrigatórios:
   - Testes focados novos/ajustados (1 por endpoint relevante)
   - **Invariantes transacionais** (mesmo `instance_id` por transação — atomização, fluxo multi-evento, ledger+outbox)
   - Regressões existentes
8. Perguntas para o Arquiteto/Fabiano (decisões abertas)
9. Prompt sugerido para implementação (com procedimento numerado e
   restrições explícitas)

## Verificação automatizada (refinada na 4D.1 rodada 4)

Para o §6 do ticket, use o `grep` filtrado a `.py` e sem `__pycache__`:

```bash
# Para cada uma das 4 tabelas alvo:
for tab in pedido_exame_eventos laudo_eventos agendamento_eventos circulacao_diagnostica_eventos; do
  grep -RInI --include='*.py' --exclude-dir='__pycache__' \
    "INSERT INTO $tab" backend/app/routers/
done
```

Esperado: zero matches após implementação.

## Sites em outros arquivos (descoberta da 4D.1 — atenção)

Na 4D.1, a verificação automatizada descobriu 2 sites adicionais em
`auth.py` que não estavam no mapa inicial. **CODEX, verifique
preventivamente** se há INSERTs em `pedido_exame_eventos`, `laudo_eventos`,
`agendamento_eventos`, `circulacao_diagnostica_eventos` em **routers fora
dos 4 alvo** (ex: `auth.py`, `custodia.py`, `hospitalares.py`,
`receituarios.py` — qualquer um). Se houver, decidir junto com o
Arquiteto se entram na 4D.2 ou viram sub-tarefa separada.

## Referências

- TICKET-4D-1-PRESCRICAO-LEDGER-INSTANCE-ID.md (espelhar formato)
- `app/domain/ledger.py` (helper + `_LEDGER_SCHEMA`)
- `app/instance.py::get_instance_id_conn` (variante raw-conn)
- CLAUDE.md / AGENTS.md §10 (classificação `core`)
- `docs/PLANO-PRODUCAO-V2.md` §4 (Etapa 4)
