"""
tests/browser/test_aba_agendamentos_cidadao.py — ENG-015 §4 (`module`).

A REGRA QUE ESTE ARQUIVO GUARDA
-------------------------------
§4 do `DESENHO-AGENDAMENTOS-UX.md` (martelo do Fabiano, 23/08):

  > Nova aba "Agendamentos" na carteira: compromissos ativos ordenados por data
  > (quando/onde/exame/protocolo). MVP: agregação no front a partir do
  > `agendamento` que os cartões já carregam — sem endpoint novo.
  > O selo no cartão MANTÉM data/hora (...). O selo linka para a aba.

A pergunta da aba é **"o que eu tenho marcado?"**. Antes dela essa pergunta não
tinha onde ser respondida: o compromisso só existia como selo DENTRO do cartão
do pedido, então descobrir a próxima coleta era abrir os pedidos um a um.

POR QUE PELO NAVEGADOR
----------------------
Não há contrato de backend novo para provar — é justamente o ponto do §4
(agregação no front, `pedido.agendamento` de carona). O que existe de novo é
GEOMETRIA DE TELA e só a tela prova: a lista agrega de dois pedidos, ordena
pela data, o selo leva até lá e o caminho volta.

As guardas estáticas de `tests/unit/test_frontend_abas_j8_j9.py` travam as duas
DECISÕES do §4 (o selo não emudece; não nasce rota própria) e rodam em todo PR.
Este arquivo prova que a tela funciona.

ERRO DE JS: VIGIADO AQUI, E NÃO PELA FIXTURE
--------------------------------------------
`erros_de_console` escuta a `page` do fixture. Estes testes falam por uma
`page` de CONTEXTO PRÓPRIO (o cidadão precisa da sessão dele no
`sessionStorage`), que a fixture não enxerga — pedi-la aqui seria decoração.
Por isso `_nova_pagina` prende o listener na página que o teste realmente usa.
Vigia-se `pageerror` (exceção JS não tratada): é a classe de bug que esta
entrega mais arrisca — helper de tela chamado da tela errada derruba o render
inteiro sem devolver erro nenhum ao teste.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_aba_agendamentos_cidadao.py -v
"""
from __future__ import annotations

import json
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

