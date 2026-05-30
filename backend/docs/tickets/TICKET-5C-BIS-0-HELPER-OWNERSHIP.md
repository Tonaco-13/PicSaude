# TICKET-5C-BIS-0-HELPER-OWNERSHIP — spike de avaliação (não implementação)

> **Origem:** decisão estratégica de 2026-05-26 (Arquiteto + Fabiano) — abertura do 5C-bis com spike avaliativo antes do TICKET-A.
> **Classe:** `docs` (artefato de decisão arquitetural). Saída deste ticket é um documento + decisão go/no-go, não código de produção.
> **Ritmo:** Regra 3 (sem CODEX rodada 1). CODEX vê o output como insumo do TICKET-A.
> **Prazo:** até quinta 28/05 (após reunião com extensionistas — antes de redigir TICKET-A).
> **Versão:** v0.2 (2026-05-26 após CODEX rodada 0 integrada — 0 P1 + 6 P2 + 4 P3 aceitos integralmente). Amadurece para v1.0 na quinta com a leitura concreta dos 5 routers.

---

## §1 Objetivo

**DECIDIR** se faz sentido extrair um helper compartilhado de ownership check para reuso entre os 5 subdomínios do 5C-bis (pedidos de exame, laudos, agendamentos, circulação diagnóstica, hospitalar), ou se cada subdomínio deve continuar com checagem local.

Este ticket NÃO implementa o helper. Só avalia. O output é um documento que:

- (a) propõe uma assinatura comum e o coloca como base do TICKET-5C-BIS-A; ou
- (b) conclui que abstração é prematura/artificial e declara que cada subdomínio segue com checagem local — registrando o porquê em ADR-002.

A escolha é vinculante para os 5 tickets seguintes (A/B/C/D/E). Não revisitar depois — se aparecer caso de borda em E, vira refactor próprio.

## §2 Material a analisar

### §2.1 Padrões já implementados no 5C (HEAD = `5db20ef`)

Reestruturado a partir do parecer CODEX rodada 0 (2026-05-26): classificação por **padrão de check**, não por endpoint. As 11 vulnerabilidades V1-V11 caem em 5 padrões dominantes — essa é a unidade real para decidir helper vs local. V2 foi adicionada ao inventário (estava ausente no v0.1).

#### Padrão A — payload-vs-JWT (mutação com ownership pré-INSERT)

| V | Endpoint | Linha | Forma do check |
|---|---|---|---|
| V1 | POST /prescricoes | prescricoes.py:213 | `normalize_cns(payload.cns_prescritor) == normalize_cns(usuario["sub"])` |
| V2 | POST /prescricoes/fisica | prescricoes.py:690 | mesmo padrão de V1 no fluxo físico |

Característica: o objeto ainda não existe no banco. O check é sobre o **payload declarado** vs **identidade do JWT** — uma comparação direta de string normalizada, sem query auxiliar.

#### Padrão B — SQL JOIN com prescritor (leitura com query auxiliar)

| V | Endpoint | Linha | Forma do check |
|---|---|---|---|
| V3 | GET /prescricoes/{proto}/documento | prescricoes.py:872 | `SELECT 1 FROM prescricoes JOIN prescritores ON cns = ?` |
| V7 | GET /prescricoes/{proto}/validacao | validacao.py:25 | mesmo padrão de V3 |
| V8 | GET /prescricoes/{proto}/assinatura | assinaturas.py:148 | mesmo padrão de V3 |

Característica: o objeto existe; a query confirma ownership pelo JOIN com a tabela de atores legítimos. Admin passa sem query.

#### Padrão C — row já carregado (leitura com check em memória)

| V | Endpoint | Linha | Forma do check |
|---|---|---|---|
| V4 | GET /prescricoes/{proto}/pdf | prescricoes.py:972 | `normalize_cns(usuario["sub"]) == row["cns_prescritor"]` |

Característica: o objeto foi buscado antes para outra finalidade; o check reusa o row em memória, sem nova query.

#### Padrão D — matriz multi-role (leitura com lógica de papel ativo/histórico)

