# ADR-002 — Helper compartilhado de ownership check no 5C-bis

| Campo | Valor |
|---|---|
| **Status** | Accepted |
| **Data** | 2026-05-30 |
| **Decisor** | Engenheiro-Arquiteto (Code workspace), sob calibração 2026-05-28 |
| **Origem** | [TICKET-5C-BIS-0-HELPER-OWNERSHIP](../tickets/TICKET-5C-BIS-0-HELPER-OWNERSHIP.md) v0.2 (CODEX rodada 0 integrada 2026-05-26) |
| **Commit analisado** | `43664f4` (HEAD em 2026-05-30) |
| **Predecessores** | TICKET-5C (autorização nos 11 endpoints ambulatoriais) fechado em `01c67fa` |
| **Sucessores** | TICKET-5C-BIS-A (pedidos_exame), B (laudos), C (agendamentos), D (circulação), E (hospitalar) |
| **Arquivos lidos** | `backend/app/routers/{pedidos_exame,laudos,agendamentos,circulacao_diagnostica,hospitalares}.py` |

> **Nota de governança:** esta é a **primeira ADR registrada como arquivo separado** no repositório. ADR-001 está embutida no relatório do TICKET-4E-2 (`backend/docs/tickets/TICKET-4E-2-RELATORIO-INTEGRADO.md`), não como arquivo dedicado em `decisoes/`. Esta ADR cria a pasta `backend/docs/decisoes/` no próprio commit que registra a decisão.

---

## §1 Contexto

O TICKET-5C fechou autorização mínima em 11 endpoints clínicos ambulatoriais (commit `01c67fa`, CODEX rodada 2 zero P1, 2026-05-22). A decisão estratégica de 2026-05-26 ampliou o MVP para incluir os 5 subdomínios sucessores antes do deploy público (Etapa 8): exames, laudos, agendamentos, circulação diagnóstica, hospitalar.

O TICKET-5C-BIS-0 (spike) foi aberto para decidir, **antes de redigir os tickets A-E**, se faz sentido extrair um helper compartilhado de ownership check entre os 5 subdomínios, ou se cada subdomínio deve continuar com checagem local. A escolha é vinculante para os 5 tickets seguintes (não revisitar depois).

### §1.1 Leitura concreta dos 5 routers (2026-05-30)

| Router | Endpoints reais | Captura `usuario=` | Descarta `_=` | Bug ativo |
|---|---|---|---|---|
| `pedidos_exame.py` | 11 | 0 | 11 | sim — todos vulneráveis |
| `laudos.py` | 12 | 1 (`ciencia-paciente`) | 11 | sim — inclusive o `usuario=` capturado não valida ownership |
| `agendamentos.py` | 8 | 2 (`criar`, `remarcar`) | 6 | sim — captura sem validar |
| `circulacao_diagnostica.py` | 7 | 6 | 1 | sim — `criar` captura mas não valida que paciente é dono do pedido |
| `hospitalares.py` | 1 | 0 | 1 | sim — caso especial, vínculo via duas hops `CNPJ → unidades.unidade_id` |
| **Total** | **39** | **9** | **30** | **39/39 com gap** |

**Conclusão:** o gap de ownership está espalhado por TODOS os 39 endpoints, com **8 chaves de identidade distintas** (CNS prescritor, CNS autor de laudo, CPF paciente, CNPJ prestador ambulatorial, CNPJ dispensador hospitalar via `unidades.unidade_id`, `org_id` do agendamento, `chave_circulacao`, `dispensacao_id`). Heterogeneidade confirmada — não é caso de generalizar uma query única.

### §1.2 Padrões observados (reaproveitando §2.1 do spike)

O spike v0.2 classificou as vulnerabilidades V1-V11 do 5C original em 5 padrões dominantes. A leitura dos 5 routers do 5C-bis confirma que os mesmos padrões se repetem, com expansão para os casos D matriz e E composto:

| Padrão | Caracterização | Endpoints do 5C-bis encaixados |
|---|---|---|
| **A** — payload-vs-JWT | Objeto ainda não existe; compara identidade declarada vs JWT | POST `criar` em todos os 5 routers (5 endpoints) |
| **B** — SQL JOIN | Objeto existe; query confirma ownership por JOIN com tabela de atores | GET `{protocolo}` em pedidos/laudos (4 endpoints) |
| **C** — row em memória | Objeto já buscado antes; check reusa row sem nova query | GET pdf/qr em pedidos/laudos (6 endpoints) |
| **D** — matriz multi-role | Múltiplos atores legítimos, cada um com critério próprio; admite custodiante histórico | GET custódia em pedidos/laudos (2 endpoints) + listar agendamentos (1 endpoint) |
| **E** — mutação composta | Mutação + ownership + semântica de payload (ex: papel declarado, transição declarada) | POST agendar/coletar/cancelar/resultado/encerrar/assinar/liberar/ciencia × 2/dispensar hospitalar/circulação 6 endpoints |

