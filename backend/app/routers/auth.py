from __future__ import annotations

import json
import os
import secrets
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import require_role
from app.auth.jwt import criar_access_token
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.states import ESTADOS_TERMINAIS_PRESCRICAO
from app.domain.states_exame import ESTADOS_TERMINAIS_PEDIDO_EXAME
from app.instance import get_instance_id_conn
from app.utils.helpers import normalize_cnpj, normalize_cpf

router = APIRouter()


# TICKET-6 P1#2 — em DEMO_MODE, OTP legado devolve 403 demo_mode_ativo.
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

class SolicitarCodigoIn(BaseModel):
    cpf: str
    telefone: Optional[str] = None  # kept for backward compat, not required


class ValidarCodigoIn(BaseModel):
    cpf: str
    codigo: str


# ---------------------------------------------------------------------------
# POST /paciente/enviar-codigo
# ---------------------------------------------------------------------------

@router.post("/paciente/enviar-codigo")
def enviar_codigo(body: SolicitarCodigoIn, _demo=Depends(_reject_if_demo)):
    cpf = normalize_cpf(body.cpf)

    if not cpf:
        raise HTTPException(status_code=400, detail="CPF inválido ou não informado.")

    codigo = str(secrets.randbelow(900000) + 100000)
    agora = datetime.utcnow().isoformat()
    expiracao = (datetime.utcnow() + timedelta(minutes=5)).isoformat()

    with get_tx() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO pacientes (cpf, nome, created_at, updated_at, ativo)
            VALUES (?, 'PACIENTE', ?, ?, false)
            """,
            (cpf, agora, agora),
        )
        conn.execute(
            """
            INSERT INTO codigos_login (cpf, codigo, expiracao, usado, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (cpf, codigo, expiracao, agora),
        )

    # Print OTP no stdout APENAS em dev/test — em produção (Render),
    # OTP nunca aparece nos logs. Bloqueador de segurança CODEX 2026-05-06.
    # SEM default: PICSAUDE_ENV ausente é tratado como "não-dev/test",
    # então deploy sem env configurada NÃO vaza OTP.
    _cpf_mascarado = f"*******{cpf[-4:]}" if len(cpf) >= 4 else "***"
    if os.getenv("PICSAUDE_ENV") in ("dev", "test"):
        print(f"\n[PICSAUDE-OTP] CPF={_cpf_mascarado} | CODIGO={codigo} | Expira em 5min (apenas dev)\n")

    return {"ok": True, "mensagem": "Código de verificação gerado. Em produção será enviado por SMS."}


# ---------------------------------------------------------------------------
# POST /paciente/validar-codigo  → retorna JWT com role="paciente"
# ---------------------------------------------------------------------------

@router.post("/paciente/validar-codigo")
def validar_codigo(body: ValidarCodigoIn, _demo=Depends(_reject_if_demo)):
    cpf    = normalize_cpf(body.cpf)
    codigo = (body.codigo or "").strip()

    if not cpf or not codigo:
        raise HTTPException(status_code=400, detail="CPF e código são obrigatórios.")

    with get_tx() as conn:
        agora_check = datetime.utcnow().isoformat()
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
            (cpf, codigo, agora_check),
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
    return {"ok": True, "access_token": access_token, "token_type": "bearer", "nome": nome, "cpf": cpf}


# ---------------------------------------------------------------------------
# GET /paciente/prescricoes  — carteira digital do cidadão
# ---------------------------------------------------------------------------

