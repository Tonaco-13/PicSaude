"""
Fixture compartilhada para o cluster de testes CNES.

Arquitetura dual (docs/arquitetura_dual_bancos.md):
    app/domain/cnes_prescritor.py:_get_cnes_conn abre app.config.DB_PATH
    diretamente, ignorando qualquer `conn` injetada pelo caller. Para testar
    esse caminho sem o snapshot CNES físico (~2GB), criamos um SQLite tmp
    com o schema CNES e patcheamos a variável DB_PATH do módulo de produção.

O patch tem de ser no atributo do MÓDULO `app.domain.cnes_prescritor`,
não em `app.config`: `from app.config import DB_PATH` congela o valor no
momento do import, então setattr em `app.config.DB_PATH` depois não afeta
o módulo consumidor.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest


# Schema unificado — cobre o uso das 3 tabelas pelas funções de produção
# em cnes_prescritor.py (validar_cns_prescritor, _validar_vinculo_prestador)
# e identidade_prescritor.py (_buscar_cnes_por_conselho,
# BancoCnesConselhoProvider). Mantemos colunas que aparecem em qualquer
# SELECT, ainda que algum teste só preencha um subconjunto via helpers.
_DDL_CNES = """
CREATE TABLE profissionais_cnes (
    CO_PROFISSIONAL_SUS TEXT PRIMARY KEY,
    CO_CPF              TEXT,
    NO_PROFISSIONAL     TEXT,
    CO_CNS              TEXT
);

CREATE TABLE relacao_prof_estab (
    CO_UNIDADE          TEXT,
    CO_PROFISSIONAL_SUS TEXT,
    CO_CBO              TEXT,
    CO_CONSELHO_CLASSE  TEXT,
    NU_REGISTRO         TEXT,
    SG_UF_CRM           TEXT
);

CREATE TABLE estabelecimentos_cnes (
    CO_UNIDADE  TEXT PRIMARY KEY,
    CO_CNES     TEXT,
    NU_CNPJ     TEXT,
    NO_FANTASIA TEXT,
    TP_UNIDADE  TEXT
);
"""


class _CnesDbHelper:
    """Helper que inserta linhas no arquivo SQLite CNES de teste."""

    def __init__(self, path: str) -> None:
        self.path = path

    def _exec(self, sql: str, params: tuple) -> None:
        conn = sqlite3.connect(self.path)
        try:
            conn.execute(sql, params)
            conn.commit()
        finally:
            conn.close()

    def add_profissional(
        self,
        *,
        CO_PROFISSIONAL_SUS: str,
        NO_PROFISSIONAL: str,
        CO_CNS: str,
        CO_CPF: str = "",
    ) -> None:
        self._exec(
            "INSERT OR IGNORE INTO profissionais_cnes "
            "(CO_PROFISSIONAL_SUS, CO_CPF, NO_PROFISSIONAL, CO_CNS) "
            "VALUES (?, ?, ?, ?)",
            (CO_PROFISSIONAL_SUS, CO_CPF, NO_PROFISSIONAL, CO_CNS),
        )

    def add_relacao(
        self,
        *,
        CO_PROFISSIONAL_SUS: str,
        CO_CONSELHO_CLASSE: str,
        NU_REGISTRO: str,
        SG_UF_CRM: str,
        CO_CBO: str,
        CO_UNIDADE: str,
    ) -> None:
        self._exec(
            "INSERT INTO relacao_prof_estab "
            "(CO_UNIDADE, CO_PROFISSIONAL_SUS, CO_CBO, CO_CONSELHO_CLASSE, "
            " NU_REGISTRO, SG_UF_CRM) VALUES (?, ?, ?, ?, ?, ?)",
            (CO_UNIDADE, CO_PROFISSIONAL_SUS, CO_CBO, CO_CONSELHO_CLASSE,
             NU_REGISTRO, SG_UF_CRM),
        )

    def add_estabelecimento(
        self,
        *,
        CO_UNIDADE: str,
        CO_CNES: str,
        NU_CNPJ: str = "",
        NO_FANTASIA: str = "",
        TP_UNIDADE: str = "",
    ) -> None:
        self._exec(
            "INSERT OR IGNORE INTO estabelecimentos_cnes "
            "(CO_UNIDADE, CO_CNES, NU_CNPJ, NO_FANTASIA, TP_UNIDADE) "
            "VALUES (?, ?, ?, ?, ?)",
            (CO_UNIDADE, CO_CNES, NU_CNPJ, NO_FANTASIA, TP_UNIDADE),
        )


@pytest.fixture
def cnes_db(tmp_path: Path, monkeypatch) -> _CnesDbHelper:
    """
    SQLite tmp com o schema CNES + patch de `app.domain.cnes_prescritor.DB_PATH`.

    Use os helpers `add_profissional`, `add_relacao`, `add_estabelecimento`
    para seedar. `_get_cnes_conn()` em produção abrirá este arquivo a cada
    chamada (sem ser intercalado com a `conn` de aplicação).
    """
    db_file = tmp_path / "cnes_test.db"
    conn = sqlite3.connect(str(db_file))
    try:
        conn.executescript(_DDL_CNES)
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr("app.domain.cnes_prescritor.DB_PATH", str(db_file))
    return _CnesDbHelper(str(db_file))


@pytest.fixture
def cnes_db_sem_tabelas(tmp_path: Path, monkeypatch) -> str:
    """
    SQLite tmp VAZIO (sem CREATE TABLE) + patch de DB_PATH.

    Usado pelo teste que cobre o ramo `except Exception` em
    `validar_cns_prescritor` — quando o arquivo existe mas as tabelas
    CNES não, a consulta levanta `OperationalError` que vira
    `divergencias=["erro_consulta_cnes: ..."]` + `nao_encontrado`.
    """
    db_file = tmp_path / "cnes_vazio.db"
    sqlite3.connect(str(db_file)).close()  # cria arquivo vazio
    monkeypatch.setattr("app.domain.cnes_prescritor.DB_PATH", str(db_file))
    return str(db_file)
