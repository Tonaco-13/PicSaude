# TICKET 21 — Assinatura digital ICP-Brasil embutida no PDF (PAdES-B)

> Embute assinatura PAdES-B (PDF Advanced Electronic Signatures, baseline)
> dentro do PDF do receituário regulatório, usando o certificado
> ICP-Brasil A1 do prescritor.

## 1. Problema

O PDF do receituário (Ticket 17) é gerado pelo ReportLab com QR de
rastreabilidade e selo visual, mas **não tem assinatura digital
embutida**. A verificação criptográfica existente (T66–T68) opera
sobre o payload canônico — não sobre o PDF entregue à farmácia.

Para validade jurídica plena (RDC 1.000/2025 + MP 2.200-2/2001), o
PDF precisa ter assinatura PAdES verificável por qualquer leitor
compatível (Adobe Reader, validadores PAdES, ITI ICP-Brasil).

## 2. Solução

Endpoint dedicado `POST /receituarios/{id}/pdf-assinado` que:

1. Carrega o certificado ICP-Brasil A1 do prescritor (pré-cadastrado,
   armazenado AES-256-GCM cifrado)
2. Gera PDF base via T17
3. Assina com pyHanko no padrão PAdES-B
4. Embute selo visual no rodapé
5. Registra evento `pdf_assinado_pades` no ledger

## 3. Distinção das duas assinaturas

O PicSaúde mantém DUAS camadas de assinatura, com finalidades distintas:

| Camada | Objeto assinado | Onde persiste | Ticket |
|---|---|---|---|
| **Payload canônico** | `documento_canonico` (ato clínico) | `prescricao_assinatura` | T66–T68 |
| **PAdES no PDF** | bytes do PDF regulatório | embutido no PDF + evento ledger | **T21** |

Ambas podem usar o mesmo certificado ICP-Brasil. Não são redundantes
— assinam objetos diferentes, com propósitos distintos:
- T68 prova autoria do **ato médico**
- T21 prova integridade do **documento entregue à farmácia**

## 4. Fluxo end-to-end

```
1) POST /prescritor/certificado
       (multipart: pfx_file + senha)
       └─ valida senha + KeyUsage.digitalSignature
       └─ extrai identidade ICP via parsear_certificado_icp() (T66)
       └─ marca cert anterior como ativo=FALSE + substituido_em
       └─ cifra .pfx com AES-256-GCM (PFX_ENCRYPTION_KEY)
       └─ persiste em prescritor_certificados

2) POST /prescricoes/{proto}/receituarios/gerar      (T15)
3) POST /prescricoes/{proto}/receituarios/numerar    (T16A)

4) POST /prescricoes/{proto}/receituarios/{id}/pdf-assinado
       (body: { senha_pfx })
       ├─ assinatura_modo != "icp_brasil_local" → 409
       ├─ sem certificado ativo                  → 422
       ├─ senha errada                           → 401
       └─ sucesso:
            ├─ decifra .pfx em memória
            ├─ gera PDF via T17
            ├─ assina (PAdES-B) com pyHanko
            ├─ registra evento pdf_assinado_pades
            └─ retorna PDF assinado (StreamingResponse)
```

## 5. Componentes criados

### 5.1 Domain — assinatura PAdES

[`app/domain/pdf_assinatura.py`](../../backend/app/domain/pdf_assinatura.py):

| Função / classe | Responsabilidade |
|---|---|
| `MetadataAssinatura` (dataclass) | Dados para o selo visual e dicionário /Reason, /Location |
| `PfxCarregado` (dataclass) | Resultado in-memory do `carregar_pfx` |
| `assinar_pdf_icp()` | API principal — recebe PDF + .pfx + senha, retorna PDF assinado |
| `carregar_pfx()` | Valida senha + KeyUsage.digitalSignature |
| `pdf_tem_assinatura()` | Helper para testes (detecta CMS embutido) |
| `SenhaPfxInvalida` / `CertificadoSemKeyUsage` | Exceções tipadas |

