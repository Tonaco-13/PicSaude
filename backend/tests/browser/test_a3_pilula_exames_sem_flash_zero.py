"""
tests/browser/test_a3_pilula_exames_sem_flash_zero.py — FILA-VIVA A3 (fila 5).

SINTOMA (walkthrough do arquiteto, 27/08): "a pílula de Exames da carteira
exibe 0 com a aba de exames cheia de pedidos." Hipótese original ("contador lê
bucket diferente do que a aba lista") foi DESCARTADA por leitura: o contador
(`_contagemCarteira.pedidos = ativos.length`, `cidadao.html`) e a lista
(`renderizarPedidosExame(ativos)`) usam o MESMO array, na MESMA função — não
há bucket divergente.

PROVA (engenheiro, 29/08): 30 amostras do texto de `#submod-count-exames` a
cada 100ms, a partir do `domcontentloaded`, mostraram `'0'` na primeira
amostra e `'2'` (o valor real) em todas as seguintes. Causa raiz: a barra de
pílulas (`submodulos.js`) pinta `_SUBMODULOS_CARTEIRA`'s `contador: 0`
(placeholder ESTÁTICO) antes de o fetch assíncrono de
`GET /paciente/pedidos-exame` resolver e chamar
`_sincronizarContadoresCarteira()`. `0` pintado de saída é indistinguível de
"genuinamente vazio" — o walkthrough viu exatamente essa janela.

FIX: `_SUBMODULOS_CARTEIRA` passa a usar `contador: null` ("sem dado ainda"),
e `submodulos.js::render()` esconde (`hidden`) a pílula quando `contador ===
null`, em vez de pintar `0`. `Submodulos.contador()` (não mudou) já sabia
desesconder + preencher quando o valor real chega — só o lado que MONTA a
barra não usava esse vocabulário.

Este arquivo prova, com a rede deliberadamente atrasada (`page.route`, sem
race contra a velocidade real do fetch), que a pílula nasce ESCONDIDA e só
aparece com o valor certo — nunca visível mostrando `0` no meio do caminho.
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import Page, expect

_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_TIMEOUT_MS = 15_000
_TS = time.strftime("%Y%m%d%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _autenticar_paciente(page: Page, base_url: str) -> None:
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
    ptok = _tok(base_url, "prescritor")
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers={"Authorization": f"Bearer {ptok}", "Content-Type": "application/json"},
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


def test_pilula_exames_nao_pisca_zero_nasce_escondida_ate_o_fetch(
    page: Page, app_demo, erros_de_console
):
    _emitir_pedido_para_paciente(app_demo, f"INVESTIGA-A3-{_TS}")
    _autenticar_paciente(page, app_demo)

    # Atrasa DELIBERADAMENTE a resposta do fetch que preenche o contador —
    # sem isto, o teste corre contra uma rede local rápida demais para provar
    # o estado intermediário de forma determinística.
    def _atrasar(route):
        page.wait_for_timeout(600)
        route.continue_()

    page.route("**/paciente/pedidos-exame", _atrasar)

    page.goto(f"{app_demo}/cidadao.html", wait_until="domcontentloaded")

    pilula = page.locator("#submod-count-exames")

    # Durante a janela atrasada: a pílula EXISTE (o <span> nasceu — contador
    # não é `undefined`) mas está ESCONDIDA — nunca "0" visível.
    expect(pilula).to_be_attached(timeout=_TIMEOUT_MS)
    expect(pilula).to_be_hidden(timeout=_TIMEOUT_MS)

    # Depois que o fetch (atrasado) resolve: visível, com o valor real —
    # nunca "0" (há ao menos o pedido recém-emitido nesta função).
    expect(pilula).to_be_visible(timeout=_TIMEOUT_MS)
    texto = pilula.text_content()
    assert texto != "0", f"pílula voltou a mostrar 0 depois do fetch: {texto!r}"

    assert not erros_de_console
