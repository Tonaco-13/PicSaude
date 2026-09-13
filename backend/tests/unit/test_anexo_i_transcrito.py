"""
tests/unit/test_anexo_i_transcrito.py — G1, o DADO real do carimbo (13/09).

O QUE ESTE ARQUIVO PROVA
------------------------
A mecânica do carimbo já tinha guarda desde o #218
(`test_catalogo_regulatorio.py` 22–26, com snapshot sintético). O que nunca
existiu foi guarda sobre **o dado**: o Anexo I da Portaria 344/98 transcrito
do PDF consolidado do Anvisa Legis.

Isto importa mais que o normal porque o carimbo **inverte o princípio da
cautela**: a partir dele, ausência deixa de ser silêncio e passa a AFIRMAR
"não-controlado sob a versão V". Uma transcrição torta não devolve um
alerta errado — devolve uma afirmação negativa errada, que é pior.

1. O snapshot commitado é o que o despacho mandou carimbar: fonte, versão e
   data exatas.
2. Toda entrada tem `dcb` e uma `classe_controle` do vocabulário
   prescritível. Nada de D1/D2/E/F (precursor e proscrito não são
   "controlado com receita").
3. As contagens por lista estão CONGELADAS. Transcrição é dado regulatório:
   se o número muda sem que ninguém mexa na fonte, é regressão do extrator.
   (Se a fonte mudar de verdade — nova Atualização —, este teste é o lugar
   certo para o número novo entrar junto com o novo sha256 no MANIFEST.)
4. Nenhuma ligadura tipográfica vazou (ﬁ/ﬂ do PDF) — `Buprenorﬁna` entraria
   como substância diferente de `Buprenorfina`.
5. Nenhuma cláusula de ADENDO vazou para dentro do catálogo. As listas do
   consolidado terminam em texto normativo ("excetuam-se dos controles…"),
   e capturá-lo criaria "substâncias" que são parágrafos de lei.
6. **AC5** — as 20 curadas reconciliam contra a oficial, e as divergências
   conhecidas são exatamente as três relatadas em
   `docs/tickets/RECONCILIACAO-ANEXO-I-2026-09-13.md`. Divergência nova
   aparecendo aqui é achado regulatório, não ruído de teste.
7. Toda divergência MIGRA no upsert (a chave `normalizar_dcb` da curada
   existe no snapshot). Uma que não migrasse deixaria row curada antiga
   convivendo com a oficial — classe contraditória dentro de um catálogo
   carimbado, exatamente o que o carimbo promete não ter.
8. As outras seeds (antimicrobianos, GLP-1) NÃO são tocadas: não são da
   Portaria 344 e têm que sobreviver ao snapshot.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pytest

from app.domain.catalogo_regulatorio import normalizar_dcb
from app.domain.catalogo_seed import (
    SEED_ANTIMICROBIANOS,
    SEED_GLP1,
    SEED_PORTARIA_344,
    caminho_snapshot_anexo_i,
)

_FONTE = (
    "Anexo I Portaria 344/98 consolidada, Atualização nº 101 — "
    "RDC 1.036/2026, Anvisa Legis 13/09/2026"
)
_VERSAO = "RDC 1.036/2026 (Atualização nº 101)"
_DATA = "2026-09-13"

_CLASSES_PRESCRITIVEIS = {"A1", "A2", "A3", "B1", "B2", "C1", "C2", "C3", "C5"}

# Congelado na transcrição de 13/09 (PDF sha256 58e88fd0…, MANIFEST).
_CONTAGEM_POR_LISTA = {
    "A1": 94, "A2": 13, "A3": 14, "B1": 95, "B2": 8,
    "C1": 213, "C2": 5, "C3": 3, "C5": 31,
}
_TOTAL_SUBSTANCIAS = 476
_TOTAL_ALTERNATIVAS = 21

# AC5 — as três divergências achadas na reconciliação de 13/09.
_DIVERGENCIAS_CONHECIDAS = {
    "Tramadol": ("B1", "A2"),
    "Isotretinoína": ("D1", "C2"),
    "Talidomida": ("D1", "C3"),
}

_LIGADURAS = "ﬁﬂﬀﬃﬄ"


@pytest.fixture(scope="module")
def snapshot() -> dict:
    caminho = Path(caminho_snapshot_anexo_i())
    if not caminho.exists():  # pragma: no cover — só num checkout quebrado
        pytest.fail(f"snapshot do Anexo I não commitado: {caminho}")
    return json.loads(caminho.read_text(encoding="utf-8"))


def _principais(snapshot: dict) -> list[dict]:
    """Entradas que são substância da lista (sem as designações alternativas)."""
    return [e for e in snapshot["entradas"] if not e.get("observacao")]


def test_o_carimbo_e_o_que_o_despacho_mandou(snapshot):
    assert snapshot["fonte"] == _FONTE
    assert snapshot["versao"] == _VERSAO
    assert snapshot["data_snapshot"] == _DATA


def test_toda_entrada_tem_dcb_e_classe_prescritivel(snapshot):
    for e in snapshot["entradas"]:
        assert e["dcb"] and e["dcb"].strip(), f"entrada sem dcb: {e}"
        assert e["classe_controle"] in _CLASSES_PRESCRITIVEIS, (
            f"{e['dcb']}: classe {e['classe_controle']!r} não é prescritível. "
            f"D1/D2 (precursores), E (plantas) e F (proscritas) não entram no "
            f"catálogo de prescrição."
        )


def test_contagem_por_lista_congelada(snapshot):
    contagem: dict[str, int] = {}
    for e in _principais(snapshot):
        contagem[e["classe_controle"]] = contagem.get(e["classe_controle"], 0) + 1

    assert contagem == _CONTAGEM_POR_LISTA, (
        "a contagem por lista mudou. Se a FONTE mudou (nova Atualização da "
        "Portaria), atualize junto: o PDF estagiado, o sha256 no MANIFEST, o "
        "carimbo e estes números. Se a fonte NÃO mudou, é regressão do "
        "extrator."
    )
    assert len(_principais(snapshot)) == _TOTAL_SUBSTANCIAS
    assert (
        len(snapshot["entradas"]) - len(_principais(snapshot)) == _TOTAL_ALTERNATIVAS
    )


def test_nenhuma_ligadura_tipografica_vazou(snapshot):
    for e in snapshot["entradas"]:
        achadas = [c for c in _LIGADURAS if c in e["dcb"]]
        assert not achadas, (
            f"{e['dcb']!r} carrega ligadura {achadas} do PDF — NFKC não foi "
            f"aplicado, e o nome não casaria no lookup"
        )
        assert e["dcb"] == unicodedata.normalize("NFKC", e["dcb"])


def test_nenhuma_clausula_de_adendo_virou_substancia(snapshot):
    marcas = re.compile(
        r"excetua|ficam sujeit|padrões analíticos|unidade posológica|"
        r"Resolução da Diretoria|VENDA SOB|estabelecimentos de saúde",
        re.I,
    )
    for e in _principais(snapshot):
        assert not marcas.search(e["dcb"]), (
            f"cláusula de ADENDO capturada como substância: {e['dcb']!r}"
        )


def test_ac5_reconciliacao_das_curadas(snapshot):
    """As 20 curadas resolvem na oficial; divergências são as 3 conhecidas."""
    por_chave = {normalizar_dcb(e["dcb"]): e for e in snapshot["entradas"]}

    ausentes, divergentes = [], {}
    for dcb, classe, _ret, _fonte, _obs in SEED_PORTARIA_344:
        achado = por_chave.get(normalizar_dcb(dcb))
        if achado is None:
            ausentes.append(dcb)
        elif achado["classe_controle"] != classe:
            divergentes[dcb] = (classe, achado["classe_controle"])

    assert not ausentes, (
        f"curada(s) que não resolvem na oficial: {ausentes}. Nome divergente ou "
        f"substância saiu da Portaria — decisão humana, não silêncio."
    )
    assert divergentes == _DIVERGENCIAS_CONHECIDAS, (
        f"o conjunto de divergências mudou.\nesperado: {_DIVERGENCIAS_CONHECIDAS}"
        f"\nachado  : {divergentes}\nDivergência nova é achado regulatório: "
        f"relate em docs/tickets/RECONCILIACAO-ANEXO-I-2026-09-13.md."
    )


def test_toda_divergencia_migra_no_upsert(snapshot):
    """Chave exata presente = o snapshot sobrescreve a curada.

    Sem isto, `Talidomida` (curada D1) sobreviveria ao lado de
    `Ftalimidoglutarimida (talidomida)` (oficial C3): duas classes para a
    mesma substância dentro de um catálogo carimbado.
    """
    chaves = {normalizar_dcb(e["dcb"]) for e in snapshot["entradas"]}
    for dcb in _DIVERGENCIAS_CONHECIDAS:
        assert normalizar_dcb(dcb) in chaves, (
            f"{dcb}: o upsert NÃO migraria — a chave curada não existe no "
            f"snapshot, então a row antiga sobreviveria com a classe errada."
        )


def test_outras_seeds_sobrevivem_ao_snapshot(snapshot):
    """Antimicrobianos e GLP-1 não são da Portaria 344 e não podem ser tocados."""
    chaves = {normalizar_dcb(e["dcb"]) for e in snapshot["entradas"]}
    tocadas = [
        e[0]
        for e in list(SEED_ANTIMICROBIANOS) + list(SEED_GLP1)
        if normalizar_dcb(e[0]) in chaves
    ]
    assert not tocadas, (
        f"o snapshot sobrescreveria seeds de outro regime: {tocadas}. "
        f"Antimicrobianos (IN 83/2021) e GLP-1 (IN 360/2025) não são Portaria 344."
    )


def test_designacoes_alternativas_sao_marcadas_e_coerentes(snapshot):
    """Alternativa carrega a MESMA classe da principal e se declara como tal."""
    principais = {normalizar_dcb(e["dcb"]): e for e in _principais(snapshot)}
    for e in snapshot["entradas"]:
        if not e.get("observacao"):
            continue
        assert "Designação alternativa" in e["observacao"]
        # Colchete, não aspas: `Intermediário "a" da petidina` tem aspas no
        # próprio nome, e um parser de aspas casaria o `a`.
        citado = re.search(r"\[([^\]]+)\]", e["observacao"])
        assert citado, f"observação sem a designação canônica: {e}"
        principal = principais.get(normalizar_dcb(citado.group(1)))
        assert principal is not None, f"alternativa órfã: {e['dcb']}"
        assert principal["classe_controle"] == e["classe_controle"], (
            f"{e['dcb']} ({e['classe_controle']}) diverge da principal "
            f"{principal['dcb']} ({principal['classe_controle']})"
        )
