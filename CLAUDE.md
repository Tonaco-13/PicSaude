# PicSaúde — Princípios arquiteturais obrigatórios

> Este arquivo é lido automaticamente pelo Claude Code a cada sessão.
> Qualquer desenvolvedor ou agente que atue neste projeto deve seguir
> estas regras antes de qualquer decisão de implementação.

---

## MAPA RÁPIDO

| Tópico | Seção |
|---|---|
| Regras invioláveis (imutabilidade, ledger, custódia, dispensação parcial) | 1 · 2 · 3 · 4 |
| Regras de ouro do relatório regulatório (R1–R4) | 2a |
| Estados de prescrição física vs digital | 5 |
| Referência completa de estados (prescrição e item) | 5a |
| Contrato de Estados (invariantes + fonte de verdade) | 5b |
| Emissão exclusivamente física + fire-and-forget | 6 |
| Convenções técnicas (CPF sentinela) | 6a |
| Escopo institucional (org_id + unidade_id) — convenção e guardrail | 6b |
| Modelo generalizável + Núcleo Sanitário (exames, laudos, internações…) | 7 |
| Estrutura de arquivos do projeto | 8 |
| Migração como autoridade de schema · migração declara sobre o que agiu | 9 |
| Taxonomia de contribuição — classificação obrigatória de mudanças | 10 |

---

## 1. Objetos sanitários são imutáveis após emissão

**Regra:** Nunca editar uma prescrição (ou qualquer objeto sanitário) já emitida.
Qualquer alteração gera um **novo objeto derivado**, com `origem_prescricao_id` apontando para o anterior.

```
REC-001 (original) ← REC-002 (correção) ← REC-003 (renovação)
```

Isso vale para: correções, renovações, reemissões, ajustes terapêuticos.

**Violação proibida:** `UPDATE prescricoes SET ... WHERE id = X` após emissão.
**Correto:** `INSERT INTO prescricoes (..., tipo_emissao='correcao', origem_prescricao_id=X)`

---

## 2. O ledger é imutável

A tabela `prescricao_eventos` nunca recebe `UPDATE` nem `DELETE`.
Todo evento de negócio relevante deve gerar um INSERT nessa tabela.

Vocabulário de eventos conhecido:

| Evento | Quando ocorre |
|---|---|
| `prescricao_emitida` | Emissão digital (POST /prescricoes) |
| `prescricao_renovada` | Derivação por renovação |
| `prescricao_corrigida` | Derivação por correção |
| `prescricao_impressa` | **Fluxo físico** — ato de impressão pelo prescritor |
| `encerrada_localmente` | **Fluxo físico** — transição de estado: sem cadeia digital |
| `custodia_transferida` | Transferência entre detentores de custódia |
| `dispensacao_registrada` | Dispensação registrada (total) |
| `dispensacao_parcial` | Dispensação parcial de um item |
| `item_dispensado` | Item individual entregue ao paciente |
| `item_devolvido_paciente` | Item devolvido por abandono de compra |
| `item_devolvido_prescritor` | Item devolvido por erro clínico |
| `erro_prescricao_identificado` | Erro identificado no balcão |
| `pagamento_nao_concluido` | Falha de pagamento no balcão |
| `assinatura_registrada` | Metadados de assinatura digital declarados pelo prescritor (stub MVP) |
| `decisao_clinica_avaliada` | **Camada 3** — trilha de auditoria do semáforo: sinal + versão da regra por item, gravado na emissão (não-bloqueante; só com a flag `PICSAUDE_DECISAO_CLINICA` ativa e `codigo_cid` presente). Ver `docs/EXPLICABILIDADE_DECISAO_CLINICA.md` §11 |
| `pdf_assinado_pades` | Geração de PDF com assinatura ICP-Brasil PAdES-B (cofre server-side). Emitido pela prescrição comum (`POST /prescricoes/{proto}/pdf-assinado`) e pelo receituário. Payload: hash do PDF + serial do certificado |
| `estorno_registrado` | **T2** — reversão de uma dispensação registrada. O estorno é um **objeto sanitário derivado e imutável** (`estornos`, padrão `origem_dispensacao_id`); a `dispensacoes` original **sempre** permanece intocada e o efeito contábil é sempre saldo efetivo = Σ dispensado − Σ estornado. **Muta o item CONDICIONALMENTE** (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO, 10/08): só no estorno **TOTAL** (Σ estornado == Σ dispensado do item) nos motivos "cidadão recupera" (`desistencia_paciente`, `pagamento_nao_concluido`, `outro`) o item vai a `devolvido_paciente` (evento `item_devolvido_paciente`) e a custódia volta ao paciente; nos demais casos (estorno parcial, ou `erro_dispensacao`) o item **não** é mutado (TICKET-B0 preservado). Emitido por `POST /dispensacoes/{id}/estornar`. Payload: `estorno_id` + `estorno_protocolo` + `origem_dispensacao_id` + `item_id` + `quantidade_estornada` + `motivo` (enum `MOTIVOS_ESTORNO`). Ver `docs/tickets/TICKET-ESTORNO-OBJETO-DERIVADO.md` e `docs/tickets/TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO.md` |
| `custodia_reconciliada_data_fix` | **COER-2** — data-fix de reconciliação: encerra custódia ATIVA excedente quando um objeto tinha dupla posse (violação de unicidade). Emitido **pela migração** (`c0e2f1a3b4d5`), nunca no caminho clínico. Régua de corte: mantém a mais recente por `(created_at DESC, id DESC)`. Payload: `custodia_id_encerrada` + `custodia_id_mantida` + `detentor_tipo/_id` + `nivel` + `item_id`. Ver `docs/tickets/TICKET-COERENCIA-DEVOLUCOES-2.md` |

