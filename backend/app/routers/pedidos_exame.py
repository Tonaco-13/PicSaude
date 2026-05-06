"""
routers/pedidos_exame.py
========================
Emissão digital e física de pedidos de exame.

Ticket 15 — Model + emissão (digital e física)
Ticket 16 — Custódia + fluxo (agendar/coletar)    [futuro]
Ticket 17 — Resultado + PDF + validação pública    [futuro]

ROTAS IMPLEMENTADAS (Ticket 15)
---------------------------------
POST /pedidos-exame           ← emissão digital
POST /pedidos-exame/fisica    ← emissão física (fire-and-forget)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.outbox import registrar_outbox
from app.domain.states_exame import (
    ESTADOS_TERMINAIS_PEDIDO_EXAME,
    derivar_status_pedido,
    transicao_valida_pedido,
    transicao_valida_item_exame,
    eh_terminal_pedido,
    eh_terminal_item_exame,
)
from app.utils.helpers import normalize_cns, normalize_cpf, normalize_nome

router = APIRouter(prefix="/pedidos-exame", tags=["pedidos_exame"])

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO = "00000000000"   # Convenção: mesmo valor da prescrição
_TIPOS_EMISSAO_VALIDOS = {"novo", "correcao", "renovacao"}
_PRIORIDADES_VALIDAS   = {"rotina", "urgente", "urgentissimo"}
_VALIDADE_PADRAO_DIAS  = 30


# ---------------------------------------------------------------------------
# Schemas de entrada
# ---------------------------------------------------------------------------

class ItemExameIn(BaseModel):
    nome_exame:    str
    codigo_tuss:   Optional[str] = None
    codigo_sigtap: Optional[str] = None
    quantidade:    int = 1

    @field_validator("nome_exame")
    @classmethod
    def nome_nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("nome_exame não pode ser vazio")
        return v.strip().upper()

    @field_validator("quantidade")
    @classmethod
    def quantidade_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantidade deve ser maior que zero")
        return v


class PedidoExameIn(BaseModel):
    cns_prescritor:   str
    nome_prescritor:  Optional[str] = None
    cpf_paciente:     str
    nome_paciente:    str
    prioridade:       str = "rotina"
    indicacao_clinica: Optional[str] = None
    data_validade:    Optional[str] = None    # ISO 8601; padrão: 30 dias
    tipo_emissao:     str = "novo"
    origem_pedido_id: Optional[int] = None
    # Ticket 63 — Escolha de modo de entrega na emissão.
    # True  = criar custódia prescritor→paciente imediatamente (carteira digital).
    # False = pedido fica em 'emitido', paciente acessa via link (comportamento original).
    enviar_ao_paciente: bool = False
    itens:            List[ItemExameIn] = []

    @field_validator("tipo_emissao")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _TIPOS_EMISSAO_VALIDOS:
            raise ValueError(
                f"tipo_emissao inválido: '{v}'. Valores aceitos: {sorted(_TIPOS_EMISSAO_VALIDOS)}"
            )
        return v

    @field_validator("prioridade")
    @classmethod
    def prioridade_valida(cls, v: str) -> str:
        if v not in _PRIORIDADES_VALIDAS:
            raise ValueError(
                f"prioridade inválida: '{v}'. Valores aceitos: {sorted(_PRIORIDADES_VALIDAS)}"
            )
        return v

    @model_validator(mode="after")
    def origem_obrigatoria_para_nao_novo(self) -> "PedidoExameIn":
        if self.tipo_emissao != "novo" and self.origem_pedido_id is None:
            raise ValueError(
                f"origem_pedido_id é obrigatório quando tipo_emissao='{self.tipo_emissao}'"
            )
        return self


class FisicaExameIn(BaseModel):
    cns_prescritor:    str
    nome_prescritor:   Optional[str] = None
    cpf_paciente:      Optional[str] = None
    nome_paciente:     str
    prioridade:        str = "rotina"
    indicacao_clinica: Optional[str] = None
    itens:             List[ItemExameIn] = []

    @field_validator("prioridade")
    @classmethod
    def prioridade_valida(cls, v: str) -> str:
        if v not in _PRIORIDADES_VALIDAS:
            raise ValueError(
                f"prioridade inválida: '{v}'. Valores aceitos: {sorted(_PRIORIDADES_VALIDAS)}"
            )
        return v


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _calcular_hash(protocolo: str, cns: str, cpf: str,
                   data_emissao: str, data_validade: str,
                   prioridade: str, indicacao: Optional[str],
                   itens: list) -> str:
    """
    Hash SHA-256 do documento canônico do pedido de exame.
    Versão simplificada para Ticket 15 — módulo completo vem no Ticket 17.
    """
    doc = {
        "protocolo":        protocolo,
        "prescritor_cns":   cns,
        "paciente_cpf":     cpf,
        "data_emissao":     data_emissao,
        "data_validade":    data_validade,
        "prioridade":       prioridade,
        "indicacao_clinica": indicacao,
        "itens": [
            {
                "nome_exame":  item.nome_exame,
                "codigo_tuss": item.codigo_tuss,
                "quantidade":  item.quantidade,
            }
            for item in itens
        ],
        "versao_esquema": "1",
    }
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _localizar_ou_criar_prescritor(conn, cns: str, nome_hint: Optional[str], agora: str) -> int:
    row = conn.execute("SELECT id FROM prescritores WHERE cns = ?", (cns,)).fetchone()
    if row:
        return row["id"]
    nome = normalize_nome(nome_hint or "")
    if not nome:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Prescritor com CNS '{cns}' não encontrado. "
                "Envie 'nome_prescritor' para registrá-lo automaticamente."
            ),
        )
    cursor = conn.execute(
        "INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
        (cns, nome, agora, agora),
    )
    return cursor.lastrowid


def _localizar_ou_criar_paciente(conn, cpf: str, nome: str, agora: str) -> int:
    row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
    if row:
        return row["id"]
    cursor = conn.execute(
        "INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at) VALUES (?, ?, true, ?, ?)",
        (cpf, nome, agora, agora),
    )
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# POST /pedidos-exame — emissão digital
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def criar_pedido_exame(
    payload: PedidoExameIn,
    _=Depends(require_role("prescritor")),
):
    """
    Emite um pedido de exame digitalmente.

    Fluxo:
    1. Localiza ou registra prescritor por CNS
    2. Valida pedido de origem (correcao/renovacao)
    3. Localiza ou registra paciente por CPF
    4. Insere pedido com status 'emitido'
    5. Insere itens com status 'pendente'
    6. Gera hash do documento canônico
    7. Grava evento 'pedido_emitido' no ledger
    """
    if not payload.itens:
        raise HTTPException(status_code=422, detail="O pedido deve conter ao menos um item.")

    cns       = normalize_cns(payload.cns_prescritor)
    cpf       = normalize_cpf(payload.cpf_paciente)
    nome_pac  = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora     = datetime.utcnow().isoformat()

    data_emissao  = date.today().isoformat()
    data_validade = (
        payload.data_validade
        or (date.today() + timedelta(days=_VALIDADE_PADRAO_DIAS)).isoformat()
    )

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)

        if payload.origem_pedido_id is not None:
            origem = conn.execute(
                "SELECT id FROM pedidos_exame WHERE id = ?", (payload.origem_pedido_id,)
            ).fetchone()
            if not origem:
                raise HTTPException(
                    status_code=404,
                    detail=f"Pedido de origem id={payload.origem_pedido_id} não encontrado.",
                )

        # Ticket 63: verificar se paciente já existe antes de criar
        _pac_row = conn.execute("SELECT id FROM pacientes WHERE cpf = ?", (cpf,)).fetchone()
        paciente_existia = _pac_row is not None
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO pedidos_exame
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               origem_pedido_id, prioridade, indicacao_clinica,
               data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'emitido', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id,
                payload.tipo_emissao, payload.origem_pedido_id,
                payload.prioridade, payload.indicacao_clinica,
                data_emissao, data_validade, agora,
            ),
        )
        pedido_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO pedido_exame_itens
                  (pedido_id, nome_exame, codigo_tuss, codigo_sigtap,
                   status_item, quantidade, criado_em)
                VALUES (?, ?, ?, ?, 'pendente', ?, ?)
                """,
                (pedido_id, item.nome_exame, item.codigo_tuss,
                 item.codigo_sigtap, item.quantidade, agora),
            )

        doc_hash = _calcular_hash(
            protocolo, cns, cpf, data_emissao, data_validade,
            payload.prioridade, payload.indicacao_clinica, payload.itens,
        )
        conn.execute(
            "UPDATE pedidos_exame SET assinatura_hash = ? WHERE id = ?",
            (doc_hash, pedido_id),
        )

        ev_emitido = {
            "tipo_emissao":     payload.tipo_emissao,
            "origem_pedido_id": payload.origem_pedido_id,
            "prioridade":       payload.prioridade,
            "itens_count":      len(payload.itens),
        }
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos
              (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_emitido', ?, ?)
            """,
            (pedido_id, json.dumps(ev_emitido, ensure_ascii=False), agora),
        )
        registrar_outbox(conn, "pedido_emitido", "pedido_exame", protocolo, ev_emitido)

        # ------------------------------------------------------------------
        # Ticket 63 — Entrega à carteira digital
        # Se enviar_ao_paciente=True e paciente já existia (tem carteira),
        # cria custódia prescritor→paciente em pedido_exame_custodia.
        # O status do pedido permanece 'emitido' (não há estado
        # 'transferida_paciente' no módulo de exames — exceção documentada).
        # ------------------------------------------------------------------
        entregue_carteira = False

        if payload.enviar_ao_paciente and paciente_existia:
            conn.execute(
                """
                INSERT INTO pedido_exame_custodia
                  (pedido_id, item_id, de, para, transferido_em, dados_json)
                VALUES (?, NULL, 'prescritor', 'paciente', ?, ?)
                """,
                (
                    pedido_id,
                    agora,
                    json.dumps(
                        {
                            "de": "prescritor", "de_id": cns,
                            "para": "paciente", "para_id": cpf,
                            "motivo": "entrega_carteira_digital",
                            "via": "emissao_direta",
                        },
                        ensure_ascii=False,
                    ),
                ),
            )
            conn.execute(
                """
                INSERT INTO pedido_exame_eventos
                  (pedido_id, tipo_evento, dados_json, criado_em)
                VALUES (?, 'custodia_transferida', ?, ?)
                """,
                (
                    pedido_id,
                    json.dumps(
                        {
                            "de": "prescritor", "de_id": cns,
                            "para": "paciente", "para_id": cpf,
                            "via": "emissao_direta",
                        },
                        ensure_ascii=False,
                    ),
                    agora,
                ),
            )
            entregue_carteira = True

        return {
            "id":               pedido_id,
            "protocolo":        protocolo,
            "status":           "emitido",
            "tipo_emissao":     payload.tipo_emissao,
            "prioridade":       payload.prioridade,
            "data_emissao":     data_emissao,
            "data_validade":    data_validade,
            "itens_count":      len(payload.itens),
            "documento_hash":   doc_hash,
            # Ticket 63 — resultado da entrega à carteira digital
            # True  = custódia criada imediatamente em pedido_exame_custodia
            # False = pedido em 'emitido'; frontend exibe link de acesso
            "entregue_carteira": entregue_carteira,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/fisica — emissão exclusivamente física (fire-and-forget)
# ---------------------------------------------------------------------------

@router.post("/fisica", status_code=201)
def criar_pedido_exame_fisico(
    payload: FisicaExameIn,
    _=Depends(require_role("prescritor")),
):
    """
    Registra um pedido de exame emitido exclusivamente em papel.

    Diferenças em relação à emissão digital:
    - Status final do pedido: encerrado_fisico
    - Status de cada item: encerrado_fisico
    - Sem cadeia de custódia (nenhum registro em pedido_exame_custodia)
    - Dois eventos no ledger: pedido_impresso + encerrado_localmente
    - cpf_paciente é opcional (sentinela '00000000000' se ausente)

    Fire-and-forget: o frontend imprime sem aguardar resposta.
    """
    if not payload.itens:
        raise HTTPException(status_code=422, detail="O pedido deve conter ao menos um item.")

    cns      = normalize_cns(payload.cns_prescritor)
    cpf      = normalize_cpf(payload.cpf_paciente) if payload.cpf_paciente else _CPF_NAO_IDENTIFICADO
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora    = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)
        paciente_id   = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO pedidos_exame
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               prioridade, indicacao_clinica, data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'encerrado_fisico', 'fisico', ?, ?, ?, NULL, ?)
            """,
            (
                protocolo, prescritor_id, paciente_id,
                payload.prioridade, payload.indicacao_clinica,
                data_emissao, agora,
            ),
        )
        pedido_id = cursor.lastrowid

        for item in payload.itens:
            conn.execute(
                """
                INSERT INTO pedido_exame_itens
                  (pedido_id, nome_exame, codigo_tuss, codigo_sigtap,
                   status_item, quantidade, criado_em)
                VALUES (?, ?, ?, ?, 'encerrado_fisico', ?, ?)
                """,
                (pedido_id, item.nome_exame, item.codigo_tuss,
                 item.codigo_sigtap, item.quantidade, agora),
            )

        # Dois eventos no ledger (mesmo padrão do fluxo físico da prescrição)
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_impresso', ?, ?)
            """,
            (
                pedido_id,
                json.dumps({
                    "tipo_emissao":      "fisico",
                    "itens_count":       len(payload.itens),
                    "cpf_identificado":  payload.cpf_paciente is not None,
                }, ensure_ascii=False),
                agora,
            ),
        )
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'encerrado_localmente', ?, ?)
            """,
            (
                pedido_id,
                json.dumps({
                    "status_novo":           "encerrado_fisico",
                    "motivo":                "emissao_exclusivamente_fisica",
                    "sem_custodia_digital":  True,
                }, ensure_ascii=False),
                agora,
            ),
        )

        return {
            "protocolo":     protocolo,
            "status":        "encerrado_fisico",
            "tipo_emissao":  "fisico",
            "prioridade":    payload.prioridade,
            "data_emissao":  data_emissao,
            "itens_count":   len(payload.itens),
        }


