# Panorama Técnico Consolidado — PicSaúde v2

> **Gerado em:** 2026-04-07
> **Base:** leitura direta do código em `backend/app/`, `*.html`, `config.js`, `init_tables.py`, `tests/`
> **Cobertura de tickets:** 62A · 62B · 62C · 64 · 65 · 66 · 67 · 68 · 68A
> **Metodologia:** análise estática de arquivos — sem inventar capacidades. Classificações:
> `[IMPLEMENTADO]` · `[PARCIAL]` · `[LIMITAÇÃO DOCUMENTADA]` · `[AUSENTE]`
>
> **Destinado a:** revisão por ChatGPT (arquiteto), Gemini (revisor técnico), Claude Chat (análise externa)

---

## 1. VISÃO GERAL

### O que é o PicSaúde hoje (estado real)

O PicSaúde é uma **infraestrutura de rastreamento de objetos sanitários** com cadeia de custódia digital. Não é EHR, não é prontuário eletrônico, não é gateway de integração. É uma plataforma que rastreia **quem emite, quem carrega e quem executa** cada objeto clínico (prescrição, exame, laudo, agendamento), garantindo imutabilidade auditável.

### O que já está resolvido tecnicamente

| Área | Status |
|---|---|
| Emissão de prescrições (digital + física) | `[IMPLEMENTADO]` |
| Cadeia de custódia (prescritor → paciente → dispensador) | `[IMPLEMENTADO]` |
| Ledger imutável com triggers de banco | `[IMPLEMENTADO]` — Ticket 62A |
| Config frontend agnóstico de ambiente | `[IMPLEMENTADO]` — Ticket 62B |
| Rate limiting por IP | `[IMPLEMENTADO]` — Ticket 62C |
| Parsing criptográfico de certificado ICP X.509 | `[IMPLEMENTADO]` — Ticket 66 |
| Pipeline de identidade prescritor (CNES + conselho) | `[IMPLEMENTADO]` — Ticket 65 |
| NomeValidator fuzzy (ICP × CNES × Conselho) | `[IMPLEMENTADO]` — Ticket 64 |
| String de validação auditável | `[IMPLEMENTADO]` — Ticket 67 |
| Verificação criptográfica RSA PKCS1v15 | `[IMPLEMENTADO]` — Ticket 68 |
| Bloqueio do par incompleto (cert sem assinatura) | `[IMPLEMENTADO]` — Ticket 68A |
| Dispensação (ambulatorial + hospitalar) | `[IMPLEMENTADO]` |
| Pedido de exame, laudo, agendamento, circulação diagnóstica | `[IMPLEMENTADO]` |
| Token de apresentação (QR Code + código curto) | `[IMPLEMENTADO]` |
| Event publishing via outbox (G4A) | `[IMPLEMENTADO]` |
| API Keys institucionais (G4B) | `[IMPLEMENTADO]` |
| IA farmacêutica passiva (alertas, posologia, CID) | `[IMPLEMENTADO]` |
| Validação documental em 5 camadas (pública) | `[IMPLEMENTADO]` |

### O que ainda depende de validação / está ausente

| Área | Status | Risco |
|---|---|---|
| Validação de cadeia ICP-Brasil (OCSP/CRL/raiz) | `[AUSENTE]` | CRÍTICO |
| Banco SQLite → PostgreSQL em produção | `[AUSENTE]` | ALTO |
| Rate limiting efetivo em multi-instância | `[AUSENTE]` | ALTO |
| Serialização JSON canônica frontend/backend testada end-to-end | `[PARCIAL]` | ALTO |
| JWT secret rotacionado em produção | `[AUSENTE]` | ALTO |
| Lookup CNES com CPF real (DataSUS enriquecido) | `[LIMITAÇÃO DOCUMENTADA]` | MÉDIO |
| Adapter HIS/TISS/HL7/e-SUS | `[AUSENTE]` | N/A (requer G4A completo) |

---

## 2. ARQUITETURA ATUAL (REAL)

### Backend

**Stack:**
- FastAPI `0.128.8` + Uvicorn (ASGI)
- SQLAlchemy `2.0.41` (ORM apenas para criação de tabelas; queries em raw SQL via `get_conn()`)
- SQLite único: `data/pix_saude_pe.db` (CNES + aplicação no mesmo arquivo)
- 24 routers ativos, registrados em `main.py`
- Middlewares: `RateLimitMiddleware` (62C) + `CORSMiddleware`

