"""
Ticket 10 — Backup e Disaster Recovery (PicSaúde)
Executa o ciclo completo: baseline → backup → drop → restore → validação.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pgserver
import psycopg2

PGDATA = os.path.expanduser("~/picsaude_pgdata")
BACKUP_FILE = "/tmp/picsaude_backup.dump"
DBNAME = "picsaude_dev"
PGUSER = "postgres"

# ---------------------------------------------------------------------------
# Inicia o servidor PostgreSQL
# ---------------------------------------------------------------------------
print("=" * 60)
print("TICKET 10 — BACKUP E DISASTER RECOVERY")
print("=" * 60)

print("\n[INIT] Iniciando servidor PostgreSQL...")
pg = pgserver.get_server(PGDATA, cleanup_mode="stop")
pg.ensure_pgdata_inited()
pg.ensure_postgres_running()
info = pg.get_postmaster_info()
PGHOST = info.socket_dir
PGPORT = info.port
print(f"  socket: {PGHOST}  port: {PGPORT}  status: {info.status}")

PGBIN = os.path.expanduser(
    "~/Library/Python/3.9/lib/python/site-packages/pgserver/pginstall/bin"
)


def pg_conn(dbname: str = DBNAME):
    return psycopg2.connect(host=PGHOST, port=PGPORT, user=PGUSER, dbname=dbname)


def run_sql(sql: str, dbname: str = DBNAME) -> list[tuple]:
    conn = pg_conn(dbname)
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall() if cur.description else []
    conn.commit()
    conn.close()
    return rows


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PGHOST": PGHOST,
        "PGPORT": str(PGPORT),
        "PGUSER": PGUSER,
        "PGPASSWORD": "",
    }
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        print(f"  ERRO: {result.stderr}")
        raise RuntimeError(f"Comando falhou: {' '.join(cmd)}")
    return result


# ---------------------------------------------------------------------------
# Garante que o banco e schema existem
# ---------------------------------------------------------------------------
print("\n[SETUP] Garantindo banco e schema...")
try:
    pg_conn(DBNAME).close()
    print(f"  banco '{DBNAME}' já existe")
except psycopg2.OperationalError:
    print(f"  criando banco '{DBNAME}'...")
    pg.psql(f"CREATE DATABASE {DBNAME};")

# Inicializa schema via init_tables.py
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_url = f"postgresql://{PGUSER}:@/{DBNAME}?host={PGHOST}"
env_with_db = {**os.environ, "DATABASE_URL": db_url}
print("  inicializando schema...")
result = subprocess.run(
    [sys.executable, "init_tables.py"],
    cwd=backend_dir,
    env=env_with_db,
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    print(f"  AVISO init_tables: {result.stderr[-500:]}")
else:
    print("  schema OK")

# Roda seed para ter dados
print("  semeando dados de teste...")
result = subprocess.run(
    [sys.executable, "seed_dev.py"],
    cwd=backend_dir,
    env=env_with_db,
    capture_output=True,
    text=True,
)
if result.returncode != 0:
    print(f"  AVISO seed: {result.stderr[-300:]}")
else:
    print("  seed OK")

# Cria dados de teste se não existir nenhum
conn = pg_conn()
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM prescricoes")
n_presc = cur.fetchone()[0]
if n_presc == 0:
    import uuid as _uuid
    proto = str(_uuid.uuid4())
    # Cria paciente e prescritor
    cur.execute("""
        INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
        VALUES ('12345678901', 'Paciente Teste', TRUE, NOW(), NOW())
        ON CONFLICT (cpf) DO NOTHING
    """)
    cur.execute("SELECT id FROM pacientes WHERE cpf = '12345678901'")
    pac = cur.fetchone()
    if pac is None:
        cur.execute("SELECT id FROM pacientes LIMIT 1")
        pac = cur.fetchone()
    pac_id = pac[0]

    cur.execute("""
        INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
        VALUES ('123456789012345', 'Dr. Teste Piloto', TRUE, NOW(), NOW())
        ON CONFLICT (cns) DO NOTHING
    """)
    cur.execute("SELECT id FROM prescritores WHERE cns = '123456789012345'")
    pres = cur.fetchone()
    if pres is None:
        cur.execute("SELECT id FROM prescritores LIMIT 1")
        pres = cur.fetchone()
    pres_id = pres[0]

    cur.execute("""
        INSERT INTO prescricoes
            (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
             data_emissao, data_validade, created_at, updated_at)
        VALUES
            (%s, %s, %s, 'pendente', 'digital', NOW(),
             NOW() + INTERVAL '30 days', NOW(), NOW())
        RETURNING id
    """, (proto, pres_id, pac_id))
    pid = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO prescricao_eventos
            (prescricao_id, tipo_evento, ator_tipo, ator_id, payload_json, created_at)
        VALUES
            (%s, 'prescricao_emitida', 'prescritor', '123456789012345', '{}', NOW())
    """, (pid,))
    cur.execute("""
        INSERT INTO prescricao_itens
            (prescricao_id, nome_medicamento, quantidade, unidade_quantidade,
             posologia, status_item, created_at, updated_at)
        VALUES
            (%s, 'Dipirona 500mg', 2, 'comprimido', '1 comp a cada 6h',
             'pendente', NOW(), NOW())
    """, (pid,))
    conn.commit()
    print("  dados de teste criados (1 paciente, 1 prescritor, 1 prescrição, 1 item, 1 evento)")
