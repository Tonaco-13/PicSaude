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
2. Os alvos `http(s)://` externos de cada página são uma LISTA FECHADA e
   nomeada — sem iconografia de terceiro, sem badge, sem widget (nenhum
   outro domínio externo entrou de carona).

   Em `index.html` são DOIS desde 04/09 (atribuição institucional): o
   repositório e a **certidão PJ324-2026** no rodapé, no lugar da antiga
   linha "Responsável técnico". Em `entrar.html` segue sendo um só.
   O que este teste guarda é a lista fechada, não o número um: acrescentar
   um alvo é decisão declarada aqui, nunca efeito colateral de outra PR.
   Ver `docs/tickets/DESPACHO-ATRIBUICAO-INSTITUCIONAL.md`.
3. A microcopy "Código aberto · AGPL-3.0" está presente perto do link —
   quem clica já sabe o que encontra.
"""
from __future__ import annotations

import re

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000
_REPO_URL = "https://github.com/Tonaco-13/PicSaude"
_CERTIDAO_URL = (
    "https://github.com/Tonaco-13/PicSaude/blob/main/docs/institucional/PJ324-2026.md"
)

# Lista fechada de alvos externos, por página. Acrescentar um item aqui é ato
# declarado; sem isso, qualquer domínio novo derruba o teste.
_EXTERNOS_INDEX = {_REPO_URL, _CERTIDAO_URL}
_EXTERNOS_ENTRAR = {_REPO_URL}

_RE_HREF_EXTERNO = re.compile(r'href\s*=\s*["\'](https?://[^"\']+)["\']')


def _hrefs_externos(html: str) -> set[str]:
    return set(_RE_HREF_EXTERNO.findall(html))


def test_index_tem_os_dois_alvos_externos_declarados(app_demo):
    html = httpx.get(f"{app_demo}/", timeout=15.0).text
    externos = _hrefs_externos(html)
    assert externos == _EXTERNOS_INDEX, (
        f"a lista de alvos externos de / mudou. Esperava {_EXTERNOS_INDEX}; "
        f"achei {externos}. Alvo externo novo é decisão declarada — se for "
        f"legítimo, acrescente em _EXTERNOS_INDEX e diga por quê no despacho."
    )
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "Código aberto" in html and "AGPL-3.0" in html


def test_entrar_tem_o_link_e_e_o_unico_externo(app_demo):
    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    externos = _hrefs_externos(html)
    assert externos == _EXTERNOS_ENTRAR, (
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
