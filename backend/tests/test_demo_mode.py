"""
TICKET-6 — testes do DEMO_MODE.

Estratégia (§5 + P3#9 do ticket):
- Função pura `_validate_demo_mode_at_boot` é testada em
  tests/test_config_guards.py (mesmo padrão do 5D).
- Aqui cobrimos a camada HTTP construindo FastAPI mínimos com os routers
  alvo + monkeypatch de `app.routers.{demo,config_publico}.PICSAUDE_DEMO_MODE`
  para evitar reload de módulos (config é import-time).
- §5.7 PDF watermark cobre o caminho `is_demo=True` direto na função pura.

Os cenários cobertos correspondem a §5.1, §5.2, §5.3, §5.4, §5.5, §5.5b,
§5.7. §5.6 (isolamento DB), §5.8 (banner UI render) e §5.9 (instance_id no
ledger) ficam para verificação manual / Etapa 8 (precisam de subprocess
+ ambiente completo de DB; trade-off documentado).
"""
from __future__ import annotations

import pytest
from jose import jwt as _jwt_lib
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import JWT_ALGORITHM, JWT_SECRET
from app.routers import config_publico as _config_publico_mod
from app.routers import demo as _demo_mod


# ---------------------------------------------------------------------------
# Fábrica de TestClient com flag controlada
# ---------------------------------------------------------------------------

