"""
init_tables.py
==============

⚠️  DEPRECADO — use 'alembic upgrade head' para evoluir o schema.

Este arquivo é mantido apenas para:
  - bootstrap inicial de ambientes de desenvolvimento
  - CHECAGEM de schema (tabelas esperadas + triggers de imutabilidade)

Ele NÃO cria mais os triggers de imutabilidade do ledger
(TICKET-LEDGER-TRIGGERS-MIGRACAO). Quem cria é a migração
`f2b7c1d0a4e5_ledger_triggers_imutabilidade`, porque é a migração que roda em
produção: o `predeploy.sh` do Render executa `alembic upgrade head` + `seed_demo.py`
e NUNCA chama este script. Enquanto os triggers nasciam aqui — em código
`sqlite3.connect()`, SQLite-only — o PostgreSQL jamais os teve. Invariante que só
existe no script de bootstrap não chega em produção.

A partir do Ticket 2, o mecanismo OFICIAL de evolução de schema é o Alembic:
  cd backend && alembic upgrade head

NÃO adicione novas tabelas ou colunas aqui — crie uma migration Alembic:
  alembic revision -m "descricao_da_mudanca"

O create_all() desta ferramenta NÃO faz ALTER TABLE. Novas colunas adicionadas
aos models Python não aparecerão no banco sem uma migration explícita.
Esse comportamento foi a causa da ausência de 'classe_controle' no banco (Ticket 44).

-----------------------------------------------------------------------
Suporta PostgreSQL (DATABASE_URL) e SQLite (fallback dev).

Uso:
    cd backend
    DATABASE_URL=postgresql://user:pass@localhost:5432/picsaude python3 init_tables.py
    # ou (dev SQLite):
    python3 init_tables.py

Seguro para re-execução: usa CREATE TABLE IF NOT EXISTS via SQLAlchemy.
Não apaga dados existentes.
"""

from __future__ import annotations

import os
import sys

# Garante que o pacote `app` seja encontrado mesmo rodando direto da pasta backend/
sys.path.insert(0, os.path.dirname(__file__))

from app.database import Base, engine, _USE_SQLITE
import app.models  # noqa: F401 — registra todos os models no Base.metadata


# ---------------------------------------------------------------------------
# Tabelas de eventos (ledger imutável) — protegidas por triggers no banco
# ---------------------------------------------------------------------------
# Fonte única: a MESMA lista que a migração usa para criar os triggers. Ver o
# bloco "Triggers de imutabilidade do ledger" abaixo.

from app.domain.ledger_imutabilidade import TABELAS_LEDGER as _TABELAS_LEDGER

# ---------------------------------------------------------------------------
# Tabelas esperadas na aplicação
# ---------------------------------------------------------------------------

_TABELAS_APP = [
    "pacientes",
    "prescritores",
    "estabelecimentos_proprios",
    "prescricoes",
    "prescricao_itens",
    "prescricao_eventos",
    "codigos_login",
    "prescricao_custodia",
    "dispensacoes",
    "usuarios",
    "prescricao_assinatura",          # Ticket 5 — metadados de assinatura digital
    "solicitacoes_renovacao",         # Ticket 13 — solicitações de renovação pelo paciente
    "pedidos_exame",                  # Ticket 15 — módulo de pedidos de exame
    "pedido_exame_itens",             # Ticket 15
    "pedido_exame_eventos",           # Ticket 15 — ledger de exames
    "pedido_exame_custodia",          # Ticket 15 — cadeia de custódia de exames
    "laudos",                         # Ticket 20 — módulo de laudos
    "laudo_itens",                    # Ticket 20
    "laudo_eventos",                  # Ticket 20 — ledger de laudos
    "laudo_custodia",                 # Ticket 20 — cadeia de custódia de laudos
    "tokens_apresentacao",            # Ticket 24 — token de apresentação
    "tokens_apresentacao_usos",       # Ticket 24 — audit log técnico de resoluções
    "dispensacoes_hospitalares",      # Ticket 27 — extensão hospitalar da dispensação
    "agendamentos",                   # Ticket 29 — módulo de agendamento
    "agendamento_eventos",            # Ticket 29 — ledger de agendamentos
    "eventos_publicacao",             # G4A — outbox de publicação de eventos externos
    "meta_instalacao",                # G5-impl — metadados de instalação
    "prestadores",                    # Ticket 30 — identidade formal de org_id
    "unidades",                       # Ticket 30 — unidades operacionais
    "api_keys",                       # G4B — API keys institucionais para adapters
    "circulacoes_diagnosticas",           # Ticket 52 — circulação diagnóstica
    "circulacao_diagnostica_itens",       # Ticket 52
    "circulacao_diagnostica_eventos",     # Ticket 52 — ledger de circulação diagnóstica
    "encaminhamentos",                    # TICKET-ENCAMINHAMENTO-E1
    "encaminhamento_itens",               # TICKET-ENCAMINHAMENTO-E1
    "encaminhamento_eventos",             # TICKET-ENCAMINHAMENTO-E1 — ledger
    "encaminhamento_custodia",            # TICKET-ENCAMINHAMENTO-E1 — cadeia de custódia
    "contrarreferencias",                 # TICKET-ENCAMINHAMENTO-E2 — objeto derivado
    "contrarreferencia_eventos",          # TICKET-ENCAMINHAMENTO-E2 — ledger
    "contrarreferencia_custodia",         # TICKET-ENCAMINHAMENTO-E2 — cadeia de custódia
    "atestados",                          # Atestado — objeto sanitário monolítico
    "atestado_eventos",                   # Atestado — ledger imutável
    "atestado_custodia",                  # Atestado — cadeia de custódia
    "catalogo_substancias",               # Ticket 20 — catálogo regulatório (gap
                                           # pré-existente: nunca tinha entrado aqui)
    "catalogo_regulatorio_carimbo",       # DESENHO-TALAO-DIGITAL-SNCR.md §1 (G1) —
                                           # linha única que carimba a base completa
]


