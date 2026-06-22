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
