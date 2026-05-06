# PicSaúde — Guia de Instalação

**Versão do núcleo:** 1.0.0
**Público:** Operadores institucionais (equipe de TI)

---

## Pré-requisitos

| Requisito | Versão mínima | Como verificar |
|---|---|---|
| Docker | 24.x | `docker --version` |
| Docker Compose | 2.x | `docker compose version` |
| Bash | 3.x | disponível em Linux/macOS |
| curl | qualquer | `curl --version` |

---

## Instalação em 5 passos

### 1. Extrair o pacote

```bash
tar -xzf picsaude-v1.0.tar.gz
cd picsaude-v1.0
```

### 2. Configurar o ambiente

```bash
cp .env.example .env
```

Abra o arquivo `.env` e preencha obrigatoriamente:

| Variável | Descrição | Exemplo |
|---|---|---|
| `PICSAUDE_INSTANCE_ORG_ID` | Código único da sua instituição (sigla curta + número) | `HOSPITAL-RECIFE-001` |
| `PICSAUDE_INSTANCE_NAME` | Nome legível da instituição | `Hospital São Lucas — Recife/PE` |
| `PICSAUDE_BASE_URL` | URL pública da instalação | `http://192.168.1.10:8080` |
| `PICSAUDE_JWT_SECRET` | Chave JWT (gerar abaixo) | — |
| `PICSAUDE_ADMIN_EMAIL` | E-mail do administrador | `ti@minhainstituicao.br` |
| `PICSAUDE_ADMIN_NOME` | Nome do administrador | `Equipe TI` |
| `PICSAUDE_ADMIN_SENHA` | Senha inicial (trocar após login) | — |

**Gerar chave JWT:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 3. Executar o bootstrap

```bash
chmod +x bootstrap.sh
./bootstrap.sh
```

O script:
- valida sua configuração
- inicializa o banco de dados
- cria o administrador inicial
- sobe os containers
- verifica a saúde da instância

Tempo esperado: **< 5 minutos**.

### 4. Verificar acesso

Abra no navegador: `http://localhost:8080` (ou a URL configurada em `PICSAUDE_BASE_URL`)

Módulos disponíveis:
- `/prescritor.html` — Módulo do prescritor
- `/dispensador.html` — Módulo do dispensador
- `/cidadao.html` — Módulo do cidadão
- `/health` — Status da instância (sem autenticação)

### 5. Trocar a senha do admin

No primeiro login, use o e-mail e senha definidos no `.env`.
**Troque a senha imediatamente após o primeiro acesso.**

---

## Verificação de saúde

```bash
# Verificação rápida
./healthcheck.sh

# Verificação em URL remota
./healthcheck.sh http://192.168.1.10:8080
```

Endpoints disponíveis sem autenticação:

| Endpoint | O que verifica |
|---|---|
| `GET /health` | Backend ativo |
| `GET /health/db` | Banco íntegro + tabelas presentes |
| `GET /health/version` | Versão, org_id, ambiente, uptime |

---

## Backup

### Manual (recomendado para produção)

```bash
# Executar dentro do container ou com acesso ao volume
DATE=$(date +%Y%m%d_%H%M%S)
sqlite3 /data/picsaude.db ".backup /data/backups/picsaude_${DATE}.db"

# Verificar integridade do backup
sqlite3 /data/backups/picsaude_${DATE}.db "PRAGMA integrity_check"
```

### Agendado via cron (host)

```bash
# Adicionar ao crontab: backup diário às 2h
0 2 * * * docker exec picsaude-backend python3 -c "
import subprocess, datetime
ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
subprocess.run(['sqlite3', '/data/picsaude.db', f'.backup /data/backups/picsaude_{ts}.db'])
"
```

**Retenção:** manter os últimos 7 dias é o mínimo recomendado.

---

## Atualização

```bash
# 1. Fazer backup antes de atualizar
DATE=$(date +%Y%m%d_%H%M%S)
docker exec picsaude-backend sqlite3 /data/picsaude.db \
    ".backup /data/backups/pre_atualizacao_${DATE}.db"

# 2. Parar a stack
docker compose down

# 3. Substituir os arquivos pela nova versão
# (manter o .env e o volume picsaude_data)

# 4. Executar bootstrap novamente (detecta instalação existente — idempotente)
./bootstrap.sh
```

---

## Operação diária

```bash
# Ver logs em tempo real
docker compose logs -f picsaude-backend

# Parar
docker compose down

# Reiniciar
docker compose restart picsaude-backend

# Status dos containers
docker compose ps
```

---

## Customização local

O que sua instituição **pode** customizar sem suporte do núcleo:
- Logotipo e cores (CSS)
- Campos extras opcionais em formulários
- Relatórios institucionais locais
- Integração com sistemas locais via API (G4A)

O que **não deve ser modificado** sem revisão técnica:
- Máquina de estados clínicos
- Ledger de eventos (`*_eventos`)
- Cálculo de hash de integridade de documentos
- Código de custódia e dispensação

Consulte `docs/EMPACOTAMENTO_DISTRIBUICAO.md` para os limites completos.

---

## Suporte

- Documentação técnica: `docs/ARQUITETURA.md`
- Princípios do núcleo: `CLAUDE.md`
- Arquitetura de distribuição: `docs/EMPACOTAMENTO_DISTRIBUICAO.md`
- Health check de emergência: `./healthcheck.sh`
