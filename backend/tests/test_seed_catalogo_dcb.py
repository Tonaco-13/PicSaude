"""
DESPACHO-OPS-SEED-CATALOGO-DCB — guarda contra o "seeder órfão".

O defeito que este arquivo impede de renascer
---------------------------------------------
`app/domain/catalogo_seed.py` (~120 DCBs curadas) e
`scripts/seed_catalogo_substancias.py` existiam desde o Ticket 20, mas NADA no
pipeline os chamava: nem o `predeploy.sh` (Render/vitrine), nem o
`scripts/reset_demo_db.py`, nem o conftest do gate de navegador. Resultado:
`catalogo_substancias` nascia VAZIA em todo ambiente.

Vazia, o catálogo não é inofensivo — é silencioso. Pelo princípio de cautela do
catálogo parcial (`catalogo_regulatorio.validar_classificacao`, cenário 1),
substância ausente devolve `coerente=True, alertas=[]`. O motor RDC 1.000/2025
chamado por `routers/receituarios.py` (`validar_itens_prescricao`) ficava CEGO
sem emitir um único sinal, e `/catalogo/substancias` respondia vazio. A jornada
do controlado (B1 CLONAZEPAM) rodava sem oráculo.

O que este arquivo prova
------------------------
1. Depois do seed, a tabela NÃO está vazia (a guarda propriamente dita).
2. Re-executar o seed não duplica (o deploy re-roda o seed a cada push).
3. O motor enxerga a classificação do CLONAZEPAM — evidência pela função que o
   `receituarios.py` realmente chama, não por `print`.
4. Vermelho-antes-de-verde: com a tabela esvaziada, o mesmo motor emudece.

A receita usada é a do `predeploy.sh` — `alembic upgrade head` + `seed_demo.py`,
em SQLite efêmero. É o caminho da vitrine; `reset_demo_db.py` e o conftest de
navegador desembocam no mesmo `seed_demo.main()`.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.domain.catalogo_regulatorio import (
    buscar_substancia_por_nome,
    normalizar_dcb,
    validar_itens_prescricao,
)
from app.domain.catalogo_seed import (
    SEED_ANTIMICROBIANOS,
    SEED_GLP1,
    SEED_INATIVOS,
    SEED_PORTARIA_344,
)

_BACKEND_ROOT = Path(__file__).resolve().parent.parent

# O seed faz UPSERT por `dcb_normalizada` — o esperado é o número de DCBs
# DISTINTAS, não o de linhas das tuplas curadas. Deriva do próprio seed: se o
# arquiteto acrescentar substâncias, este número acompanha sem editar o teste.
_DCBS_ESPERADAS = {
    normalizar_dcb(dcb)
    for lista in (SEED_GLP1, SEED_ANTIMICROBIANOS, SEED_PORTARIA_344, SEED_INATIVOS)
    for dcb, *_ in lista
}


def _env_demo(demo_db: Path) -> dict:
    env = {
        **os.environ,
        "PICSAUDE_DEMO_MODE": "true",
        "PICSAUDE_ENV": "stg",  # != prod (seed_demo aborta em prod)
        "PIX_SAUDE_DEMO_DB": str(demo_db),
    }
    env.pop("DATABASE_URL", None)  # força o ramo SQLite mesmo no gate de PG
    return env


def _rodar(passo: str, args: list[str], env: dict) -> None:
    proc = subprocess.run(
        args,
        cwd=str(_BACKEND_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, (
        f"{passo} falhou (rc={proc.returncode}):\n{proc.stdout}\n{proc.stderr}"
    )


def _semear(demo_db: Path) -> None:
    """A receita do `predeploy.sh`, contra um SQLite efêmero."""
    env = _env_demo(demo_db)
    _rodar("alembic upgrade head", [sys.executable, "-m", "alembic", "upgrade", "head"], env)
    _rodar("seed_demo.py", [sys.executable, "seed_demo.py"], env)


def _conn(db: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory) -> Path:
    """Banco demo efêmero, semeado uma vez por módulo (a receita é lenta)."""
    db = tmp_path_factory.mktemp("demo_catalogo") / "pix_saude_demo.db"
    _semear(db)
    assert db.exists(), "o banco demo não foi criado pela receita"
    return db


# ---------------------------------------------------------------------------
# 1. A guarda — o seed não pode deixar o catálogo vazio
# ---------------------------------------------------------------------------

def test_seed_da_demo_popula_catalogo_substancias(demo_db):
    conn = _conn(demo_db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM catalogo_substancias").fetchone()[0]
    finally:
        conn.close()

    assert n > 0, (
        "catalogo_substancias está VAZIA após o seed da demo. O seeder voltou a "
        "ficar órfão: `seed_demo.main()` precisa chamar "
        "`_garantir_catalogo_regulatorio` (que chama "
        "`app.domain.catalogo_seed.aplicar_seed_catalogo`). Sem isso o motor "
        "RDC 1.000/2025 fica cego e /catalogo/substancias responde vazio."
    )
    assert n == len(_DCBS_ESPERADAS), (
        f"o seed gravou {n} substâncias, mas o catálogo curado tem "
        f"{len(_DCBS_ESPERADAS)} DCBs distintas — seed parcial."
    )


def test_seed_reexecutado_nao_duplica(demo_db, tmp_path):
    """O deploy re-roda o seed a cada push: 2ª rodada tem de ser inerte."""
    db2 = tmp_path / "pix_saude_demo_idem.db"
    shutil.copy(str(demo_db), str(db2))

    conn = _conn(db2)
    try:
        antes = conn.execute("SELECT COUNT(*) FROM catalogo_substancias").fetchone()[0]
    finally:
        conn.close()
    assert antes > 0, "sem catálogo semeado, este teste passaria à toa (0 == 0)"

    # Só o seed (o schema já está em head) — é o que o predeploy repete.
    _rodar("re-seed", [sys.executable, "seed_demo.py"], _env_demo(db2))

    conn = _conn(db2)
    try:
        depois = conn.execute("SELECT COUNT(*) FROM catalogo_substancias").fetchone()[0]
        dups = conn.execute(
            "SELECT dcb_normalizada, COUNT(*) c FROM catalogo_substancias "
            "GROUP BY dcb_normalizada HAVING COUNT(*) > 1"
        ).fetchall()
    finally:
        conn.close()

    assert depois == antes, f"seed não é idempotente: {antes} → {depois} substâncias"
    assert not dups, f"DCBs duplicadas após re-seed: {[r['dcb_normalizada'] for r in dups]}"


# ---------------------------------------------------------------------------
# 2. Jornada do controlado — o motor passa a ENXERGAR o CLONAZEPAM
# ---------------------------------------------------------------------------

def test_motor_enxerga_classificacao_do_clonazepam(demo_db):
    """Evidência pela mesma função que `routers/receituarios.py` chama."""
    conn = _conn(demo_db)
    try:
        # (a) o oráculo resolve o nome comercial-ish do prescritor à DCB
        subst = buscar_substancia_por_nome("Clonazepam 2mg", conn)
        assert subst is not None, "catálogo não resolveu 'Clonazepam 2mg'"
        assert subst.classe_controle == "B1", (
            f"classe do clonazepam veio '{subst.classe_controle}', esperado 'B1' "
            "(Portaria SVS/MS 344/1998)"
        )
        assert subst.fonte == "portaria_344"

        # (b) o motor do /gerar reage: item declarado SEM classe vira alerta
        alertas = validar_itens_prescricao(
            [{"id": 1, "nome_medicamento": "Clonazepam 2mg", "classe_controle": None,
              "tipo_retencao": None}],
            conn,
        )
    finally:
        conn.close()

    assert len(alertas) == 1, f"esperado 1 alerta, veio {len(alertas)}: {alertas}"
    alerta = alertas[0]
    assert alerta.severidade == "warning"
    assert alerta.sugestao_classe == "B1"
    assert "B1" in alerta.mensagem


def test_catalogo_vazio_deixa_o_motor_cego(demo_db, tmp_path):
    """Vermelho-antes-de-verde: é o seed que acende o motor, não o código dele.

    Mesma prescrição do teste acima, mesma função — só a tabela é esvaziada.
    Zero alertas: era este o estado da demo antes deste despacho.
    """
    db_vazio = tmp_path / "pix_saude_demo_sem_catalogo.db"
    shutil.copy(str(demo_db), str(db_vazio))

    conn = _conn(db_vazio)
    try:
        povoado = conn.execute("SELECT COUNT(*) FROM catalogo_substancias").fetchone()[0]
        assert povoado > 0, "o esvaziamento precisa partir de um catálogo semeado"
        conn.execute("DELETE FROM catalogo_substancias")
        conn.commit()
        assert buscar_substancia_por_nome("Clonazepam 2mg", conn) is None
        alertas = validar_itens_prescricao(
            [{"id": 1, "nome_medicamento": "Clonazepam 2mg", "classe_controle": None,
              "tipo_retencao": None}],
            conn,
        )
    finally:
        conn.close()

    assert alertas == [], (
        "com o catálogo vazio o motor deveria emudecer (princípio de cautela) — "
        "se isto falhou, a semântica do catálogo parcial mudou e esta guarda "
        "precisa ser reescrita."
    )