# ---------------------------------------------------------------------------
# Helpers internos compartilhados pelos endpoints de fluxo
# ---------------------------------------------------------------------------

def _get_pedido_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")
    return dict(row)


def _get_itens(conn, pedido_id: int) -> list:
    return [
        dict(r) for r in conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE pedido_id = ?", (pedido_id,)
        ).fetchall()
    ]


def _recalcular_e_atualizar_status_pedido(conn, pedido_id: int, agora: str) -> str:
    itens = conn.execute(
        "SELECT status_item FROM pedido_exame_itens WHERE pedido_id = ?", (pedido_id,)
    ).fetchall()
    novo_status = derivar_status_pedido([i["status_item"] for i in itens])
    conn.execute(
        "UPDATE pedidos_exame SET status = ? WHERE id = ?",
        (novo_status, pedido_id),
    )
    return novo_status


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo} — consulta individual
# ---------------------------------------------------------------------------

@router.get("/{protocolo}")
def get_pedido_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (MVP, futuro: prestador)
):
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)
        itens  = _get_itens(conn, pedido["id"])
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, dados_json, criado_em FROM pedido_exame_eventos "
                "WHERE pedido_id = ? ORDER BY id ASC",
                (pedido["id"],),
            ).fetchall()
        ]
        return {**pedido, "itens": itens, "eventos": eventos}


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/custodia — histórico de custódia
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/custodia")
def get_custodia_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin", "paciente")),
):
    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)
        registros = conn.execute(
            "SELECT de, para, transferido_em, dados_json FROM pedido_exame_custodia "
            "WHERE pedido_id = ? ORDER BY id ASC",
            (pedido["id"],),
        ).fetchall()
        return {"protocolo": protocolo, "custodia": [dict(r) for r in registros]}


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/agendar — nível do pedido
# Transição: emitido → agendado
# Todos os itens pendentes → agendado
# Cria registro de custódia: paciente → prestador_exame
# ---------------------------------------------------------------------------

