# G5 — Empacotamento e Distribuição do PicSaúde

**Classificação:** `docs` — arquitetura de distribuição; sem impacto em código executável neste ticket.
**Pré-requisito:** Núcleo sanitário formalizado, G4A (publicação de eventos), 307/307 testes passando.

---

## 1. Modelo de distribuição

### Decisão

O PicSaúde é distribuído como **pacote híbrido**:

```
containers Docker  +  arquivos de configuração  +  scripts de bootstrap
```

| Camada | O que é | Justificativa |
|---|---|---|
| Container Docker | Backend FastAPI + dependências Python | Reprodutibilidade total; elimina conflitos de ambiente |
| Frontend estático | Arquivos HTML/JS servidos pelo Nginx ou diretamente | Sem build; portável; editável localmente |
| SQLite em volume | Banco de dados persistente no host | Sem servidor externo; baixo atrito; backup trivial |
| `.env` | Configuração específica da instalação | Separação entre código e segredos |
| `bootstrap.sh` | Inicialização da instância | Fluxo reproduzível e auditável |

### O que um parceiro homologado recebe

```
picsaude-distribuicao/
├── docker-compose.yml          ← orquestração local completa
├── .env.example                ← template de configuração
├── bootstrap.sh                ← script de inicialização
├── healthcheck.sh              ← verificação de sanidade
├── README_instalacao.md        ← guia de 5 passos
└── docs/
    └── GOVERNANCA_INSTALACAO.md ← limites de customização
```

O parceiro **não recebe** o código-fonte do núcleo como requisito de operação — apenas as imagens Docker publicadas e os artefatos de configuração acima. O código-fonte permanece disponível para auditoria e contribuição, mas não é necessário para operar.

### Unidade mínima de implantação

Uma instância PicSaúde operacional mínima consiste em:

```
1 container backend  +  1 volume SQLite  +  1 arquivo .env  +  frontends estáticos
```

Sem load balancer, sem banco externo, sem broker de mensagens. Tudo o que for necessário para operação primária reside nesses 4 elementos.

---

## 2. Stack mínima distribuível

### Obrigatório

| Componente | Tecnologia | Notas |
|---|---|---|
| Backend API | FastAPI (Python 3.11+) em container | Porta `8000` interna, `8080` externa |
| Banco de dados | SQLite em volume persistente | Arquivo único; backup = cópia do arquivo |
| Frontends | HTML estático servido pelo backend ou Nginx | `prescritor.html`, `dispensador.html`, `cidadao.html` |
| Configuração | `.env` por ambiente | Nunca comitado; template em `.env.example` |
| Bootstrap | `bootstrap.sh` | Executado uma vez na primeira implantação |

### Opcional (ativável por configuração)

| Componente | Quando ativar | Variável `.env` |
|---|---|---|
| Nginx reverso | Múltiplos frontends ou HTTPS local | `PICSAUDE_SERVE_STATIC=nginx` |
| Backup agendado | Produção local com risco de perda | `PICSAUDE_BACKUP_CRON=0 2 * * *` |
| Outbox polling ativo | Adapter externo em operação | `PICSAUDE_OUTBOX_ENABLED=true` |

### Evitar nesta fase

- PostgreSQL como banco principal — SQLite é suficiente para MVP distribuído; migração para Postgres é ticket separado (G6)
- Redis, Kafka, RabbitMQ — sem caso de uso real ainda
- Kubernetes / Helm — overhead operacional sem ganho no perfil atual de parceiros
- Múltiplas réplicas de backend — SQLite não suporta write concurrency; resolver antes de escalar horizontalmente
- Secrets Manager externo (Vault, AWS Secrets) — overkill para instalações locais

---

## 3. Inventário de artefatos

### Artefatos de implantação

| Artefato | Função | Status no G5 |
|---|---|---|
| `Dockerfile` | Imagem do backend | Definir neste ticket → implementar no ticket técnico |
| `docker-compose.yml` | Stack completa local | Definir neste ticket → implementar no ticket técnico |
| `.env.example` | Template de configuração | Definir neste ticket → implementar no ticket técnico |
| `bootstrap.sh` | Inicialização da instância | Definir neste ticket → implementar no ticket técnico |
| `healthcheck.sh` | Verificação de sanidade externa | Definir neste ticket → implementar no ticket técnico |
| `README_instalacao.md` | Guia do operador | Definir neste ticket → implementar no ticket técnico |

