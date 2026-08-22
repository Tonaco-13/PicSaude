"""Guarda dos objetos-demo do seed — variante do "verde e não gateado apodrece".

O DEFEITO QUE ESTE ARQUIVO IMPEDE DE RENASCER
---------------------------------------------
Na vitrine resetada em 20/08 o `seed_demo` abortou o **laudo-demo** com

    duplicate key value violates unique constraint
    "uq_custodia_exame_ativa_pedido_item_pg"
    Key (pedido_id, item_id)=(2, null) already exists

O caminho abria uma SEGUNDA custódia de nível-pedido sem fechar a primeira, por
`INSERT` à mão. Enquanto a posse era "a última linha" isso passava; com o índice
único parcial (migração `d4b8c1e07f36`) virou o que sempre foi — dupla posse
ativa — e a PG recusou.

**Mas o seed continuou verde.** Os blocos de objetos-demo são best-effort
(`try/except` + `rollback` + aviso), por decisão: uma falha ali não pode
derrubar o deploy. O efeito colateral é que o seed sai `0` **sem o objeto**, e
ninguém fica sabendo até alguém abrir a vitrine e não achar o laudo.

Best-effort no DEPLOY é resiliência; best-effort no GATE é cegueira. Este
arquivo põe a conferência onde ela pode falhar sem custo: no CI.

O QUE ESTE ARQUIVO PROVA
------------------------
1. Depois da receita do `predeploy.sh`, os objetos-demo EXISTEM — pedido ativo,
   pedido com resultado, e o laudo liberado.
2. A cadeia de custódia do exame respeita a **posse única**: no máximo uma linha
   ATIVA por `(pedido_id, item_id)` — o invariante que o índice garante na PG e
   que aqui é conferido também no SQLite (§9 do CLAUDE.md: os dois dialetos).
3. A **proveniência** ficou inteira: o pedido do laudo tem o elo de origem
   (prescritor → paciente) ENCERRADO e a posse do laboratório ATIVA.
4. Re-semear não duplica nem quebra o invariante (o deploy re-roda o seed a cada
   push).
5. Vermelho-antes-de-verde: `TestAGuardaMorde` prova que a asserção de posse
   única acusa uma dupla posse injetada.

A receita é a do `predeploy.sh` — `alembic upgrade head` + `seed_demo.py` — em
SQLite efêmero, como em `test_seed_catalogo_dcb.py`. As MESMAS conferências
rodam na PG, no smoke do `gates.yml`, que é o dialeto onde o erro doeu.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

_PEDIDO_ATIVO = "DEMO-EXAME-0001"
_PEDIDO_LAUDO = "DEMO-EXAME-0002"
_LAUDO = "DEMO-LAUDO-0001"


def _env_demo(demo_db: Path) -> dict:
    env = {
        **os.environ,
        "PICSAUDE_DEMO_MODE": "true",
        "PICSAUDE_ENV": "stg",          # != prod (seed_demo aborta em prod)
        "PIX_SAUDE_DEMO_DB": str(demo_db),
    }
    env.pop("DATABASE_URL", None)       # força o ramo SQLite mesmo no gate de PG
    return env


def _rodar(passo: str, args: list[str], env: dict) -> str:
    proc = subprocess.run(args, cwd=str(_BACKEND_ROOT), env=env,
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, (
        f"{passo} falhou (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )
    return proc.stdout


def _semear(demo_db: Path) -> str:
    env = _env_demo(demo_db)
    _rodar("alembic upgrade head", [sys.executable, "-m", "alembic", "upgrade", "head"], env)
    return _rodar("seed_demo.py", [sys.executable, "seed_demo.py"], env)


def _conn(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("demo_objetos") / "pix_saude_demo.db"
    _semear(db)
    assert db.exists(), "o banco demo não foi criado pela receita"
    return db


def _duplas_posses(conn) -> list[tuple]:
    return conn.execute(
        "SELECT pedido_id, COALESCE(item_id, -1) AS k, COUNT(*) AS n "
        "  FROM pedido_exame_custodia WHERE encerrada_em IS NULL "
        " GROUP BY pedido_id, COALESCE(item_id, -1) HAVING COUNT(*) > 1"
    ).fetchall()


# ---------------------------------------------------------------------------
# 1 — os objetos-demo existem (a guarda propriamente dita)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("protocolo", [_PEDIDO_ATIVO, _PEDIDO_LAUDO])
def test_pedidos_demo_existem(demo_db, protocolo):
    conn = _conn(demo_db)
    row = conn.execute(
        "SELECT status FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    assert row is not None, (
        f"{protocolo} não foi semeado — o bloco best-effort engoliu o erro e o "
        "seed saiu 0 sem o objeto"
    )


def test_laudo_demo_existe(demo_db):
    """O objeto que a vitrine perdeu em 20/08."""
    conn = _conn(demo_db)
    row = conn.execute(
        "SELECT status FROM laudos WHERE protocolo = ?", (_LAUDO,)
    ).fetchone()
    assert row is not None, "laudo-demo ausente — foi exatamente o incidente de 20/08"
    assert row["status"] == "liberado"


# ---------------------------------------------------------------------------
# 2 — posse única: o invariante que o índice garante na PG
# ---------------------------------------------------------------------------

def test_nenhuma_dupla_posse_ativa(demo_db):
    """No máximo UMA custódia ativa por `(pedido_id, item_id)`.

    Na PG o índice único parcial recusa a segunda; no SQLite da demo o índice
    também existe (migração `d4b8c1e07f36`, dois dialetos). Este teste confere o
    RESULTADO — que o seed produz uma cadeia coerente, e não que o banco se
    defendeu.
    """
    conn = _conn(demo_db)
    assert _duplas_posses(conn) == [], "dupla posse ativa no banco semeado"


def test_proveniencia_do_pedido_do_laudo(demo_db):
    """A cadeia inteira: origem encerrada, posse do laboratório ativa.

    "Snapshot" justifica pular ESTADOS da máquina, nunca ELOS de custódia — o
    elo prescritor → paciente tem de existir, ENCERRADO, com a posse do
    laboratório aberta depois dele.
    """
    conn = _conn(demo_db)
    linhas = conn.execute(
        "SELECT c.de, c.para, c.encerrada_em FROM pedido_exame_custodia c "
        "  JOIN pedidos_exame p ON p.id = c.pedido_id "
        " WHERE p.protocolo = ? ORDER BY c.id", (_PEDIDO_LAUDO,),
    ).fetchall()

    assert len(linhas) == 2, f"esperava 2 elos de custódia, achei {len(linhas)}"
    origem, posse = linhas
    assert (origem["de"], origem["para"]) == ("prescritor", "paciente")
    assert origem["encerrada_em"] is not None, "o elo de origem ficou ATIVO — dupla posse"
    assert posse["de"] == "paciente"
    assert posse["encerrada_em"] is None, "a posse do laboratório devia estar ativa"


def test_pedido_ativo_segue_com_o_cidadao(demo_db):
    """O outro pedido é o da carteira: a posse fica com o cidadão."""
    conn = _conn(demo_db)
    linhas = conn.execute(
        "SELECT c.para FROM pedido_exame_custodia c "
        "  JOIN pedidos_exame p ON p.id = c.pedido_id "
        " WHERE p.protocolo = ? AND c.encerrada_em IS NULL", (_PEDIDO_ATIVO,),
    ).fetchall()
    assert [r["para"] for r in linhas] == ["paciente"]


# ---------------------------------------------------------------------------
# 3 — o ledger acompanha a custódia
# ---------------------------------------------------------------------------

def test_cada_elo_de_custodia_tem_evento(demo_db):
    """Abrir custódia sem emitir o evento é bug, não feature (CLAUDE.md §2).

    Como o choke-point escreve os dois juntos, a contagem tem de bater.
    """
    conn = _conn(demo_db)
    for protocolo in (_PEDIDO_ATIVO, _PEDIDO_LAUDO):
        elos = conn.execute(
            "SELECT COUNT(*) n FROM pedido_exame_custodia c "
            "  JOIN pedidos_exame p ON p.id = c.pedido_id WHERE p.protocolo = ?",
            (protocolo,),
        ).fetchone()["n"]
        eventos = conn.execute(
            "SELECT COUNT(*) n FROM pedido_exame_eventos e "
            "  JOIN pedidos_exame p ON p.id = e.pedido_id "
            " WHERE p.protocolo = ? AND e.tipo_evento = 'custodia_transferida'",
            (protocolo,),
        ).fetchone()["n"]
        assert elos == eventos, (
            f"{protocolo}: {elos} elos de custódia × {eventos} eventos"
        )


# ---------------------------------------------------------------------------
# 4 — idempotência (o deploy re-roda o seed a cada push)
# ---------------------------------------------------------------------------

def test_re_semear_nao_duplica_nem_quebra(demo_db):
    saida = _rodar("seed_demo.py (2ª vez)", [sys.executable, "seed_demo.py"],
                   _env_demo(demo_db))
    assert "já existe" in saida

    conn = _conn(demo_db)
    assert _duplas_posses(conn) == [], "a re-execução criou dupla posse"
    for protocolo in (_PEDIDO_ATIVO, _PEDIDO_LAUDO):
        n = conn.execute(
            "SELECT COUNT(*) n FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
        ).fetchone()["n"]
        assert n == 1, f"{protocolo} duplicado após re-seed"


# ---------------------------------------------------------------------------
# Prova de que a guarda morde
# ---------------------------------------------------------------------------

class TestAGuardaMorde:
    """Sem isto, uma query mal escrita deixaria a guarda verde para sempre."""

    def test_dupla_posse_injetada_e_detectada(self, tmp_path):
        db = tmp_path / "falso.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE pedido_exame_custodia (id INTEGER PRIMARY KEY, "
            "pedido_id INTEGER, item_id INTEGER, encerrada_em TEXT)"
        )
        conn.execute("INSERT INTO pedido_exame_custodia VALUES (1, 2, NULL, NULL)")
        conn.execute("INSERT INTO pedido_exame_custodia VALUES (2, 2, NULL, NULL)")
        assert _duplas_posses(conn) != [], "a guarda não viu a dupla posse (pedido 2)"

    def test_banco_coerente_nao_acusa(self, tmp_path):
        db = tmp_path / "ok.db"
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE pedido_exame_custodia (id INTEGER PRIMARY KEY, "
            "pedido_id INTEGER, item_id INTEGER, encerrada_em TEXT)"
        )
        conn.execute("INSERT INTO pedido_exame_custodia VALUES (1, 2, NULL, '2026-08-20')")
        conn.execute("INSERT INTO pedido_exame_custodia VALUES (2, 2, NULL, NULL)")
        assert _duplas_posses(conn) == []

def test_laudo_demo_nasce_com_o_elo(demo_db):
    """ENG-014 (v2, §2.1) — o laudo-demo NÃO pode nascer legado.

    Sem `pedido_item_id`, ele cai na ponte §2.2 a cada reset — e a ponte existe
    para o histórico de verdade (laudos anteriores à migração), não para objeto
    novo. A demo mostra o caminho moderno; o seed tem de exercitá-lo.

    O elo também tem de apontar para um item DO PEDIDO vinculado — um elo que
    aponta para outro lugar é pior que elo nenhum, porque parece certo.
    """
    conn = _conn(demo_db)
    linhas = conn.execute(
        "SELECT li.pedido_item_id, l.pedido_id, pei.pedido_id AS dono "
        "  FROM laudo_itens li "
        "  JOIN laudos l ON l.id = li.laudo_id "
        "  LEFT JOIN pedido_exame_itens pei ON pei.id = li.pedido_item_id "
        " WHERE l.protocolo = ?", (_LAUDO,),
    ).fetchall()

    assert linhas, "laudo-demo sem itens"
    for ln in linhas:
        assert ln["pedido_item_id"] is not None, (
            "laudo-demo nasceu LEGADO (sem elo) — cai na ponte §2.2 a cada reset"
        )
        assert ln["dono"] == ln["pedido_id"], (
            "o elo aponta para item de OUTRO pedido"
        )
