"""
assinaturas.py
==============
Endpoints de metadados de assinatura digital das prescrições PicSaúde.

PROPÓSITO
---------
Preparar a infraestrutura de dados para futura integração com ICP-Brasil
(tokens A1/A3) e gov.br (assinatura em nuvem).

Na fase MVP:
  - O sistema aceita e armazena os metadados declarados pelo cliente.
  - Nenhuma validação criptográfica real é realizada.
  - O status inicial é sempre 'assinatura_pendente'.
  - O hash enviado é comparado com prescricoes.assinatura_hash para
    detectar divergências de integridade no momento do registro.

Na fase pós-MVP (integração ICP-Brasil):
  - dados_assinatura_b64 (PKCS#7/CAdES) será validado contra a AC raiz ICP-Brasil.
  - status_validacao será atualizado para 'assinada_valida' ou equivalente.
  - Uma entrada no ledger ('assinatura_validada') será inserida.

INVARIANTES
-----------
- Prescrições físicas (tipo_emissao='fisica') nunca têm metadados de assinatura.
- Cada prescrição tem no máximo um registro (UNIQUE em prescricao_id).
- O ledger recebe o evento 'assinatura_registrada' a cada POST bem-sucedido.
- O campo `hash_documento` enviado é contrastado com `prescricoes.assinatura_hash`.
  Se divergirem, o registro é salvo mas `hash_integro=False` é retornado.

ROLES AUTORIZADOS
-----------------
GET  /prescricoes/{protocolo}/assinatura  → prescritor, admin
POST /prescricoes/{protocolo}/assinatura  → prescritor, admin
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn
from app.domain.assinatura import (
    TIPOS_CERTIFICADO_VALIDOS,
    DESCRICAO_STATUS_ASSINATURA,
    calcular_nivel_formal,
)

router = APIRouter(prefix="/prescricoes", tags=["assinaturas"])


# ---------------------------------------------------------------------------
# Schema de entrada
# ---------------------------------------------------------------------------

class AssinaturaIn(BaseModel):
    """
    Metadados de assinatura declarados pelo cliente.

    Todos os campos são opcionais para permitir registro gradual —
    o prescritor pode enviar apenas os dados disponíveis no momento.
    O campo mais importante para integridade é hash_documento.
    """

    tipo_certificado:     Optional[str] = None   # A1, A3, gov_br_nuvem
    emissor:              Optional[str] = None   # CN do certificado / AC
    serial_certificado:   Optional[str] = None   # hex serial
    timestamp_assinatura: Optional[str] = None   # ISO 8601 — quando foi assinado
    hash_documento:       Optional[str] = None   # SHA-256 do doc canônico
    dados_assinatura_b64: Optional[str] = None   # PKCS#7/CAdES em Base64 (stub)

    @field_validator("tipo_certificado")
    @classmethod
    def tipo_valido(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in TIPOS_CERTIFICADO_VALIDOS:
            raise ValueError(
                f"tipo_certificado inválido: '{v}'. "
                f"Valores aceitos: {sorted(TIPOS_CERTIFICADO_VALIDOS)}"
            )
        return v

    @field_validator("hash_documento")
    @classmethod
    def hash_formato(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            limpo = v.strip().lower()
            if len(limpo) != 64 or not all(c in "0123456789abcdef" for c in limpo):
                raise ValueError(
                    "hash_documento deve ser um hex SHA-256 de 64 caracteres."
                )
            return limpo
        return v


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_meta_prescricao(conn, protocolo: str) -> dict:
    """
    Retorna metadados básicos da prescrição ou levanta 404.
    Levanta 400 se for física (sem assinatura digital).
    """
    row = conn.execute(
        """
        SELECT p.id, p.tipo_emissao, p.assinatura_modo, p.assinatura_hash, p.status
          FROM prescricoes p
         WHERE p.protocolo = ?
        """,
        (protocolo,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Prescrição '{protocolo}' não encontrada.",
        )

    if row["tipo_emissao"] == "fisica":
        raise HTTPException(
            status_code=400,
            detail={
                "erro": "assinatura_nao_aplicavel",
                "mensagem": (
                    "Prescrições físicas (tipo_emissao='fisica') não possuem "
                    "assinatura digital. Use o fluxo de emissão digital para "
                    "prescrições que requerem assinatura ICP-Brasil ou gov.br."
                ),
                "nivel_formal": "fisica",
                "protocolo": protocolo,
            },
        )

    return dict(row)


# ---------------------------------------------------------------------------
# GET /{protocolo}/assinatura — consultar metadados
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/assinatura")
def get_assinatura(
    protocolo: str,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Retorna os metadados de assinatura registrados para a prescrição.

    Campos retornados:
    - protocolo, status_prescricao, nivel_formal
    - tipo_certificado, emissor, serial_certificado
    - timestamp_assinatura, hash_documento
    - status_validacao, descricao_status, hash_integro
    - dados_assinatura_b64 (somente se presente — stub MVP)

    404 → prescrição não encontrada
    400 → prescrição física (sem assinatura digital)
    404 → prescrição existe mas ainda não tem metadados de assinatura registrados
    """
    with get_tx() as conn:
        meta = _get_meta_prescricao(conn, protocolo)

        assin = conn.execute(
            """
            SELECT tipo_certificado, emissor, serial_certificado,
                   timestamp_assinatura, hash_documento, dados_assinatura_b64,
                   status_validacao, detalhe_validacao, created_at, updated_at
              FROM prescricao_assinatura
             WHERE prescricao_id = ?
            """,
            (meta["id"],),
        ).fetchone()

        if assin is None:
            nivel = calcular_nivel_formal(meta["assinatura_modo"], meta["tipo_emissao"])
            raise HTTPException(
                status_code=404,
                detail={
                    "erro": "assinatura_nao_registrada",
                    "mensagem": (
                        "Esta prescrição ainda não tem metadados de assinatura "
                        "registrados. Use POST /prescricoes/{protocolo}/assinatura "
                        "para registrá-los."
                    ),
                    "nivel_formal": nivel,
                    "protocolo": protocolo,
                },
            )

    nivel = calcular_nivel_formal(meta["assinatura_modo"], meta["tipo_emissao"])
    hash_integro = (
        assin["hash_documento"] is not None
        and meta["assinatura_hash"] is not None
        and assin["hash_documento"] == meta["assinatura_hash"]
    )

    return {
        "protocolo":           protocolo,
        "status_prescricao":   meta["status"],
        "nivel_formal":        nivel,
        # Metadados de certificado
        "tipo_certificado":    assin["tipo_certificado"],
        "emissor":             assin["emissor"],
        "serial_certificado":  assin["serial_certificado"],
        "timestamp_assinatura": assin["timestamp_assinatura"],
        # Integridade do documento
        "hash_documento":      assin["hash_documento"],
        "hash_prescricao":     meta["assinatura_hash"],
        "hash_integro":        hash_integro,
        # Estado de validação
        "status_validacao":    assin["status_validacao"],
        "descricao_status":    DESCRICAO_STATUS_ASSINATURA.get(assin["status_validacao"], ""),
        "detalhe_validacao":   assin["detalhe_validacao"],
        # Prova criptográfica (stub)
        "dados_assinatura_b64": assin["dados_assinatura_b64"],
        # Timestamps
        "registrado_em":  assin["created_at"],
        "atualizado_em":  assin["updated_at"],
    }


