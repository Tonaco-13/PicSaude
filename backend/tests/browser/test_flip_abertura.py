"""
tests/browser/test_flip_abertura.py — flip da abertura (30/08).

O QUE ESTE ARQUIVO PROVA
------------------------
O conceito de abertura (Kimi/arquiteto, `conceitos-landing/index.html`)
virou o `index.html` de produção; a fachada de serviço anterior (seletor
de papéis) moveu-se inteira para `entrar.html`. AC do despacho: "/ serve
a abertura (hero, trilho, lente demo rotulada) e /entrar.html serve a
fachada de serviço; nenhuma referência quebrada".

1. `/` serve a abertura — hero, trilho do objeto, lente rotulada como
   demonstração (a fiação real da lente é PR `module` separada, ainda
   não esta).
2. `/entrar.html` serve a fachada de serviço (o antigo `index.html`,
   sem mudança de conteúdo — só de endereço).
3. Nenhuma referência quebrada: todo `href`/`src` local do novo `/`
   resolve com 200 (as 4 pílulas das estações + "Entrar" + os 2 logos +
   as 3 fontes) — a mesma disciplina de "gate verde, deploy cego" que
   `test_paridade_deploy_assets.py` prova estaticamente, aqui provada
   ao vivo contra o servidor rodando.
4. O gesto "Entrar" pela tela leva a `/entrar.html` de verdade (clique,
   não só o href correto no HTML).

Cache-Control (no-cache para `entrar.html`, cache longo para `.woff2`)
tem arquivo próprio: `test_cache_control_entrada.py`.
"""
from __future__ import annotations

import re

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

_RE_LOCAL_REF = re.compile(r'(?:src|href)\s*=\s*["\']([^"\':?#]+)["\']')


def _refs_locais(html: str) -> list[str]:
    achados = []
    for ref in _RE_LOCAL_REF.findall(html):
        if ref.startswith(("http://", "https://", "//", "data:", "mailto:")):
            continue
        achados.append(ref)
    return achados


# ===========================================================================
# 1 — "/" serve a abertura
# ===========================================================================

def test_raiz_serve_a_abertura(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    expect(page).to_have_title(re.compile("trilhos", re.IGNORECASE))
    expect(page.locator("h1")).to_contain_text("trilhos")
    # o trilho do objeto (hero card + estações)
    expect(page.locator(".objeto-rail")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#railDots .rail-dot")).to_have_count(4)
    # a lente segue demonstrativa e ROTULADA como tal nesta PR — a fiação
    # real é a próxima PR module, não esta.
    lente = page.locator("#lente")
    expect(lente).to_contain_text("Demonstração visual")


def test_raiz_nao_tem_mais_disclaimer_de_prototipo(app_demo):
    """O rodapé "protótipo conceitual" saía nesta PR — agora É o site."""
    r = httpx.get(f"{app_demo}/", timeout=15.0)
    assert "Protótipo conceitual" not in r.text
    assert "Não é o site oficial" not in r.text


# ===========================================================================
# 2 — "/entrar.html" serve a fachada de serviço
# ===========================================================================

def test_entrar_html_serve_a_fachada_de_servico(page: Page, app_demo):
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
    expect(page).to_have_title(re.compile("Portal de Acesso"))
    expect(page.locator("h2")).to_contain_text("Custódia Sanitária Digital")


# ===========================================================================
# 3 — nenhuma referência quebrada
# ===========================================================================

def test_nenhuma_referencia_local_da_abertura_quebrada(app_demo):
    html = httpx.get(f"{app_demo}/", timeout=15.0).text
    refs = _refs_locais(html)
    assert refs, "nenhuma referência local encontrada — parser do teste quebrado"

    quebradas = []
    for ref in set(refs):
        alvo = ref.lstrip("/") or "index.html"
        r = httpx.get(f"{app_demo}/{alvo}", timeout=15.0)
        if r.status_code != 200:
            quebradas.append((ref, r.status_code))
    assert not quebradas, f"referências quebradas em /: {quebradas}"


def test_pilulas_e_entrar_apontam_para_paginas_reais(app_demo):
    """As 4 estações + o botão Entrar — checagem nomeada, não só via regex
    genérico, para o achado ficar legível se uma quebrar."""
    esperado = {
        "prescritor.html": "Consultório",
        "dispensador.html": "Farmácia",
        "cidadao.html": "Carteira Cidadã",
        "clinica.html": "Clínica / Laboratório",
        "entrar.html": "Entrar",
    }
    for pagina, rotulo in esperado.items():
        r = httpx.get(f"{app_demo}/{pagina}", timeout=15.0)
        assert r.status_code == 200, f"{rotulo} ({pagina}): {r.status_code}"


# ===========================================================================
# 4 — o gesto "Entrar" pela tela
# ===========================================================================

def test_clicar_entrar_navega_para_entrar_html(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    page.get_by_role("link", name="Entrar", exact=True).click()
    page.wait_for_url(re.compile(r"/entrar\.html$"), timeout=_TIMEOUT_MS)
    expect(page).to_have_title(re.compile("Portal de Acesso"))
