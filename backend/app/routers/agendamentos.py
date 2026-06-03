"""
agendamentos.py
===============
Endpoints do módulo de Agendamento — objeto sanitário leve (Ticket 29).

Classificação: objeto sanitário leve.
  - Tem identidade própria (protocolo UUID)
  - Tem máquina de estados (states_agendamento.py)
  - Tem ledger (agendamento_eventos)
  - SEM custódia (compromisso bilateral — sem transferência de posse)
  - SEM assinatura/hash (não é documento clínico)

Integração com Pedido de Exame:
  - Criar agendamento  → itens pendente  → agendado
  - Realizar           → itens agendado  → coletado  [simplificação MVP]
  - Cancelar / falta   → itens agendado  → pendente

Nota MVP obrigatória (comentada no código):
  'realizado' implica 'coletado'. Em versões futuras pode haver separação
  entre comparecimento e coleta efetiva.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.domain.outbox import registrar_outbox
from app.instance import get_instance_id_conn
from app.domain.states_agendamento import (
    ESTADOS_TERMINAIS_AGENDAMENTO,
    validar_transicao,
    eh_terminal,
)
from app.domain.states_exame import derivar_status_pedido
from app.utils.helpers import normalize_cnpj, _assert_or_403, _normalizar_identidade_jwt

router = APIRouter(tags=["agendamentos"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AgendarIn(BaseModel):
    pedido_protocolo:  str
    data_hora:         str            # ISO 8601 datetime
    org_id:            str
    unidade_id:        str
    tipo_agendamento:  str = "exame"
    local_texto:       Optional[str] = None
    observacao:        Optional[str] = None

    @field_validator("org_id", "unidade_id")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("org_id e unidade_id são obrigatórios e não podem ser vazios.")
        return v.strip()

    @field_validator("tipo_agendamento")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in {"exame"}:
            raise ValueError("tipo_agendamento deve ser 'exame' (MVP).")
        return v


class RemarcarIn(BaseModel):
    data_hora:         str
    org_id:            Optional[str] = None      # se None, mantém o original
    unidade_id:        Optional[str] = None      # se None, mantém o original
    observacao:        Optional[str] = None

    @field_validator("data_hora")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("data_hora é obrigatório.")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_agendamento_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM agendamentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Agendamento '{protocolo}' não encontrado.")
    return dict(row)


# ---------------------------------------------------------------------------
# TICKET-5C-BIS-C §6 — ownership local (4 resolvers + asserts).
# Reusa o Helper 1 global `_assert_or_403`. O prestador (role `dispensador`) é
# INSTITUCIONAL: liga-se ao agendamento por `org_id`, resolvido de
# `prestadores.cnpj → org_id` (two-hop, fail-closed, org-level — §D1/D2).
# `criado_por` é informativo e NUNCA entra em ownership (§D6).
# ---------------------------------------------------------------------------

def _cns_prescritor_de_pedido(conn, pedido_id: int) -> str | None:
    row = conn.execute(
        "SELECT pr.cns FROM pedidos_exame pe JOIN prescritores pr ON pr.id = pe.prescritor_id "
        "WHERE pe.id = ?", (pedido_id,),
    ).fetchone()
    return row["cns"] if row else None


def _cpf_paciente_de_pedido(conn, pedido_id: int) -> str | None:
    row = conn.execute(
        "SELECT pa.cpf FROM pedidos_exame pe JOIN pacientes pa ON pa.id = pe.paciente_id "
        "WHERE pe.id = ?", (pedido_id,),
    ).fetchone()
    return row["cpf"] if row else None


def _org_id_ag(conn, protocolo: str) -> str | None:
    row = conn.execute(
        "SELECT org_id FROM agendamentos WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    return row["org_id"] if row else None


def _org_id_do_dispensador(conn, cnpj_norm: str) -> str | None:
    # §D1/D2 — two-hop fail-closed: prestadores.cnpj (gravado cru) → org_id.
    # Normaliza READ-SIDE; só prestador ativo; org único (0 ou >1 ambíguo → None
    # → 403). Sem JWT carregando unidade_id, o vínculo é no nível da ORG.
    #
    # FAIL-CLOSED institucional: o schema org_id de prestadores (Ticket 30) NÃO
    # está migrado no PostgreSQL/prod hoje (só existe via init_tables/SQLite) —
    # ver TICKET-5C-BIS-C.1. Enquanto ausente, a query falha e QUALQUER
    # dispensador é negado (None → 403). É o comportamento seguro do §D1; a
    # resolução positiva só ativa quando a migration institucional existir.
    if len(cnpj_norm) != 14:
        return None
    try:
        rows = conn.execute(
            "SELECT org_id, cnpj FROM prestadores WHERE cnpj IS NOT NULL AND ativo = 1"
        ).fetchall()
    except Exception:
        return None  # schema institucional ausente → fail-closed
    orgs = {r["org_id"] for r in rows if normalize_cnpj(r["cnpj"]) == cnpj_norm}
    return orgs.pop() if len(orgs) == 1 else None


def _assert_ag_owner(conn, ag: dict, papel: str, ident: str) -> None:
    """Ownership sobre um agendamento existente (endpoints 2,4,5,6,7,8)."""
    if papel == "prescritor":
        cond = ident == _cns_prescritor_de_pedido(conn, ag["pedido_id"])
        msg = "Este agendamento pertence a outro prescritor."
    elif papel == "paciente":
        cond = ident == _cpf_paciente_de_pedido(conn, ag["pedido_id"])
        msg = "Este agendamento pertence a outro paciente."
    elif papel == "dispensador":
        org = _org_id_do_dispensador(conn, ident)
        cond = org is not None and org == _org_id_ag(conn, ag["protocolo"])
        msg = "Agendamento sob responsabilidade de outro prestador."
    else:
        cond, msg = False, "Papel sem vínculo com este agendamento."
    _assert_or_403(cond, codigo="nao_e_dono_do_agendamento", mensagem=msg)


def _assert_pedido_owner_criar(conn, pedido: dict, papel: str, ident: str, payload_org: str) -> None:
    """Ownership sobre o PEDIDO ao criar agendamento (endpoint 1, §D3)."""
    if papel == "prescritor":
        cond = ident == _cns_prescritor_de_pedido(conn, pedido["id"])
    elif papel == "paciente":
        cond = ident == _cpf_paciente_de_pedido(conn, pedido["id"])
    elif papel == "dispensador":
        org = _org_id_do_dispensador(conn, ident)
        cond = org is not None and org == payload_org
    else:
        cond = False
    _assert_or_403(
        cond, codigo="nao_e_dono_do_pedido",
        mensagem="Você não tem vínculo com o pedido deste agendamento.",
    )


def _get_pedido_por_protocolo(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pedido de exame '{protocolo}' não encontrado.")
    return dict(row)


def _gravar_evento_agendamento(conn, agendamento_id: int, evento: str,
                                payload: dict, agora: str,
                                *,
                                instance_id: str,
                                ag_context: dict | None = None) -> None:
    """Insere evento no ledger de agendamentos. Nunca recebe UPDATE/DELETE.

    Ticket 4D.2: helper delega para ``registrar_evento_ledger`` (escopo
    helper único + drift de nomenclatura encapsulado em ``_LEDGER_SCHEMA``,
    onde ``agendamento_eventos`` é outlier com coluna ``evento``/``payload``).
    ``instance_id`` é parâmetro keyword-only obrigatório — caller obtém
    via ``get_instance_id_conn(conn)`` uma vez por transação e repassa.

    Se ``ag_context`` for fornecido (dict com 'protocolo', 'org_id',
    'unidade_id'), espelha o evento no outbox de publicação externa
    (G4A) com o mesmo ``instance_id`` — preserva correspondência
    forense entre ledger e outbox.
    """
    registrar_evento_ledger(
        conn,
        objeto_tipo="agendamento",
        objeto_id=agendamento_id,
        tipo_evento=evento,
        instance_id=instance_id,
        payload=payload,
    )
    if ag_context:
        registrar_outbox(
            conn, evento, "agendamento",
            ag_context.get("protocolo", ""),
            payload,
            org_id=ag_context.get("org_id"),
            unidade_id=ag_context.get("unidade_id"),
            instance_id=instance_id,
        )


def _itens_ativos_do_pedido(conn, pedido_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM pedido_exame_itens WHERE pedido_id = ?", (pedido_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _recalcular_status_pedido(conn, pedido_id: int, agora: str) -> str:
    itens = _itens_ativos_do_pedido(conn, pedido_id)
    novo_status = derivar_status_pedido([i["status_item"] for i in itens])
    conn.execute(
        "UPDATE pedidos_exame SET status = ? WHERE id = ?",
        (novo_status, pedido_id),
    )
    return novo_status


def _montar_payload_evento(ag: dict) -> dict:
    return {
        "agendamento_id":  ag["id"],
        "pedido_id":       ag["pedido_id"],
        "org_id":          ag["org_id"],
        "unidade_id":      ag["unidade_id"],
        "data_hora":       ag["data_hora"],
    }


def _serializar_agendamento(conn, ag: dict) -> dict:
    """Monta resposta enriquecida com dados do pedido."""
    pedido = conn.execute(
        "SELECT protocolo, status FROM pedidos_exame WHERE id = ?", (ag["pedido_id"],)
    ).fetchone()
    return {
        "protocolo":          ag["protocolo"],
        "status":             ag["status"],
        "tipo_agendamento":   ag["tipo_agendamento"],
        "data_hora":          ag["data_hora"],
        "org_id":             ag["org_id"],
        "unidade_id":         ag["unidade_id"],
        "local_texto":        ag["local_texto"],
        "observacao":         ag["observacao"],
        "tipo_emissao":       ag["tipo_emissao"],
        "origem_agendamento_id": ag["origem_agendamento_id"],
        "criado_por":         ag["criado_por"],
        "criado_em":          ag["criado_em"],
        "pedido_protocolo":   pedido["protocolo"] if pedido else None,
        "pedido_status":      pedido["status"] if pedido else None,
    }


# ---------------------------------------------------------------------------
# POST /agendamentos — criar
# ---------------------------------------------------------------------------

@router.post("/agendamentos", status_code=201)
def criar_agendamento(
    payload: AgendarIn,
    usuario=Depends(require_role("prescritor", "paciente", "admin", "dispensador")),  # dispensador = clínica/lab MVP
):
    """
    Cria um agendamento vinculado a um pedido de exame.

    - Valida existência do pedido
    - Impede agendamento duplicado ativo para o mesmo pedido
    - Itens 'pendente' do pedido transitam para 'agendado'
    - Emite evento agendamento_criado
    """
    agora = datetime.utcnow().isoformat()
    protocolo = str(uuid.uuid4())
    # §7 — ownership ANTES de duplicidade/estado: pedido 404 → 403 → 409 (§D3).
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_por_protocolo(conn, payload.pedido_protocolo)

        if papel != "admin":
            _assert_pedido_owner_criar(conn, pedido, papel, ident, payload.org_id)

        # Verificar se há agendamento ativo para este pedido
        ativo = conn.execute(
            """
            SELECT id FROM agendamentos
             WHERE pedido_id = ? AND status NOT IN ('cancelado', 'nao_compareceu', 'realizado')
            """,
            (pedido["id"],),
        ).fetchone()
        if ativo:
            raise HTTPException(
                status_code=409,
                detail="Já existe um agendamento ativo para este pedido. "
                       "Cancele o atual antes de criar outro ou use /remarcar.",
            )

        # Verificar pedido em estado agendável
        _ESTADOS_AGENDAVEIS = {"emitido", "agendado"}
        if pedido["status"] not in _ESTADOS_AGENDAVEIS:
            raise HTTPException(
                status_code=409,
                detail=f"Pedido com status '{pedido['status']}' não pode ser agendado.",
            )

        # Buscar paciente_id do pedido
        paciente_id = pedido["paciente_id"]

        # Criar agendamento
        cur = conn.execute(
            """
            INSERT INTO agendamentos
              (protocolo, pedido_id, paciente_id,
               org_id, unidade_id, tipo_agendamento,
               data_hora, local_texto, observacao,
               status, tipo_emissao, origem_agendamento_id,
               criado_por, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'criado', 'novo', NULL, ?, ?)
            """,
            (protocolo, pedido["id"], paciente_id,
             payload.org_id, payload.unidade_id, payload.tipo_agendamento,
             payload.data_hora, payload.local_texto, payload.observacao,
             usuario["sub"], agora),
        )
        ag_id = cur.lastrowid

        # Itens pendente → agendado
        itens = _itens_ativos_do_pedido(conn, pedido["id"])
        for item in itens:
            if item["status_item"] == "pendente":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'agendado' WHERE id = ?",
                    (item["id"],),
                )

        novo_status_pedido = _recalcular_status_pedido(conn, pedido["id"], agora)

        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag_id, "agendamento_criado", {
            "agendamento_id": ag_id,
            "pedido_id":      pedido["id"],
            "org_id":         payload.org_id,
            "unidade_id":     payload.unidade_id,
            "data_hora":      payload.data_hora,
            "itens_agendados": sum(1 for i in itens if i["status_item"] == "pendente"),
        }, agora,
        instance_id=instance_id,
        ag_context={"protocolo": protocolo, "org_id": payload.org_id, "unidade_id": payload.unidade_id})

        return {
            "protocolo":          protocolo,
            "status":             "criado",
            "data_hora":          payload.data_hora,
            "org_id":             payload.org_id,
            "unidade_id":         payload.unidade_id,
            "pedido_protocolo":   payload.pedido_protocolo,
            "status_pedido":      novo_status_pedido,
        }


# ---------------------------------------------------------------------------
# GET /agendamentos/{proto} — consultar
# ---------------------------------------------------------------------------

@router.get("/agendamentos/{protocolo}")
def get_agendamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin", "dispensador")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        ag = _get_agendamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_ag_owner(conn, ag, papel, ident)
        return _serializar_agendamento(conn, ag)


# ---------------------------------------------------------------------------
# GET /pedidos_exame/{proto}/agendamentos — histórico do pedido
# ---------------------------------------------------------------------------

@router.get("/pedidos-exame/{protocolo_pedido}/agendamentos")
def listar_agendamentos_pedido(
    protocolo_pedido: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin", "dispensador")),
):
    """Lista todos os agendamentos (incluindo cancelados) de um pedido de exame."""
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        pedido = _get_pedido_por_protocolo(conn, protocolo_pedido)
        if papel != "admin":
            # §D4 — listagem é sobre o PEDIDO; dispensador não tem vínculo de org aqui.
            if papel == "prescritor":
                _assert_or_403(ident == _cns_prescritor_de_pedido(conn, pedido["id"]),
                               codigo="nao_e_dono_do_pedido",
                               mensagem="Este pedido foi emitido por outro prescritor.")
            elif papel == "paciente":
                _assert_or_403(ident == _cpf_paciente_de_pedido(conn, pedido["id"]),
                               codigo="nao_e_dono_do_pedido",
                               mensagem="Este pedido pertence a outro paciente.")
            else:  # dispensador → 403
                _assert_or_403(False, codigo="nao_e_dono_do_pedido",
                               mensagem="Prestador não lista agendamentos por pedido.")
        rows = conn.execute(
            """
            SELECT * FROM agendamentos
             WHERE pedido_id = ?
             ORDER BY criado_em DESC
            """,
            (pedido["id"],),
        ).fetchall()
        return {
            "pedido_protocolo": protocolo_pedido,
            "agendamentos": [_serializar_agendamento(conn, dict(r)) for r in rows],
        }


# ---------------------------------------------------------------------------
# Helper de transição de estado
# ---------------------------------------------------------------------------

def _transicionar(conn, protocolo: str, novo_status: str, agora: str) -> dict:
    ag = _get_agendamento_ou_404(conn, protocolo)
    try:
        validar_transicao(ag["status"], novo_status)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    conn.execute(
        "UPDATE agendamentos SET status = ? WHERE id = ?",
        (novo_status, ag["id"]),
    )
    ag["status"] = novo_status
    return ag


# ---------------------------------------------------------------------------
# POST /agendamentos/{proto}/confirmar
# ---------------------------------------------------------------------------

@router.post("/agendamentos/{protocolo}/confirmar", status_code=200)
def confirmar_agendamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        ag0 = _get_agendamento_ou_404(conn, protocolo)        # 404
        if papel != "admin":
            _assert_ag_owner(conn, ag0, papel, ident)          # 403 antes do 409
        ag = _transicionar(conn, protocolo, "confirmado", agora)
        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_confirmado",
                                   _montar_payload_evento(ag), agora,
                                   instance_id=instance_id, ag_context=ag)
        return {"protocolo": protocolo, "status": "confirmado"}


# ---------------------------------------------------------------------------
# POST /agendamentos/{proto}/realizar
# ---------------------------------------------------------------------------

@router.post("/agendamentos/{protocolo}/realizar", status_code=200)
def realizar_agendamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "dispensador")),
):
    """
    Registra a realização do agendamento.

    Nota MVP: 'realizado' implica 'coletado' nos itens do pedido.
    Em versões futuras, comparecimento e coleta efetiva podem ser
    eventos distintos (ex.: coleta parcial, preparo inadequado).
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        ag0 = _get_agendamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_ag_owner(conn, ag0, papel, ident)
        ag = _transicionar(conn, protocolo, "realizado", agora)

        # MVP: realizado → itens agendado → coletado
        itens = _itens_ativos_do_pedido(conn, ag["pedido_id"])
        coletados = 0
        for item in itens:
            if item["status_item"] == "agendado":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'coletado' WHERE id = ?",
                    (item["id"],),
                )
                coletados += 1

        novo_status_pedido = _recalcular_status_pedido(conn, ag["pedido_id"], agora)

        payload_ev = _montar_payload_evento(ag)
        payload_ev["itens_coletados"] = coletados
        payload_ev["mvp_nota"] = "realizado implica coletado — simplificacao MVP"
        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_realizado",
                                   payload_ev, agora,
                                   instance_id=instance_id, ag_context=ag)

        return {
            "protocolo":      protocolo,
            "status":         "realizado",
            "itens_coletados": coletados,
            "status_pedido":  novo_status_pedido,
        }


