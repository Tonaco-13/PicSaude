# Fabiano — bloco de notas

> Anotações do Fabiano registradas pelo arquiteto (Z). Itens triados e classificados; ver
> despacho vigente em `docs/tickets/DESPACHO-ENG-010-SERIE-J-EXCURSAO-VITRINE.md`.

---

## 2026-08-14 — Bug do "já agendado" + UI de gentileza (laboratório e cidadão)

> Anotação original do Fabiano (verbatim):
>
> "Mais uma coisinha (bug). O pedido de exames chega à clínica já agendado. Ela a princípio,
> só tem que receber, com duas opções iniciais: realizar ou agendar. Quando chegar o dia e a
> hora do agendamento (ou antes, a critério do laboratório) a gente muda para realizar. Em
> realizar, envia à bancada ou preenche o resultado. Temos que pensar em dar gentileza ao
> usuário nesta UI, talvez deixar como aquela barra do prescritor: Receita, Exame e Atestado.
> No laboratório ficaria: Recepção, Agendamento, Realização, Bancada (aqui entra o laudamento).
> Aproveito para dizer que podemos adotar a mesma lógica do prescritor ao cidadão: Receita,
> Exames e Atestado. Clicou, abriu."

### Triagem do arquiteto (Z)

**1. Bug confirmado no código — vira J.7 (core · martelo do Fabiano).**
`POST /pedidos-exame/{proto}/transferir-laboratorio` (`pedidos_exame.py:860+`) faz a custódia
paciente → prestador **e de quebra** transiciona itens `pendente → agendado`, emitindo
`pedido_agendado` sem existir agendamento (sem data, sem hora, sem unidade). Conflita com o
modelo (AGENTS §7: é o `agendamento_criado` que promove itens a `agendado`) e engana a UI da
clínica — que recebe o pedido "já agendado" sem ter agendado nada.
**Correção proposta:** transferir-laboratorio = custódia apenas (itens permanecem `pendente`,
evento só `custodia_transferida`); a clínica então escolhe **agendar** (com data/hora → aí sim
`pedido_agendado`) ou **realizar** direto. Como altera emissão de evento de ledger, é `core`
(§10) — martelo do Fabiano. Interage com J.1 (mesma máquina de estados): J.7 deve entrar no
mesmo PR core da série J.

**2. UI do laboratório em barra de abas — vira J.8 (module).**
`Recepção | Agendamento | Realização | Bancada (laudamento)` no `clinica.html`, espelhando a
barra do prescritor (Receita/Exame/Atestado). Puramente frontend (nenhuma API mudando).
Recepção = fila do que chegou (receber → realizar ou agendar); Agendamento = agenda com
data/hora e ação "realizar" quando chegar a hora (ou antes, a critério do laboratório);
Realização = coleta; Bancada = análise/resultado/laudamento. Depende de J.7 para fazer sentido
(a fila de Recepção só existe se o pedido NÃO chegar pré-agendado).

**3. UI do cidadão em barra de abas — vira J.9 (module).**
`Receita | Exames | Atestado` no `cidadao.html` — clicou, abriu. Consistente com a carteira
existente; só reorganiza a navegação. Frontend-only.

**Parecer:** proposta boa nos três pontos — separa posse de agenda (correto para o modelo de
custódia) e uniformiza a linguagem de navegação entre prescritor, laboratório e cidadão.
J.7 precisa de martelo; J.8/J.9 são `module` e podem entrar no PR 2 da série J ou num PR 3
de UI, a critério do ritmo.

---

## 2026-08-15 — Resposta ao cidadão (pós-transferência) · atomização · ticket V2 do Conselheiro

> Anotação do Fabiano (verbatim):
>
> "o pedido não chega pré agendado. a única coisa que o paciente faz é a transferência de
> custódia para a clínica/laboratório. O que podemos criar é uma resposta à transferência de
> custódia, mas não o retorno da custódia, com o agendamento ao paciente: aí teríamos que
> acrescentar aos submódulos receitas, exames, atestados, o de agendamentos. (…) Mais adiante,
> teremos a atomização dos objetos sanitários. Temos que ver quando faremos isso."

