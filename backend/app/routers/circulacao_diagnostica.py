"""
circulacao_diagnostica.py
=========================
Endpoints do módulo de Circulação Diagnóstica — Tickets 53 e 54.

Fase implementada (Ticket 53):
  - POST /pedidos-exame/{protocolo}/circulacao — paciente cria circulação
  - GET  /circulacao/{chave}                   — laboratório consulta por chave

Fase implementada (Ticket 54):
  - POST /circulacao/{chave}/proposta  — laboratório registra proposta
  - POST /circulacao/{chave}/confirmar — paciente confirma proposta
  - POST /circulacao/{chave}/desmarcar — paciente ou laboratório desmarca

Fases futuras (Tickets 55–57):
  - Realização da coleta
  - Remarcação (origem_circulacao_id)
  - Integração com agendamento concreto

Regras de domínio (Ticket 53):
  - Apenas paciente pode criar circulação (sub = CPF do criador)
  - Itens elegíveis: status_item = 'pendente' (não pode estar em circulação ativa)
  - O mesmo item NÃO pode pertencer a duas circulações ativas simultaneamente
  - Circulação ativa: status NOT IN terminal states
  - Status inicial: 'selecionado'
  - Estados do pedido/itens NÃO são alterados nesta fase
  - Privacidade: GET /circulacao/{chave} expõe SOMENTE os itens do subconjunto,
    nunca o pedido completo

Regras de domínio (Ticket 54):
  - Proposta: apenas dispensador (laboratório) ou admin
  - Confirmação: apenas paciente ou admin
  - Desmarcação: paciente (→ desmarcado_paciente) ou dispensador/admin (→ desmarcado_laboratorio)
  - Nenhum endpoint altera pedido_exame nem pedido_exame_itens
  - Todas as transições validadas por states_circulacao_diagnostica.py

Referência: docs/ARQUITETURA_AGENDAMENTO_ATOMIZADO_EXAMES.md
States:     domain/states_circulacao_diagnostica.py
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn
from app.domain.states_circulacao_diagnostica import (
    ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA,
    validar_transicao_circulacao_diagnostica,
)
from app.utils.helpers import _assert_or_403, _normalizar_identidade_jwt, normalize_cnpj

router = APIRouter(tags=["circulacao_diagnostica"])

# Janela padrão de validade da chave quando não informada pelo chamador
_VALIDADE_PADRAO_DIAS = 30
_CPF_NAO_IDENTIFICADO = "00000000000"


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CriarCirculacaoIn(BaseModel):
    org_id:     str
    unidade_id: str
    item_ids:   list[int]                # IDs de pedido_exame_itens selecionados
    validade:   Optional[str] = None     # ISO 8601 datetime; None = +30 dias

    @field_validator("org_id", "unidade_id")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("org_id e unidade_id são obrigatórios e não podem ser vazios.")
        return v.strip()

    @field_validator("item_ids")
    @classmethod
    def pelo_menos_um_item(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("item_ids deve conter ao menos um item.")
        return v


# ---------------------------------------------------------------------------
# Schemas — Ticket 54
# ---------------------------------------------------------------------------

class PropostaIn(BaseModel):
    """Payload da proposta do laboratório: data/hora, local e preparo."""
    data_hora_proposta: str
    local_texto:        Optional[str] = None
    instrucoes_preparo: Optional[str] = None

    @field_validator("data_hora_proposta")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("data_hora_proposta é obrigatório.")
        return v.strip()


class DesmarcarIn(BaseModel):
    """Payload opcional da desmarcação. Motivo é livre e facultativo."""
    motivo: Optional[str] = None


class RealizarIn(BaseModel):
    """Payload opcional da realização. Observação é livre e facultativa."""
    observacao: Optional[str] = None


class RemarcarIn(BaseModel):
    """
    Payload da remarcação pelo laboratório.
    Cria nova circulação derivada com os mesmos itens e novo destino.
    """
    org_id:     str
    unidade_id: str
    observacao: Optional[str] = None

    @field_validator("org_id", "unidade_id")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("org_id e unidade_id são obrigatórios e não podem ser vazios.")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_pedido_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")
    return dict(row)


def _get_circulacao_por_chave_ou_404(conn, chave: str) -> dict:
    row = conn.execute(
        "SELECT * FROM circulacoes_diagnosticas WHERE chave_circulacao = ?", (chave,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Circulação com chave '{chave}' não encontrada.")
    return dict(row)


def _gerar_chave_circulacao() -> str:
    """Gera chave legível de 12 caracteres hexadecimais maiúsculos.
    Colisão improvável: 48 bits de entropia para uso operacional.
    Exemplo: 'A3F1C2B4E5D6'
    """
    return uuid.uuid4().hex[:12].upper()


def _gravar_evento(conn, circulacao_id: int, tipo_evento: str,
                   dados: dict, agora: str,
                   *, instance_id: str) -> None:
    """Insere evento no ledger. Nunca recebe UPDATE nem DELETE.

    Ticket 4D.2: delega para ``registrar_evento_ledger``. ``instance_id``
    é parâmetro keyword-only obrigatório — caller obtém via
    ``get_instance_id_conn(conn)`` uma vez por transação.
    """
    registrar_evento_ledger(
        conn,
        objeto_tipo="circulacao_diagnostica",
        objeto_id=circulacao_id,
        tipo_evento=tipo_evento,
        instance_id=instance_id,
        payload=dados,
    )


def _itens_da_circulacao(conn, circulacao_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT cdi.id, cdi.pedido_exame_item_id, cdi.nome_exame,
               pei.codigo_tuss, pei.codigo_sigtap, pei.quantidade, pei.status_item
          FROM circulacao_diagnostica_itens cdi
          JOIN pedido_exame_itens pei ON pei.id = cdi.pedido_exame_item_id
         WHERE cdi.circulacao_id = ?
        """,
        (circulacao_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _erro_schema_org_prestador(exc: Exception) -> bool:
    msg = str(exc).lower()
    return (
        "org_id" in msg
        and (
            "prestadores" in msg
            or "no such column" in msg
            or "does not exist" in msg
            or "undefinedcolumn" in msg
        )
    )


def _org_id_do_dispensador(conn, ident_cnpj: str) -> str | None:
    if len(ident_cnpj) != 14:
        return None
    try:
        rows = conn.execute(
            "SELECT org_id, cnpj FROM prestadores WHERE cnpj IS NOT NULL AND ativo = true"
        ).fetchall()
    except Exception as exc:
        # C.1/D.2: enquanto a coluna org_id não estiver migrada em PG,
        # dispensadores falham fechado (403) em vez de ganhar acesso por chave.
        if _erro_schema_org_prestador(exc):
            return None
        raise
    # §D2 — normalização read-side: prestadores.cnpj é gravado cru/mascarado
    #   (prestadores.py:103), enquanto o ident do JWT já vem normalizado.
    # §D1 — ambiguidade: mesmo CNPJ em >1 org ativa → None → 403 (fail-closed).
    orgs = {r["org_id"] for r in rows if r["org_id"] and normalize_cnpj(r["cnpj"]) == ident_cnpj}
    return orgs.pop() if len(orgs) == 1 else None


def _assert_paciente_dono_pedido(conn, pedido_id: int, ident_cpf: str) -> None:
    row = conn.execute(
        "SELECT pa.cpf FROM pedidos_exame pe "
        "JOIN pacientes pa ON pa.id = pe.paciente_id "
        "WHERE pe.id = ?",
        (pedido_id,),
    ).fetchone()
    cpf = row["cpf"] if row else None
    _assert_or_403(
        cpf is not None and cpf != _CPF_NAO_IDENTIFICADO and ident_cpf == cpf,
        codigo="nao_e_dono_do_pedido_exame",
        mensagem="Este pedido de exame pertence a outro paciente.",
    )


def _assert_paciente_dono_circulacao(conn, circ: dict, ident_cpf: str) -> None:
    row = conn.execute(
        "SELECT cpf FROM pacientes WHERE id = ?",
        (circ["paciente_id"],),
    ).fetchone()
    cpf = row["cpf"] if row else None
    _assert_or_403(
        cpf is not None and cpf != _CPF_NAO_IDENTIFICADO and ident_cpf == cpf,
        codigo="nao_e_dono_da_circulacao_diagnostica",
        mensagem="Esta circulação diagnóstica pertence a outro paciente.",
    )


def _assert_prescritor_dono_circulacao(conn, circ: dict, ident_cns: str) -> None:
    row = conn.execute(
        "SELECT pr.cns FROM pedidos_exame pe "
        "JOIN prescritores pr ON pr.id = pe.prescritor_id "
        "WHERE pe.id = ?",
        (circ["pedido_id"],),
    ).fetchone()
    _assert_or_403(
        row is not None and ident_cns == row["cns"],
        codigo="nao_e_dono_da_circulacao_diagnostica",
        mensagem="Esta circulação diagnóstica pertence a outro prescritor.",
    )


def _assert_dispensador_dono_circulacao(conn, circ: dict, ident_cnpj: str) -> None:
    org_id = _org_id_do_dispensador(conn, ident_cnpj)
    _assert_or_403(
        org_id is not None and org_id == circ["org_id"],
        codigo="nao_e_dono_da_circulacao_diagnostica",
        mensagem="Esta circulação diagnóstica pertence a outro prestador.",
    )


def _assert_usuario_pode_acessar_circulacao(conn, circ: dict, papel: str, ident: str) -> None:
    if papel == "admin":
        return
    if papel == "paciente":
        _assert_paciente_dono_circulacao(conn, circ, ident)
        return
    if papel == "prescritor":
        _assert_prescritor_dono_circulacao(conn, circ, ident)
        return
    if papel == "dispensador":
        _assert_dispensador_dono_circulacao(conn, circ, ident)
        return
    _assert_or_403(
        False,
        codigo="papel_sem_acesso_a_circulacao_diagnostica",
        mensagem="Este perfil não pode acessar esta circulação diagnóstica.",
    )


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/circulacao
# ---------------------------------------------------------------------------

@router.post("/pedidos-exame/{protocolo}/circulacao", status_code=201)
def criar_circulacao(
    protocolo: str,
    payload: CriarCirculacaoIn,
    usuario=Depends(require_role("paciente", "admin")),
):
    """
    Cria uma circulação diagnóstica para um subconjunto de itens do pedido.

    Quem pode criar: paciente (dono do pedido) ou admin.

    Validações:
    - Pedido existe e não está em estado terminal
    - Todos os item_ids pertencem ao pedido
    - Todos os item_ids estão com status_item = 'pendente'
    - Nenhum item está em circulação ativa simultânea

    Não altera status do pedido nem dos itens (Ticket 53).
    """
    agora = datetime.utcnow().isoformat()
    protocolo_circ = str(uuid.uuid4())
    papel, ident = _normalizar_identidade_jwt(usuario)

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if papel != "admin":
            _assert_paciente_dono_pedido(conn, pedido["id"], ident)

        # Pedido não pode estar em estado terminal
        _ESTADOS_TERMINAIS_PEDIDO = {"cancelado", "expirado", "encerrado_fisico"}
        if pedido["status"] in _ESTADOS_TERMINAIS_PEDIDO:
            raise HTTPException(
                status_code=409,
                detail=f"Pedido com status '{pedido['status']}' não aceita novas circulações.",
            )

        # Carregar itens do pedido para validação
        todos_itens = {
            row["id"]: dict(row)
            for row in conn.execute(
                "SELECT * FROM pedido_exame_itens WHERE pedido_id = ?", (pedido["id"],)
            ).fetchall()
        }

        # Validar que cada item_id pertence ao pedido
        ids_invalidos = [i for i in payload.item_ids if i not in todos_itens]
        if ids_invalidos:
            raise HTTPException(
                status_code=422,
                detail=f"Os seguintes item_ids não pertencem ao pedido '{protocolo}': {ids_invalidos}",
            )

        # Validar que todos os itens estão pendentes
        nao_pendentes = [
            i for i in payload.item_ids
            if todos_itens[i]["status_item"] != "pendente"
        ]
        if nao_pendentes:
            statuses = {i: todos_itens[i]["status_item"] for i in nao_pendentes}
            raise HTTPException(
                status_code=409,
                detail=f"Itens não elegíveis (apenas 'pendente' é aceito): {statuses}",
            )

        # Validar que nenhum item já está em circulação ativa
        placeholders = ",".join("?" * len(payload.item_ids))
        em_circulacao_ativa = conn.execute(
            f"""
            SELECT cdi.pedido_exame_item_id
              FROM circulacao_diagnostica_itens cdi
              JOIN circulacoes_diagnosticas cd ON cd.id = cdi.circulacao_id
             WHERE cdi.pedido_exame_item_id IN ({placeholders})
               AND cd.status NOT IN ({",".join("?" * len(ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA))})
            """,
            payload.item_ids + sorted(ESTADOS_TERMINAIS_CIRCULACAO_DIAGNOSTICA),
        ).fetchall()
        if em_circulacao_ativa:
            ids_conflito = [r["pedido_exame_item_id"] for r in em_circulacao_ativa]
            raise HTTPException(
                status_code=409,
                detail=f"Os seguintes itens já pertencem a uma circulação ativa: {ids_conflito}",
            )

        # Calcular validade
        if payload.validade:
            validade = payload.validade
        else:
            validade = (
                datetime.utcnow() + timedelta(days=_VALIDADE_PADRAO_DIAS)
            ).isoformat()

        # Gerar chave única (retry em colisão improvável)
        for _ in range(3):
            chave = _gerar_chave_circulacao()
            existe = conn.execute(
                "SELECT id FROM circulacoes_diagnosticas WHERE chave_circulacao = ?", (chave,)
            ).fetchone()
            if not existe:
                break
        else:
            raise HTTPException(status_code=500, detail="Falha ao gerar chave de circulação.")

        # Inserir circulação
        cur = conn.execute(
            """
            INSERT INTO circulacoes_diagnosticas
              (protocolo, chave_circulacao, pedido_id, paciente_id,
               org_id, unidade_id, status, tipo_emissao,
               validade, criado_por, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, 'selecionado', 'novo', ?, ?, ?)
            """,
            (protocolo_circ, chave, pedido["id"], pedido["paciente_id"],
             payload.org_id, payload.unidade_id,
             validade, usuario["sub"], agora),
        )
        circ_id = cur.lastrowid

        # Inserir itens
        itens_inseridos = []
        for item_id in payload.item_ids:
            item = todos_itens[item_id]
            conn.execute(
                """
                INSERT INTO circulacao_diagnostica_itens
                  (circulacao_id, pedido_exame_item_id, nome_exame, criado_em)
                VALUES (?, ?, ?, ?)
                """,
                (circ_id, item_id, item["nome_exame"], agora),
            )
            itens_inseridos.append({
                "pedido_exame_item_id": item_id,
                "nome_exame":          item["nome_exame"],
            })

        # Evento no ledger
        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ_id, "circulacao_criada", {
            "circulacao_id":  circ_id,
            "pedido_id":      pedido["id"],
            "org_id":         payload.org_id,
            "unidade_id":     payload.unidade_id,
            "itens":          [i["pedido_exame_item_id"] for i in itens_inseridos],
            "criado_por":     usuario["sub"],
        }, agora, instance_id=instance_id)

        return {
            "protocolo":         protocolo_circ,
            "chave_circulacao":  chave,
            "status":            "selecionado",
            "org_id":            payload.org_id,
            "unidade_id":        payload.unidade_id,
            "validade":          validade,
            "criado_em":         agora,
            "itens":             itens_inseridos,
        }


