"""
scripts/reset_demo_db.py
========================
TICKET-DEMO-RESET-PG — rebuild do banco demo, agora capaz de PostgreSQL (o
dialeto da vitrine no Render) preservando o comportamento SQLite (dev).

Mecanismo OFICIAL e versionado de reconstrução do banco demo. Ação destrutiva
e irreversível POR DESIGN — apaga todo o schema e o recria do zero. Não é
data-fix no ledger (CLAUDE.md §2): não faz UPDATE/DELETE seletivo em nenhuma
tabela clínica; destrói o schema inteiro e o refaz vazio.

Uso manual (dev, SQLite):
    cd backend && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py

Uso manual (vitrine, PostgreSQL — Render Shell / job disparado por Fabiano):
    cd /app && PICSAUDE_DEMO_MODE=true python3 scripts/reset_demo_db.py --sim-eu-quero

Comportamento por dialeto (§3.1 do ticket)
------------------------------------------
PostgreSQL (engine.dialect.name == "postgresql"):
    1. Confirma o ALVO (host+dbname mascarado, schema efetivo do search_path) e
       EXIGE assentimento explícito antes de qualquer DROP (§3.3).
    2. DROP SCHEMA <schema> CASCADE; CREATE SCHEMA <schema>;  (commit + dispose)
    3. alembic upgrade head
    4. seed_demo.main()
SQLite (engine.dialect.name == "sqlite"):
    1. Remove o arquivo do banco demo (+ sidecars -wal/-shm).
    2. alembic upgrade head   (SUBSTITUI o antigo create_all — ver §3.2)
    3. seed_demo.main()

§3.2 — alembic upgrade head, NUNCA Base.metadata.create_all (REGRA DE OURO)
---------------------------------------------------------------------------
`create_all` reproduz o schema a partir dos modelos ORM — e os modelos NÃO
contêm os 17 triggers de banco (16 de imutabilidade do ledger em
f2b7c1d0a4e5 + 1 de saldo efetivo em c3d4e5f6a7b8). Um rebuild via create_all
recriaria as tabelas SEM triggers, reproduzindo exatamente o defeito que
f2b7c1d0a4e5 documenta ter corrigido ("em PostgreSQL os triggers nunca
existiram"). create_all burla o §9 (a migração é a única autoridade de
schema). Portanto: toda recriação de schema, em qualquer dialeto, passa pela
migração — `alembic upgrade head` é o único caminho.

§3.3/§3.4 — confirmação do alvo como CÓDIGO
-------------------------------------------
As guardas do §5 (`PICSAUDE_ENV` / `PICSAUDE_DEMO_MODE`) protegem o AMBIENTE,
não o ALVO — a `DATABASE_URL` que será destruída. Um ambiente mal-configurado
(DEMO_MODE=true + DATABASE_URL apontando para o lugar errado) passaria as duas
guardas e faria DROP no alvo errado. Por isso, no ramo PG, o script ecoa o alvo
e exige assentimento (input interativo OU `--sim-eu-quero` para execução
não-interativa) antes de emitir qualquer DROP. Sem assentimento, aborta.

§5 — régua de segurança (defense-in-depth), preservada de TICKET-6:
    1. Aborta se PICSAUDE_ENV=prod.
    2. Aborta se PICSAUDE_DEMO_MODE != "true".
    NENHUM agente recebe a DATABASE_URL da vitrine — a execução no Render é de
    Fabiano. O script é versionado e testado; a credencial não circula em chat.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Permite executar do dir backend/ direto.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND_ROOT))

_FLAG_ASSENTIMENTO = "--sim-eu-quero"


def _abortar(msg: str) -> None:
    print(msg)
    sys.exit(1)


def _checar_guardas() -> None:
    """§5 — defesa em profundidade. Preservadas de TICKET-6, nunca contornadas
    (mesmo em automação). Protegem o AMBIENTE; o ALVO é protegido em §3.3."""
    if os.getenv("PICSAUDE_ENV", "") == "prod":
        _abortar("❌ ABORTANDO: reset_demo_db.py NUNCA pode rodar em PICSAUDE_ENV=prod.")

    if os.getenv("PICSAUDE_DEMO_MODE", "").lower() != "true":
        _abortar(
            "❌ ABORTANDO: PICSAUDE_DEMO_MODE precisa ser 'true' para o reset.\n"
            "   Isso evita derrubar acidentalmente o DB de dev/prod."
        )


def _confirmacao_ok(
    assentido: bool, is_tty: bool, resposta: str | None, dbname: str
) -> bool:
    """Decisão pura de autorização do alvo (§3.3) — testável sem banco.

    - `--sim-eu-quero` (assentido) autoriza qualquer execução (inclusive job
      não-interativo no Render).
    - Sem a flag, só há autorização quando há terminal E o operador digita
      exatamente o nome do banco.
    - Sem flag e sem terminal (job cego) → NÃO autoriza: aborta antes do DROP.
    """
    if assentido:
        return True
    if is_tty and resposta is not None:
        return resposta.strip() == dbname
    return False


def _confirmar_alvo_pg(engine, assentido: bool) -> str:
    """§3.3/§3.4 — ecoa o alvo, lê o schema efetivo do search_path e exige
    confirmação. Retorna o nome do schema a destruir; aborta se não autorizado.
    """
    from sqlalchemy import text
    from sqlalchemy.engine.url import make_url

    from app.database import DATABASE_URL, mask_url_credentials

    url = make_url(DATABASE_URL)
    host = url.host or "(local)"
    dbname = url.database or "(desconhecido)"

    # Schema efetivo — lido do search_path do PG, não hardcodado (§3.4).
    with engine.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar() or "public"

    print("\n⚠️  DESTRUIÇÃO IRREVERSÍVEL — reset_demo_db.py (PostgreSQL)")
    print(f"    URL    : {mask_url_credentials(DATABASE_URL)}")
    print(f"    Host   : {host}")
    print(f"    Banco  : {dbname}")
    print(f'    Schema : {schema}  (DROP SCHEMA "{schema}" CASCADE)\n')

    is_tty = sys.stdin.isatty()
    resposta: str | None = None
    if not assentido and is_tty:
        resposta = input(f"    Para confirmar, digite o nome do banco ({dbname}): ")

    if not _confirmacao_ok(assentido, is_tty, resposta, dbname):
        _abortar(
            "❌ ABORTANDO: alvo não confirmado — nenhum DROP emitido.\n"
            f"   Assinta com {_FLAG_ASSENTIMENTO} (execução não-interativa) ou "
            "digite o nome do banco (terminal).\n"
            "   As guardas de ENV/DEMO_MODE protegem o ambiente, não o alvo."
        )

    print(f"    ✔ alvo confirmado.")
    return schema


def _reset_postgres(engine, assentido: bool) -> None:
    from sqlalchemy import text

    schema = _confirmar_alvo_pg(engine, assentido)  # aborta se não autorizado

    # DDL crua: DROP + CREATE do schema, commitado no bloco `begin()`.
    with engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    print(f'🗑️  schema "{schema}" dropado e recriado (vazio)')

    # §3.4 — dispose() antes do alembic: descarta o pool cujas conexões ainda
    # veem o schema antigo, para que a migração E o seed_demo peguem conexões
    # limpas (seed usa get_conn() → engine.raw_connection() do MESMO pool).
    engine.dispose()


def _reset_sqlite() -> None:
    from app.config import PIX_SAUDE_DEMO_DB

    db_path = Path(PIX_SAUDE_DEMO_DB).resolve()
    print(f"DB demo (SQLite): {db_path}")

    # Remove o arquivo e os sidecars WAL/SHM (senão o seed pode morrer com
    # 'disk I/O error' por -shm órfão — gotcha registrado no rebuild-banco-demo).
    removidos = False
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
            print(f"🗑️  arquivo removido: {p}")
            removidos = True
    if not removidos:
        print(f"·  arquivo não existia: {db_path} (será criado)")

    db_path.parent.mkdir(parents=True, exist_ok=True)


def _alembic_upgrade_head() -> None:
    """§3.2 — recria o schema pela migração (autoridade §9), nunca create_all.

    O env.py do Alembic resolve o alvo igual ao app: DATABASE_URL vence sempre;
    sem ela, SQLite honrando PICSAUDE_DEMO_MODE. Rodar do backend/ para achar
    alembic.ini e o pacote app.*.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_BACKEND_ROOT / "alembic.ini"))
    cwd_before = os.getcwd()
    try:
        os.chdir(_BACKEND_ROOT)
        command.upgrade(cfg, "head")
    finally:
        os.chdir(cwd_before)
    print("✅ schema recriado via alembic upgrade head")


def main(argv: list[str] | None = None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    assentido = _FLAG_ASSENTIMENTO in argv

    _checar_guardas()

    # Imports tardios — honram as env vars checadas acima e evitam efeito
    # colateral no import do módulo (paridade com env.py: registra models).
    from app.database import engine
    import app.models  # noqa: F401

    dialeto = engine.dialect.name
    print("\n=== reset_demo_db.py — TICKET-DEMO-RESET-PG ===")
    print(f"Dialeto: {dialeto}")

    if dialeto == "postgresql":
        _reset_postgres(engine, assentido)
    elif dialeto == "sqlite":
        _reset_sqlite()
    else:
        _abortar(f"❌ ABORTANDO: dialeto não suportado para reset: {dialeto}")

    # §3.2 — ambos os dialetos recriam o schema pela migração.
    _alembic_upgrade_head()

    # Semeia as personas/artefatos canônicos.
    import seed_demo
    seed_demo.main()


if __name__ == "__main__":
    main()
