"""Recepção da clínica age a partir do cartão da fila — ENG-014, PR A.

A PROPOSTA (Fabiano, 20/08)
---------------------------
O gesto da recepção é decidir o percurso do exame que acabou de chegar. Até
aqui isso exigia abrir o pedido, trocar de aba e só então agir. As três ações
passam a viver no CARTÃO:

  · sem compromisso vigente → "Agendar" (marca para depois) ou "Coletar
    agora" (coleta direta — o segundo caminho que o martelo do J.7 autoriza,
    para quem já está com o material na mão);
  · com compromisso vigente → também "Coletar agora" (MARTELO 27/08, PR 2 do
    desenho de circulação — rótulo unificado; era "Executar agendado"), que é
    o `POST /agendamentos/{p}/realizar` de sempre.

POR QUE UM SMOKE
----------------
A integração prova os endpoints; o que só aqui se prova é que o CAMINHO existe
na tela e que ele não colide com o cartão — que é, ele todo, um botão que abre
o pedido. Sem `stopPropagation`, agir dispararia a navegação junto e o operador
perderia a fila de vista no meio do gesto.

E a persona é o LABORATÓRIO, que a fixture de integração não consegue
exercitar (fail-closed sem prestador semeado) — a mesma razão que levou o J.7 e
o J.11 a cobrirem aqui.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_recepcao_clinica.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"

_TS = time.strftime("%Y%m%d%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx_clinica(browser, base_url: str):
    ctx = browser.new_context()
    tok = _tok(base_url, "clinica")
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'dispensador');
        sessionStorage.setItem('picsaude_demo_sub',   {_CNPJ_CLINICA!r});
        sessionStorage.setItem('picsaude_demo_nome',  'Clínica Demo');
        """
    )
    return ctx


def _emitir_e_entregar(base_url: str, nome_exame: str) -> str:
    """Pedido na mão do cidadão e entregue ao laboratório — o que cai na fila."""
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers=_h(_tok(base_url, "prescritor")),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    rt = httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(_tok(base_url, "paciente")),
        json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
        timeout=15.0,
    )
    assert rt.status_code == 201, rt.text
    return proto