# ---------------------------------------------------------------------------
# GET /circulacao/{chave}
# ---------------------------------------------------------------------------

@router.get("/circulacao/{chave}")
def consultar_circulacao_por_chave(
    chave: str,
    usuario=Depends(require_role("dispensador", "prescritor", "paciente", "admin")),
):
    """
    Consulta uma circulação diagnóstica pela chave de circulação.

    Privacidade obrigatória:
    - Retorna APENAS os itens selecionados para esta circulação.
    - Nunca expõe outros itens do pedido de origem.
    - Nunca expõe o total de itens do pedido.

    O laboratório recebe as informações necessárias para atender o paciente:
    - Nome do paciente
    - Nome e CNS do prescritor
    - Itens selecionados com códigos TUSS/SIGTAP
    - Validade da chave
    - Status da circulação
    """
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)
        _assert_usuario_pode_acessar_circulacao(conn, circ, papel, ident)

        # Dados do paciente
        paciente = conn.execute(
            "SELECT nome FROM pacientes WHERE id = ?",
            (circ["paciente_id"],),
        ).fetchone()

        # Dados do prescritor via pedido
        pedido = conn.execute(
            "SELECT prescritor_id, prioridade FROM pedidos_exame WHERE id = ?",
            (circ["pedido_id"],),
        ).fetchone()

        prescritor = None
        if pedido and pedido["prescritor_id"]:
            prescritor = conn.execute(
                "SELECT nome, cns FROM prescritores WHERE id = ?",
                (pedido["prescritor_id"],),
            ).fetchone()

        # Itens — SOMENTE o subconjunto desta circulação (privacidade)
        itens = _itens_da_circulacao(conn, circ["id"])

        return {
            "protocolo":         circ["protocolo"],
            "chave_circulacao":  circ["chave_circulacao"],
            "status":            circ["status"],
            "org_id":            circ["org_id"],
            "unidade_id":        circ["unidade_id"],
            "validade":          circ["validade"],
            "criado_em":         circ["criado_em"],
            "paciente": {
                "nome": paciente["nome"] if paciente else None,
            },
            "prescritor": {
                "nome": prescritor["nome"] if prescritor else None,
                "cns":  prescritor["cns"]  if prescritor else None,
            },
            "prioridade": pedido["prioridade"] if pedido else None,
            # Privacidade: apenas os itens do subconjunto desta circulação
            "itens": [
                {
                    "nome_exame":    i["nome_exame"],
                    "codigo_tuss":   i["codigo_tuss"],
                    "codigo_sigtap": i["codigo_sigtap"],
                    "quantidade":    i["quantidade"],
                }
                for i in itens
            ],
            # Proposta do laboratório (preenchida em POST /circulacao/{chave}/proposta)
            "data_hora_proposta":  circ["data_hora_proposta"],
            "local_texto":         circ["local_texto"],
            "instrucoes_preparo":  circ["instrucoes_preparo"],
        }


