# TICKET 5A — Falhar explicitamente entrega digital solicitada sem carteira do paciente

> **Classe (CLAUDE.md §10):** `module` — toque em endpoints clínicos centrais (prescrição e pedido de exame). Não muda ledger nem máquina de estados; muda contrato de erro.
> **Pacto:** Regra 2 estrita (>100 linhas previstas, `module`)
> **Data:** 2026-05-22
> **Origem:** `docs/PLANO-PRODUCAO-V2.md §5A` (Fix B1 histórico), revisão Z AI 2026-05-05. Decisão de escopo (cobrir prescrição **e** pedido de exame no mesmo ciclo) e correção semântica da mensagem (`emitida mas não entregue` → `emissão rejeitada`) aprovadas por Fabiano em 2026-05-22.
> **Predecessor:** Etapa 4 fechada (`f72936d`), 5D fechado (`6ff6910`), fix CNES em curso (cluster pré-existente vermelho não bloqueia este ticket — seleção focal de testes verde).
> **Sucessor:** 5C (testes mínimos de autorização), depois encerramento da Etapa 5.
> **Redigido por:** Arquiteto (rodada 0). Aguarda revisão CODEX (rodada 1) antes de passar ao Code.

---

## §1 Contexto regulatório

Toda prescrição ou pedido de exame emitido digitalmente deve ter destino rastreável. A `RDC 1.000/2025` (Anvisa) e o princípio `CLAUDE.md §3` ("backend é fonte de verdade — nunca confiar no frontend para afirmações de estado") exigem que a intenção declarada pelo prescritor — entregar o objeto sanitário à carteira digital do paciente — só seja registrada como tal quando o backend efetivamente conseguir realizar a entrega.

Hoje, quando o prescritor declara `enviar_ao_paciente=true` mas o paciente ainda não possui cadastro (e portanto não tem carteira digital disponível no modelo atual), o backend:

1. Cria silenciosamente um paciente novo (linha 297–303 de `prescricoes.py`);
2. Emite a prescrição/pedido normalmente;
3. **Não cria a custódia da carteira digital**, porque `paciente_existia=False`;
4. Devolve `entregue_carteira: false` no payload, junto de status 200.

O frontend recebe 200 e não tem como distinguir "entrega concluída" de "entrega solicitada mas não realizada". A intenção do prescritor é perdida — silêncio que vira dívida regulatória.

A diretriz aprovada para o fix é a **rejeição explícita**: se a entrega digital foi solicitada e não pode ser realizada, a emissão como um todo é rejeitada com `HTTP 422`. O prescritor decide conscientemente: (a) re-emitir com `enviar_ao_paciente=false`; ou (b) cadastrar/vincular o paciente primeiro.

## §2 Achado — código atual

### §2.1 `prescricoes.py`

```python
# linha 292-307 — determinação de paciente_existia
paciente_antes = conn.execute(
    "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
).fetchone()
paciente_existia = paciente_antes is not None

conn.execute(
    """INSERT OR IGNORE INTO pacientes (cpf, nome, ativo, created_at, updated_at)
       VALUES (?, ?, true, ?, ?)""",
    (cpf, nome, agora, agora),
)
# … paciente novo é criado mesmo se enviar_ao_paciente=true e paciente_existia=False
```

```python
# linha 549-594 — bloco da carteira digital
entregue_carteira = False
status_final = "pendente"

if payload.enviar_ao_paciente and paciente_existia:
    # cria custódia prescritor→paciente
    # avança status para 'transferida_paciente'
    # registra evento custodia_transferida
    entregue_carteira = True
    status_final = "transferida_paciente"

# senão: silêncio
```

### §2.2 `pedidos_exame.py`

```python
# linha 320-362 — bloco da carteira digital
entregue_carteira = False

if payload.enviar_ao_paciente and paciente_existia:
    # cria custódia em pedido_exame_custodia
    # registra evento custodia_transferida
    entregue_carteira = True

# senão: silêncio; status permanece 'emitido'
```

Padrão idêntico nos dois routers. Difere apenas no destino da custódia (`prescricao_custodia` vs `pedido_exame_custodia`) e em que `pedidos_exame` não tem estado `transferida_paciente` (exceção documentada na linha 324-325 do router).

## §3 Decisões semânticas

### §3.1 Inferência "paciente sem carteira digital"

No modelo atual, considera-se que **um paciente tem carteira digital disponível** se e somente se já existe registro em `pacientes` no momento da emissão. Essa inferência é uma simplificação — não há campo dedicado `paciente.carteira_ativa`. Quando o modelo de carteira digital evoluir (autenticação, vínculo verificável), a definição pode mudar e este ticket precisará ser revisitado.

