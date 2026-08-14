"""
tests/browser/test_bancada_clinica.py — TICKET-F: o gesto "Enviar à bancada".

O QUE ESTE ARQUIVO GUARDA
-------------------------
O item coletado agora tem DOIS caminhos na tela do laboratório: mandar à bancada
(`coletado → em_analise`, o passo que faltava) ou registrar o resultado direto
(atalho legítimo para exame de leitura imediata). Depois do envio, o item mostra
"Na bancada — aguardando laudo".

Por que um smoke, se o Ticket F pedia teste manual: o backend do `/em-analise`
já tem 12 casos de integração, mas nenhum deles prova que a TELA chama o endpoint
certo, com o corpo certo, e reflete o novo estado. É exatamente a fresta entre o
que o backend faz e o que a tela afirma — o defeito que o gate de navegador
existe para pegar (lição do #152). Sem isto, o gesto seria verde no backend e
não-gateado na tela.

Três perguntas, três testes:
  1. o gesto funciona e o estado muda de verdade (tela E ledger)?
  2. cancelar o prompt de setor não envia nada?
  3. o item na bancada continua na fila do laboratório?

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_bancada_clinica.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

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


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _pedido_coletado_no_laboratorio(base_url: str, nome_exame: str) -> tuple[str, int]:
    """Leva o pedido até `coletado` pela API, que é o pré-requisito do gesto.

    O caminho de tela até aqui (transferir custódia, abrir da fila, coletar) já
    é guardado por `test_exame_transferencia_cidadao.py`; repeti-lo aqui só
    tornaria este smoke lento e frágil sem cobrir nada novo.
    """
    ptok = _tok(base_url, "prescritor")
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers=_h(ptok),
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
    proto = r.json()["protocolo"]

    # Cidadão entrega a posse ao laboratório (mesmo gesto da receita).
    pactok = _tok(base_url, "paciente")
    rt = httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(pactok), json={"cnpj_laboratorio": _CNPJ_CLINICA}, timeout=15.0,
    )
    assert rt.status_code in (200, 201), f"transferência falhou: {rt.status_code} {rt.text}"

    ltok = _tok(base_url, "clinica")
    itens = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(ltok),
                      timeout=15.0).json()["itens"]
    item_id = itens[0]["id"]

    rc = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                    headers=_h(ltok), json={}, timeout=15.0)
    assert rc.status_code in (200, 201), f"coleta falhou: {rc.status_code} {rc.text}"
    return proto, item_id


def _abrir_laboratorio(browser, base_url: str):
    """Contexto autenticado como a clínica (role `dispensador`)."""
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


def _abrir_pedido_pela_fila(page: Page, base_url: str, proto: str) -> None:
    page.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    fila = page.locator("#fila-lista")
    expect(fila).to_be_visible(timeout=_TIMEOUT_MS)
    expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
    fila.locator(".fila-item", has_text=proto).click()
    expect(page.locator("#resultado-pedido")).to_be_visible(timeout=_TIMEOUT_MS)


def _status_do_item(base_url: str, proto: str, item_id: int) -> str:
    tok = _tok(base_url, "clinica")
    itens = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(tok),
                      timeout=15.0).json()["itens"]
    return next(i["status_item"] for i in itens if i["id"] == item_id)


def _eventos(base_url: str, proto: str) -> list[str]:
    tok = _tok(base_url, "clinica")
    corpo = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(tok), timeout=15.0).json()
    return [e["tipo_evento"] for e in corpo.get("eventos", [])]


# ---------------------------------------------------------------------------
# 1 — o gesto ponta a ponta
# ---------------------------------------------------------------------------

def test_enviar_a_bancada_muda_o_item_na_tela_e_no_ledger(
    page: Page, browser, app_demo, erros_de_console
):
    proto, item_id = _pedido_coletado_no_laboratorio(app_demo, f"HEMOGRAMA-BANCADA-{_TS}")

    ctx = _abrir_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido_pela_fila(pg, app_demo, proto)

        item = pg.locator(f"#item-exame-{item_id}")
        expect(item).to_be_visible(timeout=_TIMEOUT_MS)

        # AC1 — o item coletado oferece os DOIS caminhos.
        botao = item.get_by_role("button", name="Enviar à bancada")
        expect(botao).to_be_visible(timeout=_TIMEOUT_MS)
        expect(item.get_by_role("button", name="Registrar resultado")).to_be_visible()

        # O prompt de setor é aceito com um valor — work-area, não fila de máquina.
        pg.once("dialog", lambda d: d.accept("bioquímica"))
        botao.click()

        # AC3 — o estado novo aparece com o texto do ticket.
        expect(item).to_contain_text("Na bancada — aguardando laudo", timeout=_TIMEOUT_MS)
        expect(item).to_contain_text("Em Análise", timeout=_TIMEOUT_MS)

        # AC2 — a tela não está mentindo: o backend concorda.
        assert _status_do_item(app_demo, proto, item_id) == "em_analise"
        assert "pedido_em_analise" in _eventos(app_demo, proto)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# 2 — cancelar o prompt não envia nada
# ---------------------------------------------------------------------------

def test_cancelar_o_prompt_de_setor_nao_envia_nada(
    page: Page, browser, app_demo, erros_de_console
):
    """Desistência do próprio usuário é silêncio legítimo — mas silêncio que NÃO
    pode ter mudado estado no servidor."""
    proto, item_id = _pedido_coletado_no_laboratorio(app_demo, f"GLICEMIA-CANCELA-{_TS}")

    ctx = _abrir_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido_pela_fila(pg, app_demo, proto)

        item = pg.locator(f"#item-exame-{item_id}")
        pg.once("dialog", lambda d: d.dismiss())          # cancelou o prompt
        item.get_by_role("button", name="Enviar à bancada").click()

        # O botão continua clicável (não ficou preso em "Enviando…").
        expect(item.get_by_role("button", name="Enviar à bancada")).to_be_enabled(
            timeout=_TIMEOUT_MS)
        assert _status_do_item(app_demo, proto, item_id) == "coletado"
        assert "pedido_em_analise" not in _eventos(app_demo, proto)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# 3 — o pedido na bancada NÃO some da fila
# ---------------------------------------------------------------------------

def test_pedido_na_bancada_continua_na_fila_do_laboratorio(
    page: Page, browser, app_demo, erros_de_console
):
    """A contrapartida do TICKET-B em `_ESTADOS_ITEM_ACIONAVEL_LAB`.

    Se `em_analise` não fosse acionável, mandar à bancada apagaria o pedido da
    tela no instante do clique — e o laboratório perderia o caminho até o laudo.
    Trabalho na bancada é trabalho PENDENTE; sair da fila é privilégio de estado
    terminal.
    """
    proto, item_id = _pedido_coletado_no_laboratorio(app_demo, f"TSH-FILA-{_TS}")

    ctx = _abrir_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido_pela_fila(pg, app_demo, proto)

        item = pg.locator(f"#item-exame-{item_id}")
        pg.once("dialog", lambda d: d.accept(""))          # sem setor declarado
        item.get_by_role("button", name="Enviar à bancada").click()
        expect(item).to_contain_text("Na bancada", timeout=_TIMEOUT_MS)

        # `recarregarPedido()` já repuxou a fila; o pedido segue lá.
        fila = pg.locator("#fila-lista")
        expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)

        # E o setor vazio não virou setor declarado no ledger.
        assert _status_do_item(app_demo, proto, item_id) == "em_analise"
    finally:
        ctx.close()