Erros tipados → endpoint mapeia para 401 / 422.

### 5.2 Domain — cofre AES-GCM

[`app/domain/cofre_pfx.py`](../../backend/app/domain/cofre_pfx.py):

```
PFX_ENCRYPTION_KEY (env, hex 64 chars ou 32 bytes)
       │
       ▼
   AESGCM(chave)
   ┌────────────────────────────────────────────────────┐
   │ cifrar_pfx(pfx_bytes) → PfxCifrado(cifrado, iv, tag)│
   │ decifrar_pfx(cifrado, iv, tag) → pfx_bytes          │
   └────────────────────────────────────────────────────┘
```

Modo de fallback explícito (sentinela `PICSAUDE_DEV_INSECURE_PFX_KEY___`)
quando a env var não está definida — para dev/teste apenas. Função
`chave_eh_segura()` permite assertion em produção.

### 5.3 Modelo de banco

Tabela `prescritor_certificados` — separada de `prescritores` para
permitir histórico de renovação/revogação:

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | INT | PK |
| `prescritor_id` | INT FK | → prescritores.id |
| `pfx_cifrado` | BYTEA | AES-GCM |
| `pfx_iv` / `pfx_tag` | BYTEA(12) / BYTEA(16) | IV + tag |
| `hash_cert_der` | VARCHAR(64) | SHA-256 do DER (fingerprint imutável) |
| `serial` | VARCHAR(100) | serial X.509 |
| `valido_de` / `valido_ate` | TIMESTAMP | validade do cert |
| `nome_no_certificado` / `cpf_no_certificado` / `emissor` | TEXT | metadados |
| `ativo` / `revogado_em` / `substituido_em` | BOOL/TS | lifecycle |
| `uploaded_em` | TIMESTAMP | auditoria |
| UNIQUE `(prescritor_id, hash_cert_der)` | | impede re-upload duplicado |

Apenas UM certificado ativo por prescritor por vez (enforcement no
endpoint, não no schema — permite múltiplos inativos para histórico).

### 5.4 Endpoints

| Método | Rota | Descrição |
|---|---|---|
| `POST` | `/prescritor/certificado` | Upload .pfx (multipart) — auth `prescritor` |
| `POST` | `/prescricoes/{proto}/receituarios/{id}/pdf-assinado` | Gera PDF + embute PAdES — auth `prescritor` |

### 5.5 Anti-logging

[`app/middleware/sensitive_body.py`](../../backend/app/middleware/sensitive_body.py)
declara o conjunto explícito `BODY_NUNCA_LOGAR`:

```python
BODY_NUNCA_LOGAR = frozenset({
    "/prescritor/certificado",
    "/pdf-assinado",
})

def rota_tem_body_sensivel(path: str) -> bool: ...
```

O middleware principal (`observabilidade.py`) **já** não loga bodies
por design. Esta constante é uma camada complementar — qualquer novo
middleware (debug, APM, request inspector) deve consultá-la antes de
serializar bodies.

### 5.6 Selo visual

```
┌────────────────────────────────────────────┐
│  Assinado digitalmente por:                │
│  FABIANO TONACO BORGES                     │
│  CPF: 830.864.391-49                       │
│  CRM-PE 22847                              │
│  Data: 29/04/2026 18:45:32 UTC             │
│  Certificado ICP-Brasil                    │
└────────────────────────────────────────────┘
```

Posicionado no rodapé da primeira página (~110×25mm a 20mm da
esquerda + 8mm do bottom). Gerado pelo `TextStampStyle` do pyHanko.

## 6. Decisões de design

1. **Endpoint separado de `GET /pdf`.** Mantém o caminho de
   visualização (sem assinatura) limpo e isolado da lógica
   criptográfica e da senha sensível.

2. **Senha no body JSON, não em header.** Headers são logados por
   muitos proxies/load balancers; bodies não. Combinado com o
   middleware anti-logging, a senha permanece privada.

