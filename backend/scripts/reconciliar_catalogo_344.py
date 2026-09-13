"""
reconciliar_catalogo_344.py
============================
DESENHO-TALAO-DIGITAL-SNCR.md §1.1 — **AC5**, a reconciliação que estava
pendente ("as 56 curadas atuais migram/reconciliam contra a lista oficial,
divergências relatadas, NÃO silenciosas").

Compara o seed curado à mão (`catalogo_seed.SEED_*`) com o Anexo I oficial
transcrito (`transcrever_portaria_344.py`). Não escreve nada: é relatório.

POR QUE ISTO É UM SCRIPT E NÃO UM COMENTÁRIO NUMA PR
-----------------------------------------------------
Divergência entre dado curado e fonte oficial é achado REGULATÓRIO, e
achado regulatório se reproduz. Rodar de novo depois da próxima
Atualização da Portaria devolve o novo conjunto de divergências sem que
ninguém precise lembrar de conferir à mão.

TRÊS VEREDITOS POR SUBSTÂNCIA CURADA
-------------------------------------
    CONFERE   presente na oficial, mesma classe
    DIVERGE   presente na oficial, CLASSE DIFERENTE  → a oficial vence
    AUSENTE   não encontrada na oficial              → decisão humana

`DIVERGE` não é erro do importador: o snapshot faz upsert por
`dcb_normalizada`, então a classe oficial SUBSTITUI a curada quando os
nomes batem. É a migração que o AC5 pede — e este relatório é o "não
silenciosa" dela.

SINÔNIMO ENTRE PARÊNTESES
--------------------------
O consolidado nomeia algumas substâncias pelo nome químico com o nome
comum entre parênteses — `Ftalimidoglutarimida (talidomida)`. Comparar só
pelo nome inteiro reportaria `AUSENTE` para uma substância que ESTÁ na
lista, o que seria um relatório falso. O índice inclui, além do nome
inteiro, o conteúdo dos parênteses e o nome sem eles.

Uso
---
    python3 backend/scripts/reconciliar_catalogo_344.py \\
        --oficial data/fontes-oficiais/anvisa-controlados-2026-08-28/anexo-i-consolidado.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.domain.catalogo_regulatorio import normalizar_dcb  # noqa: E402
from app.domain.catalogo_seed import (  # noqa: E402
    SEED_ANTIMICROBIANOS,
    SEED_GLP1,
    SEED_INATIVOS,
    SEED_PORTARIA_344,
)


def chave(nome: str) -> str:
    base = unicodedata.normalize("NFKD", nome.casefold())
    base = "".join(c for c in base if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", base).strip()


def apelidos(nome: str) -> set[str]:
    """Nome inteiro + conteúdo dos parênteses + nome sem os parênteses."""
    formas = {nome}
    for dentro in re.findall(r"\(([^)]+)\)", nome):
        formas.add(dentro)
    formas.add(re.sub(r"\([^)]*\)", "", nome))
    for sep in (" ou ", ";"):
        if sep in nome:
            formas.update(p for p in nome.split(sep))
    return {chave(f) for f in formas if len(chave(f)) >= 3}


def indexar(entradas) -> dict[str, tuple[str, str]]:
    indice: dict[str, tuple[str, str]] = {}
    for e in entradas:
        for k in apelidos(e["dcb"]):
            indice.setdefault(k, (e["dcb"], e["classe_controle"]))
    return indice


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--oficial", required=True, help="JSON do Anexo I transcrito")
    args = ap.parse_args()

    with open(args.oficial, encoding="utf-8") as fh:
        snapshot = json.load(fh)

    indice = indexar(snapshot["entradas"])
    # Chaves EXATAS do upsert (`normalizar_dcb` sobre o `dcb` de cada entrada).
    # É por elas — não pelos apelidos — que o snapshot sobrescreve uma row
    # curada. Separar as duas coisas impede o relatório de afirmar "a oficial
    # vence" quando o upsert, na verdade, criaria uma segunda row.
    chaves_upsert = {normalizar_dcb(e["dcb"]): e for e in snapshot["entradas"]}

    print("fonte  :", snapshot["fonte"])
    print("versão :", snapshot["versao"], "·", snapshot["data_snapshot"])
    print("oficial: %d substâncias prescritíveis" % len(snapshot["entradas"]))
    print("curadas: %d (Portaria 344)" % len(SEED_PORTARIA_344))
    print()

    confere, diverge, ausente = [], [], []
    for dcb, classe, _retencao, _fonte, _obs in SEED_PORTARIA_344:
        achado = indice.get(chave(dcb))
        if achado is None:
            ausente.append((dcb, classe))
        elif achado[1] != classe:
            diverge.append((dcb, classe, achado[1], achado[0]))
        else:
            confere.append((dcb, classe))

    print("=== CONFERE (%d) ===" % len(confere))
    for dcb, classe in confere:
        print("    %-24s %s" % (dcb, classe))

    print("\n=== DIVERGE — classe curada ≠ classe oficial (%d) ===" % len(diverge))
    nao_migram = []
    for dcb, nossa, dela, nome_oficial in diverge:
        alvo = chaves_upsert.get(normalizar_dcb(dcb))
        if alvo is None:
            migra = "NÃO MIGRA (upsert criaria 2ª row)"
            nao_migram.append((dcb, nossa, dela))
        else:
            migra = "migra (upsert sobrescreve para %s)" % alvo["classe_controle"]
        extra = (
            "" if nome_oficial.lower() == dcb.lower() else "  [oficial: %s]" % nome_oficial
        )
        print("    %-22s curada=%-3s → oficial=%-3s  %s%s" % (dcb, nossa, dela, migra, extra))

    if nao_migram:
        print(
            "\n    ⚠️  %d divergência(s) NÃO são corrigidas pelo import: a row "
            "curada sobrevive\n        com a classe antiga ao lado da oficial. "
            "Catálogo carimbado com classe\n        contraditória é exatamente o "
            "que o carimbo promete não ter — exige\n        decisão humana antes "
            "de carimbar." % len(nao_migram)
        )

    print("\n=== AUSENTE da oficial — decisão humana (%d) ===" % len(ausente))
    for dcb, classe in ausente:
        print("    %-24s curada=%s" % (dcb, classe))

    outras = list(SEED_ANTIMICROBIANOS) + list(SEED_GLP1) + list(SEED_INATIVOS)
    colisao = [e[0] for e in outras if chave(e[0]) in indice]
    print("\n=== outras seeds tocadas pelo snapshot (%d) ===" % len(colisao))
    print(
        "   ",
        colisao
        if colisao
        else "nenhuma — antimicrobianos/GLP-1 não são da Portaria 344 e sobrevivem",
    )

    print(
        "\nRESUMO: %d confere · %d diverge · %d ausente"
        % (len(confere), len(diverge), len(ausente))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
