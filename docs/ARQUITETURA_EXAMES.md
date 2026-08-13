# Ticket 14 — Arquitetura do Módulo de Pedidos de Exame

> Documento oficial de arquitetura.
> Aprovado antes da implementação conforme princípio do CLAUDE.md (§7).
> Implementação inicia no Ticket 15.

---

## Decisão arquitetural central

O módulo de exames **reutiliza a infraestrutura de custódia do PicSaúde sem modificá-la**.
Novas tabelas, novo domínio, mesmo padrão. Isso é o teste real da generalidade arquitetural.

O que é reutilizado diretamente:
- Máquina de estados (padrão + estados terminais + ledger imutável)
- Custódia explícita e granular (`item_id NULL` = pedido inteiro; `item_id X` = exame específico)
- Documento canônico + hash SHA-256
- PDF institucional (novo template, mesma infraestrutura ReportLab)
- JWT + RBAC (`require_role`)
- Página pública de validação (rota GET sem autenticação)
- `tipo_emissao` + `origem_pedido_id` para cadeia de derivações

---

## Entidades

### `pedidos_exame`

```
id                    INTEGER PK
protocolo             TEXT UNIQUE NOT NULL      ← mesmo padrão da prescrição
prescritor_id         INTEGER FK → prescritores
paciente_id           INTEGER FK → pacientes
status                TEXT NOT NULL DEFAULT 'emitido'
tipo_emissao          TEXT NOT NULL DEFAULT 'novo'  ← novo | correcao | renovacao
origem_pedido_id      INTEGER FK → pedidos_exame   ← cadeia de derivação
prioridade            TEXT NOT NULL DEFAULT 'rotina'  ← rotina | urgente | urgentissimo
indicacao_clinica     TEXT                      ← justificativa clínica (exigida por alguns labs)
data_emissao          TEXT NOT NULL
data_validade         TEXT NOT NULL
assinatura_hash       TEXT                      ← hash SHA-256 do documento canônico
criado_em             DATETIME
```

### `pedido_exame_itens`

```
id                    INTEGER PK
pedido_id             INTEGER FK → pedidos_exame
nome_exame            TEXT NOT NULL             ← nome clínico (ex: "Hemograma Completo")
codigo_tuss           TEXT                      ← código TUSS (opcional, interoperabilidade)
codigo_sigtap         TEXT                      ← código SIGTAP/SUS (opcional)
status_item           TEXT NOT NULL DEFAULT 'pendente'
quantidade            INTEGER NOT NULL DEFAULT 1
resultado_resumo      TEXT                      ← texto curto do laudo
resultado_url         TEXT                      ← link/path para o arquivo completo
resultado_em          DATETIME
criado_em             DATETIME
```

> **Nota TUSS/SIGTAP:** campos opcionais no MVP para permitir interoperabilidade futura
> com operadoras de saúde e BNAFAR. Não são obrigatórios para emissão.

### `pedido_exame_eventos`  (ledger — imutável)

```
id                    INTEGER PK
pedido_id             INTEGER FK → pedidos_exame
tipo_evento           TEXT NOT NULL
dados_json            TEXT                      ← payload livre por evento
criado_em             DATETIME
```

### `pedido_exame_custodia`

```
id                    INTEGER PK
pedido_id             INTEGER FK → pedidos_exame
item_id               INTEGER FK → pedido_exame_itens  ← NULL = pedido inteiro
de                    TEXT NOT NULL             ← papel ou CNPJ
para                  TEXT NOT NULL
transferido_em        DATETIME
dados_json            TEXT
```

---

## Princípio de estado: item é autônomo, pedido é agregado

**O estado do pedido é sempre derivado dos estados dos itens — nunca o contrário.**

Um pedido pode ter simultaneamente:
- item A: `coletado`
- item B: `agendado`
- item C: `resultado_disponivel`

O pedido reflete o agregado: `em_analise` (estado mais avançado ativo).
Isso segue o mesmo padrão da dispensação parcial em prescrições.

