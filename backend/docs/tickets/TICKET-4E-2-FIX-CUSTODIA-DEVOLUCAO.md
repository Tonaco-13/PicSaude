# TICKET 4E.2-FIX-CUSTODIA-DEVOLUCAO — `devolver_item` usa evento genérico

> **Classe (CLAUDE.md §10):** `module` com toque em `core` (vocabulário de eventos do ledger é core; routes que escrevem em ledger clínico são module)
> **Pacto:** Regra 2 estrita
> **Data:** 2026-05-21
> **Origem:** Achado P2-A do CODEX (`docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md` §3.1), confirmado pelo Arquiteto em `TICKET-4E-2-RELATORIO-INTEGRADO.md` §3.2
> **Predecessor:** Relatório integrado 4E.2 (`TICKET-4E-2-RELATORIO-INTEGRADO.md`)
> **Sucessor:** Etapa 5
> **Redigido por:** Arquiteto (rodada 0). Aguarda revisão CODEX (rodada 1).

---

## §1 Contexto regulatório

Devolução de itens prescritos é evento auditável previsto no fluxo de custódia (CLAUDE.md §3) e na máquina de estados de itens (CLAUDE.md §5b). Há **dois cenários funcionalmente distintos** que o vocabulário canônico (CLAUDE.md §2) já separa:

- `item_devolvido_paciente` — abandono de compra: item retorna ao paciente, disponível para nova tentativa em outra farmácia
- `item_devolvido_prescritor` — erro clínico identificado no balcão: item retorna ao prescritor, aguarda correção via nova prescrição derivada (`origem_prescricao_id`)

A distinção tem **valor regulatório real**:

| Aspecto | `item_devolvido_paciente` | `item_devolvido_prescritor` |
|---|---|---|
| Motivo padrão | Operacional/financeiro | Clínico |
| Estado final do item | `devolvido_paciente` (retry possível) | `devolvido_prescritor` (terminal) |
| Custódia retorna a | Paciente | Prescritor |
| Próximo passo | Nova apresentação em outra farmácia | Nova prescrição derivada |
| Implicação para vigilância | Indicador econômico | Indicador de erro de prescrição (notificável a CRM/CFM em caso recorrente) |

> **Nota de escopo (P2 CODEX rodada 1):** A coluna "Custódia retorna a" descreve a **intenção do fluxo de devolução** existente no produto, não promessa deste ticket. Este ticket **corrige apenas o evento de ledger e o ator** — não modifica `_fechar_custodia_ativa`, não abre novas custódias, não altera transições de `prescricao_custodia`. Coerência estrutural da cadeia de custódia em fluxos de devolução fica para `TICKET-COERENCIA-DEVOLUCOES.md` (registrado em `TICKET-4E-2-RELATORIO-INTEGRADO.md §3.3.2`).

Eventos no ledger são a **única fonte forense** para distinguir esses dois fluxos a posteriori. Gravar evento genérico `item_devolvido` apaga essa distinção no momento da auditoria — o motivo no payload pode estar mal preenchido ou inexistente, e o `tipo_evento` se torna a única âncora estável.

## §2 Achado original (CODEX) + análise Arquiteto

### §2.1 Achado CODEX (P2-A, 2026-05-21)

> `devolver_item` grava evento genérico `item_devolvido`, mas `CLAUDE.md §2` define eventos separados: `item_devolvido_paciente` e `item_devolvido_prescritor`. Além disso, o ator fica hardcoded como `dispensador` / `sistema`, apesar do endpoint aceitar `dispensador` e `prescritor`.
>
> Sugestão: escolher `tipo_evento` conforme `payload.para` e usar o usuário real do `Depends(require_role(...))` para `ator_tipo/ator_id`. Se a intenção for manter `item_devolvido`, atualizar formalmente o vocabulário em `CLAUDE.md`.

### §2.2 Inspeção Arquiteto do código atual

`backend/app/routers/custodia.py` linhas 577–630 (commit `6b5dbed`):

