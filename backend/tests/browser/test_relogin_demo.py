"""
tests/browser/test_relogin_demo.py — TICKET-J.3: login invisível na demo.

O QUE ESTE ARQUIVO GUARDA
-------------------------
`JWT_ACCESS_TTL_MINUTES = 15`. Passados 15 minutos de visita, o próximo request
levava 401 e os módulos mostravam "Sessão expirada" + tela de acesso. O auto-login
demo existia, mas só no CARREGAMENTO da página — não socorria sessão que expira
no meio do uso. Era o que fazia a vitrine "cair para o login" (relato do Fabiano).

Agora um interceptador único (`config.js::instalarReloginDemo`) renova a sessão e
**reemite o request**. O visitante não vê nada.

COMO A EXPIRAÇÃO É SIMULADA
---------------------------
Adulterando o token no `sessionStorage` — o backend devolve 401 de assinatura
inválida, que é indistinguível de expirado do ponto de vista da tela. Esperar 15
minutos reais no gate seria absurdo, e mexer no TTL do backend mudaria o objeto
sob teste.

O QUE NÃO É TESTADO AQUI
------------------------
Que o JWT/RBAC continuam de pé — isso é `core` e tem suíte própria. O J.3 é
frontend: nenhuma linha de `auth/` foi tocada.
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 20_000

_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"

# JWT sintaticamente válido, assinatura lixo → 401 no backend.
_TOKEN_PODRE = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwOSIsInJvbGUiOiJwYWNpZW50ZSIsImV4cCI6MTB9"
    ".assinatura-invalida-de-proposito"
)


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _ctx(browser, base_url: str, role: str, papel: str, sub: str, nome: str):
    ctx = browser.new_context()
    tok = _tok(base_url, role)
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {papel!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _apodrecer_token(pg: Page) -> None:
    """Troca o token em memória E no sessionStorage pelo token inválido."""
    pg.evaluate(
        """(podre) => {
            sessionStorage.setItem('picsaude_demo_token', podre);
            if (typeof jwtAccessToken !== 'undefined') { jwtAccessToken = podre; }
            if (typeof sessaoAtual !== 'undefined' && sessaoAtual) { sessaoAtual.token = podre; }
        }""",
        _TOKEN_PODRE,
    )


# ---------------------------------------------------------------------------
# O interceptador está instalado nos 4 módulos
# ---------------------------------------------------------------------------

def test_interceptador_instalado_nos_quatro_modulos(page: Page, browser, app_demo, erros_de_console):
    """Sem isto, os outros testes poderiam passar por acaso — e o módulo que
    faltasse só apareceria na apresentação."""
    modulos = [
        ("cidadao.html",     "paciente",    "paciente",    _CPF,           _NOME_PACIENTE),
        ("clinica.html",     "clinica",     "dispensador", _CNPJ_CLINICA,  "Clínica Demo"),
        ("prescritor.html",  "prescritor",  "prescritor",  "980001112223334", "Dra. Demo"),
        ("dispensador.html", "dispensador", "dispensador", "99999999000191",  "Farmácia Demo"),
    ]
    for arquivo, role, papel, sub, nome in modulos:
        ctx = _ctx(browser, app_demo, role, papel, sub, nome)
        try:
            pg = ctx.new_page()
            pg.goto(f"{app_demo}/{arquivo}", wait_until="networkidle")
            instalado = pg.evaluate("() => window.__picsaudeReloginInstalado === true")
            assert instalado, f"{arquivo}: interceptador de re-login não foi instalado"
        finally:
            ctx.close()


# ---------------------------------------------------------------------------
# A recuperação, ponta a ponta
# ---------------------------------------------------------------------------

def test_cidadao_recupera_sozinho_apos_token_expirar(page: Page, browser, app_demo, erros_de_console):
    """AC — carteira do cidadão com token inválido: recarrega sozinha, sem tela
    de acesso e sem "sessão expirada"."""
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)

        _apodrecer_token(pg)

        # Qualquer request autenticado serve de gatilho: o interceptador renova
        # e reemite. O resultado observável é a carteira continuar de pé.
        pg.evaluate("() => carregarCarteira()")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#tela-acesso")).to_be_hidden(timeout=_TIMEOUT_MS)

        # E o token guardado já é OUTRO — a sessão renasceu de fato.
        assert pg.evaluate(
            "(podre) => sessionStorage.getItem('picsaude_demo_token') !== podre", _TOKEN_PODRE
        ), "o token não foi renovado — o interceptador não agiu"
    finally:
        ctx.close()


def test_clinica_recupera_sozinha_apos_token_expirar(page: Page, browser, app_demo, erros_de_console):
    """Mesmo AC no módulo com mais superfície autenticada (29 fetches)."""
    ctx = _ctx(browser, app_demo, "clinica", "dispensador", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        expect(pg.locator("#fila-lista")).to_be_visible(timeout=_TIMEOUT_MS)

        _apodrecer_token(pg)
        pg.evaluate("() => carregarFilaExames()")

        # A fila volta a renderizar (não caiu para a tela de login).
        expect(pg.locator("#fila-lista")).to_be_visible(timeout=_TIMEOUT_MS)
        assert pg.evaluate(
            "(podre) => sessionStorage.getItem('picsaude_demo_token') !== podre", _TOKEN_PODRE
        ), "o token não foi renovado no clinica.html"
    finally:
        ctx.close()


def test_sair_na_demo_nao_mostra_tela_de_acesso(page: Page, browser, app_demo, erros_de_console):
    """AC — em demo não existe "ficar deslogado": `sair()` reentra. A tela de
    acesso é o atrito que o ticket removeu."""
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)

        pg.evaluate("() => sair()")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#tela-acesso")).to_be_hidden(timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


def test_uma_tentativa_apenas_quando_a_renovacao_nao_resolve(
    page: Page, browser, app_demo, erros_de_console
):
    """A rede de segurança não pode virar armadilha: se o retry também falha, o
    interceptador desiste e devolve o 401 — nada de laço infinito de /demo/login.
    """
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

        # Faz o /demo/login falhar: o interceptador não tem como renovar.
        pg.route("**/demo/login", lambda rota: rota.fulfill(status=500, body="{}"))
        _apodrecer_token(pg)

        status = pg.evaluate(
            """async () => {
                const r = await fetch('/paciente/prescricoes', {
                    headers: { Authorization: 'Bearer ' + sessionStorage.getItem('picsaude_demo_token') },
                });
                return r.status;
            }"""
        )
        assert status == 401, f"esperava 401 devolvido sem laço; veio {status}"
    finally:
        ctx.close()