### Triagem do arquiteto (Z)

**1. Resposta ao cidadão — semântica CORRETA e sem custo em `core`.**
Informação ≠ custódia: o agendamento criado pelo laboratório vira **visível** ao cidadão,
sem nenhuma transição de custódia de volta (custódia segue `prestador_exame` até o fim).
O evento já existe (`agendamento_criado` no ledger do agendamento); falta só caminho de
leitura com papel `paciente` + UI — classe `module`, leitura apenas.

**Recomendação de forma:** embutir no submódulo **Exames** (o pedido conta a própria história:
"com o laboratório → agendado para dd/mm hh:mm na unidade X → coletado → resultado"), que é a
narrativa objeto-cêntrica da demo. A 4ª aba "Agendamentos" é visão de conveniência derivada
(o cidadão não cria agendamentos — quem cria é o laboratório); só vale a pena quando houver
volume real. **Decisão do Fabiano:** embutido (recomendado) ou 4ª aba. Escolhida a forma, eu
emito adendo ao ENG-011 §7 (J.9) incluindo a resposta ao cidadão no escopo.

**2. Atomização dos objetos sanitários — quando. ✔ DECIDIDO (15/08): "de acordo".**
Sequenciamento aprovado pelo Fabiano: atomização (ticket V2) fica **depois do go-public**.
Ordem: J.7–J.9 → go-public (GP-1..GP-4) → piloto/parceiros → atomização (gatilho: decisão
explícita do Fabiano ou G1/G2/G3). O ticket permanece **na gaveta, implementação-pronto**,
com os pré-requisitos de ativação anotados no parecer do item 3.

**3. Análise estática do TICKET-RASTREABILIDADE-POR-OBJETO-V2 (Conselheiro) — parecer PARCIAL.**
*O texto recebido corta no meio do §3 ("nova tabela `objetos_dispensaveis`…"); avaliáveis só
§1–§2 e a abertura do §3. Parecer vale para o que foi visto; o resto vem antes de formalizar.*

- **§1 (governança): correto.** Ativação = decisão explícita do Fabiano; o ticket não se
  auto-ativa. Consistente com a casa (§10 do AGENTS, NUCLEO_SANITARIO).
- **§2 (granularidade): concordo com a recomendação (b) por frasco/caixa.** Alinha com o
  rastreio por lote da ANVISA, preserva identidade individual e controla volume. A (a) é
  over-engineering regulatório; a (c) perde a identidade individual. Ressalvas a verificar
  na ativação: mapeamento quantidade-prescrita (unidades) ↔ objetos (embalagens) com
  dispensação parcial em múltiplos atos (vira entrega de N objetos — limpo); a constraint
  da casa `Σ dispensado ≤ prescrito` permanece; estorno/devolução por objeto simplifica os
  `item_devolvido_*`.
- **Base desatualizada:** o ticket cita `main@f361ab8` (09/08); a main atual é `e19e216`
  (pós-série J). Na ativação, revalidar sítios (J.1/J.2/J.5 tocaram `states_exame.py` e
  áreas adjacentes).
- **A exigir na ativação (se ainda não estiver no ticket):** checklist NUCLEO_SANITARIO §11
  completo (identidade UUID, estados, ledger, custódia por objeto — `farmácia → paciente`
  por embalagem), vocabulário de estados novo seguindo a governança §5a (AGENTS + DDL-doc +
  `states.py` juntos), impacto de volume no ledger (evento por objeto), e plano de migração
  da dispensação atual (`dispensacoes` vira extensão dos objetos? caminho paralelo proibido).
- **Classe `core`: correta** — reescreve a máquina de dispensação; martelo do Fabiano no PR.

**Parecer COMPLETO (15/08, texto integral recebido — §3–§9):**

