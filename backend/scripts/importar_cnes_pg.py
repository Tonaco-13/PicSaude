"""
Importa o CNES nacional (estabelecimentos + profissionais + vínculos) para PostgreSQL.

Espelha `importar_cnes_br.py` (que é SQLite-only), mas carrega na base PG — usado
para popular a gaveta de referência da PRODUÇÃO. As tabelas do CNES são dados
EXTERNOS do DATASUS (não schema clínico): por isso são criadas FORA do Alembic
(DROP + CREATE ... TEXT), exatamente como no fluxo SQLite. O Alembic continua dono
apenas do schema clínico.

Tabelas populadas (substituição completa):
  - estabelecimentos_cnes  ← cnes_br_tmp/tbEstabelecimento202605.csv   (~400 mil — usada no login da farmácia)
  - profissionais_cnes     ← cnes_br_tmp/tbDadosProfissionalSus202605.csv
  - relacao_prof_estab     ← cnes_br_tmp/tbCargaHorariaSus202605.csv

Pré-requisito: data/cnes_br_tmp/ com os 3 CSVs
  (unzip BASE_DE_DADOS_CNES_202605.ZIP -d data/cnes_br_tmp/).

Uso:
    DATABASE_URL=postgresql://user:senha@host:5432/picsaude python backend/scripts/importar_cnes_pg.py
    DATABASE_URL=postgresql://... python backend/scripts/importar_cnes_pg.py --apenas estabelecimentos_cnes
    DATABASE_URL=postgresql://... python backend/scripts/importar_cnes_pg.py --tmp-dir /caminho/csvs  # p/ testes
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

# ---------------------------------------------------------------------------
# Caminhos padrão
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR     = PROJECT_ROOT / "data"
DEFAULT_TMP  = DATA_DIR / "cnes_br_tmp"

# nome lógico -> nome do CSV (resolvido contra --tmp-dir em runtime)
ARQUIVOS_CSV = {
    "estabelecimentos_cnes": "tbEstabelecimento202605.csv",
    "profissionais_cnes":    "tbDadosProfissionalSus202605.csv",
    "relacao_prof_estab":    "tbCargaHorariaSus202605.csv",
}

# Índices (espelham importar_cnes_br.py) + 1 índice FUNCIONAL que casa com a query
# do login (REPLACE encadeado em NU_CNPJ) para conferência rápida da farmácia.
INDICES = [
    ("idx_estab_nome",     "estabelecimentos_cnes", '"NO_RAZAO_SOCIAL"'),
    ("idx_estab_fantasia", "estabelecimentos_cnes", '"NO_FANTASIA"'),
    ("idx_estab_cnpj",     "estabelecimentos_cnes", '"NU_CNPJ"'),
    ("idx_estab_uf",       "estabelecimentos_cnes", '"CO_ESTADO_GESTOR"'),
    ("idx_prof_nome",      "profissionais_cnes",    '"NO_PROFISSIONAL"'),
    ("idx_prof_cns",       "profissionais_cnes",    '"CO_CNS"'),
    ("idx_rel_unidade",    "relacao_prof_estab",    '"CO_UNIDADE"'),
    ("idx_rel_prof",       "relacao_prof_estab",    '"CO_PROFISSIONAL_SUS"'),
]
# Expressão IDÊNTICA à do login (routers/login.py) — índice funcional só é usado se casar.
_CNPJ_NORMALIZADO = (
    "REPLACE(REPLACE(REPLACE(REPLACE(\"NU_CNPJ\", '.', ''), '/', ''), '-', ''), ' ', '')"
)
INDICES_FUNCIONAIS = [
    ("idx_estab_cnpj_norm", "estabelecimentos_cnes", f"({_CNPJ_NORMALIZADO})"),
]

CHUNK_SIZE = 5000


# ---------------------------------------------------------------------------
# Utilitários de CSV (espelham importar_cnes_br.py)
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
        yield [sanitize_col(c) for c in header_raw]
        for row in reader:
            yield row


# ---------------------------------------------------------------------------
# Carga PostgreSQL
# ---------------------------------------------------------------------------

def recriar_tabela(cur, tabela: str, colunas: list[str]) -> None:
    cols_sql = ",\n  ".join(f'"{c}" TEXT' for c in colunas)
    cur.execute(f'DROP TABLE IF EXISTS "{tabela}" CASCADE')
    cur.execute(f'CREATE TABLE "{tabela}" (\n  {cols_sql}\n)')


def importar_arquivo(conn, tabela: str, caminho: Path) -> int:
    if not caminho.exists():
        print(f"  [ERRO] Arquivo não encontrado: {caminho}", file=sys.stderr)
        sys.exit(1)

    print(f"  Lendo {caminho.name} ...", flush=True)
    gen = ler_csv_stream(caminho)
    colunas = next(gen)
    n = len(colunas)
    print(f"  {n} colunas. Recriando tabela '{tabela}' ...", flush=True)

    cur = conn.cursor()
    recriar_tabela(cur, tabela, colunas)
    conn.commit()

    cols_quoted = ", ".join(f'"{c}"' for c in colunas)
    sql = f'INSERT INTO "{tabela}" ({cols_quoted}) VALUES %s'

    total = 0
    batch: list[tuple] = []
    t0 = time.perf_counter()
    for row in gen:
        # normaliza o comprimento da linha (CSV do DATASUS tem linhas curtas/longas)
        batch.append(tuple((row + [""] * n)[:n]))
        if len(batch) >= CHUNK_SIZE:
            execute_values(cur, sql, batch, page_size=CHUNK_SIZE)
            conn.commit()
            total += len(batch)
            batch = []
            if total % 200_000 == 0:
                print(f"    {total:,} linhas ({time.perf_counter()-t0:.0f}s) ...", flush=True)
    if batch:
        execute_values(cur, sql, batch, page_size=CHUNK_SIZE)
        conn.commit()
        total += len(batch)

    cur.close()
    print(f"  OK — {total:,} linhas em {time.perf_counter()-t0:.1f}s")
    return total


def criar_indices(conn, tabelas_carregadas: set[str]) -> None:
    print("\nCriando índices ...", flush=True)
    cur = conn.cursor()
    for nome, tabela, coluna in INDICES + INDICES_FUNCIONAIS:
        if tabela not in tabelas_carregadas:
            continue
        try:
            cur.execute(f'CREATE INDEX IF NOT EXISTS "{nome}" ON "{tabela}" ({coluna})')
            conn.commit()
            print(f"  ✓ {nome}")
        except Exception as e:  # noqa: BLE001 — índice é best-effort
            conn.rollback()
            print(f"  [AVISO] {nome}: {e}")
    cur.close()


# ---------------------------------------------------------------------------
# Resolução de DATABASE_URL (mesma lógica de database.py: normaliza postgres://)
# ---------------------------------------------------------------------------

def resolver_database_url(cli_url: str | None) -> str:
    url = cli_url or os.getenv("DATABASE_URL", "")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if not url.startswith("postgresql"):
        print(
            "[ERRO] Este importador é EXCLUSIVO de PostgreSQL. Defina DATABASE_URL=postgresql://...\n"
            "       Para SQLite (dev/teste), use backend/scripts/importar_cnes_br.py.",
            file=sys.stderr,
        )
        sys.exit(2)
    return url


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa CNES nacional para PostgreSQL")
    parser.add_argument("--db-url", default=None, help="DATABASE_URL (senão lê do ambiente)")
    parser.add_argument("--tmp-dir", default=str(DEFAULT_TMP), help="Pasta com os CSVs do CNES")
    parser.add_argument("--apenas", nargs="+", choices=list(ARQUIVOS_CSV),
                        help="Carregar apenas estas tabelas (padrão: todas)")
    args = parser.parse_args()

    db_url = resolver_database_url(args.db_url)
    tmp_dir = Path(args.tmp_dir)
    alvos = args.apenas or list(ARQUIVOS_CSV)

    # confere os arquivos ANTES de tocar no banco
    arquivos = {t: tmp_dir / ARQUIVOS_CSV[t] for t in alvos}
    faltando = [str(c) for c in arquivos.values() if not c.exists()]
    if faltando:
        print("[ERRO] CSVs ausentes:", file=sys.stderr)
        for f in faltando:
            print(f"   - {f}", file=sys.stderr)
        print("       unzip BASE_DE_DADOS_CNES_202605.ZIP -d data/cnes_br_tmp/", file=sys.stderr)
        sys.exit(1)

    safe_url = re.sub(r"://[^:@]+:[^@]+@", "://<credenciais>@", db_url)
    print(f"\nPostgreSQL : {safe_url}")
    print(f"CSVs       : {tmp_dir}")
    print(f"Tabelas    : {', '.join(alvos)}\n")

    conn = psycopg2.connect(db_url)
    resultados: dict[str, int] = {}
    try:
        for tabela, caminho in arquivos.items():
            print(f"[{tabela}]")
            resultados[tabela] = importar_arquivo(conn, tabela, caminho)
        criar_indices(conn, set(alvos))
    finally:
        conn.close()

    print("\n" + "=" * 56)
    print("  Importação concluída — CNES nacional (PostgreSQL)")
    print("=" * 56)
    for tabela, total in resultados.items():
        print(f"  {tabela:<28} {total:>12,} linhas")
    print("=" * 56)


if __name__ == "__main__":
    main()
