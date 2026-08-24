"""
tests/browser/test_carteira_submodulos.py — a barra de submódulos da carteira.

A DECISÃO (Fabiano, 24/08)
--------------------------
A **barra de pílulas substitui as abas** como navegação primária da carteira —
e é a **mesma barra** da tela do prescritor, desenhada pela **mesma função**.
Um arquivo, duas telas: a aparência é idêntica porque é o mesmo código, não
porque alguém a mantém parecida.

A "placa da porta" (o que há atrás de cada uma) vive nos **empty states** de
cada seção, que já explicam o vazio por pergunta. Nada se perde; muda de lugar.

**Muda a porta, não o que há na casa.** Os baldes (posse / em andamento /
histórico) e as sinalizações da ENG-017 — botão de ciência do exame, elo para o
laudo — continuam exatamente como estavam. É isso que os testes de regressão
abaixo guardam: a navegação nova não pode ter custado nada do que já funcionava.

LAUDOS ganhou porta própria, saindo de dentro de Exames: é o que o cidadão veio
buscar, e estava uma rolagem abaixo dos pedidos (comissão #189, S1+S4).

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_carteira_cartoes.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira

_TIMEOUT_MS = 15_000
_CNS = "980001112223334"
_CPF = "12345678909"
_NOME = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"
_TS = time.strftime("%H%M%S")

_SUBMODULOS = ["receita", "exames", "agendamentos", "laudos", "atestado", "encaminhamentos"]


def _tok(u, r):
    resp = httpx.post(f"{u}/demo/login", json={"role": r}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _h(t): return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _ctx_cidadao(browser, u):
    ctx = browser.new_context()
    tok = _tok(u, "paciente")
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'paciente');
        sessionStorage.setItem('picsaude_demo_sub',   {_CPF!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME!r});
        """
    )
    return ctx


def _pagina(ctx):
    pg = ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    return pg, erros


# ===========================================================================
# 1 — a fórmula
# ===========================================================================

def test_a_carteira_abre_com_os_seis_submodulos(browser, app_demo):
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        barra = pg.locator("#submod-nav-carteira")
        expect(barra).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("[id^='submod-btn-']")).to_have_count(6)
        # A barra de ABAS saiu: navegação primária é uma só, senão o cidadão
        # tem duas maneiras de fazer a mesma coisa e nenhuma parece a certa.
        expect(pg.locator(".abas-carteira")).to_have_count(0)
        assert not erros, erros
    finally:
        ctx.close()