Padrões B e C são candidatos óbvios a helper; A pode caber com cuidado; D exige adaptador por subdomínio; E fica sempre local.

---

## §2 Decisão

**Adotar Opção C estendida — três helpers compartilhados pequenos, sem ambição genérica, e queries de ownership locais a cada subdomínio.**

A decisão segue a hipótese de trabalho apontada pelo CODEX rodada 0 (§10 do spike), com refinamento: além do `_assert_or_403` previsto na opção C original, adicionamos dois helpers de normalização que separam **identidade** (puro, sem DB) de **vínculo institucional** (com DB, isolado). Essa separação é a correção principal do parecer CODEX rodada 0 — sem ela, A parecia limpa no papel e quebrava no E hospitalar (duas hops).

### §2.1 Os três helpers

#### Helper 1 — `_assert_or_403`

```python
# Mora em: app/utils/helpers.py
# Puro, sem DB, sem dependência de FastAPI além de HTTPException.

def _assert_or_403(
    condicao: bool,
    codigo: str,
    mensagem: str,
) -> None:
    """
    Garante uma condição de ownership ou levanta 403 com formato padrão.

    O formato {codigo, mensagem} em português é o contrato estabelecido em §3.5
    do TICKET-5C-AUTORIZACAO-MINIMA e replicado nos handlers do 5C original.

    Uso:
        _assert_or_403(
            usuario_cns == row["cns_prescritor"],
            codigo="ownership_negada",
            mensagem="Apenas o prescritor pode encerrar este pedido.",
        )
    """
    if not condicao:
        raise HTTPException(
            status_code=403,
            detail={"codigo": codigo, "mensagem": mensagem},
        )
```

**Escopo:** centraliza o raise HTTPException com formato `{codigo, mensagem}` em português. NÃO faz query, NÃO comparação, NÃO normalização. Recebe um booleano já avaliado.

#### Helper 2 — `_normalizar_identidade_jwt`

```python
# Mora em: app/utils/helpers.py
# Puro, sem DB.

def _normalizar_identidade_jwt(usuario: dict) -> tuple[str, str]:
    """
    Extrai (papel, identificador canônico) do payload JWT.

    O identificador canônico é a chave que aparece nas tabelas clínicas:
      - prescritor   → CNS (15 dígitos)
      - paciente     → CPF (11 dígitos)
      - dispensador  → CNPJ (14 dígitos)
      - auditor      → identificador admin (sem chave clínica)
      - admin        → identificador admin (sem chave clínica)

    Retorna a TUPLA (papel, identificador) já normalizada (sem máscara,
    sem espaços). Útil para alimentar comparações diretas e queries.

    Para o caso hospitalar, retornar o CNPJ raw — a tradução para
    unidade_id é trabalho do Helper 3, NÃO daqui (separação de
    identidade × vínculo institucional, conforme CODEX rodada 0 do spike).

    Uso:
        papel, ident = _normalizar_identidade_jwt(usuario)
        if papel == "prescritor":
            _assert_or_403(
                ident == row["cns_prescritor"],
                codigo="ownership_negada",
                mensagem="Apenas o prescritor que emitiu pode...",
            )
    """
    papel = usuario.get("role", "")
    sub_raw = usuario.get("sub", "")
    ident = "".join(c for c in sub_raw if c.isdigit())  # strip non-digit
    return papel, ident
```

**Escopo:** normalização pura. Strip de máscaras, espaços, formatação. NÃO faz query, NÃO valida vínculo institucional.

#### Helper 3 — `_unidade_id_do_dispensador`

