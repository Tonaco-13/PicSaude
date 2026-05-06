# RT-001 — Revisão pré-teste E2E com certificado ICP-Brasil A1 real

| Campo | Valor |
|---|---|
| **Status** | 🟡 OPEN — aguardando revisão |
| **Criado em** | 2026-05-04 |
| **Autor (implementador)** | Claude Opus (Cowork) |
| **Solicitante** | Fabiano Tonaco Borges |
| **Revisor convidado** | ChatGPT Teams |
| **Tópico** | Validar plano de teste E2E do PicSaúde com certificado A1 Serpro real, antes de proceder com 9 etapas (git init → GitHub → docs → instance_id → demo → Docker → Render → labels → E2E público) |
| **Bloqueia** | Etapas 1–9 do plano `PROJETO-PICSAUDE-OPUS.md` |

---

## TL;DR

Antes de versionar, publicar ou fazer deploy do PicSaúde, vamos rodar localmente um teste end-to-end com o certificado ICP-Brasil A1 real do Fabiano (Serpro e-CPF). Durante o levantamento descobri que: (1) `pyhanko` está sendo usado mas não declarado em `requirements.txt`; (2) há divergências entre o plano original e o estado atual do código; (3) o cert .pfx real está hoje dentro da pasta do workspace (risco de commit). Proponho fixes e plano de execução abaixo. **Pergunta central para o revisor:** o plano cobre os riscos relevantes? Há algum vetor de falha que estou subestimando?

---

## 1. Contexto curto

PicSaúde = sistema de prescrição digital com assinatura ICP-Brasil PAdES-B. Backend Python/FastAPI (146 testes, segundo o prompt original). Já existe pasta `backend/` funcional na máquina do Fabiano, sem repositório Git ainda. O plano original (em `docs/PROJETO-PICSAUDE-OPUS.md` e `backend/docs/PROMPT-OPUS-4.7.md`) é executar 9 etapas para ter:
- Repositório GitHub privado pronto para colaboração com 7 estudantes de extensão
- Modo demo público (URL acessível com cert autogerado)

O Fabiano pediu antes disso um teste E2E com **cert real** — para validar que o sistema funciona com cadeia ICP-Brasil completa antes de qualquer publicação.

## 2. Descobertas do levantamento

### 2.1 Estado do workspace (≠ plano original)
O projeto evoluiu além do prompt. O plano cita "Tickets 15, 16A, 17, 18, 19, 20, 21, 65, 66, 68". O código tem ainda:
- Tickets 14–17 (módulo Pedido de Exame completo)
- Tickets 19–21 (módulo Laudo)
- Ticket 26–27 (Farmácia Hospitalar — `dispensacao_hospitalar`, `prescricao_custodia` com `unidade_id`)
- Ticket 28–29 (Agendamento — `agendamentos`)
- G4A (`evento_publicacao` — Event Publishing Layer)
- G4B (`adapters/json_local`)
- IA farmacêutica (`ai/normalizacao_medicamento`, `ai/regras_farmaceuticas`, `ai/ia_farmaceutica`)
- IA documental (pasta `ai_documental/`)
- Frontends HTML completos: `cidadao.html`, `clinica.html`, `dispensador.html`, `prescritor.html`, `validar.html`, `index.html`

### 2.2 Stack real (≠ stack do prompt)
| Item | Prompt | Real |
|---|---|---|
| Banco | PostgreSQL 15+ produção / SQLite demo | SQLite (`PIX_SAUDE_DB=/data/picsaude.db`), via volume Docker. `pgdata/` existe mas é vestigial. |
| Python | 3.10 | Dockerfile usa **3.11-slim** |
| Bootstrap | manual (`pip install`, `pytest`) | `bootstrap.sh` automatizado (8 passos: deps, .env, secrets, build, migrate, admin, up, healthcheck) |
| Frontend | Cloudflare Pages estático | Servido pelo próprio backend (`http://localhost:8080/prescritor.html` etc.) |
| Compose | criar do zero | `docker-compose.yml` v3.9 já existe (1 service: `picsaude-backend`) |

### 2.3 Modelo de assinatura — duas camadas distintas
O código tem **duas** infraestruturas de assinatura, com objetivos diferentes:

**Camada 1 — Assinatura do payload canônico** (`prescricao_assinatura` table, `routers/assinaturas.py`):
- MVP: backend só armazena metadados declarados (tipo_certificado, emissor, hash, dados_b64). Comentário literal no código: *"Nenhuma validação criptográfica real é realizada. O status inicial é sempre 'assinatura_pendente'"*.
- Pós-MVP: validar `dados_assinatura_b64` contra AC raiz ICP-Brasil.

**Camada 2 — Assinatura PAdES-B do PDF** (`domain/pdf_assinatura.py`):
- Implementação **real** com pyHanko 0.34.x: `SimpleSigner.load_pkcs12_data` → `PdfSigner.sign_pdf` com `subfilter=PADES`, selo visual no rodapé (nome, CPF, CRM, data UTC, "ICP-Brasil"), validação de `KeyUsage.digitalSignature`.
- Não implementa: PAdES-T (timestamp via TSA), PAdES-LT/LTA (revogação OCSP/CRL embutida).

O teste E2E se concentra na **Camada 2** — é onde o `.pfx` real importa.

### 2.4 Bug crítico de instalação — `requirements.txt` incompleto
**Faltam declarações** para libs que o código importa:
| Lib | Onde é usada | Faltava |
|---|---|---|
| `pyhanko` | `domain/pdf_assinatura.py` (5 imports) | ❌ |
| `cryptography` | `domain/cofre_pfx.py`, `documento_canonico.py`, `pdf_assinatura.py` | ❌ (vinha transitivamente de `python-jose[cryptography]`) |
| `rapidfuzz` | `ai/lookup_def.py`, `ai/tuss_base.py`, `ai/base_cid.py` | ❌ |
| `pydantic` | Praticamente todos os routers | ❌ (transitiva de fastapi, mas API v2 explícita) |

**Diagnóstico:** os 146 testes passam localmente porque o venv do Fabiano tem essas libs instaladas manualmente. O Docker build vai quebrar no `import pyhanko`.

### 2.5 Arquivos sensíveis no workspace
- `Certificação Digital Cerpro/` — contém `.pfx` real do Fabiano (9,4 KB, A1 e-CPF Serpro), `CNH-e.pdf.pdf`, `certidao_quitacao_*.pdf`
- `picsaude_inpi.zip` (14 MB) — provável documentação INPI
- `pgdata/` — dados PostgreSQL local

Decidido com Fabiano: mover para `~/Desktop/PicSaude_PRIVATE/` antes do `git init`. O `.pfx` continua acessível pelo navegador (upload via UI, não montagem de volume).

## 3. Decisões tomadas (com rationale)

### 3.1 Raiz do repo Git: `PicSaude_Dev/` inteiro (não só `backend/`)
**Justificativa:** o projeto tem frontends HTML, docs, Dockerfile, docker-compose.yml todos no nível superior. Versionar só `backend/` deixaria 60% do projeto fora do controle de versão. O plano original assumiu uma separação backend/frontend que não existe na prática.

### 3.2 `requirements.txt` atualizado (commitless por enquanto)
Adicionado:
```
pyhanko==0.34.1         # pin exato — regulatório
cryptography>=43        # explícito (era transitivo via python-jose)
rapidfuzz>=3.5,<4       # IA farmacêutica
pydantic>=2.0,<3        # API v2 explícita
```
**Rationale dos pins:**
- `pyhanko==0.34.1`: pin exato porque é assinatura ICP-Brasil — qualquer break de API em patch release pode invalidar prescrições. Versão validada pelo prompt original.
- `cryptography>=43`: pyHanko 0.34 exige cryptography ≥41; deixei margem para patches de segurança (CVEs comuns).
- `rapidfuzz>=3.5,<4`: faixa permissiva com upper bound major. v3 é estável, v4 ainda não existe.
- `pydantic>=2.0,<3`: o código usa `field_validator` e `model_validator` (API v2). Sem upper bound, futuro pydantic 3 quebraria silenciosamente.