**Fluxo físico emite DOIS eventos em sequência:**
1. `prescricao_impressa` — ato de impressão (quem, quando, quantos itens)
2. `encerrada_localmente` — transição de estado (motivo: emissão exclusivamente física)

Nunca criar endpoints que apaguem ou alterem eventos.

**Invariante de retenção (ratificado por Fabiano, 2026-07-09):** toda retenção de
custódia — **inclusive a auto-retenção** do T1.5 em modo demo — DEVE emitir
`custodia_transferida`. Abrir custódia (`_abrir_custodia`) sem o evento é **bug,
não feature**: o ledger é a fonte da verdade da cadeia de custódia (§3). Em
produção não existe auto-retenção — item não retido → 409 `item_nao_retido`.

---

## 2a. Regras de ouro do relatório regulatório (R1–R4)

O ledger é a fonte da verdade (§2). O relatório regulatório é a sua **projeção verificável** — a
superfície onde a vigilância *confere* a verdade, nunca a fonte dela. (Declarar o relatório como fonte
deixaria uma query com bug redefinir a realidade.) O relatório é a verdade final **para o auditor**
porque é derivável do ledger de forma **determinística e reproduzível**. Disso derivam:

**R1 — Reprodutibilidade.** Todo relatório regulatório é projeção pura e determinística do ledger.
Reexecutar um período fechado produz resultado **byte-idêntico, para sempre** (corte temporal na data
do movimento — TICKET-F5 §3). Relatório não tem estado próprio e nunca é editado.

**R2 — Unicidade de identificadores.** Cada movimento (`dispensacao_id`, `estorno_protocolo`) aparece
**EXATAMENTE UMA VEZ** no relatório. Duplicidade de identificador = **alarme de fraude**, não erro
cosmético. **Guard-rail test permanente no gate**, executado em (a) todo PR que toque `dispensacoes`,
`estornos` **ou** `prescricao_itens`, e (b) **nightly** — captura duplicidade introduzida por migração
ou data-fix, não só por código de PR. Consequência técnica: toda mutação de objeto sanitário deve ser
**idempotente** e protegida contra duplo-submit (lock / idempotency-key).

**R3 — Linhagem-mãe indelével.** A primeira prescrição é mãe de todas as derivações. Todo objeto
derivado resolve ao **protocolo-raiz** pela cadeia `origem_prescricao_id`, e o `protocolo_raiz` é
**coluna visível** do relatório. **Critério de parada da recursão: `origem_prescricao_id IS NULL` — a
mãe não tem mãe; prescrição sem origem é a própria raiz.** "Excluir" não existe: cancelamento é
*estado*, nunca DELETE. O número da mãe nunca se perde — nem quando o prescritor cancela.

**R4 — Identificadores externos são referência congelada.** Números de vigilância externos (ex.:
registro ANVISA do medicamento) entram por **importação periódica** no catálogo local (padrão
CNES/CMED) e são **congelados no movimento** por *snapshot*. **O snapshot é tirado no ato da
DISPENSAÇÃO** (evento que conta para a escrituração regulatória — registro vigente à época da saída
do produto), **não** na emissão da prescrição. **Nunca** chamada externa ao vivo no caminho clínico de
escrita ou na geração do relatório (feriria R1 e a disponibilidade). Import de catálogo nunca escreve
em tabela clínica (regra de adapter, §10).

---

### O que R1–R4 acrescentam ao que já é invariante

Já existem: não-deleção (§1/§2), protocolo imutável (§6b), estorno-como-derivado. **Novo:**
reprodutibilidade como **princípio**, unicidade como **teste de fraude executável no gate**,
`protocolo_raiz` como **coluna visível**, e registro externo como **snapshot congelado na dispensação**.

### Nota de governança

Este bloco é `core` (altera CLAUDE.md). Ao adicioná-lo, atualizar também o MAPA RÁPIDO (topo do
CLAUDE.md) com a linha: `| Regras de ouro do relatório regulatório (R1–R4) | 2a |`.

---

## 3. Custódia é explícita, granular e rastreável

Cada prescrição tem um **detentor de custódia** a cada momento.
A cadeia de custódia é registrada em `prescricao_custodia`.

