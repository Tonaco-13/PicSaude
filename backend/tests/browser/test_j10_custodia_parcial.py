"""
tests/browser/test_j10_custodia_parcial.py — TICKET-J.10 (`module`), AC (v).

A REGRA QUE ESTE ARQUIVO GUARDA
-------------------------------
DESENHO-J10-CUSTODIA-PARCIAL-EXAMES §0 (Fabiano):

  > Laboratório que retém o pedido inteiro inviabiliza, em outro laboratório,
  > os exames que ele não realiza.

Dois mecanismos, e este smoke exerce OS DOIS pela tela, ponta a ponta:

  1. transferência PARCIAL — o cidadão marca 2 de 3 itens e entrega só eles;
  2. devolução de não-realizável — a unidade devolve 1 item por item.

POR QUE UM SMOKE, SE A INTEGRAÇÃO JÁ COBRE
------------------------------------------
`tests/integration/test_pedidos_exame_custodia_parcial.py` prova as regras no
backend. O que ela NÃO consegue provar é onde o J.10 mais arrisca:

  · a carteira desenhando caixas de seleção POR ITEM — e enviando só os
    marcados ("nenhum marcado = todos", §3.6);
  · a fila da clínica mostrando o pedido com SÓ os itens da unidade — o
    anti-vazamento (AC vi) é invisível para a integração da FILA se a tela
    buscar o pedido inteiro por outro caminho;
  · o botão "Não realizamos este exame" tirando o item da tela porque ele
    saiu da custódia — não porque a tela o escondeu por conta própria.

    > **Superseded em 23/08 (ENG-015 §2, martelo do Fabiano):** o botão MUDOU
    > DE ABA — saiu da Realização e foi para a Recepção, onde vivem as três
    > decisões da triagem (Agendar · Coletar agora · Não realizamos — o
    > segundo rótulo unificado no MARTELO 27/08, PR 2; era "Executar agora").
    > Recusar
    > não é etapa de execução: quem recusa não vai coletar. O que este teste
    > guarda não mudou uma vírgula — o item some da tela porque saiu da
    > CUSTÓDIA —, só o lugar de onde se clica. O cartão da Recepção tem id
    > próprio (`item-recep-exame-N`) porque o mesmo item aparece nas duas
    > listas, e id repetido é HTML inválido.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_j10_custodia_parcial.py -v
"""
from __future__ import annotations

import time
from contextlib import contextmanager

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira, preencher_modal_fato

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (config.js DEMO.* / seed_demo.py).
_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"
_CNPJ_OUTRO_LAB = "98765432000110"

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


def _emitir_varios(base_url: str, nomes: list[str]) -> str:
    """Emite pedido multi-item JÁ na carteira do cidadão — o caminho da vitrine."""
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers=_h(_tok(base_url, "prescritor")),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": n, "quantidade": 1} for n in nomes],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _cartao(base_url: str, proto: str) -> dict:
    """Cartão do pedido na carteira do cidadão (API) — itens com posse por item."""
    r = httpx.get(
        f"{base_url}/paciente/pedidos-exame",
        headers=_h(_tok(base_url, "paciente")), timeout=15.0,
    )
    assert r.status_code == 200, r.text
    todos = [*r.json()["posse"], *r.json()["em_andamento"], *r.json()["historico"]]
    return next(p for p in todos if p["protocolo"] == proto)


def _por_nome(base_url: str, proto: str) -> dict[str, dict]:
    return {i["nome_exame"]: i for i in _cartao(base_url, proto)["itens"]}


@contextmanager
def _responder_dialogos(page: Page, prompt_text: str | None = None):
    """Aceita a sequência prompt→confirm do gesto de devolução.

    O `remove_listener` no finally importa: sem ele, o handler aceitaria
    diálogos de passos seguintes (o confirm da transferência, por exemplo)
    antes da hora — o teste passaria por motivo errado.
    """
    def _handler(dialog):
        if dialog.type == "prompt":
            dialog.accept(prompt_text or "")
        else:
            dialog.accept()

    page.on("dialog", _handler)
    try:
        yield
    finally:
        page.remove_listener("dialog", _handler)


# ===========================================================================
# AC (v) — E2E: cidadão transfere 2 de 3 → clínica vê 2 e devolve 1 →
# cidadão re-envia o devolvido a OUTRO laboratório.
# ===========================================================================

