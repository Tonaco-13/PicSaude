"""ledger_imutabilidade.py — DDL dos triggers que tornam o ledger imutável.

CLAUDE.md §2 afirma que as tabelas `*_eventos` nunca recebem UPDATE nem DELETE.
Até o TICKET-LEDGER-TRIGGERS-MIGRACAO essa afirmação era sustentada por DUAS
coisas frágeis:

  1. disciplina de código (nenhum UPDATE/DELETE em `backend/app/`), e
  2. triggers criados EXCLUSIVAMENTE por `init_tables.py`, em código
     `sqlite3.connect()` — SQLite-only.

O `predeploy.sh` do Render roda `alembic upgrade head` + `seed_demo.py` e NUNCA
chama `init_tables.py`. Consequência medida: em PostgreSQL os triggers nunca
existiram, e não poderiam existir — o caminho que os criava era SQLite-only.

Este módulo é a **fonte única** do DDL. Quem o APLICA é a migração
(`f2b7c1d0a4e5_ledger_triggers_imutabilidade`), que é a autoridade de schema:
é ela que roda em produção. `init_tables.py` não cria mais trigger nenhum —
apenas verifica que existem (bootstrap/checagem).

Por que a migração importa código de app
----------------------------------------
Migração idealmente é um retrato congelado do schema, e importar app faz o
passado mudar quando o módulo muda. Aceito conscientemente aqui porque a
alternativa é duplicar o DDL entre migração, `init_tables.py` e a fixture de
teste — exatamente a duplicação que criou o defeito. A lista de tabelas é
aditiva por natureza (ledger novo = trigger novo) e a semântica é fixa: recusar
toda mutação. `alembic/env.py` já insere `backend/` no `sys.path` e já importa
`app.models`, então o import é seguro no contexto de migração.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Tabelas de ledger protegidas. Todo novo objeto sanitário com `*_eventos`
# entra aqui E ganha uma migração que cria seus dois triggers.
# ---------------------------------------------------------------------------

TABELAS_LEDGER: tuple[str, ...] = (
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "agendamento_eventos",
    "circulacao_diagnostica_eventos",
    "encaminhamento_eventos",
    "atestado_eventos",
)

# Nome da função PL/pgSQL compartilhada pelos triggers no PostgreSQL.
FUNCAO_PG = "picsaude_prevent_ledger_mutation"


def nome_trigger(acao: str, tabela: str) -> str:
    """`prevent_update_prescricao_eventos`, `prevent_delete_laudo_eventos`, …"""
    return f"prevent_{acao.lower()}_{tabela}"


def mensagem(acao: str, tabela: str) -> str:
    """Mensagem de recusa — IDÊNTICA em SQLite e PostgreSQL.

    Há teste que casa este texto. Mudá-lo é mudança de contrato observável:
    quem depura uma escrita recusada em produção (PG) tem que ver exatamente a
    mesma frase que vê em dev (SQLite).
    """
    return f"Ledger imutável: {acao.upper()} não permitido em {tabela}"


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def sql_criar_sqlite() -> list[str]:
    """DDL idempotente (`IF NOT EXISTS`) dos 14 triggers no SQLite."""
    comandos: list[str] = []
    for tabela in TABELAS_LEDGER:
        for acao in ("UPDATE", "DELETE"):
            comandos.append(
                f"CREATE TRIGGER IF NOT EXISTS {nome_trigger(acao, tabela)}\n"
                f"BEFORE {acao} ON {tabela}\n"
                f"BEGIN\n"
                f"    SELECT RAISE(FAIL, '{mensagem(acao, tabela)}');\n"
                f"END"
            )
    return comandos


def sql_remover_sqlite() -> list[str]:
    return [
        f"DROP TRIGGER IF EXISTS {nome_trigger(acao, tabela)}"
        for tabela in TABELAS_LEDGER
        for acao in ("UPDATE", "DELETE")
    ]


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
# `RAISE(FAIL, ...)` não existe no PostgreSQL: a recusa vem de uma função
# PL/pgSQL com RAISE EXCEPTION, compartilhada pelos 14 triggers. A mensagem é
# montada com TG_OP/TG_TABLE_NAME para reproduzir, caractere a caractere, o
# texto do SQLite.

def sql_criar_postgres() -> list[str]:
    """DDL idempotente (DROP + CREATE) da função e dos 14 triggers no PG."""
    comandos: list[str] = [
        f"""
        CREATE OR REPLACE FUNCTION {FUNCAO_PG}()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'Ledger imutável: % não permitido em %',
                TG_OP, TG_TABLE_NAME;
        END;
        $$
        """
    ]
    for tabela in TABELAS_LEDGER:
        for acao in ("UPDATE", "DELETE"):
            nome = nome_trigger(acao, tabela)
            # DROP + CREATE em vez de CREATE OR REPLACE TRIGGER: este último só
            # existe no PG 14+, e o alvo declarado do projeto é PostgreSQL 15+
            # em prod mas 13 ainda aparece em instalações locais.
            comandos.append(f"DROP TRIGGER IF EXISTS {nome} ON {tabela}")
            comandos.append(
                f"CREATE TRIGGER {nome}\n"
                f"BEFORE {acao} ON {tabela}\n"
                f"FOR EACH ROW EXECUTE FUNCTION {FUNCAO_PG}()"
            )
    return comandos


def sql_remover_postgres() -> list[str]:
    comandos = [
        f"DROP TRIGGER IF EXISTS {nome_trigger(acao, tabela)} ON {tabela}"
        for tabela in TABELAS_LEDGER
        for acao in ("UPDATE", "DELETE")
    ]
    comandos.append(f"DROP FUNCTION IF EXISTS {FUNCAO_PG}()")
    return comandos


# ---------------------------------------------------------------------------
# Seleção por dialeto
# ---------------------------------------------------------------------------

def aplicar_triggers_sqlite(db_path: str) -> None:
    """Aplica os triggers num SQLite específico. Uso restrito: fixtures de teste.

    A fixture `db_path` monta o schema com `Base.metadata.create_all` — caminho
    paralelo ao Alembic, que não passa pela migração e portanto não ganharia os
    triggers. Esta função existe para essa fixture não ficar com um ledger
    desprotegido, aplicando o MESMO DDL da migração.

    Produção e demo NÃO passam por aqui: quem cria os triggers é
    `alembic upgrade head`. Ver `test_ledger_imutabilidade.py`, que valida a
    migração de verdade em SQLite e PostgreSQL.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        for comando in sql_criar_sqlite():
            conn.execute(comando)
        conn.commit()
    finally:
        conn.close()


def sql_criar(dialeto: str) -> list[str]:
    return sql_criar_postgres() if dialeto == "postgresql" else sql_criar_sqlite()


def sql_remover(dialeto: str) -> list[str]:
    return sql_remover_postgres() if dialeto == "postgresql" else sql_remover_sqlite()
