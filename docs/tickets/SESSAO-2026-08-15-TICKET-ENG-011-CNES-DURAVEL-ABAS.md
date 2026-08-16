# Sessão 2026-08-15 — Engenheiro: ENG-011 — CNES durável (`ops`) + abas J.8/J.9 (`module`)

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator |
| **Despacho** | `DESPACHO-ENG-011-J7-CNES-DURAVEL-ABAS.md` (arquiteto Z) |
| **Base** | `main` em `e19e216` (pós-merge #161) |
| **Branch** | trabalho na árvore, sobre `fix/serie-j-demo-ux` (#162) — **nada commitado**, conforme §9 |
| **Estado** | **CNES durável (`ops`) ✅ · J.8 ✅ · J.9 ✅ · J.7 NÃO INICIADO** (martelo pendente, §2) |
| **Gates** | unit ✅ (zero regressão) · integração ✅ 466 · navegador ✅ 74 |

---

## §1 Resumo em uma frase

Os dois PRs despachados estão feitos e verdes; o micro-ticket do CNES **mudou de
sítio** (boot, não `predeploy.sh`) porque a verificação obrigatória do §5 deu
negativa — e o próprio §5 já nomeava essa saída; o J.7 não foi tocado.

---

## §2 Micro-ticket `ops` — CNES durável

### A verificação obrigatória (§5) — resultado: **NÃO persiste**

O despacho mandou confirmar se o arquivo escrito pelo `preDeployCommand` chega ao
container do serviço. **Não chega.** Três evidências independentes:

| # | Evidência | Fonte |
|---|---|---|
| 1 | *"The pre-deploy command executes on a separate instance from your running service. […] Changes you make to the filesystem are **not** reflected in the deployed service."* | `render.com/docs/deploys` |
| 2 | *"By default, Render services have an ephemeral filesystem. […] without a persistent disk, any changes you make to a service's local files are lost every time the service redeploys or restarts."* · *"You can't access persistent disks during a service's build command or pre-deploy command."* | `render.com/docs/disks` |
| 3 | **Empírica:** o `render.yaml` não declara bloco `disk:`, e o arquivo criado à mão no Shell em 14/08 morreu no redeploy. Se houvesse disco persistente em `/data`, teria sobrevivido — a morte observada *é* a prova de que `/data` é efêmero. | repo + relato de 14/08 |

A evidência 3 fecha a única brecha das duas primeiras: mesmo que o dashboard do
Render tivesse um disco não declarado no blueprint (o `render.yaml` é
manual-sync), o comportamento observado o desmente.

**Conclusão:** o `predeploy.sh` era o sítio errado. Aplicada a alternativa que o
próprio §5 previu — **criar/verificar no boot da aplicação, idempotente**. Não é
discordância do §3: é o ramo condicional que o despacho já autorizava.

### O defeito, com precisão

`cnes_prescritor._get_cnes_conn()` **sempre** abre um SQLite (arquitetura dual).
Na vitrine, `PICSAUDE_DEMO_MODE=true` + `DATABASE_URL` de PostgreSQL produzem
isto:

- `alembic upgrade head` → migra a **PostgreSQL**;
- `seed_demo.py` → abre `get_conn()`, que em PostgreSQL cria o cinturão CNES
  **na PostgreSQL** — onde `_get_cnes_conn()` nunca vai olhar;
- ninguém cria `/data/pix_saude_demo.db` → `FileNotFoundError`.

O selo "baixo" do guia (TICKET-J.4 (c)) deixava de ser a verdade sobre identidade
sintética e virava falha de base ausente. Note que **o pre-deploy não conseguiria
consertar isso nem se quisesse**: o `seed_demo.py` roda lá, e o que ele escreve no
filesystem é descartado. Só o boot alcança.

### O que foi feito

**Novo `backend/app/cnes_demo.py`** (`ops` — não toca tabela clínica, não emite
evento, nunca levanta):

- `DDL_CNES_DEMO` — as 3 tabelas CNES, **fonte única**, agora importada também
  pelo `seed_demo.py` (que antes tinha o seu próprio `CREATE TABLE`).
- `garantir_snapshot_cnes_demo()` — chamada no `_lifespan_bootstrap`.

Três decisões que merecem registro:

1. **No-op quando o banco da aplicação é o próprio SQLite.** Aí o arquivo é do
   alembic/seed; criá-lo antes trocaria o erro claro (*"SQLite DB não
   encontrado"*) por um obscuro (*"no such table: prescricoes"*).

2. **As 2 farmácias do §5 não são declaradas no módulo novo.** Elas já têm dono —
   `seed_demo.DISPENSADOR` / `DISPENSADOR_NORTE`, os mesmos dicts que o
   `test_guardrail_identidades_demo.py` casa contra o `config.js`. O side-car é
   **projeção** do que o seed semeou, não uma segunda declaração. Um teste novo
   proíbe literal de identidade dentro de `cnes_demo.py`.

3. **O espelho lê as colunas que a tabela de origem TEM.** A
   `estabelecimentos_cnes` da vitrine foi criada por uma versão anterior do
   cinturão, **sem `CO_UNIDADE`**, e `CREATE TABLE IF NOT EXISTS` não acrescenta
   coluna a tabela existente. Um `SELECT` fixo estouraria `UndefinedColumn`
   exatamente no ambiente que o ticket conserta. Há teste de regressão para esse
   estado real.

**Achado de brinde (bug dormente corrigido):** o cinturão antigo do `seed_demo.py`
não tinha `CO_UNIDADE` em `estabelecimentos_cnes`, e
`identidade_prescritor._buscar_cnes_por_conselho` faz `LEFT JOIN … ON
e.CO_UNIDADE = r.CO_UNIDADE`. Num banco demo SQLite a query quebrava com *"no such
column: e.CO_UNIDADE"* — e o `except Exception` da produção engolia, devolvendo
`[]`. O DDL unificado inclui a coluna.

**`predeploy.sh`:** ganhou apenas um aviso explicando por que **não** se cria
arquivo ali. Sem isso, o próximo a passar "conserta" no lugar errado.

### AC do §5

| AC | Estado |
|---|---|
| validação CNES responde com base presente (`nao_encontrado` por identidade sintética, não `FileNotFoundError`) | ✅ teste executável — ver §5 |
| log da criação idempotente | ✅ `[cnes-demo] snapshot CNES garantido em … (N estabelecimento(s) espelhado(s))` |
| nada muda em `core` | ✅ |

> **Pendência para o Fabiano:** o efeito só aparece no **próximo redeploy da
> vitrine**. Nada a fazer no Shell desta vez — é isso que "durável" significa.

---

## §3 J.8 (`module`) — 4 abas do laboratório + desambiguante de 403

### As abas

`clinica.html` passou a ter **Recepção · Agendamento · Realização · Bancada**.
UI only: nenhuma rota, estado, evento ou custódia mudou.

| Aba | Conteúdo |
|---|---|
| 📥 Recepção | fila de exames · busca por protocolo · contexto institucional · chave de circulação · detalhes do pedido |
| 📅 Agendamento | criar/ver agendamentos |
| 🧪 Realização | exames ainda não coletados + "Registrar coleta" |
| 🔬 Bancada | material coletado em diante + gatilho, editor e painel do laudo |

**Faixa "pedido em foco"** acima das abas (paciente + protocolo + "← Nova
busca"): sem ela, sair da Recepção seria perder de vista sobre qual pedido as
ações agem.

**Abrir um pedido cai na aba do próximo gesto** — sem coleta feita, Realização;
já coletado, Bancada. Abrir e cair numa aba vazia obrigaria o operador a caçar o
trabalho.

### A instrução do §6 sobre `agendado`, cumprida ao pé da letra

> *"evitar acoplar UI ao estado `agendado` como sinônimo de 'com o laboratório'"*

A partição é por **percurso** — "já foi coletado?" — e não por nome de estado:

```js
const _ETAPAS_POS_COLETA = ['coletado', 'em_analise', 'resultado_disponivel'];
_itensDaAbaRealizacao = tudo que não está em POS_COLETA nem encerrado
```

Realização é definida **por negação**. Se o J.7 tirar a transição para `agendado`
do `transferir-laboratorio`, os itens chegam como `pendente` e **continuam caindo
em Realização, sem retrabalho nesta tela**. Duas guardas estáticas travam isso
(`test_frontend_abas_j8_j9.py`): uma proíbe `agendado` nas listas de partição, a
outra exige que Realização siga sendo o complemento de Bancada.

### Desambiguante 403-posse × 403-sessão (§1)

**12 sítios** da `clinica.html` colapsavam `401 || 403` em `handleUnauthorized()`
— que alerta *"Sessão expirada ou sem permissão"* e desloga. São fatos
diferentes:

```
401 → o TOKEN não vale mais            → renovar sessão (J.3) / relogar
403 → o token vale; o OBJETO não é seu → avisar no lugar certo e seguir
```

Novo `tratarNaoAutorizado(resp, containerFeedbackId)`: 401 segue o caminho antigo;
403 escreve no painel de feedback do próprio gesto, **sessão intacta**. O
`buscarPedido` recebeu tratamento próprio (o painel dele é `#busca-erro`).

Isto **generaliza** o que `carregarAgendamentos` já fazia sozinho para o seu 403
(§D4): o remédio existia num sítio só, e os outros 11 seguiam colapsando.

**Efeito colateral achado ao criar a aba:** `GET
/pedidos-exame/{p}/agendamentos` recusa `dispensador` por desenho, então a aba
Agendamento nascia permanentemente morta. Mas **`POST /agendamentos` aceita
`dispensador`** — ler é vedado, marcar não é. A aba agora explica a lacuna e
mantém o formulário de marcação. Nenhum RBAC mudou; é a mesma API.

### Simplificação que a aba forçou (e que o TICKET-F já pedia)

`atualizarStatusUI` remendava o cartão no lugar, com um bloco que o próprio
TICKET-F anotava como *"espelho exato do ramo 'coletado' de renderizarItens — se
os dois divergirem, a tela mente"*. Com duas listas, coletar **move** o item de
aba, e remendo in-place o deixaria na aba errada. Passou a atualizar o estado em
memória e repintar a partir dele: um sítio só sabe desenhar um item, e os dois
espelhos viraram um.

---

## §4 J.9 (`module`) — 3 abas do cidadão

`cidadao.html`: **Receita · Exames · Atestado**. UI only.

| Aba | Conteúdo |
|---|---|
| 💊 Receita | receitas sob custódia + histórico de prescrições |
| 🧪 Exames | pedidos de exame ativos + laudos/resultados |
| 📄 Atestado | atestados |

- **Pedido e laudo dividem a aba Exames** porque são o mesmo percurso visto em
  dois momentos (solicita → agenda → coleta → laudo).
- **Alertas de renovação ficam FORA das abas** — valem para a carteira inteira.
- **O botão "Atualizar" fica junto das abas**, não dentro de uma: ele chama
  `carregarCarteira()`, que recarrega as três. Pendurá-lo numa aba faria parecer
  que só aquela é atualizada.
- **Contadores mostram o que está vivo** (custódia / pedidos ativos / laudos
  disponíveis / atestados vigentes), não o histórico — é o que diz ao cidadão se
  há algo a fazer sem abrir cada aba.
- **J.3 preservado:** o poll da carteira e o interceptador global de re-login
  seguem intactos; nada foi duplicado. Guarda estática nova cobre isso.

**Correção de estilo de brinde:** a regra era `h2.section-title`, mas os títulos
das seções da carteira sempre foram `h3` — ficavam sem estilo nenhum. Passou a
`.section-title`.

---

## §5 Gates — todos verdes

### Unit — zero regressão, provada por diff

```
antes (git stash, árvore limpa):  52 FAILED
depois (com as mudanças):         52 FAILED
comm -13 antes.txt depois.txt  →  (vazio)
```

As 52 são as pré-existentes conhecidas deste Mac (`test_migration_*`,
`test_string_validacao`, `test_integration.py` batendo no DB de dev
compartilhado). **Nenhuma falha nova; nenhuma sumiu.**

```
1650 passed, 52 failed, 33 skipped
```

### Integração (PostgreSQL 15 efêmero)

```
466 passed in 68s
```

> ⚠️ `tests/integration/test_concorrencia.py` **não coleta** — importa
> `DATABASE_URL_TEST` de `tests/integration/conftest.py`, símbolo que não existe
> lá. Confirmado **pré-existente na `main`** (`git show
> origin/main:…/conftest.py | grep -c DATABASE_URL_TEST` → `0`). Fora do escopo
> deste despacho; **fica registrado como pendência**.

### Navegador

```
74 passed, 8 deselected (external, opt-in) in 155s
```

Inclui `tests/browser/test_abas_j8_j9.py` **novo** — 6 smokes:

| Teste | AC |
|---|---|
| operador circula pelas 4 abas sem perder o pedido | §6 |
| abrir pedido cai na aba do próximo gesto | §6 |
| nova busca devolve à Recepção e avisa as abas vazias | §6 |
| 403 de posse não derruba a sessão | §1 |
| cidadão alcança os 3 tipos de objeto nas abas | §7 |
| Atualizar serve às três abas | §7 |

### Testes existentes que precisaram de adaptação

Reorganizar UI move onde os gestos moram; sete arquivos apontavam para a
disposição antiga. Nenhuma asserção de **comportamento** foi afrouxada:

| Arquivo | Adaptação |
|---|---|
| 5 arquivos de navegador | `#resultado-pedido` → `#pedido-foco`; abrir a aba antes de procurar o card. Helper único `abrir_aba_carteira()` no `conftest.py` — se o seletor mudar, muda num lugar só |
| `test_demo_lab_e2e.py` | após coletar, o exame **muda de aba**: o teste troca de aba porque o trabalho trocou de etapa (e passou a checar o contador) |
| `test_frontend_acao_sem_silencio.py` | `tratarNaoAutorizado(` entra no registro `_FEEDBACK`. O gate mordeu corretamente: função nova, ainda não registrada. Ela **sempre** termina em voz — 401 renova/alerta, 403 escreve no painel |

**Uma asserção foi substituída, e merece o olho do arquiteto** —
`test_f5_etapa_c_cidadao.py::test_c3_atestado_card_tem_hierarquia_visual_propria`
afirmava *"Atestados aparece ANTES de Pedidos de Exame no DOM"* (F5-C3). O
despacho §7 fixa a ordem das abas como **Receita · Exames · Atestado**, então
Atestado é a 3ª — e a asserção passaria a medir posição de aba, não hierarquia de
documento. Troquei o **critério**, não a regra: agora se afirma que o atestado
tem painel próprio e que **nenhum card de exame vaza para ele** — separação mais
forte que a posicional. Se o arquiteto preferir a ordem antiga das abas, é uma
linha no HTML.

---

## §6 J.7 — não iniciado

`core`, martelo do Fabiano pendente (§2 do despacho). **Nenhuma linha tocada** em
`backend/app/routers/pedidos_exame.py` nem em `states_exame.py`.

O J.8 foi construído para não atrapalhá-lo: a partição das abas ignora `agendado`
e há guarda estática travando isso. Quando o J.7 entrar, a tela do laboratório
**não precisa de retrabalho** — os itens simplesmente chegam como `pendente` e
continuam em Realização.

---

## §7 Arquivos

**Novos**

```
backend/app/cnes_demo.py                          ops   — snapshot CNES durável + DDL fonte única
backend/tests/unit/test_cnes_demo_bootstrap.py    ops   — 13 guardas
backend/tests/unit/test_frontend_abas_j8_j9.py    module— 16 guardas estáticas
backend/tests/browser/test_abas_j8_j9.py          module— 6 smokes
```

**Alterados**

```
PR ops:
  backend/app/main.py            (+8)   chamada no _lifespan_bootstrap
  backend/seed_demo.py           (±39)  importa DDL_CNES_DEMO em vez de repetir
  backend/predeploy.sh           (+7)   aviso: não criar arquivo aqui

PR module:
  clinica.html                   (+447/-…)  abas + desambiguante 403
  cidadao.html                   (+137/-…)  abas da carteira
  backend/tests/browser/conftest.py         helper abrir_aba_carteira
  backend/tests/browser/test_{demo_lab_e2e,bancada_clinica,laudo_clinica_cidadao,
    exame_transferencia_cidadao,smokes,f5_etapa_c_cidadao,f5_externo_picsaude}.py
  backend/tests/unit/test_frontend_acao_sem_silencio.py  registro _FEEDBACK
```

Os dois conjuntos são **disjuntos em arquivos** — a separação nos dois PRs do §8
é mecânica.

---

## §8 Nota sobre a base do PR `module`

O §8.2 pede base na `main`. **Recomendo empilhar sobre o #162** (`fix/serie-j-demo-ux`),
não sobre a `main` crua:

- o #162 toca `clinica.html`, `cidadao.html` e `config.js` — exatamente os
  arquivos do J.8/J.9;
- o §7 manda *"manter o re-login transparente do J.3 intacto — o interceptador é
  global, não duplicar"*, e o J.3 **vive no #162**. Basear na `main` sem ele
  significaria reintroduzir ou duplicar aquilo que o despacho proíbe duplicar.

Com o #162 mergeado (parecer do arquiteto: aprovado, aguardando ordem), a base
vira `main` sem nenhum trabalho extra. **É por isso que o trabalho desta sessão
está na árvore sobre `fix/serie-j-demo-ux`.**

---

## §9 Limites respeitados

- **Nada commitado** (§9 do despacho) — tudo na árvore de trabalho.
- **#162 não mergeado.**
- **J.7 não iniciado.**
- Docs não versionados (pareceres, `Fabiano.md`, `planejamento/`) intocados.

## §10 Aguardando ordem

1. Commitar e abrir os dois PRs (ops → main; module → sobre #162, ver §8).
2. Merge do #162 (fora deste despacho; parecer já favorável).
3. Redeploy da vitrine para o CNES durável entrar em vigor.
4. Martelo do J.7.

---

*Relatório do engenheiro, 2026-08-15. Gates completos verdes; zero regressão
provada por diff de conjunto de falhas.*