Regra de derivação do status do pedido:
```
todos os itens encerrados/cancelados   → pedido = encerrado | cancelado
ao menos um resultado_disponivel       → pedido = resultado_disponivel
ao menos um em_analise                 → pedido = em_analise
ao menos um coletado                   → pedido = coletado
ao menos um agendado                   → pedido = agendado
caso contrário                         → pedido = emitido
```

---

## Máquina de Estados

### Status do Pedido (`pedidos_exame.status`)

```
emitido               ← pedido emitido digitalmente, em custódia do paciente
agendado              ← ao menos um item agendado com prestador
coletado              ← ao menos um item coletado
em_analise            ← laboratório processando
resultado_disponivel  ← ao menos um laudo disponível, aguarda ciência
encerrado             ← todos os itens ativos encerrados           [TERMINAL]
cancelado             ← cancelado pelo prescritor ou paciente      [TERMINAL]
expirado              ← data_validade ultrapassada                 [TERMINAL]
encerrado_fisico      ← emissão exclusivamente em papel            [TERMINAL]
```

**Estados terminais do pedido:** `encerrado · cancelado · expirado · encerrado_fisico`

### Status do Item (`pedido_exame_itens.status_item`)

```
pendente              ← estado inicial
agendado              ← item agendado
coletado              ← material do item coletado
em_analise            ← item em processamento
resultado_disponivel  ← laudo do item disponível                   [TERMINAL de fluxo normal]
encerrado             ← ciência registrada                         [TERMINAL]
cancelado             ← cancelado                                  [TERMINAL]
nao_realizado         ← coleta não ocorreu (ver nota)              [TERMINAL — reservado v2]
encerrado_fisico      ← fluxo físico, sem ciclo digital            [TERMINAL]
```

**Estados terminais do item:** `resultado_disponivel · encerrado · cancelado · nao_realizado · encerrado_fisico`

> **Nota — `nao_realizado` (reservado para v2, não implementado no MVP):**
> Cobre cenários frequentes que a prescrição não tem equivalente direto:
> - Paciente faltou ao agendamento
> - Preparo pré-exame inadequado (jejum não realizado, etc.)
> - Material biológico insuficiente ou hemolisado
> - Coleta recusada pelo paciente no momento
> - Equipamento indisponível
>
> Diferença de `cancelado`: cancelado = decisão clínica/administrativa antes da coleta.
> `nao_realizado` = falha ou impedimento operacional após agendamento confirmado.
> O item `nao_realizado` pode originar novo agendamento sem nova prescrição.

### Transições válidas — Pedido

```
emitido              → agendado | cancelado | expirado
agendado             → coletado | cancelado | expirado
coletado             → em_analise | cancelado
em_analise           → resultado_disponivel | cancelado
resultado_disponivel → encerrado | cancelado
encerrado            → (terminal)
cancelado            → (terminal)
expirado             → (terminal)
encerrado_fisico     → (terminal)
```

### Transições válidas — Item

```
pendente             → agendado | cancelado
agendado             → coletado | cancelado
coletado             → em_analise | cancelado
em_analise           → resultado_disponivel | cancelado
resultado_disponivel → encerrado | cancelado
encerrado            → (terminal)
cancelado            → (terminal)
encerrado_fisico     → (terminal)
```

---

## Custódia

### Cadeia de custódia padrão (fluxo digital)

```
prescritor  → paciente          (emissão digital)
paciente    → prestador_exame   (agendamento/apresentação na recepção)
prestador_exame → paciente      (laudo disponível)
prescritor  → prescritor        (retorno clínico — opcional)
```

> **Nota:** `prestador_exame` é identificado por CNPJ do estabelecimento CNES.
> Não existe separação entre "agendamento" e "laboratório" no MVP —
> o estabelecimento que agenda também realiza e emite o laudo.
> Separação futura possível: `prestador_agendador` → `prestador_laboratorio`.