def test_a_barra_da_carteira_e_a_do_prescritor_sao_a_MESMA(browser, app_demo):
    """"Um arquivo, duas telas", verificado na tela e não no código.

    As guardas estáticas provam que as duas CARREGAM o componente; só o
    navegador prova que as duas RENDERIZAM a mesma coisa — mesma classe de
    trilho, mesma classe de pílula, mesma semântica.
    """
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-nav-carteira.submod-nav")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#submod-nav-carteira .submod-btn")).to_have_count(6)
        assert not erros, erros
    finally:
        ctx.close()

    tok = _tok(app_demo, "prescritor")
    ctx2 = browser.new_context()
    ctx2.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'prescritor');
        sessionStorage.setItem('picsaude_demo_sub',   '980001112223334');
        sessionStorage.setItem('picsaude_demo_nome',  'Dra. Demo Maria Souza');
        """
    )
    try:
        pg2, erros2 = _pagina(ctx2)
        pg2.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        expect(pg2.locator("#submod-nav-prescritor.submod-nav")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg2.locator("#submod-nav-prescritor .submod-btn")).to_have_count(4)
        # e o painel que o `aria-controls` promete existe DE VERDADE — era
        # `form-*` antes, e ARIA apontando para o vazio é fachada.
        alvo = pg2.locator("#submod-btn-encaminhamento").get_attribute("aria-controls")
        expect(pg2.locator(f"#{alvo}")).to_have_count(1)
        assert not erros2, erros2
    finally:
        ctx2.close()


def test_navegar_pelos_cartoes_mostra_um_painel_por_vez(browser, app_demo):
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        for chave in _SUBMODULOS:
            abrir_aba_carteira(pg, chave)
            expect(pg.locator(f"#submod-btn-{chave}")).to_have_attribute("aria-selected", "true")
            outros = [c for c in _SUBMODULOS if c != chave]
            for o in outros:
                expect(pg.locator(f"#submod-{o}")).to_be_hidden()
        assert not erros, erros
    finally:
        ctx.close()


def test_a_semantica_de_aba_foi_preservada(browser, app_demo):
    """Mudou a aparência, não a semântica: leitor de tela continua anunciando
    "aba N de 6, selecionada". Trocar abas por pílulas não pode custar
    acessibilidade."""
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-nav-carteira")).to_have_attribute("role", "tablist")
        for chave in _SUBMODULOS:
            expect(pg.locator(f"#submod-btn-{chave}")).to_have_attribute("role", "tab")
            expect(pg.locator(f"#submod-btn-{chave}")).to_have_attribute(
                "aria-controls", f"submod-{chave}")
        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 2 — o que NÃO pode ter mudado (muda a porta, não a casa)
# ===========================================================================

def _pedido_com_laudo(u):
    tp, tc, tl = _tok(u, "prescritor"), _tok(u, "paciente"), _tok(u, "clinica")
    r = httpx.post(f"{u}/pedidos-exame", headers=_h(tp), json={
        "cns_prescritor": _CNS, "nome_prescritor": "Dra. Demo Maria Souza",
        "cpf_paciente": _CPF, "nome_paciente": _NOME, "enviar_ao_paciente": True,
        "itens": [{"nome_exame": f"CARTOES-{_TS}", "quantidade": 1}]}, timeout=15.0)
    proto = r.json()["protocolo"]
    httpx.post(f"{u}/pedidos-exame/{proto}/transferir-laboratorio", headers=_h(tc),
               json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
               timeout=15.0)
    item = httpx.get(f"{u}/pedidos-exame/{proto}", headers=_h(tl), timeout=15.0).json()["itens"][0]["id"]
    httpx.post(f"{u}/pedidos-exame/{proto}/itens/{item}/coletar", headers=_h(tl), json={}, timeout=15.0)
    httpx.post(f"{u}/pedidos-exame/{proto}/itens/{item}/resultado", headers=_h(tl),
               json={"resultado_resumo": "sem alterações"}, timeout=15.0)
    rl = httpx.post(f"{u}/laudos", headers=_h(tl), json={
        "cns_autor": _CNS, "nome_autor": "RT", "cpf_paciente": _CPF, "nome_paciente": _NOME,
        "pedido_protocolo": proto,
        "itens": [{"pedido_item_id": item, "nome_exame": f"CARTOES-{_TS}",
                   "conclusao": "normal"}]}, timeout=15.0)
    lp = rl.json()["protocolo"]
    httpx.post(f"{u}/laudos/{lp}/assinar", headers=_h(tl), json={}, timeout=15.0)
    httpx.post(f"{u}/laudos/{lp}/liberar", headers=_h(tl), json={}, timeout=15.0)
    return proto, lp


def test_o_elo_da_ENG017_atravessa_a_porta_nova(browser, app_demo):
    """REGRESSÃO da entrega anterior: o cartão do exame leva ao laudo — que
    agora mora em submódulo próprio. Mudou o destino de aba, não o gesto."""
    proto, lp = _pedido_com_laudo(app_demo)
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")
        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        cartao.get_by_role("button", name="Ver laudo").click()

        expect(pg.locator("#submod-laudos")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator(f"#laudo-card-{lp}")).to_be_visible()
        assert not erros, erros
    finally:
        ctx.close()


def test_a_ciencia_do_exame_continua_no_cartao(browser, app_demo):
    """REGRESSÃO: o botão do S3 sobreviveu à troca de navegação."""
    proto, _ = _pedido_com_laudo(app_demo)
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")
        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao.get_by_role("button", name="Confirmo ciência do resultado")).to_be_visible(
            timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_o_contador_de_exames_deixou_de_somar_laudos(browser, app_demo):
    """Enquanto Laudos vivia dentro de Exames, o contador somava os dois e
    mudava sem dizer por quê — um dos sintomas do S4 na comissão. Agora cada
    porta conta o que há atrás dela."""
    _pedido_com_laudo(app_demo)
    ctx = _ctx_cidadao(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-count-laudos")).to_be_visible(timeout=_TIMEOUT_MS)
        laudos = int(pg.locator("#submod-count-laudos").inner_text())
        assert laudos >= 1, "o contador de Laudos não contou o laudo liberado"
        assert not erros, erros
    finally:
        ctx.close()
