"""
tests/browser/test_laudo_clinica_cidadao.py — TICKET-G: a pedra angular.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O laboratório produz um laudo ESTRUTURADO (conclusão + valor de referência +
resumo, por exame), assina em nome do Responsável Técnico e libera — e o laudo
aparece na carteira do CIDADÃO, que dá ciência. É o arco inteiro da demo:

    clinica.html                              cidadao.html
    ────────────                              ────────────
    item na bancada → 🔬 Produzir laudo
    → assina (RT) → libera ao cidadão   ──▶   laudo na carteira
                                              → dar ciência
    painel mostra "Ciência do cidadão"  ◀──

DUAS AFIRMAÇÕES QUE SÓ UM NAVEGADOR PROVA
-----------------------------------------
1. O `autor_id` é o RT (CNS), não o CNPJ da unidade — o operador entra como
   dispensador e mesmo assim o laudo sai no nome do responsável técnico
   (TICKET-C). Um teste de API provaria o backend; este prova que a TELA manda
   os campos certos.
2. O laudo chega ao cidadão. A custódia clínica é dele — é a política de
   `docs/POLITICA_CUSTODIA_CLINICA_LAUDO.md` acontecendo, não declarada.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_laudo_clinica_cidadao.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira

_TIMEOUT_MS = 20_000

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


def _pedido_na_bancada(base_url: str, nome_exame: str) -> tuple[str, int]:
    """Pedido emitido → transferido ao laboratório → coletado → NA BANCADA.

    Tudo por API: o caminho de tela até aqui já é guardado por
    `test_exame_transferencia_cidadao.py` e `test_bancada_clinica.py`.
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
    for rota in ("coletar", "em-analise"):
        rr = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/{rota}",
                        headers=_h(ltok), json={}, timeout=15.0)
        assert rr.status_code in (200, 201), f"{rota} falhou: {rr.status_code} {rr.text}"
    return proto, item_id


def _ctx_laboratorio(browser, base_url: str):
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


def _ctx_cidadao(browser, base_url: str):
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


def _abrir_pedido(pg: Page, base_url: str, proto: str) -> None:
    pg.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    fila = pg.locator("#fila-lista")
    expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
    fila.locator(".fila-item", has_text=proto).click()
    expect(pg.locator("#pedido-foco")).to_be_visible(timeout=_TIMEOUT_MS)


def _preencher_e_liberar(pg: Page, item_id: int, resumo: str, conclusao: str, ref: str) -> None:
    pg.get_by_role("button", name="🔬 Produzir laudo", exact=False).click()
    editor = pg.locator("#editor-laudo")
    expect(editor).to_be_visible(timeout=_TIMEOUT_MS)

    # O RT vem pré-preenchido da fonte única de identidades (config.js DEMO.*).
    expect(pg.locator("#laudo-rt-cns")).to_have_value(_CNS)

    pg.locator(f"#laudo-resumo-{item_id}").fill(resumo)
    pg.locator(f"#laudo-conclusao-{item_id}").select_option(conclusao)
    pg.locator(f"#laudo-ref-{item_id}").fill(ref)
    pg.get_by_role("button", name="Assinar e liberar ao cidadão").click()


