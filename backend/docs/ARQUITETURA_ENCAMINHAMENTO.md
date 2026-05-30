# PicSaúde — Arquitetura do Módulo de Encaminhamento (Referência / Contrarreferência)

| Campo | Valor |
|---|---|
| **Status** | Arquitetura (fase docs) — em paralelo ao 5C-BIS, sem disputar com a implementação |
| **Classe** | `module` (destino = CNS, reusa role `prescritor`; RBAC intacto — ver §12) |
| **Autor** | Engenheiro-Arquiteto (Code workspace), calibração 2026-05-28 |
| **Data** | 2026-05-30 |
| **Commit base da leitura** | `da93d45` (HEAD) — todo código/contrato citado foi LIDO neste commit |
| **Gêmeo estrutural** | `pedido_exame` (objeto + custódia que viaja) · `laudo` (o "retorno") |
| **Contrato obrigatório** | [NUCLEO_SANITARIO.md](../../docs/NUCLEO_SANITARIO.md) — checklist §11 respondido em §14 |
| **Ticket de implementação** | **a redigir só quando o 5C-BIS fechar** (§16) — para nascer já-autorizado com os helpers |

> **Convenção de honestidade:** **[VERIFICADO]** = lido em `da93d45`. **[PROPOSTA]** = decisão de
> design a validar/refinar — Fabiano decide. Esta é arquitetura para discussão, não spec congelada.

---

## §1 O que é o Encaminhamento

Encaminhamento é o objeto sanitário que move um paciente de um ponto de cuidado a outro: o prescritor
de origem encaminha o paciente a outro clínico (destino), que o atende e devolve uma
**contrarreferência** — o "retorno" clínico. É a referência↔contrarreferência do SUS.

