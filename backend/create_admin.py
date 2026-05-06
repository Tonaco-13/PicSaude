"""
create_admin.py
===============
Script idempotente de criação do administrador inicial do PicSaúde (G5-impl).

Uso (dentro do container ou com o banco configurado):
    python3 create_admin.py

Variáveis de ambiente lidas:
    PICSAUDE_ADMIN_EMAIL   — e-mail / identificador do admin
    PICSAUDE_ADMIN_NOME    — nome do administrador
    PICSAUDE_ADMIN_SENHA   — senha inicial (troque após o primeiro login)
    PICSAUDE_VERSION       — versão do núcleo (padrão: 1.0.0)
    PICSAUDE_INSTANCE_ORG_ID — org_id da instância
    PICSAUDE_INSTANCE_NAME   — nome legível da instituição
    PIX_SAUDE_DB           — caminho do banco SQLite

Comportamento:
    - Idempotente: se já existir um admin com o mesmo e-mail, não cria duplicata.
    - Registra metadados de instalação em meta_instalacao (chave→valor).
    - Saída clara no terminal com status final.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Garantir que o pacote `app` seja encontrado
sys.path.insert(0, os.path.dirname(__file__))

from app.auth.jwt import hash_senha
from app.database import get_conn

# ---------------------------------------------------------------------------
# Leitura de variáveis de ambiente
# ---------------------------------------------------------------------------

ADMIN_EMAIL   = os.getenv("PICSAUDE_ADMIN_EMAIL", "").strip().lower()
ADMIN_NOME    = os.getenv("PICSAUDE_ADMIN_NOME", "Administrador").strip()
ADMIN_SENHA   = os.getenv("PICSAUDE_ADMIN_SENHA", "").strip()
VERSAO        = os.getenv("PICSAUDE_VERSION", "1.0.0")
ORG_ID        = os.getenv("PICSAUDE_INSTANCE_ORG_ID", "").strip()
INSTANCE_NAME = os.getenv("PICSAUDE_INSTANCE_NAME", "").strip()
BOOTSTRAP_VER = os.getenv("PICSAUDE_BOOTSTRAP_VERSION", "1.0.0")

SENHAS_PADRAO = {"TROCAR_IMEDIATAMENTE", "TROQUE_IMEDIATAMENTE", "", "admin", "admin123"}


def _validar_env() -> None:
    erros = []
    if not ADMIN_EMAIL:
        erros.append("PICSAUDE_ADMIN_EMAIL não definido.")
    if "@" not in ADMIN_EMAIL:
        erros.append(f"PICSAUDE_ADMIN_EMAIL inválido: '{ADMIN_EMAIL}'")
    if not ADMIN_SENHA:
        erros.append("PICSAUDE_ADMIN_SENHA não definido.")
    if ADMIN_SENHA in SENHAS_PADRAO:
        erros.append(
            "PICSAUDE_ADMIN_SENHA é o valor de exemplo — defina uma senha real."
        )
    if not ORG_ID:
        erros.append("PICSAUDE_INSTANCE_ORG_ID não definido.")
    if erros:
        for e in erros:
            print(f"  ❌ {e}")
        sys.exit(1)


def _criar_admin() -> bool:
    """Cria o admin se não existir. Retorna True se criou, False se já existia."""
    now = datetime.now(timezone.utc).isoformat()

    conn = get_conn()
    try:
        existente = conn.execute(
            "SELECT id, nome FROM usuarios WHERE identificador = ?",
            (ADMIN_EMAIL,),
        ).fetchone()

        if existente:
            print(f"  ℹ️  Admin já existe: {ADMIN_EMAIL} ({existente['nome']})")
            return False

        senha_hash = hash_senha(ADMIN_SENHA)
        conn.execute(
            """
            INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
            VALUES ('admin', ?, ?, ?, 1, ?, ?)
            """,
            (ADMIN_EMAIL, ADMIN_NOME, senha_hash, now, now),
        )
        conn.commit()
        print(f"  ✅ Admin criado: {ADMIN_EMAIL} ({ADMIN_NOME})")
        return True
    finally:
        conn.close()


def _registrar_meta() -> None:
    """Registra (ou atualiza) metadados de instalação na tabela meta_instalacao."""
    now = datetime.now(timezone.utc).isoformat()

    entradas = {
        "nucleo_version":    VERSAO,
        "schema_version":    "1",
        "org_id":            ORG_ID,
        "instance_name":     INSTANCE_NAME,
        "instalado_em":      now,
        "bootstrap_version": BOOTSTRAP_VER,
    }

    conn = get_conn()
    try:
        for chave, valor in entradas.items():
            # INSERT OR REPLACE → idempotente: atualiza se já existir
            conn.execute(
                "INSERT OR REPLACE INTO meta_instalacao (chave, valor, criado_em) VALUES (?, ?, ?)",
                (chave, valor, now),
            )
        conn.commit()
        print(f"  ✅ meta_instalacao registrada (versão {VERSAO}, org: {ORG_ID})")
    finally:
        conn.close()


def main() -> None:
    print("\n─────────────────────────────────────────────")
    print("  PicSaúde — Criação do administrador inicial")
    print("─────────────────────────────────────────────")

    print("\n[1] Validando variáveis de ambiente...")
    _validar_env()
    print("  ✅ Variáveis OK")

    print("\n[2] Verificando/criando admin...")
    _criar_admin()

    print("\n[3] Registrando metadados de instalação...")
    _registrar_meta()

    print("\n─────────────────────────────────────────────")
    print("  Bootstrap concluído com sucesso.")
    print(f"  Instância: {INSTANCE_NAME or ORG_ID}")
    print(f"  Admin:     {ADMIN_EMAIL}")
    print(f"  Versão:    {VERSAO}")
    print("─────────────────────────────────────────────\n")


if __name__ == "__main__":
    main()