def _abrir_pedido_por_busca(pg: Page, base_url: str, proto: str) -> None:
    """Abre o pedido digitando o protocolo — caminho independente da fila."""
    pg.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    pg.locator("#busca-protocolo").fill(proto)
    pg.get_by_role("button", name="Buscar").click()
    expect(pg.locator("#pedido-foco")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(pg.locator("#detalhes-pedido")).to_contain_text(proto, timeout=_TIMEOUT_MS)


def _laudos_do_cidadao(base_url: str) -> list[dict]:
    """Carteira do cidadão. O endpoint separa `disponiveis` de `historico`
    (auth.py) — aqui interessa a existência do laudo, em qualquer das duas."""
    tok = _tok(base_url, "paciente")
    r = httpx.get(f"{base_url}/paciente/laudos", headers=_h(tok), timeout=15.0)
    assert r.status_code == 200, r.text
    corpo = r.json()
    return list(corpo.get("disponiveis", [])) + list(corpo.get("historico", []))


# ---------------------------------------------------------------------------
# 1 — o arco completo: clínica produz, cidadão recebe e dá ciência
# ---------------------------------------------------------------------------

def test_clinica_produz_laudo_cidadao_recebe_e_da_ciencia(
    page: Page, browser, app_demo, erros_de_console
):
    nome_exame = f"GLICEMIA-LAUDO-{_TS}"
    proto, item_id = _pedido_na_bancada(app_demo, nome_exame)

    ctx_lab = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx_lab.new_page()
        _abrir_pedido(pg, app_demo, proto)

        # AC — com item na bancada, o gatilho de nível-PEDIDO aparece.
        expect(pg.locator("#acoes-laudo")).to_contain_text("Produzir laudo", timeout=_TIMEOUT_MS)

        _preencher_e_liberar(pg, item_id, "Glicemia 92 mg/dL", "normal", "70-99 mg/dL")

        # AC — o editor fecha e a tela diz que o laudo foi ao cidadão.
        expect(pg.locator("#feedback-laudo")).to_contain_text(
            "carteira do cidadão", timeout=_TIMEOUT_MS)
        # AC — o item fechou o ciclo; o gatilho some (sem item na bancada).
        expect(pg.locator(f"#item-exame-{item_id}")).to_contain_text(
            "Resultado disponível", timeout=_TIMEOUT_MS)
        expect(pg.locator("#acoes-laudo")).not_to_contain_text("Produzir laudo")
        # AC — painel de acompanhamento mostra a etapa alcançada.
        expect(pg.locator("#painel-laudo")).to_contain_text("Liberado", timeout=_TIMEOUT_MS)
    finally:
        ctx_lab.close()

    # ── O laudo é do RT, não do CNPJ (TICKET-C visto pela tela) ─────────────
    laudos = _laudos_do_cidadao(app_demo)
    # Identificado pelo NOME DO EXAME (único por execução), não por ordenação —
    # a carteira também traz os laudos do seed.
    meu = next((l for l in laudos
                if any(i.get("nome_exame") == nome_exame for i in l.get("itens", []))), None)
    assert meu, f"o laudo não chegou à carteira do cidadão: {laudos}"
    proto_laudo = meu["protocolo"]

    # O conteúdo ESTRUTURADO viajou: conclusão por item, não só um resumo solto.
    assert meu["itens"][0]["conclusao"] == "normal", meu["itens"]
    # E o autor é o RT declarado, nunca a unidade que operou (TICKET-C).
    assert meu["autor_nome"] == _NOME_PRESCRITOR, meu

    ltok = _tok(app_demo, "clinica")
    detalhe = httpx.get(f"{app_demo}/laudos/{proto_laudo}", headers=_h(ltok), timeout=15.0).json()
    eventos = {e["tipo_evento"] for e in detalhe.get("eventos", [])}
    assert "laudo_criado" in eventos and "laudo_liberado" in eventos, eventos

    # ── Cidadão: recebe e dá ciência, na própria tela dele ──────────────────
    ctx_cid = _ctx_cidadao(browser, app_demo)
    try:
        pc = ctx_cid.new_page()
        pc.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pc, "laudos")          # porta própria do laudo (24/08)
        lista = pc.locator("#lista-laudos")
        expect(lista).to_be_visible(timeout=_TIMEOUT_MS)
        expect(lista).to_contain_text(proto_laudo, timeout=_TIMEOUT_MS)

        # Escopo no CARD do nosso laudo: o seed da demo traz outros laudos, e
        # asserção na lista inteira mediria o vizinho.
        card = lista.locator(".exame-card", has_text=proto_laudo)
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)
        # ENG-014 (PR C) — martelo (a): ABRIR o laudo É dar ciência. O botão
        # "Dar ciência" deixou de existir (era clique morto); o gesto é abrir.
        expect(card.get_by_role("button", name="Dar ciência")).to_have_count(0)
        card.get_by_role("button", name="Abrir laudo").click()

        card_apos = lista.locator(".exame-card", has_text=proto_laudo)
        expect(card_apos).to_contain_text("Ciência registrada", timeout=_TIMEOUT_MS)
    finally:
        ctx_cid.close()

    # ── A ciência reflui para o laboratório ────────────────────────────────
    status = httpx.get(f"{app_demo}/laudos/{proto_laudo}", headers=_h(ltok),
                       timeout=15.0).json()["status"]
    assert status in ("ciencia_paciente", "encerrado"), status


# ---------------------------------------------------------------------------
# 2 — o gatilho depende da bancada, não da vontade do operador
# ---------------------------------------------------------------------------