# ---------------------------------------------------------------------------
# POST /circulacao/{chave}/proposta — laboratório registra proposta
# ---------------------------------------------------------------------------

@router.post("/circulacao/{chave}/proposta", status_code=200)
def registrar_proposta(
    chave: str,
    payload: PropostaIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Laboratório registra proposta de data/hora, local e instruções de preparo.

    Estado exigido: enviado_laboratorio
    Transição:      enviado_laboratorio → proposta_recebida
    Ator:           dispensador (laboratório) ou admin

    Não altera pedido_exame nem pedido_exame_itens.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)
        if papel != "admin":
            _assert_dispensador_dono_circulacao(conn, circ, ident)

        try:
            validar_transicao_circulacao_diagnostica(circ["status"], "proposta_recebida")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        conn.execute(
            """
            UPDATE circulacoes_diagnosticas
               SET status             = 'proposta_recebida',
                   data_hora_proposta = ?,
                   local_texto        = ?,
                   instrucoes_preparo = ?
             WHERE id = ?
            """,
            (payload.data_hora_proposta, payload.local_texto,
             payload.instrucoes_preparo, circ["id"]),
        )

        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ["id"], "circulacao_proposta_recebida", {
            "circulacao_id":      circ["id"],
            "data_hora_proposta": payload.data_hora_proposta,
            "local_texto":        payload.local_texto,
            "instrucoes_preparo": payload.instrucoes_preparo,
            "registrado_por":     usuario["sub"],
        }, agora, instance_id=instance_id)

        return {
            "protocolo":          circ["protocolo"],
            "status":             "proposta_recebida",
            "data_hora_proposta": payload.data_hora_proposta,
            "local_texto":        payload.local_texto,
            "instrucoes_preparo": payload.instrucoes_preparo,
        }


