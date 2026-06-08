# TICKET-ENCAMINHAMENTO-E1 — Objeto sanitário Encaminhamento (referência)

| Campo | Valor |
|---|---|
| **Status** | **Martelos de escopo cravados (Fabiano, 2026-06-08) — apto para rodada 1 do CODEX.** |
| **Classe** | `module` — novo objeto sanitário, gêmeo de `pedido_exame`. Destino = clínico (CNS), reusa role `prescritor`; RBAC intacto. Checklist NUCLEO §11 já respondido na arquitetura. |
| **Origem** | `docs/ARQUITETURA_ENCAMINHAMENTO.md` (30/05). Pré-condição §15 satisfeita: 5C-BIS fechado (A·B·C·C.1·D·E na main). |
| **Base** | `main` em `1a033e7`. |
| **Gêmeos a espelhar** | `pedido_exame` (objeto principal) · `laudo` (objeto derivado — será o molde do E2). |
| **Faseamento** | **E1 = objeto Encaminhamento (este ticket).** E2 = Contrarreferência derivada (`origem_encaminhamento_id`) + `POST /contrarreferir` — ticket seguinte. |

---

## §1 Escopo

**ENTRA (E1):** o objeto **Encaminhamento** completo e já-autorizado — emissão digital + física,
custódia, ledger, máquina de estados, ownership inline (reusa 5C-BIS), documento canônico + hash,
PDF, QR e validação pública. Espelha `pedido_exame` ponta a ponta.

**NÃO ENTRA (vai para E2):** a **Contrarreferência** como objeto derivado e o endpoint
`POST /encaminhamentos/{proto}/contrarreferir`. O estado `contrarreferido` é **definido** na máquina
de estados (contrato completo, forward-compat), mas **nenhum endpoint de E1 transiciona para ele** —
quem o aciona é o `/contrarreferir` do E2. Em E1, `atendido → encerrado` direto.

**NÃO ENTRA (MVP, herdado da arquitetura §13):** motor de regulação assistencial (`em_regulacao` é
gancho sem engine); destino-instituição (CNPJ/`org_id` — gatilho `core`, não improvisar); assinatura
ICP-Brasil (mesma fronteira R6 do 5C-BIS).

---

## §2 Decisões cravadas (não reabrir)

| # | Decisão | Quando |
|---|---|---|
| D1 | Escopo MVP = objeto + contrarreferência; **faseado** (E1 objeto, E2 contrarreferência) | 30/05 + **08/06** |
| D2 | Destino = clínico via **CNS**, reusa role `prescritor`. RBAC intacto | 30/05 |
| D3 | Contrarreferência = objeto derivado com `origem_encaminhamento_id` (Fork 3 = b) — **realizada no E2** | 30/05 |
| D4 | **Agregação `direto`** (atômico, estilo laudo) — status controlado no objeto | **08/06** |
| D5 | Estado **`negado`** incluído no MVP como terminal (recusa manual, sem engine) | **08/06** |

**Gatilho de reclassificação `core` (PARE e escale):** se o destino algum dia virar CNPJ/`org_id`
(instituição, não clínico), muda RBAC/escopo institucional → `core`. Não improvisar.

---

## §3 Máquina de estados — `domain/states_encaminhamento.py` (criar)

Espelha a estrutura de `states_exame.py` (constantes `frozenset` + `dict` de transições + helpers
`transicao_valida_*`, `eh_terminal_*`, `derivar_status_encaminhamento`).

### Encaminhamento (`encaminhamentos.status`)
```
emitido · em_regulacao · agendado · atendido · contrarreferido
encerrado · cancelado · expirado · negado · encerrado_fisico
```
Terminais: `encerrado · cancelado · expirado · negado · encerrado_fisico`.
(Núcleo NUCLEO §3 exige `encerrado·cancelado·expirado·encerrado_fisico`; `negado` é o específico — D5.)

### Transições (contrato completo; `contrarreferido` definido mas só alcançado no E2)
```
emitido        → em_regulacao | agendado | cancelado | expirado | negado
em_regulacao   → agendado | negado | cancelado | expirado      (gancho; MVP pode ir direto a agendado)
agendado       → atendido | cancelado | expirado
atendido       → contrarreferido | encerrado | cancelado       (→contrarreferido só via E2)
contrarreferido→ encerrado | cancelado
(terminais sem saída)
```

