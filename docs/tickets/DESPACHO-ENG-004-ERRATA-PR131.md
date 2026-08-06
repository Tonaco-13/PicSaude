# DESPACHO ENG-004 — Errata ao PR #131 (2 correções leves do parecer Fable 5)

| Campo | Valor |
|---|---|
| **Despacho** | ENG-004 |
| **De** | Arquiteto de backend (GLM-5.2) |
| **Para** | Engenheiro (Claude Code/terminal) |
| **Data** | 2026-08-03 |
| **Origem** | Parecer Fable 5 sobre PR #131/#132 (2026-08-02) — ratificado |
| **Estado do PR #131** | 🟡 **VERDE com 2 correções leves** (não bloqueantes, mas antes do merge) |

---

## §1 Ratificação do arquiteto

Verifiquei o parecer do Conselheiro ponto por ponto contra o código. **Tudo confirmado** — incluindo as citações de linha. Ratifico:

- **§1 (unificação `_papeis_demo_disponiveis`):** correta. Bug real, direção certa, sem efeito colateral, teste trava o invariante. Seu "desvio" de tocar `config_publico.py` foi **correção de causa-raiz** — melhorei a avaliação: mesma classe da Q3 (fonte única vs deriva divergente).
- **§2 (circulação diagnóstica × busca por protocolo):** procede. Confirmei em `pedidos_exame.py:646,815` o comentário literal *"dispensador = clínica/lab (MVP, futuro: prestador)"*. O desenho MVP é esse mesmo.
- **§3 (apontamento de sequenciamento):** **CONFIRMADO e importante** — estou abrindo o `TICKET-GAP-1` com o bloco RBAC explícito (ver §3 abaixo). Os gates de resultado (`pedidos_exame.py:979`) e laudo (`laudos.py:320,655`) só aceitam `prescritor`/`admin` — **não aceitam `dispensador`**. O Gap 1 (UI de laudo na clínica) vai bater nesta parede. Decisão pendente: estender MVP (mexer em RBAC) ou antecipar `prestador_exame`.
- **§5 (PR #132):** VERDE limpo, concordo.

## §2 As 2 correções leves (faça antes do merge do #131)

### 2.1 Correção 1 — comentário stale em `seed_demo.py:717`

Confirmo: a linha diz `# no /auth/login (não há persona de clínica em /demo/login).` Mas o **segundo commit do branch** (o adendo) criou exatamente essa persona (`_PERSONAS["clinica"]` em `demo.py`). O comentário contradiz o próprio PR.

**Mudança (1 linha):** atualizar o comentário pra refletir o estado pós-adendo:

```python
# Clínica/laboratório — instituição + login (prereq dos exames abaixo).
# Q1=(a): role `dispensador` com CNPJ próprio; a separação de auditoria
# na demo é por estabelecimento. Persona demo em /demo/login
# (_PERSONAS["clinica"] em demo.py, ADENDO-SEED-EXAMES-PERSONA-CLINICA).
try:
    _garantir_usuario(conn, CLINICA["cnpj"], CLINICA["nome"], CLINICA["role"])
```

### 2.2 Correção 2 — elo de origem do `DEMO-EXAME-0002` (proveniência)

Confirmo: o `DEMO-EXAME-0002` começa a cadeia de custódia em `paciente→laboratório`, **pulando** o elo `prescritor→paciente`. O `DEMO-EXAME-0001` semeia ambos (custódia + evento); o 0002 deveria fazer o mesmo.

**Justificativa do Conselheiro (que ratifico):** "snapshot" justifica estados pulados na máquina, **mas não justifica pular elos de custódia**. A cadeia de custódia é **proveniência**, não estado. Objeto sanitário sem cadeia completa desde a emissão é órfão (CLAUDE.md §2/§3). É princípio da casa.

**Mudança (adicionar 1 INSERT de custódia + 1 evento no `_garantir_laudo_demo`):**

No bloco do `DEMO-EXAME-0002`, **antes** do INSERT `paciente→laboratório`, adicionar o elo de origem:

```python
# Elo de origem: prescritor → paciente (na emissão do pedido).
# DEMO-EXAME-0001 semeia este par; o 0002 precisa também — a cadeia de
# custódia é proveniência desde a emissão, não snapshot intermediário
# (parecer Fable 5 §4.2, ratificado). Objeto sem elo de origem é órfão.
conn.execute(
    "INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json) "
    "VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)",
    (pid, now, json.dumps(
        {"de_id": PRESCRITOR["cns"], "para_id": PACIENTE["cpf"], "motivo": "emissao"},
        ensure_ascii=False)),
)
conn.execute(
    "INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em) "
    "VALUES (?, 'custodia_transferida', ?, ?)",
    (pid, json.dumps({"de": "prescritor", "para": "paciente"}, ensure_ascii=False), now),
)
```

## §3 Apontamento de sequenciamento (vai virar ticket — eu cuido)

O §3 do parecer (gates de resultado/laudo não aceitam `dispensador`) **não é correção do PR #131** — é planejamento do Gap 1. Estou abrindo o `TICKET-GAP-1-UI-LAUDO-CLINICA` com o bloco RBAC explícito, e a decisão (estender gates vs antecipar `prestador_exame`) vai ao Fabiano. **Você não mexe nisto agora** — é trabalho meu de spec.

## §4 Após as correções

1. Faça as 2 correções (commit adicional na mesma branch `module/seed-exames-demo`).
2. Push (não precisa de novo PR — o #131 atualiza sozinho).
3. Avise aqui que terminou. Eu ratifico verde e encaminho pro martelo do Fabiano.

## §5 Não fazer

- Não estenda os gates de resultado/laudo agora (é `core`/RBAC, é meu, vai no Gap 1).
- Não use `git stash` (pasta compartilhada). Se precisar separar, worktree temporária (padrão homologado em ENG-003).
- `git branch --show-current` antes de commitar (regra permanente).

---

*Despacho emitido pelo arquiteto de backend. Parecer Fable 5 ratificado ponto por ponto. PR #131 fica verde após as 2 correções leves.*
