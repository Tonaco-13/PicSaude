"""
tests/browser/test_abas_j8_j9.py — TICKET-J.8 / J.9 (DESPACHO-ENG-011 §6, §7).

O QUE ESTE ARQUIVO GUARDA
-------------------------
As abas são retrabalho de UI, mas mexem em ONDE cada gesto do ciclo mora. As
guardas estáticas (`tests/unit/test_frontend_abas_j8_j9.py`) provam que a regra
continua escrita; estes smokes provam que a tela continua NAVEGÁVEL — que o
operador percorre Recepção → Agendamento → Realização → Bancada sem perder o
pedido de vista, e que o cidadão alcança os três tipos de objeto.

AC do §6: "operador circula pelas 4 abas cobrindo o ciclo completo na vitrine".
AC do §7: "cidadão vê e opera os 3 tipos de objeto nas abas".

O que NÃO está aqui, de propósito: o ciclo clínico ponta a ponta (coleta →
bancada → laudo → ciência) já é guardado por `test_demo_lab_e2e.py`, que passou
a atravessar as abas. Repeti-lo aqui só tornaria o gate lento sem cobrir nada
novo — o mesmo critério do TICKET-F.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_abas_j8_j9.py -v
"""
from __future__ import annotations

import re
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

_TS = time.strftime("%Y%m%d%H%M%S")
_ATIVA = re.compile(r"\bativa\b")
# Os CARTÕES da carteira usam a classe `ativo` (masculino: é um cartão, não uma
# aba). As abas da clínica seguem com `ativa` — não foram tocadas por este
# ticket, e por isso as duas constantes convivem.
_ATIVO_SUBMOD = re.compile(r"\bativo\b")


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


def _pedido_no_laboratorio(base_url: str, nome_exame: str, *, coletar: bool) -> tuple[str, int]:
    """Emite, entrega ao laboratório e (opcionalmente) coleta — tudo pela API.

    O caminho de TELA até aqui já é guardado por `test_exame_transferencia_
    cidadao.py`; o que interessa neste arquivo é o estado em que o pedido chega
    às abas.
    """
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
    proto = r.json()["protocolo"]

    rt = httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(_tok(base_url, "paciente")),
        json={"cnpj_laboratorio": _CNPJ_CLINICA}, timeout=15.0,
    )
    assert rt.status_code in (200, 201), f"transferência falhou: {rt.status_code} {rt.text}"

    ltok = _tok(base_url, "clinica")
    item_id = httpx.get(f"{base_url}/pedidos-exame/{proto}", headers=_h(ltok),
                        timeout=15.0).json()["itens"][0]["id"]
    if coletar:
        rc = httpx.post(f"{base_url}/pedidos-exame/{proto}/itens/{item_id}/coletar",
                        headers=_h(ltok), json={}, timeout=15.0)
        assert rc.status_code in (200, 201), f"coleta falhou: {rc.status_code} {rc.text}"
    return proto, item_id


def _abrir_da_fila(pg: Page, base_url: str, proto: str) -> None:
    pg.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    fila = pg.locator("#fila-lista")
    expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
    fila.locator(".fila-item", has_text=proto).click()
    expect(pg.locator("#pedido-foco")).to_be_visible(timeout=_TIMEOUT_MS)


# ===========================================================================
# J.8 — as 4 abas do laboratório
# ===========================================================================

def test_operador_circula_pelas_quatro_abas_sem_perder_o_pedido(
    page: Page, browser, app_demo, erros_de_console
):
    """AC §6 — o ciclo inteiro é alcançável, e o pedido em foco acompanha."""
    proto, _ = _pedido_no_laboratorio(app_demo, f"HEMOGRAMA-ABAS-{_TS}", coletar=False)

    ctx = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()
        _abrir_da_fila(pg, app_demo, proto)

        # A faixa do pedido em foco é o que permite sair da Recepção sem se
        # perder: ela vive ACIMA das abas e nomeia paciente + protocolo.
        expect(pg.locator("#pedido-foco-texto")).to_contain_text(_NOME_PACIENTE)
        expect(pg.locator("#pedido-foco-texto")).to_contain_text(proto)

        # MARTELO 27/08 — "aguardando" entrou no ciclo (DESENHO-CIRCULACAO-
        # CLINICA-CASAS.md §2.3).
        abas = ("recepcao", "agendamento", "realizacao", "bancada", "aguardando")
        for aba in abas:
            pg.locator(f"#aba-btn-{aba}").click()
            expect(pg.locator(f"#aba-{aba}")).to_be_visible(timeout=_TIMEOUT_MS)
            expect(pg.locator(f"#aba-btn-{aba}")).to_have_class(_ATIVA)
            # Uma aba por vez — e o pedido nunca some de vista.
            for outra in abas:
                if outra != aba:
                    expect(pg.locator(f"#aba-{outra}")).to_be_hidden()
            expect(pg.locator("#pedido-foco")).to_be_visible()
    finally:
        ctx.close()


