"""
tests/browser/test_chips_cidadaos_demo.py — M-B (`module`).

DESENHO-VITRINE-HIGIENE-VISITANTE.md §3: quick-pick de cidadãos demo nos três
campos de paciente do prescritor (receita/exame/encaminhamento). Um clique
preenche nome + CPF de um cidadão canônico (`DEMO.cidadaos`, config.js,
espelhado em `seed_demo.py` PACIENTE/PACIENTE_2/PACIENTE_3) — o caminho
CANÔNICO fica mais preguiçoso que digitar um nome chulo qualquer.

O QUE ESTE ARQUIVO PROVA
-------------------------
1. Os três mounts (receita/exame/encaminhamento) desenham os três chips.
2. Clicar um chip preenche NOME + CPF (mascarado) nos dois campos certos —
   inclusive na receita, onde o campo de CPF (`pac-chave`) não é vizinho do
   campo de nome (`pac-nome`), mas o MESMO clique preenche os dois.
3. Texto livre continua funcionando — o campo é um <input> comum, não um
   <select>; digitar por cima do que o chip preencheu (ou sem tocar em chip
   nenhum) funciona igual.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_chips_cidadaos_demo.py -v
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

# Cidadãos canônicos da demo (config.js DEMO.cidadaos / seed_demo.py).
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"

_NOME_2, _CPF_2, _CPF_2_MASCARADO = "Ana Demo Ferreira", "23456789173", "234.567.891-73"
_NOME_3, _CPF_3, _CPF_3_MASCARADO = "Pedro Demo Costa", "34567891228", "345.678.912-28"


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


def _abrir(pg: Page, base_url: str, submodulo: str | None = None):
    pg.goto(f"{base_url}/prescritor.html", wait_until="networkidle")
    if submodulo:
        pg.locator(f"#submod-btn-{submodulo}").click()
        expect(pg.locator(f"#submod-{submodulo}")).to_be_visible(timeout=_TIMEOUT_MS)


# ===========================================================================
# 1 — os três mounts desenham os chips
# ===========================================================================

def test_os_tres_mounts_desenham_tres_chips_cada(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo)  # receita — aba padrão
        expect(pg.locator("#chips-cidadao-receita .chip-cidadao-demo")).to_have_count(3, timeout=_TIMEOUT_MS)

        _abrir(pg, app_demo, "exames")
        expect(pg.locator("#chips-cidadao-exame .chip-cidadao-demo")).to_have_count(3, timeout=_TIMEOUT_MS)

        _abrir(pg, app_demo, "encaminhamento")
        expect(pg.locator("#chips-cidadao-encaminhamento .chip-cidadao-demo")).to_have_count(3, timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 2 — clicar preenche nome + CPF nos dois campos certos
# ===========================================================================

def test_chip_na_receita_preenche_nome_e_cpf_apesar_da_distancia(browser, app_demo):
    """`pac-chave` (CPF) não é vizinho de `pac-nome` no formulário — o mesmo
    clique preenche os dois assim mesmo (a lacuna visual é do form, não do
    componente)."""
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo)
        pg.locator("#chips-cidadao-receita .chip-cidadao-demo", has_text=_NOME_2).click()
        expect(pg.locator("#pac-nome")).to_have_value(_NOME_2, timeout=_TIMEOUT_MS)
        expect(pg.locator("#pac-chave")).to_have_value(_CPF_2_MASCARADO, timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_chip_no_exame_preenche_nome_e_cpf(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo, "exames")
        pg.locator("#chips-cidadao-exame .chip-cidadao-demo", has_text=_NOME_3).click()
        expect(pg.locator("#exam-pac-nome")).to_have_value(_NOME_3, timeout=_TIMEOUT_MS)
        expect(pg.locator("#exam-pac-cpf")).to_have_value(_CPF_3_MASCARADO, timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_chip_no_encaminhamento_preenche_nome_e_cpf(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo, "encaminhamento")
        pg.locator("#chips-cidadao-encaminhamento .chip-cidadao-demo", has_text=_NOME_2).click()
        expect(pg.locator("#enc-pac-nome")).to_have_value(_NOME_2, timeout=_TIMEOUT_MS)
        expect(pg.locator("#enc-pac-cpf")).to_have_value(_CPF_2_MASCARADO, timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 3 — texto livre continua funcionando (o chip é atalho, não gate)
# ===========================================================================

def test_texto_livre_continua_disponivel_apos_o_chip(browser, app_demo):
    """O campo é um <input> comum: digitar por cima do que o chip preencheu
    funciona — o chip nunca vira a única porta de entrada."""
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo)
        pg.locator("#chips-cidadao-receita .chip-cidadao-demo", has_text=_NOME_2).click()
        expect(pg.locator("#pac-nome")).to_have_value(_NOME_2, timeout=_TIMEOUT_MS)

        pg.locator("#pac-nome").fill("Visitante Qualquer da Silva")
        expect(pg.locator("#pac-nome")).to_have_value("Visitante Qualquer da Silva")
        assert not erros, erros
    finally:
        ctx.close()
