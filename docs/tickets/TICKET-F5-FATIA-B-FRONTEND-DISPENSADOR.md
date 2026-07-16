# TICKET-F5-FATIA-B — Frontend do dispensador (paridade v27): relatórios, ciclo pós-dispensação, estorno visível

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — segunda fatia (frontend), sequência da Fatia A (PR #88) |
| **Classe** | `module` (frontend do módulo dispensação) **+ dois enxertos `module` de backend** — ver §2 e §5.A |
| **Para** | Z AI (parecer) → code/MS (engenheiro) |
| **Origem** | Handoff arquiteto 2026-07-10 (mission #1–#3) · spec UX `dispensador.txt` · TICKET-F5-RELATORIO-SNGPC §4 (stub da Fatia B) |
| **Pré-requisito (GATE DURO)** | (a) **#88 mergeado** — diagnóstico ponta-a-ponta **concluído (2026-07-11): não era bug**; backend da Fatia A comprovado ao vivo (§5.1–5.9 verdes, isolamento por CNPJ, saldo reposto). A "falha" do teste manual = ausência do botão (Fatia B) + roteiro que consumiu a receita inteira (terminal). Merge autorizado pelo Fabiano — gate = comando ao engenheiro, sem diagnóstico pendente. (b) decisão do §2 (B0) ratificada pelo Fabiano após parecer Z AI. |
| **Parecer Z AI** | pendente |

---

## §0 Decisões de produto ratificadas (Fabiano, 2026-07-11)

1. **Duas farmácias com roteiro pedagógico.** A demo prova isolamento por CNPJ (Central vs Norte).
   **B1 NÃO precisa de seletor de troca de farmácia** — verificado: o login é `POST /auth/token` com
   CNPJ+senha ([dispensador.html:910-918]), então trocar de farmácia = **re-logar com o outro CNPJ**.
   O **roteiro escrito** (`ROTEIRO-DEMO-V27.md`) conduz o visitante a logar como Norte para ver o
   relatório vazio. Seletor de troca embutido na UI = **polish P2**, fora desta fatia.
2. **Pull de 15s é suficiente.** Push/WebSocket **sai** da lista de dívidas da demo → **P2 permanente**.
   Nenhum trabalho de push nesta fatia.
3. **Devolução integral sem baixa + re-apresentação fracionada A→B: CORTADAS** desta fatia → **P1
   backlog, sem data**. A circulação fluída da demo não depende delas. (A remoção do resíduo de
   devolução **ao prescritor** — §4.3 — permanece; é limpeza, não a devolução ao paciente.)

## §1 Contexto (não reabrir)

A Fatia A (backend do relatório SNGPC do dispensador — `GET /dispensadores/relatorio.{csv,pdf}`,
travado ao CNPJ do JWT, escrituração por movimento, `saldo_escriturado_item` com corte
temporal) está no PR #88, gate verde, revisão do arquiteto aprovada. **Porém o teste manual
do Fabiano falhou em ponto ainda não diagnosticado** — há missão de diagnóstico pendente com
o engenheiro. Esta fatia (frontend) **não pode ser despachada** antes de #88 verde.

O que **já existe** no `dispensador.html` (não reconstruir — reaproveitar):
- Histórico de retenções (`GET /dispensadores/historico`) renderizado em `#historico-lista`,
  já com **uma linha por medicamento dispensado**, botão **📄 Comprovante** e botão **⏪ Estorno**,
  este último trocado por badge "Estornado" quando `i.estornado === true` — **estado vindo do
  backend** (`dispensadores.py:253`), exatamente como a mission #2 pede.
- Modal de comprovante COMPRADOR × PACIENTE (`verComprovante` / `_renderComprovante`).
- `estornarDispensacao(id)` chamando `POST /dispensacoes/{id}/estornar`, com repô-saldo visível.

Ou seja: **a mission #2 já está ~80% implementada**. Esta fatia é, em grande parte, (a) adicionar
os botões de relatório, (b) fazer a receita **sair da fila** ao esgotar as ações, (c) **remover**
o resíduo de devolução ao prescritor, e (d) tornar o **estorno inequívoco no comprovante** — o
único item que exige backend novo.

---

## §2 ACHADO ARQUITETURAL BLOQUEANTE (B0) — "item volta a ser dispensável" NÃO é entregue hoje

> **Este é o item mais importante do ticket. Ele precisa de decisão do Fabiano + parecer Z AI
> antes de a Fatia B ter sentido, porque a mission #2/#3 depende dele.**

A mission #2/#3 e o CLAUDE.md §4 afirmam: *estorno repõe o saldo e o item volta a ser dispensável*.
Isso é **verdadeiro para dispensação PARCIAL** (item permanece `em_custodia`) — o estorno repõe
o saldo e o item segue dispensável. **É FALSO para dispensação TOTAL**, pelo código atual:

1. Ao dispensar o saldo inteiro, `custodia.py:787` grava `status_item = 'dispensado'` (terminal) e
   `:796` **fecha a custódia** do item.
2. O estorno (`dispensacoes.py:514-515`) — por design do TICKET-ESTORNO-OBJETO-DERIVADO — **não muta
   o item**: `status_item` permanece `'dispensado'` e a custódia permanece fechada. Só o **número**
   do saldo efetivo é reposto (Σ dispensado − Σ estornado).
3. Uma nova tentativa de dispensar bate no guard `custodia.py:737-743`:
   `_BLOQUEADOS_DISPENSAR = {'dispensado', ...}` → **409 "Item com status 'dispensado' não pode ser
   dispensado"**, mesmo com saldo efetivo > 0.

**Resultado:** após estornar uma dispensação total, o saldo aparece reposto, mas o item **não pode
ser re-dispensado** e **não reaparece na fila** (custódia fechada + status terminal). A promessa
"item volta a ser dispensável" fica quebrada exatamente no caminho que o balcão mais usa (dispensou,
errou, estornou, quer dispensar de novo).

### Tensão de invariante

O invariante ratificado é: *o estorno não muta a **dispensação** e não cria a transição de item
`dispensado→estornado`* (CLAUDE.md §2 / TICKET-ESTORNO). Ele **não** proíbe que a **fonte de verdade
da dispensabilidade** seja o **saldo efetivo**, não o rótulo `status_item`. Hoje o guard usa o rótulo
terminal; o correto é ele refletir o saldo.

### Opções (recomendação para o parecer Z AI + martelo Fabiano)

- **Opção A (recomendada) — guard por saldo, não por rótulo.** O guard de re-dispensação passa a
  permitir quando `saldo_efetivo > 0`, mesmo que `status_item='dispensado'`; e a fila/custódia
  volta a expor o item quando o saldo é reposto. Não cria transição `dispensado→estornado` (respeita
  o invariante); trata `status_item='dispensado'` como "sem saldo no momento", derivado. Exige reabrir
  a custódia do item no estorno **ou** afrouxar a query da fila para saldo>0. **É backend `module`
  (toca guard de dispensação + custódia/fila) — não é `core` de máquina de estados** se não criarmos
  estado novo.
- **Opção B — reverter rótulo no estorno.** No estorno, se o item estava `'dispensado'` e o saldo
  volta a >0, transicionar `dispensado→em_custodia` e reabrir custódia. Mais simples de exibir, mas
  **muta o item** — precisa ser explicitamente ratificado como transição legítima (o saldo mudou de
  fato), senão colide com a leitura literal de "estorno não muta item".
- **Opção C — não suportar re-dispensação após estorno total** (só estorno parcial repõe). Rebaixa a
  mission #3 ("item volta a ser dispensável") a "somente parcial". **Não recomendada** — contradiz o
  target v27 e o CLAUDE.md §4.

**Recomendação convergente dos dois arquitetos (sem pré-decidir): Opção A.** Cowork (arquiteto
anterior) e este arquiteto chegam à mesma conclusão de forma independente: a dispensabilidade deve
ser **derivada do saldo efetivo**; o rótulo `status_item='dispensado'` permanece como **registro
histórico**, não como fonte de verdade da ação. Alinha ao padrão CLAUDE.md §10 ("estados computados
não persistidos") e é o **caso concreto** da tese R1–R4 do §2a (verdade deriva do ledger, nunca do
rótulo/projeção editável). **O martelo é do Fabiano após o parecer do Z AI** — o §2 vai ao Z AI
**aberto** (A/B/C). **Parecer Z AI (2026-07-11): Opção A, verde**, com a condição de que a **regra de
fila** seja explícita (fila expõe `acionavel` derivado do saldo; custódia reabre no estorno total).
Detalhamento no **ticket próprio `TICKET-B0-DISPENSABILIDADE-POR-SALDO.md`** — pré-requisito da
fila/estorno da Fatia B.

> **Nota de escopo + corroboração:** B0 é distinto da missão de diagnóstico do #88 (que era sobre o
> **relatório** Fatia A e foi encerrada — não era bug). **Porém o próprio diagnóstico tropeçou no
> cenário do B0 sem nomeá-lo:** a receita virou terminal e "não havia mais o que dispensar". Isso
> **corrobora** o achado — o caminho dispensar-tudo→estornar→re-dispensar existe na prática e hoje
> bate no 409.

---

## §3 Fatia B1 — Botões de relatório no cabeçalho da fila (frontend puro, consome Fatia A)

**Onde:** `dispensador.html`, `.fila-card-head` da `#fila-container` (linha ~418), ao lado do
`↻ Atualizar`. Dois botões, na posição do `dispensador.txt`:

- **🖨️ Relatório Consolidado** — view de impressão.
- **SNGPC (CSV/PDF)** — exportação.

### Contrato (endpoints reais da Fatia A)

```
GET /dispensadores/relatorio.csv?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
GET /dispensadores/relatorio.pdf?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
Auth: JWT role=dispensador (Authorization: Bearer …). Escopo = CNPJ do JWT. Default: últimos 30 dias.
```

### Requisitos

1. **Sempre `fetch` com `authHeaders()` → `blob` → download** (`_baixarBlob`, já existe). **NUNCA**
   montar `<a href>` com a URL do endpoint — expor relatório com PII sem cabeçalho de auth é proibido
   (LEARNINGS PII-EXAUSTIVIDADE; a rota exige Bearer). Nome do arquivo:
   `dispensacoes_sngpc_${data_fim}.csv` / `.pdf`.
2. **Relatório Consolidado (impressão):** view no padrão `#print-area` + `@media print` do v27,
   alimentada pelo **mesmo endpoint** — o engenheiro decide entre (a) formato JSON opcional do mesmo
   endpoint ou (b) parse do CSV já baixado; **sem segunda query divergente** (repete a régua da Fatia A §4).
3. **Seletor de período** data_inicio/data_fim, default 30 dias (inputs simples ou modal; reusar o
   padrão de data `_fmtDataInput` já presente).
4. **Erros do backend legíveis** — `detail.mensagem` (nunca `[object Object]`, nunca tela branca).
   401/403 → `tratarSessaoExpirada()`.
5. **Aviso de truncamento visível** quando o PDF vier truncado em 1000 registros (critério §5.8 da
   Fatia A) — a UI deve exibir/repassar o aviso, nunca truncamento silencioso.

---

## §4 Fatia B2 — Ciclo pós-dispensação na UI + remoção do resíduo "devolução ao prescritor"

### 4.1 Receita sai da fila → fica no histórico

**Decisão de produto (Fabiano):** após dispensar, a receita **sai da fila** e permanece no
**histórico** (que já existe e já traz Comprovante + Estorno por medicamento).

**Como (critério do backend, nunca local — nota B2 do Z AI incorporada):** a receita **não é
renderizada na fila** quando **nenhum** item seu é acionável. "Acionável" **não** é calculado no
cliente: cada item da fila expõe o booleano **`i.acionavel`**, computado no backend por B0 §3.3
(`acionavel = saldo_efetivo > 0 AND status_item NOT IN _BLOQUEADOS_HARD`). O front renderiza a receita
sse `p.itens.some(i => i.acionavel)`. **Não usar `_FILA_TERMINAIS` para decidir acionabilidade** — com
o B0, um item `status_item='dispensado'` com saldo reposto por estorno é **acionável**, e o rótulo
terminal daria o resultado errado. `_FILA_TERMINAIS`/`saldo` seguem só para **exibir badge/saldo** nos
itens não-acionáveis que ainda apareçam na receita. Hoje a fila mantém itens terminais com badge
(`_renderizarFila`, 1242-1244); a mudança é **ocultar a receita inteira** quando `!some(acionavel)`.

> **Dependência dura de B0:** o campo `i.acionavel` e a reentrada na fila vêm do TICKET-B0. Sem B0
> mergeado, este critério não tem a fonte de verdade — B0 é pré-requisito de B2.

**Reentrada por estorno (depende de B0):** quando um estorno repõe o saldo e **B0** torna o item
dispensável de novo, `GET /dispensadores/fila` volta a trazê-lo com `saldo>0` e status não-terminal
→ a receita **reaparece** na fila automaticamente (o front só re-renderiza). **Sem B0 (ou com Opção
C), a receita estornada-total NÃO reaparece na fila** — permanece só no histórico, de onde o estorno
foi disparado. O comportamento correto aqui é **consequência de B0**, não código de front adicional.

> ⚠️ **Amarração explícita:** a §4.1 só entrega "estornou → dá pra dispensar de novo no balcão" se
> B0 = Opção A ou B. O engenheiro **não deve** simular reentrada no front (violaria "estado vindo do
> backend"). Se B0 = C, ajustar o texto de sucesso do estorno para não prometer reentrada na fila.

### 4.2 Estado do botão Estorno — do backend, nunca local (já conforme)

O botão ⏪ Estorno no histórico já só aparece quando `!i.estornado`; senão vira badge "Estornado"
(`_renderHistorico`, 1509-1511), com `i.estornado` vindo de `dispensadores.py:253`
(`q_est > 0 and q_est >= q_disp`). **Manter.** Não recalcular "já estornado" no cliente.

### 4.3 Remover o resíduo de devolução ao prescritor (despacho já dado)

Endpoint de backend `dispensador→prescritor` **permanece**; badges de estado `devolvido_prescritor`
**permanecem** (`_filaStatusInfo`, `statusBadge`). Remover **apenas a UI de ação**:

- **Fila:** botão `✕ Prescritor` e a função `_devolverPrescritorFila` (linhas ~1249 e ~1365-1368).
- **Outra tela (painel por prescrição):** botão `✕ Dev. ao Prescritor`, `toggleMotivoPrescritor`
  (~1675, ~1702) e `devolverItemPrescritor` (~1934) — remover o botão e o bloco de motivo. Se
  `_devolverFila(proto, item, 'prescritor', …)` ficar sem chamador após a remoção, retirar o ramo
  `'prescritor'` ou deixar comentado com referência a este ticket (decisão do engenheiro; sem código
  morto silencioso).

**Grep de confirmação (obrigatório, método code/MS passo 5):** após remover, `grep -n
"devolverPrescritor\|toggleMotivoPrescritor\|devolverItemPrescritor\|✕ Prescritor\|Dev. ao Prescritor"
dispensador.html` deve retornar **zero** ocorrências de **ação** (badges de estado podem citar
"prescritor" — não confundir).

---

## §5 Fatia B3 — Estorno inequívoco no comprovante (backend novo + frontend)

Mission #3: o comprovante de uma dispensação estornada deve exibir de forma **inequívoca** que foi
**ESTORNADO**, com referência ao `estorno_protocolo`; **nunca some, nunca é editado**. Hoje o
comprovante **não expõe** nada de estorno (`_montar_json`, `dispensacoes.py:89-146`). Logo, **backend
antes de frontend**.

### 5.A Enxerto de backend (`module`) — comprovante expõe estorno (read-only)

`GET /dispensacoes/{id}/comprovante` (JSON **e** PDF) passa a incluir o estado de estorno da
dispensação, **sem alterar nada** (read-only sobre `estornos`):

```jsonc
"estorno": {
  "estornado": true,                 // tem algum estorno (Σ estornada > 0)
  "estorno_total": false,            // Σ estornada >= quantidade_dispensada
  "quantidade_estornada": 2,         // Σ quantidade_estornada WHERE origem_dispensacao_id = {id}
  "quantidade_restante": 1,          // quantidade_dispensada − Σ estornada
  "estornos": [                      // uma entrada por objeto-estorno (ledger imutável)
    { "protocolo": "…uuid…", "quantidade": 2, "motivo": "erro_dispensacao", "data": "…" }
  ]
}
```

- **Semântica binária vs. parcial (nota 1 do Z AI — incorporada):** `estornado` é "tem algum estorno";
  `estorno_total` distingue estorno **total** de **parcial**; `quantidade_restante` é derivada **no
  backend**. A UI **nunca** infere "parcial" comparando quantidades no cliente (violaria "estado do
  backend").
- Fonte: `SELECT … FROM estornos WHERE origem_dispensacao_id = ? ORDER BY id` (determinismo, desempate
  por `id` — régua Jules).
- **Nunca** edita a dispensação nem apaga linha (CLAUDE.md §2). O comprovante é o mesmo objeto; ganha
  uma seção derivada.
- **PDF:** carimbo visível ("DISPENSAÇÃO ESTORNADA — ref. estorno {protocolo}") no comprovante da
  dispensação estornada.
- **PII:** nenhuma PII nova (protocolo, quantidade, motivo enum, data). A `[PII-EXAUSTIVIDADE]` da §6
  cobre; auth inalterada (dispensador por CNPJ; admin bypassa).

### 5.B Frontend — marcação no modal de comprovante

`_renderComprovante` passa a exibir, quando `c.estorno?.estornado`, um **banner/carimbo inequívoco** no
topo do modal, acima dos blocos COMPRADOR/PACIENTE, em estilo destacado (ex.: faixa vermelha):
- `estorno_total === true` → **"⏪ DISPENSAÇÃO ESTORNADA"** + `estorno_protocolo`.
- `estorno_total === false` → **"⏪ DISPENSAÇÃO PARCIALMENTE ESTORNADA — {quantidade_estornada} de
  {quantidade_dispensada} un. (restam {quantidade_restante})"** + `estorno_protocolo`(s).

Os campos `estorno_total`/`quantidade_restante` vêm **prontos do backend** (§5.A) — a UI só renderiza.
O comprovante **continua abrindo normalmente** (nunca some, nunca edita a dispensação original).

### 5.C REGRA DE OURO (já é invariante — CLAUDE.md §6b) — reafirmada como critério

O **protocolo (UUID) da prescrição** e o **id/nº da dispensação** são **imutáveis** e aparecem
**iguais** em qualquer tela, relatório, CSV, PDF ou comprovante — antes e depois do estorno. O estorno
**adiciona** informação (a seção/carimbo), **nunca** altera a identificação da receita emitida. Isso é
critério de aceite verificável (§7).

### 5.D Tradução de "estorno limpa relatório e comprovante" (NÃO é deleção)

Reafirmando a tradução obrigatória do handoff (mission #3), para ninguém implementar deleção:
- No **relatório/CSV** (Fatia A): o estorno **adiciona** a linha `tipo_movimento=estorno`; o
  `saldo_escriturado_item` volta (Σ dispensado − Σ estornado). "Limpar" = **efeito contábil líquido
  zero**, não linha apagada. A Fatia A já faz isso — a Fatia B **não** toca no relatório.
- No **comprovante**: "limpar" = passar a exibir **ESTORNADO** (§5.B), não sumir/editar.
- Deleção de linha em `dispensacoes`/`estornos`/ledger é **proibida** (CLAUDE.md §2) e **fora de escopo**.

---

## §6 [PII-EXAUSTIVIDADE] — rotas tocadas nesta fatia

| Rota | PII exposta | Auth | Muda nesta fatia? |
|---|---|---|---|
| `GET /dispensadores/relatorio.csv` | paciente nome+CPF, comprador nome+documento, prescritor nome+CNS | JWT `dispensador`, travado ao CNPJ do JWT | Não (Fatia A) — B1 só consome |
| `GET /dispensadores/relatorio.pdf` | idem | idem | Não (Fatia A) — B1 só consome |
| `GET /dispensacoes/{id}/comprovante` | paciente nome+CPF, comprador nome+documento, prescritor nome+CNS | JWT `dispensador` por CNPJ; admin bypassa | **Sim (§5.A)** — acrescenta seção `estorno` **sem PII nova** (protocolo/qtd/motivo/data); auth inalterada |

Nenhuma rota pública. Nenhum endereço em nenhuma saída. Grep de auth do §5.A antes do merge:
confirmar que `comprovante` e `estornar` seguem sob `require_role(...)`.

---

## §7 Critérios de aceite

1. **B1:** os dois botões baixam via `fetch`+`blob` com Bearer; **nunca** há `<a href>` para o
   endpoint de relatório. Trocar o JWT (dispensador B) → CSV não contém movimento do dispensador A.
2. **B1:** erro do backend renderiza `detail.mensagem` legível; PDF truncado exibe aviso.
3. **B2:** após dispensar todos os itens de uma receita, ela **desaparece da fila** e está no histórico.
4. **B2 (depende de B0):** estornar a dispensação total → a receita **reaparece na fila** com saldo
   reposto e o item **pode ser dispensado de novo** (ou, se B0=Opção C, mensagem não promete reentrada).
5. **B2:** zero botões/handlers de **ação** de devolução ao prescritor no `dispensador.html` (grep §4.3);
   badges de estado `devolvido_prescritor` **permanecem**; endpoint de backend **intacto**.
6. **B3:** comprovante de dispensação estornada abre normalmente e exibe **carimbo ESTORNADO** +
   `estorno_protocolo` (JSON e PDF). Comprovante de dispensação **não** estornada permanece idêntico.
7. **B3/Regra de ouro:** protocolo da prescrição e nº da dispensação **idênticos** antes/depois do
   estorno em fila, histórico, comprovante e CSV.
8. **B3:** nenhuma linha apagada/editada em `dispensacoes`/`estornos`/ledger (verificação por contagem
   antes/depois do estorno).
9. Testes do enxerto §5.A **verdes contra PG** (datetime do `criado_em` normalizado como na Fatia A) +
   gate com predeploy. Determinismo (`ORDER BY … id`).

---

## §8 Fora de escopo

- XML SNGPC oficial / webservice ANVISA (bloqueado até G4A — CLAUDE.md §10).
- Atualizar a visão do auditor (`/relatorios/*`) — dívida própria (DIVIDA-TECNICA).
- Campo comprador na UI da fila (fatia seguinte da Fase 5).
- **Reabrir** a ação de devolução ao prescritor na UI (só remoção nesta fatia).
- **Seletor de troca de farmácia** na UI (roteiro-driven nesta fatia — §0.1) → **P2**.
- **Push/WebSocket** na fila (pull de 15s basta — §0.2) → **P2 permanente**.
- **Devolução integral sem baixa + re-apresentação fracionada A→B** (§0.3) → **P1 backlog**.
- Deleção de qualquer registro (proibida por §2 do CLAUDE.md).

---

## §9 Fluxo de aprovação

1. **Parecer Z AI primeiro (§2 aberto — decisão do Fabiano 2026-07-11):** o Z AI deve **recomendar
   explicitamente A, B ou C** para o B0, com justificativa contra os invariantes (CLAUDE.md §2/§4 e
   TICKET-ESTORNO-OBJETO-DERIVADO), e dar parecer sobre o enxerto §5.A. **Só então** o martelo do
   Fabiano sobre a opção. A recomendação do arquiteto (Opção A) fica registrada no §2, mas **não**
   pré-decide — o §2 vai ao Z AI aberto.
2. **Gate duro:** #88 mergeado (comando do Fabiano ao engenheiro — diagnóstico concluído, não era bug).
   Só então despachar a implementação.
3. Sequência-mestre (parecer Z AI, split R4 incorporado): **R2 (core, Jules por PR) → B0 → §5.A
   (backend comprovante) → B1 → B2 → B3 → Jules audita F5 (A+B) → R3 ∥ R4-import → R4-snapshot**.
   Backend antes de frontend, sempre.
4. PR → gate (PG + predeploy) → validação UI↔invariante (padrão TICKET-ZAI-FASE4) → teste manual Fabiano.
5. Jules audita a fatia F5 completa (A+B) só após o merge da B, sobre o SHA mergeado.

---

### Anexo — âncoras de código (para o engenheiro)

| Item | Arquivo:linha (aprox.) |
|---|---|
| Cabeçalho da fila (inserir botões B1) | `dispensador.html:418` (`.fila-card-head` de `#fila-container`) |
| Render da fila (ocultar receita sem ação — B2.1) | `dispensador.html:1228-1271` (`_renderizarFila`), `_FILA_TERMINAIS`:1214 |
| Botão/handler `✕ Prescritor` na fila (remover — B2.3) | `dispensador.html:1249`, `_devolverPrescritorFila`:1365 |
| Bloco prescritor no painel (remover — B2.3) | `dispensador.html:1675`, `toggleMotivoPrescritor`:1702, `devolverItemPrescritor`:1934 |
| Histórico (Comprovante + Estorno, `i.estornado`) — já OK | `dispensador.html:1503-1523` |
| Modal comprovante (carimbo estorno — B3.B) | `dispensador.html:1444-1476` (`_renderComprovante`) |
| Comprovante JSON (acrescentar `estorno` — B3.A) | `backend/app/routers/dispensacoes.py:89-146` (`_montar_json`) |
| Estorno objeto-derivado (fonte de `estornos`) | `backend/app/routers/dispensacoes.py:392-517` |
| Guard de re-dispensação (B0) | `backend/app/routers/custodia.py:737-743` |
| Dispensação total fecha custódia + status terminal (B0) | `backend/app/routers/custodia.py:787-796` |
| Fila: prescrições com custódia ativa | `backend/app/routers/dispensadores.py:92-168` |
| Histórico: `estornado` do backend | `backend/app/routers/dispensadores.py:227-253` |
