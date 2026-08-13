# Sessão 2026-08-13 — Arquiteto: parecer sobre Tickets B e C (demo Laboratório)

| Campo | Valor |
|---|---|
| **Arquiteto** | Z AI — redator deste parecer e autorização |
| **Engenheiro** | Claude Code no terminal — executou B e C; autor de `SESSAO-2026-08-13-TICKETS-B-C-DEMO-LAB.md` |
| **Escopo** | Verificação de código (não só relatório) de B (`module`) e C (**`core` — RBAC**) |
| **Base** | `planejamento/demo-laboratorio-laudo-cidadao/` (Tickets B e C) |
| **Estado** | **Aprovados.** Um item de teste pré-existente a corrigir (autorizado abaixo). |

---

## §1 Veredito em uma frase

Tickets B e C estão **aprovados** — verifiquei no código, não só no relatório; o C está **melhor que
a letra do ticket** nos três pontos que o engenheiro sinalizou como extrapolação, e todos são
corretos. Resta corrigir um teste vermelho **pré-existente** (não causado por esta sessão), o que
autorizo adiante.

---

## §2 Ticket B — "Enviar à bancada" (`module`) ✅

Verificado em `backend/app/routers/pedidos_exame.py:1060`:

- RBAC `require_role("dispensador", "admin")` — a bancada é da unidade. ✓
- Ordem **404 → 403 → 422** preservada (`:1088` pedido → `:1091` ownership → `:1093` terminal →
  `:1104` item → `:1110` estado). Anti-leak #52 intacto. ✓
- `setor` vazio vira `None` (`:1085`) — o ledger imutável não guarda `""` como dado declarado. ✓
- Evento `pedido_em_analise` + outbox, mesmo `instance_id` (`:1131-1143`). ✓
- `status 200` (transição pura, como `cancelar`/`encerrar`). `states_exame.py` **intocado**; nenhum
  estado novo; sem migração. ✓

**Achado de acompanhamento (autorizado):** `_ESTADOS_ITEM_ACIONAVEL_LAB` em
`dispensadores.py:215` ganhou `em_analise`. Sem isso, o gesto "enviar à bancada" **sumiria com o
pedido da fila do laboratório** no instante do clique — quebrando o caminho até o `/resultado`, que
exige `coletado|em_analise`. Decisão cirúrgica e correta. *"Item na bancada é trabalho pendente;
sair da fila é privilégio de estado terminal."*

---

## §3 Ticket C — RBAC do laudo ao dispensador (`core`) ✅

Verificado em `backend/app/routers/laudos.py`. A superfície é exatamente a especificada:

```
criar · assinar · liberar · encerrar · cancelar · GET · pdf · qr   → + dispensador (via posse do pedido)
ciencia-paciente · ciencia-prescritor · /fisica                    → INALTERADOS
laudo standalone (sem pedido_id)                                   → prescritor/admin (403 p/ dispensador)
```

- O RT é **sempre** o `autor_id`; o CNPJ **nunca** vira autor (`criar_laudo:451` resolve autor por
  `cns_autor`). ✓
- Ownership sem coluna nova: `_dispensador_detem_pedido` (`:310`) usa a custódia **ATUAL** do pedido
  (`item_id IS NULL`, `ORDER BY id DESC LIMIT 1`) — não custódia histórica. Guard de 14 dígitos
  impede casamento acidental com CPF do paciente. ✓
- Ledger gravou `produzido_por`/`produzido_por_cnpj` (`:540-541`) e `liberado_por` (`:830`) — a
  pergunta de auditoria ("foi a unidade ou o RT?") fica respondida. ✓

### Os três desvios sinalizados pelo engenheiro — **todos endossados**

