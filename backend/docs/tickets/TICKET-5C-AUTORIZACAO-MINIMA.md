# TICKET 5C — Autorização mínima em endpoints clínicos centrais

> **Classe (CLAUDE.md §10):** `core` — toca RBAC (autenticação/autorização) em endpoints clínicos centrais. CLAUDE.md §10 lista explicitamente "RBAC e autenticação" como core obrigatório.
> **Pacto:** Regra 2 estrita
> **Data:** 2026-05-23
> **Origem:** Auditoria do plano §5C revelou vulnerabilidades reais (não cobertura de teste faltante). Achado central pela revisão CODEX em 2026-05-23 sobre a lista preliminar do Arquiteto, calibrando contra o código real em `/Users/fabianotonacoborges/PicSaude_Dev`.
> **Predecessor:** 5A fechado em `e09dc3e` + `66547e4`; P2 follow-up #43 fechado em `f82b0da`.
> **Sucessor:** Encerramento da Etapa 5 (atualizar PLANO-PRODUCAO-V2 + CLAUDE.md + PROMPT-OPUS).
> **Redigido por:** Arquiteto rodada 0. Aguarda CODEX rodada 1 antes de passar ao Code.

---

## §1 Contexto regulatório

RDC 1.000/2025 (Anvisa) e CLAUDE.md §3 ("backend é fonte de verdade — nunca confiar no frontend para afirmações de estado") exigem que **todo objeto sanitário emitido ou consultado em endpoints autenticados tenha vínculo verificável entre o ator declarado e o ator do JWT**.

Hoje, vários endpoints clínicos centrais:

- aceitam o `require_role` mas **descartam o usuário** (assinatura `_=Depends(require_role(...))` em vez de `usuario=Depends(...)`)
- **não verificam vínculo de ownership** entre o solicitante e o objeto sanitário
- em um caso (`GET /custodia`) **não verificam autenticação nenhuma**

Consequência: prescritor A pode emitir prescrição declarando-se prescritor B (impersonação documental); prescritor C pode ler o documento canônico e PDF de prescrição emitida por prescritor D (vazamento clínico); qualquer cliente com o protocolo pode ler a cadeia de custódia completa (`GET /custodia`).

Esse comportamento contradiz o princípio sanitarista do projeto — **a rastreabilidade da emissão e da circulação é a coluna vertebral do sistema** (CLAUDE.md §2, "ledger é arquitetura"). Sem amarração de ator real, a forense fica comprometida.

Este ticket é o **bloqueador de autorização do MVP ambulatorial** antes do deploy público (Etapa 8 do PLANO-PRODUCAO-V2.md). Cobre **11 vulnerabilidades (V1-V11)** identificadas pela revisão CODEX rodada 1 + varredura canônica + rodada 1.5 final (2026-05-23). Endpoints clínicos centrais de exames, laudos, agendamentos, circulação diagnóstica e fluxo hospitalar têm padrão similar e ficam em **tickets sucessores** abertos por §7.1.

## §2 Achado central — CODEX rodada 0 sobre auditoria do Arquiteto (2026-05-23)

O Arquiteto fez auditoria inicial de gap do plano §5C e listou 5-6 cenários de cobertura faltante. CODEX, ao revisar a lista contra o código real, identificou que o problema **não era cobertura de teste** — era **vulnerabilidade ativa**:

> "O maior gap não é 'transição inválida', é **endpoint crítico ignorando o ator autenticado**."

Crédito do achado central para CODEX 2026-05-23.

### §2.1 Inventário de vulnerabilidades (V1-V11)

Organizado por arquivo (estrutura aprovada por Fabiano em 2026-05-23 após varredura CODEX, atualizada na rodada 1.5):

- **V1-V4:** `prescricoes.py`
- **V5, V6, V10:** `custodia.py`
- **V7:** `validacao.py`
- **V8, V11:** `assinaturas.py`
- **V9:** `dispensacoes.py`

V10 foi incluído após a varredura CODEX (§10.1). V11 foi promovido a P1 obrigatório na rodada 1.5 do CODEX (§10.5) — o POST `/assinatura` já usa `usuario=Depends(...)` mas **não valida ownership**, permitindo que prescritor B grave metadados de assinatura em prescrição emitida por A. Demais matches da varredura recaíram em classe B (tickets sucessores em §7.1) ou C (admin/health/IA stateless — fora do escopo).

#### V1 — `POST /prescricoes` (prescricoes.py:213-214)

```python
@router.post("", status_code=201)
def criar_prescricao(payload: PrescricaoIn, _=Depends(require_role("prescritor"))):
```

`_` descarta o usuário. `payload.cns_prescritor` é aceito sem verificação contra o JWT. **Qualquer prescritor pode emitir prescrição declarando-se outro prescritor.**

#### V2 — `POST /prescricoes/fisica` (prescricoes.py:681-682)

Mesmo padrão. Mesma vulnerabilidade no fluxo físico.

#### V3 — `GET /prescricoes/{proto}/documento` (prescricoes.py:832-833)

```python
@router.get("/{protocolo}/documento")
def get_documento(protocolo: str, _=Depends(require_role("prescritor", "admin"))):
```

Valida role mas descarta usuário. **Qualquer prescritor pode ler o documento canônico de prescrição emitida por outro prescritor.**

#### V4 — `GET /prescricoes/{proto}/pdf` (prescricoes.py:892-895)

Mesmo padrão de V3, com roles `("prescritor", "dispensador", "admin")`. **Qualquer prescritor pode baixar PDF de receita emitida por outro prescritor.** (Dispensador autenticado já pode ver PDFs como parte do fluxo de balcão — desejado.)

#### V5 — `GET /custodia/{proto}/custodia` (custodia.py:237-238)

```python
@router.get("/{protocolo}/custodia")
def get_custodia(protocolo: str):
```

**Nenhuma dependência de autenticação.** Qualquer cliente com o protocolo lê a cadeia de custódia completa, histórico de transferências e status da prescrição.

#### V6 — `POST /custodia/{proto}/custodia/transferir` (custodia.py:282-283)

```python
@router.post("/{protocolo}/custodia/transferir", status_code=201)
def transferir_custodia(protocolo: str, payload: TransferirCustodiaIn, _=Depends(require_role("prescritor", "dispensador"))):
```

Valida role mas descarta ator. **Prescritor C pode registrar transferência em nome do prescritor A para o paciente B sem qualquer vínculo com a prescrição.** Compromete a linearidade da cadeia de custódia.

#### V7 — `GET /prescricoes/{proto}/validacao` (validacao.py:25-29)

```python
@router.get("/{protocolo}/validacao")
def get_validacao(
    protocolo: str,
    _=Depends(require_role("prescritor", "dispensador", "admin")),
):
```

Valida role mas descarta usuário. **Qualquer prescritor pode ler o resultado da validação documental de prescrição emitida por outro prescritor.** O endpoint retorna 5 camadas de validação (estrutural, integridade, CFM, assinatura digital, ICP-Brasil) — informação clínica + forense.

#### V8 — `GET /prescricoes/{proto}/assinatura` (assinaturas.py:148-151)

```python
@router.get("/{protocolo}/assinatura")
def get_assinatura(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin")),
):
```

Valida role mas descarta usuário. **Qualquer prescritor pode ler metadados de assinatura digital de prescrição emitida por outro prescritor.**

#### V9 — `GET /dispensacoes/{id}/comprovante` (dispensacoes.py:276-280)

```python
@router.get("/{dispensacao_id}/comprovante")
def comprovante(
    dispensacao_id: int,
    formato: str = Query(default="json", pattern="^(json|pdf)$"),
    _=Depends(require_role("dispensador", "prescritor", "auditor", "admin")),
):
```

Valida role mas descarta usuário. **Qualquer dispensador pode baixar comprovante de dispensação realizada por outro dispensador**; **qualquer prescritor pode baixar comprovante de dispensação de prescrição emitida por outro prescritor**.

Owner check é multi-role:
- `auditor`, `admin` → sempre passam (fiscalização)
- `dispensador` → CNPJ do JWT deve coincidir com `dispensacoes.cnpj_estabelecimento` da dispensação
- `prescritor` → CNS do JWT deve coincidir com `prescritores.cns` da prescrição associada

#### V10 — `POST /prescricoes/{proto}/itens/{item_id}/dispensar` (custodia.py:363-364) — **escrita clínica central**

```python
@router.post("/{protocolo}/itens/{item_id}/dispensar", status_code=201)
def dispensar_item(protocolo: str, item_id: int, payload: DispensarItemIn, _=Depends(require_role("dispensador"))):
    # ...
    cnpj = normalize_cnpj(payload.cnpj_estabelecimento)
```

Valida role `dispensador` mas descarta JWT. Aceita `payload.cnpj_estabelecimento` arbitrário e grava em `dispensacoes.cnpj_estabelecimento` **sem comparar com o CNPJ do JWT**. **Dispensador B autenticado pode registrar dispensação com CNPJ do dispensador A** — fraude documental direta em registro com efeito de ledger (`dispensacao_registrada` no `prescricao_eventos`).

Achado P1 CODEX varredura 2026-05-23. Severidade maior que V1-V9 por ser **escrita clínica que altera estado** (não consulta nem fluxo de custódia).

#### V11 — `POST /prescricoes/{proto}/assinatura` (assinaturas.py:233-237) — **escrita clínica em metadados de assinatura**

```python
@router.post("/{protocolo}/assinatura", status_code=201)
def registrar_assinatura(
    protocolo: str,
    payload: AssinaturaIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    # ...
    with get_tx() as conn:
        meta = _get_meta_prescricao(conn, protocolo)
        # INSERT / UPDATE em prescricao_assinatura SEM owner check
        # Evento 'assinatura_registrada' no ledger
```

**Padrão diferente de V1-V10:** o `usuario` JÁ está capturado (não é `_=Depends`). Mas **`_get_meta_prescricao` não compara com `usuario["sub"]`** antes do INSERT/UPDATE em `prescricao_assinatura` (linhas 276-319) nem antes do evento `assinatura_registrada` no ledger (linha 324).

**Vulnerabilidade:** prescritor B autenticado pode registrar (ou atualizar — endpoint é upsert) metadados de assinatura digital em prescrição emitida por prescritor A. Inclui certificado, emissor, serial, timestamp, hash do documento e dados base64 da assinatura. **Fraude documental direta sobre metadados crípticos**, com efeito de ledger (`assinatura_registrada`).