### Artefatos de governança (já existentes)

| Artefato | Localização | Papel |
|---|---|---|
| `CLAUDE.md` | Raiz | Princípios invioláveis do núcleo |
| `NUCLEO_SANITARIO.md` | `docs/` | Contrato de objetos sanitários |
| `ARQUITETURA_G4A.md` | `docs/` | Contrato da camada de publicação |
| `picsaude_ddl_postgres_v1.sql` | `docs/` | Referência de schema para auditores |

---

## 4. Dockerfile (especificação)

```dockerfile
# Imagem de referência — implementar no ticket técnico
FROM python:3.11-slim

WORKDIR /app

# Dependências primeiro (cache de layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código
COPY backend/ .

# Banco em volume externo — nunca dentro da imagem
ENV PIX_SAUDE_DB=/data/picsaude.db

# Health check embutido
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Invariantes do Dockerfile:**
- Banco NUNCA dentro da imagem — sempre em volume externo
- Imagem deve ser idempotente — reconstrução não perde dados
- Versão Python fixada (`3.11-slim`, não `latest`)

---

## 5. docker-compose.yml (especificação)

```yaml
# Especificação — implementar no ticket técnico
version: "3.9"

services:
  backend:
    image: picsaude/backend:${PICSAUDE_VERSION:-latest}
    # ou: build: ./  (para desenvolvimento)
    ports:
      - "${PICSAUDE_PORT:-8080}:8000"
    volumes:
      - picsaude_data:/data          # banco persistente
      - ./frontend:/app/static:ro    # frontends estáticos (opcional)
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  picsaude_data:
    driver: local
    # Para bind mount explícito em produção local:
    # driver_opts:
    #   type: none
    #   o: bind
    #   device: /srv/picsaude/data
```

---

## 6. .env.example (especificação)

```bash
# ─────────────────────────────────────────────────────────
# PicSaúde — Configuração de instância
# Copie para .env e preencha antes de executar bootstrap.sh
# NUNCA commite o .env em repositório de código
# ─────────────────────────────────────────────────────────

# Identificação da instância
PICSAUDE_VERSION=1.0.0
PICSAUDE_INSTANCE_NAME=Universidade Federal de Exemplo
PICSAUDE_INSTANCE_ORG_ID=UFE-001          # org_id desta instalação (usado em escopo institucional)

# Banco de dados
PIX_SAUDE_DB=/data/picsaude.db            # caminho interno ao container

# Servidor
PICSAUDE_PORT=8080                        # porta exposta ao host
PICSAUDE_BASE_URL=http://localhost:8080   # URL base pública (para QR codes, PDFs)

# Segurança
PICSAUDE_SECRET_KEY=TROCAR_POR_CHAVE_ALEATORIA_256_BITS
PICSAUDE_JWT_EXPIRY_MINUTES=60

# Admin inicial (criado pelo bootstrap.sh — mudar senha após primeiro login)
PICSAUDE_ADMIN_CPF=00000000001
PICSAUDE_ADMIN_NOME=Administrador
PICSAUDE_ADMIN_SENHA_INICIAL=TROCAR_IMEDIATAMENTE

# Ambiente (dev | hml | prod)
PICSAUDE_ENV=prod

# Outbox (G4A)
PICSAUDE_OUTBOX_ENABLED=true

