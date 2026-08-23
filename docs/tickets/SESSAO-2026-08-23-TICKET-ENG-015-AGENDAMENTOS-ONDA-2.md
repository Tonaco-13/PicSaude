# SESSÃO 2026-08-23 — ENG-015: agendamentos, onda 2

| Campo | Valor |
|---|---|
| **Despacho** | ENG-015 (agendamentos — onda 2), sobre o `DESENHO-AGENDAMENTOS-UX.md` do arquiteto |
| **Martelos** | Fabiano, 23/08 — (i) micro-ticket `core` do GET **aprovado** (implementação liberada; merge sob martelo no PR) · (ii) adoções **aprovadas**: ato composto "Não realizamos" pós-`agendado` (§2) e aba Agendamentos do cidadão (§4) |
| **Ruling** | §3 — escopo da agenda **por CUSTÓDIA** vira o oficial; agenda institucional literal fica como endpoint futuro registrado (arquiteto, 23/08) |
| **Executor** | Engenheiro · versionado sob ordem do Fabiano |
| **Base** | `main` em `e85180b` → **`447f707`** |

---

## §0 Entregue

| PR | Classe | Squash | O quê |
|---|---|---|---|
| **#181** | `core` | `7e88286` | `GET /pedidos-exame/{p}/agendamentos` aceita `dispensador`, escopo de posse |
| **#182** | `module` | `6723eef` | Carteira do cidadão ganha a aba **Agendamentos** (§4) |
| **#183** | `module` | `447f707` | Recepção com **três decisões**, agenda da unidade, ato composto e §6 (§2 · §3 · §6) |

Gates finais na `main`: unit **548** · integração **568** · navegador **103**.

### Igualdade de patch — prova mecânica de cada merge

Regra da casa desde a substituição do #165: o squash não é auditado pela
mensagem, é conferido pelo **hash do patch**. Cada linha abaixo foi recomputada
pelo arquiteto de forma independente.

| PR | Commit auditado | Squash na `main` | `sha256` do patch |
|---|---|---|---|
| #181 | `bc4604c` | `e85180b..7e88286` | `ab49c0d640092e02cbbf6db5336c6b7e0f450df201ef42056fdd2f83beab33d3` |
| #182 | `a286a6c` | `7e88286..6723eef` | `606ea34d207d7b5dcb968bfb83b1b191a6b1a353a183bf5bac29378417ef48ba` |
| #183 | `db07b76` | `6723eef..447f707` | `a5e3751778813ffe19c9861ee3eede707b3ffc7a32dd1e8da42b4f370ea923bd` |

Os três batem byte a byte. Além disso, **os gates locais rodaram sobre a `main`
combinada** depois de #181+#182 (unit 534 · integração 562 · navegador 98):
nenhum dos dois CIs tinha visto o outro, e merge verde de dois PRs não é o
mesmo que merge verde do resultado.

---

## §1 #181 (`core`) — a última assimetria da família do #171

`dispensador` **já estava** no `require_role`. Quem o barrava era o ownership,
em bloco:

```python
else:  # dispensador → 403
    _assert_or_403(False, ..., "Prestador não lista agendamentos por pedido.")
```

