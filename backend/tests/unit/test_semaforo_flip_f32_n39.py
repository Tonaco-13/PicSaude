"""tests/unit/test_semaforo_flip_f32_n39.py — o flip de 02/09 (assinatura Fabiano).

Martelo: *"Estou de acordo … com suas recomendações"* (02/09) — F32 e N39.0
exaustivos no padrão I10 (diretrizes de especialidade + RENAME 2024), com as
decisões do rascunho aplicadas:

  · F32 — **elenco estrito RENAME 2024**: 5 fármacos 🟢; sertralina e
    escitalopram ficam 🟡 com causa (não constam da RENAME 2024 — as seeds
    citavam "RENAME" por costume, não por conferência);
  · N39.0 — elenco com **fonte por row**; fosfomicina 🟢 com a ausência na
    RENAME 2024 declarada NA PRÓPRIA ROW (decisão do Fabiano); fluoroquinolonas
    🟢 com reserva AWaRe Watch na fonte;
  · posologia N39.0 — só rows citáveis da RAMB 2003 (idade da fonte declarada);
    F32 sem posologia (pendência declarada — não se inventa dose).

Fontes estagiadas (sha256 nos MANIFESTs): fontes-oficiais/rename/ e
fontes-oficiais/diretrizes/. Rascunhos assinados:
RASCUNHO-F32-DEPRESSAO-2026.md e RASCUNHO-N39-ITU-2026.md.
"""
from __future__ import annotations

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
_V_F32 = "semaforo_f32_exaustiva_v1_2026-09"
_V_N39 = "semaforo_n39_exaustiva_v1_2026-09"


def _av(cid: str, ativo: str):
    aprovados, cids, cond_prov = carregar_regras(str(_CSV))
    return avaliar_semaforo(cid, ativo, aprovados, cids, cond_prov)


def test_f32_e_n39_estao_exaustivos():
    _, cids, _ = carregar_regras(str(_CSV))
    assert "F32" in cids and "N39.0" in cids


def test_f32_elenco_estrito_rename_acende():
    for ativo in ("fluoxetina", "clomipramina", "amitriptilina", "nortriptilina",
                  "bupropiona"):
        assert _av("F32", ativo).sinal == SINAL_VERDE, ativo


def test_f32_sertralina_e_escitalopram_amarelo_com_causa():
    """A decisão assinada: fora da RENAME 2024 → 🟡 honesto, nunca 🟢."""
    for ativo in ("sertralina", "escitalopram"):
        a = _av("F32", ativo)
        assert a.sinal == SINAL_AMARELO, ativo
        assert a.causa == "ausente_lista_exaustiva", ativo


def test_f32_dose_digitada_casa():
    assert _av("F32", "Fluoxetina 20mg").sinal == SINAL_VERDE


def test_n39_elenco_acende():
    for ativo in ("nitrofurantoína", "fosfomicina", "cefalexina", "amoxicilina",
                  "amoxicilina + clavulanato de potássio",
                  "sulfametoxazol + trimetoprima", "ciprofloxacino",
                  "levofloxacino"):
        assert _av("N39.0", ativo).sinal == SINAL_VERDE, ativo


def test_n39_fosfomicina_declara_a_ausencia_na_propria_row():
    """A row conta a verdade inteira: RAMB 2003 E a ausência na RENAME 2024."""
    aprovados, _, _ = carregar_regras(str(_CSV))
    prov = aprovados[(canon_cid("N39.0"), canon_ativo("fosfomicina"))]
    assert "NÃO consta da RENAME 2024" in prov.fonte


def test_i10_intacto():
    assert _av("I10", "losartana").sinal == SINAL_VERDE


def test_proveniencia_assinada():
    aprovados, _, _ = carregar_regras(str(_CSV))
    assert aprovados[(canon_cid("F32"), canon_ativo("bupropiona"))].versao == _V_F32
    assert aprovados[(canon_cid("N39.0"), canon_ativo("ciprofloxacino"))].versao == _V_N39
    assert "AWaRe Watch" in aprovados[(canon_cid("N39.0"), canon_ativo("ciprofloxacino"))].fonte
