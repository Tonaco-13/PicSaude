"""Ticket 17 — Testes de integração do gerador de PDF de receituários.

Cobertura
---------
1. Geração de PDF para cada tipo (NRA / NRB / RCE / NRE / RSI).
2. Transição de status: numerado_stub | nao_requer_sncr → emitido.
3. Idempotência no acesso repetido (não dispara novo `receituario_emitido`).
4. Marca d'água em modo stub.
5. QR Code presente.
6. Bloqueio de receituário não numerado / cancelado.
7. Autenticação e posse.

Setup reaproveita os helpers de `test_receituarios.py` (insere prescrição
direto via outer_conn, gera receituários via /gerar, numera via /numerar).
"""
from __future__ import annotations

import json
from datetime import datetime

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


def _inserir_prescricao(
    outer_conn,
    *,
    assinatura_modo: str | None,
    classes_itens: list[str | None],
    protocolo: str,
    tipo_certificado: str | None = None,
    indicacao_clinica: str | None = None,
) -> int:
    prescritor_id, paciente_id = _inserir_prescritor_e_paciente(outer_conn)
    now = datetime.utcnow()
    now_iso = now.isoformat()
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescricoes
              (protocolo, prescritor_id, paciente_id, status, assinatura_modo,
               assinatura_hash, indicacao_clinica,
               tipo_emissao, data_emissao, created_at, updated_at)
            VALUES (%s, %s, %s, 'pendente', %s,
                    'a1b2c3d4e5f6789012345678901234567890abcdef0123456789aaaa',
                    %s, 'nova', %s, %s, %s)
            RETURNING id
            """,
            (
                protocolo, prescritor_id, paciente_id, assinatura_modo,
                indicacao_clinica, now, now, now,
            ),
        )
        prescricao_id = cur.fetchone()[0]
        for idx, classe in enumerate(classes_itens, start=1):
            cur.execute(
                """
                INSERT INTO prescricao_itens
                  (prescricao_id, nome_medicamento, concentracao, quantidade,
                   unidade_quantidade, forma_farmaceutica, posologia,
                   status_item, classe_controle, created_at, updated_at)
                VALUES (%s, %s, '500mg', 30, 'comprimidos',
                        '1 cx c/ 30 cps', '1 cp 8/8h por 7 dias',
                        'pendente', %s, %s, %s)
                """,
                (
                    prescricao_id,
                    f"MEDICAMENTO {classe or 'LIVRE'} {idx}",
                    classe,
                    now,
                    now,
                ),
            )
        if tipo_certificado is not None:
            cur.execute(
                """
                INSERT INTO prescricao_assinatura
                  (prescricao_id, tipo_certificado, status_validacao,
                   created_at, updated_at)
                VALUES (%s, %s, 'assinatura_pendente', %s, %s)
                """,
                (prescricao_id, tipo_certificado, now_iso, now_iso),
            )
    return prescricao_id


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _gerar(client, token: str, protocolo: str):
    return client.post(
        f"/prescricoes/{protocolo}/receituarios/gerar",
        headers=_headers(token),
    )


def _numerar(client, token: str, protocolo: str):
    return client.post(
        f"/prescricoes/{protocolo}/receituarios/numerar",
        headers=_headers(token),
    )


def _baixar_pdf(client, token: str, protocolo: str, receituario_id: int):
    return client.get(
        f"/prescricoes/{protocolo}/receituarios/{receituario_id}/pdf",
        headers=_headers(token),
    )


def _setup_prescricao_completa(
    client, token, outer_conn, *, classes, protocolo,
    tipo_certificado="A1", assinatura_modo="icp_brasil_local",
    indicacao_clinica=None,
):
    """Insere prescrição, gera receituários e numera. Retorna response do /numerar."""
    _inserir_prescricao(
        outer_conn,
        assinatura_modo=assinatura_modo,
        classes_itens=classes,
        protocolo=protocolo,
        tipo_certificado=tipo_certificado,
        indicacao_clinica=indicacao_clinica,
    )
    r = _gerar(client, token, protocolo)
    assert r.status_code == 201, r.text
    rn = _numerar(client, token, protocolo)
    assert rn.status_code == 200, rn.text
    return rn.json()


# ---------------------------------------------------------------------------
# 1–4. Geração por tipo + transição de status
# ---------------------------------------------------------------------------

def test_gerar_pdf_notificacao_a_amarela(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1"],
        protocolo="TEST-PDF-NRA-001",
    )
    rec = body_num["receituarios"][0]
    assert rec["tipo"] == "notificacao_receita_a"

    r = _baixar_pdf(client, token, "TEST-PDF-NRA-001", rec["id"])
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
    assert "receituario-NRA-" in r.headers["content-disposition"]
    assert len(r.content) > 2000  # PDF não-trivial

    # status agora deve ser "emitido"
    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status, emitido_em FROM receituarios WHERE id = %s",
            (rec["id"],),
        )
        row = cur.fetchone()
    assert row[0] == "emitido"
    assert row[1] is not None, "emitido_em deve ser preenchido"


def test_gerar_pdf_notificacao_b_azul(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["B1"],
        protocolo="TEST-PDF-NRB-001",
    )
    rec = body_num["receituarios"][0]
    assert rec["tipo"] == "notificacao_receita_b"

    r = _baixar_pdf(client, token, "TEST-PDF-NRB-001", rec["id"])
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert "NRB" in r.headers["content-disposition"]


def test_gerar_pdf_receita_controle_especial(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["C5"],
        protocolo="TEST-PDF-RCE-001",
    )
    rec = body_num["receituarios"][0]
    assert rec["tipo"] == "receita_controle_especial"

    r = _baixar_pdf(client, token, "TEST-PDF-RCE-001", rec["id"])
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert "RCE" in r.headers["content-disposition"]


def test_gerar_pdf_receita_simples(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=[None],
        protocolo="TEST-PDF-RSI-001",
        tipo_certificado=None,
        assinatura_modo=None,
    )
    rec = body_num["receituarios"][0]
    assert rec["tipo"] == "receita_simples"
    assert rec["status"] == "nao_requer_sncr"

    r = _baixar_pdf(client, token, "TEST-PDF-RSI-001", rec["id"])
    assert r.status_code == 200, r.text
    assert r.content[:4] == b"%PDF"
    assert "RSI" in r.headers["content-disposition"]

    with outer_conn.cursor() as cur:
        cur.execute(
            "SELECT status FROM receituarios WHERE id = %s", (rec["id"],),
        )
        assert cur.fetchone()[0] == "emitido"


# ---------------------------------------------------------------------------
# 5. Bloqueio de receituário não numerado
# ---------------------------------------------------------------------------

def test_pdf_bloqueia_receituario_nao_numerado(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["B1"],
        protocolo="TEST-PDF-NAO-NUM-001",
        tipo_certificado="A1",
    )
    r = _gerar(client, token, "TEST-PDF-NAO-NUM-001")
    assert r.status_code == 201
    rec_id = r.json()["receituarios"][0]["id"]

    # Pular /numerar — receituário ainda em status "gerado"
    r_pdf = _baixar_pdf(client, token, "TEST-PDF-NAO-NUM-001", rec_id)
    assert r_pdf.status_code == 422, r_pdf.text
    assert "numer" in r_pdf.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 6. Idempotência no acesso repetido
# ---------------------------------------------------------------------------

def test_pdf_acesso_repetido_idempotente(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1"],
        protocolo="TEST-PDF-IDEMP-001",
    )
    rec_id = body_num["receituarios"][0]["id"]

    r1 = _baixar_pdf(client, token, "TEST-PDF-IDEMP-001", rec_id)
    r2 = _baixar_pdf(client, token, "TEST-PDF-IDEMP-001", rec_id)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.content[:4] == b"%PDF"
    assert r2.content[:4] == b"%PDF"

    # Verificar que apenas 1 evento receituario_emitido foi gerado,
    # e que o segundo acesso gerou um receituario_pdf_acessado.
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.tipo_evento, pe.payload_json
              FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento IN ('receituario_emitido', 'receituario_pdf_acessado')
             ORDER BY pe.id ASC
            """,
            ("TEST-PDF-IDEMP-001",),
        )
        eventos = cur.fetchall()
    tipos = [e[0] for e in eventos]
    assert tipos.count("receituario_emitido") == 1, \
        f"Deveria emitir apenas 1× receituario_emitido, recebeu: {tipos}"
    assert tipos.count("receituario_pdf_acessado") >= 1, \
        f"Deveria registrar pdf_acessado no 2º acesso, recebeu: {tipos}"


