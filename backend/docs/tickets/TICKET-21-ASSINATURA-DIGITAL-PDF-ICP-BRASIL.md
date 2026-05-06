# TICKET 21 — ASSINATURA DIGITAL ICP-BRASIL EMBUTIDA NO PDF

## Problema

Hoje o PicSaúde gera PDFs de receituários regulatórios via ReportLab, mas esses PDFs **não contêm assinatura digital embutida**. O documento é visualmente completo (cabeçalho, itens, QR code, hash de rastreabilidade), mas ao abrir no Adobe Reader ou outro validador, não aparece nenhum selo de assinatura digital.

A verificação criptográfica existe (Tickets 66–68) mas opera **fora do PDF** — valida o payload canônico da prescrição, não o documento final entregue à farmácia.

Para que o receituário digital tenha validade jurídica plena sob a RDC 1.000/2025 e a MP 2.200-2/2001, a assinatura ICP-Brasil precisa estar **embutida no próprio PDF** no padrão PAdES (PDF Advanced Electronic Signatures), verificável por qualquer leitor de PDF compatível.

## Validação prévia

O certificado real do prescritor (Fabiano Tonaco Borges, A1 Serpro/Cerpro, e-CPF) foi testado com sucesso em toda a pipeline existente:

- Carregamento de .pfx com senha ✓
- Extração de identidade (CPF `83086439149`, nome `FABIANO TONACO BORGES`) via OID 2.16.76.1.3.1 ✓
- Assinatura de payload canônico (RSA PKCS1v15 SHA-256) ✓
- Verificação criptográfica via `verificar_assinatura_icp()` ✓
- Certificado válido até 02/04/2027, emitido por AC SERPRORFBv5 ✓

O certificado é e-CPF (não e-Saúde), portanto o CRM não está no certificado — é resolvido pelo binding manual do Ticket 65.

## Objetivo

Embutir assinatura digital ICP-Brasil no PDF do receituário, no padrão PAdES-B (baseline), de modo que:

1. O Adobe Reader exiba "Assinado digitalmente por FABIANO TONACO BORGES"
2. A assinatura seja verificável criptograficamente offline (integridade + autoria); estado de revogação fica fora do escopo (requer PAdES-LT/LTA)
3. O selo visual apareça no rodapé do PDF com nome, CPF, data/hora e indicação ICP-Brasil
4. A cadeia de certificação (AC Raiz, AC intermediária, AC emissora) seja embutida para validação da cadeia de confiança

## Contexto técnico

### Padrão PAdES (ETSI EN 319 142)

PAdES é o padrão europeu/internacional para assinaturas digitais em PDF, adotado pelo ITI (Instituto Nacional de Tecnologia da Informação) como referência para ICP-Brasil. Níveis:

- **PAdES-B** (baseline): assinatura + certificado + cadeia. Suficiente para validação offline. **Este é o nível alvo do Ticket 21.**
- **PAdES-T** (timestamp): adiciona carimbo de tempo de uma TSA. Futuro.
- **PAdES-LT** (long-term): adiciona OCSP/CRL para validação de longo prazo. Futuro.
- **PAdES-LTA** (long-term archival): adiciona timestamp de arquivamento. Futuro.

### Biblioteca: pyHanko

pyHanko é a biblioteca Python mais madura para assinatura PAdES. Open-source (MIT), mantida ativamente, suporte completo a PAdES-B/T/LT/LTA, CAdES, e XAdES.

Vantagens sobre alternativas:
- **endesive**: abandonada (último commit 2022), bugs conhecidos com PAdES
- **PyPDF2 + cryptography manual**: não suporta PAdES nativamente, exige implementação manual de estruturas CMS/PKCS#7
- **pyHanko**: suporte nativo a PAdES, integração com `cryptography`, aceita .pfx/.p12 diretamente

```
pip install pyhanko[pkcs12]
```

### Fluxo atual do PDF

