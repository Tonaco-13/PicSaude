"""
tests/browser/test_eng017_last_mile.py — ENG-017 PR A.

O QUE SÓ A TELA PROVA
---------------------
A comissão de diagnóstico (#189) mostrou que sete dos nove atritos eram a mesma
coisa: **o fato aconteceu no banco e não apareceu na tela**. A integração prova
que os campos chegam; só aqui se prova que o cidadão CONSEGUE chegar ao fim do
percurso — que era, literalmente, o que faltava.

  · **S3** — o pedido morria em `resultado_disponivel` porque o gesto de
    ciência não tinha botão. Atrito medido pela comissão: **infinito**.
  · **S1+S4** — o cartão CITAVA "Laudos / Resultados" pelo nome e não levava.
  · **S2** — a agenda da clínica identificava por nome, com o CPF chegando do
    backend e sendo descartado na renderização.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_eng017_last_mile.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import abrir_aba_carteira

_TIMEOUT_MS = 15_000
_CNS = "980001112223334"
_CPF = "12345678909"
_NOME = "João Demo da Silva"
_CNPJ_CLINICA = "11222333000181"
_TS = time.strftime("%H%M%S")


def _tok(u, r):
    resp = httpx.post(f"{u}/demo/login", json={"role": r}, timeout=10.0)
    resp.raise_for_status()
    return resp.json()["access_token"]


def _h(t): return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _ctx(browser, u, role, papel, sub, nome):
    ctx = browser.new_context()
    tok = _tok(u, role)
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {papel!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _pagina(ctx):
    pg = ctx.new_page()
    erros = []
    pg.on("pageerror", lambda e: erros.append(f"pageerror: {e}"))
    return pg, erros


def _pedido_ate_resultado(u, com_laudo: bool) -> tuple[str, str | None]:
    tp, tc, tl = _tok(u, "prescritor"), _tok(u, "paciente"), _tok(u, "clinica")
    r = httpx.post(f"{u}/pedidos-exame", headers=_h(tp), json={
        "cns_prescritor": _CNS, "nome_prescritor": "Dra. Demo Maria Souza",
        "cpf_paciente": _CPF, "nome_paciente": _NOME, "enviar_ao_paciente": True,
        "itens": [{"nome_exame": f"HEMOGRAMA-{_TS}", "quantidade": 1}]}, timeout=15.0)
    proto = r.json()["protocolo"]
    httpx.post(f"{u}/pedidos-exame/{proto}/transferir-laboratorio", headers=_h(tc),
               json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
               timeout=15.0)
    item = httpx.get(f"{u}/pedidos-exame/{proto}", headers=_h(tl), timeout=15.0).json()["itens"][0]["id"]
    httpx.post(f"{u}/pedidos-exame/{proto}/itens/{item}/coletar", headers=_h(tl), json={}, timeout=15.0)
    httpx.post(f"{u}/pedidos-exame/{proto}/itens/{item}/resultado", headers=_h(tl),
               json={"resultado_resumo": "sem alterações"}, timeout=15.0)
    if not com_laudo:
        return proto, None
    rl = httpx.post(f"{u}/laudos", headers=_h(tl), json={
        "cns_autor": _CNS, "nome_autor": "RT", "cpf_paciente": _CPF, "nome_paciente": _NOME,
        "pedido_protocolo": proto,
        "itens": [{"pedido_item_id": item, "nome_exame": f"HEMOGRAMA-{_TS}",
                   "conclusao": "normal", "resultado_resumo": "sem alterações"}]}, timeout=15.0)
    lp = rl.json()["protocolo"]
    httpx.post(f"{u}/laudos/{lp}/assinar", headers=_h(tl), json={}, timeout=15.0)
    httpx.post(f"{u}/laudos/{lp}/liberar", headers=_h(tl), json={}, timeout=15.0)
    return proto, lp


# ===========================================================================
# S3 — o percurso ganha fim
# ===========================================================================

def test_o_cidadao_fecha_o_ciclo_do_exame_pela_tela(browser, app_demo):
    """O atrito que a comissão mediu como INFINITO: o gesto era inalcançável.

    Antes deste PR não havia botão nenhum — `POST /encerrar` existia, aceitava
    `paciente`, e nenhuma das três telas o chamava. Todo pedido da vitrine
    parava em `resultado_disponivel`.
    """
    proto, _ = _pedido_ate_resultado(app_demo, com_laudo=True)
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")

        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        expect(cartao).to_contain_text("Resultado disponível")

        botao = cartao.get_by_role("button", name="Confirmo ciência do resultado")
        expect(botao).to_be_visible()
        pg.once("dialog", lambda d: d.accept())
        botao.click()
        expect(pg.locator("#picsaude-toast")).to_contain_text("Ciência registrada",
                                                             timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()

    r = httpx.get(f"{app_demo}/pedidos-exame/{proto}",
                  headers=_h(_tok(app_demo, "prescritor")), timeout=15.0)
    assert r.json()["status"] == "encerrado", "a ciência não chegou ao objeto"


def test_a_confirmacao_avisa_o_que_vai_acontecer(browser, app_demo):
    """Encerrar é terminal, e ciência declarada sem querer não se desfaz. A
    tela diz o que vai acontecer ANTES — e promete que o laudo fica."""
    proto, _ = _pedido_ate_resultado(app_demo, com_laudo=True)
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME)
    try:
        pg, erros = _pagina(ctx)
        textos = []
        pg.on("dialog", lambda d: (textos.append(d.message), d.dismiss()))
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")
        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        cartao.get_by_role("button", name="Confirmo ciência do resultado").click()
        pg.wait_for_timeout(500)
        assert textos, "não houve confirmação"
        assert "encerra" in textos[0]
        assert "laudo continua" in textos[0], (
            "a confirmação não promete que o laudo fica — e a tela promete isso "
            "ao lado do botão"
        )
        assert not erros, erros
    finally:
        ctx.close()

    # dismiss → nada aconteceu
    r = httpx.get(f"{app_demo}/pedidos-exame/{proto}",
                  headers=_h(_tok(app_demo, "prescritor")), timeout=15.0)
    assert r.json()["status"] == "resultado_disponivel"


# ===========================================================================
# S1 + S4 — o elo, e o recebimento visível
# ===========================================================================

def test_do_cartao_do_exame_ate_o_laudo_em_um_clique(browser, app_demo):
    """O que a comissão mediu: ler a frase, memorizar o nome da seção e rolar.
    Agora é um clique — e o destino é realçado, senão seria só rolar sozinho."""
    proto, lp = _pedido_ate_resultado(app_demo, com_laudo=True)
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")

        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao).to_contain_text("O laudo deste exame já está com você",
                                       timeout=_TIMEOUT_MS)
        cartao.get_by_role("button", name="Ver laudo").click()
        expect(pg.locator(f"#laudo-card-{lp}")).to_be_visible(timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_o_recebimento_do_laudo_aparece_no_cartao(browser, app_demo):
    """R2-lite — o handoff que já era fato e não era mostrado.

    Distinto de "Liberado em", que é a data do documento: um é o ato do
    laboratório, o outro é a chegada às mãos do cidadão.
    """
    _, lp = _pedido_ate_resultado(app_demo, com_laudo=True)
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")
        expect(pg.locator(f"#laudo-card-{lp}")).to_contain_text("Chegou a você em",
                                                                timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()


def test_sem_laudo_o_cartao_explica_em_vez_de_prometer(browser, app_demo):
    """`resultado_disponivel` sem laudo liberado: o cidadão precisa saber que
    falta um passo do laboratório — e não ver um link que não leva a nada."""
    proto, _ = _pedido_ate_resultado(app_demo, com_laudo=False)
    ctx = _ctx(browser, app_demo, "paciente", "paciente", _CPF, _NOME)
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        abrir_aba_carteira(pg, "exames")
        cartao = pg.locator(".exame-card", has_text=proto)
        expect(cartao).to_contain_text("O laudo é liberado pelo laboratório",
                                       timeout=_TIMEOUT_MS)
        expect(cartao.get_by_role("button", name="Ver laudo")).to_have_count(0)
        assert not erros, erros
    finally:
        ctx.close()


# ===========================================================================
# S2 — a chave, na agenda
# ===========================================================================

def test_a_agenda_da_clinica_mostra_o_CPF(browser, app_demo):
    """A Regra Zero ancora o objeto ao CPF; a agenda identificava por nome.

    O dado já vinha do backend (`paciente.cpf` na fila) e era descartado na
    renderização — dois pacientes homônimos no mesmo dia eram indistinguíveis.
    """
    tp, tc, tl = _tok(app_demo, "prescritor"), _tok(app_demo, "paciente"), _tok(app_demo, "clinica")
    r = httpx.post(f"{app_demo}/pedidos-exame", headers=_h(tp), json={
        "cns_prescritor": _CNS, "nome_prescritor": "Dra. Demo Maria Souza",
        "cpf_paciente": _CPF, "nome_paciente": _NOME, "enviar_ao_paciente": True,
        "itens": [{"nome_exame": f"AGENDA-CPF-{_TS}", "quantidade": 1}]}, timeout=15.0)
    proto = r.json()["protocolo"]
    httpx.post(f"{app_demo}/pedidos-exame/{proto}/transferir-laboratorio", headers=_h(tc),
               json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
               timeout=15.0)
    assert httpx.post(f"{app_demo}/agendamentos", headers=_h(tl), json={
        "pedido_protocolo": proto, "org_id": "clinica-demo",
        "unidade_id": "DEMO-LAB", "data_hora": "2026-11-05T09:00:00"},
        timeout=15.0).status_code in (200, 201)

    ctx = _ctx(browser, app_demo, "clinica", "dispensador", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg, erros = _pagina(ctx)
        pg.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        pg.locator("#aba-btn-agendamento").click()
        linha = pg.locator("#lista-agenda-unidade .agenda-linha", has_text=proto)
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha).to_contain_text(_NOME)
        expect(linha).to_contain_text("CPF")
        expect(linha).to_contain_text(_CPF)
        assert not erros, erros
    finally:
        ctx.close()
