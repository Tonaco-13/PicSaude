"""
tests/browser/test_typeahead_encaminhamento.py — typeahead/CBO PR 1 (`module`).

DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §4/§6: o encaminhamento adota a
mesma língua visual dos painéis assistidos (padrão-ouro: o painel de CID do
atestado). Um componente (`typeahead-catalogo.js`), duas montagens —
especialidade e mini-CID. Base = a lista atual de 15/55 nesta PR; a base
CBO entra depois (PR `adapter` seguinte) e o componente não muda uma linha
(AC 6 do §3) — mas essa promessa só se prova aqui, contra a lista pequena.

O QUE ESTE ARQUIVO PROVA
-------------------------
AC1: digitar abre o painel com eco + lista + contagem, sem clique em <select>.
AC2: rodapé declara a provenância lida do catálogo (na estréia: lista local).
AC3: zero badge de confiança (sem engine de casamento difuso aqui).
AC4: escape ("OUTRA"/"não listado") funciona nos dois campos.
AC5: mini-CID mostra código como chip; provenância "parcial".
AC6: digitar "CARDIO" lista CARDIOLOGIA; navegação por teclado não
     submete o formulário (Enter escolhe da lista, não envia).

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_typeahead_encaminhamento.py -v
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


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
    return ctx


def _pagina(ctx) -> tuple[Page, list[str]]:
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    return pg, erros


def _abrir_encaminhamento(pg: Page, base_url: str):
    pg.goto(f"{base_url}/prescritor.html", wait_until="networkidle")
    pg.locator("#submod-btn-encaminhamento").click()
    expect(pg.locator("#submod-encaminhamento")).to_be_visible(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC1 + AC6 — digitar abre o painel; "CARDIO" lista CARDIOLOGIA
# ===========================================================================

def test_digitar_cardio_abre_painel_e_lista_cardiologia(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)

        pg.locator("#enc-especialidade-busca").click()
        pg.locator("#enc-especialidade-busca").type("CARDIO")

        painel = pg.locator("#enc-especialidade-painel")
        expect(painel).to_be_visible(timeout=_TIMEOUT_MS)
        linha = painel.locator(".tac-item", has_text="CARDIOLOGIA")
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(painel.locator(".tac-eco")).to_contain_text("CARDIO")

        linha.click()
        expect(pg.locator("#enc-especialidade-busca")).to_have_value("CARDIOLOGIA")
        expect(pg.locator("#enc-especialidade")).to_have_value("CARDIOLOGIA")
        # painel fecha após escolher
        expect(painel).to_be_hidden(timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC1 (chip honesto) — especialidade da lista atual não tem código
# ===========================================================================

def test_especialidade_sem_codigo_nao_mostra_chip(browser, app_demo):
    """A lista atual não tem código CBO — o chip sem código É a forma
    honesta dela (§4), não um bug de renderização."""
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        linha = pg.locator("#enc-especialidade-painel .tac-item", has_text="CARDIOLOGIA")
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha.locator(".tac-item-codigo")).to_have_count(0)

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC2 — rodapé declara a provenância lida do catálogo
# ===========================================================================

def test_rodape_declara_provenancia_da_lista_local(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        rodape = pg.locator("#enc-especialidade-painel .tac-rodape")
        expect(rodape).to_be_visible(timeout=_TIMEOUT_MS)
        expect(rodape).to_contain_text("lista local curada")
        expect(rodape).to_contain_text("15 entradas")
        expect(rodape).to_contain_text("2026-08-23.1")

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC3 — zero badge de confiança (sem engine de casamento difuso)
# ===========================================================================

def test_zero_badge_de_confianca(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        painel = pg.locator("#enc-especialidade-painel")
        expect(painel).to_be_visible(timeout=_TIMEOUT_MS)
        texto = painel.inner_text()
        for termo_proibido in ("Aproximada", "Alta", "Média", "Exata"):
            assert termo_proibido not in texto, (
                f"'{termo_proibido}' apareceu no painel — badge de confiança "
                "não deveria existir aqui (§4, sem engine de casamento difuso)"
            )

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC4 — escape funciona (especialidade e CID)
# ===========================================================================

def test_escape_outra_na_especialidade(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        pg.locator("#enc-especialidade-painel .tac-escape").click()
        expect(pg.locator("#enc-especialidade")).to_have_value("OUTRA")
        expect(pg.locator("#enc-especialidade-outra-wrap")).to_be_visible(timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()


def test_escape_nao_listado_no_cid(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-cid-busca").click()

        pg.locator("#enc-cid-painel .tac-escape").click()
        expect(pg.locator("#enc-cid")).to_have_value("__OUTRO__")
        expect(pg.locator("#enc-cid-outro-wrap")).to_be_visible(timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC5 — mini-CID mostra código como chip; provenância "parcial"
# ===========================================================================

def test_cid_mostra_codigo_como_chip_e_provenancia_parcial(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)

        pg.locator("#enc-cid-busca").click()
        pg.locator("#enc-cid-busca").type("diabetes")

        painel = pg.locator("#enc-cid-painel")
        linha = painel.locator(".tac-item", has_text="Diabetes mellitus tipo 2")
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha.locator(".tac-item-codigo")).to_have_text("E11")

        rodape = painel.locator(".tac-rodape")
        expect(rodape).to_contain_text("parcial")
        expect(rodape).to_contain_text("códigos verificáveis")

        linha.click()
        expect(pg.locator("#enc-cid")).to_have_value("E11")
        expect(pg.locator("#enc-cid-busca")).to_have_value("E11 — Diabetes mellitus tipo 2")

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC6 — navegação por teclado não submete o formulário
# ===========================================================================

def test_enter_escolhe_da_lista_sem_submeter_o_formulario(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)

        pg.locator("#enc-especialidade-busca").click()
        pg.locator("#enc-especialidade-busca").press("ArrowDown")
        pg.locator("#enc-especialidade-busca").press("Enter")

        expect(pg.locator("#enc-especialidade")).to_have_value("CARDIOLOGIA")
        # Enter escolheu da lista — não é o "Confirmar e emitir": a tela de
        # revisão/documento não pode ter aparecido.
        expect(pg.locator("#enc-revisao")).to_be_hidden()
        expect(pg.locator("#form-enc-main")).to_be_visible()

        assert not erros, erros
    finally:
        ctx.close()