Âncoras verificadas no código pelo arquiteto: `estornos.protocolo` UUID existe
(`estorno.py:29`) · `dispensacoes.quantidade_dispensada` existe (`dispensacao.py:28`) ·
COER-2 documentado (`docs/LEARNINGS.md`). O ticket está fundamentado de verdade. Achados
que exigem **adendo de design antes de o engenheiro começar** (pré-requisitos de ativação):

1. **Quando o objeto nasce (o §3 não fechou isto).** O design mistura dois modelos
   incompatíveis entre si: FK `prescricao_item_id` obrigatória (objeto nasce preso a um
   item — ou seja, nasce NA dispensação) e, ao mesmo tempo, estado `disponivel` + a
   promessa "não dispensar duas vezes = constraint de banco" — que só morde se o objeto
   **existe antes**, num pool de estoque. Se nasce na dispensação, `disponivel` não existe
   e a proteção real continua sendo Σ no nível do item. Se nasce no estoque, precisa de
   fluxo de entrada/lote/validade (subdomínio de estoque inteiro — maior que 2–3 semanas).
   Decidir explicitamente qual dos dois é o V2.
2. **Máquina de 4 estados é insuficiente.** `devolvido` conflita `devolvido_paciente`
   (abandono — re-dispensável, AGENTS §4) com `devolvido_prescritor` (erro clínico —
   terminal). E `estornado` terminal quebra o princípio "a identidade percorre toda a
   vida": a mesma caixa devolvida e re-dispensada é o MESMO objeto com mais história
   (dispensado → devolvido_paciente → disponivel → dispensado), não um objeto novo.
3. **R2/AC5 mal formulado.** "Cada objeto aparece uma única vez" no SNGPC é falso num
   mundo com re-dispensação (o mesmo objeto tem 2 movimentos legítimos). Unicidade
   correta = por (objeto, movimento). O alarme de fraude é o mesmo objeto em duas
   dispensações ATIVAS simultâneas — exatamente o que a constraint parcial pega.
4. **Fracionamento.** Granularidade (b) embalagem-fechada conflita com fracionamento e
   dose unitária previstos na farmácia hospitalar (`ARQUITETURA_FARMACIA_HOSPITALAR.md`
   L41/76/246). Regra necessária: fração vira objeto parcial com quantidade (híbrido
   (c) só nesses casos), ou fracionamento fica fora do V2 (ambulatorial, caixa fechada).
5. **Migração — preferência declarada: corte-limpo** (§6, 2ª opção). Backfill sintético
   inventa identidades para um passado que não as tinha; ledger registra o que aconteceu.
   O teste em PG efêmero (saldo inalterado) vale nas duas opções.
6. **Governança:** máquina de estados nova de objeto entra AGENTS + DDL-doc + `states.py`
   juntos (regra §5a da casa). O §9 do ticket (fatias, gate PG+Jules, martelo por fatia)
   está correto e alinhado.

**Síntese do parecer:** ticket bem fundamentado (âncoras batem), classe e fluxo corretos,
estimativa plausível — mas **não é implementação-pronto no sentido estrito**: os achados
1–4 são decisões de design que precedem código. Como a ativação ficou pós-go-public
(item 2), o ticket volta para a gaveta com estes 6 itens como checklist de abertura.

### Segunda leva (15/08, tarde) — resposta ao cidadão ✔ · lente · atomização de exames

> Anotações do Fabiano (resumo): (1) "de acordo, versão A" — resposta ao cidadão inline no
> Exames; (2) a Lente de Auditoria do index "pode estar no módulo cidadão, já que com o novo
> desenho ele vai ficar mais organizado"; (3) a rastreabilidade "valerá para os exames também" —
> clínica que não faz todos os exames e retém o pedido inteiro inviabiliza o resto em outro
> laboratório.

**1. Resposta ao cidadão — ✔ DECIDIDO: versão A (inline).** Adendo 1 emitido no
`DESPACHO-ENG-011` (§10): J.9 ganha o selo de agendamento no cartão do exame (aba Exames,
três abas mantidas), leitura com papel `paciente`, zero transição de custódia.

