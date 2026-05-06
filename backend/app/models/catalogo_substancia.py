"""
catalogo_substancia.py
======================
Model SQLAlchemy — Ticket 20 — Catálogo regulatório de substâncias.

Propósito
---------
Oráculo local de classificação regulatória por DCB (Denominação Comum
Brasileira). Permite ao motor regulatório validar a coerência entre a
classificação declarada pelo prescritor (`classe_controle` /
`tipo_retencao`) e o que a Anvisa publica como verdade regulatória.

NÃO é fonte primária — `prescricao_itens.classe_controle` e
`prescricao_itens.tipo_retencao` continuam sendo a fonte-de-verdade
para roteamento. O catálogo é um oráculo de validação que produz
ALERTAS (não bloqueios) em fase 1.

Características
---------------
- Chave de unicidade: `dcb_normalizada` (lowercase, sem acentos,
  combinações com " + " padronizadas — ver `domain/catalogo_regulatorio.py`)
- Coexistência: uma substância pode ter AMBOS `classe_controle` e
  `tipo_retencao` preenchidos (raro, mas legítimo). Motor regulatório
  resolve prioridade — Portaria 344 prevalece.
- `ativo=False` desativa sem deletar (ex: exenatida excluída da IN 360/2025).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from app.database import Base


class CatalogoSubstancia(Base):
    """Substância regulada — catálogo regulatório local (Ticket 20)."""

    __tablename__ = "catalogo_substancias"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # DCB legível (preserva acentos e capitalização da publicação Anvisa).
    dcb = Column(String(200), nullable=False)

    # DCB normalizada para lookup e unicidade.
    # Gerada por `domain/catalogo_regulatorio.normalizar_dcb()`.
    dcb_normalizada = Column(
        String(250), nullable=False, unique=True, index=True,
    )

    # DCB com capitalização para exibição em UI (autocomplete).
    dcb_display = Column(String(200), nullable=False)

    # Classe da Portaria SVS/MS 344/1998 (A1, A2, A3, B1, B2, C1..C5, D1, D2).
    # NULL = não classificada na Portaria 344.
    classe_controle = Column(String(10), nullable=True)

    # Tipo de retenção da RDC 471/2021 ("antimicrobiano", "glp1_agonista").
    # NULL = não classificada na RDC 471.
    tipo_retencao = Column(String(30), nullable=True)

    # Norma de origem do registro: "portaria_344", "in_83_2021",
    # "in_360_2025", etc. Permite auditoria e atualização rastreável.
    fonte = Column(String(100), nullable=False)

    # Notas regulatórias (opcional). Uso típico: classificação dupla,
    # exclusões temporárias, observações da publicação Anvisa.
    observacao = Column(Text, nullable=True)

    # Soft-delete: ativo=False mantém histórico mas remove do lookup.
    ativo = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
