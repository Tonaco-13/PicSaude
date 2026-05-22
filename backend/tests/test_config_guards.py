"""
Regressão do guard PICSAUDE_JWT_SECRET em backend/app/main.py.

Estratégia (5D do PLANO-PRODUCAO-V2.md):
  - 5 testes diretos da função pura `_validate_jwt_secret_at_boot`
    (prod+default bloqueia, prod+curto bloqueia, prod+forte ok,
     dev+default ok, test+default ok).
  - 1 smoke subprocess que valida IMPORT-TIME: `import app.main` em
    PICSAUDE_ENV=prod sem PICSAUDE_JWT_SECRET deve falhar com a
    mensagem do guard no stderr.

Origem: docs/PLANO-PRODUCAO-V2.md §5D — sem regressão, um refactor
futuro pode quebrar o guard silenciosamente.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.main import _validate_jwt_secret_at_boot


# ---- 1. prod + default placeholder → RuntimeError ---------------------------

def test_prod_com_secret_default_bloqueia():
    with pytest.raises(RuntimeError, match="INICIALIZAÇÃO BLOQUEADA"):
        _validate_jwt_secret_at_boot(
            "prod", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"
        )


# ---- 2. prod + secret curto (<32) → RuntimeError ----------------------------

def test_prod_com_secret_curto_bloqueia():
    with pytest.raises(RuntimeError, match="INICIALIZAÇÃO BLOQUEADA"):
        _validate_jwt_secret_at_boot("prod", "abc123")


# ---- 3. prod + secret forte → silencioso ------------------------------------

def test_prod_com_secret_forte_nao_bloqueia():
    # 64 chars hex = 32 bytes — limiar exato do guard (>= 32 caracteres)
    secret = "a" * 64
    _validate_jwt_secret_at_boot("prod", secret)  # não levanta


# ---- 4. dev + qualquer secret → silencioso ----------------------------------

def test_dev_com_default_nao_bloqueia():
    _validate_jwt_secret_at_boot(
        "dev", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"
    )


# ---- 5. test + qualquer secret → silencioso ---------------------------------

def test_test_com_default_nao_bloqueia():
    _validate_jwt_secret_at_boot(
        "test", "TROQUE_EM_PRODUCAO_use_secrets_token_hex_32"
    )


# ---- 6. smoke: IMPORT-TIME real dispara guard em prod ----------------------

def test_smoke_import_time_em_prod_falha():
    """
    Confirma que IMPORT-TIME continua disparando o guard.
    Subprocess isolado para escapar do conftest que seta PICSAUDE_ENV=test.

    IMPORTANTE: este teste NÃO depende de DB; mesmo se app.main tentar
    importar outras coisas e falhar por motivo ortogonal, a mensagem do
    guard JWT deve aparecer ANTES (ordem em main.py: chamada após
    `from app.config import ...`).
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ, "PICSAUDE_ENV": "prod"}
    env.pop("PICSAUDE_JWT_SECRET", None)  # força uso do default

    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        env=env,
        cwd=backend_dir,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0, (
        f"esperava exit code != 0; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "INICIALIZAÇÃO BLOQUEADA" in result.stderr, (
        f"esperava mensagem do guard no stderr; stderr={result.stderr!r}"
    )
    assert "PICSAUDE_JWT_SECRET" in result.stderr
