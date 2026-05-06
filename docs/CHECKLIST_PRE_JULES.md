# CHECKLIST PRÉ-JULES — PicSaúde

## Objetivo
Validar se o PicSaúde está pronto para entrar em teste pesado com Jules, com foco em:
- integridade
- criptografia
- rastreabilidade
- robustez
- separação correta entre fluxo físico e digital

---

## 1. Fluxo físico vs digital

### 1.1 Fluxo físico
- [ ] Emissão física funciona sem `cert_pem`
- [ ] Emissão física funciona sem `assinatura_b64`
- [ ] `string_validacao_prescritor` fica `NULL`
- [ ] Ledger registra `validacao_prescritor = NAO_REALIZADA`
- [ ] Nenhuma etapa ICP é executada no fluxo físico

### 1.2 Fluxo digital
- [ ] `cert_pem` e `assinatura_b64` são obrigatórios juntos
- [ ] Assinatura é validada antes da geração da string
- [ ] Certificado é validado temporalmente
- [ ] String de validação só é gerada quando a assinatura for válida
- [ ] Ledger registra os dados da validação digital

### 1.3 Anomalias bloqueadas (Ticket 68A)
- [ ] `cert_pem` sem `assinatura_b64` retorna 422
- [ ] `assinatura_b64` sem `cert_pem` retorna 422
- [ ] Nada é persistido nesses cenários

---

## 2. Identidade do prescritor

### 2.1 Certificado (Ticket 66)
- [ ] CPF é extraído corretamente via OID 2.16.76.1.3.1 (offset 9–19, DOC-ICP-04.4)
- [ ] Nome é extraído corretamente do CN
- [ ] CRM/CRO + UF são extraídos quando presentes no OU
- [ ] Fallback manual só pede conselho, nunca CPF ou nome

### 2.2 NomeValidator (Ticket 64)
- [ ] Variações reais brasileiras passam (Luiz/Luis, Thiago/Tiago, acentos)
- [ ] Nomes divergentes são classificados sem bloquear o fluxo automaticamente
- [ ] Status de coerência fica auditável (COERENTE_FORTE / COERENTE_PARCIAL / DIVERGENTE)

### 2.3 Pipeline institucional (Ticket 65)
- [ ] Integração com CNES funciona (busca por número de conselho)
- [ ] Integração com CFM/CFO (ou provider mock) funciona
- [ ] Múltiplos vínculos CNES retornam `multiplo_vinculo` sem escolha por heurística
- [ ] Nenhum vínculo é escolhido sem critério forte

---

## 3. Evidência auditável

### 3.1 String de validação (Ticket 67)
- [ ] String é gerada no momento da emissão (não no login)
- [ ] Formato canônico: `CPF|CONSELHO|CNS|STATUS_NOME|HASH_CERT|TIMESTAMP`
- [ ] Hash do certificado é baseado em DER (não no PEM cru)
- [ ] PEM com `\n` e `\r\n` gera o mesmo hash DER
- [ ] Nome divergente pode gerar string com `DIVERGENTE` sem bloquear emissão
- [ ] String `NULL` quando emissão física (sem ICP)

### 3.2 Ledger
- [ ] `prescricao_emitida` contém `string_validacao` quando houver ICP válido
- [ ] `prescricao_emitida` contém `verificacao_assinatura_icp` no fluxo digital
- [ ] Emissão física registra `validacao_prescritor = NAO_REALIZADA`
- [ ] Tabelas de eventos seguem INSERT-only (sem UPDATE, sem DELETE)
- [ ] Triggers de imutabilidade continuam ativas (`prevent_update_*`, `prevent_delete_*`)

---

## 4. Infraestrutura mínima

### 4.1 Banco
- [ ] Triggers de UPDATE/DELETE bloqueado seguem funcionando
- [ ] Alterações de schema foram aplicadas de forma idempotente (`init_tables.py`)
- [ ] Coluna `string_validacao_prescritor` presente em `prescricoes`

### 4.2 Frontend/Backend
- [ ] Não há URLs hardcoded restantes
- [ ] `config.js` funciona em `file://`
- [ ] `config.js` funciona em localhost
- [ ] `config.js` funciona em mesmo domínio

### 4.3 Segurança básica
- [ ] Rate limiting está ativo
- [ ] `X-Forwarded-For` está sendo usado corretamente
- [ ] Não há vazamento de memória no rate limiter
- [ ] Endpoints críticos retornam 429 corretamente

---

## 5. Testes

### 5.1 Criptografia (Ticket 68)
- [ ] Assinatura válida → `valida=True`
- [ ] Payload alterado → `assinatura_invalida`
- [ ] Cert incompatível → `assinatura_invalida`
- [ ] Cert expirado → `certificado_expirado` (assinatura matematicamente ok)
- [ ] Cert não ativo → `certificado_nao_ativo`
- [ ] Base64 inválido → `base64_invalido`
- [ ] Prehashed alinhado com WebCrypto

### 5.2 Parsing X.509 (Ticket 66)
- [ ] CPF via OID extraído corretamente
- [ ] CN extraído corretamente
- [ ] CRM/CRO via OU (variações: espaço, hífen, ponto, lowercase)
- [ ] PEM inválido → `parseable=False` sem exceção

### 5.3 String de validação (Ticket 67)
- [ ] Geração básica correta
- [ ] Hash DER consistente entre chamadas
- [ ] PEM CRLF vs LF → mesmo hash
- [ ] Status_nome normalizado corretamente

### 5.4 Não regressão
- [ ] Suite completa está verde (214+ testes)
- [ ] Fluxo físico continua funcionando
- [ ] Fluxo digital continua funcionando
- [ ] Cenário B (par incompleto) retorna 422

---

## 6. Alvos do Jules

Jules deve atacar primeiro:

- [ ] Concorrência na emissão digital (race condition no INSERT)
- [ ] Alteração do payload após assinatura (verify deve rejeitar)
- [ ] Brute force de token OTP
- [ ] Flood em `/auth/token`
- [ ] Nomes divergentes com CPF válido (classificar, não bloquear)
- [ ] Múltiplos vínculos CNES (não escolher sem critério forte)
- [ ] Combinações inválidas de `cert_pem` e `assinatura_b64` (Cenário B)
- [ ] Serialização determinística sob repetição (sort_keys)
- [ ] Certificado expirado com assinatura matematicamente válida
- [ ] PEM com quebras de linha diferentes (CRLF vs LF)

---

## Decisão final

### Pré-requisitos obrigatórios

- [ ] Fluxo físico íntegro
- [ ] Fluxo digital íntegro
- [ ] Cenário B bloqueado (422)
- [ ] Ledger imutável
- [ ] String auditável correta
- [ ] Assinatura ICP válida
- [ ] Rate limiting ativo
- [ ] Suite verde (zero falhas)

## Se todos marcados:

**Pode chamar Jules para teste pesado.**