# Backup (opcional)
PICSAUDE_BACKUP_DIR=/data/backups
# PICSAUDE_BACKUP_CRON=0 2 * * *         # descomente para ativar backup agendado
```

---

## 7. Bootstrap mínimo

### Objetivo

Transformar um ambiente limpo em uma instância PicSaúde operacional em menos de 5 minutos, de forma reproduzível.

### Fluxo do `bootstrap.sh`

```
bootstrap.sh
│
├── [1] Validar pré-requisitos
│     ├── Docker instalado e acessível
│     ├── docker-compose disponível
│     └── arquivo .env presente (não .env.example)
│
├── [2] Validar variáveis obrigatórias do .env
│     ├── PICSAUDE_SECRET_KEY (não pode ser o exemplo)
│     ├── PICSAUDE_ADMIN_SENHA_INICIAL (não pode ser o exemplo)
│     ├── PICSAUDE_BASE_URL
│     └── PICSAUDE_INSTANCE_ORG_ID
│
├── [3] Criar estrutura de diretórios
│     ├── /data/               ← volume do banco
│     └── /data/backups/       ← diretório de backup
│
├── [4] Inicializar banco de dados
│     └── docker run --rm ... python3 init_tables.py
│         → cria todas as tabelas (idempotente)
│         → confirma tabelas obrigatórias presentes
│
├── [5] Criar admin inicial
│     └── docker run --rm ... python3 create_admin.py
│         → só cria se não existir (idempotente)
│         → usa PICSAUDE_ADMIN_CPF + PICSAUDE_ADMIN_SENHA_INICIAL
│
├── [6] Verificação de integridade básica
│     ├── Banco acessível e íntegro (PRAGMA integrity_check)
│     ├── Versão do núcleo registrada
│     └── Todas as tabelas presentes
│
├── [7] Subir stack
│     └── docker-compose up -d
│
└── [8] Verificar saúde
      └── curl /health → OK
          curl /health/db → OK
          curl /health/version → { version: "1.0.0", ... }
```

### Propriedades obrigatórias do bootstrap

- **Idempotente**: rodar duas vezes não corrompe dados nem cria duplicatas
- **Verificável**: cada passo produz saída clara de sucesso ou falha
- **Atômico no passo crítico**: se init_tables falhar, não sobe o stack
- **Sem prompt interativo**: adequado para automação futura

---

## 8. Convenção de configuração por ambiente

### Arquivos `.env`

| Arquivo | Ambiente | Características |
|---|---|---|
| `.env.local` | Desenvolvimento | Secrets fracos, banco local, debug ativo, CORS aberto |
| `.env.hml` | Homologação | Dados sintéticos, URL de hml, secrets mais fortes |
| `.env.prod` | Produção local | Secrets fortes, backup ativo, CORS restrito, sem debug |

### Convenção de uso

```bash
# Desenvolvimento
cp .env.example .env.local
# editar .env.local
docker-compose --env-file .env.local up

# Produção
cp .env.example .env.prod
# editar .env.prod com segredos reais
docker-compose --env-file .env.prod up -d
```

### Variáveis por ambiente

| Variável | local | hml | prod |
|---|---|---|---|
| `PICSAUDE_ENV` | `dev` | `hml` | `prod` |
| `PICSAUDE_SECRET_KEY` | fraca | média | forte (256 bits) |
| Debug logs | ativado | parcial | desativado |
| CORS | aberto | restrito | restrito |
| Backup automático | não | não | recomendado |

---

## 9. Persistência e backup

### Banco SQLite

```
Volume Docker → /data/picsaude.db (dentro do container)
              → bind mount para /srv/picsaude/data/picsaude.db (no host)
```

**Backup mínimo:**

```bash
# backup_simples.sh — executar manualmente ou via cron
BACKUP_DIR="${PICSAUDE_BACKUP_DIR:-/data/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
sqlite3 /data/picsaude.db ".backup ${BACKUP_DIR}/picsaude_${TIMESTAMP}.db"
# Manter últimos 7 dias:
find "${BACKUP_DIR}" -name "*.db" -mtime +7 -delete
```

**Regras de backup:**
- Backup diário em produção (mínimo)
- Usar `.backup` do SQLite (cópia consistente, sem lock prolongado)
- Nunca copiar o arquivo `.db` direto enquanto o servidor está rodando
- Armazenar em diretório separado do banco ativo

### PDFs e QR Codes

**Decisão:** geração **efêmera** por padrão.

- PDFs são gerados na requisição, entregues em stream, não persistidos
- QR Codes idem — gerados sob demanda via endpoint
- **Justificativa:** evita gestão de armazenamento de arquivos; reduz superfície de ataque; conteúdo sempre regenerável a partir do banco

**Exceção documentada:** se uma instituição precisar de cache de PDFs (ex: volume alto), implementar como `local-extension` com tabela auxiliar própria — nunca no núcleo.

### Arquivos temporários

- Usar `/tmp` dentro do container para buffers de geração
- Container efêmero: `/tmp` limpo a cada reinicialização

---

## 10. Health checks

### Endpoints obrigatórios

| Endpoint | Verifica | Resposta esperada |
|---|---|---|
| `GET /health` | Backend respondendo | `{"ok": true}` |
| `GET /health/db` | Banco acessível e íntegro | `{"ok": true, "tabelas": N, "integrity": "ok"}` |
| `GET /health/version` | Versão do núcleo e data de migração | `{"version": "1.0.0", "env": "prod", "tabelas_ok": true}` |

### Especificação de `/health/db` (a implementar)

```python
GET /health/db
# Executa:
#   PRAGMA integrity_check  → "ok"
#   SELECT count(*) FROM sqlite_master WHERE type='table'
#   Verifica tabelas obrigatórias presentes
# Resposta: { "ok": true, "tabelas": 28, "integrity": "ok" }
# Em falha: HTTP 503 com detalhe
```

### Especificação de `/health/version` (a implementar)

```python
GET /health/version
# Resposta:
# {
#   "version":     "1.0.0",
#   "env":         "prod",
#   "instance":    "UFE-001",
#   "tabelas_ok":  true,
#   "outbox_ativo": true,
#   "uptime_s":    3600
# }
```

### `healthcheck.sh` (script externo)

```bash
#!/bin/bash
# healthcheck.sh — verificação de sanidade de uma instância
BASE_URL="${1:-http://localhost:8080}"

