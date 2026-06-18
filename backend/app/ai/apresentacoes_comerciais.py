"""Apresentações comerciais (embalagens reais) por medicamento — base CMED (Modelo A).

Para o medicamento escolhido no autocomplete (princípio ativo · concentração · forma),
oferece as EMBALAGENS reais da CMED — "caixa com 30 comprimidos", "frasco com 150 mL".
Campo OPCIONAL: a prescrição padrão é por quantidade total (genérico/SUS).

Índice construído de data/cmed_apresentacoes.csv (override PICSAUDE_CMED_APRES_CSV).
A chave (princípio ativo, concentração, forma) casa 1:1 com o autocomplete (mesma fonte).
"""
from __future__ import annotations

import csv
import os
import re
from collections import defaultdict

from app.ai.lookup_def import _unidade_de_forma

_RE_PACK = re.compile(r"X\s*([\d.,]+)\s*(ML|L|G|KG)?", re.IGNORECASE)


def _resolver_csv() -> str:
    override = os.getenv("PICSAUDE_CMED_APRES_CSV")
    if override:
        return override
    return os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "cmed_apresentacoes.csv")
    )


def _plural(unidade: str, n: str) -> str:
    return unidade if n == "1" else unidade + "s"


def _rotulo(apresentacao: str, forma: str) -> str | None:
    """Transforma a embalagem CMED em rótulo legível, ou None se não houver 'X N'."""
    matches = list(_RE_PACK.finditer(apresentacao or ""))
    if not matches:
        return None
    n = matches[-1].group(1).strip()
    unit = (matches[-1].group(2) or "").upper()
    if unit in ("ML", "L"):
        return f"frasco com {n} {unit.lower()}"
    if unit in ("G", "KG"):
        cont = "bisnaga" if _unidade_de_forma(forma) == "bisnaga" else "frasco"
        return f"{cont} com {n} {unit.lower()}"
    return f"caixa com {n} {_plural(_unidade_de_forma(forma), n)}"


def _construir_indice() -> dict:
    indice: dict[tuple, set] = defaultdict(set)
    try:
        with open(_resolver_csv(), encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                pa = (row.get("principio_ativo") or "").strip()
                conc = (row.get("concentracao_texto") or "").strip()
                forma = (row.get("forma_farmaceutica") or "").strip()
                if not pa or not forma:
                    continue
                rotulo = _rotulo(row.get("apresentacao") or "", forma)
                if rotulo:
                    indice[(pa, conc, forma)].add(rotulo)
    except FileNotFoundError:
        pass
    return indice


_INDICE = _construir_indice()


def _ordenar(rotulos: set) -> list[str]:
    def chave(r: str) -> float:
        m = re.search(r"com\s+([\d.,]+)", r)
        if not m:
            return 1e12
        return float(m.group(1).replace(".", "").replace(",", "."))
    return sorted(rotulos, key=chave)


def apresentacoes_comerciais(
    principio_ativo: str, concentracao: str, forma: str, max_resultados: int = 12
) -> list[str]:
    """Embalagens reais (ordenadas, menores primeiro) para o medicamento dado."""
    rots = _INDICE.get((
        (principio_ativo or "").strip(),
        (concentracao or "").strip(),
        (forma or "").strip(),
    ), set())
    return _ordenar(rots)[:max_resultados]


def total_indexado() -> int:
    return sum(len(v) for v in _INDICE.values())
