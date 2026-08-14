"""
routers/tokens.py
=================
Token de apresentação — Ticket 24.

ARQUITETURA
-----------
  O token é uma credencial efêmera, persistida e revogável.
  Gerado sob demanda pelo paciente; resolvido pelo dispensador no balcão.

  Fluxo:
    paciente gera token → apresenta QR/código no balcão
    → dispensador resolve → backend retorna protocolo
    → dispensador usa fluxo autenticado normal de dispensação

  O token NÃO executa custódia nem dispensação.
  NÃO entra no ledger clínico (prescricao_eventos).
  Cada resolução é registrada em tokens_apresentacao_usos (audit log técnico).

DECISÕES ARQUITETURAIS (Ticket 24)
-----------------------------------
  1. Persistido   — armazenado no banco para revogabilidade e auditoria
  2. Sob demanda  — gerado pelo paciente (JWT sub=cpf)
  3. Auxiliar     — não altera estados nem máquina de custódia
  4. Multiuso     — válido até expirar, ser revogado ou prescrição encerrar
  5. QR + código  — QR é UX primária; código curto é fallback
  6. Aberto       — qualquer dispensador autenticado resolve (sem CNPJ fixo)
  7. Escopo único — 'apresentacao' (campo preparado para evolução)

ROTAS
-----
  POST   /tokens/apresentacao                      ← paciente gera
  GET    /tokens/apresentacao                      ← paciente lista ativos
  DELETE /tokens/apresentacao/{codigo_curto}       ← paciente revoga
  GET    /tokens/apresentacao/{codigo_curto}/qr    ← paciente obtém QR PNG
  POST   /tokens/apresentacao/resolver             ← dispensador resolve
"""

from __future__ import annotations

import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database import get_conn
from app.database_tx import get_tx


router = APIRouter(prefix="/tokens", tags=["tokens_apresentacao"])


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Alfabeto Crockford: sem I, L, O, U (evita confusão visual 0/O, 1/I, 5/S…)
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_CODIGO_LEN          = 8
_VALIDADE_MIN_PADRAO = 60
_VALIDADE_MAX_MIN    = 120

# Estados que ainda permitem dispensação
_ESTADOS_DISPENSAVEIS = {
    "pendente",
    "transferida_paciente",
    "em_custodia",
    "parcialmente_dispensada",
}

# Estados terminais de prescrição (não permitem mais dispensação)
_ESTADOS_TERMINAIS_PRESCRICAO = {
    "dispensada",
    "cancelada",
    "expirada",
    "encerrada_localmente",
}

# Ticket 44 — estados de item que ainda permitem resolução de token atomizado
_ESTADOS_ITEM_CIRCULAVEIS_TOKEN = frozenset({
    "pendente",
    "em_custodia",          # item já em farmácia — resolução ainda válida
    "devolvido_paciente",   # abandono de compra — item disponível novamente
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _expira_em_iso(minutos: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutos)).isoformat()


def _esta_expirado(expira_em: str) -> bool:
    try:
        dt = datetime.fromisoformat(expira_em)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > dt
    except (ValueError, TypeError):
        return True


def _gerar_codigo_curto(conn, tentativas: int = 5) -> str:
    """
    Gera código único de 8 chars Crockford.
    Tenta até `tentativas` vezes para evitar colisão (extremamente rara).
    """
    for _ in range(tentativas):
        codigo = "".join(secrets.choice(_CROCKFORD) for _ in range(_CODIGO_LEN))
        existe = conn.execute(
            "SELECT 1 FROM tokens_apresentacao WHERE codigo_curto = ?", (codigo,)
        ).fetchone()
        if not existe:
            return codigo
    raise RuntimeError("Não foi possível gerar código único após várias tentativas.")


def _gerar_qr_png(conteudo: str) -> bytes:
    """Gera imagem QR Code PNG em memória."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(conteudo)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _registrar_uso(
    conn,
    token_id: Optional[int],
    codigo_curto: str,
    resultado: str,
    dispensador_cns: Optional[str] = None,
    cnpj_estabelecimento: Optional[str] = None,
    protocolo_resolvido: Optional[str] = None,
) -> None:
    """Registra tentativa de resolução em tokens_apresentacao_usos."""
    conn.execute(
        """
        INSERT INTO tokens_apresentacao_usos
            (token_id, codigo_curto, dispensador_cns, cnpj_estabelecimento,
             resultado, protocolo_resolvido, criado_em)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            token_id,
            codigo_curto,
            dispensador_cns,
            cnpj_estabelecimento,
            resultado,
            protocolo_resolvido,
            _agora_iso(),
        ),
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GerarTokenIn(BaseModel):
    protocolo:         str
    validade_minutos:  int = _VALIDADE_MIN_PADRAO

    @field_validator("validade_minutos")
    @classmethod
    def validade_no_limite(cls, v: int) -> int:
        if not (1 <= v <= _VALIDADE_MAX_MIN):
            raise ValueError(
                f"validade_minutos deve estar entre 1 e {_VALIDADE_MAX_MIN}."
            )
        return v