**2. Lente de Auditoria — avaliação do arquiteto: NÃO mover; compartilhar.**
A lente do index é **verificação pública anônima** — consome os endpoints neutros
`/public/*` e `/circulacao/{chave}` sem login (verificado em `index.html`). Isso é a
demonstração da tese para o visitante que NÃO é o dono do objeto ("qualquer um confere") —
peça central do go-public (GP-2). Tirá-la do portal tira o momento de prova do visitante
anônimo. Dentro do módulo cidadão, o cidadão não precisa de busca genérica: os objetos dele
já estão listados nas abas. **O que a intuição do Fabiano acertou:** cada cartão de objeto
(abas Receita/Exames/Atestado) deve ter "ver rastreabilidade" abrindo a mesma trilha neutra
daquele objeto. **Recomendação:** extrair o render da lente em componente compartilhado →
index mantém a lente pública; cidadão ganha a trilha por objeto. Zero backend (`/public/*`
intocado, é `core`). **✔ ENDOSSADA pelo Fabiano (15/08) — entrou no J.9 (ENG-011 §11b).**

**3. Rastreabilidade/atomização para EXAMES — ENDOSSE do arquiteto: custódia parcial por item.**
O problema é real e o princípio já é da casa: AGENTS §4 (impossibilidade num ponto não
invalida o objeto — o item volta a `pendente` e circula em outro lugar). O análogo para
exames: quem não realiza certo exame não pode reter o item. **O schema JÁ suporta** —
`pedido_exame_custodia.item_id` nullable, granularidade documentada no model
(`pedido_exame_custodia.py:12-14`); falta endpoint (transferir-laboratorio hoje só faz
nível-pedido, `item_id NULL`). Forma proposta: **(i)** transferência parcial — cidadão
transfere só os itens que o laboratório realiza (`itens: [...]` no payload); **(ii)**
devolução de não-realizáveis — laboratório devolve itens que não performa (custódia
prestador → paciente por item, motivo documentado; espelho da dispensação parcial da
receita). Sem estado novo, sem evento novo (`custodia_transferida` por item já existe no
vocabulário). **✔ J.10 CONFIRMADO com os DOIS mecanismos** (Fabiano: "1 e 2 ao mesmo tempo")
— despachado no ENG-011 §11c; desenho junto do J.7, execução após o merge dele. Narrativa:
fortalece a tese da custódia cidadã — o cidadão decide o que entrega a quem.

**4. Martelo do J.7 ✔ DADO (15/08).** Regra aprovada: *transferir ao laboratório é ato de
posse (custódia), não de agenda — itens continuam `pendente`; quem promove a `agendado` é o
laboratório (agendamento com data/hora/unidade) ou realiza direto.* Implementação liberada;
forma técnica delegada ao engenheiro com revisão do arquiteto; estado novo volta ao martelo
(governança §5a); merge do PR `core` aguarda martelo no PR. Registrado no ENG-011 §11a.

**5. Individualização dos exames — ✔ MESMO MOMENTO da atomização das receitas (15/08).**
Duas camadas, para não confundir: **(i)** a custódia por ITEM de exame (J.10) vai AGORA —
não é atomização, os itens de pedido já têm identidade própria; resolve o problema do
cidadão. **(ii)** a individualização profunda — AMOSTRA/tubo como objeto sanitário rastreável
(UUID próprio, cadeia coleta → transporte → bancada → laudo) — é a atomização do lado exame,
mesma classe de mudança de paradigma que o V2 das receitas (embalagem). Fica NA MESMA
GAVETA e no mesmo momento: pós-go-public, mesmos gatilhos (G1/G2/G3 ou decisão explícita).
Na ativação, desenhar como UM programa de atomização (checklist NUCLEO_SANITARIO §11
cobrindo receita e exame juntos), não duas reescritas separadas.

---

## 2026-08-15 (fecho do dia) — 3 PRs abertos · J.7 revisado ✔ · J.10 desenho + martelo