```
POST /gerar → gera receituários (metadata)
POST /numerar → obtém numeração SNCR
GET /pdf → gera PDF (ReportLab) → StreamingResponse(pdf_bytes)
```

O ponto de integração é um **novo endpoint** `POST /receituarios/{id}/pdf-assinado`: recebe a senha do .pfx no body JSON, gera o PDF com ReportLab, assina com pyHanko, registra evento no ledger, e retorna o PDF assinado.

### Dois artefatos assinados (distinção importante)

O PicSaúde mantém **dois níveis de assinatura** com finalidades distintas:

1. **Assinatura do payload canônico** (Tickets 66–68, existente): valida o objeto clínico — o ato da prescrição. Opera sobre o documento canônico determinístico (`documento_canonico.py`). É a prova de autoria e integridade da prescrição como ato médico.

2. **Assinatura PAdES do PDF** (este ticket): valida o documento regulatório — o artefato entregue à farmácia. Opera sobre os bytes do PDF gerado. É a prova de integridade do documento físico/digital apresentado para dispensação.

Ambas usam o mesmo certificado ICP-Brasil do prescritor, mas assinam objetos diferentes. A assinatura do payload canônico é registrada no banco (`prescricao_assinatura`); a assinatura PAdES é embutida no PDF e registrada como evento no ledger.

## Escopo

### ENTRA

- [ ] Módulo `app/domain/pdf_assinatura.py` — lógica de assinatura PAdES
- [ ] Função `assinar_pdf_icp(pdf_bytes, pfx_bytes, senha, metadata) -> bytes`
- [ ] Endpoint `POST /receituarios/{id}/pdf-assinado` — recebe senha no body JSON, retorna PDF assinado
- [ ] Selo visual de assinatura no rodapé do PDF (nome, CPF, data/hora, "ICP-Brasil")
- [ ] Cadeia de certificação embutida no PDF (AC Raiz + intermediárias do .pfx)
- [ ] Validação de `KeyUsage.digitalSignature` no upload do certificado
- [ ] Evento `pdf_assinado_pades` no ledger (`prescricao_eventos`) com hash do PDF, serial do certificado, hash DER do certificado, nível PAdES
- [ ] Tabela `prescritor_certificados` (separada de `prescritores`) com `ativo`, `revogado_em`, `substituido_em`, `hash_cert_der`, `serial`, `valido_ate`
- [ ] Endpoint `POST /prescritor/certificado` para upload seguro do .pfx (criptografado at rest)
- [ ] Middleware para garantir que o body do endpoint de assinatura nunca seja logado
- [ ] Testes unitários com certificado de teste autogerado
- [ ] Testes de integração com validação do PDF assinado
- [ ] Documentação do ticket

### NÃO ENTRA (futuros)

- PAdES-T (carimbo de tempo via TSA) — requer integração com servidor de timestamp
- PAdES-LT/LTA (validação de longo prazo com revogação embutida) — requer OCSP/CRL. PAdES-B resolve integridade e autoria, mas não substitui PAdES-LT/LTA para prova robusta de longo prazo.
- Assinatura gov.br (assinatura em nuvem) — arquitetura diferente (API REST)
- Assinatura A3 via PKCS#11 (token USB) — requer driver nativo
- Múltiplas assinaturas no mesmo PDF (co-assinatura farmacêutico)
- Revogação de assinatura
- Interface de upload de certificado no frontend
- Versionamento de re-assinatura — definir qual assinatura é a "vigente" quando o mesmo receituário é re-assinado (hoje cada re-assinatura gera evento no ledger com hash distinto; falta campo `assinatura_vigente` ou convenção de que a última é sempre a oficial)
- Logging de KeyUsage ausente — quando o certificado não possui `KeyUsage.digitalSignature` (aceito por compatibilidade com certs legados), registrar `certificado_keyusage_ausente=True` no evento do ledger para rastreabilidade

## Design

### Módulo `pdf_assinatura.py`

