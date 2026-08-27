"""ENG-019 PR 6 — fato clínico não se digita em diálogo nativo.

CONSULTA-UX-001/NC-7: o resumo do resultado era capturado num `prompt()` que só
barrava o cancelar. String vazia passava, e o item avançava para
`resultado_disponivel` com um resultado clínico SEM CONTEÚDO — no ledger, que é
imutável por trigger (§2): o que entra em branco não se corrige nunca.

POR QUE SÓ UM NAVEGADOR PROVA ISTO
----------------------------------
O Playwright DESCARTA diálogos nativos por padrão. Com `prompt()`, este teste
sequer conseguiria digitar — o gesto era, literalmente, inautomatizável e
inobservável. Trocar por markup próprio é o que torna o fato clínico verificável
de fora, e não só mais bonito.

A guarda de contrato (backend recusando `""`) vive em
tests/integration/test_resultado_resumo_vazio.py. Aqui se prova a outra metade:
o operador descobre ANTES de mandar, com o motivo à vista, e o item não anda.
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

from tests.browser.test_e2_laudo_apos_resultado_e2e import _pedido_e2
from tests.browser.test_laudo_clinica_cidadao import (
    _TIMEOUT_MS,
    _ctx_laboratorio,
    _h,
    _tok,
)

_TS_PR6 = "pr6modal"


def _status_do_item(base_url: str, proto: str) -> str:
    tok = _tok(base_url, "clinica")
    r = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(tok), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()["itens"][0]["status_item"]


def _pedido_coletado(base_url: str, nome_exame: str) -> tuple[str, int]:
    """Reusa o preparo do E2 e desfaz o último passo: aqui o item precisa estar
    COLETADO, aguardando o resultado que o operador vai digitar na tela."""
    proto, item_id = _pedido_e2(base_url, nome_exame)
    return proto, item_id


def test_resultado_vazio_nao_avanca_o_item(page: Page, browser, app_demo, erros_de_console):
    """O AC do PR 6: vazio não passa, e o operador sabe por quê."""
    nome_exame = f"GLICEMIA-{_TS_PR6}"

    # Pedido COLETADO (sem resultado ainda) — o estado em que o gesto existe.
    ptok = _tok(app_demo, "prescritor")
    from tests.browser.test_laudo_clinica_cidadao import (
        _CNPJ_CLINICA, _CNS, _CPF, _NOME_PACIENTE, _NOME_PRESCRITOR,
    )
    r = httpx.post(f"{app_demo}/pedidos-exame", headers=_h(ptok), json={
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "enviar_ao_paciente": True,
        "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
    }, timeout=15.0)
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    pactok = _tok(app_demo, "paciente")
    assert httpx.post(f"{app_demo}/pedidos-exame/{proto}/transferir-laboratorio",
                      headers=_h(pactok), json={"cnpj_laboratorio": _CNPJ_CLINICA},
                      timeout=15.0).status_code in (200, 201)

    ltok = _tok(app_demo, "clinica")
    item_id = httpx.get(f"{app_demo}/pedidos-exame/{proto}", headers=_h(ltok),
                        timeout=15.0).json()["itens"][0]["id"]
    assert httpx.post(f"{app_demo}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                      headers=_h(ltok), json={}, timeout=15.0).status_code in (200, 201)

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        from tests.browser.test_laudo_clinica_cidadao import _abrir_pedido_por_busca
        _abrir_pedido_por_busca(pg, app_demo, proto)

        pg.locator(f"#btn-resultado-{item_id}").click()

        modal = pg.locator("#modal-fato")
        expect(modal).to_be_visible(timeout=_TIMEOUT_MS)

        # Vazio: o modal recusa, explica, e NADA é enviado.
        pg.locator("#modal-fato-input").fill("   ")
        pg.locator("#modal-fato-ok").click()
        expect(pg.locator("#modal-fato-erro")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(modal).to_be_visible()
        assert _status_do_item(app_demo, proto) == "coletado", (
            "o item avançou com resultado vazio — é o defeito da NC-7 de volta")

        # Com conteúdo: passa, e o modal se fecha.
        pg.locator("#modal-fato-input").fill("Glicemia 92 mg/dL")
        pg.locator("#modal-fato-ok").click()
        expect(modal).to_be_hidden(timeout=_TIMEOUT_MS)
    finally:
        ctx.close()

    assert _status_do_item(app_demo, proto) == "resultado_disponivel"


def test_desistir_do_modal_de_devolucao_nao_move_a_posse(
    page: Page, browser, app_demo, erros_de_console
):
    """Cancelar tem de ser inócuo — é o que o `prompt()` fazia certo, e a troca
    não pode perder. O gesto vive na Recepção, com o item ainda `pendente`."""
    from tests.browser.test_laudo_clinica_cidadao import (
        _CNPJ_CLINICA, _CNS, _CPF, _NOME_PACIENTE, _NOME_PRESCRITOR,
        _abrir_pedido_por_busca,
    )
    nome_exame = f"TSH-{_TS_PR6}"

    ptok = _tok(app_demo, "prescritor")
    r = httpx.post(f"{app_demo}/pedidos-exame", headers=_h(ptok), json={
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "enviar_ao_paciente": True,
        "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
    }, timeout=15.0)
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    pactok = _tok(app_demo, "paciente")
    assert httpx.post(f"{app_demo}/pedidos-exame/{proto}/transferir-laboratorio",
                      headers=_h(pactok), json={"cnpj_laboratorio": _CNPJ_CLINICA},
                      timeout=15.0).status_code in (200, 201)

    ltok = _tok(app_demo, "clinica")
    item_id = httpx.get(f"{app_demo}/pedidos-exame/{proto}", headers=_h(ltok),
                        timeout=15.0).json()["itens"][0]["id"]
    assert _status_do_item(app_demo, proto) == "pendente"

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido_por_busca(pg, app_demo, proto)

        # O gesto vive na Recepção — "o que chegou, o que eu decido". Abrir a
        # aba faz parte do percurso do operador.
        pg.locator("#aba-btn-recepcao").click()

        # Casar por ATRIBUTO, não por texto: o rótulo deste botão é justamente
        # o que o PR 3 vai mexer, e um E2E não deve quebrar por renomeação.
        pg.locator(f'[data-devolver="{item_id}"]').first.click()
        expect(pg.locator("#modal-fato")).to_be_visible(timeout=_TIMEOUT_MS)
        pg.locator(".btn-fato-cancelar").click()
        expect(pg.locator("#modal-fato")).to_be_hidden(timeout=_TIMEOUT_MS)
    finally:
        ctx.close()

    assert _status_do_item(app_demo, proto) == "pendente", (
        "cancelar o modal mexeu na posse — desistir tem de ser inócuo")
