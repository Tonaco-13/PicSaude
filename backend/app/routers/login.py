"""
routers/login.py
================
Autenticação do PicSaúde — emissão de JWT por perfil.

Endpoints:
  POST /auth/token      — login (retorna access + refresh token)
  POST /auth/refresh    — renova access token com refresh token
  POST /auth/registrar  — cria usuário (bootstrap: primeiro usuário vira admin)

Identificadores por perfil:
  prescritor   → CNS  (normalizado, 15 dígitos)
  dispensador  → CNPJ (normalizado, 14 dígitos)
  auditor      → e-mail
  admin        → e-mail

Bootstrap:
  Se não houver nenhum usuário no banco, o primeiro registro é automaticamente admin.
  Após isso, apenas admin pode criar novos usuários.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, require_role
from app.auth.jwt import (
    criar_access_token,
    criar_refresh_token,
    hash_senha,
    verificar_refresh_token,
    verificar_senha,
)
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.roles import PERFIS_VALIDOS
from app.utils.helpers import normalize_cnpj, normalize_cns, normalize_nome

router = APIRouter(prefix="/auth", tags=["auth"])


# TICKET-6 P1#2 — em DEMO_MODE, endpoints de login real / OTP devolvem
# 403 demo_mode_ativo. Helper local (inline KISS, sem dependency externa).
def _reject_if_demo() -> None:
    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "demo_mode_ativo",
                "mensagem": "Login real desabilitado em modo demo. Use o seletor em /.",
            },
        )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegistrarIn(BaseModel):
    role:          str
    identificador: str   # CNS, CNPJ ou e-mail conforme o perfil
    nome:          str
    senha:         str


class RefreshIn(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalizar_identificador(role: str, identificador: str) -> str:
    if role == "prescritor":
        return normalize_cns(identificador)
    if role == "dispensador":
        return normalize_cnpj(identificador)
    return identificador.strip().lower()   # e-mail para auditor/admin


# ---------------------------------------------------------------------------
# POST /auth/token  — login padrão OAuth2 (form: username + password)
# ---------------------------------------------------------------------------

@router.post("/token", summary="Login — obtém access token e refresh token")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    _demo=Depends(_reject_if_demo),
):
    """
    Autentica um usuário e retorna os tokens JWT.

    - `username` → identificador do usuário (CNS, CNPJ ou e-mail)
    - `password` → senha cadastrada

    O token retornado deve ser enviado como `Authorization: Bearer <token>`
    nos endpoints protegidos.
    """
    with get_tx() as conn:
        usuario = conn.execute(
            "SELECT id, role, identificador, nome, senha_hash, ativo FROM usuarios WHERE identificador = ?",
            (form.username.strip(),),
        ).fetchone()

    if not usuario or not usuario["ativo"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verificar_senha(form.password, usuario["senha_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access  = criar_access_token(
        sub=usuario["identificador"],
        role=usuario["role"],
        nome=usuario["nome"],
    )
    refresh = criar_refresh_token(sub=usuario["identificador"])

    return {
        "access_token":  access,
        "refresh_token": refresh,
        "token_type":    "bearer",
        "role":          usuario["role"],
        "nome":          usuario["nome"],
    }


# ---------------------------------------------------------------------------
# POST /auth/refresh  — renova access token
# ---------------------------------------------------------------------------

@router.post("/refresh", summary="Renova o access token com o refresh token")
def refresh_token(body: RefreshIn, _demo=Depends(_reject_if_demo)):
    try:
        sub = verificar_refresh_token(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    with get_tx() as conn:
        usuario = conn.execute(
            "SELECT role, nome, ativo FROM usuarios WHERE identificador = ?", (sub,)
        ).fetchone()

    if not usuario or not usuario["ativo"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inativo.")

    return {
        "access_token": criar_access_token(sub=sub, role=usuario["role"], nome=usuario["nome"]),
        "token_type":   "bearer",
    }


# ---------------------------------------------------------------------------
# POST /auth/registrar  — cria usuário
# ---------------------------------------------------------------------------

@router.post("/registrar", status_code=201, summary="Registra novo usuário")
def registrar(
    body: RegistrarIn,
    # TICKET-6.1 P2#4: demo guard PRIMEIRO. Sem isso, require_role devolve
    # 401 'Not authenticated' antes do 403 demo_mode_ativo. FastAPI resolve
    # dependencies na ordem declarada.
    _demo=Depends(_reject_if_demo),
    _admin=Depends(require_role("admin")),
):
    """
    Cria um novo usuário no sistema.

    **Requer perfil admin.**

    Bootstrap: o primeiro usuário pode ser criado via `POST /auth/bootstrap`
    sem autenticação (disponível apenas quando não há nenhum usuário no banco).
    """
    return _criar_usuario(body)


@router.post("/bootstrap", status_code=201, summary="Cria o primeiro usuário admin (bootstrap)")
def bootstrap(body: RegistrarIn, _demo=Depends(_reject_if_demo)):
    """
    Cria o primeiro usuário admin quando o banco está vazio.
    Retorna 409 se já existir qualquer usuário.

    Use este endpoint uma única vez para inicializar o sistema.
    Após isso, use `POST /auth/registrar` (requer auth de admin).
    """
    with get_tx() as conn:
        total = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]

    if total > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap indisponível: já existem usuários cadastrados. Use POST /auth/registrar.",
        )

    # Bootstrap sempre cria admin, independente do role enviado
    body.role = "admin"
    return _criar_usuario(body)


# ---------------------------------------------------------------------------
# Helper interno de criação
# ---------------------------------------------------------------------------

def _criar_usuario(body: RegistrarIn) -> dict:
    if body.role not in PERFIS_VALIDOS:
        raise HTTPException(
            status_code=422,
            detail=f"Perfil inválido: '{body.role}'. Permitidos: {sorted(PERFIS_VALIDOS)}",
        )

    identificador = _normalizar_identificador(body.role, body.identificador)
    nome          = normalize_nome(body.nome) or body.nome.strip().upper()
    senha_hash    = hash_senha(body.senha)

    with get_tx() as conn:
        existente = conn.execute(
            "SELECT id FROM usuarios WHERE identificador = ?", (identificador,)
        ).fetchone()

        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Identificador '{identificador}' já cadastrado.",
            )

        from datetime import datetime
        agora = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO usuarios (role, identificador, nome, senha_hash, ativo, created_at, updated_at)
            VALUES (?, ?, ?, ?, true, ?, ?)
            """,
            (body.role, identificador, nome, senha_hash, agora, agora),
        )

    return {"ok": True, "role": body.role, "identificador": identificador, "nome": nome}


