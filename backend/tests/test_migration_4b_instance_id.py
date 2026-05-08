"""
tests/test_migration_4b_instance_id.py
======================================

Testes da migration ``4b1ce80a017d_etapa4b_add_instance_id``.

Cobertura:
  1. ``upgrade head`` adiciona coluna ``instance_id`` nas 10 tabelas alvo
  2. ``downgrade`` remove a coluna nas 10 tabelas
  3. ``upgrade head`` é idempotente (re-aplicar não falha)
  4. Coluna ``instance_id`` é ``VARCHAR(36) NULL`` (nullable, comprimento UUID v4)

Estratégia:
  - Cada teste cria um SQLite temporário em ``tmp_path``.
  - ``DATABASE_URL`` é setada via ``monkeypatch`` ANTES do Alembic ler
    ``env.py`` — env.py respeita ``DATABASE_URL`` (ver ``alembic/env.py``).
  - ``alembic.command`` é usado programaticamente (sem subprocess).
  - O upgrade aplica TODA a cadeia desde o baseline (a migration 4B só
    ALTERA tabelas que já existem nas migrations anteriores).

Por que testar migration:
  - 4B é classe ``core`` (toca o ledger imutável). Operações no schema do
    ledger não podem falhar silenciosamente.
  - Sem teste de downgrade, um ambiente preso na 4B fica sem caminho de
    rollback se outra migration falhar depois.
  - Idempotência protege contra ``alembic upgrade head`` rodado duas vezes
    em scripts de deploy (cenário comum em CI/CD).

Referência: docs/PLANO-PRODUCAO-V2.md §4 (sub-tarefa 4B).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


# ---------------------------------------------------------------------------
# Constantes — espelham as listas em ``4b1ce80a017d_etapa4b_add_instance_id.py``
# ---------------------------------------------------------------------------

REVISION_4B = "4b1ce80a017d"
REVISION_PREVIA = "a3f5c8d9e1b2"  # regulariza_circulacao_diagnostica (precondição imediata da 4B).
# Importante (CODEX, 2026-05-08): apontar para a regularização — não para
# e2e98a4780e4 — para que o teste de downgrade da 4B remova APENAS a coluna
# instance_id, e não derrube também as 3 tabelas de circulação diagnóstica.
# Caso contrário, o teste passaria pelo motivo errado.

TABELAS_LEDGER = [
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "circulacao_diagnostica_eventos",
    "agendamento_eventos",
    "eventos_publicacao",
]

TABELAS_PRINCIPAIS = [
    "prescricoes",
    "pedidos_exame",
    "laudos",
    "agendamentos",
]

TODAS_AS_TABELAS = TABELAS_LEDGER + TABELAS_PRINCIPAIS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def alembic_setup(tmp_path, monkeypatch):
    """
    Configura ambiente isolado para rodar migrations:
      - SQLite temporário em ``tmp_path/test_migration.db``
      - ``DATABASE_URL`` apontando para esse SQLite
      - ``alembic.Config`` carregando o ``alembic.ini`` real do projeto

    Retorna:
      tupla ``(cfg, db_path)`` — config alembic e caminho do banco SQLite.
    """
    db_path = tmp_path / "test_migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    # alembic.ini fica em backend/alembic.ini (dois níveis acima deste arquivo)
    backend_root = Path(__file__).resolve().parent.parent
    alembic_ini = backend_root / "alembic.ini"
    assert alembic_ini.exists(), f"alembic.ini não encontrado em {alembic_ini}"

    cfg = Config(str(alembic_ini))

    # Garante que o env.py do alembic encontre os models
    # (env.py já tem essa lógica, mas reforçamos aqui para o pytest)
    monkeypatch.chdir(backend_root)

    return cfg, db_path


def _colunas(db_path: Path, tabela: str) -> dict:
    """Retorna dict {nome_coluna: dict_metadata} da tabela no SQLite."""
    engine = create_engine(f"sqlite:///{db_path}")
    inspector = inspect(engine)
    return {c["name"]: c for c in inspector.get_columns(tabela)}


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_upgrade_head_adiciona_instance_id_em_todas_10_tabelas(alembic_setup):
    """
    ``alembic upgrade head`` em SQLite virgem aplica TODA a cadeia, incluindo
    a 4B, e cada uma das 10 tabelas alvo recebe a coluna ``instance_id``.

    Esta é a verificação primária da migration: nenhuma tabela é esquecida
    no for-loop ``for tabela in TODAS_AS_TABELAS``.
    """
    cfg, db_path = alembic_setup

    command.upgrade(cfg, "head")

    for tabela in TODAS_AS_TABELAS:
        colunas = _colunas(db_path, tabela)
        assert "instance_id" in colunas, (
            f"Tabela '{tabela}' não recebeu a coluna 'instance_id' após upgrade."
        )


def test_upgrade_head_idempotente(alembic_setup):
    """
    ``alembic upgrade head`` aplicado duas vezes não falha.

    Cenário real: deploy roda ``alembic upgrade head`` no boot. Se o boot
    reiniciar (crash, SIGHUP), a segunda chamada não pode quebrar a
    aplicação — Alembic deve reconhecer que já está no head e ser no-op.
    """
    cfg, db_path = alembic_setup

    command.upgrade(cfg, "head")
    # Re-aplicar: não deve raise
    command.upgrade(cfg, "head")

    # Sanity: a coluna continua lá após a segunda invocação
    colunas = _colunas(db_path, "prescricoes")
    assert "instance_id" in colunas


def test_downgrade_remove_instance_id_de_todas_10_tabelas(alembic_setup):
    """
    Após ``downgrade`` para a revisão imediatamente anterior à 4B
    (``e2e98a4780e4``), nenhuma das 10 tabelas mantém a coluna
    ``instance_id``.

    Garante reversibilidade: se a 4B precisar ser rollback no futuro,
    o caminho de volta funciona sem perder dados das outras colunas.
    """
    cfg, db_path = alembic_setup

    command.upgrade(cfg, "head")
    command.downgrade(cfg, REVISION_PREVIA)

    for tabela in TODAS_AS_TABELAS:
        colunas = _colunas(db_path, tabela)
        assert "instance_id" not in colunas, (
            f"Tabela '{tabela}' ainda contém 'instance_id' após downgrade — "
            f"rollback incompleto."
        )


def test_coluna_instance_id_eh_varchar_36_nullable(alembic_setup):
    """
    A coluna ``instance_id`` deve ser ``VARCHAR(36) NULL`` em todas as
    tabelas (formato canônico de UUID v4 cabe em 36 caracteres).

    NULL é exigido por decisão arquitetural (docstring da migration):
    preserva registros pré-instance_id sem forçar backfill automático,
    o que violaria a imutabilidade do ledger.

    Verificamos um subset representativo (1 tabela do ledger + 1 principal):
    o for-loop da migration garante que se a coluna está correta numa
    tabela, está correta em todas (vide
    test_upgrade_head_adiciona_instance_id_em_todas_10_tabelas).
    """
    cfg, db_path = alembic_setup

    command.upgrade(cfg, "head")

    amostra = ["prescricoes", "prescricao_eventos"]
    for tabela in amostra:
        colunas = _colunas(db_path, tabela)
        col = colunas["instance_id"]

        assert col["nullable"] is True, (
            f"{tabela}.instance_id deve ser nullable=True (preserva registros "
            f"pré-instance_id). Recebido: nullable={col['nullable']}"
        )

        # Em SQLite, o tipo aparece como "VARCHAR(36)" (string)
        tipo_str = str(col["type"]).upper()
        assert "36" in tipo_str, (
            f"{tabela}.instance_id deve ser VARCHAR(36). "
            f"Recebido: type={tipo_str}"
        )


def test_revisao_4b_existe_na_cadeia(alembic_setup):
    """
    Sanity check: após ``upgrade head``, a revisão atual no banco é a 4B.
    Garante que a migration entrou na cadeia e não foi ignorada por algum
    erro de encadeamento (down_revision inválido, branch órfão, etc.).
    """
    cfg, db_path = alembic_setup

    command.upgrade(cfg, "head")

    # Lê a versão atual diretamente da tabela alembic_version
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        from sqlalchemy import text

        row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
        assert row is not None, "Tabela alembic_version vazia após upgrade"
        assert row[0] == REVISION_4B, (
            f"Head do banco esperado={REVISION_4B}, obtido={row[0]}. "
            f"Migration 4B não é o head ou cadeia está fora de ordem."
        )
