# Sessão 2026-08-13 — Engenheiro: Tickets B e C (demo Laboratório / Laudo Cidadão)

| Campo | Valor |
|---|---|
| **Engenheiro** | Claude Code no terminal — executor e redator deste registro |
| **Arquiteto** | Z AI — autor do plano `planejamento/demo-laboratorio-laudo-cidadao/` |
| **Fonte** | `01-contexto-visao-decisoes.md` (decisões #4 e #5) |
| **Escopo da sessão** | Ticket B (`module`) e Ticket C (**`core` — RBAC**) |
| **Branch** | `docs/sessoes-11-12-agosto` — **sem commit**, trabalho na árvore |
| **Estado** | Ambos implementados e verdes em todos os gates rodados localmente |

---

## §1 Resumo em uma frase

O laboratório passou a ter **um estado onde repousar** (`em_analise`, Ticket B) e **direito de operar
o laudo em nome do RT** (Ticket C) — as duas peças que faltavam entre a coleta e o laudo chegar ao
cidadão.

---

## §2 Ticket B — "Enviar à bancada" (`coletado → em_analise`) · classe `module`

### O que era

`em_analise` era **estado fantasma**: declarado em `states_exame.py`, presente na lista branca de
transições (`coletado → em_analise`) e no vocabulário de eventos (`pedido_em_analise`) — mas
**nenhum endpoint o persistia**. O `/resultado` emitia o evento como marco intermediário e escrevia
`resultado_disponivel` direto. O item nunca *repousava* na bancada, e por isso não havia de onde o
Ticket G ancorar a produção do laudo.

### O que entrou

**`POST /pedidos-exame/{protocolo}/itens/{item_id}/em-analise`** — cópia estrutural do `coletar`,
com quatro desvios deliberados:

| Aspecto | `coletar` | `em-analise` |
|---|---|---|
| RBAC | prescritor · admin · dispensador | **dispensador · admin** — a bancada é da unidade |
| Ownership | prescritor **ou** dispensador | só custódia do dispensador |
| Guarda de estado | `!= "agendado"` | `!= "coletado"` |
| Status code | 201 | **200** — transição pura, como `cancelar`/`encerrar` |

Ordem **404 → 403 → 422** preservada (anti-leak #52). Evento `pedido_em_analise` no ledger + outbox,
mesmo `instance_id`. `setor` é texto livre opcional (`max_length=120`), normalizado — string vazia
vira `None`, para o ledger imutável não guardar `""` como se alguém tivesse informado algo.

**Fronteira LIMS respeitada:** nada de analisador, técnico, fila de equipamento ou lote. `setor` é
visibilidade operacional. Se virar fila de máquina, virou outro produto.

**`states_exame.py` intocado. Sem migração. Nenhum estado novo.**

### Achado durante a implementação — correção de acompanhamento (autorizada pelo Fabiano)

`dispensadores.py` derivava `acionavel` de `_ESTADOS_ITEM_ACIONAVEL_LAB = {"agendado", "coletado"}`,
e `clinica.html` só lista pedido com **ao menos um item acionável**. Sem tocar nisso, o Ticket B
entregaria um gesto que **apaga o pedido da tela do laboratório** no instante em que ele é enviado à
bancada — e o lab perderia o caminho para registrar resultado, que o `/resultado` aceita justamente
a partir de `em_analise`.

`em_analise` entrou no conjunto, com o comentário do contrato derivado (§10) atualizado. **Item na
bancada é trabalho pendente; sair da fila é privilégio de estado terminal.**

---

## §3 Ticket C — RBAC do laudo estendido ao dispensador · classe `core` ⚠️

> Aprovação central já concedida pelo arquiteto (registrada no README do plano).

### O princípio

O laudo exige Responsável Técnico com CNS; quem opera a tela entra como `dispensador` (CNPJ). A
unidade **produz em nome do RT**: declara `cns_autor`, e o RT continua sendo o `autor_id`. **O CNPJ
nunca vira autor.** O que autoriza a unidade não é identidade nominal — é **posse**: o laudo precisa
estar preso a um pedido sob sua custódia atual.

**Sem coluna nova. Sem migração.** O ownership sai de `pedido_exame_custodia`, que já existe.

### Superfície alterada

```
criar · assinar · liberar · encerrar · cancelar · GET · pdf · qr   → + dispensador
ciencia-paciente · ciencia-prescritor · /fisica                    → INALTERADOS
laudo standalone (sem pedido vinculado)                            → segue prescritor/admin
```

Ciência é ato de quem **recebe** o laudo — quem produziu não dá ciência por ninguém.

Helper novo, local ao subdomínio: `_dispensador_detem_pedido` (custódia nível-pedido,
`item_id IS NULL`, a mais recente) com dois asserts em cima. Escrito aqui e não importado do módulo
de exames por decisão de arquitetura (ADR-002 opção C mantém queries de ownership locais) — e o
comentário diz isso **sem prometer fonte única que não existe**.

### Três decisões que extrapolam a letra do ticket

1. **Ordem no `criar`** — a posse é conferida **antes** do vínculo clínico paciente↔pedido. O ticket
   não especificava a ordem; assim uma unidade alheia leva 403 sem aprender de quem é o pedido.
2. **`cnpj_prestador` virou opcional** em `LiberarIn`. O dispensador não declara o próprio CNPJ: ele
   vem do JWT e o payload é ignorado — **posse provada, não posse declarada**; senão a cadeia de
   custódia (§3 do CLAUDE.md) deixaria de valer como prova. Para prescritor/admin continua
   obrigatório, agora com 422 nomeado em vez do erro genérico do Pydantic.
   ⚠️ **É afrouxamento de contrato num ticket `core` — sinalizado para revisão.**
3. **`GET /laudos/{proto}/custodia` ficou de fora** — não constava da tabela do ticket. O
   `GET /laudos/{proto}` já devolve status e eventos, que é o que a tela precisa. Se o Ticket G
   quiser a cadeia crua, é uma linha.

### Ledger

`laudo_criado` passou a gravar `produzido_por` e `produzido_por_cnpj`; `laudo_liberado` ganhou
`liberado_por`. Sem isso, laudo produzido pela unidade seria **indistinguível** de um digitado pelo
próprio RT — e essa é exatamente a pergunta que uma auditoria faria.

---

## §4 Arquivos

| Arquivo | Δ | Papel |
|---|---|---|
| `backend/app/routers/pedidos_exame.py` | +118 / −1 | endpoint `/em-analise` + `EmAnaliseIn` |
| `backend/app/routers/laudos.py` | +171 / −27 | RBAC do dispensador (Ticket C) |
| `backend/app/routers/dispensadores.py` | +13 / −3 | `em_analise` acionável na fila |
| `backend/tests/integration/test_pedidos_exame_bancada.py` | novo, 342 linhas | 12 casos |
| `backend/tests/integration/test_laudos_dispensador_autorizacao.py` | novo, 383 linhas | 16 casos |
| `backend/tests/integration/test_fila_exames_dispensador.py` | +44 / −1 | fila não perde o pedido |

**Nomeação deliberada dos arquivos de teste:** ambos casam com o `-k` do gate (`test_pedidos_exame`
e `autorizacao`). Suíte de RBAC não-gateada apodrece — ver §6.

---

## §5 Gates (PostgreSQL efêmero local, mesma seleção da CI)

| Gate | Comando | Resultado |
|---|---|---|
| Suíte Ticket B | `tests/integration/test_pedidos_exame_bancada.py` | **12 passed** |
| Suíte Ticket C | `tests/integration/test_laudos_dispensador_autorizacao.py` | **16 passed** |
| Integração (seleção `-k` da CI) | `gates.yml` §86-90 | **279 passed** (era 263 antes do C) |
| Unitários | `tests/unit` | **412 passed** |
| Ledger imutável (SQLite + PG) | `tests/test_ledger_imutabilidade.py` | **69 passed** |
| Smokes de navegador | `tests/browser` | **54 passed** |

`backend/app/routers/**` está nos paths do `gates-browser` (fechamento do buraco do #152) — os
smokes foram rodados localmente por isso, não por precaução genérica.

---

## §6 Achado para o Fabiano decidir — teste vermelho **pré-existente**

`test_4d2_instance_id_ledger.py::test_laudo_ciencia_paciente_dois_eventos_mesmo_instance_id` falha
**desde antes desta sessão** (confirmado com `git stash`: falha idêntica sem as mudanças).

**Não é bug de código.** O teste cria laudo com `_PAYLOAD_LAUDO`, que **não tem `pedido_protocolo`**
— laudo standalone. Depois chama `/ciencia-prescritor`. Sem pedido vinculado não há solicitante, e o
`_assert_solicitante` devolve 403: comportamento **ratificado** no TICKET-5C-BIS-B §8.1 ("sem
fallback de autor") e afirmado como correto por
`test_laudos_autorizacao.py::test_ciencia_prescritor_sem_pedido_403`.

O teste é anterior a essa regra e **envelheceu em silêncio** porque a suíte `test_4d2_*` não casa com
nenhum termo do `-k` da CI. É a mesma doutrina que os comentários do `gates.yml` já registram: *verde
e não gateado apodrece* — aqui foi vermelho e não gateado, que é pior.

**Correção:** uma linha (vincular o laudo a um pedido do prescritor semeado).
**Não implementada:** é mudança de semântica de teste em módulo `core`; a chamada é do arquiteto.
**Recomendação adicional:** avaliar a entrada de `test_4d2` no `-k` do gate, senão volta a apodrecer.

---

## §7 Estado e próximos passos

- Nada commitado; nada mergeado. Trabalho na árvore de `docs/sessoes-11-12-agosto`.
- **Desbloqueados:** Ticket F (gesto na tela, depende de B) e Ticket G (UI de laudo, depende de C).
- **Não tocados nesta sessão:** Ticket A (`docs` — política de custódia clínica), Ticket D
  (`module` — SIGTAP), Ticket E (`docs`), Ticket H (E2E).
- **Nenhuma transmissão externa** implementada: sem G4A não há adapter (CLAUDE.md §10). TUSS/SIGTAP
  seguem sendo agregação interna.

---

*Registro emitido pelo Engenheiro (Claude Code) em 2026-08-13. Ticket C é `core` e vai ao portão do
Conselheiro + martelo do Fabiano — com atenção especial ao item 2 do §3.*
