"""
tests/browser/test_j7_transferir_e_posse.py — TICKET-J.7 (`core`).

A REGRA QUE ESTE ARQUIVO GUARDA
-------------------------------
Martelo do Fabiano em 15/08 (DESPACHO-ENG-011 §11a), verbatim:

  > transferir ao laboratório é um ato de posse (custódia), não de agenda;
  > itens continuam `pendente`; quem promove a `agendado` é o laboratório,
  > criando agendamento com data/hora/unidade — ou realizando direto.

POR QUE UM SMOKE, SE A INTEGRAÇÃO JÁ COBRE
-------------------------------------------
`tests/integration/test_transferencia_exame_cidadao.py` prova a regra no
backend. O que ela NÃO consegue provar é o que este ticket mais arrisca: as
duas telas liam POSSE do STATUS, e o status parou de responder essa pergunta.

  · a carteira do cidadão oferecia "Transferir Custódia" para `status ==
    'emitido'` — que agora é o estado de um pedido JÁ entregue;
  · a tela do laboratório só desenhava "Registrar coleta" para `agendado` — e o
    item agora chega `pendente`;
  · a fila esconde pedido sem item acionável, e `pendente` não era acionável.

Cada um desses seria verde no backend e quebrado na vitrine. É a fresta entre o
que o backend faz e o que a tela afirma — a mesma lição do #152.

Há ainda um papel que só aqui se exercita: **o laboratório criando o
agendamento**. Na integração, `POST /agendamentos` como `dispensador` é 403 por
falta de `prestadores.cnpj → org_id` na fixture (fail-closed do §D1); no seed
da demo a Clínica Demo é prestador de verdade, então a persona funciona.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_j7_transferir_e_posse.py -v
"""
from __future__ import annotations

import re
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

