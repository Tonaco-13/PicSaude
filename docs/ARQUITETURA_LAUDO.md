# PicSaúde — Arquitetura do Módulo de Laudo

> **Ticket 19 — Arquitetura (pré-implementação)**
> Este documento aplica o checklist de `docs/NUCLEO_SANITARIO.md` ao objeto Laudo,
> identifica conformidades, exceções e o que o laudo revela sobre o núcleo.

---

## O que é um Laudo no PicSaúde

O laudo é um **artefato clínico produzido**, não uma ordem. Essa é a distinção arquitetural mais importante em relação a prescrições e pedidos de exame.

| Dimensão | Prescrição | Pedido de Exame | Laudo |
|---|---|---|---|
| Natureza | Ordem de tratamento | Ordem de investigação | Resultado interpretado |
| Quem origina | Prescritor (médico) | Prescritor (médico) | Prestador (lab / patologista) |
| Direção da custódia | médico → paciente → farmácia | médico → paciente → lab | lab → paciente / médico |
| Conteúdo | O que fazer | O que investigar | O que foi encontrado |
| Validade clínica | Prazo para dispensação | Prazo para coleta | Prazo de referência do resultado |

Esta diferença **não quebra o núcleo** — ela revela que o núcleo é mais robusto do que parecía: a custódia é suficientemente genérica para suportar tanto ordens quanto artefatos.

---

## Relação com o Pedido de Exame

O laudo pode — mas não precisa — ser vinculado a um pedido de exame digital:

```
Caso A (fluxo digital completo):
  pedido_exame (emitido → coletado → resultado_disponivel)
      └── laudo (em_producao → assinado → liberado → encerrado)

Caso B (laudo standalone — exame externo ou físico):
  laudo (em_producao → assinado → liberado → encerrado)
  pedido_id = NULL
```

**Decisão MVP:** `pedido_id` é nullable. O laudo funciona de forma autônoma. A vinculação com o pedido é referencial, não estrutural.

---

## Máquina de Estados

### Status do Laudo (`laudos.status`)

```
em_producao          ← laudo em elaboração pelo responsável técnico
assinado             ← laudo assinado (responsável técnico declarou)    [pode ser terminal futuro]
liberado             ← laudo liberado para acesso do paciente/prescritor
ciencia_paciente     ← paciente registrou ciência do resultado
ciencia_prescritor   ← prescritor solicitante registrou ciência clínica
encerrado            ← todas as ciências pertinentes registradas        [TERMINAL]
cancelado            ← cancelado antes da liberação                     [TERMINAL]
expirado             ← resultado não acessado dentro do prazo           [TERMINAL]
encerrado_fisico     ← laudo emitido exclusivamente em papel            [TERMINAL]
```

**Estados terminais:** `encerrado · cancelado · expirado · encerrado_fisico`

### Status do Item do Laudo (`laudo_itens.status_item`)

Cada item corresponde a um exame interpretado dentro do laudo.

```
em_producao          ← resultado individual em elaboração
concluido            ← resultado do item pronto (não requer ciência separada por item no MVP)
cancelado            ← item cancelado                                   [TERMINAL]
encerrado_fisico     ← fluxo físico                                     [TERMINAL]
```

> **Nota MVP:** A ciência (paciente e prescritor) opera no nível do laudo inteiro, não por item. Isso simplifica o fluxo sem perder rastreabilidade. Em v2, ciência por item pode ser adicionada para laudos multidisciplinares.

### Transições do Laudo

```
em_producao → assinado       (responsável assina)
em_producao → cancelado      (cancelado antes de assinar)
assinado    → liberado        (liberação para acesso)
assinado    → cancelado       (cancelado após assinatura, antes de liberar)
liberado    → ciencia_paciente
liberado    → ciencia_prescritor
ciencia_paciente → ciencia_prescritor
ciencia_prescritor → ciencia_paciente
ciencia_paciente → encerrado  (quando prescritor também já deu ciência)
ciencia_prescritor → encerrado (quando paciente também já deu ciência)
liberado    → encerrado       (se apenas uma ciência for exigida — configurável)
qualquer    → expirado        (scheduler)
```