Transições permitidas (implementadas em `routers/custodia.py`):
```
prescritor  → paciente       (emissão digital)
paciente    → dispensador    (apresentação no balcão)
dispensador → paciente       (abandono/devolução parcial)
dispensador → prescritor     (erro de prescrição)
paciente    → prescritor     (devolução voluntária)
```

Granularidade: a custódia pode ser por **prescrição inteira** (`item_id = NULL`)
ou por **item individual** (`item_id = X`).

### Choke-point de posse + unicidade (COER-2)

**Invariante de banco:** no máximo UMA custódia ATIVA (`encerrada_em IS NULL`) por
`(prescricao_id, item_id)`. Dupla posse ativa = o **R2 na camada de custódia** (um
objeto em dois lugares ao mesmo tempo) — alarme, não erro cosmético. Garantido por
índice único parcial nos dois dialetos (migração `c0e2f1a3b4d5`): PG usa
`NULLS NOT DISTINCT`; SQLite usa `COALESCE(item_id, -1)`.

**Choke-point:** toda transição de posse passa por `custodia.py::transferir_posse`,
que **obrigatoriamente** fecha a custódia anterior + abre a nova + emite
`custodia_transferida` — atômico. Nenhum caminho de produto faz `_fechar` + `_abrir`
à mão. O `motivo` da custódia é **canônico por caminho** (o T6/histórico separa os
caminhos): `transferencia_farmacia` · `abandono_balcao` · `devolucao_integral_paciente`
· `devolucao_ao_prescritor` · `estorno_reposicao_saldo` · `devolucao_pos_estorno`
· `auto_retencao_demo` · `dispensacao`. Texto livre do usuário vai em `motivo_detalhe`
(nunca sobrescreve o canônico). (`devolucao_pos_estorno` = estorno TOTAL que devolve a
custódia ao paciente — TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO; distinto de
`estorno_reposicao_saldo`, que retem no dispensador.)

> A constraint pega dupla posse de **mesma granularidade**. A dupla posse
> **cross-granularidade** (nível-prescrição obsoleto + nível-item ativo — raiz do
> Cenário 1) é fechada pela **reconciliação** do caminho (`devolver_item`), não pela
> constraint. As duas guardam coisas diferentes.

---

## 4. Dispensação parcial é suportada e não invalida a prescrição

A impossibilidade de pagar um item no balcão **não cancela a prescrição**.
O item volta ao estado `pendente` e pode ser dispensado em outra farmácia.

A soma de `quantidade_dispensada` nas `dispensacoes` de um item nunca pode
superar `prescricao_itens.quantidade`.

---

## 5. Estados de prescrição física vs digital

### Fluxo digital

```text
pendente
  -> transferida_paciente
  -> em_custodia
  -> parcialmente_dispensada | dispensada
  -> cancelada   (revogação clínica dentro do fluxo digital)
```

- Itens nesse fluxo participam de custódia e dispensação.
- `cancelada` = decisão clínica ou operacional. Nunca usar para emissão física.

### Fluxo físico

```text
impressa
  -> encerrada_localmente
     -> itens: encerrado_fisico
```

- `encerrado_fisico` = emitido em papel; nunca inserido no ciclo digital.
- Prescrição física não gera custódia.
- Prescrição física não entra no fluxo de dispensação digital.

### Regra semântica obrigatória

```
encerrado_fisico  =  emitido em papel, nunca entrou no ciclo digital   (status de item)
cancelada         =  revogação clínica dentro do fluxo digital          (status de prescrição)
cancelado         =  revogação clínica dentro do fluxo digital          (status de item)
```

---

## 5a. Referência completa de estados

### Prescrição (`prescricoes.status`)
```
pendente                 ← emitida digitalmente, aguarda transferência
transferida_paciente     ← em custódia do cidadão
transferida_prescritor   ← devolvida ao prescritor p/ correção (espelho de transferida_paciente; COER-2)
em_custodia              ← dispensador reteve a prescrição
parcialmente_dispensada  ← ao menos um item dispensado
dispensada               ← todos os itens ativos dispensados
cancelada                ← revogação clínica ou todos os itens encerrados
expirada                 ← data_validade ultrapassada
encerrada_localmente     ← emissão exclusivamente física (terminal)
```

### Item (`prescricao_itens.status_item`)
```
pendente              ← estado inicial do ciclo digital
em_custodia           ← dispensador reteve para dispensação
dispensado            ← entregue ao paciente (terminal; ver (†) — exceção pós-estorno)
devolvido_paciente    ← abandono de compra; nova tentativa OU volta ao médico (**) · também destino do estorno TOTAL "cidadão recupera" (†)
devolvido_prescritor  ← erro identificado; aguarda correção (terminal*)
cancelado             ← revogação clínica (terminal)
estornado             ← scaffolding dormente — a transição existe no mapa mas NÃO é usada no fluxo real (o estorno é objeto derivado; ver (†))
encerrado_fisico      ← emissão física; sem ciclo digital (terminal)
```

`(*)` devolvido_prescritor aguarda nova prescrição derivada com `origem_prescricao_id`.

