"""Gate PG do loader `scripts/importar_cnes_pg.py` — prova que a carga nacional do
CNES popula o PostgreSQL e que a query EXATA do login encontra o estabelecimento.

As tabelas CNES são de REFERÊNCIA (criadas fora do Alembic). O loader usa conexão
própria que COMMITa, então este teste DROPa as 3 tabelas no teardown para não poluir
`test_prestadores_institucional_pg::...cnes_ausente_fail_open` (que exige a tabela ausente).

Requer PostgreSQL (pulado se DATABASE_URL não for PG).
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psycopg2
import pytest

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL.startswith("postgresql"):
    pytest.skip("requer PostgreSQL (DATABASE_URL)", allow_module_level=True)

# Carrega o script de scripts/ (fora do pacote app) por caminho.
_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "importar_cnes_pg.py"
_spec = importlib.util.spec_from_file_location("importar_cnes_pg", _SCRIPT)
loader = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loader)  # type: ignore[union-attr]

_TABELAS = ["estabelecimentos_cnes", "profissionais_cnes", "relacao_prof_estab"]


def _escrever_csvs(d: Path) -> None:
    (d / "tbEstabelecimento202512.csv").write_text(
        "CO_CNES;NU_CNPJ;TP_UNIDADE;NO_FANTASIA;NO_RAZAO_SOCIAL;CO_ESTADO_GESTOR\n"
        "1234567;12.345.678/0001-95;05;Farmacia Central;Farmacia Central LTDA;26\n"
        "0000001;11222333000144;73;Clinica Y;Clinica Y ME\n",  # linha curta (falta CO_ESTADO_GESTOR)
        encoding="utf-8",
    )
    (d / "tbDadosProfissionalSus202512.csv").write_text(
        "CO_PROFISSIONAL_SUS;CO_CNS;NO_PROFISSIONAL\nP1;700000000000001;MARIA SILVA\n",
        encoding="utf-8",
    )
    (d / "tbCargaHorariaSus202512.csv").write_text(
        "CO_UNIDADE;CO_PROFISSIONAL_SUS;CO_CBO\n1234567;P1;225125\n",
        encoding="utf-8",
    )


@pytest.fixture
def carga_cnes(tmp_path):
    _escrever_csvs(tmp_path)
    conn = psycopg2.connect(loader.resolver_database_url(None))
    try:
        for tabela, csv_nome in loader.ARQUIVOS_CSV.items():
            loader.importar_arquivo(conn, tabela, tmp_path / csv_nome)
        loader.criar_indices(conn, set(loader.ARQUIVOS_CSV))
        yield conn
    finally:
        cur = conn.cursor()
        for t in _TABELAS:
            cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
        conn.commit()
        conn.close()


def test_carga_popula_contagens(carga_cnes):
    cur = carga_cnes.cursor()
    cur.execute("SELECT COUNT(*) FROM estabelecimentos_cnes")
    assert cur.fetchone()[0] == 2
    cur.execute("SELECT COUNT(*) FROM profissionais_cnes")
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT COUNT(*) FROM relacao_prof_estab")
    assert cur.fetchone()[0] == 1


def test_query_login_encontra_estabelecimento(carga_cnes):
    """A query EXATA do login (CNPJ normalizado + TP_UNIDADE) acha a farmácia."""
    cur = carga_cnes.cursor()
    cur.execute(
        'SELECT "CO_CNES" FROM estabelecimentos_cnes '
        "WHERE REPLACE(REPLACE(REPLACE(REPLACE(\"NU_CNPJ\",'.',''),'/',''),'-',''),' ','') = %s "
        'AND "TP_UNIDADE" IN (%s) LIMIT 1',
        ("12345678000195", "05"),
    )
    assert cur.fetchone()[0] == "1234567"


def test_linha_curta_normalizada(carga_cnes):
    """Linha com colunas faltantes carrega com vazio — não quebra a importação."""
    cur = carga_cnes.cursor()
    cur.execute('SELECT "CO_ESTADO_GESTOR" FROM estabelecimentos_cnes WHERE "CO_CNES" = \'0000001\'')
    assert cur.fetchone()[0] == ""


def test_indice_funcional_casa_com_query_login(carga_cnes):
    """O índice funcional idx_estab_cnpj_norm é estruturalmente usável pela query do login."""
    cur = carga_cnes.cursor()
    cur.execute("SET enable_seqscan = off")
    cur.execute(
        'EXPLAIN SELECT "CO_CNES" FROM estabelecimentos_cnes '
        "WHERE REPLACE(REPLACE(REPLACE(REPLACE(\"NU_CNPJ\",'.',''),'/',''),'-',''),' ','') = %s",
        ("12345678000195",),
    )
    plano = "\n".join(row[0] for row in cur.fetchall())
    assert "idx_estab_cnpj_norm" in plano, plano
