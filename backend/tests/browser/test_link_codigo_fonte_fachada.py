"""
tests/browser/test_link_codigo_fonte_fachada.py — despacho "O link do código
na fachada" (module, 02/09).

O QUE ESTE ARQUIVO PROVA
------------------------
A vitrine aponta para a própria prova: `index.html` (abertura) e
`entrar.html` (obras — a página mais pública de todas, quem espera por uma
plataforma merece ver que ela já existe em aberto) ganham um link para o
repositório no GitHub.

1. O link "Código-fonte (GitHub)" existe nas duas páginas, aponta para o
   repo certo, abre em nova aba (`target="_blank"`) com `rel="noopener
   noreferrer"` (a casa não deixa a aba nova controlar a original).
2. É o ÚNICO alvo `http(s)://` externo novo em cada página — sem
   iconografia de terceiro, sem badge, sem widget (nenhum outro domínio
   externo apareceu de carona).
3. A microcopy "Código aberto · AGPL-3.0" está presente perto do link —
   quem clica já sabe o que encontra.
"""
from __future__ import annotations

import re

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000
_REPO_URL = "https://github.com/Tonaco-13/PicSaude"

_RE_HREF_EXTERNO = re.compile(r'href\s*=\s*["\'](https?://[^"\']+)["\']')


def _hrefs_externos(html: str) -> set[str]:
    return set(_RE_HREF_EXTERNO.findall(html))


def test_index_tem_o_link_e_e_o_unico_externo(app_demo):
    html = httpx.get(f"{app_demo}/", timeout=15.0).text
    externos = _hrefs_externos(html)
    assert externos == {_REPO_URL}, (
        f"esperava só o link do repo como alvo externo em /; achei {externos}"
    )
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "Código aberto" in html and "AGPL-3.0" in html


def test_entrar_tem_o_link_e_e_o_unico_externo(app_demo):
    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    externos = _hrefs_externos(html)
    assert externos == {_REPO_URL}, (
        f"esperava só o link do repo como alvo externo em /entrar.html; achei {externos}"
    )
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "Código aberto" in html and "AGPL-3.0" in html


def test_link_e_clicavel_e_visivel_na_abertura(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    link = page.get_by_role("link", name="Código-fonte (GitHub)")
    expect(link).to_be_visible(timeout=_TIMEOUT_MS)
    expect(link).to_have_attribute("href", _REPO_URL)
    expect(link).to_have_attribute("target", "_blank")


def test_link_e_clicavel_e_visivel_em_obras(page: Page, app_demo):
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
    link = page.get_by_role("link", name="Código-fonte (GitHub)")
    expect(link).to_be_visible(timeout=_TIMEOUT_MS)
    expect(link).to_have_attribute("href", _REPO_URL)
    expect(link).to_have_attribute("target", "_blank")
