"""
routers/contrarreferencias.py
=============================
Contrarreferência — objeto sanitário DERIVADO do Encaminhamento (E2).

Gêmeo de laudo ↔ pedido_exame. Reusa os helpers de ownership/transição do E1
(`app.routers.encaminhamentos`) SEM modificá-lo — mesma lógica, sem divergência.

Lições embutidas:
- ownership desde o nascimento (5C-BIS / E1);
- público NEUTRO desde o nascimento (#15) — `conteudo_clinico` NUNCA no /public;
- gate PG nos caminhos 2xx.
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import date, datetime
from typing import Optional

import qrcode
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, field_validator

from app.auth.dependencies import require_role
from app.config import BASE_URL
from app.database_tx import get_tx
from app.domain.ledger import registrar_evento_ledger
from app.instance import get_instance_id_conn
from app.utils.helpers import _assert_or_403, _normalizar_identidade_jwt
from app.routers.encaminhamentos import (
    _get_encaminhamento_ou_404,
    _validar_transicao,
    _assert_destino,
    _cns_origem,
    _cpf_paciente,
    _evento as _evento_enc,
)

router = APIRouter(tags=["contrarreferencias"])

_CPF_NAO_IDENTIFICADO = "00000000000"


class ContrarreferirIn(BaseModel):
    conteudo_clinico: str

    @field_validator("conteudo_clinico")
    @classmethod
    def nao_vazio(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("conteudo_clinico não pode ser vazio")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calcular_hash_cr(
    *, protocolo: str, cns_autor: str, cns_origem: Optional[str],
    cpf_paciente: str, origem_encaminhamento_id: int, conteudo_clinico: str,
) -> str:
    doc = {
        "protocolo": protocolo,
        "cns_autor": cns_autor,
        "cns_origem": cns_origem,
        "paciente_cpf": cpf_paciente,
        "origem_encaminhamento_id": origem_encaminhamento_id,
        "conteudo_clinico": conteudo_clinico,
        "versao_esquema": "1",
    }
    payload = json.dumps(doc, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _get_contrarreferencia_ou_404(conn, protocolo: str) -> dict:
    row = conn.execute(
        "SELECT * FROM contrarreferencias WHERE protocolo = ?", (protocolo,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Contrarreferência '{protocolo}' não encontrada.")
    return dict(row)


def _evento_cr(conn, cr_id: int, tipo: str, payload: dict, papel: str, ident: str,
               *, instance_id: str) -> None:
    registrar_evento_ledger(
        conn,
        objeto_tipo="contrarreferencia",
        objeto_id=cr_id,
        tipo_evento=tipo,
        instance_id=instance_id,
        payload=payload,
        ator_tipo=papel,
        ator_id=ident,
    )


def _cns_origem_de_cr(conn, cr: dict) -> str | None:
    row = conn.execute(
        "SELECT pr.cns FROM encaminhamentos e JOIN prescritores pr ON pr.id = e.prescritor_id "
        "WHERE e.id = ?",
        (cr["origem_encaminhamento_id"],),
    ).fetchone()
    return row["cns"] if row else None


def _cpf_paciente_de_cr(conn, cr: dict) -> str | None:
    if cr["paciente_id"] is None:
        return None
    row = conn.execute("SELECT cpf FROM pacientes WHERE id = ?", (cr["paciente_id"],)).fetchone()
    return row["cpf"] if row else None


def _assert_leitura_cr(conn, cr: dict, papel: str, ident: str) -> None:
    """Dono = autor(destino) OU origem (prescritor) OU paciente."""
    if papel == "prescritor":
        donos = {cr["cns_autor"], _cns_origem_de_cr(conn, cr)} - {None}
        _assert_or_403(
            ident in donos,
            codigo="nao_e_dono_da_contrarreferencia",
            mensagem="Esta contrarreferência pertence a outro prescritor.",
        )
        return
    if papel == "paciente":
        cpf = _cpf_paciente_de_cr(conn, cr)
        _assert_or_403(
            cpf is not None and cpf != _CPF_NAO_IDENTIFICADO and cpf == ident,
            codigo="nao_e_dono_da_contrarreferencia",
            mensagem="Esta contrarreferência pertence a outro paciente.",
        )
        return
    _assert_or_403(
        False,
        codigo="papel_sem_acesso_a_contrarreferencia",
        mensagem="Este perfil não pode acessar a contrarreferência.",
    )


# ---------------------------------------------------------------------------
# POST /encaminhamentos/{protocolo}/contrarreferir — cria o objeto derivado
# ---------------------------------------------------------------------------

@router.post("/encaminhamentos/{protocolo}/contrarreferir", status_code=201)
def contrarreferir(
    protocolo: str,
    payload: ContrarreferirIn,
    usuario=Depends(require_role("prescritor", "admin")),
):
    """O prescritor de DESTINO devolve a contrarreferência: cria o objeto derivado
    e transiciona o encaminhamento `atendido → contrarreferido`. Anti-leak 404→403→409.
    """
    papel, ident = _normalizar_identidade_jwt(usuario)
    agora = datetime.utcnow().isoformat()
    data_emissao = date.today().isoformat()
    cr_protocolo = str(uuid.uuid4())

    with get_tx() as conn:
        enc = _get_encaminhamento_ou_404(conn, protocolo)        # 404
        if papel != "admin":
            _assert_destino(enc, ident)                           # 403 — só o destino
        _validar_transicao(enc, "contrarreferido")               # 409 — exige 'atendido'

        cns_origem = _cns_origem(conn, enc)
        cns_autor = enc["cns_destino"]
        cpf = _cpf_paciente(conn, enc) or _CPF_NAO_IDENTIFICADO
        # autor_id best-effort: vincula se houver linha em prescritores; NÃO cria
        # (o destino é identificado por CNS, sem exigir nome — padrão do E1).
        autor_row = conn.execute(
            "SELECT id FROM prescritores WHERE cns = ?", (cns_autor,)
        ).fetchone()
        autor_id = autor_row["id"] if autor_row else None

        doc_hash = _calcular_hash_cr(
            protocolo=cr_protocolo, cns_autor=cns_autor, cns_origem=cns_origem,
            cpf_paciente=cpf, origem_encaminhamento_id=enc["id"],
            conteudo_clinico=payload.conteudo_clinico,
        )

        cursor = conn.execute(
            """
            INSERT INTO contrarreferencias
              (protocolo, cns_autor, autor_id, paciente_id, origem_encaminhamento_id,
               conteudo_clinico, status, tipo_emissao, assinatura_hash, data_emissao, criado_em)
            VALUES (?, ?, ?, ?, ?, ?, 'registrada', 'novo', ?, ?, ?)
            """,
            (
                cr_protocolo, cns_autor, autor_id, enc["paciente_id"], enc["id"],
                payload.conteudo_clinico, doc_hash, data_emissao, agora,
            ),
        )
        cr_id = cursor.lastrowid

        # Custódia da contrarreferência: o retorno "viaja de volta" à origem.
        conn.execute(
            """
            INSERT INTO contrarreferencia_custodia
              (contrarreferencia_id, item_id, detentor_tipo, detentor_id,
               transferida_em, encerrada_em, motivo, created_at)
            VALUES (?, NULL, 'prescritor', ?, ?, NULL, 'contrarreferencia_registrada', ?)
            """,
            (cr_id, cns_origem, agora, agora),
        )

        instance_id = get_instance_id_conn(conn)
        # Ledger DUPLO (arch §8): no objeto derivado e no encaminhamento-parent.
        _evento_cr(conn, cr_id, "contrarreferencia_registrada", {
            "origem_encaminhamento_id": enc["id"],
            "encaminhamento_protocolo": protocolo,
            "cns_autor": cns_autor,
        }, papel, ident, instance_id=instance_id)
        _evento_enc(conn, enc["id"], "contrarreferencia_registrada", {
            "contrarreferencia_protocolo": cr_protocolo,
        }, papel, ident, instance_id=instance_id)

        conn.execute(
            "UPDATE encaminhamentos SET status = 'contrarreferido' WHERE id = ?", (enc["id"],)
        )

        return {
            "protocolo_contrarreferencia": cr_protocolo,
            "protocolo_encaminhamento": protocolo,
            "status_encaminhamento": "contrarreferido",
            "documento_hash": doc_hash,
        }


# ---------------------------------------------------------------------------
# GET /contrarreferencias/{protocolo} — autenticado, ownership (clínica visível)
# ---------------------------------------------------------------------------

@router.get("/contrarreferencias/{protocolo}")
def get_contrarreferencia(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        cr = _get_contrarreferencia_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura_cr(conn, cr, papel, ident)
        eventos = [
            dict(r) for r in conn.execute(
                "SELECT tipo_evento, ator_tipo, ator_id, payload, created_at "
                "FROM contrarreferencia_eventos WHERE contrarreferencia_id = ? ORDER BY id ASC",
                (cr["id"],),
            ).fetchall()
        ]
        return {**cr, "eventos": eventos}


@router.get("/contrarreferencias/{protocolo}/custodia")
def get_custodia_contrarreferencia(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        cr = _get_contrarreferencia_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura_cr(conn, cr, papel, ident)
        rows = conn.execute(
            """
            SELECT item_id, detentor_tipo, detentor_id, transferida_em,
                   encerrada_em, motivo, created_at
              FROM contrarreferencia_custodia
             WHERE contrarreferencia_id = ?
             ORDER BY id ASC
            """,
            (cr["id"],),
        ).fetchall()
        return {"protocolo": protocolo, "custodia": [dict(r) for r in rows]}


@router.get("/contrarreferencias/{protocolo}/qr", response_class=Response)
def qr_contrarreferencia(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "paciente", "admin")),
):
    papel, ident = _normalizar_identidade_jwt(usuario)
    with get_tx() as conn:
        cr = _get_contrarreferencia_ou_404(conn, protocolo)
        if papel != "admin":
            _assert_leitura_cr(conn, cr, papel, ident)

    url = f"{BASE_URL}/public/contrarreferencias/{protocolo}"
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.read(), media_type="image/png")