_TS = time.strftime("%Y%m%d%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx_paciente(browser, base_url: str):
    ctx = browser.new_context()
    tok = _tok(base_url, "paciente")
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'paciente');
        sessionStorage.setItem('picsaude_demo_sub',   {_CPF!r});
        sessionStorage.setItem('picsaude_demo_nome',  {_NOME_PACIENTE!r});
        """
    )
    return ctx


def _emitir_ao_paciente(base_url: str, nome_exame: str) -> str:
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


def _transferir(base_url: str, proto: str) -> None:
    """Entregar é POSSE (J.7) — pré-condição para o laboratório agendar."""
    r = httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(_tok(base_url, "paciente")),
        json={"cnpj_laboratorio": "11222333000181", "nome_laboratorio": "Clínica Demo"},
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"transferência falhou: {r.text}"


def _laboratorio_agenda(base_url: str, proto: str, data_hora: str, unidade: str) -> str:
    r = httpx.post(
        f"{base_url}/agendamentos",
        headers=_h(_tok(base_url, "clinica")),
        json={"pedido_protocolo": proto, "org_id": "clinica-demo",
              "unidade_id": unidade, "data_hora": data_hora},
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"laboratório não conseguiu agendar: {r.text}"
    return r.json()["protocolo"]


def _pedido_agendado(base_url: str, sufixo: str, data_hora: str, unidade: str) -> str:
    proto = _emitir_ao_paciente(base_url, f"AGD-{sufixo}-{_TS}")
    _transferir(base_url, proto)
    _laboratorio_agenda(base_url, proto, data_hora, unidade)
    return proto


def _nova_pagina(ctx) -> tuple[Page, list[str]]:
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda exc: erros.append(f"pageerror: {exc}"))
    return pg, erros


def _carteira(ctx, base_url: str) -> tuple[Page, list[str]]:
    pg, erros = _nova_pagina(ctx)
    pg.goto(f"{base_url}/cidadao.html", wait_until="networkidle")
    return pg, erros


# ===========================================================================
# 1 — a pergunta da aba tem resposta: agrega, ordena e mostra o essencial
# ===========================================================================

def test_a_aba_reune_os_compromissos_ordenados_pelo_mais_proximo(
    browser, app_demo
):
    """Dois pedidos, duas datas — e a aba responde "o que eu tenho marcado?".

    O CENÁRIO É CONSTRUÍDO CONTRA A ORDEM NATURAL, de propósito. O backend
    devolve os pedidos por `pe.id DESC`, isto é, o criado por último primeiro.
    Emitindo o de data PRÓXIMA antes do de data distante, a ordem de chegada
    fica [distante, próximo] — o inverso do que a aba deve mostrar. Sem a
    ordenação por data o teste cai.

    Isto não é zelo teórico: na primeira escrita o cenário era o oposto e
    passava VERDE com a ordenação arrancada. Um teste de ordem que aceita a
    ordem de chegada não testa ordem nenhuma.
    """
    proximo  = _pedido_agendado(app_demo, "CEDO",  "2026-09-02T07:15:00", "DEMO-LAB")
    distante = _pedido_agendado(app_demo, "TARDE", "2026-12-20T15:30:00", "DEMO-LAB-2")

    ctx = _ctx_paciente(browser, app_demo)
    try:
        pg, erros_js = _carteira(ctx, app_demo)
        abrir_aba_carteira(pg, "agendamentos")

        cartao_proximo  = pg.locator("#lista-agendamentos .compromisso-card", has_text=proximo)
        cartao_distante = pg.locator("#lista-agendamentos .compromisso-card", has_text=distante)
        expect(cartao_proximo).to_be_visible(timeout=_TIMEOUT_MS)
        expect(cartao_distante).to_be_visible(timeout=_TIMEOUT_MS)

        # quando / onde / qual exame — o cartão responde sem abrir o pedido
        expect(cartao_proximo).to_contain_text("02/09/2026 às 07:15")
        expect(cartao_proximo).to_contain_text("quarta")
        expect(cartao_proximo).to_contain_text("DEMO-LAB")
        expect(cartao_proximo).to_contain_text(f"AGD-CEDO-{_TS}")

        # ordem: o mais próximo vem antes do mais distante
        todos = pg.locator("#lista-agendamentos .compromisso-card")
        protos = [c.inner_text() for c in todos.all()]
        i_prox = next(i for i, t in enumerate(protos) if proximo in t)
        i_dist = next(i for i, t in enumerate(protos) if distante in t)
        assert i_prox < i_dist, (
            "a aba listou o compromisso mais distante antes do mais próximo — "
            "a ordenação por data se perdeu"
        )

        # o contador da aba conta compromissos, não pedidos
        assert int(pg.locator("#aba-count-agendamentos").inner_text()) >= 2
        assert not erros_js, erros_js
    finally:
        ctx.close()


# ===========================================================================
# 2 — o selo linka para a aba, e o caminho volta
# ===========================================================================

def test_o_selo_leva_a_aba_e_o_botao_ver_pedido_traz_de_volta(
    browser, app_demo
):
    """O §4 pede o link do selo para a aba. O caminho de volta vem junto: uma
    aba que mostra um protocolo sem porta de retorno é um beco."""
    proto = _pedido_agendado(app_demo, "LINK", "2026-10-05T09:00:00", "DEMO-LAB")

    ctx = _ctx_paciente(browser, app_demo)
    try:
        pg, erros_js = _carteira(ctx, app_demo)
        abrir_aba_carteira(pg, "exames")

        card = pg.locator("#lista-pedidos-exame .exame-card", has_text=proto)
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)
        selo = card.locator("button.exame-selo-agendamento")
        # A decisão do §4: o selo mantém a data — ele LEVA à aba, não substitui
        # a informação por um convite a clicar.
        expect(selo).to_contain_text("Agendado: 05/10 09:00")

        selo.click()

        expect(pg.locator("#aba-agendamentos")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#aba-exames")).to_be_hidden()
        destino = pg.locator(f"#compromisso-{proto}")
        expect(destino).to_be_visible(timeout=_TIMEOUT_MS)

        destino.get_by_role("button", name="Ver pedido").click()
        expect(pg.locator("#aba-exames")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator(f"#exame-card-{proto}")).to_be_visible(timeout=_TIMEOUT_MS)
        assert not erros_js, erros_js
    finally:
        ctx.close()


# ===========================================================================
# 3 — vazio responde à pergunta; erro responde por que não há resposta
# ===========================================================================
# A carteira da demo é compartilhada entre os testes deste diretório — o
# cidadão acumula pedidos. Para provar os dois estados de forma determinística,
# a resposta de `/paciente/pedidos-exame` é interceptada. É a mesma técnica do
# `test_relogin_demo.py`; aqui ela isola a TELA do estado do banco.


def _com_pedidos_exame(pg: Page, corpo) -> None:
    """Faz `/paciente/pedidos-exame` responder `corpo` (ou falhar, se None)."""
    def responder(rota):
        if corpo is None:
            rota.fulfill(status=500, body='{"detail":"boom"}',
                         content_type="application/json")
        else:
            rota.fulfill(status=200, body=json.dumps(corpo),
                         content_type="application/json")
    pg.route("**/paciente/pedidos-exame", responder)


def test_sem_compromisso_a_aba_diz_quem_marca(
    browser, app_demo
):
    """O vazio responde à pergunta da aba — e à seguinte, que o cidadão faria
    em voz alta: "então como é que eu marco?". Quem marca é o laboratório,
    depois da transferência de custódia (J.7)."""
    ctx = _ctx_paciente(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        _com_pedidos_exame(pg, {"posse": [], "em_andamento": [], "historico": []})
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "agendamentos")

        painel = pg.locator("#lista-agendamentos")
        expect(painel).to_contain_text("Nenhum compromisso marcado", timeout=_TIMEOUT_MS)
        expect(painel).to_contain_text("laboratório")
        expect(pg.locator("#aba-count-agendamentos")).to_have_text("0")
        assert not erros_js, erros_js
    finally:
        ctx.close()


def test_carga_que_falha_nao_vira_nenhum_compromisso(
    browser, app_demo
):
    """A lição do #181, agora do lado do cidadão.

    Lá, "Nenhum agendamento ativo" escondia um 403 de posse — a tela respondia
    a pergunta errada com cara de resposta certa. Aqui o risco é o mesmo: uma
    carga que falhou não é uma agenda vazia. Vazio responde à PERGUNTA; erro
    responde POR QUE não há resposta.
    """
    ctx = _ctx_paciente(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        _com_pedidos_exame(pg, None)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "agendamentos")

        painel = pg.locator("#lista-agendamentos")
        expect(painel).to_contain_text("Não foi possível carregar", timeout=_TIMEOUT_MS)
        expect(painel).not_to_contain_text("Nenhum compromisso marcado")
        # A carga falhou; a TELA não pode ter caído junto.
        assert not erros_js, erros_js
    finally:
        ctx.close()