**Por que é estratégico (não é só mais uma função):** encaminhamento/regulação é o processo de **maior
atrito e maior fila no SUS** — logo é o módulo que mais diretamente testa a tese fundadora do PicSaúde:
máquina de estados aberta de **circulação de objetos sanitários**, inspirada no Pix do BACEN (o
`protocolo` UUID é o análogo da "chave Pix"; a regulação ambulatorial seria o análogo das "rails de
liquidação"). [contexto registrado em memória do projeto; tese de Fabiano]

**Estruturalmente é gêmeo do `pedido_exame`** [VERIFICADO — `states_exame.py`, `ARQUITETURA_EXAMES.md`]:
emitido pelo prescritor, custódia que viaja (`prescritor → paciente → destino → paciente`), e tem um
"retorno" que espelha a relação `laudo ↔ pedido_exame` [VERIFICADO — `ARQUITETURA_LAUDO.md:25-39`].
**Mandato desta arquitetura: reusar o padrão, não inventar arquitetura nova.**

---

## §2 Nomenclatura — guard-rail anti-colisão (chapéu Conselheiro)

Dois conceitos parecidos no nome, **completamente distintos**, não podem ser confundidos:

| Nome canônico | O que é | Estado no repo |
|---|---|---|
| **Regulação assistencial** (ou *regulação ambulatorial*) | Fila / priorização / matching de vagas tipo SISREG. **FUTURO**, fora deste MVP. | Não existe. Entra só como **gancho** (estado `em_regulacao`, sem engine). |
| **Motor regulatório** | Regras **sanitárias** sobre substâncias: catálogo, retenção, alertas de prescrição. | **Existe** [VERIFICADO — git `e7ac454` "docs(motor-regulatorio)"]. Domínio totalmente diferente. |

**Regra:** nunca usar "motor regulatório" para falar de fila/regulação assistencial, nem vice-versa.
O estado `em_regulacao` deste módulo refere-se à **regulação assistencial** (gancho), não ao motor
regulatório de substâncias.

---

## §3 Decisões já fechadas por Fabiano (2026-05-30 — não reabrir)

1. **Escopo MVP** = objeto **Encaminhamento + Contrarreferência**. Classe `module`.
2. **Destino = Opção A** — outro clínico, identificado por **CNS**, **reusa o role `prescritor`**.
   RBAC permanece intacto (sem ator/papel novo). Contrarreferência é
   `prescritor(destino) → prescritor(origem)`.
3. **Fora de escopo nesta rodada:** motor de regulação assistencial (fila/priorização/matching). O
   estado `em_regulacao` entra **apenas como gancho** para o futuro, sem engine por trás.
   Destino-instituição (CNPJ/`org_id`) fica como extensão incremental posterior.

---

## §4 Máquina de Estados — `domain/states_encaminhamento.py` [PROPOSTA]

Espelha `states_exame.py` [VERIFICADO]. **Agregação proposta: `direto`** (estilo `laudo`, não
`por_itens`) — um encaminhamento é um ato clínico atômico (encaminhar a uma especialidade), e os
estados propostos por Fabiano são de objeto, não de item. Itens existem para conformidade do núcleo
(§6) e carregam a especialidade/motivo; multi-especialidade com progressão independente fica como
`por_itens` em v2. (Refinamento na linha do "Refinamento 2" do laudo, `ARQUITETURA_LAUDO.md:280`.)

### Status do Encaminhamento (`encaminhamentos.status`)
```
emitido         ← emissão digital pelo prescritor de origem
em_regulacao    ← [GANCHO] aguardando regulação assistencial; SEM engine no MVP (pode ser pulado)
agendado        ← destino marcou atendimento
atendido         ← paciente atendido pelo profissional de destino
contrarreferido ← destino devolveu a contrarreferência (ver Fork 3, §5)
encerrado       ← terminal — ciência da origem registrada, ciclo completo
cancelado       ← terminal — revogação clínica/administrativa (origem)
expirado        ← terminal — validade ultrapassada
negado          ← terminal — destino/regulação recusou o encaminhamento  [PROPOSTA, específico]
encerrado_fisico← terminal — emissão exclusivamente em papel
```

Estados terminais: `encerrado · cancelado · expirado · negado · encerrado_fisico`.
Obrigatórios do núcleo presentes [VERIFICADO — NUCLEO §3]: `encerrado · cancelado · expirado ·
encerrado_fisico`. O específico do domínio é `negado` (um encaminhamento pode ser recusado mesmo sem
engine de fila — registro manual).

### Transições propostas — Encaminhamento
```
emitido        → em_regulacao | agendado | cancelado | expirado | negado
em_regulacao   → agendado | negado | cancelado | expirado     (gancho; MVP pode ir direto a agendado)
agendado       → atendido | cancelado | expirado
atendido        → contrarreferido | encerrado | cancelado
contrarreferido→ encerrado | cancelado
encerrado | cancelado | expirado | negado | encerrado_fisico → (terminais)
```

### Item (`encaminhamento_itens.status_item`) — conformidade de núcleo, agregação `direto`
```
pendente · em_andamento · concluido · cancelado · encerrado_fisico
```
> No MVP o status do objeto é controlado nos endpoints (agregação `direto`, como o laudo). Itens
> guardam a especialidade/procedimento de destino. `derivar_status_encaminhamento()` existe para
> satisfazer o checklist, mas no MVP devolve o status já controlado no objeto.

---

## §5 Contrarreferência — Fork 3 [DECIDIDO por Fabiano em 2026-05-30 → opção (b)]

> **Decisão:** opção **(b) — objeto sanitário derivado** (recomendação aceita). A contrarreferência é
> um objeto próprio com `origem_encaminhamento_id`, espelhando `laudo↔pedido_exame`. As tabelas
> `contrarreferencias`(+`_eventos`,`_custodia`) integram o desenho (§6). Mantém classe `module`.

A contrarreferência é o retorno clínico do profissional de destino. Duas formas foram avaliadas:

### Opção (a) — evento leve + anexo no próprio encaminhamento
`contrarreferencia_registrada` no ledger + campos de texto/anexo em `encaminhamentos`. Mais leve, menos
tabelas. **Custo:** enterra um documento clínico (autor distinto, conteúdo próprio, momento próprio)
dentro do ledger de outro objeto, sem protocolo, hash, custódia ou validação independentes.

### Opção (b) — objeto sanitário derivado com `origem_encaminhamento_id`
A contrarreferência vira objeto próprio (protocolo UUID próprio, autor = prescritor de destino,
documento canônico + hash próprios, `origem_encaminhamento_id` apontando ao encaminhamento). Espelha
**exatamente** `laudo ↔ pedido_exame` [VERIFICADO — `ARQUITETURA_LAUDO.md:25-39, 185`].

### ✅ Recomendação: **opção (b)** — objeto derivado

Fundamentos:
1. **Fidelidade ao §1 (imutabilidade) do CLAUDE.md.** Uma contrarreferência é uma **nova asserção
   clínica de um novo autor** — deve ser um objeto novo imutável, não anexo/mutação do original.
   `origem_encaminhamento_id` é o mesmo mecanismo de `origem_prescricao_id`/`origem_laudo_id`.
2. **O gêmeo já existe.** `laudo↔pedido_exame` é isomórfico: objeto derivado, **autor diferente**
   (lá responsável técnico; aqui prescritor de destino, CNS ≠ CNS de origem), vínculo referencial via
   `origem_*_id` nullable. Reusar o padrão provado é o próprio mandato "gêmeo estrutural".
3. **Autoria e auditabilidade.** O laudo já revelou que `prescritor_id` é na verdade `autor_id`
   [VERIFICADO — `ARQUITETURA_LAUDO.md:271`]. Objeto derivado dá à contrarreferência autor, hash e
   linhagem de ledger próprios — auditável como ato clínico autônomo.
4. **Assinatura futura.** Quando a assinatura ICP-Brasil chegar, a contrarreferência (documento
   clínico) precisará de assinatura própria — `assinatura_hash` próprio só existe num objeto, não num
   payload de evento.
5. **Não reclassifica para `core`.** O autor da contrarreferência ainda é um `prescritor` (CNS) →
   RBAC intacto, segue `module` (§12).

**Custo aceito de (b):** ~3 tabelas a mais (`contrarreferencias` + `_eventos` + `_custodia`), mesmo
peso de qualquer objeto do núcleo. O estado `contrarreferido` do encaminhamento passa a significar
"existe uma contrarreferência derivada me referenciando" — análogo a `pedido_exame` virar
`resultado_disponivel` quando seu laudo é produzido.

> Se Fabiano priorizar superfície mínima de MVP, (a) é aceitável — mas a contrarreferência perde
> assinatura/validação independentes, o que contraria a tese de "circulação de objetos sanitários".

---

## §6 Entidades [PROPOSTA — padrão do núcleo]

### `encaminhamentos` (objeto principal)
```
id, protocolo (UUID), prescritor_id (autor/origem, FK), paciente_id (FK),
cns_destino (TEXT — o clínico de destino; Opção A),
especialidade_destino (TEXT/CBO), cid (TEXT, opcional), justificativa_clinica (TEXT),
status, tipo_emissao ('novo'|'correcao'|'fisico'),
origem_encaminhamento_id (FK self, nullable — correção/derivação),
assinatura_hash (SHA-256 do documento canônico), data_emissao, data_validade, criado_em
```
Conforme núcleo: `protocolo · status · tipo_emissao · origem_id · assinatura_hash` presentes.

### `encaminhamento_itens`
`status_item` próprio; carrega especialidade/procedimento de destino. Agregação `direto` no MVP (§4).

### `encaminhamento_eventos` (ledger imutável) e `encaminhamento_custodia`
Padrão idêntico ao do núcleo [VERIFICADO — NUCLEO §4 e §5].

### `contrarreferencias` (+ `_eventos`, `_custodia`) — objeto derivado [Fork 3 = (b), decidido]
```
id, protocolo (UUID), autor_id (prescritor de destino, FK), paciente_id,
origem_encaminhamento_id (FK → encaminhamentos.id, NOT NULL),
conteudo_clinico (TEXT), status, assinatura_hash, criado_em
```

---

## §7 Custódia (`encaminhamento_custodia`) [VERIFICADO — padrão NUCLEO §4]

Cadeia: `prescritor(origem) → paciente → profissional destino (CNS) → paciente`.
`para` recebe o CNS de destino no passo de apresentação ao destino. Granularidade `item_id NULL` =
encaminhamento inteiro. **Fluxo físico não gera custódia** (NUCLEO §4 invariante).

> **Lição já internalizada do 5C-BIS-A (§8.1/§8.4):** se a custódia de destino for usada para
> ownership, o CNS gravado em `para` deve ser **normalizado na escrita** (`normalize_cns`), e o
> ownership deve mirar a **custódia atual** (`item_id IS NULL ORDER BY id DESC`), não histórica.

---

## §8 Ledger — vocabulário de eventos (`EVENTOS_ENCAMINHAMENTO`) [PROPOSTA]
```
encaminhamento_emitido        ← emissão digital
encaminhamento_impresso       ← fluxo físico — ato de impressão
encerrado_localmente          ← fluxo físico — terminal (mesmo nome em todos os objetos)
custodia_transferida          ← qualquer transferência de posse
encaminhamento_em_regulacao   ← [gancho] entrou em regulação assistencial
encaminhamento_agendado       ← destino marcou atendimento
encaminhamento_atendido       ← atendimento realizado
contrarreferencia_registrada  ← retorno do destino (emite também no ledger do objeto derivado, §5)
encaminhamento_negado         ← recusa pelo destino/regulação
encaminhamento_encerrado      ← ciência da origem; ciclo completo
encaminhamento_cancelado      ← cancelamento (qualquer fase)
encaminhamento_expirado       ← validade ultrapassada
encaminhamento_corrigido      ← derivação por correção (origem_encaminhamento_id)
```
Obrigatórios do núcleo presentes [VERIFICADO — NUCLEO §5]: `_emitido · _impresso ·
encerrado_localmente · _cancelado · custodia_transferida`.

---

## §9 Ownership desde o nascimento (reusa o 5C-BIS-A) [PROPOSTA]

O encaminhamento **nasce já-autorizado** — não repete o gap que o 5C-BIS está fechando. Reusa os
helpers que o 5C-BIS-A introduz em `utils/helpers.py`: `_assert_or_403` e
`_normalizar_identidade_jwt` [referência: `TICKET-5C-BIS-A-PEDIDOS-EXAME.md`, em `da93d45`]. Seria o
**primeiro objeto a nascer com ownership** — prova o investimento nos helpers.

Matriz de ownership (Opção A — tudo por CNS, role `prescritor`; `admin` faz bypass):

| Ação | Quem é dono | Chave |
|---|---|---|
| Emitir | prescritor de **origem** | `payload.cns == JWT.sub` (padrão A do 5C-BIS-A) |
| Agendar / Atender | prescritor de **destino** | `JWT.sub == encaminhamento.cns_destino` |
| Registrar contrarreferência | prescritor de **destino** | `JWT.sub == cns_destino` |
| Consultar / dar ciência (encerrar) | origem **ou** destino | matriz (CNS origem via JOIN, ou cns_destino) |

Vocabulário de erro no estilo 5C (decisão de governança do 5C-BIS-A §6.3): `prescritor_mismatch`
(payload×JWT) e `nao_e_dono_do_encaminhamento` (ownership em GET/mutação).

---

## §10 Endpoints (padrão do checklist NUCLEO §11) [PROPOSTA]
```
POST /encaminhamentos                         emissão digital
POST /encaminhamentos/fisica                  emissão física (fire-and-forget)
GET  /encaminhamentos/{proto}                 consulta autenticada (ownership origem/destino/admin)
GET  /encaminhamentos/{proto}/custodia        histórico de custódia
POST /encaminhamentos/{proto}/agendar         destino marca atendimento
POST /encaminhamentos/{proto}/atender         destino registra atendimento
POST /encaminhamentos/{proto}/contrarreferir  destino devolve a contrarreferência
POST /encaminhamentos/{proto}/encerrar        ciência da origem
POST /encaminhamentos/{proto}/cancelar
GET  /encaminhamentos/{proto}/pdf             PDF institucional
GET  /encaminhamentos/{proto}/qr              QR → validação pública
GET  /public/encaminhamentos/{proto}          validação pública (sem dados sensíveis)
```
Todos os privados: JWT + RBAC + ownership inline (§9). O `contrarreferir` **cria o objeto derivado**
da contrarreferência (Fork 3 = (b), §5) e transiciona o encaminhamento a `contrarreferido`.

---

## §11 Documento canônico + hash [VERIFICADO — padrão NUCLEO §6]
Documento canônico do encaminhamento (protocolo, origem CNS, destino CNS, paciente, especialidade,
CID, justificativa, itens, versão de esquema) → SHA-256 em `assinatura_hash`. **Não toca**
`domain/documento_canonico.py` nem caminho de assinatura nesta fase (anti-escopo R6, igual ao 5C-BIS).

---

## §12 Classificação e guard-rails de governança

- **Classe `module` — CONFIRMADA.** Destino = CNS, reusa role `prescritor`, RBAC intacto. Não há ator
  novo, não há tabela de ledger com semântica nova além do padrão do núcleo.
- **Gatilho de reclassificação para `core` (PARE e escale):** se em algum momento o desenho exigir
  **destino = CNPJ/`org_id`** (instituição como destino, não um clínico), isso muda RBAC/escopo
  institucional → vira `core` (revisão central obrigatória, CLAUDE.md §10). Não improvisar: parar e
  reclassificar.
- **Anti-escopo R6:** nada aqui toca serialização canônica nem assinatura — confirmado.

---

## §13 O que NÃO entra no MVP
- Motor de **regulação assistencial** (fila SISREG-like, priorização, matching de vagas). `em_regulacao`
  é gancho sem engine.
- **Destino-instituição** (CNPJ/`org_id`) — extensão incremental futura (gatilho `core`, §12).
- Assinatura ICP-Brasil do encaminhamento/contrarreferência (mesma fronteira do 5C-BIS).

---

## §14 Checklist de conformidade — NUCLEO_SANITARIO §11 [VERIFICADO contra o contrato]

### Contrato de domínio
- [x] Máquina de estados em `domain/states_encaminhamento.py` — §4 (a criar na implementação)
- [x] Estados terminais explícitos (objeto + item) — §4
- [x] Vocabulário de eventos documentado — §8
- [x] `derivar_status_encaminhamento()` — §4 (agregação `direto` no MVP)
- [x] `encerrado_fisico` e `cancelado` com semântica distinta — §4 (regra NUCLEO §3 respeitada)

### Contrato de persistência
- [x] Tabela principal com `protocolo·status·tipo_emissao·origem_id·assinatura_hash` — §6
- [x] Tabela de itens com `status_item` próprio — §6
- [x] Tabela de eventos (ledger imutável) — §6/§8
- [x] Tabela de custódia — §6/§7

### Contrato de API
- [x] `POST /encaminhamentos` · `/fisica` · `GET /{proto}` · `/custodia` · `/pdf` · `/qr` ·
  `GET /public/...` — §10
- [ ] `GET /paciente/encaminhamentos` (carteira) — **pendente**: depende do desfecho do ticket de
  carteira do paciente (fora do 5C-bis; ver PLANO §carteira). Registrado, não bloqueia arquitetura.

### Contrato de segurança
- [x] JWT + RBAC + ownership inline em todos os privados — §9
- [x] Endpoint público sem autenticação e sem dados sensíveis — §10
- [x] CPF sentinela no fluxo físico — herda convenção CLAUDE.md §6a
- [x] Emissão física sem cadeia de custódia — §7

---

## §15 Sequenciamento
- **Arquitetura agora / em paralelo** ao 5C-BIS (classe docs, não disputa com a implementação em curso).
- **O ticket de implementação só é redigido quando o 5C-BIS fechar** — assim o encaminhamento já
  consome `_assert_or_403`/`_normalizar_identidade_jwt` prontos e estáveis. Não abrir implementação no
  meio do sweep de ownership (reabriria a superfície que o 5C-BIS está fechando).

---

## §16 Forks — estado

1. **Fork 3 (§5) — forma da contrarreferência. ✅ DECIDIDO por Fabiano (2026-05-30): opção (b)**,
   objeto derivado com `origem_encaminhamento_id`.

Ainda abertos (não bloqueiam a arquitetura; decidir na redação do ticket de implementação):
2. **Agregação (§4):** `direto` (recomendado, atômico) vs. `por_itens` (multi-especialidade v2).
3. **Estado `negado` (§4):** incluir já no MVP como terminal? (recomendo sim — recusa manual é real
   mesmo sem engine de fila).

---

## §17 Referências
- Contrato: [NUCLEO_SANITARIO.md](../../docs/NUCLEO_SANITARIO.md) (§11 respondido em §14)
- Gêmeos: [ARQUITETURA_EXAMES.md](../../docs/ARQUITETURA_EXAMES.md) · [ARQUITETURA_LAUDO.md](../../docs/ARQUITETURA_LAUDO.md)
- Estados de referência: `backend/app/domain/states_exame.py` [VERIFICADO]
- Ownership reusado: [TICKET-5C-BIS-A-PEDIDOS-EXAME.md](tickets/TICKET-5C-BIS-A-PEDIDOS-EXAME.md)
- Nomenclatura motor regulatório: git `e7ac454`
- Memória de projeto: módulo planejado (forks de design)

---

*Arquitetura redigida em 2026-05-30 sobre código/contratos lidos em `da93d45`. Classe docs, em
paralelo ao 5C-BIS. Fork 3 decidido (opção b); forks 2–3 do §16 ficam para o ticket de implementação,
que aguarda o fechamento do 5C-BIS.*
