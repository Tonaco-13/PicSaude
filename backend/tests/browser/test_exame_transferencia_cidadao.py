"""
tests/browser/test_exame_transferencia_cidadao.py — E2E do pedido de exame
circulando pelo MESMO gesto da receita.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O pedido de exame passou a circular como a receita: o cidadão informa o CNPJ do
laboratório (já preenchido na demo) e clica em **Transferir Custódia**; o pedido
cai na **Fila de Exames** do laboratório (GAP-4/#148), como a receita cai na fila do
balcão.
Saíram da carteira do cidadão o agendamento (Ticket 29) e a chave de circulação
(Tickets 56/58) — ambos seguem existindo no backend e na tela do laboratório.

Três perguntas, três testes:
  1. o gesto funciona ponta a ponta (cidadão → laboratório)?
  2. o que foi retirado sumiu mesmo da carteira?
  3. depois de transferido, o card para de oferecer a transferência?

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_exame_transferencia_cidadao.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (config.js DEMO.* / seed_demo.py).
_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"

_TS = time.strftime("%Y%m%d%H%M")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _autenticar_paciente(page: Page, base_url: str) -> None:
    """Planta as 4 chaves `picsaude_demo_*` — o IIFE de cidadao.html hidrata."""
    tok = _tok(base_url, "paciente")
    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'paciente');
        sessionStorage.setItem('picsaude_demo_sub',   {_CPF!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME_PACIENTE!r});
        """
    )


def _emitir_pedido_para_paciente(base_url: str, nome_exame: str) -> str:
    """Pedido digital que JÁ chega em posse do cidadão (status `emitido`)."""
    ptok = _tok(base_url, "prescritor")
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers={"Authorization": f"Bearer {ptok}", "Content-Type": "application/json"},
        json={
            "cns_prescritor":  _CNS,
            "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente":    _CPF,
            "nome_paciente":   _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _card_do_pedido(page: Page, proto: str):
    # TICKET-J.9 — pedido de exame vive na aba Exames da carteira.
    abrir_aba_carteira(page, "exames")
    lista = page.locator("#lista-pedidos-exame")
    expect(lista).to_be_visible(timeout=_TIMEOUT_MS)
    expect(lista).to_contain_text(proto, timeout=_TIMEOUT_MS)
    return lista.locator(".exame-card", has_text=proto)


def _transferir_pelo_card(page: Page, card) -> None:
    botao = card.get_by_role("button", name="Transferir Custódia")
    expect(botao).to_be_visible(timeout=_TIMEOUT_MS)
    page.once("dialog", lambda d: d.accept())      # confirm() nativo do handler
    botao.click()


# ---------------------------------------------------------------------------
# 1 — o gesto ponta a ponta
# ---------------------------------------------------------------------------

def test_cidadao_transfere_exame_e_pedido_cai_na_fila_do_laboratorio(
    page: Page, browser, app_demo, erros_de_console
):
    proto = _emitir_pedido_para_paciente(app_demo, f"HEMOGRAMA-E2E-{_TS}")

    _autenticar_paciente(page, app_demo)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    card = _card_do_pedido(page, proto)
    # O CNPJ do laboratório da demo já vem preenchido — um clique, como na receita.
    expect(card.locator("input[id^='cnpj-lab-']")).to_have_value(_CNPJ_CLINICA)
    _transferir_pelo_card(page, card)

    modal = page.locator("#modal-transferencia")
    expect(modal).to_be_visible(timeout=_TIMEOUT_MS)
    expect(modal).to_contain_text("Pedido de exame transferido", timeout=_TIMEOUT_MS)
    # O pedido não vai para um "histórico" — segue na lista, com novo rótulo.
    expect(page.locator("#modal-transferencia-historico")).to_be_hidden()
    page.get_by_role("button", name="Fechar").click()

    # ── Lado do laboratório: o pedido chegou sozinho na fila ────────────────
    # Contexto novo: o init_script que hidrata o PACIENTE roda em toda navegação
    # desta aba, e clinica.html expulsa quem não é `dispensador`. O laboratório
    # entra pelo auto-login demo da própria tela, como na vitrine.
    ctx_lab = browser.new_context()
    try:
        # A persona `clinica` do /demo/login emite JWT com role `dispensador`
        # (papel único, ratificado em Q1=(a)) — é o que clinica.html hidrata.
        tok_lab = _tok(app_demo, "clinica")
        ctx_lab.add_init_script(
            f"""
            sessionStorage.setItem('picsaude_demo_token', {tok_lab!r});
            sessionStorage.setItem('picsaude_demo_role',  'dispensador');
            sessionStorage.setItem('picsaude_demo_sub',   {_CNPJ_CLINICA!r});
            sessionStorage.setItem('picsaude_demo_nome',  'Clínica Demo');
            """
        )
        page_lab = ctx_lab.new_page()
        page_lab.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        fila = page_lab.locator("#fila-lista")
        expect(fila).to_be_visible(timeout=_TIMEOUT_MS)
        expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
        expect(fila).to_contain_text(_NOME_PACIENTE, timeout=_TIMEOUT_MS)

        # Clicar na fila abre o pedido — sem digitar protocolo.
        fila.locator(".fila-item", has_text=proto).click()
        expect(page_lab.locator("#pedido-foco")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(page_lab.locator("#detalhes-pedido")).to_contain_text(proto, timeout=_TIMEOUT_MS)
    finally:
        ctx_lab.close()

    assert not erros_de_console, (
        "Erros de console no ciclo cidadão→laboratório:\n"
        + "\n".join(f"  - {e}" for e in erros_de_console)
    )


# ---------------------------------------------------------------------------
# 2 — o que foi retirado sumiu
# ---------------------------------------------------------------------------

def test_carteira_do_cidadao_nao_oferece_mais_agendamento_nem_chave(
    page: Page, app_demo, erros_de_console
):
    """Agendamento e chave de circulação saíram do módulo cidadão.

    Guarda de ausência: o valor da mudança está justamente em NÃO haver mais dois
    caminhos concorrentes para o cidadão mandar o exame ao laboratório.
    """
    proto = _emitir_pedido_para_paciente(app_demo, f"GLICEMIA-E2E-{_TS}")

    _autenticar_paciente(page, app_demo)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    card = _card_do_pedido(page, proto)
    texto = card.inner_text().lower()
    assert "agendar" not in texto, f"agendamento ainda aparece no card:\n{texto}"
    assert "chave" not in texto, f"chave de circulação ainda aparece no card:\n{texto}"
    assert "circulação" not in texto, f"circulação ainda aparece no card:\n{texto}"
    assert card.locator(".agendar-area").count() == 0
    assert card.locator(".circ-area").count() == 0


# ---------------------------------------------------------------------------
# 3 — depois de transferido, a posse é do laboratório
# ---------------------------------------------------------------------------

def test_card_transferido_mostra_no_laboratorio_e_nao_reoferece_transferencia(
    page: Page, app_demo, erros_de_console
):
    proto = _emitir_pedido_para_paciente(app_demo, f"TSH-E2E-{_TS}")

    _autenticar_paciente(page, app_demo)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    _transferir_pelo_card(page, _card_do_pedido(page, proto))
    expect(page.locator("#modal-transferencia")).to_be_visible(timeout=_TIMEOUT_MS)
    page.get_by_role("button", name="Fechar").click()   # fechar recarrega a carteira

    card = _card_do_pedido(page, proto)
    expect(card).to_contain_text("No laboratório", timeout=_TIMEOUT_MS)
    expect(card.get_by_role("button", name="Transferir Custódia")).to_have_count(0)