### 3.3 Tratamento dos arquivos sensíveis
Mover para `~/Desktop/PicSaude_PRIVATE/` (fora do workspace) **antes** de qualquer `git init` ou `git add`. Adicionar regras no `.gitignore`:
```gitignore
# Certificados ICP-Brasil
*.pfx
*.p12
*.pem
*.key
*.crt
*.cer
Certificação Digital*/
Certificacao Digital*/
# Documentos PI sensíveis
picsaude_inpi.zip
# Volume Postgres local
pgdata/
# pyHanko temp
*.sig
# PicSaúde local
.instance_id
```

### 3.4 Stack do teste E2E: Docker Compose via `bootstrap.sh`
**Recomendado.** Por quê:
- É o caminho documentado em `README_instalacao.md`
- Reproduz exatamente o que vai rodar no Render (Etapa 7)
- `bootstrap.sh` faz validação de pré-requisitos, geração de admin, healthcheck
- Single command: `./bootstrap.sh`

**Trade-off:** primeiro build leva ~5min baixando deps. Aceitável.

**Alternativa rejeitada:** uvicorn nativo sem Docker. Mais rápido para iterar, mas não reproduz o ambiente de produção e não revela bugs de empacotamento (que é justamente o que descobrimos com pyhanko).

### 3.5 Política de senhas/credenciais durante o teste
- Senha do `.pfx` é digitada **pelo Fabiano** no browser, nunca colada em chat ou stdin que o assistente leia.
- `PFX_ENCRYPTION_KEY` (cofre AES-256-GCM) gerada localmente com `python3 -c "import secrets; print(secrets.token_hex(32))"` e armazenada apenas em `.env` (gitignored).
- `PICSAUDE_JWT_SECRET` idem.
- `PICSAUDE_ADMIN_SENHA` inicial gerada como random 16-char e trocada no primeiro login.

## 4. Plano de execução proposto

### Fase A — Preparação (~5 min)
- A1. Mover sensíveis para `~/Desktop/PicSaude_PRIVATE/`
- A2. Validar Docker Desktop instalado e rodando
- A3. Confirmar que cópia do `.pfx` está num local acessível pelo navegador (Desktop ou Downloads)

### Fase B — Configurar instância local (~10 min)
- B1. `cp .env.example .env`
- B2. Gerar segredos com `python3 -c "import secrets; print(secrets.token_hex(32))"` (3x: JWT, PFX, admin)
- B3. Preencher `.env`:
  - `PICSAUDE_INSTANCE_ORG_ID=HOSPITAL-RECIFE-001`
  - `PICSAUDE_INSTANCE_NAME=Hospital São Lucas — Recife/PE`
  - `PICSAUDE_BASE_URL=http://localhost:8080`
  - `PICSAUDE_JWT_SECRET=<hex 64>`
  - `PFX_ENCRYPTION_KEY=<hex 64>` (esta var precisa ser adicionada ao `.env.example` se não estiver)
  - `PICSAUDE_ADMIN_EMAIL=fabianotonaco@gmail.com`
  - `PICSAUDE_ADMIN_NOME=Fabiano Tonaco Borges`
  - `PICSAUDE_ADMIN_SENHA=<random 16>`
- B4. `chmod +x bootstrap.sh && ./bootstrap.sh`
- B5. `curl http://localhost:8080/health` → 200

### Fase C — Setup do prescritor (~5 min)
- C1. Login `/index.html` ou `/prescritor.html` como admin
- C2. Cadastrar Fabiano como prescritor (CRM real, UF=PE, etc.)
- C3. Logout e login como prescritor
- C4. Upload do `.pfx` via UI — Fabiano digita senha pessoalmente
- C5. Verificar registro em `prescritor_certificado` (consulta DB no container)

### Fase D — Fluxo end-to-end (~15 min)
- D1. Cadastrar 1 paciente fictício (CPF gerado aleatório válido)
- D2. Criar prescrição (medicamento simples — dipirona 500mg, 1cp 6/6h, 5 dias)
- D3. `GET /prescricoes/{proto}/pdf` — gerar PDF
- D4. Endpoint de assinatura PAdES — Fabiano digita senha do .pfx
- D5. Validar no Adobe Reader (offline): selo visual + cadeia ICP-Brasil
- D6. `POST /custodia/transferir` — prescritor → paciente
- D7. Login como dispensador (criar dispensador antes via admin)
- D8. Apresentar token, dispensar parcialmente
- D9. `GET /eventos?protocolo=...` — verificar ledger (deve ter `prescricao_emitida`, `assinatura_registrada`, `custodia_transferida`, `dispensacao_parcial`)

