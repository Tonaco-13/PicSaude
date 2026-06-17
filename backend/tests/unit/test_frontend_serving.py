"""Unit — decisão de servir o frontend pela própria casa (vitrine "uma casa só").

Cobre `app.domain.frontend_serving.resolve_frontend_dir` (pura, sem DB/FastAPI),
incluindo a invariante de segurança: em prod NUNCA serve (expõe só a API).
"""
from __future__ import annotations

from pathlib import Path

from app.domain.frontend_serving import resolve_frontend_dir


def _com_index(d: Path) -> Path:
    (d / "index.html").write_text("<!doctype html>", encoding="utf-8")
    return d


def test_prod_nunca_serve(tmp_path):
    _com_index(tmp_path)
    # mesmo com diretório válido, prod expõe só a API
    assert resolve_frontend_dir("prod", str(tmp_path), tmp_path) is None


def test_demo_stg_serve_via_override(tmp_path):
    _com_index(tmp_path)
    # override (PICSAUDE_FRONTEND_DIR) tem prioridade — caso do Docker
    assert resolve_frontend_dir("stg", str(tmp_path), Path("/nao/existe")) == tmp_path


def test_dev_usa_base_default_quando_sem_override(tmp_path):
    _com_index(tmp_path)
    assert resolve_frontend_dir("dev", "", tmp_path) == tmp_path


def test_sem_index_retorna_none(tmp_path):
    # diretório existe mas não tem a porta de entrada → não serve
    assert resolve_frontend_dir("dev", "", tmp_path) is None


def test_override_inexistente_retorna_none(tmp_path):
    assert resolve_frontend_dir("stg", str(tmp_path / "nao_existe"), tmp_path) is None