# ---------------------------------------------------------------------------
# POST /agendamentos/{proto}/cancelar
# ---------------------------------------------------------------------------

@router.post("/agendamentos/{protocolo}/cancelar", status_code=200)
def cancelar_agendamento(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin", "dispensador")),
):
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        ag0 = _get_agendamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_ag_owner(conn, ag0, papel, ident)
        ag = _transicionar(conn, protocolo, "cancelado", agora)

        # Itens agendado → pendente
        itens = _itens_ativos_do_pedido(conn, ag["pedido_id"])
        for item in itens:
            if item["status_item"] == "agendado":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'pendente' WHERE id = ?",
                    (item["id"],),
                )

        novo_status_pedido = _recalcular_status_pedido(conn, ag["pedido_id"], agora)

        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_cancelado",
                                   _montar_payload_evento(ag), agora,
                                   instance_id=instance_id, ag_context=ag)
        return {
            "protocolo":      protocolo,
            "status":         "cancelado",
            "status_pedido":  novo_status_pedido,
        }


# ---------------------------------------------------------------------------
# POST /agendamentos/{proto}/nao-compareceu
# ---------------------------------------------------------------------------

@router.post("/agendamentos/{protocolo}/nao-compareceu", status_code=200)
def nao_compareceu(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin")),
):
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        ag0 = _get_agendamento_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_ag_owner(conn, ag0, papel, ident)
        ag = _transicionar(conn, protocolo, "nao_compareceu", agora)

        # Itens agendado → pendente
        itens = _itens_ativos_do_pedido(conn, ag["pedido_id"])
        for item in itens:
            if item["status_item"] == "agendado":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'pendente' WHERE id = ?",
                    (item["id"],),
                )

        novo_status_pedido = _recalcular_status_pedido(conn, ag["pedido_id"], agora)

        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_nao_compareceu",
                                   _montar_payload_evento(ag), agora,
                                   instance_id=instance_id, ag_context=ag)
        return {
            "protocolo":     protocolo,
            "status":        "nao_compareceu",
            "status_pedido": novo_status_pedido,
        }