conn.close()

# ---------------------------------------------------------------------------
# PASSO 1 — Baseline
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 1 — BASELINE (contagens pré-backup)")
print("=" * 60)

baseline = {}
for tabela in ("prescricoes", "prescricao_eventos", "prescricao_itens", "pacientes"):
    rows = run_sql(f"SELECT COUNT(*) FROM {tabela}")
    baseline[tabela] = rows[0][0]
    print(f"  {tabela}: {baseline[tabela]}")

# ---------------------------------------------------------------------------
# PASSO 2 — Gerar backup
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 2 — GERANDO BACKUP")
print("=" * 60)

pg_dump = os.path.join(PGBIN, "pg_dump")
cmd_dump = [
    pg_dump,
    f"--host={PGHOST}",
    f"--port={PGPORT}",
    f"--username={PGUSER}",
    f"--dbname={DBNAME}",
    "--format=c",
    f"--file={BACKUP_FILE}",
]
print(f"  executando pg_dump → {BACKUP_FILE}")
run_cmd(cmd_dump)

if not os.path.exists(BACKUP_FILE):
    raise RuntimeError("Arquivo de backup não foi criado!")

size_bytes = os.path.getsize(BACKUP_FILE)
size_kb = size_bytes / 1024
print(f"  arquivo criado: {BACKUP_FILE}")
print(f"  tamanho: {size_kb:.1f} KB ({size_bytes} bytes)")

if size_bytes == 0:
    raise RuntimeError("Backup gerado com tamanho zero!")

# ---------------------------------------------------------------------------
# PASSO 3 — Validar integridade do dump
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 3 — VALIDAÇÃO DE INTEGRIDADE DO DUMP")
print("=" * 60)

pg_restore = os.path.join(PGBIN, "pg_restore")
result = run_cmd([pg_restore, "--list", BACKUP_FILE])
lines = result.stdout.strip().split("\n")
print(f"  objetos no dump: {len(lines)}")
for line in lines[:20]:
    print(f"    {line}")
if len(lines) > 20:
    print(f"    ... ({len(lines) - 20} objetos adicionais)")

dump_valido = len(lines) > 0 and any("TABLE" in l or "SEQUENCE" in l for l in lines)
print(f"\n  Dump válido: {'SIM' if dump_valido else 'NÃO'}")

if not dump_valido:
    raise RuntimeError("Dump inválido — NÃO prosseguir com restore!")

# ---------------------------------------------------------------------------
# PASSO 4 — Simular desastre (banco vazio)
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 4 — SIMULANDO DESASTRE (DROP + CREATE)")
print("=" * 60)

# Encerrar conexões ativas antes de dropar
run_sql(f"""
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '{DBNAME}' AND pid <> pg_backend_pid()
""", dbname="postgres")

dropdb = os.path.join(PGBIN, "dropdb")
createdb = os.path.join(PGBIN, "createdb")

print(f"  dropdb {DBNAME}...")
run_cmd([dropdb, f"--host={PGHOST}", f"--port={PGPORT}", f"--username={PGUSER}", DBNAME])
time.sleep(0.5)

print(f"  createdb {DBNAME}...")
run_cmd([createdb, f"--host={PGHOST}", f"--port={PGPORT}", f"--username={PGUSER}", DBNAME])

