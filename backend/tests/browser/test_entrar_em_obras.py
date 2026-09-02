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
2. **Despacho "Lista de espera direta" (module, 01/09) superou o mailto
   como MECANISMO de envio**: o formulário POSTa de verdade para
   `/lista-espera` (mesma origem, sem `config.js`/`BACKEND_URL`) — não é
   mais "monta um mailto e torce". O mailto SEGUE presente como link
   visível (fallback sem JS e para quem prefere), mas o gesto principal
   do botão "Entrar na lista de espera" agora é uma escrita real,
   auditável na rede (`page.expect_response`), não mais um artefato de
   `location.href` "unforgeable" (a lição anterior sobre isso morreu com
   o mecanismo que a exigia).
3. Sem JS, o endereço de contato continua visível e clicável — fallback
   real, não decorativo (checado com um contexto de browser à parte, JS
   desligado).
4. Nenhum campo pré-preenchido: o placeholder ensina o formato sem
   fornecer um valor fictício que o visitante possa enviar sem querer.
5. Honeypot (§4 do despacho): campo invisível e fora do tab-order; um
   preenchimento automatizado que o alcança recebe a MESMA confirmação —
   nunca sabe que foi pego. A gravação real (ou a ausência dela) é
   provada no backend, `tests/unit/test_lista_espera.py`.
6. A copy antiga ("nada é enviado sem que ela veja e confirme no seu
   cliente de email") morreu — não é mais verdade. A linha de
   consentimento nova declara o que realmente acontece com o dado.
"""
from __future__ import annotations

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
    """Despacho "Lista de espera direta" (module, 01/09): o formulário POSTa
    de verdade para `/lista-espera` (mesma origem — sem config.js/
    BACKEND_URL). Ponta a ponta: preenche → submete → a rede confirma 201
    → a confirmação aparece → a página não navega para fora de si mesma."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")

    with page.expect_response(
        lambda r: r.url.endswith("/lista-espera") and r.request.method == "POST"
    ) as resp_info:
        page.fill("#campoNome", "Maria de Teste")
        page.fill("#campoEmail", "maria.obras@example.com")
        page.click(".btn-lista")
    resposta = resp_info.value
    assert resposta.status == 201, f"POST /lista-espera devolveu {resposta.status}"

    expect(page.locator("#confirmacao")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#confirmacao")).to_contain_text("Você está na lista")
    expect(page.locator("#erroLista")).not_to_be_visible()
    assert page.url.endswith("/entrar.html"), (
        f"a página navegou para {page.url} — o fetch não deveria trocar a aba"
    )
    assert not erros_de_console, erros_de_console


def test_honeypot_preenchido_finge_sucesso_sem_avisar_o_robo(page: Page, app_demo):
    """§4 do despacho: um preenchimento automatizado que alcança o campo
    invisível recebe a MESMA confirmação — o robô nunca sabe que foi pego
    (a gravação real é provada no backend, `test_lista_espera.py`)."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")

    page.fill("#campoNome", "Robo de Teste")
    page.fill("#campoEmail", "robo@example.com")
    # Um humano nunca alcança este campo (fora da tela, fora do tab-order) —
    # preenchê-lo via JS simula exatamente o que um preenchimento
    # automatizado sem esse cuidado faz.
    page.evaluate("document.getElementById('campoEmpresa').value = 'Acme Bot Corp'")

    with page.expect_response(
        lambda r: r.url.endswith("/lista-espera") and r.request.method == "POST"
    ) as resp_info:
        page.click(".btn-lista")
    assert resp_info.value.status == 201

    expect(page.locator("#confirmacao")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#confirmacao")).to_contain_text("Você está na lista")


def test_campo_honeypot_fica_fora_da_visao_e_do_tab_order(page: Page, app_demo):
    """Fora da TELA (posicionamento, não `display:none`/`visibility:hidden`)
    é desenho, não descuido: bots de preenchimento automatizado costumam
    pular campos com essas duas propriedades justamente por serem o sinal
    de honeypot mais conhecido — por isso `to_be_hidden()` do Playwright
    (que olha exatamente essas duas) não é o teste certo aqui; a posição
    fora do viewport é."""
    page.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
    honeypot = page.locator("#campoEmpresa")

    caixa = honeypot.bounding_box()
    assert caixa is not None
    assert caixa["x"] < 0, f"honeypot deveria estar fora do viewport, x={caixa['x']}"

    assert honeypot.get_attribute("tabindex") == "-1"
    assert honeypot.get_attribute("autocomplete") == "off"
    expect(page.locator(".campo-honeypot")).to_have_attribute("aria-hidden", "true")


def test_mailto_de_fallback_continua_visivel_e_correto(app_demo):
    """§3 do despacho: "o mailto permanece como link visível — fallback sem
    JS e para quem prefere." Prova por fonte (sem JS, o link já resolve
    sozinho — não depende de nenhum script rodar)."""
    import httpx

    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    assert 'href="mailto:contato@picsaude.com.br' in html
    assert html.count('href="mailto:contato@picsaude.com.br') >= 2, (
        "esperava pelo menos 2 links mailto (nota de consentimento + rodapé)"
    )


def test_linha_de_consentimento_substituiu_a_promessa_antiga(app_demo):
    """§3 do despacho: a copy antiga ("nada é enviado sem que ela veja e
    confirme no seu cliente de email") deixou de ser verdade — o POST
    manda de verdade, sem confirmação manual. A linha nova declara o que
    realmente acontece com o dado."""
    import httpx

    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    assert "ficam guardados só para o contato da lista" in html
    assert "Nada é enviado sem" not in html
    assert "aplicativo de email vai abrir" not in html


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
    """A página segue sem `config.js` (nem seletor de personas, nem
    bootstrap de DEMO_MODE) — mas desde a Lista de espera direta (01/09)
    já NÃO é mais "nada server-side": o formulário fala com um endpoint
    real, `POST /lista-espera`. `config.js` continua desnecessário porque
    a chamada é direta (fetch relativo), não porque a página é estática."""
    import httpx

    html = httpx.get(f"{app_demo}/entrar.html", timeout=15.0).text
    assert 'src="config.js"' not in html
