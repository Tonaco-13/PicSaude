# TICKET-GAP-4-LISTAGENS-EXAME — Endpoints de listagem de pedidos de exame (prescritor + laboratório)

| Campo | Valor |
|---|---|
| **ID** | TICKET-GAP-4-LISTAGENS-EXAME |
| **Classe** | `module` (extensão do módulo de exames — não toca núcleo) |
| **Estado** | 🟡 **SPEC INICIAL** — abre discussão de escopo |
| **Para** | Arquiteto ratifica → Engenheiro implementa → Revisor → Fabiano |
| **Origem** | Diagnóstico do módulo de exames (2026-08-02) — Gap 4 do DESPACHO-ENG-001 §7 |
| **Pré-requisito** | Nenhum (independente da working tree e dos PRs em fila) |

---

## §1 Contexto

Hoje só existe **um** endpoint de listagem de pedidos de exame: `GET /paciente/pedidos-exame` (`auth.py:446`) — a carteira do cidadão. Para os outros dois atores do ciclo, **não há listagem**:

- **Prescritor** que emitiu um pedido **não consegue vê-lo de volta** — o painel "Histórico de Emissões" do `prescritor.html` só lista receitas (`_painelBackend.historico`). Um pedido de exame, uma vez emitido, "some" da tela do prescritor.
- **Laboratório** (clínica) só vê pedido se **digitar o protocolo manualmente** — não há fila/lista de pedidos sob sua custódia. Hoje a clínica usa `GET /pedidos-exame/{protocolo}` (`pedidos_exame.py:646`) por busca direta.

**Consequência:** a demo de exames fica capenga — o prescritor não acompanha o que emitiu, e o laboratório não descobre pedidos a não ser que alguém lhe dê o protocolo. O caminho atual do laboratório é a **circulação diagnóstica** (por chave, `circulacao_diagnostica.py:556,728`) — mas isso exige que o paciente acione a circulação; não substitui uma fila.

## §2 Especificação — 2 endpoints

### 2.1 `GET /prescritor/pedidos-exame`

Lista os pedidos de exame emitidos pelo prescritor autenticado.

```
GET /prescritor/pedidos-exame
Auth: JWT role=prescritor (ou admin)
Retorna: pedidos onde prescritor_id = <id do JWT>
         cada pedido: protocolo, paciente_nome, paciente_cpf, status,
                       prioridade, data_emissao, data_validade,
                       itens[{nome_exame, status_item}]
Query params opcionais:
  ?status=emitido|agendado|...    (filtro)
  ?paciente_cpf=...               (filtro por paciente)
```

**Ownership:** filtra por `prescritor_id` do JWT. Admin bypassa (padrão da casa, ver `pedidos_exame.py:652-660` — `_assert_prescritor_dono_pedido` ou equivalente).

**Semântica:** projection do ledger — não cria estado, não muta.

### 2.2 `GET /dispensadores/fila-exames` (fila do laboratório)

Lista os pedidos de exame sob custódia do laboratório autenticado.

```
GET /dispensadores/fila-exames
Auth: JWT role=dispensador (clínica/lab, Q1=(a)) ou admin
Retorna: pedidos onde a custódia atual do pedido (item_id IS NULL)
         está com o CNPJ do JWT (para=<cnpj>)
         cada pedido: protocolo, paciente_nome, status, itens acionáveis,
                       data_ultimo_agendamento
Query params opcionais:
  ?status=agendado|coletado|...   (filtro por estado do pedido)
```

**Ownership:** filtra por custódia ativa — último registro de `pedido_exame_custodia` com `item_id IS NULL` e `para=<cnpj do JWT>`. Padrão análogo a `GET /dispensadores/fila` (prescrições em custódia, `dispensadores.py:92-168`).

**Semântica:** projection do ledger. Reusa o conceito de "acionável" do B0 — mas para exames, "acionável" = item em estado que o laboratório pode agir (pendente/agendado/coletado, não terminal).

> ⚠️ **Atenção RBAC:** este endpoint aceita `dispensador`. Como a clínica usa essa role (Q1=(a)), funciona hoje. Se/when `prestador_exame` entrar (`TICKET-CORE-ROLE-PRESTADOR-EXAME`), o gate migra. **Não bloquear por isso agora.**

## §3 Invariantes

- **R1 (reprodutibilidade):** listagens são projection do ledger + custódia. Não criam estado, não mutam.
- **Ownership (5C):** cada listagem é escopada ao ator autenticado — prescritor só vê o que emitiu; laboratório só vê o que detém. Admin bypassa.
- **§10 (estados computados não persistidos):** `acionavel` (para a fila do lab) é derivado, não persistido — mesmo padrão do B0 (`custodia.py:737-743`).
- **PII-EXAUSTIVIDADE:** listagens expõem paciente_nome + CPF. JWT-only, scoped por ownership. Semelhante a `GET /dispensadores/fila` (prescrições).

## §4 Critérios de aceite

1. `GET /prescritor/pedidos-exame` retorna apenas pedidos do prescritor do JWT.
2. Admin bypassa o filtro de ownership (vê todos).
3. `GET /dispensadores/fila-exames` retorna apenas pedidos sob custódia do CNPJ do JWT.
4. Filtro `?status=` funciona nos dois endpoints.
5. Pedido sem custódia ativa (encerrado/cancelado) não aparece na fila do laboratório.
6. Testes de autorização (análogos a `test_pedidos_exame_autorizacao.py`) cobrem: prescritor A não vê pedidos de prescritor B; laboratório A não vê pedidos de laboratório B; admin vê todos.
7. Sem regressão nos testes existentes.

## §5 Browser-E2E / integração

- **Prescritor:** após emitir `DEMO-EXAME-0001`, painel "Histórico de Emissões" deve listar o pedido (não só receitas). **Dependência:** `prescritor.html` precisa consumir o endpoint novo — trabalho frontend (Kimi 3, ticket separado).
- **Laboratório:** ao logar a clínica, deve ver `DEMO-EXAME-0002` (sob sua custódia) na fila, sem digitar protocolo. **Dependência:** `clinica.html` precisa consumir o endpoint novo — trabalho frontend (Kimi 3, ticket separado).

## §6 Fora de escopo

- **Frontend** (painel do prescritor + fila da clínica) — tickets separados do Kimi 3 após este backend.
- **Filtros avançados** (por data, por paciente, paginação) — MVP sem filtros complexos; adicionar sob demanda.
- **WebSocket/push** — pull periódico (análogo ao `_pollCarteira` do cidadão, 30s).

## §7 Dependências e coordenadas

| Artefato | Relação |
|---|---|
| `auth.py:446` (`GET /paciente/pedidos-exame`) | Padrão de listagem a espelhar |
| `dispensadores.py:92-168` (`GET /dispensadores/fila`) | Padrão de "fila por custódia" a espelhar |
| `pedidos_exame.py:646,815` (gates aceitam dispensador) | Confirma que clínica consegue acessar a fila nova |
| `TICKET-CORE-ROLE-PRESTADOR-EXAME` | Quando ativo, o gate migra de `dispensador` → `prestador_exame` |

---

*Ticket `module` aberto pelo arquiteto de backend (GLM-5.2) em 2026-08-03. Spec inicial — abre discussão de escopo com o Engenheiro. Não bloqueia em nada (independente da working tree e da fila de PRs).*
