"""
tests/browser/test_encaminhamento_tres_sessoes.py — ENG-016, AC (vi).

O ROTEIRO DA VITRINE, PONTA A PONTA, EM TRÊS PERSONAS
-----------------------------------------------------
  > (vi) E2E das 3 sessões (origem/cidadão/destino) ensaiado com seed —
  > **403 no meio da vitrine mata a narrativa**.

É a razão de este arquivo existir e de ele usar TRÊS contextos de navegador
separados, com as personas do seed. Um teste de API prova que os endpoints
respondem; só o navegador prova que o Fabiano consegue contar a história sem
bater numa tela vazia — que é o que o AC pede.

O CICLO INTEIRO, e quem age em cada passo:

  1. **origem** emite pelo formulário (§5) → o documento vai à carteira;
  2. **cidadão** vê "Com você — leve ao profissional de CARDIOLOGIA" e
     **ENTREGA** (§1a: o gesto é dele, e é ele que move a posse);
  3. **destino** vê em "Chegou para mim", marca a consulta e atende;
  4. **cidadão** vê a consulta marcada com a DATA DA CONSULTA (§2 lei 4);
  5. **destino** contrarreferencia;
  6. **cidadão** vê "Voltou para você" com o retorno no MESMO cartão;
  7. **origem** dá ciência e encerra (§2 lei 7 — aqui a ciência é ATO).

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_encaminhamento_tres_sessoes.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira

_TIMEOUT_MS = 15_000

_CNS_ORIGEM  = "980001112223334"
_CNS_DESTINO = "980001112223335"
_CPF         = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_DATA_CONSULTA_ISO = "2026-10-07T14:30:00"

_TS = time.strftime("%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _ctx(browser, base_url: str, role: str, papel: str, sub: str, nome: str):
    ctx = browser.new_context()
    tok = _tok(base_url, role)
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {papel!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _pagina(ctx) -> tuple[Page, list[str]]:
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda exc: erros.append(f"pageerror: {exc}"))
    return pg, erros


def test_o_ciclo_completo_nas_tres_sessoes(browser, app_demo):
    """AC (vi) — e a prova de que nenhuma tela fica vazia no meio do roteiro."""
    justificativa = f"dor toracica aos esforcos, investigar isquemia {_TS}"
    todos_os_erros: list[str] = []

    # ── 1. ORIGEM emite pelo formulário ──────────────────────────────────
    ctx_o = _ctx(browser, app_demo, "prescritor", "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _pagina(ctx_o)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        pg.locator("#btn-submod-encaminhamento").click()
        expect(pg.locator("#form-encaminhamento")).to_be_visible(timeout=_TIMEOUT_MS)

        pg.fill("#enc-pac-nome", _NOME_PACIENTE)
        pg.fill("#enc-pac-cpf", _CPF)
        pg.select_option("#enc-finalidade", "avaliacao")
        pg.select_option("#enc-especialidade", "CARDIOLOGIA")
        pg.fill("#enc-cns-destino", _CNS_DESTINO)
        pg.fill("#enc-justificativa", justificativa)
        pg.click("#form-enc-main button[type=submit]")
        expect(pg.locator("#enc-doc-corpo")).to_contain_text("Encaminho o(a) paciente",
                                                             timeout=_TIMEOUT_MS)
        pg.click("#btn-enc-confirmar")
        expect(pg.locator("#enc-status-msg")).to_contain_text("entregue à carteira",
                                                              timeout=_TIMEOUT_MS)
        todos_os_erros += erros
    finally:
        ctx_o.close()

    proto = httpx.get(f"{app_demo}/paciente/encaminhamentos",
                      headers={"Authorization": f"Bearer {_tok(app_demo, 'paciente')}"},
                      timeout=15.0).json()["ativos"][0]["protocolo"]

    # ── 2. CIDADÃO vê "com você" e ENTREGA (§1a) ─────────────────────────
    ctx_c = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg, erros = _pagina(ctx_c)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "encaminhamentos")

        cartao = pg.locator(f"#enc-cid-{proto}")
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        expect(cartao).to_contain_text("CARDIOLOGIA")
        expect(cartao).to_contain_text("Com você")
        expect(cartao).to_contain_text("Leve ao profissional")

        pg.once("dialog", lambda d: d.accept())
        cartao.get_by_role("button", name="Entregar ao profissional").click()
        expect(pg.locator(f"#enc-cid-{proto}")).to_contain_text("Entregue", timeout=_TIMEOUT_MS)
        todos_os_erros += erros
    finally:
        ctx_c.close()

    # ── 3. DESTINO vê em "chegou para mim", marca e atende ───────────────
    ctx_d = _ctx(browser, app_demo, "prescritor_destino", "prescritor", _CNS_DESTINO,
                 "Dr. Demo Carlos Andrade")
    try:
        pg, erros = _pagina(ctx_d)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        pg.locator("#btn-submod-encaminhamento").click()
        pg.click("#enc-aba-btn-recebidos")
        expect(pg.locator("#enc-lista-chegou")).to_contain_text(proto, timeout=_TIMEOUT_MS)

        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_contain_text("aguardando sua decisão")   # DEVER
        pg.once("dialog", lambda d: d.accept("2026-10-07 14:30"))
        cartao.get_by_role("button", name="Agendar").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("Consulta marcada",
                                                              timeout=_TIMEOUT_MS)
        todos_os_erros += erros
    finally:
        ctx_d.close()

    # ── 4. CIDADÃO vê a DATA DA CONSULTA (§2 lei 4) ──────────────────────
    ctx_c2 = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg, erros = _pagina(ctx_c2)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "encaminhamentos")
        cartao = pg.locator(f"#enc-cid-{proto}")
        expect(cartao).to_contain_text("Consulta:", timeout=_TIMEOUT_MS)
        expect(cartao).to_contain_text("07/10/2026")
        expect(cartao).to_contain_text("14:30")
        todos_os_erros += erros
    finally:
        ctx_c2.close()

    # ── 5. DESTINO atende e contrarreferencia ────────────────────────────
    ctx_d2 = _ctx(browser, app_demo, "prescritor_destino", "prescritor", _CNS_DESTINO,
                  "Dr. Demo Carlos Andrade")
    try:
        pg, erros = _pagina(ctx_d2)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        pg.locator("#btn-submod-encaminhamento").click()
        pg.click("#enc-aba-btn-recebidos")
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        pg.once("dialog", lambda d: d.accept())
        cartao.get_by_role("button", name="Atender").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("contrarreferência agora é sua",
                                                              timeout=_TIMEOUT_MS)

        # dever ≠ posse: continua na tela DELE, com a posse no cidadão
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_contain_text("com o cidadão")
        expect(cartao).to_contain_text("você deve a contrarreferência")

        pg.once("dialog", lambda d: d.accept("avaliado; sem isquemia, manter conduta"))
        cartao.get_by_role("button", name="Contrarreferir").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("devolvida à origem",
                                                              timeout=_TIMEOUT_MS)
        todos_os_erros += erros
    finally:
        ctx_d2.close()

    # ── 6. CIDADÃO vê "voltou para você", com o retorno no MESMO cartão ──
    ctx_c3 = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg, erros = _pagina(ctx_c3)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "encaminhamentos")
        cartao = pg.locator(f"#enc-cid-{proto}")
        expect(cartao).to_contain_text("Voltou para você", timeout=_TIMEOUT_MS)
        expect(cartao).to_contain_text("manter conduta")
        expect(cartao).to_contain_text("Retorno do especialista")
        todos_os_erros += erros
    finally:
        ctx_c3.close()

    # ── 7. ORIGEM dá ciência e encerra (§2 lei 7) ────────────────────────
    ctx_o2 = _ctx(browser, app_demo, "prescritor", "prescritor", _CNS_ORIGEM,
                  "Dra. Demo Maria Souza")
    try:
        pg, erros = _pagina(ctx_o2)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        pg.locator("#btn-submod-encaminhamento").click()
        pg.click("#enc-aba-btn-encaminhados")
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        pg.once("dialog", lambda d: d.accept())
        cartao.get_by_role("button", name="Dar ciência e encerrar").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("encerrado", timeout=_TIMEOUT_MS)
        todos_os_erros += erros
    finally:
        ctx_o2.close()

    # NENHUM erro de JS em NENHUMA das sessões — é o "403 no meio da vitrine
    # mata a narrativa" generalizado: exceção não tratada faz o mesmo estrago.
    assert not todos_os_erros, todos_os_erros

    r = httpx.get(f"{app_demo}/encaminhamentos/{proto}",
                  headers={"Authorization": f"Bearer {_tok(app_demo, 'prescritor')}"},
                  timeout=15.0)
    assert r.json()["status"] == "encerrado"