**Dívida semântica explícita (P2 CODEX rodada 1, 2026-05-22):** um paciente pode ter sido auto-cadastrado em emissão anterior com `enviar_ao_paciente=false`. No modelo atual ele passa a contar como "com carteira" em emissões subsequentes, ainda que nunca tenha autenticado ou estabelecido vínculo verificável. Ou seja: o critério "tem linha em `pacientes`" prova existência de cadastro mínimo, **não prova carteira digital real**. Esta dívida é aceitável para 5A, mas deve ser fechada antes do projeto vender "carteira digital" como funcionalidade — preferencialmente via campo dedicado ou tabela `carteiras_digitais` com prova de vínculo (Dívida B-Carteira, a registrar).

| Plano | Linguagem |
|---|---|
| Produto / mensagem ao usuário | "paciente sem carteira digital disponível" |
| Critério técnico interno | `paciente_existia == False` no momento da emissão |
| Código de erro estável | `patient_no_digital_wallet` |

A separação é deliberada para que o frontend não acoplemos a inferência temporária à camada de UX.

### §3.2 Semântica do 422 — rejeição, não aviso

`HTTP 422 patient_no_digital_wallet` significa **emissão rejeitada**. Ao receber esse erro:

- A prescrição ou pedido **não foi criado** no banco. `conn.rollback()` reverte tudo.
- O paciente novo **não foi auto-cadastrado**. O `INSERT OR IGNORE` em `pacientes` é executado depois do check (ver §4.1) ou revertido junto.
- O frontend deve oferecer ao prescritor: (a) re-emitir com `enviar_ao_paciente=false`; ou (b) cancelar e vincular/cadastrar o paciente antes de tentar novamente.

A mensagem **não deve** dizer "prescrição emitida mas não entregue". O plano original (`docs/PLANO-PRODUCAO-V2.md §5A`) carrega essa formulação; este ticket o corrige.

### §3.3 Posição do check no fluxo

O check vai **logo após** a determinação de `paciente_existia` e **antes** da criação/localização do paciente (linha 297 de `prescricoes.py` via `INSERT OR IGNORE`, linha 258 de `pedidos_exame.py` via helper `_localizar_ou_criar_paciente`). Vantagens:

- Nenhum paciente novo é criado pelo caminho rejeitado. O rollback ainda cobre inserts anteriores ao check — em particular o **auto-registro do prescritor** (`prescricoes.py` linhas 247-271 cria prescritor por CNS quando não existe; `pedidos_exame.py` linha 243 chama `_localizar_ou_criar_prescritor`). Esses INSERTs ficam revertidos pelo `conn.rollback()` no `except HTTPException`.
- Teste mais determinístico: contagem de linhas em `pacientes` permanece igual entre antes e depois da requisição rejeitada.
- Independente da camada de validação de carteira evoluir, o ponto do check fica estável.

## §4 Especificação do fix

### §4.1 `prescricoes.py` (alvo: linhas 292-307)

Inserir, imediatamente após a determinação de `paciente_existia` e **antes** do `INSERT OR IGNORE INTO pacientes`:

```python
paciente_antes = conn.execute(
    "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
).fetchone()
paciente_existia = paciente_antes is not None

# 5A — entrega digital solicitada sem carteira disponível
# (ver TICKET-5A-CARTEIRA-DIGITAL-422.md §3.1 — "paciente_existia=False"
# é a inferência atual para "sem carteira digital"; modelo pode evoluir.)
if payload.enviar_ao_paciente and not paciente_existia:
    raise HTTPException(
        status_code=422,
        detail={
            "codigo": "patient_no_digital_wallet",
            "mensagem": (
                "Paciente sem carteira digital disponível. "
                "Emissão rejeitada porque a entrega digital solicitada não é possível. "
                "Reemita com enviar_ao_paciente=false ou cadastre o paciente antes."
            ),
        },
    )

conn.execute(
    """INSERT OR IGNORE INTO pacientes ...""",
    ...
)
```

**Importante:** o bloco existente `if payload.enviar_ao_paciente and paciente_existia:` (linha 558) **não muda**. Continua intacto. O check de §4.1 simplesmente garante que esse bloco nunca é alcançado pelo caminho silencioso — ou paciente existia (entra), ou 422 dispara antes.

**Convenções de payload (P2 CODEX rodada 1):**
- Chaves em português (`codigo`, `mensagem`) — alinha ao padrão estabelecido do projeto (`main.py:147`, `assinaturas.py:131,187`, `icp_identity.py:487+`, `prescricoes.py:639-640`, `auth.py:77`).
- `patient_id` **removido** do payload. Justificativa: frontend já sabe o CPF que enviou, e ecoar CPF em response/log aumenta superfície LGPD.