# ---------------------------------------------------------------------------
# POST /auth/paciente/solicitar-codigo  — OTP para autenticação do cidadão
# ---------------------------------------------------------------------------

class _SolicitarCodigoIn(BaseModel):
    cpf: str


class _ValidarCodigoIn(BaseModel):
    cpf: str
    codigo: str


# ---------------------------------------------------------------------------
# GET /auth/me/institucional  — contexto de prestador do usuário logado
# ---------------------------------------------------------------------------

@router.get("/me/institucional", summary="Contexto institucional do usuário autenticado")
def contexto_institucional(usuario: dict = Depends(require_role("dispensador", "admin"))):
    """
    Retorna o prestador e unidades vinculados ao CNPJ do usuário autenticado.

    Uso: dispensador.html e clinica.html chamam este endpoint após login para
    auto-preencher org_id e unidade_id sem exigir digitação manual.

    - 200  → { org_id, nome, tipo, cnes_verificado, unidades: [{unidade_id, nome, tipo}] }
    - 404  → CNPJ não tem prestador cadastrado (campo preenchido manualmente)

    cnes_verificado=True quando o CNPJ consta em estabelecimentos_cnes com
    TP_UNIDADE compatível com o tipo do prestador (Tratamento 3).
    """
    cnpj = usuario.get("sub", "")
    with get_tx() as conn:
        prestador = conn.execute(
            "SELECT id, org_id, nome, tipo FROM prestadores WHERE cnpj = ? AND ativo = true",
            (cnpj,),
        ).fetchone()
        if not prestador:
            raise HTTPException(
                status_code=404,
                detail="Nenhum prestador vinculado a este CNPJ. Preencha org_id e unidade_id manualmente.",
            )
        unidades = conn.execute(
            """
            SELECT unidade_id, nome, tipo
            FROM unidades
            WHERE prestador_id = ? AND ativo = true
            ORDER BY criado_em ASC
            """,
            (prestador["id"],),
        ).fetchall()

        # Tratamento 3 — cruzar CNPJ contra estabelecimentos_cnes por tipo
        _TP_FARMACIA  = ("04", "40", "70", "71")
        _TP_CLINICA   = ("01", "02", "05", "15", "20", "21", "36", "39", "43")
        tipo_prestador = (prestador["tipo"] or "").lower()
        tipos_cnes = _TP_FARMACIA if tipo_prestador == "farmacia" else _TP_CLINICA
        placeholders = ", ".join("?" * len(tipos_cnes))
        cnes_row = conn.execute(
            f"""
            SELECT CO_CNES FROM estabelecimentos_cnes
            WHERE REPLACE(REPLACE(REPLACE(REPLACE(NU_CNPJ, '.', ''), '/', ''), '-', ''), ' ', '') = ?
              AND TP_UNIDADE IN ({placeholders})
            LIMIT 1
            """,
            (cnpj, *tipos_cnes),
        ).fetchone()
        cnes_verificado = cnes_row is not None

    return {
        "org_id":          prestador["org_id"],
        "nome":            prestador["nome"],
        "tipo":            prestador["tipo"],
        "cnes_verificado": cnes_verificado,
        "unidades":        [dict(u) for u in unidades],
    }


