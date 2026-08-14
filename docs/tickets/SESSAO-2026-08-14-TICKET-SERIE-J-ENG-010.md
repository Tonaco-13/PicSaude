# Sessão 2026-08-14 — Engenheiro: série J (ENG-010) — correções da excursão + login invisível

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator |
| **Despacho** | `DESPACHO-ENG-010-SERIE-J-EXCURSAO-VITRINE.md` (arquiteto Z) |
| **Base** | `main` em `c85442f` |
| **Branch** | `main` (trabalho na árvore) — **nada commitado**, conforme §6 do despacho |
| **Estado** | J.1 · J.2 · J.3 · J.5 · J.6.b **implementados e verdes**. **J.4 PARADO** — discordância técnica, §7 |

---

## §1 Resumo em uma frase

Cinco dos seis tickets estão feitos com gates completos verdes; o **J.4 foi
interrompido antes de qualquer alteração de código**, porque o critério de aceite
dele não é alcançável pela correção proposta — e a regra do Fabiano manda parar e
devolver, não improvisar.

---

## §2 J.2 (`core`) — hash do documento canônico × caixa do nome

### O que estava errado

A emissão hasheia `normalize_nome(payload.nome_paciente)` (MAIÚSCULAS) mas **não
reescreve** `pacientes.nome`: resolve por CPF e reaproveita a linha existente. Um
paciente semeado como `"João Demo da Silva"` fazia a reconstrução ler Title Case,
e o hash **nunca** casava.

### Achado que o despacho não previa: eram DOIS sítios, não um

O despacho apontava `documento_canonico.py::montar_documento_de_conn`. Corrigi-lo
deixou 3 dos 4 testes verdes — o de `/validacao` continuou vermelho.
`validacao_documental.py:395` **reconstrói o canônico por conta própria**, sem
passar pelo helper. E é justamente a superfície que o cidadão/auditor vê: era ali
que a demo acusava o próprio sistema de adulteração.

Os dois normalizam agora, com comentário cruzado — se divergirem, `/documento` e
`/validacao` passam a discordar sobre o mesmo documento.

### Por que isto não afrouxa a verificação

`normalize_nome` é `upper()` + colapso de espaços, e é **idempotente** — hashes de
documentos cujo nome já estava em maiúsculas não mudam. A caixa do nome **nunca**
fez parte do que o hash promete (a emissão já a descartava); trocar o nome por
**outro** segue quebrando o hash, que é o que a verificação existe para detectar.
Um teste trava que o acento é preservado: perdê-lo mudaria o hash de todo o
histórico.

### Round-trip análogo (o despacho pediu para verificar)

**Exame, laudo e atestado são imunes**: os três hasheiam `paciente_cpf` e **não o
nome** (`_calcular_hash` em cada router). E só `prescricoes` tem reconstrução a
partir do banco. O defeito era exclusivo da receita.

### Por que o gate não via

`conftest` de integração semeia `SEED_PACIENTE_NOME = "PACIENTE TESTE TICKET13"` —
**já em maiúsculas**. Nesse dado `normalize_nome` é no-op e o hash casa por
acidente. O `seed_demo.py` usa Title Case. O bug só existia onde o dado tinha
caixa mista, e **nenhum teste tinha dado assim** — por isso os novos criam o
paciente em Title Case de propósito.

**Provas:** `tests/integration/test_documento_canonico_integridade.py` (4 casos —
nome no arquivo casa com `integridade` no `-k`). Vermelho antes, verde depois.

---

## §3 J.1 (`core`) — `resultado_disponivel` inalcançável

### A correção

`derivar_status_pedido`: quando **todos** os itens estão em estado terminal e ao
menos um é `resultado_disponivel`, o pedido **repousa** em `resultado_disponivel`.
`encerrado` passa a ser exclusivamente resultado do ato de ciência (`/encerrar`).

Removi também a variável `ativos`, que era calculada e nunca lida — restava do
desenho anterior e confundia a leitura.

> Derivar "encerrado" de "o laboratório terminou" confundia **produzir o
> resultado** com **o cidadão tomar ciência dele**. São dois fatos, e o segundo é
> o que fecha o ciclo.