# ---------------------------------------------------------------------------
# POST /circulacao/{chave}/confirmar — paciente aceita proposta
# ---------------------------------------------------------------------------

@router.post("/circulacao/{chave}/confirmar", status_code=200)
def confirmar_proposta(
    chave: str,
    usuario=Depends(require_role("paciente", "admin")),
):
    """
    Paciente confirma a proposta registrada pelo laboratório.

    Estado exigido: proposta_recebida
    Transição:      proposta_recebida → confirmado_paciente
    Ator:           paciente ou admin

    Não altera pedido_exame nem pedido_exame_itens.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)
        if papel != "admin":
            _assert_paciente_dono_circulacao(conn, circ, ident)

        try:
            validar_transicao_circulacao_diagnostica(circ["status"], "confirmado_paciente")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'confirmado_paciente' WHERE id = ?",
            (circ["id"],),
        )

        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ["id"], "circulacao_confirmada_paciente", {
            "circulacao_id":  circ["id"],
            "confirmado_por": usuario["sub"],
        }, agora, instance_id=instance_id)

        return {
            "protocolo": circ["protocolo"],
            "status":    "confirmado_paciente",
        }


# ---------------------------------------------------------------------------
# POST /circulacao/{chave}/desmarcar — paciente ou laboratório desmarca
# ---------------------------------------------------------------------------

@router.post("/circulacao/{chave}/desmarcar", status_code=200)
def desmarcar_circulacao(
    chave: str,
    payload: DesmarcarIn = Body(default=DesmarcarIn()),
    usuario=Depends(require_role("paciente", "dispensador", "admin")),
):
    """
    Desmarca a circulação diagnóstica.

    Ator e estado destino:
      paciente    → desmarcado_paciente    (de proposta_recebida ou confirmado_paciente)
      dispensador → desmarcado_laboratorio (de enviado_laboratorio, proposta_recebida
                                             ou confirmado_paciente)
      admin       → desmarcado_laboratorio (comportamento equivalente ao dispensador)

    A transição é validada pela máquina de estados. Se o role ou o estado
    atual não permitirem a transição, retorna 409.

    Não altera pedido_exame nem pedido_exame_itens.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)

        if papel == "paciente":
            _assert_paciente_dono_circulacao(conn, circ, ident)
            novo_status = "desmarcado_paciente"
            tipo_evento = "circulacao_desmarcada_paciente"
        else:
            if papel != "admin":
                _assert_dispensador_dono_circulacao(conn, circ, ident)
            # dispensador ou admin atuam como laboratório
            novo_status = "desmarcado_laboratorio"
            tipo_evento = "circulacao_desmarcada_laboratorio"

        try:
            validar_transicao_circulacao_diagnostica(circ["status"], novo_status)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = ? WHERE id = ?",
            (novo_status, circ["id"]),
        )

        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ["id"], tipo_evento, {
            "circulacao_id":  circ["id"],
            "desmarcado_por": usuario["sub"],
            "motivo":         payload.motivo,
        }, agora, instance_id=instance_id)

        return {
            "protocolo": circ["protocolo"],
            "status":    novo_status,
        }


