# PicSaúde — Núcleo de Objeto Sanitário

> **Status:** Contrato arquitetural ativo — v1.1
> **Baseado em:** prescrição (Tickets 1–13) + pedido de exame (Tickets 14–17) + laudo (Ticket 19 — validação do padrão)
> **v1.1:** `prescritor_id → autor_id`; parâmetro `tipo_agregacao_status` (seções 1 e 3)
> **Propósito:** Todo novo objeto sanitário deve satisfazer este contrato antes de ser implementado.

---

## Por que este documento existe

O PicSaúde demonstrou, na prática, que a mesma infraestrutura serve para objetos sanitários distintos. A prescrição e o pedido de exame foram projetados de forma independente e convergiram organicamente para o mesmo padrão arquitetural. Este documento cristaliza esse padrão **antes** que um terceiro objeto possa fazer o sistema divergir acidentalmente.

**Este documento é o CLAUDE.md do domínio.**

Regras de governança:
- Nenhum novo objeto sanitário deve ser implementado sem satisfazer este contrato.
- O vocabulário de domínio (medicamentos, exames, laudos) nunca deve ser generalizado — apenas a estrutura.
- Qualquer extensão ao contrato deve ser discutida antes de ser codificada.

---

## Mapa rápido

| Contrato | Seção |
|---|---|
| Objeto sanitário principal | 1 |
| Itens | 2 |
| Máquina de estados | 3 |
| Custódia | 4 |
| Ledger de eventos | 5 |
| Documento canônico + hash | 6 |
| PDF institucional | 7 |
| QR Code + validação pública | 8 |
| Emissão física | 9 |
| O que NÃO abstrair | 10 |
| Checklist para novo objeto | 11 |

---

## 1. Contrato — Objeto Sanitário Principal

Todo objeto sanitário deve ter uma tabela principal com este esquema mínimo:

```sql
CREATE TABLE {objeto}s (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    protocolo           TEXT UNIQUE NOT NULL,   -- UUID, identidade pública
    autor_id            INTEGER REFERENCES prescritores(id),  -- autor do objeto sanitário
    paciente_id         INTEGER REFERENCES pacientes(id),
    status              TEXT NOT NULL,          -- máquina de estados (seção 3)
    tipo_emissao        TEXT NOT NULL,          -- novo | correcao | renovacao | fisico
    origem_id           INTEGER REFERENCES {objeto}s(id),  -- rastreabilidade
    data_emissao        TEXT NOT NULL,          -- ISO 8601 date (imutável após emissão)
    data_validade       TEXT,                   -- ISO 8601 date (NULL para físico)
    assinatura_hash     TEXT,                   -- SHA-256 do documento canônico
    criado_em           DATETIME DEFAULT (datetime('now'))
    -- + campos específicos do domínio (ver seção 10)
);
```

**Sobre `autor_id`:**
O campo `autor_id` referencia o **autor** do objeto sanitário — quem o produziu ou ordenou.
Para prescrições e pedidos de exame, o autor é o prescritor (médico). Para laudos, é o responsável técnico (patologista, bioquímico). A tabela `prescritores` serve como registro genérico de profissionais de saúde identificados por CNS. O alias semântico (`prescritor_id`) pode ser mantido em módulos específicos para clareza do domínio.

**Invariantes:**
- `protocolo` é gerado no backend com `uuid.uuid4()` — nunca pelo frontend
- `data_emissao` é imutável após INSERT — nunca recebe UPDATE
- `status` segue o `tipo_agregacao_status` do objeto (seção 3)
- `origem_id` é obrigatório quando `tipo_emissao` ≠ `'novo'`
- Objetos físicos usam `tipo_emissao = 'fisico'` e `data_validade = NULL`

---

## 2. Contrato — Itens

Todo objeto sanitário tem itens. Os itens são a **unidade operacional real**; o status do objeto é derivado dos status dos itens.

