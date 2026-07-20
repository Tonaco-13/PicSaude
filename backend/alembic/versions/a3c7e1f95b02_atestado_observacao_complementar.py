"""atestado_observacao_complementar

Adiciona `atestados.observacao_complementar` (TICKET-ATESTADO-RASCUNHO-ESPELHO).

O que é
-------
Texto livre OPCIONAL que o profissional acrescenta ao atestado. Aparece como
parágrafo próprio depois do corpo, tanto no rascunho de conferência quanto no
PDF oficial — os dois consomem `domain/texto_atestado.corpo_atestado`.

Por que ACRESCENTA e não substitui o corpo
------------------------------------------
Corpo editável deixaria o texto CONTRADIZER os campos estruturados: bastaria
escrever "5 dias" com `dias_afastamento=3` no banco para que o documento e a
carteira do cidadão divergissem — que é exatamente a classe de defeito que este
ticket fecha. A observação dá liberdade de redação sem disputar a autoridade dos
campos.

Entra no documento canônico
---------------------------
Diferente de `cid_consta_na_base` (metadado de qualidade do NOSSO catálogo, e por
isso fora do hash — CLAUDE.md §2a R1), a observação é CONTEÚDO do atestado: está
impressa no documento que o profissional assina. Fora do hash, dois atestados com
observações diferentes teriam a mesma impressão digital. Entra, portanto, em
`_calcular_hash_atestado`, que sobe para `versao_esquema = "3"`.

Legado: NULL. O hash dos atestados já emitidos é gravado uma vez na emissão e
nunca recalculado (CLAUDE.md §1), então nenhum documento existente muda.

Revision ID: a3c7e1f95b02
Revises: f2b7c1d0a4e5
Create Date: 2026-07-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision: str = "a3c7e1f95b02"
down_revision: Union[str, Sequence[str], None] = "f2b7c1d0a4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona observacao_complementar a atestados (idempotente)."""
    if not _column_exists("atestados", "observacao_complementar"):
        op.add_column(
            "atestados",
            sa.Column(
                "observacao_complementar",
                sa.Text(),
                nullable=True,
                comment=(
                    "Texto livre opcional impresso como parágrafo próprio depois "
                    "do corpo do atestado. ACRESCENTA ao texto gerado, nunca o "
                    "substitui — os campos estruturados seguem sendo a autoridade "
                    "sobre dias, datas e finalidade. Entra no documento canônico "
                    "(versao_esquema 3). NULL = não declarada (inclui todo o legado)."
                ),
            ),
        )


def downgrade() -> None:
    """Remove observacao_complementar de atestados (idempotente)."""
    if _column_exists("atestados", "observacao_complementar"):
        op.drop_column("atestados", "observacao_complementar")
