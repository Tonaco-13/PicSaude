from __future__ import annotations

from contextlib import asynccontextmanager

import psycopg2

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.instance import get_instance_id
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.observabilidade import ObservabilidadeMiddleware
from app.observabilidade.logging_config import configure_logging
from app.routers import agendamentos, api_keys, auth, assinaturas, catalogo, circulacao_diagnostica, custodia, dispensacoes, dispensadores, eventos, health, hospitalares, ia, laudos, login, metrics, pacientes, pedidos_exame, prestadores, prescritor, prescritores, prescricoes, publico, receituarios, relatorios, solicitacoes, tokens, validacao

# Configura logging estruturado o mais cedo possível
configure_logging()

# ---------------------------------------------------------------------------
# Guardrail de produção — impede inicialização com SQLite em ambiente prod
#
# Se PICSAUDE_ENV=prod e DATABASE_URL não estiver configurada, o servidor
# recusa iniciar com mensagem clara. Usa variáveis já definidas em config.py.
# NÃO altera a camada dual SQLite/PostgreSQL — apenas bloqueia o caso inválido.
# ---------------------------------------------------------------------------
from app.config import PICSAUDE_ENV, JWT_SECRET
from app.database import _USE_SQLITE

if PICSAUDE_ENV == "prod" and _USE_SQLITE:
    raise RuntimeError(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ERRO DE CONFIGURAÇÃO — INICIALIZAÇÃO BLOQUEADA              ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        "║  PICSAUDE_ENV=prod mas DATABASE_URL não está configurada.    ║\n"
        "║  Produção não pode rodar com SQLite.                         ║\n"
        "║                                                              ║\n"
        "║  Configure a variável de ambiente antes de iniciar:          ║\n"
        "║    export DATABASE_URL=postgresql://user:pass@host:5432/db   ║\n"
        "║                                                              ║\n"
        "║  Para ambiente de desenvolvimento, use PICSAUDE_ENV=dev      ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )

# ---------------------------------------------------------------------------
# Guardrail de produção — impede inicialização com JWT secret fraco/default
#
# Se PICSAUDE_ENV=prod e JWT_SECRET contém o placeholder padrão ou tem menos
# de 32 caracteres, o servidor recusa iniciar com mensagem clara.
# NÃO altera lógica de autenticação — apenas bloqueia o caso inválido.
# ---------------------------------------------------------------------------
if PICSAUDE_ENV == "prod" and (
    "TROQUE_EM_PRODUCAO" in JWT_SECRET or len(JWT_SECRET) < 32
):
    raise RuntimeError(
        "\n"
        "╔══════════════════════════════════════════════════════════════╗\n"
        "║  ERRO DE CONFIGURAÇÃO — INICIALIZAÇÃO BLOQUEADA              ║\n"
        "╠══════════════════════════════════════════════════════════════╣\n"
        "║  PICSAUDE_ENV=prod mas PICSAUDE_JWT_SECRET é fraco ou é      ║\n"
        "║  o valor padrão inseguro do repositório.                     ║\n"
        "║                                                              ║\n"
        "║  Gere um segredo forte e configure antes de iniciar:         ║\n"
        "║    python3 -c \"import secrets; print(secrets.token_hex(32))\" ║\n"
        "║    export PICSAUDE_JWT_SECRET=<valor gerado>                 ║\n"
        "║                                                              ║\n"
        "║  Requisito mínimo: 32 caracteres, sem valor padrão do repo.  ║\n"
        "║  Para ambiente de desenvolvimento, use PICSAUDE_ENV=dev      ║\n"
        "╚══════════════════════════════════════════════════════════════╝\n"
    )

def _lifespan_bootstrap() -> None:
    """
    Hook do startup — bootstrap idempotente do ``instance_id``.

    Função module-level para ser patchável em testes via
    ``unittest.mock.patch`` (CODEX rodada 5 P1). Em produção/dev, abre
    ``SessionLocal`` global e chama ``get_instance_id(session)``:
    garante que DB (``meta_instalacao``), arquivo (``.instance_id``) e
    env override estão coerentes ANTES do primeiro request.

    Sem isso, ``get_instance_id_conn(conn)`` no primeiro request pode
    criar valor no DB sem propagar para o arquivo, gerando divergência
    forense que ``get_instance_id(session)`` rejeitaria depois com
    ``RuntimeError`` (DATA-PROTECTION.md §4.2).

    O bootstrap é idempotente (race-safe via INSERT OR IGNORE) e barato
    quando o ``instance_id`` já existe — apenas um SELECT.

    Em testes, ``backend/conftest.py`` neutraliza este hook via
    ``patch("app.main._lifespan_bootstrap", lambda: None)`` para evitar
    que ``with TestClient(app)`` toque o DB real.
    """
    session = SessionLocal()
    try:
        get_instance_id(session)
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _lifespan_bootstrap()
    yield


app = FastAPI(title="PIX da Saúde", version="0.2.0", lifespan=lifespan)


# ---------------------------------------------------------------------------
# Handler global — psycopg2.OperationalError
#
# Captura erros de conectividade com PostgreSQL (pool esgotado, timeout, etc.)
# e retorna 503 auditável em vez de stacktrace bruto 500.
# ---------------------------------------------------------------------------

@app.exception_handler(psycopg2.OperationalError)
async def _pg_operational_handler(request: Request, exc: psycopg2.OperationalError) -> JSONResponse:
    msg = str(exc).lower()
    if any(kw in msg for kw in ("could not connect", "connection", "timeout", "pool")):
        return JSONResponse(
            status_code=503,
            content={
                "erro": "banco_temporariamente_indisponivel",
                "detalhe": (
                    "O banco de dados está temporariamente indisponível. "
                    "Tente novamente em instantes."
                ),
                "codigo": "DB_UNAVAILABLE",
            },
        )
    return JSONResponse(
        status_code=500,
        content={
            "erro": "erro_operacional_banco",
            "detalhe": "Erro operacional inesperado no banco de dados.",
            "codigo": "DB_OPERATIONAL_ERROR",
        },
    )

# Middlewares são executados em ordem LIFO (último add = primeiro a rodar).
# RateLimitMiddleware deve rodar antes do CORS para rejeitar abuso cedo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)        # Ticket 62C — rate limiting por IP
app.add_middleware(SecurityHeadersMiddleware)  # Ticket 9 — headers HTTP de segurança
app.add_middleware(ObservabilidadeMiddleware)  # Ticket 11 — logging e métricas por request

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(login.router)        # POST /auth/token, /auth/refresh, /auth/bootstrap
app.include_router(prescritores.router)
app.include_router(pacientes.router)
app.include_router(auth.router)
app.include_router(dispensadores.router)
app.include_router(prescricoes.router)
app.include_router(receituarios.router)   # Ticket 15 — motor regulatório RDC 1.000/2025
app.include_router(catalogo.router)        # Ticket 20 — catálogo regulatório de substâncias
app.include_router(prescritor.router)      # Ticket 21 — endpoints do prescritor logado (certificado ICP)
app.include_router(assinaturas.router)    # GET+POST /prescricoes/{proto}/assinatura
app.include_router(validacao.router)      # GET /prescricoes/{proto}/validacao
app.include_router(custodia.router)
app.include_router(dispensacoes.router)
app.include_router(relatorios.router)
app.include_router(solicitacoes.router)   # Ticket 13 — solicitações de renovação
app.include_router(pedidos_exame.router)  # Ticket 15 — módulo de pedidos de exame
app.include_router(laudos.router)         # Ticket 20 — módulo de laudos
app.include_router(ia.router)             # Ticket 22 — IA farmacêutica v1
app.include_router(tokens.router)         # Ticket 24 — token de apresentação
app.include_router(hospitalares.router)   # Ticket 27 — dispensação hospitalar
app.include_router(agendamentos.router)          # Ticket 29 — módulo de agendamento
app.include_router(circulacao_diagnostica.router) # Ticket 53 — circulação diagnóstica
app.include_router(eventos.router)        # G4A — event publishing layer
app.include_router(health.router)         # G5-impl — health checks
app.include_router(metrics.router)        # Ticket 11 — métricas operacionais (localhost only)
app.include_router(prestadores.router)    # Ticket 30 — cadastro de prestadores
app.include_router(api_keys.router)       # G4B — gestão de API keys institucionais
app.include_router(publico.router)

# ---------------------------------------------------------------------------
# Servir HTMLs do frontend (apenas em DEV/HML)
#
# Em produção, os HTMLs ficam em Cloudflare Pages (picsaude.com.br) e o backend
# expõe só a API. Mas em desenvolvimento local é prático servir tudo na mesma
# porta para evitar setup de servidor estático separado.
#
# Este mount tem que vir DEPOIS de todos os routers — senão StaticFiles
# captura as URLs da API. FastAPI prioriza rotas registradas antes do mount.
# ---------------------------------------------------------------------------
if PICSAUDE_ENV != "prod":
    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent  # PicSaude_Dev/
    if FRONTEND_DIR.exists() and (FRONTEND_DIR / "index.html").exists():
        app.mount(
            "/",
            StaticFiles(directory=str(FRONTEND_DIR), html=True),
            name="frontend",
        )