```python
# Mora em: app/auth/ownership.py (NOVO arquivo)
# Toca DB — isola a query de duas hops do caso hospitalar.

def _unidade_id_do_dispensador(conn, cnpj: str) -> str | None:
    """
    Resolve o `unidade_id` do dispensador hospitalar a partir do CNPJ no JWT.

    Caminho de duas hops (apontado pelo CODEX rodada 0 do spike, achado §2.3):
        JWT.sub (CNPJ raw)
        → prestadores.cnpj == ?
        → unidades.org_id == prestadores.org_id (1:N — uma org pode ter N unidades)
        → retorna unidade_id

    Caso multi-unidade do mesmo CNPJ: retorna a primeira encontrada.
    Caso especial: se a query precisar de uma unidade específica (ex: dispensação
    em unidade X mas dispensador trabalha em N unidades), o ticket E deve receber
    `unidade_id` no payload e comparar — NÃO inferir.

    Retorna None se o CNPJ não tem prestador cadastrado ou se nenhuma unidade
    está vinculada. O caller decide se isso é 403 ownership ou 404 unidade
    não encontrada (semântica fica local).

    Uso (no TICKET-5C-BIS-E):
        papel, cnpj = _normalizar_identidade_jwt(usuario)
        unidade_jwt = _unidade_id_do_dispensador(conn, cnpj)
        _assert_or_403(
            unidade_jwt == payload.unidade_id,
            codigo="vinculo_institucional_negado",
            mensagem="Dispensador não tem vínculo com a unidade declarada.",
        )
    """
    # implementação concreta vira parte do TICKET-5C-BIS-E
    ...
```

**Escopo:** isola a única query de duas hops específica do caso hospitalar. Sem este helper, o TICKET-E reescreve esta query inline — exatamente o cenário que o CODEX rodada 0 alertou ("A parece limpa no papel e quebra em E").

### §2.2 Cobertura dos 5 padrões com os 3 helpers

| Padrão | Composição típica | Notas |
|---|---|---|
| **A** payload-vs-JWT | `_normalizar_identidade_jwt` + comparação inline + `_assert_or_403` | Sem query. POST criar. |
| **B** SQL JOIN | Query local + `_assert_or_403` | Query é específica do subdomínio (cns_prescritor / cpf_paciente / cnpj_prestador). |
| **C** row em memória | `_normalizar_identidade_jwt` + comparação com row local + `_assert_or_403` | Reusa row já buscado para outra finalidade. |
| **D** matriz multi-role | Switch local por `papel` + queries específicas + `_assert_or_403` | Não cabe em helper genérico. Auditor passa sem query; outros papéis cada um com critério próprio. |
| **E** mutação composta | `_normalizar_identidade_jwt` + query local + check de payload + `_assert_or_403`; no caso hospitalar também `_unidade_id_do_dispensador` | Helper 3 só aparece no caso hospitalar. |

---

## §3 Implicações concretas para os 5 tickets

### TICKET-5C-BIS-A (`pedidos_exame.py`)

**Volume estimado:** ~250 linhas. **11 endpoints.** Distribuição esperada por padrão:
- Padrão A: POST criar + POST /fisica (2)
- Padrão B: GET `{protocolo}` (1)
- Padrão C: GET pdf + GET qr (2)
- Padrão D: GET custódia (1)
- Padrão E: agendar, coletar item, resultado item, cancelar, encerrar (5)

**Helpers usados:** 1, 2 — não usa Helper 3 (não há caso hospitalar aqui).

### TICKET-5C-BIS-B (`laudos.py`)

**Volume estimado:** ~280 linhas. **12 endpoints.** Tem a peculiaridade do "responsável técnico" (CNS autor ≠ CNS prescritor) e da ciência múltipla (paciente + prescritor).

Distribuição esperada:
- Padrão A: POST criar + POST /fisica (2)
- Padrão B: GET `{protocolo}` (1)
- Padrão C: GET pdf + GET qr (2)
- Padrão D: GET custódia (1)
- Padrão E: assinar, liberar, ciência-paciente, ciência-prescritor, encerrar, cancelar (6)

**Bug específico já identificado:** `ciencia-paciente` (L571) captura `usuario=` mas não valida que `usuario.cpf == laudo.cpf_paciente`. TICKET-B deve fechar.

**Helpers usados:** 1, 2.

### TICKET-5C-BIS-C (`agendamentos.py`)

**Volume estimado:** ~200 linhas. **8 endpoints.** Particularidade: vínculo do prestador é via `org_id` + `unidade_id` (não CNPJ direto).

Distribuição esperada:
- Padrão A: POST criar agendamento (1)
- Padrão D: GET listar por pedido (1)
- Padrão E: confirmar, realizar, cancelar, não-compareceu, remarcar (5)
- Padrão B: GET `{protocolo}` (1)

**Helpers usados:** 1, 2 (e potencialmente uma variante do Helper 3 para `org_id`/`unidade_id` — discutir no TICKET-C antes de implementar; se a query for trivial e única, mantém local).

### TICKET-5C-BIS-D (`circulacao_diagnostica.py`)

**Volume estimado:** ~180 linhas. **7 endpoints.** Vínculo via `chave_circulacao` (chave própria do objeto).

Distribuição esperada:
- Padrão A: POST criar (1)
- Padrão B: GET `{chave}` (1)
- Padrão E: proposta, confirmar, desmarcar, realizar, remarcar (5)