### Transições de custódia permitidas

| De | Para | Quando |
|---|---|---|
| prescritor | paciente | Emissão digital |
| paciente | prestador_exame | Agendamento confirmado |
| prestador_exame | paciente | Resultado disponível |

### Fluxo físico

```
emitido_fisico
  → encerrado_fisico
     → itens: encerrado_fisico
```
- Sem cadeia de custódia digital
- Dois eventos no ledger: `pedido_impresso` + `encerrado_localmente`

---

## Vocabulário de Eventos (ledger)

```
pedido_emitido            ← emissão digital
pedido_impresso           ← fluxo físico — ato de impressão
encerrado_localmente      ← fluxo físico — status terminal (reuso do nome)
pedido_agendado           ← agendamento confirmado com prestador
pedido_coletado           ← coleta realizada
pedido_em_analise         ← laboratório iniciou processamento
resultado_registrado      ← laudo inserido no sistema pelo prestador
resultado_comunicado      ← paciente/prescritor notificado da disponibilidade
pedido_encerrado          ← ciência registrada (fluxo completo)
pedido_cancelado          ← cancelamento (qualquer fase)
pedido_expirado           ← validade ultrapassada
custodia_transferida      ← qualquer transferência de posse (reuso do nome)
pedido_corrigido          ← derivação por correção
```

---

## Documento Canônico

Mesma lógica da prescrição: objeto Python determinístico + SHA-256.

Campos do hash:
```python
{
  "protocolo":          str,
  "prescritor_cns":     str,
  "paciente_cpf":       str,     # '00000000000' para fluxo físico
  "data_emissao":       str,     # ISO 8601
  "data_validade":      str,
  "prioridade":         str,
  "indicacao_clinica":  str | None,
  "itens": [
    {
      "nome_exame":    str,
      "codigo_tuss":   str | None,
      "quantidade":    int,
    }
  ],
  "versao_esquema":     "1",
}
```

---

## Endpoints

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/pedidos-exame` | prescritor | Emissão digital |
| POST | `/pedidos-exame/fisica` | prescritor | Emissão física (fire-and-forget) |
| GET  | `/pedidos-exame/{proto}/documento` | — | Documento canônico + integridade |
| GET  | `/pedidos-exame/{proto}/pdf` | — | PDF do pedido |
| GET  | `/pedidos-exame/{proto}/validacao` | — | Validação pública (QR Code) |
| GET  | `/pedidos-exame/{proto}/custodia` | prescritor/paciente | Histórico de custódia |
| POST | `/pedidos-exame/{proto}/agendar` | prestador | Registrar agendamento |
| POST | `/pedidos-exame/{proto}/itens/{item_id}/coletar` | prestador | Registrar coleta (`agendado → coletado`) |
| POST | `/pedidos-exame/{proto}/itens/{item_id}/em-analise` | prestador | **Enviar à bancada** (`coletado → em_analise`), `setor` opcional — Ticket B |
| POST | `/pedidos-exame/{proto}/itens/{item_id}/resultado` | prestador | Registrar resultado do item (aceita `coletado` ou `em_analise`) |
| POST | `/pedidos-exame/{proto}/transferir-laboratorio` | paciente | Cidadão entrega a posse ao laboratório escolhido |
| POST | `/pedidos-exame/{proto}/encerrar` | paciente/prescritor | Ciência e encerramento |
| GET  | `/paciente/pedidos-exame` | paciente | Carteira: pedidos ativos + histórico |

> **Nota de precisão (2026-08-13):** as rotas de `coletar` e `resultado` estavam grafadas nesta
> tabela no formato de projeto (`/{proto}/coletar`, `/{proto}/resultado/{item_id}`); a implementação
> as expõe sob `/{proto}/itens/{item_id}/…`, porque **o item é a unidade operacional** (§ "Princípio
> de estado"). Corrigido junto com a entrada do `em-analise`, para a tabela não ensinar caminho que
> não existe.

### `em_analise` deixou de ser estado fantasma

Até o Ticket B, `em_analise` constava desta arquitetura e da lista branca de transições, mas
**nenhum endpoint o persistia**: o `/resultado` emitia o evento `pedido_em_analise` como marco e
escrevia `resultado_disponivel` direto. O endpoint `/em-analise` materializa a transição que este
documento já prometia. **Fronteira LIMS:** `setor` é *work-area* leve; roteamento interno
(analisador, técnico, fila de equipamento, lote) é o LIMS do laboratório, não o PicSaúde.
Ver `docs/ARQUITETURA_LAUDO.md` § "Fluxo bancada".

---

## Diferenças vs Prescrição (o que muda)

| Dimensão | Prescrição | Pedido de Exame |
|---|---|---|
| Evento terminal do fluxo | dispensação | resultado + ciência |
| Quem executa | dispensador (farmácia) | prestador_exame (lab/hospital) |
| Quantidade | `quantidade_dispensada` | sempre 1 por item (coleta/laudo) |
| Produto | medicamento (RENAME/DEF) | procedimento (TUSS/SIGTAP) |
| Campo extra | forma_farmaceutica, unidade | codigo_tuss, indicacao_clinica, prioridade |
| Devolução parcial | sim (itens independentes) | não (cancelamento por item) |
| Resultado | N/A | resultado_resumo + resultado_url |

---

## Resultado como artefato — separação futura

**No MVP (Tickets 14–17):** o resultado é registrado como atributo do item
(`resultado_resumo`, `resultado_url`, `resultado_em`). Simples e funcional.

**No futuro (v2+):** o laudo pode se tornar um objeto sanitário próprio,
seguindo o padrão generalizável do PicSaúde:

```
Laudo
  id, pedido_id, item_id
  status: produzido → assinado → liberado → ciência_paciente → ciência_prescritor
  hash documental próprio
  custódia: laboratorio → paciente | prescritor
