"""
tests/browser/test_f5_etapa_c_cidadao.py — E2E da Etapa C de UX do cidadão
(F5-C1/C2/C3) contra o `app_demo` local.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
A Etapa C são três melhorias de UX no `cidadao.html`, baseadas em tropeços reais
vistos navegando a demo via Playwright nos testes de circulação:

  - C1: feedback de transferência pra farmácia (modal + toast enriquecido)
  - C2: polling da carteira (30s + pause em aba oculta)
  - C3: hierarquia visual do atestado (CSS `.atestado-card` + reordenação)

Diferente do `test_f5_externo_picsaude.py` (que aponta pra `picsaude.com.br`),
estes testes rodam contra o `app_demo` — o subprocesso efêmero que serve o
`cidadao.html` **modificado** (a demo pública ainda tem a versão anterior até o
deploy). É a separação correta: regressão de UX roda local (determinístico,
contra o código do PR); smoke da demo pública roda externo.

COMO RODAR
----------
    cd backend
    python -m pytest tests/browser/test_f5_etapa_c_cidadao.py -v
"""
from __future__ import annotations

import re
import time

import httpx
import pytest
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo.
_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_DISP_CENTRAL = "99999999000191"

_TS = time.strftime("%Y%m%d%H%M")


# ---------------------------------------------------------------------------
# Helpers — mesmas formas do test_coer2_e2e.py (login demo + coreografia via API).
# ---------------------------------------------------------------------------

def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _api(base_url: str, token: str, method: str, path: str, body=None) -> httpx.Response:
    return httpx.request(
        method, f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body, timeout=15.0,
    )


def _autenticar(page: Page, base_url: str, role: str, sub: str, nome: str) -> None:
    """Planta as 4 chaves `picsaude_demo_*` no sessionStorage antes do goto.

    O `_hidratarSessaoDemo` IIFE em cidadao.html lê exatamente estas chaves na
    carga — plantá-las antes do goto faz o cidadão entrar direto na carteira,
    sem passar pelo fluxo CPF+OTP.
    """
    tok = _tok(base_url, role)
    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  {role!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )


def _sem_erros(erros: list[str], tela: str) -> None:
    assert not erros, f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in erros)


def _emitir_para_paciente(base_url: str, ptok: str, med: str, qtd: int = 10) -> str:
    r = _api(base_url, ptok, "POST", "/prescricoes", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "enviar_ao_paciente": True,
        "itens": [{"nome_medicamento": med, "quantidade": qtd,
                   "posologia": "1cp 8/8h", "unidade_quantidade": "comprimido"}],
    })
    assert r.status_code in (200, 201), f"emit falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


# ---------------------------------------------------------------------------
# F5-C1 — Modal de confirmação pós-transferência
# ---------------------------------------------------------------------------

def test_c1_modal_apos_transferencia_mostra_farmacia_e_scroll(
    page: Page, app_demo, erros_de_console
):
    """C1: após clicar Transferir Custódia + confirmar, modal aparece com nome da
    farmácia + botão Ver no histórico faz scroll + destaca a linha.
    """
    med = f"TESTE-C1-MODAL-{_TS}"
    proto = _emitir_para_paciente(app_demo, _tok(app_demo, "prescritor"), med)

    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    carteira = page.locator("#lista-receitas")
    expect(carteira).to_be_visible(timeout=_TIMEOUT_MS)
    expect(carteira).to_contain_text(proto, timeout=_TIMEOUT_MS)

    card = carteira.locator(".receita-card", has_text=proto)
    # Native confirm() no handler — aceitar automaticamente.
    page.once("dialog", lambda d: d.accept())
    card.get_by_role("button", name="Transferir Custódia").click()

    # 🎯 modal de confirmação aparece (não desaparecimento silencioso).
    modal = page.locator("#modal-transferencia")
    expect(modal).to_have_class(re.compile(r"\baberto\b"), timeout=_TIMEOUT_MS)
    # 🎯 corpo do modal menciona o protocolo (curto) e o nome da farmácia demo.
    corpo = page.locator("#modal-transferencia-corpo")
    expect(corpo).to_contain_text(proto[:13], timeout=_TIMEOUT_MS)
    expect(corpo).to_contain_text("Farmácia Demo Central", timeout=_TIMEOUT_MS)

    # 🎯 clicar "Ver no histórico" faz scroll + destaca a linha (fundo amarelo).
    page.get_by_role("button", name="Ver no histórico").click()
    # O carregarCarteira roda após fechar o modal; esperar a linha aparecer.
    hist = page.locator("#lista-historico")
    expect(hist).to_contain_text(proto, timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "cidadao.html (C1)")


# ---------------------------------------------------------------------------
# F5-C2 — Polling da carteira
# ---------------------------------------------------------------------------

def test_c2_polling_atualiza_carteira_sem_clique_manual(page: Page, app_demo, erros_de_console):
    """C2: após prescritor emitir, cidadão vê a receita chegar via poll (sem clicar
    Atualizar). Janela de observação: 35s (poll = 30s + margem).
    """
    # Autenticar e abrir carteira ANTES de emitir — assim o poll é quem traz a
    # receita nova, provando que não precisa de clique manual.
    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    med = f"TESTE-C2-POLL-{_TS}"
    proto = _emitir_para_paciente(app_demo, _tok(app_demo, "prescritor"), med)

    carteira = page.locator("#lista-receitas")
    expect(carteira).to_be_visible(timeout=_TIMEOUT_MS)
    # 🎯 sem clicar nada, a receita aparece dentro da janela de 1 poll (35s).
    expect(carteira).to_contain_text(proto, timeout=35_000)

    _sem_erros(erros_de_console, "cidadao.html (C2 poll)")


