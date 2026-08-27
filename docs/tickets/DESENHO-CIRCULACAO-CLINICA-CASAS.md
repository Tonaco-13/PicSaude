# Desenho — a clínica ganha casas por estado, e a Realização se dissolve (`module`)

| Campo | Valor |
|---|---|
| **Origem** | Fabiano percorreu a vitrine em 26/08 pedindo parecer sobre a circulação do exame na clínica; a troca virou proposta, aprovada por partes — o martelo sobre a ciência do pedido já saiu como `core` (#203/#204). Este desenho cobre o resto: a forma das abas. |
| **Autor** | Engenheiro (Claude Code) — desenho, **não implementação** |
| **Classe** | `module` — telas e contadores da clínica. Nenhuma máquina de estados, ledger ou custódia é tocada; ver §5 sobre a fronteira |
| **Estado** | 🟢 Martelado (Fabiano, 27/08, §6). PR A em implementação; PR B aguarda os PRs 2/4 da CONSULTA-UX-001 |
| **Pré-requisito já cumprido** | O martelo de 26/08 (abrir o laudo encerra o pedido, #203/#204) — sem ele a casa nova do §2 não fecharia sozinha |

---

## §0 O que o Fabiano pediu, e o que já foi resolvido

> *"Os objetos dentro da clínica devem circular da esquerda para a direita livremente, mas com
> um passo de cada vez na execução. No histórico, não circula mais."*

A resposta, dada percorrendo a vitrine com um pedido real: a circulação **Realização → Bancada**
já anda assim, um passo de cada vez. O que não anda é o **contador** — ele fica aceso depois que
o objeto já saiu da casa, porque a régua de cada aba mede coisa diferente da régua das outras.
Isso já foi corrigido nos casos mais graves:

- A **ciência do pedido derivada da abertura do laudo** (martelo 26/08, #203/#204) — sem isso, o
  item ficava preso em `resultado_disponivel` esperando um segundo gesto do cidadão que a
  consultoria já tinha apontado como duplicado (NC-6). Agora o laudo lido **fecha o pedido
  sozinho**, na régua exata que o pedido repartido exige.

O que falta é a **forma das abas** — e é o que este desenho resolve.

---

## §1 O achado que muda o desenho: a Realização não é uma casa

Percorri a régua de cada aba no código (`clinica.html`):

```js
const _ETAPAS_POS_COLETA   = ['coletado', 'em_analise', 'resultado_disponivel'];
const _ETAPAS_ENCERRADAS   = ['encerrado', 'cancelado', 'encerrado_fisico'];

function _itensDaAbaRealizacao(itens) {
  return itens.filter(i => !_ETAPAS_POS_COLETA.includes(i.status_item)
                         && !_ETAPAS_ENCERRADAS.includes(i.status_item));
}
```

Isso é `pendente` **ou** `agendado` — exatamente os mesmos itens que já povoam a **Recepção**
(`pendente`) e o **Agendamento** (`agendado`). A Realização não guarda estado próprio: ela é uma
segunda vitrine dos mesmos dois estados, com um botão a mais.

Confirmado na excursão real: abri um pedido recém-chegado e a Realização marcou **2** — os
mesmos dois exames que a Recepção estava com `1` esperando decisão.

**Consequência para o desenho:** fundir Realização com Bancada — a alternativa óbvia — juntaria
a duplicata com uma casa que já é boa, e a fronteira do passo (que é o que o Fabiano quer
preservar) sumiria de vista numa casa de quatro estados. A correção não é fundir; é
**dissolver**: a Realização deixa de existir como aba, e o botão que ela oferece (coletar) migra
para as duas casas onde o exame já mora.

---

## §2 A régua nova: uma casa por estado, sem sobreposição

### 2.1 O princípio

> Cada exame mora em exatamente uma casa. A casa é onde ele **está**, não por onde ele **passou**.

### 2.2 O mapa

| Casa | Guarda (`status_item`) | Gestos disponíveis |
|---|---|---|
| **Recepção** | `pendente` | agendar · **coletar agora** · não realizamos (item) |
| **Agenda** | `agendado` | confirmar presença · **coletar** · remarcar · faltou |
| **Bancada** | `coletado` · `em_analise` | enviar à bancada · registrar resultado · produzir laudo |
| **Aguardando o cidadão** ⟵ *nova* | `resultado_disponivel` **e** `laudado === true` | nenhum — só leitura e acompanhamento |
| **Histórico** | `encerrado` · `cancelado` · `encerrado_fisico` | nenhum — só leitura |

Duas linhas merecem nota:

- **Recepção e Agenda ganham o gesto de coletar**, que hoje já existe nos dois — na fila da
  Recepção e no compromisso da Agenda (`registrarColeta` e `realizarAgendamento`) — e que a
  Realização apenas repetia com um terceiro rótulo ("Registrar coleta"). Isso não é gesto novo:
  os dois endpoints já emitem `pedido_coletado`; só muda **onde o botão mora**, e a Realização
  perde a cópia redundante.
- **A casa nova depende do campo `laudado`**, que o #201 (ENG-019 PR 1) já introduziu no payload
  do pedido para o gatilho de laudo. Reuso, não invento campo.

### 2.3 Por que a casa nova, e não continuar contando na Bancada

Hoje `_itensDaAbaBancada` inclui `resultado_disponivel` — por isso, depois de eu liberar um
laudo, a Bancada continuou marcando **2** mesmo sem ter mais nada a fazer. O item que só espera
o cidadão abrir não é trabalho de bancada: é trabalho **de ninguém no laboratório**, e uma casa
que mistura "o que eu preciso tocar" com "o que já não é meu" é uma lista de pendências que
mente.

A régua da casa nova:

```js
function _itensAguardandoCidadao(itens) {
  return itens.filter(i => i.status_item === 'resultado_disponivel' && i.laudado === true);
}
```

Um item `resultado_disponivel` **sem** laudo continua na Bancada — é exatamente o caso que o
próprio martelo de 26/08 declarou como "resultado que ninguém laudou não é ciência de ninguém";
ele ainda espera o laboratório, não o cidadão.

### 2.4 O que acontece quando o cidadão abre

Nada que este desenho precise fazer. O #203/#204 já garantem que, na abertura, o item vai a
`encerrado` (quando não resta mais nada por ler no pedido) — e aí ele sai de "Aguardando o
cidadão" e entra no Histórico **sozinho**, no próximo `GET`. A casa nova é, literalmente, a
materialização visual do painel de laudo que a vitrine já mostra (`Liberado · Ciência do
cidadão · Encerrado`), só que em nível de lista, não de card avulso.

---

## §3 A volta (direita → esquerda): duas coisas com nomes diferentes

A régua acima não é unidirecional por acidente — ela responde ao "vice-versa" que o Fabiano
pediu, mas com uma distinção que a tela hoje não faz:

### 3.1 Recuo — real, e deve ser visível

Desmarcar um agendamento (`nao_compareceu`/cancelamento) devolve o item de `agendado` para
`pendente` — ele sai da casa Agenda e volta para a Recepção. Isso já é o comportamento do
backend (`states_exame.py`); a régua de §2 só precisa **deixar isso visível**: hoje, se o
operador estiver com a aba Recepção fechada, o recuo acontece sem que ele veja o contador mudar
na hora — porque a Recepção lê `fila-count`, um contador **independente** (ver §4), e não o
conjunto de itens do pedido em foco.

### 3.2 Saída — não é recuo, é fronteira

"Não realizamos" não devolve o item uma casa para trás: ele **sai da clínica**. A custódia volta
ao paciente (`devolucao_nao_realizavel`, J.10), que pode levar o exame a outro laboratório — o
objeto deixa de existir, para esta unidade, tanto quanto a régua de §2 é capaz de mostrar.

**Proposta:** os dois gestos devem ter pesos visuais diferentes. Recuo (remarcar, faltou) é
botão discreto, sem confirmação pesada — é reversível e comum. Saída ("Não realizamos") é gesto
de fronteira: confirmação com o que está sendo devolvido, no mesmo espírito do que o PR 3 da
CONSULTA-UX-001 já propõe (listar os N itens antes de devolver). Este desenho **não substitui**
o PR 3 — reforça o motivo de ele ser necessário.

---

## §4 A Recepção precisa de régua própria

`fila-count` é a fila **global** da unidade (quantos pedidos aguardam decisão, contando pedidos,
não itens), e não muda com o pedido em foco. Na excursão, isso produziu o sintoma mais confuso
da sessão: com um pedido já 100% coletado e na Bancada, a Recepção continuava marcando `1`.

**Proposta:** manter `fila-count` como está para a fila **sem foco** (ele já serve a esse
propósito e não deve mudar), mas — com pedido em foco — a aba Recepção passa a contar os itens
`pendente` **daquele pedido**, na mesma régua que as outras quatro casas já usam:

```js
function _itensDaAbaRecepcao(itens) {
  return itens.filter(i => i.status_item === 'pendente');
}
```

Isso resolve a assimetria "recepção nunca é 0 mesmo depois que tudo saiu de lá" sem tocar no
comportamento da fila sem foco, que continua sendo — corretamente — uma lista de pedidos, não de
itens.

---

## §5 Fronteira do que este desenho NÃO faz

Nenhuma linha deste desenho toca `states_exame.py`, `pedido_exame_eventos` ou
`pedido_exame_custodia`. É reorganização de **onde a tela mostra** um estado que já existe, com
um filtro adicional (`laudado`) que já é lido do backend. A classificação `module` se sustenta
nisso — mas duas coisas merecem checagem explícita do arquiteto antes do martelo:

- O botão de coletar, hoje já duplicado em nome (`registrarColeta` na fila e na Realização,
  `realizarAgendamento` no compromisso), passa a aparecer em **dois lugares visuais**, sem
  ganhar terceira função — são os mesmos dois endpoints, chamados do mesmo jeito. Se o
  arquiteto achar que isso ainda assim merece revisão central por tocar em superfície de ação
  clínica, este desenho se reclassifica.
- A casa "Aguardando o cidadão" **não tem gesto nenhum** — de propósito, para não convidar o
  laboratório a agir sobre algo que já não é dele. Se o Fabiano quiser um botão de
  "reenviar/lembrar" ali no futuro, é escopo novo, não deste ticket.

---

## §6 Martelo (Fabiano, 27/08)

### 6.1 O nome da casa nova — MARTELADO: "Aguardando o cidadão"

Confirmado. Argumento decisivo: o painel do laudo, já em produção, diz literalmente **"⏳ Na
carteira do cidadão, aguardando ciência."** (`clinica.html:3419`). O nome da casa ecoa o
vocabulário que o operador já lê, em vez de introduzir termo novo — e evita o custo de uma
segunda curva de aprendizado sem ganho.

Nota de precisão que sustentou a escolha, e que serve de guarda para não se propor mudar o nome
sem reabrir esta checagem: **abrir/liberar o laudo não transfere a posse do ITEM de volta ao
cidadão** — `laudos.py` nunca chama `transferir_posse_exame`. O que vai à carteira é o
**documento**; o item de exame, em `pedido_exame_custodia`, permanece registrado com o
laboratório. Por isso "Com o cidadão" foi descartado: seria uma afirmação de posse que o sistema
não faz.

### 6.2 Ordem de implementação — MARTELADO: A imediato, B batido com os PRs 2/4

Confirmado o raciocínio do §6.2 original, reforçado pela lente clínica: um contador que MENTE
é pior que um contador ausente — o operador aprende a desconfiar dele e para de checar quando
importa (o mesmo mecanismo do alarme que berra demais em UTI, ao contrário: aqui é silêncio
falso). A Bancada presa em 2 depois que não há mais nada a fazer é esse risco.

- **PR A** (implementado nesta rodada) — a casa nova (§2.3) + a régua da Recepção com foco (§4).
- **PR B** — dissolver a Realização (§2.2). Fica para quando os PRs 2 e 4 da CONSULTA-UX-001
  forem martelados, porque PR B move o local físico de um botão clínico (memória motora do
  operador) — trocar isso deve acontecer **uma vez só**, junto com os outros PRs que já mexem
  no mesmo lugar, não em duas ondas separadas de readaptação.

---

*Desenho do engenheiro, 2026-08-27, a partir da excursão registrada na conversa com o Fabiano em
26/08. Implementação aguarda o martelo do §6.*
