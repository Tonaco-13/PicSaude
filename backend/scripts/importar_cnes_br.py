"""
Importa os arquivos CSV do CNES Brasil (maio/2026) para o banco SQLite.

Tabelas populadas (substituição completa das tabelas PE):
  - estabelecimentos_cnes    ← cnes_br_tmp/tbEstabelecimento202605.csv
  - profissionais_cnes       ← cnes_br_tmp/tbDadosProfissionalSus202605.csv
  - relacao_prof_estab       ← cnes_br_tmp/tbCargaHorariaSus202605.csv

Uso:
    python backend/scripts/importar_cnes_br.py
    python backend/scripts/importar_cnes_br.py --db caminho/para/banco.db
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos padrão
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR     = PROJECT_ROOT / "data"
TMP_DIR      = DATA_DIR / "cnes_br_tmp"
DEFAULT_DB   = os.environ.get("PIX_SAUDE_DB") or str(DATA_DIR / "pix_saude_pe.db")

ARQUIVOS = {
    "estabelecimentos_cnes": TMP_DIR / "tbEstabelecimento202605.csv",
    "profissionais_cnes":    TMP_DIR / "tbDadosProfissionalSus202605.csv",
    "relacao_prof_estab":    TMP_DIR / "tbCargaHorariaSus202605.csv",
}

CHUNK_SIZE = 2000


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def sanitize_col(name: str) -> str:
    s = name.strip().strip('"').replace("'", "")
    s = re.sub(r"TO_CHAR\(([^,]+),[^)]+\)", r"\1", s)
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()


def detectar_delimitador(caminho: Path, encoding: str = "utf-8") -> str:
    with open(caminho, encoding=encoding, errors="replace") as fh:
        linha = fh.readline()
    return ";" if linha.count(";") > linha.count(",") else ","


def ler_csv_stream(caminho: Path, encoding: str = "utf-8"):
    """Lê CSV linha a linha (gerador) para economizar memória nos arquivos grandes."""
    delim = detectar_delimitador(caminho, encoding)
    with open(caminho, encoding=encoding, errors="replace", newline="") as fh:
        reader = csv.reader(fh, delimiter=delim)
        header_raw = next(reader)
        colunas = [sanitize_col(c) for c in header_raw]
        yield colunas
        for row in reader:
            yield row


def recriar_tabela(conn: sqlite3.Connection, tabela: str, colunas: list[str]) -> None:
    cols_sql = ",\n  ".join(f'"{c}" TEXT' for c in colunas)
    conn.execute(f'DROP TABLE IF EXISTS "{tabela}"')
    conn.execute(f'CREATE TABLE "{tabela}" ({cols_sql})')
    conn.commit()


def importar_arquivo(conn: sqlite3.Connection, tabela: str, caminho: Path) -> int:
    if not caminho.exists():
        print(f"  [AVISO] Arquivo não encontrado: {caminho}")
        return 0

    print(f"  Lendo {caminho.name} ...", flush=True)
    gen = ler_csv_stream(caminho)
    colunas = next(gen)  # type: ignore[arg-type]
    print(f"  {len(colunas)} colunas detectadas. Recriando tabela '{tabela}' ...", flush=True)
    recriar_tabela(conn, tabela, colunas)

    placeholders = ", ".join("?" * len(colunas))
    cols_quoted  = ", ".join(f'"{c}"' for c in colunas)
    sql = f'INSERT INTO "{tabela}" ({cols_quoted}) VALUES ({placeholders})'
    n_colunas = len(colunas)

    total = 0
    batch: list[list[str]] = []
    t0 = time.perf_counter()

    for row in gen:
        normalizado = (row + [""] * n_colunas)[:n_colunas]
        batch.append(normalizado)
        if len(batch) >= CHUNK_SIZE:
            conn.executemany(sql, batch)
            conn.commit()
            total += len(batch)
            batch = []
            if total % 100_000 == 0:
                elapsed = time.perf_counter() - t0
                print(f"    {total:,} linhas inseridas ({elapsed:.0f}s) ...", flush=True)

    if batch:
        conn.executemany(sql, batch)
        conn.commit()
        total += len(batch)

    elapsed = time.perf_counter() - t0
    print(f"  OK — {total:,} linhas em {elapsed:.1f}s")
    return total


# ---------------------------------------------------------------------------
# Índices para performance de busca
# ---------------------------------------------------------------------------

INDICES = [
    ("idx_estab_nome",   "estabelecimentos_cnes", "NO_RAZAO_SOCIAL"),
    ("idx_estab_fantasia","estabelecimentos_cnes", "NO_FANTASIA"),
    ("idx_estab_cnpj",   "estabelecimentos_cnes", "NU_CNPJ"),
    ("idx_estab_uf",     "estabelecimentos_cnes", "CO_ESTADO_GESTOR"),
    ("idx_prof_nome",    "profissionais_cnes",     "NO_PROFISSIONAL"),
    ("idx_prof_cns",     "profissionais_cnes",     "CO_CNS"),
    ("idx_rel_unidade",  "relacao_prof_estab",     "CO_UNIDADE"),
    ("idx_rel_prof",     "relacao_prof_estab",     "CO_PROFISSIONAL_SUS"),
]

def criar_indices(conn: sqlite3.Connection) -> None:
    print("\nCriando índices ...", flush=True)
    for idx_name, tabela, coluna in INDICES:
        try:
            conn.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{tabela}" ("{coluna}")')
            print(f"  ✓ {idx_name}")
        except Exception as e:
            print(f"  [AVISO] {idx_name}: {e}")
    conn.commit()
    print("Índices criados.")


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Importa CNES Brasil (mai/2026) para SQLite")
    parser.add_argument("--db", default=DEFAULT_DB,
                        help=f"Caminho do banco (padrão: {DEFAULT_DB})")
    parser.add_argument("--apenas", nargs="+", choices=list(ARQUIVOS.keys()), default=None,
                        help="Carregar só estas tabelas (ex.: --apenas estabelecimentos_cnes — "
                             "destrava o login da farmácia sem os arquivos multi-GB). Padrão: as 3.")
    args = parser.parse_args()

    arquivos_alvo = {t: ARQUIVOS[t] for t in (args.apenas or ARQUIVOS.keys())}

    db_path = Path(args.db)
    if not db_path.parent.exists():
        print(f"[ERRO] Diretório não existe: {db_path.parent}", file=sys.stderr)
        sys.exit(1)

    for tabela, caminho in arquivos_alvo.items():
        if not caminho.exists():
            print(f"[ERRO] Arquivo não encontrado: {caminho}", file=sys.stderr)
            print(f"       Execute primeiro: unzip BASE_DE_DADOS_CNES_202605.ZIP -d data/cnes_br_tmp/",
                  file=sys.stderr)
            sys.exit(1)

    print(f"\nBanco SQLite : {db_path}")
    print(f"Arquivos CNES: {TMP_DIR}\n")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")   # 64 MB cache

    resultados: dict[str, int] = {}
    try:
        for tabela, caminho in arquivos_alvo.items():
            print(f"\n[{tabela}]")
            resultados[tabela] = importar_arquivo(conn, tabela, caminho)
        criar_indices(conn)
    finally:
        conn.close()

    print("\n" + "=" * 56)
    print("  Importação concluída — CNES Brasil mai/2026")
    print("=" * 56)
    for tabela, total in resultados.items():
        print(f"  {tabela:<28} {total:>10,} linhas")
    print("=" * 56)
    print(f"\n  Banco: {db_path}")


if __name__ == "__main__":
    main()
