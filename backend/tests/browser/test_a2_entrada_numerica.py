"""
tests/browser/test_a2_entrada_numerica.py — FILA-VIVA A2 (ticket da Júlia, 26/08).

Sintoma: campos numéricos dos formulários — Idade, CPF, CEP — aceitavam
letras; o erro só aparecia no submit (422). Backend já era fail-closed
(normaliza e rejeita) — defeito de higiene de entrada, não de integridade.

Solução cirúrgica, só frontend (config.js): `aplicarMascaraCEP` (nova, espelha
`aplicarMascaraCPF` que já existia desde o commit inicial) + `aplicarRestricaoNumerica`
(nova, para campos sem separador — Idade). Zero mudança em API, estados, ledger.

Este arquivo prova, digitando letras num navegador real, que elas não entram —
em Idade e CEP, na aba Receita do prescritor (o formulário citado pela Júlia).
CPF fica de fora deste arquivo: os quatro campos de CPF de paciente
(receita/exame/encaminhamento/atestado) já são `readonly` desde o M-D
(`campo-paciente-travado-md-revoga-mb-mc` — ver memória do projeto), então
não há caminho de digitação a testar ali; `aplicarMascaraCPF` (que cobre o
login do cidadão, fora do escopo deste ticket) já existe desde o commit
inicial e não foi tocado aqui.
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"


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


def test_idade_bloqueia_letras(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

        campo = pg.locator("#pac-idade")
        campo.click()
        campo.press_sequentially("ab45cd")
        expect(campo).to_have_value("45", timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()


def test_cep_bloqueia_letras_e_aplica_mascara(browser, app_demo):
    ctx = _ctx_prescritor(browser, app_demo)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

        campo = pg.locator("#pac-cep")
        campo.click()
        campo.press_sequentially("a5b6c1d0e0f9g7o0")
        expect(campo).to_have_value("56100-970", timeout=_TIMEOUT_MS)

        assert not erros, erros
    finally:
        ctx.close()