**Bug específico já identificado:** `criar` (L205) captura `usuario=paciente` mas não valida que `usuario.cpf == pedido.cpf_paciente`. TICKET-D deve fechar.

**Helpers usados:** 1, 2.

### TICKET-5C-BIS-E (`hospitalares.py`)

**Volume estimado:** ~120 linhas. **1 endpoint** + absorve TICKET-5C-FOLLOWUP-CUSTODIA-HOSPITALAR (§7.1 do 5C). Caso especial — único que usa o **Helper 3**.

Distribuição:
- Padrão E composto com vínculo institucional via duas hops (1)

**Helpers usados:** 1, 2, **3**.

---

## §4 Alternativas consideradas

### Opção A — helper completo (rejeitada)

Proposta: um único helper `assert_ownership(conn, usuario, objeto, papel_esperado, ...)` que faria a query interna e o raise.

**Por que rejeitada:** 8 chaves de identidade distintas (CNS prescritor, CNS autor, CPF paciente, CNPJ prestador, CNPJ → unidade_id hospitalar, org_id, unidade_id direto, chave_circulacao). Helper único viraria fábrica parametrizada com >10 argumentos e múltiplos caminhos internos — pior do que o código local. Caso hospitalar (duas hops) explicitamente não cabe na assinatura genérica. CODEX rodada 0 já apontou este risco em §10 achado #4.

### Opção B — manter local em cada subdomínio (rejeitada)

Proposta: cada router implementa seu próprio raise, sem helper.

**Por que rejeitada:** o formato do erro `{codigo, mensagem}` em português é contrato público do PicSaúde (§3.5 do TICKET-5C-AUTORIZACAO-MINIMA). Replicar o raise em ~30 lugares aumenta a superfície de regressão — basta um erro de digitação em "mensgem" para quebrar contrato. O helper `_assert_or_403` é trivial de manter (5 linhas) e elimina essa categoria de erro.

### Opção C original — só `_assert_or_403` (rejeitada parcialmente — escolhemos versão estendida)

Proposta: apenas o helper de raise; tudo o mais local.

**Por que rejeitada na forma minimal:** sem `_normalizar_identidade_jwt`, cada router reimplementa a strip de dígitos no `usuario["sub"]` — exatamente o tipo de duplicação trivial que causa drift entre subdomínios. E sem `_unidade_id_do_dispensador`, o TICKET-E volta a embutir a query de duas hops inline — bug-prone e difícil de auditar.

A versão estendida adiciona 2 helpers mínimos que isolam **identidade pura** e **vínculo institucional** (correção principal do CODEX rodada 0).

---

## §5 Localização dos helpers

| Helper | Arquivo | Razão |
|---|---|---|
| `_assert_or_403` | `app/utils/helpers.py` | Já existe; puro; consistente com `normalize_cpf` etc. lá presentes |
| `_normalizar_identidade_jwt` | `app/utils/helpers.py` | Puro; depende só do contrato de payload JWT |
| `_unidade_id_do_dispensador` | `app/auth/ownership.py` (novo) | Toca DB; semântica de autorização justifica arquivo dedicado |

**Por que `app/auth/ownership.py` novo (e não `app/auth/dependencies.py`):** `dependencies.py` hospeda dependencies do FastAPI (`require_role`, `get_current_user`). O Helper 3 não é dependency — é função consultada pelo handler. Misturar polui semanticamente. Criar `ownership.py` deixa explícito o domínio (autorização por vínculo) e abre espaço para o Helper 3 ganhar irmãos se subdomínios futuros precisarem (ex: `_unidade_id_do_responsavel_tecnico(conn, cns)` para laudos hospitalares).

---

## §6 Análise de cobertura — amostra real

Como ficaria um endpoint vulnerável atual após o TICKET-5C-BIS-A com os helpers:

### Antes (`pedidos_exame.py:541`, vulnerável)

```python
@router.get("/{protocolo}")
def get_pedido_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin", "dispensador")),
):
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)
        ...
```

### Depois (TICKET-5C-BIS-A esperado, Padrão B)

```python
@router.get("/{protocolo}")
def get_pedido_exame(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel == "admin":
            return _serializar_pedido(conn, pedido)

        if papel == "prescritor":
            _assert_or_403(
                ident == pedido["cns_prescritor"],
                codigo="ownership_negada",
                mensagem="Apenas o prescritor que emitiu pode consultar este pedido.",
            )
        elif papel == "dispensador":
            # dispensador = clínica/lab no MVP — vínculo é via cnpj_prestador
            _assert_or_403(
                ident == pedido["cnpj_prestador"],
                codigo="ownership_negada",
                mensagem="Apenas o prestador destinatário pode consultar este pedido.",
            )

        return _serializar_pedido(conn, pedido)
```