### Fase E — Wrap up (~5 min)
- E1. Documentar resultados em `docs/review-tickets/RT-001-resultados.md`
- E2. Listar bugs/gotchas (se houver)
- E3. Decidir: prosseguir Etapa 1 (git init) ou consertar antes

**Total estimado:** ~40 min

## 5. Perguntas específicas para o revisor

1. **Versão do pyhanko:** `pyhanko==0.34.1` é a escolha certa? Há razão para considerar 0.27.x (LTS-ish) ou aguardar 0.35? O código usa apenas APIs estáveis (`SimpleSigner.load_pkcs12_data`, `PdfSigner`, `SigSeedSubFilter.PADES`).

2. **Falta cryptography como pin exato?** Coloquei `>=43`. Para regulatório ICP-Brasil, faz sentido pinar exato (ex.: `cryptography==44.0.0`)?

3. **Camada 1 vs Camada 2:** o teste só exercita a Camada 2 (PAdES-B do PDF). A Camada 1 (`prescricao_assinatura` como stub MVP) fica sem cobertura de teste com cert real. Aceitável para essa fase, ou queremos validar as duas?

4. **PAdES-T (timestamp) ausente:** uma assinatura PAdES-B sem timestamp tem validade jurídica plena segundo MP 2.200-2 / RDC 1.000? Ou seria melhor declarar limite (ex.: "válida até X dias após emissão") até a Camada T entrar em produção?

5. **Restrição clínica nula:** o teste vai gerar uma prescrição "real-shaped" (com meu CPF/CRM ICP-Brasil) mas para um paciente fictício. Algum risco regulatório nisso? (Não é prescrição clínica de fato; é teste técnico em ambiente local.)

6. **Custódia hospitalar (T26/T27):** o teste cobre fluxo ambulatorial. O fluxo hospitalar (`prescricao_custodia.unidade_id`) fica para depois?

7. **Ataque local v1/v2:** existem `ataque_local.py` e `ataque_local_v2.py` na raiz (decididos como "públicos / vão pro repo"). Quer fazer um sweep de segurança neles antes de tornar o repo público (mesmo privado, prudente)?

8. **Render free tier + SQLite:** o deploy futuro (Etapa 7) vai usar SQLite no Render. SQLite + Render free = banco volátil (filesystem reseta a cada redeploy). Aceitável para demo? Ou já mudar para Render Postgres add-on?

## 6. Anexos

### A. Diff do requirements.txt (antes vs agora)
```diff
- fastapi==0.128.8
- uvicorn[standard]==0.39.0
- python-jose[cryptography]==3.5.0
- passlib[bcrypt]==1.7.4
- python-multipart==0.0.20
- reportlab==4.4.10
- qrcode[pil]==8.2
- pillow==11.3.0
- sqlalchemy==2.0.41
- alembic>=1.13.0
- psycopg2-binary>=2.9.9
- httpx>=0.27.0
+ # ── Web framework ──────────────
+ fastapi==0.128.8
+ uvicorn[standard]==0.39.0
+ python-multipart==0.0.20
+ pydantic>=2.0,<3
+ # ── Auth ───────────────────────
+ python-jose[cryptography]==3.5.0
+ passlib[bcrypt]==1.7.4
+ # ── Banco e ORM ────────────────
+ sqlalchemy==2.0.41
+ alembic>=1.13.0
+ psycopg2-binary>=2.9.9
+ # ── HTTP client ────────────────
+ httpx>=0.27.0
+ # ── PDF: geração e assinatura ICP-Brasil ───
+ reportlab==4.4.10
+ qrcode[pil]==8.2
+ pillow==11.3.0
+ pyhanko==0.34.1            # ← NOVO
+ cryptography>=43           # ← explícito (era transitivo)
+ # ── IA farmacêutica ────────────
+ rapidfuzz>=3.5,<4          # ← NOVO
```