### §4.2 `pedidos_exame.py` (alvo: linhas 255-258)

Estrutura do código real:

```python
# Linha 255-258 do pedidos_exame.py (estado atual):
_pac_row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
paciente_existia = _pac_row is not None
paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)
```

Inserir o check **entre** a linha 257 (`paciente_existia = _pac_row is not None`) e a linha 258 (`paciente_id = _localizar_ou_criar_paciente(...)`):

```python
_pac_row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
paciente_existia = _pac_row is not None

# 5A — entrega digital solicitada sem carteira disponível
if payload.enviar_ao_paciente and not paciente_existia:
    raise HTTPException(
        status_code=422,
        detail={
            "codigo": "patient_no_digital_wallet",
            "mensagem": (
                "Paciente sem carteira digital disponível. "
                "Emissão rejeitada porque a entrega digital solicitada não é possível. "
                "Reemita com enviar_ao_paciente=false ou cadastre o paciente antes."
            ),
        },
    )

paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)
```

A mensagem é **idêntica** à de `prescricoes.py` — mesmo `codigo`, mesma chave `mensagem`, mesmo texto. Não há divergência de contrato entre os dois endpoints do ponto de vista do consumidor.

**Observação técnica:** `pedidos_exame.py` usa o helper `_localizar_ou_criar_paciente` em vez de `INSERT OR IGNORE` inline (diferente de `prescricoes.py`). O check entra **antes** da chamada do helper para evitar criação do paciente novo no caminho rejeitado.

### §4.3 Anti-escopo de implementação

- **Não inventar novo estado** em pedido de exame. `pedidos_exame` continua devolvendo `status: emitido` quando entrega é bem-sucedida. Apenas o caminho de erro é novo.
- **Não tocar no bloco `if … and paciente_existia:`** (lógica de entrega bem-sucedida). É escopo zero.
- **Não acrescentar campo a `pacientes`** (carteira_ativa, ou similar). Inferência fica em `paciente_existia` até que B (modelagem definitiva) seja redigida.
- **Não alterar o payload do response 200** (`entregue_carteira`, `status_final`). Permanece como hoje.
- **Não tocar em emissão física** (`POST /prescricoes/fisica`, fluxo `encerrada_localmente`). Esse fluxo não tem `enviar_ao_paciente`.

## §5 Critérios de aceite

### §5.1 Testes obrigatórios — `prescricoes`

Em `backend/tests/test_prescricoes.py` (ou arquivo de teste do endpoint POST `/prescricoes`).

> **Nota sobre status codes (P1 CODEX rodada 1):** o endpoint declara `status_code=201` (linha 213 de `prescricoes.py`); o caminho de erro declara `status_code=422` no `raise HTTPException`. Os testes devem usar **201** para sucesso e **422** para rejeição.

1. **`test_prescricao_422_quando_enviar_ao_paciente_sem_carteira`**
   - Setup: paciente com CPF nunca cadastrado (limpar `pacientes` se necessário, ou usar CPF novo).
   - Request: POST `/prescricoes` com `enviar_ao_paciente=true`, paciente novo, itens válidos, prescritor válido.
   - Asserts (contrato HTTP):
     - `response.status_code == 422`
     - `response.json()["detail"]["codigo"] == "patient_no_digital_wallet"`
     - `"carteira digital" in response.json()["detail"]["mensagem"]`
     - `"patient_id" not in response.json()["detail"]` (CPF não ecoa)
   - Asserts (rollback efetivo — P2 CODEX rodada 1):
     - `SELECT COUNT(*) FROM prescricoes p JOIN pacientes pa ON pa.id = p.paciente_id WHERE pa.cpf = ?` retorna 0
     - `SELECT COUNT(*) FROM pacientes WHERE cpf = ?` retorna 0 (paciente novo não auto-criado)
     - `SELECT COUNT(*) FROM prescricao_eventos` igual ao baseline pré-requisição
     - `SELECT COUNT(*) FROM prescricao_custodia` igual ao baseline pré-requisição
     - `SELECT COUNT(*) FROM eventos_publicacao` (outbox) igual ao baseline pré-requisição

2. **`test_prescricao_201_quando_enviar_ao_paciente_com_carteira`**
   - Setup: paciente já cadastrado em `pacientes`.
   - Request: POST `/prescricoes` com `enviar_ao_paciente=true`.
   - Asserts:
     - `response.status_code == 201`
     - `response.json()["entregue_carteira"] is True`
     - `response.json()["status"] == "transferida_paciente"`
     - `SELECT COUNT(*) FROM prescricao_custodia ... WHERE detentor_tipo = 'paciente'` retorna 1 (entrega registrada)
     - `SELECT COUNT(*) FROM prescricao_eventos WHERE tipo_evento = 'custodia_transferida'` aumentou em 1