# ---------------------------------------------------------------------------
# POST /agendamentos/{proto}/remarcar
# ---------------------------------------------------------------------------

@router.post("/agendamentos/{protocolo}/remarcar", status_code=201)
def remarcar_agendamento(
    protocolo: str,
    payload: RemarcarIn,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    """
    Cria um novo agendamento derivado (remarcação).

    O agendamento anterior é cancelado com motivo 'remarcado'.
    O novo recebe origem_agendamento_id apontando para o anterior.
    """
    agora = datetime.utcnow().isoformat()
    novo_protocolo = str(uuid.uuid4())
    # §7 — ownership após o 404, antes das regras de estado (409). Sem dispensador
    # no RBAC; _assert_ag_owner cobre prescritor/paciente.
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        ag = _get_agendamento_ou_404(conn, protocolo)

        if papel != "admin":
            _assert_ag_owner(conn, ag, papel, ident)

        if eh_terminal(ag["status"]) and ag["status"] != "cancelado":
            raise HTTPException(
                status_code=409,
                detail=f"Agendamento em status terminal '{ag['status']}' não pode ser remarcado.",
            )
        if ag["status"] == "cancelado":
            raise HTTPException(
                status_code=409,
                detail="Agendamento já cancelado não pode ser remarcado.",
            )

        # Cancelar o agendamento anterior
        conn.execute(
            "UPDATE agendamentos SET status = 'cancelado' WHERE id = ?", (ag["id"],),
        )
        # Ticket 4D.2: 3 eventos da remarcação compartilham instance_id
        # (este e o terceiro evento agendamento_criado abaixo).
        instance_id = get_instance_id_conn(conn)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_remarcado", {
            **_montar_payload_evento(ag),
            "novo_protocolo": novo_protocolo,
            "motivo":         "remarcacao",
        }, agora, instance_id=instance_id, ag_context=ag)
        _gravar_evento_agendamento(conn, ag["id"], "agendamento_cancelado", {
            **_montar_payload_evento(ag),
            "motivo": "remarcado",
        }, agora, instance_id=instance_id, ag_context=ag)

        # Criar novo agendamento derivado
        novo_org_id    = payload.org_id    or ag["org_id"]
        novo_unidade   = payload.unidade_id or ag["unidade_id"]

        cur = conn.execute(
            """
            INSERT INTO agendamentos
              (protocolo, pedido_id, paciente_id,
               org_id, unidade_id, tipo_agendamento,
               data_hora, local_texto, observacao,
               status, tipo_emissao, origem_agendamento_id,
               criado_por, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'criado', 'remarcacao', ?, ?, ?)
            """,
            (novo_protocolo, ag["pedido_id"], ag["paciente_id"],
             novo_org_id, novo_unidade, ag["tipo_agendamento"],
             payload.data_hora, ag["local_texto"], payload.observacao or ag["observacao"],
             ag["id"], usuario["sub"], agora),
        )
        novo_ag_id = cur.lastrowid

        _gravar_evento_agendamento(conn, novo_ag_id, "agendamento_criado", {
            "agendamento_id":    novo_ag_id,
            "pedido_id":         ag["pedido_id"],
            "org_id":            novo_org_id,
            "unidade_id":        novo_unidade,
            "data_hora":         payload.data_hora,
            "tipo_emissao":      "remarcacao",
            "origem_protocolo":  protocolo,
        }, agora,
        instance_id=instance_id,
        ag_context={"protocolo": novo_protocolo, "org_id": novo_org_id, "unidade_id": novo_unidade})

        return {
            "protocolo_anterior": protocolo,
            "protocolo_novo":     novo_protocolo,
            "status_anterior":    "cancelado",
            "status_novo":        "criado",
            "data_hora":          payload.data_hora,
        }