```python
@router.post("/{protocolo}/itens/{item_id}/devolver", status_code=200)
def devolver_item(protocolo: str, item_id: int, payload: DevolverItemIn,
                  _=Depends(require_role("dispensador", "prescritor"))):    # ← descarta o usuário (_)
    """
    Devolve um item ao paciente (abandono de compra) ou ao prescritor (erro).

    - Devolução ao prescritor: status_item → 'cancelado', aguarda correção.   # ← MENTIRA (código faz devolvido_prescritor)
    - Devolução ao paciente:   status_item → 'pendente', disponível para nova dispensação.   # ← MENTIRA (código faz devolvido_paciente)
    """
    ...
    novo_status_item = "devolvido_prescritor" if payload.para == "prescritor" else "devolvido_paciente"
    ...
    _gravar_evento(conn, presc["id"], "item_devolvido", "dispensador", "sistema",   # ← três bugs
                   {"item_id": item_id, ...
                    "devolvido_para": payload.para,
                    ...}, agora,
                   instance_id=instance_id)
```

### §2.3 Três defeitos cofirmados + um detalhe extra

| Defeito | Linha | Status |
|---|---|---|
| `tipo_evento` é `"item_devolvido"` genérico, deveria ser `item_devolvido_paciente` ou `item_devolvido_prescritor` conforme `payload.para` | 616 | Confirmado |
| `ator_tipo` hardcoded `"dispensador"` — endpoint aceita também `"prescritor"` | 616 | Confirmado |
| `ator_id` hardcoded `"sistema"` — perde rastreabilidade do ator real | 616 | Confirmado |
| **Extra encontrado pelo Arquiteto:** docstring linhas 582–583 afirma transições `→ 'cancelado'` e `→ 'pendente'` que NÃO correspondem ao código real (que faz `devolvido_prescritor` e `devolvido_paciente`) | 582–583 | Confirmado |

### §2.4 Por que isso é Regra 2 estrita

`custodia.py` é centro do fluxo de custódia clínica. Mudança no vocabulário de eventos gravados:
- Toca contrato auditável (CLAUDE.md §2)
- Pode invalidar consultas/dashboards externos que filtram por `tipo_evento`
- Exige verificação de cobertura por teste pré e pós

Tamanho estimado da implementação: ~30 linhas de produção + ~50 linhas de teste = ~80 linhas. **Mesmo abaixo de 100 linhas, a sensibilidade do escopo justifica ciclo formal Regra 2.**

---

## §3 Escopo

### §3.1 Arquivos que serão tocados

- `backend/app/routers/custodia.py` — endpoint `devolver_item` (linhas 577–630)
- `backend/tests/integration/test_custodia_devolucao.py` — **novo arquivo de teste** (não há cobertura E2E focal para este endpoint hoje)

### §3.2 Arquivos que NÃO serão tocados

- `backend/app/domain/states.py` — máquina de estados já tem `devolvido_paciente`/`devolvido_prescritor` corretos
- `backend/app/domain/ledger.py` — helper não precisa mudar
- Outros routers — nenhum outro endpoint usa `tipo_evento="item_devolvido"` (validar com grep durante a impl)
- CLAUDE.md — vocabulário já está correto; este ticket alinha o código com a doc, não o contrário
- Frontend — payload de entrada (`{para, motivo}`) e resposta (`{status_item, ...}`) **não mudam**

### §3.3 Vocabulário de eventos — confirmação prévia

Antes de implementar, validar via grep que nenhum **consumer de produção** depende do evento genérico. Greps restritos a `app/` com literal exata (P2 CODEX rodada 1 — separar busca em código de menções textuais em docs/tests):

```bash
cd backend
# Código de produção — esperado: apenas custodia.py:616
grep -RnE "\"item_devolvido\"|'item_devolvido'" app/

# Identificar consumers (handlers, dashboards, queries internas) que filtrem pelo nome
grep -RnE "tipo_evento\s*==\s*['\"]item_devolvido['\"]|WHERE.*tipo_evento\s*=\s*['\"]item_devolvido['\"]" app/

# Eventos canônicos já reconhecidos pelo vocabulário (espera-se zero usos de produção hoje)
grep -RnE "item_devolvido_(paciente|prescritor)" app/
```

Greps em `tests/`, `docs/` e `scripts/` são apenas informativos (esperam-se ocorrências em strings de teste/documentação) e **não bloqueiam** a implementação.

