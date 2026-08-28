"""
tests/browser/test_cidadao_demo_fixo.py — M-D (`module`, REVOGA M-B/M-C).

DESENHO-VITRINE-HIGIENE-VISITANTE.md §8: texto livre nos campos de paciente
permitia nome chulo — "aconteceu isso" (Fabiano, 28/08). M-B (chips) e M-C
(preenchimento padrão) tentaram tornar o caminho canônico mais preguiçoso
que a chulice sem fechar a porta do texto livre; não bastou. M-D fecha a
porta: os quatro campos de paciente (receita/exame/encaminhamento/atestado)
ficam `readonly`, sempre com o cidadão canônico (`DEMO.cidadao`) — nenhuma
edição possível pela tela, e não há mais escolha entre cidadãos (o
quick-pick do M-B foi removido).

O QUE ESTE ARQUIVO PROVA
-------------------------
1. Fresh load: os quatro pares já mostram o cidadão canônico, sem ação
   nenhuma do visitante.
2. Os oito campos (nome+CPF × 4 objetos) NÃO são editáveis — Playwright
   recusa `.fill()` num campo `readonly`, então tentar preencher é a prova.
3. O quick-pick do M-B não existe mais — nenhum `.chip-cidadao-demo` na
   página.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_cidadao_demo_fixo.py -v
"""
from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

# Cidadão canônico da demo (config.js DEMO.cidadao / seed_demo.py PACIENTE).
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_NOME_CANONICO = "João Demo da Silva"
_CPF_CANONICO_MASCARADO = "123.456.789-09"

# (nome_id, cpf_id, submodulo) — os quatro objetos travados.
_CAMPOS = [
    ("pac-nome", "pac-chave", None),                      # receita — aba padrão
    ("exam-pac-nome", "exam-pac-cpf", "exames"),
    ("enc-pac-nome", "enc-pac-cpf", "encaminhamento"),
    ("atestado-paciente", "atestado-cpf", "atestado"),
]


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
# 1 — fresh load: os quatro pares já mostram o cidadão canônico
# ===========================================================================

def test_fresh_load_os_quatro_pares_ja_mostram_o_cidadao_canonico(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo)
        for nome_id, cpf_id, submodulo in _CAMPOS:
            if submodulo:
                pg.locator(f"#submod-btn-{submodulo}").click()
                expect(pg.locator(f"#submod-{submodulo}")).to_be_visible(timeout=_TIMEOUT_MS)
            expect(pg.locator(f"#{nome_id}")).to_have_value(_NOME_CANONICO, timeout=_TIMEOUT_MS)
            expect(pg.locator(f"#{cpf_id}")).to_have_value(_CPF_CANONICO_MASCARADO, timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 2 — os oito campos não são editáveis
# ===========================================================================

@pytest.mark.parametrize("nome_id,cpf_id,submodulo", _CAMPOS)
def test_campos_travados_nao_sao_editaveis(browser, app_demo, nome_id, cpf_id, submodulo):
    """Playwright recusa `.fill()`/`.type()` num <input readonly> — a
    exceção É a prova de que o campo não aceita edição pela tela."""
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo, submodulo)

        expect(pg.locator(f"#{nome_id}")).not_to_be_editable(timeout=_TIMEOUT_MS)
        expect(pg.locator(f"#{cpf_id}")).not_to_be_editable(timeout=_TIMEOUT_MS)

        with pytest.raises(Exception):
            pg.locator(f"#{nome_id}").fill("TEBATO NAKARA", timeout=2_000)
        expect(pg.locator(f"#{nome_id}")).to_have_value(_NOME_CANONICO)

        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 3 — o quick-pick do M-B não existe mais
# ===========================================================================

def test_nenhum_chip_de_quick_pick_na_pagina(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        _abrir(pg, app_demo)
        expect(pg.locator(".chip-cidadao-demo")).to_have_count(0, timeout=_TIMEOUT_MS)

        for _, _, submodulo in _CAMPOS[1:]:
            pg.locator(f"#submod-btn-{submodulo}").click()
            expect(pg.locator(f"#submod-{submodulo}")).to_be_visible(timeout=_TIMEOUT_MS)
            expect(pg.locator(".chip-cidadao-demo")).to_have_count(0)

        assert not erros, erros
    finally:
        ctx.close()