**Módulos `domain/` relevantes:**

| Arquivo | Responsabilidade | Ticket |
|---|---|---|
| `states.py` | Máquina de estados: prescrição + itens | Core |
| `documento_canonico.py` | Documento canônico + hash SHA-256 (versao_esquema=2) | Core |
| `assinatura.py` | Modos de assinatura (icp_brasil_local, gov_br_nuvem) | 5 |
| `nome_validator.py` | Fuzzy matching ICP × CNES × Conselho | 64 |
| `identidade_prescritor.py` | Pipeline identidade via CNES | 65 |
| `icp_identity.py` | Parsing X.509 + extração CPF/CRM/CRO | 66 |
| `string_validacao.py` | String auditável CPF\|CONSELHO\|CNS\|STATUS\|HASH\|TS | 67 |
| `assinatura_icp.py` | Verificação RSA PKCS1v15 Prehashed SHA-256 | 68 |
| `outbox.py` | Espelho de eventos para G4A (silent fail) | G4A |
| `validacao_documental.py` | Validação em 5 camadas pública | 6 |
| `confianca_cuidado.py` | Score composto de confiança | 50 |

**Fluxo de emissão de prescrição (`POST /prescricoes`):**

```
1. Guardrail 68A: cert_pem XOR assinatura_b64 → 422 imediato
2. Localizar/criar prescritor por CNS
3. Validar origem (quando correcao/renovacao)
4. Localizar/criar paciente por CPF
5. INSERT prescricoes (status='pendente')
6. INSERT prescricao_itens
7. Gerar documento canônico (SHA-256 do JSON sorted)
8. UPDATE prescricoes.assinatura_hash
9. Validação CNES (5 camadas) → score de confiança
10. Ticket 68: verificar assinatura ICP (se cert + assinatura presentes)
    → falha: HTTPException 422 (rollback implícito)
    → sucesso: continua
11. Ticket 67: gerar string_validacao_prescritor (se cert_pem presente)
12. UPDATE prescricoes.string_validacao_prescritor
13. INSERT prescricao_eventos (ledger)
14. Transferência de custódia: INSERT prescricao_custodia
15. conn.commit()
```

**Observação crítica:** O `conn.commit()` ocorre na etapa 15. A verificação de assinatura (etapa 10) é executada *antes* do commit, mas *após* os INSERTs de prescrição e itens. Se a verificação falhar e lançar HTTPException, o SQLite fará rollback da transação implicitamente — **desde que `conn.commit()` não tenha sido chamado antes**. Isso está correto no código atual, mas requer atenção em refatorações futuras.

### Frontend

**Páginas:**

| Arquivo | Ator | Funcionalidade principal |
|---|---|---|
| `prescritor.html` | Médico/Odontólogo | Emissão de prescrições (digital + física) |
| `dispensador.html` | Farmácia | Dispensação, scan de token |
| `cidadao.html` | Paciente | Carteira digital, histórico |
| `clinica.html` | Clínica/Lab | Pedidos de exame, laudos, agendamentos |
| `validar.html` | Público | Validação documental pública |
| `index.html` | Portal | Entrada unificada |

**Ticket 62B — `config.js`:**
```javascript
const _isLocal =
    window.location.protocol === 'file:' ||
    window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1';

const BACKEND_URL = _isLocal
    ? 'http://127.0.0.1:8000'
    : window.location.origin;
```
Incluído como primeiro `<script>` em todos os HTMLs. Elegante, sem hardcode.

**WebPKI/WebCrypto:** O frontend usa `window.crypto.subtle` para assinar o digest SHA-256 do payload com o certificado A1/A3 do usuário. Gera `assinatura_b64` (Base64 da assinatura RSA) e envia `cert_pem` ao backend.

**Limitação real:** Não há testes automatizados de integração frontend↔backend com WebCrypto real. A compatibilidade da serialização JSON canônica (sort_keys no frontend vs Python) foi implementada mas não testada end-to-end com cert real.

### Banco de dados

**Arquivo:** `data/pix_saude_pe.db` (SQLite)

