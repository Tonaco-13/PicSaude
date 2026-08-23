# SESSÃO 2026-08-22 — ENG-014: recepção, histórico e laudo×item

| Campo | Valor |
|---|---|
| **Despacho** | ENG-014 (recepção, histórico e laudo×item — série pós-J) |
| **Martelos** | (a) abrir o laudo = dar ciência · (b) faturamento ancorado na liberação — Fabiano, 20/08 |
| **Executor** | Engenheiro · **NÃO versionado** (docs sem ordem não se commitam) |
| **Base** | `main` em `11f1de9` → **`8f6bf90`** |

---

## §0 Entregue

| PR | Classe | SHA | O quê |
|---|---|---|---|
| **#175** | `module` | `31d1ede` | Recepção age do cartão + **guard de escopo por item no agendamento** |
| **#176** | `module` | `178cc61` | Aba Histórico (read-only, mesma fonte do relatório) |
| **#177** | `module` | `8f6bf90` | **Frente 2** do PR C: abrir o laudo é dar ciência |
| **#178** | `module` | `5735d0f` | **Frente 1 (v2)**: o elo `pedido_item_id` + ponte para legados |
| **#179** | `ops` | `0cb8b73` | Laudo-demo do seed nasce com o elo |

Gates finais na `main`: unit **541** · integração **556** · navegador **94**.

---

## §1 ⚠️ DEVOLVIDO AO ARQUITETO — frente 1 do PR C (posse por item no laudo)

O **§2 do desenho** manda os guards de `laudos.py` usarem:

| Gesto | Guard novo (desenho) |
|---|---|
| CRIAR laudo | detém o pedido **OU todos os itens do laudo** |
| Operar laudo | detém o pedido **OU ao menos um item DESTE laudo** |

**Isso pressupõe um elo `laudo_item → pedido_item` que não existe no schema.**
Verificado no código:

- `models/laudo_item.py` — colunas: `laudo_id`, `nome_exame`, `codigo_tuss`,
  `resultado_resumo`, `conclusao`, `valor_referencia`, `resultado_url`,
  `status_item`, `criado_em`. **Nenhum `pedido_item_id`.**
- `routers/laudos.py::ItemLaudoIn` — recebe `nome_exame` e `codigo_tuss`.
  Também não recebe id de item do pedido.

O único casamento possível hoje é por **`nome_exame`** — texto livre.

### Por que parei em vez de implementar

Basear **autorização** em casamento de nome é a mesma família de defeito que
esta casa já rejeitou três vezes:

- **J.7** — ler posse do `status` (proxy) em vez da custódia (fonte);
- **#168** — predicado de posse duplicado em dois arquivos, divergindo em silêncio;
- **#172** — relatório lendo nível-pedido quando a posse virou por item.

Um exame renomeado, ou dois itens de mesmo nome no mesmo pedido, mudariam **quem
pode operar o laudo**. Não é detalhe de implementação: é a chave de uma decisão
de segurança. §3 do ENG-012 manda parar e devolver — parei.

### Duas opções, para sua decisão

**(1) Criar o elo de verdade.** `pedido_item_id` em `laudo_itens` (migração,
dois dialetos) + `ItemLaudoIn` passa a recebê-lo. O guard do §2 fica
implementável como escrito, sobre chave autoritativa. Custo: migração + tocar
o caminho de criação do laudo (a bancada escolhe itens — ela já sabe os ids).

**(2) Afrouxar o guard.** "detém o pedido **OU ao menos um item do pedido
vinculado**" — repousa em custódia autoritativa e **resolve o bug real**: hoje,
num pedido explodido em nível-item, `dispensador_detem_pedido` devolve `False`
para todo mundo e **nenhuma unidade** consegue operar o laudo. É menos preciso
que o §2 pede (uma unidade que detém o item X poderia operar um laudo que cobre
só o item Y), mas é honesto sobre o que o schema sustenta.

Minha leitura: **(1)** é o certo; **(2)** é aceitável como ponte se houver
pressa, desde que registrada como tal. Não escolhi sozinho.

> O bug que a frente 1 existe para consertar **continua aberto** — não piorou,
> mas também não foi fechado. Está nomeado aqui para não sumir.

---

## §2 PR #175 — o guard que o despacho chamou de obrigatório

`POST /agendamentos` promovia a `agendado` **todos** os itens `pendente` do
pedido. Com a custódia parcial, o laboratório que detinha **1 de 3 agendava os
3** — inclusive os que o cidadão nem entregara.

