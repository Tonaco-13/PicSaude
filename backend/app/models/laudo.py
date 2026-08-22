from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class Laudo(Base):
    """
    Laudo clínico/laboratorial — artefato produzido pelo prestador.

    tipo_agregacao_status = "direto" (ver domain/states_laudo.py)

    Status possíveis (ver domain/states_laudo.py):
        em_producao · assinado · liberado
        ciencia_paciente · ciencia_prescritor
        encerrado · cancelado · expirado · encerrado_fisico

    autor_id:
        Referencia o responsável técnico pelo laudo (patologista, bioquímico,
        médico laboratorista). Usa a tabela prescritores como registro genérico
        de profissionais de saúde identificados por CNS.
        Ver NUCLEO_SANITARIO.md v1.1 — seção 1 (autor_id).
    """

    __tablename__ = "laudos"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    protocolo         = Column(String(50), unique=True, nullable=False, index=True)
    autor_id          = Column(Integer, ForeignKey("prescritores.id"), nullable=True)
    paciente_id       = Column(Integer, ForeignKey("pacientes.id"), nullable=True)
    pedido_id         = Column(Integer, ForeignKey("pedidos_exame.id"), nullable=True)
    status            = Column(String(30), nullable=False, default="em_producao")
    tipo_emissao      = Column(String(20), nullable=False, default="novo")
    origem_laudo_id   = Column(Integer, ForeignKey("laudos.id"), nullable=True)
    data_emissao      = Column(String(10), nullable=False)    # ISO 8601 date
    data_validade     = Column(String(10), nullable=True)     # NULL para físico
    assinatura_hash   = Column(String(64), nullable=True)     # SHA-256 do documento canônico
    # ENG-014 (PR C): carimbo da PRIMEIRA abertura pelo cidadão. NULL = nunca
    # aberto — e é a ausência que distingue "não lido" de "lido". Informativo:
    # alimenta o selo "Lido em" do Histórico da clínica e NUNCA condiciona
    # faturamento (martelo (b): o fato financeiro é a liberação, da unidade).
    aberto_em         = Column(DateTime, nullable=True)
    criado_em         = Column(DateTime, server_default=func.now(), nullable=False)
