"""
seed_dev.py
===========
Script idempotente de dados de teste (ambiente DEV).

Cria/garante os papéis operacionais do fluxo E2E:
  - 1 prescritor (médico)
  - 1 farmácia    (dispensador ambulatorial)
  - 1 hospital    (dispensador hospitalar)
  - 1 USF         (dispensador ambulatorial — atenção primária)

Credenciais após execução:
  Prescritor   CNS  123456789012345   senha  Teste@2024
  Farmácia     CNPJ 12345678000199   senha  Teste@2024
  Hospital     CNPJ 11111111000111   senha  Teste@2024
  USF          CNPJ 33333333000133   senha  Teste@2024

Nota: clínica e laboratório foram removidos do seed de dispensadores.
  - laboratório pertence ao módulo de pedidos de exame (role futuro)
  - clínica não tem caso de uso definido como dispensador

Uso:
    cd backend && python3 seed_dev.py

Seguro para re-execução: idempotente em todos os INSERT.
NÃO executar em produção — use apenas para testes locais/dev.
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
# Dados de teste
# ---------------------------------------------------------------------------

SENHA_TESTE = "Teste@2024"

PRESCRITOR = dict(
    cns="123456789012345",
    nome="Dr. Teste Piloto",
    role="prescritor",
)

FARMACIA = dict(
    cnpj="12345678000199",
    nome="Farmácia Piloto",
    role="dispensador",
    org_id="farmacia-piloto",
    tipo_prestador="farmacia",
    unidade_id="FAR-001",
    unidade_nome="Unidade Central",
    unidade_tipo="farmacia",
)

HOSPITAL = dict(
    cnpj="11111111000111",
    nome="Hospital Piloto",
    role="dispensador",
    org_id="hospital-piloto",
    tipo_prestador="hospital",
    unidade_id="HOSP-001",
    unidade_nome="Farmácia Hospitalar",
    unidade_tipo="farmacia",
)

USF = dict(
    cnpj="33333333000133",
    nome="USF Piloto",
    role="dispensador",
    org_id="usf-piloto",
    tipo_prestador="usf",
    unidade_id="USF-001",
    unidade_nome="Unidade de Saúde da Família",
    unidade_tipo="usf",
)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Garantir usuário com senha conhecida
# ---------------------------------------------------------------------------

def _garantir_usuario(conn, identificador: str, nome: str, role: str) -> None:
    """Cria o usuário se não existir; atualiza a senha se já existir."""
    now = _agora()
    senha_hash = hash_senha(SENHA_TESTE)

    row = conn.execute(
        "SELECT id FROM usuarios WHERE identificador = ?", (identificador,)
    ).fetchone()

    if row:
        conn.execute(
            "UPDATE usuarios SET senha_hash = ?, updated_at = ? WHERE identificador = ?",
            (senha_hash, now, identificador),
        )
        print(f"  ↺  usuario '{identificador}' ({role}) — senha atualizada")
    else:
        conn.execute(
            """
            INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (role, identificador, nome, senha_hash, now, now),
        )
        print(f"  ✅ usuario '{identificador}' ({role}) — criado")


# ---------------------------------------------------------------------------
# Garantir prescritor na tabela prescritores
# ---------------------------------------------------------------------------

