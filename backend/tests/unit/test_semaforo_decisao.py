"""
Semáforo de apoio à decisão (validador) — motor determinístico.

Cobre app/domain/semaforo_decisao.py: canonicalização (sal/acento), hierarquia
do CID, a LEI DA EXAUSTIVIDADE (só julga condição com lista completa; senão se
cala — neutro) e a cadeia 🟢/🟡 (o 🔴 é Fase 2).
"""
from __future__ import annotations

from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_NEUTRO,
    SINAL_VERDE,
    avaliar_semaforo,
    cadeia_cid,
    canon_ativo,
    canon_cid,
)

# Regras-amostra (NÃO é conteúdo clínico de produção — só exercita o motor).
# I10 e E11 marcadas como EXAUSTIVAS (lista completa) → o motor pode julgar.
_APROVADOS = {
    ("I10", "losartana"): "PCDT Hipertensão",
    ("E11", "metformina"): "PCDT Diabetes tipo 2",
}
_CIDS_EXAUSTIVOS = {"I10", "E11"}


def _av(cid, ativo):
    return avaliar_semaforo(cid, ativo, _APROVADOS, _CIDS_EXAUSTIVOS)


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


# --- avaliação (condição EXAUSTIVA) ---

def test_verde_quando_aprovado():
    a = _av("I10", "losartana")
    assert a.sinal == SINAL_VERDE
    assert a.fonte == "PCDT Hipertensão"


def test_verde_via_hierarquia_do_cid():
    assert _av("I10.0", "losartana").sinal == SINAL_VERDE


def test_verde_apesar_do_sal_no_nome():
    assert _av("I10", "Losartana Potássica").sinal == SINAL_VERDE


def test_amarelo_fora_do_protocolo_em_condicao_exaustiva():
    a = _av("I10", "amoxicilina")
    assert a.sinal == SINAL_AMARELO
    assert "fora do protocolo" in a.motivo


# --- LEI DA EXAUSTIVIDADE: condição não-exaustiva → neutro (sem 🟢 nem 🟡) ---

def test_neutro_quando_condicao_nao_exaustiva():
    """J45 não está em _CIDS_EXAUSTIVOS → o semáforo não julga (neutro)."""
    assert _av("J45", "salbutamol").sinal == SINAL_NEUTRO


def test_neutro_para_aprovado_se_condicao_nao_exaustiva():
    """Crucial: mesmo um fármaco que seria 🟢 fica NEUTRO se a condição não é
    exaustiva — senão privilegiaríamos os curados sobre os válidos que faltam."""
    aprovados = {("Z00", "remedio_x"): "fonte"}     # Z00 NÃO está em exaustivos
    a = avaliar_semaforo("Z00", "remedio_x", aprovados, set())
    assert a.sinal == SINAL_NEUTRO


def test_neutro_quando_falta_cid_ou_farmaco():
    assert _av(None, "losartana").sinal == SINAL_NEUTRO
    assert _av("I10", None).sinal == SINAL_NEUTRO


def test_nunca_vermelho_na_v1():
    for cid, ativo in [("I10", "losartana"), ("I10", "amoxicilina"), ("J45", "x")]:
        assert _av(cid, ativo).sinal in (SINAL_VERDE, SINAL_AMARELO, SINAL_NEUTRO)


# ===========================================================================
# Loader — semente validada (data/decisao_semaforo.csv)
# ===========================================================================

def test_condicao_semente_silenciosa_e_exaustiva_acende():
    """Lei da exaustividade ao vivo: condições ainda em semente (exaustivo=false)
    → NEUTRO (sem viés); a condição EXAUSTIVA (I10/hipertensão) acende 🟢."""
    from app.domain.semaforo_decisao import avaliar, total_regras
    assert total_regras() >= 60                                  # I10 exaustiva + semente
    assert avaliar("E11", "metformina").sinal == SINAL_NEUTRO    # semente → silêncio
    assert avaliar("F32", "escitalopram").sinal == SINAL_NEUTRO
    assert avaliar("I10", "losartana").sinal == SINAL_VERDE      # exaustiva → acende
    assert avaliar("I10", "captopril").sinal == SINAL_VERDE      # antes ausente, agora 🟢
    assert avaliar("I10", "amoxicilina").sinal == SINAL_AMARELO  # fora do protocolo


def test_condicao_marcada_exaustiva_acende(tmp_path):
    from app.domain import semaforo_decisao as sd
    csv_path = tmp_path / "regras.csv"
    csv_path.write_text(
        "codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo\n"
        "I10,Hipertensão,losartana,PCDT HAS,validado,X,v1,true\n"
        "I10,Hipertensão,captopril,PCDT HAS,validado,X,v1,true\n",
        encoding="utf-8",
    )
    aprovados, exaustivos = sd.carregar_regras(str(csv_path))
    assert ("I10", "losartana") in aprovados and "I10" in exaustivos
    assert sd.avaliar_semaforo("I10", "losartana", aprovados, exaustivos).sinal == SINAL_VERDE
    assert sd.avaliar_semaforo("I10", "captopril", aprovados, exaustivos).sinal == SINAL_VERDE
    assert sd.avaliar_semaforo("I10", "amoxicilina", aprovados, exaustivos).sinal == SINAL_AMARELO


def test_loader_ignora_status_nao_validado(tmp_path):
    from app.domain import semaforo_decisao as sd
    csv_path = tmp_path / "regras.csv"
    csv_path.write_text(
        "codigo_cid,condicao_nome,principio_ativo,fonte,status_curadoria,validado_por,versao,exaustivo\n"
        "I10,Hipertensão,losartana,x,validado,X,v1,true\n"
        "I10,Hipertensão,farmaco_rascunho,x,rascunho,X,v1,true\n",
        encoding="utf-8",
    )
    aprovados, _ex = sd.carregar_regras(str(csv_path))
    assert ("I10", "losartana") in aprovados
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


def test_endpoint_flag_on_condicao_semente_neutra(client, monkeypatch):
    """Condição ainda em semente (E11, não-exaustiva) → neutro (sem ponto na UI)."""
    import app.routers.ia as ia
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    r = client.post("/ia/decisao/validar",
                    json={"codigo_cid": "E11", "principio_ativo": "metformina"})
    assert r.status_code == 200
    d = r.json()
    assert d["ativo"] is True and d["sinal"] == SINAL_NEUTRO


def test_endpoint_flag_on_condicao_exaustiva_acende_verde(client, monkeypatch):
    import app.routers.ia as ia
    import app.domain.semaforo_decisao as sd
    monkeypatch.setattr(ia, "PICSAUDE_DECISAO_CLINICA", True)
    monkeypatch.setattr(sd, "_REGRAS_CACHE",
                        ({("I10", "losartana"): "PCDT HAS"}, {"I10"}))
    r = client.post("/ia/decisao/validar",
                    json={"codigo_cid": "I10", "principio_ativo": "losartana"})
    d = r.json()
    assert d["ativo"] is True and d["sinal"] == SINAL_VERDE and d["fonte"]