### B. Lista de imports externos do `backend/app/`
```
cryptography, fastapi, jose (python-jose), passlib, pydantic, pyhanko,
rapidfuzz, reportlab, sqlalchemy, starlette (transitivo), psycopg2, qrcode
```
Stdlib usados: `csv, unicodedata, dataclasses, datetime, hashlib, io, itertools, json, os, pathlib, re, secrets, sqlite3, typing, uuid, base64`.

### C. Endpoints relevantes para o teste
| Método | Rota | Fase do teste |
|---|---|---|
| `POST /auth/login` | autenticação | C1, C3, D7 |
| `POST /prescritores/` | cadastrar prescritor | C2 |
| `POST /prescritores/{id}/certificado` | upload .pfx | C4 |
| `POST /pacientes/` | cadastrar paciente | D1 |
| `POST /prescricoes/` | emitir prescrição digital | D2 |
| `GET /prescricoes/{proto}/pdf` | gerar PDF | D3 |
| **(endpoint de assinatura PAdES — confirmar nome real)** | assinar PDF | D4 |
| `POST /custodia/transferir` | transferir prescrição | D6 |
| `POST /tokens/` | apresentação no balcão | D8 |
| `POST /dispensacoes/` | registrar dispensação parcial | D8 |
| `GET /eventos?protocolo=...` | ledger | D9 |

> **Pendente:** confirmar nome do endpoint que dispara assinatura PAdES (linha D4) — o `routers/assinaturas.py` só registra metadados (Camada 1). O endpoint que invoca `pdf_assinatura.assinar_pdf_icp(...)` ainda precisa ser localizado. Suspeita: `routers/prescritor.py` ou `routers/receituarios.py` (ambos importam `cofre_pfx`).

---

## 7. Pedido ao revisor

Revisar este documento sob 3 lentes:
- **Técnica:** versões, APIs, choices de pin, gaps no plano
- **Regulatória:** PAdES-B sem timestamp, validade jurídica, RDC 1.000 / MP 2.200-2 / LGPD
- **De segurança:** vetor de exfiltração do .pfx durante teste, política de senhas, gitignore suficiente

Resposta esperada: **GO / NO-GO / GO-COM-AJUSTES** + comentários inline ou listados.

---

## 8. Revisão ChatGPT — Veredito + Ações tomadas

| Campo | Valor |
|---|---|
| **Data revisão** | 2026-05-04 |
| **Revisor** | ChatGPT Teams (multi-AI) |
| **Veredito** | 🟡 **GO-COM-AJUSTES** |
| **Status pós-ajustes** | 🟢 GO pleno (após correções abaixo) |

### 8.1 Ajustes obrigatórios — ✅ aplicados

#### 1. Endpoint de assinatura (lacuna real, bloqueador silencioso)
**Risco apontado:** sem o endpoint exato, fluxo trava no D4 ou usa endpoint errado (Camada 1).

**Resolução:** localizado em `app/routers/receituarios.py:1100`. Rota completa:
```
POST /prescricoes/{protocolo}/receituarios/{receituario_id}/pdf-assinado
```
- Body JSON: `{"senha_pfx": "<senha digitada pelo prescritor>"}`
- Retorno: PDF assinado (`Content-Type: application/pdf`)
- Ledger: evento `pdf_assinado_pades` registrado automaticamente
- Anti-logging middleware: `ROTAS_BODY_SENSIVEL` esconde a senha de logs (Ticket 21, seção 6)

**Mapa de endpoints D4 atualizado:**
| Fase | Método | Rota | Responsabilidade |
|---|---|---|---|
| D2 | POST | `/prescricoes` | Emitir prescrição digital |
| D2.1 | POST | `/prescricoes/{proto}/receituarios` | Criar receituário dentro da prescrição |
| D3 | GET | `/prescricoes/{proto}/pdf` | PDF não-assinado (preview) |
| D4 | **POST** | **`/prescricoes/{proto}/receituarios/{rid}/pdf-assinado`** | **Assinar PDF com .pfx (PAdES-B)** |