echo "Verificando PicSaúde em $BASE_URL ..."
curl -sf "${BASE_URL}/health"      || { echo "FALHA: /health"; exit 1; }
curl -sf "${BASE_URL}/health/db"   || { echo "FALHA: /health/db"; exit 1; }
curl -sf "${BASE_URL}/health/version" | python3 -m json.tool
echo "Instância OK."
```

### Outbox health (G4A)

```
GET /health/outbox (futuro — G4B)
→ { "pendentes": N, "mais_antigo_em": "...", "ok": true/false }
```

Flag de alerta: se houver eventos pendentes com mais de 24h sem ack, considerar instância com degradação de integração (não de operação clínica).

---

## 11. Limites de customização local

### O que uma instituição PODE customizar

```
local-extension PODE:
  ✅ Tema visual (cores, logo, nome da instituição) — via CSS/configuração
  ✅ Campos extras opcionais em objetos clínicos (NULL default, sem obrigatoriedade)
  ✅ Relatórios e dashboards locais (tabelas auxiliares próprias)
  ✅ Adapters externos (via G4A — nunca escrevem no banco clínico)
  ✅ Tradução/localização de labels e mensagens
  ✅ Integração com sistemas locais (via endpoints G4A)
  ✅ Módulos locais de autorização (ex: TISS) — como adapters
```

### O que uma instituição NÃO PODE alterar

```
local-extension NUNCA:
  ❌ Alterar semântica de estados clínicos (máquina de estados)
  ❌ Modificar o ledger (*_eventos) — sem UPDATE, sem DELETE
  ❌ Criar estados novos sem atualizar CLAUDE.md + states.py + DDL
  ❌ Criar prescrição_hospitalar, dispensador_hospitalar como entidades separadas
  ❌ Fazer adapters escreverem diretamente no banco clínico
  ❌ Alterar documento canônico ou cálculo de hash de integridade
  ❌ Remover custódia ou torná-la opcional
  ❌ Modificar CLAUDE.md sem revisão central obrigatória
```

### Como empacotar customizações locais

```
picsaude-local-extensao/
├── config/
│   ├── tema.css               ← customização visual
│   └── labels_pt_br.json     ← traduções locais
├── relatorios/                ← SQL/scripts de relatórios locais
├── adapters/                  ← consumidores G4A (código do adapter)
└── MANIFEST.md               ← documenta o que foi alterado e por quê
```

**MANIFEST.md obrigatório** em qualquer pacote de extensão local. Deve declarar:
- Versão do núcleo compatível
- O que foi alterado (só `local-extension`)
- Responsável pela extensão
- Data de criação

---

## 12. Governança e licenciamento

### Princípios de distribuição

| Princípio | Aplicação |
|---|---|
| **Núcleo comum** | Todos os parceiros usam o mesmo núcleo — sem forks do core |
| **Extensões locais isoladas** | Customizações ficam fora do núcleo; não sobem como PRs de core |
| **Contribuição de melhorias** | Melhorias ao núcleo seguem taxonomia §10 do CLAUDE.md — revisão obrigatória |
| **Compatibilidade de versão** | Instâncias devem declarar versão do núcleo; breaking changes têm versão maior |

### Modelo de versão sugerido

```
MAJOR.MINOR.PATCH