| V | Endpoint | Linha | Forma do check |
|---|---|---|---|
| V5 | GET /custodia/{proto}/custodia | custodia.py:237 | matriz de roles + "histórico de participação" |
| V9 | GET /dispensacoes/{id}/comprovante | dispensacoes.py:276 | matriz de roles via chave indireta (dispensacao_id) |

Característica: múltiplos atores legítimos (prescritor, dispensador, paciente, auditor, admin) cada um com critério próprio. Auditor passa neste padrão; **não passa nos demais**. Diferente dos demais padrões, há fallback semântico (`dispensador que já teve custódia` ≠ `dispensador autenticado`).

#### Padrão E — mutação composta (ownership + semântica de payload)

| V | Endpoint | Linha | Forma do check |
|---|---|---|---|
| V6 | POST /custodia/{proto}/custodia/transferir | custodia.py:346 | `payload.de == usuario.role` + ownership da prescrição |
| V10 | POST /custodia bypass | custodia.py:517 | composto (envolve transição de detentor) |
| V11 | POST /prescricoes/{proto}/assinatura | assinaturas.py (upsert) | ownership pré + semântica do payload de assinatura |

Característica: a operação altera estado; o check precisa combinar ownership do objeto com validação do payload (papel declarado, transição declarada, conteúdo declarado). Não cabe em helper genérico — cada caso tem invariantes próprias.

**Síntese:** padrões B e C são candidatos óbvios a helper; A pode caber com cuidado; D exige adaptador por subdomínio; E fica sempre local.

### §2.2 Subdomínios do 5C-bis — dimensões a mapear

Para cada endpoint dos 5 subdomínios, responder as 7 dimensões abaixo (expandido a partir do parecer CODEX rodada 0, 2026-05-26 — as 4 últimas eram ausentes no v0.1 e importam especialmente em circulação e hospitalar):

1. **Captura ou descarta o usuário?** O endpoint usa `usuario=Depends(...)` (captura) ou `_=Depends(...)` (descarta)? Endpoints com `_` são vulneráveis por definição — entram no escopo do ticket A-E correspondente.

2. **Quem é "dono"?** Resposta esperada por subdomínio (a confirmar lendo `pedidos_exame.py`, `laudos.py`, `agendamentos.py`, `circulacao_diagnostica.py`, `hospitalares.py`):
   - Pedidos de exame: prescritor que pediu (CNS, via `cns_prescritor` no row); prestador que executa (CNPJ via `cnpj_prestador`)
   - Laudos: responsável técnico do prestador (CNS); destinatários da ciência: prescritor + paciente
   - Agendamentos: paciente (CPF) + prestador via `org_id` + `unidade_id` (não CNPJ direto)
   - Circulação diagnóstica: prestador via `org_id` + `unidade_id`; chave própria `chave_circulacao`
   - Hospitalar: `detentor_id = unidade_id` (não CNPJ direto) — caso especial

3. **Tipo de vínculo do ator com o objeto.** O ator está acessando como dono original, destinatário (ciência), operador (executa ação), custodiante ativo (tem o objeto agora), ou participante histórico (já teve custódia)? V5 (matriz multi-role) admite custodiante histórico; demais padrões não.

4. **Qual a chave de identidade?** CNS (prescritor), CPF (paciente), CNPJ (dispensador ambulatorial), `unidade_id` (dispensador hospitalar, via JWT CNPJ → `prestadores.cnpj` → `unidades.unidade_id`). Múltiplas chaves possíveis no mesmo endpoint.

5. **Granularidade do recurso protegido.** Pedido inteiro, item individual, subconjunto de itens, ou chave de circulação? Granularidade afeta a query — helper de "ownership de pedido" não atende "ownership de item".

6. **Mutação ou leitura?** Leituras tendem a caber em padrão B ou C (candidatos a helper). Mutações tendem ao padrão A (payload-vs-JWT) ou E (composta).

7. **Checagem antes de side effects?** Mutações que disparam transição de custódia, registro em ledger, ou notificação ao paciente precisam do check 100% antes do `INSERT`/`UPDATE`. Helper que só levanta exceção tardiamente quebra essa garantia.

### §2.3 Inventário de chaves de identidade — origem real no JWT

