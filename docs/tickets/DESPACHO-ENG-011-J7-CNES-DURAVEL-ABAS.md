# DESPACHO ENG-011 — J.7 (custódia ≠ agenda) + CNES durável + abas da demo

| Campo | Valor |
|---|---|
| **Despacho** | ENG-011 (J.7 + micro-ticket do CNES durável + J.8/J.9) |
| **De** | Arquiteto (Z) |
| **Para** | Engenheiro (implementa) · cc: Fabiano (martelo de J.7 pendente, §2) |
| **Data** | 2026-08-15 |
| **Origem** | Handoff de 14/08 (fim do dia) · parecer série J (`SESSAO-2026-08-14-PARECER-ARQUITETO-SERIE-J-REVISAO.md`) · bloco Fabiano.md de 14/08 |
| **Base** | `main` em `e19e216` (pós-merge #161). PR #162 (`fix/serie-j-demo-ux`) já rebaseado sobre esta base, CI verde, OPEN |
| **Classes** | J.7 = **`core`** (martelo PENDENTE) · CNES durável = `ops` · J.8/J.9 = `module` |

---

## §1 Contexto

Série J principal fechada: #161 mergeado (J.1/J.2/J.5), #162 pronto para merge (J.3/J.6.b).
Verificações do arquiteto em 15/08 (todas no código, branch `fix/serie-j-demo-ux`):

- **Linha do guia sobre score baixo — CONFERIDA, sem ação.** `guia.html:444` (TICKET-J.4 (c)):
  explica que o selo "baixo" é o indicador dizendo a verdade sobre CNS/CNPJ sintéticos.
  Texto adequado à adjudicação (c)+(a); nada a retrabalhar.
- **403-como-sessão-expirada — mitigado em demo, permanece rastreado.** O J.3 tornou
  `handleUnauthorized()` não-destrutivo em demo (renova e segue, sem alert/logout — diff do #162
  em `clinica.html`), e o interceptador de `config.js` cobre os fetches. Os sítios que ainda
  colapsam 403 em `handleUnauthorized` (ex.: `clinica.html:1288, 1384, 1677, 1706, 1725, 1750,
  2408`) deixaram de derrubar o visitante, mas seguem conflatando 403-posse com 403-sessão.
  **Dobrar o desambiguaute dentro do J.8** (mesmo arquivo, mesma retrabalhada de UI); não é
  ticket separado.

## §2 Martelos

| Ticket | Estado do martelo |
|---|---|
| **J.7** (`core`) | **✔ MARTELADO (15/08 — §11a).** Transferir = posse, não agenda. Implementação liberada; merge aguarda martelo no PR (padrão da casa). |
| CNES durável (`ops`) | Despachado (decisão de 14/08: predeploy cria o SQLite). Pode executar. |
| J.8 / J.9 (`module`) | Despachados (bloco Fabiano.md de 14/08). Podem executar. |

## §3 Instrução de execução — LER PRIMEIRO

> **Regra do Fabiano (verbatim, vale como em ENG-010):** *"Na implementação, o engenheiro deve
> avaliar os fixes propostos. Se discordar de algum ponto técnico, não segue em frente — retorna
> o problema ao arquiteto para reavaliação antes de qualquer alteração no código."*
>
> Os fixes abaixo são propostas do arquiteto; a **forma técnica** é julgamento do engenheiro.
> Discordou → para, documenta com evidência (código/teste) e devolve. Nada de improviso no `core`.

## §4 J.7 — `core`: `transferir-laboratorio` não agenda (custódia ≠ agenda)

**Sítio:** `backend/app/routers/pedidos_exame.py:860` (`POST /pedidos-exame/{protocolo}/transferir-laboratorio`).

**Diagnóstico verificado:** o gesto do cidadão (escolher laboratório e entregar a posse) faz
TUDO: custódia `paciente → prestador_exame` (L919) **e** transição de estado — itens
`pendente → agendado` (L913–917) + eventos `custodia_transferida` e `pedido_agendado`
(L945–966) — **sem nenhum registro em `agendamentos`**. O comentário do próprio endpoint
(L846–850) admite a confluência: "`agendado` É 'sob custódia do prestador'".

**Por que é defeito:** o módulo de agendamento (AGENTS §7 / ARQUITETURA_AGENDAMENTO) estabelece
que itens chegam a `agendado` via `agendamento_criado` — existe um **objeto agendamento** com
identidade, estados e ledger próprios. Aqui o item fica `agendado` sem agendamento algum:
a fila do laboratório não consegue distinguir "chegou, esperando marcar" de "já marcado para
quinta às 8h". Custódia é posse; agenda é compromisso. **São fatos distintos** — o mesmo
princípio que o endpoint invoca para justificar DOIS eventos é o que ele viola ao fundi-los.

**Direção da correção (proposta, sujeita a §3):**
1. `transferir-laboratorio` vira **ato de custódia only**: `custodia_transferida`
   (paciente → prestador_exame, nível pedido). Nenhuma transição de item, nenhum `pedido_agendado`.
2. O pedido em posse do laboratório precisa ser representável sem `agendado`. Duas formas
   candidatas — o engenheiro avalia e propõe: **(a)** pedido permanece `emitido` com a custódia
   como fonte da verdade da posse (a fila já lê custódia), itens permanecem `pendente`; **(b)** o
   recálculo de status do pedido passa a derivar "em posse de prestador" da custódia, sem tocar
   no vocabulário de itens. **Proibido:** criar estado novo sem atualizar AGENTS §7, DDL-doc e
   `states_exame.py` (governança §5a) — se concluir que estado novo é inevitável, PARA e devolve
   ao arquiteto.
3. AC: (i) transferir gera SOMENTE `custodia_transferida` no ledger; (ii) pedido circula para a
   fila do CNPJ (GET fila-exames continua funcionando); (iii) item só chega a `agendado` via
   `POST /agendamentos` (evento `agendamento_criado`); (iv) testes de regressão cobrindo o
   caminho cidadão → fila → agendamento → realização; (v) `guia.html`/demos ajustados se a
   narrativa do fluxo mudar.
4. Impacto em cascata a verificar: `states_exame.py::derivar_status_pedido` (o que o pedido
   repousa após custódia sem agenda), e a UI de `clinica.html`/`cidadao.html` que hoje pressupõe
   `agendado` pós-transferência — coordenar com J.8 para não retrabalhar.

## §5 Micro-ticket `ops` — CNES durável no predeploy

**Problema:** o SQLite da demo (`/data/pix_saude_demo.db`, path resolvido em
`backend/app/config.py:75`) serve à validação CNES (`app/domain/cnes_prescritor.py`, tabela
`profissionais_cnes`). No Render ele foi criado à mão via Shell (14/08) e **morre a cada
redeploy** — FileNotFoundError volta, score "baixo" deixa de ser verdade explicável e vira
falha de base ausente.

**Correção (decidida 14/08):** o `backend/predeploy.sh` (rodado via `preDeployCommand` no
`render.yaml`, WORKDIR `/app`) passa a criar o SQLite demo CNES — tabelas CNES + as 2 farmácias
demo do snippet manual. Fonte do conteúdo: o snippet executado pelo Fabiano em 14/08 (histórico
do chat); se indisponível, reconstruir a partir do que `_get_cnes_conn` lê
(`profissionais_cnes` + estabelecimentos consultados).

**Verificação técnica obrigatória do engenheiro (§3):** confirmar que arquivo escrito pelo
preDeployCommand **persiste até o container do serviço** no Render Docker runtime. Se não
persistir (pre-deploy em instância efêmera), a forma correta é criar/verificar a base **no boot
da aplicação** (idempotente, barato) — mesma decisão de "durável", sítio diferente. Documentar
a verificação no relatório.

AC: redeploy na vitrine → validação CNES responde com base presente (score "baixo" por
identidade sintética, não por FileNotFoundError); log do predeploy/boot mostra a criação
idempotente; nada muda em `core`.

## §6 J.8 — `module`: abas do laboratório (`clinica.html`)

Reorganizar a tela do operador em 4 abas, espelhando o percurso real do exame:
**Recepção** (fila de pedidos transferidos/chave de circulação) · **Agendamento** (criar/ver
agendamentos) · **Realização** (comparecimento/coleta) · **Bancada** (produção e liberação de
laudo). É retrabalho de UI: **não** alterar rotas, estados, ledger, custódia. Aproveitar a
retrabalhada para o desambiguaute de 403 (§1). Se J.7 já tiver martelo e sair junto, alinhar as
abas ao novo fluxo (custódia sem agenda); senão, abas sobre o fluxo corrente — sem gambiarras
que o J.7 vai quebrar (evitar acoplar UI ao estado `agendado` como sinônimo de "com o
laboratório").

AC: operador circula pelas 4 abas cobrindo o ciclo completo na vitrine; E2E browser pelas abas;
403 de posse não derruba sessão nem em demo nem fora.

## §7 J.9 — `module`: abas do cidadão (`cidadao.html`)

Reorganizar a carteira do cidadão em 3 abas: **Receita** · **Exames** · **Atestado**. Mesma
regra: UI only, zero mudança de API/estados. Manter o poll da carteira e o re-login
transparente do J.3 intactos (o interceptador é global — não duplicar).

AC: cidadão vê e opera os 3 tipos de objeto nas abas; sessão demo sobrevive 20+ min contínuos
(regressão do J.3 preservada); E2E browser.

## §8 Estratégia de PR e gates

1. **PR `ops`:** micro-ticket CNES (`predeploy.sh` ou boot, conforme §5). Pequeno, sai primeiro.
2. **PR `module`:** J.8 + J.9 (+ desambiguaute 403 do §1). Base na `main`.
3. **PR `core`:** J.7 — **somente após martelo do Fabiano**. Merge aguarda martelo no PR
   (padrão da casa).
4. Gates obrigatórios verdes antes de reportar: unit + integração + browser completos.
   J.7 exige testes de regressão específicos (AC §4.5).
5. Ordem sugerida: micro-ticket CNES → J.8/J.9 → J.7 (se martelo chegar). Micro-ticket e abas
   podem correr em paralelo.

## §9 Registro e limites

- Relatório em `docs/tickets/SESSAO-2026-08-15-TICKET-ENG-011-*.md` (padrão da casa), com
  evidências (testes, prints de API, log do predeploy).
- **Não commita sem ordem** (regra contínua). Ao terminar os PRs, reporta e aguarda.
- Escalonamento: §3 — discordância técnica em qualquer ticket → para e devolve ao arquiteto.
- Pendências de fora deste despacho (não executar, só constar): merge do #162 (parecer do
  arquiteto: aprovado; aguarda ordem), reset manual da vitrine via Shell do Render (Fabiano),
  commit dos docs não versionados (decisão do Fabiano).

---

## §10 Adendo 1 (2026-08-15) — J.9 ganha a "resposta ao cidadão" (decisão do Fabiano)

Origem: decisão do Fabiano em 15/08 ("de acordo, versão A" — inline no Exames; houve avaliação
prévia do arquiteto registrada em `Fabiano.md`, bloco 2026-08-15). **As abas do cidadão
permanecem TRÊS** (Receita | Exames | Atestado) — decisão explícita contra a 4ª aba.

**Escopo acrescido ao J.9 (§7):** o cidadão vê, em tempo de leitura, o agendamento que o
laboratório criou para o seu exame — **sem nenhuma transição de custódia** (informação ≠
custódia; a custódia segue com `prestador_exame` até o fim).

- **Forma:** no cartão de cada pedido (aba Exames), selo em destaque com o agendamento corrente:
  `Agendado: dd/mm hh:mm · Unidade X`. Remarcação = objeto derivado; mostrar sempre o agendamento
  ativo. Histórico completo permanece no ledger (persona admin), não na carteira.
- **Backend:** novo caminho de leitura com papel `paciente` (agendamentos dos seus pedidos) —
  `module`, leitura apenas, zero escrita, zero evento novo. Reaproveitar a consulta que a
  clínica já faz (`GET /pedidos-exame/{p}/agendamentos`) como base, protegida por ownership de
  paciente (padrão anti-leak).
- **AC adicional:** cidadão transfere exame → laboratório agenda → cidadão vê data/hora/unidade
  no cartão do exame sem sair da aba; a leitura não gera evento de custódia; regressão do J.3
  preservada; E2E browser cobrindo o caminho completo.

## §11 Adendo 2 (2026-08-15, tarde) — martelo J.7 ✔ · lente no J.9 · J.10 NOVO

### (a) Martelo do Fabiano no J.7 — DECISÃO DADA

Regra aprovada (registrada em `Fabiano.md`): *transferir ao laboratório é um ato de posse
(custódia), não de agenda; itens continuam `pendente`; quem promove a `agendado` é o
laboratório, criando agendamento com data/hora/unidade — ou realizando direto.*

- **Implementação LIBERADA** — §4 vale integralmente, incluindo as proibições.
- Forma técnica (status que representa "com o laboratório, aguardando decisão") = engenheiro
  propõe, arquiteto revisa. Estado novo → PARA e volta ao Fabiano (governança §5a).
- Merge do PR `core` aguarda martelo do Fabiano **no PR** (padrão da casa).
- Dependência do J.8 resolvida: as abas passam a ser desenhadas sobre a semântica nova.

### (b) J.9 += lente compartilhada (endossada pelo Fabiano)

- Extrair o render da Lente de Auditoria (`index.html`) em **componente compartilhado**.
  O index **mantém** a lente pública (busca anônima por protocolo/chave — prova da tese para
  o visitante); cada cartão de objeto nas abas do cidadão ganha **"ver rastreabilidade"**
  abrindo a trilha neutra daquele objeto.
- Endpoints `/public/*` e `/circulacao/{chave}` são `core` e ficam **intocados** — zero
  backend. AC: cartão → trilha sem login adicional; função do index inalterada.

### (c) J.10 NOVO (`module`) — custódia parcial de exames

**Problema (Fabiano):** laboratório que retém o pedido inteiro inviabiliza, em outro
laboratório, os exames que ele não realiza. **Base:** `pedido_exame_custodia.item_id`
nullable já suporta nível-item (documentado no model, `pedido_exame_custodia.py:12-14`);
falta endpoint — o `transferir-laboratorio` só faz nível-pedido.

**Dois mecanismos (ambos confirmados pelo Fabiano):**
1. **Transferência parcial** — payload de `transferir-laboratorio` aceita `itens: [...]`
   (opcional; ausente = pedido inteiro, retrocompatível). Itens não listados permanecem na
   custódia do cidadão e circulam a outro CNPJ.
2. **Devolução de não-realizáveis** — endpoint para o laboratório devolver, por item, o que
   não performa: custódia `prestador_exame → paciente` com motivo documentado, item volta a
   `pendente`. Espelho da dispensação parcial da receita (AGENTS §4).

**Restrições:** sem estado novo, sem evento novo (`custodia_transferida` por item já existe);
sem dupla custódia ativa do mesmo item — **constraint no banco** (lição COER-2);
`fila-exames` enxerga custódia item-granular; pedido com itens sob custodiantes distintos
exige derivação de status coerente (parte do design).

**Sequência:** desenhar JUNTO com J.7 (mesma semântica de custódia); implementar APÓS o
merge do J.7; PR `module` próprio.

**AC:** (i) transferir 2 de 5 itens → 2 na fila do CNPJ, 3 com o cidadão e transferíveis a
outro; (ii) devolução devolve item específico → `pendente` + custódia paciente + evento;
(iii) constraint recusa dupla custódia ativa (IntegrityError, teste injetando a tentativa);
(iv) remanescentes circulam a outro laboratório até o resultado; (v) E2E browser.

### (d) Ordem de execução revisada (supera §5 do §8)

1. PR `ops` — micro-ticket CNES durável (§5).
2. PR `core` — J.7 (§4 + §11a); J.10 desenhado junto.
3. PR `module` — J.8 + J.9 (§6/§7 + §10 + §11b).
4. PR `module` — J.10 (§11c), após merge do J.7.

Gates completos (unit + integração + browser) antes de reportar; J.7 e J.10 com testes de
regressão específicos (ACs).

---

*Despacho emitido pelo arquiteto (Z) em 2026-08-15, na sequência do handoff de 14/08 e das
verificações de código desta data. Adendo 1 (resposta ao cidadão) e Adendo 2 (martelo J.7,
lente no J.9, J.10) na mesma data.*