# ---------------------------------------------------------------------------
# Path do SQLite — fonte ÚNICA, a mesma do engine
# ---------------------------------------------------------------------------

def _sqlite_path() -> str:
    """Path do SQLite pelo mesmo resolver que o engine do SQLAlchemy usa.

    Todo `sqlite3.connect()` deste arquivo passa por aqui. Importar
    `app.config.DB_PATH` direto ignora o redirecionamento de `PICSAUDE_DEMO_MODE`
    para `PIX_SAUDE_DEMO_DB` e faz este script operar num arquivo diferente
    daquele onde o `create_all` criou as tabelas (achado do TICKET-GATE-BROWSER:
    com `PICSAUDE_DEMO_MODE=true` os dois apontavam para ARQUIVOS DIFERENTES).
    """
    from app.database import _resolve_sqlite_db_path
    return _resolve_sqlite_db_path()


# ---------------------------------------------------------------------------
# Triggers de imutabilidade do ledger — CRIADOS PELA MIGRAÇÃO, não aqui
# ---------------------------------------------------------------------------
# TICKET-LEDGER-TRIGGERS-MIGRACAO. Este script criava os triggers via
# `sqlite3.connect()` (SQLite-only) e o PostgreSQL nunca os recebeu, porque o
# `predeploy.sh` do Render só roda `alembic upgrade head` + `seed_demo.py`.
# A autoridade de schema é a migração `f2b7c1d0a4e5_ledger_triggers_imutabilidade`;
# aqui restou apenas a CHECAGEM (passo 4 de `criar_tabelas`).
#
# O DDL canônico — e a lista de tabelas — vivem em
# `app/domain/ledger_imutabilidade.py`. Importar (em vez de manter uma segunda
# lista aqui) é o que impede a checagem de divergir silenciosamente.
#
# Esta checagem é a consumidora natural de `TABELAS_LEDGER` como lista VIVA:
# a pergunta aqui é "todo ledger que DEVE estar protegido agora está?". Se
# alguém acrescentar um ledger à lista sem escrever a migração correspondente,
# este script falha (exit 1) — que é exatamente o alarme desejado. A migração,
# ao contrário, congela a sua própria tupla: ela declara o que fez, não o que
# deveria ser feito hoje (CLAUDE.md §9).


# ---------------------------------------------------------------------------
# Helpers de inspeção do schema — SQLite e PostgreSQL
# ---------------------------------------------------------------------------

def _get_tables_sqlite() -> set[str]:
    import sqlite3

    conn = sqlite3.connect(_sqlite_path())
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        }
    finally:
        conn.close()


def _get_tables_postgres() -> set[str]:
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        return {row[0] for row in cur.fetchall()}
    finally:
        raw_conn.close()


def _get_triggers_sqlite() -> set[str]:
    import sqlite3

    conn = sqlite3.connect(_sqlite_path())
    try:
        return {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'"
            ).fetchall()
        }
    finally:
        conn.close()


def _get_triggers_postgres() -> set[str]:
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        cur.execute("""
            SELECT trigger_name FROM information_schema.triggers
            WHERE trigger_schema = 'public'
        """)
        return {row[0] for row in cur.fetchall()}
    finally:
        raw_conn.close()


def _has_column_sqlite(table: str, column: str) -> bool:
    import sqlite3

    conn = sqlite3.connect(_sqlite_path())
    try:
        return any(
            row[1] == column
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        )
    finally:
        conn.close()


