"""AC (vii) do desenho — cidadão abre o laudo → clínica vê "Lido em".

É o ciclo que fecha a proposta do Fabiano: a unidade precisa SABER que o laudo
foi lido, e não há infra de push (nem haverá antes do G4A). A confirmação
rastreada vive na LEITURA — o Histórico mostra o selo no polling que já roda.

Só aqui se prova o ciclo entre as DUAS telas: a integração cobre cada lado, mas
não que a leitura de um chega ao outro.
"""
from __future__ import annotations

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


def _laudo_liberado(base_url: str, nome_exame: str) -> str:
    r = httpx.post(
        f"{base_url}/pedidos-exame", headers=_h(_tok(base_url, "prescritor")),
        json={"cns_prescritor": _CNS, "nome_prescritor": "Dra. Demo Maria Souza",
              "cpf_paciente": _CPF, "nome_paciente": "João Demo da Silva",
              "enviar_ao_paciente": True,
              "itens": [{"nome_exame": nome_exame, "quantidade": 1}]}, timeout=15.0)
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    assert httpx.post(f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
                      headers=_h(_tok(base_url, "paciente")),
                      json={"cnpj_laboratorio": _CNPJ_CLINICA,
                            "nome_laboratorio": "Clínica Demo"}, timeout=15.0).status_code == 201

    hl = _h(_tok(base_url, "clinica"))
    item_id = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=hl,
                        timeout=15.0).json()["itens"][0]["id"]
    assert httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                      headers=hl, json={}, timeout=15.0).status_code == 201
    assert httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/resultado",
                      headers=hl, json={"resultado_resumo": "98 mg/dL"},
                      timeout=15.0).status_code in (200, 201)

    # ENG-014 (v2, §2.1): laudo de dispensador exige o elo em todos os itens.
    rl = httpx.post(f"{base_url}/laudos", headers=hl, json={
        "cns_autor": _CNS, "nome_autor": "Dra. Demo Maria Souza",
        "cpf_paciente": _CPF, "nome_paciente": "João Demo da Silva",
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": nome_exame, "conclusao": "normal",
                   "pedido_item_id": item_id}]}, timeout=15.0)
    assert rl.status_code == 201, rl.text
    lp = rl.json()["protocolo"]
    assert httpx.post(f"{base_url}/laudos/{lp}/assinar", headers=hl, timeout=15.0).status_code == 200
    assert httpx.post(f"{base_url}/laudos/{lp}/liberar", headers=hl, json={},
                      timeout=15.0).status_code == 200
    return lp


def _laudo(base_url: str, lp: str) -> dict:
    r = httpx.get(f"{base_url}/laudos/{lp}", headers=_h(_tok(base_url, "prescritor")), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()


def test_cidadao_abre_e_clinica_ve_lido_em(page: Page, browser, app_demo, erros_de_console):
    """O ciclo do AC (vii), ponta a ponta."""
    nome = f"ABERT-{_TS}"
    lp = _laudo_liberado(app_demo, nome)
    assert _laudo(app_demo, lp)["status"] == "liberado"

    # ── a clínica, ANTES: laudo liberado e sem selo ──────────────────────
    ctx_lab = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl = ctx_lab.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pl.locator("#aba-btn-historico").click()
        linha = pl.locator("#historico-laudos .hist-linha", has_text=lp)
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha).not_to_contain_text("Lido em")
    finally:
        ctx_lab.close()

    # ── o cidadão abre ───────────────────────────────────────────────────
    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, "João Demo da Silva")
    try:
        pc = ctx_cid.new_page()
        pc.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        from tests.browser.conftest import abrir_aba_carteira
        abrir_aba_carteira(pc, "exames")
        cartao = pc.locator("#lista-laudos .exame-card", has_text=lp)
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        # Não há botão de ciência: abrir É dar ciência (martelo (a)).
        expect(cartao.get_by_role("button", name="Dar ciência")).to_have_count(0)
        cartao.get_by_role("button", name="Abrir laudo").click()
        pc.wait_for_timeout(1500)
    finally:
        ctx_cid.close()

    # A ciência foi DERIVADA da abertura — sem clique morto.
    corpo = _laudo(app_demo, lp)
    assert corpo["status"] == "ciencia_paciente"
    evs = [e["tipo_evento"] for e in corpo.get("eventos", [])]
    assert "laudo_aberto_paciente" in evs
    assert "ciencia_paciente" in evs

    # ── a clínica, DEPOIS: o selo apareceu ───────────────────────────────
    ctx_lab2 = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl2 = ctx_lab2.new_page()
        pl2.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pl2.locator("#aba-btn-historico").click()
        linha = pl2.locator("#historico-laudos .hist-linha", has_text=lp)
        expect(linha).to_contain_text("Lido em", timeout=_TIMEOUT_MS)
    finally:
        ctx_lab2.close()
