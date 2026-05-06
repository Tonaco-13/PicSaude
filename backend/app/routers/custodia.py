"""
custodia.py
===========
Endpoints de custódia sanitária digital do PicSaúde.

Modelo de custódia:
  - A prescrição percorre: prescritor → paciente → dispensador → (paciente | prescritor)
  - Cada etapa é registrada em prescricao_custodia
  - Dispensação parcial: cada item pode ser dispensado individualmente
  - Devolução: dispensador ou paciente devolve ao prescritor para correção
  - Abandono no balcão: dispensador devolve ao paciente sem dispensar

Ledger:
  - Todo evento de custódia gera uma entrada em prescricao_eventos (imutável)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.confianca_cuidado import calcular_score_confianca_dispensacao
from app.domain.states import ESTADOS_PRESCRICAO, ESTADOS_TERMINAIS_PRESCRICAO
from app.utils.helpers import normalize_cnpj, normalize_cpf, normalize_cns

router = APIRouter(prefix="/prescricoes", tags=["custodia"])


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DETENTORES_VALIDOS = {"paciente", "dispensador", "prescritor"}

_TRANSICOES_VALIDAS = {
    ("prescritor",  "paciente"),
    ("paciente",    "dispensador"),
    ("dispensador", "paciente"),
    ("dispensador", "prescritor"),
    ("paciente",    "prescritor"),
}

# Estados em que a prescrição aceita transferência de custódia.
# = ESTADOS_PRESCRICAO − ESTADOS_TERMINAIS (estados não-terminais, exceto expirada).
# Fonte única: domain/states.py
_STATUS_PRESCRICAO_ATIVOS = ESTADOS_PRESCRICAO - ESTADOS_TERMINAIS_PRESCRICAO - {"expirada"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TransferirCustodiaIn(BaseModel):
    de: str           # prescritor | paciente | dispensador
    de_id: str        # CNS | CPF | CNPJ normalizado
    para: str         # prescritor | paciente | dispensador
    para_id: str      # CNS | CPF | CNPJ normalizado
    motivo: Optional[str] = None

    @field_validator("de", "para")
    @classmethod
    def tipo_valido(cls, v: str) -> str:
        if v not in _DETENTORES_VALIDOS:
            raise ValueError(f"Tipo de detentor inválido: '{v}'. Aceitos: {sorted(_DETENTORES_VALIDOS)}")
        return v


class DispensarItemIn(BaseModel):
    cnpj_estabelecimento:  str
    quantidade_dispensada: int
    dispensado_por:        Optional[str] = None
    lote:                  Optional[str] = None
    fabricante:            Optional[str] = None
    observacao:            Optional[str] = None
    # Ticket 44 — Fase 2: token de circulação atomizada (opcional)
    # Quando presente, autoriza dispensação de item específico e garante isolamento.
    codigo_curto_token:    Optional[str] = None
    # Tratamento 4 — origem do contexto institucional: 'cnes_verificado' | 'manual' | None
    origem_contexto:              Optional[str]  = None
    # Ticket 46 — gate leve: True quando usuário explicitamente confirmou operação manual
    contexto_confirmado_manual:   Optional[bool] = None

    @field_validator("quantidade_dispensada")
    @classmethod
    def qtd_positiva(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantidade_dispensada deve ser maior que zero")
        return v


class DevolverItemIn(BaseModel):
    para:  str             # paciente | prescritor
    motivo: Optional[str] = None

    @field_validator("para")
    @classmethod
    def destino_valido(cls, v: str) -> str:
        if v not in {"paciente", "prescritor"}:
            raise ValueError("para deve ser 'paciente' ou 'prescritor'")
        return v


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_prescricao_by_protocolo(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM prescricoes WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Prescrição '{protocolo}' não encontrada.")
    return dict(row)


def _fechar_custodia_ativa(conn, prescricao_id: int, item_id: Optional[int], agora: str) -> None:
    """Fecha a custódia ativa (encerrada_em = agora) para a prescrição ou item."""
    if item_id is None:
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (agora, prescricao_id),
        )
    else:
        conn.execute(
            """
            UPDATE prescricao_custodia
               SET encerrada_em = ?
             WHERE prescricao_id = ? AND item_id = ? AND encerrada_em IS NULL
            """,
            (agora, prescricao_id, item_id),
        )


def _abrir_custodia(conn, prescricao_id: int, item_id: Optional[int],
                    detentor_tipo: str, detentor_id: str,
                    motivo: Optional[str], agora: str) -> None:
    """Abre uma nova custódia."""
    conn.execute(
        """
        INSERT INTO prescricao_custodia
          (prescricao_id, item_id, detentor_tipo, detentor_id,
           transferida_em, encerrada_em, motivo, created_at)
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
        """,
        (prescricao_id, item_id, detentor_tipo, detentor_id, agora, motivo, agora),
    )


def _gravar_evento(conn, prescricao_id: int, tipo_evento: str,
                   ator_tipo: str, ator_id: str, payload: dict, agora: str) -> None:
    conn.execute(
        """
        INSERT INTO prescricao_eventos
          (prescricao_id, tipo_evento, ator_tipo, ator_id, payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (prescricao_id, tipo_evento, ator_tipo, ator_id,
         json.dumps(payload, ensure_ascii=False), agora),
    )