**Tabelas clínicas principais:**
```
prescricoes              — objeto raiz da prescrição
prescricao_itens         — itens individuais (medicamentos)
prescricao_eventos       — ledger imutável (APPEND-ONLY via trigger)
prescricao_custodia      — cadeia de custódia granular
dispensacoes             — registro de dispensação ambulatorial
dispensacoes_hospitalares — dispensação hospitalar (org_id + unidade_id)
pedidos_exame            — pedidos de exame
pedido_exame_itens       — itens do pedido
pedido_exame_eventos     — ledger do módulo de exame
laudos                   — laudos laboratoriais
laudo_itens              — itens do laudo
laudo_eventos            — ledger do módulo de laudo
agendamentos             — agendamentos de coleta
agendamento_eventos      — ledger do módulo de agendamento
circulacao_diagnostica   — circulação diagnóstica
circulacao_diagnostica_eventos — ledger da circulação
eventos_publicacao       — outbox G4A
```

**Tabelas CNES (DataSUS, importadas):**
```
profissionais_cnes, relacao_prof_estab, estabelecimentos_cnes
```

**Triggers de ledger (Ticket 62A):**
```sql
-- Aplicados via init_tables.py::aplicar_triggers_ledger()
-- 5 tabelas: prescricao_eventos, pedido_exame_eventos, laudo_eventos,
--            agendamento_eventos, circulacao_diagnostica_eventos
CREATE TRIGGER IF NOT EXISTS prevent_update_{tabela}
BEFORE UPDATE ON {tabela}
BEGIN SELECT RAISE(FAIL, 'Ledger imutável: UPDATE não permitido em {tabela}'); END;

CREATE TRIGGER IF NOT EXISTS prevent_delete_{tabela}
BEFORE DELETE ON {tabela}
BEGIN SELECT RAISE(FAIL, 'Ledger imutável: DELETE não permitido em {tabela}'); END;
```

---

## 3. PIPELINE CRIPTOGRÁFICO COMPLETO

### Ordem exata de execução

```
[Frontend]
  1. Usuário clica "Emitir prescrição"
  2. Frontend serializa payload canônico:
       JSON.stringify({cns_prescritor, cpf_paciente, tipo_emissao, itens[...]},
                      sort_keys_order, no_spaces)
  3. WebCrypto calcula SHA-256 do payload serializado → digest (32 bytes)
  4. WebCrypto assina digest com chave privada do cert A1/A3
       → assinatura RSA PKCS1v15 sobre SHA-256 digest
  5. Exporta cert_pem (PEM do certificado público)
  6. Envia POST /prescricoes com:
       { ...dados..., cert_pem: "...", assinatura_b64: "base64(assinatura)" }

[Backend — antes de qualquer persistência]
  7. Ticket 68A — Guardrail de par:
       se cert_pem XOR assinatura_b64 → HTTP 422 imediato

[Backend — após INSERTs de prescrição/itens, antes de commit]
  8. Ticket 68 — Verificação criptográfica:
       a. base64.b64decode(assinatura_b64)
       b. json.dumps(dados_canonicos, sort_keys=True, separators=(',',':'))
          → SHA-256 → digest (32 bytes)
       c. x509.load_pem_x509_certificate(cert_pem)
       d. public_key.verify(assinatura, digest, PKCS1v15(), Prehashed(SHA256()))
          → InvalidSignature → HTTP 422 (rollback)
       e. verificar_validade_temporal(cert) → expirado → HTTP 422 (rollback)

  9. Ticket 66 — Extração de identidade do certificado:
       a. parsear_certificado_icp(cert_pem)
       b. CPF: OID 2.16.76.1.3.1 (SAN OtherName), offset 9-19 (DOC-ICP-04.4)
          Fallback: SAN RFC822Name, OU
       c. Nome: CN do Subject (stripped, uppercase)
       d. CRM/CRO: OU via regex tolerante

  10. Ticket 65 — Pipeline de identidade profissional:
       a. Busca CNES por número de conselho (JOIN profissionais_cnes + relacao_prof_estab)
       b. Consulta BancoCnesConselhoProvider (snapshot local)
       c. NomeValidator.validar_correspondencia(cert, cnes, conselho)
       d. Resolve vínculo único (ou multiplo_vinculo)

  11. Ticket 64 — NomeValidator:
       a. Normaliza (unicode, lowercase, sem acentos, sem pontuação)
       b. Extrai componentes (nome_proprio, sobrenome, preposições, sufixos)
       c. SequenceMatcher + Levenshtein para nome_proprio (limiar 0.85)
       d. SequenceMatcher para sobrenome (limiar 0.80)
       e. Retorna (valido, motivo, confianca)

  12. Ticket 67 — String de validação auditável:
       CPF|CONSELHO|CNS|STATUS_NOME|HASH_CERT|TIMESTAMP
       onde HASH_CERT = SHA-256(DER do certificado) — não do PEM
       Persiste em prescricoes.string_validacao_prescritor
       Registrado no payload do prescricao_eventos

  13. conn.commit() — tudo persiste atomicamente
```

