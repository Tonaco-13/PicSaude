"""
Sugestão de posologia usual (companheiro do semáforo) — motor determinístico.

Cobre app/domain/posologia_sugerida.py: canonicalização (reuso do semáforo),
linha vermelha (só serve `validado`) e o endpoint atrás da flag.
"""
from __future__ import annotations

import pytest

from app.domain.posologia_sugerida import carregar_posologias, sugerir


def _csv(tmp_path, linhas: str):
    p = tmp_path / "posologia.csv"
    p.write_text(
        "principio_ativo,posologia_usual,condicao_nome,codigo_cid,fonte,"
        "status_curadoria,validado_por,versao,observacao\n" + linhas,
        encoding="utf-8",
    )
    return str(p)


def test_so_serve_validado(tmp_path):
    caminho = _csv(
        tmp_path,
        "losartana,Tomar 1 cp 50 mg 1x/dia,HAS,I10,fonte,validado,Dr,v1,obs\n"
        "captopril,Tomar 1 cp 25 mg 2x/dia,HAS,I10,fonte,rascunho,,v0,obs\n",
    )
    idx = carregar_posologias(caminho)
    assert "losartana" in idx               # validado entra
    assert "captopril" not in idx           # rascunho fica de fora (linha vermelha)
    assert idx["losartana"].posologia.startswith("Tomar")
    assert idx["losartana"].validado_por == "Dr"


def test_canonicaliza_o_ativo(tmp_path):
    caminho = _csv(
        tmp_path,
        "losartana,Tomar 1 cp 50 mg 1x/dia,HAS,I10,fonte,validado,Dr,v1,\n",
    )
    idx = carregar_posologias(caminho)
    # "Losartana Potássica" canoniza para "losartana" (mesma regra do semáforo)
    from app.domain.posologia_sugerida import _CACHE  # noqa
    import app.domain.posologia_sugerida as ps
    ps._CACHE = idx
    s = sugerir("Losartana Potássica")
    assert s is not None and s.posologia.startswith("Tomar")
    ps._CACHE = None


def test_sem_posologia_retorna_none(tmp_path):
    import app.domain.posologia_sugerida as ps
    ps._CACHE = carregar_posologias(_csv(tmp_path, ""))
    assert sugerir("amoxicilina") is None
    assert sugerir("") is None
    assert sugerir(None) is None
    ps._CACHE = None


def test_rascunho_de_producao_fica_dormente():
    """O CSV de produção (data/posologia_sugerida.csv) entra como RASCUNHO →
    o motor não serve nada até Fabiano validar (status_curadoria=validado)."""
    from app.domain.posologia_sugerida import _resolver_csv
    idx = carregar_posologias(_resolver_csv())
    assert idx == {}   # tudo rascunho → dormente


# --- Endpoint ---

from fastapi.testclient import TestClient
from app.main import app
from app.auth.dependencies import get_current_user


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: {"sub": "123456789012345", "role": "prescritor"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint_flag_off(client, monkeypatch):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", False)
    r = client.post("/ia/posologia/sugerir", json={"principio_ativo": "losartana"})
    assert r.status_code == 200 and r.json() == {"disponivel": False}


def test_endpoint_flag_on_serve_validado(client, monkeypatch, tmp_path):
    import app.routers.ia as ia
    import app.domain.posologia_sugerida as ps
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    caminho = _csv(tmp_path, "losartana,Tomar 1 cp 50 mg 1x/dia,HAS,I10,RENAME,validado,Dr X,v1,obs\n")
    monkeypatch.setattr(ps, "_CACHE", carregar_posologias(caminho))
    r = client.post("/ia/posologia/sugerir", json={"principio_ativo": "Losartana Potássica"})
    d = r.json()
    assert d["disponivel"] is True
    assert d["posologia"].startswith("Tomar")
    assert d["validado_por"] == "Dr X"
    assert "responsável" in d["aviso"].lower()


def test_endpoint_flag_on_sem_match(client, monkeypatch, tmp_path):
    import app.routers.ia as ia
    import app.domain.posologia_sugerida as ps
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    monkeypatch.setattr(ps, "_CACHE", carregar_posologias(_csv(tmp_path, "")))
    r = client.post("/ia/posologia/sugerir", json={"principio_ativo": "amoxicilina"})
    assert r.json() == {"disponivel": False}