def _pedido(base_url: str, proto: str) -> dict:
    r = httpx.get(f"{base_url}/pedidos-exame/{proto}",
                  headers=_h(_tok(base_url, "clinica")), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()


def _esperar_coletado(base_url: str, proto: str, tentativas: int = 30) -> None:
    """Aguarda o efeito no backend — a ação da tela é assíncrona por natureza."""
    for _ in range(tentativas):
        if _pedido(base_url, proto)["itens"][0]["status_item"] == "coletado":
            return
        time.sleep(0.5)
    raise AssertionError("a coleta não chegou ao backend dentro do prazo")


def _cartao(pl: Page, base_url: str, proto: str):
    pl.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    card = pl.locator(".fila-item", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    return card


# ===========================================================================
# 1 — executar agora (coleta direta, martelo J.7)
# ===========================================================================

def test_executar_agora_coleta_direto_do_cartao(page: Page, browser, app_demo, erros_de_console):
    """Um clique no cartão coleta, sem inventar agendamento retroativo."""
    proto = _emitir_e_entregar(app_demo, f"RECEP-AGORA-{_TS}")
    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "pendente"

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        card = _cartao(pl, app_demo, proto)
        pl.once("dialog", lambda d: d.accept())
        card.get_by_role("button", name="Coletar agora").click()
        # Espera no EFEITO, não na tela: depois da coleta a `clinica.html`
        # troca de aba sozinha (J.8 — o item migra para a Bancada), então
        # qualquer âncora de DOM aqui é sinal instável. O backend é o fato.
        _esperar_coletado(app_demo, proto)
    finally:
        ctx.close()

    corpo = _pedido(app_demo, proto)
    assert corpo["itens"][0]["status_item"] == "coletado"
    # `emitido → coletado` sem escala em `agendado`: a aresta do J.7.
    assert corpo["status"] == "coletado"
    assert "pedido_agendado" not in [e["tipo_evento"] for e in corpo.get("eventos", [])]


# ===========================================================================
# 2 — agendar a partir do cartão
# ===========================================================================

def test_agendar_leva_ao_formulario_da_aba(page: Page, browser, app_demo, erros_de_console):
    """"Agendar" abre o pedido na aba certa, com o formulário pronto.

    Não há um segundo formulário: dois divergiriam. O que o cartão encurta é o
    CAMINHO até o que já existe.
    """
    proto = _emitir_e_entregar(app_demo, f"RECEP-AGENDAR-{_TS}")

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        card = _cartao(pl, app_demo, proto)
        card.get_by_role("button", name="Agendar").click()

        expect(pl.locator("#form-agendar")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pl.locator("#ag-data-hora")).to_be_visible()
        # A aba de Agendamento é a ativa — o cartão levou o operador até lá.
        expect(pl.locator("#aba-btn-agendamento")).to_have_class(
            __import__("re").compile(r"\bativa\b"), timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


# ===========================================================================
# 3 — executar agendado
# ===========================================================================

def test_executar_agendado_aparece_e_realiza(page: Page, browser, app_demo, erros_de_console):
    """Com compromisso vigente o cartão troca de oferta — e realiza.

    Sem janela de horário: "a qualquer hora" já é o comportamento do endpoint.
    """
    proto = _emitir_e_entregar(app_demo, f"RECEP-AGENDADO-{_TS}")

    r = httpx.post(
        f"{app_demo}/agendamentos",
        headers=_h(_tok(app_demo, "clinica")),
        json={"pedido_protocolo": proto, "org_id": "clinica-demo",
              "unidade_id": "DEMO-LAB", "data_hora": "2026-09-01T08:00:00"},
        timeout=15.0,
    )
    assert r.status_code in (200, 201), r.text

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        card = _cartao(pl, app_demo, proto)
        # MARTELO 27/08 (PR 2) — "Executar agora" e "Executar agendado" viraram
        # o mesmo rótulo, "Coletar agora": o ledger só conhece `pedido_coletado`,
        # um fato. A prova de que é o RAMO CERTO (compromisso vigente) deixa de
        # ser textual e vira estrutural + comportamental: "Agendar" desaparece
        # (não se reagenda por aqui) e o clique dispara o endpoint de
        # agendamento — só ele emite o feedback "realizado" abaixo.
        expect(card.get_by_role("button", name="Agendar")).to_have_count(0)
        expect(card.get_by_role("button", name="Coletar agora")).to_be_visible(
            timeout=_TIMEOUT_MS)

        pl.once("dialog", lambda d: d.accept())
        card.get_by_role("button", name="Coletar agora").click()
        expect(pl.locator("#feedback-agendamento")).to_contain_text(
            "realizado", timeout=_TIMEOUT_MS)
    finally:
        ctx.close()

    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "coletado"


def test_agir_no_cartao_nao_navega_junto(page: Page, browser, app_demo, erros_de_console):
    """O cartão inteiro é um botão que abre o pedido.

    Sem `stopPropagation` nas ações, agir dispararia a navegação junto e o
    operador perderia a fila de vista no meio do gesto. A fila continua na tela.
    """
    proto = _emitir_e_entregar(app_demo, f"RECEP-PROPAG-{_TS}")

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        card = _cartao(pl, app_demo, proto)
        pl.once("dialog", lambda d: d.dismiss())      # recusa a confirmação
        card.get_by_role("button", name="Coletar agora").click()

        # Recusou a ação: nada aconteceu E a Recepção continua sendo a aba ativa.
        expect(pl.locator("#aba-btn-recepcao")).to_have_class(
            __import__("re").compile(r"\bativa\b"), timeout=_TIMEOUT_MS)
        expect(pl.locator("#fila-lista")).to_be_visible()
    finally:
        ctx.close()

    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "pendente"