Corrigido a partir do parecer CODEX rodada 0: o JWT carrega `usuario["sub"]` = `usuarios.identificador`, e a tradução para a entidade clínica depende do role. Tabela `dispensadores.cnpj` mencionada no v0.1 estava errada — não é origem direta da identidade do JWT.

| Tipo de ator | `usuario["sub"]` no JWT | Normalizador | Origem na fonte | Vínculo a recurso clínico |
|---|---|---|---|---|
| Prescritor | CNS (15 dígitos) | `normalize_cns` | `usuarios.identificador` | `prescritores.cns` (match direto) |
| Paciente | CPF (11 dígitos) | `normalize_cpf` | `usuarios.identificador` | `pacientes.cpf` (match direto) |
| Dispensador ambulatorial | CNPJ normalizado | `_normalizar_identificador` (login.py:70) | `usuarios.identificador` | `prestadores.cnpj` → `prestadores.id` (uma hop) |
| Dispensador hospitalar | CNPJ normalizado | `_normalizar_identificador` | `usuarios.identificador` | `prestadores.cnpj` → `prestadores.id` → `unidades.unidade_id` (login.py:270) (duas hops) |
| Admin | identificador admin | — | `usuarios.identificador` | sem ownership de objeto clínico |
| Auditor | identificador auditor | — | `usuarios.identificador` | sem ownership de objeto clínico (passa em padrão D apenas) |

**Implicação para o helper:** o helper precisa distinguir entre **normalização de identidade** (`usuario["sub"]` → chave canônica) e **prova de vínculo institucional** (chave canônica → `unidade_id` via prestador). A primeira é trivial e candidata óbvia; a segunda exige join de duas hops para hospitalar e é o ponto onde a abstração tende a quebrar.

### §2.3 Inventário de chaves de identidade

| Tipo de ator | Campo no JWT (`usuario["sub"]`) | Normalizador | Tabela origem |
|---|---|---|---|
| Prescritor | CNS (15 dígitos) | `normalize_cns` | `prescritores.cns` |
| Paciente | CPF (11 dígitos) | `normalize_cpf` | `pacientes.cpf` |
| Dispensador ambulatorial | CNPJ (14 dígitos) | `_normalizar_identificador` (login.py:70) | `dispensadores.cnpj` |
| Dispensador hospitalar | CNPJ → `unidade_id` via prestador | normalização composta | `prestadores.unidade_id` |
| Admin | identificador admin | — | tabela própria (sem ownership de objeto) |

## §3 Critérios de decisão

Reestruturado a partir do parecer CODEX rodada 0: critérios baseados em **classe de operação** (correspondendo aos padrões A-E do §2.1), não em "≥ 4 dos 5 subdomínios" que era grosseiro porque os subdomínios têm pesos diferentes (circulação e hospitalar são semanticamente especiais).

### §3.1 Decisão por classe de operação

Para cada uma das 4 classes que aparecem nos sucessores, decidir independentemente se o helper se aplica:

1. **Leitura simples (padrões B + C)** — endpoints `GET` que confirmam ownership por JOIN com prescritor/prestador ou por comparação com row já carregado. **Critério para A:** helper cobre B e C com no máximo 2 parâmetros (tabela/coluna ou row-key), `roles_isentas` controlado por enum. Economia esperada: ≥ 60% das linhas de ownership dos endpoints `GET` dos 5 subdomínios.

2. **Mutação payload-vs-JWT (padrão A)** — endpoints `POST` onde o objeto ainda não existe e o check é declaração no payload vs JWT. **Critério para A:** helper pode oferecer `_assert_payload_matches_jwt(payload_field, sub, normalizer)` — mas é tão fino que talvez não justifique abstração. Em A, isso fica claro; em B (manter local), também.

3. **Matriz multi-owner (padrão D)** — endpoints onde múltiplos atores legítimos têm critério próprio (V5 custódia, V9 comprovante). **Critério para A:** helper precisa expressar matriz como dado (mapa role → predicado) sem virar DSL. Probabilidade de A: baixa. Auditor passa aqui, **não passa nos demais** — esse fato sozinho já justifica tratamento separado.