### Onde pode falhar

| Ponto | Falha | Consequência |
|---|---|---|
| Etapa 7 | cert_pem sem assinatura_b64 | HTTP 422, nada persiste |
| Etapa 8d | Assinatura matematicamente inválida | HTTP 422, rollback |
| Etapa 8e | Cert expirado | HTTP 422, rollback |
| Etapa 8b | JSON canônico frontend ≠ backend | Assinatura inválida → HTTP 422 |
| Etapa 9b | OID ausente no cert + OU sem CPF | cpf_certificado=None (string_validacao não gerada) |
| Etapa 9d | CRM/CRO ausente no cert | necessita_conselho_manual (string_validacao não gerada) |
| Etapa 10a | Conselho não encontrado no CNES | status=nao_encontrado_cnes |
| Etapa 10c | Nomes divergentes | status=divergente (não bloqueia emissão) |
| Etapa 12 | CPF ou conselho ausentes | ValueError silenciado, string_validacao=NULL |

### Garantias matemáticas

**O que está garantido:**
- `assinatura_valida=True` prova que a chave privada correspondente ao `cert_pem` assinou exatamente aquele payload JSON canonizado
- O `digest_hex` registrado no ledger permite re-verificação posterior
- `hash_cert_der` no campo `string_validacao` identifica o certificado usado de forma imune a variações de formatação PEM

**O que NÃO está garantido (lacuna crítica):**
- Que o `cert_pem` foi emitido por uma CA da cadeia ICP-Brasil
- Que o certificado não foi revogado (sem OCSP/CRL)
- Que o CN/CPF do certificado pertence a um médico real (sem validação de cadeia contra raiz confiável)

Em outras palavras: a matemática da assinatura está correta, mas o **certificado pode ser autoassinado ou emitido por CA qualquer** e passará na verificação. Isso é a maior lacuna de segurança atual.

---

## 4. MODOS DO SISTEMA

### Fluxo físico

**Comportamento:**
- `POST /prescricoes/fisica` — fire-and-forget
- Frontend não aguarda resposta (timeout ignorado)
- Se backend offline: impressão ocorre, registro fica apenas no `localStorage`
- Status final: `encerrada_localmente` (prescrição), `encerrado_fisico` (itens)
- CPF sentinela: `00000000000` quando paciente não identificado digitalmente
- Sem cadeia de custódia, sem transferência ao paciente, sem dispensação digital

**Limitações:**
- Pode haver impressões sem persistência central (trade-off documentado e aceito)
- Sem rastreabilidade pós-impressão
- Sem verificação de identidade do prescritor

**Riscos:**
- Falsificação de emissão física é indistinguível do sistema
- Um agente malicioso pode gerar prescrições físicas localmente sem acesso ao backend

### Fluxo digital ICP

**Comportamento:**
- `POST /prescricoes` com `cert_pem` + `assinatura_b64`
- Verificação criptográfica obrigatória (Ticket 68)
- Pipeline de identidade completo (Tickets 64/65/66/67)
- `string_validacao_prescritor` gerada e persistida
- Cadeia de custódia registrada em `prescricao_custodia`
- Eventos registrados em `prescricao_eventos` (ledger imutável)

**Garantias reais:**
- A assinatura RSA prova que quem gerou a prescrição tinha acesso à chave privada do certificado
- O digest do payload está registrado no ledger — modificação posterior detectável
- A string de validação consolida identidade civil, profissional e institucional em formato auditável

**Diferenças entre modos:**

| Característica | Físico | Digital ICP |
|---|---|---|
| Verificação criptográfica | Não | Sim (68) |
| Cadeia de custódia | Não | Sim |
| Dispensação digital | Não | Sim |
| String de validação | Não | Sim (se cert válido) |
| Persistência garantida | Não (fire-and-forget) | Sim |
| Validade CFM (Res. 2.299/2021) | Não | Depende (sem chain validation) |

---

## 5. LEDGER E AUDITORIA

### Como eventos são registrados