`(**)` **COER2-POS-MERGE-FIX**: `devolvido_paciente → devolvido_prescritor` é transição
válida — quando o cidadão devolve ao médico um item que **já voltara a ele** (rescaldo de
estorno/devolução ao paciente). Antes só `pendente → devolvido_prescritor` era coberto
(`auth.py::devolver_prescritor`), deixando o item contraditório com a prescrição
(`transferida_prescritor`) e invisível no painel de correções — eco de "dupla posse" no
nível de estado. Ao virar terminal, a custódia de ITEM no nome do paciente é FECHADA (sem
órfã). Ver `TICKET-COER2-POS-MERGE-FIX` e a nota em `states.py::TRANSICOES_ITEM`.

`(†)` **Estorno condicional (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO, 10/08):** o estorno
sempre cria o objeto derivado `estornos` (a `dispensacoes` original permanece intocada). O
item SÓ é mutado no estorno **TOTAL** (`Σ estornado == Σ dispensado`) nos motivos "cidadão
recupera" (`desistencia_paciente`, `pagamento_nao_concluido`, `outro`): aí o item vai
`dispensado → devolvido_paciente` (aresta adicionada em `states.py::TRANSICOES_ITEM`), a
custódia volta ao paciente (`devolucao_pos_estorno`) e a prescrição regredir a
`transferida_paciente` (exceção nomeada ao terminal `dispensada`, à moda do
COER2-POS-MERGE-FIX) — destravando retry em outra farmácia e devolução ao prescritor (§3).
Nos demais casos (estorno **parcial**, ou motivo `erro_dispensacao`) o item **não** é
mutado (TICKET-B0 preservado: saldo reposto, re-dispensável na mesma farmácia). A transição
`dispensado → estornado` segue como scaffolding dormente (não usada).

> ⚠️ **Governança:** Estados de prescrição e de item são parte do modelo de domínio.
> Não criar novos estados sem atualizar esta seção, o DDL em `docs/picsaude_ddl_postgres_v1.sql`
> **e** as constantes em `backend/app/domain/states.py`.

---

## 5b. Contrato de Estados (invariantes)

**Este contrato é a fonte de verdade para estados de prescrição.**

### Estados permitidos

```
Fluxo digital — prescrição:
  pendente | transferida_paciente | transferida_prescritor | em_custodia
  parcialmente_dispensada | dispensada | cancelada

Fluxo físico — prescrição:
  encerrada_localmente

Estados de item:
  pendente | em_custodia | dispensado
  devolvido_paciente | devolvido_prescritor
  cancelado | estornado | encerrado_fisico
```

### Estados terminais

```
Prescrição:  dispensada · cancelada · encerrada_localmente · expirada
Item:        dispensado · devolvido_prescritor · cancelado · estornado · encerrado_fisico
```

> **Exceção nomeada ao terminal (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO, 10/08):** à moda
> do COER2-POS-MERGE-FIX, `dispensada`/`dispensado` permanecem terminais no caso geral, mas
> admitem **uma** regressão nomeada — o estorno TOTAL nos motivos "cidadão recupera" leva o
> item a `devolvido_paciente` e a prescrição a `transferida_paciente` (via
> `_recalcular_status_prescricao`), devolvendo a custódia ao paciente. Não é afrouxamento
> geral do terminal; é a única brecha legítima, declarada. Ver §5a `(†)`.

### Invariantes

- Prescrições físicas não entram em custódia digital
- Itens `encerrado_fisico` não voltam ao fluxo digital
- `cancelada/cancelado` = revogação clínica; nunca usar para fluxo físico
- **Item devolvido ao prescritor segue a prescrição** (COER2-POS-MERGE-FIX): os dois
  estados retornáveis — `pendente` **e** `devolvido_paciente` — transicionam para
  `devolvido_prescritor`. Nenhum item fica em `devolvido_paciente` enquanto a prescrição
  está em `transferida_prescritor` (seria incoerência de estado). Guarda executável (PG):
  `tests/integration/test_custodia_devolucao.py::test_coer12_devolver_prescritor_de_item_devolvido_paciente_vira_devolvido_prescritor`
  (custódia sem órfã em `::test_coer13_...`; render do painel em `tests/browser/test_coer2_fix.py`)
- **Estorno é condicional** (TICKET-CORE-ESTORNO-NAO-CHEGA-AO-CIDADAO): o objeto derivado
  `estornos` é sempre criado, mas o item só é mutado (`dispensado → devolvido_paciente`) no
  estorno TOTAL dos motivos "cidadão recupera"; nos demais casos o item não é mutado
  (TICKET-B0 preservado). Guarda executável: `tests/integration/test_estorno.py`.
- Transições válidas estão declaradas em `backend/app/domain/states.py`

---

## 6. Emissão exclusivamente física

Quando o prescritor imprime sem iniciar cadeia digital:
- Status final da prescrição: `encerrada_localmente`
- Status de cada item: `encerrado_fisico`
- Evento no ledger: `prescricao_impressa`
- Sem cadeia de custódia (nenhum registro em `prescricao_custodia`)
- Sem transferência ao paciente

