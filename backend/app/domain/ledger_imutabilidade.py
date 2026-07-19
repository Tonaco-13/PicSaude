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

Por que a migração importa código de app — e o que ela NÃO importa
------------------------------------------------------------------
A migração importa daqui o **construtor de DDL** (`sql_criar`/`sql_remover`):
o "como" se escreve um trigger de imutabilidade. Duplicar esse DDL entre
migração, `init_tables.py` e fixture de teste é exatamente a duplicação que
criou o defeito original. `alembic/env.py` já insere `backend/` no `sys.path` e
já importa `app.models`, então o import é seguro no contexto de migração.

O que a migração NÃO importa é a LISTA de tabelas — o "quê". `TABELAS_LEDGER` é
uma lista VIVA: descreve quais ledgers devem estar protegidos AGORA. Se a
migração a lesse, o efeito dela mudaria conforme a lista crescesse: um banco
migrado hoje ficaria com 16 triggers, e um banco criado do zero depois da 9ª
tabela ficaria com 18 — dois bancos no mesmo `alembic head` com schemas
diferentes, que é o próprio defeito que este ticket conserta. Por isso cada
migração carrega a TUPLA LITERAL das tabelas sobre as quais agiu.

É o mesmo princípio do R4 (CLAUDE.md §2a): congela-se o grupo POR VALOR no ato
do movimento, para que mudar a regra amanhã não altere o movimento de ontem.
Ledger × projeção: `TABELAS_LEDGER` é o presente, a migração é o passado —
nenhuma das duas está errada, elas só não podem ser o mesmo objeto.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Tabelas de ledger protegidas — fonte do PRESENTE.
#
# Quem consome esta lista: `init_tables.py` (checagem de ambiente: "todo ledger
# desta lista tem seus dois triggers?") e os testes. Migração NÃO consome —
# migração declara sobre o que agiu, com tupla literal própria (CLAUDE.md §9).
#
# Todo novo objeto sanitário com `*_eventos` entra aqui E ganha uma migração
# NOVA que cria seus dois triggers. Nunca editar a migração anterior.
# ---------------------------------------------------------------------------

TABELAS_LEDGER: tuple[str, ...] = (
    "prescricao_eventos",
    "pedido_exame_eventos",
    "laudo_eventos",
    "agendamento_eventos",
    "circulacao_diagnostica_eventos",
    "encaminhamento_eventos",
    "contrarreferencia_eventos",
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
# Construtores de DDL
# ---------------------------------------------------------------------------
# `tabelas` é OBRIGATÓRIO e SEM DEFAULT em todos eles — de propósito.
#
# Um default `tabelas=TABELAS_LEDGER` faria a lista viva voltar pela porta dos
# fundos: o próximo chamador distraído omitiria o parâmetro e reintroduziria a
# resolução-na-leitura numa migração. Quem chama tem que DIZER sobre o que está
# agindo. Chamada sem `tabelas` é TypeError, e há teste que o exige.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------

def sql_criar_sqlite(tabelas: tuple[str, ...]) -> list[str]:
    """DDL idempotente (`IF NOT EXISTS`) dos 2×N triggers no SQLite."""
    comandos: list[str] = []
    for tabela in tabelas:
        for acao in ("UPDATE", "DELETE"):
            comandos.append(
                f"CREATE TRIGGER IF NOT EXISTS {nome_trigger(acao, tabela)}\n"
                f"BEFORE {acao} ON {tabela}\n"
                f"BEGIN\n"
                f"    SELECT RAISE(FAIL, '{mensagem(acao, tabela)}');\n"
                f"END"
            )
    return comandos


def sql_remover_sqlite(tabelas: tuple[str, ...]) -> list[str]:
    return [
        f"DROP TRIGGER IF EXISTS {nome_trigger(acao, tabela)}"
        for tabela in tabelas
        for acao in ("UPDATE", "DELETE")
    ]


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
# `RAISE(FAIL, ...)` não existe no PostgreSQL: a recusa vem de uma função
# PL/pgSQL com RAISE EXCEPTION, compartilhada por todos os triggers. A mensagem
# é montada com TG_OP/TG_TABLE_NAME para reproduzir, caractere a caractere, o
# texto do SQLite.

def sql_criar_postgres(tabelas: tuple[str, ...]) -> list[str]:
    """DDL idempotente (DROP + CREATE) da função e dos 2×N triggers no PG."""
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
    for tabela in tabelas:
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


def sql_remover_postgres(tabelas: tuple[str, ...]) -> list[str]:
    comandos = [
        f"DROP TRIGGER IF EXISTS {nome_trigger(acao, tabela)} ON {tabela}"
        for tabela in tabelas
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
        # Fixture é PRESENTE, não passado: protege todo ledger que deve estar
        # protegido agora. Por isso aqui `TABELAS_LEDGER` é a fonte correta —
        # ao contrário da migração, que congela a sua própria lista.
        for comando in sql_criar_sqlite(TABELAS_LEDGER):
            conn.execute(comando)
        conn.commit()
    finally:
        conn.close()


def sql_criar(dialeto: str, tabelas: tuple[str, ...]) -> list[str]:
    """DDL de criação para `tabelas`, no dialeto pedido. Ver nota sobre o
    parâmetro obrigatório em "Construtores de DDL", acima."""
    return (
        sql_criar_postgres(tabelas) if dialeto == "postgresql"
        else sql_criar_sqlite(tabelas)
    )


def sql_remover(dialeto: str, tabelas: tuple[str, ...]) -> list[str]:
    return (
        sql_remover_postgres(tabelas) if dialeto == "postgresql"
        else sql_remover_sqlite(tabelas)
    )