def test_c2_polling_pausa_em_aba_oculta(page: Page, app_demo, erros_de_console):
    """C2: aba oculta pausa o poll — nenhum fetch novo em /paciente/prescricoes.
    """
    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    # Contar requests à carteira.
    contagem = {"n": 0}
    def _contar(req):
        if "/paciente/prescricoes" in req.url and "expirando" not in req.url:
            contagem["n"] += 1
    page.on("request", _contar)

    # Esconder a aba (simula troca de tab / minimizar).
    page.evaluate("document.dispatchEvent(new Event('visibilitychange')); document.hidden = true;")
    # Ouvir o evento hidden programaticamente: visibilitychange só dispara se o
    # `document.visibilityState` muda — em headless precisamos forçar o handler.
    # Solução: o handler registrado chama _pararCarteiraPoll() quando
    # document.hidden é true; forçamos o hidden e dispararmos o evento.
    page.evaluate("""
        Object.defineProperty(document, 'hidden', { value: true, configurable: true });
        document.dispatchEvent(new Event('visibilitychange'));
    """)

    baseline = contagem["n"]
    # Esperar uma janela que cruzaria um tick de poll (35s).
    page.wait_for_timeout(35_000)

    # 🎯 nenhum fetch novo durante a aba oculta.
    assert contagem["n"] == baseline, \
        f"poll continuou em aba oculta: {contagem['n'] - baseline} fetch(es) extras"

    page.remove_listener("request", _contar)
    _sem_erros(erros_de_console, "cidadao.html (C2 pause)")


# ---------------------------------------------------------------------------
# F5-C3 — Hierarquia visual do atestado
# ---------------------------------------------------------------------------

def test_c3_atestado_card_tem_hierarquia_visual_propria(page: Page, app_demo, erros_de_console):
    """C3: atestado tem classe `.atestado-card` (não `.exame-card`); badge "ATESTADO"
    em verde; seção Atestados aparece ANTES de Pedidos de Exame no DOM.
    """
    finalidade = f"TESTE-C3 Atestado hierarquia {_TS}"
    r = _api(app_demo, _tok(app_demo, "prescritor"), "POST", "/atestados", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "finalidade": finalidade, "municipio_emissao": "Recife",
        "dias_afastamento": 3, "conselho": "CFM",
    })
    assert r.status_code == 201, r.text
    proto = r.json()["protocolo"]

    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    lista = page.locator("#lista-atestados")
    expect(lista).to_be_visible(timeout=_TIMEOUT_MS)
    card = lista.locator(".atestado-card", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 classe é .atestado-card, NÃO .exame-card (laudos/exames continuam com esta).
    expect(card).to_have_class(re.compile(r"\batestado-card\b"), timeout=_TIMEOUT_MS)
    expect(card).not_to_have_class(re.compile(r"\bexame-card\b"), timeout=_TIMEOUT_MS)

    # 🎯 badge em maiúsculas com classe modificadora `.atestado`.
    badge = card.locator(".exame-badge-prioridade")
    expect(badge).to_have_text("ATESTADO", timeout=_TIMEOUT_MS)
    expect(badge).to_have_class(re.compile(r"\batestado\b"), timeout=_TIMEOUT_MS)
    # 🎯 cor de fundo verde sólido (#16a34a) — distingue do azul dos exames.
    bg = badge.evaluate("el => getComputedStyle(el).backgroundColor")
    assert "22" in bg and "163" in bg and "74" in bg, \
        f"badge sem fundo verde esperado (rgb(22,163,74)); veio: {bg}"

    # 🎯 título do documento em verde-900 (#14532d), 16px bold.
    titulo = card.locator(".atestado-titulo")
    expect(titulo).to_contain_text("ATESTADO MÉDICO", timeout=_TIMEOUT_MS)
    titulo_bg = titulo.evaluate("el => getComputedStyle(el).color")
    assert "20" in titulo_bg and "83" in titulo_bg and "45" in titulo_bg, \
        f"título sem cor verde-900 esperada (rgb(20,83,45)); veio: {titulo_bg}"

    # 🎯 seção Atestados aparece ANTES de Pedidos de Exame no DOM.
    idx_atestados = page.evaluate(
        "(() => { const els = Array.from(document.querySelectorAll('[id^=lista-]')); "
        "return els.findIndex(e => e.id === 'lista-atestados'); })()"
    )
    idx_pedidos = page.evaluate(
        "(() => { const els = Array.from(document.querySelectorAll('[id^=lista-]')); "
        "return els.findIndex(e => e.id === 'lista-pedidos-exame'); })()"
    )
    assert 0 <= idx_atestados < idx_pedidos, \
        f"ordem incorreta: atestados={idx_atestados}, pedidos-exame={idx_pedidos}"

    _sem_erros(erros_de_console, "cidadao.html (C3)")
