"""
Guard-rails do snapshot CNES durável da demo (DESPACHO-ENG-011 §5, classe `ops`).

O que estes testes travam
-------------------------
1. **Fronteira** — o bootstrap só age em DEMO_MODE e só quando o banco da
   aplicação NÃO é o próprio SQLite (aí o arquivo é do alembic/seed, não nosso).
2. **Suficiência do schema** — as queries REAIS de produção (`cnes_prescritor`
   e `identidade_prescritor`) rodam contra um side-car criado apenas por
   `DDL_CNES_DEMO` sem estourar coluna/tabela ausente. É o teste que dá sentido
   ao ticket: o defeito original era a base ausente virar `FileNotFoundError` em
   vez de o selo dizer a verdade sobre identidade sintética.
3. **Fonte única** — o módulo não declara CNPJ nem código CNES próprios; o
   side-car é projeção do que o `seed_demo.py` semeou (o mesmo princípio do
   `test_guardrail_identidades_demo.py`).
4. **Não derruba o boot** — falha no espelhamento degrada com log, nunca levanta.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from app.cnes_demo import DDL_CNES_DEMO, garantir_snapshot_cnes_demo


# ---------------------------------------------------------------------------
# Dublê do banco da aplicação (PostgreSQL na vitrine)
# ---------------------------------------------------------------------------

class _FakeRow(dict):
    pass


class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeAppConn:
    """Mímica mínima de `_PgConnection`: catálogo de colunas em
    `information_schema` + SELECT dos estabelecimentos, com chaves em minúsculo
    (como o RealDictCursor devolve, porque a PostgreSQL dobra identificadores
    não-citados)."""

    def __init__(self, estabelecimentos, *, colunas=None, erro=None):
        self.estabelecimentos = estabelecimentos
        if colunas is None:
            colunas = list(estabelecimentos[0].keys()) if estabelecimentos else []
        self.colunas = [c.lower() for c in colunas]
        self.erro = erro
        self.fechada = False

    def execute(self, sql, params=()):
        if self.erro:
            raise self.erro
        if "information_schema.columns" in sql:
            return _FakeCursor([_FakeRow({"column_name": c}) for c in self.colunas])
        # Só devolve as colunas que o chamador pediu — como faria a PostgreSQL.
        pedidas = [c.strip().split(" AS ")[-1].strip() for c in
                   sql.split("SELECT", 1)[1].split("FROM", 1)[0].split(",")]
        return _FakeCursor([
            _FakeRow({c: linha.get(c) for c in pedidas}) for linha in self.estabelecimentos
        ])

    def close(self):
        self.fechada = True


_ESTAB_DEMO = [
    _FakeRow({
        "co_unidade": "9900001", "co_cnes": "9900001", "nu_cnpj": "99999999000191",
        "tp_unidade": "04", "no_fantasia": "Farmácia Demo Central", "co_municipio": "261160",
    }),
    _FakeRow({
        "co_unidade": "9900002", "co_cnes": "9900002", "nu_cnpj": "99999999000272",
        "tp_unidade": "04", "no_fantasia": "Farmácia Demo Norte", "co_municipio": "261160",
    }),
]


@pytest.fixture
def vitrine(tmp_path, monkeypatch):
    """Ambiente da vitrine: DEMO_MODE ligado + banco da aplicação em PostgreSQL.

    Devolve `(caminho_do_sidecar, instalar_conn)` — `instalar_conn` troca o
    dublê de banco da aplicação usado pelo espelhamento.
    """
    caminho = tmp_path / "pix_saude_demo.db"
    monkeypatch.setattr("app.config.PICSAUDE_DEMO_MODE", True)
    monkeypatch.setattr("app.database._USE_SQLITE", False)
    monkeypatch.setattr("app.database._resolve_sqlite_db_path", lambda: str(caminho))

    def instalar_conn(conn):
        monkeypatch.setattr("app.database.get_conn", lambda: conn)

    instalar_conn(_FakeAppConn(_ESTAB_DEMO))
    return caminho, instalar_conn


def _tabelas(caminho: Path) -> set[str]:
    conn = sqlite3.connect(str(caminho))
    try:
        return {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1. Fronteira — quando o bootstrap NÃO age
# ---------------------------------------------------------------------------

def test_noop_fora_do_demo_mode(tmp_path, monkeypatch):
    """Fora de DEMO_MODE não se cria arquivo algum — nem em dev, nem em prod."""
    caminho = tmp_path / "nao_deve_existir.db"
    monkeypatch.setattr("app.config.PICSAUDE_DEMO_MODE", False)
    monkeypatch.setattr("app.database._USE_SQLITE", False)
    monkeypatch.setattr("app.database._resolve_sqlite_db_path", lambda: str(caminho))

    garantir_snapshot_cnes_demo()

    assert not caminho.exists()


def test_noop_quando_o_banco_da_aplicacao_e_o_proprio_sqlite(tmp_path, monkeypatch):
    """Se o SQLite É o banco da aplicação, o arquivo é do alembic/seed.

    Criá-lo aqui trocaria o erro claro ("SQLite DB não encontrado") por um
    obscuro ("no such table: prescricoes") em quem sobe a app antes de migrar.
    """
    caminho = tmp_path / "app_e_sidecar.db"
    monkeypatch.setattr("app.config.PICSAUDE_DEMO_MODE", True)
    monkeypatch.setattr("app.database._USE_SQLITE", True)
    monkeypatch.setattr("app.database._resolve_sqlite_db_path", lambda: str(caminho))

    garantir_snapshot_cnes_demo()

    assert not caminho.exists()


# ---------------------------------------------------------------------------
# 2. Criação, espelhamento e idempotência
# ---------------------------------------------------------------------------

def test_cria_o_sidecar_com_as_tres_tabelas_cnes(vitrine):
    caminho, _ = vitrine

    garantir_snapshot_cnes_demo()

    assert caminho.exists(), "o side-car CNES não foi criado no boot"
    assert {"profissionais_cnes", "relacao_prof_estab", "estabelecimentos_cnes"} <= _tabelas(caminho)


def test_espelha_as_farmacias_demo_do_banco_da_aplicacao(vitrine):
    """As 2 farmácias do §5 chegam ao side-car — vindas do seed, não de literais."""
    caminho, _ = vitrine

    garantir_snapshot_cnes_demo()

    conn = sqlite3.connect(str(caminho))
    try:
        linhas = conn.execute(
            "SELECT NU_CNPJ, CO_CNES, TP_UNIDADE, CO_UNIDADE FROM estabelecimentos_cnes "
            "ORDER BY NU_CNPJ"
        ).fetchall()
    finally:
        conn.close()

    assert [l[0] for l in linhas] == [r["nu_cnpj"] for r in _ESTAB_DEMO]
    assert [l[1] for l in linhas] == [r["co_cnes"] for r in _ESTAB_DEMO]
    assert all(l[2] == "04" for l in linhas), "TP_UNIDADE de farmácia perdido no espelho"
    assert all(l[3] for l in linhas), "CO_UNIDADE vazio quebraria o JOIN de identidade"


def test_reexecucao_nao_duplica_nem_perde_atualizacao(vitrine):
    """Idempotência por reposição: o banco da aplicação é quem manda.

    Dois boots seguidos não duplicam a linha; e se o seed mudar o código CNES,
    o side-car acompanha em vez de manter as duas versões convivendo.
    """
    caminho, instalar_conn = vitrine

    garantir_snapshot_cnes_demo()
    garantir_snapshot_cnes_demo()

    def _linhas():
        conn = sqlite3.connect(str(caminho))
        try:
            return conn.execute(
                "SELECT NU_CNPJ, CO_CNES FROM estabelecimentos_cnes ORDER BY NU_CNPJ"
            ).fetchall()
        finally:
            conn.close()

    assert len(_linhas()) == len(_ESTAB_DEMO), "boot repetido duplicou estabelecimento"

    atualizado = [_FakeRow({**_ESTAB_DEMO[0], "co_cnes": "9900009"}), _ESTAB_DEMO[1]]
    instalar_conn(_FakeAppConn(atualizado))
    garantir_snapshot_cnes_demo()

    linhas = _linhas()
    assert len(linhas) == 2
    assert dict(linhas)["99999999000191"] == "9900009"


def test_espelha_o_que_existe_quando_a_tabela_de_origem_e_mais_antiga(vitrine):
    """Regressão do estado REAL da vitrine.

    A `estabelecimentos_cnes` da PostgreSQL foi criada por uma versão anterior
    do cinturão do seed, sem `CO_UNIDADE` — e `CREATE TABLE IF NOT EXISTS` não
    acrescenta coluna a tabela que já existe. Um SELECT fixo estouraria
    `UndefinedColumn` exatamente no ambiente que este ticket conserta; o espelho
    copia o que há e deixa o resto NULL.
    """
    caminho, instalar_conn = vitrine
    legado = [
        _FakeRow({k: v for k, v in linha.items() if k != "co_unidade"})
        for linha in _ESTAB_DEMO
    ]
    instalar_conn(_FakeAppConn(legado))

    garantir_snapshot_cnes_demo()

    conn = sqlite3.connect(str(caminho))
    try:
        linhas = conn.execute(
            "SELECT NU_CNPJ, CO_CNES, CO_UNIDADE FROM estabelecimentos_cnes ORDER BY NU_CNPJ"
        ).fetchall()
    finally:
        conn.close()

    assert [l[0] for l in linhas] == [r["nu_cnpj"] for r in _ESTAB_DEMO]
    assert [l[1] for l in linhas] == [r["co_cnes"] for r in _ESTAB_DEMO]
    assert all(l[2] is None for l in linhas), "coluna ausente na origem deve virar NULL"


def test_sem_a_tabela_no_banco_da_aplicacao_ainda_cria_o_schema_vazio(vitrine):
    """Seed não rodou → schema vazio mesmo assim.

    É o suficiente para o AC: a validação responde `nao_encontrado` (identidade
    sintética) em vez de `cnes_snapshot_indisponivel` (base ausente).
    """
    caminho, instalar_conn = vitrine
    instalar_conn(_FakeAppConn([], colunas=[]))

    garantir_snapshot_cnes_demo()

    assert caminho.exists()
    conn = sqlite3.connect(str(caminho))
    try:
        assert conn.execute("SELECT COUNT(*) FROM estabelecimentos_cnes").fetchone()[0] == 0
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 3. Suficiência do schema — as queries REAIS de produção rodam
# ---------------------------------------------------------------------------

def test_validacao_cnes_roda_contra_o_sidecar_sem_base_ausente(vitrine, monkeypatch):
    """O defeito que o ticket fecha, em forma executável.

    Antes: `FileNotFoundError` → `divergencias=['cnes_snapshot_indisponivel']`.
    Depois: base presente, CNS sintético não consta → `nao_encontrado` limpo,
    que é o selo "baixo" dizendo a verdade (TICKET-J.4 (c)).
    """
    from app.domain.cnes_prescritor import validar_cns_prescritor

    caminho, _ = vitrine
    assert not caminho.exists()

    antes = validar_cns_prescritor(None, "980001112223334", "Dra. Demo Maria Souza")
    assert "cnes_snapshot_indisponivel" in antes["divergencias"], (
        "pré-condição do teste: sem o bootstrap, a base está ausente"
    )

    garantir_snapshot_cnes_demo()

    depois = validar_cns_prescritor(None, "980001112223334", "Dra. Demo Maria Souza")
    assert depois["nivel_validacao_cnes"] == "nao_encontrado"
    assert depois["divergencias"] == [], (
        f"schema insuficiente para a query de produção: {depois['divergencias']}"
    )


class _EspiaoCnesConn:
    """Conexão de verdade ao side-car que DELATA erro de SQL.

    `identidade_prescritor` engole qualquer exceção e devolve `[]` — o que faria
    um teste ingênuo passar mesmo com o schema errado. O espião registra o erro
    antes de a produção o engolir, e a SQL vem da própria produção (não é cópia
    colada aqui, que envelheceria em silêncio).
    """

    def __init__(self, caminho: str) -> None:
        self._real = sqlite3.connect(caminho)
        self._real.row_factory = sqlite3.Row
        self.erros: list[str] = []

    def execute(self, sql, params=()):
        try:
            return self._real.execute(sql, params)
        except sqlite3.OperationalError as exc:
            self.erros.append(f"{exc} :: {' '.join(sql.split())[:140]}")
            raise

    def close(self):
        self._real.close()


def test_identidade_por_conselho_roda_contra_o_sidecar(vitrine, monkeypatch):
    """A outra consumidora do side-car — inclui o LEFT JOIN por `CO_UNIDADE`,
    coluna que o cinturão anterior do `seed_demo.py` não tinha (o JOIN quebrava
    com "no such column: e.CO_UNIDADE" num banco demo SQLite)."""
    from app.domain import identidade_prescritor

    caminho, _ = vitrine
    garantir_snapshot_cnes_demo()

    espiao = _EspiaoCnesConn(str(caminho))
    monkeypatch.setattr(identidade_prescritor, "_get_cnes_conn", lambda: espiao)

    vinculos = identidade_prescritor._buscar_cnes_por_conselho(None, "12345", "PE")

    assert espiao.erros == [], f"schema insuficiente para a query real: {espiao.erros}"
    assert vinculos == [], "CRM sintético não consta — a query rodou, e não achou"


# ---------------------------------------------------------------------------
# 4. Fonte única e robustez de boot
# ---------------------------------------------------------------------------

def test_modulo_nao_declara_identidades_proprias():
    """O side-car é PROJEÇÃO do seed, não uma segunda declaração.

    Um CNPJ (14 díg.) ou código CNES chumbado aqui criaria um segundo lugar para
    a mesma verdade — o que o `test_guardrail_identidades_demo.py` existe para
    impedir do lado das telas. Mesma régua, outro sítio.
    """
    fonte = Path(__file__).resolve().parents[2] / "app" / "cnes_demo.py"
    codigo = "\n".join(
        linha for linha in fonte.read_text(encoding="utf-8").splitlines()
        if not linha.lstrip().startswith("#")
    )
    assert not re.search(r"(?<!\d)\d{11,14}(?!\d)", codigo), (
        "literal de identidade em app/cnes_demo.py — as farmácias vêm do seed"
    )


def test_falha_no_espelhamento_nao_derruba_o_boot(vitrine):
    """Validação CNES é não-bloqueante por contrato; o boot não pode cair por ela.

    E a falha não é permanente: o boot seguinte, com o banco de volta, repara.
    """
    caminho, instalar_conn = vitrine
    instalar_conn(_FakeAppConn([], erro=RuntimeError("pool esgotado")))

    garantir_snapshot_cnes_demo()  # não levanta — este é o ponto

    instalar_conn(_FakeAppConn(_ESTAB_DEMO))
    garantir_snapshot_cnes_demo()

    assert {"profissionais_cnes", "relacao_prof_estab", "estabelecimentos_cnes"} <= _tabelas(caminho)
    conn = sqlite3.connect(str(caminho))
    try:
        assert conn.execute("SELECT COUNT(*) FROM estabelecimentos_cnes").fetchone()[0] == 2
    finally:
        conn.close()


def test_o_bootstrap_esta_ligado_no_lifespan():
    """Módulo escrito e nunca chamado é módulo que não existe.

    `conftest.py` neutraliza `_lifespan_bootstrap` na suíte inteira, então
    nenhum outro teste passaria pelo sítio de chamada — sem esta guarda, apagar
    a linha do `main.py` deixaria a suíte verde e a vitrine sem base CNES.
    """
    import ast

    # Lido do ARQUIVO, e não do atributo do módulo: o próprio `conftest.py`
    # substitui `main._lifespan_bootstrap` por um lambda durante a suíte.
    fonte = Path(__file__).resolve().parents[2] / "app" / "main.py"
    arvore = ast.parse(fonte.read_text(encoding="utf-8"))

    bootstrap = next(
        (n for n in ast.walk(arvore)
         if isinstance(n, ast.FunctionDef) and n.name == "_lifespan_bootstrap"),
        None,
    )
    assert bootstrap is not None, "_lifespan_bootstrap sumiu de app/main.py"

    chamadas = {
        n.func.id for n in ast.walk(bootstrap)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "garantir_snapshot_cnes_demo" in chamadas, (
        "o snapshot CNES da demo não é mais garantido no boot"
    )


def test_ddl_e_fonte_unica_compartilhada_com_o_seed():
    """`seed_demo.py` aplica o MESMO DDL (importado, não copiado).

    Comentário que promete fonte única sem prova é decoração: aqui a prova é
    que o seed referencia o símbolo, e não um `CREATE TABLE` próprio.
    """
    seed = Path(__file__).resolve().parents[2] / "seed_demo.py"
    texto = seed.read_text(encoding="utf-8")

    assert "from app.cnes_demo import DDL_CNES_DEMO" in texto
    assert "for _ddl in DDL_CNES_DEMO" in texto
    for tabela in ("profissionais_cnes", "relacao_prof_estab", "estabelecimentos_cnes"):
        assert f"CREATE TABLE IF NOT EXISTS {tabela}" not in texto, (
            f"{tabela} voltou a ter DDL próprio no seed — duplicação"
        )
    assert len(DDL_CNES_DEMO) == 3