> **Sobre derivação de status:** diferente de prescrições e exames, o laudo não usa `derivar_status_laudo(status_itens)` porque a ciência opera no nível do objeto, não dos itens. O status do laudo é transitado diretamente. Essa é uma exceção legítima ao padrão do núcleo — documentada em seção própria abaixo.

---

## Custódia

### Cadeia de custódia do laudo

```
prestador_exame  →  paciente          (liberação do laudo)
paciente         →  prescritor        (encaminhamento clínico — opcional)
prestador_exame  →  prescritor        (retorno clínico direto — bypass do paciente)
```

**Diferença fundamental em relação à prescrição e ao exame:**
A custódia do laudo começa no prestador, não no prescritor. O prestador é o **produtor** do objeto sanitário, não o receptor.

Essa inversão é suportada pelo modelo de custódia existente (que usa campos `de` e `para` como texto) sem necessidade de alteração estrutural.

### Tabela `laudo_custodia`

```sql
id              INTEGER PRIMARY KEY
laudo_id        INTEGER REFERENCES laudos(id)
item_id         INTEGER REFERENCES laudo_itens(id)  -- NULL = laudo inteiro
de              TEXT NOT NULL   -- ex: 'prestador', CNPJ do lab
para            TEXT NOT NULL   -- ex: 'paciente', CNS do prescritor
transferido_em  DATETIME
dados_json      TEXT
```

---

## Ledger de Eventos

### Vocabulário de eventos (`EVENTOS_LAUDO`)

```
laudo_criado              ← laudo iniciado no sistema pelo prestador
laudo_assinado            ← responsável técnico declarou assinatura
laudo_liberado            ← laudo liberado para acesso
ciencia_paciente          ← paciente registrou ciência
ciencia_prescritor        ← prescritor registrou ciência clínica
laudo_encerrado           ← ciclo completo
laudo_cancelado           ← cancelamento
laudo_expirado            ← validade ultrapassada
laudo_impresso            ← fluxo físico — ato de impressão
encerrado_localmente      ← fluxo físico — estado terminal (padrão do núcleo)
custodia_transferida      ← qualquer transferência de posse
laudo_corrigido           ← derivação por correção (novo laudo com origem_laudo_id)
laudo_aberto_paciente     ← cidadão abriu o laudo (ENG-014; carimba laudos.aberto_em)
```

### Abertura pelo cidadão — `POST /laudos/{protocolo}/abrir` (ENG-014)

> **Martelo do Fabiano, 20/08: "abrir o laudo = dar ciência".**

O evento nomeia a **abertura**, que é o fato real; a **ciência é consequência
DERIVADA**, declarada como regra. O ledger fica honesto — *abriu em X → ciência
derivada da abertura* —, nunca uma "ciência" anunciando fato que não ocorreu
(a lição do `pedido_agendado` fantasma, J.7).

