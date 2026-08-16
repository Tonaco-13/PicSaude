# Sessão 2026-08-15 (parte 2) — Engenheiro: PRs abertos + J.7 implementado

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator |
| **Despacho** | `DESPACHO-ENG-011-J7-CNES-DURAVEL-ABAS.md` + Adendos 1 e 2 |
| **Parecer** | `SESSAO-2026-08-15-PARECER-ARQUITETO-ENG-011-REVISAO.md` — APROVADO com 2 determinações |
| **Base** | `main` em `097534a` (pós-merge #162) |
| **Estado** | **3 PRs abertos, CI verde** · J.10 **desenhado** (não implementado) |

---

## §1 Os três PRs

| PR | Classe | Base | CI |
|---|---|---|---|
| [#163](https://github.com/Tonaco-13/PicSaude/pull/163) — CNES durável no boot | `ops` | `main` | ✅ gates + smokes |
| [#164](https://github.com/Tonaco-13/PicSaude/pull/164) — abas J.8/J.9 + desambiguante 403 | `module` | `main` | ✅ gates + smokes |
| [#165](https://github.com/Tonaco-13/PicSaude/pull/165) — J.7: transferir é posse, não agenda | `core` | **#164** | (ver §5) |

**Determinação §3.1 do parecer cumprida:** ambos os PRs originais saíram de branches novos a
partir da main atual. Confirmei que o squash do #162 (`097534a`) tem conteúdo idêntico ao
`aeae896` de onde o trabalho vinha (`git diff aeae896 origin/main --stat` → vazio), então o
carregamento foi limpo. Cada branch foi rodada **isoladamente** antes do push, como o CI faria.

**Determinação §3.2 cumprida:** ordem Receita·Exames·Atestado mantida; a troca de critério do
F5-C3 ficou como está.

---

## §2 J.7 — `core`: transferir ao laboratório é posse, não agenda

### A forma técnica escolhida

O §4.2 dava duas candidatas e mandava o engenheiro propor. **O martelo do §11a já escolheu**:
*"itens continuam `pendente`"* → forma **(a)**. O pedido permanece `emitido`, e a custódia vira
a fonte da verdade da posse. `derivar_status_pedido(["pendente"])` já devolvia `"emitido"` —
o derivador não precisou de uma linha.

**Nenhum estado novo** (a proibição do §4.2 respeitada). Duas **arestas**, ambas consequência
direta do *"ou realizando direto"* do martelo:

- `pendente → coletado` (item)
- `emitido → coletado` (pedido)

Declarar as arestas não é formalidade: `derivar_status_pedido` **não valida transição**, então
sem elas a máquina declarada e a máquina real discordariam em silêncio até uma auditoria de
ledger. Há teste que confronta as duas.

### A cascata — o que o §4.4 mandava verificar, verificado

O ponto central é que **três consumidores liam POSSE do STATUS**, e o status parou de responder
essa pergunta. Cada um seria verde no backend e quebrado na vitrine:

| Sítio | O que quebraria |
|---|---|
| guard de `transferir-laboratorio` (era `status != 'emitido'`) | o cidadão entregaria o **mesmo** pedido a um segundo CNPJ enquanto o primeiro o detém — dupla posse ativa, o R2 na camada de custódia (§3) |
| `_ESTADOS_ITEM_ACIONAVEL_LAB` (não tinha `pendente`) | a fila esconde pedido sem item acionável → o exame recém-entregue **sumiria** da tela do laboratório |
| `cidadao.html` (`emPosse = status === 'emitido'`) | reofereceria "Transferir Custódia" de algo já entregue, com a etiqueta "Com você" logo acima de "Custódia transferida" |

Os três migraram para a custódia, via dois helpers novos com **fonte única do predicado**:
`detentor_atual_pedido()` e `posse_do_cidadao()`.

`derivar_status_pedido` **não** precisou mudar — status de item nunca dependeu de custódia.

### O bug que só o gate de navegador pegou

`pedido_exame_custodia.para` guarda o **papel** (`'paciente'`) para o cidadão e o **CNPJ** para o
prestador; o CPF vive só em `dados_json.para_id`. O primeiro guard comparava o detentor com o
CPF do JWT e **recusava o dono legítimo com 409**.

A integração ficou verde: todos os seus testes emitiam **sem** `enviar_ao_paciente`, então
`detentor` vinha `None` e o ramo defeituoso nunca era exercido. A vitrine quebrava.

Corrigido com `posse_do_cidadao()` — e o **buraco de cobertura foi tapado junto com o bug**:
`_emitir_pedido` ganhou o parâmetro `enviar_ao_paciente`, e há teste novo que emite pelos dois
caminhos e confere a custódia inicial (`('prescritor', 'paciente')`) antes de transferir.

> Vale registrar por que o gate de navegador foi quem achou: ele é o único que roda contra o
> **seed da demo**, onde a emissão passa por `enviar_ao_paciente`. É a mesma família da lição
> "gate não enxerga dado do seed".

### Testes

| Camada | Novos / mexidos |
|---|---|
| unit | `test_states_exame_j7_posse.py` — 8 guardas (arestas, derivação × contrato, "nenhum estado novo" congelado por valor) |
| integração | 3 reescritos + 5 novos em `test_transferencia_exame_cidadao.py` (AC i–iv + carteira + custódia inicial) |
| navegador | `test_j7_transferir_e_posse.py` — 5 smokes; inclui a **persona LABORATÓRIO agendando**, que a fixture de integração não consegue exercitar (403 fail-closed sem `prestadores.cnpj → org_id` semeado) |

### Docs `core`

`CLAUDE.md` §7 e `docs/ARQUITETURA_EXAMES.md` passam a declarar a regra **e o corolário**:
`pedidos_exame.status` não responde "onde está o pedido"; quem responde é a custódia. Sem essa
frase escrita, o próximo a passar reintroduz o proxy sem perceber.

`guia.html` **não menciona** o fluxo de exame — nada a ajustar (AC §4.3.v verificado, não
presumido). O DDL-doc não declara estados de exame.

---

## §3 Base do PR #165 — por que empilhado no #164

O §11d põe o `core` antes do `module`. Só que o PR module **já estava aberto** por ordem do
Fabiano quando o martelo chegou, e o J.7 precisa mexer em `clinica.html` (botão de coleta para
item `pendente`) — arquivo cuja função de render o #164 reescreveu. Basear na `main` produziria
conflito garantido.

Empilhar mantém base fresca e diff honesto. **Ordem de merge: #164 → #165.** Ao mergear o #164,
o GitHub reaponta o #165 para a `main` sozinho.

Se o arquiteto preferir a ordem do §11d, o caminho é mergear o #165 primeiro rebasando-o em
`main` e assumindo o conflito em `clinica.html` — resolvível, mas é retrabalho sem ganho.

---

## §4 J.10 — desenhado, não implementado (§11c)

Desenho completo em **`docs/tickets/DESENHO-J10-CUSTODIA-PARCIAL-EXAMES.md`**.

Dois achados que mudam a conversa:

**1. O AC (iii) é inalcançável sobre o schema atual.** O §11c parte de *"`item_id` nullable já
suporta nível-item; falta endpoint"*. O `item_id` suporta — mas `pedido_exame_custodia` é um
**ledger append-only** (`de`/`para`/`transferido_em`), sem `encerrada_em`. Num ledger não existe
"linha ativa" para um índice único restringir. A custódia da **receita** tem outro formato
(posse atual + índice único parcial, COER-2); a do **exame** nunca teve.

Logo: a constraint pedida exige **migração** — e mexer na cadeia de custódia é `core` pela
taxonomia do §10, não `module`. Proponho (recomendado) partir a migração num PR `core` próprio
e deixar o J.10 `module` de verdade empilhado nele. **Isso precisa de martelo antes de eu
começar** (§3 do despacho).

**2. O J.7 é pré-requisito semântico, não só de ordem.** Um pedido com 2 itens no laboratório e
3 com o cidadão **não tem** status que descreva a posse. Enquanto status fosse proxy de posse, a
custódia parcial era insolúvel. Com os eixos separados pelo J.7, `derivar_status_pedido` não
precisa de mudança nenhuma para o J.10.

Um achado de segurança entrou no escopo: a fila do laboratório hoje casa só custódia de
nível-pedido. Com transferência parcial, sem filtrar os itens exibidos por custódia, **um
prestador veria e poderia acionar exames que estão com outro**. Virou AC (vi) no desenho.

---

## §5 Gates

Rodados em cada branch **isoladamente**, como o CI faz:

| Branch | unit | integração (PG 15 efêmero) | navegador |
|---|---|---|---|
| `ops/cnes-demo-durable` | ✅ 449 | ✅ 466 | ✅ 68 |
| `module/abas-j8-j9` | ✅ 452 | ✅ 466 | ✅ 74 |
| `core/j7-transferir-e-posse` | ✅ 1647 · **zero regressão** (52 falhas = linha de base, `comm -13` vazio) | ✅ 471 | ✅ 79 |

CI do GitHub: **#163 e #164 verdes** (gates + smokes). #165 rodando na abertura deste relatório.

> `tests/integration/test_concorrencia.py` segue sem coletar (importa `DATABASE_URL_TEST`
> inexistente no conftest) — **pré-existente na main**, rastreado no §4 do parecer.

---

## §6 Um ponto que precisa do olho do arquiteto

**Os Adendos 1 (§10) e 2 (§11b) acrescentaram escopo ao J.9 que o PR #164 não contém.**

Meu relatório anterior e o PR #164 foram escritos antes desses adendos — o mesmo descompasso
que o parecer apontou sobre o martelo do J.7 (§5 do parecer). O §11d lista o PR module como
"J.8 + J.9 (§6/§7 **+ §10 + §11b**)", e faltam as duas peças:

- **§10 — "resposta ao cidadão":** selo `Agendado: dd/mm hh:mm · Unidade X` no cartão do pedido
  (aba Exames) + caminho de leitura de agendamentos com papel `paciente` no backend.
- **§11b — lente compartilhada:** extrair o render da Lente de Auditoria do `index.html` em
  componente e pôr "ver rastreabilidade" em cada cartão do cidadão.

A ordem do Fabiano nesta rodada nomeou o conteúdo do PR module como "clinica/cidadao + testes",
que é o que #164 entrega — então **não os incluí por conta própria**. Duas saídas:

- **(a)** acrescentar §10 + §11b ao #164 antes do merge; ou
- **(b)** PR `module` próprio depois, o que também deixa o §10 nascer sobre a semântica do J.7
  (com o J.7, o selo só aparece quando existe agendamento de verdade — que é justamente o que o
  §10 quer mostrar). **Recomendo (b).**

Aguardo a definição.

---

## §7 Limites

- Nenhum merge. Os três PRs aguardam ordem.
- J.10 **não** implementado — desenho apenas, e travado no martelo do §5 do desenho.
- Docs não versionados (pareceres, `Fabiano.md`, `planejamento/`) intocados.

---

*Relatório do engenheiro, 2026-08-15 (parte 2). Gates completos verdes nas três branches.*