def test_parcial_e_devolucao_pelas_telas(browser, app_demo, erros_de_console):
    nomes = [f"J10-HEMOG-{_TS}", f"J10-GLICO-{_TS}", f"J10-TSH-{_TS}"]
    proto = _emitir_varios(app_demo, nomes)

    # ── 1. cidadão marca 2 de 3 e transfere só eles (§3.6) ──────────────────
    ctx_cid = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc = ctx_cid.new_page()
        pc.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pc, "exames")
        card = pc.locator("#lista-pedidos-exame .exame-card", has_text=proto)
        expect(card).to_be_visible(timeout=_TIMEOUT_MS)

        for nome in nomes[:2]:
            card.locator("li", has_text=nome).locator("input.chk-exame-item").check()

        pc.once("dialog", lambda d: d.accept())
        card.get_by_role("button", name="Transferir Custódia").click()
        expect(pc.locator("#modal-transferencia")).to_contain_text(
            "itens marcados", timeout=_TIMEOUT_MS)
    finally:
        ctx_cid.close()

    # Backend confirma o que a tela disse: 2 com a clínica, 1 com o cidadão,
    # e NENHUM item mudou de estado (J.7 segue valendo na parcial).
    itens = _por_nome(app_demo, proto)
    assert itens[nomes[0]]["detentor"] == _CNPJ_CLINICA
    assert itens[nomes[1]]["detentor"] == _CNPJ_CLINICA
    assert itens[nomes[2]]["detentor"] == "paciente"
    assert itens[nomes[2]]["sob_minha_custodia"] is True
    assert all(i["status_item"] == "pendente" for i in itens.values())
    id_hemog = itens[nomes[0]]["id"]
    id_tsh = itens[nomes[2]]["id"]

    # ── 2. bancada: pedido na fila com SÓ os 2 itens dela; devolve 1 ────────
    ctx_lab = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pl = ctx_lab.new_page()
        pl.goto(f"{app_demo}/clinica.html", wait_until="networkidle")

        fila = pl.locator("#fila-lista")
        expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
        fila.locator(".fila-item", has_text=proto).click()

        # AC (vi) na tela: o item que ficou com o cidadão NÃO aparece — a
        # unidade não vê (nem aciona) exame que está com outro.
        #
        # MARTELO 27/08 (PR B) — item `pendente` só mora na Recepção agora
        # (`item-recep-exame-N`); a Realização, que também o mostrava, foi
        # dissolvida. O anti-vazamento continua provado numa lista só, porque
        # só sobrou uma.
        expect(pl.locator(f"#item-recep-exame-{id_tsh}")).to_have_count(0)
        item_hemog_recepcao = pl.locator(f"#item-recep-exame-{id_hemog}")
        expect(item_hemog_recepcao).to_be_visible(timeout=_TIMEOUT_MS)
        expect(item_hemog_recepcao).to_contain_text("Pendente")

        # §0.2: "o laboratório devolve, por item, o que não performa".
        #
        # ENG-015 §2 — a recusa passou a ser gesto de RECEPÇÃO. É a mesma
        # devolução pura de sempre (`/devolver`, J.10); mudou a aba de onde se
        # clica, não o que acontece.
        pl.locator("#aba-btn-recepcao").click()
        # ENG-019 PR 6 — o motivo saiu do `prompt()` nativo e virou o modal
        # `#modal-fato`, que valida conteúdo. O `confirm()` de escopo que vem em
        # seguida continua nativo, e por isso o handler permanece.
        with _responder_dialogos(pl):
            item_hemog_recepcao.get_by_role("button", name="Não realizamos este exame").click()
            preencher_modal_fato(pl, "Não realizamos este exame na unidade")
            # O item sai da lista porque saiu da CUSTÓDIA da unidade (§3.6) —
            # a re-carga devolve o conjunto filtrado pela posse.
            expect(pl.locator(f"#item-recep-exame-{id_hemog}")).to_have_count(
                0, timeout=_TIMEOUT_MS)
    finally:
        ctx_lab.close()

    # Backend: devolvido segue `pendente` e voltou ao cidadão; o colega da
    # unidade e o item do cidadão não foram tocados.
    itens2 = _por_nome(app_demo, proto)
    assert itens2[nomes[0]]["detentor"] == "paciente"
    assert itens2[nomes[0]]["sob_minha_custodia"] is True
    assert itens2[nomes[1]]["detentor"] == _CNPJ_CLINICA
    assert itens2[nomes[2]]["detentor"] == "paciente"
    assert all(i["status_item"] == "pendente" for i in itens2.values())

    # ── 3. cidadão re-envia o devolvido a OUTRO laboratório (§0.1) ──────────
    ctx_cid2 = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pc2 = ctx_cid2.new_page()
        pc2.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pc2, "exames")
        card2 = pc2.locator("#lista-pedidos-exame .exame-card", has_text=proto)
        expect(card2).to_be_visible(timeout=_TIMEOUT_MS)

        card2.locator("li", has_text=nomes[0]).locator("input.chk-exame-item").check()
        pc2.locator(f"#cnpj-lab-{proto}").fill(_CNPJ_OUTRO_LAB)
        pc2.once("dialog", lambda d: d.accept())
        card2.get_by_role("button", name="Transferir Custódia").click()
        expect(pc2.locator("#modal-transferencia")).to_contain_text(
            "itens marcados", timeout=_TIMEOUT_MS)
    finally:
        ctx_cid2.close()

    itens3 = _por_nome(app_demo, proto)
    assert itens3[nomes[0]]["detentor"] == _CNPJ_OUTRO_LAB
    assert itens3[nomes[1]]["detentor"] == _CNPJ_CLINICA
    assert itens3[nomes[2]]["detentor"] == "paciente"
    assert all(i["status_item"] == "pendente" for i in itens3.values())
