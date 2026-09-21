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
    # ENG-019: a chave do índice é COMPOSTA — `(ativo, CID)`. A linha vermelha
    # (só `validado` entra) não mudou; mudou o endereço de cada dose.
    idx = carregar_posologias(caminho)
    assert ("losartana", "I10") in idx        # validado entra
    assert ("captopril", "I10") not in idx    # rascunho fica de fora (linha vermelha)
    assert idx[("losartana", "I10")].posologia.startswith("Tomar")
    assert idx[("losartana", "I10")].validado_por == "Dr"
    assert idx[("losartana", "I10")].codigo_cid == "I10"


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


def test_producao_so_serve_o_que_foi_validado():
    """O CSV de produção (data/posologia_sugerida.csv) só deve alimentar o
    motor com linhas `status_curadoria == 'validado'` — linha vermelha.

    Antes da Fase A (commit 23ca07d, 2026-06-25) o CSV inteiro era rascunho
    e o motor ficava dormente (idx == {}). A Fase A validou 11 posologias de
    HAS+DM2 — mudança intencional, não regressão. Este teste acompanha o
    CSV real (conta linhas validado por leitura direta) em vez de fixar o
    número 11, para não quebrar a cada nova validação de rotina; continua
    garantindo a linha vermelha: nenhum rascunho vaza para o índice e toda
    posologia servida tem responsável de validação registrado.
    """
    import csv as _csv
    from app.domain.posologia_sugerida import _resolver_csv

    caminho = _resolver_csv()
    with open(caminho, newline="", encoding="utf-8") as f:
        linhas_validadas = [
            row for row in _csv.DictReader(f)
            if (row.get("status_curadoria") or "").strip() == "validado"
        ]

    idx = carregar_posologias(caminho)

    # Com a chave composta (ENG-019) esta igualdade passou a provar UMA COISA A
    # MAIS: se duas linhas validadas dividissem o mesmo par (ativo, CID), uma
    # sobrescreveria a outra e o índice ficaria menor que o CSV. Ou seja, ela
    # agora também é a guarda contra dose duplicada para a mesma condição.
    assert len(idx) == len(linhas_validadas)   # nenhum rascunho vaza; nenhum validado some
    for posologia in idx.values():
        assert posologia.validado_por, (
            f"posologia '{posologia.principio_ativo}' está servida sem validado_por"
        )


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