```python
from pyhanko.sign import signers, fields
from pyhanko.sign.general import load_cert_list_from_pemder
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from cryptography.hazmat.primitives.serialization import pkcs12

@dataclass(frozen=True)
class MetadataAssinatura:
    nome_prescritor: str
    cpf_prescritor: str
    crm_prescritor: str | None
    uf_prescritor: str | None
    razao: str = "Prescrição médica digital"
    localizacao: str | None = None  # ex.: "Recife-PE"

def assinar_pdf_icp(
    pdf_bytes: bytes,
    pfx_bytes: bytes,
    senha: str,
    metadata: MetadataAssinatura,
) -> bytes:
    """
    Assina PDF com certificado ICP-Brasil A1 no padrão PAdES-B.
    
    1. Carrega .pfx (chave privada + certificado + cadeia CA)
    2. Configura campo de assinatura visual no rodapé
    3. Assina com pyHanko (PAdES-B, SHA-256, RSA PKCS1v15)
    4. Retorna PDF assinado como bytes
    
    A cadeia de certificação (AC Raiz → AC intermediária → AC emissora)
    é extraída do .pfx e embutida no PDF para validação offline.
    """
    ...
```

### Selo visual de assinatura

O selo aparece no rodapé da última página do PDF, abaixo do QR code existente:

```
┌──────────────────────────────────────────────┐
│  ✎ Assinado digitalmente por:                │
│    FABIANO TONACO BORGES                     │
│    CPF: 830.864.391-49                       │
│    CRM-PE 22.847                             │
│    Data: 29/04/2026 15:45:32 -03:00          │
│    Certificado ICP-Brasil A1                 │
│    AC: Autoridade Certificadora SERPRORFBv5  │
└──────────────────────────────────────────────┘
```

Dimensões: ~170mm × 25mm, posicionado 15mm acima da margem inferior.

### Armazenamento do certificado

O .pfx do prescritor **não pode ser armazenado em texto claro**. O armazenamento usa uma **tabela dedicada** `prescritor_certificados`, separada de `prescritores`, para permitir histórico de certificados (renovação, revogação, substituição) sem poluir a tabela principal:

```sql
CREATE TABLE prescritor_certificados (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prescritor_id   UUID NOT NULL REFERENCES prescritores(id),
    pfx_cifrado     BYTEA NOT NULL,          -- .pfx criptografado com AES-256-GCM
    pfx_iv          BYTEA NOT NULL,           -- IV do AES-GCM (12 bytes)
    pfx_tag         BYTEA NOT NULL,           -- tag de autenticação (16 bytes)
    hash_cert_der   VARCHAR(64) NOT NULL,     -- SHA-256 do certificado em DER (fingerprint único)
    serial          VARCHAR(100) NOT NULL,    -- serial do certificado X.509
    valido_ate      TIMESTAMP NOT NULL,       -- validade do certificado
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,   -- apenas um ativo por prescritor
    revogado_em     TIMESTAMP,               -- se revogado pelo prescritor
    substituido_em  TIMESTAMP,               -- se substituído por upload de novo certificado
    uploaded_em     TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (prescritor_id, hash_cert_der)    -- impede upload duplicado do mesmo certificado
);

CREATE INDEX idx_prescritor_cert_ativo ON prescritor_certificados (prescritor_id) WHERE ativo = TRUE;
```

Quando o prescritor faz upload de um novo certificado, o anterior é marcado como `ativo = FALSE` e `substituido_em = now()`. Isso preserva o histórico para auditoria e permite vincular cada PDF assinado ao certificado que o assinou (via `hash_cert_der` no evento do ledger).

A chave de criptografia (`PFX_ENCRYPTION_KEY`) é uma variável de ambiente, nunca persistida no banco. O .pfx é descriptografado apenas no momento da assinatura, em memória, e imediatamente descartado.

Endpoint de upload:

```
POST /prescritor/certificado
Content-Type: multipart/form-data
Body: pfx_file + senha

→ 201 Created
{
    "serial": "48383745601936963188073072312",
    "nome_certificado": "FABIANO TONACO BORGES",
    "cpf_certificado": "83086439149",
    "valido_ate": "2027-04-02T21:02:58Z",
    "emitido_por": "AC SERPRORFBv5",
    "hash_cert_der": "a1b2c3d4..."
}
```

O endpoint:
1. Carrega o .pfx com a senha fornecida (valida que a senha está correta)
2. Extrai metadados do certificado (serial, nome, CPF, validade, emissor)
3. Calcula `hash_cert_der` — SHA-256 dos bytes DER do certificado (fingerprint único e imutável)
4. **Valida `KeyUsage.digitalSignature`** — rejeita certificados que não tenham a extensão KeyUsage com o bit `digitalSignature` ativo (ex.: certificados emitidos exclusivamente para autenticação ou criptografia). Retorna 422 com detalhe `"Certificado não possui KeyUsage.digitalSignature"`
5. Valida identidade contra o cadastro do prescritor (CPF deve bater)
6. Se já existe certificado ativo, marca-o como `ativo = FALSE, substituido_em = now()`
7. Criptografa o .pfx com AES-256-GCM
8. Persiste os bytes cifrados + IV + tag + hash_cert_der + serial + valido_ate no banco
9. **Não persiste a senha** — o prescritor fornece a senha a cada sessão

### Fluxo de assinatura no endpoint `POST /receituarios/{id}/pdf-assinado`

O endpoint de PDF assinado é **separado** do `GET /pdf` existente. Isso evita poluir o endpoint de visualização com lógica de criptografia e garante que a senha nunca viaje em header (onde pode ser logada por proxies/load balancers).

```
POST /receituarios/{id}/pdf-assinado
Content-Type: application/json
Body: { "senha_pfx": "..." }

  │
  ├─ assinatura_modo != "icp_brasil_local" → 409 Conflict (receituário não usa ICP-Brasil)
  │
  └─ assinatura_modo == "icp_brasil_local"
       │
       ├─ prescritor sem certificado ativo → 422 Unprocessable Entity
       │                                      (detalhe: "Nenhum certificado ativo encontrado")
       │
       ├─ senha_pfx ausente no body → 422 Unprocessable Entity
       │
       └─ senha_pfx fornecida
            │
            ├─ descriptografa .pfx → carrega com senha → gera PDF → assina → registra evento no ledger → retorna PDF assinado
            │
            └─ senha inválida → 401 Unauthorized (detalhe: "Senha do certificado inválida")
```

A senha do .pfx é passada no **body JSON** (não em header), em request `POST` com HTTPS obrigatório. O body deste endpoint **nunca deve ser logado** — um middleware dedicado deve excluir esta rota do request logging.

O endpoint `GET /pdf` existente continua funcionando normalmente para visualização do PDF sem assinatura digital.

### Middleware anti-logging

O endpoint `POST /receituarios/{id}/pdf-assinado` carrega a senha do certificado no body. Para garantir que a senha nunca apareça em logs de acesso, request logs, ou ferramentas de observabilidade:

```python
# Lista de rotas cujo body não deve ser logado
ROTAS_BODY_SENSIVEL = {"/receituarios/{id}/pdf-assinado"}

# No middleware de logging, verificar se a rota está na lista
# antes de serializar o body para o log.
```

### Alternativa: senha em sessão

Para evitar pedir a senha a cada PDF, uma alternativa é armazenar a senha em sessão (JWT claim criptografado ou cache Redis com TTL curto). Decisão adiada para fase 2 — na fase 1, a senha é por request.

## Testes

