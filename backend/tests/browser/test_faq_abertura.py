"""
tests/browser/test_faq_abertura.py — FAQ da abertura (module, 03/09).

O QUE ESTE ARQUIVO PROVA
------------------------
A abertura ganhou a seção "Perguntas de quem acabou de chegar", logo depois
de Princípios: 9 entradas em `<details>`/`<summary>`, accordion NATIVO.

1. As 9 perguntas existem — e existem no HTML SERVIDO, antes de qualquer
   script rodar. Contadas na resposta crua do servidor, não no DOM montado.
2. Abrem SEM JavaScript. Aqui a prova é literal: um contexto de navegador
   com `java_script_enabled=False` abre a página, clica no `<summary>` e o
   `<details>` fica `[open]` com a resposta visível. É a exigência da casa
   ("conteúdo acessível sem JS", a mesma disciplina dos reveals, que só
   escondem sob `body.js-reveal`) verificada pelo comportamento, não pela
   leitura do código.
3. Nenhum script da página toca a FAQ — se algum dia alguém trocar o
   accordion nativo por um de JavaScript, este teste acusa.
4. A âncora `#faq` responde: navegar até ela para a seção dentro da janela e
   abaixo da topbar sticky — e o rodapé aponta para ela, porque âncora que
   ninguém alcança é âncora pela metade.
5. A ordem no documento é Princípios → FAQ (o despacho pede "após
   Princípios", e ordem de seção é conteúdo, não enfeite).
"""
from __future__ import annotations

import re

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

_QUANTAS_PERGUNTAS = 9

# `<details class="faq-item" ...>` — a marcação de cada entrada da FAQ.
_RE_ITEM = re.compile(r"<details[^>]*\bclass=[\"'][^\"']*\bfaq-item\b", re.I)
_RE_SUMMARY = re.compile(r"<summary\b", re.I)
_RE_SCRIPT = re.compile(r"<script\b[^>]*>(.*?)</script>", re.I | re.S)


def _html_da_abertura(app_demo: str) -> str:
    resposta = httpx.get(f"{app_demo}/", timeout=15.0)
    resposta.raise_for_status()
    return resposta.text


def test_a_faq_tem_nove_perguntas_no_html_servido(app_demo):
    """As 9 entradas chegam prontas do servidor — nada é montado por script."""
    html = _html_da_abertura(app_demo)

    itens = _RE_ITEM.findall(html)
    assert len(itens) == _QUANTAS_PERGUNTAS, (
        f"esperava {_QUANTAS_PERGUNTAS} <details class='faq-item'> no HTML "
        f"servido; achei {len(itens)}"
    )

    # Cada item precisa da sua pergunta clicável.
    corpo_faq = html.split('id="faq"', 1)[1]
    assert len(_RE_SUMMARY.findall(corpo_faq)) >= _QUANTAS_PERGUNTAS, (
        "toda entrada da FAQ precisa de um <summary> — a pergunta é o que se clica"
    )


def test_nenhum_script_da_pagina_toca_a_faq(app_demo):
    """Accordion nativo: se virar JS um dia, o gate acusa aqui."""
    html = _html_da_abertura(app_demo)
    for corpo in _RE_SCRIPT.findall(html):
        assert "faq" not in corpo.lower(), (
            "algum <script> da abertura menciona a FAQ — o accordion é nativo "
            "(<details>/<summary>) e não deve depender de JavaScript"
        )


def test_a_faq_abre_com_javascript_desligado(browser, app_demo):
    """A prova literal: sem JS, clicar na pergunta revela a resposta."""
    ctx = browser.new_context(java_script_enabled=False)
    try:
        page = ctx.new_page()
        page.goto(f"{app_demo}/", wait_until="domcontentloaded")

        itens = page.locator("#faq details.faq-item")
        expect(itens).to_have_count(_QUANTAS_PERGUNTAS, timeout=_TIMEOUT_MS)

        primeiro = itens.first
        # Nasce fechado, e a pergunta é legível mesmo assim.
        expect(primeiro.locator("summary")).to_be_visible(timeout=_TIMEOUT_MS)
        assert primeiro.get_attribute("open") is None, (
            "a FAQ deve nascer fechada — abrir é gesto de quem lê"
        )

        primeiro.locator("summary").click()

        # `[open]` é estado do próprio elemento: quem abriu foi o navegador.
        expect(page.locator("#faq details.faq-item[open]")).to_have_count(
            1, timeout=_TIMEOUT_MS
        )
        expect(primeiro.locator(".faq-resposta")).to_be_visible(timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


def test_a_ancora_faq_responde(page: Page, app_demo):
    """`#faq` responde e a seção para ABAIXO da topbar sticky.

    A abertura tem `html { scroll-behavior: smooth }`, e são ~5.700px até a
    FAQ: a rolagem leva mais de um segundo e `networkidle` dispara com ela
    ainda em voo. Por isso esperamos a medida ASSENTAR, em vez de medir uma
    vez só — medir cedo aqui acusa um defeito que não existe.
    """
    page.goto(f"{app_demo}/#faq", wait_until="networkidle")

    expect(page.locator("#faq")).to_have_count(1)

    altura_topbar = page.evaluate(
        "() => document.querySelector('.topbar').getBoundingClientRect().height"
    )
    assert altura_topbar > 0, "a topbar sumiu da abertura"

    # Assentada, a seção fica a `scroll-margin-top` do topo (100px) — folga
    # maior que a topbar (87px). Sem a folga, o título pararia atrás dela.
    page.wait_for_function(
        """(alturaTopbar) => {
            const topo = document.querySelector('#faq').getBoundingClientRect().top;
            return topo >= alturaTopbar && topo < window.innerHeight;
        }""",
        arg=altura_topbar,
        timeout=_TIMEOUT_MS,
    )


def test_o_rodape_leva_a_faq(page: Page, app_demo):
    """Âncora existe para ser alcançada — algo na página precisa apontar."""
    page.goto(f"{app_demo}/", wait_until="networkidle")

    link = page.locator('a[href="#faq"]')
    expect(link).to_have_count(1)
    expect(link.first).to_be_visible(timeout=_TIMEOUT_MS)


def test_a_faq_vem_depois_dos_principios(app_demo):
    """Ordem de seção é conteúdo: o despacho pede a FAQ APÓS Princípios."""
    html = _html_da_abertura(app_demo)
    pos_principios = html.find('id="principios"')
    pos_faq = html.find('id="faq"')
    assert pos_principios != -1, "seção de Princípios sumiu da abertura"
    assert pos_faq != -1, "seção #faq não existe na abertura"
    assert pos_principios < pos_faq, (
        "a FAQ precisa vir depois de Princípios no documento"
    )
