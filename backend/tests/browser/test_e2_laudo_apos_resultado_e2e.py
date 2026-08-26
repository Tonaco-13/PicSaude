"""ENG-019 PR 1 (opção a) — o percurso E2 termina COM laudo, e só um.

CONSULTA-UX-001/NC-5: no walk-in de leitura imediata (coletar e ler na hora) o
gatilho "🔬 Produzir laudo" nunca aparecia, e o pedido encerrava sem artefato —
sem selo "Lido em" e sem âncora de faturamento.

Por que só um navegador prova isto: a causa era um FILTRO DE TELA. O backend
sempre aceitou (guarda em tests/integration/test_e2_laudo_apos_resultado.py); o
que faltava era o botão existir. Um teste de API passaria verde com o defeito no
ar — foi exatamente o que aconteceu por toda a vida do ENG-014.

DUAS AFIRMAÇÕES:
  1. AC (i)  — o pedido E2 chega a laudo liberado, e o laudo cai na carteira.
  2. AC (iv) — feito o laudo, o gatilho SOME. É o que substitui o efeito
     colateral de que a tela vivia: antes o botão sumia porque laudar tirava o
     item de `em_analise`; agora quem o cala é `laudado`, campo do backend. Sem
     esta metade, alargar o filtro criaria a duplicação que o TICKET-I.1 fechou.

Os helpers vêm de test_laudo_clinica_cidadao.py — mesma casa, mesmas identidades.
Só o preparo do pedido é novo, porque é justamente ele que muda: coleta e
resultado SEM passar por "enviar à bancada".
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect, Page

from tests.browser.test_laudo_clinica_cidadao import (
    _CNPJ_CLINICA,
    _CNS,
    _CPF,
    _NOME_PACIENTE,
    _NOME_PRESCRITOR,
    _TIMEOUT_MS,
    _abrir_pedido_por_busca,
    _ctx_laboratorio,
    _h,
    _laudos_do_cidadao,
    _preencher_e_liberar,
    _tok,
)

_TS_E2 = "e2laudo"


def _pedido_e2(base_url: str, nome_exame: str) -> tuple[str, int]:
    """Walk-in de leitura imediata: emitido → laboratório → COLETADO → RESULTADO.

    O que distingue do preparo do TICKET-G: nenhuma chamada a `em-analise`. O
    `/resultado` colapsa `coletado → em_analise → resultado_disponivel` e emite
    os dois eventos — o item passa pela análise sem REPOUSAR nela, e é o repouso
    que a tela media.
    """
    ptok = _tok(base_url, "prescritor")
    r = httpx.post(
        f"{base_url}/pedidos-exame", headers=_h(ptok),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": nome_exame, "quantidade": 1}],
        }, timeout=15.0)
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    proto = r.json()["protocolo"]

    pactok = _tok(base_url, "paciente")
    rt = httpx.post(f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
                    headers=_h(pactok), json={"cnpj_laboratorio": _CNPJ_CLINICA}, timeout=15.0)
    assert rt.status_code in (200, 201), f"transferência falhou: {rt.text}"

    ltok = _tok(base_url, "clinica")
    item_id = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(ltok),
                        timeout=15.0).json()["itens"][0]["id"]

    rc = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                    headers=_h(ltok), json={}, timeout=15.0)
    assert rc.status_code in (200, 201), f"coleta falhou: {rc.status_code} {rc.text}"

    rr = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/resultado",
                    headers=_h(ltok), json={"resultado_resumo": "Glicemia 92 mg/dL"},
                    timeout=15.0)
    assert rr.status_code in (200, 201), f"resultado falhou: {rr.status_code} {rr.text}"

    estado = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(ltok),
                       timeout=15.0).json()["itens"][0]
    assert estado["status_item"] == "resultado_disponivel", estado
    assert estado["laudado"] is False, "ainda não há laudo — o item tem de estar laudável"
    return proto, item_id


def test_percurso_e2_produz_laudo_e_nao_duplica(
    page: Page, browser, app_demo, erros_de_console
):
    nome_exame = f"GLICEMIA-{_TS_E2}"
    proto, item_id = _pedido_e2(app_demo, nome_exame)

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        # Por BUSCA, não pela fila: a fila lista quem aguarda atendimento, e o
        # pedido E2 já foi coletado e lido. É o caminho real do operador que
        # volta a um pedido para laudá-lo.
        _abrir_pedido_por_busca(pg, app_demo, proto)

        # AC (i) — o gatilho EXISTE para item já com resultado. É a linha que o
        # defeito matava: antes daqui o percurso E2 não tinha como laudar.
        gatilho = pg.get_by_role("button", name="🔬 Produzir laudo", exact=False)
        expect(gatilho).to_be_visible(timeout=_TIMEOUT_MS)

        _preencher_e_liberar(pg, item_id, "Glicemia 92 mg/dL", "normal", "70–99 mg/dL")
        expect(pg.locator("#feedback-laudo")).to_contain_text(
            "Laudo liberado", timeout=_TIMEOUT_MS)

        # AC (iv) — o gatilho SOME. Não por o item ter mudado de estado (ele já
        # estava em `resultado_disponivel` antes do laudo), mas por `laudado`.
        expect(pg.locator("#acoes-laudo")).not_to_contain_text(
            "Produzir laudo", timeout=_TIMEOUT_MS)
    finally:
        ctx.close()

    # AC (i), segunda metade — o artefato chegou ao cidadão.
    # O backend normaliza o nome do exame para maiúsculas — comparar em caixa
    # alta, senão o teste falha por acidente de grafia e não por defeito.
    laudos = _laudos_do_cidadao(app_demo)
    assert any(nome_exame.upper() in str(ld).upper() for ld in laudos), (
        f"laudo do E2 não apareceu na carteira: {laudos}")


def test_item_do_e2_se_declara_laudado_apos_o_laudo(app_demo):
    """A metade de contrato do AC (iv), sem navegador: o backend passa a dizer
    que o item está coberto — é o que cala o botão e o que sobrevive a um F5."""
    nome_exame = f"TSH-{_TS_E2}"
    proto, item_id = _pedido_e2(app_demo, nome_exame)

    ltok = _tok(app_demo, "clinica")
    r = httpx.post(f"{app_demo}/laudos", headers=_h(ltok), json={
        "cns_autor": _CNS, "nome_autor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "pedido_protocolo": proto,
        "itens": [{"nome_exame": nome_exame, "pedido_item_id": item_id,
                   "conclusao": "normal"}],
    }, timeout=15.0)
    assert r.status_code in (200, 201), f"criação do laudo falhou: {r.text}"

    item = httpx.get(f"{app_demo}/pedidos-exame/{proto}", headers=_h(ltok),
                     timeout=15.0).json()["itens"][0]
    assert item["laudado"] is True