@router.get("/paciente/prescricoes")
def listar_prescricoes(usuario=Depends(require_role("paciente"))):
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                p.id,
                p.protocolo,
                p.status,
                p.tipo_emissao,
                p.data_emissao,
                pr.nome AS prescritor_nome
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE pa.cpf = ?
              AND p.tipo_emissao != 'fisica'
            ORDER BY p.id DESC
            """,
            (cpf,),
        ).fetchall()

        prescricoes = []
        for row in rows:
            itens = conn.execute(
                """
                SELECT nome_medicamento, concentracao, quantidade, posologia, status_item
                FROM prescricao_itens
                WHERE prescricao_id = ?
                """,
                (row["id"],),
            ).fetchall()
            prescricoes.append({
                "protocolo":      row["protocolo"],
                "status":         row["status"],
                "tipo_emissao":   row["tipo_emissao"],
                "data_emissao":   row["data_emissao"],
                "prescritor_nome": row["prescritor_nome"],
                "itens": [dict(i) for i in itens],
            })

    _EM_POSSE   = {"transferida_paciente", "pendente"}
    _HISTORICO  = {"em_custodia", "parcialmente_dispensada", "dispensada",
                   "cancelada", "expirada"}

    return {
        "posse":    [p for p in prescricoes if p["status"] in _EM_POSSE],
        "historico": [p for p in prescricoes if p["status"] in _HISTORICO],
    }


# ---------------------------------------------------------------------------
# POST /paciente/prescricoes/{proto}/transferir-farmacia
# paciente → dispensador
# ---------------------------------------------------------------------------

@router.post("/paciente/prescricoes/{proto}/transferir-farmacia", status_code=201)
def transferir_farmacia(proto: str, body: dict, usuario=Depends(require_role("paciente"))):
    cpf  = usuario["sub"]
    cnpj = normalize_cnpj(body.get("cnpj_farmacia", ""))

    if not cnpj or len(cnpj) != 14:
        raise HTTPException(status_code=400, detail="cnpj_farmacia inválido")

    agora = datetime.utcnow().isoformat()
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.status
            FROM prescricoes p
            JOIN pacientes pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ? AND pa.cpf = ?
            """,
            (proto, cpf),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404,
                                detail="Prescrição não encontrada ou não pertence a este paciente")

        if row["status"] != "transferida_paciente":
            raise HTTPException(status_code=409,
                                detail=f"Prescrição não está sob sua custódia (status: {row['status']})")

        pid = row["id"]

        # Encerra custódia ativa (nível prescrição)
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (agora, pid),
        )
        # Abre custódia do dispensador
        # Ticket 4D.1 (P1.2): fix de schema — coluna real é
        # `transferida_em` (não `iniciada_em`); `created_at` é NOT NULL
        # sem server_default. Bug latente que falhava transacionalmente
        # antes desta correção.
        conn.execute(
            """
            INSERT INTO prescricao_custodia
                   (prescricao_id, item_id, detentor_tipo, detentor_id,
                    transferida_em, encerrada_em, motivo, created_at)
            VALUES (?, NULL, 'dispensador', ?,
                    ?, NULL, 'Transferência pelo cidadão via app', ?)
            """,
            (pid, cnpj, agora, agora),
        )
        conn.execute(
            "UPDATE prescricoes SET status = 'em_custodia', updated_at = ? WHERE id = ?",
            (agora, pid),
        )
        # Ticket 4D.1: substituído INSERT manual divergente
        # (`dados_json`/`criado_em` violavam ator_tipo NOT NULL).
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=pid,
            tipo_evento="custodia_transferida",
            instance_id=instance_id,
            payload={
                "de": "paciente",     "de_id":  cpf,
                "para": "dispensador", "para_id": cnpj,
                "origem": "cidadao_app",
            },
            ator_tipo="paciente",
            ator_id=cpf,
        )

    return {"ok": True, "protocolo": proto, "status": "em_custodia"}


# ---------------------------------------------------------------------------
# POST /paciente/prescricoes/{proto}/devolver-prescritor
# paciente → prescritor  (erro identificado pelo paciente)
# ---------------------------------------------------------------------------