4. **Institucional org/unidade (subset de D, ampliado em hospitalar)** — endpoints onde a prova de vínculo exige duas hops via prestador. **Critério para A:** helper precisa suportar a tradução `CNPJ JWT → unidade_id`. Se exigir parâmetros específicos que não aparecem em B/C, sinaliza adaptador hospitalar separado — **C híbrido** com helper só para B+C e local para D-institucional.

### §3.2 Quando A (helper completo) é defensável

Todas as 4 classes acima cabem no helper com no máximo 2 parâmetros de variação **por classe** + roles_isentas declarado por enum. Sem builder, sem cascata de `if role == ...`. Economia agregada ≥ 50% no soma dos tickets A-E.

### §3.3 Quando B (manter local) é defensável

Pelo menos 2 das 4 classes exigem mais de 2 parâmetros, OU a classe D-institucional não cabe sem adaptador dedicado. Helper único viraria builder. Refactor disfarçado de helper.

### §3.4 Quando C (helper mínimo) é defensável — caminho intermediário

Helper só para a parte comum aos padrões A/B/C (levantar 403 com estrutura padrão + considerar admin/auditor por enum) sem tentar abstrair a query de ownership. Cada router faz sua query e chama `_assert_or_403(condition, codigo, mensagem, roles_isentas=("admin",))`. Padrões D e E ficam locais. Simples, sem abstração prematura, economiza ~3 linhas por uso.

Este é, segundo o parecer CODEX rodada 0, o **cenário mais provável** — sem decisão antecipada, mas registrado como hipótese de trabalho.

### §3.5 Sobre `admin` e `auditor` — não são equivalentes

Importante distinguir no critério: `admin` passa em todos os 5 padrões (A/B/C/D/E) como bypass institucional. `auditor` passa **apenas em D** (V5 e V9) — e quase não aparece nos sucessores do 5C-bis (pedidos de exame, laudos, agendamentos, circulação, hospitalar). O helper, se vier, não pode tratar `roles_isentas=("admin", "auditor")` como default global — precisa ser declarado por uso.

## §4 Output esperado

Documento em `backend/docs/decisoes/ADR-002-helper-ownership-5c-bis.md` (fechada em 2026-05-30) com:

- §1 Resumo da decisão (1 parágrafo)
- §2 Material analisado — incluir **commit analisado** (`5db20ef` ou o HEAD vigente quando a ADR for redigida) e lista curta dos arquivos lidos (mínimo: os 5 routers do escopo + os 5 do 5C como base comparativa). Isso deixa a decisão auditável.
- §3 Opções consideradas (A, B, C — sendo C o caso intermediário descrito em §3.4 deste ticket)
- §4 Decisão e justificativa, declarando explicitamente para cada uma das 4 classes de operação (§3.1) qual caminho foi escolhido
- §5 Implicações para TICKET-5C-BIS-A (e demais)

Se opção A (helper completo): incluir assinatura proposta + 1 exemplo de uso em pedidos_exame.

Se opção B (manter local): incluir 1 frase resumindo o porquê + a quem reportar caso de borda em E.

Se opção C (helper mínimo): incluir assinatura do `_assert_or_403` + nota de que não inclui query.

**Pasta `backend/docs/decisoes/`:** ainda não existe no repo. A ADR-002 cria a pasta no próprio commit de decisão. **Não criar agora neste spike** — a pasta nasce com a primeira ADR registrada como arquivo. Nota explicativa no topo da ADR-002 deve mencionar que **ADR-001 não está registrada como arquivo separado** — está embutida no relatório/ticket 4E-2 ([[picsaude_estado_2026_05_22]] confirma). ADR-002 é a primeira ADR em formato arquivo.

## §5 Anti-escopo

