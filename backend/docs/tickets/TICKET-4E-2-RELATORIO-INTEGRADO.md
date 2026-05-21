# TICKET 4E.2 — Relatório integrado da Regra 5

> **Classe (CLAUDE.md §10):** `module` para os fixes; `docs` para o ADR; `core` rejeitado (ver §5)
> **Pacto:** Regra 5 (análise estática consolidada ao fim da Etapa 4)
> **Data:** 2026-05-21
> **Material:** `git diff d8abf7e^..6b5dbed -- backend/` (18 commits, 64 arquivos, +12.416 −510 linhas)
> **Revisores:** CODEX (lente: conformidade técnica) + Jules (lente: pragmatismo/onboarding)
> **Predecessor direto:** 4E.1 (`65181dc` + `a53d5ba`)
> **Sucessor:** Etapa 5 — Fix B1 / carteira digital 422
> **Redigido por:** Arquiteto (Opus 4.7), integrando relatórios de CODEX e Jules
> **Relatórios fonte:**
> - `docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md`
> - `docs/revisoes/JULES-4E-2-relatorio-2026-05-21.md`

---

## §1 Resumo executivo

A Regra 5 sobre o diff acumulado da Etapa 4 produziu **12 achados** combinando CODEX (8) e Jules (4). A análise cruzada confirma:

- **Zero P1 reais.** A Etapa 4 entrega o que se propôs. O P1 declarado pelo Jules (overhead de query) é, na escala atual, um P2 técnico — não bloqueador de produção.
- **Lentes complementares funcionaram.** Quase zero sobreposição entre os dois revisores: CODEX viu bugs em routers + lapidações de docstring; Jules viu arquitetura do `instance_id`. Cada um cobriu o ponto cego do outro — validação prática do pacto Regra 5.
- **Um conflito direto entre revisores** (item #7 vs #5): CODEX quer `instance_id` mais explícito (hardening), Jules quer menos explícito (helpers leem cache global). **Arquiteto decidiu pela posição CODEX** e registrou ADR em §5 deste documento.

### Distribuição final pós-Arquiteto

| Decisão | Quantidade |
|---|---|
| ✅ Aceitar (fix direto na 4E.2) | 8 |
| 🔄 Aceitar adaptado | 2 |
| ❌ Rejeitar com ADR | 1 |
| 🆕 Ticket separado pós-4E.2 | 1 (mais 1 ticket de auditoria pré-existente) |

---

## §2 Tabela cruzada CODEX × Jules × Arquiteto

| # | Origem | Achado curto | Severidade declarada | Severidade real | Decisão Arquiteto | Tratamento |
|---|---|---|---|---|---|---|
| 1 | Jules | `instance.py:382` overhead SELECT por transação | P1 | P2 | ✅ Aceitar | Edit Regra 3 — `lru_cache` |
| 2 | CODEX | `custodia.py:616` evento genérico + ator hardcoded | P2 | P2 | 🔄 Aceitar adaptado | Ticket Regra 2 (toca core de custódia) |
| 3 | CODEX | `assinaturas.py:323` `ator_id` armazena modo | P2 | P2 | ✅ Aceitar | Edit Regra 3 — `sub` do JWT |
| 4 | CODEX | `auth.py:320` estado item terminal mas prescrição não | P2 | P3 (pré-existente) | 🔄 Aceitar adaptado | Edit Regra 3 — estender NOTA + abrir ticket separado |
| 5 | CODEX | `outbox.py:33` `instance_id` opcional | P2 | P2 | ✅ Aceitar | Edit Regra 3 — `keyword-only` obrigatório |
| 6 | CODEX | Cobertura faltante: `receituarios`, `hospitalares`, `assinaturas` | P2 | P3 | 🆕 Ticket separado | Ticket pré-Etapa 5 |
| 7 | Jules | Propagação manual `instance_id` nos routers | P2 | — | ❌ Rejeitar | ADR §5 |
| 8 | Jules | `instance.py:393` first-boot acoplado a runtime | P2 | P3 | ✅ Aceitar | Edit Regra 3 — docstring + log |
| 9 | CODEX | `outbox.py:6` docstring contradiz decisão 4D | P3 | P3 | ✅ Aceitar | Edit Regra 3 (batch docstrings) |
| 10 | CODEX | `ledger.py:19` docstring "4D — ainda não implementado" | P3 | P3 | ✅ Aceitar | Edit Regra 3 (batch docstrings) |
| 11 | CODEX | `test_4e_e2e_consolidado.py:480` C5 frágil | P3 | P3 | ✅ Aceitar | Edit Regra 3 — filtrar por objetos do teste |
| 12 | Jules | Onboarding: confusão `instance_id` vs request_id | P3 | P3 | ✅ Aceitar | Edit Regra 3 (batch docstrings) |

---

## §3 Specs de fix por achado aceito

Os fixes estão agrupados por **classe de pacto**:
- **§3.1** — Batch único Regra 3 (lapidações + hardening leve, ~60 linhas combinadas)
- **§3.2** — Ticket separado Regra 2 (achado #2, toca custódia)
- **§3.3** — Tickets pós-4E.2 (achado #6 + acompanhamento do #4)

### §3.1 Batch único Regra 3 — Edits diretos do Code

Code aplica em commit único `fix(4e-2): lapidações pós-Regra 5`. Verificação após: `pytest tests/test_instance_id.py tests/integration/test_4e_e2e_consolidado.py`.

#### §3.1.1 Achado #1 — Cache em memória do `instance_id`

**Arquivo:** `backend/app/instance.py`

**Antes** (lógica em `get_instance_id_conn`, bloco "1. SELECT primeiro"):
```python
# Cada chamada faz SELECT em meta_instalacao
row = conn.execute("SELECT instance_id FROM meta_instalacao LIMIT 1").fetchone()
```

**Depois:**
```python
# Cache em nível de módulo — instance_id é imutável por instalação
_CACHED_INSTANCE_ID: Optional[str] = None

def get_instance_id_conn(conn) -> str:
    global _CACHED_INSTANCE_ID
    if _CACHED_INSTANCE_ID is not None:
        return _CACHED_INSTANCE_ID
    # ... lógica existente (SELECT → first-boot → INSERT) ...
    _CACHED_INSTANCE_ID = valor_lido_ou_inserido
    return _CACHED_INSTANCE_ID
```

**Cuidado com testes:** o cache **deve ser resetável** entre testes que troquem `PICSAUDE_INSTANCE_ID` via env. Adicionar:
```python
def _reset_cache_for_tests() -> None:
    """Reset cache. APENAS para testes — não chamar em produção."""
    global _CACHED_INSTANCE_ID
    _CACHED_INSTANCE_ID = None
```

E em `conftest.py` adicionar fixture que chama `_reset_cache_for_tests()` no setup, se a busca não estiver coberta.

**Critério de aceite:**
- Suíte `tests/test_instance_id.py` continua verde
- `tests/integration/test_4e_e2e_consolidado.py` continua verde
- Grep confirma: única chamada a `conn.execute("SELECT instance_id FROM meta_instalacao` em `instance.py`

#### §3.1.2 Achado #3 — `ator_id` em assinaturas

**Arquivo:** `backend/app/routers/assinaturas.py`

**Estado real do código (calibrado em 2026-05-21 — diferente da nota original):**
- Linha 237: endpoint usa `_=Depends(require_role("prescritor", "admin"))` — descarta o usuário, **mesmo padrão do bug `custodia.py:578` que acabamos de corrigir no commit `9ef3bb2`**.
- Linha 330: chamada `registrar_evento_ledger(... ator_tipo="prescritor", ator_id=<valor — provavelmente meta.get(...) na linha logo abaixo>)`.
- Comentário pré-existente linhas 322-323: `# ator_id preservado intencionalmente (semanticamente fraco — ver §4.3).` — referência interna obsoleta a um §4.3 anterior. **Substituir.**

**Mudanças necessárias (3, todas em assinaturas.py):**

1. **Linha 237** — trocar `_=Depends(require_role("prescritor", "admin"))` por `usuario=Depends(require_role("prescritor", "admin"))`
2. **Localizar a chamada `registrar_evento_ledger` em `registrar_assinatura`** (range 322-340) e trocar `ator_id=meta.get("assinatura_modo") or "sem_modo"` (ou variante equivalente) por `ator_id=usuario["sub"]` (acesso estrito — mesmo padrão da custódia).
3. **Substituir o comentário linhas 322-323** pelo comentário canônico:
   ```python
   # 4E.2 §3.1.2: ator_id agora vem do sub do JWT (CNS/CPF do prescritor),
   # não mais do modo de assinatura. Padrão consistente com custodia.py:629.
   ```

**Critério de aceite:**
- Suíte completa verde (sem regressão E2E)
- Grep `ator_id=usuario\["sub"\]` em `assinaturas.py` retorna pelo menos 1 match
- Grep `assinatura_modo.*ator_id\|sem_modo` em `assinaturas.py` retorna **zero**
- Opcional: teste E2E focal curto valida que `ator_id` num evento `assinatura_registrada` corresponde ao `sub` do JWT — se cobertura já existe em outro teste, dispensável (sinalizar no commit message).

#### §3.1.3 Achado #4 — Estender nota documentada em `states.py`

**Arquivo:** `backend/app/domain/states.py:153`

**Antes:**
```python
# NOTA SOBRE INCONSISTÊNCIA DOCUMENTADA:
#   Em custodia.py, devolução dispensador→prescritor transiciona a prescrição
#   para "pendente" (não previsto em TRANSICOES_PRESCRICAO["em_custodia"]).
#   E devolução dispensador→paciente transiciona itens para "pendente" em vez
#   de "devolvido_paciente" → "em_custodia" (conforme o state machine do item).
```

**Depois:**
```python
# NOTA SOBRE INCONSISTÊNCIA DOCUMENTADA:
#   Em custodia.py, devolução dispensador→prescritor transiciona a prescrição
#   para "pendente" (não previsto em TRANSICOES_PRESCRICAO["em_custodia"]).
#   E devolução dispensador→paciente transiciona itens para "pendente" em vez
#   de "devolvido_paciente" → "em_custodia" (conforme o state machine do item).
#   Em auth.py:devolver_prescritor (paciente → prescritor), itens transicionam
#   de "pendente" diretamente para "devolvido_prescritor" (terminal), pulando
#   "em_custodia" exigido por TRANSICOES_ITEM. Apontado pelo CODEX em 2026-05-21
#   (4E.2). Tratamento previsto: ticket pós-Etapa 5 para auditoria completa das
#   máquinas de estado de devolução. Ver docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md §3.3.
```

**Critério de aceite:** grep confirma a presença da nova nota.

#### §3.1.4 Achado #5 — `outbox.registrar_outbox` exige `instance_id`

**Arquivo:** `backend/app/domain/outbox.py:25-33`

**Estado real do código (calibrado em 2026-05-21 — diferente da nota original):**
A assinatura atual **NÃO é keyword-only** — parâmetros são todos posicionais com defaults nos opcionais:

```python
def registrar_outbox(
    conn,
    tipo_evento:  str,
    objeto_tipo:  str,
    objeto_id:    str,
    payload:      dict[str, Any],
    org_id:       str | None = None,
    unidade_id:   str | None = None,
    instance_id:  str | None = None,   # ← opcional permite regressão silenciosa
) -> str | None:
    ...
```

**Mudanças necessárias:**

1. **Adicionar `*` antes de `instance_id`** para forçar keyword-only.
2. **Remover o default `None`** — vira obrigatório.
3. **Atualizar a docstring de `instance_id`** (linhas 50-55 atualmente dizem "Opcional para retrocompatibilidade com chamadas pré-4D"). Trocar para: `"UUID v4 da instância. **Keyword-only obrigatório desde 4E.2.** Caller obtém via get_instance_id_conn(conn) e passa para ledger e outbox no mesmo `with get_tx()` para garantir coerência forense."`

**Resultado esperado:**
```python
def registrar_outbox(
    conn,
    tipo_evento:  str,
    objeto_tipo:  str,
    objeto_id:    str,
    payload:      dict[str, Any],
    org_id:       str | None = None,
    unidade_id:   str | None = None,
    *,
    instance_id:  str,   # ← keyword-only OBRIGATÓRIO (4E.2)
) -> str | None:
    ...
```

**Atenção aos callers:** verificar com grep `registrar_outbox\(` em `app/routers/` antes de aplicar a mudança. Se algum caller ainda passar `instance_id` posicionalmente (improvável dada a 4D, mas vale checar), atualizar para keyword.

Verificação adicional (teste estático):
```python
# tests/test_outbox_hardening.py
def test_registrar_outbox_exige_instance_id():
    """Não permitir regressão silenciosa: chamada sem instance_id deve falhar."""
    import inspect
    from app.domain.outbox import registrar_outbox
    sig = inspect.signature(registrar_outbox)
    param = sig.parameters.get("instance_id")
    assert param is not None
    assert param.kind == inspect.Parameter.KEYWORD_ONLY
    assert param.default is inspect.Parameter.empty   # sem default = obrigatório
```

**Critério de aceite:**
- Grep `registrar_outbox\(` em `app/routers/` mostra zero chamadas sem `instance_id=`
- Suíte completa verde
- Novo teste estático passa

#### §3.1.5 Achado #8 — `first-boot` documentado como fallback

**Arquivo:** `backend/app/instance.py` (no bloco "2. First boot" dentro de `get_instance_id_conn`)

**Antes:** lógica de INSERT existe sem aviso de que é fallback.

**Depois:** adicionar docstring/comentário explícito + log de aviso:
```python
# Fallback defensivo: em produção, lifespan/startup popula meta_instalacao
# ANTES de qualquer request. Este bloco existe para os cenários onde o
# lifespan está intencionalmente desabilitado (testes/demo, conftest.py:37)
# ou onde o startup falhou silenciosamente. Se este caminho executar em
# produção, indica problema operacional.
import logging
logger = logging.getLogger(__name__)
logger.warning(
    "get_instance_id_conn fallback INSERT executado — verificar se lifespan rodou. "
    "Em produção, este caminho não deve ocorrer."
)
```

**Critério de aceite:** ler `app/instance.py` linha do INSERT já vê comentário + log.

#### §3.1.6 Achados #9, #10, #12 — Batch de docstrings

Consolidar três lapidações em commit único de docstrings:

**`backend/app/domain/outbox.py:6`** — Antes: "todo router que inserir em *_eventos **deve** chamar `registrar_outbox()`". Depois: "quando houver evento publicável previsto, o router deve chamar `registrar_outbox()` com o mesmo `instance_id` do ledger".

**`backend/app/domain/ledger.py:19`** — Antes: "4D — ainda não implementado". Depois: "Contrato aplicado pelos routers desde 4D (Etapa 4 fechada em 2026-05-21)".

**`backend/app/instance.py` (topo do módulo + docstrings de helpers)** — Adicionar destaque:
```
================================================================
ATENÇÃO: `instance_id` REPRESENTA A INSTALAÇÃO FÍSICA DO PICSAÚDE.
É um UUID v4 IMUTÁVEL gerado no primeiro boot da instância e
persistido em `meta_instalacao` + `.instance_id`. NÃO É um ID de
request, transação, sessão ou objeto. Todos os eventos de uma
mesma instalação compartilham o mesmo `instance_id`. Esta marca
d'água tem função forense: identificar a instalação de origem se
um row vazar. Ver DATA-PROTECTION.md §4.2.
================================================================
```

**Critério de aceite:** grep confirma os 3 textos novos presentes.

#### §3.1.7 Achado #11 — C5 do teste filtra por objetos do teste

**Arquivo:** `backend/tests/integration/test_4e_e2e_consolidado.py` (cenário C5, linhas ~470-510)

**Estado real do código (calibrado em 2026-05-21):**
C5 atualmente tem **duas asserções** consecutivas:

```python
# I1 universal: zero NULL em cada ledger (5 tabelas, query global)
for tabela in (
    "prescricao_eventos", "pedido_exame_eventos", "laudo_eventos",
    "agendamento_eventos", "circulacao_diagnostica_eventos",
):
    cur.execute(f"SELECT COUNT(*) FROM {tabela} WHERE instance_id IS NULL")
    assert cur.fetchone()[0] == 0, f"{tabela}: existem rows com instance_id NULL"

# I2 agregada: SELECT DISTINCT instance_id sobre UNION ALL dos 5 ledgers = 1 linha
cur.execute("SELECT DISTINCT instance_id FROM (UNION ALL dos 5)")
rows = cur.fetchall()
assert len(rows) == 1, f"esperado 1 instance_id distinto..."
```

**Problema:** I1 é frágil — qualquer row histórica em qualquer dos 5 ledgers com `instance_id IS NULL` quebra o teste (não foi quebra ainda só porque os `prescricao_eventos`/etc. dos testes anteriores não têm NULL — mas o briefing menciona drift de 210 rows em `eventos_publicacao`, e outras tabelas podem acumular o mesmo problema com o tempo).

**Mudança:** **manter I1 universal** (vale como smoke de higiene global) **mas mudar a mensagem de erro para sinalizar drift histórico, NÃO falhar o teste** quando o drift é claramente pré-existente; e **adicionar I3 focal** filtrando pelos objetos criados no próprio teste como guarda principal contra regressão do código novo.

**Spec do refactor — escolher uma das duas estratégias:**

**Estratégia A (preferida) — converter I1 para guarda focal estrita:**
Substituir o loop I1 inteiro por:
```python
# I1 focal (4E.2 §3.1.7): apenas eventos dos objetos criados neste teste —
# mitiga falso positivo se o banco de teste acumular rows pré-4D.1.
objetos_do_teste = [
    ("prescricao_eventos",              [prescricao_id]),
    ("pedido_exame_eventos",            [pedido_id]),
    ("laudo_eventos",                   [laudo_id]),
    ("agendamento_eventos",             [agendamento_id]),
    ("circulacao_diagnostica_eventos",  [circulacao_id]),
]
for tabela, ids in objetos_do_teste:
    cur.execute(
        f"SELECT COUNT(*) FROM {tabela} "
        f"WHERE objeto_id = ANY(%s) AND instance_id IS NULL",
        (ids,),
    )
    nulls = cur.fetchone()[0]
    assert nulls == 0, (
        f"{tabela}: {nulls} eventos dos objetos criados neste teste sem instance_id "
        f"(objeto_ids={ids}). Bug em código novo — não é drift histórico."
    )
```

I2 (UNION DISTINCT) **permanece como está** — ela já é insensível a NULL (DISTINCT ignora NULL na agregação) e o teste sobre `len(rows) == 1` valida o invariante canônico.

**Estratégia B (subsidiária, se A criar problema com nomes de variável ainda não disponíveis no escopo):**
Manter I1 + adicionar I3 filtrado depois — mais defensivo mas mais código.

**Code escolhe estratégia A se possível. Se variáveis dos objetos do teste não estão disponíveis no escopo de C5, escalar e perguntar.**

**Critério de aceite:**
- C5 passa
- Mensagem de erro nova é informativa sobre objetos do teste
- Suíte completa verde (123 passed pós-implementação inalterada)

---

### §3.2 Ticket separado Regra 2 — Achado #2 (`custodia.py:616`)

Este achado **toca core de custódia clínica** — exige ticket formal Regra 2 estrita.

**Arquivo a redigir:** `backend/docs/tickets/TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md`

**Conteúdo mínimo:**
- §1 Contexto regulatório (devolução é evento que entra em auditoria; vocabulário separado já existe em CLAUDE.md §2)
- §2 Escopo (toca apenas `custodia.py:devolver_item` + testes; não toca outros endpoints de devolução)
- §3 Fix proposto:
  - Escolher `tipo_evento` conforme `payload.para` (`paciente` → `item_devolvido_paciente`; `prescritor` → `item_devolvido_prescritor`)
  - Capturar `usuario=Depends(require_role(...))` e gravar `ator_tipo`/`ator_id` corretos (não hardcode `dispensador`/`sistema`)
- §4 Critérios de aceite + testes
- §5 Predecessoras: este relatório (4E.2)
- §6 Sucessor: Etapa 5

**Quem redige o ticket:** Arquiteto (depois do fechamento da 4E.2 propriamente dita)
**Quem implementa:** Code, no ciclo Regra 2 estrita (CODEX revisa o ticket → Code implementa → CODEX revisa pós-implementação)

---

### §3.3 Tickets pós-4E.2 — Não bloqueiam o fechamento da Etapa 4

#### §3.3.1 Achado #6 — Cobertura de testes adicional

**Arquivo a redigir (pós-fechamento Etapa 4):** `backend/docs/tickets/TICKET-COBERTURA-LEDGER-COMPLEMENTAR.md`

**Escopo:** testes focados curtos para os ledgers que a Etapa 4 migrou mas a 4E.1 não cobriu por endpoint:
- `receituarios.py:398` — `receituarios_gerados`, `receituarios_numerados`, `receituario_emitido`
- `hospitalares.py:351` — `dispensacao_hospitalar_registrada`
- `assinaturas.py:324` — `pdf_assinado_pades`, `assinatura_registrada`

**Forma:** um teste focal por evento + uma checagem estática que falhe se qualquer router chamar `registrar_evento_ledger` sem `instance_id=` (mecanismo geral contra regressão futura).

**Pacto:** Regra 3 simplificada (cada teste ~20 linhas, não core).

**Pré-Etapa 5:** sim, recomendado fechar antes do deploy.

#### §3.3.2 Achado #4 (acompanhamento) — Auditoria completa das máquinas de devolução

**Arquivo a redigir (pós-Etapa 5):** `backend/docs/tickets/TICKET-COERENCIA-DEVOLUCOES.md`

**Escopo:** auditoria estrutural dos fluxos de devolução em `auth.py`, `custodia.py`, `hospitalares.py`.

**Pacto:** Regra 2 estrita — classe `core`, mexe em endpoints de produção e em `TRANSICOES_PRESCRICAO`/`TRANSICOES_ITEM`.

**Pré-Etapa 5:** **não** — pode ficar para Etapa 6+. A inconsistência é pré-existente e está documentada no código.

---

## §4 ADR-001 — Propagação explícita de `instance_id` é design

**Status:** Adotado (2026-05-21)
**Origem:** Resposta arquitetural à sugestão Jules P2-J #1 (achado #7) de "esconder `instance_id` dentro dos helpers, lendo cache global".

### §4.1 Contexto

A Etapa 4 do PicSaúde introduziu o conceito de **`instance_id` canônico** — marca d'água da instalação física, UUID v4 imutável, propagado de cada caller para o helper `registrar_evento_ledger`/`registrar_outbox` via parâmetro `keyword-only`.

A revisão Jules (4E.2, 2026-05-21) sugeriu remover essa propagação: helpers leem o valor de cache global em memória, o caller não passa nada. Argumento: simplificação, redução de boilerplate, menor chance de o caller esquecer.

### §4.2 Decisão

**Manter a propagação explícita.** O caller passa `instance_id=...` em cada chamada de ledger/outbox. Helpers exigem o parâmetro `keyword-only`. Helpers não leem variável global para gravar `instance_id`.

### §4.3 Consequências

**A favor da decisão (e contra a sugestão Jules):**

1. **Auditoria é arquitetura** (Princípio 2 do CLAUDE.md). Quando um auditor (juiz, fiscal sanitário, ANVISA) abrir o código fonte de `prescricoes.py:155` para entender o que foi gravado no ledger, ele deve enxergar **literalmente** qual `instance_id` está sendo gravado. Esconder no helper transfere essa rastreabilidade para um nível de indireção — torna a auditoria pelo código fonte impraticável sem rastreio dinâmico.

2. **A Etapa 4 inteira foi desenhada nessa tese.** 4A criou o helper, 4B criou o schema, 4C criou `registrar_evento_ledger` exigindo o parâmetro, 4D.1 + 4D.2 migraram 34 callers. Aceitar a sugestão Jules reverteria as 4D inteiras, reabriria 5 ledgers, exigiria nova auditoria CODEX, e essencialmente recomeçaria a Etapa 4.

3. **A preocupação válida do Jules ("dev novo esquece") é mitigada pelo `keyword-only` obrigatório** — desde 4C, chamadas a `registrar_evento_ledger` sem `instance_id=` levantam `TypeError` no import-time/parse-time. O único caso de regressão silenciosa que existia era `registrar_outbox` (CODEX P2-D), e o achado #5 deste relatório fecha esse buraco.

**Contra a decisão (custos aceitos):**

1. Boilerplate visual permanece. Cada router lê `instance_id = get_instance_id_conn(conn)` no início da transação e o passa adiante. ~3 linhas extras por endpoint. Cache do achado #1 mitiga o custo de I/O.

2. Dev novo precisa entender por que esse parâmetro existe. O batch de docstrings (§3.1.6) é a contramedida — explicação clara em destaque no topo de `app/instance.py`.

### §4.4 Quando reconsiderar

Reconsiderar esta ADR se:
- Surgir framework de OpenTelemetry com contexto de request integrado nativamente (tornaria viável `instance_id` viver no contexto sem perder rastreabilidade)
- A escala do PicSaúde ultrapassar 100 instalações federadas, onde a propagação manual vire fonte concreta de bugs apesar do `keyword-only`
- Auditoria sanitária formalizar que rastreio dinâmico (logs/traces) é equivalente a leitura de código (improvável a curto prazo)

### §4.5 Referência

- `docs/revisoes/JULES-4E-2-relatorio-2026-05-21.md` §3.1 (achado original)
- `docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md` §3.4 (hardening complementar)
- CLAUDE.md §10 (classe `core` exige aprovação central — esta decisão é arquitetural)
- DATA-PROTECTION.md §4.2 (semântica de `instance_id` como marca d'água forense)

---

## §5 Itens pré-identificados do briefing — status final

Dois itens estavam pré-classificados em §4.6 do `TICKET-4E-BRIEFING-PARA-CODEX.md`:

| Item | Status final |
|---|---|
| Docstring `outbox.py:6` contradiz decisão 4D | ✅ Confirmado pelo CODEX (achado #9). Tratamento: §3.1.6. |
| 210 rows `instance_id IS NULL` em `eventos_publicacao` no banco de teste | ✅ Confirmado pelo CODEX (achado #11). Tratamento: filtragem por objetos do teste em §3.1.7. **Não exige TRUNCATE no conftest** — a filtragem resolve o falso positivo sem precisar tocar o estado histórico do banco de teste. Drift remanescente é dívida operacional, registrar para Etapa 6+ se voltar a importunar. |

---

## §6 Aplicação dos fixes — Sequência sugerida

### §6.1 Batch único Regra 3 (Code aplica em uma sessão)

Code lê este relatório, aplica os 7 fixes da §3.1 em commit único:
```
fix(4e-2): lapidações pós-Regra 5

- cache lru de instance_id (§3.1.1)
- assinaturas: ator_id agora vem do sub do JWT (§3.1.2)
- states.py: estende nota documentada para auth.py:devolver_prescritor (§3.1.3)
- outbox: instance_id agora keyword-only obrigatório + teste estático (§3.1.4)
- instance.py: documenta first-boot como fallback + log warning (§3.1.5)
- batch de docstrings: outbox.py + ledger.py + instance.py (§3.1.6)
- test_4e_e2e_consolidado.py: C5 filtra por objetos do teste (§3.1.7)

Refs: TICKET-4E-2-RELATORIO-INTEGRADO.md §3.1
```

**Verificação automatizada antes do commit:**
```bash
cd backend
python3 -m pytest tests/test_instance_id.py tests/integration/test_4e_e2e_consolidado.py -v
python3 -m pytest tests/test_outbox_hardening.py -v   # novo teste estático
grep -RnI "registrar_outbox(" app/routers/ | grep -v "instance_id="   # esperado: zero
```

### §6.2 Ticket separado Regra 2 (§3.2)

Arquiteto redige `TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md` **após** o batch §6.1 ser commitado. O ciclo formal (CODEX redige → Arquiteto valida → Code implementa → CODEX revisa pós-implementação) acontece em sessão posterior. **Não bloqueia o fechamento administrativo da Etapa 4** — o achado é P2 mas o fix é isolado e auditável separadamente.

### §6.3 Tickets pós-fechamento (§3.3)

- `TICKET-COBERTURA-LEDGER-COMPLEMENTAR.md` — redigir antes da Etapa 5 (recomendado)
- `TICKET-COERENCIA-DEVOLUCOES.md` — redigir junto com Etapa 6 ou quando dor concreta aparecer

---

## §7 Critérios de fechamento da 4E.2 (= fechamento da Etapa 4) — ✅ TODOS CUMPRIDOS

- [x] Batch §3.1 commitado e pushado — commit `9cc339f` `fix(4e-2): lapidações pós-Regra 5`
- [x] Suíte da Etapa 4 verde após o batch — **124 testes passed**, 0 failed
- [x] Teste estático novo `tests/test_outbox_hardening.py` passa
- [x] Grep `registrar_outbox(` em routers sem `instance_id=` retorna zero
- [x] Ticket `TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md` redigido **e implementado** — commit `9ef3bb2` (`fix(custodia): item_devolvido genérico vira item_devolvido_{paciente,prescritor}`)
- [x] `docs/PLANO-PRODUCAO-V2.md` marca Etapa 4 como ✅ Fechada com referência aos hashes finais
- [x] `backend/CLAUDE.md` e `backend/docs/PROMPT-OPUS-4.7-ARQUITETO.md` atualizados com a 4E.2 fechada
- [x] Memória `picsaude_estado_2026_05_21.md` atualizada com snapshot pós-Etapa 4

**Status oficial:** Etapa 4 fechada em 2026-05-21. Próximo: Etapa 5 (Fix B1).

## §10 Calibrações do Code durante implementação do §3.1 (2026-05-21)

Code identificou 4 imprecisões na spec do §3.1 ao implementar — todas tratadas corretamente, aprovadas pelo Arquiteto antes do push do `9cc339f`. Registrar para trilha de auditoria:

| # | Spec §3.1 dizia | Realidade encontrada | Decisão do Code | Análise Arquiteto |
|---|---|---|---|---|
| 1 (§3.1.1) | Cache lru sem especificar ordem vs env override | Testes existentes assumem env override sempre vence | Env override **antes** do cache. Cache só pega quando env não está setada. | ✅ Aprovado. Preserva coerência forense; latência otimizada onde importa (prod sem env override) |
| 2 (§3.1.1) | "conftest.py" sem qualificar qual | `test_get_instance_id_conn_funciona_com_pgconnection_wrapper` está em `tests/`, não em `tests/integration/` | Fixture autouse colocada em `backend/conftest.py` raiz, não em `tests/integration/conftest.py` | ✅ Aprovado. Garante reset em qualquer escopo de teste |
| 3 (§3.1.4) | "remover" `test_outbox_sem_instance_id_continua_funcionando_silencioso` | Teste captura comportamento pré-4E.2 que estamos eliminando | **Reescrito** (não removido) — agora asserta `TypeError`, preservando cobertura ativa da guarda nova | ✅ Aprovado. Sugestão minor pendente: renomear para `_levanta_typeerror` (não bloqueador) |
| 4 (§3.1.7) | Spec usava `objeto_id` genérico para filtragem | Ledgers internos têm FK específica por subdomínio (`prescricao_id`, `pedido_id`, etc.); `objeto_id` só existe em `eventos_publicacao` | I1 do C5 usa FK específica por ledger; IDs capturados via `r.json()["id"]` ou `SELECT WHERE protocolo = %s` quando o endpoint só retorna protocolo | ✅ Aprovado. Spec original era imprecisa; calibragem preserva o invariante de regressão |

**Métricas finais do batch `9cc339f`:**
- Pytest: 124 passed (+1 do `test_outbox_hardening`), 0 failed
- Diff stat: 9 arquivos, +196 −55, **net 84 linhas reais** (abaixo do threshold de 150 → Regra 3 mantida)
- Verificações automatizadas §6.1: todas verde
- Pacto: Regra 3 (commit único) cumprido

---

## §8 Avaliação do pacto de desenvolvimento

A Regra 5 (revisão estática consolidada ao fim da etapa por CODEX + Jules) **funcionou como previsto**:

| Critério | Resultado |
|---|---|
| Revisores entregaram material acionável | ✅ Sim — 12 achados específicos com arquivo:linha |
| Lentes complementares produziram pontos cegos distintos | ✅ Sim — quase zero sobreposição (§5/§6 dos relatórios fonte) |
| Zero P1 reais ao final da etapa | ✅ Sim — todos os achados são P2/P3 tratáveis sem reabrir arquitetura |
| Conflito direto entre revisores foi tratado pelo Arquiteto sem escalada | ✅ Sim — ADR-001 registrada |
| Itens pré-identificados foram confirmados pelos revisores externos | ✅ Sim — 2/2 (outbox.py:6 e drift 210 rows) |
| Custo de coordenação foi proporcional | ✅ Sim — 1 sessão Arquiteto integrar (este documento) |

**Sugestão de calibração para a Etapa 5:** manter Regra 5 inalterada. Considerar se faz sentido pedir lente adicional (Gemini-pragmático teve overlap baixo com CODEX — talvez ChatGPT-LGPD ou ChatGPT-regulatório seja a terceira lente em etapas que toquem dados pessoais ou normas sanitárias).

---

## §9 Próximos passos imediatos — TODOS CONCLUÍDOS em 2026-05-21

1. ✅ **Fabiano aprovou este documento** (revisão final no fluxo CODEX rodada 1 sobre o ticket).
2. ✅ **Arquiteto redigiu `TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md`** e **Code implementou** — commit `9ef3bb2` pushado.
3. ✅ **Code recebeu spec do §3.1** e aplicou o batch único Regra 3 — commit `9cc339f`.
4. ✅ **Verificação pytest pós-batch** — 124 testes verdes. Diff net 84 linhas (sem necessidade de Regra 2 estrita).
5. ✅ **Fabiano commitou + pushou** os 3 commits da 4E.2: `ab1c897` + `9ef3bb2` + `9cc339f`.
6. ✅ **Arquiteto atualizou `PLANO-PRODUCAO-V2.md` + `CLAUDE.md` + `PROMPT-OPUS-4.7-ARQUITETO.md`** marcando Etapa 4 ✅.
7. ✅ **Memória atualizada** (`picsaude_estado_2026_05_21.md`, 4 checkpoints).

**Próxima sessão:** Etapa 5 (Fix B1 carteira digital 422). Antes disso, considerar redigir `TICKET-COBERTURA-LEDGER-COMPLEMENTAR.md` para fechar a cobertura focal pendente (achado #6 CODEX).
