# TICKET-F5-RELATORIO-SNGPC — Relatório consolidado + SNGPC CSV do dispensador

| Campo | Valor |
|---|---|
| **Fase** | 5 (paridade v27) — primeira fatia, decisão de Fabiano 2026-07-09 |
| **Classe** | `module` (extensão do módulo dispensação: novo endpoint read-only + UI) |
| **Para** | code/MS (engenheiro) — após parecer do Z AI |
| **Origem** | Era o T8 cortado (handoff §4a) · spec UX `dispensador.txt` (botões "Relatório Consolidado" e "SNGPC (CSV)") |
| **Pré-requisito** | `main@ba307b7` (ciclo mínimo publicado: T1.5, T2 estorno, T5 comprador, T6 histórico) |
| **Ordem** | **Fatia A (backend) → Fatia B (frontend).** Nada de UI antes do endpoint real. |
| **Parecer Z AI** | **VERDE com 3 notas** (2026-07-10) — notas 1–2 incorporadas (§3 + DIVIDA-TECNICA); nota 3 virou critério §5.8 |

## §1 Contexto (não reabrir)

O ciclo mínimo do dispensador está publicado. O backend de relatórios existente
(`/relatorios/dispensacoes.{csv,pdf}`) é a **visão do auditor/admin** — role
`auditor|admin`, escopo global, CNPJ como filtro opcional — e está **pré-T2/T5**:

- emite `comprador_nome/cpf` = paciente (comentário "MVP" em `relatorios.py:106`),
  ignorando as colunas reais `dispensacoes.comprador_nome/comprador_documento` (T5);
- **ignora a tabela `estornos`** (T2): uma dispensação estornada aparece como saída
  plena — escrituração incorreta.

O v27 exige a **visão do dispensador**: relatório da própria farmácia, travado ao
CNPJ do JWT. Não existe hoje (`dispensadores.py` não tem rota de relatório).

## §2 Decisões arquiteturais desta fatia

1. **Visão nova, não remendo.** A visão do dispensador nasce em `dispensadores.py`
   (`GET /dispensadores/relatorio.csv` e `.pdf`), ao lado de `fila` e `historico`.
   `/relatorios/*` permanece como visão do auditor (atualizá-la é fatia futura, fora
   de escopo aqui — exceto se o engenheiro extrair SQL comum sem mudar contrato).
2. **CNPJ sempre do JWT.** Nunca por query param. Role exigida: `dispensador`.
   Mesmo padrão de auth do comprovante (validação por CNPJ).
3. **Escrituração por movimento.** O CSV SNGPC lista **movimentos**, não estados:
   cada dispensação = 1 linha (`tipo_movimento=dispensacao`), cada estorno = 1 linha
   (`tipo_movimento=estorno`, quantidade da reversão, ref. `origem_dispensacao_id`).
   Isso espelha o ledger imutável (CLAUDE.md §2): o estorno é objeto derivado, não
   edição da saída original. Saldo efetivo = Σ dispensado − Σ estornado por item.
4. **Desvio documentado do v27 (PII):** o protótipo v27 inclui `End_Paciente`
   (endereço) no CSV. **Não entra.** Minimização ratificada: comprador = só
   nome + documento; endereço não é armazenado nem exportado. O v27 é spec de UX,
   não contrato de dados.
5. **Comprador real com semântica do comprovante:** `comprador_nome/documento` das
   colunas de `dispensacoes`; se NULL → comprador é o paciente, com flag explícita
   `comprador_eh_paciente` (mesma regra de `dispensacoes.py:96`). Cabeçalho usa
   `comprador_documento` (não "cpf" — pode ser outro documento).

## §3 Fatia A — Backend (`module`)

### Contrato

```
GET /dispensadores/relatorio.csv?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
GET /dispensadores/relatorio.pdf?data_inicio=YYYY-MM-DD&data_fim=YYYY-MM-DD
Auth: JWT role=dispensador · escopo = CNPJ do JWT (WHERE d.cnpj_estabelecimento = :cnpj_jwt)
Default sem filtros: últimos 30 dias. PDF limitado a 1000 registros (como o do auditor).
```

### Colunas do CSV (uma linha por movimento)

```
tipo_movimento            dispensacao | estorno
data_movimento            dispensado_em | estorno criado_em
dispensacao_id            id da dispensação (no estorno: origem_dispensacao_id)
estorno_protocolo         (só em estorno)
protocolo_prescricao
medicamento · dose · unidade_quantidade
quantidade                dispensada (saída) | estornada (reversão)
saldo_escriturado_item        saldo NA DATA DO MOVIMENTO (regra abaixo — nota 2 do Z AI)
lote · fabricante
paciente_nome · paciente_cpf
comprador_nome · comprador_documento · comprador_eh_paciente
prescritor_nome · prescritor_cns
motivo_estorno            (só em estorno; enum MOTIVOS_ESTORNO)
status_item
```

### Regra de corte temporal do `saldo_escriturado_item` (nota 2 do Z AI — ratificada)

O saldo de cada linha é o **saldo na data do movimento** (running balance):
Σ dispensado − Σ estornado do item considerando **apenas movimentos com
`data_movimento` ≤ a data da linha** (desempate por `id` do movimento, mesma ordem
do ORDER BY). Consequências normativas:

- Estornos posteriores ao `data_fim` do filtro **não afetam** linhas do período —
  o relatório de um período fechado é **estável para sempre** (reexecutar = idêntico).
- A linha nunca "muda de valor" quando o futuro acontece — mesma filosofia do
  ledger imutável.