_TS = time.strftime("%Y%m%d%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx(browser, base_url: str, role: str, sub: str, nome: str):
    ctx = browser.new_context()
    tok = _tok(base_url, role)
    papel = "paciente" if role == "paciente" else "dispensador"
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {papel!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _emitir_ao_paciente(base_url: str, nome_exame: str) -> str:
    """Emite JÁ na carteira do cidadão — o caminho da vitrine.

    `enviar_ao_paciente` grava a custódia inicial com `para='paciente'` (o
    PAPEL, não o CPF). É a forma que o guard de posse precisa entender.
    """
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
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _pedido(base_url: str, proto: str) -> dict:
    r = httpx.get(f"{base_url}/pedidos-exame/{proto}",
                  headers=_h(_tok(base_url, "clinica")), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()


def _eventos(base_url: str, proto: str) -> list[str]:
    return [e["tipo_evento"] for e in _pedido(base_url, proto).get("eventos", [])]


def _transferir_pela_tela(pc: Page, base_url: str, proto: str) -> None:
    pc.goto(f"{base_url}/cidadao.html", wait_until="networkidle")
    abrir_aba_carteira(pc, "exames")
    card = pc.locator("#lista-pedidos-exame .exame-card", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    pc.once("dialog", lambda d: d.accept())
    card.get_by_role("button", name="Transferir Custódia").click()
    expect(pc.locator("#modal-transferencia")).to_contain_text(
        "transferido", timeout=_TIMEOUT_MS)


# ===========================================================================
# 1 — o ato: posse muda, estado não
# ===========================================================================

def test_transferir_move_a_posse_e_nao_o_estado(
    page: Page, browser, app_demo, erros_de_console
):
    """AC §4.3(i) — pela TELA, e conferido no backend e no ledger."""
    proto = _emitir_ao_paciente(app_demo, f"J7-POSSE-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        _transferir_pela_tela(ctx.new_page(), app_demo, proto)
    finally:
        ctx.close()

    corpo = _pedido(app_demo, proto)
    assert corpo["status"] == "emitido", "transferir não é agendar"
    assert [i["status_item"] for i in corpo["itens"]] == ["pendente"]

    eventos = _eventos(app_demo, proto)
    assert "custodia_transferida" in eventos, eventos
    assert "pedido_agendado" not in eventos, (
        f"transferir voltou a anunciar agendamento inexistente: {eventos}"
    )


# ===========================================================================
# 2 — a carteira do cidadão sabe que a posse saiu (posse ≠ status)
# ===========================================================================

def test_carteira_para_de_oferecer_transferencia_apos_entregar(
    page: Page, browser, app_demo, erros_de_console
):
    """O cartão lia `status === 'emitido'` para dizer "está comigo".

    Depois do J.7 o pedido entregue continua `emitido`. Sem
    `sob_minha_custodia` (derivado da custódia no backend), o cartão
    reofereceria "Transferir Custódia" de algo que já está no laboratório — e a
    etiqueta diria "Com você" logo acima de "Custódia transferida".
    """
    proto = _emitir_ao_paciente(app_demo, f"J7-CARTEIRA-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx.new_page()
        _transferir_pela_tela(pc, app_demo, proto)

        pc.reload(wait_until="networkidle")
        abrir_aba_carteira(pc, "exames")
        card = pc.locator("#lista-pedidos-exame .exame-card", has_text=proto)
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)

        expect(card).to_contain_text("Custódia transferida", timeout=_TIMEOUT_MS)
        expect(card).to_contain_text("No laboratório")
        expect(card).not_to_contain_text("Com você")
        expect(card.get_by_role("button", name="Transferir Custódia")).to_have_count(0)
    finally:
        ctx.close()

    # A tela não mentiu por conta própria: o estado segue `emitido`.
    assert _pedido(app_demo, proto)["status"] == "emitido"


# ===========================================================================
# 3 — a fila do laboratório recebe o item `pendente` e ACIONÁVEL
# ===========================================================================

def test_laboratorio_recebe_item_pendente_e_pode_coletar(
    page: Page, browser, app_demo, erros_de_console
):
    """A fila esconde pedido sem item acionável.

    Se `pendente` não fosse acionável, o exame recém-entregue sumiria da tela do
    laboratório — a demo mostraria "o exame desapareceu".
    """
    proto = _emitir_ao_paciente(app_demo, f"J7-FILA-{_TS}")

    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        _transferir_pela_tela(ctx_cid.new_page(), app_demo, proto)
    finally:
        ctx_cid.close()

    item_id = _pedido(app_demo, proto)["itens"][0]["id"]

    ctx_lab = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl = ctx_lab.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        fila = pl.locator("#fila-lista")
        expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
        fila.locator(".fila-item", has_text=proto).click()

        # TICKET-J.8 — o pedido sem coleta feita abre na aba Realização, e o
        # item `pendente` cai lá por percurso (não por nome de estado).
        expect(pl.locator("#aba-btn-realizacao")).to_have_class(
            re.compile(r"\bativa\b"), timeout=_TIMEOUT_MS)

        item = pl.locator(f"#item-exame-{item_id}")
        expect(item).to_be_visible(timeout=_TIMEOUT_MS)
        expect(item).to_contain_text("Pendente")
        expect(item.get_by_role("button", name="Registrar coleta")).to_be_visible()
    finally:
        ctx_lab.close()


# ===========================================================================
# 4 — os DOIS caminhos que o martelo autoriza
# ===========================================================================

def test_coleta_direta_sem_agendamento(page: Page, browser, app_demo, erros_de_console):
    """"…ou realizando direto" — `pendente → coletado`, sem agendamento."""
    proto = _emitir_ao_paciente(app_demo, f"J7-DIRETO-{_TS}")

    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        _transferir_pela_tela(ctx_cid.new_page(), app_demo, proto)
    finally:
        ctx_cid.close()

    item_id = _pedido(app_demo, proto)["itens"][0]["id"]

    ctx_lab = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl = ctx_lab.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pl.locator("#fila-lista .fila-item", has_text=proto).click()

        item = pl.locator(f"#item-exame-{item_id}")
        expect(item).to_be_visible(timeout=_TIMEOUT_MS)
        item.get_by_role("button", name="Registrar coleta").click()
        expect(item).to_contain_text("Coletado", timeout=_TIMEOUT_MS)
    finally:
        ctx_lab.close()

    corpo = _pedido(app_demo, proto)
    assert corpo["itens"][0]["status_item"] == "coletado"
    # `emitido → coletado` sem escala em `agendado`: a aresta nova do pedido.
    assert corpo["status"] == "coletado"
    assert "pedido_agendado" not in _eventos(app_demo, proto)


def test_laboratorio_agenda_e_so_entao_o_item_fica_agendado(
    page: Page, browser, app_demo, erros_de_console
):
    """AC §4.3(iii) — `agendado` volta a significar o que o nome diz.

    A persona é o LABORATÓRIO (`POST /agendamentos` como `dispensador`), que só
    passa no ownership porque a Clínica Demo é prestador semeado com `org_id` —
    condição que a fixture de integração não tem.
    """
    proto = _emitir_ao_paciente(app_demo, f"J7-AGENDA-{_TS}")

    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        _transferir_pela_tela(ctx_cid.new_page(), app_demo, proto)
    finally:
        ctx_cid.close()

    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "pendente"

    ltok = _tok(app_demo, "clinica")
    r = httpx.post(
        f"{app_demo}/agendamentos",
        headers=_h(ltok),
        json={
            "pedido_protocolo": proto,
            "org_id":     "clinica-demo",
            "unidade_id": "DEMO-LAB",
            "data_hora":  "2026-09-01T08:00:00",
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"laboratório não conseguiu agendar: {r.text}"

    corpo = _pedido(app_demo, proto)
    assert corpo["itens"][0]["status_item"] == "agendado"
    assert corpo["status"] == "agendado"