O laboratório **marcava** (`POST /agendamentos`), **remarcava** e **registrava
falta** (#171) — e não podia **listar** o que ele mesmo marcou. Mesma família de
acidente do #171: papel esquecido numa decisão de ownership, não decisão
registrada. E a última dela.

O escopo passou a ser **posse**, pelo predicado da fonte única
(`dispensador_tem_algo_no_pedido`, #172). Como o agendamento é do **pedido** —
sem granularidade de item —, não há o que filtrar: ou a unidade é parte, e vê a
agenda, ou não é, e leva 403. *(Nota de desenho endossada pelo arquiteto: por
isso o predicado é o GROSSO, não o fino.)*

### Duas coisas que a execução obrigou a decidir

**O aviso confuso morreu — mas o vazio genérico mentiria.** A tela precisava
explicar que "a lista é do prescritor e do cidadão, não sua" enquanto o mesmo
operador marcava e remarcava. Ao removê-lo, o 403 caía no empty state "Nenhum
agendamento ativo para este pedido" — **falso** quando o que falta é posse. O
403 passou a dizer *"este pedido está sob custódia de outra unidade"*.

> Um vazio sem explicação foi exatamente o que gerou o aviso que este ticket
> matou. Repeti-lo teria sido irônico.

**O teste do J.8 provocava o 403 pelo defeito.**
`test_403_de_posse_nao_derruba_a_sessao` usava o pedido que a **própria clínica
detinha** — era "o 403 mais fácil de provocar na vitrine" **porque era um bug**.
Com o fix, esse caso devolve 200. Reescrito para as duas metades de verdade: a
unidade que detém vê a agenda; e um 403 de posse **real** (buscar pedido já
devolvido) não derruba a sessão.

---

## §2 #182 (`module`) — a aba Agendamentos do cidadão (§4)

Desde o J.11 o cidadão via a data do exame, mas só **dentro** do cartão do
pedido: com três pedidos, descobrir a próxima coleta era abrir os três.

**Agregação no front**, sem endpoint novo — o compromisso vigente já chega em
`pedido.agendamento`. Um `/paciente/agendamentos` seria uma **segunda fonte**
para "qual é o corrente"; uma chamada por cartão seria N+1 **e** a mesma segunda
fonte. Duas fontes divergem em silêncio: a lição que o J.7 cobrou quando a posse
era lida do status.

**O selo mantém data e hora** — decisão do §4 contra a consulta externa, que o
reduziria a "ver compromisso". Ele vira botão e leva à aba; "Ver pedido" traz de
volta, porque aba que mostra protocolo sem porta de retorno é um beco.

### A armadilha que o desenho não nomeava

`agendamento_atual_do_pedido` filtra os terminais **do agendamento**, não os **do
pedido**: um pedido **cancelado** pode carregar um agendamento ainda `criado`.
Anunciá-lo seria marcar o cidadão para uma coleta que não vai acontecer. A lista
sai dos pedidos **ativos** (posse + em_andamento).

---

## §3 #183 (`module`) — recepção, agenda e a mensagem que ensina a válvula

### §2 do desenho — a terceira decisão

O ENG-014 trouxe duas ("Agendar", "Executar agora"): o que fazer quando a
unidade **vai** realizar. Faltava a decisão de quem **não** vai — e é ela que
solta o exame. "Não realizamos" saiu da Realização (demanda do Fabiano) e foi
para a Recepção: recusar não é etapa de execução, é triagem.

**Por item, e não só pelo pedido** — a unidade pode realizar dois exames e não
realizar o terceiro; uma decisão no nível do pedido não saberia dizer isso, e a
devolução granular do J.10 sumiria.

**Ato composto** sobre item `agendado`: cancela a agenda **e** devolve a posse —
dois fatos, dois eventos, nunca UPDATE que funda. Ordem: **cancelar primeiro**
(`devolver` exige `pendente`, e é o cancelamento que devolve o item a
`pendente`). Se a segunda metade falhar, a tela **diz**: o meio do caminho é
"item pendente, ainda com você", que o próprio botão resolve no clique seguinte.

`POST /agendamentos/{p}/cancelar` ganhou `{motivo}` **opcional** — o endpoint já
existia sem corpo e é chamado também pelo paciente e pelo prescritor.

### §3 do desenho — a agenda da unidade

A pergunta "o que está marcado?" só tinha resposta **depois** de abrir um
pedido. Quem chega de manhã para ver o dia não tem protocolo, tem agenda.

**Ruling do arquiteto (23/08), agora oficial:** o escopo é por **CUSTÓDIA**, não
por `org_id`. É o *"ou equivalente"* do §6b, e é o escopo **certo**: a agenda
responde *"o que está marcado para chegar à minha bancada"* — mesmo trabalho da
fila, outra janela. Filtrar por `org_id` mostraria compromissos de pedidos que
**já saíram** da unidade, contradizendo o #181 (ex-custodiante perde a agenda).

> **Registrado como futuro:** a agenda institucional literal — a organização
> inteira, incluindo pré-marcados por prescritores — é endpoint novo, e nasce
> quando um caso real pedir. Mesma disciplina do elo do laudo.

Gestos por compromisso: **Executar** (também em `criado` — a máquina permite
desde o Ticket 29; era só a tela inventando burocracia) · **Confirmar presença**
· **Remarcar** (derivação; a cadeia vive no Histórico) · **Registrar falta** (só
após `data_hora` + 15min, trava de **UX declarada como tal**, com guarda
travando que ela não migre para o domínio) · **Não realizamos**.

### §6 do desenho — a limitação reproduzida, e a mensagem corrigida

A regra permanece. O que mudou é o **conselho**: o texto antigo mandava a
segunda unidade *"cancelar o atual"* — e o compromisso ativo é **da outra
unidade**. Agenda alheia não se cancela.

| Caso | Conselho |
|---|---|
| mesma org | remarque o compromisso existente |
| **outra org** | **execute direto** — a válvula nativa (aresta J.7) |

Reproduzido com duas unidades de verdade; a válvula testada de ponta a ponta:
B coleta direto **sem** derrubar a agenda de A.

---

## §4 Erros meus, e onde cada um foi pego

Nenhum chegou à `main`. Ficam registrados porque o modo como foram pegos é o
que se repete.

**1 · Ids duplicados no DOM (#183).** Ao renderizar o mesmo item `pendente` em
duas listas, dupliquei `id` — HTML inválido, `getElementById` devolvendo o
primeiro, e o código que desabilita "Registrar coleta" mexendo no botão da outra
aba. **Três E2E caíram no gate.** A Recepção ganhou namespace próprio
(`item-recep-exame-N`) e quem age sobre o item passou a agir sobre **todos** os
seus botões via `data-`, cada um recuperando o **seu** rótulo.

**2 · Um teste de ordenação que passava por acidente (#182).** O E2E da aba
Agendamentos nasceu com o cenário invertido: como o backend devolve `id DESC`, a
ordem de chegada já era a esperada, e o teste passava **verde com o `.sort`
arrancado**. Só apareceu porque mutei a ordenação para conferir a mordida.

> Um teste de ordem que aceita a ordem de chegada não testa ordem nenhuma.
> Reconstruído **contra** a ordem natural.

**3 · Guarda que acusaria a própria explicação (#181, #183).** Duas vezes a
guarda estática mordeu o comentário que a justifica — a docstring cita a
mensagem antiga para explicar o que morreu; o caminho de coleta cita
`/agendamentos` para dizer que **não** chama. Guardas passaram a olhar o
**construto** (`_assert_or_403(False`) e a ignorar linhas de comentário.

---

## §5 Registros de método desta onda

**Vazio responde à PERGUNTA; erro responde POR QUE não há resposta.** Apareceu
três vezes: o 403 de posse na agenda da clínica (#181), a carga que falha na aba
do cidadão (#182), o empty state por pergunta na agenda da unidade (#183). Um
vazio genérico é a tela mentindo com cara de resposta certa.

**Teste testa REGRA, não acidente.** Três testes cederam nesta onda, e nos três
o que caiu foi acidente do momento em que foram escritos:

| Teste | Acidente que caiu | Regra que ficou |
|---|---|---|
| `test_403_de_posse_nao_derruba_a_sessao` | o 403 era fácil de provocar **porque era defeito** | 403 de posse não desloga |
| `test_j11_selo_e_lente` (`abas == 3`) | a contagem de abas do momento | a data chega ao cartão **sem** navegação |
| `test_selo_le_o_campo_do_backend` | a **assinatura** literal da função | a **fonte** do dado é `pedido.agendamento` |
| `test_j10_custodia_parcial` | a aba de onde se clica | o item some porque saiu da **custódia** |

**Supersessão escrita, com martelo citado** — o padrão para teste que cede: o
arquivo diz o que mudou, quando, por ordem de quem, e o que **continua** valendo.
Teste que muda sem deixar rastro é regra que se afrouxa em silêncio.

**Guarda de rumo vira contagem de eventos.** A rejeição do "agendamento
instantâneo" não ficou só no documento: `test_executar_agora_e_um_fato_so` conta
os eventos do pedido, e a guarda estática impede qualquer caminho de coleta de
falar com `/agendamentos`. Rejeição registrada só em prosa volta na refatoração
seguinte de quem não estava na conversa.

**Toda guarda nova conferida por MUTAÇÃO**, no arquivo real, além da prova
sintética do molde da casa (`TestAsGuardasMordem`). Guarda que nunca falha
quando deveria é decoração — lição do R2.

**Vermelho antes de verde** em tudo que corrige defeito: 3 dos 6 de integração
do #181, 4 dos 4 de navegador do #182, 4 dos 6 de integração do #183.

**Baseline medida, não estimada.** O ganho do gate de unidade do #182 (526 → 534)
saiu de rodar a suíte com e sem as mudanças (`git stash`), não de contar testes
no diff.

---

## §6 Estado ao fechar

- **Fila vazia.** Nenhum PR aberto; a onda ENG-015 fechou com os três merges.
- **Pendências herdadas:** nenhuma desta onda.
- **Registrado como futuro:** a agenda institucional literal (§3) — endpoint
  novo, quando um caso real pedir.
- **Restante do repositório:** go-public (GP-1..GP-4), sob gatilho do Fabiano.

---

*Relatório do Engenheiro, 23/08. Desenho do arquiteto (Z) versionado junto neste
PR. Martelos do Fabiano de 23/08 registrados no cabeçalho; ruling do §3 no §3.*
