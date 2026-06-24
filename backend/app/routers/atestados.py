"""
routers/atestados.py
====================
Atestado médico como objeto sanitário MONOLÍTICO (sem itens).

ROTAS
-----
POST /atestados                       ← emissão digital
POST /atestados/fisica                ← emissão física (fire-and-forget)
GET  /atestados/{protocolo}           ← consulta autenticada (dono/admin)
GET  /atestados/{protocolo}/custodia  ← histórico de custódia

PDF e assinatura: ver get_pdf / pdf-assinado neste mesmo router (fatias 4-5).
Validação pública neutra: routers/publico.py.

Contrato de estados: domain/states_atestado.py. Ver docs/ARQUITETURA_ATESTADO.md.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from app.auth.dependencies import require_role
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.cofre_pfx import decifrar_pfx
from app.domain.ledger import registrar_evento_ledger
from app.domain.outbox import registrar_outbox
from app.domain.pdf_assinatura import (
    MetadataAssinatura,
    SenhaPfxInvalida,
    assinar_pdf_icp,
)
from app.domain.pdf_atestado import gerar_pdf_atestado
from app.domain.states_atestado import transicao_valida_atestado
from app.instance import get_instance_id_conn
from app.utils.helpers import (
    _assert_or_403,
    _normalizar_identidade_jwt,
    normalize_cns,
    normalize_cpf,
    normalize_nome,
)

router = APIRouter(prefix="/atestados", tags=["atestados"])

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

_CPF_NAO_IDENTIFICADO = "00000000000"      # convenção 6a — fluxo físico
_TIPOS_EMISSAO_VALIDOS = {"nova", "correcao"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AtestadoIn(BaseModel):
    cns_prescritor:        str
    nome_prescritor:       Optional[str] = None
    cpf_paciente:          str
    nome_paciente:         str
    finalidade:            str                        # obrigatória
    indicacao_clinica:     Optional[str] = None       # opcional (privacidade)
    codigo_cid:            Optional[str] = None        # opcional
    dias_afastamento:      Optional[int] = None        # opcional
    data_documento:        Optional[str] = None        # ISO; default hoje
    nome_profissional:     Optional[str] = None
    registro_profissional: Optional[str] = None
    assinatura_modo:       Optional[str] = None        # icp_brasil_local | gov_br_nuvem
    tipo_emissao:          str = "nova"
    origem_atestado_id:    Optional[int] = None

    @field_validator("finalidade")
    @classmethod
    def _finalidade_nao_vazia(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Finalidade é obrigatória.")
        return v.strip()

    @field_validator("dias_afastamento")
    @classmethod
    def _dias_positivo(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError("dias_afastamento não pode ser negativo.")
        return v

    @model_validator(mode="after")
    def _coerencia(self):
        if self.tipo_emissao not in _TIPOS_EMISSAO_VALIDOS:
            raise ValueError(f"tipo_emissao inválido: {self.tipo_emissao!r}")
        if self.tipo_emissao != "nova" and self.origem_atestado_id is None:
            raise ValueError("origem_atestado_id é obrigatório para correção.")
        return self


class AtestadoFisicaIn(BaseModel):
    cns_prescritor:        str
    nome_prescritor:       Optional[str] = None
    nome_paciente:         Optional[str] = None       # físico pode não identificar
    finalidade:            str
    indicacao_clinica:     Optional[str] = None
    codigo_cid:            Optional[str] = None
    dias_afastamento:      Optional[int] = None
    data_documento:        Optional[str] = None
    nome_profissional:     Optional[str] = None
    registro_profissional: Optional[str] = None

    @field_validator("finalidade")
    @classmethod
    def _finalidade_nao_vazia(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("Finalidade é obrigatória.")
        return v.strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _calcular_hash_atestado(
    protocolo: str, cns: str, cpf: str, finalidade: str,
    indicacao: Optional[str], cid: Optional[str], dias: Optional[int],
    data_documento: str,
) -> str:
    doc = {
        "protocolo":         protocolo,
        "prescritor_cns":    cns,
        "paciente_cpf":      cpf,
        "finalidade":        finalidade,
        "indicacao_clinica": indicacao,
        "codigo_cid":        cid,
        "dias_afastamento":  dias,
        "data_documento":    data_documento,
        "versao_esquema":    "1",
    }
    return hashlib.sha256(
        json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _validade_de(data_documento: str, dias: Optional[int]) -> Optional[str]:
    """Fim do período = data_documento + dias (só quando há afastamento)."""
    if not dias:
        return None
    try:
        base = date.fromisoformat(data_documento)
    except ValueError:
        return None
    return (base + timedelta(days=dias)).isoformat()


# ---------------------------------------------------------------------------
# POST /atestados — emissão digital
# ---------------------------------------------------------------------------

@router.post("", status_code=201)
def criar_atestado(
    payload: AtestadoIn,
    usuario=Depends(require_role("prescritor")),
):
    """Emite um atestado digitalmente. O atestado é entregue ao paciente:
    registra custódia prescritor → paciente na própria emissão."""
    papel, ident = _normalizar_identidade_jwt(usuario)

    cns = normalize_cns(payload.cns_prescritor)
    _assert_or_403(
        ident == cns,
        codigo="prescritor_mismatch",
        mensagem="CNS do payload não coincide com prescritor autenticado.",
    )
    cpf = normalize_cpf(payload.cpf_paciente)
    if cpf == _CPF_NAO_IDENTIFICADO:
        raise HTTPException(
            status_code=422,
            detail="Atestado digital exige CPF válido do paciente (use /atestados/fisica para não identificado).",
        )
    nome_pac = normalize_nome(payload.nome_paciente)
    protocolo = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()
    data_documento = payload.data_documento or date.today().isoformat()
    data_emissao = date.today().isoformat()
    data_validade = _validade_de(data_documento, payload.dias_afastamento)

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)

        if payload.origem_atestado_id is not None:
            origem = conn.execute(
                "SELECT pr.cns FROM atestados a "
                "JOIN prescritores pr ON pr.id = a.prescritor_id "
                "WHERE a.id = ?",
                (payload.origem_atestado_id,),
            ).fetchone()
            if not origem:
                raise HTTPException(
                    status_code=404,
                    detail=f"Atestado de origem id={payload.origem_atestado_id} não encontrado.",
                )
            _assert_or_403(
                origem["cns"] == ident,
                codigo="nao_e_dono_do_atestado",
                mensagem="O atestado de origem foi emitido por outro prescritor.",
            )

        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO atestados
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               origem_atestado_id, finalidade, indicacao_clinica, codigo_cid,
               dias_afastamento, nome_profissional, registro_profissional,
               assinatura_modo, data_documento, data_emissao, data_validade, criado_em)
            VALUES (?, ?, ?, 'emitido', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (protocolo, prescritor_id, paciente_id, payload.tipo_emissao,
             payload.origem_atestado_id, payload.finalidade, payload.indicacao_clinica,
             payload.codigo_cid, payload.dias_afastamento, payload.nome_profissional,
             payload.registro_profissional, payload.assinatura_modo,
             data_documento, data_emissao, data_validade, agora),
        )
        atestado_id = cursor.lastrowid

        doc_hash = _calcular_hash_atestado(
            protocolo, cns, cpf, payload.finalidade, payload.indicacao_clinica,
            payload.codigo_cid, payload.dias_afastamento, data_documento,
        )
        conn.execute(
            "UPDATE atestados SET assinatura_hash = ? WHERE id = ?",
            (doc_hash, atestado_id),
        )

        instance_id = get_instance_id_conn(conn)
        ev = {
            "tipo_emissao":       payload.tipo_emissao,
            "origem_atestado_id": payload.origem_atestado_id,
            "finalidade":         payload.finalidade,
            "tem_cid":            bool(payload.codigo_cid),
            "dias_afastamento":   payload.dias_afastamento,
        }
        registrar_evento_ledger(
            conn, objeto_tipo="atestado", objeto_id=atestado_id,
            tipo_evento="atestado_emitido", instance_id=instance_id,
            payload=ev, ator_tipo="prescritor", ator_id=cns,
        )
        registrar_outbox(conn, "atestado_emitido", "atestado", protocolo, ev,
                         instance_id=instance_id)

        # Custódia prescritor → paciente (o atestado é entregue ao paciente).
        conn.execute(
            """
            INSERT INTO atestado_custodia (atestado_id, de, para, transferido_em, dados_json)
            VALUES (?, 'prescritor', 'paciente', ?, ?)
            """,
            (atestado_id, agora, json.dumps(
                {"de_id": cns, "para_id": cpf, "motivo": "emissao"}, ensure_ascii=False)),
        )
        registrar_evento_ledger(
            conn, objeto_tipo="atestado", objeto_id=atestado_id,
            tipo_evento="custodia_transferida", instance_id=instance_id,
            payload={"de": "prescritor", "para": "paciente", "para_id": cpf},
            ator_tipo="prescritor", ator_id=cns,
        )

    return {
        "protocolo": protocolo,
        "status": "emitido",
        "tipo_emissao": payload.tipo_emissao,
        "finalidade": payload.finalidade,
        "codigo_cid": payload.codigo_cid,
        "dias_afastamento": payload.dias_afastamento,
        "data_documento": data_documento,
        "data_validade": data_validade,
        "assinatura_modo": payload.assinatura_modo,
        "assinatura_hash": doc_hash,
    }


# ---------------------------------------------------------------------------
# POST /atestados/fisica — emissão física (fire-and-forget)
# ---------------------------------------------------------------------------

@router.post("/fisica", status_code=201)
def criar_atestado_fisico(
    payload: AtestadoFisicaIn,
    usuario=Depends(require_role("prescritor")),
):
    """Emissão exclusivamente física: status terminal encerrada_localmente,
    CPF sentinela, sem cadeia de custódia (convenções 6 e 6a)."""
    papel, ident = _normalizar_identidade_jwt(usuario)
    cns = normalize_cns(payload.cns_prescritor)
    _assert_or_403(
        ident == cns, codigo="prescritor_mismatch",
        mensagem="CNS do payload não coincide com prescritor autenticado.",
    )
    cpf = _CPF_NAO_IDENTIFICADO
    nome_pac = normalize_nome(payload.nome_paciente or "Não identificado")
    protocolo = str(uuid.uuid4())
    agora = datetime.utcnow().isoformat()
    data_documento = payload.data_documento or date.today().isoformat()
    data_emissao = date.today().isoformat()

    with get_tx() as conn:
        prescritor_id = _localizar_ou_criar_prescritor(conn, cns, payload.nome_prescritor, agora)
        paciente_id = _localizar_ou_criar_paciente(conn, cpf, nome_pac, agora)

        cursor = conn.execute(
            """
            INSERT INTO atestados
              (protocolo, prescritor_id, paciente_id, status, tipo_emissao,
               finalidade, indicacao_clinica, codigo_cid, dias_afastamento,
               nome_profissional, registro_profissional,
               data_documento, data_emissao, criado_em)
            VALUES (?, ?, ?, 'encerrada_localmente', 'fisica', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (protocolo, prescritor_id, paciente_id, payload.finalidade,
             payload.indicacao_clinica, payload.codigo_cid, payload.dias_afastamento,
             payload.nome_profissional, payload.registro_profissional,
             data_documento, data_emissao, agora),
        )
        atestado_id = cursor.lastrowid
        instance_id = get_instance_id_conn(conn)

        for tipo in ("atestado_impresso", "encerrada_localmente"):
            registrar_evento_ledger(
                conn, objeto_tipo="atestado", objeto_id=atestado_id,
                tipo_evento=tipo, instance_id=instance_id,
                payload={"finalidade": payload.finalidade, "motivo": "emissao_fisica"},
                ator_tipo="prescritor", ator_id=cns,
            )

    return {"protocolo": protocolo, "status": "encerrada_localmente", "tipo_emissao": "fisica"}