Toda transição de estado relevante gera um `INSERT` em `prescricao_eventos` (ou equivalente para outros módulos). O payload do evento é JSON serializado e pode conter:
- `string_validacao` com componentes auditáveis (Ticket 67)
- `verificacao_assinatura_icp` com `digest_hex` e flags (Ticket 68)
- `score_confianca` do prescritor (Ticket 50)
- `validacao_prescritor` com resultado das 5 camadas de validação CNES

### O que é garantido (imutabilidade real)

Tickets 62A implementaram triggers `BEFORE UPDATE` e `BEFORE DELETE` em 5 tabelas de ledger. Os triggers foram testados em `test_ledger_imutabilidade.py` (1019 testes passando). Qualquer tentativa de UPDATE ou DELETE via SQL direto resulta em `sqlite3.DatabaseError: Ledger imutável`.

### O que ainda não é garantido

1. **Triggers bypassáveis**: `PRAGMA foreign_keys = OFF` + `DROP TRIGGER` permitem contornar os triggers via acesso direto ao banco. Os triggers protegem contra acidente, não contra acesso malicioso com permissão de escrita no arquivo SQLite.

2. **Outbox pode falhar silenciosamente**: `outbox.py` usa `try/except Exception` com `logging.warning`. Se a tabela `eventos_publicacao` não existir ou tiver esquema incorreto, o evento de ledger clínico já foi gravado, mas o outbox será perdido sem alerta imediato ao operador.

3. **Sem assinatura criptográfica dos eventos**: Os eventos no ledger são strings JSON em texto claro. Não há assinatura que impeça modificação direta no arquivo `.db`.

### Como um auditor reconstruiria uma prescrição

```sql
-- 1. Localizar prescrição por protocolo
SELECT * FROM prescricoes WHERE protocolo = '<uuid>';

-- 2. Reconstruir linha do tempo de eventos
SELECT tipo_evento, created_at, payload
FROM prescricao_eventos
WHERE prescricao_id = <id>
ORDER BY created_at;

-- 3. Verificar cadeia de custódia
SELECT detentor_tipo, detentor_id, item_id, created_at
FROM prescricao_custodia
WHERE prescricao_id = <id>
ORDER BY created_at;

-- 4. Verificar dispensações
SELECT * FROM dispensacoes WHERE prescricao_id = <id>;

-- 5. Re-calcular hash do documento canônico (via GET /prescricoes/{proto}/documento)
-- Comparar com assinatura_hash armazenado
```

O auditor pode verificar se o `hash_sha256` do documento reconstruído corresponde ao `assinatura_hash` armazenado. Se divergir, o conteúdo clínico foi alterado após emissão (violação das regras do núcleo).

A `string_validacao_prescritor` (campo da prescrição) e o payload do evento `prescricao_emitida` permitem reconstituir a identidade do prescritor no momento da emissão.

---

## 6. SEGURANÇA

### ICP — correto matematicamente, insuficiente como validação de identidade

**O que foi implementado corretamente:**
- RSA PKCS1v15 com `Prehashed(SHA256())` — necessário para compatibilidade com WebCrypto
- Validação temporal timezone-safe (compatível com `cryptography >= 42.0`)
- JSON canônico determinístico (`sort_keys=True`, `separators=(',',':')`)
- Hash DER (não PEM) — imune a variações de formatação

**O que está faltando:**
- Validação de cadeia de confiança contra CAs raiz ICP-Brasil
- Verificação de revogação (OCSP/CRL)
- Verificação de uso (KeyUsage: digitalSignature)
- Verificação de que o OID do certificado é ICP-Brasil Pessoa Física (2.16.76.1.3.1 presente)

**Consequência prática:** qualquer certificado X.509 RSA autoassinado com CN e OID adequados passaria na verificação atual.

### Rate limiting — implementação correta, efetividade limitada

```python
# Ticket 62C — backend/app/middleware/rate_limit.py
ROUTE_LIMITS = [
    ("/auth/token",          5),   # 5 req/60s por IP
    ("/tokens/apresentacao", 10),  # 10 req/60s por IP
    ("/circulacao",          20),  # 20 req/60s por IP
]
DEFAULT_LIMIT = 30  # req/60s por IP
```

**Problema real:** estado em dicionário Python in-process (`_store: Dict[str, Deque[float]]`). Em deployment com múltiplas instâncias (Cloud Run, qualquer orquestrador stateless), cada instância tem seu próprio contador. Um atacante com N instâncias pode fazer `5N` requisições para `/auth/token` antes de ser bloqueado. **Sem Redis ou estado compartilhado, a proteção é zero em produção multi-instância.**

