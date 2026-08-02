"""
tests/browser/test_f5_b1_relatorio_botoes.py — Browser-E2E do TICKET-F5-B1 §6
(botões Relatório Consolidado + SNGPC CSV/PDF no cabeçalho da fila).

POR QUE ESTE TESTE EXISTE
-------------------------
O B1 está implementado e mergeado (PR #91), mas o critério de aceite §5 n.9 —
o browser-E2E — nunca foi entregue. Este arquivo fecha essa lacuna (despacho
KIMI3-001 §3.1). A proteção central é contra a regressão histórica: o botão
"Relatório Consolidado" já esteve quebrado (não respondia ao clique —
TICKET-COER2-POS-MERGE-DIAGNOSTICO §6). Se voltar a quebrar, este teste pega.

O QUE PROVA (invariantes do ticket B1 §5)
------------------------------------------
1. Os 3 botões existem NO CABEÇALHO DA FILA (`.fila-card-head .fila-head-acoes`)
   — não "em algum lugar da página" (lição do COER2-POS-MERGE).
2. CSV e PDF baixam via fetch + Bearer (nunca <a href> pro endpoint — PII-
   EXAUSTIVIDADE). O teste intercepta a rede e afirma o header Authorization.
3. "Relatório Consolidado" alimenta o #print-area pela MESMA fonte (o CSV do
   período — uma única query, sem divergência).
4. Isolamento por CNPJ do JWT: trocar para dispensador_norte → CSV sem
   movimento da Farmácia Central.
5. Erro do backend renderiza `detail.mensagem` — nunca `[object Object]`.
6. Guarda estática: `href...relatorio` segue ZERO no dispensador.html.

PADRÃO
------
Segue test_coer2_e2e.py: sessão plantada via sessionStorage (mesma mecânica do
_autoLoginDemo), asserções sobre o DOM RENDERIZADO (não sobre respostas de API
isoladas). A coreografia mínima necessária já existe no seed (DEMO-FILA-0001
garante ao menos uma linha na fila da Farmácia Central).
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect

_TIMEOUT_MS = 15_000

# Personas do seed de demo (seed_demo.py / demo.py::_PERSONAS).
_DISP_CENTRAL = "99999999000191"   # Farmácia Demo Central — tem DEMO-FILA-0001 na fila
_DISP_NORTE = "99999999000272"     # Farmácia Demo Norte — sem movimento (isolamento)

_HTML = Path(__file__).resolve().parents[3] / "dispensador.html"


# ---------------------------------------------------------------------------
# Sessão de demo (mesmo padrão de test_coer2_e2e.py)
# ---------------------------------------------------------------------------

def _login_demo(base_url: str, papel: str) -> dict:
    r = httpx.post(f"{base_url}/demo/login", json={"role": papel}, timeout=10.0)
    r.raise_for_status()
    return r.json()


def _autenticar(page, base_url: str, papel: str) -> None:
    """Planta a sessão demo — equivalente ao que _autoLoginDemo faz sozinho."""
    data = _login_demo(base_url, papel)
    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {data['access_token']!r});
        sessionStorage.setItem('picsaude_demo_role',  {data['role']!r});
        sessionStorage.setItem('picsaude_demo_sub',   {data['sub']!r});
        sessionStorage.setItem('picsaude_demo_nome',  {data['nome']!r});
        """
    )


def _sem_erros(erros: list[str], tela: str, ignorar: tuple[str, ...] = ()) -> None:
    restantes = [e for e in erros if not any(trecho in e for trecho in ignorar)]
    assert not restantes, (
        f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in restantes)
    )


def _abrir_dispensador(page, app_demo: str, papel: str = "dispensador") -> None:
    _autenticar(page, app_demo, papel)
    page.goto(f"{app_demo}/dispensador.html", wait_until="networkidle")
    # A fila saiu do "Carregando fila…" — sem isto, asserções sobre a página
    # passariam por vacuidade durante o bootstrap da sessão.
    expect(page.locator("#fila-lista")).not_to_contain_text(
        "Carregando fila", timeout=_TIMEOUT_MS
    )