def _has_column_postgres(table: str, column: str) -> bool:
    raw_conn = engine.raw_connection()
    try:
        cur = raw_conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name   = %s
              AND column_name  = %s
            """,
            (table, column),
        )
        return cur.fetchone() is not None
    finally:
        raw_conn.close()


def _has_column(table: str, column: str) -> bool:
    return _has_column_sqlite(table, column) if _USE_SQLITE else _has_column_postgres(table, column)


def _add_column_if_missing(table: str, column: str, definition: str) -> None:
    """Adiciona coluna se não existir. Idempotente."""
    if not _has_column(table, column):
        if _USE_SQLITE:
            import sqlite3

            conn = sqlite3.connect(_sqlite_path())
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                conn.commit()
            finally:
                conn.close()
        else:
            raw_conn = engine.raw_connection()
            try:
                cur = raw_conn.cursor()
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
                raw_conn.commit()
                cur.close()
            finally:
                raw_conn.close()
        print(f"  Migration aplicada: coluna {column} adicionada em {table}.")
    else:
        print(f"  Coluna {column}: ✅ presente em {table}.")


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def criar_tabelas() -> None:
    db_label = os.getenv("DATABASE_URL", "(SQLite fallback)")
    print(f"Banco de dados: {db_label}")
    print("Criando / verificando tabelas...\n")

    # 1. Criar tabelas via SQLAlchemy ORM (dialeto-agnostic)
    Base.metadata.create_all(engine)

    # 2. (vago) Os triggers de imutabilidade são criados pela migração —
    #    ver o bloco "Triggers de imutabilidade do ledger" acima. Aqui só se
    #    confere, no passo 4.

    # 3. Verificar tabelas presentes
    tabelas_existentes = _get_tables_sqlite() if _USE_SQLITE else _get_tables_postgres()

    todos_ok = True
    for t in _TABELAS_APP:
        status = "✅" if t in tabelas_existentes else "❌ AUSENTE"
        print(f"  {status}  {t}")
        if t not in tabelas_existentes:
            todos_ok = False

    print()
    if todos_ok:
        print("Todas as tabelas da aplicação estão presentes.")
    else:
        print("ATENÇÃO: tabelas ausentes. Verifique os modelos em backend/app/models/.")
        sys.exit(1)

    # 4. Verificar triggers de imutabilidade
    triggers_existentes = _get_triggers_sqlite() if _USE_SQLITE else _get_triggers_postgres()

    print("\nTriggers de imutabilidade do ledger:")
    faltando: list[str] = []
    for tabela in _TABELAS_LEDGER:
        for acao in ("update", "delete"):
            nome = f"prevent_{acao}_{tabela}"
            presente = nome in triggers_existentes
            print(f"  {'✅' if presente else '❌ AUSENTE'}  {nome}")
            if not presente:
                faltando.append(nome)

    if faltando:
        # Não é aviso cosmético: sem estes triggers o CLAUDE.md §2 ("o ledger é
        # imutável") está sustentado só por convenção de código. Quem cria é a
        # migração — e é ela que precisa rodar.
        print(
            f"\n❌ {len(faltando)} trigger(s) de imutabilidade ausente(s). "
            f"O ledger NÃO está protegido pelo banco.\n"
            f"   Rode as migrações:  cd backend && alembic upgrade head"
        )
        sys.exit(1)
    print(f"  → {len(_TABELAS_LEDGER) * 2} triggers presentes (criados pela migração).")

    # 5. Migrations de colunas (idempotentes)
    print("\nMigrations de colunas:")

    # prescricoes — colunas críticas
    for col in ("tipo_emissao", "origem_prescricao_id"):
        if not _has_column("prescricoes", col):
            print(
                f"\n  ⚠️  Coluna '{col}' ausente em prescricoes. Execute manualmente:\n"
                f"     ALTER TABLE prescricoes ADD COLUMN tipo_emissao TEXT NOT NULL DEFAULT 'nova';\n"
                f"     ALTER TABLE prescricoes ADD COLUMN origem_prescricao_id INTEGER REFERENCES prescricoes(id);"
            )
        else:
            print(f"  Coluna {col}: ✅ presente em prescricoes.")

    # Ticket 2 — documento canônico
    _add_column_if_missing("prescricoes", "assinatura_hash", "TEXT")

    # Ticket 8 — taxonomia de medicamentos
    _add_column_if_missing("prescricao_itens", "unidade_quantidade", "TEXT")
    _add_column_if_missing("prescricao_itens", "forma_farmaceutica", "TEXT")

    # Ticket 27 — contexto hospitalar em custódia
    _add_column_if_missing("prescricao_custodia", "contexto_operacional", "TEXT")
    _add_column_if_missing("prescricao_custodia", "unidade_id", "TEXT")

    # Ticket 30 / segurança prestadores
    _add_column_if_missing("dispensacoes", "origem_contexto", "TEXT")

    # Ticket 44 — circulação atomizada
    _add_column_if_missing("prescricao_itens", "classe_controle", "TEXT")

    # Ticket 67 — string de validação do prescritor
    _add_column_if_missing("prescricoes", "string_validacao_prescritor", "VARCHAR(512)")

    print("\n✅  init_tables concluído com sucesso.")


if __name__ == "__main__":
    criar_tabelas()