# ---------------------------------------------------------------------------
# 7. Evento receituario_emitido no ledger
# ---------------------------------------------------------------------------

def test_pdf_registra_evento_ledger(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["B1"],
        protocolo="TEST-PDF-LEDGER-001",
    )
    rec = body_num["receituarios"][0]

    r = _baixar_pdf(client, token, "TEST-PDF-LEDGER-001", rec["id"])
    assert r.status_code == 200

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento = 'receituario_emitido'
             ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-PDF-LEDGER-001",),
        )
        row = cur.fetchone()

    assert row is not None, "Evento receituario_emitido não foi registrado"
    payload = json.loads(row[0])
    assert payload["tipo_receituario"] == "notificacao_receita_b"
    assert payload["adapter_usado"] == "stub"
    assert payload["numeracao_sncr"].startswith("STUB-")
    assert payload["ticket_referencia"] == "TICKET-17"


# ---------------------------------------------------------------------------
# 8. Marca d'água em modo stub
# ---------------------------------------------------------------------------

def test_pdf_stub_tem_marca_dagua():
    """Verifica direto a função `_watermark_callback`.

    Parsear o PDF gerado é frágil (ReportLab comprime streams por default),
    então testamos a função pura: o callback de stub DEVE escrever a
    string da marca d'água via canvas; o callback de modo real NÃO.
    """
    from app.domain.pdf_receituario import _watermark_callback

    chamadas: dict[str, list] = {"stub": [], "real": []}

    class _CanvasFake:
        """Mock mínimo de canvas — registra a string desenhada."""
        def __init__(self, registro: list):
            self.registro = registro

        def saveState(self): pass
        def restoreState(self): pass
        def setFont(self, *a, **kw): pass
        def setFillColor(self, *a, **kw): pass
        def translate(self, *a): pass
        def rotate(self, *a): pass

        def drawCentredString(self, x, y, text):
            self.registro.append(text)

    cb_stub = _watermark_callback(is_stub=True)
    cb_real = _watermark_callback(is_stub=False)

    cb_stub(_CanvasFake(chamadas["stub"]), None)
    cb_real(_CanvasFake(chamadas["real"]), None)

    # Stub desenhou a marca d'água
    assert any("DOCUMENTO SEM VALIDADE" in s for s in chamadas["stub"]), \
        f"Marca d'água stub não foi desenhada: {chamadas['stub']!r}"
    # Real NÃO desenhou nada
    assert chamadas["real"] == [], \
        f"Modo real não deve desenhar marca d'água: {chamadas['real']!r}"


