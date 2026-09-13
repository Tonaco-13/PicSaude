"""tests/unit/test_semaforo_flip_i10_v2.py — o flip de 05/09 (sinal verde Fabiano).

O QUE ESTE ARQUIVO GUARDA
-------------------------
Sinal verde do Fabiano em 04/09/2026, verbatim: **"sinal verde I10 estrito"**.
O elenco fundador do semáforo (I10, 61 fármacos de maio) foi re-conferido
contra a RENAME 2024 estagiada (sha256 no MANIFEST): **44 não constavam**.
A decisão assinada alinha o I10 ao princípio já vigente em F32/N39.0:

  🟢 significa *reconhecido E disponível no SUS* — em TODAS as condições.

O que mudou (v2):
  · elenco: 61 → 17, cada row com página da RENAME 2024 na fonte
    (diretriz SBC 2020 permanece como fonte coadjuvante);
  · as 44 excomungadas viram 🟡 com causa ("não consta da RENAME 2024"),
    o que é orientação CORRETA para prescritor de APS no SUS (ex.: ramipril
    → 🟡 redireciona ao enalapril);
  · posologia: a row de clortalidona sai (ausente da RENAME);
  · casos de demo PRESERVADOS: I10×sinvastatina segue 🟡 (nunca foi do
    elenco); I10×dapagliflozina segue 🟡 (o contraste didático E11🟢 vive).

Varredura e listas completas: SESSAO-2026-09-05-06-AGENDA-WEEKEND.md
(sementes da R1) e o corpo da PR.
"""
from __future__ import annotations

import csv
from pathlib import Path

from app.domain.semaforo_decisao import (
    SINAL_AMARELO,
    SINAL_VERDE,
    avaliar_semaforo,
    carregar_regras,
    canon_ativo,
    canon_cid,
)

_CSV = Path(__file__).resolve().parents[3] / "data" / "decisao_semaforo.csv"
_POS = Path(__file__).resolve().parents[3] / "data" / "posologia_sugerida.csv"
_V = "semaforo_i10_exaustiva_v2_2026-09"

_ELENCO = [
    "hidroclorotiazida", "furosemida", "espironolactona", "captopril",
    "enalapril", "losartana", "valsartana", "anlodipino", "nifedipino",
    "verapamil", "atenolol", "propranolol", "metoprolol", "carvedilol",
    "metildopa", "hidralazina", "doxazosina",
]


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = carregar_regras(str(_CSV))
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


def test_elenco_estrito_acende_verde():
    for ativo in _ELENCO:
        assert _av("I10", ativo).sinal == SINAL_VERDE, ativo


def test_elenco_tem_pagina_da_rename_na_fonte():
    aprovados, _, _ = carregar_regras(str(_CSV))
    for ativo in _ELENCO:
        fonte = aprovados[(canon_cid("I10"), canon_ativo(ativo))].fonte
        assert "RENAME 2024 (p." in fonte, ativo
        assert "SBC" in fonte, ativo  # coadjuvante preservada


def test_excomungadas_amarelo_com_causa():
    """As 44 que citavam RENAME sem constar: agora 🟡 honesto."""
    for ativo in ("ramipril", "clortalidona", "telmisartana", "diltiazem",
                  "bisoprolol", "clonidina", "minoxidil"):
        a = _av("I10", ativo)
        assert a.sinal == SINAL_AMARELO, ativo
        assert a.causa == "ausente_lista_exaustiva", ativo


def test_casos_de_demo_preservados():
    """O contraste didático da vitrina não pode quebrar com a curadoria."""
    assert _av("I10", "sinvastatina").sinal == SINAL_AMARELO
    assert _av("I10", "dapagliflozina").sinal == SINAL_AMARELO
    assert _av("E11", "dapagliflozina").sinal == SINAL_VERDE


def test_proveniencia_v2_assinada():
    aprovados, _, _ = carregar_regras(str(_CSV))
    prov = aprovados[(canon_cid("I10"), canon_ativo("losartana"))]
    assert prov.versao == _V
    assert prov.validado_por == "Fabiano Tonaco Borges"


def test_posologia_perdeu_clortalidona_e_ganhou_v2():
    with _POS.open(encoding="utf-8") as f:
        i10 = [r for r in csv.DictReader(f) if r["codigo_cid"] == "I10"]
    ativos = {r["principio_ativo"] for r in i10}
    assert "clortalidona" not in ativos
    assert len(i10) == 5
    assert all(r["versao"] == "posologia_has_v2_2026-09" for r in i10)
    assert all("RENAME 2024 (p." in r["fonte"] for r in i10)


def test_nenhuma_outra_condicao_touch():
    """A cirurgia é só no I10: os outros quatro CIDs intocados."""
    _, cids, _ = carregar_regras(str(_CSV))
    assert cids == {"I10", "E11", "J45", "F32", "N39.0"}
    assert _av("E11", "metformina").sinal == SINAL_VERDE
    assert _av("J45", "beclometasona").sinal == SINAL_VERDE
    assert _av("F32", "fluoxetina").sinal == SINAL_VERDE
    assert _av("N39.0", "fosfomicina").sinal == SINAL_VERDE