def test_abrir_pedido_cai_na_aba_do_proximo_gesto(
    page: Page, browser, app_demo, erros_de_console
):
    """Sem coleta feita → Realização. Já coletado → Bancada.

    Abrir um pedido e cair numa aba vazia obrigaria o operador a caçar o
    trabalho. O critério é o percurso, não o nome do estado — é o que mantém a
    escolha válida se o J.7 mexer no `agendado`.
    """
    proto_novo, _ = _pedido_no_laboratorio(app_demo, f"NOVO-{_TS}", coletar=False)
    proto_col, item_col = _pedido_no_laboratorio(app_demo, f"COLETADO-{_TS}", coletar=True)

    ctx = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()

        _abrir_da_fila(pg, app_demo, proto_novo)
        expect(pg.locator("#aba-btn-realizacao")).to_have_class(_ATIVA)
        # MARTELO 27/08 (PR 2) — rótulo unificado; era "Registrar coleta".
        expect(pg.locator("#lista-realizacao")).to_contain_text("Coletar agora")
        expect(pg.locator("#aba-count-realizacao")).to_have_text("1")
        expect(pg.locator("#aba-count-bancada")).to_have_text("0")

        _abrir_da_fila(pg, app_demo, proto_col)
        expect(pg.locator("#aba-btn-bancada")).to_have_class(_ATIVA)
        expect(pg.locator(f"#item-exame-{item_col}")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#aba-count-bancada")).to_have_text("1")
        expect(pg.locator("#aba-count-realizacao")).to_have_text("0")
    finally:
        ctx.close()


def test_nova_busca_devolve_a_recepcao_e_avisa_as_abas_vazias(
    page: Page, browser, app_demo, erros_de_console
):
    """Soltar o pedido não pode deixar as outras abas mostrando restos dele."""
    proto, _ = _pedido_no_laboratorio(app_demo, f"SOLTAR-{_TS}", coletar=False)

    ctx = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()
        _abrir_da_fila(pg, app_demo, proto)

        pg.locator("#aba-btn-recepcao").click()
        pg.get_by_role("button", name="← Nova busca").click()

        expect(pg.locator("#pedido-foco")).to_be_hidden(timeout=_TIMEOUT_MS)
        expect(pg.locator("#aba-btn-recepcao")).to_have_class(_ATIVA)

        for aba, card in (("agendamento", "card-agendamento"),
                          ("realizacao", "card-realizacao"),
                          ("bancada", "card-bancada"),
                          ("aguardando", "card-aguardando")):
            pg.locator(f"#aba-btn-{aba}").click()
            expect(pg.locator(f"#vazio-{aba}")).to_be_visible(timeout=_TIMEOUT_MS)
            expect(pg.locator(f"#{card}")).to_be_hidden()
            # CONSULTA-UX-001/NC-2, MARTELO 27/08 (PR 4) — "0" sem pedido em
            # foco era mentira: dizia "nada aqui" quando o certo era "não sei,
            # ninguém está olhando". As quatro casas que só sabem contar o
            # pedido em foco mostram o traço, nunca zero, quando soltas.
            expect(pg.locator(f"#aba-count-{aba}")).to_have_text("—")
    finally:
        ctx.close()


def test_403_de_posse_nao_derruba_a_sessao(
    page: Page, browser, app_demo, erros_de_console
):
    """§1 — 403 é posse, não sessão. E a agenda do PRÓPRIO pedido agora abre.

    ENG-015 (PR 1) reescreveu este teste porque a REGRA mudou. Antes,
    `GET /pedidos-exame/{p}/agendamentos` recusava o papel `dispensador` em
    bloco — e era esse o "403 mais fácil de provocar na vitrine" que o teste
    usava, com o pedido que a própria clínica DETINHA. Ou seja: o caso era
    fácil porque era um defeito.

    Agora o teste cobre as duas metades de verdade:

      1. a unidade que DETÉM vê a agenda do pedido (o que este ticket entrega);
      2. um 403 de posse REAL — buscar pedido de outra unidade — não derruba a
         sessão (o que o teste sempre guardou).

    A regra "nenhum 403 vai para `handleUnauthorized`" segue travada também no
    estático, em `tests/unit/test_frontend_abas_j8_j9.py`.
    """
    proto, _ = _pedido_no_laboratorio(app_demo, f"POSSE-{_TS}", coletar=False)

    ctx = _ctx(browser, app_demo, "clinica", _CNPJ_CLINICA, "Clínica Demo")
    try:
        pg = ctx.new_page()
        alertas: list[str] = []
        pg.on("dialog", lambda d: (alertas.append(d.message), d.dismiss()))

        # ── 1. a agenda do pedido PRÓPRIO abre ──────────────────────────────
        _abrir_da_fila(pg, app_demo, proto)
        pg.locator("#aba-btn-agendamento").click()

        # Sem compromisso ainda: o vazio HONESTO, e não o aviso de vedação que
        # este ticket matou.
        expect(pg.locator("#conteudo-agendamento")).to_contain_text(
            "Nenhum agendamento ativo", timeout=_TIMEOUT_MS)
        expect(pg.locator("#conteudo-agendamento")).not_to_contain_text("não ao laboratório")
        expect(pg.get_by_role("button", name="+ Agendar exame")).to_be_visible()

        # ── 2. 403 de posse REAL não derruba a sessão ───────────────────────
        # Devolver ao cidadão tira a posse da clínica — daí em diante o pedido
        # é "de outra unidade" do ponto de vista dela, e buscá-lo dá 403.
        alheio, item_alheio = _pedido_no_laboratorio(app_demo, f"ALHEIO-{_TS}", coletar=False)
        rdev = httpx.post(
            f"{app_demo}/pedidos-exame/{alheio}/itens/{item_alheio}/devolver",
            headers=_h(_tok(app_demo, "clinica")),
            json={"motivo": "sai da nossa custodia para o teste"}, timeout=15.0,
        )
        assert rdev.status_code == 200, rdev.text
        # A busca vive na Recepção — voltar à aba antes de usá-la.
        pg.locator("#aba-btn-recepcao").click()
        pg.fill("#busca-protocolo", alheio)
        pg.get_by_role("button", name="Buscar").click()
        pg.wait_for_timeout(1200)

        assert not alertas, f"403 de posse disparou alerta de sessão: {alertas}"
        expect(pg.locator("#tela-dashboard")).to_be_visible()
        expect(pg.locator("#tela-login")).to_be_hidden()
    finally:
        ctx.close()


def test_cidadao_alcanca_os_tres_tipos_de_objeto_nas_abas(
    page: Page, browser, app_demo, erros_de_console
):
    """AC §7 — receita, exames e atestado, cada um na sua aba."""
    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)

        # A carteira trocou a BARRA DE ABAS pelos CARTÕES-TÍTULO (decisão do
        # Fabiano, 24/08): os seletores viraram `#submod-*`. A asserção é a
        # mesma — um painel por vez, com o título certo, e contadores que dizem
        # a verdade. Nada foi afrouxado; e o conjunto ganhou LAUDOS, que saiu de
        # dentro de Exames e agora tem porta própria.
        #
        # Receita abre por padrão: é o objeto mais frequente da carteira.
        expect(pg.locator("#submod-btn-receita")).to_have_class(_ATIVO_SUBMOD)

        esperado = {
            "receita":  "Histórico de Prescrições",
            "exames":   "Pedidos de Exame Ativos",
            "laudos":   "Laudos / Resultados",
            "atestado": "Atestados",
        }
        for aba, titulo in esperado.items():
            pg.locator(f"#submod-btn-{aba}").click()
            painel = pg.locator(f"#submod-{aba}")
            expect(painel).to_be_visible(timeout=_TIMEOUT_MS)
            expect(painel).to_contain_text(titulo)
            for outra in esperado:
                if outra != aba:
                    expect(pg.locator(f"#submod-{outra}")).to_be_hidden()

        # O seed traz um atestado e um pedido de exame — os contadores dizem a
        # verdade sobre o que há, sem o cidadão precisar abrir cada porta.
        expect(pg.locator("#submod-count-atestado")).not_to_have_text("0")
        expect(pg.locator("#submod-count-exames")).not_to_have_text("0")
    finally:
        ctx.close()


