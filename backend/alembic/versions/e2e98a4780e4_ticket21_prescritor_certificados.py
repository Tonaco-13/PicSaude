"""ticket21_prescritor_certificados

Cria a tabela `prescritor_certificados` (Ticket 21).

Armazena .pfx criptografados (AES-256-GCM) por prescritor, com
histórico de renovação/substituição/revogação.

Apenas UM certificado ativo por prescritor por vez. Isto é garantido
no nível de aplicação (endpoint marca ativo=FALSE no upload anterior).
Uma constraint única exige (prescritor_id, hash_cert_der) — impede
re-upload do mesmo cert.

Revision ID: e2e98a4780e4
Revises: 0c8654f77baf
Create Date: 2026-04-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'e2e98a4780e4'
down_revision: Union[str, Sequence[str], None] = '0c8654f77baf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    return inspect(bind).has_table(table)


def upgrade() -> None:
    if _table_exists("prescritor_certificados"):
        return

    op.create_table(
        "prescritor_certificados",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "prescritor_id", sa.Integer(),
            sa.ForeignKey("prescritores.id"), nullable=False,
        ),
        sa.Column("pfx_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("pfx_iv", sa.LargeBinary(length=12), nullable=False),
        sa.Column("pfx_tag", sa.LargeBinary(length=16), nullable=False),
        sa.Column("hash_cert_der", sa.String(64), nullable=False),
        sa.Column("serial", sa.String(100), nullable=False),
        sa.Column("valido_de", sa.DateTime(), nullable=False),
        sa.Column("valido_ate", sa.DateTime(), nullable=False),
        sa.Column("nome_no_certificado", sa.String(200), nullable=False),
        sa.Column("cpf_no_certificado", sa.String(11), nullable=False),
        sa.Column("emissor", sa.String(200), nullable=True),
        sa.Column(
            "ativo", sa.Boolean(), nullable=False, server_default=sa.true(),
        ),
        sa.Column("revogado_em", sa.DateTime(), nullable=True),
        sa.Column("substituido_em", sa.DateTime(), nullable=True),
        sa.Column(
            "uploaded_em", sa.DateTime(), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "prescritor_id", "hash_cert_der",
            name="uq_prescritor_cert_hash",
        ),
    )
    op.create_index(
        "ix_prescritor_certificados_prescritor_id",
        "prescritor_certificados",
        ["prescritor_id"],
    )
    # Lookup do certificado ativo (filtragem comum na assinatura)
    op.create_index(
        "ix_prescritor_certificados_ativo",
        "prescritor_certificados",
        ["prescritor_id", "ativo"],
    )


def downgrade() -> None:
    if not _table_exists("prescritor_certificados"):
        return
    op.drop_index(
        "ix_prescritor_certificados_ativo", "prescritor_certificados",
    )
    op.drop_index(
        "ix_prescritor_certificados_prescritor_id", "prescritor_certificados",
    )
    op.drop_table("prescritor_certificados")
