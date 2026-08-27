"""
tests/browser/test_recepcao_tres_decisoes.py — ENG-015, PR 2 (`module`).

AS REGRAS QUE ESTE ARQUIVO GUARDA
---------------------------------
`DESENHO-AGENDAMENTOS-UX.md`, §2 e §3 (martelo do Fabiano, 23/08):

  §2 — Recepção: **Agendar · Coletar agora · Não realizamos**, três decisões
  num só lugar ("Coletar agora" é o rótulo desde o MARTELO 27/08, PR 2 do
  desenho de circulação — era "Executar agora"). "Não realizamos" SAIU da
  Realização, que ficou, então, com um gesto só — e foi exatamente por
  sobrar um gesto só, já disponível na própria Recepção, que a Realização
  foi DISSOLVIDA (MARTELO 27/08, PR B, mesmo desenho, §2.2). Sobre item já
  `agendado`, a recusa é **ato composto**: cancela a agenda E devolve a posse
  — dois fatos, dois eventos.

  §3 — a agenda da unidade responde "o que está marcado?" **sem** exigir um
  pedido em foco; "Registrar falta" só depois da hora marcada; empty state por
  pergunta.

POR QUE PELO NAVEGADOR
----------------------
`tests/integration/test_agendamento_ato_composto_e_valvula.py` prova o backend:
os dois eventos, o motivo no ledger, a válvula do §6. O que só a tela prova é
que o operador CONSEGUE fazer isso — que as três decisões existem onde o §2 as
colocou, que um clique dispara os dois fatos na ordem certa, e que a agenda
aparece antes de qualquer busca.

GUARDA DE RUMO (o arquiteto foi explícito): "Coletar agora" é a COLETA DIRETA
do J.7 — `pendente → coletado`, UM evento. A sugestão externa de "agendamento
instantâneo" (criar+confirmar+realizar) foi REJEITADA: inventaria três fatos
para um ato que não teve compromisso. `test_executar_agora_e_um_fato_so` é essa
rejeição virada teste; a guarda estática correspondente está em
`tests/unit/test_frontend_recepcao_decisoes.py`.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_recepcao_tres_decisoes.py -v
"""
from __future__ import annotations

import contextlib
import time

import httpx
from playwright.sync_api import expect, Page

from tests.browser.conftest import preencher_modal_fato

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (config.js DEMO.* / seed_demo.py).
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


def _ctx_lab(browser, base_url: str):
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


def _nova_pagina(ctx) -> tuple[Page, list[str]]:
    pg = ctx.new_page()
    erros: list[str] = []
    pg.on("pageerror", lambda exc: erros.append(f"pageerror: {exc}"))
    return pg, erros


@contextlib.contextmanager
def _responder_dialogos(page: Page, prompt_text: str | None = None):
    """Aceita a sequência prompt→confirm dos gestos de recusa."""
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