@router.post("/paciente/solicitar-codigo", status_code=200,
             summary="Solicita código OTP para autenticação do cidadão")
def solicitar_codigo_paciente(
    body: _SolicitarCodigoIn,
    _demo=Depends(_reject_if_demo),
):
    """
    Gera e armazena um OTP de 6 dígitos para o CPF informado.

    Segurança:
    - OTP NÃO é retornado na resposta (evita exposição via HTTP).
    - Em ambiente local/dev, o código é impresso no console do backend.
    - Em produção, substituir o print() por integração SMS/e-mail.

    Expiração: 5 minutos. Uso único.
    """
    from app.utils.helpers import normalize_cpf
    cpf = normalize_cpf(body.cpf)
    if not cpf:
        raise HTTPException(status_code=400, detail="CPF inválido ou não informado.")

    codigo = str(secrets.randbelow(900000) + 100000)
    agora_str = datetime.utcnow().isoformat()

    with get_tx() as conn:
        from datetime import timedelta
        expiracao_str = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO pacientes (cpf, nome, created_at, updated_at, ativo) VALUES (?, 'PACIENTE', ?, ?, false)",
            (cpf, agora_str, agora_str),
        )
        conn.execute(
            "INSERT INTO codigos_login (cpf, codigo, expiracao, usado, created_at) VALUES (?, ?, ?, 0, ?)",
            (cpf, codigo, expiracao_str, agora_str),
        )

    # Print OTP no stdout APENAS em dev/test — em produção (Render),
    # OTP nunca aparece nos logs. Bloqueador de segurança CODEX 2026-05-06.
    # SEM default: PICSAUDE_ENV ausente é tratado como "não-dev/test",
    # então deploy sem env configurada NÃO vaza OTP.
    _cpf_mascarado = f"*******{cpf[-4:]}" if len(cpf) >= 4 else "***"
    if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
        print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

    return {
        "ok": True,
        "mensagem": "Código de verificação gerado. Em produção será enviado por SMS ou e-mail.",
    }


@router.post("/paciente/validar-codigo", status_code=200,
             summary="Valida o OTP e emite token JWT para o cidadão")
def validar_codigo_paciente(
    body: _ValidarCodigoIn,
    _demo=Depends(_reject_if_demo),
):
    """
    Valida o OTP informado e emite um JWT com role=paciente.

    - OTP é invalidado imediatamente após uso (uso único).
    - Códigos expirados são rejeitados.
    - Retorna access_token para ser usado como Bearer em endpoints protegidos.
    """
    from app.utils.helpers import normalize_cpf
    cpf = normalize_cpf(body.cpf)
    codigo = (body.codigo or "").strip()

    if not cpf or not codigo:
        raise HTTPException(status_code=400, detail="CPF e código são obrigatórios.")

    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT id FROM codigos_login
            WHERE cpf = ?
              AND codigo = ?
              AND usado = 0
              AND expiracao >= ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (cpf, codigo, datetime.utcnow().isoformat()),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Código inválido, expirado ou já utilizado.")

        conn.execute("UPDATE codigos_login SET usado = 1 WHERE id = ?", (row["id"],))
        conn.execute("UPDATE pacientes SET ativo = true WHERE cpf = ?", (cpf,))

        paciente = conn.execute(
            "SELECT nome FROM pacientes WHERE cpf = ?", (cpf,)
        ).fetchone()
        nome = (paciente["nome"] if paciente else None) or "Paciente"

    access_token = criar_access_token(sub=cpf, role="paciente", nome=nome)
    return {
        "ok":           True,
        "access_token": access_token,
        "token_type":   "bearer",
        "nome":         nome,
        # cpf omitido da resposta (LGPD — cliente já conhece o próprio CPF)
    }