```sql
CREATE TABLE {objeto}_itens (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    {objeto}_id INTEGER NOT NULL REFERENCES {objeto}s(id),
    status_item TEXT NOT NULL,   -- máquina de estados do item (seção 3)
    quantidade  INTEGER NOT NULL DEFAULT 1,
    criado_em   DATETIME DEFAULT (datetime('now'))
    -- + campos específicos do domínio (ver seção 10)
);
```

**`tipo_agregacao_status` — como o status do objeto é calculado:**

| Valor | Quando usar | Exemplos |
|---|---|---|
| `por_itens` | Itens têm transições operacionais independentes | prescrição (dispensação por item), exame (coleta por item) |
| `direto` | Transições operam no nível do objeto inteiro | laudo (ciência, assinatura, liberação são do laudo todo) |

**Invariantes para `por_itens`:**
- O status do objeto NUNCA é setado diretamente — sempre via `derivar_status_{objeto}(status_itens)`
- Lógica: mais avançado dos itens ativos vence
- Itens terminais são ignorados no cálculo
- Se todos os itens estão em estados terminais: objeto → terminal correspondente

**Invariantes para `direto`:**
- O status do objeto é transitado explicitamente pelos endpoints de negócio
- `derivar_status_{objeto}()` não é necessária (pode ser omitida ou retornar o status atual)
- A exceção deve ser documentada explicitamente na arquitetura do módulo (ex: `docs/ARQUITETURA_LAUDO.md`)

---

## 3. Contrato — Máquina de Estados

Cada objeto sanitário define sua máquina de estados em `backend/app/domain/states_{objeto}.py`.

### Estrutura obrigatória do arquivo

```python
# Estados do objeto
ESTADOS_{OBJETO}: frozenset[str]
ESTADOS_TERMINAIS_{OBJETO}: frozenset[str]
TRANSICOES_{OBJETO}: dict[str, frozenset[str]]

# Estados do item
ESTADOS_ITEM_{OBJETO}: frozenset[str]
ESTADOS_TERMINAIS_ITEM_{OBJETO}: frozenset[str]
TRANSICOES_ITEM_{OBJETO}: dict[str, frozenset[str]]

# Vocabulário de eventos do ledger
EVENTOS_{OBJETO}: frozenset[str]

# Função de derivação (obrigatória)
def derivar_status_{objeto}(status_itens: list[str]) -> str: ...

# Helpers de validação (obrigatórios)
def transicao_valida_{objeto}(de: str, para: str) -> bool: ...
def transicao_valida_item_{objeto}(de: str, para: str) -> bool: ...
def eh_terminal_{objeto}(status: str) -> bool: ...
def eh_terminal_item_{objeto}(status: str) -> bool: ...
```

### Estados obrigatórios em qualquer objeto

```
Objeto:
  encerrado      ← terminal — ciclo completo, ciência registrada
  cancelado      ← terminal — revogação clínica/administrativa
  expirado       ← terminal — validade ultrapassada
  encerrado_fisico (ou encerrada_localmente)  ← terminal — fluxo físico

Item:
  pendente       ← estado inicial do ciclo digital
  encerrado      ← terminal — item concluído
  cancelado      ← terminal — item revogado
  encerrado_fisico  ← terminal — fluxo físico
```

### Regra semântica inviolável

```
encerrado_fisico  ≠  cancelado
```

- `encerrado_fisico` = emitido em papel, nunca entrou no ciclo digital
- `cancelado` = decisão clínica dentro do fluxo digital

Nunca usar `cancelado` para representar emissão física. Nunca usar `encerrado_fisico` para representar revogação clínica.

### Objetos implementados

| Objeto | Arquivo de estados | Agregação | Estados terminais objeto |
|---|---|---|---|
| Prescrição | `domain/states.py` | `por_itens` | dispensada · cancelada · encerrada_localmente · expirada |
| Pedido de exame | `domain/states_exame.py` | `por_itens` | encerrado · cancelado · expirado · encerrado_fisico |
| Laudo | `domain/states_laudo.py` | `direto` | encerrado · cancelado · expirado · encerrado_fisico |

