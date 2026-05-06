"""
observabilidade/metrics.py — Ticket 11
=======================================
Contadores em memória por processo (per-worker).

Usa incrementos simples protegidos pelo GIL do Python — sem threading.Lock.
Adequado para async (event loop single-thread) e workers uvicorn com forks.

LIMITAÇÕES DOCUMENTADAS:
- Valores são por processo/worker uvicorn — não são agregados entre workers.
- Resetam a zero em cada reinicialização.
- Não persistem em banco ou arquivo.
- Para observabilidade real em produção: integrar Prometheus/Grafana.
"""
from __future__ import annotations


class _Metrics:
    __slots__ = (
        "requests_total",
        "errors_total",
        "errors_4xx",
        "errors_5xx",
        "_latency_sum_ms",
        "_latency_count",
        "_last_latency_ms",
    )

    def __init__(self) -> None:
        self.requests_total: int = 0
        self.errors_total: int = 0
        self.errors_4xx: int = 0
        self.errors_5xx: int = 0
        self._latency_sum_ms: float = 0.0
        self._latency_count: int = 0
        self._last_latency_ms: float = 0.0

    def record_request(self, status_code: int, latency_ms: float) -> None:
        self.requests_total += 1
        self._latency_sum_ms += latency_ms
        self._latency_count += 1
        self._last_latency_ms = latency_ms
        if status_code >= 500:
            self.errors_total += 1
            self.errors_5xx += 1
        elif status_code >= 400:
            self.errors_total += 1
            self.errors_4xx += 1

    @property
    def latency_avg_ms(self) -> float:
        if self._latency_count == 0:
            return 0.0
        return round(self._latency_sum_ms / self._latency_count, 2)

    def snapshot(self) -> dict:
        return {
            "requests_total": self.requests_total,
            "errors_total": self.errors_total,
            "errors_4xx": self.errors_4xx,
            "errors_5xx": self.errors_5xx,
            "latency_avg_ms": self.latency_avg_ms,
            "last_latency_ms": round(self._last_latency_ms, 2),
        }


metrics = _Metrics()