# ---------------------------------------------------------------------------
# POST /{protocolo}/assinatura — registrar / atualizar metadados
# ---------------------------------------------------------------------------

@router.post("/{protocolo}/assinatura", status_code=201)
def registrar_assinatura(
    protocolo: str,
    payload: AssinaturaIn,
    _=Depends(require_role("prescritor", "admin")),
):
    """
    Registra ou atualiza os metadados de assinatura digital de uma prescrição.

    Comportamento MVP
    -----------------
    - Nenhuma validação criptográfica real é realizada.
    - status_validacao inicial = 'assinatura_pendente'.
    - Se já existir um registro para esta prescrição, os campos informados
      são atualizados (upsert — mesmo status permanece, salvo novo).
    - O campo hash_documento é comparado com prescricoes.assinatura_hash:
      a divergência é reportada em hash_integro=False mas NÃO impede o registro.
    - Evento 'assinatura_registrada' é gravado no ledger.

    Status 201 → criação bem-sucedida (primeiro registro)
    Status 200 → atualização de registro existente (via header ou campo)

    Roles autorizados: prescritor, admin.
    """
    with get_tx() as conn:
        meta = _get_meta_prescricao(conn, protocolo)
        agora = datetime.utcnow().isoformat()
        # Ticket 4D.1: instance_id obtido uma vez por transação clínica.
        instance_id = get_instance_id_conn(conn)

        # Verificar se já existe registro
        existente = conn.execute(
            "SELECT id FROM prescricao_assinatura WHERE prescricao_id = ?",
            (meta["id"],),
        ).fetchone()

        hash_integro = (
            payload.hash_documento is not None
            and meta["assinatura_hash"] is not None
            and payload.hash_documento == meta["assinatura_hash"]
        )

        if existente is None:
            conn.execute(
                """
                INSERT INTO prescricao_assinatura
                  (prescricao_id, tipo_certificado, emissor, serial_certificado,
                   timestamp_assinatura, hash_documento, dados_assinatura_b64,
                   status_validacao, detalhe_validacao, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'assinatura_pendente', NULL, ?, ?)
                """,
                (
                    meta["id"],
                    payload.tipo_certificado,
                    payload.emissor,
                    payload.serial_certificado,
                    payload.timestamp_assinatura,
                    payload.hash_documento,
                    payload.dados_assinatura_b64,
                    agora, agora,
                ),
            )
            operacao = "criado"
        else:
            conn.execute(
                """
                UPDATE prescricao_assinatura SET
                    tipo_certificado     = COALESCE(?, tipo_certificado),
                    emissor              = COALESCE(?, emissor),
                    serial_certificado   = COALESCE(?, serial_certificado),
                    timestamp_assinatura = COALESCE(?, timestamp_assinatura),
                    hash_documento       = COALESCE(?, hash_documento),
                    dados_assinatura_b64 = COALESCE(?, dados_assinatura_b64),
                    updated_at           = ?
                WHERE prescricao_id = ?
                """,
                (
                    payload.tipo_certificado,
                    payload.emissor,
                    payload.serial_certificado,
                    payload.timestamp_assinatura,
                    payload.hash_documento,
                    payload.dados_assinatura_b64,
                    agora,
                    meta["id"],
                ),
            )
            operacao = "atualizado"

        # Ticket 4D.1: substituído INSERT manual por registrar_evento_ledger.
        # ator_id preservado intencionalmente (semanticamente fraco — ver §4.3).
        registrar_evento_ledger(
            conn,
            objeto_tipo="prescricao",
            objeto_id=meta["id"],
            tipo_evento="assinatura_registrada",
            instance_id=instance_id,
            payload={
                "tipo_certificado":   payload.tipo_certificado,
                "emissor":            payload.emissor,
                "serial_certificado": payload.serial_certificado,
                "hash_documento":     payload.hash_documento,
                "hash_integro":       hash_integro,
                "tem_dados_b64":      payload.dados_assinatura_b64 is not None,
                "operacao":           operacao,
                "status_validacao":   "assinatura_pendente",
            },
            ator_tipo="prescritor",
            ator_id=meta.get("assinatura_modo") or "sem_modo",
        )

    nivel = calcular_nivel_formal(meta["assinatura_modo"], meta["tipo_emissao"])

    return {
        "protocolo":          protocolo,
        "operacao":           operacao,
        "status_validacao":   "assinatura_pendente",
        "descricao_status":   DESCRICAO_STATUS_ASSINATURA["assinatura_pendente"],
        "nivel_formal":       nivel,
        "hash_integro":       hash_integro,
        "aviso_hash":         (
            None if hash_integro or payload.hash_documento is None else
            "O hash_documento enviado diverge de prescricoes.assinatura_hash. "
            "Verifique se o documento canônico correto foi assinado."
        ),
        "campos_registrados": {
            "tipo_certificado":    payload.tipo_certificado is not None,
            "emissor":             payload.emissor is not None,
            "serial_certificado":  payload.serial_certificado is not None,
            "timestamp_assinatura": payload.timestamp_assinatura is not None,
            "hash_documento":      payload.hash_documento is not None,
            "dados_assinatura_b64": payload.dados_assinatura_b64 is not None,
        },
        "registrado_em": agora,
    }
