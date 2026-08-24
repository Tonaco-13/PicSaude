"""
tests/browser/test_demo_lab_e2e.py — TICKET-H: o roteiro da demo, executável.

O QUE ESTE ARQUIVO GUARDA
-------------------------
O roteiro 1→5 de `planejamento/demo-laboratorio-laudo-cidadao/TICKET-H-demo-e2e.md`,
do jeito que ele será apresentado — só que sem ninguém clicando:

    1. prescritor emite pedido (TUSS + SIGTAP nos itens)
    2. cidadão transfere a custódia ao laboratório         [tela do cidadão]
    3. laboratório: fila → coleta → bancada → laudo        [tela da clínica]
    4. cidadão recebe o laudo e dá ciência                 [tela do cidadão]
    5. a ciência reflui à clínica + faturamento TUSS ≠ SIGTAP

POR QUE ELE EXISTE, SE JÁ HÁ SMOKES POR TICKET
----------------------------------------------
Os smokes de F e G provam cada gesto isolado. Este prova que os gestos **se
encadeiam** — que a saída de um é a entrada do outro, atravessando três telas e
dois perfis. É a diferença entre "cada peça funciona" e "a demo acontece".

Ele também é a única prova de que a **ciência do cidadão volta à tela da
clínica**: um recorte por ticket nunca cruzaria essa fronteira.

O QUE ELE NÃO É
---------------
Não substitui o passe de `web-gui-tester` pedido pelo ticket — essa skill não
existe neste ambiente (bloqueio registrado no relatório do Ticket H).

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_demo_lab_e2e.py -v
"""
from __future__ import annotations

import csv
import io
import re
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

