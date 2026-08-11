# TICKET-EXAME-TRANSFERENCIA-COMO-RECEITA — o pedido de exame circula pelo mesmo gesto da receita

| Campo | Valor |
|---|---|
| **ID** | TICKET-EXAME-TRANSFERENCIA-COMO-RECEITA |
| **Classe** | `module` (extensão do módulo de exames + UI; nenhum estado, transição ou evento novo) |
| **Estado** | ✅ **IMPLEMENTADO** — 2026-08-11, verde local (unit + integração PG + smokes de navegador) |
| **Origem** | Despacho do Fabiano (11/08): "deixe a transferência de custódia de um pedido de exames idêntica à de receita; retire o agendamento para exames do módulo cidadão" |
| **Decisões ratificadas** | (1) a circulação diagnóstica **sai da carteira do cidadão** e é substituída pela transferência; (2) o laboratório precisa de fila para o pedido "cair" — **já entregue pelo #148 (GAP-4)**, aproveitada aqui |
| **Depende de** | `TICKET-GAP-4-LISTAGENS-EXAME` §2.2 (PR #148) — a Fila de Exames da bancada |

---

## §1 O problema

Na vitrine, receita e pedido de exame circulavam por caminhos diferentes — e o do exame
tinha dois, concorrentes entre si:

| | Receita | Pedido de exame (antes) |
|---|---|---|
| Cidadão | CNPJ pré-preenchido + **Transferir Custódia** | **Agendar** (form com data/hora + org + unidade) **ou** gerar **chave de circulação** |
| Destino | cai na **fila do balcão** (`GET /dispensadores/fila`) | a Fila de Exames (#148) existia, mas **nada do cidadão a alimentava**: só o prescritor, via `/agendar` |

O cidadão não tinha, em nenhum ponto, o gesto de **entregar a posse** do exame — a
transferência `paciente → prestador_exame` só existia via `POST /pedidos-exame/{p}/agendar`,
endpoint de papel `prescritor`/`admin`. A cadeia de custódia do exame (§7 do CLAUDE.md)
existia no banco, mas o dono do documento não a acionava. O #148 pôs a bancada para
receber; faltava a mão que entrega.

## §2 O que mudou

### 2.1 Backend — um endpoint (`module`)

**`POST /pedidos-exame/{protocolo}/transferir-laboratorio`** — papel `paciente`.
Espelho de `POST /paciente/prescricoes/{proto}/transferir-farmacia` (`auth.py:202`):

- exige o pedido em `emitido` (posse do cidadão); `agendado` → **409**, terminal → **422**
- ownership **antes** do estado (anti-leak #52): outro CPF → **403**, sem revelar o status
- itens `pendente` → `agendado`; custódia de nível-pedido `paciente → <cnpj>`
- ledger: **dois** eventos, como o fluxo físico da prescrição (§2) — `custodia_transferida`
  (a posse; invariante de retenção) e `pedido_agendado` (a transição `emitido → agendado`,
  o mesmo evento que o caminho `/agendar` já emitia)

O CNPJ é normalizado na escrita (§8.4 opção A), então a custódia gravada casa com o
`_assert_dispensador_dono_pedido` e com o filtro da fila do #148 sem conversão no meio.

> **Por que `agendado`.** No vocabulário do exame, `agendado` **é** "sob custódia do
> prestador, aguardando coleta" — o análogo de `em_custodia` na receita. Nenhum estado
> novo foi criado; a máquina de estados (`states_exame.py`) não foi tocada.

### 2.2 Frontend

**`cidadao.html`** — o card do exame passou a ter o mesmo bloco da receita: CNPJ do
laboratório pré-preenchido de `DEMO.clinica` (fonte única, nunca literal) + botão
**Transferir Custódia** + modal de confirmação (o mesmo do F5-C1, agora com título e
botão "Ver no histórico" parametrizados — o exame não vai para o histórico, segue na
lista). Saíram da tela:

- o **agendamento** (Ticket 29): form de data/hora, `criarAgendamento`, `cancelarAgendamento`
- a **circulação diagnóstica** (Tickets 56/58): chave, seleção de itens, proposta,
  confirmar/desmarcar, storage de chaves em `localStorage`, modal de desmarcação

Depois de transferido, o card não reoferece a transferência: mostra "No laboratório".

**`clinica.html`** — nenhuma tela nova: a Fila de Exames do #148 já recebe o pedido, e o
filtro por `acionavel` do próprio #148 é satisfeito porque a transferência deixa os itens
em `agendado`. Só houve o conserto abaixo.

### 2.3 Bug pré-existente corrigido de passagem

`carregarAgendamentos()` tratava **403** como sessão inválida e chamava `handleUnauthorized()`
→ `alert` + `logout`. Só que `GET /pedidos-exame/{p}/agendamentos` **recusa o papel
`dispensador` por desenho** (`agendamentos.py` §D4). Resultado: **abrir qualquer pedido
derrubava o operador do laboratório para a tela de login** — pela busca por protocolo e,
depois do #148, também pelo clique na fila. Agora só 401 encerra a sessão; o 403 apenas
apaga aquele painel, com aviso. O defeito é anterior a este ticket; o smoke ponta a ponta
só o tornou impossível de não ver.

## §3 O que NÃO mudou (deliberado)

- **A circulação diagnóstica continua inteira** no backend e na tela do laboratório. O que
  saiu foi a porta de entrada dela na carteira do cidadão.
- **O agendamento (Ticket 29) continua inteiro** — inclusive o card "Agendamento" do
  laboratório, que é quem marca data. O que saiu foi o form do cidadão.
- **Sem token de apresentação para exame.** `tokens_apresentacao` é ancorado em
  `prescricoes`; dar código ao exame exigiria migração e é escopo próprio.
- **`CLAUDE.md` não foi editado** (é `core`, exige martelo). Se o §7 for atualizado, a
  linha a acrescentar é o endpoint do cidadão na cadeia
  `prescritor → paciente → prestador_exame → paciente`.

## §4 Cobertura

| Arquivo | O que trava |
|---|---|
| `backend/tests/integration/test_transferencia_exame_cidadao.py` (9 testes) | posse/estado/ledger do novo endpoint; 403 antes de estado; 409 de posse exclusiva; 422 terminal; 400 de CNPJ; o elo com a bancada (pedido transferido cai na fila, acionável) |
| `backend/tests/browser/test_exame_transferencia_cidadao.py` (3 smokes) | ciclo cidadão → laboratório ponta a ponta; **ausência** do agendamento e da chave no card; card transferido não reoferece transferência |

Escopo por CNPJ, ex-custodiante e filtros da fila **não** são reteste aqui — já são
travados por `test_fila_exames_dispensador.py` (#148). Duplicar seria manter dois lugares
para divergir.
