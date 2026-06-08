"""
publico.py
==========
Endpoints públicos do PicSaúde — consulta mínima e segura de protocolo de prescrição.

SEPARAÇÃO DE RESPONSABILIDADES:
  - /public/*           → acesso público, sem autenticação, sem dados sensíveis
  - /prescricoes/*/qr   → geração de QR Code (pode exigir auth futuramente)

REGRA DE SEGURANÇA DESTE MÓDULO:
  Nenhum endpoint aqui pode retornar:
  - CPF ou nome do paciente
  - CNS ou nome do prescritor
  - Dados do comprador
  - Lote, fabricante ou validade
  - Histórico de eventos (ledger)
  - Dados do estabelecimento

  Retorna apenas: protocolo, status, tipo_emissao e lista de itens (nome + dose + status).
"""

from __future__ import annotations

import io

import qrcode
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.config import BASE_URL
from app.database_tx import get_tx

router = APIRouter(tags=["publico"])


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

_SQL_PRESCRICAO_PUBLICA = """
SELECT
    p.protocolo,
    p.status,
    p.tipo_emissao
FROM prescricoes p
WHERE p.protocolo = ?
"""

_SQL_ITENS_PUBLICOS = """
SELECT
    i.status_item
FROM prescricao_itens i
JOIN prescricoes p ON p.id = i.prescricao_id
WHERE p.protocolo = ?
ORDER BY i.id
"""


# ---------------------------------------------------------------------------
# GET /public/prescricoes/{protocolo}
# Consulta pública mínima — sem dados sensíveis
# ---------------------------------------------------------------------------

@router.get(
    "/public/prescricoes/{protocolo}",
    summary="Consulta pública mínima de protocolo de prescrição",
    response_description="Protocolo, status e itens (sem dados sensíveis)",
)
def consulta_publica(protocolo: str):
    """
    Retorna o estado atual de uma prescrição identificada pelo protocolo (UUID).

    **Job: validação por QR — existência + estado. Payload NEUTRO (sem clínica).**

    **Retorna apenas:** protocolo, status da prescrição, tipo de emissão e, por item,
    `ordem` + `status_item`.

    **Nunca retorna:** medicamento, dose ou qualquer conteúdo clínico; CPF, nome do
    paciente, CNS do prescritor, lote, fabricante, estabelecimento ou eventos do ledger.
    """
    with get_tx() as conn:
        pres = conn.execute(_SQL_PRESCRICAO_PUBLICA, (protocolo,)).fetchone()

        if not pres:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

        itens_rows = conn.execute(_SQL_ITENS_PUBLICOS, (protocolo,)).fetchall()


    itens = [
        {
            "ordem":       idx + 1,
            "status_item": r["status_item"],
        }
        for idx, r in enumerate(itens_rows)
    ]

    return {
        "protocolo":        pres["protocolo"],
        "status_prescricao": pres["status"],
        "tipo_emissao":     pres["tipo_emissao"],
        "itens":            itens,
    }


# ---------------------------------------------------------------------------
# GET /prescricoes/{protocolo}/qr
# QR Code em PNG gerado em memória — aponta para a URL pública acima
# ---------------------------------------------------------------------------