def _recalcular_status_prescricao(conn, prescricao_id: int, agora: str) -> str:
    """
    Recalcula o status da prescrição com base no status_item de todos os itens.
    Atualiza a tabela e retorna o novo status.
    """
    rows = conn.execute(
        "SELECT status_item FROM prescricao_itens WHERE prescricao_id = ?",
        (prescricao_id,),
    ).fetchall()

    total = len(rows)
    dispensados       = sum(1 for r in rows if r["status_item"] == "dispensado")
    # Itens encerrados definitivamente: sem possibilidade de dispensação
    #   cancelado         → revogação clínica
    #   estornado         → dispensação revertida após registro
    #   devolvido_prescritor → erro identificado, aguarda correção
    #   encerrado_fisico  → emitido apenas em papel, sem cadeia digital
    encerrados        = sum(1 for r in rows if r["status_item"] in
                            {"cancelado", "estornado", "devolvido_prescritor", "encerrado_fisico"})
    # Itens operacionais: tudo exceto encerrados definitivamente
    ativos            = total - encerrados

    if ativos == 0:
        # Todos os itens foram encerrados sem dispensação
        novo_status = "cancelada"
    elif dispensados == 0:
        novo_status = "em_custodia"
    elif dispensados >= ativos:
        novo_status = "dispensada"
    else:
        novo_status = "parcialmente_dispensada"

    conn.execute(
        "UPDATE prescricoes SET status = ?, updated_at = ? WHERE id = ?",
        (novo_status, agora, prescricao_id),
    )
    return novo_status


