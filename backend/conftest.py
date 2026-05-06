# conftest.py raiz (backend/) — configura sys.path ANTES de qualquer importação.
import os
import sys

import pytest

# Garante que 'app' seja importável como pacote de backend/
# abspath resolve __file__ relativo (ocorre quando pytest é invocado com path explícito)
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)


@pytest.fixture(autouse=True, scope="session")
def _disable_rate_limit_in_tests():
    """Desativa rate limiting globalmente durante testes.

    O middleware verifica RATE_LIMIT_DISABLED antes de contar requisições,
    permitindo que a suíte de testes faça chamadas repetidas sem receber 429.
    """
    os.environ["RATE_LIMIT_DISABLED"] = "1"
    yield
    del os.environ["RATE_LIMIT_DISABLED"]
