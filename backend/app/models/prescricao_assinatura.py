"""
prescricao_assinatura.py
========================
Metadados de assinatura digital de uma prescrição PicSaúde.

PROPÓSITO
---------
Armazenar os campos necessários para futura integração com ICP-Brasil
(token A1/A3) e gov.br (assinatura em nuvem), mesmo que na fase MVP
esses campos sejam registrados como stub e a validação criptográfica
ainda não seja realizada.

RELACIONAMENTO
--------------
- Um-para-um com `prescricoes` (UNIQUE em prescricao_id).
- Prescrições físicas (tipo_emissao='fisica') nunca terão registro aqui.
- A prescrição pode existir sem registro de assinatura; o registro é criado
  apenas quando o prescritor declara os metadados via POST /assinatura.

CICLO DE STATUS
---------------
nao_assinada → assinatura_pendente → assinada_valida
                                   → assinada_invalida
                                   → certificado_expirado
                                   → revogada

O status 'nao_assinada' não é armazenado nesta tabela: é inferido pela
ausência de linha. O registro nasce com 'assinatura_pendente' (MVP stub).

CAMPOS SENSÍVEIS
----------------
- dados_assinatura_b64: bytes brutos da assinatura (PKCS#7/CAdES) em Base64.
  Em produção, usar campo criptografado em repouso. Para o MVP, stub aceito.
- serial_certificado: identificador único do certificado digital.
  Necessário para verificação de revogação (CRL/OCSP).
"""

from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.database import Base


class PrescricaoAssinatura(Base):
    """
    Metadados de assinatura digital — um registro por prescrição.

    Colunas
    -------
    id                    PK
    prescricao_id         FK → prescricoes.id (UNIQUE: um por prescrição)
    tipo_certificado      'A1' | 'A3' | 'gov_br_nuvem' | None (stub)
    emissor               CN do certificado ICP-Brasil ou AC emissora
    serial_certificado    Número serial hex do certificado
    timestamp_assinatura  ISO 8601 — quando a assinatura foi aplicada (declarado)
    hash_documento        SHA-256 do documento canônico — deve coincidir com
                          prescricoes.assinatura_hash para garantir integridade
    dados_assinatura_b64  PKCS#7/CAdES em Base64 (stub: None no MVP)
    status_validacao      Estado de validação (ver domain/assinatura.py)
    detalhe_validacao     Mensagem de erro ou detalhe da última validação
    created_at            ISO 8601 UTC
    updated_at            ISO 8601 UTC
    """

    __tablename__ = "prescricao_assinatura"

    id = Column(Integer, primary_key=True, autoincrement=True)

    prescricao_id = Column(
        Integer,
        ForeignKey("prescricoes.id"),
        nullable=False,
        index=True,
    )

    # -----------------------------------------------------------------------
    # Identificação do certificado
    # -----------------------------------------------------------------------
    tipo_certificado   = Column(String, nullable=True)   # A1, A3, gov_br_nuvem
    emissor            = Column(String, nullable=True)   # CN do emissor / AC
    serial_certificado = Column(String, nullable=True)   # hex serial

    # -----------------------------------------------------------------------
    # Prova temporal
    # -----------------------------------------------------------------------
    timestamp_assinatura = Column(String, nullable=True)  # ISO 8601, declarado

    # -----------------------------------------------------------------------
    # Integridade do documento
    # -----------------------------------------------------------------------
    hash_documento = Column(String, nullable=True)        # SHA-256 canônico

    # -----------------------------------------------------------------------
    # Prova criptográfica (stub MVP)
    # -----------------------------------------------------------------------
    dados_assinatura_b64 = Column(Text, nullable=True)    # PKCS#7/CAdES em B64

    # -----------------------------------------------------------------------
    # Estado de validação
    # -----------------------------------------------------------------------
    status_validacao  = Column(String, nullable=False, default="assinatura_pendente")
    detalhe_validacao = Column(Text, nullable=True)

    # -----------------------------------------------------------------------
    # Timestamps de infraestrutura
    # -----------------------------------------------------------------------
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("prescricao_id", name="uq_prescricao_assinatura_prescricao"),
    )
