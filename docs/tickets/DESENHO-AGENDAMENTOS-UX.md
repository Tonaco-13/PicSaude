# Desenho — organização de agendamentos: recepção, agenda e carteira (`module` + 1 `core` pequeno)

| Campo | Valor |
|---|---|
| **Origem** | Demanda do Fabiano em 23/08 (vitrine) + consulta externa (Kimi, 23/08) integrada pelo arquiteto com verificação no código |
| **Autor** | Arquiteto (Z) — consolidação; implementação do engenheiro |
| **Classe** | 2 PRs `module` (telas) + 1 micro-ticket `core` (RBAC do GET — martelo do Fabiano) + 1 verificação (possível fricção, ver §6) |
| **Estado** | Para o martelo do Fabiano sobre as adoções novas (§2 e §4) |

---

## §1 O princípio: cada aba responde UMA pergunta

| Aba (clínica) | Pergunta | Conjunto |
|---|---|---|
| **Recepção** | "O que chegou — o que eu decido?" | itens `pendente` sob custódia |
| **Agendamento** | "O que está marcado?" | agendamento ATIVO dos pedidos sob custódia |
| **Realização** | "O que eu coleto agora?" | itens prontos p/ coleta (`pendente` direto + `agendado`) |
| **Bancada / Histórico** | — | inalteradas |

Confirmado no código: o item já muda de aba sozinho ao mudar de percurso (J.8) —
a fronteira "Realização = só coleta" já está garantida pelo filtro de percurso.

## §2 Recepção — três decisões, um só lugar

Itens `pendente` sob custódia: **Agendar** · **Executar agora** · **Não realizamos**.

- **"Executar agora" é a COLETA DIRETA do J.7** — aresta `pendente → coletado`
  (`states_exame.py`), UM evento (`pedido_coletado`). **REJEITADA** a sugestão
  externa de "agendamento instantâneo" (criar+confirmar+realizar): inventaria
  três fatos para um ato que não teve compromisso — o padrão
  `pedido_agendado` fantasma que o martelo do J.7 matou.
- **"Não realizamos"** na Recepção = devolução pura (`/devolver`, J.10).
  Sai da Realização (demanda do Fabiano).
- **ADOÇÃO (consulta externa): o caso "agendou e não consegue"** — o gesto
  "Não realizamos" passa a existir TAMBÉM no item `agendado`, como **ato
  composto**: cancela o agendamento (com motivo) **e** devolve a custódia —
  **dois fatos, dois eventos** (`agendamento_cancelado` + `custodia_transferida`),
  nunca UPDATE que funda. Sem isso: item "livre no papel, preso na prática"
  (a unidade só cancela a agenda e a custódia fica presa nela).
- Em `coletado`+ o botão não existe — pós-coleta é outro fato clínico
  (amostra insuficiente), ticket próprio quando o caso real aparecer.
- `motivo` explícito sempre (capacidade ≠ desistência ≠ erro clínico).

## §3 Agendamento — a agenda da unidade (o aviso morre)

- Alimenta-se do **GET /pedidos-exame/{p}/agendamentos aceitando dispensador**
  (micro-ticket `core`, martelo do Fabiano — a última assimetria da família
  do #171), com escopo de posse como o GET do pedido.
- Query com **`WHERE org_id = ?`** (guardrail §6b — agendamento é NOT NULL em
  org/unidade); unidade quando houver.
- Gestos por compromisso: **Executar** (realizar → coletado) · **Remarcar**
  (derivação) · **Registrar falta** · **Não realizamos** (ato composto §2).
- **"Registrar falta" habilitado só após `data_hora` + margem** — validação de
  UX documentada como tal (o domínio permanece permissivo).
- **Cadeia de remarcação (AG-001 → AG-002) vive no Histórico**, não na agenda;
  agenda mostra só o ativo (o filtro já existe: `agendamento_atual_do_pedido`).
- **Empty state por pergunta**: "nada chegou" ≠ "tudo triado" — o aviso
  confuso de hoje nasceu exatamente de um estado vazio sem explicação.
- Nenhum papel novo: Recepção/Agendamento/Realização são **views do
  `dispensador`** (mesmo princípio que proíbe `dispensador_hospitalar`).

## §4 Cidadão — o selo fica, a agenda nasce

- **Nova aba "Agendamentos"** na carteira: compromissos ativos ordenados por
  data (quando/onde/exame/protocolo). MVP: agregação no front a partir do
  `agendamento` que os cartões já carregam — **sem endpoint novo**.
- **O selo no cartão MANTÉM data/hora** (discordância parcial da consulta
  externa, que o reduziria a "ver compromisso"): fonte única já garante
  coerência (mesmo campo), e a data no cartão é informação de primeira
  necessidade na demo. O selo linka para a aba.
- Simetria futura (registrada, fora do MVP): a máquina permite o `paciente`
  cancelar — quando a aba existir, avaliar o gesto no lado do cidadão.

## §5 Custódia após falta/cancelamento — a regra, dita

Verificado no código: `nao_compareceu`/`cancelado` devolvem o ITEM a
`pendente` e **não tocam na custódia** — que fica com o prestador. **É o
comportamento certo e vira regra escrita:** faltar não devolve posse; a
triagem recomeça NA MESMA unidade (o item reaparece na Recepção dela). Se o
cidadão quiser levar a outro prestador, a unidade devolve por "Não realizamos"
— posse se transfere por ato, nunca por ausência.

## §6 Limitação conhecida: um agendamento ativo POR PEDIDO (§ para o Fabiano)

Existe guarda ("Já existe um agendamento ativo para este pedido"). Com a
custódia parcial, pedido dividido entre duas unidades trava o segundo
agendamento. **Válvula nativa: a coleta direta** (a segunda unidade executa
sem agendar — aresta J.7). MVP aceita a limitação; a mensagem de erro ensina
("itens já agendados neste pedido — execute direto ou remaque o compromisso").
O elo agendamento↔itens (tabela/persistência do escopo) é o caminho para
levantar a limitação — **só quando um caso real pedir** (a mesma disciplina
do elo do laudo: chave quando a ambiguidade bater na porta).

## §7 Entregas

| # | O quê | Classe |
|---|---|---|
| 1 | GET agendamentos aceita dispensador (escopo posse) | `core` (martelo) |
| 2 | Clínica: Recepção com 3 decisões + agenda da unidade + botões móveis | `module` |
| 3 | Cidadão: aba Agendamentos + selo linkado | `module` |
| 4 | Verificar §6 na prática (reproduzir o cenário duas-unidades) | incluído no PR 2 |

---

*Desenho do arquiteto (Z), 23/08. Consulta externa (Kimi) integrada por ponto —
adoções e rejeições registradas nos §§; divergências fundamentadas no código.
Martelos pendentes do Fabiano: o `core` do item 1 e o aceite das adoções novas
(§2 ato composto, §4 aba do cidadão).*
