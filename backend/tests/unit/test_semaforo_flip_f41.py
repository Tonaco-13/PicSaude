"""
tests/unit/test_semaforo_flip_f41.py — caneta do F41 (transtornos ansiosos).

Caneta do Fabiano, 13/09/2026, verbatim:

    "Concordo com o elenco: clonazepam e clomipramina 🟢. Fluoxetina e
     diazepam saem como 🟡 com causa (TOC fora de escopo; sem citação
     nominal). Vira flip — semaforo_f41_exaustiva_v1_2026-09."

Levantura dual em `docs/tickets/RASCUNHO-F41-DUPLO-PCDT-2026.md` (v2, #264):
RENAME 2024 × AMB/CFM 2008 × ABP/TAG 2024, sha256 das três conferido contra
os MANIFESTs antes da leitura.

O QUE ESTE ARQUIVO PROVA
------------------------
1. F41 está EXAUSTIVO e o elenco assinado acende verde.
2. **O elenco tem DOIS, e isso é o achado, não um defeito.** Das 9
   substâncias que as diretrizes recomendam para pânico (F41.0) e TAG
   (F41.1), **sete não constam da RENAME 2024** — inclusive TODAS as de
   primeira linha. Sobra no SUS um benzodiazepínico de 3ª linha e um
   tricíclico de 2ª. O 🟡 nas de 1ª linha é o serviço que o semáforo presta:
   o prescritor de APS vê que o livro e a prateleira não coincidem.
3. As quatro que saíram acendem 🟡 **com causa** — e a causa é de máquina:
   com `exaustivo=true`, quem não está na lista recebe
   `CAUSA_AMARELO = "ausente_lista_exaustiva"` do próprio motor. "Sair como
   🟡" é literalmente sair do CSV, mesmo mecanismo do I10 v2.
4. **Escopo F41 PURO**: fluoxetina sai porque o algoritmo da AMB (p. 9) só a
   sustenta sob TOC (F42), fora do escopo — e ela CONSTA da RENAME, então
   não é caso de indisponibilidade, é de indicação. Diazepam sai por falta de
   citação nominal (a linha de TAG diz só "BZD: prazos curtos").
5. **A não-contaminação com F32**: fluoxetina é 🟢 na depressão e continua
   sendo. Sair do elenco de ansiedade não a tira de onde ela é indicada.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.domain.semaforo_decisao import (
    CAUSA_AMARELO,
    SINAL_AMARELO,
    SINAL_VERDE,
    avaliar_semaforo,
    carregar_regras,
)

_CSV = Path(__file__).resolve().parents[3] / "data" / "decisao_semaforo.csv"

_ASSINATURA = "Fabiano Tonaco Borges"
_V = "semaforo_f41_exaustiva_v1_2026-09"

_ELENCO = ["clonazepam", "clomipramina"]

# As quatro que a caneta mandou sair, com o motivo declarado por ela.
_SAIRAM = {
    "fluoxetina": "TOC fora de escopo (AMB p. 9 só a sustenta em F42)",
    "diazepam": "sem citação nominal (a TAG diz só 'BZD: prazos curtos')",
    "sertralina": "não consta da RENAME 2024 (excomunhão dobrada, precedente F32)",
    "escitalopram": "não consta da RENAME 2024 (excomunhão dobrada, precedente F32)",
}

# Recomendadas pelas diretrizes para F41 e AUSENTES da RENAME 2024 — o achado
# que explica o elenco de dois.
_PRIMEIRA_LINHA_FORA_DO_SUS = [
    "sertralina", "paroxetina", "escitalopram", "venlafaxina",
]


def _carregar():
    return carregar_regras(str(_CSV))


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = _carregar()
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


def _rows():
    with _CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ---------------------------------------------------------------------------
# 1 — o flip
# ---------------------------------------------------------------------------

def test_f41_esta_exaustivo():
    _aprovados, exaustivos, _prov = _carregar()
    assert "F41" in exaustivos


def test_elenco_assinado_acende_verde():
    for ativo in _ELENCO:
        assert _av("F41", ativo).sinal == SINAL_VERDE, ativo


def test_o_elenco_tem_exatamente_dois():
    """Se alguém acrescentar sem caneta, o gate acusa."""
    f41 = [r for r in _rows() if r["codigo_cid"] == "F41"]
    assert sorted(r["principio_ativo"] for r in f41) == sorted(_ELENCO)


# ---------------------------------------------------------------------------
# 2 — o silêncio mudou de lado, e a causa é de máquina
# ---------------------------------------------------------------------------

def test_as_quatro_que_sairam_acendem_amarelo_com_causa():
    for ativo, motivo in _SAIRAM.items():
        a = _av("F41", ativo)
        assert a.sinal == SINAL_AMARELO, f"{ativo} — {motivo}"
        assert a.causa == CAUSA_AMARELO, f"{ativo} — {motivo}"


def test_primeira_linha_das_diretrizes_fica_amarela_por_ausencia_no_sus():
    """O achado da levantura, executável.

    Sertralina, paroxetina, escitalopram e venlafaxina são 1ª linha para
    pânico/TAG nas diretrizes e NÃO constam da RENAME 2024. O amarelo aqui
    não é defeito de curadoria — é a informação correta para quem prescreve
    no SUS.
    """
    for ativo in _PRIMEIRA_LINHA_FORA_DO_SUS:
        assert _av("F41", ativo).sinal == SINAL_AMARELO, ativo


# ---------------------------------------------------------------------------
# 3 — escopo puro e não-contaminação
# ---------------------------------------------------------------------------

def test_fluoxetina_sai_da_ansiedade_e_continua_verde_na_depressao():
    """Escopo é escopo: sair de F41 não tira fluoxetina de onde é indicada."""
    assert _av("F41", "fluoxetina").sinal == SINAL_AMARELO
    assert _av("F32", "fluoxetina").sinal == SINAL_VERDE


def test_clomipramina_verde_em_f41_sem_puxar_o_toc_para_dentro():
    """Clomipramina entra pelo PÂNICO (F41.0), não pelo TOC.

    Foi o ponto de decisão que contrariou a premissa do despacho: a AMB a
    recomenda em seção própria de pânico, com dose distinta da do TOC
    (100-150 contra 300 mg/dia). F42 não é exaustivo e segue neutro — o
    elenco de ansiedade não o arrasta junto.
    """
    assert _av("F41", "clomipramina").sinal == SINAL_VERDE
    _aprovados, exaustivos, _prov = _carregar()
    assert "F42" not in exaustivos


def test_f41_nao_vazou_elenco_para_f32():
    """Clonazepam e clomipramina são de ansiedade; a depressão tem elenco próprio."""
    assert _av("F32", "clonazepam").sinal == SINAL_AMARELO


# ---------------------------------------------------------------------------
# 4 — proveniência
# ---------------------------------------------------------------------------

def test_proveniencia_assinada_com_as_duas_fontes_e_pagina():
    f41 = [r for r in _rows() if r["codigo_cid"] == "F41"]
    assert len(f41) == 2

    for r in f41:
        assert r["status_curadoria"] == "validado", r
        assert r["validado_por"] == _ASSINATURA, r
        assert r["versao"] == _V, r
        assert r["exaustivo"] == "true", r
        # A levantura é DUAL: diretriz + RENAME, ambas com página.
        assert "AMB/CFM" in r["fonte"], r
        assert "RENAME 2024" in r["fonte"], r
        assert r["fonte"].count("p. ") >= 2, f"fonte sem as duas páginas: {r}"
        # E o escopo aparece na própria citação.
        assert "pânico" in r["fonte"], f"fonte sem o transtorno de F41: {r}"


def test_a_citacao_falsa_de_junho_sumiu_do_f41():
    """As seeds diziam `RENAME/PCDT (APS)` — citação em bloco, falsa para duas
    delas. Nenhuma row de F41 pode voltar a citar assim."""
    for r in _rows():
        if r["codigo_cid"] == "F41":
            assert r["fonte"] != "RENAME/PCDT (APS)", r
