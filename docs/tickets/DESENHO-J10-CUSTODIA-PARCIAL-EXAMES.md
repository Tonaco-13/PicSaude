# Desenho J.10 — custódia parcial de exames (`module`)

| Campo | Valor |
|---|---|
| **Origem** | DESPACHO-ENG-011 §11c (Adendo 2, 2026-08-15) |
| **Autor** | Engenheiro (Claude Code) — desenho, **não implementação** |
| **Sequência** | Desenhado JUNTO com o J.7 (§11c); implementar **após o merge do J.7** (PR #165) |
| **Classe** | `module` — mas com **uma migração de schema que é `core` de fato** (§1.3 abaixo) |
| **Estado** | 🟡 Desenho para revisão do arquiteto. Há **uma decisão que precisa de martelo** (§5) |

---

## §0 O problema (Fabiano)

> Laboratório que retém o pedido inteiro inviabiliza, em outro laboratório, os exames que ele
> não realiza.

Dois mecanismos, ambos confirmados:

1. **Transferência parcial** — o cidadão entrega só alguns itens; os demais seguem com ele e
   circulam a outro CNPJ.
2. **Devolução de não-realizáveis** — o laboratório devolve, por item, o que não performa.

---

## §1 O achado que muda o custo do ticket

O §11c parte de: *"`pedido_exame_custodia.item_id` nullable já suporta nível-item; falta
endpoint"*. **Verificado no código: o `item_id` suporta, mas a TABELA não tem a forma que o
AC (iii) exige.**

### 1.1 As duas custódias do PicSaúde não têm o mesmo formato

| | `prescricao_custodia` (receita) | `pedido_exame_custodia` (exame) |
|---|---|---|
| Modelo | **posse atual** | **ledger de transferências** |
| Colunas de posse | `detentor_tipo` · `detentor_id` · `encerrada_em` | `de` · `para` · `transferido_em` |
| "Quem detém agora?" | linha com `encerrada_em IS NULL` | **última linha** (`ORDER BY id DESC LIMIT 1`) |
| Unicidade de posse | índice único parcial nos 2 dialetos (COER-2, migração `c0e2f1a3b4d5`) | **não existe** — e não há o que indexar |
| Choke-point | `custodia.py::transferir_posse` (fecha + abre + evento, atômico) | nenhum: cada endpoint dá o seu `INSERT` |

### 1.2 Por que isso importa para o AC (iii)

> AC (iii): *constraint recusa dupla custódia ativa (IntegrityError, teste injetando a tentativa)*

Num ledger append-only **não existe "linha ativa"** para um índice único restringir: toda linha
é um fato passado, e a posse é uma leitura derivada. Não há constraint possível sobre a forma
atual — o AC (iii) é inalcançável sem mudar o schema.

E a lição COER-2 fecha a saída fácil: invariante afirmado por convenção de código **não é**
invariante. O §9 do CLAUDE.md é explícito — *"todo invariante que o CLAUDE.md afirma como
garantido pelo banco precisa de migração + teste que rode nos dois dialetos"*.

### 1.3 Consequência de classificação

O §11c classifica J.10 como `module`. A parte de endpoints e UI é `module`, sim. Mas
**acrescentar `encerrada_em` + índice único a uma tabela de custódia é `core`** pela taxonomia
do §10 (*"Cadeia de custódia (`prescricao_custodia` ou equivalente)"*). Sugiro que o arquiteto
reclassifique o ticket como **`core` com escopo de `module`** — ou que a migração saia num PR
`core` próprio, antes.

---

## §2 O que o J.7 já resolveu para o J.10

Não é só ordem de merge: o J.7 é **pré-requisito semântico**.

Antes do J.7, `pedidos_exame.status` era proxy de posse (`emitido` = cidadão,
`agendado` = laboratório). Com custódia parcial isso seria insolúvel: um pedido com 2 itens no
laboratório e 3 com o cidadão **não tem** um status que descreva a posse — a pergunta deixa de
ter resposta única no nível do pedido.

O J.7 já separou os eixos:

- **estado** = onde o item está no percurso clínico (derivado dos itens, ortogonal à posse);
- **posse** = `pedido_exame_custodia` (helpers `detentor_atual_pedido` / `posse_do_cidadao`).

Com isso, `derivar_status_pedido` **não precisa de mudança nenhuma** para o J.10: itens sob
custodiantes distintos derivam o status normalmente, porque status de item nunca dependeu de
custódia. É o item (iv) do "impacto em cascata" do §4 do despacho, resolvido de antemão.

---

## §3 Desenho proposto

### 3.1 Schema — migração nova (dois dialetos)

Alinhar `pedido_exame_custodia` ao modelo da receita, **reusando os construtores de DDL** da
migração `c0e2f1a3b4d5` (o "como" se importa; o "quê" vai congelado por valor na migração nova
— §9 do CLAUDE.md):

```
ALTER TABLE pedido_exame_custodia ADD COLUMN encerrada_em TIMESTAMP NULL;

-- índice único parcial: no máximo UMA custódia ativa por (pedido_id, item_id)
--   PG     : ... WHERE encerrada_em IS NULL, com NULLS NOT DISTINCT
--   SQLite : ... ON (pedido_id, COALESCE(item_id, -1)) WHERE encerrada_em IS NULL
```

**Data-fix na própria migração** (a régua de corte do COER-2): para cada
`(pedido_id, item_id)`, manter aberta a linha mais recente por `(transferido_em DESC, id DESC)`
e fechar as demais com `encerrada_em = transferido_em` da linha seguinte. Emitir
`custodia_reconciliada_data_fix` **pela migração** — nunca no caminho clínico.

> Risco conhecido: a leitura "detentor atual = última linha" existe hoje em
> `detentor_atual_pedido`, `_assert_dispensador_dono_pedido` e na subquery de
> `fila-exames`. Todas migram para `encerrada_em IS NULL`. São 3 sítios; grep de confirmação
> obrigatório (método §2 do CLAUDE.md do backend).

### 3.2 Choke-point (espelho do COER-2)

Criar `pedidos_exame.py::transferir_posse_exame(conn, pedido_id, item_id, de, para, motivo)` —
**fecha a anterior + abre a nova + emite `custodia_transferida`, atômico**. Nenhum caminho de
produto volta a fazer `INSERT` à mão. Motivos canônicos por caminho:
`transferencia_laboratorio` · `transferencia_parcial` · `devolucao_nao_realizavel` ·
`devolucao_pos_resultado`.

### 3.3 Granularidade: a parcial **explode** o nível-pedido em nível-item

Esta é a decisão de desenho que evita o problema mais feio do COER-2 — a **dupla posse
cross-granularidade** (nível-pedido obsoleto + nível-item ativo), que a constraint *não* pega
porque as chaves diferem.

Proposta: **transferência parcial nunca deixa as duas granularidades vivas.** No ato:

1. fecha a custódia ativa de nível-pedido (`item_id IS NULL`);
2. abre uma custódia de **nível-item para cada item ativo** — os escolhidos vão ao CNPJ, os
   demais ficam com `paciente`.

Depois disso o pedido opera só em nível-item, e a constraint do §3.1 basta. Transferência
integral (`itens` ausente no payload) continua em nível-pedido, retrocompatível.

### 3.4 Endpoints

| Método | Rota | Papel | O que faz |
|---|---|---|---|
| POST | `/pedidos-exame/{p}/transferir-laboratorio` | paciente | payload ganha `itens: [id, …]` **opcional**. Ausente = pedido inteiro (comportamento atual). Presente = §3.3 |
| POST | `/pedidos-exame/{p}/itens/{item_id}/devolver` | dispensador | custódia `prestador_exame → paciente`, `motivo` obrigatório; item volta a `pendente` |

**Sem estado novo e sem evento novo**, como o §11c exige: `custodia_transferida` por item já
existe no vocabulário. O item devolvido volta a `pendente` — o estado `nao_realizado`
(reservado v2) **não** é usado; a informação "este laboratório não performa" vive no `motivo`
da custódia, não num estado terminal que impediria o item de circular.

### 3.5 Fila do laboratório

`GET /dispensadores/fila-exames` hoje casa só `item_id IS NULL AND para = ?`. Passa a unir as
duas granularidades e a filtrar os itens exibidos por custódia:

- o pedido entra na fila se o CNPJ detém a custódia **do pedido OU de ao menos um item**;
- `itens[]` traz **apenas** os itens sob custódia daquele CNPJ (senão um laboratório veria — e
  poderia acionar — exames que estão com outro);
- `acionavel` continua derivado no backend (§10), agora com a custódia do item no critério.

> **Achado de segurança:** sem o segundo ponto, a transferência parcial vazaria itens entre
> prestadores. É o motivo de a fila entrar no escopo do J.10 e não ficar para depois.

### 3.6 Telas

- **`cidadao.html`** (aba Exames, J.9): o cartão passa a listar itens com caixa de seleção
  quando `sob_minha_custodia`; "Transferir Custódia" envia os marcados. Nenhum marcado = todos
  (o gesto de hoje, preservado). Itens já entregues aparecem com o detentor.
- **`clinica.html`** (aba Realização, J.8): botão "Não realizamos este exame" por item →
  `/devolver` com motivo. A partição por percurso do J.8 já acomoda: o item devolvido some da
  lista do laboratório porque sai da custódia dele.

---

## §4 Testes (AC do §11c)

| AC | Onde |
|---|---|
| (i) transferir 2 de 5 → 2 na fila do CNPJ, 3 com o cidadão e transferíveis a outro | integração |
| (ii) devolução → item `pendente` + custódia paciente + evento | integração |
| (iii) constraint recusa dupla custódia ativa (IntegrityError) | integração **nos dois dialetos** (§9) |
| (iv) remanescentes circulam a outro laboratório até o resultado | integração |
| (v) E2E navegador | `tests/browser/test_j10_custodia_parcial.py` |
| **(vi) — acrescentado:** fila de um CNPJ não mostra item sob custódia de outro | integração (§3.5) |

---

## §5 Decisão que precisa de martelo

**A migração do §3.1 mexe na cadeia de custódia — é `core`.** Três caminhos:

- **(a)** J.10 vira `core` inteiro, com o portão do Conselheiro e o martelo do Fabiano.
- **(b)** A migração sai num PR `core` próprio ("custódia de exame ganha posse atual"), e o
  J.10 fica `module` de verdade, empilhado sobre ele. **Recomendado** — separa o que muda o
  invariante do que constrói a feature, e o PR `core` fica pequeno e revisável.
- **(c)** Abrir mão do AC (iii) e afirmar a unicidade só no código. **Desaconselho**: é
  exatamente o defeito que o COER-2 e o §9 do CLAUDE.md existem para impedir.

Sem esse martelo, **não inicio a implementação** (§3 do despacho).

---

## §6 Pendência de fora deste desenho

**RBAC assimétrico de agendamentos** (rastreado no §4 do parecer do arquiteto): o dispensador
CRIA agendamento mas não LISTA por pedido. Se o J.10 vai mexer na fila e nas ações por item, é
a janela natural para o micro-ticket resolver a assimetria junto.

---

*Desenho do engenheiro, 2026-08-15, feito junto com o J.7 conforme §11c. Implementação
aguarda (a) merge do J.7 e (b) o martelo do §5.*