3. **`.pfx` cifrado no banco, não em filesystem.** Evita problemas
   de permissão de arquivo, é backupeado junto com o banco, e não
   exige integração com sistema de arquivos compartilhado em
   deploy horizontal.

4. **Apenas PAdES-B na fase 1.** Carimbo de tempo (PAdES-T) e
   validação de longo prazo (PAdES-LT/LTA) ficam para tickets
   futuros — exigem integração com TSA externa e servidor OCSP/CRL.

5. **Senha por request.** Mais seguro que cache em sessão. UX é
   inferior, mas eliminamos a janela onde a senha estaria viva no
   processo. Fase 2 pode avaliar cache em memória com TTL curto.

6. **Re-assinatura permitida.** Cada chamada gera novo PDF assinado
   (com timestamp diferente). NÃO altera status do receituário —
   PAdES é independente da emissão lógica. O ledger registra
   `pdf_assinado_pades` para cada assinatura, com `hash_pdf`
   distinto. Auditoria pode reconstruir o histórico.

7. **Tabela separada de `prescritores`.** Histórico de certificados
   sem poluir entidade principal. Cada PDF assinado pode ser
   auditado contra o `hash_cert_der` específico que o assinou.

8. **Validação `KeyUsage.digitalSignature` no upload.** Rejeita
   certificados emitidos exclusivamente para autenticação ou
   criptografia. Aceita certs sem extensão KeyUsage (compatibilidade
   com ICP-Brasil legados que não declaram explicitamente).

## 7. Cobertura de testes

### Unitários — [`tests/test_pdf_assinatura.py`](../../backend/tests/test_pdf_assinatura.py)

11 testes:

- `test_assinar_pdf_basico` — assinatura simples
- `test_assinar_pdf_invisivel` — sem selo visual
- `test_assinar_pdf_senha_invalida` → `SenhaPfxInvalida`
- `test_assinar_pdf_sem_keyusage_digital_signature` → `CertificadoSemKeyUsage`
- `test_texto_selo_visual_contem_campos_obrigatorios`
- `test_pdf_assinado_traz_certificado_embutido` — cert no SignedData CMS
- `test_carregar_pfx_retorna_pfx_carregado`
- `test_carregar_pfx_certificado_expirado_nao_bloqueia`
- `test_pdf_tem_assinatura_negativo_para_pdf_sem_assinatura`
- `test_pdf_tem_assinatura_robusto_a_bytes_invalidos`
- `test_assinar_pdf_receituario_real` — integração T17 + T21

### Integração — [`tests/integration/test_pdf_assinatura.py`](../../backend/tests/integration/test_pdf_assinatura.py)

15 testes:

**Upload de certificado** (6):
- sucesso com cert teste
- substituição marca anterior como inativo
- senha inválida → 401
- sem KeyUsage → 422
- arquivo > 64KB → 413
- sem auth → 401/403

**Endpoint /pdf-assinado** (8):
- sucesso (201, content-type PDF, > 5KB)
- PDF é validável via pyHanko (`pdf_tem_assinatura`)
- evento `pdf_assinado_pades` no ledger com hash_pdf, hash_cert_der, ticket_referencia
- sem certificado ativo → 422
- senha inválida → 401
- senha ausente no body → 422
- modo `gov_br_nuvem` (não ICP) → 409
- outro prescritor → 403

**Anti-logging** (1):
- `rota_tem_body_sensivel` cobre rotas críticas e ignora outras

### Fixture de certificado — [`tests/fixtures/certificado_teste.py`](../../backend/tests/fixtures/certificado_teste.py)

Gera `.pfx` autoassinado simulando ICP-Brasil:
- CN no formato Serpro (`NOME:CPF`)
- SAN com OID 2.16.76.1.3.1 (DOC-ICP-04.4 Pessoa Física)
- KeyUsage parametrizável (para testar bloqueio)
- Validade configurável (para testar cert expirado)