#### 2. `cryptography==44.0.0` (pin exato)
**Justificativa do revisor:** parsing PKCS#12 já quebrou em patches anteriores; assinatura regulatória exige reprodutibilidade > flexibilidade.

**Resolução:** `requirements.txt` atualizado:
```diff
- cryptography>=43        # ICP-Brasil (T20/T21)
+ cryptography==44.0.0    # Pin exato p/ ICP-Brasil (RT-001 review)
```

#### 3. Cadeia ICP-Brasil completa no CMS (validação Adobe Reader)
**Risco apontado:** se a cadeia não estiver embutida no CMS, o Adobe mostra:
- ❌ "cadeia não confiável" (apesar de cripto válida)
- ❌ "assinatura desconhecida"

**Análise do código atual (`pdf_assinatura.py:244-249`):**
```python
# other_certs é obrigatório nesta versão do pyHanko — passamos
# iterável vazio. A cadeia CA do .pfx é absorvida automaticamente
# pelo loader.
signer = signers.SimpleSigner.load_pkcs12_data(
    pfx_bytes,
    other_certs=(),
    passphrase=...,
)
```
O autor do Ticket 21 já considerou isso e confiou na auto-absorção do `load_pkcs12_data`. Para Serpro ICP-Brasil A1 típico (e-CPF), a cadeia geralmente **está embutida** no `.pfx`.

**Plano de contingência (se Adobe acusar cadeia):**
1. Inspecionar com `openssl pkcs12 -in arquivo.pfx -info -nokeys` quantos certs tem
2. Se só houver 1 (folha), baixar AC SERPROACF + AC SERPRO + ICP-Brasil (raiz) do site da Serpro
3. Passar como `other_certs=[ac_serproacf, ac_serpro, icp_raiz]` para `load_pkcs12_data`
4. Adicionar essa lógica como hotfix se necessário

**Decisão:** prosseguir com `other_certs=()` e validar no Adobe. Se falhar, hotfix conforme contingência. Resultado esperado para Serpro: cadeia completa, validação OK (apenas timestamp ausente, esperado).

### 8.2 Ajustes não-bloqueantes — 📝 incorporados ao plano

| Item revisor | Origem | Onde foi incorporado |
|---|---|---|
| Documentar limitação PAdES-B (sem timestamp) | §2.1 | README (Etapa 3) — seção "Limitações conhecidas" |
| Documentar volatilidade SQLite no Render | §2.3 | README (Etapa 3) — seção "Modo demo" |
| Sweep de segurança em `ataque_local*.py` | §1.7 | **Nova etapa antes da Etapa 2** (publicação no GitHub) |
| Cleanup do `.pfx` pós-teste | §1.4 | Fase E (E1.5) |
| CPF/CRM real só em ambiente local | §2.4 | Política do teste — PDF assinado **não sai** da máquina do Fabiano |

### 8.3 Pontos elogiados pelo revisor (manter)

- Separação Camada 1 (declarativa) vs Camada 2 (PAdES-B real) ✅
- Uso do `bootstrap.sh` como caminho oficial (reproduz produção) ✅
- Descoberta antecipada do bug de dependências ✅
- Tratamento prévio de arquivos sensíveis ✅
- Fluxo end-to-end completo (até dispensação + ledger) ✅

### 8.4 Respostas diretas às 8 perguntas

| # | Pergunta | Resposta do revisor |
|---|---|---|
| 1 | pyhanko 0.34.1? | ✅ correto manter |
| 2 | cryptography pin? | 🔧 ajustar para `==44.0.0` |
| 3 | Camada 1 vs 2? | ✅ só Camada 2 agora |
| 4 | PAdES-B sem timestamp tem validade? | ✅ válido com limitação documentada |
| 5 | CPF/CRM real local? | ✅ seguro |
| 6 | Custódia hospitalar? | ✅ pode ficar fora |
| 7 | `ataque_local*.py`? | ⚠️ revisar antes do GitHub |
| 8 | SQLite no Render? | ✅ aceitável p/ demo c/ aviso |

### 8.5 Status final do RT-001

🟢 **GO pleno após ajustes** — pode iniciar Fase A.