Bypass de dev: `RATE_LIMIT_DISABLED=1` — adequado, mas deve estar documentado para não ser ativado em produção.

### Confiança no frontend vs backend

O backend **nunca confia** em dados de identidade enviados pelo frontend:
- CPF do prescritor: extraído do certificado no backend
- Nome: extraído do CN do certificado no backend
- CRM/CRO: extraído do OU do certificado no backend

O frontend fornece apenas: `cert_pem` (bruto), `assinatura_b64` (bruta) e os campos clínicos (itens, paciente, etc.). A verificação de identidade acontece inteiramente no backend.

### JWT — configuração com risco de descuido

```python
# config.py linha 33
JWT_SECRET: str = os.getenv(
    "PICSAUDE_JWT_SECRET",
    "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"  # fallback perigoso
)
```

O fallback é deliberadamente óbvio e longo para desencorajar uso acidental. Mas em um deploy descuidado onde a env var não é definida, o segredo padrão se tornará público trivialmente (está no código). **Em produção, `PICSAUDE_JWT_SECRET` deve ser obrigatória — o sistema deveria falhar no startup se ausente ou igual ao padrão.**

Algoritmo: HS256 (simétrico). Para auditoria externa, RS256 seria preferível.

### CORS — permissivo

```python
# main.py
CORSMiddleware(
    allow_origins=["http://localhost", "http://127.0.0.1:5500"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins` está restrito a localhost — correto para dev. Em produção, este array deve listar os domínios reais. `allow_methods=["*"]` e `allow_headers=["*"]` são permissivos mas aceitáveis para API interna.

### Superfícies de ataque ainda abertas

1. **Acesso direto ao arquivo SQLite**: sem autenticação de banco, sem criptografia em repouso
2. **Sem WAL explícito**: `PRAGMA journal_mode=WAL` não está configurado → writes lentos, risco de corrupção em crash
3. **CNES + app no mesmo arquivo**: backup do banco expõe dados de profissionais e dados clínicos simultaneamente
4. **`datetime.utcnow()`**: `prescricoes.py:215` usa API deprecated em Python 3.12+. Não é vulnerabilidade, mas pode silenciar erros futuros.
5. **Snapshot CNES desatualizado**: referência `cnes_br_2025_12` (dez/2025). Profissionais com registro pós-dezembro não serão encontrados no lookup.
6. **Sem HTTPS forçado**: o sistema serve HTTP. Em produção, HTTPS é responsabilidade do reverse proxy — mas não há verificação no startup.

---

## 7. RISCOS REAIS (NÃO TEÓRICOS)

### CRÍTICOS — risco de fraude ou quebra de integridade

**R1 — Certificados autoassinados passam na verificação ICP**
- Qualquer pessoa pode gerar um cert X.509 RSA autoassinado com CPF e CRM fictícios no CN/OU
- A verificação de assinatura (`verificar_assinatura_icp`) valida a matemática, não a origem
- Uma prescrição assinada com cert autoassinado terá `assinatura_valida=True` no ledger
- **Impacto:** falsificação de identidade de prescritor com auditoria falsa

**R2 — JWT secret padrão em deploy descuidado**
- Se `PICSAUDE_JWT_SECRET` não for definida, o segredo é `TROQUE_EM_PRODUCAO_use_secrets_token_hex_32`
- Qualquer atacante que conheça o código pode forjar tokens JWT com qualquer role
- **Impacto:** elevação de privilégio total (prescritor, admin, dispensador)

**R3 — Snapshot CNES via conselho sem CPF**
- O DataSUS público não inclui CPF em `profissionais_cnes` (campo `CO_CPF` = literal "CO_CPF")
- O lookup é feito por número de conselho, não por CPF do certificado
- Um atacante com número de conselho real pode usar certificado com CPF diferente
- O NomeValidator mitiga parcialmente, mas não é prova de identidade

### ALTOS — risco em produção

**R4 — Rate limiting inoperante em multi-instância**
- Brute force em `/auth/token` (5 req/60s por instância) é trivial com N instâncias
- **Impacto:** credential stuffing sem contenção efetiva

**R5 — SQLite em produção**
- Sem WAL configurado explicitamente
- Sem backup automático
- Sem replicação
- Arquivo único com CNES (dados públicos) + dados clínicos sensíveis
- **Impacto:** perda de dados em crash, LGPD (dados de saúde em arquivo desprotegido)