def test_atualizar_serve_as_tres_abas(page: Page, browser, app_demo, erros_de_console):
    """O botão recarrega a carteira inteira (`carregarCarteira`), então vive
    junto da navegação — e não dentro de um submódulo, o que faria parecer que
    só aquele é atualizado.

    A regra sobreviveu à troca de abas por CARTÕES-TÍTULO (24/08): o botão
    continua fora da grade, e a porta escolhida continua sobrevivendo à
    recarga. Só os seletores mudaram.
    """
    ctx = _ctx(browser, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    try:
        pg = ctx.new_page()
        pg.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        expect(pg.locator("#tela-carteira")).to_be_visible(timeout=_TIMEOUT_MS)

        for aba in ("receita", "exames", "laudos", "atestado"):
            pg.locator(f"#submod-btn-{aba}").click()
            expect(pg.locator("#btn-refresh")).to_be_visible()

        pg.locator("#btn-refresh").click()
        expect(pg.locator("#refresh-text")).to_have_text("Atualizado!", timeout=_TIMEOUT_MS)
        # A porta escolhida sobrevive à recarga.
        expect(pg.locator("#submod-btn-atestado")).to_have_class(_ATIVO_SUBMOD)
        expect(pg.locator("#submod-atestado")).to_be_visible()
    finally:
        ctx.close()
