# Máquina de Estados — PicSaúde

> Fonte de verdade: `backend/app/domain/states.py`
> Em caso de divergência, o código prevalece.

---

## A. Estados de Prescrição (`prescricoes.status`)

| Estado | Terminal? | Descrição |
|---|---|---|
| `pendente` | Não | Emitida digitalmente; aguarda transferência |
| `transferida_paciente` | Não | Em custódia do cidadão |
| `em_custodia` | Não | Dispensador reteve para dispensação |
| `parcialmente_dispensada` | Não | Ao menos um item dispensado |
| `dispensada` | **Sim** | Todos os itens ativos dispensados |
| `cancelada` | **Sim** | Revogação clínica (fluxo digital) |
| `expirada` | **Sim** | `data_validade` ultrapassada |
| `encerrada_localmente` | **Sim** | Emissão exclusivamente física |

---

## B. Estados de Item (`prescricao_itens.status_item`)

| Estado | Terminal? | Descrição |
|---|---|---|
| `pendente` | Não | Estado inicial do ciclo digital |
| `em_custodia` | Não | Dispensador reteve para dispensação |
| `dispensado` | **Sim** | Entregue ao paciente |
| `devolvido_paciente` | Não | Abandono de compra; retry possível |
| `devolvido_prescritor` | **Sim** (*) | Erro identificado; aguarda nova prescrição derivada |
| `cancelado` | **Sim** | Revogação clínica |
| `estornado` | **Sim** | Dispensação revertida após registro |
| `encerrado_fisico` | **Sim** | Emissão física; sem ciclo digital |

`(*)` aguarda nova prescrição com `origem_prescricao_id`.

---

## C. Transições válidas — Prescrição

| De | Para | Evento ledger |
|---|---|---|
| `pendente` | `transferida_paciente` | `custodia_transferida` |
| `pendente` | `cancelada` | `prescricao_cancelada` |
| `pendente` | `expirada` | `prescricao_expirada` |
| `transferida_paciente` | `em_custodia` | `custodia_transferida` |
| `transferida_paciente` | `cancelada` | `prescricao_cancelada` |
| `transferida_paciente` | `expirada` | `prescricao_expirada` |
| `em_custodia` | `parcialmente_dispensada` | `dispensacao_parcial` |
| `em_custodia` | `dispensada` | `dispensacao_registrada` |
| `em_custodia` | `cancelada` | `prescricao_cancelada` |
| `em_custodia` | `transferida_paciente` | `custodia_transferida` |
| `parcialmente_dispensada` | `dispensada` | `dispensacao_registrada` |
| `parcialmente_dispensada` | `cancelada` | `prescricao_cancelada` |
| `parcialmente_dispensada` | `expirada` | `prescricao_expirada` |

---

## D. Transições válidas — Item

| De | Para | Evento ledger |
|---|---|---|
| `pendente` | `em_custodia` | `custodia_transferida` |
| `pendente` | `cancelado` | `item_cancelado` |
| `em_custodia` | `dispensado` | `item_dispensado` |
| `em_custodia` | `devolvido_paciente` | `item_devolvido_paciente` |
| `em_custodia` | `devolvido_prescritor` | `item_devolvido_prescritor` |
| `em_custodia` | `cancelado` | `item_cancelado` |
| `devolvido_paciente` | `em_custodia` | `custodia_transferida` |
| `devolvido_paciente` | `cancelado` | `item_cancelado` |
| `dispensado` | `estornado` | `item_estornado` |

---

## E. Transições proibidas (exemplos)

| Tentativa | Motivo |
|---|---|
| `dispensada` → qualquer | Estado terminal |
| `cancelada` → qualquer | Estado terminal |
| `encerrado_fisico` → qualquer | Nunca volta ao ciclo digital |
| `pendente` → `dispensado` | Salta etapas obrigatórias |

---

## F. Inconsistências documentadas

Funcionam em runtime mas desviam do modelo formal. Documentadas para rastreabilidade.

### F.1 — Devolução ao prescritor transiciona prescrição para `pendente`

**Arquivo:** `routers/custodia.py`

Devolução dispensador→prescritor usa `pendente`, que não consta em
`TRANSICOES_PRESCRICAO["em_custodia"]`. Correção sugerida: introduzir
estado `transferida_prescritor`.

### F.2 — Itens vão direto para `pendente` no abandono de balcão

**Arquivo:** `routers/custodia.py`

Devolução dispensador→paciente transiciona itens `em_custodia → pendente`
em vez de `em_custodia → devolvido_paciente`. O evento é registrado no ledger,
mas `status_item` não passa por `devolvido_paciente`.

---

## G. Estados vs. detentores de custódia

Dois eixos ortogonais:

| Eixo | O que rastreia | Tabela | Módulo |
|---|---|---|---|
| **Estados** | Fase clínica/operacional | `prescricoes.status`, `prescricao_itens.status_item` | `domain/states.py` |
| **Custódia** | Quem detém o documento | `prescricao_custodia` | `routers/custodia.py` |

Detentores válidos: `prescritor ↔ paciente ↔ dispensador`

---

## Governança

Para adicionar estado:
1. `domain/states.py` — Literal type + frozensets + transições + eventos
2. `CLAUDE.md` — seções 5a e 5b
3. `docs/picsaude_ddl_postgres_v1.sql` — DDL PostgreSQL
4. Este documento