def _normalizar_id(detentor_tipo: str, raw_id: str) -> str:
    if detentor_tipo == "paciente":
        return normalize_cpf(raw_id)
    if detentor_tipo == "dispensador":
        return normalize_cnpj(raw_id)
    # prescritor
    return normalize_cns(raw_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/custodia")
def get_custodia(protocolo: str):
    """
    Retorna a custódia ativa e o histórico completo de transferências.
    """
    with get_tx() as conn:
        presc = _get_prescricao_by_protocolo(conn, protocolo)

        ativa = conn.execute(
            """
            SELECT * FROM prescricao_custodia
             WHERE prescricao_id = ? AND item_id IS NULL AND encerrada_em IS NULL
            """,
            (presc["id"],),
        ).fetchone()

        historico = conn.execute(
            """
            SELECT * FROM prescricao_custodia
             WHERE prescricao_id = ?
             ORDER BY transferida_em
            """,
            (presc["id"],),
        ).fetchall()

        itens_custodia = conn.execute(
            """
            SELECT c.*, i.nome_medicamento, i.status_item
              FROM prescricao_custodia c
              JOIN prescricao_itens i ON i.id = c.item_id
             WHERE c.prescricao_id = ? AND c.item_id IS NOT NULL AND c.encerrada_em IS NULL
             ORDER BY c.item_id
            """,
            (presc["id"],),
        ).fetchall()

        return {
            "protocolo": protocolo,
            "status_prescricao": presc["status"],
            "custodia_ativa": dict(ativa) if ativa else None,
            "itens_custodia_ativa": [dict(r) for r in itens_custodia],
            "historico": [dict(r) for r in historico],
        }


@router.post("/{protocolo}/custodia/transferir", status_code=201)
def transferir_custodia(protocolo: str, payload: TransferirCustodiaIn, _=Depends(require_role("prescritor", "dispensador"))):
    """
    Transfere a custódia da prescrição inteira entre detentores.

    Transições permitidas:
      prescritor  → paciente      (emissão digital)
      paciente    → dispensador   (apresentação na farmácia)
      dispensador → paciente      (abandono no balcão / devolução parcial)
      dispensador → prescritor    (erro de prescrição)
      paciente    → prescritor    (devolução voluntária)
    """
    if (payload.de, payload.para) not in _TRANSICOES_VALIDAS:
        raise HTTPException(
            status_code=422,
            detail=f"Transição '{payload.de}' → '{payload.para}' não é permitida.",
        )

    de_id  = _normalizar_id(payload.de, payload.de_id)
    para_id = _normalizar_id(payload.para, payload.para_id)
    agora  = datetime.utcnow().isoformat()

    with get_tx() as conn:
        presc = _get_prescricao_by_protocolo(conn, protocolo)

        if presc["status"] not in _STATUS_PRESCRICAO_ATIVOS:
            raise HTTPException(
                status_code=409,
                detail=f"Prescrição está com status '{presc['status']}' e não pode ser transferida.",
            )

        _fechar_custodia_ativa(conn, presc["id"], None, agora)
        _abrir_custodia(conn, presc["id"], None, payload.para, para_id, payload.motivo, agora)

        # Atualizar status da prescrição conforme destino
        novo_status = presc["status"]
        if payload.para == "paciente" and presc["status"] == "pendente":
            novo_status = "transferida_paciente"
        elif payload.para == "dispensador":
            novo_status = "em_custodia"
        elif payload.para == "prescritor":
            novo_status = "pendente"   # volta ao prescritor para correção

        conn.execute(
            "UPDATE prescricoes SET status = ?, updated_at = ? WHERE id = ?",
            (novo_status, agora, presc["id"]),
        )

        # Quando dispensador devolve ao paciente (abandono), itens em_custodia voltam a pendente
        if payload.de == "dispensador" and payload.para == "paciente":
            conn.execute(
                """
                UPDATE prescricao_itens SET status_item = 'pendente', updated_at = ?
                 WHERE prescricao_id = ? AND status_item = 'em_custodia'
                """,
                (agora, presc["id"]),
            )
            conn.execute(
                """
                UPDATE prescricao_custodia SET encerrada_em = ?
                 WHERE prescricao_id = ? AND item_id IS NOT NULL AND encerrada_em IS NULL
                """,
                (agora, presc["id"]),
            )

        _gravar_evento(conn, presc["id"], "custodia_transferida", payload.de, de_id,
                       {"de": payload.de, "de_id": de_id,
                        "para": payload.para, "para_id": para_id,
                        "motivo": payload.motivo}, agora)

        return {
            "protocolo": protocolo,
            "status": novo_status,
            "custodia_atual": {"detentor_tipo": payload.para, "detentor_id": para_id},
        }


@router.post("/{protocolo}/itens/{item_id}/dispensar", status_code=201)
def dispensar_item(protocolo: str, item_id: int, payload: DispensarItemIn, _=Depends(require_role("dispensador"))):
    """
    Registra a dispensação (total ou parcial) de um item da prescrição.

    - Valida que o item pertence à prescrição.
    - Valida que quantidade_dispensada não ultrapassa o saldo disponível.
    - Quando o item fica totalmente dispensado → status_item = 'dispensado'.
    - Após cada dispensação, recalcula o status geral da prescrição.
    - Fecha a custódia ativa do item e grava evento no ledger.
    """
    cnpj = normalize_cnpj(payload.cnpj_estabelecimento)
    agora = datetime.utcnow().isoformat()
    agora_utc = datetime.now(timezone.utc)

    with get_tx() as conn:
        presc = _get_prescricao_by_protocolo(conn, protocolo)

        item = conn.execute(
            "SELECT * FROM prescricao_itens WHERE id = ? AND prescricao_id = ?",
            (item_id, presc["id"]),
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} não encontrado na prescrição.")

        # -----------------------------------------------------------------------
        # Ticket 44 — Fase 2: validação de token atomizado (quando fornecido)
        # -----------------------------------------------------------------------
        _origem_token: str | None = None
        _token_row = None

        if payload.codigo_curto_token:
            _token_row = conn.execute(
                "SELECT * FROM tokens_apresentacao WHERE codigo_curto = ?",
                (payload.codigo_curto_token,),
            ).fetchone()

            if not _token_row:
                raise HTTPException(status_code=404, detail="Token não encontrado.")

            # Verifica se o token é de item (circulação atomizada)
            if _token_row["item_id"] is None:
                raise HTTPException(
                    status_code=422,
                    detail="Token fornecido é de prescrição inteira; use o fluxo de dispensação convencional.",
                )

            # Isolamento: o token deve corresponder exatamente ao item solicitado
            if _token_row["item_id"] != item_id:
                raise HTTPException(
                    status_code=403,
                    detail=(
                        f"Token '{payload.codigo_curto_token}' não autoriza dispensação do item {item_id}. "
                        "Isolamento de circulação atomizada violado."
                    ),
                )

            # Verifica status do token
            if _token_row["status"] in ("revogado", "expirado"):
                raise HTTPException(
                    status_code=410,
                    detail=f"Token '{payload.codigo_curto_token}' está {_token_row['status']}.",
                )

            # Verifica expiração temporal
            try:
                expira_em = datetime.fromisoformat(_token_row["expira_em"])
                if expira_em.tzinfo is None:
                    expira_em = expira_em.replace(tzinfo=timezone.utc)
                if agora_utc > expira_em:
                    # Lazily marca como expirado
                    conn.execute(
                        "UPDATE tokens_apresentacao SET status = 'expirado' WHERE id = ?",
                        (_token_row["id"],),
                    )
                    raise HTTPException(
                        status_code=410,
                        detail=f"Token '{payload.codigo_curto_token}' expirou.",
                    )
            except (ValueError, TypeError):
                pass  # expira_em malformado — segue sem rejeitar por tempo

            _origem_token = "atomizado"

        _BLOQUEADOS_DISPENSAR = {"dispensado", "cancelado", "devolvido_prescritor",
                                  "estornado", "encerrado_fisico"}
        if item["status_item"] in _BLOQUEADOS_DISPENSAR:
            raise HTTPException(
                status_code=409,
                detail=f"Item com status '{item['status_item']}' não pode ser dispensado.",
            )

        # Calcular saldo disponível
        ja_dispensado = conn.execute(
            "SELECT COALESCE(SUM(quantidade_dispensada), 0) AS total FROM dispensacoes WHERE prescricao_item_id = ?",
            (item_id,),
        ).fetchone()["total"]

        prescrito = item["quantidade"] or 0
        saldo = prescrito - ja_dispensado

        if saldo <= 0:
            raise HTTPException(status_code=409, detail="Não há saldo disponível para dispensação neste item.")
        if payload.quantidade_dispensada > saldo:
            raise HTTPException(
                status_code=422,
                detail=f"Quantidade solicitada ({payload.quantidade_dispensada}) supera o saldo disponível ({saldo}).",
            )

        # Gravar dispensação
        conn.execute(
            """
            INSERT INTO dispensacoes
              (prescricao_item_id, cnpj_estabelecimento, quantidade_dispensada,
               dispensado_por, dispensado_em, lote, fabricante, observacao,
               origem_contexto, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (item_id, cnpj, payload.quantidade_dispensada, payload.dispensado_por,
             agora, payload.lote, payload.fabricante, payload.observacao,
             payload.origem_contexto, agora),
        )

        novo_saldo = saldo - payload.quantidade_dispensada
        novo_status_item = "dispensado" if novo_saldo == 0 else "em_custodia"

        conn.execute(
            "UPDATE prescricao_itens SET status_item = ?, updated_at = ? WHERE id = ?",
            (novo_status_item, agora, item_id),
        )

        # Fechar custódia ativa do item e abrir nova (de volta ao paciente) se dispensação total
        if novo_status_item == "dispensado":
            _fechar_custodia_ativa(conn, presc["id"], item_id, agora)
        else:
            # Dispensação parcial: item ainda fica com dispensador — mantém custódia aberta
            # Garante que há custódia ativa do item para o dispensador
            ativa = conn.execute(
                """
                SELECT id FROM prescricao_custodia
                 WHERE prescricao_id = ? AND item_id = ? AND encerrada_em IS NULL
                """,
                (presc["id"], item_id),
            ).fetchone()
            if not ativa:
                _abrir_custodia(conn, presc["id"], item_id, "dispensador", cnpj, "dispensacao_parcial", agora)

        novo_status_prescricao = _recalcular_status_prescricao(conn, presc["id"], agora)

        # Ticket 44 — Fase 2: invalidação lazy do token quando item chega ao estado terminal
        if _token_row and novo_status_item == "dispensado":
            conn.execute(
                "UPDATE tokens_apresentacao SET status = 'expirado' WHERE id = ?",
                (_token_row["id"],),
            )

        # Ticket 50 — recuperar cnes_validacao do evento prescricao_emitida para score
        _cnes_val: Optional[dict] = None
        _ev_emitida = conn.execute(
            """SELECT payload_json FROM prescricao_eventos
               WHERE prescricao_id = ? AND tipo_evento = 'prescricao_emitida'
               ORDER BY created_at DESC LIMIT 1""",
            (presc["id"],),
        ).fetchone()
        if _ev_emitida and _ev_emitida["payload_json"]:
            try:
                _cnes_val = json.loads(_ev_emitida["payload_json"]).get("cnes_validacao")
            except (json.JSONDecodeError, TypeError):
                pass

        score_confianca = calcular_score_confianca_dispensacao(
            _cnes_val,
            payload.origem_contexto,
            payload.contexto_confirmado_manual,
        )

        evento_payload: dict = {
            "item_id": item_id,
            "nome_medicamento": item["nome_medicamento"],
            "quantidade_dispensada": payload.quantidade_dispensada,
            "saldo_restante": novo_saldo,
            "status_item": novo_status_item,
            "lote": payload.lote,
        }
        if _origem_token:
            evento_payload["origem_token"] = _origem_token
        if payload.origem_contexto:
            evento_payload["origem_contexto"] = payload.origem_contexto
        if payload.contexto_confirmado_manual is not None:
            evento_payload["confirmado_manual"] = payload.contexto_confirmado_manual
        # Ticket 50 — score gravado no ledger somente quando contexto é suficiente
        if payload.origem_contexto or _cnes_val:
            evento_payload["score_confianca"] = score_confianca

        _gravar_evento(conn, presc["id"], "item_dispensado", "dispensador", cnpj,
                       evento_payload, agora)

        return {
            "protocolo": protocolo,
            "item_id": item_id,
            "nome_medicamento": item["nome_medicamento"],
            "quantidade_dispensada": payload.quantidade_dispensada,
            "saldo_restante": novo_saldo,
            "status_item": novo_status_item,
            "status_prescricao": novo_status_prescricao,
            # Ticket 50 — score de confiança da operação de dispensação
            "score_confianca": score_confianca,
        }


@router.post("/{protocolo}/itens/{item_id}/devolver", status_code=200)
def devolver_item(protocolo: str, item_id: int, payload: DevolverItemIn, _=Depends(require_role("dispensador", "prescritor"))):
    """
    Devolve um item ao paciente (abandono de compra) ou ao prescritor (erro).

    - Devolução ao prescritor: status_item → 'cancelado', aguarda correção.
    - Devolução ao paciente:   status_item → 'pendente', disponível para nova dispensação.
    """
    agora = datetime.utcnow().isoformat()

    with get_tx() as conn:
        presc = _get_prescricao_by_protocolo(conn, protocolo)

        item = conn.execute(
            "SELECT * FROM prescricao_itens WHERE id = ? AND prescricao_id = ?",
            (item_id, presc["id"]),
        ).fetchone()
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} não encontrado na prescrição.")

        if item["status_item"] == "dispensado":
            raise HTTPException(status_code=409, detail="Item já dispensado não pode ser devolvido.")
        if item["status_item"] in {"cancelado", "encerrado_fisico"}:
            raise HTTPException(status_code=409, detail=f"Item com status '{item['status_item']}' não pode ser devolvido.")

        novo_status_item = "devolvido_prescritor" if payload.para == "prescritor" else "devolvido_paciente"

        conn.execute(
            "UPDATE prescricao_itens SET status_item = ?, updated_at = ? WHERE id = ?",
            (novo_status_item, agora, item_id),
        )

        _fechar_custodia_ativa(conn, presc["id"], item_id, agora)

        novo_status_prescricao = _recalcular_status_prescricao(conn, presc["id"], agora)

        _gravar_evento(conn, presc["id"], "item_devolvido", "dispensador", "sistema",
                       {"item_id": item_id,
                        "nome_medicamento": item["nome_medicamento"],
                        "devolvido_para": payload.para,
                        "motivo": payload.motivo,
                        "novo_status_item": novo_status_item}, agora)

        return {
            "protocolo": protocolo,
            "item_id": item_id,
            "nome_medicamento": item["nome_medicamento"],
            "status_item": novo_status_item,
            "status_prescricao": novo_status_prescricao,
        }