@router.post("/paciente/prescricoes/{proto}/devolver-prescritor", status_code=201)
def devolver_prescritor(proto: str, body: dict, usuario=Depends(require_role("paciente"))):
    cpf    = usuario["sub"]
    motivo = body.get("motivo") or "Devolução voluntária pelo cidadão"

    agora = datetime.utcnow().isoformat()
    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT p.id, p.status, pr.cns AS prescritor_cns
            FROM prescricoes p
            JOIN prescritores pr ON pr.id = p.prescritor_id
            JOIN pacientes    pa ON pa.id = p.paciente_id
            WHERE p.protocolo = ? AND pa.cpf = ?
            """,
            (proto, cpf),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Prescrição não encontrada")

        if row["status"] not in ("transferida_paciente", "pendente"):
            raise HTTPException(status_code=409,
                                detail=f"Prescrição com status '{row['status']}' não pode ser devolvida")

        pid  = row["id"]
        cns  = row["prescritor_cns"]

        # Encerra custódia ativa
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (agora, pid),
        )
        # Abre custódia do prescritor
        # Ticket 4D.1 (P1.2): fix de schema (mesmo bug do site
        # transferir-farmacia — `iniciada_em` → `transferida_em` +
        # `created_at`).
        conn.execute(
            """
            INSERT INTO prescricao_custodia
                   (prescricao_id, item_id, detentor_tipo, detentor_id,
                    transferida_em, encerrada_em, motivo, created_at)
            VALUES (?, NULL, 'prescritor', ?,
                    ?, NULL, ?, ?)
            """,
            (pid, cns, agora, motivo, agora),
        )
        # Itens pendentes voltam ao prescritor
        conn.execute(
            """
            UPDATE prescricao_itens
               SET status_item = 'devolvido_prescritor', updated_at = ?
             WHERE prescricao_id = ? AND status_item = 'pendente'
            """,
            (agora, pid),
        )
        conn.execute(
            "UPDATE prescricoes SET status = 'pendente', updated_at = ? WHERE id = ?",
            (agora, pid),
        )
        # Ticket 4D.1: substituído INSERT manual divergente.
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=pid,
            tipo_evento="custodia_transferida",
            instance_id=instance_id,
            payload={
                "de": "paciente",      "de_id":  cpf,
                "para": "prescritor",  "para_id": cns,
                "motivo": motivo,
                "origem": "cidadao_app",
            },
            ator_tipo="paciente",
            ator_id=cpf,
        )

    return {"ok": True, "protocolo": proto, "status": "pendente"}


# ---------------------------------------------------------------------------
# GET /paciente/prescricoes/expirando  — alertas de renovação
# ---------------------------------------------------------------------------

# Estados não-terminais que o cidadão pode enxergar
_ESTADOS_ATIVOS = frozenset({
    "pendente",
    "transferida_paciente",
    "em_custodia",
    "parcialmente_dispensada",
}) - ESTADOS_TERMINAIS_PRESCRICAO   # garante coerência com o domínio


@router.get("/paciente/prescricoes/expirando")
def prescricoes_expirando(
    dias: int = Query(default=7, ge=1, le=90,
                      description="Janela em dias a partir de hoje (padrão: 7)"),
    usuario=Depends(require_role("paciente")),
):
    """
    Retorna prescrições não-terminais do cidadão cuja data_validade
    está entre hoje e hoje + `dias`.

    - CPF extraído do JWT (não aceito via query param).
    - Prescrições expiradas ou em estado terminal são ignoradas.
    - Campo `dias_restantes` calculado no servidor.
    """
    cpf   = usuario["sub"]
    hoje  = date.today()
    limite = hoje + timedelta(days=dias)

    placeholders = ",".join("?" * len(_ESTADOS_ATIVOS))
    sql = f"""
        SELECT
            p.protocolo,
            p.status,
            p.tipo_emissao,
            p.data_validade,
            COUNT(i.id)                                                AS total_itens,
            SUM(CASE WHEN i.status_item = 'dispensado' THEN 1 ELSE 0 END) AS itens_dispensados
        FROM prescricoes p
        JOIN prescricao_itens i ON i.prescricao_id = p.id
        JOIN pacientes pa       ON pa.id = p.paciente_id
        WHERE pa.cpf = ?
          AND p.data_validade IS NOT NULL
          AND p.data_validade >= ?
          AND p.data_validade <= ?
          AND p.status IN ({placeholders})
        GROUP BY p.id
        ORDER BY p.data_validade ASC
    """

    params = [cpf, hoje.isoformat(), limite.isoformat(), *sorted(_ESTADOS_ATIVOS)]

    with get_tx() as conn:
        rows = conn.execute(sql, params).fetchall()

    resultado = []
    for r in rows:
        try:
            validade = date.fromisoformat(r["data_validade"][:10])
            dias_restantes = (validade - hoje).days
        except (ValueError, TypeError):
            dias_restantes = None

        resultado.append({
            "protocolo":        r["protocolo"],
            "status":           r["status"],
            "tipo_emissao":     r["tipo_emissao"],
            "data_validade":    r["data_validade"][:10] if r["data_validade"] else None,
            "dias_restantes":   dias_restantes,
            "itens_total":      r["total_itens"],
            "itens_dispensados": r["itens_dispensados"] or 0,
        })

    return resultado


# ---------------------------------------------------------------------------
# GET /paciente/pedidos-exame  — carteira de exames do cidadão
# ---------------------------------------------------------------------------

_EM_POSSE_EXAME   = {"emitido", "agendado"}
_HISTORICO_EXAME  = ESTADOS_TERMINAIS_PEDIDO_EXAME | {"coletado", "em_analise", "resultado_disponivel"}


@router.get("/paciente/pedidos-exame")
def listar_pedidos_exame(usuario=Depends(require_role("paciente"))):
    """
    Retorna os pedidos de exame do paciente autenticado, separados em:
    - posse: pedidos ainda em curso (emitido, agendado)
    - em_andamento: coletado, em_analise, resultado_disponivel
    - historico: encerrados, cancelados, expirados, encerrado_fisico
    """
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                pe.id,
                pe.protocolo,
                pe.status,
                pe.tipo_emissao,
                pe.prioridade,
                pe.data_emissao,
                pe.data_validade,
                pr.nome AS prescritor_nome
            FROM pedidos_exame pe
            JOIN prescritores pr ON pr.id = pe.prescritor_id
            JOIN pacientes    pa ON pa.id = pe.paciente_id
            WHERE pa.cpf = ?
              AND pe.tipo_emissao != 'fisico'
            ORDER BY pe.id DESC
            """,
            (cpf,),
        ).fetchall()

        pedidos = []
        for row in rows:
            itens = conn.execute(
                """
                SELECT nome_exame, codigo_tuss, quantidade, status_item
                FROM pedido_exame_itens
                WHERE pedido_id = ?
                """,
                (row["id"],),
            ).fetchall()
            pedidos.append({
                "protocolo":      row["protocolo"],
                "status":         row["status"],
                "tipo_emissao":   row["tipo_emissao"],
                "prioridade":     row["prioridade"],
                "data_emissao":   row["data_emissao"],
                "data_validade":  row["data_validade"],
                "prescritor_nome": row["prescritor_nome"],
                "itens": [dict(i) for i in itens],
            })

    _EM_ANDAMENTO = {"coletado", "em_analise", "resultado_disponivel"}

    return {
        "posse":        [p for p in pedidos if p["status"] in _EM_POSSE_EXAME],
        "em_andamento": [p for p in pedidos if p["status"] in _EM_ANDAMENTO],
        "historico":    [p for p in pedidos if p["status"] in ESTADOS_TERMINAIS_PEDIDO_EXAME],
    }


