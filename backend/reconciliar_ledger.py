#!/usr/bin/env python3
"""
PicSaúde — Reconciliação do Ledger
====================================
Ticket 4: inserção de evento de reconciliação para prescrições
que existem sem nenhum evento no ledger (prescricao_eventos).

Regras absolutas:
  - NÃO deleta registros
  - NÃO altera status de prescrições
  - NÃO retrocede timestamps
  - NÃO usa tipo de evento de operação normal
  - Idempotente: não duplica evento de reconciliação
  - Aborta se encontrar escopo diferente de 1 prescrição órfã
  - NÃO inclui dados pessoais (CPF, nome) no payload

Tipo de evento: "RECONCILIACAO_MANUAL"
  - Coluna tipo_evento é VARCHAR livre (sem Enum/constraint)
  - Confirmado em Ticket 3 — sem necessidade de migration Alembic

Uso:
  python3 reconciliar_ledger.py [--db PATH]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_PROJECT_ROOT = Path(__file__).parent.parent
_DEFAULT_DB   = os.environ.get(
    "PIX_SAUDE_DB",
    str(_PROJECT_ROOT / "data" / "pix_saude_pe.db"),
)

TIPO_RECONCILIACAO = "RECONCILIACAO_MANUAL"
ATOR_TIPO          = "sistema"
ATOR_ID            = "reconciliar_ledger.py"


def _conn_rw(db_path: str):
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def reconciliar(db_path: str) -> None:
    import sqlite3

    db_path = os.path.abspath(db_path)
    if not os.path.exists(db_path):
        print(f"ERRO: banco não encontrado: {db_path}", file=sys.stderr)
        sys.exit(1)

    agora = datetime.now(timezone.utc).isoformat()
    print(f"\n{'='*60}")
    print(f"  PicSaúde — Reconciliação do Ledger")
    print(f"  Banco : {db_path}")
    print(f"  Início: {agora}")
    print(f"{'='*60}\n")

    conn = _conn_rw(db_path)
    try:
        # ── 1. Identificar prescrições sem nenhum evento ──────────────────
        orfas = conn.execute("""
            SELECT p.id, p.protocolo, p.status, p.tipo_emissao, p.created_at
            FROM prescricoes p
            LEFT JOIN prescricao_eventos pe ON pe.prescricao_id = p.id
            WHERE pe.id IS NULL
        """).fetchall()

        n_orfas = len(orfas)
        print(f"Prescrições sem evento encontradas: {n_orfas}")

        # ── 2. Controle de escopo ─────────────────────────────────────────
        if n_orfas == 0:
            print("Nada a fazer — nenhuma prescrição órfã. Encerrando sem commit.")
            return

        if n_orfas > 1:
            ids = [r["id"] for r in orfas]
            print(
                f"\nABORTADO — escopo inesperado: encontradas {n_orfas} prescrições "
                f"órfãs (ids={ids}). Esperado: exatamente 1.\n"
                f"Execute a auditoria (auditar_integridade_ledger.py) para investigar "
                f"antes de prosseguir.",
                file=sys.stderr,
            )
            sys.exit(2)

        # Exatamente 1 — prosseguir
        prescricao = orfas[0]
        pid        = prescricao["id"]
        protocolo  = prescricao["protocolo"]

        print(f"  → id={pid}  protocolo={protocolo}  status={prescricao['status']}")

        # ── 3. Idempotência: verificar se já existe evento de reconciliação ─
        ja_existe = conn.execute("""
            SELECT id FROM prescricao_eventos
            WHERE prescricao_id = ? AND tipo_evento = ?
        """, (pid, TIPO_RECONCILIACAO)).fetchone()

        if ja_existe:
            print(
                f"\nIdempotência: evento {TIPO_RECONCILIACAO!r} já existe "
                f"para prescricao_id={pid} (evento id={ja_existe['id']}). "
                f"Nada inserido."
            )
            return

        # ── 4. Montar payload — SEM dados pessoais (LGPD) ────────────────
        payload = {
            "natureza_correcao":               "reconciliacao_ledger",
            "evento_original_ausente":          "prescricao_emitida",
            "motivo":                           (
                "Reconciliação de integridade. Prescrição criada antes do "
                "módulo de ledger estar funcional. Inserção retroativa de "
                "rastreabilidade via Ticket 4."
            ),
            "data_emissao_original":            prescricao["created_at"],
            "status_no_momento_da_auditoria":   prescricao["status"],
            "tipo_emissao":                     prescricao["tipo_emissao"],
            "protocolo":                        protocolo,
            "ticket_referencia":                "TICKET-4-RECONCILIACAO",
            "executor":                         ATOR_ID,
        }
        # Garantia explícita: sem CPF, sem nome
        for campo_proibido in ("cpf", "nome", "paciente", "cpf_paciente"):
            assert campo_proibido not in payload, (
                f"LGPD: campo proibido '{campo_proibido}' detectado no payload"
            )

        # ── 5. Inserção ───────────────────────────────────────────────────
        conn.execute("""
            INSERT INTO prescricao_eventos
                   (prescricao_id, tipo_evento, ator_tipo, ator_id, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            pid,
            TIPO_RECONCILIACAO,
            ATOR_TIPO,
            ATOR_ID,
            json.dumps(payload, ensure_ascii=False),
            agora,
        ))

        conn.commit()

        print(f"\n  ✓ Evento {TIPO_RECONCILIACAO!r} inserido para id={pid}")
        print(f"  ✓ created_at do evento: {agora}  (timestamp atual — não retroativo)")
        print(f"  ✓ COMMIT realizado")

    except Exception as exc:
        conn.rollback()
        print(f"\nERRO — rollback executado: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()

    print(f"\n{'='*60}")
    print(f"  Reconciliação concluída")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="PicSaúde — Reconciliação do Ledger (Ticket 4)"
    )
    parser.add_argument(
        "--db", default=_DEFAULT_DB,
        help="Caminho para o banco SQLite (default: pix_saude_pe.db)",
    )
    args = parser.parse_args()
    reconciliar(args.db)


if __name__ == "__main__":
    main()
