"""
tests/browser/test_carteira_wrap_e_fachada.py — fachada (estações) e o wrap da barra.

AS DUAS COISAS QUE ESTE ARQUIVO GUARDA
--------------------------------------
**1. A FACHADA nomeia ESTAÇÕES, o domínio nomeia ATORES** (decisão do Fabiano,
25/08). As portas passaram a se chamar Consultório · Farmácia · Carteira Cidadã
· Clínica/Laboratório. Os papéis de JWT, o RBAC e o vocabulário de custódia
continuam `prescritor`, `dispensador`, `paciente` — **renomear a porta não
renomeia quem entra**, e há teste afirmando as duas metades.

**2. A BARRA COM SEIS PÍLULAS QUEBRA LINHA COM GRAÇA.** A da tela do prescritor
tem quatro e sempre coube numa linha; a carteira tem seis. Viewport **fixa** nos
dois testes, porque wrap medido em janela de tamanho indefinido é medida que
muda sozinha.

O QUE ESTES TESTES **NÃO** FAZEM
--------------------------------
Não travam QUANTAS pílulas cabem por linha. Isso depende de fonte, zoom e do
texto de cada rótulo — travar o número transformaria toda troca de palavra em
teste vermelho. O que se trava é o que **não pode** acontecer: texto cortado,
barra estourando a janela, pílula invisível.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_carteira_wrap_e_fachada.py -v
"""
from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import expect

_TIMEOUT_MS = 15_000
_CPF = "12345678909"
_NOME = "João Demo da Silva"

_SUBMODULOS = ["receita", "exames", "atestado", "encaminhamentos", "laudos", "agendamentos"]

# As ESTAÇÕES (fachada) — o que o visitante lê.
_ESTACOES = {
    "prescritor.html": "Consultório",
    "dispensador.html": "Farmácia",
    "cidadao.html": "Carteira Cidadã",
    "clinica.html": "Clínica / Laboratório",
}