# ---------------------------------------------------------------------------
# Helpers de leitura
# ---------------------------------------------------------------------------

def _carregar_atestado(conn, protocolo: str) -> dict:
    row = conn.execute(
        """
        SELECT a.*, pr.cns AS cns_prescritor, pr.nome AS nome_prescritor,
               pa.cpf AS cpf_paciente, pa.nome AS nome_paciente
          FROM atestados a
          JOIN prescritores pr ON pr.id = a.prescritor_id
          JOIN pacientes    pa ON pa.id = a.paciente_id
         WHERE a.protocolo = ?
        """,
        (protocolo,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Atestado '{protocolo}' não encontrado.")
    return dict(row)


def _exigir_leitura(dados: dict, usuario: dict) -> None:
    """Autoriza leitura do atestado: admin, prescritor-autor ou paciente-titular.

    O paciente sentinela (fluxo físico não identificado, CPF 00000000000) nunca
    é titular — atestado físico não entra em custódia digital nem é lido pelo
    paciente. (Revisão #60 — o detentor da custódia precisa de acesso autenticado.)
    """
    role = usuario["role"]
    if role == "prescritor":
        _assert_or_403(
            normalize_cns(usuario["sub"]) == dados["cns_prescritor"],
            codigo="nao_e_dono_do_atestado",
            mensagem="Este atestado foi emitido por outro prescritor.",
        )
    elif role == "paciente":
        cpf = normalize_cpf(usuario["sub"])
        _assert_or_403(
            cpf != _CPF_NAO_IDENTIFICADO and cpf == dados["cpf_paciente"],
            codigo="nao_e_titular_do_atestado",
            mensagem="Este atestado pertence a outro paciente.",
        )
    # admin: leitura irrestrita


# ---------------------------------------------------------------------------
# GET /atestados/{protocolo} — consulta autenticada
# ---------------------------------------------------------------------------

@router.get("/{protocolo}")
def get_atestado(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    with get_tx() as conn:
        dados = _carregar_atestado(conn, protocolo)
    _exigir_leitura(dados, usuario)
    return {
        "protocolo": dados["protocolo"],
        "status": dados["status"],
        "tipo_emissao": dados["tipo_emissao"],
        "finalidade": dados["finalidade"],
        "indicacao_clinica": dados["indicacao_clinica"],
        "codigo_cid": dados["codigo_cid"],
        "dias_afastamento": dados["dias_afastamento"],
        "data_documento": dados["data_documento"],
        "data_emissao": dados["data_emissao"],
        "data_validade": dados["data_validade"],
        "assinatura_modo": dados["assinatura_modo"],
        "assinatura_hash": dados["assinatura_hash"],
        "nome_paciente": dados["nome_paciente"],
        "nome_prescritor": dados["nome_prescritor"],
    }


# ---------------------------------------------------------------------------
# GET /atestados/{protocolo}/custodia — histórico de custódia
# ---------------------------------------------------------------------------

@router.get("/{protocolo}/custodia")
def get_custodia_atestado(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    with get_tx() as conn:
        dados = _carregar_atestado(conn, protocolo)
        _exigir_leitura(dados, usuario)
        rows = conn.execute(
            """
            SELECT de, para, transferido_em, dados_json
              FROM atestado_custodia WHERE atestado_id = ? ORDER BY id
            """,
            (dados["id"],),
        ).fetchall()
    return {
        "protocolo": protocolo,
        "custodia": [
            {
                "de": r["de"], "para": r["para"],
                "transferido_em": str(r["transferido_em"]),
                "contexto": json.loads(r["dados_json"]) if r["dados_json"] else None,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# PDF institucional + assinatura ICP-Brasil (PAdES)
# ---------------------------------------------------------------------------

def _pdf_de_dados(dados: dict) -> bytes:
    return gerar_pdf_atestado(
        protocolo=dados["protocolo"], status=dados["status"],
        tipo_emissao=dados["tipo_emissao"], finalidade=dados["finalidade"],
        indicacao_clinica=dados["indicacao_clinica"], codigo_cid=dados["codigo_cid"],
        dias_afastamento=dados["dias_afastamento"], data_documento=dados["data_documento"],
        data_validade=dados["data_validade"], assinatura_modo=dados["assinatura_modo"],
        assinatura_hash=dados["assinatura_hash"], nome_prescritor=dados["nome_prescritor"],
        cns_prescritor=dados["cns_prescritor"], registro_profissional=dados["registro_profissional"],
        nome_paciente=dados["nome_paciente"], cpf_paciente=dados["cpf_paciente"],
        is_demo=PICSAUDE_DEMO_MODE,
    )


def _carregar_certificado_ativo(conn, prescritor_id: int):
    row = conn.execute(
        """
        SELECT pfx_cifrado, pfx_iv, pfx_tag, hash_cert_der, serial,
               nome_no_certificado, cpf_no_certificado
          FROM prescritor_certificados
         WHERE prescritor_id = ? AND ativo = TRUE
        """,
        (prescritor_id,),
    ).fetchone()
    return dict(row) if row else None


@router.get("/{protocolo}/pdf")
def get_pdf_atestado(
    protocolo: str,
    usuario=Depends(require_role("prescritor", "admin", "paciente")),
):
    with get_tx() as conn:
        dados = _carregar_atestado(conn, protocolo)
    _exigir_leitura(dados, usuario)
    pdf = _pdf_de_dados(dados)
    return StreamingResponse(
        iter([pdf]), media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=atestado_{protocolo[:8]}.pdf"},
    )


class PdfAssinadoRequest(BaseModel):
    senha_pfx: str = Field(..., min_length=1, max_length=200)


@router.post("/{protocolo}/pdf-assinado", response_class=StreamingResponse)
def get_pdf_assinado_atestado(
    protocolo: str,
    body: PdfAssinadoRequest,
    usuario=Depends(require_role("prescritor")),
):
    """Gera o PDF do atestado e embute assinatura ICP-Brasil (PAdES-B) com o
    certificado do prescritor no cofre. Transiciona emitido → assinado.
    Bloqueado em DEMO_MODE; senha usada uma vez, não persistida."""
    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={"codigo": "demo_mode_ativo",
                    "mensagem": "Assinatura com certificado desabilitada em modo demo."},
        )
    cns_token = normalize_cns(usuario.get("sub") or "")
    with get_tx() as conn:
        dados = _carregar_atestado(conn, protocolo)
        _assert_or_403(
            cns_token == dados["cns_prescritor"],
            codigo="nao_e_dono_do_atestado",
            mensagem="Somente o prescritor que emitiu o atestado pode assiná-lo.",
        )
        if (dados["assinatura_modo"] or "") != "icp_brasil_local":
            raise HTTPException(
                status_code=422,
                detail="Atestado não usa assinatura ICP-Brasil local (assinatura_modo != 'icp_brasil_local').",
            )
        cert = _carregar_certificado_ativo(conn, dados["prescritor_id"])
        if not cert:
            raise HTTPException(
                status_code=422,
                detail="Nenhum certificado ICP-Brasil ativo. Faça upload via POST /prescritor/certificado.",
            )

        pfx_bytes = decifrar_pfx(
            bytes(cert["pfx_cifrado"]), bytes(cert["pfx_iv"]), bytes(cert["pfx_tag"]),
        )
        meta = MetadataAssinatura(
            nome_prescritor=cert["nome_no_certificado"] or dados["nome_prescritor"] or "",
            cpf_prescritor=cert["cpf_no_certificado"],
            razao="Atestado médico digital PicSaúde",
        )
        try:
            pdf_assinado = assinar_pdf_icp(
                pdf_bytes=_pdf_de_dados(dados), pfx_bytes=pfx_bytes,
                senha=body.senha_pfx, metadata=meta,
            )
        except SenhaPfxInvalida:
            raise HTTPException(status_code=401, detail="Senha do certificado inválida.")
        finally:
            del pfx_bytes

        # Transição emitido → assinado (idempotente: se já assinado, só registra).
        if transicao_valida_atestado(dados["status"], "assinado"):
            conn.execute("UPDATE atestados SET status = 'assinado' WHERE id = ?", (dados["id"],))

        import hashlib as _hashlib
        instance_id = get_instance_id_conn(conn)
        registrar_evento_ledger(
            conn, objeto_tipo="atestado", objeto_id=dados["id"],
            tipo_evento="atestado_assinado", instance_id=instance_id,
            payload={"hash_pdf": _hashlib.sha256(pdf_assinado).hexdigest(),
                     "serial_cert": cert["serial"], "hash_cert_der": cert["hash_cert_der"],
                     "nivel_pades": "B"},
            ator_tipo="prescritor", ator_id=cns_token,
        )

    return StreamingResponse(
        iter([pdf_assinado]), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="atestado-{protocolo[:8]}-assinado.pdf"'},
    )