# Códigos reais das duas tabelas, para o passo 5 contar por pagadores distintos.
_TUSS_HEMOGRAMA = "40304361"
_SIGTAP_HEMOGRAMA = "0202020380"


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx(browser, base_url: str, role: str, sub: str, nome: str):
    """Contexto de navegador já autenticado como a persona da demo."""
    papel = "dispensador" if role == "clinica" else role
    ctx = browser.new_context()
    tok = _tok(base_url, role)
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {papel!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _csv_faturamento(base_url: str, agrupar_por: str) -> list[dict]:
    tok = _tok(base_url, "clinica")
    r = httpx.get(f"{base_url}/clinicas/faturamento.csv",
                  params={"agrupar_por": agrupar_por},
                  headers={"Authorization": f"Bearer {tok}"}, timeout=15.0)
    assert r.status_code == 200, f"{agrupar_por}: {r.status_code} {r.text}"
    return list(csv.DictReader(io.StringIO(r.text)))


# ---------------------------------------------------------------------------
# O roteiro inteiro
# ---------------------------------------------------------------------------

def test_roteiro_da_demo_ponta_a_ponta(page: Page, browser, app_demo, erros_de_console):
    nome_exame = f"HEMOGRAMA-DEMO-{_TS}"

    # ── 1. Prescritor emite o pedido ────────────────────────────────────────
    # Emissão pela API: a tela do prescritor tem guarda própria e não é o que
    # este roteiro está testando.
    ptok = _tok(app_demo, "prescritor")
    r = httpx.post(
        f"{app_demo}/pedidos-exame", headers=_h(ptok),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            # Passo 1 do roteiro: o item nasce classificado nas DUAS tabelas —
            # é o que permite ao passo 5 contar a mesma produção por pagadores
            # diferentes. O payload de emissão aceita ambos (ItemExameIn).
            "itens": [{
                "nome_exame": nome_exame, "quantidade": 1,
                "codigo_tuss": _TUSS_HEMOGRAMA, "codigo_sigtap": _SIGTAP_HEMOGRAMA,
            }],
        }, timeout=15.0)
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    # Lido com o token do PRESCRITOR: neste instante o pedido está em posse do
    # cidadão, e a clínica ainda leva 403 — a posse só chega no passo 2.
    item_id = httpx.get(f"{app_demo}/pedidos-exame/{proto}",
                        headers=_h(ptok), timeout=15.0).json()["itens"][0]["id"]

    # ── 2. Cidadão entrega a posse ao laboratório (TELA do cidadão) ─────────
    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx_cid.new_page()
        pc.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pc, "exames")          # TICKET-J.9
        lista = pc.locator("#lista-pedidos-exame")
        expect(lista).to_contain_text(proto, timeout=_TIMEOUT_MS)
        card = lista.locator(".exame-card", has_text=proto)
        expect(card.locator("input[id^='cnpj-lab-']")).to_have_value(_CNPJ_CLINICA)
        pc.once("dialog", lambda d: d.accept())
        card.get_by_role("button", name="Transferir Custódia").click()
        expect(pc.locator("#modal-transferencia")).to_contain_text(
            "transferido", timeout=_TIMEOUT_MS)
    finally:
        ctx_cid.close()

    # ── 3. Laboratório: fila → coleta → bancada → laudo (TELA da clínica) ───
    ctx_lab = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl = ctx_lab.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        # 3a. O pedido chegou sozinho na fila — sem digitar protocolo.
        fila = pl.locator("#fila-lista")
        expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
        fila.locator(".fila-item", has_text=proto).click()
        expect(pl.locator("#pedido-foco")).to_be_visible(timeout=_TIMEOUT_MS)

        # TICKET-J.8 — abrir um pedido cai na aba do próximo gesto. Sem coleta
        # feita, é Realização.
        expect(pl.locator("#aba-btn-realizacao")).to_have_class(re.compile(r"\bativa\b"))

        item = pl.locator(f"#item-exame-{item_id}")

        # 3b. Coleta.
        item.get_by_role("button", name="Registrar coleta").click()
        expect(item).to_contain_text("Coletado", timeout=_TIMEOUT_MS)

        # 3c. Enviar à bancada (Ticket F). TICKET-J.8 — coletar MOVE o exame de
        # Realização para Bancada: o operador troca de aba porque o trabalho
        # trocou de etapa. O contador da aba é quem avisa que há material lá.
        expect(pl.locator("#aba-count-bancada")).to_have_text("1", timeout=_TIMEOUT_MS)
        pl.locator("#aba-btn-bancada").click()
        expect(item).to_be_visible(timeout=_TIMEOUT_MS)

        pl.once("dialog", lambda d: d.accept("bioquímica"))
        item.get_by_role("button", name="Enviar à bancada").click()
        expect(item).to_contain_text("Na bancada — aguardando laudo", timeout=_TIMEOUT_MS)

        # 3d. Produzir o laudo estruturado (Ticket G).
        pl.get_by_role("button", name="🔬 Produzir laudo", exact=False).click()
        expect(pl.locator("#editor-laudo")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pl.locator("#laudo-rt-cns")).to_have_value(_CNS)
        pl.locator(f"#laudo-resumo-{item_id}").fill("Série vermelha normal")
        pl.locator(f"#laudo-conclusao-{item_id}").select_option("normal")
        pl.locator(f"#laudo-ref-{item_id}").fill("4.5-11.0 mil/mm³")
        pl.get_by_role("button", name="Assinar e liberar ao cidadão").click()

        expect(pl.locator("#feedback-laudo")).to_contain_text(
            "carteira do cidadão", timeout=_TIMEOUT_MS)
        expect(pl.locator("#painel-laudo")).to_contain_text("Liberado", timeout=_TIMEOUT_MS)

        # ── 4. Cidadão recebe e dá ciência (TELA do cidadão, outro contexto) ─
        # A aba da clínica fica ABERTA de propósito: é ela que tem de perceber a
        # ciência acontecendo do outro lado.
        laudos = httpx.get(f"{app_demo}/paciente/laudos",
                           headers=_h(_tok(app_demo, "paciente")), timeout=15.0).json()
        meu = next(l for l in laudos["disponiveis"]
                   if any(i["nome_exame"] == nome_exame for i in l["itens"]))
        proto_laudo = meu["protocolo"]
        assert meu["autor_nome"] == _NOME_PRESCRITOR, "o laudo não saiu no nome do RT"

        ctx_cid2 = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
        try:
            pc2 = ctx_cid2.new_page()
            pc2.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
            abrir_aba_carteira(pc2, "laudos")     # o laudo ganhou porta própria (24/08)
            card_laudo = pc2.locator("#lista-laudos .exame-card", has_text=proto_laudo)
            expect(card_laudo).to_be_visible(timeout=_TIMEOUT_MS)
            # ENG-014 (PR C) — a ciência nasce da ABERTURA (martelo (a)).
            card_laudo.get_by_role("button", name="Abrir laudo").click()
            expect(pc2.locator("#lista-laudos .exame-card", has_text=proto_laudo)
                   ).to_contain_text("Ciência registrada", timeout=_TIMEOUT_MS)
        finally:
            ctx_cid2.close()

        # ── 5a. A ciência reflui à clínica ──────────────────────────────────
        # Na demo isso chega pelo poll de 30s do painel. Aqui a função é chamada
        # direto: o que importa provar é que ela REFLETE o novo estado — o timer
        # é só quando, e esperar 30s no gate seria desperdício.
        pl.evaluate("atualizarPainelLaudo()")
        expect(pl.locator("#painel-laudo")).to_contain_text(
            "Ciência do cidadão", timeout=_TIMEOUT_MS)
    finally:
        ctx_lab.close()

    # ── 5b. Faturamento: dois pagadores, duas contagens ─────────────────────
    # A MESMA produção aparece sob códigos diferentes conforme quem paga —
    # plano de saúde (TUSS) ou SUS (SIGTAP). Classificação e contagem internas:
    # nada é transmitido a operadora nem ao SUS (isso é adapter, depende de G4A).
    por_tuss = {l["codigo_tuss"]: int(l["qtd"]) for l in _csv_faturamento(app_demo, "tuss")}
    por_sigtap = {l["codigo_sigtap"]: int(l["qtd"]) for l in _csv_faturamento(app_demo, "sigtap")}

    assert _TUSS_HEMOGRAMA in por_tuss, por_tuss
    assert _SIGTAP_HEMOGRAMA in por_sigtap, por_sigtap
    # Agregações DISTINTAS (chaves diferentes), mesma produção por baixo.
    assert set(por_tuss) != set(por_sigtap)
    assert sum(por_tuss.values()) == sum(por_sigtap.values())

    # E o valor inválido continua morrendo em 422 (Ticket D).
    tok = _tok(app_demo, "clinica")
    r422 = httpx.get(f"{app_demo}/clinicas/faturamento.csv",
                     params={"agrupar_por": "invalido"},
                     headers={"Authorization": f"Bearer {tok}"}, timeout=15.0)
    assert r422.status_code == 422, r422.text