---

## 4. Contrato — Custódia

A cadeia de custódia é explícita, granular e rastreável para todo objeto sanitário digital.

```sql
CREATE TABLE {objeto}_custodia (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    {objeto}_id    INTEGER NOT NULL REFERENCES {objeto}s(id),
    item_id        INTEGER REFERENCES {objeto}_itens(id),  -- NULL = objeto inteiro
    de             TEXT NOT NULL,   -- papel ou CNPJ/CNS do cedente
    para           TEXT NOT NULL,   -- papel ou CNPJ/CNS do receptor
    transferido_em DATETIME DEFAULT (datetime('now')),
    dados_json     TEXT             -- contexto adicional (JSON)
);
```

**Invariantes:**
- `item_id = NULL` → custódia do objeto inteiro
- `item_id = X` → custódia de item específico
- Custódia não é registrada para fluxo físico (`tipo_emissao = 'fisico'`)
- Toda transferência é INSERT — nunca UPDATE ou DELETE

### Atores padrão

```
prescritor    → paciente       (emissão digital)
paciente      → prestador      (apresentação / agendamento)
prestador     → paciente       (devolução / resultado)
paciente      → prescritor     (devolução voluntária)
prestador     → prescritor     (erro / devolução clínica)
```

O vocabulário de papéis específicos (dispensador, prestador_exame, laboratório) é domínio do módulo.

---

## 5. Contrato — Ledger de Eventos

O ledger é imutável. Todo evento de negócio relevante gera um INSERT.

```sql
CREATE TABLE {objeto}_eventos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    {objeto}_id INTEGER NOT NULL REFERENCES {objeto}s(id),
    tipo_evento TEXT NOT NULL,   -- vocabulário controlado em EVENTOS_{OBJETO}
    dados_json  TEXT,            -- contexto estruturado (JSON)
    criado_em   DATETIME DEFAULT (datetime('now'))
);
```

**Invariantes invioláveis:**
- Nunca recebe UPDATE
- Nunca recebe DELETE
- Nenhum endpoint pode expor operações de remoção ou alteração de eventos
- `tipo_evento` deve ser membro de `EVENTOS_{OBJETO}` (frozenset)

### Eventos obrigatórios em qualquer objeto

```
{objeto}_emitido       ← emissão digital
{objeto}_impresso      ← fluxo físico — ato de impressão
encerrado_localmente   ← fluxo físico — estado terminal (mesmo nome em todos os objetos)
{objeto}_cancelado     ← cancelamento
custodia_transferida   ← qualquer transferência de posse
```

### Convenção do fluxo físico

O fluxo físico sempre emite **dois eventos** em sequência:
1. `{objeto}_impresso` — ato físico de impressão
2. `encerrado_localmente` — transição de estado (terminal)

---

## 6. Contrato — Documento Canônico + Hash

Todo objeto sanitário tem um documento canônico cujo hash SHA-256 é armazenado em `assinatura_hash`.

### Estrutura mínima do documento canônico

```json
{
  "protocolo":      "<UUID>",
  "autor_cns":      "<CNS do autor — prescritor, responsável técnico, etc.>",
  "paciente_cpf":   "<CPF>",
  "data_emissao":   "<ISO 8601>",
  "data_validade":  "<ISO 8601 | null>",
  "itens": [ ... ],
  "versao_esquema": "<semver>"
}
```

### Regras de geração do hash

```python
payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
hash_sha256 = hashlib.sha256(payload.encode()).hexdigest()
```

**Invariantes:**
- `sort_keys=True` é obrigatório — garante determinismo
- `ensure_ascii=False` é obrigatório — preserva caracteres especiais
- `versao_esquema` deve ser incrementado quando campos do documento forem alterados
- O hash é calculado no momento da emissão e nunca recalculado após commit

---

## 7. Contrato — PDF Institucional