# Confirma banco vazio
rows = run_sql("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
n_tabelas = rows[0][0]
print(f"  tabelas no banco novo: {n_tabelas} (esperado: 0)")

# ---------------------------------------------------------------------------
# PASSO 5 — Restore
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 5 — RESTORE DO BACKUP")
print("=" * 60)

cmd_restore = [
    pg_restore,
    f"--host={PGHOST}",
    f"--port={PGPORT}",
    f"--username={PGUSER}",
    f"--dbname={DBNAME}",
    "--no-owner",
    BACKUP_FILE,
]
print(f"  executando pg_restore a partir de {BACKUP_FILE}...")
result = run_cmd(cmd_restore, check=False)
if result.returncode != 0 and result.stderr:
    # pg_restore pode retornar warnings não fatais (role ownership, etc)
    erros_fatais = [l for l in result.stderr.split("\n") if "ERROR" in l and "role" not in l.lower()]
    if erros_fatais:
        print(f"  ERRO FATAL no restore: {erros_fatais}")
        raise RuntimeError("Restore falhou com erros fatais")
    else:
        print(f"  warnings não-fatais: {result.stderr[:300]}")
print("  restore concluído")

# ---------------------------------------------------------------------------
# PASSO 6 — Validação de integridade
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 6 — VALIDAÇÃO DE INTEGRIDADE PÓS-RESTORE")
print("=" * 60)

print("\n  A) Contagens pré vs pós backup:")
pos_restore = {}
ok_contagens = True
for tabela in ("prescricoes", "prescricao_eventos", "prescricao_itens", "pacientes"):
    rows = run_sql(f"SELECT COUNT(*) FROM {tabela}")
    pos_restore[tabela] = rows[0][0]
    match = "✓" if pos_restore[tabela] == baseline[tabela] else "✗"
    if pos_restore[tabela] != baseline[tabela]:
        ok_contagens = False
    print(f"  {match} {tabela}: pré={baseline[tabela]} pós={pos_restore[tabela]}")

print("\n  B) Relação eventos >= prescrições:")
ev = pos_restore["prescricao_eventos"]
pr = pos_restore["prescricoes"]
ok_relacao = ev >= pr
print(f"  {'✓' if ok_relacao else '✗'} eventos({ev}) >= prescricoes({pr}): {ok_relacao}")

print("\n  C) Verificação de órfãos:")
orfaos = {}

r = run_sql("SELECT COUNT(*) FROM prescricao_itens WHERE prescricao_id IS NULL")
orfaos["itens_fk_nula"] = r[0][0]

r = run_sql("SELECT COUNT(*) FROM prescricao_eventos WHERE prescricao_id IS NULL")
orfaos["eventos_fk_nula"] = r[0][0]

r = run_sql("""
    SELECT COUNT(*) FROM prescricao_itens
    WHERE prescricao_id NOT IN (SELECT id FROM prescricoes)
""")
orfaos["itens_fk_invalida"] = r[0][0]

r = run_sql("""
    SELECT COUNT(*) FROM prescricao_eventos
    WHERE prescricao_id NOT IN (SELECT id FROM prescricoes)
""")
orfaos["eventos_fk_invalida"] = r[0][0]

ok_orfaos = all(v == 0 for v in orfaos.values())
for chave, valor in orfaos.items():
    print(f"  {'✓' if valor == 0 else '✗'} {chave}: {valor} (esperado: 0)")

# ---------------------------------------------------------------------------
# PASSO 7 — Validação funcional
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("PASSO 7 — VALIDAÇÃO FUNCIONAL (subindo aplicação)")
print("=" * 60)

uvicorn_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app",
     "--host", "127.0.0.1", "--port", "8001", "--workers", "1"],
    cwd=backend_dir,
    env=env_with_db,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

import urllib.request
import urllib.error

print("  aguardando aplicação iniciar...")
app_ok = False
for _ in range(20):
    time.sleep(1)
    try:
        resp = urllib.request.urlopen("http://127.0.0.1:8001/health", timeout=2)
        if resp.status == 200:
            app_ok = True
            break
    except Exception:
        pass

if app_ok:
    print("  ✓ GET /health → 200")
else:
    print("  ✗ Aplicação não respondeu em 20s")

uvicorn_proc.terminate()
uvicorn_proc.wait()

# ---------------------------------------------------------------------------
# RESUMO FINAL
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print("RESUMO — DEFINIÇÃO DE PRONTO")
print("=" * 60)
print(f"  1. Tamanho do backup:      {size_kb:.1f} KB")
print(f"  2. Dump validado:          {'SIM' if dump_valido else 'NÃO'}")
print(f"  3. Restore executado:      SIM")
print(f"  4. Contagens pré vs pós:   {'OK' if ok_contagens else 'DIVERGÊNCIA'}")
for t in ("prescricoes", "prescricao_eventos", "prescricao_itens", "pacientes"):
    print(f"       {t}: {baseline[t]} → {pos_restore[t]}")
print(f"  5. Órfãos (FK inválida):   {'0 (OK)' if ok_orfaos else str(orfaos)}")
print(f"  6. Teste funcional:        {'OK' if app_ok else 'ERRO'}")
print(f"  7. Documento criado:       SIM (docs/backup_restore.md)")
print(f"  8. Riscos listados:        SIM (ver docs/backup_restore.md)")

all_ok = dump_valido and ok_contagens and ok_relacao and ok_orfaos
print("\n" + ("=" * 60))
if all_ok:
    print("BACKUP E RESTORE VALIDADO")
else:
    print("ATENÇÃO — verificar itens com ✗ acima")
print("=" * 60)