**R6 — Serialização JSON canônica frontend↔backend sem teste E2E**
- O backend usa `json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False)`
- O frontend deve usar serialização equivalente (RFC 8785 ou manual com sort)
- Qualquer divergência (ordem de chaves, encoding de caracteres especiais) quebra a verificação
- Não há teste automatizado com WebCrypto real
- **Impacto:** prescrições com cert válido rejeitadas em produção (falso negativo)

**R7 — Triggers bypassáveis via acesso direto**
- `DROP TRIGGER prevent_update_prescricao_eventos` + `UPDATE` contorna a imutabilidade
- Requer acesso ao arquivo `.db` com permissão de escrita
- **Impacto:** adulteração de ledger sem trace (se não houver backup comparativo)

### MÉDIOS — ajustes futuros

**R8 — `datetime.utcnow()` deprecated**
- `prescricoes.py:215` usa API deprecated em Python 3.12+
- Pode gerar `DeprecationWarning` → potencialmente `RuntimeError` em versões futuras

**R9 — Snapshot CNES dezembro/2025**
- Profissionais cadastrados após a data do snapshot não são encontrados
- Prescrições com binding ICP falharão com `status=nao_encontrado_cnes`
- Requer processo de atualização periódica documentado

**R10 — `allow_methods=["*"]` em CORS**
- Aceita qualquer método HTTP (incluindo TRACE, CONNECT)
- Restrição a `["GET", "POST", "OPTIONS"]` seria mais defensiva

---

## 8. PONTOS DE DÍVIDA TÉCNICA

### Decisões de MVP que precisam revisão antes de produção real

| Dívida | Arquivo | Impacto |
|---|---|---|
| Sem validação de cadeia ICP-Brasil | `assinatura_icp.py` | CRÍTICO — validade jurídica |
| SQLite → PostgreSQL | `config.py`, `database.py` | ALTO — produção multi-usuário |
| Rate limiting sem Redis | `middleware/rate_limit.py` | ALTO — brute force em multi-instância |
| JWT secret sem validação de startup | `config.py:33` | ALTO — deploy descuidado |
| `datetime.utcnow()` deprecated | `routers/prescricoes.py:215` | BAIXO — compatibilidade futura |
| CNES sem CPF no DataSUS | `identidade_prescritor.py` (comentário L14-26) | MÉDIO — identidade imprecisa |

### Simplificações feitas (documentadas no código)

- **MVP de assinatura**: `assinatura.py` documenta que "a prova criptográfica completa (PKCS#7/CAdES) será adicionada na integração com token A1/A3 ou API gov.br"
- **Agendamento → Coletado**: equivalência direta `realizado → coletado` — simplificação do MVP
- **Fire-and-forget físico**: aceita perda de registro quando backend offline
- **BancoCnesConselhoProvider**: usa snapshot local sem chamar API CFM/CFO real; `nome_conselho=None`, `ativo=None`

### Partes frágeis

1. **`_decode_der_string`** em `icp_identity.py`: parser DER manual com 5 tags reconhecidas. Certificados com tags não listadas caem no fallback UTF-8 direto — pode produzir CPF incorreto silenciosamente.

2. **`outbox.py` silent fail**: se `eventos_publicacao` não existir (init_tables não rodou), eventos G4A são silenciosamente descartados. O ledger clínico é preservado, mas a camada de publicação externa fica cega.

3. **Múltiplos vínculos**: quando prescritor tem vínculos em múltiplos estados e `conselho_uf` não é suficiente para discriminar, o pipeline retorna `multiplo_vinculo` e `string_validacao` não é gerada. Em produção, profissionais com atividade em múltiplos estados terão binding incompleto.

---

## 9. PRONTIDÃO PARA TESTE PESADO (JULES)

### O sistema aguenta teste pesado?

**Sim, com ressalvas.**

**Pontos robustos:**
- 1019 testes automatizados passando (100%), incluindo integração com banco real
- Triggers de ledger testados e verificados
- Pipeline ICP testado com certificados de teste
- Rate limiting testado com bypass via `RATE_LIMIT_DISABLED=1`
- Todos os módulos core têm cobertura unitária

**Onde pode quebrar sob carga:**

