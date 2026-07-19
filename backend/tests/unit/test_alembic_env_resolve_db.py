"""test_alembic_env_resolve_db.py — dívida #98

Trava QUAL banco o `alembic` migra quando não há `DATABASE_URL`.

Por que este teste existe
-------------------------
`alembic/env.py` prometia no comentário "mesma lógica de database.py, sem
duplicar código" e logo abaixo cravava `pix_saude_pe.db`. Por 22 migrações ele
ignorou `PICSAUDE_DEMO_MODE` e `PIX_SAUDE_DB`. Duas consequências reais:

  - o banco demo nunca recebia migração (não havia como mandá-la para lá), e a
    reconstrução virava receita manual;
  - `PIX_SAUDE_DB=/tmp/x.db alembic upgrade head` mutava o banco de DEV em
    silêncio — quem rodava achando que mexia num efêmero perdia o dev.

Nenhum dos dois aparece como erro: aparecem como o banco errado sendo escrito.
Só um teste que afirma o DESTINO pega isso.

Por que modo offline (`--sql`)
------------------------------
`alembic upgrade head --sql` roda o `env.py` inteiro — incluindo a resolução do
path — mas NÃO conecta e NÃO cria arquivo nenhum. Um teste sobre "qual banco
seria escrito" não pode escrever em banco nenhum, e menos ainda tocar o dev do
desenvolvedor (que é justamente o acidente sob teste).

O comando termina com erro depois de imprimir o path: em modo offline o
SQLAlchemy entrega um `MockConnection`, que as migrações com `_table_exists()`
não conseguem inspecionar. Isso é ortogonal ao que se afirma aqui, então o
returncode é ignorado de propósito — a asserção é sobre a linha impressa.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parents[2]

# Variáveis que decidem o destino. Todas removidas antes de cada caso para que o
# teste não herde o ambiente de quem o roda (nem o do CI).
_VARS = ("DATABASE_URL", "PICSAUDE_DEMO_MODE", "PIX_SAUDE_DB", "PIX_SAUDE_DEMO_DB")


def _resolver(**env_extra: str) -> str:
    """Roda o env.py via alembic offline e devolve a saída (stdout + stderr)."""
    env = {k: v for k, v in os.environ.items() if k not in _VARS}
    env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.stdout + proc.stderr


def _path_resolvido(saida: str) -> str:
    """Extrai o path da linha `[alembic/env.py] ... usando SQLite <modo>: <path>`."""
    for linha in saida.splitlines():
        if "[alembic/env.py]" in linha and "usando SQLite" in linha:
            return linha.split(": ", 1)[1].strip()
    pytest.fail(f"env.py não anunciou o path do SQLite.\n--- saída ---\n{saida}")


def test_demo_mode_migra_o_banco_demo(tmp_path) -> None:
    """PICSAUDE_DEMO_MODE=true manda a migração para o banco DEMO, não o de dev.

    Era o coração da #98: sem isto, o demo ficava para trás do alembic head.
    """
    demo = tmp_path / "demo.db"
    saida = _resolver(PICSAUDE_DEMO_MODE="true", PIX_SAUDE_DEMO_DB=str(demo))

    assert _path_resolvido(saida) == str(demo)
    assert "pix_saude_pe.db" not in saida, "vazou para o banco de dev"


def test_pix_saude_db_migra_o_path_indicado(tmp_path) -> None:
    """PIX_SAUDE_DB=<path> manda a migração para <path>.

    Este é o acidente do TICKET-LEDGER-TRIGGERS-MIGRACAO: rodar alembic achando
    que o alvo era um banco efêmero e mutar o dev real.
    """
    efemero = tmp_path / "efemero.db"
    saida = _resolver(PIX_SAUDE_DB=str(efemero))

    assert _path_resolvido(saida) == str(efemero)
    assert "pix_saude_pe.db" not in saida, "ignorou PIX_SAUDE_DB e foi para o dev"


def test_sem_variaveis_continua_no_banco_de_dev() -> None:
    """Sem nenhuma das variáveis, nada muda para quem já usava — sem regressão."""
    saida = _resolver()

    assert _path_resolvido(saida).endswith(os.path.join("data", "pix_saude_pe.db"))


def test_database_url_vence_tudo(tmp_path) -> None:
    """DATABASE_URL tem precedência sobre as duas variáveis de SQLite.

    É o que torna esta mudança prod-safe por construção: produção define
    DATABASE_URL e nunca entra no ramo SQLite. Um PICSAUDE_DEMO_MODE herdado do
    ambiente não pode desviar a migração de produção para um arquivo local.
    """
    saida = _resolver(
        DATABASE_URL="postgresql://u:p@localhost:5432/picsaude",
        PICSAUDE_DEMO_MODE="true",
        PIX_SAUDE_DEMO_DB=str(tmp_path / "demo.db"),
        PIX_SAUDE_DB=str(tmp_path / "dev.db"),
    )

    assert "usando SQLite" not in saida, "DATABASE_URL foi ignorada — risco em produção"
    assert "demo.db" not in saida and "dev.db" not in saida


def test_resolucao_e_a_mesma_do_app() -> None:
    """env.py e app usam o MESMO resolvedor — o comentário virou código.

    Se alguém reintroduzir um path cravado no env.py, os testes acima pegam o
    desvio de destino; este pega a duplicação que os causa.
    """
    fonte = (_BACKEND_DIR / "alembic" / "env.py").read_text(encoding="utf-8")

    assert "_resolve_sqlite_db_path" in fonte, (
        "env.py deixou de usar o resolvedor de app/database.py — a duplicação "
        "que criou a dívida #98 voltou."
    )
    # Não se afirma aqui a AUSÊNCIA de "pix_saude_pe.db" no arquivo: o docstring
    # do env.py cita o default legitimamente, e a asserção daria falso positivo
    # em documentação. Um path cravado de volta seria pego pelos testes de
    # destino acima, que é onde o defeito se manifesta.