Se aparecer consumer **em `app/`** dependente de `item_devolvido` genérico, **parar e escalar para o Arquiteto** antes de prosseguir.

---

## §4 Spec de implementação

### §4.1 Capturar o usuário do `Depends`

**Antes** (linha 578):
```python
def devolver_item(protocolo: str, item_id: int, payload: DevolverItemIn,
                  _=Depends(require_role("dispensador", "prescritor"))):
```

**Depois:**
```python
def devolver_item(protocolo: str, item_id: int, payload: DevolverItemIn,
                  usuario=Depends(require_role("dispensador", "prescritor"))):
```

Notar: `_` vira `usuario`. O resto da assinatura permanece igual.

### §4.2 Escolher `tipo_evento` conforme destino

Substituir a chamada `_gravar_evento` da linha 616 por:

```python
# Vocabulário canônico (CLAUDE.md §2): eventos separados por destino
tipo_evento = (
    "item_devolvido_prescritor"
    if payload.para == "prescritor"
    else "item_devolvido_paciente"
)

# Ator real do JWT, não hardcoded "sistema"
# Acesso estrito (não .get) — falha cedo se contrato do JWT mudar (P3 CODEX rodada 1)
ator_tipo = usuario["role"]    # "dispensador" ou "prescritor"
ator_id   = usuario["sub"]     # CNPJ do dispensador OU CNS do prescritor

_gravar_evento(
    conn, presc["id"], tipo_evento, ator_tipo, ator_id,
    {"item_id": item_id,
     "nome_medicamento": item["nome_medicamento"],
     "devolvido_para": payload.para,
     "motivo": payload.motivo,
     "novo_status_item": novo_status_item},
    agora,
    instance_id=instance_id,
)
```

**Cuidado:** verificar a estrutura real de `usuario` retornado por `require_role`. Se as chaves não forem exatamente `role` e `sub`, ajustar conforme o JWT/sessão do PicSaúde (provavelmente já é assim — `auth.py:269` já usa `usuario["sub"]`).

### §4.3 Corrigir a docstring

**Antes:**
```python
"""
Devolve um item ao paciente (abandono de compra) ou ao prescritor (erro).

- Devolução ao prescritor: status_item → 'cancelado', aguarda correção.
- Devolução ao paciente:   status_item → 'pendente', disponível para nova dispensação.
"""
```

**Depois:**
```python
"""
Devolve um item ao paciente (abandono de compra) ou ao prescritor (erro clínico).

Transições (CLAUDE.md §5b + `domain/states.py::TRANSICOES_ITEM`):
- payload.para = "prescritor": status_item → 'devolvido_prescritor' (terminal*).
  Evento ledger: 'item_devolvido_prescritor'. Aguarda nova prescrição derivada.
- payload.para = "paciente": status_item → 'devolvido_paciente' (não-terminal).
  Evento ledger: 'item_devolvido_paciente'. Item pode ser apresentado em outra farmácia.

Custódia ativa do item é encerrada em ambos os casos.
O ator (dispensador ou prescritor) é capturado via Depends(require_role).
"""
```

---

## §5 Critérios de aceite

### §5.1 Funcionais (comportamento observável)

1. POST `/prescricoes/{protocolo}/itens/{item_id}/devolver` com `payload.para = "prescritor"` gera evento ledger com `tipo_evento = "item_devolvido_prescritor"` (rota correta confirmada via `APIRouter(prefix="/prescricoes")` em `custodia.py:34` — achado P1 CODEX rodada 1 corrigido)
2. POST com `payload.para = "paciente"` gera evento ledger com `tipo_evento = "item_devolvido_paciente"`
3. `ator_tipo` no evento corresponde ao role do JWT (`dispensador` ou `prescritor`), nunca hardcoded
4. `ator_id` no evento corresponde ao `sub` do JWT (CNPJ ou CNS), nunca `"sistema"`
5. `instance_id` no evento continua sendo preenchido (já estava correto desde 4D.1)
6. Payload de entrada e resposta da API permanecem idênticos (sem breaking change para o frontend)

### §5.2 Estruturais (código)