### Unitários (sem banco)
1. `test_assinar_pdf_basico` — gera PDF com ReportLab, assina, verifica que o resultado é PDF válido
2. `test_assinar_pdf_selo_visual` — verifica presença do selo de assinatura no PDF
3. `test_assinar_pdf_cadeia_embutida` — verifica que certificados CA estão no PDF
4. `test_assinar_pdf_senha_invalida` — senha errada levanta erro claro
5. `test_assinar_pdf_certificado_expirado` — certificado vencido gera alerta mas não bloqueia (decisão do endpoint)
6. `test_metadata_assinatura_campos` — validação dos campos obrigatórios

### Integração (com PostgreSQL)
7. `test_upload_certificado_prescritor` — POST /prescritor/certificado com .pfx de teste
8. `test_upload_certificado_cpf_divergente` — CPF do certificado != CPF do prescritor → 422
9. `test_pdf_assinado_endpoint` — POST /receituarios/{id}/pdf-assinado com certificado e senha retorna PDF assinado
10. `test_pdf_assinado_sem_certificado` — POST sem certificado ativo → 422
11. `test_pdf_assinado_senha_ausente` — POST sem senha_pfx no body → 422
12. `test_pdf_assinado_senha_invalida` — POST com senha errada → 401
13. `test_pdf_assinado_validavel` — PDF assinado é validável via pyHanko.validate
14. `test_pdf_assinado_evento_ledger` — verifica que evento `pdf_assinado_pades` foi registrado com hash_pdf, serial, hash_cert_der
15. `test_upload_certificado_sem_keyusage` — certificado sem KeyUsage.digitalSignature → 422

### Certificado de teste
Para testes automatizados, gerar um certificado autoassinado com a `cryptography` library:

```python
def gerar_certificado_teste() -> tuple[bytes, str]:
    """Gera .pfx autoassinado para testes. Retorna (pfx_bytes, senha)."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    import datetime

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "TESTE PICSAUDE:00000000000"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "ICP-Brasil"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "BR"),
    ])
    cert = (x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256()))
    
    senha = "teste123"
    pfx = serialization.pkcs12.serialize_key_and_certificates(
        b"teste", key, cert, None,
        serialization.BestAvailableEncryption(senha.encode()),
    )
    return pfx, senha
```

## Riscos e mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|:------------:|:-------:|-----------|
| pyHanko incompatível com versão do ReportLab | Baixa | Alto | pyHanko opera em PDF bytes já gerados — não depende do ReportLab internamente. Testar com versão atual antes de mergear. |
| Certificado e-CPF não aceito como assinatura médica | Média | Alto | RDC 1.000/2025 aceita qualquer certificado ICP-Brasil (A1/A3). O CRM é vinculado pelo binding do Ticket 65, não pelo certificado em si. Documentar fundamentação regulatória. |
| Senha do .pfx interceptada em trânsito | Baixa | Crítico | HTTPS obrigatório. Senha viaja no body JSON (não em header), e o middleware anti-logging exclui a rota do request log. Considerar migração para sessão criptografada na fase 2. |
| .pfx cifrado no banco com chave comprometida | Baixa | Crítico | `PFX_ENCRYPTION_KEY` é variável de ambiente, nunca no código. Rotação de chave possível (re-criptografar com nova chave). |
| Validação Adobe Reader falha com AC Serpro | Baixa | Médio | Embutir cadeia completa (AC Raiz ICP-Brasil v5 → AC Serpro). Adobe Reader reconhece ACs ICP-Brasil desde 2019 (AATL). |

## Dependências

- **Ticket 66** (concluído): parsing de identidade ICP-Brasil — `parsear_certificado_icp()`
- **Ticket 68** (concluído): verificação criptográfica — `verificar_assinatura_icp()`
- **Ticket 65** (concluído): binding de conselho (CRM) — necessário para o selo visual
- **Ticket 17** (concluído): PDF de receituário — base para embutir assinatura
- **pyHanko**: nova dependência (`pip install pyhanko[pkcs12]`)

## Decisões de design