O PDF de qualquer objeto sanitário segue o layout visual do PicSaúde.

### Paleta de cores (compartilhada)

```python
NAVY      = "#1a2e44"   # cabeçalho, títulos de seção
GREEN     = "#2e7d32"   # itens principais (medicamento, exame, etc.)
ORANGE    = "#e65100"   # urgência / emissão física
AMBER     = "#f57f17"   # urgente
SLATE     = "#546e7a"   # operacional / rotina
GREY_BG   = "#eceff1"   # fundo de seção
```

### Blocos estruturais (ordem obrigatória)

1. **Cabeçalho** — NAVY, "PicSaúde", subtítulo institucional, badge de tipo
2. **Prescritor** — nome, CNS
3. **Paciente** — nome, CPF mascarado (`123.***.***-XX`)
4. **Conteúdo** — específico do domínio (medicamentos / exames / laudo)
5. **Identificação do documento** — protocolo, data emissão, validade, status, hash
6. **Área de assinatura** — linha física + nome/CNS do prescritor
7. **Rodapé** — "PicSaúde — Plataforma de Custódia Sanitária Digital | Protocolo: {proto}"

**Invariante de segurança:** CPF `00000000000` deve ser exibido como `"Não identificado"` — nunca exposto diretamente.

### Arquivos existentes

| Objeto | Arquivo |
|---|---|
| Prescrição | `domain/pdf_prescricao.py` |
| Pedido de exame | `domain/pdf_pedido_exame.py` |

---

## 8. Contrato — QR Code + Validação Pública

Todo objeto sanitário digital tem um QR Code e uma página pública de validação.

### QR Code

```
GET /{objeto}s/{protocolo}/qr
→ PNG em memória
→ Codifica: {BASE_URL}/public/{objeto}s/{protocolo}
→ Auth: prescritor | admin
```

### Endpoint de validação pública

```
GET /public/{objeto}s/{protocolo}
→ Sem autenticação
→ Retorna: protocolo, status, tipo_emissao, itens (mínimos)
```

### Regra de segurança da validação pública (inviolável)

O endpoint público **nunca retorna**:
- CPF ou nome do paciente
- CNS ou nome do prescritor
- Dados clínicos (indicação, posologia, resultado)
- Histórico de eventos (ledger)
- Dados do estabelecimento

Retorna apenas: protocolo, status, tipo_emissao, lista de itens com nome e status_item.

---

## 9. Contrato — Emissão Física

A emissão exclusivamente física é suportada por todos os objetos sanitários. O padrão é idêntico entre objetos.

### Regras

- Status final do objeto: `encerrado_fisico` (ou `encerrada_localmente` — nomenclatura do módulo)
- Status de cada item: `encerrado_fisico`
- Dois eventos no ledger: `{objeto}_impresso` + `encerrado_localmente`
- Nenhum registro em `{objeto}_custodia`
- Nenhuma transferência ao paciente
- `data_validade = NULL`

### CPF sentinela

`'00000000000'` é reservado para objetos físicos sem identificação digital do paciente.

```python
_CPF_NAO_IDENTIFICADO = "00000000000"
```

Regras de uso:
- Queries analíticas devem excluir: `WHERE cpf != '00000000000'`
- Nunca expor em relatórios como identificação real
- Exibir como "Não identificado" no PDF e na validação pública

### Fire-and-forget

O frontend envia o POST de emissão física sem aguardar resposta. A impressão não depende do backend estar acessível. Consequência aceita: pode haver impressões sem persistência central.

---

## 10. O que NÃO abstrair

A distinção mais importante deste núcleo:

> **Abstrair a estrutura. Nunca o vocabulário de domínio.**

### Vocabulário que pertence a cada módulo