Mesma família do AC (vi) do J.10, um andar acima: **lá a fila MOSTRAVA item
alheio; aqui o agendamento MEXIA nele.**

- `itens: [...]` opcional; ausente = **os que detenho** (não "todos" — essa era
  a suposição que a parcial invalidou); item alheio → 403; sem posse → 403;
  `itens: []` → 422.
- Escopo por posse só para `dispensador`; prescritor/paciente/admin inalterados.
- Os 7 testes foram escritos **vermelhos** antes do fix.

### A recepção delega — e é isso que importa

As três ações do cartão **não reimplementam** nada. As funções existentes
carregam guardas que um atalho perderia em silêncio:

| delegado | guarda |
|---|---|
| `realizarAgendamento` | gate de contexto **CNES** (Ticket 46) |
| `registrarColeta` | **403 como POSSE**, não sessão expirada (TICKET-I.4) |
| formulário de agendar | um só — o segundo nasceria sem `_aplicarContextoNoForm` |

Guarda estática trava isso, conferida por mutação.

---

## §3 PR #176 — Histórico

Mesma fonte do relatório de propósito: uma segunda verdade sobre "o que é meu"
divergiria da primeira na próxima mudança de forma da custódia — foi o que
aconteceu no #172. "Concluído = tem resultado" é o mesmo fato que ancora o
faturamento, então as duas telas não podem discordar.

Subiu **sem** o selo "Lido em" (guarda de escopo no E2E), e o #177 o acrescentou.

---

## §4 PR #177 — a abertura como fato

Martelo (a) implementado como escrito: o evento nomeia a **abertura**; a ciência
é derivada e o ledger diz `origem: "abertura"`. Idempotente por `aberto_em` —
um fato, um evento. **Máquina de estados: mudança nenhuma** (caminho novo para
aresta existente, mesmo formato do J.7).

Martelo (b) preservado com regressão explícita: laudo aberto e não-aberto
faturam igual.

O botão "Dar ciência" saiu da carteira — era clique morto. Dois E2E existentes
migraram ao gesto novo, sem afrouxar asserção.

### Bug achado pelo próprio teste de idempotência

1ª abertura respondia `...T17:52:13`; a 2ª, `... 17:52:13` — mesmo instante,
formatos diferentes (PG `datetime` × SQLite `str` × a ISO recém-gerada). Um
cliente que comparasse os dois para decidir "já abri?" concluiria que mudou.
`_iso()` normaliza.

---

## §5 Erros meus no caminho (para o registro)

1. **`apiFetch` na `clinica.html`** — usei o helper de outra tela; a tela usa
   `fetch` + `authHeaders()`. Pego pelo E2E.
2. **`_filaCache` nunca declarado** — um script de edição abortou num assert
   antes do write, e eu segui como se tivesse gravado. Pego pelo E2E
   (`PAGEERROR: _filaCache is not defined`). Lição: conferir o efeito da edição,
   não só o "ok" impresso.
3. **`esc()` na `cidadao.html`** — o arquivo não define; quebrou o render dos
   laudos inteiro. Pego pelo E2E.
4. **Âncoras de DOM instáveis** em dois testes meus (painel de aba oculto,
   troca automática de aba pelo J.8) — trocadas por espera no efeito real.

Nenhum chegou a PR: todos morreram no gate local.

---

## §6 Pendências

1. ~~**Frente 1 do PR C**~~ — **resolvida**: desenho v2 com errata, entregue em
   #178. Ver §7.
2. **Parecer retroativo do J.11** e **PR docs** — fila paralela sua; o PR docs
   aguarda ordem do Fabiano e está **acumulando** (§7.3).
3. O relatório desta sessão segue **não versionado**, como o de 19–20/08.

---

## §7 Fecho — frente 1 (v2), o seed, e o que o PR docs acumula

### §7.1 Frente 1 resolvida — #178 (`5735d0f`)

O arquiteto registrou a **errata** do §2 (o stop foi dado como correto) e
decidiu: **elo de verdade + ponte declarada**. Entregue como especificado.

- **`laudo_itens.pedido_item_id`** (migração `f2d8b41c9e73`, dois dialetos,
  **sem backfill**). O id é a chave; `nome_exame` virou exibição.
- **Duas camadas:** criação por dispensador exige o elo em todos os itens, cada
  um sob custódia; operação pede o pedido **OU** um item do laudo **com elo**.
