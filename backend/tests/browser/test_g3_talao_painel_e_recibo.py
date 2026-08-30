"""
tests/browser/test_g3_talao_painel_e_recibo.py — DESENHO-TALAO-DIGITAL-SNCR.md
§3 (G3, `module`).

O QUE ESTE ARQUIVO PROVA
------------------------
As duas ACs do §3, ao vivo:

1. **A vista dos talões** — o painel "Talões SNCR" do prescritor (leitura
   apenas) mostra o lote adquirido, com tipo/cor certos (A=amarelo,
   B=azul), próximo número, consumo e o selo honesto de stub.
2. **A presença do número na receita emitida de controlado** — o PDF do
   receituário numerado (endpoint já existente de Ticket 15/21, não
   tocado nesta PR) carrega o `Nº SNCR` + o rótulo honesto
   "[DESENVOLVIMENTO — numeração não regulatória]" quando o adapter é o
   stub. Verificado extraindo o TEXTO do PDF (pypdf — dependência só de
   `requirements-browser.txt`, nunca do Docker de produção).

Setup via API (padrão de `test_j11_selo_e_lente.py`/`test_typeahead_
encaminhamento.py`): a aquisição do lote e a geração/numeração do
receituário são chamadas de API — `adquirir_lote`/gerar/numerar não são
"gesto novo" desta PR (§2 já os construiu); o painel §3 só EXIBE o que
já existe, e o browser test SEMEIA esse "já existe" pela mesma API que
um cliente real chamaria, exatamente como os testes irmãos fazem.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_g3_talao_painel_e_recibo.py -v
"""
from __future__ import annotations

import io
import time

import httpx
from playwright.sync_api import expect, Page
from pypdf import PdfReader

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (config.js DEMO.* / seed_demo.py).
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF_PACIENTE = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"