3. **`test_prescricao_201_quando_nao_enviar_ao_paciente_sem_carteira`**
   - Setup: paciente nunca cadastrado.
   - Request: POST `/prescricoes` com `enviar_ao_paciente=false`.
   - Asserts:
     - `response.status_code == 201`
     - `response.json()["entregue_carteira"] is False`
     - `response.json()["status"] == "pendente"`
     - paciente novo foi criado (linha 297-303 continua executando neste caminho)

### §5.2 Testes obrigatórios — `pedidos_exame`

Em `backend/tests/test_pedidos_exame.py` (ou equivalente).

> **Nota sobre status codes:** análogo a §5.1 — `status_code=201` no endpoint (linha 210 de `pedidos_exame.py`).

4. **`test_pedido_exame_422_quando_enviar_ao_paciente_sem_carteira`** — espelho de §5.1.1.
   - Mesmo contrato HTTP (422 + payload `{codigo, mensagem}` sem `patient_id`).
   - Asserts de rollback adaptados:
     - `SELECT COUNT(*) FROM pedidos_exame pe JOIN pacientes pa ON pa.id = pe.paciente_id WHERE pa.cpf = ?` retorna 0
     - `SELECT COUNT(*) FROM pacientes WHERE cpf = ?` retorna 0
     - `SELECT COUNT(*) FROM pedido_exame_eventos` igual ao baseline
     - `SELECT COUNT(*) FROM pedido_exame_custodia` igual ao baseline
     - `SELECT COUNT(*) FROM eventos_publicacao` igual ao baseline

5. **`test_pedido_exame_201_quando_enviar_ao_paciente_com_carteira`** — espelho de §5.1.2.
   - `response.status_code == 201`
   - `response.json()["entregue_carteira"] is True`
   - `response.json()["status"] == "emitido"` (pedido_exame não tem `transferida_paciente` — exceção documentada na linha 324-325 do router)
   - `SELECT COUNT(*) FROM pedido_exame_custodia ... WHERE para = 'paciente'` retorna 1
   - `SELECT COUNT(*) FROM pedido_exame_eventos WHERE tipo_evento = 'custodia_transferida'` aumentou em 1

6. **`test_pedido_exame_201_quando_nao_enviar_ao_paciente_sem_carteira`** — espelho de §5.1.3.
   - `response.status_code == 201`
   - `response.json()["entregue_carteira"] is False`
   - `response.json()["status"] == "emitido"`
   - paciente novo auto-criado.

### §5.3 Critérios não-funcionais

- Mensagem da chave `mensagem` deve ser idêntica nos dois endpoints (acoplamento explícito ao código de erro `patient_no_digital_wallet`).
- O literal `"patient_no_digital_wallet"` aparece direto no `raise HTTPException` em ambos os routers — sem constante comum em módulo separado (lapidação P3 CODEX rodada 1: a sugestão de constante comum foi removida para alinhar com a verificação automatizada §6, que faz grep pelo literal).

## §6 Verificação automatizada

Pré-implementação (Code grep antes de codificar):

```bash
grep -n "enviar_ao_paciente and paciente_existia" backend/app/routers/prescricoes.py
grep -n "enviar_ao_paciente and paciente_existia" backend/app/routers/pedidos_exame.py
```

Esperado: 1 match cada. Se mais que 1, mapear e ajustar o spec antes.

Pós-implementação — literal espalhado nos 2 routers (ver §5.3, decisão P3 CODEX):

```bash
grep -rn "patient_no_digital_wallet" backend/app/routers/
# Esperado: 2 matches — 1 em prescricoes.py, 1 em pedidos_exame.py.
# Se houver match em backend/app/domain/ ou outro módulo, foi criada constante
# comum (não é desejado por §5.3) — investigar.
```

Pós-implementação — confirmar que o payload do erro NÃO ecoa CPF:

```bash
grep -A 10 "patient_no_digital_wallet" backend/app/routers/prescricoes.py | grep -i "cpf\|patient_id"
grep -A 10 "patient_no_digital_wallet" backend/app/routers/pedidos_exame.py | grep -i "cpf\|patient_id"
# Esperado: zero matches em ambos. Se houver, CPF ainda está sendo ecoado.
```

Suite focal:

```bash
cd backend
pytest tests/test_prescricoes.py -v -k "carteira or wallet"
pytest tests/test_pedidos_exame.py -v -k "carteira or wallet"
```

Suite completa para detectar regressão:

```bash
pytest -q
```