- **Ponte §2.2** (`dispensador_tem_algo_no_pedido`, do #172, reusado) para os
  legados — e é ela que **fecha o bug que estava aberto** (pedido explodido →
  ninguém operava o laudo). Havendo elo, ele manda: a ponte não é consultada,
  para que a frouxidão do legado não vaze para o novo. Há teste dessa fronteira.

Os dois ACs que provam por que o nome não servia:

| AC | Caso |
|---|---|
| (viii) | **dois "HEMOGRAMA"** no mesmo pedido, um por unidade — A lauda o seu (201) e é barrada no de B (**403**). Pelo nome, seriam o mesmo item |
| (ix) | laudo escrito *"Hemograma (série vermelha)"* sobre item *"HEMOGRAMA COMPLETO"* → **201**: o direito vem do id |

**A tela já sabia o id.** `_coletarItensDoEditor` sempre coletou
`dataset.itemId`; o mapeamento explícito do POST é que o descartava. Duas linhas
na `clinica.html` — a bancada não mudou de gesto.

**Correção que um teste seu cobrou.** Minha primeira versão punha o 422 do elo
ausente **antes** do 403 de posse: uma unidade estranha passava a receber 422
onde antes recebia 403, aprendendo que o endpoint espera `pedido_item_id`.
Inversão anti-leak (#52), pega por
`test_disp_de_outra_unidade_403_em_todas_as_superficies`. Ordem final: guarda
grossa primeiro; só quem **é parte** recebe o 422 que o ensina.

Quatro arquivos de teste existentes precisaram do elo; **um helper central
resolveu 16 casos de uma vez**, sem afrouxar asserção.

### §7.2 #179 — o seed, e uma premissa corrigida

O laudo-demo nascia **legado** (sem elo) a cada reset, caindo na ponte §2.2 —
que existe para o histórico de verdade, não para objeto novo. Corrigido; o id é
lido por `SELECT` e não por `lastrowid` (o wrapper de PG e o SQLite não
concordam sobre ele, e o seed roda nos dois). Guardas nos dois dialetos,
conferidas por mutação.

**Mas a causa atribuída no ticket não procedia.** O ticket ligava o elo à
ausência do selo "Lido em". Verifiquei antes de mexer: `_SQL_LAUDOS_DO_CNPJ`
não referencia `pedido_item_id` (casa por custódia do pedido) e o selo depende
só de `laudos.aberto_em`. Reproduzido em PG semeada **com o elo ainda ausente**:
laudo no Histórico, `POST /abrir` → 200, `aberto_em` preenchido.

A vitrine não mostrava "Lido em" porque **ninguém tinha aberto o laudo-demo** —
estado inicial correto para a demo, e justamente o que o roteiro demonstra.

> Correção aceita pelo arquiteto, com a regra derivada registrada: **ticket
> traz sintoma; hipótese vem marcada como hipótese.** Vale nos dois sentidos —
> eu também devo separar as duas coisas ao reportar.

### §7.3 O que o PR docs acumula (e o buraco na cadeia de autoridade)

Três arquivos em disco, não versionados:

```
docs/tickets/DESENHO-LAUDO-POSSE-POR-ITEM-E-ABERTURA.md      (arquiteto, v2 com errata)
docs/tickets/SESSAO-2026-08-19-TICKET-ENG-013-REVISAO-E-RBAC.md  (com o §6 do martelo)
docs/tickets/SESSAO-2026-08-22-TICKET-ENG-014-...md          (este)
```

**E dois despachos que autorizaram todo este trabalho não existem como
arquivo:** `DESPACHO-ENG-013` e `DESPACHO-ENG-014` vieram pelo chat, como
vieram o parecer de 20/08, a ordem do martelo e a decisão da frente 1 (v2).

Consequência, já sinalizada em 19/08 e agora maior: o repo guardará o
**registro** dos martelos e a **execução**, mas não os **despachos** que os
autorizaram. Para um `core` como o #168/#171, a cadeia fica pela metade.

Duas saídas, e a escolha é do arquiteto porque os documentos são dele:

1. ele escreve os despachos como arquivo, e eu levo tudo num PR `docs`;
2. eu transcrevo o que recebi, **marcado como transcrição do chat feita pelo
   engenheiro**, e ele confere antes de o PR sair.

Não fiz nem uma nem outra: transcrever despacho alheio muda o registro de
autoria, e docs sem ordem não se commitam.

---

*Relatório do engenheiro, 2026-08-22, fechado em 22/08 após #178 e #179.*