- **NÃO implementar o helper neste ticket.** Output é só a decisão.
- **NÃO refatorar o 5C** já em produção. Mesmo se a decisão for A, o 5C atual fica como está — não há valor em refatorar código auditado e em produção. Risco sem retorno para o deploy. Helper, se vier, entra fresco no TICKET-5C-BIS-A. (Confirmado por CODEX rodada 0.)
- **NÃO ampliar para outros padrões transversais** (ex: error handling genérico, logging de auditoria, rate limit). Foco estrito em ownership.
- **NÃO mudar contratos de API.** Erro 403 mantém formato atual `{codigo, mensagem}` independente da decisão.
- **NÃO incluir `pacientes.py` no escopo.** O endpoint `GET /pacientes/me` está correto (CPF do JWT). O endpoint `GET /pacientes/{cpf}/carteira` é information disclosure (LGPD/UX), não ownership clínico — ticket próprio menor pós-5C-bis, conforme decisão de 2026-05-26.

## §6 Classe, volume, ritmo

- **Classe:** `docs` (artefato de decisão; toca apenas `backend/docs/decisoes/ADR-002-*.md`).
- **Volume:** ~150 linhas em 1 arquivo.
- **Ritmo:** Regra 3. CODEX pode ser consultado se decisão A propor assinatura concreta (rodada 0 sobre a assinatura, antes de virar base do TICKET-A) — mas o spike em si não precisa de CODEX rodada 1.
- **Predecessor:** Etapa 6 fechada formalmente (push 9eb7228 + CODEX rodada 3 + §11 do TICKET-6).

## §7 Quem participa

- **Arquiteto** (Opus 4.7): redige o spike, lê os 5 routers, mapeia padrões, escreve ADR-002.
- **Code** (VS Code): consultivo. Pode rodar `grep` cruzado e validar se a assinatura proposta sobrevive a 1 uso experimental em `pedidos_exame.py` (sem commit — só checagem mental).
- **CODEX**: opcional. Convidar se decisão A propor assinatura concreta — para revisar antes do TICKET-5C-BIS-A.
- **Extensionistas**: primeira atividade compartilhada da extensão na semana 1. Eles acompanham a leitura do código, discutem semântica de ownership por subdomínio (quem é "dono" de um laudo? do ponto de vista clínico, sanitário, regulatório?), e participam da decisão A/B/C com perspectiva de domínio.

## §8 Marco de fechamento

ADR-002 mergeada em `main` → TICKET-5C-BIS-A é redigido com base na decisão tomada. Se A: helper entra como predecessora do A. Se B/C: cada subdomínio segue padrão local + nota inline citando ADR-002.

## §10 Observações CODEX rodada 0 (2026-05-26) — integradas

CODEX revisou o spike v0.1 sob o briefing `PROMPT-CODEX-5C-BIS-0.md` (Arquiteto, 2026-05-26) e retornou **0 P1 + 6 P2 + 4 P3**. Aprovado com ajustes. Achado central de método: separar **normalização de identidade** (`usuario["sub"]` → chave canônica) de **prova de vínculo institucional** (chave canônica → `unidade_id` via prestador). Sem essa separação, a opção A pode parecer limpa no papel e quebrar exatamente no E hospitalar.

