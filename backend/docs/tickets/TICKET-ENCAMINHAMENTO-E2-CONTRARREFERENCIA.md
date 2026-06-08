# TICKET-ENCAMINHAMENTO-E2 — Contrarreferência (objeto sanitário derivado)

| Campo | Valor |
|---|---|
| **Status** | **Engatilhado (2026-06-08) — apto para revisão do CODEX (revisor até amanhã) + implementação solo.** |
| **Classe** | `module` — objeto derivado, gêmeo de `laudo` (↔ pedido_exame). Autor = prescritor de destino (CNS), reusa role `prescritor`; RBAC intacto. |
| **Origem** | `docs/ARQUITETURA_ENCAMINHAMENTO.md` §5/§6/§8 (Fork 3 = b, decidido). Continuação de E1 (#14, na main). |
| **Base** | `main` em `6303da7` (E1 + neutralização `/public/*` já mergeados). |
| **Gêmeo a espelhar** | `laudo` (objeto derivado: `autor_id`, `origem_laudo_id`, `assinatura_hash`, ledger+custódia próprios). |

---

## §1 Escopo

A **Contrarreferência** é o retorno clínico do profissional de destino — um **objeto sanitário
derivado** com protocolo próprio, autor próprio (o destino), documento canônico + hash próprios e
`origem_encaminhamento_id` apontando ao encaminhamento que o originou. Espelha **exatamente**
`laudo ↔ pedido_exame`.

**ENTRA (E2):**
- 3 models novos: `contrarreferencias` (+ `_eventos` ledger + `_custodia`) + migration + init SQLite.
- `POST /encaminhamentos/{proto}/contrarreferir` — o destino cria a contrarreferência derivada **e**
  transiciona o encaminhamento `atendido → contrarreferido` (o estado e a transição **já existem** na
  máquina de estados desde o E1 — este ticket só os alcança).
- `GET /contrarreferencias/{proto}` (ownership) · `/custodia` · `/pdf` · `/qr`.
- `GET /public/contrarreferencias/{proto}` — **NEUTRO desde o nascimento** (ver §6, lição do PR #15).
- Evento `contrarreferencia_registrada` nos **dois** ledgers (encaminhamento + contrarreferência, arch §8).

**NÃO ENTRA:** assinatura ICP-Brasil (fronteira R6); motor de regulação; destino-instituição
(CNPJ/`org_id` — gatilho `core`); correção/derivação da própria contrarreferência
(`origem_contrarreferencia_id` fica como coluna nullable preparada, sem endpoint de correção no MVP).

---

## §2 Decisões cravadas + 1 a decidir

**Cravadas (arch + E1):**
- Objeto derivado (Fork 3 = b); autor = `cns_destino`, role `prescritor`; custódia `destino → origem`;
  evento `contrarreferencia_registrada` duplo; parent vai a `contrarreferido` e depois `encerrado`
  (ciência da origem) pelo `/encerrar` que **já existe** no E1.

**A decidir (recomendação embutida) — máquina de estados da contrarreferência:**
> **Opção R (recomendada): mínima.** `registrada` (criação) · `cancelada` (terminal). A *ciência da
> origem* já é carregada pelo **parent** (`contrarreferido → encerrado` via `/encerrar`). Não duplicar
> semântica de ciência no objeto derivado no MVP.
>
> Opção L (espelho laudo): incluir `ciencia_origem` no próprio objeto (`registrada → ciencia_origem`).
> Mais fiel ao laudo, mas duplica a ciência que o parent já modela. **Recomendo R**; decidir na revisão.

---

## §3 Entidades (espelham `laudo*`)

### `contrarreferencias`
```
id (Integer PK) · protocolo (String(50) unique index)
autor_id (FK prescritores — o destino) · paciente_id (FK pacientes)
origem_encaminhamento_id (FK encaminhamentos.id, NOT NULL — o parent)
conteudo_clinico (Text — o retorno clínico; SENSÍVEL, nunca no público)
status (default 'registrada') · tipo_emissao (default 'novo')
origem_contrarreferencia_id (FK self, nullable — preparada p/ correção futura)
assinatura_hash (String(64), nullable) · data_emissao (String(10)) · criado_em (DateTime server_default)
```
### `contrarreferencia_eventos` (ledger imutável — INSERT-only)
```
id · contrarreferencia_id (FK) · tipo_evento · ator_tipo · ator_id · payload · instance_id · created_at
```
### `contrarreferencia_custodia`
```
id · contrarreferencia_id (FK) · item_id (nullable, sempre NULL — sem itens no MVP)
detentor_tipo · detentor_id · transferida_em · encerrada_em (nullable) · motivo · created_at
```
> ⚠️ **bool×integer ([[pg-gate-bool-integer-trap]]):** nenhuma coluna boolean aqui, mas vale a regra —
> e **rodar o gate PG nos caminhos 2xx** (o `/contrarreferir` é o write a exercitar). Registrar
> `contrarreferencia` no `_LEDGER_SCHEMA` de `domain/ledger.py` (como o E1 fez p/ `encaminhamento`):
> `coluna_fk=contrarreferencia_id · coluna_tipo=tipo_evento · coluna_data=created_at · tem_ator=True`.

---

## §4 Endpoint central — `POST /encaminhamentos/{proto}/contrarreferir`

`usuario=Depends(require_role("prescritor", "admin"))`. Payload: `{ conteudo_clinico: str }`.
Sequência (anti-leak 404 → 403 → 409):
1. `_get_encaminhamento_ou_404(proto)`.
2. **Ownership:** não-admin → `ident (CNS) == encaminhamento.cns_destino` senão **403**
   (`nao_e_dono_do_encaminhamento`). Só o destino contrarrefere.
3. **Estado:** `_validar_transicao(enc, "contrarreferido")` — exige `atendido`; senão **409**.
4. Cria `contrarreferencias` (protocolo UUID novo, `autor_id` = prescritor do `cns_destino` via JOIN/
   upsert do mesmo jeito do E1, `paciente_id` herdado do parent, `origem_encaminhamento_id` = enc.id,
   `conteudo_clinico`, `assinatura_hash` = SHA-256 do documento canônico §6, `data_emissao`).
5. Abre custódia da contrarreferência `destino → origem` (detentor inicial = origem? **decidir**:
   recomendo abrir já apontando a origem como detentor — o retorno "viaja de volta"; espelha a custódia
   do laudo `prestador → prescritor`).
6. Ledger **duplo**: `contrarreferencia_registrada` no ledger da contrarreferência **e** no do
   encaminhamento (arch §8 linha 207).
7. `UPDATE encaminhamentos SET status='contrarreferido'`.
8. Retorna `{ protocolo_contrarreferencia, protocolo_encaminhamento, status_encaminhamento }`.

> A ciência da origem permanece no parent: origem chama `/encaminhamentos/{proto}/encerrar`
> (`contrarreferido → encerrado`), endpoint **já existente** no E1. E2 não adiciona endpoint de ciência.

---

## §5 Ownership (reusa 5C-BIS / E1) — matriz
`admin` bypass; anti-leak 404 → 403 → 409. Resolvers idênticos aos do E1 (origem CNS via JOIN
prescritores; destino = `cns_destino`; paciente CPF via JOIN pacientes).

| Ação | Dono |
|---|---|
| `POST /encaminhamentos/{proto}/contrarreferir` | **destino** (`cns_destino`) |
| `GET /contrarreferencias/{proto}` · `/custodia` | **autor(destino) OU origem OU paciente** OU admin |
| `GET /contrarreferencias/{proto}/pdf` · `/qr` | mesmos da consulta |

---

## §6 Documento canônico + **público NEUTRO desde o nascimento** (lição PR #15)

- **Documento canônico próprio:** protocolo · CNS autor(destino) · CNS origem (do parent) · paciente ·
  `origem_encaminhamento_id` · `conteudo_clinico` · versão de esquema → SHA-256 em `assinatura_hash`.
  **NÃO toca** `domain/documento_canonico.py` global (R6).
- **`GET /public/contrarreferencias/{proto}` nasce NEUTRO** — devolve **somente**
  `protocolo · status · tipo_emissao`. **NUNCA** `conteudo_clinico` (é o dado mais sensível do módulo —
  o retorno clínico literal). Neutro **por construção**: o SQL do público **não projeta**
  `conteudo_clinico`. Docstring honesto. (Não repetir o vazamento que o #15 fechou nos outros quatro.)

---

## §7 Critérios de aceite (gate PG + SQLite)
1. **Contrarreferir feliz** — destino sobre encaminhamento `atendido` → 201; cria `contrarreferencias`
   (1 linha), custódia `destino→origem`, evento `contrarreferencia_registrada` **nos dois** ledgers,
   parent vira `contrarreferido`.
2. **Ownership** — origem tenta contrarreferir → 403; paciente → 403; outro prescritor → 403.
3. **Estado** — contrarreferir sobre `emitido`/`agendado` (não `atendido`) → 409 (anti-leak: 403 de
   não-destino **precede** 409).
4. **Ciência da origem** — após contrarreferir, origem `/encerrar` → `encerrado` (fluxo completo).
5. **GET ownership** — autor/origem/paciente 200; estranho 403; admin 200.
6. **Público NEUTRO** — `GET /public/contrarreferencias/{proto}` 200 **sem** `conteudo_clinico` (assert
   de ausência por nome **e** por valor semeado); 404 p/ inexistente.
7. **Convergência** — gate PG verde **nos 2xx**; SQLite verde.

CI: `tests/integration/test_contrarreferencias_autorizacao.py` (sufixo `autorizacao` entra na seleção)
+ suíte SQLite de fluxo.

---

## §8 NÃO toca
- `documento_canonico.py` global / assinatura / serialização (R6).
- Máquina de estados do encaminhamento (o `contrarreferido`/transições **já existem** — só alcançar).
- `GET /{proto}` e `/public/*` dos outros objetos (já neutralizados no #15).
- RBAC/auth — reusa role `prescritor`.

---

## §9 Forks
- **Resolvido (arch):** objeto derivado (b), autor=destino, custódia destino→origem, ledger duplo.
- **A decidir na revisão (§2):** estado da contrarreferência — **R (mínima `registrada·cancelada`)**
  recomendada vs L (espelho laudo com ciência própria).
- **Detalhe de implementação (§4.5):** detentor inicial da custódia (recomendo origem).

---

*Engatilhado sobre `6303da7`. Gêmeo: `laudo`. Lições embutidas: ownership-desde-o-nascimento (E1) +
público-neutro-desde-o-nascimento (#15) + gate-PG-nos-2xx ([[pg-gate-bool-integer-trap]]).
Apto para revisão do CODEX e implementação solo.*