_TS = time.strftime("%Y%m%d%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx_prescritor(browser, base_url: str):
    ctx = browser.new_context()
    tok = _tok(base_url, "prescritor")
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'prescritor');
        sessionStorage.setItem('picsaude_demo_sub',   {_CNS_PRESCRITOR!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME_PRESCRITOR!r});
        """
    )
    return ctx, tok


def _emitir_prescricao_controlada(
    base_url: str, tok: str, sufixo: str, *, classe_controle: str = "B1",
) -> str:
    """`classe_controle` decide o `tipo_receituario` no motor regulatório —
    A1/A2/A3 → notificacao_receita_a (amarela); B1/B2 → notificacao_receita_b
    (azul) (`domain/motor_regulatorio.py::GRUPO_A/GRUPO_B`)."""
    r = httpx.post(
        f"{base_url}/prescricoes",
        headers=_h(tok),
        json={
            "cns_prescritor": _CNS_PRESCRITOR, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF_PACIENTE, "nome_paciente": _NOME_PACIENTE,
            "assinatura_modo": "icp_brasil_local",
            "tipo_emissao": "nova",
            "itens": [{
                "nome_medicamento": f"MEDICAMENTO G3 {sufixo}",
                "quantidade": 20,
                "unidade_quantidade": "comprimido",
                "posologia": "1 cp à noite",
                "classe_controle": classe_controle,
            }],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _gerar_e_numerar(base_url: str, tok: str, protocolo: str) -> dict:
    r_gerar = httpx.post(
        f"{base_url}/prescricoes/{protocolo}/receituarios/gerar",
        headers=_h(tok), timeout=15.0,
    )
    assert r_gerar.status_code == 201, f"gerar falhou: {r_gerar.status_code} {r_gerar.text}"

    r_numerar = httpx.post(
        f"{base_url}/prescricoes/{protocolo}/receituarios/numerar",
        headers=_h(tok), timeout=15.0,
    )
    assert r_numerar.status_code == 200, f"numerar falhou: {r_numerar.status_code} {r_numerar.text}"
    return r_numerar.json()["receituarios"][0]


def _adquirir_lote(base_url: str, tok: str, tipo: str, quantidade: int) -> dict:
    r = httpx.post(
        f"{base_url}/receituarios/lotes",
        headers=_h(tok),
        json={"tipo_receituario": tipo, "quantidade": quantidade},
        timeout=15.0,
    )
    assert r.status_code == 201, f"adquirir lote falhou: {r.status_code} {r.text}"
    return r.json()


def _abrir_taloes(pg: Page, base_url: str):
    pg.goto(f"{base_url}/prescritor.html", wait_until="networkidle")
    pg.get_by_role("button", name="🎫 Talões SNCR").click()
    expect(pg.locator("#tela-taloes")).to_be_visible(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC1 do §3 — a vista dos talões
# ===========================================================================

def test_painel_taloes_mostra_lote_com_cor_e_consumo_certos(browser, app_demo):
    """Lote A (amarelo): adquirido com 5, consome 1 numerando um
    receituário controlado — o painel mostra tipo, cor, próximo número
    (2), consumo (1 de 5) e o selo honesto de stub."""
    ctx, tok = _ctx_prescritor(browser, app_demo)
    try:
        sufixo = f"{_TS}A"
        lote = _adquirir_lote(app_demo, tok, "notificacao_receita_a", 5)
        protocolo = _emitir_prescricao_controlada(
            app_demo, tok, sufixo, classe_controle="A1"
        )
        rec = _gerar_e_numerar(app_demo, tok, protocolo)
        assert rec["numeracao_sncr"].startswith(lote["lote_id"]), (
            f"numeração deveria sair do lote recém-adquirido ({lote['lote_id']}), "
            f"veio {rec['numeracao_sncr']!r}"
        )

        pg = ctx.new_page()
        _abrir_taloes(pg, app_demo)

        card = pg.locator(".talao-card", has_text=lote["lote_id"])
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)
        expect(card).to_have_class(re_compile_class("talao-card-a"))
        expect(card).to_contain_text("Notificação de Receita A")
        expect(card).to_contain_text("2")     # próximo número, após 1 saque
        expect(card).to_contain_text("1 de 5")  # consumo
        expect(card).to_contain_text("Ativo")
        expect(card).to_contain_text("STUB — ambiente de testes, sem validade SNCR real")
    finally:
        ctx.close()


def test_painel_taloes_lote_b_e_azul(browser, app_demo):
    ctx, tok = _ctx_prescritor(browser, app_demo)
    try:
        lote = _adquirir_lote(app_demo, tok, "notificacao_receita_b", 3)

        pg = ctx.new_page()
        _abrir_taloes(pg, app_demo)

        card = pg.locator(".talao-card", has_text=lote["lote_id"])
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)
        expect(card).to_have_class(re_compile_class("talao-card-b"))
        expect(card).to_contain_text("Notificação de Receita B")
    finally:
        ctx.close()


def test_painel_taloes_vazio_para_prescritor_sem_lote(browser, app_demo):
    """Persona isolada (token próprio, sem lotes adquiridos nesta sessão)
    — o painel não inventa dado; mostra o estado vazio."""
    ctx, tok = _ctx_prescritor(browser, app_demo)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        # Intercepta a chamada para simular "sem lotes" sem depender de
        # isolamento de dados entre testes (a mesma persona demo é
        # compartilhada pela sessão inteira do app_demo).
        pg.route(
            "**/receituarios/lotes",
            lambda route: route.fulfill(status=200, json={"lotes": []}),
        )
        pg.get_by_role("button", name="🎫 Talões SNCR").click()
        expect(pg.locator("#tela-taloes")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#taloes-lista")).to_contain_text(
            "Nenhum talão adquirido ainda", timeout=_TIMEOUT_MS
        )
    finally:
        ctx.close()


# ===========================================================================
# AC2 do §3 — a numeração aparece na receita (PDF) com o selo honesto
# ===========================================================================

def test_numero_sncr_e_selo_stub_aparecem_no_pdf_do_receituario(browser, app_demo):
    ctx, tok = _ctx_prescritor(browser, app_demo)
    try:
        sufixo = f"{_TS}PDF"
        protocolo = _emitir_prescricao_controlada(app_demo, tok, sufixo)
        rec = _gerar_e_numerar(app_demo, tok, protocolo)
        numeracao = rec["numeracao_sncr"]
        assert numeracao.startswith("STUB-")

        pg = ctx.new_page()
        resp = pg.request.get(
            f"{app_demo}/prescricoes/{protocolo}/receituarios/{rec['id']}/pdf",
            headers={"Authorization": f"Bearer {tok}"},
        )
        assert resp.ok, f"download do PDF falhou: {resp.status} {resp.text()}"
        assert resp.headers.get("content-type", "").startswith("application/pdf")

        texto = "".join(
            (p.extract_text() or "") for p in PdfReader(io.BytesIO(resp.body())).pages
        )
        assert numeracao in texto, (
            f"número SNCR {numeracao!r} não encontrado no texto extraído do PDF"
        )
        assert "DESENVOLVIMENTO" in texto, (
            "selo honesto de stub ([DESENVOLVIMENTO — numeração não regulatória]) "
            "ausente do PDF"
        )
    finally:
        ctx.close()


def re_compile_class(classe: str):
    """`expect(...).to_have_class` casa a string INTEIRA de `class="..."`
    por padrão; os cards têm duas classes (`talao-card talao-card-a`).
    Um regex que só exige a substring evita reescrever a lista toda."""
    import re
    return re.compile(rf"(^|\s){re.escape(classe)}(\s|$)")