```

Isso significa que a custódia do **pedido** e a custódia do **laudo** são cadeias distintas.
O pedido vai de `prescritor → paciente → prestador_exame`.
O laudo vai de `prestador_exame → paciente | prescritor`.

**Decisão MVP:** não criar tabela `laudos` agora. O resultado fica nos atributos do item.
A separação é arquitetada aqui para que a migração futura não quebre o modelo.

---

## O que NÃO entra no MVP (Tickets 14–17)

| Funcionalidade | Justificativa |
|---|---|
| Integração TISS/ANS (operadoras) | Requer credenciais; escopo regulatório diferente |
| Upload de arquivo de laudo | Infraestrutura de storage; não é SQLite simples |
| IA para sugestão de código TUSS | Depende da Fase IA-1 |
| Agendamento online com prestador | Requer cadastro de prestadores_exame; Ticket futuro |
| Notificação push de resultado | Requer FCM/APNS; fora do MVP |
| prestador_exame.html | Interface para laboratório; Ticket futuro (após 17) |

---

## Sequência de implementação

```
Ticket 14 — Arquitetura (este documento)          ← CONCLUÍDO após aprovação
Ticket 15 — Model + states + emissão digital
             domain/states_exame.py               ← espelha states.py
             models/pedido_exame.py
             models/pedido_exame_item.py
             models/pedido_exame_evento.py
             models/pedido_exame_custodia.py
             routers/pedidos_exame.py (POST emissão)
Ticket 16 — Custódia + fluxo (agendar/coletar/análise)
             routers/pedidos_exame.py (POST agendar, coletar)
             paciente: GET /paciente/pedidos-exame
Ticket 17 — Resultado
             POST /pedidos-exame/{proto}/resultado/{item_id}
             POST /pedidos-exame/{proto}/encerrar
             domain/pdf_pedido_exame.py (PDF)
             domain/documento_canonico_exame.py
             GET /pedidos-exame/{proto}/validacao (página pública)
```
