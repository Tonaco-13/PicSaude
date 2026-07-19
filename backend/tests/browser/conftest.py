"""
tests/browser/conftest.py — app de demo efêmero para os smokes de navegador.

TICKET-GATE-BROWSER (opção C, híbrido).

POR QUE ESTA PASTA EXISTE SEPARADA
----------------------------------
As guardas estáticas de `tests/unit/test_frontend_atestado.py` rodam em TODO PR e
são a primeira linha. Estes smokes são a SEGUNDA camada — rodam só em PR que toca
`**.html` e no nightly (`.github/workflows/gates-browser.yml`). Ficam fora de
`tests/unit` e `tests/integration` justamente para não entrar no gate atual: um PR
de ledger não deve pagar por um navegador.

Guardas estáticas respondem "o código está na ordem certa?".
Estes smokes respondem "a tela abre?". São perguntas diferentes.

O AMBIENTE
----------
Sobe a própria aplicação em DEMO_MODE contra um SQLite efêmero, pela receita que a
dívida #98 ainda nos obriga a fazer à mão:

    DATABASE_URL=sqlite:///<tmp>              alembic upgrade head
    PIX_SAUDE_DB=<tmp>  python3 init_tables.py
    PIX_SAUDE_DB=<tmp>  PICSAUDE_DEMO_MODE=true  python3 seed_demo.py
    PIX_SAUDE_DB=<tmp>  PICSAUDE_DEMO_MODE=true  uvicorn app.main:app

O `alembic upgrade head` vem PRIMEIRO e não é opcional (TICKET-LEDGER-TRIGGERS-
MIGRACAO): a migração é a autoridade de schema (CLAUDE.md §9) e é ela — não o
`init_tables.py` — que cria os triggers de imutabilidade do ledger. Sem este
passo o banco efêmero nasce sem a proteção do §2, e o `init_tables.py` (que agora
CONFERE os triggers e sai com 1 se faltarem) derruba a fixture inteira. Foi
exatamente o que aconteceu: era o mesmo defeito do ticket — um caminho de criação
de banco que não passa pela migração — só que na fixture.

Bônus documentado no ticket: o CI passa a PROVAR que essa receita funciona. Se a
reconstrução do banco demo quebrar, estes testes ficam vermelhos antes da demo.

O app serve os HTMLs por conta própria (`main.py` monta StaticFiles em `/` depois
dos routers), então um único processo entrega API e frontend na mesma origem — sem
CORS e sem servidor estático separado.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# `pytest.ini` tem testpaths=tests, então um `pytest` cru a partir de backend/
# coletaria esta pasta. Quem não instalou o requirements-browser.txt (a maioria
# — ele é só do gate de navegador) receberia um erro de coleta em vez de rodar
# a suíte. Pulamos a pasta inteira quando o Playwright não está presente.
#
# gates.yml não é afetado: ele chama tests/unit e tests/integration por nome.
collect_ignore_glob: list[str] = []
try:  # noqa: SIM105
    import playwright.sync_api  # noqa: F401
except ImportError:  # pragma: no cover — caminho de quem não tem o extra
    collect_ignore_glob.append("test_*.py")

# backend/ — de onde init_tables.py, seed_demo.py e o uvicorn precisam rodar.
_BACKEND_DIR = Path(__file__).resolve().parents[2]

_BOOT_TIMEOUT_S = 60.0
_BOOT_POLL_S = 0.25

# Não é credencial: vale só para o processo efêmero deste gate, que nasce e morre
# dentro da sessão de teste e nunca vê dado real.
_JWT_SECRET_TESTE = "gate-browser-secret-nao-usar-em-producao"


def _porta_livre() -> int:
    """Reserva uma porta efêmera do SO e devolve o número.

    Fecha o socket antes de entregar — há uma janela de corrida teórica entre o
    fechamento e o bind do uvicorn, mas é a forma padrão de evitar colisão em CI
    e o alvo é um processo só.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _rodar_argv(rotulo: str, argv: list[str], env: dict[str, str]) -> None:
    """Roda um passo de bootstrap do banco, falhando alto se ele falhar.

    Sem `check=True` um seed quebrado viraria um smoke vermelho e confuso lá na
    frente ("a fila está vazia") em vez do erro real aqui.
    """
    proc = subprocess.run(
        argv,
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Falha ao preparar o banco demo com {rotulo} "
            f"(exit {proc.returncode}).\n"
            f"--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )


def _rodar(script: str, env: dict[str, str]) -> None:
    _rodar_argv(repr(script), [sys.executable, script], env)


def _migrar(db_path: str, env: dict[str, str]) -> None:
    """`alembic upgrade head` contra o SQLite efêmero — schema + triggers do ledger.

    `alembic/env.py` lê `DATABASE_URL` (e só ela): `PIX_SAUDE_DB`/`PICSAUDE_DEMO_MODE`
    roteiam o app, não o Alembic. Por isso a URL vai explícita aqui, apontando para
    o MESMO arquivo que o app vai abrir depois.
    """
    _rodar_argv(
        "'alembic upgrade head'",
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        {**env, "DATABASE_URL": f"sqlite:///{db_path}"},
    )


@pytest.fixture(scope="session")
def app_demo(tmp_path_factory) -> str:
    """Sobe o app em DEMO_MODE contra um DB efêmero. Devolve a base_url."""
    # Import tardio: httpx é dependência do backend, mas manter o import aqui
    # deixa o erro de coleta legível se a pasta rodar sem o ambiente completo.
    import httpx

    db_path = tmp_path_factory.mktemp("demo-db") / "picsaude_browser.db"
    porta = _porta_livre()
    base_url = f"http://127.0.0.1:{porta}"

    env = {
        **os.environ,
        # Os DOIS apontam para o mesmo arquivo efêmero. Em DEMO_MODE o resolver
        # de path usa PIX_SAUDE_DEMO_DB (database.py:_resolve_sqlite_db_path);
        # fixamos PIX_SAUDE_DB junto para que nada caia no banco de dev do
        # desenvolvedor caso algum caminho ainda não passe pelo resolver.
        "PIX_SAUDE_DB": str(db_path),
        "PIX_SAUDE_DEMO_DB": str(db_path),
        "PICSAUDE_DEMO_MODE": "true",
        # DEMO e prod são mutuamente exclusivos — o guard de boot do main.py
        # aborta se os dois vierem juntos. Fixamos 'dev' para não herdar um
        # PICSAUDE_ENV do runner.
        "PICSAUDE_ENV": "dev",
        # Segredo fixo: o token do /demo/login precisa continuar válido para o
        # processo inteiro. Vale só para este app efêmero de teste.
        "JWT_SECRET": _JWT_SECRET_TESTE,
        "PYTHONUNBUFFERED": "1",
    }

    # Ordem obrigatória: migração (autoridade de schema) → init_tables (create_all
    # do que ainda está fora do alembic + CONFERE os triggers) → seed.
    _migrar(str(db_path), env)
    _rodar("init_tables.py", env)
    _rodar("seed_demo.py", env)

    servidor = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(porta),
            "--log-level", "warning",
        ],
        cwd=_BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        limite = time.monotonic() + _BOOT_TIMEOUT_S
        while True:
            if servidor.poll() is not None:
                raise RuntimeError(
                    "O servidor de demo morreu durante o boot.\n"
                    f"--- saída ---\n{servidor.stdout.read() if servidor.stdout else ''}"
                )
            try:
                if httpx.get(f"{base_url}/health", timeout=2.0).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > limite:
                servidor.kill()
                raise RuntimeError(
                    f"O servidor de demo não respondeu em {_BOOT_TIMEOUT_S:.0f}s."
                )
            time.sleep(_BOOT_POLL_S)

        yield base_url
    finally:
        servidor.terminate()
        try:
            servidor.wait(timeout=10)
        except subprocess.TimeoutExpired:
            servidor.kill()