### Item (`encaminhamento_itens.status_item`) — agregação `direto` (D4)
```
pendente · em_andamento · concluido · cancelado · encerrado_fisico
```
> `derivar_status_encaminhamento()` existe para satisfazer o checklist do núcleo, mas no MVP
> **devolve o status já controlado no objeto** (passthrough — agregação direto, como o laudo). Itens
> carregam especialidade/procedimento de destino; progressão independente fica para `por_itens` (v2).

---

## §4 Entidades (criar 4 models + migration)

Espelham `pedido_exame*` (Integer PK autoincrement, `protocolo` String(50) unique index,
`assinatura_hash` String(64), datas ISO em String, `criado_em` DateTime server_default).

### `encaminhamentos`
```
id · protocolo (UUID) · prescritor_id (FK prescritores, autor/origem) · paciente_id (FK pacientes)
cns_destino (String — clínico de destino, D2) · especialidade_destino (String/CBO)
cid (String, nullable) · justificativa_clinica (Text)
status (default 'emitido') · tipo_emissao ('novo'|'correcao'|'fisico')
origem_encaminhamento_id (FK self, nullable — correção/derivação)
assinatura_hash (String(64), nullable) · data_emissao · data_validade · criado_em
```
### `encaminhamento_itens`
```
id · encaminhamento_id (FK) · especialidade (String) · procedimento (String, nullable)
motivo (Text, nullable) · status_item (default 'pendente')
```
### `encaminhamento_eventos` (ledger imutável — INSERT-only)
```
id · encaminhamento_id (FK) · tipo_evento · ator_tipo · ator_id · payload (JSON/Text)
instance_id · created_at
```
> Naming do campo de tipo: seguir o padrão do gêmeo `pedido_exame_evento` (verificar `tipo_evento`
> vs `evento` no model real e manter consistência — atenção ao outlier de naming registrado no
> backend/CLAUDE.md "Gotchas").
### `encaminhamento_custodia`
```
id · encaminhamento_id (FK) · item_id (nullable) · detentor_tipo · detentor_id
transferida_em · encerrada_em (nullable) · motivo · created_at
```
> ⚠️ **Bool×integer (memória do projeto):** qualquer coluna boolean usa `true`/bool nativo, nunca
> `0/1`. Rodar o **gate PG** nos caminhos 2xx — não confiar em verde só-SQLite (pegou C.1 e E).

---

## §5 Ledger — `EVENTOS_ENCAMINHAMENTO`
```
encaminhamento_emitido · encaminhamento_impresso (físico)
encaminhamento_em_regulacao · encaminhamento_agendado · encaminhamento_atendido
encaminhamento_encerrado · encaminhamento_cancelado · encaminhamento_negado
custodia_transferida
```
(`contrarreferencia_registrada` é do E2.) Ledger nunca recebe UPDATE/DELETE (CLAUDE.md §2).

---

## §6 Custódia (`encaminhamento_custodia`) — cadeia NUCLEO §4
```
prescritor(origem) → paciente → prescritor(destino) → paciente
```
- Emissão digital: abre custódia `prescritor(origem) → paciente`.
- Fluxo físico (`/fisica`): **sem custódia** (igual ao pedido_exame físico); itens `encerrado_fisico`;
  evento `encaminhamento_impresso`; CPF sentinela §6a quando paciente não identificado.

---

## §7 Ownership desde o nascimento (reusa 5C-BIS — `_assert_or_403` / `_normalizar_identidade_jwt`)

Captura `usuario=Depends(require_role(...))`; `(papel, ident) = _normalizar_identidade_jwt(usuario)`.
`admin` faz bypass. Anti-leak: **404 → 403 → 409/422**. Resolvers (JOIN, não denormalizado):

| Papel | ident | dono quando |
|---|---|---|
| `prescritor` (origem) | CNS | `ident == ` CNS de `prescritor_id` (JOIN prescritores) |
| `prescritor` (destino) | CNS | `ident == encaminhamentos.cns_destino` |
| `paciente` | CPF | `ident == ` CPF de `paciente_id` (JOIN pacientes) |

Matriz por endpoint:
- `POST /encaminhamentos` — emitente vira a origem (sem objeto prévio; valida que é `prescritor`).
- `GET /{proto}` · `/custodia` — **origem OU destino OU paciente** OU admin.
- `POST /agendar` · `/atender` — **somente destino** (`cns_destino`) ou admin.
- `POST /encerrar` — **somente origem** (ciência) ou admin.
- `POST /cancelar` — **somente origem** (revogação clínica) ou admin.

---