Achado P1 CODEX rodada 1.5 (2026-05-23). Mais sutil que V1-V10 mas **escrita clínica equivalente em severidade** — atinge a integridade do registro de assinatura, que é fonte primária para futura validação ICP-Brasil/gov.br.

## §3 Decisões de design

### §3.1 Status code: 403 vs 404 quando não-dono

Quando prescritor A tenta acessar prescrição do prescritor B, há duas escolhas:

- **403 Forbidden** — revela que a prescrição existe (privacidade menor); rastreabilidade forense melhor
- **404 Not Found** — esconde a existência (privacidade maior); forense ruim

Plano original §5C e CODEX rodada 0 alinhados em **403**. Decisão preservada — admin sempre passa.

**Exceção justificada:** quando o protocolo nem existe, devolver 404 (não 403). Permite que admins/auditores distingam "não encontrado" de "não autorizado". Para prescritor não-dono, 403 sempre.

### §3.2 Implementação do check de ownership

**Sem helper novo na primeira passada (KISS).** O check vai inline em cada endpoint via query JOIN:

```python
row = conn.execute(
    """
    SELECT p.*
      FROM prescricoes p
      JOIN prescritores pr ON pr.id = p.prescritor_id
     WHERE p.protocolo = ? AND pr.cns = ?
    """,
    (protocolo, normalize_cns(usuario["sub"])),
).fetchone()
```

Padrão consistente nos 4 endpoints prescritor-dono (V3, V4, V5 com role prescritor, V6). Se CODEX rodada 1 ou Code apontarem duplicação grave, refatorar para helper `verificar_dono_prescricao(conn, protocolo, usuario)` em `auth/dependencies.py` ou `routers/_helpers.py`.

### §3.3 Matriz de roles para `GET /custodia` (V5)

Quem pode ler a cadeia de custódia da prescrição? Cadeia de custódia é informação clínica sensível mas não secreta entre os atores do ciclo.

Matriz proposta:

| Role | Acesso | Justificativa |
|---|---|---|
| `prescritor` | Apenas se for o dono da prescrição | RBAC mínimo |
| `dispensador` | **Histórico de participação** — qualquer custódia (ativa ou encerrada) já registrada para esse CNPJ | Vínculo verificável; transparência entre atores do ciclo |
| `paciente` | Apenas se for o dono (CPF na prescrição = CPF do JWT) | Direito à informação clínica |
| `admin` / `auditor` | Sempre | Fiscalização |
| `outros` (sem token / token inválido) | 401 | RBAC mínimo |

