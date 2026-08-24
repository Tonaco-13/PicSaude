"""
tests/browser/test_j11_selo_e_lente.py — TICKET-J.11 (`module`).

AS REGRAS QUE ESTE ARQUIVO GUARDA
---------------------------------
Adendo §10 do ENG-011 (decisão do Fabiano, 15/08 — "de acordo, versão A"):

  > o cidadão vê, em tempo de leitura, o agendamento que o laboratório criou
  > para o seu exame — sem nenhuma transição de custódia (informação ≠
  > custódia; a custódia segue com `prestador_exame` até o fim).

Adendo §11b (lente compartilhada):

  > o index MANTÉM a lente pública; cada cartão de objeto nas abas do cidadão
  > ganha "ver rastreabilidade" abrindo a trilha neutra daquele objeto.

POR QUE UM SMOKE, SE A INTEGRAÇÃO JÁ COBRE
-------------------------------------------
`tests/integration/test_j11_selo_agendamento.py` prova o contrato do backend.
O que só aqui se prova:

  · **a persona LABORATÓRIO agendando** — `POST /agendamentos` como
    `dispensador` é 403 na fixture de integração (fail-closed do §D1, sem
    `prestadores.cnpj → org_id`); no seed da demo a Clínica Demo é prestador de
    verdade. É o ator real do AC, e o J.7 já tinha cobrado essa lição;
  · **"sem sair da aba"** — o AC é explícito: a data aparece no MESMO cartão,
    sem o cidadão ter de ir procurar noutro lugar. Isso é geometria de tela,
    não contrato;

    > **Superseded em 23/08 (ENG-015 §4, martelo do Fabiano):** a carteira
    > ganhou a 4ª aba, *Agendamentos*. O que caiu foi a contagem de abas —
    > acidente do momento em que o J.11 foi escrito. O que este arquivo guarda
    > segue de pé, e ficou mais forte: a data continua no cartão (o §4 recusou
    > explicitamente reduzir o selo a "ver compromisso") e continua chegando lá
    > **sem** navegação. A aba nova é um segundo lugar para a mesma verdade,
    > não a mudança de lugar dela.
  · **a extração da lente não quebrou o portal** — o `index.html` é a prova da
    tese para o visitante anônimo. Um refactor que a mudasse passaria em toda
    guarda estática que só olha a `cidadao.html`.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_j11_selo_e_lente.py -v
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

_TS = time.strftime("%Y%m%d%H%M%S")

_DATA_HORA = "2026-09-01T08:00:00"
_UNIDADE   = "DEMO-LAB"


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


def _laboratorio_agenda(base_url: str, proto: str, *,
                        data_hora: str = _DATA_HORA,
                        unidade: str = _UNIDADE) -> str:
    """A persona do AC: quem marca é o LABORATÓRIO."""
    r = httpx.post(
        f"{base_url}/agendamentos",
        headers=_h(_tok(base_url, "clinica")),
        json={"pedido_protocolo": proto, "org_id": "clinica-demo",
              "unidade_id": unidade, "data_hora": data_hora},
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"laboratório não conseguiu agendar: {r.text}"
    return r.json()["protocolo"]


def _cartao_do_exame(pc: Page, base_url: str, proto: str):
    pc.goto(f"{base_url}/cidadao.html", wait_until="networkidle")
    abrir_aba_carteira(pc, "exames")
    card = pc.locator("#lista-pedidos-exame .exame-card", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    return card


# ===========================================================================
# 1 — o AC completo: transferiu → laboratório agendou → o cidadão vê a data
# ===========================================================================

def test_cidadao_ve_o_agendamento_no_cartao_sem_sair_da_aba(
    page: Page, browser, app_demo, erros_de_console
):
    """AC do Adendo §10, ponta a ponta e pela tela.

    O caminho inteiro numa aba só: o cidadão entrega, o laboratório marca, e a
    data aparece no MESMO cartão da aba Exames, sem ele ter de procurar em
    outro lugar. Desde o ENG-015 §4 existe também a aba Agendamentos — segundo
    lugar para a MESMA verdade, nunca a mudança de lugar dela.
    """
    proto = _emitir_ao_paciente(app_demo, f"J11-SELO-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx.new_page()
        _transferir_pela_tela(pc, app_demo, proto)

        # Antes de marcarem: entregar é posse, não agenda (J.7). Sem selo.
        card = _cartao_do_exame(pc, app_demo, proto)
        expect(card).not_to_contain_text("Agendado:")

        _laboratorio_agenda(app_demo, proto)

        card = _cartao_do_exame(pc, app_demo, proto)
        selo = card.locator(".exame-selo-agendamento")
        expect(selo).to_be_visible(timeout=_TIMEOUT_MS)
        expect(selo).to_contain_text("Agendado: 01/09 08:00")
        expect(selo).to_contain_text(_UNIDADE)

        # "sem sair da aba": o cartão foi carregado com o painel de Exames já
        # ativo e a data estava ali — nenhum clique de navegação entre o
        # `goto` e a leitura do selo (ver `_cartao_do_exame`).
        expect(pc.locator("#aba-exames")).to_be_visible()
        # A carteira tem as CINCO abas declaradas (ENG-015 §4 + ENG-016 §4) — a
        # contagem segue travada para que aba nova entre por decisão, não por
        # descuido. Cada aumento aqui corresponde a um martelo registrado.
        expect(pc.locator("[id^='aba-btn-']")).to_have_count(5)
    finally:
        ctx.close()


def test_ler_o_selo_nao_transfere_custodia(
    page: Page, browser, app_demo, erros_de_console
):
    """informação ≠ custódia — a regra que dá nome ao ticket.

    O cidadão olha a data quantas vezes quiser; a posse continua no
    laboratório e o ledger não cresce por causa de um olhar.
    """
    proto = _emitir_ao_paciente(app_demo, f"J11-LEITURA-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx.new_page()
        _transferir_pela_tela(pc, app_demo, proto)
        _laboratorio_agenda(app_demo, proto)

        antes = _eventos(app_demo, proto)
        for _ in range(2):
            card = _cartao_do_exame(pc, app_demo, proto)
            expect(card.locator(".exame-selo-agendamento")).to_be_visible(
                timeout=_TIMEOUT_MS)
        depois = _eventos(app_demo, proto)
    finally:
        ctx.close()

    assert antes == depois, f"ler o selo mexeu no ledger: {antes} → {depois}"

    # E o cartão continua dizendo a verdade sobre a posse (J.7 preservado).
    # `to_contain_text` lê o texto do DOM; `inner_text()` leria o RENDERIZADO,
    # com o `text-transform:uppercase` do `.exame-no-lab strong` já aplicado.
    ctx2 = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        card = _cartao_do_exame(ctx2.new_page(), app_demo, proto)
        expect(card).to_contain_text("Custódia transferida", timeout=_TIMEOUT_MS)
        expect(card.get_by_role("button", name="Transferir Custódia")).to_have_count(0)
    finally:
        ctx2.close()


# ===========================================================================
# 2 — remarcação: o cartão mostra o corrente
# ===========================================================================

def test_remarcacao_troca_a_data_no_cartao(
    page: Page, browser, app_demo, erros_de_console
):
    """Remarcar é derivar. O cartão mostra o vigente, não o revogado.

    Se mostrasse o antigo, mandaria o cidadão à coleta na data errada — o tipo
    de erro que a tela, e não o backend, entrega ao usuário.
    """
    proto = _emitir_ao_paciente(app_demo, f"J11-REMARCA-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx.new_page()
        _transferir_pela_tela(pc, app_demo, proto)
        ag = _laboratorio_agenda(app_demo, proto)

        expect(_cartao_do_exame(pc, app_demo, proto)).to_contain_text("01/09 08:00")

        # Quem remarca é o LABORATÓRIO — o ator real, e agora o autorizado.
        #
        # Este teste nasceu com o prescritor aqui, porque
        # `POST /agendamentos/{p}/remarcar` não aceitava `dispensador` embora
        # `POST /agendamentos` aceitasse: o laboratório marcava e não podia
        # remarcar. A assimetria foi reportada daqui e fechada pelo
        # MICRO-TICKET RBAC (`core`) — ver
        # `tests/integration/test_rbac_agendamento_prestador.py`. Com o papel
        # aberto, o smoke passou a exercitar o caminho de verdade.
        r = httpx.post(
            f"{app_demo}/agendamentos/{ag}/remarcar",
            headers=_h(_tok(app_demo, "clinica")),
            json={"data_hora": "2026-09-15T14:30:00", "unidade_id": "DEMO-LAB-2"},
            timeout=15.0,
        )
        assert r.status_code in (200, 201), r.text

        card = _cartao_do_exame(pc, app_demo, proto)
        selo = card.locator(".exame-selo-agendamento")
        expect(selo).to_contain_text("15/09 14:30", timeout=_TIMEOUT_MS)
        expect(selo).to_contain_text("DEMO-LAB-2")
        expect(selo).not_to_contain_text("01/09 08:00")
        expect(selo).to_contain_text("remarcado")
    finally:
        ctx.close()


# ===========================================================================
# 3 — a lente compartilhada (Adendo §11b)
# ===========================================================================

def test_ver_rastreabilidade_abre_a_trilha_no_proprio_cartao(
    page: Page, browser, app_demo, erros_de_console
):
    """AC §11b: cartão → trilha, sem login adicional.

    A mesma lente do portal, aberta a partir de um objeto que o cidadão já tem
    na mão — ele não precisa copiar o protocolo e ir procurar no index.
    """
    proto = _emitir_ao_paciente(app_demo, f"J11-LENTE-{_TS}")

    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx.new_page()
        card = _cartao_do_exame(pc, app_demo, proto)

        card.get_by_role("button", name="Ver rastreabilidade").click()

        lente = card.locator(".lente-card")
        expect(lente).to_be_visible(timeout=_TIMEOUT_MS)
        expect(lente).to_contain_text(proto)
        expect(lente).to_contain_text("Pedido de exame")
        # Visão NEUTRA: estado sim, conteúdo clínico não.
        expect(lente).to_contain_text("sem conteúdo clínico")

        # Toggle — o cartão não cresce para sempre.
        card.get_by_role("button", name="Ver rastreabilidade").click()
        expect(lente).to_have_count(0, timeout=_TIMEOUT_MS)
    finally:
        ctx.close()


def test_lente_publica_do_portal_segue_intacta(page: Page, app_demo, erros_de_console):
    """§11b: "o index mantém a lente pública; função inalterada".

    A extração mudou de ONDE vem o desenho, não o que o visitante anônimo faz:
    digita o protocolo, clica em Consultar, recebe o cartão neutro. Sem sessão
    nenhuma — esta página é a prova da tese para quem chega de fora.
    """
    proto = _emitir_ao_paciente(app_demo, f"J11-PORTAL-{_TS}")

    page.goto(f"{app_demo}/index.html", wait_until="networkidle")
    page.fill("#lente-input", proto)
    page.get_by_role("button", name="Consultar").click()

    resultado = page.locator("#lente-resultado")
    expect(resultado).to_be_visible(timeout=_TIMEOUT_MS)
    expect(resultado).to_contain_text(proto)
    expect(resultado).to_contain_text("Pedido de exame")


def test_lente_do_portal_avisa_quando_nao_acha(page: Page, app_demo, erros_de_console):
    """R4 — nunca calar: não achou, diz o próximo passo.

    A mensagem também saiu para o componente; se a extração a tivesse perdido,
    a busca falha em silêncio, que é o pior resultado possível numa tela cuja
    função é provar que o objeto existe.
    """
    page.goto(f"{app_demo}/index.html", wait_until="networkidle")
    page.fill("#lente-input", "protocolo-que-nao-existe-0000")
    page.get_by_role("button", name="Consultar").click()

    expect(page.locator("#lente-feedback")).to_contain_text(
        "Nenhum objeto sanitário encontrado", timeout=_TIMEOUT_MS)