| # | Desvio | Posse do arquiteto |
|---|---|---|
| 1 | Posse conferida **antes** do vínculo paciente↔pedido (`:472`) | ✅ **Endossado.** Unidade alheia leva 403 sem aprender de quem é o pedido (doutrina anti-leak #52). |
| 2 | `cnpj_prestador` virou **opcional** em `LiberarIn`; para dispensador vem do JWT e o payload é ignorado (`:796`) | ✅ **Endossado com força.** É *posse provada, não posse declarada* — a cadeia de custódia (CLAUDE.md §3) tem que registrar a unidade **autenticada**. Para prescritor/admin segue obrigatório, agora com 422 nomeado em vez do erro genérico do Pydantic. É **endurecimento**, não afrouxamento perigoso. |
| 3 | `GET /laudos/{proto}/custodia` ficou de fora | ✅ **Endossado.** `GET /laudos/{proto}` já devolve status + eventos, que é o que a tela precisa. Uma linha se o Ticket G quiser a cadeia crua. |

> Nota sobre o item 2: embora seja um **afrouxamento de schema** num ticket `core`, o efeito líquido
> é mais seguro. Registro aqui para o Conselheiro: o campo tornou-se opcional, mas o **valor
> autoritativo** passou a ser o JWT para o ator que pode se auto-declarar (dispensador). Sem
> regressão — prescritor/admin seguem obrigados a enviá-lo.

**Gates:** 16 casos de autorização (`test_laudos_dispensador_autorizacao.py`) + 12 de bancada
(`test_pedidos_exame_bancada.py`); 279 integração, 412 unitários, 69 imutabilidade, 54 browser —
todos verdes. Os arquivos de teste casam com o `-k` da CI por nome (`autorizacao`,
`test_pedidos_exame`).

---

## §4 Decisão — teste vermelho **pré-existente** (autorização para corrigir)

O engenheiro identificou, e confirmei no código:

- `test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` (`test_4d2_instance_id_ledger.py:370`)
  cria laudo com `_PAYLOAD_LAUDO` (`:64`) **sem `pedido_protocolo`** → laudo standalone →
  `/ciencia-prescritor` (`laudos.py:896`) chama `_assert_solicitante` (`:915`), que resolve
  solicitante `None` → **403**. Comportamento **ratificado** (TICKET-5C-BIS-B §8.1, "sem fallback de
  autor") e afirmado por `test_ciencia_prescritor_sem_pedido_403`.
- Confirmei pré-existente (o engenheiro validou com `git stash`).
- A suíte `test_4d2_*` **não casa** com nenhum termo do `-k` da CI (`gates.yml:89`) — por isso
  envelheceu em silêncio. *Vermelho e não-gateado é pior que verde e não-gateado.*

### Autorização (decisão do arquiteto)

**1. Corrigir o teste — autorizado.** É mudança de **teste**, não de código de produção.
Instrução precisa para o engenheiro:

> No teste `test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` (`:370`):
> 1. Antes de criar o laudo, criar um pedido do prescritor semeado:
>    `protocolo_pedido, _ = _criar_pedido(client, token)` (helper em `:101`).
> 2. Criar o laudo com payload **local** (não mexer no `_PAYLOAD_LAUDO` compartilhado):
>    `payload = {**_PAYLOAD_LAUDO, "pedido_protocolo": protocolo_pedido}`.
> 3. O vínculo é válido porque `_PAYLOAD_PEDIDO` (`:42`) usa `SEED_PACIENTE_CPF` (mesmo do laudo,
>    `:67`) e `SEED_PRESCRITOR_CNS` (mesmo autor) → `_cns_solicitante` resolve o solicitante e
>    `/ciencia-prescritor` passa a devolver 200. A invariante real (2 eventos, mesmo `instance_id`)
>    volta a ser exercitada.
> 4. Rodar `test_4d2_instance_id_ledger.py` inteiro — confirmar tudo verde.

**2. Incluir `test_4d2` no `-k` da CI — autorizado.** Adicionar `or test_4d2` à expressão em
`gates.yml:89`. Lição de fundo: suíte de invariante sem gate apodrece. O engenheiro deve ainda
**varrer** se há outros arquivos de invariante/ledger relevantes fora do gate (ex.: demais
`test_4*_*.py`) e incluir os que valerem — registrar a decisão no comentário do `-k`.

---

## §5 Postura de merge (C é `core`)

- Nada commitado; trabalho na árvore de `docs/sessoes-11-12-agosto`.
- **Martelo do Fabiano (mérito): concedido** por este parecer. Quando for commitar, **PR isolado
  para o C** com os 16 testes de autorização como prova de ownership (unidade A ≠ unidade B).
- O B pode seguir no fluxo normal de `module`; o fix do §4 (teste + gate) no mesmo PR ou no de B.

---

## §6 Despacho para o engenheiro — pacote "fix §4 + A + D + E"

Executar como **um pacote**, nesta ordem. (F e G — Dia 2 — **ficam de fora** deste despacho.)

### Passo 1 — Confiabilidade da suíte (pré-requisito)
- Aplicar o fix do §4 (corrigir `test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` +
  adicionar `or test_4d2` ao `-k` em `gates.yml:89`).
- Rodar `test_4d2_instance_id_ledger.py` + o `-k` da CI → tudo verde antes de seguir.

### Passo 2 — Ticket A (`docs`)
- Criar `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` conforme `planejamento/.../TICKET-A-politica-custodia-clinica.md`.
- Princípio: custódia clínica do laudo = cidadão; rastro forense + mínimo legal = lab (RDC 302/2005,
  CFM 2.052/2013, LGPD). Mapear ao backend existente com `file:line`. Cross-link em `ARQUITETURA_LAUDO.md`.

### Passo 3 — Ticket D (`module`)
- `agrupar_por=tuss|sigtap` nos 4 endpoints `/clinicas/faturamento.*` (`clinicas.py:361/:395`).
- Coluna `codigo_sigtap` já existe (`models/pedido_exame_item.py:26`); **sem schema change**.
- Permanece contabilidade interna read-only; **sem transmissão** a operadora/SUS (G4A).
- Testes casam com `-k` via `faturamento`.

### Passo 4 — Ticket E (`docs`)
- Atualizar `docs/ARQUITETURA_LAUDO.md`: seção "dispensador-produz-sob-RT" (documenta o que C
  implementou) + seção "fluxo bancada" (documenta o que B implementou). Cross-links para a política
  (Ticket A) e para `ARQUITETURA_EXAMES.md`.

### Aceite do pacote
- [ ] `test_4d2_*` verde e no `-k` da CI.
- [ ] `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` criado com `file:line` do backend.
- [ ] `/clinicas/faturamento.*?agrupar_por=sigtap` agrega por SIGTAP; `=invalido` → 422; TUSS
  (default) sem regressão; igualdade ledger↔faturamento preservada.
- [ ] `ARQUITETURA_LAUDO.md` documenta o modelo dispensador + bancada.
- [ ] `-k` da CI verde (incluindo `faturamento` e `test_4d2`).

### Fora deste despacho (próxima rodada — Dia 2)
- **Ticket F** (gesto bancada no `clinica.html`, depende de B ✅).
- **Ticket G** (UI de laudo no `clinica.html`, depende de C ✅).
- **Ticket H** (demo E2E).

---

*Parecer emitido pelo Arquiteto (Z AI) em 2026-08-13. Ticket C é `core` e segue para commit como PR
isolado, com o martelo de mérito do Fabiano concedido aqui. Atenção do Conselheiro ao item 2 do §3
(afrouxamento de schema com efeito líquido mais seguro).*
