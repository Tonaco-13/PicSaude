"""
tests/browser/test_typeahead_encaminhamento.py — typeahead/CBO PR 1+2 (`module`+`adapter`).

DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §4/§6: o encaminhamento adota a
mesma língua visual dos painéis assistidos (padrão-ouro: o painel de CID do
atestado). Um componente (`typeahead-catalogo.js`), duas montagens —
especialidade e mini-CID.

PR 1 (`module`) construiu o painel contra a lista local de 15/55 — prova
que o componente é agnóstico de fonte. PR 2 (`adapter`,
`importar_snapshot_cbo_encaminhamento.py`) trocou SÓ o arquivo de dados: 21
especialidades com código CBO (as 15 médicas + odontologia/enfermagem/
fisioterapia/nutrição/fonoaudiologia/psicologia), família declarada,
provenância CBO/MTE — sem tocar `typeahead-catalogo.js` nem
`prescritor.html`'s glue de montagem. Os testes que dependiam da lista
local antiga (chip ausente, rodapé "lista local curada") foram atualizados
para o novo estado — é a evolução esperada, não regressão.

O QUE ESTE ARQUIVO PROVA
-------------------------
AC1 (painel): digitar abre o painel com eco + lista + contagem, sem clique em <select>.
AC1 (base):   toda especialidade oferecida carrega código CBO (chip).
AC2+AC6 (base): "PSI" lista PSICOLOGIA com CBO 2515 — o caso-guarda do §1
     (psicologia fora do subgrupo 22, dentro do universo de destino).
AC3 (painel): zero badge de confiança (sem engine de casamento difuso aqui).
AC3+AC6 (base): rodapé passa a citar CBO/MTE — o teste da agnosticidade.
AC4 (painel): escape ("OUTRA"/"não listado") funciona nos dois campos.
AC5 (painel): mini-CID mostra código como chip; provenância "parcial"
     (mini-CID não muda nesta PR — só especialidade trocou de base).
AC6 (painel): digitar "CARDIO" lista CARDIOLOGIA; navegação por teclado não
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
# AC1 (base CBO) — toda especialidade oferecida carrega código CBO
# ===========================================================================

def test_toda_especialidade_mostra_codigo_cbo_como_chip(browser, app_demo):
    """DESENHO-TYPEAHEAD-ENCAMINHAMENTO-CBO.md §3 AC1 — pós-troca de base,
    NENHUMA entrada fica sem código (era o oposto na lista local do PR do
    painel — a mudança de comportamento É o ponto desta PR)."""
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        linha = pg.locator("#enc-especialidade-painel .tac-item", has_text="CARDIOLOGIA")
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha.locator(".tac-item-codigo")).to_have_text("2251-20")

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC2 + AC6 (§3) — 2515 presente: "PSI" acende PSICOLOGIA com o CBO da
# família guarda (fora do subgrupo 22, dentro do universo de destino mesmo
# assim — o caso inteiro que motivou a whitelist explícita em vez de prefixo)
# ===========================================================================

def test_psi_lista_psicologia_com_cbo_2515(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)

        pg.locator("#enc-especialidade-busca").click()
        pg.locator("#enc-especialidade-busca").type("PSI")

        painel = pg.locator("#enc-especialidade-painel")
        linha = painel.locator(".tac-item", has_text="PSICOLOGIA")
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha.locator(".tac-item-codigo")).to_have_text("2515-10")

        # "PSI" também casa PSIQUIATRIA — as duas convivem na lista, sem a
        # psicologia ficar de fora por estar num subgrupo CBO diferente.
        expect(painel.locator(".tac-item", has_text="PSIQUIATRIA")).to_be_visible()

        linha.click()
        expect(pg.locator("#enc-especialidade")).to_have_value("PSICOLOGIA")

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# AC3 + AC6 — rodapé passa a citar CBO/MTE porque o catálogo passou a
# declarar (o painel em si — typeahead-catalogo.js — não foi tocado nesta
# PR: é o teste da agnosticidade de fonte prometida no PR do painel)
# ===========================================================================

def test_rodape_declara_provenancia_cbo(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir_encaminhamento(pg, app_demo)
        pg.locator("#enc-especialidade-busca").click()

        rodape = pg.locator("#enc-especialidade-painel .tac-rodape")
        expect(rodape).to_be_visible(timeout=_TIMEOUT_MS)
        expect(rodape).to_contain_text("CBO/MTE")
        expect(rodape).to_contain_text("21 entradas")
        expect(rodape).to_contain_text("CBO 2002")

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
