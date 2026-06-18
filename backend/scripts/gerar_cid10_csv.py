"""
Gera `data/cid10.csv` (base de busca CID-10) a partir dos CSVs oficiais do DATASUS.

Fonte: DATASUS — Tabelas da CID-10 V2008
  http://www2.datasus.gov.br/cid10/V2008/download.htm  (CID10CSV.zip)
  - CID-10-CATEGORIAS.CSV     (códigos de 3 caracteres, ex.: A09)
  - CID-10-SUBCATEGORIAS.CSV  (códigos de 4 caracteres, ex.: A150 → A15.0)

Saída (UTF-8, separador ','): colunas `codigo_cid,descricao,fonte`.
O `app/ai/base_cid.py` carrega este CSV (completude) e mescla a curadoria local de
aliases (qualidade de busca para termos clínicos comuns).

Uso:
    python backend/scripts/gerar_cid10_csv.py --src ~/picsaude_bases/cid10
    python backend/scripts/gerar_cid10_csv.py --src <dir> --out backend/../data/cid10.csv
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

_FONTE = "DATASUS/CID-10 V2008"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = PROJECT_ROOT / "data" / "cid10.csv"


def _formatar_subcat(subcat: str) -> str:
    """'A150' -> 'A15.0'. Mantém 3 chars como estão."""
    s = subcat.strip().upper()
    return f"{s[:3]}.{s[3]}" if len(s) == 4 else s


def _ler(caminho: Path, col_codigo: str, formatar) -> list[tuple[str, str]]:
    registros: list[tuple[str, str]] = []
    with open(caminho, encoding="latin1", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            codigo = (row.get(col_codigo) or "").strip()
            descricao = (row.get("DESCRICAO") or "").strip()
            if codigo and descricao:
                registros.append((formatar(codigo), descricao))
    return registros


def main() -> None:
    ap = argparse.ArgumentParser(description="Gera data/cid10.csv a partir do DATASUS")
    ap.add_argument("--src", required=True, help="Pasta com CID-10-CATEGORIAS.CSV e CID-10-SUBCATEGORIAS.CSV")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help=f"CSV de saída (padrão: {DEFAULT_OUT})")
    args = ap.parse_args()

    src = Path(os.path.expanduser(args.src))
    categorias = _ler(src / "CID-10-CATEGORIAS.CSV", "CAT", lambda c: c.strip().upper())
    subcategorias = _ler(src / "CID-10-SUBCATEGORIAS.CSV", "SUBCAT", _formatar_subcat)

    # dedup por código (categorias + subcategorias; sem colisão de formato, mas defensivo)
    vistos: dict[str, str] = {}
    for codigo, descricao in categorias + subcategorias:
        vistos.setdefault(codigo, descricao)

    out = Path(os.path.expanduser(args.out))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["codigo_cid", "descricao", "fonte"])
        for codigo in sorted(vistos):
            w.writerow([codigo, vistos[codigo], _FONTE])

    print(f"OK — {len(vistos):,} códigos escritos em {out}")
    print(f"  categorias: {len(categorias):,} | subcategorias: {len(subcategorias):,}")


if __name__ == "__main__":
    main()