class ResolverTokenIn(BaseModel):
    codigo_curto:         str
    cnpj_estabelecimento: Optional[str] = None

    @field_validator("codigo_curto")
    @classmethod
    def codigo_normalizado(cls, v: str) -> str:
        return v.strip().upper()


# TICKET-J.6.b — que objeto sanitário é este protocolo, se pertencer ao paciente?
# Cada objeto guarda o dono por caminho próprio; a consulta é escrita por extenso
# em vez de generalizada, porque generalizar aqui exigiria uma tabela de metadados
# que o projeto não tem — e inventá-la para uma mensagem de erro seria caro.
_OBJETOS_DO_PACIENTE = (
    ("atestado",         "SELECT 1 FROM atestados a JOIN pacientes pa ON pa.id = a.paciente_id "
                         "WHERE a.protocolo = ? AND pa.cpf = ?"),
    ("pedido de exame",  "SELECT 1 FROM pedidos_exame pe JOIN pacientes pa ON pa.id = pe.paciente_id "
                         "WHERE pe.protocolo = ? AND pa.cpf = ?"),
    ("laudo",            "SELECT 1 FROM laudos l JOIN pacientes pa ON pa.id = l.paciente_id "
                         "WHERE l.protocolo = ? AND pa.cpf = ?"),
)


def _tipo_de_objeto_do_paciente(conn, proto: str, cpf: str) -> str | None:
    """Rótulo do objeto sanitário, ou None se não for do paciente autenticado."""
    for rotulo, sql in _OBJETOS_DO_PACIENTE:
        try:
            if conn.execute(sql, (proto, cpf)).fetchone():
                return rotulo
        except Exception:  # noqa: BLE001
            # Tabela ausente em algum ambiente não pode derrubar a emissão do
            # token: isto é enfeite de mensagem, não caminho clínico.
            continue
    return None


# ---------------------------------------------------------------------------
# POST /tokens/apresentacao — paciente gera token
# ---------------------------------------------------------------------------

@router.post(
    "/apresentacao",
    status_code=201,
    summary="Paciente gera token de apresentação",
)
def gerar_token(
    payload: GerarTokenIn,
    usuario=Depends(require_role("paciente")),
):
    """
    Gera um token de apresentação efêmero para a prescrição informada.

    - O paciente deve ser titular da prescrição (CPF do JWT = cpf_paciente).
    - A prescrição deve estar em estado dispensável.
    - Token válido por `validade_minutos` (padrão 60, máximo 120).
    - Multiuso dentro da validade — sem contagem de usos.
    """
    cpf_paciente = usuario["sub"]
    proto = payload.protocolo.strip()
    agora = _agora_iso()

    with get_tx() as conn:
        # Verificar prescrição
        prescricao = conn.execute(
            """
            SELECT p.id, p.status, pa.cpf
            FROM prescricoes p
            JOIN pacientes pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ?
            """,
            (proto,),
        ).fetchone()

        if not prescricao:
            # TICKET-J.6.b — o token de apresentação é da RECEITA. Quando o
            # visitante da demo colava o protocolo de um atestado aqui, a
            # resposta era "Prescrição não encontrada" — mensagem que sugere
            # objeto perdido quando o objeto existe e apenas não usa este
            # mecanismo. Dizer o tipo é a diferença entre "sumiu" e "não é aqui".
            #
            # ANTI-LEAK: o tipo só é revelado se o objeto for DO PRÓPRIO paciente
            # autenticado. Para protocolo alheio (ou inexistente) a resposta
            # continua sendo a genérica — nada de confirmar existência a terceiro.
            tipo = _tipo_de_objeto_do_paciente(conn, proto, cpf_paciente)
            if tipo:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Este protocolo é de {tipo}, que não usa token de "
                        "apresentação — o token existe para a receita ser "
                        "apresentada no balcão da farmácia."
                    ),
                )
            raise HTTPException(status_code=404, detail="Prescrição não encontrada.")

        if prescricao["cpf"] != cpf_paciente:
            raise HTTPException(
                status_code=403,
                detail="Esta prescrição não pertence ao paciente autenticado.",
            )

        if prescricao["status"] in _ESTADOS_TERMINAIS_PRESCRICAO:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Prescrição com status '{prescricao['status']}' "
                    "não aceita novos tokens de apresentação."
                ),
            )

        codigo = _gerar_codigo_curto(conn)
        expira_em = _expira_em_iso(payload.validade_minutos)

        conn.execute(
            """
            INSERT INTO tokens_apresentacao
                (codigo_curto, protocolo, paciente_cpf, escopo,
                 status, expira_em, criado_em)
            VALUES (?, ?, ?, 'apresentacao', 'ativo', ?, ?)
            """,
            (codigo, proto, cpf_paciente, expira_em, agora),
        )
        return {
            "codigo_curto": codigo,
            "protocolo":    proto,
            "escopo":       "apresentacao",
            "status":       "ativo",
            "expira_em":    expira_em,
            "criado_em":    agora,
            "aviso": (
                "Apresente este código ou o QR Code no balcão da farmácia. "
                f"Válido por {payload.validade_minutos} minutos."
            ),
        }


