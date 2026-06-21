"""
routers/prescritor.py
=====================
Ticket 21 — Endpoints do prescritor autenticado.

Distinção em relação a `routers/prescritores.py`:
  - `prescritores.py` (plural) → busca pública CNES.
  - `prescritor.py`   (singular) → ações do prescritor LOGADO.

Endpoints
---------
POST /prescritor/certificado
    Upload do .pfx ICP-Brasil A1 do prescritor. Cria registro em
    `prescritor_certificados` com .pfx criptografado AES-256-GCM.
    Marca certificado anterior como `ativo=FALSE, substituido_em=now()`.
    Valida CPF do certificado contra o do prescritor logado.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.auth.dependencies import require_role
from app.config import PICSAUDE_DEMO_MODE
from app.database_tx import get_tx
from app.domain.cofre_pfx import cifrar_pfx
from app.domain.icp_identity import parsear_certificado_icp
from app.domain.pdf_assinatura import (
    CertificadoSemKeyUsage,
    SenhaPfxInvalida,
    carregar_pfx,
)
from app.domain.binding_cert import (
    STATUS_DIVERGENTE,
    STATUS_VINCULAR,
    avaliar_binding_cpf,
)


router = APIRouter(prefix="/prescritor", tags=["prescritor"])


def _carregar_prescritor_por_cns(conn, cns: str) -> Optional[dict]:
    row = conn.execute(
        "SELECT id, cns, nome, cpf FROM prescritores WHERE cns = ?",
        (cns,),
    ).fetchone()
    if not row:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def _serializa_emissor(cert) -> str:
    """Tenta extrair CN do emissor do cert, fallback para representação completa."""
    try:
        from cryptography.x509.oid import NameOID
        cn_attrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
        if cn_attrs:
            return cn_attrs[0].value
    except Exception:
        pass
    try:
        return cert.issuer.rfc4514_string()
    except Exception:
        return "?"


@router.post(
    "/certificado",
    status_code=201,
    summary="Upload do certificado ICP-Brasil A1 (.pfx) do prescritor",
)
async def upload_certificado(
    pfx_file: UploadFile = File(..., description="Arquivo .pfx/.p12"),
    senha: str = Form(..., description="Senha do .pfx"),
    usuario: dict = Depends(require_role("prescritor")),
):
    """Upload do certificado ICP-Brasil A1 do prescritor logado.

    Fluxo:
      1. Valida tamanho do arquivo (máx 64KB — .pfx típicos têm < 8KB).
      2. Carrega o .pfx com a senha (valida senha + KeyUsage).
      3. Extrai identidade via `parsear_certificado_icp` (T66) e valida
         contra o prescritor logado (CPF + nome).
      4. Calcula `hash_cert_der` (fingerprint imutável SHA-256 do DER).
      5. Marca certificados ativos anteriores como substituídos.
      6. Cifra o .pfx com AES-256-GCM e persiste.

    A senha NÃO é persistida — o prescritor a fornece a cada uso.
    """
    # Segurança (auditoria F5): a vitrine roda em modo demo e é pública —
    # não aceitar upload de certificado real (chave privada) nesse modo.
    if PICSAUDE_DEMO_MODE:
        raise HTTPException(
            status_code=403,
            detail={
                "codigo": "demo_mode_ativo",
                "mensagem": "Upload de certificado desabilitado em modo demo.",
            },
        )

    cns_token = usuario.get("sub") or ""

    # 1. Limite de tamanho
    pfx_bytes = await pfx_file.read()
    if not pfx_bytes:
        raise HTTPException(status_code=422, detail="Arquivo .pfx vazio.")
    if len(pfx_bytes) > 64 * 1024:
        raise HTTPException(
            status_code=413,
            detail="Arquivo .pfx muito grande (máx 64KB).",
        )

    # 2. Carregar .pfx (valida senha + KeyUsage)
    try:
        carregado = carregar_pfx(pfx_bytes, senha)
    except SenhaPfxInvalida:
        raise HTTPException(status_code=401, detail="Senha do certificado inválida.")
    except CertificadoSemKeyUsage:
        raise HTTPException(
            status_code=422,
            detail="Certificado não possui KeyUsage.digitalSignature.",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Falha ao carregar .pfx: {exc}",
        )

    cert = carregado.certificado

    # 3. Extrair identidade ICP via T66
    from cryptography.hazmat.primitives import serialization
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    icp = parsear_certificado_icp(cert_pem)
    if not icp.parseable:
        raise HTTPException(
            status_code=422,
            detail=f"Certificado inválido: {icp.erro}",
        )
    if not icp.cpf_certificado:
        raise HTTPException(
            status_code=422,
            detail="Certificado não contém CPF (OID 2.16.76.1.3.1).",
        )

    # 3b. F2 — a cadeia do certificado deve ancorar numa AC-Raiz ICP-Brasil
    # confiável (rejeita autoassinado/cadeia não-ancorada). Em dev/test sem
    # truststore configurado, a checagem é pulada (avaliada=False).
    from app.domain.validacao_cadeia_icp import (
        TrustStoreIndisponivel,
        validar_cadeia_icp,
    )
    try:
        cadeia = validar_cadeia_icp(cert_pem)
    except TrustStoreIndisponivel:
        raise HTTPException(
            status_code=503,
            detail={
                "codigo": "truststore_indisponivel",
                "mensagem": "Validação de certificado indisponível no momento.",
            },
        )
    if not cadeia.valida:
        raise HTTPException(
            status_code=422,
            detail={
                "codigo": "cadeia_icp_invalida",
                "mensagem": (
                    "O certificado não encadeia a uma AC-Raiz ICP-Brasil confiável."
                ),
            },
        )

    # 4. Hash do certificado em DER (fingerprint imutável)
    der_bytes = cert.public_bytes(serialization.Encoding.DER)
    hash_cert_der = hashlib.sha256(der_bytes).hexdigest()

    # 5. Validade — usar campos _utc (cryptography >= 42), com fallback
    # para compat com cryptography mais antigo.
    try:
        valido_de = cert.not_valid_before_utc.replace(tzinfo=None)
        valido_ate = cert.not_valid_after_utc.replace(tzinfo=None)
    except AttributeError:
        valido_de = cert.not_valid_before
        valido_ate = cert.not_valid_after

    # Serial — convertemos para string decimal (cert.serial_number é int).
    serial_str = str(cert.serial_number)
    emissor = _serializa_emissor(cert)

    with get_tx() as conn:
        # 6. Validar prescritor logado vs CPF do certificado
        prescritor = _carregar_prescritor_por_cns(conn, cns_token)
        if not prescritor:
            raise HTTPException(
                status_code=404, detail="Prescritor não encontrado.",
            )

        # F3 — binding verificável certificado ↔ prescritor (CPF).
        # Decisão pura em domain/binding_cert.py. Sem fonte confiável de CPF
        # (o CNES não o expõe), a Fase A garante CONSISTÊNCIA (TOFU): vincula na
        # 1ª vez e exige igualdade nas seguintes. Prova forte = Fase B (CADSUS).
        binding = avaliar_binding_cpf(icp.cpf_certificado, prescritor.get("cpf"))
        if binding.status == STATUS_DIVERGENTE:
            raise HTTPException(
                status_code=403,
                detail={
                    "codigo": "cpf_certificado_divergente",
                    "mensagem": (
                        "O CPF do certificado não corresponde ao CPF do prescritor."
                    ),
                },
            )
        if binding.status == STATUS_VINCULAR:
            conn.execute(
                "UPDATE prescritores SET cpf = ? WHERE id = ?",
                (binding.cpf_para_gravar, prescritor["id"]),
            )

        # 7. Marcar certificado ativo anterior (se houver) como substituído.
        agora = datetime.utcnow()
        anterior = conn.execute(
            """
            SELECT id FROM prescritor_certificados
             WHERE prescritor_id = ?
               AND ativo = TRUE
            """,
            (prescritor["id"],),
        ).fetchall()
        for row in anterior:
            anterior_id = row["id"] if hasattr(row, "keys") else row[0]
            conn.execute(
                """
                UPDATE prescritor_certificados
                   SET ativo = FALSE,
                       substituido_em = ?
                 WHERE id = ?
                """,
                (agora, anterior_id),
            )

        # 8. Cifrar .pfx
        cifrado = cifrar_pfx(pfx_bytes)

        # 9. Persistir — UNIQUE(prescritor_id, hash_cert_der) impede duplicação
        try:
            conn.execute(
                """
                INSERT INTO prescritor_certificados
                  (prescritor_id, pfx_cifrado, pfx_iv, pfx_tag,
                   hash_cert_der, serial, valido_de, valido_ate,
                   nome_no_certificado, cpf_no_certificado, emissor,
                   ativo, uploaded_em)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, TRUE, ?)
                """,
                (
                    prescritor["id"],
                    cifrado.cifrado,
                    cifrado.iv,
                    cifrado.tag,
                    hash_cert_der,
                    serial_str,
                    valido_de,
                    valido_ate,
                    icp.nome_certificado or "",
                    icp.cpf_certificado,
                    emissor,
                    agora,
                ),
            )
        except Exception as exc:
            # UNIQUE violation → cert já cadastrado (e estava possivelmente
            # como inativo — então vamos reativá-lo).
            if "uq_prescritor_cert_hash" in str(exc) or "UNIQUE" in str(exc).upper():
                conn.execute(
                    """
                    UPDATE prescritor_certificados
                       SET ativo = TRUE,
                           substituido_em = NULL,
                           revogado_em = NULL,
                           pfx_cifrado = ?,
                           pfx_iv = ?,
                           pfx_tag = ?,
                           uploaded_em = ?
                     WHERE prescritor_id = ?
                       AND hash_cert_der = ?
                    """,
                    (
                        cifrado.cifrado, cifrado.iv, cifrado.tag, agora,
                        prescritor["id"], hash_cert_der,
                    ),
                )
            else:
                raise

    return {
        "serial":              serial_str,
        "nome_certificado":    icp.nome_certificado,
        "cpf_certificado":     icp.cpf_certificado,
        "valido_de":           valido_de.isoformat(),
        "valido_ate":          valido_ate.isoformat(),
        "emitido_por":         emissor,
        "hash_cert_der":       hash_cert_der,
    }