1. **PAdES-B na fase 1.** Suficiente para validação offline no Adobe Reader. Carimbo de tempo (PAdES-T) e validação de longo prazo (PAdES-LT) ficam para tickets futuros — requerem integração com TSA e OCSP/CRL respectivamente.

2. **Senha por request, não por sessão.** Mais seguro na fase 1. A UX é inferior (pedir senha a cada PDF), mas o risco de armazenar a senha em sessão é eliminado. Fase 2 avaliará cache em memória com TTL.

3. **.pfx criptografado no banco, não no filesystem.** Evita problemas de permissão de arquivo, backup, e escala horizontal. O banco já é backupeado; a chave de criptografia é separada.

4. **Assinatura é opt-in.** PDFs continuam sendo gerados sem assinatura quando `assinatura_modo != "icp_brasil_local"` ou quando o prescritor não tem certificado cadastrado. Não há bloqueio.

5. **Selo visual + assinatura invisível.** O PDF contém tanto a assinatura PAdES (invisível, verificável pelo leitor) quanto o selo visual (visível, informativo para humanos). São camadas complementares.

6. **KeyUsage flexível com rastreabilidade.** Certificados sem `KeyUsage.digitalSignature` são aceitos (compatibilidade com certs ICP-Brasil legados), mas o evento no ledger deve registrar `certificado_keyusage_ausente=True` para auditoria futura. (Revisão ChatGPT — ponto de atenção #3.)

7. **Re-assinatura permitida, última prevalece.** O mesmo receituário pode ser re-assinado (ex.: certificado renovado). Cada assinatura gera evento distinto no ledger com hash próprio. Convenção: a última assinatura é a vigente. Versionamento explícito (campo `assinatura_vigente`) fica para iteração futura. (Revisão ChatGPT — ponto de atenção #2.)

## Revisão externa

Ticket revisado e aprovado pelo ChatGPT (GPT-4o). Pontos fortes destacados: separação GET /pdf vs POST /pdf-assinado, cofre AES-256-GCM, uso correto do pyHanko (SimpleSigner + cadeia embutida), ledger com hash+serial+hash_cert_der, e anti-logging. Pontos de atenção (4) incorporados como decisões de design (#6, #7) e itens futuros na seção NÃO ENTRA (versionamento de re-assinatura, logging de KeyUsage ausente). Recomendação de acelerar Fase C (certificado real) acatada.

## Cadência de execução

**Fase A** (assinatura core): módulo `pdf_assinatura.py` + função `assinar_pdf_icp()` + testes unitários com certificado autogerado.

**Fase B** (integração): endpoint de upload do .pfx (com validação KeyUsage) + tabela `prescritor_certificados` + endpoint `POST /receituarios/{id}/pdf-assinado` + middleware anti-logging + testes de integração.

**Fase C** (validação real): testar com certificado real do Fabiano + validar no Adobe Reader + ajustar selo visual.

## Arquivos a criar/modificar

| Arquivo | Ação |
|---------|------|
| `app/domain/pdf_assinatura.py` | CRIAR — lógica de assinatura PAdES com pyHanko |
| `app/routers/prescritor.py` | MODIFICAR — endpoint POST /prescritor/certificado |
| `app/routers/receituarios.py` | MODIFICAR — novo endpoint POST /receituarios/{id}/pdf-assinado |
| `app/models/prescritor_certificado.py` | CRIAR — modelo prescritor_certificados |
| `app/middleware/sensitive_body.py` | CRIAR — middleware anti-logging para rotas sensíveis |
| `alembic/versions/xxxx_ticket21_prescritor_certificados.py` | CRIAR — migration (CREATE TABLE) |
| `tests/integration/test_pdf_assinatura.py` | CRIAR — testes |
| `tests/fixtures/certificado_teste.py` | CRIAR — gerador de .pfx para testes |
| `docs/tickets/TICKET-21-ASSINATURA-DIGITAL-PDF-ICP-BRASIL.md` | CRIAR — esta documentação |
