"""Ticket 21 — Testes de integração da assinatura PAdES.

Cobre o fluxo end-to-end:
  1. Upload do certificado (.pfx) via POST /prescritor/certificado
  2. Geração de receituário (gerar + numerar)
  3. POST /receituarios/{id}/pdf-assinado com senha do .pfx
  4. Validação do PDF assinado via pyHanko
  5. Evento `pdf_assinado_pades` no ledger

Usa o certificado de teste autogerado (`tests.fixtures.certificado_teste`).
Sem rede, sem certificado real, sem TSA externa.
"""
from __future__ import annotations

import io
import json
import warnings
from datetime import datetime

import pytest

warnings.filterwarnings("ignore", message=".*LibreSSL.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pyhanko.*")

from tests.fixtures.certificado_teste import gerar_certificado_teste
from tests.integration.conftest import (
    SEED_PACIENTE_CPF,
    SEED_PACIENTE_NOME,
    SEED_PRESCRITOR_CNS,
    SEED_PRESCRITOR_NOME,
    obter_token_prescritor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _inserir_prescritor_e_paciente(outer_conn) -> tuple[int, int]:
    now = datetime.utcnow().isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cns) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PRESCRITOR_CNS, SEED_PRESCRITOR_NOME, now, now),
        )
        prescritor_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO pacientes (cpf, nome, ativo, created_at, updated_at)
            VALUES (%s, %s, true, %s, %s)
            ON CONFLICT (cpf) DO UPDATE SET nome = EXCLUDED.nome
            RETURNING id
            """,
            (SEED_PACIENTE_CPF, SEED_PACIENTE_NOME, now, now),
        )
        paciente_id = cur.fetchone()[0]
    return prescritor_id, paciente_id


def _inserir_prescricao_b1(outer_conn, *, protocolo: str) -> int:
    """Cria prescrição B1 (controlada) com assinatura_modo=icp_brasil_local."""
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    now = datetime.utcnow()
    now_iso = now.isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               assinatura_hash, tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', 'icp_brasil_local',
                    'a1b2c3d4e5f6789012345678901234567890abcdef0123456789aaaa',
                    'nova', %s, %s, %s)
            RETURNING id
            """,
            (protocolo, prescritor_id, paciente_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               unidade_quantidade, forma_farmaceutica, posologia,
               status_item, classe_controle, created_at, updated_at)
            VALUES (%s, 'DIAZEPAM', '10mg', 30, 'comprimidos',
                    '1 cx c/30', '1 cp 8/8h', 'pendente', 'B1', %s, %s)
            """,
            (prescricao_id, now, now),
        )
        cur.execute(
            """
            INSERT INTO prescricao_assinatura
              (prescricao_id, tipo_certificado, status_validacao,
               created_at, updated_at)
            VALUES (%s, 'A1', 'assinatura_pendente', %s, %s)
            """,
            (prescricao_id, now_iso, now_iso),
        )
    return prescricao_id


def _gerar_e_numerar(client, token, protocolo) -> int:
    """Gera receituários, numera, retorna id do (único) receituário B1."""
    r = client.post(
        f"/prescricoes/{protocolo}/receituarios/gerar",
        headers=_headers(token),
    )
    assert r.status_code == 201, r.text
    rec_id = r.json()["receituarios"][0]["id"]
    r = client.post(
        f"/prescricoes/{protocolo}/receituarios/numerar",
        headers=_headers(token),
    )
    assert r.status_code == 200, r.text
    return rec_id


def _upload_cert(client, token, cert_teste) -> dict:
    """Faz POST /prescritor/certificado com o cert de teste."""
    files = {
        "pfx_file": ("teste.pfx", cert_teste.pfx_bytes,
                     "application/x-pkcs12"),
    }
    data = {"senha": cert_teste.senha}
    r = client.post(
        "/prescritor/certificado",
        headers=_headers(token),
        files=files,
        data=data,
    )
    return r


# ===========================================================================
# Upload de certificado
# ===========================================================================

def test_upload_certificado_sucesso(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    # Garantir que o prescritor existe na tabela `prescritores`
    _inserir_prescritor_e_paciente(outer_conn)

    cert = gerar_certificado_teste(
        nome="DR FULANO DE TAL", cpf="12345678901",
    )
    r = _upload_cert(client, token, cert)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cpf_certificado"] == "12345678901"
    assert "FULANO" in (body["nome_certificado"] or "").upper()
    assert body["hash_cert_der"] and len(body["hash_cert_der"]) == 64


def test_upload_certificado_substitui_anterior(
    client, outer_conn, seed_usuario,
):
    """Segundo upload marca o anterior como ativo=FALSE + substituido_em."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)

    cert1 = gerar_certificado_teste(nome="DR A", cpf="12345678901")
    r1 = _upload_cert(client, token, cert1)
    assert r1.status_code == 201

    cert2 = gerar_certificado_teste(nome="DR A", cpf="12345678901")
    r2 = _upload_cert(client, token, cert2)
    assert r2.status_code == 201
    assert r2.json()["hash_cert_der"] != r1.json()["hash_cert_der"]

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pc.hash_cert_der,
                   pc.ativo,
                   pc.substituido_em IS NOT NULL AS substituido
              FROM prescritor_certificados pc
              JOIN prescritores p ON p.id = pc.prescritor_id
             WHERE p.cns = %s
             ORDER BY pc.uploaded_em ASC
            """,
            (SEED_PRESCRITOR_CNS,),
        )
        rows = cur.fetchall()
    assert len(rows) == 2
    assert rows[0][1] is False and rows[0][2] is True   # anterior inativo + substituído
    assert rows[1][1] is True  and rows[1][2] is False  # novo ativo


def test_upload_certificado_cpf_divergente_rejeitado(
    client, outer_conn, seed_usuario,
):
    """F3 — 2º certificado com CPF diferente do vinculado é rejeitado (403).

    1º upload vincula o CPF ao prescritor (TOFU); um certificado posterior com
    CPF distinto não pode ser associado à mesma conta.
    """
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)

    cert1 = gerar_certificado_teste(nome="DR A", cpf="12345678901")
    r1 = _upload_cert(client, token, cert1)
    assert r1.status_code == 201, r1.text

    cert2 = gerar_certificado_teste(nome="DR A", cpf="98765432100")
    r2 = _upload_cert(client, token, cert2)
    assert r2.status_code == 403, r2.text
    assert r2.json()["detail"]["codigo"] == "cpf_certificado_divergente"


def test_upload_certificado_senha_invalida(
    client, outer_conn, seed_usuario,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)

    cert = gerar_certificado_teste(senha="senha_correta")
    files = {"pfx_file": ("teste.pfx", cert.pfx_bytes, "application/x-pkcs12")}
    data = {"senha": "senha_errada"}
    r = client.post(
        "/prescritor/certificado",
        headers=_headers(token), files=files, data=data,
    )
    assert r.status_code == 401
    assert "senha" in r.json()["detail"].lower()


def test_upload_certificado_sem_keyusage(
    client, outer_conn, seed_usuario,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)

    cert = gerar_certificado_teste(com_keyusage_digital_signature=False)
    r = _upload_cert(client, token, cert)
    assert r.status_code == 422
    assert "KeyUsage.digitalSignature" in r.json()["detail"]


def test_upload_certificado_arquivo_muito_grande(
    client, outer_conn, seed_usuario,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    files = {
        "pfx_file": ("grande.pfx", b"X" * (100 * 1024), "application/x-pkcs12"),
    }
    data = {"senha": "qualquer"}
    r = client.post(
        "/prescritor/certificado",
        headers=_headers(token), files=files, data=data,
    )
    assert r.status_code == 413


def test_upload_certificado_exige_autenticacao(client):
    files = {"pfx_file": ("x.pfx", b"x", "application/x-pkcs12")}
    data = {"senha": "x"}
    r = client.post("/prescritor/certificado", files=files, data=data)
    assert r.status_code in (401, 403)


# ===========================================================================
# PDF assinado
# ===========================================================================

def test_pdf_assinado_sucesso(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste(nome="DR JOAO", cpf="11122233344")
    assert _upload_cert(client, token, cert).status_code == 201

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": cert.senha},
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert "assinado" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"
    # PDF assinado é maior que ~5KB (tem CMS embutido)
    assert len(r.content) > 5000


def test_pdf_assinado_validavel_via_pyhanko(client, outer_conn, seed_usuario):
    """O PDF retornado deve ter assinatura embutida detectável."""
    from app.domain.pdf_assinatura import pdf_tem_assinatura

    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste()
    _upload_cert(client, token, cert)

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-VALID-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-VALID-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-VALID-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": cert.senha},
    )
    assert r.status_code == 200
    assert pdf_tem_assinatura(r.content) is True


def test_pdf_assinado_evento_no_ledger(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste(nome="DR FULANO", cpf="22233344455")
    upload_resp = _upload_cert(client, token, cert)
    assert upload_resp.status_code == 201
    hash_cert_der = upload_resp.json()["hash_cert_der"]

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-LEDGER-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-LEDGER-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-LEDGER-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": cert.senha},
    )
    assert r.status_code == 200

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento = 'pdf_assinado_pades'
             ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-PADES-LEDGER-001",),
        )
        row = cur.fetchone()
    assert row is not None, "Evento pdf_assinado_pades deve estar registrado"
    payload = json.loads(row[0])
    assert payload["receituario_id"] == rec_id
    assert payload["nivel_pades"] == "B"
    assert payload["hash_cert_der"] == hash_cert_der
    assert "hash_pdf" in payload and len(payload["hash_pdf"]) == 64
    assert payload["ticket_referencia"] == "TICKET-21"


def test_pdf_assinado_sem_certificado_422(
    client, outer_conn, seed_usuario,
):
    """Prescritor SEM certificado ativo cadastrado → 422."""
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    # NÃO faz upload do certificado!
    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-SEMCERT-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-SEMCERT-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-SEMCERT-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": "qualquer"},
    )
    assert r.status_code == 422
    assert "certificado" in r.json()["detail"].lower()


def test_pdf_assinado_senha_invalida_401(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste(senha="senha_correta")
    _upload_cert(client, token, cert)

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-SENHA-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-SENHA-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-SENHA-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": "senha_errada"},
    )
    assert r.status_code == 401


def test_pdf_assinado_senha_ausente_422(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste()
    _upload_cert(client, token, cert)

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-NOSENHA-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-NOSENHA-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-NOSENHA-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={},   # body sem senha_pfx
    )
    assert r.status_code == 422


def test_pdf_assinado_modo_assinatura_incompativel_409(
    client, outer_conn, seed_usuario,
):
    """Prescrição emitida com gov_br_nuvem → endpoint retorna 409
    (assinatura ICP não se aplica)."""
    token = obter_token_prescritor(client, seed_usuario)
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste()
    _upload_cert(client, token, cert)

    # Inserir prescrição com gov_br_nuvem em vez de icp_brasil_local
    now = datetime.utcnow()
    now_iso = now.isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               assinatura_hash, tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', 'gov_br_nuvem',
                    'aaaaaaaa', 'nova', %s, %s, %s)
            RETURNING id
            """,
            ("TEST-PADES-GOVBR-001", prescritor_id, paciente_id, now, now, now),
        )
        prescricao_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO prescricao_itens
              (prescricao_id, nome_medicamento, concentracao, quantidade,
               unidade_quantidade, forma_farmaceutica, posologia,
               status_item, classe_controle, created_at, updated_at)
            VALUES (%s, 'DIAZEPAM', '10mg', 30, 'comprimidos', '1cx',
                    '1 cp 8/8h', 'pendente', 'B1', %s, %s)
            """,
            (prescricao_id, now, now),
        )
        cur.execute(
            """
            INSERT INTO prescricao_assinatura (prescricao_id, tipo_certificado,
                  status_validacao, created_at, updated_at)
            VALUES (%s, 'gov_br_nuvem', 'assinatura_pendente', %s, %s)
            """,
            (prescricao_id, now_iso, now_iso),
        )
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-GOVBR-001")

    r = client.post(
        f"/prescricoes/TEST-PADES-GOVBR-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": cert.senha},
    )
    assert r.status_code == 409
    assert "icp" in r.json()["detail"].lower()


def test_pdf_assinado_outro_prescritor_403(client, outer_conn, seed_usuario):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescritor_e_paciente(outer_conn)
    cert = gerar_certificado_teste()
    _upload_cert(client, token, cert)

    _inserir_prescricao_b1(outer_conn, protocolo="TEST-PADES-403-001")
    rec_id = _gerar_e_numerar(client, token, "TEST-PADES-403-001")

    # Trocar dono da prescrição
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES ('111111111111111', 'OUTRO', true, %s, %s)
            ON CONFLICT (cns) DO NOTHING
            """,
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        cur.execute(
            """
            UPDATE prescricoes
               SET prescritor_id = (SELECT id FROM prescritores WHERE cns = '111111111111111')
             WHERE protocolo = %s
            """,
            ("TEST-PADES-403-001",),
        )
    r = client.post(
        f"/prescricoes/TEST-PADES-403-001/receituarios/{rec_id}/pdf-assinado",
        headers=_headers(token),
        json={"senha_pfx": cert.senha},
    )
    assert r.status_code == 403


# ===========================================================================
# Anti-logging — middleware aux flag
# ===========================================================================

def test_rota_com_body_sensivel_marcada():
    """Constante BODY_NUNCA_LOGAR cobre as rotas críticas."""
    from app.middleware.sensitive_body import rota_tem_body_sensivel

    assert rota_tem_body_sensivel("/prescritor/certificado") is True
    assert rota_tem_body_sensivel(
        "/prescricoes/abc-123/receituarios/42/pdf-assinado"
    ) is True
    assert rota_tem_body_sensivel("/receituarios/42/pdf-assinado") is True
    # Negativos
    assert rota_tem_body_sensivel("/prescricoes") is False
    assert rota_tem_body_sensivel("/receituarios/42/pdf") is False
    assert rota_tem_body_sensivel("") is False