7. Endpoint usa `usuario=Depends(...)` em vez de `_=Depends(...)`
8. Docstring reflete o comportamento real do código
9. Grep restrito a código de produção `grep -RnE "\"item_devolvido\"|'item_devolvido'" app/` retorna **zero** matches (greps em `tests/`/`docs/` não contam — podem ter menções textuais legítimas)

### §5.3 Não-regressão

10. Suíte completa da Etapa 4 verde após o fix:
    ```bash
    pytest tests/test_instance_id.py tests/integration/test_4e_e2e_consolidado.py tests/integration/test_4d1_instance_id_ledger.py tests/integration/test_4d2_instance_id_ledger.py -v
    ```
11. Novo teste em `tests/integration/test_custodia_devolucao.py` passa (escopo abaixo)

---

## §6 Testes a implementar

Novo arquivo: `backend/tests/integration/test_custodia_devolucao.py`

**Princípios de teste:**

- Cada cenário monta seu próprio setup (sem acoplamento por ordem de execução — P2 CODEX rodada 1)
- Asserções em ledger são filtradas por `prescricao_id` criado **no próprio teste** (não consultam estado histórico do banco — P2 CODEX rodada 1)
- Cada cenário também valida a forma da resposta HTTP (critério §5.1 #6 — P2 CODEX rodada 1)

### §6.1 C1 — Devolução ao paciente (abandono)

1. **Setup interno do teste:** emitir prescrição, transferir custódia ao dispensador, dispensador chama `POST /prescricoes/{protocolo}/itens/{item_id}/devolver` com `payload.para = "paciente"`
2. **Asserções de resposta HTTP:**
   - `response.status_code == 200`
   - JSON contém pelo menos: `protocolo`, `item_id`, `nome_medicamento`, `status_item == 'devolvido_paciente'`, `status_prescricao` (forma atual preservada)
3. **Asserções de estado de domínio:**
   - `prescricao_itens.status_item == 'devolvido_paciente'`
4. **Asserções de ledger** (filtradas por `prescricao_id` do teste, não query global):
   - Existe row em `prescricao_eventos` com `prescricao_id = ${id_do_teste}` e `tipo_evento = 'item_devolvido_paciente'`
   - `ator_tipo == 'dispensador'`, `ator_id == ${CNPJ do dispensador do JWT}` (não `"sistema"`)
   - `instance_id` não-NULL
   - Payload contém `devolvido_para='paciente'`, `motivo`, `novo_status_item='devolvido_paciente'`

### §6.2 C2 — Devolução ao prescritor (erro clínico)

1. **Setup interno do teste:** igual ao C1, mas `payload.para = "prescritor"` e `motivo` clinicamente plausível
2. **Asserções de resposta HTTP:**
   - `response.status_code == 200`
   - JSON contém: `status_item == 'devolvido_prescritor'`, demais campos preservados
3. **Asserções de estado de domínio:**
   - `prescricao_itens.status_item == 'devolvido_prescritor'` (terminal)
4. **Asserções de ledger** (filtradas por `prescricao_id` do teste):
   - `tipo_evento == 'item_devolvido_prescritor'`
   - `ator_tipo == 'dispensador'`, `ator_id == ${CNPJ do dispensador}`
   - `instance_id` não-NULL

### §6.3 C3 — Ator = prescritor (quando o próprio prescritor opera o endpoint)

1. **Setup interno do teste:** prescritor com JWT chama `devolver_item` (fluxo permitido por `require_role("dispensador", "prescritor")`)
2. **Asserções de resposta HTTP:**
   - `response.status_code == 200`
   - Forma da resposta preservada
3. **Asserções de ledger** (filtradas por `prescricao_id` do teste):
   - `ator_tipo == 'prescritor'`, `ator_id == ${CNS do prescritor do JWT}`
   - `tipo_evento` consistente com `payload.para` informado (testar pelo menos um valor de `payload.para` neste cenário — escolha do Code, com justificativa em comentário)

### §6.4 C4 — Regressão de vocabulário (sem acoplamento por ordem)

C4 vira **assertion helper** independente, montando o **próprio setup mínimo** e verificando o vocabulário. Não depende de C1/C2/C3.

```python
def test_devolver_item_nunca_grava_tipo_evento_generico():
    """
    Garante que o endpoint nunca grava tipo_evento='item_devolvido' (sem sufixo).
    Vocabulário canônico CLAUDE.md §2: apenas 'item_devolvido_paciente' e 'item_devolvido_prescritor'.

    Este teste monta seu próprio setup e filtra eventos pelo prescricao_id criado aqui —
    não consulta estado histórico do banco (mitiga falso positivo por rows pré-correção).
    """
    # Setup mínimo próprio
    protocolo, prescricao_id, item_id = _fixture_prescricao_em_custodia(client, ...)

    # Disparar uma devolução de cada tipo no mesmo prescricao_id
    client.post(f"/prescricoes/{protocolo}/itens/{item_id}/devolver",
                json={"para": "paciente", "motivo": "..."},
                headers=_jwt_dispensador())
    # Recriar custodia para o segundo disparo (item_id_2)
    item_id_2 = _criar_segundo_item_em_custodia(...)
    client.post(f"/prescricoes/{protocolo}/itens/{item_id_2}/devolver",
                json={"para": "prescritor", "motivo": "..."},
                headers=_jwt_dispensador())

    # Validar vocabulário APENAS nos eventos da prescrição criada aqui
    eventos = conn.execute(
        """
        SELECT DISTINCT tipo_evento
          FROM prescricao_eventos
         WHERE prescricao_id = ?
           AND tipo_evento LIKE 'item_devolvido%'
        """,
        (prescricao_id,),
    ).fetchall()
    tipos = {row[0] for row in eventos}

    assert "item_devolvido" not in tipos, \
        f"Evento genérico 'item_devolvido' foi gravado no prescricao_id={prescricao_id} — viola CLAUDE.md §2"
    assert tipos.issubset({"item_devolvido_paciente", "item_devolvido_prescritor"}), \
        f"Vocabulário inesperado: {tipos - {'item_devolvido_paciente', 'item_devolvido_prescritor'}}"
```

**Alternativa aceitável:** C4 também pode ser implementado como **grep estático** no código de produção (assertando que `"item_devolvido"` literal exata não aparece em `app/routers/`). A escolha entre integração ou estática fica com o Code, justificada em comentário.

### §6.5 Helpers locais sugeridos (não obrigatórios)

Para reduzir duplicação entre C1/C2/C3, helpers locais como `_fixture_prescricao_em_custodia()`, `_jwt_dispensador()`, `_jwt_prescritor()` são aceitos. Manter no próprio arquivo de teste (não criar fixtures globais — fora de escopo).

---

## §7 Verificação automatizada (antes do commit)

```bash
cd backend

# 1. Suíte focal nova
python3 -m pytest tests/integration/test_custodia_devolucao.py -v

# 2. Suíte da Etapa 4 (inclui test_ledger_helper.py — guarda central — P3 CODEX rodada 1)
python3 -m pytest tests/test_instance_id.py tests/test_ledger_helper.py \
                  tests/integration/test_4e_e2e_consolidado.py \
                  tests/integration/test_4d1_instance_id_ledger.py \
                  tests/integration/test_4d2_instance_id_ledger.py -v

# 3. Regressão de routers custódia
python3 -m pytest tests/test_dispensacao_atomizada.py tests/test_atomizacao.py -v

# 4. Grep — vocabulário canônico em código de produção apenas (P2 CODEX rodada 1 — restringir a app/)
grep -RnE "\"item_devolvido\"|'item_devolvido'" app/   # esperado: zero ocorrências em código

# 5. Grep — ator hardcoded
grep -nE "'dispensador',\s*'sistema'|\"dispensador\",\s*\"sistema\"" app/routers/custodia.py   # esperado: zero
```

---

## §8 Fora de escopo

**Não fazer** neste ticket:

- Auditar outros fluxos de devolução em `auth.py:devolver_prescritor` ou `hospitalares.py` — esses entram em ticket separado pós-Etapa 5 (`TICKET-COERENCIA-DEVOLUCOES.md`)
- Alterar `TRANSICOES_ITEM` em `states.py` — já está correto
- Alterar `DevolverItemIn` (schema do payload) — atual já é suficiente
- Adicionar novos campos a `prescricao_eventos.payload` além do que já existe (`item_id`, `nome_medicamento`, `devolvido_para`, `motivo`, `novo_status_item`)
- Mudar a forma como `custodia` ativa do item é encerrada (`_fechar_custodia_ativa`)
- Refatorar `_gravar_evento` interno
- **Modificar a cadeia estrutural de `prescricao_custodia` em devoluções** — reabertura de custódia paciente↔prescritor não é objeto deste ticket. Conforme nota em §1, isso fica para `TICKET-COERENCIA-DEVOLUCOES.md` pós-Etapa 5.

Qualquer divergência exige consulta ao Arquiteto antes de prosseguir.

---

## §9 Ciclo formal Regra 2 estrita

Etapas obrigatórias:

1. **Rodada 0 — Arquiteto redige** (este documento)
2. **Rodada 1 — CODEX revisa este ticket**
   - CODEX cola a revisão; Arquiteto classifica achados em §10 (P1 corrige no ticket; P2/P3 negocia)
3. **Rodada 2 — Arquiteto valida e libera para Code** (assinatura em §11)
4. **Rodada 3 — Code implementa** seguindo §4 + §6, em ramo `fix/custodia-devolver-vocabulario` ou direto em `main` se Fabiano preferir (decisão de fluxo, não de pacto)
5. **Rodada 4 — CODEX revisa pós-implementação**
   - Olha o diff real, valida que §5 (critérios de aceite) foi cumprido, classifica novos achados se houver
6. **Rodada 5 — Fabiano aprova + Code commita + Code pusha**

**Commit message canônico:**
```
fix(custodia): item_devolvido genérico vira item_devolvido_{paciente,prescritor}

- vocabulário canônico CLAUDE.md §2 (eventos separados)
- ator capturado do JWT (não hardcoded "sistema")
- docstring alinhada ao código real
- teste novo: tests/integration/test_custodia_devolucao.py (4 cenários)

Refs: TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md
CODEX P2-A confirmado em docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md
```

---

## §10 Adições Arquiteto (preenchido após cada rodada)

### §10.1 Rodada 0 (2026-05-21)

- Identificado defeito extra **não relatado pelo CODEX**: docstring linhas 582–583 mente sobre estados resultantes (afirma `cancelado`/`pendente`, código faz `devolvido_prescritor`/`devolvido_paciente`). Incluído em §4.3 e nos critérios de aceite §5.2 (#8).
- Confirmado via leitura direta que `_=Depends(...)` descarta o usuário (linha 578). Spec §4.1 corrige.
- Estimativa final: ~30 linhas produção + ~50 linhas teste = ~80 linhas, abaixo do limite de 100 linhas que dispararia obrigatoriedade da Regra 2. **Mantém Regra 2 estrita pelo critério de sensibilidade do escopo (custódia clínica), não por tamanho.**

### §10.2 Rodada 1 — CODEX (2026-05-21, integrada no mesmo dia)

CODEX retornou 9 achados (1 P1 + 5 P2 + 3 P3). Arquiteto classificou e integrou:

| # | Achado CODEX | Severidade | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | Rota errada `/custodia/...` (na verdade é `/prescricoes/...` via APIRouter prefix) | **P1** | ✅ Aceito | §5.1 #1–#2 corrigido (rota agora explicita confirmação via `custodia.py:34`) |
| 2 | C4 acoplamento por ordem de execução | P2 | ✅ Aceito | §6 reescrito: cada cenário monta próprio setup; C4 vira teste independente |
| 3 | C4 query global captura legado histórico | P2 | ✅ Aceito | §6.4 filtra eventos por `prescricao_id` criado no teste (mesmo padrão da C5 da 4E.1) |
| 4 | Greps `§3.3 / §5.2 #9 / §7` muito amplos | P2 | ✅ Aceito | Greps restritos a `app/` com literal exata; greps em `tests/` viraram informativos |
| 5 | C1–C3 não asseram forma da resposta HTTP | P2 | ✅ Aceito | §6.1–§6.3 agora asseram `status_code == 200` + shape do JSON |
| 6 | Tabela §1 parece prometer mudança em custódia estrutural | P2 | ✅ Aceito | Nota explícita em §1 + §8 reforçando escopo do ticket |
| 7 | `usuario.get("role")` / `.get("sub")` deveriam ser `["role"]`/`["sub"]` (acesso estrito) | P3 | ✅ Aceito | §4.2 usa acesso estrito (alinhado com `auth.py:269`) |
| 8 | Ref a `TRANSICOES_ITEM` como se fosse texto do CLAUDE.md | P3 | ✅ Aceito | §4.3 cita `CLAUDE.md §5b + domain/states.py::TRANSICOES_ITEM` |
| 9 | `test_ledger_helper.py` ausente da suíte de regressão | P3 | ✅ Aceito | §7 inclui `test_ledger_helper.py` |

**Veredito CODEX (literal):** "A spec captura corretamente o achado P2-A e a Regra 2 estrita está adequada pela sensibilidade auditável/custódia, mesmo abaixo de 100 linhas. Eu corrigiria o P1 da rota antes de liberar para o Code."

**Resultado:** 9 achados aceitos, zero rejeitados, zero adaptados. P1 corrigido. Ticket liberado para Code.

### §10.3 Rodada 4 — CODEX pós-implementação (2026-05-21)

**Material:** `git diff 9ff5131^..9ff5131 -- backend/app/routers/custodia.py backend/tests/integration/test_custodia_devolucao.py`
**Modo:** revisão estática (CODEX não rodou pytest).
**Veredito literal:** "Zero P1. Liberado para push."

CODEX retornou 2 achados P2, ambos em arquivo de teste (não tocam produção):

| # | Achado CODEX | Severidade | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | C3 (`test_custodia_devolucao.py:272`) não valida shape completo da resposta nem confirma `prescricao_itens.status_item` no banco — faltam `item_id`, `nome_medicamento`, `status_prescricao` + assert de domínio | P2 | ✅ Aceito | Asserts adicionados em `test_custodia_devolucao.py:272-288`: shape completo (5 chaves) + SELECT `status_item` no banco |
| 2 | C4 (`test_custodia_devolucao.py:304`) só confere `status_code` — faltam shape JSON de r1/r2 e estado de domínio dos dois itens | P2 | ✅ Aceito | Asserts adicionados em `test_custodia_devolucao.py:317-345`: shape de body1/body2 (4 chaves cada) + SELECT `id, status_item` validando os 2 itens |

**Respostas focais confirmadas pelo CODEX:**
1. **Vocabulário:** ramo `tipo_evento` cobre exclusivamente os dois eventos canônicos. Não há caminho de produção gravando `item_devolvido` genérico.
2. **Ator JWT:** acesso estrito (`usuario["role"]`/`["sub"]`) falha cedo (KeyError no `sub`; 403 no `role` via `require_role.get()`). Rollback da transação preserva integridade — sem fallback para `"sistema"`.
3. **`instance_id` e shape da resposta:** preservados.
4. **Escopo:** respeitado (só `custodia.py` + `test_custodia_devolucao.py`).
5. **Docstring:** corresponde ao comportamento real.
6. **Regressão latente:** zero consumer interno em `backend/app` filtrando pelo evento genérico.

**Verificação pytest (executada por Fabiano após aplicar os P2):**
- Bloco 1 (`test_custodia_devolucao.py`): **4 passed** em 3.77s
- Bloco 2 (regressão Etapa 4 — 5 arquivos): **59 passed** em 3.33s
- Bloco 3 (regressão custódia/dispensação): **60 passed** em 2.11s
- Total: **123 passed, 0 failed**

**Resultado:** 2 P2 aceitos e aplicados antes do push. Zero achados pendentes. Suíte completa verde. Liberado para push (amend ao `9ff5131`).

---

## §11 Status de aprovação

| Quem | Status | Data |
|---|---|---|
| Arquiteto rodada 0 | ✅ Escrito | 2026-05-21 |
| CODEX rodada 1 | ✅ Concluído (9 achados, todos aceitos) | 2026-05-21 |
| Arquiteto integra rodada 1 | ✅ Concluído (P1 corrigido + 5 P2 + 3 P3 aplicados em §10.2) | 2026-05-21 |
| Code implementa | ✅ Concluído (commit 9ff5131 + amend com asserts P2) | 2026-05-21 |
| CODEX rodada 4 | ✅ Concluído (zero P1, 2 P2 aceitos e aplicados antes do push) | 2026-05-21 |
| Fabiano aprova final | ⏳ Pytest verde (123 passed), aguardando amend + push | 2026-05-21 |

---

## §12 Prompt para o Code

```markdown
Implementar TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.

Classificação: module (com toque em core — vocabulário de eventos).
Pacto: Regra 2 estrita.
Pós-rodada CODEX 1: ticket integrado, P1 corrigido. Liberado para implementação.

CONTEXTO
- Achado original: CODEX P2-A em docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md §3.1
- Diagnóstico: endpoint POST /prescricoes/{protocolo}/itens/{item_id}/devolver
  (custodia.py:577, prefix /prescricoes definido em custodia.py:34) tem 3 defeitos no
  evento gravado (linha 616): tipo_evento genérico, ator_tipo/ator_id hardcoded.
- Defeito extra encontrado pelo Arquiteto: docstring (linhas 582-583) mente sobre
  estados resultantes — corrigir junto.

ESCOPO
- Tocar: backend/app/routers/custodia.py (endpoint devolver_item linhas 577-630)
- Criar novo: backend/tests/integration/test_custodia_devolucao.py
- NÃO tocar: states.py, ledger.py, outros routers, schemas, frontend,
  _fechar_custodia_ativa, _gravar_evento, prescricao_custodia.

PASSO A PASSO (3 mudanças no código de produção)
1. Linha 578: trocar `_=Depends(require_role(...))` por `usuario=Depends(require_role(...))`
2. Linha 616: substituir a chamada _gravar_evento conforme §4.2 do ticket:
   - tipo_evento computado conforme payload.para
   - ator_tipo = usuario["role"]    (acesso estrito, sem .get)
   - ator_id   = usuario["sub"]     (acesso estrito, sem .get)
3. Linhas 580-583: substituir docstring conforme §4.3 do ticket

TESTES (novo arquivo) — §6 do ticket
- C1 — Devolução paciente (status_code, shape resposta, estado item, ledger filtrado)
- C2 — Devolução prescritor
- C3 — Ator = prescritor (JWT do prescritor)
- C4 — Regressão de vocabulário (próprio setup, próprio prescricao_id; não depende de C1-C3)
- Helpers locais permitidos no próprio arquivo (não criar fixtures globais)

VERIFICAÇÃO ANTES DO COMMIT (§7 do ticket)
1. pytest tests/integration/test_custodia_devolucao.py -v        # novo arquivo verde
2. pytest tests/test_instance_id.py tests/test_ledger_helper.py
        tests/integration/test_4e_e2e_consolidado.py
        tests/integration/test_4d1_instance_id_ledger.py
        tests/integration/test_4d2_instance_id_ledger.py -v       # regressão Etapa 4
3. pytest tests/test_dispensacao_atomizada.py tests/test_atomizacao.py -v   # regressão custódia
4. grep -RnE "\"item_devolvido\"|'item_devolvido'" app/           # esperado: ZERO em código
5. grep -nE "'dispensador',\s*'sistema'|\"dispensador\",\s*\"sistema\"" app/routers/custodia.py
                                                                  # esperado: ZERO

COMMIT MESSAGE CANÔNICO
fix(custodia): item_devolvido genérico vira item_devolvido_{paciente,prescritor}

- vocabulário canônico CLAUDE.md §2 (eventos separados)
- ator capturado do JWT (não hardcoded "sistema")
- docstring alinhada ao código real
- teste novo: tests/integration/test_custodia_devolucao.py (4 cenários)

Refs: TICKET-4E-2-FIX-CUSTODIA-DEVOLUCAO.md
CODEX P2-A confirmado em docs/revisoes/CODEX-4E-2-relatorio-2026-05-21.md §3.1
CODEX rodada 1 sobre ticket integrada em §10.2 (P1 rota corrigido + 5 P2 + 3 P3)

PÓS-COMMIT
- Aguardar CODEX rodada 4 (revisão pós-implementação) antes do push para main
- Fabiano aprova final
- Após approve, push e atualizar §11 status para finalizado
```