def _make_client(*, demo_mode: bool, demo_admin: bool = False) -> TestClient:
    """
    Cria FastAPI mínimo com o demo router + config_publico montados.
    Monkeypatches os flags ao nível do módulo (técnica para evitar
    importlib.reload do app.config).
    """
    # Patch dos flags importados nos módulos dos routers.
    _demo_mod.PICSAUDE_DEMO_MODE = demo_mode
    _demo_mod.PICSAUDE_DEMO_ADMIN = demo_admin
    _config_publico_mod.PICSAUDE_DEMO_MODE = demo_mode
    _config_publico_mod.PICSAUDE_DEMO_ADMIN = demo_admin

    app = FastAPI()
    app.include_router(_config_publico_mod.router)
    if demo_mode:
        app.include_router(_demo_mod.router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_demo_module_flags():
    """Restaura flags do módulo demo após cada teste (evita vazamento)."""
    yield
    from app.config import PICSAUDE_DEMO_ADMIN, PICSAUDE_DEMO_MODE
    _demo_mod.PICSAUDE_DEMO_MODE = PICSAUDE_DEMO_MODE
    _demo_mod.PICSAUDE_DEMO_ADMIN = PICSAUDE_DEMO_ADMIN
    _config_publico_mod.PICSAUDE_DEMO_MODE = PICSAUDE_DEMO_MODE
    _config_publico_mod.PICSAUDE_DEMO_ADMIN = PICSAUDE_DEMO_ADMIN


# ===========================================================================
# §5.1 boot com flag carrega /demo/*; sem flag → 404
# ===========================================================================

def test_demo_info_disponivel_com_flag():
    client = _make_client(demo_mode=True)
    r = client.get("/demo/info")
    assert r.status_code == 200
    body = r.json()
    personas = body["personas"]
    roles = sorted(p["role"] for p in personas)
    assert roles == ["dispensador", "paciente", "prescritor"]


def test_demo_info_404_sem_flag():
    client = _make_client(demo_mode=False)
    r = client.get("/demo/info")
    assert r.status_code == 404


# ===========================================================================
# §5.2 /demo/login emite JWT com sub canônico por role
# ===========================================================================

_EXPECTED_SUB = {
    "prescritor":  "980001112223334",
    "dispensador": "99999999000191",
    "paciente":    "12345678909",
}


@pytest.mark.parametrize("role", ["prescritor", "dispensador", "paciente"])
def test_demo_login_emite_jwt_correto(role: str):
    client = _make_client(demo_mode=True)
    r = client.post("/demo/login", json={"role": role})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["role"] == role
    assert body["sub"] == _EXPECTED_SUB[role]
    assert "Demo" in body["nome"] or "Dra. Demo" in body["nome"]

    payload = _jwt_lib.decode(body["access_token"], JWT_SECRET, algorithms=[JWT_ALGORITHM])
    assert payload["role"] == role
    assert payload["sub"] == _EXPECTED_SUB[role]
    assert payload["tipo"] == "access"


def test_demo_login_sem_flag_retorna_404():
    client = _make_client(demo_mode=False)
    r = client.post("/demo/login", json={"role": "prescritor"})
    assert r.status_code == 404


# ===========================================================================
# §5.3 endpoints OTP/login bloqueados — testa o helper _reject_if_demo
# ===========================================================================

def test_reject_if_demo_bloqueia_login_helper(monkeypatch):
    """Garante que _reject_if_demo (login.py + auth.py) levanta 403
    demo_mode_ativo quando o flag estiver ligado. Aqui chamamos a função
    pura diretamente — mais simples que reload de modulo e fiel ao
    comportamento de todos os 8 handlers que a invocam."""
    from app.routers import login as login_mod
    from app.routers import auth as auth_mod

    # Cenário ligado: levanta
    monkeypatch.setattr(login_mod, "PICSAUDE_DEMO_MODE", True)
    monkeypatch.setattr(auth_mod, "PICSAUDE_DEMO_MODE", True)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        login_mod._reject_if_demo()
    assert exc.value.status_code == 403
    assert exc.value.detail["codigo"] == "demo_mode_ativo"
    with pytest.raises(HTTPException) as exc2:
        auth_mod._reject_if_demo()
    assert exc2.value.status_code == 403
    assert exc2.value.detail["codigo"] == "demo_mode_ativo"

    # Cenário desligado: silencioso
    monkeypatch.setattr(login_mod, "PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr(auth_mod, "PICSAUDE_DEMO_MODE", False)
    login_mod._reject_if_demo()   # não levanta
    auth_mod._reject_if_demo()    # não levanta


def test_handlers_login_chamam_reject_if_demo():
    """Verificação estrutural: cada um dos 8 handlers deve injetar
    `Depends(_reject_if_demo)` na assinatura. Capturada regressão se
    alguém remover o guard de um handler.

    TICKET-6.1 P2#4 — o helper virou dependency (executada antes de
    require_role); o padrão antigo `_reject_if_demo()` no corpo foi
    descontinuado.
    """
    from pathlib import Path
    base = Path(__file__).resolve().parent.parent / "app" / "routers"
    login_src = (base / "login.py").read_text()
    auth_src = (base / "auth.py").read_text()
    # 6 dependencies em login.py + 2 em auth.py = 8.
    assert login_src.count("Depends(_reject_if_demo)") == 6
    assert auth_src.count("Depends(_reject_if_demo)") == 2
    # `_reject_if_demo()` deve aparecer só na definição do helper (não há
    # mais chamadas no corpo dos handlers).
    assert login_src.count("_reject_if_demo()") == 1   # apenas o def
    assert auth_src.count("_reject_if_demo()") == 1    # apenas o def


# ===========================================================================
# §5.4 /config/public retorna estado E Cache-Control: no-store
# ===========================================================================

def test_config_public_com_demo_mode_true():
    client = _make_client(demo_mode=True, demo_admin=False)
    r = client.get("/config/public")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"   # P3#10
    body = r.json()
    assert body["demo_mode"] is True
    assert body["demo_admin"] is False
    assert sorted(body["demo_roles"]) == ["dispensador", "paciente", "prescritor"]
    assert body["proximo_reset"] is not None
    assert body["instance_id"] is None   # nunca expor


def test_config_public_com_demo_mode_false():
    client = _make_client(demo_mode=False)
    r = client.get("/config/public")
    assert r.status_code == 200
    body = r.json()
    assert body["demo_mode"] is False
    assert body["demo_roles"] == []
    assert body["proximo_reset"] is None


# ===========================================================================
# §5.5 admin fora do demo público; §5.5b admin dentro de DEMO_ADMIN=true
# ===========================================================================

def test_admin_fora_do_demo_publico():
    client = _make_client(demo_mode=True, demo_admin=False)
    r = client.post("/demo/login", json={"role": "admin"})
    assert r.status_code == 403
    assert r.json()["detail"]["codigo"] == "papel_demo_indisponivel"

    cfg = client.get("/config/public").json()
    assert "admin" not in cfg["demo_roles"]


def test_admin_dentro_do_demo_admin():
    client = _make_client(demo_mode=True, demo_admin=True)
    r = client.post("/demo/login", json={"role": "admin"})
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "admin"

    cfg = client.get("/config/public").json()
    assert "admin" in cfg["demo_roles"]


# ===========================================================================
# §5.7 PDF com marca d'água "DEMO" quando is_demo=True
# ===========================================================================

def _extract_pdf_streams(pdf_bytes: bytes) -> list[bytes]:
    """Descompacta streams do PDF (ReportLab usa ASCII85+Flate)."""
    import base64
    import re
    import zlib
    out: list[bytes] = []
    for m in re.finditer(rb"stream\n(.*?)endstream", pdf_bytes, re.DOTALL):
        raw = m.group(1).strip(b"\n")
        # Tenta ASCII85+Flate (formato comum do ReportLab).
        if raw.startswith(b"<~") or raw.endswith(b"~>") or b"~>" in raw[-10:]:
            try:
                dec85 = base64.a85decode(raw, adobe=True)
                out.append(zlib.decompress(dec85))
                continue
            except Exception:
                pass
        # Tenta só Flate.
        try:
            out.append(zlib.decompress(raw))
        except Exception:
            out.append(raw)
    return out


def test_pdf_marca_dagua_demo_quando_is_demo_true():
    from app.domain.pdf_prescricao import gerar_pdf_prescricao
    pdf = gerar_pdf_prescricao(
        protocolo="teste-watermark",
        status="pendente",
        tipo_emissao="nova",
        assinatura_modo=None,
        assinatura_hash=None,
        nivel_formal="operacional",
        data_emissao="2026-05-24T10:00:00",
        nome_prescritor="Dra. X",   # sem "DEMO" no nome
        cns_prescritor="980001112223334",
        nome_paciente="João Maria",
        cpf_paciente="12345678909",
        itens=[{"nome_medicamento": "AMOXICILINA", "concentracao": "500mg",
                "quantidade": 10, "posologia": "1cp 8/8h"}],
        is_demo=True,
    )
    streams = _extract_pdf_streams(pdf)
    assert any(b"DEMO" in s for s in streams), (
        "esperava marca d'água 'DEMO' em algum stream do PDF"
    )


def test_pdf_sem_marca_dagua_quando_is_demo_false():
    from app.domain.pdf_prescricao import gerar_pdf_prescricao
    pdf = gerar_pdf_prescricao(
        protocolo="teste-normal",
        status="pendente",
        tipo_emissao="nova",
        assinatura_modo=None,
        assinatura_hash=None,
        nivel_formal="operacional",
        data_emissao="2026-05-24T10:00:00",
        nome_prescritor="Dr. Real",
        cns_prescritor="123456789012345",
        nome_paciente="Paciente Real",
        cpf_paciente="11122233344",
        itens=[{"nome_medicamento": "AMOXICILINA", "concentracao": "100mg",
                "quantidade": 1, "posologia": "1x ao dia"}],
        is_demo=False,
    )
    streams = _extract_pdf_streams(pdf)
    assert not any(b"DEMO" in s for s in streams), (
        "sem is_demo, nenhum stream deveria conter 'DEMO'"
    )


# ===========================================================================
# TICKET-6.1 — P1#1 isolamento CNES, P2#4 dependency order, P2#5 seed guard
# ===========================================================================

def test_cnes_conn_em_demo_usa_db_demo(tmp_path):
    """
    P1#1 TICKET-6.1 — em DEMO_MODE, _get_cnes_conn() deve abrir o DB demo
    (via _resolve_sqlite_db_path), não o DB de produção.

    Subprocess para isolamento total (P3#9 TICKET-6 — importlib.reload
    poluiria as próximas centenas de testes da suite).
    """
    import os
    import subprocess
    import sys

    demo_db = tmp_path / "test_demo.db"
    demo_db.write_bytes(b"")
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ}
    env.pop("DATABASE_URL", None)  # força _USE_SQLITE
    env["PICSAUDE_DEMO_MODE"] = "true"
    env["PIX_SAUDE_DEMO_DB"]   = str(demo_db)
    env["PICSAUDE_ENV"]        = "dev"

    script = (
        "import sys, json;"
        "from app.domain.cnes_prescritor import _get_cnes_conn;"
        "c = _get_cnes_conn();"
        "rows = c.execute('PRAGMA database_list').fetchall();"
        "paths = [r[2] for r in rows if r[1] == 'main'];"
        "c.close();"
        "print(json.dumps({'paths': paths}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env, cwd=backend_dir,
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, (
        f"subprocess falhou. stderr={result.stderr!r}"
    )
    import json
    data = json.loads(result.stdout.strip().splitlines()[-1])
    paths = data["paths"]
    assert paths and str(demo_db) in paths[0], (
        f"esperava {demo_db} no PRAGMA database_list, obtido: {paths}"
    )


def test_registrar_em_demo_retorna_403_demo_mode_ativo(monkeypatch):
    """
    P2#4 TICKET-6.1 — POST /auth/registrar em DEMO_MODE deve devolver
    403 demo_mode_ativo, não 401 'Not authenticated'. O bug pré-fix era:
    require_role(admin) rodava primeiro (sem token) → 401 antes do 403.

    Fix: _reject_if_demo virou dependency e ficou ANTES de require_role.
    """
    # Monta TestClient mínimo com o login router, depois de monkeypatch do flag.
    from app.routers import login as login_mod
    monkeypatch.setattr(login_mod, "PICSAUDE_DEMO_MODE", True)

    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(login_mod.router)
    client = TestClient(app)

    r = client.post("/auth/registrar", json={
        "identificador": "12345678901",
        "senha":          "qualquer",
        "role":           "prescritor",
        "nome":           "Teste",
    })
    assert r.status_code == 403, (r.status_code, r.text)
    body = r.json()
    assert body.get("detail", {}).get("codigo") == "demo_mode_ativo"


def test_seed_demo_aborta_sem_demo_mode_flag():
    """
    P2#5 TICKET-6.1 — `python3 seed_demo.py` sem PICSAUDE_DEMO_MODE=true
    deve abortar com exit != 0 e mensagem citando a flag. Espelha o guard
    duplo já existente em scripts/reset_demo_db.py.
    """
    import os
    import subprocess
    import sys
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {**os.environ}
    env.pop("PICSAUDE_DEMO_MODE", None)
    env["PICSAUDE_ENV"] = "dev"
    result = subprocess.run(
        [sys.executable, "seed_demo.py"],
        env=env, cwd=backend_dir,
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode != 0, (
        f"esperava exit code != 0; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    combined = result.stdout + result.stderr
    assert "PICSAUDE_DEMO_MODE" in combined, (
        f"esperava menção a PICSAUDE_DEMO_MODE; combined={combined!r}"
    )