### Ajuste-companheiro necessário (fora da letra do despacho)

`dispensadores.py::_ESTADOS_PEDIDO_FIM_FILA` recebeu `resultado_disponivel`.

Sem isso o pedido ficaria **preso na fila do laboratório para sempre**, sem nenhum
item acionável: antes ele saía por virar `encerrado`, e esse caminho deixou de
existir. Não afrouxa nada — `resultado_disponivel` no pedido só é derivado quando
nenhum item está fora de terminal, ou seja, **não há trabalho de bancada
pendente**. O nome da constante é "fim da fila", não "estado terminal".

### Efeito colateral positivo, verificado

A carteira do cidadão (`auth.py`) já classificava `resultado_disponivel` como
**em andamento**. Antes, o pedido pulava direto para o histórico e escondia o
resultado que acabara de sair. Agora fica em "em andamento" até a ciência — travado
em teste.

### Um caso que decidi NÃO mexer

`derivar_status_pedido([])` devolve `encerrado` por vacuidade do `all()`.
Verifiquei com `git stash` que é **comportamento anterior ao J.1**, e a emissão
recusa pedido sem item (422). Alterar seria alargar um ticket `core` por um caso
que não ocorre. Ficou travado em teste para que, se alguém mudar, seja decisão.

**Provas:** `tests/unit/test_states_exame_derivacao.py` (17 casos, domínio puro —
inclui guarda contra reincidência: *todo estado em `_PRIORIDADE_ESTADO` tem de ser
derivável por alguma combinação*) + `tests/integration/test_pedidos_exame_encerramento.py`
(5 casos: o AC ponta a ponta, incluindo o **422 circular** morto).

---

## §4 J.5 (`core`) — `pedido_coletado` no ledger do pedido

`/agendamentos/{proto}/realizar` passa a emitir `pedido_coletado` **por item**, no
ledger do pedido, na mesma transação. O `instance_id` é obtido **antes** do laço e
compartilhado com o `agendamento_realizado` — invariante forense do 4D.2: um ato,
um identificador. Travado em teste.

O payload registra `via: "agendamento"` e o protocolo do agendamento. Coleta no
balcão e coleta por agendamento são o mesmo fato com origens diferentes, e a
auditoria tem direito de distinguir — a via do balcão segue sem o campo, e há
teste de regressão para isso.

Incluí o `registrar_outbox` do mesmo evento, espelhando a via do balcão: o mesmo
tipo de evento não pode se comportar diferente na camada de publicação conforme o
caminho que o gerou. Não há risco de duplicidade — um item só percorre uma das
duas vias (a outra recusa por estado).

**Provas:** `tests/integration/test_pedidos_exame_coleta_via_agendamento.py` (4
casos, incluindo "sem item agendado → nenhum evento órfão": ledger é imutável,
evento emitido por engano não se apaga).

---

## §5 J.3 (`module`) — login invisível na demo

### Onde interceptar — a decisão de desenho

São **91 chamadas de `fetch`** nos 4 módulos. "Interceptador único" só existe de
verdade num ponto que todas atravessam, então envolvi `window.fetch` em
`config.js` — arquivo que os 4 já carregam. Isso evita 91 pontos de edição e, mais
importante, evita que o próximo `fetch` escrito amanhã nasça desprotegido.

Comportamento: 401 → `POST /demo/login` com o papel do módulo → grava
sessionStorage → **reemite o request com o header trocado**. Detalhes que não
podiam faltar:

| Cuidado | Por quê |
|---|---|
| Mutex de renovação | Dez requests que expiram juntos disparariam dez logins e o último venceria a corrida |
| Nunca intercepta `/demo/login` | 401 ali é falha real; recursão seria laço infinito |
| Uma tentativa por request | A rede de segurança não pode virar armadilha — travado em teste com `/demo/login` mockado em 500 |
| Troca o header `Authorization` | O `init` original carrega o token expirado; sem trocar, o retry repetiria o 401 |
| Só instala com `demo_mode` | Fora da demo, nada muda |