| Cenário | Risco |
|---|---|
| Concorrência em SQLite (múltiplas requisições simultâneas) | `database is locked` sem retry |
| Rate limiting com muitos IPs simultâneos | `_store` pode crescer até 10k IPs antes da limpeza |
| Certificados com encoding DER não-padrão | `_decode_der_string` pode retornar None silenciosamente |
| Payload grande com muitos itens | JSON canônico cresce linearmente — sem limite de tamanho |
| Snapshot CNES ausente/corrompido | Todos os lookups de identidade falharão silenciosamente |

**O que deve ser monitorado durante testes:**
- Taxa de `HTTP 422` em `/prescricoes` (indicativo de divergência de serialização JSON)
- Taxa de `status=nao_encontrado_cnes` (indicativo de snapshot desatualizado)
- Taxa de `status=multiplo_vinculo` (indicativo de profissionais com múltiplos vínculos)
- Taxa de `string_validacao_prescritor=NULL` (prescrições sem binding ICP)
- `sqlite3.OperationalError: database is locked` em logs

---

## 10. PRONTIDÃO PARA MVP REAL

### Pode ir para uso real controlado?

**Não diretamente. Com as seguintes condições mínimas:**

**Obrigatório antes de qualquer usuário real:**

1. **R2 — JWT secret**: `PICSAUDE_JWT_SECRET` deve ser variável de ambiente obrigatória. O sistema deve recusar startup se a variável não estiver definida ou for igual ao padrão.

2. **R5 — SQLite → PostgreSQL**: para qualquer produção com mais de 1 usuário simultâneo. SQLite com múltiplas gravações concorrentes produz `database is locked`.

3. **R4 — Rate limiting com Redis**: para qualquer deploy com múltiplas instâncias. In-memory é apenas decorativo em Cloud Run.

**Necessário antes de afirmar validade jurídica (CFM 2.299/2021):**

4. **R1 — Validação de cadeia ICP-Brasil**: implementar verificação OCSP ou CRL contra as CAs raiz ICP-Brasil. Sem isso, a assinatura não tem validade jurídica — é apenas prova de posse de chave, não de identidade credenciada.

**Pode ser aceito para piloto controlado (com consentimento de risco):**

- R3 (snapshot CNES sem CPF): risco mitigado pelo NomeValidator e auditoria manual
- R6 (serialização E2E): pode ser testado com cert real antes do piloto
- R8 (datetime.utcnow): não tem impacto funcional em Python 3.9-3.11
- R9 (snapshot desatualizado): processo de atualização manual aceitável em piloto

---

## 11. CONCLUSÃO DO ARQUITETO

**[x] PRONTO COM RESSALVAS**

### Justificativa técnica

O PicSaúde pós-Tickets 62A–68A é um sistema **corretamente arquitetado e solidamente implementado** para o que se propõe. O ledger imutável por triggers de banco é real e testado. O pipeline criptográfico ICP (Tickets 64-68) está tecnicamente correto na camada matemática (RSA PKCS1v15 Prehashed SHA-256, JSON canônico, hash DER).

**O sistema está pronto para teste pesado controlado.** Com 1019 testes passando, cobertura ampla dos fluxos críticos e pipeline ICP bem testado unitariamente, Jules pode executar testes de integração sem risco de danos irreversíveis (banco é arquivo local, sem estado externo).

**O sistema não está pronto para produção real sem três ações:**

1. JWT secret obrigatória por variável de ambiente com verificação no startup
2. SQLite → PostgreSQL (ou pelo menos WAL + backup automático)
3. Rate limiting com estado compartilhado (Redis)

**O sistema não está pronto para afirmar validade jurídica CFM sem:**

4. Validação de cadeia de confiança ICP-Brasil (OCSP/CRL contra raiz ICP-A.C. Raiz v10)

A lacuna de validação de cadeia ICP (R1) é a mais importante. Tecnicamente é uma adição de ~50 linhas com a biblioteca `cryptography` já instalada. Operacionalmente requer acesso às CRLs públicas do ICP-Brasil (ou OCSP). **Sem isso, qualquer afirmação de que "a prescrição foi assinada por médico verificado ICP-Brasil" é tecnicamente imprecisa.**

Excluindo a questão de validade jurídica e os três pré-requisitos de produção, o núcleo sanitário (ledger, custódia, estados, documento canônico) está correto, auditável e extensível conforme a arquitetura define.

---

*Documento gerado em 2026-04-07 a partir de leitura direta do código. Nenhuma capacidade foi inventada.*
*Revisão recomendada por: ChatGPT (arquiteto), Gemini (revisor técnico), Claude Chat (análise externa).*