- **Papel:** `paciente` dono (404 → 403 → 422, anti-leak #52). **Nunca em `GET`**:
  ato escreve ledger por `POST` explícito.
- **Idempotente:** a segunda abertura responde 200 e **não emite nada** — um
  fato, um evento (R2). `laudos.aberto_em` é o carimbo da primeira.
- **Composição, não duplicação:** em `liberado` deriva `ciencia_paciente`; em
  `ciencia_prescritor` as duas ciências fecham o laudo (`encerrado`). Em
  `ciencia_paciente`/`encerrado`, só o fato da leitura.
- **Máquina de estados: mudança nenhuma.** `liberado → ciencia_paciente` já era
  aresta válida — isto é um CAMINHO NOVO para uma transição existente.
- **Não há botão "Dar ciência"** na carteira: ele era clique morto.

**`aberto_em` é informativo, nunca gatilho** (martelo (b)): o faturamento segue
ancorado na liberação — fato da unidade. A leitura é comportamento do cidadão e
não move dinheiro. O campo alimenta o selo "Lido em" do Histórico da clínica —
a confirmação rastreada vive na LEITURA, porque não há push antes do G4A.

---

## Documento Canônico + Hash

### Estrutura do documento canônico do laudo

```json
{
  "protocolo":            "<UUID>",
  "responsavel_cns":      "<CNS do responsável técnico>",
  "paciente_cpf":         "<CPF>",
  "pedido_protocolo":     "<UUID do pedido | null>",
  "data_emissao":         "<ISO 8601>",
  "data_validade":        "<ISO 8601>",
  "itens": [
    {
      "nome_exame":         "<nome>",
      "resultado_resumo":   "<texto interpretativo>",
      "valor_referencia":   "<opcional>",
      "conclusao":          "<normal | alterado | indeterminado>"
    }
  ],
  "versao_esquema": "1"
}
```

**Diferença em relação à prescrição:** o documento usa `responsavel_cns` em vez de `prescritor_cns` — o autor é o responsável técnico pelo laudo (patologista, bioquímico, médico).

---

## Entidades do Domínio

### Tabela `laudos` (objeto principal)

```sql
id                    INTEGER PRIMARY KEY
protocolo             TEXT UNIQUE NOT NULL
responsavel_id        INTEGER REFERENCES prescritores(id)  -- técnico responsável
paciente_id           INTEGER REFERENCES pacientes(id)
pedido_id             INTEGER REFERENCES pedidos_exame(id)  -- nullable
status                TEXT NOT NULL DEFAULT 'em_producao'
tipo_emissao          TEXT NOT NULL DEFAULT 'novo'
origem_laudo_id       INTEGER REFERENCES laudos(id)
data_emissao          TEXT NOT NULL
data_validade         TEXT
assinatura_hash       TEXT
criado_em             DATETIME DEFAULT (datetime('now'))
```

### Tabela `laudo_itens`

```sql
id                    INTEGER PRIMARY KEY
laudo_id              INTEGER NOT NULL REFERENCES laudos(id)
nome_exame            TEXT NOT NULL
codigo_tuss           TEXT
resultado_resumo      TEXT
conclusao             TEXT   -- normal | alterado | indeterminado | inconclusivo
valor_referencia      TEXT
resultado_url         TEXT   -- arquivo do laudo (PDF externo, DICOM, etc.)
status_item           TEXT NOT NULL DEFAULT 'em_producao'
criado_em             DATETIME DEFAULT (datetime('now'))
```

### Tabelas de infraestrutura (padrão do núcleo)

```
laudo_eventos         id, laudo_id, tipo_evento, dados_json, criado_em
laudo_custodia        id, laudo_id, item_id, de, para, transferido_em, dados_json
```

---

## Endpoints

### Fluxo do prestador (produção do laudo)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/laudos` | Criar laudo (emissão digital pelo prestador) |
| POST | `/laudos/fisica` | Emissão exclusivamente física |
| POST | `/laudos/{proto}/assinar` | Responsável declara assinatura |
| POST | `/laudos/{proto}/liberar` | Liberação para acesso do paciente/prescritor |
| POST | `/laudos/{proto}/itens/{id}/resultado` | Registrar resultado individual de item |
| POST | `/laudos/{proto}/cancelar` | Cancelar laudo não liberado |

### Fluxo de ciência (paciente e prescritor)

| Método | Rota | Descrição |
|---|---|---|
| POST | `/laudos/{proto}/ciencia-paciente` | Paciente registra ciência |
| POST | `/laudos/{proto}/ciencia-prescritor` | Prescritor registra ciência clínica |
| POST | `/laudos/{proto}/encerrar` | Encerramento formal do ciclo |

### Consulta e documentação

| Método | Rota | Descrição |
|---|---|---|
| GET | `/laudos/{proto}` | Consulta completa com itens + eventos |
| GET | `/laudos/{proto}/custodia` | Histórico de custódia |
| GET | `/laudos/{proto}/pdf` | PDF institucional do laudo |
| GET | `/laudos/{proto}/qr` | QR Code → validação pública |
| GET | `/public/laudos/{proto}` | Validação pública (sem dados sensíveis) |
| GET | `/paciente/laudos` | Laudos do paciente autenticado |

---

## PDF Institucional

### Diferenças em relação à prescrição e ao exame

O PDF do laudo tem os mesmos blocos estruturais do núcleo, com ajustes de conteúdo:

| Bloco | Prescrição | Exame | Laudo |
|---|---|---|---|
| Badge | Tipo de assinatura | Prioridade (rotina/urgente) | Status (em produção / liberado) |
| Prescritor | ✓ | ✓ | Responsável técnico (CNS + CRM/CRF se disponível) |
| Paciente | ✓ | ✓ | ✓ |
| Conteúdo | Medicamentos + posologia | Exames solicitados | Resultados + conclusão por item |
| Identificação | protocolo, hash, validade | protocolo, hash, prioridade | protocolo, hash, referência do pedido |
| Assinatura | Linha física | Linha física | Linha física + campo "Responsável Técnico" |

---

## Produção do laudo pelo dispensador (unidade) em nome do RT

> Implementado no **Ticket C** (`core`, 2026-08-13). Esta seção existe para que o próximo
> desenvolvedor não leia o modelo como acidente.

### O problema

O laudo exige **Responsável Técnico com CNS** (patologista, bioquímico, médico laboratorista) — é
quem responde pelo conteúdo, por força da Resolução CFM 2.052/2013. Mas quem opera a tela do
laboratório (`clinica.html`) entra como `dispensador`, identificado pelo **CNPJ da unidade**. Os dois
fatos são verdadeiros ao mesmo tempo, e o modelo tem que acomodar ambos sem mentir sobre nenhum.

### O modelo

> **A unidade produz em nome do RT. O RT é sempre o autor. O CNPJ nunca vira autor.**

- O dispensador cria/assina/libera **declarando `cns_autor`**; o `autor_id` do laudo resolve para
  esse CNS. A unidade não se torna autora em nenhuma hipótese.
- **Ownership por posse, não por identidade nominal:** o dispensador só opera laudo vinculado a um
  pedido de exame sob sua **custódia ATUAL** (`pedido_exame_custodia`, `item_id IS NULL`, registro
  mais recente). Nada de custódia histórica — quem perdeu a posse do pedido perde o laudo junto.
- **Sem coluna nova, sem migração.** O direito é derivado de dado que já existia.

### Superfície

```
criar · assinar · liberar · encerrar · cancelar · GET · pdf · qr   → prescritor · admin · dispensador
ciencia-paciente · ciencia-prescritor · /laudos/fisica             → INALTERADOS
laudo standalone (pedido_id IS NULL)                               → prescritor · admin (403 ao dispensador)
```

Duas fronteiras que **não** se atravessa, e por quê:

1. **Ciência.** É ato de quem *recebe* o laudo — o cidadão (`ciencia-paciente`) ou o prescritor
   solicitante (`ciencia-prescritor`). Quem produziu não dá ciência por ninguém; seria o produtor
   atestando o próprio recebimento.
2. **Laudo standalone.** Sem pedido vinculado não existe custódia de onde derivar posse. Negar o
   dispensador ali é a resposta correta, não efeito colateral — por isso tem código próprio
   (`laudo_sem_pedido_vinculado`), distinto do 403 genérico de ownership.

### Auditoria — o ledger responde "foi a unidade ou o RT?"

| Evento | Campo | Para quê |
|---|---|---|
| `laudo_criado` | `produzido_por` · `produzido_por_cnpj` | Sem isso, laudo produzido pela unidade seria indistinguível de um digitado pelo próprio RT |
| `laudo_liberado` | `liberado_por` · `cnpj_prestador` | Quem entregou ao cidadão |
| `laudo_custodia` | `de = <CNPJ da unidade autenticada>` | O CNPJ vem do **JWT**, não do corpo da requisição — posse provada, não declarada. Se o payload mandasse, uma unidade poderia assinar a cadeia com o CNPJ de outra, e a cadeia deixaria de valer como prova |

**Guarda executável:** `backend/tests/integration/test_laudos_dispensador_autorizacao.py` (16 casos,
incluindo unidade A ≠ unidade B em todas as superfícies e custódia atual × histórica).

**Ver também:** `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` — onde a posse do laboratório termina e a
do cidadão começa.

---

## Fluxo bancada — o estado `em_analise`

> Implementado no **Ticket B** (`module`, 2026-08-13).

O item de exame percorre:

```
agendado → coletado → em_analise → resultado_disponivel
```

`em_analise` significa **"o material está na bancada do laboratório"**. O estado já existia no
contrato (`states_exame.py`: lista de estados, lista branca de transições e vocabulário de eventos),
mas era **fantasma** — nenhum endpoint o persistia, e o `/resultado` emitia o evento
`pedido_em_analise` como marco intermediário enquanto escrevia `resultado_disponivel` direto. O item
nunca repousava na bancada, e por isso não havia onde ancorar a produção do laudo.

| Aspecto | Valor |
|---|---|
| Endpoint | `POST /pedidos-exame/{proto}/itens/{id}/em-analise` |
| Papel | `dispensador` · `admin` — a bancada é da unidade; o prescritor não participa deste gesto |
| Entrada | `setor` (opcional, texto livre) |
| Evento | `pedido_em_analise` — `item_id`, `nome_exame`, `setor` |
| Efeito | Item → `em_analise`; status do pedido re-derivado |

### Fronteira LIMS — o guardrail desta seção

**O PicSaúde é a trilha sanitária, não o LIMS do laboratório.** `setor` é *work-area* leve, para
visibilidade operacional ("bancada de bioquímica"). **Não modelar** analisador, técnico, fila de
equipamento ou lote: roteamento interno é sistema do laboratório. No dia em que `setor` virar fila de
máquina, virou outro produto.

### Consequência na fila do laboratório

Item em `em_analise` permanece **acionável** (`dispensadores.py::_ESTADOS_ITEM_ACIONAVEL_LAB`).
Trabalho na bancada é trabalho pendente; sair da fila é privilégio de estado **terminal**. Sem isso,
o gesto "enviar à bancada" apagaria o pedido da tela no instante do clique.

**Ver também:** `docs/ARQUITETURA_EXAMES.md` — máquina de estados do item de exame.

---

## O que o Laudo Revela sobre o Núcleo

A aplicação do checklist do `NUCLEO_SANITARIO.md` ao laudo revelou **três pontos de refinamento** no núcleo. Nenhum quebra o contrato — todos o aperfeiçoam.

### Refinamento 1 — "prescritor_id" é na verdade "autor_id"

O checklist assume `prescritor_id` como FK do autor. No laudo, o autor é o responsável técnico (patologista, bioquímico, médico laboratorista), que pode ter um CNS diferente do prescritor solicitante.

**Decisão:** para o MVP, `responsavel_id` usa a mesma tabela `prescritores` (que é, na prática, uma tabela de profissionais de saúde com CNS). Em v2, a tabela pode ser renomeada para `profissionais_saude`.

**Atualização proposta ao NUCLEO_SANITARIO.md v1.1:**
> O campo `prescritor_id` representa o **autor** do objeto sanitário. Para laudos, o autor é o responsável técnico. A tabela `prescritores` serve como registro genérico de profissionais de saúde com CNS.

### Refinamento 2 — Derivação de status pode ser direta para laudos sem ciência por item

O núcleo define que o status do objeto é sempre derivado dos itens. O laudo tem uma exceção legítima: a ciência opera no nível do objeto, não por item. O status do laudo é controlado diretamente nos endpoints de ciência.

**Decisão:** aceitar esta exceção. O princípio continua válido para objetos que têm ciclo operacional por item (coleta, dispensação). Para o laudo, onde o item é apenas "resultado interpretado" sem transições operacionais independentes, a derivação por item adicionaria complexidade sem valor.

**Atualização proposta ao NUCLEO_SANITARIO.md v1.1:**
> A derivação de status via `derivar_status_{objeto}(status_itens)` é obrigatória quando os itens têm transições operacionais independentes (ex: coleta, dispensação). Para objetos cujas transições operam no nível do objeto inteiro (ex: ciência, assinatura), a transição direta é permitida — deve ser documentada explicitamente na arquitetura do módulo.

### Refinamento 3 — A custódia pode ter origem no prestador, não no prescritor

O núcleo documentou atores padrão com `prescritor → paciente` como ponto de partida. O laudo inverte: a custódia começa no prestador.

**Decisão:** sem alteração estrutural necessária. A custódia já usa texto livre em `de` e `para` — isso é uma característica de design, não uma limitação. O núcleo está correto. A documentação dos atores padrão será ampliada.

---

## Verificação do Checklist do Núcleo

| Item | Status | Observação |
|---|---|---|
| Tabela principal com `protocolo`, `status`, `tipo_emissao`, `origem_id`, `assinatura_hash` | ✅ | Conforme |
| Tabela de itens com `status_item` próprio | ✅ | `laudo_itens.status_item` |
| Tabela de eventos (ledger imutável) | ✅ | `laudo_eventos` |
| Tabela de custódia | ✅ | `laudo_custodia` |
| `domain/states_laudo.py` com estrutura obrigatória | ✅ | A implementar no Ticket 20 |
| Estados terminais explícitos (objeto + item) | ✅ | Documentados acima |
| Vocabulário de eventos documentado | ✅ | `EVENTOS_LAUDO` acima |
| `derivar_status_laudo()` | ⚠️ | Exceção aceita (seção "Refinamento 2") |
| `encerrado_fisico` e `cancelado` com semântica distinta | ✅ | Conforme |
| POST /laudos — emissão digital | ✅ | A implementar no Ticket 20 |
| POST /laudos/fisica — emissão física | ✅ | A implementar no Ticket 20 |
| GET /laudos/{proto}/pdf | ✅ | A implementar no Ticket 21 |
| GET /laudos/{proto}/qr | ✅ | A implementar no Ticket 21 |
| GET /public/laudos/{proto} — sem dados sensíveis | ✅ | A implementar no Ticket 21 |
| GET /paciente/laudos | ✅ | A implementar no Ticket 20 |
| JWT + RBAC em todos os endpoints privados | ✅ | Padrão existente |
| CPF sentinela tratado no PDF e na API | ✅ | Padrão existente |
| Emissão física sem cadeia de custódia | ✅ | Conforme |
| Estados adicionados ao CLAUDE.md seção 7 | ✅ | Ticket 19.3 |
| `states_laudo.py` em `models/__init__.py` e `init_tables.py` | ⏳ | Ticket 20 |
| Router registrado em `main.py` | ⏳ | Ticket 20 |

**Resultado:** 18/21 itens verificáveis agora (✅). 2 exceções documentadas. 3 itens aguardam implementação.

**Veredicto:** o laudo satisfaz o checklist do núcleo. As exceções revelam dois refinamentos legítimos para NUCLEO_SANITARIO.md v1.1.

---

## Sequência de Implementação

```
Ticket 20 — domain/states_laudo.py + models + emissão digital e física
            + POST /assinar + POST /liberar + POST /ciencia-*
            + GET /paciente/laudos

Ticket 21 — domain/pdf_laudo.py + GET /pdf + GET /qr
            + GET /public/laudos/{proto}
            + (opcional) vinculação com pedido_exame
```

---

## Referências

| Documento | Relevância |
|---|---|
| `docs/NUCLEO_SANITARIO.md` | Contrato que este documento aplica |
| `docs/ARQUITETURA_EXAMES.md` | Padrão arquitetural do segundo objeto |
| `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` | **Política de custódia clínica** — a custódia clínica do laudo é do cidadão; o laboratório retém rastro forense + mínimo legal do RT (RDC 302/2005, CFM 2.052/2013, LGPD). Complementa a seção "Custódia" acima dizendo onde a posse do laboratório **termina** |
| `backend/app/domain/states_exame.py` | Referência de implementação da máquina de estados |
| `backend/app/domain/pdf_pedido_exame.py` | Referência de implementação do PDF |
