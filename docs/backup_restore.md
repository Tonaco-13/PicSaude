# Backup e Disaster Recovery — PicSaúde

> **Ticket 10** — Procedimento manual validado em 2026-04-17.
> PostgreSQL via `pgserver` (dev/local). Em produção, adaptar `PGHOST`, `PGPORT` e `PGUSER`.

---

## Variáveis de ambiente

```bash
export PGDATA=~/picsaude_pgdata
export PGBIN=~/Library/Python/3.9/lib/python/site-packages/pgserver/pginstall/bin
export PGHOST=/Users/fabianotonacoborges/picsaude_pgdata   # socket Unix
export PGPORT=5432
export PGUSER=postgres
export PGDATABASE=picsaude_dev
export BACKUP_FILE=/tmp/picsaude_backup.dump
```

---

## 1. Como gerar backup

```bash
$PGBIN/pg_dump \
  --host=$PGHOST \
  --port=$PGPORT \
  --username=$PGUSER \
  --dbname=$PGDATABASE \
  --format=c \
  --file=$BACKUP_FILE
```

**Verificar:**
```bash
ls -lh $BACKUP_FILE   # deve existir e ter tamanho > 0
```

---

## 2. Como validar o dump (OBRIGATÓRIO antes de dropar o banco)

```bash
$PGBIN/pg_restore --list $BACKUP_FILE | head -30
```

**Esperado:** lista de objetos (TABLE, SEQUENCE, FUNCTION...).  
**Se falhar:** NÃO prosseguir — dump inválido.

---

## 3. Como restaurar (simulação de desastre)

### 3.1 Encerrar conexões ativas

```sql
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'picsaude_dev' AND pid <> pg_backend_pid();
```

### 3.2 Drop + create

```bash
$PGBIN/dropdb  --host=$PGHOST --port=$PGPORT --username=$PGUSER picsaude_dev
$PGBIN/createdb --host=$PGHOST --port=$PGPORT --username=$PGUSER picsaude_dev
```

### 3.3 Restore

```bash
$PGBIN/pg_restore \
  --host=$PGHOST \
  --port=$PGPORT \
  --username=$PGUSER \
  --dbname=$PGDATABASE \
  --no-owner \
  $BACKUP_FILE
```

Warnings de `role` são não-fatais. Erros de `ERROR:` devem ser investigados.

---

## 4. Como validar integridade pós-restore

### Contagens (comparar com baseline pré-backup)

```sql
SELECT COUNT(*) FROM prescricoes;
SELECT COUNT(*) FROM prescricao_eventos;
SELECT COUNT(*) FROM prescricao_itens;
SELECT COUNT(*) FROM pacientes;
```

### Invariante ledger

```sql
-- eventos >= prescrições (ledger nunca menor que o objeto)
SELECT
  (SELECT COUNT(*) FROM prescricao_eventos) AS eventos,
  (SELECT COUNT(*) FROM prescricoes)        AS prescricoes;
```

### Verificação de órfãos (esperado: zero em todos)

```sql
-- FK nula
SELECT COUNT(*) FROM prescricao_itens  WHERE prescricao_id IS NULL;
SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id IS NULL;

-- FK inválida
SELECT COUNT(*) FROM prescricao_itens
  WHERE prescricao_id NOT IN (SELECT id FROM prescricoes);

SELECT COUNT(*) FROM prescricao_eventos
  WHERE prescricao_id NOT IN (SELECT id FROM prescricoes);
```

---

## 5. Tempo estimado

| Etapa | Tempo medido (dev, banco local) |
|---|---|
| pg_dump | < 5 s |
| pg_restore --list | < 1 s |
| dropdb / createdb | < 2 s |
| pg_restore | < 10 s |
| Validação SQL | < 2 s |
| **Total** | **< 20 s** |

Em produção com banco maior: escalar proporcionalmente ao volume de dados.

---

## 6. Local do arquivo de backup

| Ambiente | Caminho padrão |
|---|---|
| Dev/local | `/tmp/picsaude_backup.dump` |
| Produção (recomendado) | `/var/backups/picsaude/picsaude_YYYYMMDD_HHMM.dump` |

---

## 7. Script de automação (Ticket 10)

```bash
cd backend && python3 scripts/ticket10_backup_restore.py
```

O script executa todo o ciclo (baseline → backup → drop → restore → validação → teste funcional) e imprime o relatório final.

---

## 8. Riscos identificados

| Risco | Descrição | Mitigação futura |
|---|---|---|
| **Backup local** | Arquivo em `/tmp` — perdido em reinicialização do sistema | Copiar para storage externo (S3, GCS, NFS) |
| **Sem automação** | Backup manual, sujeito a esquecimento | Implementar cron job (fora do escopo deste ticket) |
| **Sem versionamento** | Arquivo único sobrescrito a cada execução | Nomear por timestamp: `picsaude_YYYYMMDD_HHMM.dump` |
| **Sem criptografia** | Dump em texto claro (comprimido, não cifrado) | Criptografar com `gpg` ou usar backup criptografado do cloud |
| **Sem teste de integridade automático** | Validação manual pós-restore | Adicionar script de smoke-test ao pipeline CI |
| **Servidor pgserver (dev)** | pgserver para e sobe com o processo Python | Em produção, usar PostgreSQL gerenciado (RDS, CloudSQL) com backup nativo |

---

## Validação executada em 2026-04-17

```
Tamanho do backup:     115.5 KB
Dump validado:         SIM (341 objetos)
Restore executado:     SIM
Contagens pré vs pós:  OK (prescricoes=1, eventos=1, itens=1, pacientes=1)
Órfãos FK inválida:    0
Teste funcional:       OK (GET /health → 200)
```

**BACKUP E RESTORE VALIDADO**