def _botoes_da_fila(page):
    """Escopo OBRIGATÓRIO do ticket: o cabeçalho da fila, não a página inteira."""
    return page.locator("#fila-container .fila-card-head .fila-head-acoes")


# ---------------------------------------------------------------------------
# Guarda estática (critério §5 n.4 — PII-EXAUSTIVIDADE)
# ---------------------------------------------------------------------------

def test_b1_sem_href_para_endpoint_relatorio():
    """NUNCA existe <a href> apontando pro endpoint — PII vazaria sem auth."""
    html = _HTML.read_text(encoding="utf-8")
    assert not re.search(r"href[^>]*relatorio", html, re.IGNORECASE), (
        "Encontrado href para endpoint de relatório em dispensador.html — "
        "relatório é PII e exige fetch + Bearer + blob (critério B1 §5 n.4)."
    )


# ---------------------------------------------------------------------------
# Critério §5 n.1 — os 3 botões respondem ao clique (regressão do bug histórico)
# ---------------------------------------------------------------------------

def test_b1_botoes_presentes_no_cabecalho_da_fila(page, app_demo, erros_de_console):
    _abrir_dispensador(page, app_demo)
    head = _botoes_da_fila(page)
    expect(head.get_by_role("button", name="Relatório Consolidado")).to_be_visible()
    expect(head.get_by_role("button", name="SNGPC CSV")).to_be_visible()
    expect(head.get_by_role("button", name="SNGPC PDF")).to_be_visible()
    _sem_erros(erros_de_console, "dispensador.html (B1 — cabeçalho)")


def test_b1_botoes_relatorio_funcionam(page, app_demo, erros_de_console):
    """Os 3 botões no cabeçalho da fila respondem ao clique (B1 §6)."""
    _abrir_dispensador(page, app_demo)

    # Intercepta a rede DEPOIS do bootstrap: só interessam os fetchs disparados
    # pelos cliques (o relatório NUNCA pode ir sem Authorization — PII).
    requisicoes_relatorio: list = []
    page.on(
        "request",
        lambda req: requisicoes_relatorio.append(req)
        if "/dispensadores/relatorio." in req.url
        else None,
    )
    head = _botoes_da_fila(page)

    # ── SNGPC CSV → fetch + Bearer + blob ───────────────────────────────────
    head.get_by_role("button", name="SNGPC CSV").click()
    expect(page.locator("#fila-msg")).to_contain_text(
        "CSV SNGPC baixado", timeout=_TIMEOUT_MS
    )
    reqs_csv = [r for r in requisicoes_relatorio if "relatorio.csv" in r.url]
    assert reqs_csv, "clique em SNGPC CSV não disparou fetch para /dispensadores/relatorio.csv"
    assert all(
        r.headers.get("authorization", "").startswith("Bearer ") for r in reqs_csv
    ), "fetch do CSV saiu sem Bearer (PII-EXAUSTIVIDADE)"

    # ── SNGPC PDF → fetch + Bearer + blob ───────────────────────────────────
    head.get_by_role("button", name="SNGPC PDF").click()
    expect(page.locator("#fila-msg")).to_contain_text(
        "PDF do relatório baixado", timeout=_TIMEOUT_MS
    )
    reqs_pdf = [r for r in requisicoes_relatorio if "relatorio.pdf" in r.url]
    assert reqs_pdf, "clique em SNGPC PDF não disparou fetch para /dispensadores/relatorio.pdf"
    assert all(
        r.headers.get("authorization", "").startswith("Bearer ") for r in reqs_pdf
    ), "fetch do PDF saiu sem Bearer (PII-EXAUSTIVIDADE)"

    # ── Relatório Consolidado → #print-area alimentada pelo MESMO endpoint ──
    # Regressão histórica: este botão já não respondeu ao clique. A asserção é
    # sobre o CONTEÚDO renderizado — um clique morto deixa a área vazia.
    head.get_by_role("button", name="Relatório Consolidado").click()
    area = page.locator("#print-area")
    expect(area).to_contain_text("Relatório Consolidado", timeout=_TIMEOUT_MS)
    expect(area).to_contain_text("Movimentos:", timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B1 — cliques)")