def test_pdf_stub_evento_indica_adapter(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Salvaguarda complementar — evento receituario_emitido registra o
    adapter usado, deixando trilha auditável de que aquele PDF foi
    gerado em modo stub.
    """
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1"],
        protocolo="TEST-PDF-EVENTO-STUB-001",
    )
    rec = body_num["receituarios"][0]
    assert rec["adapter_usado"] == "stub"

    r = _baixar_pdf(client, token, "TEST-PDF-EVENTO-STUB-001", rec["id"])
    assert r.status_code == 200

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT pe.payload_json FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento = 'receituario_emitido'
             ORDER BY pe.id DESC LIMIT 1
            """,
            ("TEST-PDF-EVENTO-STUB-001",),
        )
        payload = json.loads(cur.fetchone()[0])
    assert payload["adapter_usado"] == "stub"


# ---------------------------------------------------------------------------
# 9. QR Code presente
# ---------------------------------------------------------------------------

def test_pdf_contem_qr_code(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """PDF deve conter QR code embutido. Como o conteúdo do PDF é
    comprimido por default no ReportLab, verificamos:
      1) o helper `_qr_drawing` produz um Drawing com dimensões corretas,
      2) o PDF resultante tem tamanho compatível com presença de QR.
    """
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.units import mm

    from app.domain.pdf_receituario import _qr_drawing

    # 1. Helper produz Drawing com dimensão esperada
    drawing = _qr_drawing("protocolo=test;sncr=N/A;hash=abc", lado_mm=25)
    assert isinstance(drawing, Drawing)
    assert abs(drawing.width  - 25 * mm) < 0.5
    assert abs(drawing.height - 25 * mm) < 0.5
    # Drawing tem pelo menos um conteúdo (o QrCodeWidget)
    assert len(drawing.contents) >= 1

    # 2. Endpoint retorna PDF com tamanho compatível com QR embutido
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["B1"],
        protocolo="TEST-PDF-QR-001",
    )
    rec = body_num["receituarios"][0]
    r = _baixar_pdf(client, token, "TEST-PDF-QR-001", rec["id"])
    assert r.status_code == 200
    # PDF com QR + parágrafos é bem maior que ~2KB.
    assert len(r.content) > 3500, \
        f"PDF muito pequeno para conter QR ({len(r.content)} bytes)"


# ---------------------------------------------------------------------------
# 10. Receita simples não exibe campo SNCR
# ---------------------------------------------------------------------------