| # | Severidade | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | P2 | §2.1 incompleto/defasado: V2 ausente; HEAD `01c67fa` stale (real = `5db20ef`); V6/V10 linhas defasadas (282 → 346/517); falta reclassificar por padrões, não endpoints | ✅ Aceito integral | §2.1 reescrito por padrões A/B/C/D/E; HEAD atualizado; V2 incluído; linhas V6/V10 corrigidas |
| 2 | P2 | §2.2 precisa mais dimensões (captura/descarta `_`; tipo de vínculo; granularidade; check antes de side effect) — críticas em circulação e hospitalar | ✅ Aceito integral | §2.2 expandido de 3 para 7 dimensões |
| 3 | P2 | §2.3 com erro de origem: JWT vem de `usuarios.identificador`, não `dispensadores.cnpj`; vínculo hospitalar é duas hops via `prestadores.cnpj → unidades.unidade_id` | ✅ Aceito integral | §2.3 reescrito com origem real do JWT + tradução para entidade clínica + duas hops para hospitalar; implicação para helper explicitada |
| 4 | P2 | §3 ainda deixa A fácil de parecer objetiva ("≥ 4 dos 5 subdomínios" é grosseiro); circulação e hospitalar são especiais; `admin` ≠ `auditor` (auditor passa em V5/V9, quase ausente nos sucessores) | ✅ Aceito integral | §3 reestruturado em critérios por classe de operação (§3.1) + §3.5 sobre admin vs auditor |
| 5 | P2 | §4 aponta para `backend/docs/decisoes/` que não existe; ADR-002 deve criar a pasta; ADR-001 está embutida no relatório 4E-2, não como arquivo | ✅ Aceito integral | §4 ampliado com nota explicativa; "criar pasta no próprio commit da ADR-002"; ADR-001 referenciada |
| 6 | P2 | §5 anti-escopo correto: não refatorar 5C mesmo se A vencer (risco sem retorno) | ✅ Confirmado integral | §5 reforçado com a justificativa explícita do CODEX |
| 7 | P3 | §1 dizia "4 tickets seguintes" — são 5 | ✅ Aceito | §1 corrigido para "5 tickets seguintes (A/B/C/D/E)" |
| 8 | P3 | §2.2 "prestador que executa (CNPJ)" impreciso — pedidos usa `cnpj_prestador`, agendamentos/circulação usam `org_id` + `unidade_id` | ✅ Aceito | §2.2 dimensão 2 reescrita com chaves precisas por subdomínio |
| 9 | P3 | `pacientes.py` vale citar como fora de escopo conhecido: `/me` correto, `/{cpf}/carteira` é privacidade/UX (ticket #51) | ✅ Aceito | §5 ampliado com `pacientes.py` em anti-escopo explícito |
| 10 | P3 | ADR-002 deve incluir "commit analisado: `5db20ef`" + lista curta dos arquivos lidos para auditabilidade | ✅ Aceito | §4 atualizado: "incluir commit analisado e lista curta dos arquivos lidos" |

**Conclusão CODEX:** estrutura do spike é boa; ajuste principal é endurecer o inventário e separar normalização de identidade de prova de vínculo institucional. Sem isso, A parece limpa no papel e quebra em E hospitalar. Cenário hoje mais provável, sem decidir ainda: **C — `_assert_or_403` compartilhado + queries locais de ownership**. Registrado como hipótese de trabalho em §3.4.

---

*Spike v0.2 — 2026-05-26 após CODEX rodada 0 integrada.*

---

## §11 Status final — SPIKE FECHADO (2026-05-30)

✅ **Fechado em [ADR-002-helper-ownership-5c-bis.md](../decisoes/ADR-002-helper-ownership-5c-bis.md).**

- **Decisão:** **Opção C estendida** — três helpers compartilhados (`_assert_or_403`, `_normalizar_identidade_jwt` em `utils/helpers.py`; `_unidade_id_do_dispensador` em `auth/ownership.py` novo, usado só pelo TICKET-E hospitalar).
- **Justificativa central:** 8 chaves de identidade distintas confirmadas na leitura dos 5 routers (commit `43664f4`). Helper completo (opção A) não cabe; manter local sem nenhum helper (opção B) reabre risco de drift no formato `{codigo, mensagem}` do 403. A opção C minimal foi estendida com 2 helpers mínimos que isolam **identidade pura** de **vínculo institucional** — correção principal do achado #4 do CODEX rodada 0 do spike.
- **Gatilho CODEX rodada 0 sobre a ADR:** **não dispara** (§6 do spike previa rodada 0 só para opção A com assinatura concreta; opção C não dispara).
- **Próximo gatilho CODEX:** rodada 1 sobre a spec do TICKET-5C-BIS-A (será >100 linhas, classe `core`, gatilho obrigatório do guard-rail da calibração 2026-05-28).
- **Vinculante para:** TICKET-5C-BIS-A/B/C/D/E. Não revisitar (§1 do spike).
- **Leitura realizada:** 5 routers (`pedidos_exame.py`, `laudos.py`, `agendamentos.py`, `circulacao_diagnostica.py`, `hospitalares.py`) — 39 endpoints reais (vs 30 estimados no PLANO), 30 dos quais com gap de ownership. Detalhes na §1.1 da ADR-002.

*Status final registrado pelo Engenheiro-Arquiteto sob calibração 2026-05-28.*
