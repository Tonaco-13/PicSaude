"""
tests/browser/test_entrar_em_obras.py — despacho Entrar (31/08).

O QUE ESTE ARQUIVO PROVA
------------------------
`entrar.html` deixou de ser a fachada de serviço (que mudou para
`demo.html` — guarda em `test_frontend_j11_selo_e_lente.py` e
`test_j11_selo_e_lente.py`) e passou a servir a página "em obras": sem
login falso, sem promessa vazia — um convite honesto a entrar na lista de
espera. Conceito validado por Fabiano com parecer do arquiteto
(`conceitos-landing/entrar.html`).

1. O mini-trilho mostra os três passos (Vitrine no ar · Lista de espera ·
   Plataforma), com "Vitrine no ar" como link real para `demo.html` — a
   página não esconde que a vitrine já existe.
2. O gesto do formulário (nome + email) monta o `mailto:` com assunto e
   corpo. `location.href` é "unforgeable" — nem redefinir `window.location`
   nem sobrescrever o acessor de `Location.prototype.href` intercepta a
   atribuição no Chromium (os dois foram tentados e falharam; confirmado
   empiricamente, não por suposição). A prova fica em duas pernas
   complementares: (a) em runtime, o clique completa o handler até o fim
   sem lançar erro — a confirmação aparece e a página NÃO navega (o
   Chromium headless não tem cliente de email registrado, então o mailto
   é descartado em silêncio, e `location.href` permanece na própria
   página); (b) por inspeção do FONTE do script inline, que o template do
   mailto referencia o endereço certo e interpola os campos do
   formulário — mesma disciplina estática de `test_frontend_j11_selo_e_lente.py`.
3. Sem JS, o endereço de contato continua visível e clicável — fallback
   real, não decorativo (checado com um contexto de browser à parte, JS
   desligado).
4. Nenhum campo pré-preenchido: o placeholder ensina o formato sem
   fornecer um valor fictício que o visitante possa enviar sem querer.
"""
from __future__ import annotations

import re

from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000


def test_mini_trilho_tem_os_tres_passos_e_vitrine_e_link(page: Page, app_demo):
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
    trilho = page.locator(".mini-trilho")
    expect(trilho).to_contain_text("Vitrine no ar")
    expect(trilho).to_contain_text("Lista de espera")
    expect(trilho).to_contain_text("Plataforma")

    link_vitrine = trilho.locator("a", has_text="Vitrine no ar")
    expect(link_vitrine).to_have_attribute("href", "demo.html")


def test_formulario_completa_o_gesto_e_confirma_sem_navegar(page: Page, app_demo, erros_de_console):
    """Perna (a) — runtime: o handler roda até o fim (a confirmação
    aparece) sem erro de console, e a página não navega para fora de si
    mesma (o Chromium headless não tem cliente de email para entregar o
    mailto, então descarta a tentativa em silêncio — o mesmo que um
    visitante real veria: a aba continua na mesma tela)."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")

    page.fill("#campoNome", "Maria de Teste")
    page.fill("#campoEmail", "maria@example.com")
    page.click(".btn-lista")

    expect(page.locator("#confirmacao")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#confirmacao")).to_contain_text("aplicativo de email")
    assert page.url.endswith("/entrar.html"), (
        f"a página navegou para {page.url} — o mailto não deveria trocar a aba"
    )
    assert not erros_de_console, erros_de_console


def test_formulario_monta_o_mailto_certo_no_fonte(app_demo):
    """Perna (b) — fonte: o template do mailto no script inline referencia
    o endereço certo e interpola nome/email do formulário. Runtime não
    prova ISSO (location.href é unforgeable — ver módulo); fonte prova."""
    import httpx

    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    assert "'mailto:contato@picsaude.com.br'" in html
    assert "subject=" in html and "encodeURIComponent(assunto)" in html
    assert "body=" in html and "encodeURIComponent(corpo)" in html
    # `corpo` interpola os dois campos do formulário, não texto solto.
    assert re.search(r"corpo\s*=.*campoNome.*campoEmail", html, re.DOTALL) or re.search(
        r"corpo\s*=.*Nome:.*\+\s*nome", html
    ), "o corpo do mailto não parece interpolar nome/email do formulário"


def test_endereco_de_contato_visivel_sem_js(browser, app_demo):
    """Regra de casa do conceito: conteúdo íntegro sem JS. Um contexto à
    parte com JS desligado prova que o fallback não é decorativo."""
    ctx = browser.new_context(java_script_enabled=False)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/entrar.html", wait_until="load")
        links = pg.locator('a[href^="mailto:contato@picsaude.com.br"]')
        expect(links.first).to_be_visible(timeout=_TIMEOUT_MS)
        assert links.count() >= 2, (
            "esperava pelo menos 2 mailtos visíveis sem JS (nota do "
            "formulário + rodapé) — fallback real, não decorativo"
        )
    finally:
        ctx.close()


def test_campo_livre_sem_valor_ficticio_pre_preenchido(page: Page, app_demo):
    """Placeholder ensina o formato; valor pré-preenchido ensinaria a
    digitar fictício — a mesma lição já aplicada à lente (despacho da
    Lente da abertura, item 'campo livre')."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
    nome = page.locator("#campoNome")
    email = page.locator("#campoEmail")
    expect(nome).to_have_value("")
    expect(email).to_have_value("")


def test_pagina_em_obras_nao_carrega_config_js(app_demo):
    """'Nada server-side, por desenho': a página não depende de config.js
    (que faz fetch a /config/public) nem de nenhum script além do seu
    próprio gesto de mailto."""
    import httpx

    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    assert 'src="config.js"' not in html