# ---------------------------------------------------------------------------
# GET /tokens/apresentacao — paciente lista tokens ativos
# ---------------------------------------------------------------------------

@router.get(
    "/apresentacao",
    summary="Paciente lista seus tokens de apresentação ativos",
)
def listar_tokens(
    usuario=Depends(require_role("paciente")),
):
    """
    Lista tokens de apresentação ativos do paciente autenticado.
    Tokens expirados são marcados automaticamente na resposta (sem alterar o banco).
    """
    cpf = usuario["sub"]
    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT id, codigo_curto, protocolo, escopo, status, expira_em, criado_em
            FROM tokens_apresentacao
            WHERE paciente_cpf = ?
              AND status = 'ativo'
            ORDER BY criado_em DESC
            """,
            (cpf,),
        ).fetchall()

    resultado = []
    agora = _agora_iso()
    for r in rows:
        expirado = _esta_expirado(r["expira_em"])
        resultado.append({
            "codigo_curto": r["codigo_curto"],
            "protocolo":    r["protocolo"],
            "escopo":       r["escopo"],
            "status":       "expirado" if expirado else r["status"],
            "expira_em":    r["expira_em"],
            "criado_em":    r["criado_em"],
        })

    return {"tokens": resultado, "total": len(resultado)}


# ---------------------------------------------------------------------------
# DELETE /tokens/apresentacao/{codigo_curto} — paciente revoga token
# ---------------------------------------------------------------------------

@router.delete(
    "/apresentacao/{codigo_curto}",
    summary="Paciente revoga token de apresentação",
)
def revogar_token(
    codigo_curto: str,
    usuario=Depends(require_role("paciente")),
):
    """
    Revoga um token de apresentação.
    Apenas o paciente titular pode revogar.
    Tokens já expirados ou revogados também retornam sucesso (idempotente).
    """
    cpf = usuario["sub"]
    codigo = codigo_curto.strip().upper()
    agora = _agora_iso()

    with get_tx() as conn:
        token = conn.execute(
            "SELECT id, status, paciente_cpf FROM tokens_apresentacao WHERE codigo_curto = ?",
            (codigo,),
        ).fetchone()

        if not token:
            raise HTTPException(status_code=404, detail="Token não encontrado.")

        if token["paciente_cpf"] != cpf:
            raise HTTPException(
                status_code=403,
                detail="Apenas o titular pode revogar este token.",
            )

        if token["status"] in ("expirado", "revogado"):
            return {"detail": "Token já inativo.", "status": token["status"]}

        conn.execute(
            """
            UPDATE tokens_apresentacao
            SET status = 'revogado', revogado_em = ?, revogado_por = ?
            WHERE id = ?
            """,
            (agora, cpf, token["id"]),
        )

        return {"detail": "Token revogado com sucesso.", "codigo_curto": codigo}


# ---------------------------------------------------------------------------
# GET /tokens/apresentacao/{codigo_curto}/qr — paciente obtém QR PNG
# ---------------------------------------------------------------------------

@router.get(
    "/apresentacao/{codigo_curto}/qr",
    summary="Paciente obtém QR Code PNG do token",
    response_class=Response,
)
def qr_token(
    codigo_curto: str,
    usuario=Depends(require_role("paciente")),
):
    """
    Retorna imagem PNG do QR Code para o token informado.
    O QR encoda o código curto — o dispensador escaneia e resolve normalmente.
    Apenas o paciente titular pode obter o QR.
    """
    cpf = usuario["sub"]
    codigo = codigo_curto.strip().upper()

    with get_tx() as conn:
        token = conn.execute(
            "SELECT status, expira_em, paciente_cpf FROM tokens_apresentacao WHERE codigo_curto = ?",
            (codigo,),
        ).fetchone()

        if not token:
            raise HTTPException(status_code=404, detail="Token não encontrado.")

        if token["paciente_cpf"] != cpf:
            raise HTTPException(status_code=403, detail="Acesso negado.")

        if token["status"] == "revogado":
            raise HTTPException(status_code=410, detail="Token revogado.")

        if _esta_expirado(token["expira_em"]):
            raise HTTPException(status_code=410, detail="Token expirado.")

        png = _gerar_qr_png(codigo)
        return Response(content=png, media_type="image/png")


# ---------------------------------------------------------------------------
# POST /tokens/apresentacao/resolver — dispensador resolve token
# ---------------------------------------------------------------------------

@router.post(
    "/apresentacao/resolver",
    summary="Dispensador resolve token → retorna protocolo",
)
def resolver_token(
    payload: ResolverTokenIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Resolve um código de apresentação e retorna o protocolo da prescrição.

    **Regras:**
    - Token deve estar ativo e dentro da validade.
    - Prescrição associada deve ter itens pendentes de dispensação.
    - Toda tentativa (sucesso ou falha) é registrada em tokens_apresentacao_usos.

    **O que este endpoint NÃO faz:**
    - Não executa dispensação.
    - Não altera custódia.
    - Não muda o estado da prescrição.
    - Não invalida o token (multiuso dentro da validade).

    O dispensador usa o protocolo retornado para carregar a prescrição
    e então usar o fluxo normal autenticado de dispensação.
    """
    codigo = payload.codigo_curto
    dispensador_cns   = usuario.get("sub")
    cnpj_estab        = payload.cnpj_estabelecimento

    conn = get_conn()
    try:
        token = conn.execute(
            """
            SELECT id, codigo_curto, protocolo, status, expira_em, item_id
            FROM tokens_apresentacao
            WHERE codigo_curto = ?
            """,
            (codigo,),
        ).fetchone()

        # --- Token não encontrado ---
        if not token:
            _registrar_uso(
                conn, None, codigo, "nao_encontrado",
                dispensador_cns, cnpj_estab,
            )
            conn.commit()
            raise HTTPException(status_code=404, detail="Token não encontrado.")

        token_id = token["id"]
        proto    = token["protocolo"]

        # --- Token revogado ---
        if token["status"] == "revogado":
            _registrar_uso(
                conn, token_id, codigo, "revogado",
                dispensador_cns, cnpj_estab,
            )
            conn.commit()
            raise HTTPException(status_code=410, detail="Token revogado pelo paciente.")

        # --- Token expirado ---
        if _esta_expirado(token["expira_em"]):
            # Atualiza status no banco (lazy expiration)
            conn.execute(
                "UPDATE tokens_apresentacao SET status = 'expirado' WHERE id = ?",
                (token_id,),
            )
            _registrar_uso(
                conn, token_id, codigo, "expirado",
                dispensador_cns, cnpj_estab,
            )
            conn.commit()
            raise HTTPException(
                status_code=410,
                detail="Token expirado. Solicite ao paciente que gere um novo token.",
            )

        # --- Verificar estado da prescrição ---
        prescricao = conn.execute(
            """
            SELECT p.status,
                   pa.nome  AS nome_paciente,
                   pr.nome  AS nome_prescritor
            FROM prescricoes p
            JOIN pacientes   pa ON pa.id = p.paciente_id
            JOIN prescritores pr ON pr.id = p.prescritor_id
            WHERE p.protocolo = ?
            """,
            (proto,),
        ).fetchone()

        if not prescricao:
            _registrar_uso(
                conn, token_id, codigo, "prescricao_encerrada",
                dispensador_cns, cnpj_estab,
            )
            conn.commit()
            raise HTTPException(status_code=404, detail="Prescrição não encontrada.")

        if prescricao["status"] in _ESTADOS_TERMINAIS_PRESCRICAO:
            _registrar_uso(
                conn, token_id, codigo, "prescricao_encerrada",
                dispensador_cns, cnpj_estab,
            )
            conn.commit()
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Prescrição com status '{prescricao['status']}' "
                    "não possui itens pendentes para dispensação."
                ),
            )

        # ── Ticket 44: token de item (circulação atomizada) ──────────────
        if token["item_id"] is not None:
            item = conn.execute(
                """
                SELECT id, nome_medicamento, concentracao, quantidade,
                       unidade_quantidade, forma_farmaceutica, posologia, status_item
                FROM prescricao_itens
                WHERE id = ?
                  AND prescricao_id = (SELECT id FROM prescricoes WHERE protocolo = ?)
                """,
                (token["item_id"], proto),
            ).fetchone()

            if not item:
                _registrar_uso(
                    conn, token_id, codigo, "item_nao_encontrado",
                    dispensador_cns, cnpj_estab, proto,
                )
                conn.commit()
                raise HTTPException(
                    status_code=404,
                    detail="Item da prescrição referenciado pelo token não encontrado.",
                )

            if item["status_item"] not in _ESTADOS_ITEM_CIRCULAVEIS_TOKEN:
                _registrar_uso(
                    conn, token_id, codigo, "item_terminal",
                    dispensador_cns, cnpj_estab, proto,
                )
                conn.commit()
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Item '{item['nome_medicamento']}' com status '{item['status_item']}' "
                        "não está disponível para circulação. "
                        "O item pode já ter sido dispensado, cancelado ou devolvido ao prescritor."
                    ),
                )

            _registrar_uso(
                conn, token_id, codigo, "resolvido_item",
                dispensador_cns, cnpj_estab, proto,
            )
            conn.commit()

            return {
                "protocolo":           proto,
                "modo":                "item",
                "circulacao_atomizada": True,
                "status_prescricao":   prescricao["status"],
                "item": {
                    "item_id":            item["id"],
                    "nome_medicamento":   item["nome_medicamento"],
                    "concentracao":       item["concentracao"],
                    "quantidade":         item["quantidade"],
                    "unidade_quantidade": item["unidade_quantidade"],
                    "forma_farmaceutica": item["forma_farmaceutica"],
                    "posologia":          item["posologia"],
                    "status_item":        item["status_item"],
                },
                # Privacidade: os demais itens da prescrição NÃO são expostos.
                "aviso": (
                    "Token de item atomizado. Prossiga com a dispensação do item específico. "
                    "Os demais itens da prescrição não são visíveis por este token."
                ),
            }
        # ── Fluxo original: token de prescrição inteira ───────────────

        # --- Buscar itens pendentes ---
        itens = conn.execute(
            """
            SELECT nome_medicamento, concentracao, quantidade,
                   status_item, forma_farmaceutica, unidade_quantidade
            FROM prescricao_itens
            WHERE prescricao_id = (SELECT id FROM prescricoes WHERE protocolo = ?)
              AND status_item NOT IN ('dispensado','cancelado','estornado','encerrado_fisico','devolvido_prescritor')
            """,
            (proto,),
        ).fetchall()

        # --- Registrar uso bem-sucedido ---
        _registrar_uso(
            conn, token_id, codigo, "resolvido",
            dispensador_cns, cnpj_estab, proto,
        )
        conn.commit()

        return {
            "protocolo":         proto,
            "modo":              "prescricao",
            "circulacao_atomizada": False,
            "status_prescricao": prescricao["status"],
            "nome_paciente":     prescricao["nome_paciente"],
            "nome_prescritor":   prescricao["nome_prescritor"],
            "itens_pendentes":   [dict(i) for i in itens],
            "total_pendentes":   len(itens),
            "aviso": (
                "Protocolo resolvido via token de apresentação. "
                "Prossiga com o fluxo normal de dispensação autenticada."
            ),
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
