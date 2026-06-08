# TICKET-CORE-PUBLIC-NEUTRO — Neutralizar os 4 endpoints `GET /public/*` (sem clínica no aberto)

| Campo | Valor |
|---|---|
| **Status** | **Go de Fabiano (2026-06-08) — escopo: os quatro juntos. Apto.** |
| **Classe** | **`core`** — toca `/public/*` (CLAUDE.md §10, revisão central). **Sem merge sem go de Fabiano.** |
| **Origem** | Fabiano, ao revisar `GET /public/encaminhamentos` (PR #14). Ver memória `[[public-endpoints-vazam-clinica]]`. |
| **Base** | `main` em `50a230c` (E1 já mergeado). |

---

## §1 Problema — vazamento LGPD Art. 11 (dado de saúde sensível)

Os **quatro** `GET /public/{prescricoes|exames|laudos|encaminhamentos}/{protocolo}` em
`app/routers/publico.py` são **abertos (sem auth, só o protocolo UUID)** e devolvem **conteúdo
clínico**:

| endpoint | vaza hoje |
|---|---|
| prescrição | `medicamento`, `dose` |
| exame | `nome_exame`, `codigo_tuss` |
| **laudo** | `nome_exame`, **`conclusao`** (conclusão diagnóstica em claro — o pior) |
| encaminhamento | `especialidade`, `procedimento` (item) + `especialidade_destino` (topo) |

Quem tiver o protocolo lê a condição do paciente ("Psiquiatria", "Oncologia", "biópsia de mama",
conclusão de laudo). Os docstrings se **autocontradizem**: prometem "sem dados sensíveis / nunca CID"
e entregam coisa igual ou pior.

## §2 Trabalho real do endpoint (decisão de design)
O QR do PDF aponta para `{BASE_URL}/public/...` (publico.py:148). O job é **validação por QR**: provar
*existência + estado* de um protocolo. Quem escaneia já segura o documento físico (a clínica está
impressa nele). O conteúdo clínico no JSON é **redundante para validar** e **vazamento** para quem tem
só a string. Roteamento p/ unidade de destino é outro job — já servido pelo `GET /{proto}`
autenticado (ownership). → **a clínica sai do aberto.**

## §3 Especificação — payload neutro uniforme (4 endpoints)

Cada endpoint passa a devolver **somente**:
```json
{
  "protocolo": "...",
  "status_<obj>": "...",        // mantém a chave de status já existente por objeto
  "tipo_emissao": "...",
  "itens": [ { "ordem": 1, "status_item": "..." }, ... ]
}
```
Mudanças por endpoint:
- **prescrição** — item perde `medicamento`, `dose`, `item_id`.
- **exame** — item perde `nome_exame`, `codigo_tuss`, `item_id`; topo perde `prioridade`.
- **laudo** — item perde `nome_exame`, `conclusao`, `item_id`.
- **encaminhamento** — item perde `especialidade`, `procedimento`, `item_id`; topo perde
  `especialidade_destino`.

**Neutro por construção:** tornar as queries SQL **deixarem de buscar** as colunas clínicas (não só
omitir do dict) — defesa em profundidade; o dado sensível não sai do banco. `ORDER BY id` é mantido
(a coluna pode ordenar sem ser projetada). `ordem` segue de `enumerate(idx+1)`.

**Docstrings:** reescrever os quatro para refletir o contrato neutro (some a promessa contraditória).

## §4 Escopo de arquivos
| Arquivo | Mudança |
|---|---|
| `app/routers/publico.py` | 4 endpoints: SQL enxuto + dict neutro + docstrings honestas |
| `tests/integration/test_encaminhamentos_autorizacao.py` | reforça: público sem `especialidade`/`procedimento`/`especialidade_destino` |
| testes públicos de prescrição/exame/laudo | atualizar: afirmam **ausência** dos campos clínicos (antes podiam afirmar presença) |

**NÃO toca:** `GET /{proto}` autenticados (a clínica continua lá, com ownership); QR/PDF; serialização
canônica/assinatura (R6); schema/migration (nenhuma coluna muda — só deixa de ser projetada).

## §5 Critérios de aceite (gate)
1. Os 4 `GET /public/*` respondem **200** para protocolo existente e **404** para inexistente.
2. O corpo de cada um **não contém** nenhum campo clínico (assert de ausência por nome de campo **e**
   por valor semeado: nome de medicamento/exame, conclusão, especialidade, procedimento).
3. `protocolo · status · tipo_emissao` + `itens[].ordem/status_item` **presentes** (validação ainda
   funciona — o job é preservado).
4. Suíte existente verde (PG + SQLite); zero regressão nos `GET /{proto}` autenticados.

## §6 Contradição que isto fecha
O contrato passa a ser verdadeiro: "público = existência + estado, **nenhuma** clínica". Alinha com o
princípio CLAUDE.md §6b — *"o objeto clínico é global e **neutro**; a operação é contextual"*.

## §7 Follow-up
- Revisar se há consumidores de frontend que liam os campos clínicos do público (a validação por QR
  não precisa; uma tela que os exibia estava sobre-expondo). Ajuste de UI, não de contrato.

---

*Levantado por Fabiano em 2026-06-08 (PR #14). Classe `core` — merge só com go explícito. Memória:
`[[public-endpoints-vazam-clinica]]`.*