def _tok(u, r):
    resp = httpx.post(f"{u}/demo/login", json={"role": r}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _ctx_cidadao(browser, u, largura: int):
    ctx = browser.new_context(viewport={"width": largura, "height": 900})
    tok = _tok(u, "paciente")
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'paciente');
        sessionStorage.setItem('picsaude_demo_sub',   {_CPF!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME!r});
        """
    )
    return ctx


def _pagina(ctx):
    pg = ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(str(e)))
    return pg, erros


# ===========================================================================
# 1 — a fachada
# ===========================================================================

@pytest.mark.parametrize("tela,estacao", sorted(_ESTACOES.items()))
def test_o_portal_nomeia_a_estacao(browser, app_demo, tela, estacao):
    """Casado pelo SELETOR do título, nunca por substring do cartão.

    `to_contain_text` no `a.card` inteiro varreria também o parágrafo — e o do
    dispensador fala em "balcão da farmácia". Com o rótulo virando "Farmácia",
    bastaria alguém capitalizar essa palavra para a asserção passar com o
    título errado. Igualdade no `h3` fecha a porta antes de ela existir.
    """
    ctx = browser.new_context()
    try:
        pg, erros = _pagina(ctx)
        # Flip da abertura (30/08): o portal (cards de estação) mudou de
        # `index.html` para `entrar.html`.
        pg.goto(f"{app_demo}/entrar.html", wait_until="networkidle")
        card = pg.locator(f'a.card[href="{tela}"]')
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)
        expect(card.locator("h3")).to_have_text(estacao)
        assert not erros, erros
    finally:
        ctx.close()


@pytest.mark.parametrize("tela,estacao", sorted(_ESTACOES.items()))
def test_a_tela_se_anuncia_como_a_estacao(browser, app_demo, tela, estacao):
    """O selo da tela concorda com o cartão do portal. Discordar faria o
    visitante clicar em "Farmácia" e chegar num "Módulo Dispensador"."""
    esperado = "Laboratório" if tela == "clinica.html" else estacao
    ctx = browser.new_context()
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/{tela}", wait_until="networkidle")
        expect(pg.locator(".module-tag").first).to_have_text(esperado, timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_a_fachada_nao_tocou_no_DOMINIO(browser, app_demo):
    """A outra metade da regra, e a que importa mais.

    Renomear a porta não renomeia quem entra: o `/demo/login` continua
    devolvendo os PAPÉIS de sempre. Se um dia alguém "completar" o rename até o
    JWT, este teste cai — e é exatamente aí que ele tem de cair.
    """
    for papel_demo, papel_jwt in (("prescritor", "prescritor"),
                                  ("paciente", "paciente"),
                                  ("dispensador", "dispensador"),
                                  ("clinica", "dispensador")):
        r = httpx.post(f"{app_demo}/demo/login", json={"role": papel_demo}, timeout=10.0)
        assert r.status_code == 200, r.text
        assert r.json()["role"] == papel_jwt, (
            f"o papel de `{papel_demo}` virou '{r.json()['role']}' — a fachada "
            "vazou para o domínio"
        )


# ===========================================================================
# 2 — o wrap, em viewport FIXA
# ===========================================================================

@pytest.mark.parametrize("largura", [1280, 768])
def test_as_seis_pilulas_cabem_sem_cortar_texto(browser, app_demo, largura):
    """O risco real de seis itens numa barra que foi desenhada para quatro:
    texto truncado. `scrollWidth > clientWidth` é o sintoma exato disso."""
    ctx = _ctx_cidadao(browser, app_demo, largura)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-nav-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#submod-nav-carteira .submod-btn")).to_have_count(6)

        cortados = pg.evaluate("""() => [...document.querySelectorAll(
            '#submod-nav-carteira .submod-titulo')]
            .filter(t => t.scrollWidth > t.clientWidth + 1)
            .map(t => t.textContent.trim())""")
        assert not cortados, f"rótulos truncados em {largura}px: {cortados}"

        for chave in _SUBMODULOS:
            expect(pg.locator(f"#submod-btn-{chave}")).to_be_visible()
        assert not erros, erros
    finally:
        ctx.close()


@pytest.mark.parametrize("largura", [1280, 768])
def test_a_barra_nao_estoura_a_janela(browser, app_demo, largura):
    """Quebrar linha é crescer em ALTURA. Se crescer em largura, a página
    ganha rolagem horizontal — que é o defeito que o `flex-wrap` evita."""
    ctx = _ctx_cidadao(browser, app_demo, largura)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-nav-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
        largura_barra = pg.evaluate(
            "() => document.getElementById('submod-nav-carteira').scrollWidth")
        assert largura_barra <= largura, (
            f"a barra ({largura_barra}px) é mais larga que a janela ({largura}px)"
        )
        assert not pg.evaluate(
            "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
        ), "a página ganhou rolagem horizontal"
        assert not erros, erros
    finally:
        ctx.close()


def test_em_tela_estreita_vira_uma_coluna(browser, app_demo):
    """Abaixo de 520px, seis alvos de toque lado a lado seriam pequenos demais
    — a media query os empilha. Uma pílula por linha."""
    ctx = _ctx_cidadao(browser, app_demo, 390)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#submod-nav-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
        por_linha = pg.evaluate("""() => {
            const por = {};
            document.querySelectorAll('#submod-nav-carteira .submod-btn').forEach(b => {
                const t = Math.round(b.getBoundingClientRect().top);
                por[t] = (por[t] || 0) + 1;
            });
            return Object.values(por);
        }""")
        assert por_linha == [1] * 6, f"esperava uma por linha em 390px, vi {por_linha}"
        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# 3 — o "Atualizar" mudou de lugar, não de função
# ===========================================================================

def test_o_atualizar_vive_no_cabecalho_do_titular(browser, app_demo):
    """Ele recarrega a carteira INTEIRA; ao lado das pílulas parecia pertencer
    à pílula ativa. O id `#btn-refresh` fica — dois E2Es o referenciam."""
    ctx = _ctx_cidadao(browser, app_demo, 1280)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        botao = pg.locator("#btn-refresh")
        expect(botao).to_be_visible(timeout=_TIMEOUT_MS)

        assert pg.locator(".titular-card #btn-refresh").count() == 1, (
            "o Atualizar não está no cartão do Titular"
        )
        assert pg.locator("#submod-nav-carteira #btn-refresh").count() == 0, (
            "o Atualizar continua dentro da barra de navegação"
        )

        botao.click()
        expect(pg.locator("#refresh-text")).to_have_text("Atualizado!", timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()