`handleUnauthorized` (clínica) e `sair()` (cidadão) renovam em vez de exibir a
tela de acesso: em demo **não existe "ficar deslogado"** — era o atrito que o
Fabiano pediu para remover.

**JWT e RBAC intocados.** Nenhuma linha de `auth/` ou `require_role` foi alterada,
como o despacho exige.

**Provas:** `tests/browser/test_relogin_demo.py` (5 casos). A expiração é simulada
adulterando o token no `sessionStorage` — esperar 15 min reais no gate seria
absurdo, e mexer no TTL mudaria o objeto sob teste. Um dos casos confere que o
interceptador está instalado **nos quatro** módulos: sem ele, o módulo faltante só
apareceria na apresentação.

---

## §6 J.6.b (`module`) — mensagem do token distingue o objeto

Colar o protocolo de um atestado no gerador de token devolvia *"Prescrição não
encontrada"* — mensagem que diz **sumiu** quando o objeto existe e apenas não usa
esse mecanismo.

Agora a resposta nomeia o tipo (atestado / pedido de exame / laudo) e explica para
que o token serve. **Com anti-vazamento:** o tipo só é revelado se o objeto for do
**próprio paciente autenticado**; para protocolo alheio ou inexistente a resposta
segue genérica. Sem essa metade, a mensagem "melhor" viraria oráculo — bastaria
varrer protocolos para mapear o que existe e de que natureza é.

**Provas:** `tests/integration/test_tokens_apresentacao_autorizacao.py` (4 casos).
O nome em `_autorizacao` é honesto e proposital: o critério travado é de
autorização, não de redação — e é o que faz a suíte casar com o `-k`.

**Parte do guia (`assinado: false`)** não foi escrita: é conteúdo de documentação
da demo, e prefiro confirmar com o arquiteto **onde** ele quer (guia da vitrine ×
`ROTEIRO_DEMO_LABORATORIO.md`) antes de escrever no lugar errado.

---

## §7 ⛔ J.4 (`ops`) — PARADO. Discordância técnica, conforme §3 do despacho

**Nenhuma linha de código foi alterada para o J.4.**

### O diagnóstico do arquiteto está certo — e eu localizei a raiz exata

O `Dockerfile` faz `COPY backend/ .` para `/app`, então `config.py` vive em
`/app/app/config.py`. O default é:

```python
PIX_SAUDE_DEMO_DB = os.getenv(
    "PIX_SAUDE_DEMO_DB",
    os.path.join(os.path.dirname(__file__), "../../data/pix_saude_demo.db"),
)
```

→ literalmente `/app/app/../../data/pix_saude_demo.db`, que é **exatamente** a
string do erro da excursão. E o `Dockerfile` **não define `ENV PIX_SAUDE_DEMO_DB`**
(define só `PIX_SAUDE_DB=/data/picsaude.db`), então o default se aplica. Ele
normaliza para `/data/pix_saude_demo.db` — fora de `/app`.

### Onde eu discordo

O AC do J.4 é: *"operação na vitrine exibe verificação CNES OK (**score alto**)"*.

**Esse AC não é alcançável corrigindo o path**, e a evidência está no próprio
`seed_demo.py` (linhas ~705-725), comentário verbatim:

> `# Tabelas de validação do prescritor (vazias): garantem que a consulta`
> `# CNES (cnes_prescritor.py) rode e retorne 'nao_encontrado' em vez de`
> `# falhar por tabela ausente.`

`profissionais_cnes` e `relacao_prof_estab` são criadas **vazias, por desenho**. E
o `_get_cnes_conn` documenta o mesmo:

> *"em demo, abre o DB demo (sem tabelas CNES → toda validação retorna
> `nao_encontrado`, aceitável porque persona demo usa CNS sintético e a validação
> CNES é não-bloqueante)"*

Somando: o CNS da persona demo (`980001112223334`) é **sintético** — não existe no
CNES real. Corrigir o path troca `FileNotFoundError` por `nao_encontrado`. **O
score continua baixo**, porque não há — nem pode haver — profissional real por
trás da persona.

### As três saídas, e por que não escolho sozinho