def _garantir_prescritor(conn, cns: str, nome: str) -> None:
    now = _agora()
    row = conn.execute(
        "SELECT id FROM prescritores WHERE cns = ?", (cns,)
    ).fetchone()

    if row:
        print(f"  ·  prescritores: '{cns}' já existe")
    else:
        conn.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?)
            """,
            (cns, nome, now, now),
        )
        print(f"  ✅ prescritores: '{cns}' — criado")


# ---------------------------------------------------------------------------
# Garantir prestador + unidade
# ---------------------------------------------------------------------------

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

    # --- prestador ---
    row_p = conn.execute(
        "SELECT id FROM prestadores WHERE org_id = ?", (org_id,)
    ).fetchone()

    if row_p:
        prestador_id = row_p["id"]
        print(f"  ·  prestadores: org_id='{org_id}' já existe")
    else:
        prestador_id = str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO prestadores (id, org_id, nome, tipo, cnpj, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (prestador_id, org_id, nome, tipo, cnpj, now),
        )
        print(f"  ✅ prestadores: org_id='{org_id}' ({tipo}) — criado")

    # --- unidade ---
    row_u = conn.execute(
        "SELECT id FROM unidades WHERE prestador_id = ? AND unidade_id = ?",
        (prestador_id, unidade_id),
    ).fetchone()

    if row_u:
        print(f"  ·  unidades: '{unidade_id}' já existe")
    else:
        conn.execute(
            """
            INSERT INTO unidades (id, prestador_id, unidade_id, nome, tipo, ativo, criado_em)
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (str(uuid.uuid4()), prestador_id, unidade_id, unidade_nome, unidade_tipo, now),
        )
        print(f"  ✅ unidades: '{unidade_id}' ({unidade_nome}) — criada")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n─────────────────────────────────────────────────────")
    print("  PicSaúde — seed_dev.py (dados de teste E2E)")
    print("─────────────────────────────────────────────────────")
    print(f"  Banco: {os.environ.get('PIX_SAUDE_DB', 'data/pix_saude_pe.db')}")
    print()

    conn = get_conn()
    try:
        print("[1] Prescritor de teste")
        _garantir_usuario(conn, PRESCRITOR["cns"], PRESCRITOR["nome"], PRESCRITOR["role"])
        _garantir_prescritor(conn, PRESCRITOR["cns"], PRESCRITOR["nome"])
        conn.commit()

        print()
        print("[2] Farmácia de teste")
        _garantir_usuario(conn, FARMACIA["cnpj"], FARMACIA["nome"], FARMACIA["role"])
        _garantir_prestador(
            conn,
            org_id=FARMACIA["org_id"],
            nome=FARMACIA["nome"],
            tipo=FARMACIA["tipo_prestador"],
            cnpj=FARMACIA["cnpj"],
            unidade_id=FARMACIA["unidade_id"],
            unidade_nome=FARMACIA["unidade_nome"],
            unidade_tipo=FARMACIA["unidade_tipo"],
        )
        conn.commit()

        print()
        print("[3] Hospital de teste")
        _garantir_usuario(conn, HOSPITAL["cnpj"], HOSPITAL["nome"], HOSPITAL["role"])
        _garantir_prestador(
            conn,
            org_id=HOSPITAL["org_id"],
            nome=HOSPITAL["nome"],
            tipo=HOSPITAL["tipo_prestador"],
            cnpj=HOSPITAL["cnpj"],
            unidade_id=HOSPITAL["unidade_id"],
            unidade_nome=HOSPITAL["unidade_nome"],
            unidade_tipo=HOSPITAL["unidade_tipo"],
        )
        conn.commit()

        print()
        print("[4] USF de teste")
        _garantir_usuario(conn, USF["cnpj"], USF["nome"], USF["role"])
        _garantir_prestador(
            conn,
            org_id=USF["org_id"],
            nome=USF["nome"],
            tipo=USF["tipo_prestador"],
            cnpj=USF["cnpj"],
            unidade_id=USF["unidade_id"],
            unidade_nome=USF["unidade_nome"],
            unidade_tipo=USF["unidade_tipo"],
        )
        conn.commit()

    finally:
        conn.close()

    print()
    print("─────────────────────────────────────────────────────")
    print("  Resumo de credenciais DEV (senha: Teste@2024)")
    print()
    print(f"  Prescritor   CNS  {PRESCRITOR['cns']}")
    print(f"  Farmácia     CNPJ {FARMACIA['cnpj']}   org_id={FARMACIA['org_id']}")
    print(f"  Hospital     CNPJ {HOSPITAL['cnpj']}   org_id={HOSPITAL['org_id']}")
    print(f"  USF          CNPJ {USF['cnpj']}   org_id={USF['org_id']}")
    print()
    print("  DEV_PRESET_CONTEXT=true nos três frontends.")
    print("  Altere para false antes de publicar em produção.")
    print("─────────────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
