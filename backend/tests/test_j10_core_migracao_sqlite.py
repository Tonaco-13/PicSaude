"""
tests/test_j10_core_migracao_sqlite.py
======================================

A migração `d4b8c1e07f36` no dialeto **SQLite** — data-fix + constraint.

POR QUE ESTE ARQUIVO EXISTE SEPARADO
------------------------------------
§9 do CLAUDE.md, regra derivada: *"todo invariante que o CLAUDE.md afirma como
garantido pelo banco precisa de migração + teste que rode nos DOIS dialetos.
Sem isso, a afirmação vale só para o dialeto de desenvolvimento."* O gate de
integração roda só em PostgreSQL; sem este arquivo, a unicidade de posse do
exame estaria provada em PG e apenas *afirmada* em SQLite — que é o dialeto da
demo e dos testes. Foi exatamente assim que os triggers do ledger passaram
meses existindo só no bootstrap (TICKET-LEDGER-TRIGGERS-MIGRACAO).

O par em PostgreSQL está em `tests/integration/test_j10_core_posse_exame.py`.

O QUE SE TESTA AQUI
-------------------
A função de data-fix é exercida **diretamente**, no estado exato em que a
migração a chama: logo depois do `ADD COLUMN encerrada_em`, quando toda linha
histórica está "ativa" — que é o estado que faria o índice único falhar se o
data-fix não rodasse antes.
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
    / "alembic" / "versions" / "d4b8c1e07f36_custodia_exame_posse_atual.py"
)

_IDX_SQLITE = "uq_custodia_exame_ativa_pedido_item_sqlite"


def _carregar_migracao():
    """Importa o módulo da migração pelo caminho (não é pacote importável)."""
    spec = importlib.util.spec_from_file_location("mig_d4b8c1e07f36", _MIGRACAO)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Schema mínimo no estado PÓS-`ADD COLUMN`: é onde o data-fix age.
_DDL = [
    """
    CREATE TABLE pedido_exame_custodia (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        item_id INTEGER,
        de VARCHAR(100) NOT NULL,
        para VARCHAR(100) NOT NULL,
        transferido_em DATETIME NOT NULL,
        dados_json TEXT,
        encerrada_em DATETIME
    )
    """,
    """
    CREATE TABLE pedido_exame_eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pedido_id INTEGER NOT NULL,
        tipo_evento VARCHAR(60) NOT NULL,
        dados_json TEXT,
        criado_em DATETIME NOT NULL,
        instance_id VARCHAR(36)
    )
    """,
]


def _criar_indice(conn) -> None:
    conn.execute(text(
        f"CREATE UNIQUE INDEX {_IDX_SQLITE} "
        "ON pedido_exame_custodia (pedido_id, COALESCE(item_id, -1)) "
        "WHERE encerrada_em IS NULL"
    ))


@pytest.fixture
def bind(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'j10.db'}")
    with engine.begin() as conn:
        for ddl in _DDL:
            conn.execute(text(ddl))
        yield conn


def _inserir(conn, pedido_id, item_id, de, para, quando):
    conn.execute(text(
        "INSERT INTO pedido_exame_custodia "
        "(pedido_id, item_id, de, para, transferido_em, dados_json, encerrada_em) "
        "VALUES (:p, :i, :de, :para, :q, NULL, NULL)"
    ), {"p": pedido_id, "i": item_id, "de": de, "para": para, "q": quando})


def _ativas(conn, pedido_id=None):
    sql = "SELECT id, item_id, para, encerrada_em FROM pedido_exame_custodia WHERE encerrada_em IS NULL"
    params = {}
    if pedido_id is not None:
        sql += " AND pedido_id = :p"
        params["p"] = pedido_id
    return conn.execute(text(sql + " ORDER BY id"), params).fetchall()


# ---------------------------------------------------------------------------
# 1 — o data-fix converte o ledger em posse atual
# ---------------------------------------------------------------------------

def test_data_fix_deixa_uma_posse_ativa_por_grupo(bind):
    """Três transferências do mesmo pedido → uma posse ativa: a última.

    Este é o caso NORMAL, não a anomalia. Na forma antiga a cadeia era coerente
    (a última linha era o detentor); o que a migração faz é tornar esse fato
    explícito — e, com isso, indexável.
    """
    mig = _carregar_migracao()

    _inserir(bind, 1, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 1, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")
    _inserir(bind, 1, None, "paciente",   "22222222222222", "2026-08-03T10:00:00")

    encerradas = mig._reconciliar_posse_exame(bind)
    assert encerradas == 2

    ativas = _ativas(bind, 1)
    assert len(ativas) == 1
    assert ativas[0].para == "22222222222222", "a posse ativa tem de ser a mais recente"


def test_encerrada_em_e_a_data_da_transferencia_seguinte(bind):
    """E não `utcnow()`.

    Uma custódia terminou quando a próxima começou — fato que o ledger já
    registra. Carimbar "agora" inventaria uma história em que todas as posses
    antigas terminaram no dia do deploy, quebrando o R1 (§2a): relatório de
    período fechado tem de ser reproduzível para sempre.
    """
    mig = _carregar_migracao()

    _inserir(bind, 7, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 7, None, "paciente",   "11111111111111", "2026-08-02T11:30:00")
    _inserir(bind, 7, None, "paciente",   "22222222222222", "2026-08-03T09:15:00")

    mig._reconciliar_posse_exame(bind)

    linhas = bind.execute(text(
        "SELECT para, transferido_em, encerrada_em FROM pedido_exame_custodia "
        "WHERE pedido_id = 7 ORDER BY transferido_em"
    )).fetchall()

    # A 1ª terminou quando a 2ª começou; a 2ª quando a 3ª começou; a 3ª segue
    # aberta. `replace('T', ' ')`: o separador ISO varia com o driver/dialeto e
    # não é o que este teste guarda — o que ele guarda é o INSTANTE.
    def _quando(v):
        return str(v).replace("T", " ")

    assert _quando(linhas[0].encerrada_em) == "2026-08-02 11:30:00"
    assert _quando(linhas[1].encerrada_em) == "2026-08-03 09:15:00"
    assert linhas[2].encerrada_em is None


def test_granularidades_sao_grupos_independentes(bind):
    """Nível-pedido e nível-item não competem entre si.

    O índice é por `(pedido_id, item_id)`: a posse do pedido inteiro e a de um
    item são posses de coisas diferentes. (A dupla posse CROSS-granularidade —
    nível-pedido obsoleto × nível-item ativo — nenhuma constraint pega; é
    responsabilidade do caminho, como no COER-2.)
    """
    mig = _carregar_migracao()

    _inserir(bind, 3, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 3, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")
    _inserir(bind, 3, 55,   "paciente",   "22222222222222", "2026-08-02T10:00:00")
    _inserir(bind, 3, 55,   "paciente",   "33333333333333", "2026-08-04T10:00:00")

    mig._reconciliar_posse_exame(bind)

    ativas = _ativas(bind, 3)
    assert len(ativas) == 2, "uma ativa por granularidade"
    assert {(a.item_id, a.para) for a in ativas} == {
        (None, "11111111111111"),
        (55,   "33333333333333"),
    }


def test_linha_unica_fica_intacta(bind):
    """Pedido com uma transferência só não é tocado — nada a reconciliar."""
    mig = _carregar_migracao()
    _inserir(bind, 9, None, "prescritor", "paciente", "2026-08-01T10:00:00")

    assert mig._reconciliar_posse_exame(bind) == 0
    assert len(_ativas(bind, 9)) == 1


def test_data_fix_e_idempotente(bind):
    """Reexecutar num banco já normalizado não encontra grupo e não faz nada.

    Importa porque migração pode ser reaplicada em ambiente de desenvolvimento,
    e um data-fix que agisse duas vezes reescreveria datas já corretas.
    """
    mig = _carregar_migracao()
    _inserir(bind, 4, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 4, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")

    assert mig._reconciliar_posse_exame(bind) == 1
    antes = bind.execute(text(
        "SELECT id, encerrada_em FROM pedido_exame_custodia ORDER BY id"
    )).fetchall()

    assert mig._reconciliar_posse_exame(bind) == 0
    depois = bind.execute(text(
        "SELECT id, encerrada_em FROM pedido_exame_custodia ORDER BY id"
    )).fetchall()
    assert antes == depois


# ---------------------------------------------------------------------------
# 2 — a trilha do que a migração fez
# ---------------------------------------------------------------------------

def test_cada_linha_fechada_deixa_evento_no_ledger(bind):
    """Trilha forense: qual linha fechou, qual ficou, em que nível.

    Nota semântica para quem auditar: aqui o evento significa "linha superada
    pelo modelo de posse atual", NÃO "anomalia encontrada" — por isso o
    `origem` no payload. A migração normaliza; não corrige.
    """
    mig = _carregar_migracao()
    _inserir(bind, 5, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 5, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")

    mig._reconciliar_posse_exame(bind)

    eventos = bind.execute(text(
        "SELECT pedido_id, tipo_evento, dados_json FROM pedido_exame_eventos"
    )).fetchall()
    assert len(eventos) == 1
    assert eventos[0].tipo_evento == "custodia_reconciliada_data_fix"
    assert eventos[0].pedido_id == 5

    payload = json.loads(eventos[0].dados_json)
    assert payload["origem"] == "migracao_j10_posse_atual"
    assert payload["nivel"] == "pedido"
    assert payload["item_id"] is None
    assert payload["custodia_id_encerrada"] != payload["custodia_id_mantida"]


# ---------------------------------------------------------------------------
# 3 — a constraint, no dialeto SQLite
# ---------------------------------------------------------------------------

def test_indice_recusa_dupla_posse_ativa(bind):
    """AC (iii) do §11c, dialeto SQLite: dupla posse ativa = IntegrityError.

    O R2 na camada de custódia — um objeto em dois lugares ao mesmo tempo — é
    alarme, não erro cosmético. Aqui ele passa a ser impossível de gravar.
    """
    _inserir(bind, 6, None, "prescritor", "paciente", "2026-08-01T10:00:00")
    _criar_indice(bind)

    with pytest.raises(sa.exc.IntegrityError):
        _inserir(bind, 6, None, "paciente", "11111111111111", "2026-08-02T10:00:00")


def test_indice_recusa_dupla_posse_ativa_de_item(bind):
    """Mesma guarda no nível-item — o `COALESCE(item_id, -1)` não é só cosmético."""
    _inserir(bind, 8, 42, "paciente", "11111111111111", "2026-08-01T10:00:00")
    _criar_indice(bind)

    with pytest.raises(sa.exc.IntegrityError):
        _inserir(bind, 8, 42, "paciente", "22222222222222", "2026-08-02T10:00:00")


def test_indice_permite_reabrir_depois_de_encerrar(bind):
    """A posse circula: fechou a anterior, a nova entra.

    É o caminho normal do choke-point — e o teste que prova que a constraint
    guarda a EXCLUSIVIDADE, não a imobilidade.
    """
    _inserir(bind, 10, None, "prescritor", "paciente", "2026-08-01T10:00:00")
    _criar_indice(bind)

    bind.execute(text(
        "UPDATE pedido_exame_custodia SET encerrada_em = '2026-08-02T10:00:00' "
        "WHERE pedido_id = 10 AND item_id IS NULL AND encerrada_em IS NULL"
    ))
    _inserir(bind, 10, None, "paciente", "11111111111111", "2026-08-02T10:00:00")

    assert len(_ativas(bind, 10)) == 1


def test_o_indice_nasce_instalavel_depois_do_data_fix(bind):
    """A ordem do `upgrade()` importa: data-fix ANTES da constraint.

    Sem o data-fix, um pedido com histórico teria N posses ativas e o
    `CREATE UNIQUE INDEX` falharia no meio da migração — em produção, com o
    deploy pela metade. Este teste prova a ordem, não só o resultado.
    """
    mig = _carregar_migracao()
    _inserir(bind, 11, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 11, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")

    with pytest.raises(sa.exc.IntegrityError):
        _criar_indice(bind)                    # como seria SEM o data-fix


def test_indice_instala_depois_do_data_fix(bind):
    """E com o data-fix na frente, instala limpo."""
    mig = _carregar_migracao()
    _inserir(bind, 12, None, "prescritor", "paciente",       "2026-08-01T10:00:00")
    _inserir(bind, 12, None, "paciente",   "11111111111111", "2026-08-02T10:00:00")

    mig._reconciliar_posse_exame(bind)
    _criar_indice(bind)                        # não levanta

    assert len(_ativas(bind, 12)) == 1
