# Arquitetura do Atestado Médico (objeto sanitário)

> **Classificação:** `core`/`module` — novo objeto sanitário (nova tabela de ledger
> + máquina de estados). Exige revisão central (CLAUDE.md §10).
> **Status:** **implementado** (desenho validado por Fabiano 2026-06-23 — CPF do
> paciente obrigatório no digital). Aguarda revisão central no PR.
> **Conformidade:** segue o contrato de `docs/NUCLEO_SANITARIO.md` (§11).

---

## 1. O que é

O atestado médico passa de **rascunho impresso pelo navegador** (estado atual: só um
formulário + validador de IA, sem persistência) para um **objeto sanitário completo** —
com protocolo, estados, ledger imutável, custódia, PDF institucional, assinatura
ICP-Brasil e **validação pública** (a médica pode conferir online "este atestado é
genuíno").

### Diferença essencial: o atestado é MONOLÍTICO

Prescrição e exame têm **itens** (vários medicamentos, vários exames). O atestado é
**um documento único** — uma finalidade, um período, um CID opcional. Logo:

- **Não há tabela `atestado_itens`** nem `status_item`.
- O status é **direto** (não derivado de itens).
- É o caso simples do núcleo (como o agendamento é "objeto leve").

---

## 2. Estados (`domain/states_atestado.py`)

```
emitido                ← criado digitalmente, entregue ao paciente
assinado               ← assinatura ICP-Brasil (PAdES) aplicada
cancelado              ← revogação clínica (terminal)
expirado               ← período do atestado ultrapassado (terminal, opcional)
encerrada_localmente   ← emissão exclusivamente física (terminal)
```

### Transições

```
emitido   → assinado | cancelado | expirado
assinado  → cancelado | expirado          (um atestado assinado ainda pode ser revogado)
cancelado            → ∅  (terminal)
expirado             → ∅  (terminal)
encerrada_localmente → ∅  (terminal)
```

Estados terminais: `cancelado · expirado · encerrada_localmente`.

> **Nota:** assinar é uma transição `emitido → assinado`. Reassinar (gerar novo PDF
> assinado) a partir de `assinado` **não** re-transiciona — apenas registra novo
> evento `atestado_assinado` e devolve o PDF (idempotente quanto ao estado).

### Eventos do ledger (`EVENTOS_ATESTADO`)

| Evento | Quando |
|---|---|
| `atestado_emitido` | emissão digital (POST /atestados) |
| `atestado_assinado` | PDF assinado em ICP-Brasil (PAdES) |
| `atestado_corrigido` | derivação por correção (origem_atestado_id) |
| `atestado_cancelado` | revogação clínica |
| `atestado_expirado` | período ultrapassado |
| `atestado_impresso` | **fluxo físico** — ato de impressão |
| `encerrada_localmente` | **fluxo físico** — transição terminal |
| `custodia_transferida` | transferência (emissão: prescritor → paciente) |

---

## 3. Persistência

### Tabela `atestados`

| Coluna | Tipo | Nota |
|---|---|---|
| `id` | PK | |
| `protocolo` | UUID único | identidade sanitária global |
| `prescritor_id` | FK prescritores | autor |
| `paciente_id` | FK pacientes | titular |
| `status` | str | máquina de estados (§2) |
| `tipo_emissao` | str | `nova` \| `correcao` \| `fisica` |
| `origem_atestado_id` | FK atestados, nullable | derivação (imutabilidade) |
| `finalidade` | str NOT NULL | **obrigatória** (afastamento, comparecimento, …) |
| `indicacao_clinica` | text, nullable | opcional (privacidade do diagnóstico) |
| `codigo_cid` | str, nullable | opcional |
| `dias_afastamento` | int, nullable | **opcional** (nem todo atestado afasta — ex.: comparecimento) |
| `nome_profissional` | str, nullable | declarado no formulário |
| `registro_profissional` | str, nullable | CRM/registro declarado |
| `assinatura_modo` | str, nullable | `icp_brasil_local` \| `gov_br_nuvem` \| NULL |
| `assinatura_hash` | str(64), nullable | SHA-256 do documento canônico |
| `data_documento` | str(10) | data do atestado (ISO) |
| `data_emissao` | str(10) | data de emissão no sistema |
| `data_validade` | str(10), nullable | fim do período (data_documento + dias) se aplicável |
| `instance_id` | str(36) | UUID da instância PicSaúde |
| `criado_em` | datetime | |

### Tabela `atestado_eventos` (ledger imutável)

`id · atestado_id (FK) · tipo_evento · ator_tipo · ator_id · dados_json · instance_id · criado_em`

> Inclui `ator_tipo/ator_id` (`tem_ator=True`) — o atestado tem autor explícito
> (prescritor), como a prescrição.

### Tabela `atestado_custodia`

`id · atestado_id (FK) · de · para · transferido_em · dados_json`

Sem `item_id` (objeto monolítico). Transição única na emissão: **prescritor → paciente**.

> **Registro no ledger:** `atestado_eventos` entra em `_TABELAS_LEDGER` (triggers que
> proíbem UPDATE/DELETE) e em `_LEDGER_SCHEMA` (`ledger.py`).

---

## 4. Identidade do paciente — decisão que afeta a UX

Hoje o formulário do atestado coleta **só o nome** do paciente. Para ser objeto
**completo** (custódia + validável), precisamos identificá-lo:

- **Atestado digital:** CPF do paciente **obrigatório** (como na prescrição) → resolve
  `paciente_id` → custódia prescritor → paciente → carteira digital.
- **Atestado físico:** sem identificação digital → CPF sentinela `00000000000`
  (convenção 6a), status final `encerrada_localmente`, sem custódia.

→ **Implica adicionar um campo CPF ao formulário do atestado.**

---

## 5. API (`routers/atestados.py`)

| Método | Rota | Descrição | Auth |
|---|---|---|---|
| POST | `/atestados` | Emissão digital | prescritor |
| POST | `/atestados/fisica` | Emissão física (fire-and-forget) | prescritor |
| GET | `/atestados/{proto}` | Consulta autenticada | prescritor(dono)/paciente(titular)/admin |
| GET | `/atestados/{proto}/pdf` | PDF institucional | prescritor(dono)/paciente(titular)/admin |
| POST | `/atestados/{proto}/pdf-assinado` | PDF + assinatura ICP (cofre PAdES) | prescritor(dono) |
| GET | `/atestados/{proto}/custodia` | Histórico de custódia | prescritor(dono)/paciente(titular)/admin |
| GET | `/public/atestados/{proto}` | **Validação pública** (sem dado clínico) | — |

### Validação pública — o que devolve (e o que NUNCA devolve)

A consulta pública confirma **autenticidade e vigência**, sem vazar clínica
(lição dos `/public/*` — eles nasceram neutros depois do #15):

```jsonc
// GET /public/atestados/{proto}  → devolve:
{ "protocolo": "...", "status": "assinado",
  "tipo_emissao": "nova", "assinado": true, "vigente": true }
// NUNCA: nome/CPF do paciente, finalidade, indicação, CID, dias, prescritor —
//        nem as datas: data_validade = data_documento + dias_afastamento, então
//        expô-las derivaria os dias de afastamento. A vigência vai SÓ como booleano.
```

> O verificador confirma que o atestado **existe, está assinado e está vigente** — o
> conteúdo clínico fica protegido. Quem precisa do conteúdo tem o PDF em mãos.

---

## 6. PDF institucional (`domain/pdf_atestado.py`)

ReportLab, paleta institucional compartilhada, blocos: cabeçalho PicSaúde → prescritor
→ paciente (CPF mascarado) → **corpo do atestado** (finalidade + período + cláusula
clínica opcional com CID) → identificação (protocolo, datas, hash) → área de
assinatura → rodapé com protocolo. A assinatura PAdES reusa `assinar_pdf_icp` + cofre
(idêntico ao #59 da prescrição).

---

## 7. Conformidade com o núcleo (checklist §11)

- [x] Máquina de estados em `states_atestado.py` (terminais explícitos; `direto`)
- [x] `EstadoAtestado` Literal · `TRANSICOES_ATESTADO` · `EVENTOS_ATESTADO`
- [x] Tabela principal com `protocolo, status, tipo_emissao, origem_atestado_id, assinatura_hash`
- [x] Ledger imutável `atestado_eventos` (+ triggers)
- [x] Custódia `atestado_custodia` (prescritor → paciente)
- [x] Imutabilidade: correção = novo objeto via `origem_atestado_id` (nunca UPDATE pós-emissão)
- [x] API: emissão, física, consulta, PDF, PDF-assinado, custódia, **pública neutra**
- [x] RBAC em todos os privados; público sem auth e sem clínica
- [x] CPF sentinela no fluxo físico
- [x] Registro em `init_tables.py`, `models/__init__.py`, `main.py`
- [x] Estados na §7 do CLAUDE.md

**Sem itens** (monolítico): a parte "tabela de itens / status_item" do checklist
não se aplica — exceção documentada (como o agendamento).

---

## 8. Plano de implementação (em fatias, com testes a cada uma)

1. `states_atestado.py` + testes de transição.
2. Models + migration (`atestados`, `atestado_eventos`, `atestado_custodia`) + `_LEDGER_SCHEMA` + `init_tables`.
3. `routers/atestados.py`: emissão digital + física + consulta + custódia.
4. `domain/pdf_atestado.py` + `GET /pdf`.
5. `POST /pdf-assinado` (reusa cofre + `assinar_pdf_icp`).
6. `GET /public/atestados/{proto}` (neutro).
7. UI: formulário emite de verdade + "baixar PDF" + "assinar com ICP-Brasil".
8. CLAUDE.md §7 + este doc finalizado.

---

## 9. Decisões que precisam do seu aval (clínicas/produto)

1. **Identidade do paciente:** adicionar **CPF** ao atestado (obrigatório no digital,
   sentinela no físico)? — necessário para custódia + validação pública.
2. **`dias_afastamento` opcional:** confirmar que atestado **não** é só afastamento
   (ex.: comparecimento/acompanhante não têm dias) → campo opcional.
3. **Estados:** `emitido → assinado` (assinar é milestone) — ok? Ou manter status
   simples e tratar assinatura só como evento (como na prescrição)?
4. **Validade:** `data_validade = data_documento + dias` quando houver afastamento;
   sem validade nos demais — ok?
