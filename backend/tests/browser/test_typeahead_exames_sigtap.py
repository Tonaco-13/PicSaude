"""
tests/browser/test_typeahead_exames_sigtap.py — TICKET-FILA-7-SIGTAP-EXAMES.md,
AC4: "Typeahead sugere e não bloqueia" (browser test: 'glicemia' → sugestão
com código; nome inédito é aceito sem atrito).

A "IA de exames" (`_consultarIaExame`/`_renderizarNormalizacaoExame`,
`prescritor.html`) já existia (Ticket 31) — este arquivo prova que, depois
do SIGTAP acoplado (fila 7), ela continua consultiva (nunca bloqueia) e
agora também sugere o código SIGTAP quando há um.
"""
from __future__ import annotations

import httpx
from playwright.sync_api import Page, expect

_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_TIMEOUT_MS = 15_000


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _autenticar_prescritor(page: Page, base_url: str) -> None:
    tok = _tok(base_url, "prescritor")
    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'prescritor');
        sessionStorage.setItem('picsaude_demo_sub',   {_CNS_PRESCRITOR!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME_PRESCRITOR!r});
        """
    )


def _abrir_aba_exames(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/prescritor.html", wait_until="networkidle")
    page.locator("#submod-btn-exames").click()
    expect(page.locator("#submod-exames")).to_be_visible(timeout=_TIMEOUT_MS)


def test_glicemia_sugere_com_codigo(page: Page, app_demo, erros_de_console):
    _autenticar_prescritor(page, app_demo)
    _abrir_aba_exames(page, app_demo)

    nome_el = page.locator("#exame-item-1 .exame-nome")
    expect(nome_el).to_be_visible(timeout=_TIMEOUT_MS)
    nome_el.fill("glicemia")

    chips = page.locator("#exame-item-1 .ia-exame-chip")
    expect(chips.first).to_be_visible(timeout=_TIMEOUT_MS)
    texto_chips = " ".join(chips.all_text_contents())
    assert "TUSS" in texto_chips, f"esperava chip de código; achou: {texto_chips!r}"

    # A sugestão é consultiva — só grava no card com o gesto explícito do
    # usuário ("Usar nome padronizado"), nunca automaticamente.
    page.locator("#exame-item-1 .ia-exame-btn-usar").click()
    tuss_hidden = page.locator("#exame-item-1 .exame-codigo-tuss")
    expect(tuss_hidden).to_have_value("40302019", timeout=_TIMEOUT_MS)

    assert not erros_de_console


def test_ecg_sugere_tuss_e_sigtap(page: Page, app_demo, erros_de_console):
    """ECG é o caso de fusão (curadoria + SIGTAP batem pelo nome) — prova
    que a fila 7 realmente acoplou o SIGTAP, não só manteve o TUSS."""
    _autenticar_prescritor(page, app_demo)
    _abrir_aba_exames(page, app_demo)

    nome_el = page.locator("#exame-item-1 .exame-nome")
    nome_el.fill("ECG")

    chips = page.locator("#exame-item-1 .ia-exame-chip")
    expect(chips.first).to_be_visible(timeout=_TIMEOUT_MS)
    texto_chips = " ".join(chips.all_text_contents())
    assert "SIGTAP" in texto_chips, f"esperava chip SIGTAP; achou: {texto_chips!r}"
    assert "TUSS" in texto_chips, f"esperava chip TUSS também (é fusão); achou: {texto_chips!r}"

    # "ECG" já é igual ao alias — nome padronizado ("Eletrocardiograma
    # (ECG)") é diferente do texto digitado, então o botão aparece.
    page.locator("#exame-item-1 .ia-exame-btn-usar").click()
    sigtap_hidden = page.locator("#exame-item-1 .exame-codigo-sigtap")
    expect(sigtap_hidden).not_to_have_value("", timeout=_TIMEOUT_MS)
    tuss_hidden = page.locator("#exame-item-1 .exame-codigo-tuss")
    expect(tuss_hidden).to_have_value("40311012", timeout=_TIMEOUT_MS)

    assert not erros_de_console


def test_nome_inedito_nao_bloqueia(page: Page, app_demo, erros_de_console):
    """Regra Zero: nome livre é 100% aceito, mesmo sem match nenhum na
    base — nunca vira erro, nunca limpa o campo, nunca desabilita nada."""
    _autenticar_prescritor(page, app_demo)
    _abrir_aba_exames(page, app_demo)

    nome_el = page.locator("#exame-item-1 .exame-nome")
    nome_livre = "Exame Muito Especifico Inventado XYZ987"
    nome_el.fill(nome_livre)

    # Debounce (500ms) + resposta da IA — dá tempo e confirma que nada quebrou.
    page.wait_for_timeout(1200)

    # O nome digitado permanece EXATAMENTE como o usuário escreveu — nunca
    # sobrescrito, nunca limpo, nenhuma validação bloqueante disparada.
    expect(nome_el).to_have_value(nome_livre)
    expect(nome_el).to_be_editable()

    # Sem match útil → o bloco de IA fica silenciosamente vazio (não é erro).
    container = page.locator("#exame-item-1 .ia-exame-container")
    expect(container).to_be_empty(timeout=_TIMEOUT_MS)

    assert not erros_de_console