def test_sem_item_na_bancada_nao_ha_gatilho_de_laudo(
    page: Page, browser, app_demo, erros_de_console
):
    """O laudo cobre o que está em análise. Item apenas `coletado` não produz
    laudo — e a tela não oferece o gesto, em vez de oferecer e falhar."""
    ptok = _tok(app_demo, "prescritor")
    r = httpx.post(
        f"{app_demo}/pedidos-exame", headers=_h(ptok),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": f"TSH-SEM-BANCADA-{_TS}", "quantidade": 1}],
        }, timeout=15.0)
    proto = r.json()["protocolo"]
    pactok = _tok(app_demo, "paciente")
    httpx.post(f"{app_demo}/pedidos-exame/{proto}/transferir-laboratorio",
               headers=_h(pactok), json={"cnpj_laboratorio": _CNPJ_CLINICA}, timeout=15.0)
    ltok = _tok(app_demo, "clinica")
    item_id = httpx.get(f"{app_demo}/pedidos-exame/{proto}", headers=_h(ltok),
                        timeout=15.0).json()["itens"][0]["id"]
    httpx.post(f"{app_demo}/pedidos-exame/{proto}/itens/{item_id}/coletar",
               headers=_h(ltok), json={}, timeout=15.0)

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido(pg, app_demo, proto)
        expect(pg.locator(f"#item-exame-{item_id}")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#acoes-laudo")).not_to_contain_text("Produzir laudo")
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# 3 — cancelar o editor não cria objeto sanitário
# ---------------------------------------------------------------------------

def test_painel_mostra_o_paciente_e_gate_sobrevive_ao_reload(
    page: Page, browser, app_demo, erros_de_console
):
    """TICKET-I.1 — duas afirmações que dependem do GET enriquecido.

    1. O painel de detalhes mostra o NOME do paciente (antes: "Paciente: —",
       porque o endpoint só devolvia `paciente_id`).
    2. Depois de um F5, a tela ainda sabe qual é o laudo do pedido. Antes o
       vínculo só vivia em `laudoDoPedido` (memória da sessão): recarregar a
       página e clicar de novo emitiria um SEGUNDO laudo do mesmo pedido.
    """
    proto, item_id = _pedido_na_bancada(app_demo, f"TSH-RELOAD-{_TS}")

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido(pg, app_demo, proto)

        # (1) o paciente aparece por nome, não por travessão.
        expect(pg.locator("#detalhes-pedido")).to_contain_text(
            _NOME_PACIENTE, timeout=_TIMEOUT_MS)

        _preencher_e_liberar(pg, item_id, "TSH 2,1 mUI/L", "normal", "0,4-4,0 mUI/L")
        expect(pg.locator("#painel-laudo")).to_contain_text("Liberado", timeout=_TIMEOUT_MS)

        laudos_antes = len(_laudos_do_cidadao(app_demo))

        # (2) F5: a memória da sessão morre, mas o backend lembra.
        # Reabre por BUSCA, não pela fila: concluído o laudo, os itens deixam de
        # ser acionáveis e o pedido sai da fila (Ticket B) — e é justamente no
        # caminho da busca que o workaround antigo do Ticket G (ler o paciente
        # da fila) não teria dado certo.
        _abrir_pedido_por_busca(pg, app_demo, proto)
        expect(pg.locator("#painel-laudo")).to_contain_text("Liberado", timeout=_TIMEOUT_MS)
        # Sem item na bancada, o gatilho nem se oferece.
        expect(pg.locator("#acoes-laudo")).not_to_contain_text("Produzir laudo")

        assert len(_laudos_do_cidadao(app_demo)) == laudos_antes, "nasceu laudo duplicado"
    finally:
        ctx.close()


def test_cancelar_o_editor_nao_cria_laudo(
    page: Page, browser, app_demo, erros_de_console
):
    """Abrir o editor é intenção; laudo é objeto sanitário. Só o submit cria."""
    proto, item_id = _pedido_na_bancada(app_demo, f"UREIA-CANCELA-{_TS}")
    antes = len(_laudos_do_cidadao(app_demo))

    ctx = _ctx_laboratorio(browser, app_demo)
    try:
        pg = ctx.new_page()
        _abrir_pedido(pg, app_demo, proto)
        pg.get_by_role("button", name="🔬 Produzir laudo", exact=False).click()
        expect(pg.locator("#editor-laudo")).to_be_visible(timeout=_TIMEOUT_MS)
        pg.get_by_role("button", name="Cancelar").click()
        expect(pg.locator("#editor-laudo")).to_be_hidden(timeout=_TIMEOUT_MS)
        # O gatilho volta — o item continua na bancada.
        expect(pg.locator("#acoes-laudo")).to_contain_text("Produzir laudo", timeout=_TIMEOUT_MS)
    finally:
        ctx.close()

    assert len(_laudos_do_cidadao(app_demo)) == antes, "cancelar criou laudo"
