# conftest.py raiz (backend/) — configura sys.path e ambiente de testes
# ANTES de qualquer importação de app.*
import os
import sys

# ---------------------------------------------------------------------------
# Top-level (executado antes de coleta) — evita o guard de prod em
# app/main.py (linhas ~32–69) que dispara em IMPORT-TIME se
# PICSAUDE_ENV=prod com SQLite. Fixtures autouse rodam DEPOIS dos imports
# do TestClient — não pegam isso. setdefault preserva PICSAUDE_ENV
# explícita do operador (ex.: rodar pytest em ambiente de produção
# detectaria o guard, comportamento intencional).
# ---------------------------------------------------------------------------
os.environ.setdefault("PICSAUDE_ENV", "test")

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


@pytest.fixture(autouse=True)
def _reset_instance_id_cache():
    """
    Reseta o cache de instance_id antes de cada teste (4E.2 §3.1.1).

    O cache em ``app/instance.py`` é módulo-level e persiste entre testes
    dentro do mesmo processo pytest. Sem este reset:
      - Testes que populam o cache via DB (integration) deixam um valor
        cacheado que faz ``test_get_instance_id_conn_funciona_com_pgconnection_wrapper``
        pular o ramo de SELECT/INSERT e falhar na asserção de SQL capturado.
      - Testes com banco SQLite tmp_path diferente cada vez ficariam
        servindo o instance_id de um banco anterior.

    Custo: < 1µs por teste; benefício: isolamento completo.
    """
    from app.instance import _reset_cache_for_tests
    _reset_cache_for_tests()
    yield
    _reset_cache_for_tests()


@pytest.fixture(autouse=True, scope="session")
def _disable_lifespan_bootstrap():
    """
    Neutraliza ``_lifespan_bootstrap`` em testes (CODEX rodada 5 P2).

    ``with TestClient(app)`` dispara o lifespan, que em produção/dev
    chama ``get_instance_id(session)`` contra o ``SessionLocal`` global —
    o que tocaria o DB real (``data/pix_saude_pe.db``). Em testes,
    queremos isolamento total via ``DATABASE_URL`` per-test.

    NÃO usa ``PICSAUDE_INSTANCE_ID`` global porque isso faria
    ``get_instance_id_conn`` curto-circuitar SEMPRE, quebrando o teste
    15 da 4C (``test_get_instance_id_conn_funciona_com_pgconnection_wrapper``):
    ele espera capturar ``INSERT ... RETURNING chave`` no fake PG.

    Testes que precisam exercitar o lifespan real (ex.: futuros testes
    do startup hook) devem usar fixture local que para o patch (ex.:
    ``mock.patch.stopall()`` ou um patch sobreposto).
    """
    from unittest.mock import patch
    with patch("app.main._lifespan_bootstrap", lambda: None):
        yield