**Escopo do saldo (ratificado pelo arquiteto na revisão do PR #88):** o saldo é o
running balance **da escrituração deste estabelecimento** (todos os movimentos do
CNPJ do JWT, nunca só o período exibido) — semântica do livro SNGPC, que é por
estabelecimento. **Não** é o saldo clínico global do item: se o item circular entre
farmácias (re-apresentação A→B), cada livro reflete só os próprios movimentos.
Isso também preserva o isolamento do §5.1 (nenhuma leitura de movimento de outro
CNPJ). O saldo clínico global permanece sendo o do backend de dispensação (T2).

### Invariantes tocados (read-only — nenhum é alterado)

- Ledger e `estornos` são **somente leitura**; nenhum INSERT/UPDATE nesta fatia.
- CPF sentinela `00000000000` **excluído** (CLAUDE.md §6a) — demo física não entra.
- Σ dispensado ≤ prescrito e saldo efetivo (T2) apenas **exibidos**, nunca recalculados
  para gravação.
- `ORDER BY data_movimento DESC, dispensacao_id DESC` — determinismo (régua Jules,
  desempate por id como em `custodia.py:827`).

### [PII-EXAUSTIVIDADE] — rotas que tocam PII nesta fatia

| Rota | PII exposta | Auth |
|---|---|---|
| `GET /dispensadores/relatorio.csv` | paciente nome+CPF, comprador nome+documento, prescritor nome+CNS | JWT `dispensador`, travado ao CNPJ do próprio JWT |
| `GET /dispensadores/relatorio.pdf` | idem | idem |

Nenhuma rota pública. Nenhum endereço em nenhuma saída. Rotas existentes de
`/relatorios/*` não mudam de contrato nesta fatia.

### Gotchas obrigatórios (LEARNINGS)

- **PG ≠ SQLite:** `dispensado_em`/`criado_em` voltam como `datetime` na PG, string
  no SQLite — normalizar antes de formatar o CSV. Testar caminho 2xx contra PG.
- **`database.py` na PG anexa `RETURNING id`** a INSERTs — irrelevante aqui
  (read-only), mas o teste de fixture que semear dados deve usar RETURNING explícito.
- **Gate roda o predeploy (seed) contra PG** — o teste do relatório entra no gate.

## §4 Fatia B — Frontend (`dispensador.html`)

Só depois da Fatia A mergeada.

- Dois botões no cabeçalho da fila (posição conforme `dispensador.txt`):
  **"🖨️ Relatório Consolidado"** e **"SNGPC (CSV)"**.
- CSV: `fetch` com JWT do dispensador logado → blob → download
  (`dispensacoes_sngpc_YYYY-MM-DD.csv`). Nunca URL aberta sem auth.
- Consolidado: view de impressão (`@media print`, padrão `#print-area` do v27)
  alimentada pelo **mesmo endpoint** (formato JSON opcional ou parse do CSV —
  decisão do engenheiro; sem segunda query divergente).
- Erros do backend renderizam legíveis (`detail.mensagem`, nunca `[object Object]`).
- Período: seletor simples data_inicio/data_fim, default 30 dias.

## §5 Critérios de aceite

1. CSV do dispensador A não contém movimento do dispensador B (troca de JWT → 403/escopo).
2. Dispensação parcial + estorno → CSV mostra 2 linhas (saída e reversão) e
   `saldo_escriturado_item` reposto; nada foi alterado em `dispensacoes`/`estornos`.
3. Comprador declarado no balcão aparece como comprador; sem comprador →
   `comprador_eh_paciente=true` e dados do paciente.
4. CPF sentinela ausente de qualquer linha.
5. Sem endereço em CSV, PDF ou tela de impressão.
6. Testes verdes **contra PG** (incl. tipos datetime) + gate com predeploy.
7. Ordem estável entre execuções (determinismo).
8. PDF com mais de 1000 registros exibe **aviso visível de truncamento** no próprio
   documento ("relatório truncado em 1000 registros — use o CSV para exportação
   completa"), nunca truncamento silencioso (nota 3 do Z AI).
9. Relatório de período fechado é estável: estorno registrado após `data_fim` não
   altera nenhuma linha do período (regra de corte temporal do §3).

## §6 Fora de escopo

- XML SNGPC oficial / webservice ANVISA (o CSV é escrituração exportável, não
  transmissão) — candidata a `adapter` futura, **bloqueada até G4A** (CLAUDE.md §10).
- Atualizar a visão do auditor (`/relatorios/*`) para comprador real/estornos —
  fatia própria, registrar em DIVIDA-TECNICA se não existir.
- Campo comprador na UI da fila (fatia seguinte da Fase 5).
- Devolução ao prescritor (decisão de produto pendente).

## §7 Fluxo de aprovação (atualizado pelo martelo de 2026-07-10 — auditoria por marco)

1. Z AI (conselheiro): parecer verde/nota/bloqueio sobre este ticket. ✅ (verde com 3 notas)
2. code/MS implementa Fatia A → PR #88 → gate PG ✅ → revisão do arquiteto ✅ →
   teste manual Fabiano → **merge** (Jules não bloqueia PR `module`).
3. Fatia B → PR → gate → validação UI↔invariante (padrão TICKET-ZAI-FASE4) →
   teste manual Fabiano → merge.
4. **Jules audita a fatia F5 completa (A+B) após o merge da B**, sobre o SHA
   mergeado, com este ticket como referência — cadência por marco ratificada
   por Fabiano (ver LEARNINGS 2026-07-10).