| Opção | O que dá | Custo |
|---|---|---|
| **a) Só corrigir o path** | Erro some do log; score segue "baixo". AC não cumprido, mas a vitrine para de exibir falha de arquivo | Env var no Render: `PIX_SAUDE_DEMO_DB=/app/data/pix_saude_demo.db` (ou onde o arquivo estiver). Zero código |
| **b) Popular CNES no demo** | Score alto de verdade | Importar CNES no banco demo **e** trocar a persona por um CNS real — muda identidade da demo, que tem fonte única e guard-rail |
| **c) Aceitar "baixo" como correto** | Honesto: a demo usa profissional sintético, e o score baixo **está dizendo a verdade** | Zero. Ajustar o AC e explicar no guia |

Minha leitura: **(c) é a resposta certa, com (a) junto** — o score baixo não é
defeito, é o sistema informando corretamente que não conseguiu validar um CNS que
não existe. Forçar "score alto" numa demo com identidade sintética seria fazer o
indicador **mentir** — e o indicador de confiança é justamente o que não pode
mentir.

Mas isso muda o AC de um ticket martelado, então **paro aqui e devolvo**.

### O que preciso do arquiteto

1. Escolher entre (a)/(b)/(c) — ou corrigir minha leitura.
2. Se (a) ou (c): confirmo que **não tenho acesso ao Render** para alterar env.
   Digo exatamente o que setar; a mão é do Fabiano.
3. A **vigilância do 401 de assinatura** (§2.7 do parecer) também depende de log do
   deploy, fora do meu alcance. Registro o que verificar: se
   `PICSAUDE_JWT_SECRET` é gerado por boot, todo restart invalida tokens vivos — o
   que explicaria o 401 isolado com token fresco. O `Dockerfile` não o define.

---

## §8 J.6.a — depende de deploy

`PICSAUDE_DEMO_ADMIN` existe e funciona (`config.py:67`, consumido em
`demo.py:103` para expor a persona admin). O `Dockerfile` **não a define**. É
`ENV PICSAUDE_DEMO_ADMIN=true` no Render — **zero código**, e fora do meu alcance.

---

## §9 Gates

| Gate | Resultado |
|---|---|
| Integração — seleção `-k` da CI | **368 passed** |
| Integração — suíte **completa** | **466 passed** |
| `tests/unit` | **436 passed** |
| `tests/browser` | **68 passed** |

Rodei a integração **inteira**, não só o `-k`: mudanças em `states_exame.py`,
`documento_canonico.py` e `agendamentos.py` alcançam suítes fora do filtro, e o
filtro é economia, não garantia.

### Arquivos

| Arquivo | Ticket |
|---|---|
| `backend/app/domain/documento_canonico.py` · `backend/app/domain/validacao_documental.py` | J.2 |
| `backend/app/domain/states_exame.py` · `backend/app/routers/dispensadores.py` | J.1 |
| `backend/app/routers/agendamentos.py` | J.5 |
| `config.js` · `prescritor.html` · `dispensador.html` · `clinica.html` · `cidadao.html` | J.3 |
| `backend/app/routers/tokens.py` | J.6.b |
| 5 suítes novas (4 integração + 1 unit + 1 browser) | regressão dos ACs |

---

## §10 Estado e próximos passos

- **Nada commitado** (§6 do despacho). Os PRs 1 e 2 aguardam sua ordem.
- Quando vier: **PR 1** (`fix/serie-j-core`) = J.1 + J.2 + J.5 + as 3 suítes de
  regressão. **PR 2** (`fix/serie-j-demo-ux`, base no PR 1) = J.3 + J.6.b + as 2
  suítes.
- **J.4 bloqueado** aguardando decisão do §7. Não bloqueia os PRs — é `ops` de
  deploy, ortogonal ao código.
- Pendência menor: onde escrever a parte do guia do `assinado: false` (§6).

---

*Registro emitido pelo Engenheiro em 2026-08-14. Cinco tickets entregues com
gates completos verdes; J.4 devolvido ao arquiteto sob a regra do §3 — discordância
técnica com evidência, sem alteração de código.*