## §8 Endpoints (E1 — subconjunto sem `/contrarreferir`)
```
POST /encaminhamentos                    emissão digital
POST /encaminhamentos/fisica             emissão física (fire-and-forget)
GET  /encaminhamentos/{proto}            consulta (ownership origem/destino/paciente/admin)
GET  /encaminhamentos/{proto}/custodia   histórico de custódia
POST /encaminhamentos/{proto}/agendar    destino marca atendimento  (emitido|em_regulacao → agendado)
POST /encaminhamentos/{proto}/atender    destino registra atendimento (agendado → atendido)
POST /encaminhamentos/{proto}/encerrar   ciência da origem          (atendido → encerrado)
POST /encaminhamentos/{proto}/cancelar   revogação da origem        (→ cancelado)
GET  /encaminhamentos/{proto}/pdf        PDF institucional
GET  /encaminhamentos/{proto}/qr         QR → validação pública
GET  /public/encaminhamentos/{proto}     validação pública (sem dados sensíveis)
```
> `POST /encaminhamentos/{proto}/contrarreferir` e `GET /paciente/encaminhamentos` (carteira) → fora
> de E1 (E2 e ticket de carteira, respectivamente).

---

## §9 Documento canônico + hash
Documento canônico próprio (protocolo · CNS origem · CNS destino · paciente · especialidade · CID ·
justificativa · itens · versão de esquema) → SHA-256 em `assinatura_hash`. **NÃO toca**
`domain/documento_canonico.py` global nem caminho de assinatura (anti-escopo R6).

---

## §10 Persistência
- 4 models novos em `app/models/` → adicionar nomes a `init_tables.py` (SQLite) e rodar.
- **Migration Alembic** para a PG (espelha o padrão do pedido_exame; `down_revision` = head atual).
- Convergência SQLite↔PG verificada no gate (§11).

---

## §11 Critérios de aceite (gate PG + SQLite)
Espelha as suítes `test_*autorizacao.py` do 5C-BIS. Casos:
1. **Emissão digital** → 201; encaminhamento `emitido`, item `pendente`, custódia `origem→paciente`
   aberta, evento `encaminhamento_emitido` no ledger.
2. **Fluxo físico** `/fisica` → encerramento físico: itens `encerrado_fisico`, **sem custódia**,
   evento `encaminhamento_impresso`, CPF sentinela aceito.
3. **Ownership GET** — origem 200 · destino 200 · paciente 200 · outro prescritor 403 · outro
   paciente 403 · admin 200.
4. **agendar/atender** — destino (`cns_destino`) 200 · origem 403 · paciente 403 (só destino atua).
5. **encerrar/cancelar** — origem 200 · destino 403.
6. **Anti-leak** — não-dono sobre objeto em estado terminal → **403 antes** do 409.
7. **Transições inválidas** → 409 (ex.: `encerrar` de um `emitido`; `atender` de um `emitido`).
8. **`negado`** — origem/destino registra negação a partir de `emitido`/`em_regulacao` → terminal.
9. **Validação pública** `/public/...` sem auth não vaza dados sensíveis (sem CPF/CID em claro).
10. **Convergência** — gate PG verde **nos caminhos 2xx** (não só SQLite); suíte SQLite existente verde.

CI: a suíte nova entra como `test_encaminhamentos_autorizacao.py` (sufixo `autorizacao` é pego pela
seleção do gate) + uma suíte SQLite de fluxo.

---

## §12 NÃO toca (invariantes / anti-escopo)
- `domain/documento_canonico.py`, caminho de assinatura, serialização canônica (R6).
- Ledger de outros objetos; máquinas de estado existentes.
- RBAC/auth (`auth/`) — reusa role `prescritor`, sem ator novo.
- `prescricoes`/`pedidos_exame`/`laudos` (objetos vizinhos) — só referência conceitual.

---

## §13 Forks — estado
- **Resolvidos (08/06):** faseamento (E1/E2) · agregação `direto` (D4) · `negado` no MVP (D5).
- **Vai para E2:** objeto Contrarreferência derivado (`origem_encaminhamento_id`), `POST
  /contrarreferir`, transição `atendido → contrarreferido → encerrado`, evento
  `contrarreferencia_registrada`, documento canônico + hash próprios da contrarreferência.
- **Follow-up registrado (não bloqueia):** `GET /paciente/encaminhamentos` (carteira) — depende do
  ticket de carteira do paciente (arquitetura §14, item pendente).

---

*Sanity-read sobre `1a033e7` (5C-BIS fechado). Martelos D1/D4/D5 cravados por Fabiano em 2026-06-08.
Espelha `pedido_exame` (objeto) e prepara o molde `laudo` para o E2. Apto para rodada 1 do CODEX.*