| Módulo | Vocabulário específico — não generalizar |
|---|---|
| Prescrição | `nome_medicamento`, `concentracao`, `posologia`, `unidade_quantidade`, `forma_farmaceutica` |
| Prescrição | Regras CFM: `assinatura_modo`, `MODOS_COM_VALIDADE_CFM`, `campos_cfm_obrigatorios` |
| Exame | `nome_exame`, `codigo_tuss`, `codigo_sigtap`, `prioridade`, `indicacao_clinica` |
| Exame | `resultado_resumo`, `resultado_url`, `resultado_em` |
| Laudo (futuro) | `conteudo_laudo`, `cid`, `assinatura_medica_responsavel` |

### Anti-padrões proibidos

```
# ❌ ERRADO — generaliza vocabulário de domínio
class ItemSanitario(BaseModel):
    conteudo: str          # elimina semântica farmacêutica / de exame
    codigo_universal: str  # não existe — TUSS ≠ DCB ≠ CID

# ✅ CORRETO — cada módulo tem seu schema específico
class ItemPrescricao(BaseModel):
    nome_medicamento: str
    unidade_quantidade: str

class ItemExame(BaseModel):
    nome_exame: str
    codigo_tuss: Optional[str]
```

### Estados do ledger: vocabulário é específico

Mesmo que o padrão de evento seja compartilhado, o nome dos eventos pertence a cada módulo:

```
prescricao_emitida   ≠  pedido_emitido   ≠  laudo_emitido
```

Nunca criar evento genérico `objeto_emitido` — perde auditabilidade regulatória.

---

## 11. Checklist para novo objeto sanitário

Antes de abrir qualquer ticket de implementação de novo objeto, verificar:

### Contrato de domínio
- [ ] Máquina de estados definida em `domain/states_{objeto}.py`
- [ ] Estados terminais explícitos (objeto + item)
- [ ] Vocabulário de eventos documentado
- [ ] `derivar_status_{objeto}()` implementada
- [ ] `encerrado_fisico` e `cancelado` com semântica distinta

### Contrato de persistência
- [ ] Tabela principal com `protocolo`, `status`, `tipo_emissao`, `origem_id`, `assinatura_hash`
- [ ] Tabela de itens com `status_item` próprio
- [ ] Tabela de eventos (ledger imutável)
- [ ] Tabela de custódia

### Contrato de API
- [ ] `POST /{objeto}s` — emissão digital
- [ ] `POST /{objeto}s/fisica` — emissão física
- [ ] `GET /{objeto}s/{proto}` — consulta autenticada
- [ ] `GET /{objeto}s/{proto}/custodia` — histórico
- [ ] `GET /{objeto}s/{proto}/pdf` — PDF institucional
- [ ] `GET /{objeto}s/{proto}/qr` — QR Code
- [ ] `GET /public/{objeto}s/{proto}` — validação pública (sem dados sensíveis)
- [ ] `GET /paciente/{objeto}s` — carteira do cidadão

### Contrato de segurança
- [ ] JWT + RBAC em todos os endpoints privados
- [ ] Endpoint público sem autenticação, sem dados sensíveis
- [ ] CPF sentinela tratado corretamente no PDF e na API
- [ ] Emissão física sem cadeia de custódia

### Documentação
- [ ] Estados adicionados à seção 7 do CLAUDE.md
- [ ] Arquivo de states incluído em `models/__init__.py` e `init_tables.py`
- [ ] Router registrado em `main.py`

---

## Referências internas

| Documento | Propósito |
|---|---|
| `CLAUDE.md` | Princípios arquiteturais obrigatórios do projeto |
| `docs/ARQUITETURA.md` | Visão arquitetural completa |
| `docs/ARQUITETURA_EXAMES.md` | Arquitetura específica do módulo de exames |
| `backend/app/domain/states.py` | Contrato de estados — prescrição |
| `backend/app/domain/states_exame.py` | Contrato de estados — pedido de exame |

---

*v1.0 — Gerado após Tickets 1–17 (prescrição + exame). v1.1 — Refinado após Ticket 19 (validação pelo laudo): `autor_id` generalizando `prescritor_id`; `tipo_agregacao_status` formalizando padrão por_itens vs direto.*
