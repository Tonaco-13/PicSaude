"""
Auditoria de segurança (Jules) — correções F1 e F5 da cadeia de assinatura A1.

F1 — cofre_pfx falha fechado: cifrar/decifrar recusam a chave-sentinela
     insegura fora de dev/test (stg/prod exigem PFX_ENCRYPTION_KEY).
F5 — endpoints de certificado/assinatura bloqueados (403 demo_mode_ativo) em
     PICSAUDE_DEMO_MODE (vitrine pública não manipula chave real).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.domain import cofre_pfx
from app.domain.cofre_pfx import (
    CofreChaveInsegura,
    chave_eh_segura,
    cifrar_pfx,
    decifrar_pfx,
)


# ===========================================================================
# F1 — cofre falha fechado fora de dev/test
# ===========================================================================

def test_f1_dev_sem_chave_permite_sentinela(monkeypatch):
    """Em dev (default), sem PFX_ENCRYPTION_KEY, o cofre opera com a sentinela."""
    monkeypatch.delenv("PFX_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("PICSAUDE_ENV", "dev")
    c = cifrar_pfx(b"conteudo-pfx-falso")
    assert decifrar_pfx(c.cifrado, c.iv, c.tag) == b"conteudo-pfx-falso"
    assert chave_eh_segura() is False


@pytest.mark.parametrize("env", ["stg", "prod", "homolog"])
def test_f1_falha_fechado_sem_chave_em_ambiente_real(monkeypatch, env):
    """Em stg/prod (qualquer ambiente != dev/test), ausência de chave recusa."""
    monkeypatch.delenv("PFX_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("PICSAUDE_ENV", env)
    with pytest.raises(CofreChaveInsegura):
        cifrar_pfx(b"conteudo")
    with pytest.raises(CofreChaveInsegura):
        decifrar_pfx(b"x", b"0" * 12, b"0" * 16)


def test_f1_chave_real_opera_em_prod(monkeypatch):
    """Com PFX_ENCRYPTION_KEY válida, o cofre opera normalmente mesmo em prod."""
    monkeypatch.setenv("PICSAUDE_ENV", "prod")
    monkeypatch.setenv("PFX_ENCRYPTION_KEY", "ab" * 32)  # 64 hex chars → 32 bytes
    assert chave_eh_segura() is True
    c = cifrar_pfx(b"conteudo")
    assert decifrar_pfx(c.cifrado, c.iv, c.tag) == b"conteudo"


# ===========================================================================
# F5 — endpoints de certificado/assinatura bloqueados em DEMO_MODE
# ===========================================================================

def test_f5_upload_certificado_bloqueado_em_demo(monkeypatch):
    """POST /prescritor/certificado deve devolver 403 demo_mode_ativo em demo.

    Chamamos o handler direto (técnica do test_demo_mode.py) com o flag do
    módulo ligado; o guard é a primeira instrução do corpo.
    """
    from app.routers import prescritor as presc_mod
    monkeypatch.setattr(presc_mod, "PICSAUDE_DEMO_MODE", True)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(presc_mod.upload_certificado(usuario={"sub": "980001112223334"}))
    assert exc.value.status_code == 403
    assert exc.value.detail["codigo"] == "demo_mode_ativo"


def test_f5_assinatura_pdf_bloqueada_em_demo(monkeypatch):
    """POST /receituarios/.../pdf-assinado deve devolver 403 demo_mode_ativo."""
    from app.routers import receituarios as rec_mod
    monkeypatch.setattr(rec_mod, "PICSAUDE_DEMO_MODE", True)

    with pytest.raises(HTTPException) as exc:
        rec_mod.baixar_pdf_assinado(
            protocolo="qualquer",
            receituario_id=1,
            body=None,
            usuario={"sub": "980001112223334"},
        )
    assert exc.value.status_code == 403
    assert exc.value.detail["codigo"] == "demo_mode_ativo"