MAJOR: breaking change no núcleo (estados, ledger, custódia, API pública)
MINOR: novo módulo ou endpoint compatível
PATCH: correção de bug sem impacto em contrato
```

### Rastreabilidade de versão em instâncias

Cada instância deve registrar no banco a versão do núcleo instalado:

```sql
CREATE TABLE IF NOT EXISTS meta_instalacao (
    chave   TEXT PRIMARY KEY,
    valor   TEXT NOT NULL,
    criado_em TEXT NOT NULL
);
-- Exemplos:
-- nucleo_version: "1.0.0"
-- instalado_em:   "2026-03-20T14:00:00Z"
-- org_id:         "UFE-001"
-- bootstrap_hash: sha256 do bootstrap executado
```

Isso permite que updates futuros detectem versão instalada e apliquem migrações corretas.

---

## 13. Pacote mínimo distribuível

### O que entra no pacote de distribuição `v1.0`

```
picsaude-v1.0/
├── docker-compose.yml
├── .env.example
├── bootstrap.sh
├── healthcheck.sh
├── README_instalacao.md
├── frontend/
│   ├── prescritor.html
│   ├── dispensador.html
│   └── cidadao.html
└── docs/
    ├── EMPACOTAMENTO_DISTRIBUICAO.md  ← este documento
    ├── ARQUITETURA.md
    ├── NUCLEO_SANITARIO.md
    └── GOVERNANCA_INSTALACAO.md
```

A imagem Docker (`picsaude/backend:1.0.0`) é publicada separadamente e referenciada no `docker-compose.yml`.

### Critérios de "instância homologada"

Uma instância é considerada homologada quando:
1. `GET /health` → 200
2. `GET /health/db` → 200 com `integrity: "ok"`
3. Todas as tabelas do núcleo presentes
4. Admin inicial com senha alterada (não a senha do `.env.example`)
5. `PICSAUDE_SECRET_KEY` com entropia adequada (≥ 32 bytes aleatórios)

---

## 14. Próximo passo técnico (ticket G5-impl)

Com esta arquitetura definida, o próximo passo é implementar os artefatos:

### Escopo do ticket G5-impl

| Artefato | O que implementar |
|---|---|
| `Dockerfile` | Build do backend, HEALTHCHECK embutido |
| `docker-compose.yml` | Stack completa: backend + volume |
| `.env.example` | Todas as variáveis documentadas |
| `bootstrap.sh` | Fluxo completo dos 8 passos |
| `backend/create_admin.py` | Script idempotente de criação de admin |
| `GET /health/db` | Endpoint de saúde do banco |
| `GET /health/version` | Endpoint de versão da instância |
| `healthcheck.sh` | Script de verificação externa |
| `README_instalacao.md` | Guia do operador em 5 passos |
| `meta_instalacao` table | Rastreabilidade de versão instalada |

**Critério de aceite do G5-impl:** executar `./bootstrap.sh` em ambiente limpo e chegar em instância operacional com todos os health checks verdes em menos de 5 minutos.

---

## Resumo executivo

| Dimensão | Decisão |
|---|---|
| **Modelo** | Containers + configuração + bootstrap |
| **Stack mínima** | FastAPI + SQLite em volume + frontends estáticos |
| **Unidade mínima** | 1 container + 1 volume + 1 `.env` |
| **Distribuição** | Imagem Docker + artefatos de configuração |
| **Bootstrap** | 8 passos, idempotente, verificável, sem prompt |
| **Ambientes** | `.env.local` / `.env.hml` / `.env.prod` |
| **Persistência** | SQLite em bind mount; PDFs efêmeros; backup via `.backup` |
| **Health checks** | `/health`, `/health/db`, `/health/version` |
| **Customização** | `local-extension` isolada; núcleo intocável |
| **Governança** | Núcleo comum; forks de extensão; MANIFEST.md obrigatório |
| **Próximo passo** | G5-impl: implementar artefatos; critério = instância em < 5 min |