# ---------------------------------------------------------------------------
# TICKET-I.2 — o critério de faturamento na TELA, não só na URL
# ---------------------------------------------------------------------------

def test_seletor_de_criterio_muda_o_faturamento_baixado(
    page: Page, browser, app_demo, erros_de_console
):
    """O passo 5 da demo é clicável: escolher SIGTAP e baixar tem de trazer o
    CSV do SUS, com o critério até no nome do arquivo — dois "faturamento.csv"
    na pasta de Downloads, contando por tabelas diferentes, seriam
    indistinguíveis."""
    ctx = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        seletor = pg.locator("#faturamento-criterio")
        expect(seletor).to_be_visible(timeout=_TIMEOUT_MS)
        expect(seletor).to_have_value("tuss")          # default preserva o de hoje

        seletor.select_option("sigtap")
        with pg.expect_download(timeout=_TIMEOUT_MS) as baixado:
            pg.get_by_role("button", name="💰 Faturamento").click()
        arquivo = baixado.value
        assert "sigtap" in arquivo.suggested_filename, arquivo.suggested_filename

        conteudo = open(arquivo.path(), encoding="utf-8").read()
        assert conteudo.splitlines()[0].startswith('"codigo_sigtap"'), conteudo[:80]
    finally:
        ctx.close()
