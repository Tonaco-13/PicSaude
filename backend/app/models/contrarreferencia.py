from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Contrarreferencia(Base):
    """
    Contrarreferência — objeto sanitário DERIVADO do Encaminhamento (E2).

    Espelha laudo ↔ pedido_exame: autor próprio (o prescritor de destino),
    documento canônico + hash próprios, `origem_encaminhamento_id` apontando ao
    encaminhamento que a originou.

    Identidade do autor por CNS (string, NOT NULL) — mesmo padrão de
    `encaminhamentos.cns_destino`: o destino é identificado por CNS sem exigir
    uma linha em `prescritores`. `autor_id` é FK best-effort (nullable).
    """

    __tablename__ = "contrarreferencias"

    id                          = Column(Integer, primary_key=True, autoincrement=True)
    protocolo                   = Column(String(50), unique=True, nullable=False, index=True)
    cns_autor                   = Column(String(20), nullable=False)   # destino — identidade/ownership
    autor_id                    = Column(Integer, ForeignKey("prescritores.id"), nullable=True)
    paciente_id                 = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    origem_encaminhamento_id    = Column(Integer, ForeignKey("encaminhamentos.id"), nullable=False, index=True)
    conteudo_clinico            = Column(Text, nullable=False)          # SENSÍVEL — nunca no /public
    status                      = Column(String(30), nullable=False, default="registrada")
    tipo_emissao                = Column(String(20), nullable=False, default="novo")
    origem_contrarreferencia_id = Column(Integer, ForeignKey("contrarreferencias.id"), nullable=True)
    assinatura_hash             = Column(String(64), nullable=True)
    data_emissao                = Column(String(10), nullable=False)
    criado_em                   = Column(DateTime, server_default=func.now(), nullable=False)