**Trade-off documentado (fire-and-forget):**
O frontend envia o POST `/prescricoes/fisica` sem aguardar resposta (`fire-and-forget`).
Se o backend estiver offline, a impressão ocorre normalmente e o registro fica
apenas no `localStorage`. Consequência aceita: pode haver impressões sem
persistência central. Para rastreabilidade completa, o backend deve estar acessível.

---

## 6a. Convenção técnica — CPF sentinela

O CPF `'00000000000'` é reservado para prescrições físicas sem identificação
digital do paciente. É matematicamente inválido (dígitos verificadores inválidos)
e nunca representa um cidadão real.

Regras de uso:
- Queries analíticas devem excluir: `WHERE cpf != '00000000000'`
- Nunca expor em relatórios de auditoria como identificação real
- Constante no código: `_CPF_NAO_IDENTIFICADO = "00000000000"` em `prescricoes.py`

---

## 6b. Escopo institucional — `org_id` e `unidade_id`

O PicSaúde opera como plataforma multi-institucional. O princípio central é:

> **O objeto clínico é global e neutro. A operação é contextual.**

### Identidade vs. contexto

| Campo | Papel |
|---|---|
| `protocolo` (UUID) | Identidade sanitária global — único, imutável, independente de instituição |
| `org_id` | Entidade jurídica ou rede (ex: hospital X, rede de farmácias Y) |
| `unidade_id` | Unidade operacional física (ex: filial 123, UTI, farmácia hospitalar) |

`org_id` e `unidade_id` **nunca substituem** o protocolo como chave principal.
São usados apenas como: escopo de consulta, filtro de acesso, contexto operacional.

### Convenção de campo vazio (NULL)

```
org_id    = NULL  →  objeto sem escopo institucional obrigatório
unidade_id = NULL →  objeto sem escopo institucional obrigatório
```

`NULL` significa ausência de vínculo institucional — não "público" nem "interno".
Objetos legados (anteriores à adoção de subdomínios) permanecem com `NULL`.

Não criar valor sentinela para org/unidade ausente.

### Rollout incremental

`org_id` e `unidade_id` **não são adicionados em todas as tabelas de uma vez.**
Cada tabela recebe esses campos somente quando um caso de uso real exigir.

Tabelas com escopo institucional ativo:
- `dispensacoes_hospitalares` — `org_id` + `unidade_id` obrigatórios (Ticket 27)
- `prescricao_custodia` — `unidade_id` nullable + `contexto_operacional` nullable (Ticket 27, contexto hospitalar)

Tabelas com exceção documentada (não recebem `org_id`):
- `tokens_apresentacao` — token agnóstico de instituição; contexto entra no uso (ver abaixo)
- `prescricao_itens` — herda contexto via prescrição (JOIN); sem denormalização
- `prescricoes` — rollout incremental; migrar somente quando caso real exigir

### Guardrail obrigatório para queries com escopo institucional

Toda tabela que contiver `org_id` segue esta regra:

> Toda query de leitura ou escrita que opere em contexto institucional **deve**
> incluir `WHERE org_id = ?` (ou equivalente). Se o filtro não se aplicar,
> justificar com comentário inline.

**Violação proibida:** `SELECT * FROM tabela_com_org_id WHERE ...` sem filtro de `org_id`
quando o endpoint tem contexto institucional definido.

**Correto:**
```sql
SELECT * FROM dispensacoes
WHERE org_id = ?       -- escopo institucional obrigatório
  AND protocolo = ?
```

### Tokens de apresentação — exceção documentada

`tokens_apresentacao` **não recebe `org_id`**: o token é emitido pelo paciente e é
agnóstico de instituição (token aberto por decisão do Ticket 24). O contexto
institucional aparece no uso do token, não na emissão — campo `cnpj_estabelecimento`
em `tokens_apresentacao_usos` é suficiente.

### Enforcement via JWT (fase futura)

Na fase atual, `org_id`/`unidade_id` podem entrar pelo payload da request.
Enforcement via JWT (token carregando `org_id` + `unidade_id`) exige fluxo de
onboarding institucional — implementar quando esse fluxo existir.

---

## 7. O modelo é generalizável

A arquitetura de custódia não é exclusiva de prescrições.
Qualquer objeto assistencial futuro deve seguir o mesmo padrão:

| Objeto | Estados típicos |
|---|---|
| Exame | emitido → agendado → coletado → em_analise → resultado_disponivel → encerrado |
| Agendamento | solicitação → reserva → confirmação → comparecimento |
| Laudo | produção → assinatura → liberação → ciência |
| Internação | indicação → autorização → admissão → alta |

Nunca criar tabelas ou endpoints que violem esse modelo de estados.

### Estados do módulo de Pedido de Exame (Tickets 14–17)

Pedido (`pedidos_exame.status`):
```
emitido · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · expirado · encerrado_fisico
```

Item (`pedido_exame_itens.status_item`):
```
pendente · agendado · coletado · em_analise · resultado_disponivel
encerrado · cancelado · encerrado_fisico
```