@router.get(
    "/prescricoes/{protocolo}/qr",
    summary="QR Code do protocolo de prescrição",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}}, "description": "Imagem PNG do QR Code"},
        404: {"description": "Protocolo não encontrado"},
    },
)
def qr_code_protocolo(protocolo: str):
    """
    Gera e retorna um QR Code PNG para o protocolo informado.

    O QR Code codifica a URL pública da prescrição:
    `{BASE_URL}/public/prescricoes/{protocolo}`

    - Imagem gerada inteiramente em memória (sem arquivo em disco).
    - 404 se o protocolo não existir no banco.
    - Usar diretamente em `<img src="...">` ou impressão de receituário.
    """
    # Verificar existência do protocolo antes de gerar a imagem
    with get_tx() as conn:
        existe = conn.execute(
            "SELECT 1 FROM prescricoes WHERE protocolo = ?", (protocolo,)
        ).fetchone()

    if not existe:
        raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

    # Gerar QR Code em memória
    url = f"{BASE_URL}/public/prescricoes/{protocolo}"
    qr  = qrcode.QRCode(
        version        = 1,
        error_correction = qrcode.constants.ERROR_CORRECT_M,
        box_size       = 10,
        border         = 4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return Response(content=buf.read(), media_type="image/png")


# ---------------------------------------------------------------------------
# GET /public/exames/{protocolo}
# Consulta pública mínima de pedido de exame — sem dados sensíveis
# ---------------------------------------------------------------------------

@router.get(
    "/public/exames/{protocolo}",
    summary="Consulta pública mínima de protocolo de pedido de exame",
    response_description="Protocolo, status e itens (sem dados sensíveis)",
)
def consulta_publica_exame(protocolo: str):
    """
    Retorna o estado atual de um pedido de exame identificado pelo protocolo.

    **Job: validação por QR — existência + estado. Payload NEUTRO (sem clínica).**

    **Retorna apenas:** protocolo, status do pedido, tipo de emissão e, por item,
    `ordem` + `status_item`.

    **Nunca retorna:** nome do exame, código TUSS ou qualquer conteúdo clínico; CPF,
    nome do paciente, CNS do prescritor, indicação clínica, resultados, prioridade,
    eventos do ledger.
    """
    with get_tx() as conn:
        pedido = conn.execute(
            """
            SELECT protocolo, status, tipo_emissao
            FROM pedidos_exame
            WHERE protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not pedido:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

        itens_rows = conn.execute(
            """
            SELECT i.status_item
            FROM pedido_exame_itens i
            JOIN pedidos_exame pe ON pe.id = i.pedido_id
            WHERE pe.protocolo = ?
            ORDER BY i.id
            """,
            (protocolo,),
        ).fetchall()


    itens = [
        {
            "ordem":      idx + 1,
            "status_item": r["status_item"],
        }
        for idx, r in enumerate(itens_rows)
    ]

    return {
        "protocolo":    pedido["protocolo"],
        "status_pedido": pedido["status"],
        "tipo_emissao": pedido["tipo_emissao"],
        "itens":        itens,
    }


# ---------------------------------------------------------------------------
# GET /public/laudos/{protocolo}
# Consulta pública mínima de laudo — sem dados sensíveis (Ticket 21)
# ---------------------------------------------------------------------------

@router.get(
    "/public/laudos/{protocolo}",
    summary="Consulta pública mínima de protocolo de laudo",
    response_description="Protocolo, status e itens (sem dados sensíveis)",
)
def consulta_publica_laudo(protocolo: str):
    """
    Retorna o estado atual de um laudo identificado pelo protocolo.

    **Job: validação por QR — existência + estado. Payload NEUTRO (sem clínica).**

    **Retorna apenas:** protocolo, status do laudo, tipo de emissão e, por item,
    `ordem` + `status_item`.

    **Nunca retorna:** nome do exame, conclusão diagnóstica ou qualquer conteúdo clínico;
    CPF, nome do paciente, CNS do responsável técnico, resultado, valor de referência,
    resultado_url, eventos do ledger.
    """
    with get_tx() as conn:
        laudo = conn.execute(
            """
            SELECT protocolo, status, tipo_emissao
            FROM laudos
            WHERE protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not laudo:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

        itens_rows = conn.execute(
            """
            SELECT li.status_item
            FROM laudo_itens li
            JOIN laudos l ON l.id = li.laudo_id
            WHERE l.protocolo = ?
            ORDER BY li.id
            """,
            (protocolo,),
        ).fetchall()


    itens = [
        {
            "ordem":      idx + 1,
            "status_item": r["status_item"],
        }
        for idx, r in enumerate(itens_rows)
    ]

    return {
        "protocolo":    laudo["protocolo"],
        "status_laudo": laudo["status"],
        "tipo_emissao": laudo["tipo_emissao"],
        "itens":        itens,
    }


# ---------------------------------------------------------------------------
# GET /public/encaminhamentos/{protocolo}
# Consulta pública mínima de encaminhamento — sem dados sensíveis
# ---------------------------------------------------------------------------

@router.get(
    "/public/encaminhamentos/{protocolo}",
    summary="Consulta pública mínima de protocolo de encaminhamento",
    response_description="Protocolo, status e itens (sem dados sensíveis)",
)
def consulta_publica_encaminhamento(protocolo: str):
    """
    Retorna o estado atual de um encaminhamento identificado pelo protocolo.

    **Job: validação por QR — existência + estado. Payload NEUTRO (sem clínica).**

    **Retorna apenas:** protocolo, status, tipo de emissão e, por item, `ordem` +
    `status_item`.

    **Nunca retorna:** especialidade, procedimento, CID, justificativa clínica, CPF,
    nome do paciente, CNS de origem/destino ou eventos do ledger.
    """
    with get_tx() as conn:
        enc = conn.execute(
            """
            SELECT protocolo, status, tipo_emissao
            FROM encaminhamentos
            WHERE protocolo = ?
            """,
            (protocolo,),
        ).fetchone()

        if not enc:
            raise HTTPException(status_code=404, detail="Protocolo não encontrado.")

        itens_rows = conn.execute(
            """
            SELECT ei.status_item
            FROM encaminhamento_itens ei
            JOIN encaminhamentos e ON e.id = ei.encaminhamento_id
            WHERE e.protocolo = ?
            ORDER BY ei.id
            """,
            (protocolo,),
        ).fetchall()

    itens = [
        {
            "ordem":         idx + 1,
            "status_item":   r["status_item"],
        }
        for idx, r in enumerate(itens_rows)
    ]

    return {
        "protocolo":               enc["protocolo"],
        "status_encaminhamento":   enc["status"],
        "tipo_emissao":            enc["tipo_emissao"],
        "itens":                   itens,
    }