# ---------------------------------------------------------------------------
# GET /paciente/laudos  — laudos disponíveis do cidadão
# ---------------------------------------------------------------------------

@router.get("/paciente/laudos")
def listar_laudos(usuario=Depends(require_role("paciente"))):
    """
    Retorna os laudos do paciente autenticado, separados em:
    - disponiveis: liberados e aguardando ciência
    - historico: encerrados, cancelados, expirados, encerrado_fisico
    """
    cpf = usuario["sub"]

    with get_tx() as conn:
        rows = conn.execute(
            """
            SELECT
                l.id,
                l.protocolo,
                l.status,
                l.tipo_emissao,
                l.data_emissao,
                l.data_validade,
                pr.nome AS autor_nome
            FROM laudos l
            JOIN prescritores pr ON pr.id = l.autor_id
            JOIN pacientes    pa ON pa.id = l.paciente_id
            WHERE pa.cpf = ?
              AND l.tipo_emissao != 'fisico'
            ORDER BY l.id DESC
            """,
            (cpf,),
        ).fetchall()

        laudos = []
        for row in rows:
            itens = conn.execute(
                """
                SELECT nome_exame, codigo_tuss, conclusao, status_item
                FROM laudo_itens
                WHERE laudo_id = ?
                """,
                (row["id"],),
            ).fetchall()
            laudos.append({
                "protocolo":     row["protocolo"],
                "status":        row["status"],
                "tipo_emissao":  row["tipo_emissao"],
                "data_emissao":  row["data_emissao"],
                "data_validade": row["data_validade"],
                "autor_nome":    row["autor_nome"],
                "itens":         [dict(i) for i in itens],
            })

    # ciencia_paciente entra aqui para o laudo seguir VISÍVEL ao cidadão após
    # ele dar ciência (estado não-terminal: aguarda ciência do prescritor/encerramento).
    _DISPONIVEIS    = {"liberado", "ciencia_prescritor", "ciencia_paciente"}
    _TERMINAIS_LAUDO = {"encerrado", "cancelado", "expirado", "encerrado_fisico"}

    return {
        "disponiveis": [l for l in laudos if l["status"] in _DISPONIVEIS],
        "historico":   [l for l in laudos if l["status"] in _TERMINAIS_LAUDO],
    }
