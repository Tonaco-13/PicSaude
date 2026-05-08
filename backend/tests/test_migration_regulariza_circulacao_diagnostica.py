"""
tests/test_migration_regulariza_circulacao_diagnostica.py
=========================================================

Testes da migration ``a3f5c8d9e1b2_regulariza_circulacao_diagnostica``.

Esta é uma migration de regularização de débito técnico — registra na
cadeia Alembic as 3 tabelas do subdomínio circulação diagnóstica que
historicamente eram criadas via SQL legado (``backend/migrations/052_circulacao_diagnostica.sql``)
ou via ``init_tables.py`` (``Base.metadata.create_all()``), contornando o Alembic.

Cobertura:
  1. Upgrade cria as 3 tabelas com colunas, FKs, índices e defaults corretos
  2. Idempotência: rodar ``upgrade`` em banco que já tem as tabelas é no-op
  3. Downgrade remove as 3 tabelas (em ordem inversa, respeitando FK)
  4. Pós-condição: schema das 3 tabelas bate com a fonte de verdade (SQL legado)

Estratégia de teste:
  - SQLite tmp em ``tmp_path`` para isolamento.
  - Para testes 1/3/4: ``upgrade head`` aplica TODA a cadeia desde o baseline.
  - Para teste 2 (idempotência): pré-cria as 3 tabelas via SQL e depois roda
    ``upgrade head``. Sem o ``_table_exists`` guard, falharia com
    ``OperationalError: table circulacoes_diagnosticas already exists``.

Referência:
  - docs/CONSULTA-CODEX-MIGRATION-CIRCULACAO.md
  - alembic/versions/a3f5c8d9e1b2_regulariza_circulacao_diagnostica.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

REVISION_REGULARIZA = "a3f5c8d9e1b2"
REVISION_ANTERIOR = "e2e98a4780e4"  # ticket21_prescritor_certificados

TABELAS_SUBDOMINIO = [
    "circulacoes_diagnosticas",
    "circulacao_diagnostica_itens",
    "circulacao_diagnostica_eventos",
]

# Colunas obrigatórias por tabela — espelham o SQL legado
# (backend/migrations/052_circulacao_diagnostica.sql)
COLUNAS_OBRIGATORIAS = {
    "circulacoes_diagnosticas": {
        "id", "protocolo", "chave_circulacao", "pedido_id", "paciente_id",
        "org_id", "unidade_id", "data_hora_proposta", "local_texto",
        "instrucoes_preparo", "observacao", "status", "tipo_emissao",
        "origem_circulacao_id", "validade", "criado_por", "criado_em",
    },
    "circulacao_diagnostica_itens": {
        "id", "circulacao_id", "pedido_exame_item_id", "nome_exame", "criado_em",
    },
    "circulacao_diagnostica_eventos": {
        "id", "circulacao_id", "tipo_evento", "dados_json", "criado_em",
    },
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def alembic_setup(tmp_path, monkeypatch):
    """SQLite tmp + alembic.Config carregado do alembic.ini real."""
    db_path = tmp_path / "test_regulariza.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    backend_root = Path(__file__).resolve().parent.parent
    alembic_ini = backend_root / "alembic.ini"
    cfg = Config(str(alembic_ini))
    monkeypatch.chdir(backend_root)

    return cfg, db_path


def _engine(db_path: Path):
    return create_engine(f"sqlite:///{db_path}")


def _colunas(db_path: Path, tabela: str) -> set:
    return {c["name"] for c in inspect(_engine(db_path)).get_columns(tabela)}


def _indices(db_path: Path, tabela: str) -> set:
    return {ix["name"] for ix in inspect(_engine(db_path)).get_indexes(tabela)}


def _foreign_keys(db_path: Path, tabela: str) -> list[dict]:
    return inspect(_engine(db_path)).get_foreign_keys(tabela)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_upgrade_cria_3_tabelas_do_subdominio(alembic_setup):
    """
    Após ``upgrade`` até a regularização, as 3 tabelas existem no banco.
    Verifica também a presença de todas as colunas obrigatórias.
    """
    cfg, db_path = alembic_setup
    command.upgrade(cfg, REVISION_REGULARIZA)

    insp = inspect(_engine(db_path))
    tabelas_no_banco = set(insp.get_table_names())
    for tabela in TABELAS_SUBDOMINIO:
        assert tabela in tabelas_no_banco, (
            f"Tabela '{tabela}' não foi criada pela migration."
        )

    for tabela, cols_esperadas in COLUNAS_OBRIGATORIAS.items():
        cols_no_banco = _colunas(db_path, tabela)
        faltantes = cols_esperadas - cols_no_banco
        assert not faltantes, (
            f"Tabela '{tabela}' está sem colunas: {sorted(faltantes)}"
        )


def test_upgrade_idempotente_se_tabelas_ja_existem(alembic_setup):
    """
    Se o banco já tem as 3 tabelas (cenário do dev: ``init_tables.py``
    rodou antes), ``upgrade`` deve ser no-op via ``_table_exists`` guard.

    Pré-condição: cria as tabelas com SQL minimalista (DDL não precisa
    bater 100% com a final — só precisa ter o nome certo, o guard checa
    apenas existência).
    """
    cfg, db_path = alembic_setup

    # Avança até a revisão imediatamente anterior (estado pré-regularização)
    command.upgrade(cfg, REVISION_ANTERIOR)

    # Simula que init_tables.py criou as 3 tabelas "por fora" do Alembic
    with _engine(db_path).begin() as conn:
        conn.execute(text(
            "CREATE TABLE circulacoes_diagnosticas ("
            "id INTEGER PRIMARY KEY, "
            "_simulado_init_tables TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE circulacao_diagnostica_itens ("
            "id INTEGER PRIMARY KEY, "
            "_simulado_init_tables TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE circulacao_diagnostica_eventos ("
            "id INTEGER PRIMARY KEY, "
            "_simulado_init_tables TEXT)"
        ))

    # Agora aplicar a regularização: o guard _table_exists deve fazer no-op
    # (sem essa, daria "table already exists")
    command.upgrade(cfg, REVISION_REGULARIZA)

    # Confirma: a coluna sentinela do nosso INSERT de simulação ainda existe,
    # ou seja, a migration NÃO recriou a tabela (no-op confirmado)
    cols = _colunas(db_path, "circulacoes_diagnosticas")
    assert "_simulado_init_tables" in cols, (
        "Migration recriou tabela em vez de fazer no-op — guard _table_exists "
        "não está funcionando."
    )


def test_downgrade_remove_3_tabelas(alembic_setup):
    """
    Após ``downgrade`` da regularização, nenhuma das 3 tabelas existe.
    Garante reversibilidade (CODEX-recomendado).
    """
    cfg, db_path = alembic_setup
    command.upgrade(cfg, REVISION_REGULARIZA)
    command.downgrade(cfg, REVISION_ANTERIOR)

    insp = inspect(_engine(db_path))
    tabelas_no_banco = set(insp.get_table_names())
    for tabela in TABELAS_SUBDOMINIO:
        assert tabela not in tabelas_no_banco, (
            f"Tabela '{tabela}' permaneceu após downgrade."
        )


def test_circulacao_diagnostica_eventos_tem_fk_para_mae(alembic_setup):
    """
    A FK ``circulacao_id → circulacoes_diagnosticas(id)`` é obrigatória
    para garantir integridade referencial do ledger imutável.

    Se a FK estiver ausente, a tabela vira um log "solto" — eventos
    podem referenciar circulações inexistentes silenciosamente.
    """
    cfg, db_path = alembic_setup
    command.upgrade(cfg, REVISION_REGULARIZA)

    fks = _foreign_keys(db_path, "circulacao_diagnostica_eventos")
    fk_circulacao = next(
        (fk for fk in fks if fk["constrained_columns"] == ["circulacao_id"]),
        None,
    )
    assert fk_circulacao is not None, (
        "FK circulacao_id ausente em circulacao_diagnostica_eventos"
    )
    assert fk_circulacao["referred_table"] == "circulacoes_diagnosticas", (
        f"FK aponta para '{fk_circulacao['referred_table']}' "
        f"em vez de 'circulacoes_diagnosticas'"
    )


def test_indices_idx_pattern_criados(alembic_setup):
    """
    Os índices nomeados ``idx_*`` (não ``ix_*``) são criados conforme o
    SQL legado.

    Por que o nome importa: o banco do Mac já tem os índices com prefixo
    ``idx_*`` (do SQL legado). Se a regularização criasse com prefixo
    ``ix_*`` (padrão SQLAlchemy), em ambientes pré-existentes haveria
    índices duplicados (``idx_*`` antigo + ``ix_*`` novo).
    """
    cfg, db_path = alembic_setup
    command.upgrade(cfg, REVISION_REGULARIZA)

    indices_esperados = {
        "circulacoes_diagnosticas": {
            "idx_circulacoes_diagnosticas_pedido_id",
            "idx_circulacoes_diagnosticas_paciente_id",
            "idx_circulacoes_diagnosticas_org_id",
            "idx_circulacoes_diagnosticas_unidade_id",
        },
        "circulacao_diagnostica_itens": {
            "idx_circulacao_diagnostica_itens_circulacao_id",
            "idx_circulacao_diagnostica_itens_pedido_exame_item_id",
        },
        "circulacao_diagnostica_eventos": {
            "idx_circulacao_diagnostica_eventos_circulacao_id",
        },
    }

    for tabela, esperados in indices_esperados.items():
        ix_no_banco = _indices(db_path, tabela)
        faltantes = esperados - ix_no_banco
        assert not faltantes, (
            f"Tabela '{tabela}' está sem índices: {sorted(faltantes)}. "
            f"Existentes: {sorted(ix_no_banco)}"
        )


def test_status_tem_server_default_selecionado(alembic_setup):
    """
    As colunas ``status`` e ``tipo_emissao`` em ``circulacoes_diagnosticas``
    devem ter ``server_default`` (DDL-side, não Python-side).

    CODEX (2026-05-08) apontou que ``default=...`` no model é Python-side:
    SQLAlchemy preenche em INSERT, mas o DDL não tem ``DEFAULT 'selecionado'``.
    Para reproduzir fielmente o SQL legado
    (``backend/migrations/052_circulacao_diagnostica.sql``), a migration
    deve usar ``server_default``.

    Verificação por reflection: ``inspect(engine).get_columns(tabela)``
    retorna o atributo ``default`` que corresponde ao DDL ``DEFAULT ...``.
    Se ``default is None``, o DDL não tem default — o teste falha.

    Estratégia escolhida (reflection vs INSERT): reflection é independente
    do schema de outras tabelas (``pedidos_exame``, ``pacientes``) e não
    sofre com drift conhecido (Task #5 — drift model vs alembic). Testa
    exatamente o que importa: o DDL declarou ``DEFAULT 'selecionado'``.
    """
    cfg, db_path = alembic_setup
    command.upgrade(cfg, REVISION_REGULARIZA)

    insp = inspect(_engine(db_path))
    cols_por_nome = {c["name"]: c for c in insp.get_columns("circulacoes_diagnosticas")}

    # SQLite expõe o server_default como string com aspas: "'selecionado'"
    # PostgreSQL expõe sem aspas externas. Aceitamos ambos via .strip("'").
    status_col = cols_por_nome["status"]
    assert status_col["default"] is not None, (
        "Coluna 'status' está sem server_default (DDL não tem DEFAULT). "
        "Isso indica que a migration usa default= em vez de server_default=."
    )
    valor_default_status = str(status_col["default"]).strip("'\"")
    assert valor_default_status == "selecionado", (
        f"server_default de 'status' incorreto: obtido='{valor_default_status}', "
        f"esperado='selecionado'"
    )

    tipo_emissao_col = cols_por_nome["tipo_emissao"]
    assert tipo_emissao_col["default"] is not None, (
        "Coluna 'tipo_emissao' está sem server_default."
    )
    valor_default_tipo = str(tipo_emissao_col["default"]).strip("'\"")
    assert valor_default_tipo == "novo", (
        f"server_default de 'tipo_emissao' incorreto: obtido='{valor_default_tipo}', "
        f"esperado='novo'"
    )
