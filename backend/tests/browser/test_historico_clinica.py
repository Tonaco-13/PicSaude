"""Aba Histórico da clínica — ENG-014, PR B (E2E).

O que só aqui se prova: a aba EXISTE no percurso (5ª, ao lado das quatro do
J.8), carrega sozinha ao ser aberta e mostra o que a unidade concluiu — sem
depender de um pedido em foco, ao contrário das abas 2-4.

A persona é o LABORATÓRIO, que a fixture de integração não exercita
(fail-closed sem prestador semeado) — a mesma razão do J.7/J.11.
"""
from __future__ import annotations

import re
import time

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

_CNS = "980001112223334"
_CPF = "12345678909"
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


def _pedido_concluido(base_url: str, nome_exame: str) -> str:
    """Pedido entregue, coletado e com resultado — o que entra no histórico."""
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers=_h(_tok(base_url, "prescritor")),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": "Dra. Demo Maria Souza",
            "cpf_paciente": _CPF, "nome_paciente": "João Demo da Silva",
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
        }, timeout=15.0,
    )
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    assert httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(_tok(base_url, "paciente")),
        json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
        timeout=15.0,
    ).status_code == 201

    hl = _h(_tok(base_url, "clinica"))
    corpo = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=hl, timeout=15.0).json()
    item_id = corpo["itens"][0]["id"]
    assert httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                      headers=hl, json={}, timeout=15.0).status_code == 201
    rr = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/resultado",
                    headers=hl, json={"resultado_resumo": "98 mg/dL"}, timeout=15.0)
    assert rr.status_code in (200, 201), rr.text
    return proto


def test_aba_historico_existe_e_carrega(page: Page, browser, app_demo, erros_de_console):
    """A 5ª aba do percurso, e ela se carrega sozinha ao abrir."""
    nome = f"HIST-{_TS}"
    proto = _pedido_concluido(app_demo, nome)

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        expect(pl.locator("#aba-btn-historico")).to_be_visible(timeout=_TIMEOUT_MS)
        pl.locator("#aba-btn-historico").click()

        expect(pl.locator("#aba-btn-historico")).to_have_class(
            re.compile(r"\bativa\b"), timeout=_TIMEOUT_MS)
        expect(pl.locator("#historico-itens")).to_contain_text(nome, timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


def test_historico_nao_exige_pedido_em_foco(page: Page, browser, app_demo, erros_de_console):
    """Diferente das abas 2-4: o Histórico é da UNIDADE, não do pedido aberto.

    Sem esta distinção a aba mostraria "Nenhum pedido em foco" e o operador não
    teria como ver o que a unidade produziu.
    """
    nome = f"HIST-SEMFOCO-{_TS}"
    _pedido_concluido(app_demo, nome)

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pl.locator("#aba-btn-historico").click()

        # Nenhum pedido foi aberto — e mesmo assim há conteúdo.
        expect(pl.locator("#historico-itens")).to_contain_text(nome, timeout=_TIMEOUT_MS)
        expect(pl.locator("#pedido-foco")).to_have_class(
            re.compile(r"\bhidden\b"), timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


def test_historico_sobe_sem_selo_lido(page: Page, browser, app_demo, erros_de_console):
    """O selo "Lido em" é do PR C (depende de `laudos.aberto_em`).

    Guarda de ESCOPO: se ele aparecer aqui, ou o PR C vazou para dentro deste,
    ou alguém inventou a coluna na tela sem o campo existir no backend.
    """
    _pedido_concluido(app_demo, f"HIST-SEMSELO-{_TS}")

    ctx = _ctx_clinica(browser, app_demo)
    try:
        pl = ctx.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pl.locator("#aba-btn-historico").click()
        expect(pl.locator("#historico-itens")).not_to_contain_text("Lido em",
                                                                  timeout=_TIMEOUT_MS)
    finally:
        ctx.close()
