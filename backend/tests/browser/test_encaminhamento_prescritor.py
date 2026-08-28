"""
tests/browser/test_encaminhamento_prescritor.py — ENG-016 PR 2 (`module`).

AS REGRAS QUE ESTE ARQUIVO GUARDA
---------------------------------
§3 e §5 do `DESENHO-ENCAMINHAMENTO-UX.md`:

  · **abas por CHAPÉU** — o mesmo profissional é origem de uns e destino de
    outros, e as perguntas são diferentes;
  · **§2 lei 1 — lista por DEVER, selo por POSSE**: `atendido` é dever do
    destino com posse no cidadão. Se a tela listasse por custódia, o item
    sumiria exatamente quando vira obrigação;
  · **§5 — a confirmação mostra o DOCUMENTO MONTADO**, não o formulário: a
    última coisa que o médico vê é o documento como o destino vai lê-lo, e é
    isso que o hash congela.

O QUE FICA PARA O PR 3
----------------------
O ciclo COMPLETO das três sessões (AC vi) precisa do gesto `entregar` na
carteira do cidadão, que é entrega do PR 3. Aqui o `entregar` é feito pela API,
para que o percurso do prescritor possa ser exercido inteiro — e o E2E de três
personas nasce no PR 3, com a tela do cidadão pronta.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_encaminhamento_prescritor.py -v
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

# Personas canônicas do seed (config.js DEMO.* / seed_demo.py / demo.py).
_CNS_ORIGEM  = "980001112223334"
_CNS_DESTINO = "980001112223335"
_CPF         = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"

_TS = time.strftime("%H%M%S")


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _h(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _ctx_prescritor(browser, base_url: str, role: str, cns: str, nome: str):
    ctx = browser.new_context()
    tok = _tok(base_url, role)
    ctx.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'prescritor');
        sessionStorage.setItem('picsaude_demo_sub',   {cns!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )
    return ctx


def _nova_pagina(ctx) -> tuple[Page, list[str]]:
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda exc: erros.append(f"pageerror: {exc}"))
    return pg, erros


def _abrir_submodulo(pg: Page, base_url: str):
    pg.goto(f"{base_url}/prescritor.html", wait_until="networkidle")
    pg.locator("#submod-btn-encaminhamento").click()
    expect(pg.locator("#submod-encaminhamento")).to_be_visible(timeout=_TIMEOUT_MS)


def _emitir_pela_api(base_url: str, justificativa: str) -> str:
    r = httpx.post(f"{base_url}/encaminhamentos", headers=_h(_tok(base_url, "prescritor")), json={
        "cns_prescritor": _CNS_ORIGEM, "nome_prescritor": "Dra. Demo Maria Souza",
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "cns_destino": _CNS_DESTINO, "especialidade_destino": "CARDIOLOGIA",
        "finalidade": "avaliacao", "justificativa_clinica": justificativa,
        "itens": [{"especialidade": "CARDIOLOGIA"}],
    }, timeout=15.0)
    assert r.status_code == 201, r.text
    return r.json()["protocolo"]


# ===========================================================================
# §5 — a confirmação mostra o documento montado
# ===========================================================================

def test_a_confirmacao_mostra_o_documento_e_nao_o_formulario(browser, app_demo):
    """A regra que dá sentido ao hash: o médico confirma o DOCUMENTO.

    O cabeçalho gerado ("Encaminho o(a) paciente X para Y em Z") aparece na
    revisão — e fora de qualquer caixa de texto editável, senão viraria prosa
    que se apaga sem querer e o documento perderia a frase que o define.
    """
    ctx = _ctx_prescritor(browser, app_demo, "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)

        # M-D: #enc-pac-nome/#enc-pac-cpf vêm travados (readonly) no cidadão
        # canônico — já são _NOME_PACIENTE/_CPF, sem precisar preencher.
        pg.select_option("#enc-finalidade", "segunda_opiniao")
        pg.select_option("#enc-especialidade", "CARDIOLOGIA")
        pg.fill("#enc-cns-destino", _CNS_DESTINO)
        pg.fill("#enc-justificativa", f"dor toracica aos esforcos ha tres meses {_TS}")
        pg.click("#form-enc-main button[type=submit]")

        doc = pg.locator("#enc-doc-corpo")
        expect(doc).to_be_visible(timeout=_TIMEOUT_MS)
        expect(doc).to_contain_text("Encaminho o(a) paciente")
        expect(doc).to_contain_text(_NOME_PACIENTE)
        expect(doc).to_contain_text("Segunda opinião")
        expect(doc).to_contain_text("CARDIOLOGIA")
        # o formulário SAIU de cena: a última coisa vista é o documento
        expect(pg.locator("#form-enc-main")).to_be_hidden()
        assert not erros, erros
    finally:
        ctx.close()


def test_justificativa_curta_nao_passa_e_a_tela_diz_por_que(browser, app_demo):
    """§5: justificativa OBRIGATÓRIA. A tela conhece o contrato do backend
    (`justificativa_clinica` é NOT NULL) e não oferece versão mais permissiva.
    Nada de validação semântica fingida — só comprimento, dito em voz alta."""
    ctx = _ctx_prescritor(browser, app_demo, "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)
        # M-D: #enc-pac-nome/#enc-pac-cpf vêm travados (readonly) no cidadão
        # canônico — já são _NOME_PACIENTE/_CPF, sem precisar preencher.
        pg.select_option("#enc-finalidade", "avaliacao")
        pg.select_option("#enc-especialidade", "CARDIOLOGIA")
        pg.fill("#enc-cns-destino", _CNS_DESTINO)
        pg.fill("#enc-justificativa", "curta")
        pg.click("#form-enc-main button[type=submit]")

        expect(pg.locator("#enc-status-msg")).to_contain_text(
            "obrigatória", timeout=_TIMEOUT_MS)
        expect(pg.locator("#enc-revisao")).to_be_hidden()
        assert not erros, erros
    finally:
        ctx.close()


def test_emitir_pela_tela_entrega_a_carteira_do_cidadao(browser, app_demo):
    """O caminho inteiro pela tela — e a prova de que a posse nasce no cidadão."""
    ctx = _ctx_prescritor(browser, app_demo, "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)
        # M-D: #enc-pac-nome/#enc-pac-cpf vêm travados (readonly) no cidadão
        # canônico — já são _NOME_PACIENTE/_CPF, sem precisar preencher.
        pg.select_option("#enc-finalidade", "avaliacao")
        pg.select_option("#enc-especialidade", "CARDIOLOGIA")
        pg.fill("#enc-cns-destino", _CNS_DESTINO)
        pg.fill("#enc-justificativa", f"avaliacao cardiologica de rotina {_TS}")
        pg.click("#form-enc-main button[type=submit]")
        pg.click("#btn-enc-confirmar")

        expect(pg.locator("#enc-status-msg")).to_contain_text(
            "entregue à carteira", timeout=_TIMEOUT_MS)
        # e a aba Encaminhados assume, com o selo de posse no cidadão
        expect(pg.locator("#enc-aba-encaminhados")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#enc-lista-encaminhados")).to_contain_text("com o cidadão")
        assert not erros, erros
    finally:
        ctx.close()


def test_remarcar_pela_tela_e_o_mesmo_botao(browser, app_demo):
    """Remarcação é RE-ATO (mini-desenho de 24/08): mesmo gesto, mesmo
    endpoint, nenhum objeto novo.

    O que muda na tela é o RÓTULO — "Agendar" vira "Remarcar" quando já há
    data. Dizer "consulta marcada" numa remarcação deixaria o operador em
    dúvida se criou uma segunda.
    """
    proto = _emitir_pela_api(app_demo, f"remarcar {_TS}")
    ctx = _ctx_prescritor(browser, app_demo, "prescritor_destino", _CNS_DESTINO,
                          "Dr. Demo Carlos Andrade")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)
        pg.click("#enc-aba-btn-recebidos")
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)

        # 1ª vez: Agendar
        expect(cartao.get_by_role("button", name="Agendar")).to_be_visible()
        pg.once("dialog", lambda d: d.accept("2026-11-03 09:00"))
        cartao.get_by_role("button", name="Agendar").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("Consulta marcada",
                                                              timeout=_TIMEOUT_MS)

        # 2ª vez: o MESMO botão, agora Remarcar
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao.get_by_role("button", name="Remarcar")).to_be_visible(timeout=_TIMEOUT_MS)
        pg.once("dialog", lambda d: d.accept("2026-11-10 15:30"))
        cartao.get_by_role("button", name="Remarcar").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("remarcada",
                                                              timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()

    # e o cidadão vê a data NOVA
    r = httpx.get(f"{app_demo}/paciente/encaminhamentos",
                  headers=_h(_tok(app_demo, "paciente")), timeout=15.0).json()
    item = next(x for x in r["ativos"] if x["protocolo"] == proto)
    assert item["data_consulta"].startswith("2026-11-10"), (
        f"a carteira ficou na data antiga: {item['data_consulta']}"
    )


# ===========================================================================
# §3 / §2 lei 1 — abas por chapéu; lista por dever, selo por posse
# ===========================================================================

def test_o_destino_ve_o_que_chegou_e_a_origem_ve_o_que_mandou(browser, app_demo):
    proto = _emitir_pela_api(app_demo, f"chapeu duplo {_TS}")

    ctx_o = _ctx_prescritor(browser, app_demo, "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _nova_pagina(ctx_o)
        _abrir_submodulo(pg, app_demo)
        pg.click("#enc-aba-btn-encaminhados")
        expect(pg.locator("#enc-lista-encaminhados")).to_contain_text(proto, timeout=_TIMEOUT_MS)
        pg.click("#enc-aba-btn-recebidos")
        expect(pg.locator("#enc-lista-chegou")).not_to_contain_text(proto)
        assert not erros, erros
    finally:
        ctx_o.close()

    ctx_d = _ctx_prescritor(browser, app_demo, "prescritor_destino", _CNS_DESTINO, "Dr. Demo Carlos Andrade")
    try:
        pg, erros = _nova_pagina(ctx_d)
        _abrir_submodulo(pg, app_demo)
        pg.click("#enc-aba-btn-recebidos")
        expect(pg.locator("#enc-lista-chegou")).to_contain_text(proto, timeout=_TIMEOUT_MS)
        pg.click("#enc-aba-btn-encaminhados")
        expect(pg.locator("#enc-lista-encaminhados")).not_to_contain_text(proto)
        assert not erros, erros
    finally:
        ctx_d.close()


def test_atendido_continua_visivel_ao_destino_com_a_posse_no_cidadao(browser, app_demo):
    """O CASO QUE DÁ NOME À LEI Nº 1, na tela.

    Depois de atender, o documento volta ao cidadão — e o destino passa a DEVER
    a contrarreferência. Uma tela que listasse por custódia perderia o item no
    exato momento em que ele vira obrigação.
    """
    proto = _emitir_pela_api(app_demo, f"dever sem posse {_TS}")
    td = _tok(app_demo, "prescritor_destino")
    # A máquina exige `agendado` antes de `atendido` — o §1a mudou QUEM move a
    # posse, não o percurso clínico. Agendar não move posse; entregar move.
    assert httpx.post(f"{app_demo}/encaminhamentos/{proto}/agendar",
                      headers=_h(td), json={"data_agendamento": "2026-09-20T10:00:00"},
                      timeout=15.0).status_code == 200
    assert httpx.post(f"{app_demo}/encaminhamentos/{proto}/entregar",
                      headers=_h(_tok(app_demo, "paciente")), timeout=15.0).status_code == 200
    assert httpx.post(f"{app_demo}/encaminhamentos/{proto}/atender",
                      headers=_h(td), timeout=15.0).status_code == 200

    ctx = _ctx_prescritor(browser, app_demo, "prescritor_destino", _CNS_DESTINO, "Dr. Demo Carlos Andrade")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)
        pg.click("#enc-aba-btn-recebidos")

        gaveta = pg.locator("#enc-lista-devo")
        expect(gaveta).to_contain_text(proto, timeout=_TIMEOUT_MS)
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_contain_text("com o cidadão")          # POSSE
        expect(cartao).to_contain_text("você deve a contrarreferência")  # DEVER
        expect(cartao.get_by_role("button", name="Contrarreferir")).to_be_visible()
        assert not erros, erros
    finally:
        ctx.close()


def test_o_ciclo_fecha_com_a_ciencia_explicita_da_origem(browser, app_demo):
    """§2 lei 7 — divergência deliberada do laudo: aqui a ciência é um ATO.

    No laudo, abrir é dar ciência (ENG-014). No encaminhamento, o fato é a
    origem declarar-se ciente do retorno e FECHAR o ciclo. Cada objeto nomeia o
    seu fato — e é por isso que existe um botão, e não uma inferência.
    """
    proto = _emitir_pela_api(app_demo, f"ciclo completo {_TS}")
    td = _tok(app_demo, "prescritor_destino")
    httpx.post(f"{app_demo}/encaminhamentos/{proto}/agendar", headers=_h(td),
               json={"data_agendamento": "2026-09-20T10:00:00"}, timeout=15.0)
    httpx.post(f"{app_demo}/encaminhamentos/{proto}/entregar",
               headers=_h(_tok(app_demo, "paciente")), timeout=15.0)
    httpx.post(f"{app_demo}/encaminhamentos/{proto}/atender", headers=_h(td), timeout=15.0)
    assert httpx.post(f"{app_demo}/encaminhamentos/{proto}/contrarreferir",
                      headers=_h(td), json={"conteudo_clinico": "avaliado; conduta ajustada"},
                      timeout=15.0).status_code == 201

    ctx = _ctx_prescritor(browser, app_demo, "prescritor", _CNS_ORIGEM, "Dra. Demo Maria Souza")
    try:
        pg, erros = _nova_pagina(ctx)
        _abrir_submodulo(pg, app_demo)
        pg.click("#enc-aba-btn-encaminhados")
        cartao = pg.locator(f"#enc-card-{proto}")
        expect(cartao).to_be_visible(timeout=_TIMEOUT_MS)
        pg.once("dialog", lambda d: d.accept())
        cartao.get_by_role("button", name="Dar ciência e encerrar").click()
        expect(pg.locator("#enc-status-msg")).to_contain_text("encerrado", timeout=_TIMEOUT_MS)
        assert not erros, erros
    finally:
        ctx.close()

    r = httpx.get(f"{app_demo}/encaminhamentos/{proto}",
                  headers=_h(_tok(app_demo, "prescritor")), timeout=15.0)
    assert r.json()["status"] == "encerrado"