# ---------------------------------------------------------------------------
# POST /circulacao/{chave}/realizar — laboratório registra coleta (Ticket 57)
# ---------------------------------------------------------------------------

@router.post("/circulacao/{chave}/realizar", status_code=200)
def realizar_circulacao(
    chave: str,
    payload: RealizarIn = Body(default=RealizarIn()),
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Laboratório registra que a coleta foi realizada.

    Estado exigido: confirmado_paciente
    Transição:      confirmado_paciente → realizado  [terminal]
    Ator:           dispensador (laboratório) ou admin

    Não altera pedido_exame nem pedido_exame_itens diretamente —
    a atualização de itens ocorre via endpoint de coleta do pedido.
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)
        if papel != "admin":
            _assert_dispensador_dono_circulacao(conn, circ, ident)

        try:
            validar_transicao_circulacao_diagnostica(circ["status"], "realizado")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'realizado' WHERE id = ?",
            (circ["id"],),
        )

        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ["id"], "circulacao_realizada", {
            "circulacao_id":  circ["id"],
            "realizado_por":  usuario["sub"],
            "observacao":     payload.observacao,
        }, agora, instance_id=instance_id)

        return {
            "protocolo": circ["protocolo"],
            "status":    "realizado",
        }


# ---------------------------------------------------------------------------
# POST /circulacao/{chave}/remarcar — laboratório cria nova circulação derivada (Ticket 57)
# ---------------------------------------------------------------------------

