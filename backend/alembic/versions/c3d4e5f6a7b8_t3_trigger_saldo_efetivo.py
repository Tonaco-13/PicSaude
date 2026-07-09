"""T3 — trigger Postgres: Σ efetivo (dispensado − estornado) ≤ prescrito

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-09

Rede de segurança no banco para a constraint Σ efetivo ≤ prescrito. A validação
amigável (mensagem 4xx) permanece no app (custodia.py/hospitalares.py); o
trigger é a última linha caso algo escreva em `dispensacoes` fora do endpoint.

Ciente do estorno (T2): compara Σ dispensado − Σ estornado (não só a soma das
dispensações — Flag 2 do Z AI). Só Postgres; no SQLite (dev) a validação de app
é suficiente.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_FN = """
CREATE OR REPLACE FUNCTION check_saldo_efetivo_dispensacao() RETURNS trigger AS $$
DECLARE
    v_prescrito  integer;
    v_dispensado integer;
    v_estornado  integer;
BEGIN
    SELECT quantidade INTO v_prescrito
      FROM prescricao_itens WHERE id = NEW.prescricao_item_id;

    SELECT COALESCE(SUM(quantidade_dispensada), 0) INTO v_dispensado
      FROM dispensacoes WHERE prescricao_item_id = NEW.prescricao_item_id;

    SELECT COALESCE(SUM(quantidade_estornada), 0) INTO v_estornado
      FROM estornos WHERE prescricao_item_id = NEW.prescricao_item_id;

    IF (v_dispensado - v_estornado) > COALESCE(v_prescrito, 0) THEN
        RAISE EXCEPTION
            'saldo efetivo excedido no item %: dispensado(%) - estornado(%) > prescrito(%)',
            NEW.prescricao_item_id, v_dispensado, v_estornado, v_prescrito;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite (dev): validação de app basta; sem plpgsql
    op.execute(_FN)
    op.execute(
        "DROP TRIGGER IF EXISTS trg_check_saldo_efetivo ON dispensacoes;"
    )
    op.execute(
        "CREATE TRIGGER trg_check_saldo_efetivo "
        "AFTER INSERT ON dispensacoes "
        "FOR EACH ROW EXECUTE FUNCTION check_saldo_efetivo_dispensacao();"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS trg_check_saldo_efetivo ON dispensacoes;")
    op.execute("DROP FUNCTION IF EXISTS check_saldo_efetivo_dispensacao();")