# ---------------------------------------------------------------------------
# Critério §5 n.7 — isolamento por CNPJ do JWT
# ---------------------------------------------------------------------------

def test_b1_isolamento_por_cnpj_do_jwt(page, app_demo, erros_de_console):
    """Trocar JWT (dispensador_norte) → CSV sem movimento da Farmácia Central."""
    # Camada 1 (contrato): o CSV do norte não contém NENHUM movimento — em
    # particular nada da Central (a fila DEMO-FILA-0001 é da Central).
    tok_norte = _login_demo(app_demo, "dispensador_norte")["access_token"]
    r = httpx.get(
        f"{app_demo}/dispensadores/relatorio.csv",
        headers={"Authorization": f"Bearer {tok_norte}"},
        timeout=15.0,
    )
    assert r.status_code == 200, f"relatorio.csv do norte: HTTP {r.status_code}"
    linhas = [l for l in r.text.strip().splitlines() if l.strip()]
    assert len(linhas) <= 1, (
        f"CSV do dispensador_norte veio com {len(linhas) - 1} movimento(s) — "
        "vazou escrituração de outro CNPJ (isolamento por JWT quebrado)."
    )
    assert "DEMO-FILA-0001" not in r.text

    # Camada 2 (DOM renderizado): logado como norte, o clique no SNGPC CSV
    # reporta zero movimentos — a tela reflete o escopo do JWT, não o da Central.
    _abrir_dispensador(page, app_demo, papel="dispensador_norte")
    _botoes_da_fila(page).get_by_role("button", name="SNGPC CSV").click()
    expect(page.locator("#fila-msg")).to_contain_text(
        "0 movimento", timeout=_TIMEOUT_MS
    )
    _sem_erros(erros_de_console, "dispensador.html (B1 — isolamento)")


# ---------------------------------------------------------------------------
# Critério §5 n.8 — erro do backend renderiza detail.mensagem
# ---------------------------------------------------------------------------

def test_b1_erro_do_backend_renderiza_detail_mensagem(page, app_demo, erros_de_console):
    """Falha do endpoint vira mensagem legível — NUNCA `[object Object]`."""
    _autenticar(page, app_demo, "dispensador")
    # Simula a falha do backend na ÚNICA fonte de dados do relatório (o CSV do
    # período alimenta download CSV, contagem do PDF e consolidado).
    page.route(
        "**/dispensadores/relatorio.csv**",
        lambda route: route.fulfill(
            status=422,
            content_type="application/json",
            json={"detail": {"codigo": "periodo_invalido",
                             "mensagem": "Período do relatório inválido no servidor."}},
        ),
    )
    page.goto(f"{app_demo}/dispensador.html", wait_until="networkidle")
    expect(page.locator("#fila-lista")).not_to_contain_text(
        "Carregando fila", timeout=_TIMEOUT_MS
    )

    _botoes_da_fila(page).get_by_role("button", name="SNGPC CSV").click()
    msg = page.locator("#fila-msg")
    expect(msg).to_contain_text(
        "Período do relatório inválido no servidor.", timeout=_TIMEOUT_MS
    )
    assert "[object Object]" not in (msg.inner_text() or ""), (
        "erro do backend renderizou como [object Object] — _extrairMsgErro não aplicado"
    )
    # O 422 mockado é o erro ESPERADO deste cenário — não é defeito da página.
    _sem_erros(erros_de_console, "dispensador.html (B1 — erro)",
               ignorar=("relatorio.csv",))