def _no_laboratorio(base_url: str, sufixo: str, quantos: int = 1) -> str:
    """Emite ao cidadão e entrega ao laboratório — o pedido chega `pendente`."""
    r = httpx.post(
        f"{base_url}/pedidos-exame",
        headers=_h(_tok(base_url, "prescritor")),
        json={
            "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
            "enviar_ao_paciente": True,
            "itens": [{"nome_exame": f"REC-{sufixo}-{i}-{_TS}", "quantidade": 1}
                      for i in range(quantos)],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), r.text
    proto = r.json()["protocolo"]

    t = httpx.post(
        f"{base_url}/pedidos-exame/{proto}/transferir-laboratorio",
        headers=_h(_tok(base_url, "paciente")),
        json={"cnpj_laboratorio": _CNPJ_CLINICA, "nome_laboratorio": "Clínica Demo"},
        timeout=15.0,
    )
    assert t.status_code in (200, 201), t.text
    return proto


def _agendar(base_url: str, proto: str, data_hora: str) -> str:
    r = httpx.post(
        f"{base_url}/agendamentos",
        headers=_h(_tok(base_url, "clinica")),
        json={"pedido_protocolo": proto, "org_id": "clinica-demo",
              "unidade_id": "DEMO-LAB", "data_hora": data_hora},
        timeout=15.0,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["protocolo"]


def _pedido(base_url: str, proto: str) -> dict:
    r = httpx.get(f"{base_url}/pedidos-exame/{proto}",
                  headers=_h(_tok(base_url, "clinica")), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()


def _pedido_pelo_prescritor(base_url: str, proto: str) -> dict:
    """Depois da devolução, o LABORATÓRIO não lê mais o pedido (403 de posse —
    é o comportamento certo, e é a prova de que a devolução aconteceu). Quem
    ainda enxerga é o prescritor, dono do pedido."""
    r = httpx.get(f"{base_url}/pedidos-exame/{proto}",
                  headers=_h(_tok(base_url, "prescritor")), timeout=15.0)
    assert r.status_code == 200, r.text
    return r.json()


def _eventos(base_url: str, proto: str) -> list[str]:
    return [e["tipo_evento"] for e in _pedido_pelo_prescritor(base_url, proto).get("eventos", [])]


def _abrir_pela_fila(pg: Page, base_url: str, proto: str):
    pg.goto(f"{base_url}/clinica.html", wait_until="networkidle")
    fila = pg.locator("#fila-lista")
    expect(fila).to_contain_text(proto, timeout=_TIMEOUT_MS)
    return fila.locator(".fila-item", has_text=proto)


# ===========================================================================
# §2 — as três decisões da Recepção (a Realização foi dissolvida, PR B)
# ===========================================================================

def test_a_recepcao_e_a_unica_casa_do_item_pendente(browser, app_demo):
    """A geometria do §2, agora numa casa só.

    MARTELO 27/08 (PR B, DESENHO-CIRCULACAO-CLINICA-CASAS.md §2.2) — SUPERA
    `test_a_recepcao_oferece_as_tres_decisoes_e_a_realizacao_so_coleta`
    (removido, não só afrouxado). Aquele teste provava que o mesmo item
    `pendente` aparecia em DUAS listas ao mesmo tempo (Recepção e Realização)
    e que só a Recepção tinha a recusa. A regra que importava nunca foi
    "onde a recusa NÃO está" — era que a Realização era cópia redundante da
    Recepção. Dissolvida ela, a prova vira o oposto: o item `pendente` só
    existe numa casa, com as três decisões juntas, e o namespace da Bancada
    (`item-exame-N`, sem duplicar `item-recep-exame-N`) nem chega a existir
    enquanto o item não sai de `pendente`.
    """
    proto = _no_laboratorio(app_demo, "TRES")
    item_id = _pedido(app_demo, proto)["itens"][0]["id"]

    ctx = _ctx_lab(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        _abrir_pela_fila(pg, app_demo, proto).click()

        pg.locator("#aba-btn-recepcao").click()
        na_recepcao = pg.locator(f"#item-recep-exame-{item_id}")
        expect(na_recepcao).to_be_visible(timeout=_TIMEOUT_MS)
        expect(na_recepcao.get_by_role("button", name="Agendar")).to_be_visible()
        expect(na_recepcao.get_by_role("button", name="Coletar agora")).to_be_visible()
        expect(na_recepcao.get_by_role("button", name="Não realizamos este exame")).to_be_visible()

        # A aba Realização não existe mais — este é o teste de ausência.
        expect(pg.locator("#aba-btn-realizacao")).to_have_count(0)
        expect(pg.locator(f"#item-exame-{item_id}")).to_have_count(0)
        assert not erros_js, erros_js
    finally:
        ctx.close()


def test_executar_agora_e_um_fato_so(browser, app_demo):
    """A GUARDA DE RUMO, virada teste.

    "Coletar agora" é a coleta direta do J.7: `pendente → coletado`, UM
    evento `pedido_coletado`, sem compromisso nenhum. A proposta externa de
    "agendamento instantâneo" (criar + confirmar + realizar) foi rejeitada —
    inventaria três fatos para um ato que não teve compromisso, o fantasma do
    `pedido_agendado` que o martelo do J.7 matou.

    Este teste conta os eventos. Se um dia a tela passar a criar agendamento
    para coletar, o ledger cresce e ele cai.
    """
    proto = _no_laboratorio(app_demo, "DIRETO")
    item_id = _pedido(app_demo, proto)["itens"][0]["id"]
    antes = _eventos(app_demo, proto)

    ctx = _ctx_lab(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        _abrir_pela_fila(pg, app_demo, proto).click()
        pg.locator("#aba-btn-recepcao").click()
        alvo = pg.locator(f"#item-recep-exame-{item_id}")
        expect(alvo).to_be_visible(timeout=_TIMEOUT_MS)
        alvo.get_by_role("button", name="Coletar agora").click()
        expect(pg.locator(f"#item-recep-exame-{item_id}")).to_have_count(
            0, timeout=_TIMEOUT_MS)
        assert not erros_js, erros_js
    finally:
        ctx.close()

    depois = _eventos(app_demo, proto)
    novos = depois[len(antes):]
    assert novos == ["pedido_coletado"], (
        f"a coleta direta deixou de ser UM fato: {novos}"
    )
    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "coletado"


def test_nao_realizamos_sobre_agendado_e_ato_composto(browser, app_demo):
    """§2 pela tela: um gesto do operador, DOIS fatos no ledger.

    O compromisso cai e a posse volta ao cidadão. Se só o primeiro
    acontecesse, o item ficaria "livre no papel, preso na prática" — o exame
    sem agenda e a custódia ainda aqui, e o cidadão sem poder levá-lo a outro
    laboratório.
    """
    proto = _no_laboratorio(app_demo, "COMPOSTO")
    _agendar(app_demo, proto, "2026-11-10T09:00:00")
    assert _pedido(app_demo, proto)["itens"][0]["status_item"] == "agendado"

    ctx = _ctx_lab(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        cartao = _abrir_pela_fila(pg, app_demo, proto)
        # ENG-019 PR 6 — o motivo deixou de ser `prompt()` nativo: agora é o
        # modal `#modal-fato`, que valida conteúdo. O `confirm()` de escopo que
        # vem em seguida continua nativo, e por isso o handler permanece.
        with _responder_dialogos(pg):
            cartao.get_by_role("button", name="Não realizamos").click()
            preencher_modal_fato(pg, "não realizamos nesta unidade")
            expect(pg.locator("#fila-lista")).not_to_contain_text(
                proto, timeout=_TIMEOUT_MS)
        assert not erros_js, erros_js
    finally:
        ctx.close()

    # O laboratório já não alcança o pedido — a posse saiu dele, e o 403 é
    # parte da prova. A leitura é pelo prescritor.
    assert httpx.get(f"{app_demo}/pedidos-exame/{proto}",
                     headers=_h(_tok(app_demo, "clinica")),
                     timeout=15.0).status_code == 403

    pedido = _pedido_pelo_prescritor(app_demo, proto)
    assert pedido["itens"][0]["status_item"] == "pendente", (
        "cancelar devolve o item a `pendente` — devolver é posse, não clínica"
    )
    assert "custodia_transferida" in _eventos(app_demo, proto)

    # A prova que interessa ao cidadão: o exame voltou para a carteira dele,
    # sob a custódia dele, pronto para ir a outro laboratório. É o que o §2
    # existe para garantir — sem o segundo fato, ele ficaria sem agenda e sem
    # o exame na mão.
    carteira = httpx.get(f"{app_demo}/paciente/pedidos-exame",
                         headers=_h(_tok(app_demo, "paciente")), timeout=15.0).json()
    meus = [p for p in carteira.get("posse", []) if p["protocolo"] == proto]
    assert meus, "o pedido não voltou à carteira do cidadão"
    assert meus[0]["itens"][0]["detentor"] == "paciente", (
        "o segundo fato não aconteceu: a agenda caiu e a custódia ficou no laboratório"
    )


# ===========================================================================
# §3 — a agenda da unidade
# ===========================================================================

def test_a_agenda_da_unidade_aparece_sem_pedido_em_foco(browser, app_demo):
    """A pergunta "o que está marcado?" não pode exigir um protocolo na mão.

    Antes, a aba Agendamento sem foco dizia só "nenhum pedido em foco" — quem
    chegava de manhã para ver o dia não tinha o que ver.
    """
    proto = _no_laboratorio(app_demo, "AGENDA")
    _agendar(app_demo, proto, "2026-12-01T10:30:00")

    ctx = _ctx_lab(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)
        pg.goto(f"{app_demo}/clinica.html", wait_until="networkidle")
        # sem buscar nada, sem clicar em pedido nenhum
        pg.locator("#aba-btn-agendamento").click()

        linha = pg.locator("#lista-agenda-unidade .agenda-linha", has_text=proto)
        expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
        expect(linha).to_contain_text("DEMO-LAB")
        # E o aviso de "nenhum pedido em foco" está de pé ao lado dela: a
        # agenda responde "o que está marcado?", o aviso responde por que o
        # painel do compromisso está vazio. Duas perguntas, dois textos (§3).
        expect(pg.locator("#vazio-agendamento")).to_be_visible()

        linha.get_by_role("button", name="Abrir").click()
        expect(pg.locator("#card-agendamento")).to_be_visible(timeout=_TIMEOUT_MS)
        expect(pg.locator("#pedido-foco-texto")).to_contain_text(proto)
        assert not erros_js, erros_js
    finally:
        ctx.close()


def test_registrar_falta_so_depois_da_hora(browser, app_demo):
    """§3 — antes da hora marcada a falta não é fato, é adivinhação.

    Trava de UX e declarada como tal: o endpoint segue permissivo. O teste usa
    dois compromissos — um no futuro, um no passado — porque um botão sempre
    desabilitado passaria na metade fácil do teste.
    """
    futuro = _no_laboratorio(app_demo, "FUTURO")
    _agendar(app_demo, futuro, "2027-06-01T08:00:00")
    passado = _no_laboratorio(app_demo, "PASSADO")
    _agendar(app_demo, passado, "2020-01-15T08:00:00")

    ctx = _ctx_lab(browser, app_demo)
    try:
        pg, erros_js = _nova_pagina(ctx)

        _abrir_pela_fila(pg, app_demo, futuro).click()
        pg.locator("#aba-btn-agendamento").click()
        botao_futuro = pg.locator("#conteudo-agendamento").get_by_role(
            "button", name="Registrar falta")
        expect(botao_futuro).to_be_visible(timeout=_TIMEOUT_MS)
        expect(botao_futuro).to_be_disabled()

        _abrir_pela_fila(pg, app_demo, passado).click()
        pg.locator("#aba-btn-agendamento").click()
        botao_passado = pg.locator("#conteudo-agendamento").get_by_role(
            "button", name="Registrar falta")
        expect(botao_passado).to_be_visible(timeout=_TIMEOUT_MS)
        expect(botao_passado).to_be_enabled()
        assert not erros_js, erros_js
    finally:
        ctx.close()