Custódia: `prescritor → paciente → prestador_exame → paciente`

> Arquitetura completa em `docs/ARQUITETURA_EXAMES.md`

### Estados do módulo de Agendamento (Ticket 28 — arquitetura / Ticket 29 — implementação)

Classificação: **objeto sanitário leve** — tem identidade própria (UUID), estados e ledger, mas sem conteúdo clínico autônomo, sem custódia e sem assinatura. É o elo entre pedido de exame e coleta.

Agendamento (`agendamentos.status`):
```
criado · confirmado · realizado · cancelado · nao_compareceu
```

Regras fundamentais:
- Remarcação = novo objeto derivado (`origem_agendamento_id`), nunca estado `remarcado`
- `agendamento_criado` → itens do pedido: `pendente → agendado`
- `agendamento_realizado` → itens do pedido: `agendado → coletado` *(simplificação MVP)*
- `agendamento_cancelado` / `nao_compareceu` → itens voltam a `pendente`
- `org_id` e `unidade_id` são obrigatórios (NOT NULL) em `agendamentos`
- Sem cadeia de custódia (compromisso bilateral — exceção documentada ao NUCLEO_SANITARIO)

**Nota MVP:** a equivalência `realizado → coletado` é simplificação do MVP. Em contexto real, comparecimento e coleta efetiva podem ser eventos distintos.

> Arquitetura completa em `docs/ARQUITETURA_AGENDAMENTO.md`

### Estados do módulo de Laudo (Tickets 19–21)

Laudo (`laudos.status`):
```
em_producao · assinado · liberado · ciencia_paciente · ciencia_prescritor
encerrado · cancelado · expirado · encerrado_fisico
```

Item (`laudo_itens.status_item`):
```
em_producao · concluido · cancelado · encerrado_fisico
```

Custódia: `prestador_exame → paciente | prescritor`
Origem: responsável técnico (patologista / bioquímico / médico laboratorista)
Ciência: opera no nível do laudo inteiro (exceção documentada ao núcleo)

> Arquitetura completa em `docs/ARQUITETURA_LAUDO.md`

### Estados do módulo de Atestado (objeto sanitário MONOLÍTICO)

Classificação: **objeto sanitário monolítico** — um documento único, **sem itens**
(diferente de prescrição/exame); status direto, não derivado. Tem identidade
(UUID), estados, ledger, custódia e assinatura ICP-Brasil.

Atestado (`atestados.status`):
```
emitido · assinado · cancelado · expirado · encerrada_localmente
```

Regras fundamentais:
- **Sem itens** (exceção documentada ao núcleo, como o agendamento)
- Assinar é marco de estado: `emitido → assinado` (PAdES via cofre)
- CPF do paciente **obrigatório** no digital; sentinela `00000000000` no físico
- `dias_afastamento` é opcional (nem todo atestado afasta — ex.: comparecimento)
- Custódia única: `prescritor → paciente` (emissão); físico não gera custódia
- Validação pública neutra (`GET /public/atestados/{proto}`): confirma existência/
  assinatura/vigência **sem** vazar finalidade, CID, indicação ou identidade

Custódia: `prescritor → paciente`
Eventos: `atestado_emitido · atestado_assinado · atestado_corrigido · atestado_cancelado · atestado_expirado · atestado_impresso · encerrada_localmente · custodia_transferida`

> Arquitetura completa em `docs/ARQUITETURA_ATESTADO.md`

### Farmácia Hospitalar (Ticket 26 — arquitetura / Ticket 27 — implementação)

Classificação: **subdomínio operacional da dispensação** — não é novo objeto sanitário, não é novo papel RBAC.

Regras fundamentais:
- O papel `dispensador` permanece único. O modo hospitalar é contexto operacional (`unidade_id`)
- O paciente não é detentor intermediário no fluxo hospitalar (é beneficiário clínico, não portador ativo)
- Cadeia de custódia hospitalar: `prescritor → farmacia_hospitalar → (unidade_enfermagem) → paciente`
- Dose unitária e fracionamento são modalidades operacionais, não novos objetos rastreados
- A constraint `Σ dispensado ≤ prescrito` permanece idêntica à dispensação ambulatorial
- `dispensacoes_hospitalares` é extensão de `dispensacoes` — não caminho paralelo

**Violação proibida:** criar `prescricao_hospitalar` como tabela separada, ou `dispensador_hospitalar` como papel RBAC.

> Arquitetura completa em `docs/ARQUITETURA_FARMACIA_HOSPITALAR.md`

---

### Núcleo genérico (Ticket 18)

O PicSaúde é uma **infraestrutura de objetos sanitários rastreáveis**, não apenas uma aplicação de prescrição. O padrão arquitetural comum a todos os objetos está formalizado em:

> **`docs/NUCLEO_SANITARIO.md`** — contrato obrigatório para qualquer novo objeto sanitário.

Todo novo objeto (laudo, agendamento, internação, autorização…) deve satisfazer esse contrato antes de ser implementado. O checklist de conformidade está na seção 11 do documento.

---