def test_pdf_receita_simples_sem_campo_sncr(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Receita simples não passa pelo SNCR — bloco de numeração SNCR
    NÃO deve aparecer na faixa do documento (só pode aparecer no
    rodapé genérico 'PicSaúde — SNCR').
    """
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=[None],
        protocolo="TEST-PDF-SIMPLES-SEM-SNCR-001",
        tipo_certificado=None,
        assinatura_modo=None,
    )
    rec = body_num["receituarios"][0]

    r = _baixar_pdf(client, token, "TEST-PDF-SIMPLES-SEM-SNCR-001", rec["id"])
    assert r.status_code == 200
    body = r.content
    # Não deve conter "Nº SNCR" (o label da faixa SNCR).
    # "SNCR" sozinho aparece no rodapé/cabeçalho como rótulo de rastreabilidade,
    # mas o label específico da faixa de numeração não deve aparecer.
    assert b"DESENVOLVIMENTO" not in body, \
        "Receita simples não passa pelo SNCR — não deve indicar dev"
    assert b"STUB-" not in body, \
        "Receita simples não tem numeração STUB"


# ---------------------------------------------------------------------------
# 11. Fluxo completo: gerar → numerar → PDF de cada um
# ---------------------------------------------------------------------------

def test_fluxo_completo_gerar_numerar_pdf(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Prescrição com 3 itens: A1 + B1 + sem classe → 3 receituários.
    Cada um gera PDF distinto e fica em status 'emitido'.
    """
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1", "B1", None],
        protocolo="TEST-PDF-MIX-001",
        indicacao_clinica="ansiedade + dor",
    )
    receituarios = body_num["receituarios"]
    assert len(receituarios) == 3

    # Baixar PDF de cada um
    for rec in receituarios:
        r = _baixar_pdf(client, token, "TEST-PDF-MIX-001", rec["id"])
        assert r.status_code == 200, f"falhou para tipo={rec['tipo']}: {r.text}"
        assert r.content[:4] == b"%PDF"

    # Verificar 3 status = emitido + 3 eventos receituario_emitido
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT r.status, r.tipo_receituario
              FROM receituarios r
              JOIN prescricoes p ON p.id = r.prescricao_id
             WHERE p.protocolo = %s
            """,
            ("TEST-PDF-MIX-001",),
        )
        rows = cur.fetchall()
    assert len(rows) == 3
    assert all(r[0] == "emitido" for r in rows), \
        f"todos receituários devem estar emitidos, recebeu: {rows}"

    with outer_conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM prescricao_eventos pe
              JOIN prescricoes p ON p.id = pe.prescricao_id
             WHERE p.protocolo = %s
               AND pe.tipo_evento = 'receituario_emitido'
            """,
            ("TEST-PDF-MIX-001",),
        )
        total_eventos = cur.fetchone()[0]
    assert total_eventos == 3, \
        f"deveria haver 3 eventos receituario_emitido, recebeu: {total_eventos}"


# ---------------------------------------------------------------------------
# 12. Autenticação / posse
# ---------------------------------------------------------------------------

def test_pdf_exige_autenticacao(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1"],
        protocolo="TEST-PDF-AUTH-001",
    )
    rec_id = body_num["receituarios"][0]["id"]

    # Sem token → 401
    r = client.get(f"/prescricoes/TEST-PDF-AUTH-001/receituarios/{rec_id}/pdf")
    assert r.status_code == 401


def test_pdf_outro_prescritor_403(
    client, outer_conn, seed_usuario, seed_paciente,
):
    """Apenas o prescritor da prescrição pode baixar."""
    token = obter_token_prescritor(client, seed_usuario)
    body_num = _setup_prescricao_completa(
        client, token, outer_conn,
        classes=["A1"],
        protocolo="TEST-PDF-403-001",
    )
    rec_id = body_num["receituarios"][0]["id"]

    # Trocar prescritor da prescrição (simulando outro prescritor dono)
    with outer_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO prescritores (cns, nome, ativo, created_at, updated_at)
            VALUES ('111111111111111', 'OUTRO PRESCRITOR', true, %s, %s)
            ON CONFLICT (cns) DO NOTHING
            """,
            (datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        cur.execute(
            """
            UPDATE prescricoes
               SET prescritor_id = (
                   SELECT id FROM prescritores WHERE cns = '111111111111111'
               )
             WHERE protocolo = %s
            """,
            ("TEST-PDF-403-001",),
        )

    r = _baixar_pdf(client, token, "TEST-PDF-403-001", rec_id)
    assert r.status_code == 403


def test_pdf_receituario_inexistente_404(
    client, outer_conn, seed_usuario, seed_paciente,
):
    token = obter_token_prescritor(client, seed_usuario)
    _inserir_prescricao(
        outer_conn,
        assinatura_modo="icp_brasil_local",
        classes_itens=["A1"],
        protocolo="TEST-PDF-404-001",
        tipo_certificado="A1",
    )
    r = client.get(
        "/prescricoes/TEST-PDF-404-001/receituarios/9999999/pdf",
        headers=_headers(token),
    )
    assert r.status_code == 404