```bash
DATABASE_URL=postgresql://postgres:@127.0.0.1:5432/picsaude_test \
    pytest tests/test_pdf_assinatura.py tests/integration/test_pdf_assinatura.py -v
```

**Suite completa: 146/146 testes passam, 2× consecutivas** (zero
regressão dos T15/T17/T18/T19/T20).

## 8. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| pyHanko incompatível com versão ReportLab | pyHanko opera em PDF bytes — independente do gerador. Validado com testes E2E. |
| Cert e-CPF não aceito como assinatura médica | RDC 1.000/2025 aceita qualquer cert ICP-Brasil. CRM vem do binding T65, não do cert. |
| Senha interceptada em trânsito | HTTPS obrigatório + senha no body (não em header) + anti-logging |
| `PFX_ENCRYPTION_KEY` comprometida | Variável de ambiente, nunca no código. Rotação requer re-criptografar (script futuro). |
| Validação Adobe Reader falha | Embute cadeia CA (other_certs do .pfx). Adobe Reader reconhece AC ICP-Brasil desde AATL 2019. |

## 9. Configuração para produção

Configurar variável de ambiente antes do deploy:

```bash
# Gerar chave AES-256 (32 bytes em hex)
openssl rand -hex 32 > /etc/picsaude/pfx.key
export PFX_ENCRYPTION_KEY=$(cat /etc/picsaude/pfx.key)
```

`chave_eh_segura()` retorna `False` se a variável não está definida —
deploys de produção devem assertir `True` no startup.

## 10. Escopo futuro

- **PAdES-T** — carimbo de tempo via TSA (ITI publica timestamp servers)
- **PAdES-LT/LTA** — validação de longo prazo (OCSP/CRL embutido)
- **Cache de senha em sessão** — TTL curto + JWT criptografado
- **Co-assinatura** — segunda assinatura do farmacêutico no mesmo PDF
- **A3 via PKCS#11** — token USB
- **Frontend de upload** — UI para upload e gestão de certificados
- **Validação semântica** — verificar `extended_key_usage` (ex.: `id-kp-clientAuth` vs `id-kp-emailProtection`)
- **Rotação de PFX_ENCRYPTION_KEY** — script `scripts/rotate_pfx_key.py`

## 11. Arquivos criados/modificados

| Arquivo | Ação |
|---|---|
| [`app/domain/pdf_assinatura.py`](../../backend/app/domain/pdf_assinatura.py) | criar |
| [`app/domain/cofre_pfx.py`](../../backend/app/domain/cofre_pfx.py) | criar |
| [`app/models/prescritor_certificado.py`](../../backend/app/models/prescritor_certificado.py) | criar |
| [`app/models/__init__.py`](../../backend/app/models/__init__.py) | adicionar import |
| [`alembic/versions/e2e98a4780e4_ticket21_prescritor_certificados.py`](../../backend/alembic/versions/e2e98a4780e4_ticket21_prescritor_certificados.py) | criar |
| [`app/routers/prescritor.py`](../../backend/app/routers/prescritor.py) | criar (endpoint upload) |
| [`app/routers/receituarios.py`](../../backend/app/routers/receituarios.py) | adicionar endpoint /pdf-assinado |
| [`app/middleware/sensitive_body.py`](../../backend/app/middleware/sensitive_body.py) | criar |
| [`app/main.py`](../../backend/app/main.py) | incluir prescritor.router |
| [`tests/fixtures/certificado_teste.py`](../../backend/tests/fixtures/certificado_teste.py) | criar |
| [`tests/test_pdf_assinatura.py`](../../backend/tests/test_pdf_assinatura.py) | criar (11 unitários) |
| [`tests/integration/test_pdf_assinatura.py`](../../backend/tests/integration/test_pdf_assinatura.py) | criar (15 integração) |
| `requirements.txt` (futuro) | adicionar `pyhanko[pkcs12]>=0.33` |