**Estado:** #163 (ops, CNES no boot) · #164 (module, abas J.8/J.9 + 403) · #165 (core, J.7,
base no #164) — CI verde nos três, nenhum mergeado. Pareceres do arquiteto:
`SESSAO-2026-08-15-PARECER-ARQUITETO-ENG-011-REVISAO.md` (CNES+abas) e
`SESSAO-2026-08-15-PARECER-ARQUITETO-J7-PRS.md` (J.7 + J.10, o de fecho).

**J.7 (PR #165): revisado e APROVADO pelo arquiteto.** Fiel ao martelo: transferir é posse
(um evento, itens `pendente`, pedido `emitido`); arestas novas `emitido→coletado` /
`pendente→coletado` ("ou realizando direto"); guard de dupla posse migrado para a custódia;
bug do `para = papel ('paciente') ≠ CPF` pego pelo gate de navegador e corrigido com
helpers de fonte única. **Aguarda martelo do Fabiano NO PR para o merge.**

**Escopo dos Adendos §10/§11b (selo + lente) fora do #164:** correto — despachado como
**J.11 (`module`)**, a executar após o merge do #165 (com o J.7, o selo só aparece com
agendamento real — que é o que ele deve mostrar).

**J.10 — desenho do engenheiro APROVADO com caminho (b).** O §11c do despacho errou na
classe: `pedido_exame_custodia` é ledger `de/para` SEM posse atual (não tem `encerrada_em`
como a da receita/COER-2), logo o AC (iii) é inalcançável sem migração — e migrar cadeia de
custódia é `core`. **MartiLO PENDENTE do Fabiano (formulação):** aprovar PR `core` próprio
"custódia de exame ganha posse atual" — `encerrada_em` + índice único parcial nos dois
dialetos + data-fix na migração + choke-point `transferir_posse_exame` + migração dos 3
sítios de leitura "última linha". O J.10 (endpoints `itens:[...]` + `/devolver`, fila por
custódia com anti-vazamento entre prestadores) empilha sobre ele como `module`. Caminho (c)
(desistir do AC iii) VETADO pelo arquiteto — é o defeito que o COER-2 existe para impedir.

**Ordem para amanhã:** merges #163 → #164 (ordem do Fabiano) → #165 rebase para main +
martelo no PR → J.11 → (com martelo) PR core da migração → J.10. Micro-ticket `core` do
RBAC de agendamentos (dispensador cria mas não lista) pode viajar no combo do J.10.

**Render (reset da vitrine):** passo a passo já entregue — hora certa: após merge do #163
(no mínimo); conferir linha `[cnes-demo]` no log de boot; nunca mais re-rodar snippet CNES.

---

## 2026-08-16 — "Tudo autorizado" + viagem: rodada autônoma do engenheiro

> Registro do arquiteto (Z). Às vésperas de viajar, o Fabiano autorizou de uma vez os três
> martelos que lhe foram pedidos (chat do arquiteto, 16/08): (1) merges de #163/#164 pelo
> engenheiro; (2) martelo antecipado no #165; (3) abertura da migração `core` da custódia.
> Também autorizado: PR `docs` dos arquivos não versionados. Protocolo completo e limites
> no **Adendo §10 do `DESPACHO-ENG-012-MERGES-E-REBASE-DO-J7.md`** — é a fonte de verdade
> desta rodada.

Pontos que exigem o Fabiano de volta (parada da rodada autônoma):

1. **Martelo + merge do PR `core` da migração da custódia** ("ganha posse atual") — a
   autorização de 16/08 cobre a abertura, não o merge. O J.10 (e o micro-ticket RBAC do
   combo) segue empilhado à espera dele.
2. **Reset da vitrine no Render** (runbook já entregue; conferir `[cnes-demo]` no boot).
3. Qualquer divergência no protocolo do #165 (Adendo §10b) — engenheiro NÃO mergeia e
   documenta; decisão volta ao Fabiano.

Revisão retroativa do J.11 (mergeado sob ordem geral) e revisão detalhada do PR da
migração ficam com o arquiteto na sessão de 17/08 (handoff:
`SESSAO-2026-08-16-HANDOFF-ARQUITETO.md`).