@router.post("/circulacao/{chave}/remarcar", status_code=201)
def remarcar_circulacao(
    chave: str,
    payload: RemarcarIn,
    usuario=Depends(require_role("dispensador", "admin")),
):
    """
    Laboratório remarca: encerra a circulação atual como desmarcado_laboratorio
    e cria uma nova circulação derivada com os mesmos itens e novo destino.

    Estado exigido (circulação atual): enviado_laboratorio | proposta_recebida | confirmado_paciente
    Ator:           dispensador (laboratório) ou admin

    Retorna:
      - protocolo_anterior, status_anterior  — circulação encerrada
      - protocolo_novo, chave_nova, status_novo  — nova circulação criada
    """
    agora = datetime.utcnow().isoformat()
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        circ = _get_circulacao_por_chave_ou_404(conn, chave)
        if papel != "admin":
            _assert_dispensador_dono_circulacao(conn, circ, ident)

        # Valida que pode desmarcar como laboratório
        try:
            validar_transicao_circulacao_diagnostica(circ["status"], "desmarcado_laboratorio")
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

        # Encerra circulação atual
        conn.execute(
            "UPDATE circulacoes_diagnosticas SET status = 'desmarcado_laboratorio' WHERE id = ?",
            (circ["id"],),
        )
        # Ticket 4D.2: 2 eventos da remarcação compartilham instance_id
        # (este e circulacao_criada da nova circulação derivada abaixo).
        instance_id = get_instance_id_conn(conn)
        _gravar_evento(conn, circ["id"], "circulacao_desmarcada_laboratorio", {
            "circulacao_id":  circ["id"],
            "desmarcado_por": usuario["sub"],
            "motivo":         "remarcado",
        }, agora, instance_id=instance_id)

        # Busca itens da circulação original
        itens_orig = _itens_da_circulacao(conn, circ["id"])
        if not itens_orig:
            raise HTTPException(status_code=422, detail="Circulação sem itens — remarcação impossível.")

        item_ids = [i["pedido_exame_item_id"] for i in itens_orig]

        # Cria nova circulação derivada
        novo_protocolo = str(uuid.uuid4())
        nova_validade  = (datetime.utcnow() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()

        # Gera chave única
        nova_chave = None
        for _ in range(3):
            candidato = _gerar_chave_circulacao()
            existe = conn.execute(
                "SELECT 1 FROM circulacoes_diagnosticas WHERE chave_circulacao = ?",
                (candidato,),
            ).fetchone()
            if not existe:
                nova_chave = candidato
                break
        if not nova_chave:
            raise HTTPException(status_code=500, detail="Não foi possível gerar chave única. Tente novamente.")

        conn.execute(
            """
            INSERT INTO circulacoes_diagnosticas
                   (protocolo, chave_circulacao, pedido_id, paciente_id,
                    org_id, unidade_id, status, tipo_emissao,
                    origem_circulacao_id, validade, criado_por, criado_em)
            VALUES (?, ?, ?, ?,
                    ?, ?, 'selecionado', 'remarcacao',
                    ?, ?, ?, ?)
            """,
            (
                novo_protocolo, nova_chave,
                circ["pedido_id"], circ["paciente_id"],
                payload.org_id, payload.unidade_id,
                circ["id"], nova_validade,
                usuario["sub"], agora,
            ),
        )
        nova_circ_id = conn.execute(
            "SELECT id FROM circulacoes_diagnosticas WHERE protocolo = ?",
            (novo_protocolo,),
        ).fetchone()["id"]

        # Replica itens
        for item in itens_orig:
            conn.execute(
                """
                INSERT INTO circulacao_diagnostica_itens
                       (circulacao_id, pedido_exame_item_id, nome_exame, criado_em)
                VALUES (?, ?, ?, ?)
                """,
                (nova_circ_id, item["pedido_exame_item_id"], item["nome_exame"], agora),
            )

        _gravar_evento(conn, nova_circ_id, "circulacao_criada", {
            "circulacao_id":         nova_circ_id,
            "origem_circulacao_id":  circ["id"],
            "pedido_id":             circ["pedido_id"],
            "org_id":                payload.org_id,
            "unidade_id":            payload.unidade_id,
            "itens":                 item_ids,
            "criado_por":            usuario["sub"],
            "tipo_emissao":          "remarcacao",
        }, agora, instance_id=instance_id)

        return {
            "protocolo_anterior": circ["protocolo"],
            "status_anterior":    "desmarcado_laboratorio",
            "protocolo_novo":     novo_protocolo,
            "chave_nova":         nova_chave,
            "status_novo":        "selecionado",
        }
