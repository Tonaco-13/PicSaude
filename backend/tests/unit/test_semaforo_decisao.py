"""
Semáforo de apoio à decisão (validador) — motor determinístico.

Cobre app/domain/semaforo_decisao.py: canonicalização (sal/acento), hierarquia
do CID, e a cadeia de regras 🟢/🟡 (o 🔴 é Fase 2).
"""
from __future__ import annotations

from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_VERDE,
    avaliar_semaforo,
    cadeia_cid,
    canon_ativo,
    canon_cid,
)

# Regras-amostra (NÃO é conteúdo clínico de produção — só exercita o motor).
_APROVADOS = {
    ("I10", "losartana"): "PCDT Hipertensão",
    ("E11", "metformina"): "PCDT Diabetes tipo 2",
}
_CIDS_COM_PCDT = {"I10", "E11"}


def _av(cid, ativo):
    return avaliar_semaforo(cid, ativo, _APROVADOS, _CIDS_COM_PCDT)


# --- canonicalização ---

def test_canon_ativo_remove_sal_prefixo():
    assert canon_ativo("Oxalato de Escitalopram") == "escitalopram"
    assert canon_ativo("Cloridrato de Metformina") == "metformina"


def test_canon_ativo_remove_sal_sufixo_e_acentos():
    assert canon_ativo("Losartana Potássica") == "losartana"


def test_canon_cid_normaliza():
    assert canon_cid(" i10.0 ") == "I10.0"


def test_cadeia_cid_sobe_para_categoria():
    assert cadeia_cid("I10.0") == ["I10.0", "I10"]
    assert cadeia_cid("E11") == ["E11"]


# --- avaliação (a decisão) ---

def test_verde_quando_aprovado():
    a = _av("I10", "losartana")
    assert a.sinal == SINAL_VERDE
    assert a.fonte == "PCDT Hipertensão"


def test_verde_via_hierarquia_do_cid():
    """CID específico (I10.0) casa regra indexada na categoria (I10)."""
    assert _av("I10.0", "losartana").sinal == SINAL_VERDE


def test_verde_apesar_do_sal_no_nome():
    """O fármaco vem com sal ('losartana potássica'); ainda casa."""
    assert _av("I10", "Losartana Potássica").sinal == SINAL_VERDE


def test_amarelo_farmaco_nao_consta_no_pcdt_da_condicao():
    a = _av("I10", "amoxicilina")
    assert a.sinal == SINAL_AMARELO
    assert "não consta" in a.motivo


def test_amarelo_sem_base_quando_cid_sem_pcdt():
    a = _av("J45", "salbutamol")
    assert a.sinal == SINAL_AMARELO
    assert "sem base" in a.motivo


def test_amarelo_quando_falta_cid_ou_farmaco():
    assert _av(None, "losartana").sinal == SINAL_AMARELO
    assert _av("I10", None).sinal == SINAL_AMARELO


def test_nunca_bloqueia_nem_vermelho_na_v1():
    """v1 só acende verde/amarelo — nunca vermelho (Fase 2)."""
    for cid, ativo in [("I10", "losartana"), ("I10", "amoxicilina"), ("Z99", "x")]:
        assert _av(cid, ativo).sinal in (SINAL_VERDE, SINAL_AMARELO)


# ===========================================================================
# Loader — carrega a semente validada (data/decisao_semaforo.csv)
# ===========================================================================

def test_loader_serve_semente_validada():
    from app.domain.semaforo_decisao import avaliar, total_regras
    assert total_regras() >= 30                                   # semente carregada
    assert avaliar("I10", "losartana").sinal == SINAL_VERDE
    assert avaliar("F32", "Oxalato de Escitalopram").sinal == SINAL_VERDE  # sal removido
    assert avaliar("E11", "dapagliflozina").sinal == SINAL_VERDE
    assert avaliar("I10", "amoxicilina").sinal == SINAL_AMARELO


def test_loader_ignora_status_nao_validado(tmp_path):
    from app.domain import semaforo_decisao as sd
    csv_path = tmp_path / "regras.csv"
    csv_path.write_text(
        "codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao\n"
        "I10,Hipertensão,losartana,x,validado,X,v1\n"
        "I10,Hipertensão,farmaco_rascunho,x,rascunho,X,v1\n",
        encoding="utf-8",
    )
    aprovados, _cids = sd.carregar_regras(str(csv_path))
    assert ("i10".upper(), "losartana") in aprovados
    assert ("I10", "farmaco_rascunho") not in aprovados   # não-validado fica fora


# ===========================================================================
# Endpoint — POST /ia/decisao/validar (atrás de feature flag)
# ===========================================================================

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.auth.dependencies import get_current_user, get_current_user_or_api_key

_PRESCRITOR = {"sub": "123456789012345", "role": "prescritor", "nome": "Dr"}


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = lambda: _PRESCRITOR
    app.dependency_overrides[get_current_user_or_api_key] = lambda: _PRESCRITOR
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_endpoint_flag_off_retorna_inativo(client, monkeypatch):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", False)
    r = client.post("/ia/decisao/validar",
                    json={"codigo_cid": "I10", "principio_ativo": "losartana"})
    assert r.status_code == 200
    assert r.json() == {"ativo": False}


def test_endpoint_flag_on_acende_verde(client, monkeypatch):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    r = client.post("/ia/decisao/validar",
                    json={"codigo_cid": "I10", "principio_ativo": "losartana"})
    assert r.status_code == 200
    d = r.json()
    assert d["ativo"] is True and d["sinal"] == "verde" and d["fonte"]


def test_endpoint_flag_on_amarelo_fora_da_base(client, monkeypatch):
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    r = client.post("/ia/decisao/validar",
                    json={"codigo_cid": "I10", "principio_ativo": "amoxicilina"})
    assert r.json()["sinal"] == "amarelo"