Características:
- 2 chamadas a `_assert_or_403` com `codigo`/`mensagem` específicos
- 1 chamada a `_normalizar_identidade_jwt`
- Zero queries duplicadas (`_get_pedido_ou_404` já reusa o row)
- Switch por papel é local, explícito, auditável

---

## §7 Riscos e mitigações

| Risco | Probabilidade | Mitigação |
|---|---|---|
| `_normalizar_identidade_jwt` mudar formato de retorno e quebrar 30 calls | Média | Docstring com contrato explícito; teste unitário do helper antes dos tickets A-E |
| `_unidade_id_do_dispensador` ficar órfão se hospitalar nunca crescer | Baixa | Helper único de ~10 linhas em arquivo dedicado; custo de manter é trivial |
| Drift entre subdomínios na escolha de `codigo` para o mesmo tipo de violação | Alta | Definir vocabulário fechado de `codigo` em ADR ou docstring do `_assert_or_403`: `ownership_negada`, `vinculo_institucional_negado`, `papel_invalido_para_acao` |
| Helpers virarem "deus" com o tempo, absorvendo lógica que devia ser local | Média | Linha de governança: helpers nesta ADR são imutáveis em escopo. Mudança exige ADR-N nova. |

**Vocabulário fechado de `codigo` (proposto, fechado nesta ADR):**

```
ownership_negada                  — JWT.identificador ≠ identificador no objeto
vinculo_institucional_negado      — vínculo via prestadores/unidades não confirmado
papel_invalido_para_acao          — role no JWT não habilita esta ação (rare; require_role já cobre)
contexto_operacional_negado       — operação só permitida em contexto X (ex: hospitalar)
```

Novos códigos exigem PR + nota no §7 desta ADR.

---

## §8 Decisão sobre CODEX rodada 0 desta ADR

§6 do spike (TICKET-5C-BIS-0) prevê gatilho de CODEX rodada 0 sobre a ADR **apenas se a opção escolhida for A com assinatura concreta de helper compartilhado completo**. Como escolhemos **C estendida** (helpers locais isolados, sem helper completo), o gatilho NÃO dispara.

A ADR é classe `docs` por §6 do spike, Regra 3 — fecha sem CODEX rodada 1 nem rodada 0.

**Próximo gatilho de CODEX:** rodada 1 sobre a spec do TICKET-5C-BIS-A (>100 linhas, classe `core`/`module`, conforme guard-rail da calibração 2026-05-28).

---

## §9 Implicações para PLANO-PRODUCAO-V2

Atualizar `docs/PLANO-PRODUCAO-V2.md` linha 224 (status do spike) e adicionar nota da ADR-002 fechada. Mudança feita no mesmo commit deste ADR para satisfazer "Risco 3 — docs vivos" do guard-rail da calibração.

Update esperado:

```
| TICKET-5C-BIS-0 | Spike avaliativo... | 🔄 v0.2 (...) → ✅ Fechado em ADR-002 (2026-05-30) — opção C estendida
```

---

## §10 Referências

- **Spike:** [TICKET-5C-BIS-0-HELPER-OWNERSHIP.md](../tickets/TICKET-5C-BIS-0-HELPER-OWNERSHIP.md) v0.2
- **CODEX rodada 0 do spike:** 2026-05-26, 0 P1 + 6 P2 + 4 P3 aceitos, integrada em §10 do spike
- **TICKET-5C original:** [TICKET-5C-AUTORIZACAO-MINIMA.md](../tickets/TICKET-5C-AUTORIZACAO-MINIMA.md) (commit `01c67fa`)
- **ADR-001:** embutida em [TICKET-4E-2-RELATORIO-INTEGRADO.md](../tickets/TICKET-4E-2-RELATORIO-INTEGRADO.md) (não arquivo separado)
- **PLANO-PRODUCAO-V2:** [§5C-bis](../../../docs/PLANO-PRODUCAO-V2.md#etapa-5c-bis)
- **Calibração de pacto:** [PROMPT-CODE-ENGENHEIRO-ARQUITETO.md](../PROMPT-CODE-ENGENHEIRO-ARQUITETO.md) (2026-05-28)
- **Commit base da leitura dos 5 routers:** `43664f4` (HEAD em 2026-05-30)

---

*ADR-002 fechada em 2026-05-30 pelo Engenheiro-Arquiteto. Vinculante para TICKET-5C-BIS-A/B/C/D/E.*