class AgendarIn(BaseModel):
    cnpj_prestador: str
    nome_prestador: Optional[str] = None
    data_agendamento: Optional[str] = None


@router.post("/{protocolo}/agendar", status_code=201)
def agendar_pedido_exame(
    protocolo: str,
    payload: AgendarIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Registra o agendamento de um pedido com um prestador de exames.

    - Pedido deve estar em 'emitido' ou 'agendado' (re-agendamento parcial)
    - Itens 'pendente' → 'agendado'
    - Custódia: paciente → prestador_exame (nível pedido)
    - Status do pedido recalculado via derivar_status_pedido()
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal ({pedido['status']}).",
            )
        if pedido["status"] not in ("emitido", "agendado"):
            raise HTTPException(
                status_code=422,
                detail=f"Agendamento requer status 'emitido' ou 'agendado'. Status atual: '{pedido['status']}'.",
            )

        itens = _get_itens(conn, pedido["id"])
        itens_agendar = [i for i in itens if i["status_item"] == "pendente"]

        if not itens_agendar:
            raise HTTPException(status_code=422, detail="Nenhum item 'pendente' disponível para agendar.")

        for item in itens_agendar:
            conn.execute(
                "UPDATE pedido_exame_itens SET status_item = 'agendado' WHERE id = ?",
                (item["id"],),
            )

        conn.execute(
            """
            INSERT INTO pedido_exame_custodia (pedido_id, item_id, de, para, transferido_em, dados_json)
            VALUES (?, NULL, 'paciente', ?, ?, ?)
            """,
            (
                pedido["id"],
                payload.cnpj_prestador,
                agora,
                json.dumps({
                    "nome_prestador":   payload.nome_prestador,
                    "data_agendamento": payload.data_agendamento,
                }, ensure_ascii=False),
            ),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_agendado', ?, ?)
            """,
            (
                pedido["id"],
                json.dumps({
                    "cnpj_prestador":   payload.cnpj_prestador,
                    "nome_prestador":   payload.nome_prestador,
                    "data_agendamento": payload.data_agendamento,
                    "itens_agendados":  len(itens_agendar),
                }, ensure_ascii=False),
                agora,
            ),
        )

        return {
            "protocolo":       protocolo,
            "status":          novo_status,
            "itens_agendados": len(itens_agendar),
            "cnpj_prestador":  payload.cnpj_prestador,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/itens/{item_id}/coletar — nível do item
# Transição do item: agendado → coletado
# O item é a unidade operacional de coleta.
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/itens/{item_id}/coletar", status_code=201)
def coletar_item_exame(
    protocolo: str,
    item_id: int,
    _=Depends(require_role("prescritor", "admin", "dispensador")),  # dispensador = clínica/lab (MVP, futuro: prestador)
):
    """
    Registra a coleta de um item específico.

    Item: agendado → coletado
    Status do pedido recalculado automaticamente via derivar_status_pedido().
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(status_code=422, detail=f"Pedido '{protocolo}' está em estado terminal.")

        item = conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE id = ? AND pedido_id = ?",
            (item_id, pedido["id"]),
        ).fetchone()

        if not item:
            raise HTTPException(
                status_code=404, detail=f"Item {item_id} não encontrado no pedido '{protocolo}'."
            )

        if item["status_item"] != "agendado":
            raise HTTPException(
                status_code=422,
                detail=f"Coleta requer item em 'agendado'. Status atual: '{item['status_item']}'.",
            )

        conn.execute(
            "UPDATE pedido_exame_itens SET status_item = 'coletado' WHERE id = ?",
            (item_id,),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        ev_coletado = {"item_id": item_id, "nome_exame": item["nome_exame"]}
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_coletado', ?, ?)
            """,
            (pedido["id"], json.dumps(ev_coletado, ensure_ascii=False), agora),
        )
        registrar_outbox(conn, "pedido_coletado", "pedido_exame", protocolo, ev_coletado)

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "coletado",
            "status_pedido": novo_status,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/cancelar
# ---------------------------------------------------------------------------

class CancelarIn(BaseModel):
    motivo: Optional[str] = None


@router.post("/{protocolo}/cancelar", status_code=200)
def cancelar_pedido_exame(
    protocolo: str,
    payload: CancelarIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Cancela o pedido e todos os itens não terminais.
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' já está em estado terminal ({pedido['status']}).",
            )

        itens = _get_itens(conn, pedido["id"])
        cancelados = 0
        for item in itens:
            if not eh_terminal_item_exame(item["status_item"]):
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'cancelado' WHERE id = ?",
                    (item["id"],),
                )
                cancelados += 1

        conn.execute(
            "UPDATE pedidos_exame SET status = 'cancelado' WHERE id = ?",
            (pedido["id"],),
        )

        ev_cancelado = {
            "status_anterior":  pedido["status"],
            "motivo":           payload.motivo,
            "itens_cancelados": cancelados,
        }
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_cancelado', ?, ?)
            """,
            (pedido["id"], json.dumps(ev_cancelado, ensure_ascii=False), agora),
        )
        registrar_outbox(conn, "pedido_cancelado", "pedido_exame", protocolo, ev_cancelado)

        return {
            "protocolo":        protocolo,
            "status":           "cancelado",
            "itens_cancelados": cancelados,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/itens/{item_id}/resultado
# Transição: coletado → em_analise → resultado_disponivel (colapsado para MVP)
# Dois eventos no ledger: pedido_em_analise + resultado_registrado
# ---------------------------------------------------------------------------

class ResultadoIn(BaseModel):
    resultado_resumo: Optional[str] = None
    resultado_url:    Optional[str] = None


@router.post("/{protocolo}/itens/{item_id}/resultado", status_code=201)
def registrar_resultado_item(
    protocolo: str,
    item_id: int,
    payload: ResultadoIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Registra o resultado de um item de exame.

    Fluxo MVP colapsado (dois eventos no ledger):
        coletado → em_analise   (pedido_em_analise)
        em_analise → resultado_disponivel  (resultado_registrado)

    Status do pedido recalculado automaticamente.
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if eh_terminal_pedido(pedido["status"]):
            raise HTTPException(
                status_code=422,
                detail=f"Pedido '{protocolo}' está em estado terminal.",
            )

        item = conn.execute(
            "SELECT * FROM pedido_exame_itens WHERE id = ? AND pedido_id = ?",
            (item_id, pedido["id"]),
        ).fetchone()

        if not item:
            raise HTTPException(
                status_code=404,
                detail=f"Item {item_id} não encontrado no pedido '{protocolo}'.",
            )

        if item["status_item"] not in ("coletado", "em_analise"):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Registro de resultado requer item em 'coletado' ou 'em_analise'. "
                    f"Status atual: '{item['status_item']}'."
                ),
            )

        # Evento intermediário: em_analise (semântica preservada no ledger)
        if item["status_item"] == "coletado":
            conn.execute(
                """
                INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
                VALUES (?, 'pedido_em_analise', ?, ?)
                """,
                (
                    pedido["id"],
                    json.dumps({"item_id": item_id, "nome_exame": item["nome_exame"]},
                               ensure_ascii=False),
                    agora,
                ),
            )

        # Atualizar item com resultado e transicionar para resultado_disponivel
        conn.execute(
            """
            UPDATE pedido_exame_itens
            SET status_item = 'resultado_disponivel',
                resultado_resumo = ?,
                resultado_url = ?,
                resultado_em = ?
            WHERE id = ?
            """,
            (payload.resultado_resumo, payload.resultado_url, agora, item_id),
        )

        novo_status = _recalcular_e_atualizar_status_pedido(conn, pedido["id"], agora)

        ev_resultado = {
            "item_id":    item_id,
            "nome_exame": item["nome_exame"],
            "tem_resumo": payload.resultado_resumo is not None,
            "tem_url":    payload.resultado_url is not None,
        }
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'resultado_registrado', ?, ?)
            """,
            (pedido["id"], json.dumps(ev_resultado, ensure_ascii=False), agora),
        )
        registrar_outbox(conn, "resultado_registrado", "pedido_exame", protocolo, ev_resultado)

        return {
            "protocolo":     protocolo,
            "item_id":       item_id,
            "status_item":   "resultado_disponivel",
            "status_pedido": novo_status,
        }


# ---------------------------------------------------------------------------
# POST /pedidos-exame/{protocolo}/encerrar
# Ciência formal do resultado pelo prescritor/paciente.
# Transição: itens resultado_disponivel → encerrado
# Pedido: resultado_disponivel → encerrado
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/encerrar", status_code=200)
def encerrar_pedido_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin", "paciente")),
):
    """
    Registra a ciência formal do resultado.

    "resultado_disponivel" e "encerrado" NÃO são o mesmo estado:
    - resultado_disponivel: laudo pronto, aguarda ciência
    - encerrado: ciência registrada, ciclo completo

    Todos os itens em 'resultado_disponivel' → 'encerrado'.
    Pedido → 'encerrado'.
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        pedido = _get_pedido_ou_404(conn, protocolo)

        if pedido["status"] != "resultado_disponivel":
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Encerramento requer pedido em 'resultado_disponivel'. "
                    f"Status atual: '{pedido['status']}'."
                ),
            )

        itens = _get_itens(conn, pedido["id"])
        encerrados = 0
        for item in itens:
            if item["status_item"] == "resultado_disponivel":
                conn.execute(
                    "UPDATE pedido_exame_itens SET status_item = 'encerrado' WHERE id = ?",
                    (item["id"],),
                )
                encerrados += 1

        conn.execute(
            "UPDATE pedidos_exame SET status = 'encerrado' WHERE id = ?",
            (pedido["id"],),
        )

        ev_encerrado = {
            "itens_encerrados": encerrados,
            "motivo": "ciencia_registrada",
        }
        conn.execute(
            """
            INSERT INTO pedido_exame_eventos (pedido_id, tipo_evento, dados_json, criado_em)
            VALUES (?, 'pedido_encerrado', ?, ?)
            """,
            (pedido["id"], json.dumps(ev_encerrado, ensure_ascii=False), agora),
        )
        registrar_outbox(conn, "pedido_encerrado", "pedido_exame", protocolo, ev_encerrado)

        return {
            "protocolo":       protocolo,
            "status":          "encerrado",
            "itens_encerrados": encerrados,
        }


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/pdf — PDF do pedido de exame
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/pdf")
def get_pdf_pedido_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin")),
):
    from fastapi.responses import StreamingResponse
    from app.domain.pdf_pedido_exame import gerar_pdf_pedido_exame
    import io as _io

    with get_tx() as conn:
        row = conn.execute(
            """
            SELECT
                pe.protocolo, pe.status, pe.tipo_emissao, pe.prioridade,
                pe.indicacao_clinica, pe.assinatura_hash,
                pe.data_emissao, pe.data_validade,
                pr.nome AS nome_prescritor, pr.cns AS cns_prescritor,
                pa.nome AS nome_paciente, pa.cpf AS cpf_paciente
            FROM pedidos_exame pe
            JOIN prescritores pr ON pr.id = pe.prescritor_id
            JOIN pacientes    pa ON pa.id = pe.paciente_id
            WHERE pe.protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Pedido '{protocolo}' não encontrado.")

        itens = conn.execute(
            """
            SELECT nome_exame, codigo_tuss, codigo_sigtap, quantidade, status_item
            FROM pedido_exame_itens WHERE pedido_id = (
                SELECT id FROM pedidos_exame WHERE protocolo = ?
            )
            ORDER BY id
            """,
            (protocolo,),
        ).fetchall()

    pdf_bytes = gerar_pdf_pedido_exame(
        protocolo        = row["protocolo"],
        status           = row["status"],
        tipo_emissao     = row["tipo_emissao"],
        prioridade       = row["prioridade"] or "rotina",
        indicacao_clinica = row["indicacao_clinica"],
        assinatura_hash  = row["assinatura_hash"],
        data_emissao     = row["data_emissao"],
        data_validade    = row["data_validade"],
        nome_prescritor  = row["nome_prescritor"],
        cns_prescritor   = row["cns_prescritor"],
        nome_paciente    = row["nome_paciente"],
        cpf_paciente     = row["cpf_paciente"],
        itens            = [dict(i) for i in itens],
    )

    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="pedido-exame-{protocolo[:8]}.pdf"'
            ),
        },
    )


# ---------------------------------------------------------------------------
# GET /pedidos-exame/{protocolo}/qr — QR Code (aponta para validação pública)
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/qr")
def qr_code_pedido_exame(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin")),
):
    import io as _io
    import qrcode
    from fastapi.responses import Response as _Response
    from app.config import BASE_URL

    with get_tx() as conn:
        existe = conn.execute(
            "SELECT 1 FROM pedidos_exame WHERE protocolo = ?", (protocolo,)
        ).fetchone()

    if not existe:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

    url = f"{BASE_URL}/public/exames/{protocolo}"
    qr  = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buf = _io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return _Response(content=buf.read(), media_type="image/png")
