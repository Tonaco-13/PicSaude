"""
tests/test_eng016_posse_unica_sqlite.py
=======================================

A migração `a1c9e4d70b26` (ENG-016 §6) no dialeto **SQLite** — data-fix + índice.

POR QUE ESTE ARQUIVO EXISTE SEPARADO
------------------------------------
§9 do CLAUDE.md, regra derivada: *"todo invariante que o CLAUDE.md afirma como
garantido pelo banco precisa de migração + teste que rode nos DOIS dialetos.
Sem isso, a afirmação vale só para o dialeto de desenvolvimento."* O gate de
integração roda só em PostgreSQL; sem este arquivo, a unicidade de posse da
terceira circulação estaria provada em PG e apenas *afirmada* em SQLite — que é
o dialeto da demo e do desenvolvimento. Foi exatamente assim que os triggers do
ledger passaram meses existindo só no bootstrap
(TICKET-LEDGER-TRIGGERS-MIGRACAO).

O par em PostgreSQL está em
`tests/integration/test_eng016_posse_unica_encaminhamento.py`.

O QUE SE TESTA AQUI
-------------------
1. O **índice em SQLite** morde — e morde no nível-OBJETO, que é o único que
   estas tabelas usam hoje. A expressão `COALESCE(item_id, -1)` é o que faz
   isso funcionar sem `NULLS NOT DISTINCT` (que o SQLite não tem): sem ela,
   dois `(obj, NULL)` não colidiriam e o índice seria decorativo.
2. A função de **data-fix** é exercida DIRETAMENTE, no estado em que a migração
   a chama — com dupla posse já plantada. É o estado que faria o
   `CREATE UNIQUE INDEX` estourar se o data-fix não rodasse antes, e é por isso
   que a ordem dentro do `upgrade()` não é preferência de estilo.
3. O data-fix é **idempotente**: reexecutar num banco já coerente não encontra
   grupo e não escreve nada.
4. A **tupla congelada** (`_ALVOS`) declara as duas tabelas por valor — §9, "a
   migração declara sobre o que agiu". Se alguém trocá-la por leitura de lista
   viva, este teste acusa.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import text

_MIGRACAO = (
    Path(__file__).resolve().parent.parent
    / "alembic" / "versions" / "a1c9e4d70b26_posse_unica_encaminhamento_cr.py"
)


def _carregar_migracao():
    """Importa o módulo da migração pelo caminho (não é pacote importável)."""
    spec = importlib.util.spec_from_file_location("mig_a1c9e4d70b26", _MIGRACAO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Schema mínimo das duas tabelas de custódia + os dois ledgers.
_DDL = [
    """
    CREATE TABLE encaminhamento_custodia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encaminhamento_id INTEGER NOT NULL,
        item_id INTEGER,
        detentor_tipo VARCHAR(40) NOT NULL,
        detentor_id VARCHAR(100) NOT NULL,
        transferida_em VARCHAR(40) NOT NULL,
        encerrada_em VARCHAR(40),
        motivo VARCHAR(120),
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE contrarreferencia_custodia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrarreferencia_id INTEGER NOT NULL,
        item_id INTEGER,
        detentor_tipo VARCHAR(40) NOT NULL,
        detentor_id VARCHAR(100) NOT NULL,
        transferida_em VARCHAR(40) NOT NULL,
        encerrada_em VARCHAR(40),
        motivo VARCHAR(120),
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE encaminhamento_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        encaminhamento_id INTEGER NOT NULL,
        tipo_evento VARCHAR(80) NOT NULL,
        ator_tipo VARCHAR(40) NOT NULL,
        ator_id VARCHAR(100),
        payload TEXT,
        instance_id VARCHAR(36),
        created_at DATETIME NOT NULL
    )
    """,
    """
    CREATE TABLE contrarreferencia_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contrarreferencia_id INTEGER NOT NULL,
        tipo_evento VARCHAR(80) NOT NULL,
        ator_tipo VARCHAR(40) NOT NULL,
        ator_id VARCHAR(100),
        payload TEXT,
        instance_id VARCHAR(36),
        created_at DATETIME NOT NULL
    )
    """,
]


@pytest.fixture
def bind(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'eng016.db'}")
    with engine.begin() as conn:
        for ddl in _DDL:
            conn.execute(text(ddl))
        yield conn


def _inserir(conn, tabela, coluna, obj_id, detentor, quando, item_id=None):
    conn.execute(text(
        f"INSERT INTO {tabela} "
        f"({coluna}, item_id, detentor_tipo, detentor_id, transferida_em, "
        " encerrada_em, motivo, created_at) "
        "VALUES (:o, :i, 'prescritor', :d, :q, NULL, 'teste', :q)"
    ), {"o": obj_id, "i": item_id, "d": detentor, "q": quando})


def _ativas(conn, tabela, coluna, obj_id):
    return conn.execute(text(
        f"SELECT id, detentor_id FROM {tabela} "
        f" WHERE {coluna} = :o AND encerrada_em IS NULL ORDER BY id"
    ), {"o": obj_id}).fetchall()


def _criar_indice(conn, tabela, coluna, nome):
    conn.execute(text(
        f"CREATE UNIQUE INDEX {nome} ON {tabela} "
        f"({coluna}, COALESCE(item_id, -1)) WHERE encerrada_em IS NULL"
    ))


_TABELAS = [
    ("encaminhamento_custodia", "encaminhamento_id", "encaminhamento_eventos"),
    ("contrarreferencia_custodia", "contrarreferencia_id", "contrarreferencia_eventos"),
]


# ---------------------------------------------------------------------------
# 1 — o índice morde em SQLite, nas duas tabelas
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tabela,coluna,_ev", _TABELAS)
def test_indice_recusa_dupla_posse_ativa(bind, tabela, coluna, _ev):
    """`COALESCE(item_id, -1)` é o que faz a guarda valer no nível-objeto.

    Sem ela, dois `(obj, NULL)` não colidem no SQLite (não há
    `NULLS NOT DISTINCT`) e o índice não guardaria nada — pior que ausente,
    porque pareceria presente.
    """
    _criar_indice(bind, tabela, coluna, f"uq_{tabela}_teste")
    _inserir(bind, tabela, coluna, 1, "700000000000001", "t1")
    with pytest.raises(sa.exc.IntegrityError):
        _inserir(bind, tabela, coluna, 1, "700000000000002", "t2")


@pytest.mark.parametrize("tabela,coluna,_ev", _TABELAS)
def test_indice_permite_encerrada_com_ativa(bind, tabela, coluna, _ev):
    """Exclusividade, não imobilidade — o índice é PARCIAL por isso."""
    _criar_indice(bind, tabela, coluna, f"uq_{tabela}_teste")
    _inserir(bind, tabela, coluna, 1, "700000000000001", "t1")
    bind.execute(text(
        f"UPDATE {tabela} SET encerrada_em = 'fim' WHERE {coluna} = 1"))
    _inserir(bind, tabela, coluna, 1, "700000000000002", "t2")
    assert len(_ativas(bind, tabela, coluna, 1)) == 1


# ---------------------------------------------------------------------------
# 2 — o data-fix, no estado exato em que a migração o chama
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tabela,coluna,eventos", _TABELAS)
def test_data_fix_reconcilia_e_deixa_a_mais_recente(bind, tabela, coluna, eventos):
    """Régua de corte do COER-2: mantém a mais recente por (created_at, id).

    A dupla posse não deveria existir pelos caminhos de hoje — mas "não
    deveria" é a frase que o COER-2 existe para não aceitar. Aqui ela é
    PLANTADA, para provar que a migração sobrevive a um banco que a tenha.
    """
    mig = _carregar_migracao()
    _inserir(bind, tabela, coluna, 7, "AAA", "2026-01-01")
    _inserir(bind, tabela, coluna, 7, "BBB", "2026-02-01")
    _inserir(bind, tabela, coluna, 7, "CCC", "2026-03-01")
    assert len(_ativas(bind, tabela, coluna, 7)) == 3

    encerradas = mig._reconciliar(bind, tabela, coluna, eventos)

    assert encerradas == 2
    ativas = _ativas(bind, tabela, coluna, 7)
    assert len(ativas) == 1
    assert ativas[0][1] == "CCC", "manteve a mais recente"

    # Depois do data-fix o índice ENTRA — que é a ordem do `upgrade()`.
    _criar_indice(bind, tabela, coluna, f"uq_{tabela}_teste")


@pytest.mark.parametrize("tabela,coluna,eventos", _TABELAS)
def test_data_fix_registra_no_ledger_com_origem_propria(bind, tabela, coluna, eventos):
    """A reconciliação é fato de negócio: entra no ledger como INSERT (§2).

    O `origem` distingue este data-fix dos homônimos — o mesmo nome de evento
    já tem sentidos próprios no ledger da receita e no do exame (CLAUDE.md §2).
    """
    mig = _carregar_migracao()
    _inserir(bind, tabela, coluna, 9, "AAA", "2026-01-01")
    _inserir(bind, tabela, coluna, 9, "BBB", "2026-02-01")
    mig._reconciliar(bind, tabela, coluna, eventos)

    linhas = bind.execute(text(
        f"SELECT tipo_evento, ator_tipo, payload, instance_id FROM {eventos}"
    )).fetchall()
    assert len(linhas) == 1
    tipo, ator, payload, instance_id = linhas[0]
    assert tipo == "custodia_reconciliada_data_fix"
    assert ator == "sistema"
    assert instance_id is None, "registro de migração não leva marca d'água de instalação"
    dados = json.loads(payload)
    assert dados["origem"] == "migracao_eng016_posse_unica"
    assert dados["nivel"] == "objeto"
    assert dados["detentor_id"] == "AAA", "encerrou a mais antiga"


@pytest.mark.parametrize("tabela,coluna,eventos", _TABELAS)
def test_data_fix_e_idempotente(bind, tabela, coluna, eventos):
    """Banco já coerente: não acha grupo, não escreve nada."""
    mig = _carregar_migracao()
    _inserir(bind, tabela, coluna, 3, "AAA", "2026-01-01")
    assert mig._reconciliar(bind, tabela, coluna, eventos) == 0
    assert mig._reconciliar(bind, tabela, coluna, eventos) == 0
    assert bind.execute(text(f"SELECT count(*) FROM {eventos}")).scalar() == 0


# ---------------------------------------------------------------------------
# 3 — a tupla congelada (§9: a migração declara sobre o que agiu)
# ---------------------------------------------------------------------------

def test_a_migracao_declara_suas_tabelas_por_valor():
    """Lista viva resolvida na leitura faria dois bancos no mesmo `head`
    divergirem conforme QUANDO rodassem — o defeito que o §9 existe para
    prevenir, reintroduzido pela porta dos fundos."""
    mig = _carregar_migracao()
    tabelas = {alvo[0] for alvo in mig._ALVOS}
    assert tabelas == {"encaminhamento_custodia", "contrarreferencia_custodia"}, (
        f"a tupla congelada da migração mudou: {tabelas}"
    )
    fonte = _MIGRACAO.read_text(encoding="utf-8")
    assert "TABELAS_LEDGER" not in fonte, (
        "a migração passou a ler a lista VIVA — §9: ela declara o que agiu, por valor"
    )