# Recusa de autenticação é o app FUNCIONANDO, não defeito. `clinica.html` não tem
# persona no /demo/login (a própria tela avisa: "esta tela não tem persona demo"),
# então o POST /auth/token responde 403 numa visita anônima. Tolerar só estes dois
# status — um 500 ou um 404 de asset continuam derrubando o smoke.
_STATUS_DE_AUTH_ESPERADOS = {401, 403}

# O console emite esta mensagem genérica para QUALQUER recurso que falhe, sem
# dizer qual nem com que status. Como o listener de 'response' já cobre isso com
# precisão (status + URL), a linha de console é ruído duplicado — descartá-la
# evita que um 403 legítimo apareça como erro sem contexto.
_RUIDO_DE_RECURSO = "Failed to load resource"


@pytest.fixture
def erros_de_console(page):
    """Coleta erros de JS e de rede. Base do smoke (d).

    Registra os listeners ANTES de qualquer navegação — daí ser fixture, e não
    algo montado dentro do teste: um erro disparado durante o load inicial
    passaria despercebido se o listener entrasse depois.

    Três fontes, com pesos diferentes:

      - pageerror  → exceção JS não tratada. SEMPRE falha. É a classe do bug do
                     #103: um ReferenceError de temporal dead zone não passa pelo
                     console.error, só por aqui.
      - console.error → erro que o app reportou, menos o ruído genérico de recurso.
      - response >= 400 → falha de rede COM contexto (status + URL), exceto as
                     recusas de autenticação esperadas.
    """
    capturados: list[str] = []

    def _console(msg) -> None:
        if msg.type == "error" and _RUIDO_DE_RECURSO not in msg.text:
            capturados.append(f"console.error: {msg.text}")

    def _response(resp) -> None:
        if resp.status >= 400 and resp.status not in _STATUS_DE_AUTH_ESPERADOS:
            capturados.append(f"HTTP {resp.status}: {resp.url}")

    page.on("console", _console)
    page.on("pageerror", lambda exc: capturados.append(f"pageerror: {exc}"))
    page.on("response", _response)

    return capturados
