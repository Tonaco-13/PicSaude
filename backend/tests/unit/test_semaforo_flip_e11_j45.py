"""tests/unit/test_semaforo_flip_e11_j45.py — o flip de 31/08 (assinatura Fabiano).

O QUE ESTE ARQUIVO GUARDA
-------------------------
Martelo do Fabiano em 31/08/2026: **"E11 e J45 assinados"** (sessão com o
arquiteto). Esta é a guarda do ato — lê o CSV REAL (nada de base mockada,
como faz `test_semaforo_decisao.py` para as leis do motor) e afirma o estado
pós-assinatura:

  · E11 (DM2) e J45 (Asma) estão EXAUSTIVOS — o semáforo julga;
  · o elenco assinado acende 🟢 (incluindo os aliases de insulina aterrados
    no próprio PDF 2026 — AIAR: asparte/lispro/glulisina; AIAP:
    glargina/degludeca);
  · a demonstração pedida pelo conselheiro em agosto ACENDEU:
    **E11 × dapagliflozina = 🟢** (antes: neutro, porque E11 não era exaustivo);
  · exclusões citadas ficam 🟡 honesto (não 🟢, nunca neutro): DPP-4 no E11
    (p. 22 do PCDT), teofilina/montelucaste no J45 (p. 36);
  · F32 e N39.0 seguem NÃO-exaustivos — a lei da exaustividade vale para
    quem ainda não assinou;
  · proveniência: `validado_por=Fabiano Tonaco Borges`, versões
    `semaforo_e11_exaustiva_v1_2026-08` / `semaforo_j45_exaustiva_v1_2026-08`.

Fontes estagiadas (sha256 no MANIFEST):
  · data/fontes-oficiais/pcdt/PCDT-diabete-melito-tipo-2-2026.pdf
  · data/fontes-oficiais/pcdt/corpus-conitec-2026-08-30/pcdt-da-asma.pdf
Rascunhos assinados: RASCUNHO-E11-DUPLO-PCDT-2026.md (§4.5 adjudicação de
aliases) e RASCUNHO-J45-DUPLO-PCDT-2026.md (§4 recomendações aplicadas).
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

_ASSINATURA = "Fabiano Tonaco Borges"
_V_E11 = "semaforo_e11_exaustiva_v1_2026-08"
_V_J45 = "semaforo_j45_exaustiva_v1_2026-08"

_E11_ELENCO = [
    "metformina", "glibenclamida", "gliclazida", "dapagliflozina",
    "insulina NPH", "insulina humana NPH", "insulina humana regular",
    "insulina regular", "insulina análoga de ação rápida", "insulina asparte",
    "insulina lispro", "insulina glulisina",
    "insulina análoga de ação prolongada", "insulina glargina",
    "insulina degludeca",
]
_J45_ELENCO = [
    "salbutamol", "beclometasona", "budesonida", "fenoterol", "prednisona",
    "prednisolona", "formoterol + budesonida", "mepolizumabe", "omalizumabe",
    "benralizumabe", "dupilumabe",
]


def _carregar():
    return carregar_regras(str(_CSV))


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = _carregar()
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


# ---------------------------------------------------------------------------
# 1 — o flip aconteceu, e só para quem assinou
# ---------------------------------------------------------------------------

def test_e11_e_j45_estao_exaustivos():
    _, cids, _ = _carregar()
    assert "E11" in cids and "J45" in cids


def test_f32_e_n39_assinaram_0209_e_o_silencio_mudou_de_lado():
    """Atualizada no flip de 02/09: F32 e N39.0 ASSINARAM (guarda própria em
    test_semaforo_flip_f32_n39.py). A lei da exaustividade segue valendo para
    quem nunca foi curado — o exemplo agora é M54.5."""
    _, cids, _ = _carregar()
    assert "F32" in cids and "N39.0" in cids
    assert _av("M54.5", "dipirona").sinal not in (SINAL_VERDE, SINAL_AMARELO)


# ---------------------------------------------------------------------------
# 2 — a demonstração do conselheiro acendeu
# ---------------------------------------------------------------------------

def test_demonstracao_e11_dapagliflozina_acende_verde():
    """O caso de demonstração (item C do martelo de 07/08): E11×dapagliflozina
    🟢 — antes do flip era NEUTRO (E11 não-exaustivo). O contraste didático
    com I10×dapagliflozina (🟡, não é fármaco de HAS) agora existe."""
    assert _av("E11", "dapagliflozina").sinal == SINAL_VERDE
    assert _av("I10", "dapagliflozina").sinal == SINAL_AMARELO


# ---------------------------------------------------------------------------
# 3 — o elenco assinado acende (incluindo aliases aterradas no PDF)
# ---------------------------------------------------------------------------

def test_elenco_e11_assinado_acende_verde():
    for ativo in _E11_ELENCO:
        assert _av("E11", ativo).sinal == SINAL_VERDE, ativo


def test_elenco_j45_assinado_acende_verde():
    for ativo in _J45_ELENCO:
        assert _av("J45", ativo).sinal == SINAL_VERDE, ativo


def test_alias_com_dose_digitada_casa():
    """O strip de dose (#220) foi pré-requisito do flip (vagão §3): a
    combinação dose+qualificador tem que casar igual."""
    assert _av("E11", "Insulina Humana Regular 100UI").sinal == SINAL_VERDE
    assert _av("E11", "Dapagliflozina 10mg").sinal == SINAL_VERDE


def test_alias_com_concentracao_em_barra_casa():
    """TICKET-CANON-CONCENTRACAO-SLASH, FECHADO: a notação de CONCENTRAÇÃO
    com barra ("100 UI/ml") — a forma como insulina normalmente aparece na
    prescrição real — deixava "/ml" órfão no canon e caía em amarelo falso.
    Gap achado por esta mesma guarda no dia do flip (31/08); unit tests
    dedicados de canon_ativo em test_semaforo_decisao.py."""
    assert _av("E11", "Insulina Humana Regular 100 UI/ml").sinal == SINAL_VERDE
    assert _av("E11", "Insulina Glargina 100 UI/3,15 ml").sinal == SINAL_VERDE


# ---------------------------------------------------------------------------
# 4 — exclusões citadas: 🟡 honesto, nunca neutro, nunca 🟢
# ---------------------------------------------------------------------------

def test_e11_dpp4_fora_do_protocolo_amarelo():
    """PCDT DM2 2026, p. 22: inibidores da DPP-4 'não estão incorporados ao
    SUS' — amarelo com causa, agora que E11 é exaustivo."""
    a = _av("E11", "sitagliptina")
    assert a.sinal == SINAL_AMARELO
    assert a.causa == "ausente_lista_exaustiva"
    assert "fora do protocolo" in a.motivo


def test_j45_teoﬁlina_e_montelucaste_amarelo():
    """PCDT Asma 2026, p. 36 (§7.3.2): teofilinas orais e antagonistas do
    receptor de leucotrieno 'não estão incorporados no SUS para asma'."""
    for ativo in ("teofilina", "montelucaste"):
        a = _av("J45", ativo)
        assert a.sinal == SINAL_AMARELO, ativo


# ---------------------------------------------------------------------------
# 5 — proveniência da assinatura
# ---------------------------------------------------------------------------

def test_proveniencia_assinada_por_fabiano():
    aprovados, _, _ = _carregar()
    for cid, ativo, versao in [
        ("E11", "metformina", _V_E11),
        ("E11", "insulina glargina", _V_E11),
        ("J45", "beclometasona", _V_J45),
        ("J45", "formoterol + budesonida", _V_J45),
    ]:
        prov = aprovados[(canon_cid(cid), canon_ativo(ativo))]
        assert prov.validado_por == _ASSINATURA, ativo
        assert prov.versao == versao, ativo
        assert "2026" in prov.fonte, ativo


def test_rascunhos_2022_foram_retirados_da_base():
    """Os 21 rascunhos da era PCDT-2022 (glimepirida, acarbose, DPP-4,
    GLP-1…) saíram: o elenco vigente assinado é o de 2026. Eles nunca foram
    servidos (status=rascunho), mas não convivem com a assinatura nova."""
    with _CSV.open(encoding="utf-8") as f:
        ativos = {r["principio_ativo"] for r in csv.DictReader(f)
                  if r["codigo_cid"] == "E11"}
    for fora in ("glimepirida", "acarbose", "sitagliptina", "liraglutida",
                 "insulina detemir", "empagliflozina"):
        assert fora not in ativos, fora
    # …e o que o PDF 2026 incorporou de verdade está:
    for dentro in ("metformina", "insulina degludeca", "insulina asparte"):
        assert dentro in ativos, dentro
