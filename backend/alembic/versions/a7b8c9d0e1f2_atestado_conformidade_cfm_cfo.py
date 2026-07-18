"""Atestado pronto para imprimir e assinar — local/data, conselho, hora

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-07-18

TICKET-ATESTADO-CONFORMIDADE — o atestado já era um objeto sanitário íntegro
(protocolo, ledger, custódia, hash, PAdES), mas não era um documento que o CFM
aceitaria impresso. Faltavam três coisas na face do papel:

  - municipio_emissao — o CFM exige "local e data". A data já existia
                        (`data_documento`); o LOCAL não. Vira o fecho clássico
                        "Recife, 18/07/2026" acima da assinatura.

  - conselho +        — o atestado odontológico não é um atestado médico. O
    uf_registro         conselho (CFM|CFO) decide o título do documento, o
                        adjetivo do corpo e a sigla do registro. Ver
                        `domain/conselho_profissional.py` (fonte única).
                        `registro_profissional` passa a guardar só o NÚMERO;
                        a UF sai para coluna própria.

  - hora_inicio /     — atestado de comparecimento sem horário não comprova
    hora_fim            comparecimento. String "HH:MM", SEMPRE opcional: a
                        obrigatoriedade NÃO é condicionada à finalidade (que é
                        quase texto livre — condicionar seria frágil).

Nullable no SCHEMA, obrigatório no PAYLOAD
------------------------------------------
`municipio_emissao` é NULLABLE aqui e OBRIGATÓRIO em `AtestadoIn` (422 sem ele).
A coluna precisa aceitar NULL porque os atestados já emitidos não têm município e
NÃO PODEM ser reescritos — objeto sanitário emitido é imutável (CLAUDE.md §1).
Backfill com um município inventado seria falsificar o local de emissão de um
documento assinado. O NULL é honesto: "não declarado à época".

Mesma lógica em `conselho`: NULL → o PDF renderiza como sempre renderizou
("ATESTADO MÉDICO"), via `CONSELHO_PADRAO`. Legado não quebra.

Dual-DB: `String(n)` → VARCHAR(n) em ambos (SQLite + PostgreSQL). Idempotente via
`_column_exists()` — o banco demo é `create_all` (dívida #98) e já pode ter as
colunas.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUNAS = (
    (
        "municipio_emissao",
        sa.String(120),
        "Município de emissão — o 'local' exigido pelo CFM. NULL = atestado "
        "anterior ao TICKET-ATESTADO-CONFORMIDADE (não declarado à época); "
        "obrigatório no payload de emissão.",
    ),
    (
        "conselho",
        sa.String(10),
        "Conselho profissional emissor: CFM | CFO. Decide título, adjetivo do "
        "corpo e sigla do registro — ver domain/conselho_profissional.py. "
        "NULL = legado, renderiza como ATESTADO MÉDICO.",
    ),
    (
        "uf_registro",
        sa.String(2),
        "UF do registro no conselho regional ('PE' → 'CRM-PE 12345'). NULL = "
        "legado, quando registro_profissional guardava o texto completo.",
    ),
    (
        "hora_inicio",
        sa.String(5),
        "Início do comparecimento, 'HH:MM'. Sempre opcional — a exigência não é "
        "condicionada à finalidade.",
    ),
    (
        "hora_fim",
        sa.String(5),
        "Fim do comparecimento, 'HH:MM'. Sempre opcional.",
    ),
)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in cols


def upgrade() -> None:
    """Adiciona local de emissão, conselho/UF e horário (idempotente)."""
    for nome, tipo, comentario in _COLUNAS:
        if not _column_exists("atestados", nome):
            op.add_column(
                "atestados",
                sa.Column(nome, tipo, nullable=True, comment=comentario),
            )


def downgrade() -> None:
    """Remove as colunas de conformidade do atestado (idempotente)."""
    for nome, _tipo, _comentario in reversed(_COLUNAS):
        if _column_exists("atestados", nome):
            op.drop_column("atestados", nome)
