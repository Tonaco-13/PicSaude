"""
Importa os arquivos CSV do CNES-PE para o banco SQLite do projeto.

Tabelas populadas:
  - profissionais_cnes       ← data/profissionais_pe.csv
  - relacao_prof_estab       ← data/relacao_prof_estab_pe.csv
  - estabelecimentos_cnes    ← data/estabelecimentos_pe.csv

Uso:
    python backend/scripts/importar_cnes_pe.py
    python backend/scripts/importar_cnes_pe.py --db caminho/para/banco.db
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

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # PicSaude_Dev/
DATA_DIR     = PROJECT_ROOT / "data"
DEFAULT_DB   = os.environ.get("PIX_SAUDE_DB") or str(DATA_DIR / "pix_saude_pe.db")

ARQUIVOS = {
    "profissionais_cnes":    DATA_DIR / "profissionais_pe.csv",
    "relacao_prof_estab":    DATA_DIR / "relacao_prof_estab_pe.csv",
    "estabelecimentos_cnes": DATA_DIR / "estabelecimentos_pe.csv",
}

CHUNK_SIZE = 500   # linhas por batch de INSERT


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def sanitize_col(name: str) -> str:
    """Converte um nome de coluna Oracle/CSV em identificador SQLite válido.

    Exemplos:
      TO_CHAR(DT_ATUALIZACAO,'DD/MM/YYYY')  →  DT_ATUALIZACAO_DDMMYYYY
      'CO_CPF'                               →  CO_CPF
    """
    # Remove aspas simples
    s = name.replace("'", "")
    # Extrai conteúdo entre parênteses se existir: TO_CHAR(X,Y) → X_Y
    s = re.sub(r"TO_CHAR\(([^,]+),[^)]+\)", r"\1", s)
    # Substitui caracteres não-alfanuméricos por sublinhado
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    # Colapsa múltiplos sublinhados
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper()


def ler_csv(caminho: Path, encoding: str = "utf-8") -> tuple[list[str], list[list[str]]]:
    """Lê CSV e retorna (colunas_sanitizadas, linhas)."""
    with open(caminho, encoding=encoding, errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        header_raw = next(reader)
        colunas = [sanitize_col(c) for c in header_raw]
        linhas = list(reader)
    return colunas, linhas


def recriar_tabela(conn: sqlite3.Connection, tabela: str, colunas: list[str]) -> None:
    """Drop + CREATE para garantir schema limpo e compatível com o CSV."""
    cols_sql = ",\n  ".join(f'"{c}" TEXT' for c in colunas)
    conn.execute(f'DROP TABLE IF EXISTS "{tabela}"')
    conn.execute(f"""
        CREATE TABLE "{tabela}" (
          {cols_sql}
        )
    """)
    conn.commit()


def inserir_em_lotes(
    conn: sqlite3.Connection,
    tabela: str,
    colunas: list[str],
    linhas: list[list[str]],
) -> int:
    """Insere linhas em batches. Retorna total inserido."""
    if not linhas:
        return 0

    placeholders = ", ".join("?" * len(colunas))
    cols_quoted  = ", ".join(f'"{c}"' for c in colunas)
    sql = f'INSERT INTO "{tabela}" ({cols_quoted}) VALUES ({placeholders})'

    n_colunas = len(colunas)
    total = 0

    for i in range(0, len(linhas), CHUNK_SIZE):
        batch = linhas[i : i + CHUNK_SIZE]
        # Garante que cada linha tenha exatamente n_colunas valores
        normalizado = [
            (row + [""] * n_colunas)[:n_colunas]
            for row in batch
        ]
        conn.executemany(sql, normalizado)
        total += len(batch)

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# Importação de cada arquivo
# ---------------------------------------------------------------------------

def importar_arquivo(
    conn: sqlite3.Connection,
    tabela: str,
    caminho: Path,
) -> int:
    if not caminho.exists():
        print(f"  [AVISO] Arquivo não encontrado: {caminho}")
        return 0

    print(f"  Lendo {caminho.name} ...", end=" ", flush=True)
    t0 = time.perf_counter()
    colunas, linhas = ler_csv(caminho)
    print(f"{len(linhas):,} linhas, {len(colunas)} colunas ({time.perf_counter()-t0:.1f}s)")

    recriar_tabela(conn, tabela, colunas)

    print(f"  Inserindo em '{tabela}' ...", end=" ", flush=True)
    t1 = time.perf_counter()
    total = inserir_em_lotes(conn, tabela, colunas, linhas)
    print(f"OK ({time.perf_counter()-t1:.1f}s)")

    return total


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Importa CSVs do CNES-PE para SQLite")
    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help=f"Caminho para o banco SQLite (padrão: {DEFAULT_DB})",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.parent.exists():
        print(f"[ERRO] Diretório do banco não existe: {db_path.parent}", file=sys.stderr)
        sys.exit(1)

    print(f"\nBanco SQLite: {db_path}")
    print(f"Diretório de dados: {DATA_DIR}\n")

    conn = sqlite3.connect(db_path)

    resultados: dict[str, int] = {}
    try:
        for tabela, caminho in ARQUIVOS.items():
            print(f"[{tabela}]")
            resultados[tabela] = importar_arquivo(conn, tabela, caminho)
            print()
    finally:
        conn.close()

    # Relatório final
    print("=" * 52)
    print("  Importação concluída")
    print("=" * 52)
    for tabela, total in resultados.items():
        print(f"  {tabela:<28} {total:>8,} linhas")
    print("=" * 52)


if __name__ == "__main__":
    main()