**Decisão semântica explícita (P2 CODEX rodada 1 #4, 2026-05-23):** "dispensador que já teve custódia" é **histórico de participação**, não apenas custódia ativa. Justificativa: dispensador que abandonou custódia ainda pode precisar reler para audit/finance/conferência interna. Risco aceito: dispensador que recebeu por engano e devolveu imediatamente continuará lendo histórico — aceitável porque o evento de devolução também ficou registrado (ledger é fonte de verdade). Auditoria futura pode restringir a `encerrada_em IS NULL` (custódia ativa apenas) se o uso indevido for observado em produção.

Implementação simplificada para a primeira passada: aceitar `("prescritor", "dispensador", "paciente", "admin", "auditor")` no `require_role` e fazer check de owner inline:
- `prescritor` → check JOIN como §3.2
- `paciente` → check `pacientes.cpf == usuario["sub"]` (paciente JWT carrega CPF como `sub`)
- `dispensador` → check `EXISTS (SELECT 1 FROM prescricao_custodia WHERE prescricao_id = ? AND detentor_tipo = 'dispensador' AND detentor_id = ?)` (histórico de participação) — **apenas fluxo ambulatorial; hospitalar fora do escopo, ver §3.4 e §7**
- `admin` / `auditor` → sempre passa

### §3.4 Implementação de V6 (transferir custódia) — fechar bypass

**Achado P1 #1 CODEX rodada 1 (2026-05-23):** a versão original deste §3.4 só validava o caso `usuario["role"] == "prescritor" and payload.de == "prescritor"`. As demais combinações cairiam em "seguir validações existentes" — o que mantinha a vulnerabilidade. Prescritor B autenticado podia transferir custódia de prescrição de A declarando `payload.de = "paciente"` ou `payload.de = "dispensador"`.

**Regra fechada:**

1. **`payload.de` deve coincidir com `usuario["role"]`.** Prescritor só pode declarar `de = "prescritor"`. Dispensador só pode declarar `de = "dispensador"`. Caso contrário → 403 `ator_mismatch`.

2. **Dentro do role correto, o ator declarado (`payload.de_id`) deve coincidir com o JWT (`usuario["sub"]`).**

3. **Para prescritor, exigir também ownership da prescrição.** Não basta o CNS do payload coincidir com o JWT — o JWT precisa ser do prescritor real **daquela prescrição**. Isso fecha o caso "prescritor A com JWT autêntico tenta transferir prescrição emitida por prescritor B com `payload.de_id = CNS_de_A`" (CNS do payload e do JWT coincidem, mas a prescrição não é dele).

4. **`payload.de = "paciente"` é rejeitado neste endpoint.** Justificativa: fluxo paciente já tem endpoint próprio em `auth.py:185` (`transferir_farmacia`) e `auth.py:269` (`devolver_prescritor`), com auth de role paciente. Misturar paciente em `POST /custodia/transferir` (que aceita só prescritor+dispensador) é via inválida.

5. **Para dispensador**: exigir `normalize_cnpj(usuario["sub"]) == normalize_cnpj(payload.de_id)` E custódia ativa **da prescrição inteira** (`item_id IS NULL`) registrada para esse CNPJ (`detentor_tipo = 'dispensador' AND detentor_id = CNPJ AND encerrada_em IS NULL`). `transferir_custodia` move a prescrição global, então custódia ativa **apenas item-level** não autoriza a transferência (P2 #3 CODEX rodada 1.5). Fluxo hospitalar (`unidade_id` no `detentor_id`) fica fora do escopo — ver §7.

### §3.5 Payload do erro 403

Padrão consistente com 5A (codigo + mensagem em PT, sem dados sensíveis). Tabela atualizada na rodada 1.5 do CODEX:

| Vulnerabilidade | codigo | mensagem |
|---|---|---|
| V1, V2 | `prescritor_mismatch` | "CNS do payload não coincide com prescritor autenticado." |
| V3, V4 | `nao_e_dono_da_prescricao` | "Esta prescrição foi emitida por outro prescritor." |
| V5 (todas roles não-dono) | `sem_vinculo_com_prescricao` | "Você não tem vínculo de leitura com esta prescrição." |
| V6 | `ator_mismatch` | "Ator declarado não coincide com usuário autenticado." / "Fluxo paciente não é aceito neste endpoint." / "Role do JWT não coincide com payload.de." |
| V7 | `nao_e_dono_da_prescricao` | "Esta prescrição foi emitida por outro prescritor." |
| V8 | `nao_e_dono_da_prescricao` | idem V7 |
| V9 (role dispensador não-dono) | `nao_e_dono_da_dispensacao` | "Esta dispensação foi realizada por outro estabelecimento." |
| V9 (role prescritor não-dono) | `nao_e_dono_da_prescricao` | idem V3 |
| V10 | `ator_mismatch` | "CNPJ do payload não coincide com dispensador autenticado." |
| V11 | `nao_e_dono_da_prescricao` | idem V3 |

## §4 Especificação do fix

### §4.1 V1 — `POST /prescricoes` (prescricoes.py:213-214)

**Antes:**
```python
@router.post("", status_code=201)
def criar_prescricao(payload: PrescricaoIn, _=Depends(require_role("prescritor"))):
    if not payload.itens:
        raise HTTPException(status_code=422, detail="A prescrição deve conter ao menos um item.")
    # ...
    cns = normalize_cns(payload.cns_prescritor)
```

**Depois:**
```python
@router.post("", status_code=201)
def criar_prescricao(payload: PrescricaoIn, usuario=Depends(require_role("prescritor"))):
    if not payload.itens:
        raise HTTPException(status_code=422, detail="A prescrição deve conter ao menos um item.")
    # ...
    cns = normalize_cns(payload.cns_prescritor)
    if normalize_cns(usuario["sub"]) != cns:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "prescritor_mismatch",
                "mensagem": "CNS do payload não coincide com prescritor autenticado.",
            },
        )
```

O check vai imediatamente após `cns = normalize_cns(payload.cns_prescritor)` (linha 231 atual), antes de qualquer query/INSERT.

### §4.2 V2 — `POST /prescricoes/fisica` (prescricoes.py:681-682)

Mesmo padrão de V1. Check após linha 697 (`cns = normalize_cns(payload.cns_prescritor)`).

### §4.3 V3 — `GET /prescricoes/{proto}/documento` (prescricoes.py:832-833)

**Antes:**
```python
@router.get("/{protocolo}/documento")
def get_documento(protocolo: str, _=Depends(require_role("prescritor", "admin"))):
    # ...
    with get_tx() as conn:
        # ... query atual sem filtro de owner
```

**Depois:**
```python
@router.get("/{protocolo}/documento")
def get_documento(protocolo: str, usuario=Depends(require_role("prescritor", "admin"))):
    with get_tx() as conn:
        # Owner check — admin sempre passa
        if usuario["role"] != "admin":
            owner = conn.execute(
                """
                SELECT 1
                  FROM prescricoes p
                  JOIN prescritores pr ON pr.id = p.prescritor_id
                 WHERE p.protocolo = ? AND pr.cns = ?
                """,
                (protocolo, normalize_cns(usuario["sub"])),
            ).fetchone()
            if not owner:
                # Verificar se prescrição existe para distinguir 403 de 404
                existe = conn.execute(
                    "SELECT 1 FROM prescricoes WHERE protocolo = ?",
                    (protocolo,),
                ).fetchone()
                if not existe:
                    raise HTTPException(404, "Prescrição não encontrada.")
                raise HTTPException(
                    status_code=403,
                    detail={
                        "codigo": "nao_e_dono_da_prescricao",
                        "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                    },
                )
        # ... resto do código atual
```

### §4.4 V4 — `GET /prescricoes/{proto}/pdf` (prescricoes.py:892-895)

**Antes:** `_=Depends(require_role("prescritor", "dispensador", "admin"))`

**Depois:** `usuario=Depends(require_role("prescritor", "dispensador", "admin"))`

Check de owner **apenas para role `prescritor`** (dispensador e admin passam direto):
```python
if usuario["role"] == "prescritor":
    owner = conn.execute(
        """
        SELECT 1
          FROM prescricoes p
          JOIN prescritores pr ON pr.id = p.prescritor_id
         WHERE p.protocolo = ? AND pr.cns = ?
        """,
        (protocolo, normalize_cns(usuario["sub"])),
    ).fetchone()
    if not owner:
        existe = conn.execute(
            "SELECT 1 FROM prescricoes WHERE protocolo = ?",
            (protocolo,),
        ).fetchone()
        if not existe:
            raise HTTPException(404, "Prescrição não encontrada.")
        raise HTTPException(
            status_code=403,
            detail={"codigo": "nao_e_dono_da_prescricao", "mensagem": "..."},
        )
```

### §4.5 V5 — `GET /custodia/{proto}/custodia` (custodia.py:237-238)

**Antes:**
```python
@router.get("/{protocolo}/custodia")
def get_custodia(protocolo: str):
```

**Depois:**
```python
@router.get("/{protocolo}/custodia")
def get_custodia(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "dispensador", "paciente", "admin", "auditor")),
):
    with get_tx() as conn:
        presc = _get_prescricao_by_protocolo(conn, protocolo)
        # admin / auditor sempre passam
        if usuario["role"] in ("admin", "auditor"):
            pass
        elif usuario["role"] == "prescritor":
            # Owner check via JOIN
            owner = conn.execute(
                """
                SELECT 1
                  FROM prescritores
                 WHERE id = ? AND cns = ?
                """,
                (presc["prescritor_id"], normalize_cns(usuario["sub"])),
            ).fetchone()
            if not owner:
                raise HTTPException(
                    status_code=403,
                    detail={"codigo": "sem_vinculo_com_prescricao", "mensagem": "..."},
                )
        elif usuario["role"] == "paciente":
            # Paciente JWT carrega CPF como sub
            owner = conn.execute(
                """
                SELECT 1
                  FROM pacientes
                 WHERE id = ? AND cpf = ?
                """,
                (presc["paciente_id"], normalize_cpf(usuario["sub"])),
            ).fetchone()
            if not owner:
                raise HTTPException(403, {"codigo": "sem_vinculo_com_prescricao", "mensagem": "..."})
        elif usuario["role"] == "dispensador":
            # Histórico de participação ambulatorial — qualquer custódia
            # (ativa OU encerrada) registrada para esse CNPJ. Ver §3.3.
            # JWT sub = CNPJ normalizado (login.py:70 _normalizar_identificador).
            vinculo = conn.execute(
                """
                SELECT 1
                  FROM prescricao_custodia
                 WHERE prescricao_id = ?
                   AND detentor_tipo = 'dispensador'
                   AND detentor_id = ?
                 LIMIT 1
                """,
                (presc["id"], normalize_cnpj(usuario["sub"])),
            ).fetchone()
            if not vinculo:
                raise HTTPException(403, {"codigo": "sem_vinculo_com_prescricao", "mensagem": "..."})
        # ... resto do código atual
```

> **Nota:** o formato do `usuario["sub"]` para dispensador foi confirmado pela varredura CODEX 2026-05-23 como **CNPJ normalizado** (`login.py:70` via `_normalizar_identificador`). Em custódia ambulatorial, `prescricao_custodia.detentor_id = CNPJ` — bate. Em custódia hospitalar, `detentor_id = unidade_id` — não bate; fluxo hospitalar fica em ticket follow-up #49.

### §4.6 V6 — `POST /custodia/{proto}/custodia/transferir` (custodia.py:282-283)

**Antes:** `_=Depends(require_role("prescritor", "dispensador"))`

**Depois (regra fechada conforme §3.4):**
```python
@router.post("/{protocolo}/custodia/transferir", status_code=201)
def transferir_custodia(
    protocolo: str,
    payload: TransferirCustodiaIn,
    usuario=Depends(require_role("prescritor", "dispensador")),
):
    # Regra 1: payload.de DEVE coincidir com usuario["role"].
    # Paciente não pode operar neste endpoint (fluxo próprio em auth.py).
    if payload.de == "paciente":
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "ator_mismatch",
                "mensagem": "Fluxo paciente não é aceito neste endpoint. Use /auth/prescricoes/{proto}/transferir-farmacia.",
            },
        )
    if payload.de != usuario["role"]:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "ator_mismatch",
                "mensagem": "Role do JWT não coincide com payload.de.",
            },
        )

    # Regra 2 + 3: ator declarado deve coincidir com JWT E (para prescritor)
    # ser o dono real da prescrição. Caso dispensador, vínculo via custódia
    # ativa no CNPJ.
    with get_tx() as conn:
        instance_id = get_instance_id_conn(conn)
        presc = _get_prescricao_by_protocolo(conn, protocolo)

        if usuario["role"] == "prescritor":
            # JWT sub = CNS. Verificar CNS do payload coincide com JWT
            # E o prescritor da prescrição é esse CNS.
            cns_jwt = normalize_cns(usuario["sub"])
            cns_payload = normalize_cns(payload.de_id or "")
            if cns_jwt != cns_payload:
                raise HTTPException(403, detail={"codigo": "ator_mismatch", "mensagem": "..."})
            dono = conn.execute(
                """
                SELECT 1
                  FROM prescritores
                 WHERE id = ? AND cns = ?
                """,
                (presc["prescritor_id"], cns_jwt),
            ).fetchone()
            if not dono:
                raise HTTPException(403, detail={"codigo": "ator_mismatch", "mensagem": "..."})

        else:  # dispensador (já validado no require_role)
            # JWT sub = CNPJ. Validar coincidência E custódia ATIVA da
            # PRESCRIÇÃO INTEIRA para esse CNPJ. `transferir_custodia` move
            # a prescrição global (item_id IS NULL), então custódia ativa
            # apenas item-level NÃO autoriza a transferência global.
            # (P2 #3 CODEX rodada 1.5)
            cnpj_jwt = normalize_cnpj(usuario["sub"])
            cnpj_payload = normalize_cnpj(payload.de_id or "")
            if cnpj_jwt != cnpj_payload:
                raise HTTPException(403, detail={"codigo": "ator_mismatch", "mensagem": "..."})
            vinculo = conn.execute(
                """
                SELECT 1
                  FROM prescricao_custodia
                 WHERE prescricao_id = ?
                   AND item_id IS NULL
                   AND detentor_tipo = 'dispensador'
                   AND detentor_id = ?
                   AND encerrada_em IS NULL
                 LIMIT 1
                """,
                (presc["id"], cnpj_jwt),
            ).fetchone()
            if not vinculo:
                raise HTTPException(403, detail={"codigo": "ator_mismatch", "mensagem": "..."})

        # ... resto do código atual de transferir_custodia (validação de transição,
        # _fechar_custodia_ativa, _abrir_custodia, atualização de status, etc.)
```

**Importante sobre `normalize_cnpj`:** está em `app/utils/helpers.py` (confirmado em `app/routers/login.py:70`). Importar.

### §4.7 V7 — `GET /prescricoes/{proto}/validacao` (validacao.py:25-29)

**Antes:** `_=Depends(require_role("prescritor", "dispensador", "admin"))`

**Depois:** `usuario=Depends(require_role("prescritor", "dispensador", "admin"))` + check de owner apenas para role `prescritor`:

```python
if usuario["role"] == "prescritor":
    owner = conn.execute(
        """
        SELECT 1
          FROM prescricoes p
          JOIN prescritores pr ON pr.id = p.prescritor_id
         WHERE p.protocolo = ? AND pr.cns = ?
        """,
        (protocolo, normalize_cns(usuario["sub"])),
    ).fetchone()
    if not owner:
        existe = conn.execute(
            "SELECT 1 FROM prescricoes WHERE protocolo = ?",
            (protocolo,),
        ).fetchone()
        if not existe:
            raise HTTPException(404, "Prescrição não encontrada.")
        raise HTTPException(
            status_code=403,
            detail={"codigo": "nao_e_dono_da_prescricao", "mensagem": "..."},
        )
```

Dispensador e admin passam direto (dispensador pode precisar verificar validação como parte do balcão; admin sempre fiscaliza).

### §4.8 V8 — `GET /prescricoes/{proto}/assinatura` (assinaturas.py:148-151)

**Antes:** `_=Depends(require_role("prescritor", "admin"))`

**Depois:** `usuario=Depends(...)` + check de owner para `prescritor` (admin passa). Estrutura idêntica ao §4.3 V3.

### §4.9 V9 — `GET /dispensacoes/{id}/comprovante` (dispensacoes.py:276-280)

**Antes:** `_=Depends(require_role("dispensador", "prescritor", "auditor", "admin"))`

**Depois:** `usuario=Depends(...)` + check de owner multi-role:

```python
@router.get("/{dispensacao_id}/comprovante")
def comprovante(
    dispensacao_id: int,
    formato: str = Query(default="json", pattern="^(json|pdf)$"),
    usuario=Depends(require_role("dispensador", "prescritor", "auditor", "admin")),
):
    # admin/auditor passam direto
    if usuario["role"] not in ("admin", "auditor"):
        with get_tx() as conn:
            info = conn.execute(
                """
                SELECT d.cnpj_estabelecimento, pr.cns AS prescritor_cns
                  FROM dispensacoes d
                  JOIN prescricao_itens i ON i.id = d.prescricao_item_id
                  JOIN prescricoes p       ON p.id = i.prescricao_id
                  JOIN prescritores pr     ON pr.id = p.prescritor_id
                 WHERE d.id = ?
                """,
                (dispensacao_id,),
            ).fetchone()
            if not info:
                raise HTTPException(
                    status_code=404,
                    detail=f"Dispensação {dispensacao_id} não encontrada.",
                )
            if usuario["role"] == "dispensador":
                if normalize_cnpj(usuario["sub"]) != info["cnpj_estabelecimento"]:
                    raise HTTPException(
                        status_code=403,
                        detail={"codigo": "nao_e_dono_da_dispensacao", "mensagem": "..."},
                    )
            elif usuario["role"] == "prescritor":
                if normalize_cns(usuario["sub"]) != info["prescritor_cns"]:
                    raise HTTPException(
                        status_code=403,
                        detail={"codigo": "nao_e_dono_da_prescricao", "mensagem": "..."},
                    )
    # ... resto do código atual
```

### §4.10 V10 — `POST /prescricoes/{proto}/itens/{item_id}/dispensar` (custodia.py:363-364)

**Antes:**
```python
@router.post("/{protocolo}/itens/{item_id}/dispensar", status_code=201)
def dispensar_item(protocolo: str, item_id: int, payload: DispensarItemIn, _=Depends(require_role("dispensador"))):
    cnpj = normalize_cnpj(payload.cnpj_estabelecimento)
    # ...
```

**Depois:** `usuario=Depends(...)` + check de CNPJ mismatch antes de qualquer INSERT/evento:

```python
@router.post("/{protocolo}/itens/{item_id}/dispensar", status_code=201)
def dispensar_item(
    protocolo: str,
    item_id: int,
    payload: DispensarItemIn,
    usuario=Depends(require_role("dispensador")),
):
    cnpj = normalize_cnpj(payload.cnpj_estabelecimento)
    if normalize_cnpj(usuario["sub"]) != cnpj:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "ator_mismatch",
                "mensagem": "CNPJ do payload não coincide com dispensador autenticado.",
            },
        )
    # ... resto do código atual (item lookup, validação de saldo, INSERT em dispensacoes, evento)
```

O check entra **antes de qualquer SELECT da prescrição** — economia de I/O quando rejeitado e rollback trivial (nada foi tocado).

### §4.11 V11 — `POST /prescricoes/{proto}/assinatura` (assinaturas.py:233-237)

**Antes:**
```python
@router.post("/{protocolo}/assinatura", status_code=201)
def registrar_assinatura(
    protocolo: str,
    payload: AssinaturaIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    with get_tx() as conn:
        meta = _get_meta_prescricao(conn, protocolo)
        # ... INSERT/UPDATE em prescricao_assinatura SEM owner check
```

**Depois:** owner check após `_get_meta_prescricao`, **antes** de qualquer INSERT/UPDATE/evento:

```python
@router.post("/{protocolo}/assinatura", status_code=201)
def registrar_assinatura(
    protocolo: str,
    payload: AssinaturaIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    with get_tx() as conn:
        meta = _get_meta_prescricao(conn, protocolo)

        # V11 — Owner check (admin sempre passa)
        if usuario["role"] != "admin":
            owner = conn.execute(
                """
                SELECT 1
                  FROM prescritores
                 WHERE id = ? AND cns = ?
                """,
                (meta["prescritor_id"], normalize_cns(usuario["sub"])),
            ).fetchone()
            if not owner:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "codigo": "nao_e_dono_da_prescricao",
                        "mensagem": "Esta prescrição foi emitida por outro prescritor.",
                    },
                )

        # ... resto do código atual (INSERT/UPDATE em prescricao_assinatura + evento ledger)
```

**Diferença importante vs V8 (GET /assinatura):** V11 é POST com **efeito de escrita + ledger event** (`assinatura_registrada`). O `with get_tx()` faz rollback automático na exceção, garantindo que nem o INSERT/UPDATE em `prescricao_assinatura` nem o evento `assinatura_registrada` em `prescricao_eventos` persistem no caminho rejeitado.

**Sobre `_get_meta_prescricao`:** verificar se retorna 404 quando protocolo inexistente. Se sim, o caminho "protocolo inexistente → 404 (não 403)" é preservado naturalmente — não precisa do bloco `existe` extra como nos GETs §4.3/§4.4/§4.7/§4.8.

## §5 Critérios de aceite — testes obrigatórios (V1-V11: 17 cenários)

> **Contagem final (rodada 1.5):** V1+V2+V3+V4+V5(401)+V5b(403)+V6(5 sub, incluindo 5.6e item-level)+V7+V8+V9(2 sub)+V10+V11 = **17 cenários**. V6 ganhou um sub-teste pelo P2 #3 (custódia item-level não autoriza transferência global). V11 é novo P1 da rodada 1.5.
>
> **Nota sobre arquivo:** todos integração (precisam outer_conn + autenticação real). Arquivos sugeridos: `tests/integration/test_prescricoes.py` para V1-V4; **novo** `tests/integration/test_custodia_autorizacao.py` para V5-V6.
>
> **Convenção de CNS fake nos exemplos (P3 #7 CODEX rodada 1):** usar 15 dígitos válidos. Exemplo: `"999888777666555"` (não `"outro_cns_999"`, que `normalize_cns` reduziria para `"999"` e quebraria os asserts de baseline).

### §5.1 `test_v1_prescricao_cns_mismatch_403`

- Setup: `seed_usuario` (prescritor com CNS X); payload com `cns_prescritor = "999888777666555"` (CNS fake válido, 15 dígitos).
- Request: `POST /prescricoes` com token do prescritor X.
- Asserts:
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "prescritor_mismatch"`
  - Nenhuma prescrição criada (baseline pré/pós em `prescricoes`)
  - Nenhum prescritor `"999888777666555"` criado (baseline em `prescritores`)
  - Nenhum evento no ledger (baseline em `prescricao_eventos` e `eventos_publicacao`)

### §5.2 `test_v2_prescricao_fisica_cns_mismatch_403`

Espelho de §5.1 sobre `POST /prescricoes/fisica`. Baseline adicional: `prescricao_eventos.tipo_evento = 'prescricao_impressa'` não cresce.

### §5.3 `test_v3_documento_outro_prescritor_403`

- Setup: criar prescrição com prescritor A (token A); criar segundo prescritor B com token B.
- Request: `GET /prescricoes/{proto_de_A}/documento` com token de B.
- Asserts:
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"`
- Asserts complementares:
  - Mesma request com token de A → 200 (acesso preservado para dono)
  - Mesma request com token admin → 200 (admin passa)
  - Mesma request com protocolo inexistente + token de A → 404 (não 403)

### §5.4 `test_v4_pdf_outro_prescritor_403`

Espelho de §5.3 sobre `GET /prescricoes/{proto}/pdf`. Asserts adicionais:
- Mesma request com token de dispensador → 200 (dispensador continua autorizado)

### §5.5 `test_v5_custodia_sem_token_401`

- Setup: criar prescrição.
- Request: `GET /prescricoes/{proto}/custodia` **sem header Authorization**.
- Assert: `response.status_code == 401`.

### §5.5b `test_v5_custodia_outro_prescritor_403`

- Request: `GET /prescricoes/{proto_de_A}/custodia` com token de prescritor B.
- Assert: `response.status_code == 403` com `codigo = "sem_vinculo_com_prescricao"`.

### §5.6 V6 — `POST /custodia/transferir` (4 sub-testes para fechar bypasses)

**Setup compartilhado:** criar prescrição com prescritor A; seed prescritor B com CNS independente.

#### §5.6a `test_v6_prescritor_b_de_prescritor_a_403`

- Request: token de B, `payload.de = "prescritor"`, `payload.de_id = CNS_de_A`, `payload.para = "paciente"`, etc.
- Asserts:
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "ator_mismatch"`
  - Baseline em `prescricao_custodia` e `prescricao_eventos` (`tipo_evento = 'custodia_transferida'`) sem incremento.
- Assert complementar (caminho feliz): mesma request com token de A → 201.

#### §5.6b `test_v6_prescritor_b_de_paciente_sobre_prescricao_a_403`

> P1 #1 / P2 #5 CODEX rodada 1: bypass crítico se aceitarmos `de = "paciente"` neste endpoint.

- Request: token de B (prescritor), `payload.de = "paciente"`, `payload.de_id = CPF_de_paciente_da_prescricao_A`, `payload.para = "dispensador"`, etc.
- Asserts:
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "ator_mismatch"`
  - Mensagem cita "Fluxo paciente não é aceito neste endpoint" (orientando uso de `/auth/prescricoes/{proto}/transferir-farmacia`).
  - Baseline em `prescricao_custodia` e `prescricao_eventos` sem incremento.

#### §5.6c `test_v6_prescritor_b_de_dispensador_sobre_prescricao_a_403`

> P1 #1 / P2 #5 CODEX rodada 1: bypass crítico se aceitarmos role `prescritor` declarando `de = "dispensador"`.

- Request: token de B (prescritor), `payload.de = "dispensador"`, `payload.de_id = CNPJ_qualquer`, `payload.para = "prescritor"`, etc.
- Asserts:
  - `response.status_code == 403` com `codigo = "ator_mismatch"`
  - Mensagem cita "Role do JWT não coincide com payload.de"
  - Baseline em `prescricao_custodia` e `prescricao_eventos` sem incremento.

#### §5.6d `test_v6_prescritor_b_de_prescritor_b_sobre_prescricao_a_403`

> P1 #1 CODEX rodada 1: o ataque mais sofisticado — CNS do payload coincide com JWT, mas a prescrição não é do JWT. Fechado pela regra 3 do §3.4 (ownership real da prescrição).

- Request: token de B (prescritor), `payload.de = "prescritor"`, `payload.de_id = CNS_de_B` (próprio JWT), `payload.para = "paciente"`, sobre prescrição emitida por A.
- Asserts:
  - `response.status_code == 403` com `codigo = "ator_mismatch"`
  - Baseline em `prescricao_custodia` e `prescricao_eventos` sem incremento.

#### §5.6e `test_v6_dispensador_com_custodia_item_level_nao_autoriza_transferencia_global_403`

> P2 #3 CODEX rodada 1.5: dispensador com custódia ativa **apenas de UM item** (item-level, `item_id IS NOT NULL`) não pode transferir a custódia **da prescrição inteira** (global, `item_id IS NULL`). Fechado pela cláusula `AND item_id IS NULL` na query de vínculo (§3.4 regra 5, §4.6).

- Setup: prescrição emitida por prescritor A; dispensador D com custódia ATIVA registrada apenas para item X (`detentor_tipo='dispensador'`, `detentor_id=CNPJ_D`, `item_id=X`, `encerrada_em=NULL`). **Não existe** custódia ativa para `item_id IS NULL` no CNPJ_D.
- Request: token de D, `payload.de = "dispensador"`, `payload.de_id = CNPJ_D`, `payload.para = "prescritor"`, etc.
- Asserts:
  - `response.status_code == 403` com `codigo = "ator_mismatch"`
  - Baseline em `prescricao_custodia` (linhas novas) e `prescricao_eventos` (`custodia_transferida`) sem incremento.
- Assert complementar (caminho feliz): se houver custódia ativa também para `item_id IS NULL` no mesmo CNPJ_D, request retorna 201.

### §5.7 `test_v7_validacao_outro_prescritor_403`

- Setup: prescrição emitida por prescritor A; seed prescritor B.
- Request: `GET /prescricoes/{proto_de_A}/validacao` com token de B.
- Asserts:
  - `response.status_code == 403` com `codigo = "nao_e_dono_da_prescricao"`
- Asserts complementares:
  - Mesma request com token de A → 200
  - Mesma request com token admin → 200
  - Mesma request com token dispensador autenticado → 200 (dispensador passa direto)

### §5.8 `test_v8_assinatura_outro_prescritor_403`

Espelho de §5.7 sobre `GET /prescricoes/{proto}/assinatura`. Roles: prescritor + admin (sem dispensador).
- Asserts complementares:
  - Mesma request com token admin → 200 (admin passa direto)

### §5.9 V9 — `GET /dispensacoes/{id}/comprovante` (2 sub-cenários, multi-role)

#### §5.9a `test_v9_comprovante_dispensador_outro_403`

- Setup: prescrição de prescritor A; dispensação X realizada por dispensador X (CNPJ X); seed dispensador Y (CNPJ Y).
- Request: `GET /dispensacoes/{id_de_X}/comprovante` com token de dispensador Y.
- Asserts:
  - `response.status_code == 403` com `codigo = "nao_e_dono_da_dispensacao"`
  - Mesma request com token de X → 200 (dispensador dono passa)
  - Mesma request com token de auditor/admin → 200 (passam direto)

#### §5.9b `test_v9_comprovante_prescritor_outro_403`

- Request: mesma dispensação X, com token de prescritor B (não-dono da prescrição).
- Asserts:
  - `response.status_code == 403` com `codigo = "nao_e_dono_da_prescricao"`
  - Mesma request com token de A (prescritor dono da prescrição) → 200

### §5.10 `test_v10_dispensar_cnpj_mismatch_403`

> Achado P1 CODEX varredura 2026-05-23. Escrita clínica central com efeito de ledger.

- Setup: prescrição com item disponível para dispensação (status_item = 'pendente' ou 'em_custodia'); seed dispensador A (CNPJ A) e dispensador B (CNPJ B).
- Request: `POST /prescricoes/{proto}/itens/{item_id}/dispensar` com token de **B** e `payload.cnpj_estabelecimento = CNPJ_de_A`.
- Asserts (contrato HTTP):
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "ator_mismatch"`
  - Mensagem cita "CNPJ do payload não coincide"
- Asserts (rollback efetivo — baseline pré/pós):
  - `SELECT COUNT(*) FROM dispensacoes WHERE prescricao_item_id = ?` igual ao baseline (nenhuma linha nova)
  - `SELECT status_item FROM prescricao_itens WHERE id = ?` igual ao baseline (item não muda de estado)
  - `SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id = ?` igual ao baseline (P2 #2 CODEX rodada 1.5 — baseline genérico por prescrição é mais robusto que filtrar por tipo_evento específico. O evento real do endpoint é `item_dispensado` — `custodia.py:560` — mas qualquer evento que escape do rollback aparece nesse count)
  - `SELECT COUNT(*) FROM eventos_publicacao` igual ao baseline
- Assert complementar: mesma request com token de A (dispensador dono do CNPJ no payload) → 201 (caminho válido preservado, supondo custódia ativa coerente).

### §5.11 `test_v11_assinatura_post_outro_prescritor_403`

> P1 CODEX rodada 1.5 (2026-05-23). Escrita clínica em metadados de assinatura — upsert sem owner check.

- Setup: prescrição emitida por prescritor A; seed prescritor B com CNS independente.
- Request: `POST /prescricoes/{proto_de_A}/assinatura` com token de B e payload válido (`tipo_certificado`, `emissor`, `serial_certificado`, `timestamp_assinatura`, `hash_documento`, `dados_assinatura_b64`).
- Asserts (contrato HTTP):
  - `response.status_code == 403`
  - `response.json()["detail"]["codigo"] == "nao_e_dono_da_prescricao"`
- Asserts (rollback efetivo — baseline pré/pós):
  - `SELECT COUNT(*) FROM prescricao_assinatura WHERE prescricao_id = ?` igual ao baseline (nenhuma linha nova)
  - **Se já existia registro de assinatura** (cenário upsert/UPDATE): `SELECT serial_certificado, dados_assinatura_b64, updated_at FROM prescricao_assinatura WHERE prescricao_id = ?` igual ao baseline (nenhum campo alterado)
  - `SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id = ?` igual ao baseline (sem evento `assinatura_registrada` escapando)
  - `SELECT COUNT(*) FROM eventos_publicacao` igual ao baseline
- Asserts complementares:
  - Mesma request com token de A → 201 (caminho válido preservado para dono)
  - Mesma request com token admin → 201 (admin passa direto)
  - Mesma request com protocolo inexistente + token de A → 404 (preservado via `_get_meta_prescricao`)

## §6 Verificação automatizada

### Pré-implementação (Code grep antes de codificar)

```bash
# 5 routers alvo
grep -nE "_=Depends\(require_role" backend/app/routers/prescricoes.py backend/app/routers/custodia.py backend/app/routers/validacao.py backend/app/routers/assinaturas.py backend/app/routers/dispensacoes.py
```

Esperado: pelo menos 9 matches (V1-V4, V6, V7, V8, V9, V10). V5 e V11 não casam neste grep porque já têm padrão diferente:
- V5: sem `Depends` nenhum (vulnerabilidade óbvia)
- V11: já usa `usuario=Depends` mas falta owner check (vulnerabilidade sutil)

```bash
grep -nE "^def get_custodia" backend/app/routers/custodia.py
grep -nE "^def registrar_assinatura" backend/app/routers/assinaturas.py
```

Esperado: V5 sem `Depends`; V11 com `usuario=Depends` mas sem owner check no corpo. Se algum já fixou, ajustar.

### Pós-implementação

```bash
grep -rn "_=Depends" backend/app/routers/prescricoes.py backend/app/routers/custodia.py backend/app/routers/validacao.py backend/app/routers/assinaturas.py backend/app/routers/dispensacoes.py
# Esperado: zero matches em todos os 5 routers (V1-V10 fechados).
```

```bash
grep -rn "prescritor_mismatch\|nao_e_dono_da_prescricao\|sem_vinculo_com_prescricao\|ator_mismatch\|nao_e_dono_da_dispensacao" backend/app/routers/
# Esperado (P3 #5 CODEX rodada 1.5 — flexibilizado): os 5 códigos devem
# todos APARECER em pelo menos uma ocorrência cada. Contagem total é
# variável porque V6 emite múltiplos `ator_mismatch` (rejeição de
# de=paciente + role mismatch + JWT mismatch + ownership). Não fixar
# número literal — confiar nos testes focais para garantir cobertura.
```

Suite focal:

```bash
cd backend
pytest tests/integration/test_prescricoes.py \
       tests/integration/test_custodia_autorizacao.py \
       tests/integration/test_validacao.py \
       tests/integration/test_assinaturas.py \
       tests/integration/test_dispensacoes.py \
       -v -k "v1_ or v2_ or v3_ or v4_ or v5_ or v6_ or v7_ or v8_ or v9_ or v10_ or v11_"
```

Esperado: 17/17 verdes (V1-V11, com V5+5b, V6 com 5 sub-testes — incluindo 5.6e item-level — e V9 com 2 sub-testes).

> **Nota sobre arquivos novos:** se `tests/integration/test_validacao.py`, `test_assinaturas.py` ou `test_dispensacoes.py` não existirem hoje, criar. Se existirem (verificar antes), apenas adicionar os testes V7/V8/V9 nos arquivos existentes.

Suite completa:

```bash
pytest -q
```

Esperado: nenhuma regressão. Falhas pré-existentes (27 antes do 5C) podem flutuar conforme cluster auth eventos #41 reagir ao fix do GET /custodia (improvável mas possível) — declarar separadamente.

## §7 Anti-escopo

- **Não criar helper** `require_owner_or_admin` na primeira passada. Check inline. Refatorar para helper só se CODEX rodada 1 ou Code apontarem duplicação grave.
- **Não tocar em `tokens/atomizar`** — já coberto por `test_atomizacao.py:251,258,296` (404 cross-tenant; 403 role errado; 409 terminal).
- **V5 hospitalar fora do escopo (P2 #3 CODEX rodada 1, 2026-05-23).** O JWT do dispensador carrega CNPJ como `sub` (confirmado em `login.py:70` via `_normalizar_identificador`). Em custódia ambulatorial, `prescricao_custodia.detentor_id = CNPJ` — bate. Em custódia hospitalar, `detentor_id = unidade_id` (não CNPJ — confirmado em `hospitalares.py:379`). O check do §4.5 para role `dispensador` só cobre o caso ambulatorial. **Dispensador hospitalar acessando `GET /custodia` em prescrição hospitalar pode receber 403 falso.** Aceitável para 5C porque o fluxo hospitalar tem suite própria; correção fica em ticket follow-up explícito (ver §7.1).
- **Não refatorar matriz de roles do GET /custodia** além do mínimo descrito em §3.3. CODEX rodada 1 pode propor alternativa — preservar como achado, não como mudança neste ticket.
- **Não corrigir cluster auth eventos #41** (`test_g4b::TestEventosAutenticacao`) — domínio separado (`/eventos`, JWT+API Key, G4B integrador). Ticket próprio pós-Etapa 5.
- **Não corrigir cluster catálogo regulatório #39, /health/db #40, órfão auth_paciente #42, CPF-shift #35** — todos cluster próprio.
- **Não criar tabela `carteiras_digitais`** (Dívida B-Carteira #36) — fica para depois.
- **Não validator de CPF geral** (#44) — ticket próprio.

### §7.1 Dívida obrigatória aberta por este ticket

| # | Título proposto | Origem | Severidade |
|---|---|---|---|
| (novo) | TICKET-5C-FOLLOWUP-CUSTODIA-HOSPITALAR | P2 #3 CODEX rodada 1 — V5 dispensador hospitalar fica com 403 falso até `detentor_id = unidade_id` ser reconhecido como vínculo válido via `contexto_operacional='hospitalar' + unidade_id ∈ prestador do CNPJ` | bloqueador soft do deploy hospitalar; não bloqueia MVP ambulatorial |

## §8 Predecessoras e classe

- Predecessor: 5A fechado em `e09dc3e` + `66547e4`; P2 follow-up #43 em `f82b0da`. HEAD atual do main = `f82b0da`.
- Classe `core` — RBAC/autenticação são listados explicitamente em CLAUDE.md §10 como core obrigatório. Mudança de comportamento em endpoints públicos sensíveis (privacidade clínica + integridade de ledger via V10).
- Volume previsto: ~150 linhas de fix em produção (11 endpoints) + ~470 linhas de teste = ~620 linhas → Regra 2 estrita aplica.
- **Bloqueador de deploy do MVP ambulatorial.** Endpoints hospitalares, exames, laudos, agendamentos e circulação diagnóstica não bloqueiam o MVP — vão em tickets sucessores (§10.3).

## §9 Reservado — Prompt sugerido ao Code

*A ser preenchido após CODEX rodada 1 estar integrada em §10. Não enviar ao Code antes.*

## §10 Observações CODEX rodada 1 (2026-05-23) — integradas

CODEX revisou a rodada 0 do ticket contra o repo real em `/Users/fabianotonacoborges/PicSaude_Dev` e retornou **2 P1 + 4 P2 + 2 P3**. **Achado central do CODEX confirmado pelo Arquiteto:** os P1 elevaram o escopo de 6 vulnerabilidades para 9 (V1-V9) e fecharam um bypass crítico em V6.

| # | Severidade | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | P1 | V6 ainda deixava bypass em transferências não-`de=prescritor`; faltava exigir ownership real da prescrição | ✅ Aceito integral | §3.4 reescrita + §4.6 reescrita + §5.6 expandida (4 sub-testes 5.6a/b/c/d cobrindo cada bypass) |
| 2 | P1 | Inventário incompleto: `GET /validacao`, `GET /assinatura`, `GET /comprovante` têm mesmo padrão `_=Depends(require_role(...))`. A afirmação "último bloqueador" precisa absorver esses endpoints OU rebaixar o escopo | ✅ Aceito (Caminho A escolhido por Fabiano em 2026-05-23) — V7/V8/V9 entram no ticket | §2 expandida (V7/V8/V9 adicionados após varredura CODEX confirmar inventário); §4.7/§4.8/§4.9 a redigir; §5 a expandir; §6 a atualizar |
| 3 | P2 | V5 acerta dispensador ambulatorial mas ignora hospitalar (`detentor_id = unidade_id` em hospitalares.py:379) | ✅ Aceito como anti-escopo + dívida própria | §7 atualizado: hospitalar fora; §7.1 abre TICKET-5C-FOLLOWUP-CUSTODIA-HOSPITALAR |
| 4 | P2 | Matriz GET /custodia aceitável, mas "dispensador que já teve custódia" é permissivo — explicitar "histórico de participação" | ✅ Aceito integral | §3.3 reescrita com decisão semântica explícita |
| 5 | P2 | Faltam testes negativos para V6 fechando bypasses (`de=paciente`, `de=dispensador`, `de=prescritor B sobre prescrição A`) | ✅ Aceito integral | §5.6 expandida em 4 sub-testes (5.6a/b/c/d) |
| 6 | P3 | "6 testes obrigatórios" no título de §5 mas spec listava 7 (com 5.5b) | ✅ Aceito | §5 título corrigido para "10 cenários" (V1-V6) |
| 7 | P3 | CNS fake nos exemplos não passa por `normalize_cns` (`"outro_cns_999"` viraria `"999"`) | ✅ Aceito | §5.1 usa `"999888777666555"` (15 dígitos válidos); convenção declarada no topo de §5 |

### §10.1 Varredura CODEX concluída em 2026-05-23

58 matches do padrão `_=Depends(require_role(...))` em `backend/app/routers/`. Classificação:

- **Classe A — coberto V1-V9 (9 matches):** confirmado.
- **Classe A — V10 novo (1 match):** `POST /prescricoes/{proto}/itens/{item_id}/dispensar` em `custodia.py:364` (escrita clínica central). **Absorvido neste ticket** (decisão Fabiano 2026-05-23). Spec em §2.1 (V10) e §4.10. Teste em §5.10.
- **Classe B — outros domínios (40+ matches):** abertos como tickets sucessores. Ver §10.3.
- **Classe C — admin / health / IA stateless (15 matches):** sem ação. Roles administrativas naturalmente excludentes; endpoints IA são stateless sem objeto persistido.
- **Classe D — ambíguo (1 match):** `GET /pacientes/{cpf}/carteira` (pacientes.py:49). Decisão de privacidade fica em ticket próprio (#51).

### §10.2 Confirmações do CODEX rodada 1

- **§3.1 — 403 quando prescrição existe e prescritor não é dono; 404 quando prescrição não existe.** Decisão preservada. (Zero achado.)
- **Token expirado / adulterado**: responsabilidade global de `require_role` / JWT, não precisa virar teste específico do 5C. (Zero achado.)
- **`tokens/atomizar` fora do escopo**: confirmado por `test_atomizacao.py:251,258,296`. (Zero achado.)
- **V5 (`GET /custodia`) corretamente no 5C:** não casa na varredura porque hoje não tem `Depends` nenhum — exatamente o motivo da vulnerabilidade.

### §10.3 Tickets sucessores propostos (classe B da varredura)

Abertos como tasks pendentes para Etapa pós-MVP. **Não absorver neste ticket.**

| Task | Título | Endpoints | Padrão de fix |
|---|---|---|---|
| #47 | TICKET-5C-FOLLOWUP-EXAMES-AGENDAMENTOS | `pedidos_exame.py` (11 endpoints) + `agendamentos.py` (6 endpoints) | Mesmo padrão V1-V10 (owner check inline) |
| #48 | TICKET-5C-FOLLOWUP-LAUDOS | `laudos.py` (12 endpoints) | Mesmo padrão |
| #49 | TICKET-5C-FOLLOWUP-HOSPITALAR | `hospitalares.py:245` + V5 dispensador hospitalar | Owner via `unidade_id` + `contexto_operacional='hospitalar'` |
| #50 | TICKET-5C-FOLLOWUP-CIRCULACAO-DIAGNOSTICA | `circulacao_diagnostica.py:362` | Matriz multi-role específica para chave de circulação |
| #51 | TICKET-5C-FOLLOWUP-CARTEIRA-PACIENTE | `pacientes.py:49` (classe D — ambíguo) | Decisão de privacidade LGPD + UX clínica |

### §10.4 Achados pendentes para rodada 2 (pós-impl)

Itens não absorvidos no escopo atual:

- **Nenhum.** O POST `/{protocolo}/assinatura` em `assinaturas.py:233`, originalmente registrado aqui como pendente, foi **promovido a V11 obrigatório na rodada 1.5** (ver §10.5). Não há mais pendência aberta para rodada 2 além das lapidações P2/P3 normais que o CODEX vier a apontar.

### §10.5 CODEX rodada 1.5 (final pré-impl, 2026-05-23) — integrada

Após integração da rodada 1 + varredura, CODEX revisou o ticket consolidado V1-V10. Retornou **1 P1 + 3 P2 + 2 P3**.

| # | Severidade | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | P1 | `POST /{proto}/assinatura` (assinaturas.py:233) já usa `usuario=Depends`, mas falta owner check antes de INSERT/UPDATE em `prescricao_assinatura` e evento `assinatura_registrada` no ledger. Não pode ficar para rodada 2 — é escrita clínica equivalente em severidade | ✅ Aceito como **V11 obrigatório** | §2.1 V11 novo; §3.5 tabela; §4.11 novo; §5.11 novo; §8 volume atualizado; §10.4 esvaziado |
| 2 | P2 | §5.10 V10 manda checar `tipo_evento IN ('dispensacao_registrada','dispensacao_parcial')`, mas o endpoint real grava `item_dispensado` (custodia.py:560) | ✅ Aceito — baseline genérico por prescrição é mais robusto | §5.10 reescrita: `COUNT(*) FROM prescricao_eventos WHERE prescricao_id = ?` |
| 3 | P2 | V6 dispensador não distinguia custódia da prescrição inteira vs custódia de item; dispensador com custódia ativa só de UM item poderia transferir a global | ✅ Aceito | §3.4 regra 5 e §4.6 com `AND item_id IS NULL`; §5.6e novo (teste negativo) |
| 4 | P2 | §4.5 ainda tinha `usuario["sub"]` cru (não `normalize_cnpj`) e comentário antigo "confirmar" | ✅ Aceito | §4.5 reescrita: `normalize_cnpj(usuario["sub"])` + comentário "histórico de participação ambulatorial" |
| 5 | P3 | §6 grep "Esperado: 10 ocorrências" falharia porque V6 emite múltiplos `ator_mismatch` | ✅ Aceito | §6 flexibilizado: confiar nos testes focais + checar que os 5 códigos aparecem em pelo menos 1 ocorrência cada |
| 6 | P3 | §3.5 tabela de payloads não listava V7-V11 nem `nao_e_dono_da_dispensacao` | ✅ Aceito | §3.5 tabela expandida com todas as 11 vulnerabilidades |

## §11 Status final — Etapa 5 fechada (2026-05-24)

CODEX rodada 2 (pós-impl) retornou **zero P1 + 1 P2 + 2 P3** sobre o commit `01c67fa`. Critério do Pacto atingido — ticket fechado sem rodada 2.5.

### §11.1 Implementação entregue

| Commit | Mensagem |
|---|---|
| `01c67fa` | `feat(5c): autorização mínima em 11 endpoints clínicos centrais` |
| `b020770` | `docs(5c): ticket pré-impl V1-V11 com 3 ciclos CODEX integrados` |

Volume real: 1.207 inserções, 31 deleções, 15 arquivos. Suite focal 17/17 verdes; suite completa sem regressão (27→27 falhas pré-existentes inalteradas; cluster auth eventos #41 não reagiu ao fix do GET /custodia).

### §11.2 Achados CODEX rodada 2

| # | Sev | Achado | Decisão |
|---|---|---|---|
| 1 | P2 | `_get_meta_prescricao` em `assinaturas.py:107` levanta `400 assinatura_nao_aplicavel` para prescrição física antes dos owner checks V8/V11. Prescritor B descobre que protocolo existe e é físico antes do 403. Sem efeito de escrita/ledger. | ✅ Aceito como dívida — follow-up #52 |
| 2 | P3 | V6 chama `get_instance_id_conn(conn)` em `custodia.py:404` antes dos checks de ownership; em first-boot/test pode inserir em `meta_instalacao` + popular cache de processo de forma não rollbackable | ✅ Aceito como dívida — follow-up #53 |
| 3 | P3 | V9 faz autorização em uma transação e busca o comprovante em outra (`_buscar_dados` em `dispensacoes.py:74`). TOCTOU teórico; baixo risco porque dispensações são append-only | ✅ Aceito como dívida — follow-up #54 |

Verificações do CODEX rodada 2 (cruzando com leitura estática do diff):

- `_=Depends` zerado nos 5 routers — ✅
- Os 5 códigos de erro presentes em pelo menos 1 ocorrência cada — ✅
- Imports completos — ✅
- `require_role` não foi alterado — ✅
- 11 fixes inline, sem helper compartilhado — ✅ (consistente com §3.2 KISS)

CODEX não conseguiu rodar a suite focal localmente (PostgreSQL `picsaude_test` recusou conexão em `127.0.0.1:5432`). Rodou os 4 arquivos SQLite realinhados — 139 passes + 1 falha pré-existente em `test_string_validacao.py` (CPF ICP `01112223330` vs `11122233300` — cluster CPF-shift #35, não causado pelo 5C). Cobertura compensada pela suite que o Code já rodou.

### §11.3 Follow-ups abertos por esta rodada

| # | Origem | Título proposto | Severidade |
|---|---|---|---|
| #52 | P2 CODEX rodada 2 | Owner check antes de `_get_meta_prescricao` em V8/V11 — separar SELECT de prescritor_id do check de `tipo_emissao` para evitar info disclosure 400 vs 403 em prescrição física | P2 (info disclosure, sem ledger) — não bloqueia deploy ambulatorial |
| #53 | P3 CODEX rodada 2 | V6 mover `get_instance_id_conn(conn)` para depois dos checks de ownership — evitar side-effect de cache em caminho rejeitado | P3 (lapidação; ~5 linhas) |
| #54 | P3 CODEX rodada 2 | V9 unificar autorização + busca em single-tx — fechar TOCTOU teórico em `comprovante` | P3 (refator; baixa prioridade enquanto dispensações forem append-only) |

### §11.4 Etapa 5 — status

| Sub-tarefa | Status | Commits |
|---|---|---|
| 5A — Falhar entrega digital sem carteira | ✅ Fechada | `e09dc3e` + `66547e4` + P2 #43 follow-up `f82b0da` |
| 5B — OTP secrets/guard | ✅ Fechada | `5fa6902` |
| 5C — Autorização mínima | ✅ Fechada | `01c67fa` + `b020770` |
| 5D — Guard JWT_SECRET | ✅ Fechada | `6ff6910` |

**Etapa 5 fechada em 2026-05-24.** Próximo bloqueador de deploy: Etapa 6 (DEMO_MODE + seletor de papéis).

## §12 Prompt final ao Code

Pronto para implementação. Integradas: CODEX rodada 1 (7 achados), varredura `_=Depends` (V10 P1 + 5 tickets sucessores), CODEX rodada 1.5 (V11 P1 + 5 lapidações P2/P3).

````
Tarefa: TICKET-5C — Autorização mínima em endpoints clínicos centrais.
Classe: core (RBAC). Pacto: Regra 2 estrita (ticket formal redigido,
3 ciclos de revisão CODEX integrados em §10 / §10.5).

LOCAL DO TICKET
───────────────
backend/docs/tickets/TICKET-5C-AUTORIZACAO-MINIMA.md

LEIA O TICKET INTEIRO antes de implementar — em particular §2 (inventário),
§3 (decisões), §4 (spec por endpoint), §5 (testes), §6 (verificação),
§7 (anti-escopo), §10 + §10.5 (achados CODEX integrados).

CONTEXTO REGULATÓRIO (§1)
─────────────────────────
RDC 1.000/2025 e CLAUDE.md §3 exigem amarração entre ator declarado e
ator do JWT em todos os endpoints autenticados. Hoje, 11 endpoints clínicos
centrais falham nessa amarração: 10 descartam o usuário (`_=Depends(...)`)
ou nem têm Depends; 1 captura o usuário mas não valida ownership. Esse
ticket fecha o último bloqueador de autorização do MVP ambulatorial antes
do deploy público (Etapa 8).

ESCOPO
──────
TOCAR (produção):
  - backend/app/routers/prescricoes.py (V1, V2, V3, V4)
  - backend/app/routers/custodia.py    (V5, V6, V10)
  - backend/app/routers/validacao.py   (V7)
  - backend/app/routers/assinaturas.py (V8, V11)
  - backend/app/routers/dispensacoes.py (V9)

TOCAR (testes):
  - backend/tests/integration/test_prescricoes.py (V1, V2, V3, V4)
  - backend/tests/integration/test_custodia_autorizacao.py (NOVO — V5, V6, V10)
  - backend/tests/integration/test_validacao.py (NOVO se não existir — V7)
  - backend/tests/integration/test_assinaturas.py (NOVO se não existir — V8, V11)
  - backend/tests/integration/test_dispensacoes.py (NOVO se não existir — V9)

NÃO TOCAR (anti-escopo §7):
  - tokens/atomizar (já coberto por test_atomizacao.py)
  - Endpoints hospitalares, exames, laudos, agendamentos, circulação
    diagnóstica, /pacientes/{cpf}/carteira → tickets sucessores #47-51
  - Helper require_owner_or_admin (KISS — check inline)
  - Máquina de estados, vocabulário de ledger, schema do banco
  - Clusters de falhas pré-existentes (#35, #39, #40, #41, #42)

VERIFICAÇÃO PRÉ-IMPLEMENTAÇÃO (§6)
──────────────────────────────────
Antes de codificar:

  grep -nE "_=Depends\(require_role" backend/app/routers/prescricoes.py \
       backend/app/routers/custodia.py backend/app/routers/validacao.py \
       backend/app/routers/assinaturas.py backend/app/routers/dispensacoes.py

  Esperado: 9 matches (V1, V2, V3, V4, V6, V7, V8, V9, V10).
  V5 não casa (sem Depends nenhum — ver custodia.py:237).
  V11 não casa (já usa usuario=Depends, falta owner check no corpo —
    ver assinaturas.py:233).

  Se mais que 9 matches → mapear extras e reportar antes de implementar.

ESPECIFICAÇÃO POR ENDPOINT
──────────────────────────

V1 — POST /prescricoes (prescricoes.py:213-214)
  Trocar `_` por `usuario`. Após `cns = normalize_cns(payload.cns_prescritor)`
  (linha 231), antes de qualquer query/INSERT:
    if normalize_cns(usuario["sub"]) != cns:
        raise HTTPException(403, detail={
            "codigo": "prescritor_mismatch",
            "mensagem": "CNS do payload não coincide com prescritor autenticado.",
        })

V2 — POST /prescricoes/fisica (prescricoes.py:681-682)
  Espelho de V1. Check após linha 697 (`cns = normalize_cns(...)`).

V3 — GET /prescricoes/{proto}/documento (prescricoes.py:832-833)
  Trocar `_` por `usuario`. Owner check inline:
    if usuario["role"] != "admin":
        owner = conn.execute(
            "SELECT 1 FROM prescricoes p JOIN prescritores pr "
            "ON pr.id = p.prescritor_id WHERE p.protocolo = ? AND pr.cns = ?",
            (protocolo, normalize_cns(usuario["sub"])),
        ).fetchone()
        if not owner:
            existe = conn.execute(
                "SELECT 1 FROM prescricoes WHERE protocolo = ?", (protocolo,),
            ).fetchone()
            if not existe:
                raise HTTPException(404, "Prescrição não encontrada.")
            raise HTTPException(403, detail={
                "codigo": "nao_e_dono_da_prescricao",
                "mensagem": "Esta prescrição foi emitida por outro prescritor.",
            })

V4 — GET /prescricoes/{proto}/pdf (prescricoes.py:892-895)
  Mesmo padrão de V3 mas check APENAS para role "prescritor"
  (dispensador e admin passam direto).

V5 — GET /custodia/{proto}/custodia (custodia.py:237-238)
  Adicionar `usuario=Depends(require_role("prescritor", "dispensador",
  "paciente", "admin", "auditor"))`. Matriz §3.3:
  - admin / auditor → sempre
  - prescritor → SELECT 1 FROM prescritores WHERE id = ? AND cns = ?
  - paciente → SELECT 1 FROM pacientes WHERE id = ? AND cpf = ?
    (paciente JWT sub = CPF)
  - dispensador → SELECT 1 FROM prescricao_custodia
                    WHERE prescricao_id = ?
                      AND detentor_tipo = 'dispensador'
                      AND detentor_id = ?  (normalize_cnpj(usuario["sub"]))
                    LIMIT 1
    (histórico de participação ambulatorial; sem encerrada_em IS NULL —
     ver §3.3 explicação completa)
  - Senão → 403 com codigo="sem_vinculo_com_prescricao"

V6 — POST /custodia/{proto}/custodia/transferir (custodia.py:282-283)
  Regras §3.4 (5 regras):
    1. payload.de == "paciente" → 403 (fluxo paciente em auth.py:185,269)
    2. payload.de != usuario["role"] → 403 ator_mismatch
    3. Para prescritor: cns_jwt = normalize_cns(usuario["sub"]);
       cns_payload = normalize_cns(payload.de_id);
       cns_jwt != cns_payload → 403 ator_mismatch
       AND SELECT 1 FROM prescritores WHERE id = presc.prescritor_id
           AND cns = cns_jwt → senão 403 (ownership real)
    4. Para dispensador: cnpj_jwt = normalize_cnpj(usuario["sub"]);
       cnpj_payload = normalize_cnpj(payload.de_id);
       cnpj_jwt != cnpj_payload → 403 ator_mismatch
       AND SELECT 1 FROM prescricao_custodia
           WHERE prescricao_id = ?
             AND item_id IS NULL  (← prescrição inteira, não item-level)
             AND detentor_tipo = 'dispensador'
             AND detentor_id = cnpj_jwt
             AND encerrada_em IS NULL
       LIMIT 1 → senão 403 (vínculo ativo da prescrição inteira)
    5. Hospitalar fica fora (ticket #49).
  Ver §4.6 para código completo.

V7 — GET /prescricoes/{proto}/validacao (validacao.py:25-29)
  Mesmo padrão de V3. Owner check APENAS para role "prescritor"
  (dispensador e admin passam direto).

V8 — GET /prescricoes/{proto}/assinatura (assinaturas.py:148-151)
  Mesmo padrão de V3. Owner check APENAS para role "prescritor"
  (admin passa direto).

V9 — GET /dispensacoes/{id}/comprovante (dispensacoes.py:276-280)
  Owner check multi-role:
    admin / auditor → sempre
    dispensador → normalize_cnpj(usuario["sub"]) != dispensacoes.cnpj_estabelecimento
                   → 403 codigo="nao_e_dono_da_dispensacao"
    prescritor → normalize_cns(usuario["sub"]) != prescritor.cns
                  (da prescrição associada) → 403 codigo="nao_e_dono_da_prescricao"
  JOIN necessário: dispensacoes → prescricao_itens → prescricoes →
                   prescritores. Ver §4.9 para SQL completo.

V10 — POST /prescricoes/{proto}/itens/{item_id}/dispensar (custodia.py:363-364)
  Trocar `_` por `usuario`. Antes de qualquer SELECT/INSERT:
    cnpj = normalize_cnpj(payload.cnpj_estabelecimento)
    if normalize_cnpj(usuario["sub"]) != cnpj:
        raise HTTPException(403, detail={
            "codigo": "ator_mismatch",
            "mensagem": "CNPJ do payload não coincide com dispensador autenticado.",
        })

V11 — POST /prescricoes/{proto}/assinatura (assinaturas.py:233-237)
  PADRÃO DIFERENTE — usuario JÁ é capturado, falta apenas owner check.
  Após `meta = _get_meta_prescricao(conn, protocolo)` (linha 258),
  antes de qualquer INSERT/UPDATE/evento:
    if usuario["role"] != "admin":
        owner = conn.execute(
            "SELECT 1 FROM prescritores WHERE id = ? AND cns = ?",
            (meta["prescritor_id"], normalize_cns(usuario["sub"])),
        ).fetchone()
        if not owner:
            raise HTTPException(403, detail={
                "codigo": "nao_e_dono_da_prescricao",
                "mensagem": "Esta prescrição foi emitida por outro prescritor.",
            })

CONVENÇÕES (§3.5)
─────────────────
- Chaves do payload de erro em português: `codigo` e `mensagem` (NÃO
  `code`/`message`). Padrão do projeto — ver 5A.
- Mensagens consistentes entre endpoints similares (V3=V4=V7=V8=V11
  todas usam "Esta prescrição foi emitida por outro prescritor.").
- Status code: 201 para sucesso de POST; 200 para GET; 403 para
  rejeição; 404 quando protocolo/recurso inexiste.
- Imports necessários: `from app.utils.helpers import normalize_cns,
  normalize_cpf, normalize_cnpj` onde ainda não houver.

TESTES OBRIGATÓRIOS (§5 — 17 cenários)
──────────────────────────────────────
V1 §5.1, V2 §5.2, V3 §5.3, V4 §5.4: 1 cada (4 testes)
V5 §5.5 + §5.5b: 2 testes (sem token 401 + outro prescritor 403)
V6 §5.6a/b/c/d/e: 5 testes (todos os bypasses + custódia item-level)
V7 §5.7, V8 §5.8: 1 cada (2 testes)
V9 §5.9a/b: 2 testes (dispensador + prescritor)
V10 §5.10: 1 teste
V11 §5.11: 1 teste

ATENÇÃO aos asserts críticos (todos os 403 com efeito de escrita):
- Baseline pré-request e pós-request em tabelas relevantes para
  garantir rollback efetivo.
- V1/V2: baseline em prescricoes, prescritores, pacientes,
         prescricao_eventos, eventos_publicacao
- V6: baseline em prescricao_custodia, prescricao_eventos
- V10: baseline em dispensacoes, prescricao_itens (status_item),
       prescricao_eventos (COUNT(*) WHERE prescricao_id = ? — genérico),
       eventos_publicacao
- V11: baseline em prescricao_assinatura (COUNT + campos específicos
       para detectar UPDATE escapado), prescricao_eventos, eventos_publicacao

CNS / CPF / CNPJ FAKE NOS TESTES
- CNS válido: 15 dígitos (ex: "999888777666555")
- CPF: 11 dígitos numéricos
- CNPJ: 14 dígitos numéricos
- NÃO usar strings curtas que normalize_* reduz para vazio ou tamanho errado.

VERIFICAÇÃO PÓS-IMPLEMENTAÇÃO (§6)
──────────────────────────────────

1. Greps de produção:
   grep -rn "_=Depends" backend/app/routers/prescricoes.py \
        backend/app/routers/custodia.py backend/app/routers/validacao.py \
        backend/app/routers/assinaturas.py backend/app/routers/dispensacoes.py
   Esperado: zero matches em todos os 5 routers.

   grep -rn "prescritor_mismatch\|nao_e_dono_da_prescricao\|sem_vinculo_com_prescricao\|ator_mismatch\|nao_e_dono_da_dispensacao" backend/app/routers/
   Esperado: cada um dos 5 códigos aparece em pelo menos 1 ocorrência.
   Contagem total não é fixada (V6 emite múltiplos ator_mismatch).

2. Suite focal:
   cd backend
   pytest tests/integration/test_prescricoes.py \
          tests/integration/test_custodia_autorizacao.py \
          tests/integration/test_validacao.py \
          tests/integration/test_assinaturas.py \
          tests/integration/test_dispensacoes.py \
          -v -k "v1_ or v2_ or v3_ or v4_ or v5_ or v6_ or v7_ or v8_ or v9_ or v10_ or v11_"
   Esperado: 17/17 verdes.

3. Suite completa:
   pytest -q
   Esperado: nenhuma regressão. 27 falhas pré-existentes podem
   flutuar conforme cluster auth eventos #41 reagir ao fix do
   GET /custodia (improvável mas possível) — declarar separadamente.

COMMITS ESPERADOS
─────────────────
Pode ser um único commit (preferido, mudança coesa de RBAC) ou dois
(produção + testes). Sugestão de mensagem para commit único:

  feat(5c): autorização mínima em 11 endpoints clínicos centrais

  Fecha 11 vulnerabilidades de autorização identificadas em 3 rodadas
  de revisão CODEX (rodada 1: 7 achados; varredura: V10 P1 + 5 tickets
  sucessores; rodada 1.5: V11 P1 + 5 lapidações). Cada endpoint recebe
  owner check inline antes de qualquer escrita/leitura sensível:

  - V1/V2  POST /prescricoes e /fisica          → CNS payload vs JWT
  - V3     GET /prescricoes/{p}/documento       → owner check + 404
  - V4     GET /prescricoes/{p}/pdf             → owner check (prescritor)
  - V5     GET /prescricoes/{p}/custodia        → matriz multi-role
  - V6     POST /custodia/{p}/transferir       → 5 regras §3.4 (bypass)
  - V7     GET /prescricoes/{p}/validacao      → owner check (prescritor)
  - V8     GET /prescricoes/{p}/assinatura     → owner check (prescritor)
  - V9     GET /dispensacoes/{id}/comprovante  → multi-role (dispensador,
                                                  prescritor, auditor, admin)
  - V10    POST /custodia/{p}/itens/{i}/dispensar → CNPJ payload vs JWT
  - V11    POST /prescricoes/{p}/assinatura    → owner check antes upsert

  17 testes adicionados em tests/integration/ cobrindo todos os
  cenários, com asserts de rollback regulatório (ledger, outbox,
  custódia, prescricao_assinatura) para os endpoints com efeito de
  escrita.

  Tickets sucessores #47-51 abertos para endpoints fora do MVP
  ambulatorial (exames, laudos, agendamentos, circulação, hospitalar,
  carteira paciente).

  Refs: backend/docs/tickets/TICKET-5C-AUTORIZACAO-MINIMA.md
        CLAUDE.md §3, §10 (RBAC como core obrigatório)
        RDC 1.000/2025 (rastreabilidade de emissão e custódia)

PREDECESSORAS
─────────────
HEAD atual do main: f82b0da (P2 follow-up 5A). Confirmar com
`git log -1 --oneline` antes de iniciar. Se não bater, fazer
`git pull --rebase origin main` antes de qualquer alteração.

NÃO ESQUEÇA
───────────
- Ticket é a fonte de verdade. Em caso de dúvida sobre cenário borda,
  releia §3 + §4 + §5 do endpoint específico.
- Chaves codigo+mensagem em português (não code+message).
- Status code: 201 sucesso POST; 200 sucesso GET; 403 rejeição;
  404 quando protocolo inexiste (não 403).
- Para V6 use `AND item_id IS NULL` no check de custódia dispensador
  (transferir_custodia move prescrição inteira).
- Para V10 baseline use COUNT(*) FROM prescricao_eventos WHERE
  prescricao_id = ? (genérico — não filtrar tipo_evento específico).
- Para V11 assert deve cobrir tanto cenário INSERT (nenhuma linha
  nova) quanto UPDATE (campos não alterados) em prescricao_assinatura.
- Reporte separadamente as falhas pré-existentes após pytest -q.
- NÃO criar helper require_owner_or_admin nesta passada.
- NÃO refatorar matriz de roles de V5 além do §3.3.
- NÃO absorver tickets sucessores #47-51.
````

---

> **Status do ticket (2026-05-24 — fechado):**
> Rodada 0 (Arquiteto) ✅
> CODEX rodada 1 (revisão inicial de spec) ✅ — 7 achados integrados em §10
> CODEX varredura `_=Depends` ✅ — V10 P1 + 5 tickets sucessores integrados em §10.1/§10.3
> CODEX rodada 1.5 (final pré-impl) ✅ — V11 P1 + 5 lapidações integradas em §10.5
> Fabiano: aprovado ✅
> Code: implementado em `01c67fa` ✅
> CODEX rodada 2 (pós-implementação) ✅ — zero P1, 1 P2 + 2 P3 abertos como #52/#53/#54 (§11)
> **Etapa 5 fechada** em 2026-05-24.
