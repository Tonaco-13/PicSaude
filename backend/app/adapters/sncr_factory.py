"""
sncr_factory.py
===============
Ticket 16A — Seleção da implementação do SNCRAdapter.

PADRÃO
------
Factory simples baseada em variável de ambiente `SNCR_ADAPTER`:

  - "stub" (default) → SNCRStub (mock local, dev/teste)
  - "real"           → SNCRReal (Ticket 16B, ainda não implementado)

REGRA — SEM FALLBACK SILENCIOSO
-------------------------------
Se SNCR_ADAPTER="real" for configurado em produção ANTES da implementação
real existir, esta factory levanta `NotImplementedError`. NUNCA retorna
o stub em silêncio quando "real" foi pedido.

Mesmo padrão do guardrail de produção em `app/main.py` (PICSAUDE_ENV=prod
+ SQLite → erro explícito). A intenção é falhar alto e cedo, não rodar
silenciosamente em modo errado.
"""
from __future__ import annotations

import logging
import os

from app.adapters.sncr_interface import SNCRAdapter

logger = logging.getLogger(__name__)


SNCR_ADAPTER_ENV = "SNCR_ADAPTER"
SNCR_ADAPTER_DEFAULT = "stub"

VALORES_VALIDOS = ("stub", "real")


def get_sncr_adapter(conn=None) -> SNCRAdapter:
    """Retorna a implementação do SNCRAdapter configurada pelo ambiente.

    Variável de ambiente: `SNCR_ADAPTER`
      - "stub" (default): retorna SNCRStub
      - "real":           retorna SNCRReal (Ticket 16B; hoje levanta erro)

    Args:
        conn: conexão/transação ativa (ex.: a de `get_tx()`), opcional.
            DESENHO-TALAO-DIGITAL-SNCR.md §2 (G2) — lotes precisam
            sobreviver entre requests, então o stub persiste em
            `sncr_lotes` usando esta MESMA conexão (consumo de lote e
            escrita do receituário no mesmo commit/rollback — atômico,
            nunca um lote consumido sobrevive a uma escrita clínica que
            falhou). Sem `conn`, o adapter funciona como sempre funcionou
            (numeração sob demanda em memória); `adquirir_lote` fica
            indisponível nesse modo.

    Raises:
        NotImplementedError: SNCR_ADAPTER="real" antes do Ticket 16B existir.
        ValueError: SNCR_ADAPTER tem valor desconhecido.
    """
    adapter_type = os.environ.get(SNCR_ADAPTER_ENV, SNCR_ADAPTER_DEFAULT)

    if adapter_type == "stub":
        # Import tardio para manter o módulo factory leve (e evitar acoplamento
        # circular caso o stub precise importar algo da factory no futuro).
        from app.adapters.sncr_stub import SNCRStub
        return SNCRStub(conn=conn)

    if adapter_type == "real":
        # Falha explícita — NÃO faz fallback para stub.
        raise NotImplementedError(
            "SNCR_ADAPTER='real' configurado, mas a integração real com a "
            "Anvisa ainda não foi implementada (Ticket 16B). "
            "Aguardando especificação técnica da API do SNCR. "
            "Para desenvolvimento, use SNCR_ADAPTER=stub (ou deixe não definido)."
        )

    raise ValueError(
        f"{SNCR_ADAPTER_ENV}={adapter_type!r} é inválido. "
        f"Valores aceitos: {VALORES_VALIDOS}."
    )
