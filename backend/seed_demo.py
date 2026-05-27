"""
seed_demo.py
============
TICKET-6 — seed canônico do DEMO_MODE.

Cria as 3 personas usadas pelo `/demo/login` (§3.3 do ticket).
Identificadores DIFERENTES dos do seed_dev.py para evitar colisão.

  Prescritor   CNS  980001112223334   Dra. Demo Maria Souza
  Dispensador  CNPJ 99999999000191   Farmácia Demo Central
  Paciente     CPF  12345678909      João Demo da Silva

Paciente NÃO entra em `usuarios` (KISS §3.7.1 — sem refresh em demo).

Uso:
    cd backend && PICSAUDE_DEMO_MODE=true python3 seed_demo.py

NÃO executar em produção. Idempotente — seguro para re-execução.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from app.auth.jwt import hash_senha
from app.database import get_conn

# ---------------------------------------------------------------------------
# Personas canônicas (§3.3 TICKET-6 — P3#8 CODEX rodada 1: IDs novos)
# ---------------------------------------------------------------------------

SENHA_DEMO = "Demo@2024"   # senha não é usada em demo (login via /demo/login)

PRESCRITOR = dict(
    cns="980001112223334",
    nome="Dra. Demo Maria Souza",
    role="prescritor",
)

DISPENSADOR = dict(
    cnpj="99999999000191",
    nome="Farmácia Demo Central",
    role="dispensador",
    org_id="farmacia-demo",
    tipo_prestador="farmacia",
    unidade_id="DEMO-001",
    unidade_nome="Unidade Central Demo",
    unidade_tipo="farmacia",
)

PACIENTE = dict(
    cpf="12345678909",
    nome="João Demo da Silva",
)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Garantias idempotentes
# ---------------------------------------------------------------------------

def _garantir_usuario(conn, identificador: str, nome: str, role: str) -> None:
    now = _agora()
    senha_hash = hash_senha(SENHA_DEMO)
    row = conn.execute(
        "SELECT id FROM usuarios WHERE identificador = ?", (identificador,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE usuarios SET senha_hash = ?, updated_at = ? WHERE identificador = ?",
            (senha_hash, now, identificador),
        )
        print(f"  ↺  usuario '{identificador}' ({role}) — atualizado")
    else:
        conn.execute(
            "INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
            (role, identificador, nome, senha_hash, now, now),
        )
        print(f"  ✅ usuario '{identificador}' ({role}) — criado")


def _garantir_prescritor(conn, cns: str, nome: str) -> None:
    now = _agora()
    row = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (cns,)
    ).fetchone()
    if row:
        print(f"  ·  prescritores: '{cns}' já existe")
    else:
        conn.execute(
            "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?)",
            (cns, nome, now, now),
        )
        print(f"  ✅ prescritores: '{cns}' — criado")


def _garantir_prestador(
    conn,
    org_id: str,
    nome: str,
    tipo: str,
    cnpj: str,
    unidade_id: str,
    unidade_nome: str,
    unidade_tipo: str,
) -> None:
    now = _agora()
    row_p = conn.execute(
        "SELECT id FROM prestadores WHERE org_id = ?", (org_id,)
    ).fetchone()
    if row_p:
        prestador_id = row_p["id"]
        print(f"  ·  prestadores: org_id='{org_id}' já existe")
    else:
        prestador_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em) "
            "VALUES (?, ?, ?, ?, ?, 1, ?)",
            (prestador_id, org_id, nome, tipo, cnpj, now),
        )
        print(f"  ✅ prestadores: org_id='{org_id}' ({tipo}) — criado")

    row_u = conn.execute(
        "SELECT id FROM unidades WHERE prestador_id = ? AND unidade_id = ?",
        (prestador_id, unidade_id),
    ).fetchone()
    if row_u:
        print(f"  ·  unidades: '{unidade_id}' já existe")
    else:
        conn.execute(
            "INSERT INTO unidades (id, prestador_id, unidade_id, nome, tipo, "
            "ativo, criado_em) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (str(uuid.uuid4()), prestador_id, unidade_id,
             unidade_nome, unidade_tipo, now),
        )
        print(f"  ✅ unidades: '{unidade_id}' ({unidade_nome}) — criada")


def _garantir_paciente(conn, cpf: str, nome: str) -> None:
    """
    Cria paciente em `pacientes`. NÃO insere em `usuarios` (§3.7.1 KISS —
    sem refresh em demo, paciente não precisa de identificador para reidratar).

    `ativo=true` aqui sinaliza "paciente cadastrado" — o que o 5A trata como
    "tem carteira digital" via inferência `paciente_existia=True` (§3.1 do
    TICKET-5A). Carteira formal fica para Dívida B-Carteira #36.
    """
    now = _agora()
    row = conn.execute(
        "SELECT id FROM pacientes WHERE cpf = ?", (cpf,)
    ).fetchone()
    if row:
        conn.execute(
            "UPDATE pacientes SET ativo = 1, nome = ?, updated_at = ? WHERE cpf = ?",
            (nome, now, cpf),
        )
        print(f"  ↺  pacientes: '{cpf}' — atualizado")
    else:
        conn.execute(
            "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, ?)",
            (cpf, nome, now, now),
        )
        print(f"  ✅ pacientes: '{cpf}' — criado")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if os.getenv("PICSAUDE_ENV") == "prod":
        print("❌ ABORTANDO: seed_demo não pode rodar em PICSAUDE_ENV=prod.")
        sys.exit(1)

    # TICKET-6.1 P2#5: sem a flag, _resolve_sqlite_db_path() devolve DB_PATH
    # (dev/prod). Quem rodar `python3 seed_demo.py` sem PICSAUDE_DEMO_MODE=true
    # acaba inserindo as personas demo no banco errado.
    demo = os.getenv("PICSAUDE_DEMO_MODE", "").lower()
    if demo != "true":
        print(
            "❌ ABORTANDO: PICSAUDE_DEMO_MODE precisa ser 'true' para semear o DB demo.\n"
            "   Sem a flag, get_conn() roteia para o DB de dev/prod (TICKET-6.1 P2#5)."
        )
        sys.exit(1)

    print("\n=== seed_demo.py — TICKET-6 ===")
    print(f"DB:  {os.getenv('PIX_SAUDE_DEMO_DB', '(padrão data/pix_saude_demo.db)')}")
    print(f"ENV: {os.getenv('PICSAUDE_ENV', '(não setado)')}")
    print(f"DEMO_MODE: {os.getenv('PICSAUDE_DEMO_MODE', '(não setado)')}\n")

    conn = get_conn()
    try:
        # Schema cinturão: garante que tabelas opcionais (CNES) existam vazias
        # para que endpoints de contexto institucional não quebrem em demo.
        # Defense in depth: o fallback em login.py:311 já pega o cenário, mas
        # o CREATE garante schema correto para novos bancos demo.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS estabelecimentos_cnes (
                CO_CNES      TEXT,
                NU_CNPJ      TEXT,
                TP_UNIDADE   TEXT,
                NO_FANTASIA  TEXT,
                CO_MUNICIPIO TEXT
            )
        """)

        # Prescritor
        _garantir_usuario(conn, PRESCRITOR["cns"], PRESCRITOR["nome"], PRESCRITOR["role"])
        _garantir_prescritor(conn, PRESCRITOR["cns"], PRESCRITOR["nome"])

        # Dispensador
        _garantir_usuario(conn, DISPENSADOR["cnpj"], DISPENSADOR["nome"], DISPENSADOR["role"])
        _garantir_prestador(
            conn,
            org_id=DISPENSADOR["org_id"],
            nome=DISPENSADOR["nome"],
            tipo=DISPENSADOR["tipo_prestador"],
            cnpj=DISPENSADOR["cnpj"],
            unidade_id=DISPENSADOR["unidade_id"],
            unidade_nome=DISPENSADOR["unidade_nome"],
            unidade_tipo=DISPENSADOR["unidade_tipo"],
        )

        # Paciente (sem `usuarios` — KISS §3.7.1)
        _garantir_paciente(conn, PACIENTE["cpf"], PACIENTE["nome"])

        conn.commit()
        print("\n✅ seed_demo.py concluído com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