Esperado: nenhuma falha nova além das pré-existentes (cluster outbox Dívida 1, CPF-shift novo achado #35, e qualquer remanescente das 44 atuais não diagnosticadas).

## §7 Anti-escopo

- Não criar campo `paciente.carteira_ativa` nem nova tabela `carteiras_digitais`.
- Não alterar lógica de emissão física (`POST /prescricoes/fisica`).
- Não alterar máquina de estados (`domain/states.py`).
- Não alterar vocabulário do ledger.
- Não alterar handler de exceção genérico (`except Exception` em prescricoes.py:629).
- Não criar ticket separado para pedidos de exame (decisão de escopo aprovada em 2026-05-22).
- Não corrigir cluster outbox (Dívida 1, ticket #31 — separado).
- Não corrigir cluster CNES (em curso no Code paralelamente — ticket #30).

## §8 Predecessoras e classe

- Predecessor processual: 5D fechado (`6ff6910` — guard JWT_SECRET).
- Predecessor logístico: fix CNES (ticket #30) — não bloqueia este ticket porque os testes desse cluster operam sobre routers diferentes (`cnes_prescritor`), mas a suite completa só ficará 100% verde após o cluster CNES estar fechado.
- Classe `module`: muda contrato HTTP de dois endpoints centrais. Não toca `core` (ledger, custódia, estados, vocabulário).
- Volume previsto: ~50 linhas de fix + ~200 linhas de teste = ~250 linhas → Regra 2 estrita aplica.

## §9 Prompt sugerido ao Code (rodada de implementação)

> Será inserido **após** a rodada CODEX e a integração das observações (rodada 1 → §10 abaixo). Não enviar ao Code antes.

---

## §10 Observações CODEX rodada 1 (2026-05-22) — integradas

CODEX revisou a rodada 0 deste ticket contra o repo real em `/Users/fabianotonacoborges/PicSaude_Dev`. Retornou **2 P1**, **4 P2**, **2 P3**. Avaliação central do CODEX: "o desenho central está bom — 422 como rejeição com rollback faz sentido; não trocaria para 409/400".

Todos os achados foram **validados contra o código real** antes de integração. Status:

| # | Severidade | Achado | Decisão | Aplicado em |
|---|---|---|---|---|
| 1 | P1 | Queries de rollback usavam coluna inexistente (`cpf_paciente` não existe; tabelas têm `paciente_id` FK) | ✅ Aceito | §5.1.1 e §5.2.4 — join via `paciente_id` |
| 2 | P1 | Status de sucesso é `201`, não `200` (ambos endpoints declaram `status_code=201`) | ✅ Aceito | §5.1.2, §5.1.3, §5.2.5, §5.2.6 — asserts ajustados; nota explícita em §5.1 |
| 3 | P2 | `patient_id` ecoava CPF no payload do erro (LGPD); chave `message` em inglês destoa de `mensagem` (padrão do projeto) | ✅ Aceito integral | §4.1 e §4.2 — `patient_id` removido; chave virou `mensagem`; nota com referências do padrão |
| 4 | P2 | §4.2 citava `INSERT OR IGNORE` mas `pedidos_exame.py` usa helper `_localizar_ou_criar_paciente` | ✅ Aceito | §4.2 reescrita com código literal real |
| 5 | P2 | Rollback deveria cobrir efeitos regulatórios adjacentes (ledger, outbox, custódia) | ✅ Aceito | §5.1.1 e §5.2.4 — asserts adicionais de baseline pré-requisição para `_eventos`, `_custodia`, `eventos_publicacao` |
| 6 | P2 | Inferência `paciente_existia=True` aceita "paciente sem carteira real" (auto-criado em emissão anterior com `enviar_ao_paciente=false`) | ✅ Aceito | §3.1 — nota de dívida semântica explícita; abre Dívida B-Carteira (task #36) |
| 7 | P3 | Constante comum vs grep literal em §6 — conflito menor | ✅ Aceito | §5.3 — removida sugestão de constante comum; §6 confirma 2 matches do literal |
| 8 | P3 | "Nenhum INSERT precisa rollback" impreciso (prescritor pode ser inserido antes do check) | ✅ Aceito | §3.3 reescrita reconhecendo o auto-registro do prescritor |

**Zero achados nas lentes restantes** (CODEX confirmou):
- Status code: 422 adequado; 400 seria genérico demais, 409 defensável mas menos alinhado ao padrão atual de validação semântica do projeto.
- Outros endpoints com padrão silencioso: grep retornou apenas os 2 routers mapeados (`prescricoes.py` e `pedidos_exame.py`).
- Anti-escopo §7: bem desenhado.
- CNES/outbox/CPF-shift: não bloqueiam 5A, desde que a verificação final declare falhas pré-existentes separadamente.

## §11 Status final — fechado em `e09dc3e` + `66547e4` (2026-05-22)

### §11.1 Implementação

Code entregou em commit `e09dc3e` (push em main; HEAD após docs `66547e4`).

| Artefato | Onde |
|---|---|
| Guard 422 prescricoes | `backend/app/routers/prescricoes.py` linhas 299-313 |
| Guard 422 pedidos_exame | `backend/app/routers/pedidos_exame.py` linhas 259-273 |
| 3 testes prescricoes | `backend/tests/integration/test_prescricoes.py` |
| 3 testes pedidos_exame | `backend/tests/integration/test_pedidos_exame.py` |

### §11.2 Resultados de teste

- Suite focal: **6/6 verdes**
- Suite focal estendida (Code + outros testes do arquivo): **11 passed**
- Suite completa: **1228 passed / 27 failed** — sem regressão (27 falhas pré-existentes diagnosticadas em clusters: CPF-shift, catálogo regulatório, health, g4b auth eventos, órfão auth_paciente)

### §11.3 CODEX rodada 2 (revisão pós-implementação)

| Severidade | # | Achado | Decisão |
|---|---|---|---|
| P1 | — | Zero | — |
| P2 | 1 | Assert do rollback do prescritor auto-criado não está nos testes (rollback funciona, mas teste não cobre) | Follow-up — task #43 |
| P2 | 2 | CPF inválido + `enviar_ao_paciente=true` cai em `patient_no_digital_wallet` (não há validator geral de CPF nos schemas; só `normalize_cpf` que remove não dígitos) | Não é regressão do 5A; ticket próprio — task #44 |
| P3 | 3 | Testes da mensagem usam `in` em vez de igualdade exata — não protegem drift futuro | Lapidação aceita; pode ser feita junto com P2 #1 ou ficar como issue |
| P3 | 4 | Comentário em `prescricoes.py:288` sobre concorrência `INSERT OR IGNORE` ficou amplo demais (o guard 5A já rejeita antes do INSERT em `enviar_ao_paciente=true`) | Lapidação cosmética; ajustar quando tocar o arquivo a próxima vez |

**Confirmações do CODEX rodada 2:**
- Guard no ponto exato: antes do INSERT/helper de paciente.
- Payload correto: `codigo` + `mensagem`, sem `patient_id`.
- Rollback efetivo: `except HTTPException: conn.rollback(); raise` em prescricoes; `with get_tx()` em pedidos_exame.
- Mensagem byte-a-byte idêntica nos 2 routers.
- Anti-regressão confirmada — clusters restantes não são causados pelo 5A.

### §11.4 Tickets/dívidas abertas pelo ciclo 5A

| # | Origem | Quando |
|---|---|---|
| #36 | P2 CODEX rodada 1 | Dívida B-Carteira — modelagem definitiva da carteira digital |
| #43 | P2 CODEX rodada 2 | Follow-up — teste rollback do prescritor auto-criado no caminho 422 |
| #44 | P2 CODEX rodada 2 | Validator geral de CPF nos schemas (ortogonal ao 5A; afeta semântica de mensagens de erro) |

### §11.5 Trilha de auditoria final do 5A

```
2026-05-22 (rodada 0) — Arquiteto redige ticket
2026-05-22 (rodada 1) — CODEX revisa spec: 2 P1 + 4 P2 + 2 P3 → integrados em §10
2026-05-22 (impl)     — Code implementa em e09dc3e: 6/6 verdes focal
2026-05-22 (rodada 2) — CODEX revisa código: zero P1, 2 P2, 2 P3 → §11.3
2026-05-22 (fechamento) — ticket fechado; §11 preenchido; tickets follow-up abertos
```

5A **CLOSED**.

## §12 Prompt final ao Code

Pronto para implementação (CODEX rodada 1 integrada; §10 fechado).

````
Tarefa: TICKET-5A — Falhar explicitamente entrega digital solicitada sem
carteira do paciente. Classe: module. Pacto: Regra 2 estrita (ticket formal
já redigido e revisado por CODEX rodada 1 em 2026-05-22).

LOCAL DO TICKET
───────────────
backend/docs/tickets/TICKET-5A-CARTEIRA-DIGITAL-422.md

LEIA O TICKET INTEIRO antes de implementar — em particular §3 (decisões
semânticas), §4 (especificação técnica), §5 (testes obrigatórios) e §10
(observações CODEX integradas, 8 achados — todos já aplicados no ticket).

CONTEXTO REGULATÓRIO (§1)
─────────────────────────
RDC 1.000/2025 e CLAUDE.md §3 exigem que a intenção declarada pelo prescritor
(`enviar_ao_paciente=true`) só seja registrada como entrega quando o backend
efetivamente conseguir realizar a entrega digital. Hoje há silêncio: paciente
novo é auto-criado, prescrição/pedido é emitido com status 200, e
`entregue_carteira=false` no payload. Frontend não tem como distinguir
"entrega concluída" de "entrega solicitada mas não realizada".

Fix: 422 com rollback. Operação é rejeitada por completo. Frontend exibe
escolha consciente.

ESCOPO
──────
TOCAR:
  - backend/app/routers/prescricoes.py (inserir check entre linhas 295-297)
  - backend/app/routers/pedidos_exame.py (inserir check entre linhas 257-258)
  - backend/tests/test_prescricoes.py (ou arquivo equivalente — verificar
    convenção do projeto antes; criar arquivo se necessário)
  - backend/tests/test_pedidos_exame.py (idem)

NÃO TOCAR:
  - O bloco existente `if payload.enviar_ao_paciente and paciente_existia:`
    em ambos os routers (lógica de entrega bem-sucedida — fora do escopo)
  - Máquina de estados (app/domain/states.py)
  - Vocabulário do ledger (CLAUDE.md §2)
  - Handler genérico `except Exception` em prescricoes.py:629
  - Modelo de Paciente (sem campo novo `carteira_ativa`)
  - Emissão física (POST /prescricoes/fisica)
  - Constante comum em módulo separado — literal direto no raise, sim,
    nos 2 routers (decisão P3 CODEX rodada 1, §5.3 do ticket)

VERIFICAÇÃO PRÉ-IMPLEMENTAÇÃO
────────────────────────────
Antes de codificar, grep para confirmar que o spec ainda bate com o código:

  grep -n "enviar_ao_paciente and paciente_existia" backend/app/routers/prescricoes.py
  grep -n "enviar_ao_paciente and paciente_existia" backend/app/routers/pedidos_exame.py

Esperado: 1 match cada. Se mais de 1, parar e reportar — o spec assume
exatamente 1 ponto silencioso por router.

ESPECIFICAÇÃO DO FIX (§4.1 / §4.2 do ticket)
────────────────────────────────────────────

(1) `backend/app/routers/prescricoes.py` — inserir entre linha 295 e 297,
    imediatamente após `paciente_existia = paciente_antes is not None` e
    antes de `conn.execute("""INSERT OR IGNORE INTO pacientes ...""")`:

    if payload.enviar_ao_paciente and not paciente_existia:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "patient_no_digital_wallet",
                "mensagem": (
                    "Paciente sem carteira digital disponível. "
                    "Emissão rejeitada porque a entrega digital solicitada não é possível. "
                    "Reemita com enviar_ao_paciente=false ou cadastre o paciente antes."
                ),
            },
        )

(2) `backend/app/routers/pedidos_exame.py` — inserir entre linha 257 e 258,
    imediatamente após `paciente_existia = _pac_row is not None` e antes
    de `paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)`:

    Mesma estrutura, mesma mensagem, mesmo código de erro. Literal idêntico.

CONVENÇÕES DE PAYLOAD (P2 CODEX integrado em §10)
─────────────────────────────────────────────────
- Chaves em português: `codigo` e `mensagem` (NÃO `code` / `message`).
  Padrão estabelecido em `main.py:147`, `assinaturas.py:131,187`,
  `icp_identity.py:487+`, `prescricoes.py:639-640`, `auth.py:77`.
- `patient_id` NÃO entra no payload (decisão LGPD — frontend já sabe o CPF).
- Mensagem byte-a-byte idêntica nos 2 routers (testes vão fazer assert por
  substring `"carteira digital"`).

TESTES OBRIGATÓRIOS (§5.1 e §5.2 do ticket — 6 cenários)
────────────────────────────────────────────────────────
3 testes para prescricoes + 3 testes para pedidos_exame, simétricos.

Para CADA endpoint:
- 422 quando enviar_ao_paciente=true e paciente novo
- 201 quando enviar_ao_paciente=true e paciente cadastrado (entrega ocorre)
- 201 quando enviar_ao_paciente=false e paciente novo (auto-cria, sem entrega)

ATENÇÃO aos asserts críticos:
- Status code de SUCESSO é 201 (não 200) — endpoints declaram `status_code=201`
- Payload de erro: chaves `codigo`/`mensagem`, sem `patient_id`
- Rollback efetivo (no caso 422):
    SELECT COUNT(*) FROM prescricoes p JOIN pacientes pa ON pa.id = p.paciente_id WHERE pa.cpf = ?  → 0
    SELECT COUNT(*) FROM pacientes WHERE cpf = ?  → 0
    SELECT COUNT(*) FROM prescricao_eventos  → igual ao baseline pré-requisição
    SELECT COUNT(*) FROM prescricao_custodia  → igual ao baseline pré-requisição
    SELECT COUNT(*) FROM eventos_publicacao  → igual ao baseline pré-requisição
  (e equivalente para pedido_exame_eventos / pedido_exame_custodia em §5.2)

Os asserts de baseline (`igual ao baseline pré-requisição`) implicam capturar
COUNT antes da requisição e comparar depois — protege contra refactor futuro
que mova o check para depois de evento/outbox.

Convenção de nome dos testes (sugestão):
  test_prescricao_422_quando_enviar_ao_paciente_sem_carteira
  test_prescricao_201_quando_enviar_ao_paciente_com_carteira
  test_prescricao_201_quando_nao_enviar_ao_paciente_sem_carteira
  test_pedido_exame_422_quando_enviar_ao_paciente_sem_carteira
  test_pedido_exame_201_quando_enviar_ao_paciente_com_carteira
  test_pedido_exame_201_quando_nao_enviar_ao_paciente_sem_carteira

VERIFICAÇÃO PÓS-IMPLEMENTAÇÃO (§6 do ticket)
────────────────────────────────────────────

(1) Literal espalhado nos 2 routers (não centralizado):
    grep -rn "patient_no_digital_wallet" backend/app/routers/
    Esperado: 2 matches (1 em prescricoes.py, 1 em pedidos_exame.py).
    Se houver match em backend/app/domain/, foi criada constante comum
    indevidamente (§5.3 proíbe).

(2) Payload NÃO ecoa CPF:
    grep -A 10 "patient_no_digital_wallet" backend/app/routers/prescricoes.py | grep -i "cpf\|patient_id"
    grep -A 10 "patient_no_digital_wallet" backend/app/routers/pedidos_exame.py | grep -i "cpf\|patient_id"
    Esperado: zero matches em ambos.

(3) Suite focal:
    cd backend
    pytest tests/test_prescricoes.py -v -k "carteira or wallet"
    pytest tests/test_pedidos_exame.py -v -k "carteira or wallet"
    Esperado: 6/6 verdes.

(4) Suite completa:
    pytest -q
    Esperado: nenhuma falha nova. Falhas pré-existentes (44 antes da
    implementação do 5A) devem permanecer ou reduzir — declare-as
    separadamente no relatório. Não tente consertar Dívida 1 (callers
    outbox), CPF-shift, nem demais clusters não diagnosticados — eles
    ficam para tickets próprios.

COMMITS ESPERADOS
─────────────────
Pode ser um único commit (preferido, mudança coesa) ou dois (fix + testes).

Sugestão de mensagem:

  feat(5a): rejeitar emissão quando entrega digital solicitada sem carteira

  POST /prescricoes e POST /pedidos_exame passam a retornar 422
  patient_no_digital_wallet quando enviar_ao_paciente=true e o paciente
  não tem registro prévio em pacientes (inferência atual de "sem carteira
  digital"). Operação é rejeitada com rollback efetivo — nenhuma prescrição/
  pedido criado, nenhum paciente auto-cadastrado.

  Fix B1 histórico (docs/PLANO-PRODUCAO-V2.md §5A). Ticket formal com 8
  achados CODEX integrados em backend/docs/tickets/TICKET-5A-CARTEIRA-DIGITAL-422.md.

  6 testes adicionados (3 prescricoes + 3 pedidos_exame) com asserts de
  rollback regulatório (ledger, outbox, custódia).

  Refs: docs/PLANO-PRODUCAO-V2.md §5A, CLAUDE.md §3, RDC 1.000/2025.

PREDECESSORAS
─────────────
- 5D fechado em 6ff6910
- Fix CNES fechado em 650edca
- HEAD do main após esses dois deve ser 650edca (a menos que tenha havido
  outro push entrementes — verificar `git log -5` antes de iniciar)

NÃO ESQUEÇA
───────────
- Ticket é a fonte de verdade. Em caso de dúvida, releia §3/§4/§5/§10.
- Chaves em português: codigo + mensagem (não code + message)
- Payload SEM patient_id
- Status code: 201 sucesso, 422 rejeição
- Asserts de rollback cobrem ledger + outbox + custódia, não só objeto clínico
- Não criar constante comum — literal nos 2 routers
- Reporte separadamente as falhas pré-existentes após pytest -q
````

---

> **Status do ticket (2026-05-22 — pronto para implementação):**
> Rodada 0 (Arquiteto) ✅
> CODEX rodada 1 (revisão de spec) ✅ — 8 achados integrados em §10
> Fabiano: aprovado ✅
> Code: aguarda implementação
> CODEX rodada 2 (pós-implementação) — pendente
