"""
app/observabilidade — módulo de observabilidade do PicSaúde (Ticket 11).

Exporta:
  metrics   — contadores globais em memória (por processo/worker)
  get_logger — logger estruturado reutilizável
"""
from app.observabilidade.metrics import metrics
from app.observabilidade.logging_config import get_logger, configure_logging

__all__ = ["metrics", "get_logger", "configure_logging"]