## 8. Estrutura do projeto

```
backend/
  app/
    models/                    ← SQLAlchemy ORM
      prescricao_assinatura.py ← Ticket 5: metadados de assinatura digital
    routers/                   ← FastAPI endpoints
      assinaturas.py           ← Ticket 5: GET+POST /prescricoes/{proto}/assinatura
      validacao.py             ← Ticket 6: GET /prescricoes/{proto}/validacao
    domain/                    ← Lógica de domínio pura (sem dependência de FastAPI)
      states.py                ← Contrato de estados (prescricoes + itens)
      assinatura.py            ← Modos, níveis formais, status de validação
      documento_canonico.py    ← Documento canônico + hash SHA-256
      pdf_prescricao.py        ← Geração do PDF institucional (Ticket 3)
      validacao_documental.py  ← Motor de validação em 5 camadas (Ticket 6)
    utils/helpers.py           ← normalize_cpf, normalize_cns, normalize_cnpj, normalize_nome
    config.py                  ← DB_PATH (env PIX_SAUDE_DB ou data/pix_saude_pe.db)
    database.py                ← get_conn() para raw SQL, engine/Base para ORM
  init_tables.py               ← bootstrap dev + checagem de schema (§9). NÃO cria triggers
  alembic/versions/            ← autoridade de schema — o que roda em produção (§9)
data/
  pix_saude_pe.db              ← banco SQLite (CNES + aplicação)
docs/                          ← whitepaper, DDL PostgreSQL, arquitetura
prescritor.html                ← frontend (localStorage + chamadas ao backend)
dispensador.html               ← frontend dispensador
```

### Endpoints ativos (resumo)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/prescricoes` | Emissão digital |
| POST | `/prescricoes/fisica` | Emissão física (fire-and-forget) |
| GET  | `/prescricoes/{proto}/documento` | Documento canônico + integridade |
| GET  | `/prescricoes/{proto}/pdf` | Receita em PDF institucional |
| GET  | `/prescricoes/{proto}/assinatura` | Consultar metadados de assinatura |
| POST | `/prescricoes/{proto}/assinatura` | Registrar metadados de assinatura |
| GET  | `/prescricoes/{proto}/validacao` | Validação documental em 5 camadas |

## 9. A migração é a autoridade de schema

**A migração Alembic é a ÚNICA autoridade sobre o schema — inclusive sobre
invariantes de banco (triggers, constraints).** `init_tables.py` é bootstrap e
checagem de ambiente de desenvolvimento; nada que só ele cria chega a produção.

Por quê: o `predeploy.sh` do Render roda **apenas**

```
alembic upgrade head
python3 seed_demo.py
```

e **nunca** chama `init_tables.py`. Um invariante que existe só no script de
bootstrap não existe em produção. Foi exatamente o que aconteceu com os triggers
de imutabilidade do ledger (§2): eram criados só pelo `init_tables.py`, em código
SQLite-only, e o **PostgreSQL nunca os teve** — o §2 afirmava que o banco recusa
UPDATE/DELETE enquanto apenas a convenção de código recusava
(TICKET-LEDGER-TRIGGERS-MIGRACAO).

### Ao criar um novo `model/*.py`

1. Crie a **migração** — é ela que aplica a mudança em todo ambiente:
   ```bash
   cd backend && alembic revision -m "descricao_da_mudanca"
   # implemente upgrade() e downgrade(); use op.get_bind().dialect.name
   # quando o DDL divergir entre SQLite e PostgreSQL
   cd backend && alembic upgrade head
   ```
2. Adicione o nome da tabela à lista `_TABELAS_APP` em `init_tables.py` — ali
   ela serve como **checagem**, não como criação.
3. Se a tabela for um ledger (`*_eventos`), adicione-a a `TABELAS_LEDGER` em
   `app/domain/ledger_imutabilidade.py` **e** crie uma migração NOVA que instala
   seus dois triggers (`prevent_update_*` / `prevent_delete_*`) nos dois
   dialetos, declarando a sua própria tupla literal de tabelas (ver abaixo).

### A migração declara sobre o que agiu

> **A migração declara sobre o que agiu. Estrutura nova = migração nova — nunca
> editar a anterior.**

Migração é **registro histórico**, não código vivo. Ela pode importar o **"como"**
(construtores de DDL — fonte única, zero duplicação), mas nunca o **"quê"**: a
lista de objetos sobre os quais agiu vai **escrita nela mesma, por valor**.

Por quê: uma migração que lê lista viva tem efeito dependente de **quando** roda.
Um banco migrado hoje ganha N triggers; um banco criado do zero depois de a lista
crescer ganha N+2 — dois bancos no mesmo `alembic head` com schemas diferentes.
É o mesmo defeito que o §9 existe para prevenir, reintroduzido pela porta dos
fundos. É o **R4 invertido** (§2a): lá congela-se o grupo por valor no ato do
movimento para que mudar a regra amanhã não altere o movimento de ontem; aqui a
migração *é* o movimento.

Corolário — as duas listas não são a mesma coisa, e nenhuma está errada:

| | Papel | Quem consome |
|---|---|---|
| `TABELAS_LEDGER` (lista viva) | **Presente** — "quais ledgers devem estar protegidos agora" | `init_tables.py` (checagem), testes |
| Tupla literal na migração | **Passado** — "sobre o que eu agi" | a própria migração |

Disciplina idêntica à do objeto sanitário derivado (§1): não se edita o anterior,
cria-se o próximo.

**Aperto de implementação:** construtores compartilhados de DDL recebem a lista
como parâmetro **obrigatório, sem default**. Com default, o próximo chamador
distraído omite o parâmetro e a lista viva volta a ser resolvida na leitura.
Guard-rail no gate trava a tupla congelada de cada migração
(`tests/test_ledger_imutabilidade.py`) — se alguém editar migração histórica, o
gate acusa (lição do R2: invariante executável, não memória de revisor).

### Verificação de ambiente (não substitui a migração)

```bash
cd backend && python3 init_tables.py
```

Confere tabelas esperadas e triggers de imutabilidade e **falha (exit 1)** se
faltar trigger — a correção é rodar `alembic upgrade head`, nunca "deixar o
init_tables criar".

> ⚠️ **Regra derivada:** todo invariante que o CLAUDE.md afirma como garantido
> *pelo banco* precisa de migração + teste que rode nos dois dialetos. Sem isso,
> a afirmação vale só para o dialeto de desenvolvimento.

---

## 10. Taxonomia de contribuição — classificação obrigatória de mudanças

**Padrão Arquitetural**: estados computados não são persistidos; flag read-only deriva de fonte autoritativa.

Toda mudança no PicSaúde deve ser classificada antes de ser implementada.
A classificação determina o nível de revisão exigido.

| Classe | O que é | Revisão exigida |
|---|---|---|
| `core` | Altera núcleo: NUCLEO_SANITARIO, ledger, máquina de estados, custódia, RBAC, documento canônico | **Revisão central obrigatória** |
| `module` | Novo objeto sanitário ou extensão de módulo existente (ex: novo endpoint de prescrição) | Checklist NUCLEO_SANITARIO + revisão |
| `adapter` | Integração com sistema externo — **nunca escreve diretamente no banco clínico** | Revisão de contrato de interface |
| `local-extension` | Customização institucional que não altera semântica clínica (ex: campo extra, relatório local) | Revisão de isolamento |
| `docs` | Documentação sem impacto em código executável | Revisão de consistência |
| `ops` | Infraestrutura, empacotamento, scripts, CI/CD | Revisão de segurança operacional |

### O que exige revisão central obrigatória (classe `core`)

Qualquer mudança nas seguintes áreas é `core` e **não pode ser feita sem aprovação**:
- `NUCLEO_SANITARIO.md`
- `CLAUDE.md`
- `ETHICS.md` — não-objetivos éticos (ex.: sem monetização de dado do paciente; ver guard-rail em `backend/tests/test_guardrail_sem_monetizacao.py`)
- Máquinas de estados oficiais (`domain/states*.py`)
- Ledger (`*_eventos` — qualquer nova tabela ou alteração de semântica)
- Cadeia de custódia (`prescricao_custodia` ou equivalente)
- Documento canônico e assinatura (`domain/documento_canonico.py`)
- Protocolos públicos (endpoints `/public/*`)
- RBAC e autenticação (`auth/`)

### Regra para adapters (classe `adapter`)

```
adapter NUNCA:
  - escreve diretamente em tabelas clínicas (prescricoes, dispensacoes, etc.)
  - emite eventos no ledger diretamente via SQL
  - bypassa endpoints oficiais
  - altera estados de objetos sanitários sem passar pela API

adapter SEMPRE:
  - consome eventos ou endpoints oficiais do PicSaúde
  - tem seu próprio banco ou store (se precisar de persistência)
  - é observável (logs, health check)
  - é versionado independentemente do núcleo
```

### Regra para extensões locais (classe `local-extension`)

```
local-extension NUNCA:
  - altera semântica clínica dos objetos (estados, ledger, custódia)
  - quebra contratos públicos existentes
  - adiciona campos obrigatórios a tabelas do núcleo

local-extension PODE:
  - adicionar campos opcionais com NULL default
  - criar tabelas auxiliares próprias
  - customizar UI sem alterar API
  - adicionar relatórios e dashboards
```

### Nota sobre a camada de publicação de eventos (G4)

O PicSaúde é atualmente **event-sourced internamente** (ledger imutável) mas **não é event-driven externamente** — não há mecanismo de publicação de eventos para consumo externo.

Antes de qualquer adapter real ser construído, é necessário implementar a **Event Publishing Layer (G4A)**:
- Endpoints de polling de eventos: `GET /eventos?since=...&org_id=...`
- Registro de webhooks por org_id (futuro)
- Formato canônico de evento externo

**Sem G4A, adapters não têm onde se conectar.** Não iniciar adapter de HIS, TISS, HL7, e-SUS, ou qualquer sistema externo antes de G4A existir.
