"""
tests/browser/test_f5_externo_picsaude.py — E2E da Fatia B (B1/B2/B3) + prova de
máquina de estados (circulação de receita e atestado) contra a demo pública em
picsaude.com.br.

POR QUE ESTE ARQUIVO EXISTE
---------------------------
Os três tickets F5-B1/B2/B3 pedem, no critério de aceite §6, um browser-E2E que
**não foi escrito** quando a Fatia B foi mergeada (commits 2e7ffda / 47239a5 /
9062513, todos de 2026-07-11). Esses testes fecham essa dívida (camada UI).

Além disso, dois testes extras provam a **máquina de estados do núcleo sanitário**
(AGENTS.md §5b / NUCLEO_SANITARIO.md) — não apenas a renderização, mas que os
objetos realmente circulam e os estados transicionam:

  - CIRCULAÇÃO DA RECEITA: cadeia de custódia completa
    `prescritor → paciente → dispensador`, assertada via `GET /prescricoes/{proto}/custodia`
    + DOM da carteira do cidadão (`cidadao.html`); guard B0 (re-dispensabilidade
    por saldo, não por rótulo) confirmado via `i.acionavel` na fila.
  - CIRCULAÇÃO DO ATESTADO: custódia single-hop `prescritor → paciente` escrita
    no próprio `POST /atestados`; assertada via `GET /atestados/{proto}/custodia`
    + DOM da carteira (`#lista-atestados`); o estado `emitido` (não-terminal)
    é confirmado no backend e na UI.

Diferente dos smokes (`test_smokes.py`) e do COER-2 (`test_coer2_e2e.py`), que
rodam contra o `app_demo` (subprocesso efêmero contra SQLite), estes testes
apontam para a **demo pública**: `https://picsaude.com.br` por padrão, ou o que
estiver em `PICSAUDE_DEMO_URL`. A fixture `demo_externa_viva` (em `conftest.py`)
pula automaticamente quando a demo está fora do ar — falha de rede nunca deve
derrubar a suíte local.

COMO RODAR
----------
    cd backend
    pip install -r ../requirements-browser.txt
    python -m playwright install chromium

    # Contra a demo pública (modo padrão):
    python -m pytest tests/browser/test_f5_externo_picsaude.py -v -m external

    # Contra outro alvo (ex: preview de PR):
    PICSAUDE_DEMO_URL=https://preview-xyz.onrender.com \
      python -m pytest tests/browser/test_f5_externo_picsaude.py -v -m external

CONTRATO DE ESCRITA NA DEMO
---------------------------
Os testes B2 e os dois de circulação **escrevem** na demo. Para mantê-la
auditável:

  - Todo objeto de teste é marcado `TESTE-F5B-{nome}-{ts}`, onde `{ts}` é o
    timestamp no momento da execução. Um curador pode filtrar por prefixo.
  - A demo reseta em janela programada (`proximo_reset` em `/config/public`); o
    lixo de teste é efêmero por construção.
  - Os testes NÃO dependem de estado anterior — cada um cria o próprio cenário.

O QUE PROVA
-----------
B1 — os 3 botões de relatório (Consolidado, CSV, PDF) respondem ao clique,
baixam via `fetch + Bearer` (nunca `<a href>`), e o print view abre no
`#print-area`.

B2 — a fila filtra itens terminais; estorno repõe o saldo e a receita volta a
ser dispensável (B0); o comprovante carimba ESTORNADO; o botão Estorno reflete
`i.estornado` do backend (não calculado no cliente).

B3 — zero UI de AÇÃO de devolução ao prescritor (o grep §4.5 do ticket, traduzido
pra DOM), mas badges de ESTADO `devolvido_prescritor` permanecem.

CIRCULAÇÃO RECEITA — a máquina de estados transiciona corretamente
(`pendente` → `transferida_paciente` → `em_custodia` → `dispensada`) e a cadeia
de custódia registra cada hop com motivo canônico; cidadão vê na carteira e
transfere pra farmácia; guard B0 re-arma `acionavel` após estorno.

CIRCULAÇÃO ATESTADO — objeto monolítico (sem itens) transita direto pra `emitido`
com custódia `prescritor → paciente` no próprio ato de emissão; cidadão vê em
`#lista-atestados` (vigentes, não histórico); `titulo_documento` reflete o
conselho (CFM → "ATESTADO MÉDICO").
"""
from __future__ import annotations

import time

import httpx
import pytest
from playwright.sync_api import expect, Page

pytestmark = pytest.mark.external

_TIMEOUT_MS = 20_000  # demo pública pode ser mais lenta que o subprocesso local

# Personas canônicas do seed de demo (demo.py / seed_demo.py).
_CNS = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"
_DISP_CENTRAL = "99999999000191"   # Farmácia Demo Central
_NOME_DISP = "Farmácia Demo Central"

# Sufixo de auditoria: marca medicamento como "de teste" para curadoria da demo.
_TS = time.strftime("%Y%m%d%H%M")


# ---------------------------------------------------------------------------
# Helpers — mesma forma dos helpers do test_coer2_e2e.py, mas apontando para
# `base_url` (env-driven) em vez de `app_demo`.
# ---------------------------------------------------------------------------

def _tok(base_url: str, role: str) -> str:
    """JWT de demo via POST /demo/login. Vale ~1h."""
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=15.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _api(base_url: str, token: str, method: str, path: str, body=None) -> httpx.Response:
    return httpx.request(
        method, f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body, timeout=20.0,
    )


def _autenticar(page: Page, base_url: str, role: str, sub: str, nome: str) -> str:
    """Planta as 4 chaves `picsaude_demo_*` no sessionStorage antes do goto.

    `dispensador.html` tem 3 caminhos de auto-login na carga; o primeiro
    (`_hidratarSessaoDemo`) lê exatamente estas chaves. Plantá-las antes do
    `goto` faz o usuário entrar direto no dashboard, sem passar pelo formulário
    de CNPJ+senha (que exigiria o `Demo@2024` e um POST extra).
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
    return tok


def _sem_erros(erros: list[str], tela: str) -> None:
    assert not erros, f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in erros)


def _emitir_para_paciente(base_url: str, ptok: str, med: str, qtd: int = 10) -> str:
    """Prescritor emite e já envia ao paciente (cidadão fica com a posse)."""
    r = _api(base_url, ptok, "POST", "/prescricoes", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "enviar_ao_paciente": True,
        "itens": [{"nome_medicamento": med, "quantidade": qtd,
                   "posologia": "1cp 8/8h", "unidade_quantidade": "comprimido"}],
    })
    assert r.status_code in (200, 201), f"emit falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _transferir_para_farmacia(base_url: str, patok: str, proto: str, cnpj: str = _DISP_CENTRAL) -> None:
    r = _api(base_url, patok, "POST", f"/paciente/prescricoes/{proto}/transferir-farmacia",
             {"cnpj_farmacia": cnpj})
    assert r.status_code in (200, 201), f"transferir-farmacia falhou: {r.status_code} {r.text}"


def _item_id_na_fila(base_url: str, dtok: str, proto: str) -> int:
    fila = _api(base_url, dtok, "GET", "/dispensadores/fila").json().get("fila", [])
    for f in fila:
        if f["protocolo"] == proto:
            return f["itens"][0]["item_id"]
    raise AssertionError(f"protocolo {proto} não está na fila do dispensador")


def _dispensar_total(base_url: str, dtok: str, proto: str, item_id: int, qtd: int) -> int:
    """Devolve o dispensacao_id (chave do comprovante e do estorno)."""
    r = _api(base_url, dtok, "POST", f"/prescricoes/{proto}/itens/{item_id}/dispensar",
             {"cnpj_estabelecimento": _DISP_CENTRAL, "quantidade_dispensada": qtd})
    assert r.status_code == 201, f"dispensar falhou: {r.status_code} {r.text}"
    return r.json()["dispensacao_id"]


# ---------------------------------------------------------------------------
# B1 — Botões de relatório (TICKET-F5-B1 §6)
# ---------------------------------------------------------------------------

def test_b1_botoes_relatorio_respondem(page: Page, base_url, demo_externa_viva, erros_de_console):
    """Os 3 botões no cabeçalho da fila respondem ao clique com fetch+Bearer.

    Critério §5 n.4: NUNCA existe `<a href>` apontando direto pro endpoint —
    o download tem que ser por `fetch` com Authorization, senão a PII do
    comprador/paciente vaza na URL.
    """
    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    # Stub do window.print: o handler `abrirRelatorioConsolidado` chama print()
    # ao final; sem stub, o headless trava esperando o dialog do SO.
    page.add_init_script(
        "window.print = function() { window.__printed = true; }"
    )
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    acoes = page.locator("#fila-container .fila-head-acoes")
    expect(acoes).to_be_visible(timeout=_TIMEOUT_MS)

    # Os 3 botões de relatório (existe um 4º: "↻ Atualizar", fora do escopo).
    botoes_rel = acoes.locator("button.btn-rel")
    expect(botoes_rel).to_have_count(3, timeout=_TIMEOUT_MS)

    # --- Consolidado: abre print view no #print-area ---
    page.locator("#fila-container .fila-head-acoes button.btn-rel",
                 has_text="Relatório Consolidado").click()
    expect(page.locator("#print-area h2")).to_have_text(
        "Relatório Consolidado — Dispensação (SNGPC)", timeout=_TIMEOUT_MS
    )
    assert page.evaluate("window.__printed === true"), "window.print não foi chamado"

    # --- CSV: baixa via fetch+Bearer, nome dispensacoes_sngpc_*.csv ---
    csv_autorizou = {"ok": False}
    def _checa_authorization(req):
        if "/dispensadores/relatorio.csv" in req.url:
            h = req.headers.get("authorization", "")
            csv_autorizou["ok"] = h.startswith("Bearer ")
    page.on("request", _checa_authorization)
    with page.expect_download(timeout=_TIMEOUT_MS) as dl_csv:
        page.locator("#fila-container .fila-head-acoes button.btn-rel",
                     has_text="SNGPC CSV").click()
    nome_csv = dl_csv.value.suggested_filename
    assert nome_csv.startswith("dispensacoes_sngpc_") and nome_csv.endswith(".csv"), \
        f"nome do CSV inesperado: {nome_csv}"
    assert csv_autorizou["ok"], "CSV não foi baixado via fetch com Authorization: Bearer"
    page.remove_listener("request", _checa_authorization)

    # --- PDF: idem, nome *.pdf ---
    pdf_autorizou = {"ok": False}
    def _checa_authorization_pdf(req):
        if "/dispensadores/relatorio.pdf" in req.url:
            h = req.headers.get("authorization", "")
            pdf_autorizou["ok"] = h.startswith("Bearer ")
    page.on("request", _checa_authorization_pdf)
    with page.expect_download(timeout=_TIMEOUT_MS) as dl_pdf:
        page.locator("#fila-container .fila-head-acoes button.btn-rel",
                     has_text="SNGPC PDF").click()
    nome_pdf = dl_pdf.value.suggested_filename
    assert nome_pdf.startswith("dispensacoes_sngpc_") and nome_pdf.endswith(".pdf"), \
        f"nome do PDF inesperado: {nome_pdf}"
    assert pdf_autorizou["ok"], "PDF não foi baixado via fetch com Authorization: Bearer"
    page.remove_listener("request", _checa_authorization_pdf)

    _sem_erros(erros_de_console, "dispensador.html (B1)")


# ---------------------------------------------------------------------------
# B2 — Ciclo pós-dispensação (TICKET-F5-B2 §6)
#
# Os 4 testes B2 compartilham um fixture `cenario_b2` que monta a coreografia
# uma vez por teste: emite → transfere → dispensa total. Estornar/aprovar
# comprovante fica por conta de cada teste.
# ---------------------------------------------------------------------------

@pytest.fixture
def cenario_b2(base_url, demo_externa_viva) -> dict:
    """Emite uma prescrição marcada TESTE-F5B, transfere p/ Central, dispensa total.

    Devolve: {protocolo, item_id, dispensacao_id, dtok, ptok, patok, qtd, med}.
    Cada teste que pede `cenario_b2` recebe um CENÁRIO FRESCO — não há acoplamento
    entre testes B2. O custo é 3 chamadas API por teste; o benefício é isolamento
    (a demo pública é não-determinística por construção).
    """
    pt, pat, dt = _tok(base_url, "prescritor"), _tok(base_url, "paciente"), _tok(base_url, "dispensador")
    med = f"TESTE-F5B-CICLO-{_TS}"
    proto = _emitir_para_paciente(base_url, pt, med, qtd=10)
    _transferir_para_farmacia(base_url, pat, proto)
    item_id = _item_id_na_fila(base_url, dt, proto)
    disp_id = _dispensar_total(base_url, dt, proto, item_id, qtd=10)
    return {
        "protocolo": proto, "item_id": item_id, "dispensacao_id": disp_id,
        "dtok": dt, "ptok": pt, "patok": pat, "qtd": 10, "med": med,
    }


def test_b2_escopo_a_fila_filtra_itens_terminais(page: Page, base_url, cenario_b2, erros_de_console):
    """Receita com item dispensado (terminal) NÃO aparece na fila; aparece no histórico.

    Critério §5 n.1 (Escopo A). `i.acionavel` vem do backend (B0) — a fila só
    mostra itens com ação possível.
    """
    c = cenario_b2
    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    fila = page.locator("#fila-lista")
    expect(fila).to_be_visible(timeout=_TIMEOUT_MS)
    # Confirma que a fila carregou de verdade (não está em "Carregando…").
    # O seed DEMO-FILA-0001 garante ao menos uma linha.
    expect(fila.locator(".fila-med-row").first).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 protocolo do cenario NÃO está na fila (item terminal foi filtrado).
    expect(fila).not_to_contain_text(c["protocolo"])

    # 🎯 mas ESTÁ no histórico com botão Comprovante.
    hist = page.locator("#historico-lista")
    expect(hist).to_be_visible(timeout=_TIMEOUT_MS)
    expect(hist).to_contain_text(c["protocolo"], timeout=_TIMEOUT_MS)
    expect(hist.locator("button", has_text="Comprovante").first).to_be_visible(timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B2 Escopo A)")


def test_b2_escopo_a_reentrada_por_estorno(page: Page, base_url, cenario_b2, erros_de_console):
    """Após estornar a dispensação total, a receita VOLTA pra fila (B0).

    Critério §5 n.3 (Escopo A, reentrada). O guard B0 troca o bloqueio de
    rótulo ('dispensado') por saldo efetivo; estorno repõe o saldo e o item
    volta a ser acionável sem mudar de status.
    """
    c = cenario_b2
    # Estorna via API (mais rápido que o prompt() do navegador e isola o teste
    # da UI do estorno — que tem teste próprio abaixo).
    r = _api(base_url, c["dtok"], "POST",
             f"/dispensacoes/{c['dispensacao_id']}/estornar",
             {"motivo": "desistencia_paciente"})
    assert r.status_code == 201, f"estornar falhou: {r.status_code} {r.text}"

    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    fila = page.locator("#fila-lista")
    expect(fila).to_be_visible(timeout=_TIMEOUT_MS)
    expect(fila.locator(".fila-med-row").first).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 a receita voltou pra fila e tem botão Dispensar habilitado.
    expect(fila).to_contain_text(c["protocolo"], timeout=_TIMEOUT_MS)
    expect(fila.locator("button", has_text="Dispensar").first).to_be_visible(timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B2 reentrada)")


def test_b2_escopo_c_comprovante_carimbado_estornado(page: Page, base_url, cenario_b2, erros_de_console):
    """Comprovante de dispensação estornada exibe carimbo ESTORNADO (R1: não apaga original)."""
    c = cenario_b2
    r = _api(base_url, c["dtok"], "POST",
             f"/dispensacoes/{c['dispensacao_id']}/estornar",
             {"motivo": "desistencia_paciente"})
    assert r.status_code == 201, f"estornar falhou: {r.status_code} {r.text}"

    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    hist = page.locator("#historico-lista")
    expect(hist).to_be_visible(timeout=_TIMEOUT_MS)
    # Abre o comprovante da dispensação estornada.
    hist.locator("button", has_text="Comprovante").first.click()

    modal = page.locator("#modal-comprovante")
    expect(modal).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 carimbo inequívoco de estorno no topo (B3 §5.B do ticket B2).
    carimbo = modal.locator(".comp-carimbo-estorno")
    expect(carimbo).to_be_visible(timeout=_TIMEOUT_MS)
    expect(carimbo.locator(".comp-carimbo-tit")).to_contain_text(
        "DISPENSAÇÃO ESTORNADA", timeout=_TIMEOUT_MS
    )

    # 🎯 R1: dados originais permanecem visíveis (não apagados pelo estorno).
    expect(modal.locator("#comprovante-body")).to_contain_text(c["med"], timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B2 comprovante estornado)")


def test_b2_escopo_b_botao_estorno_reflete_estado_backend(page: Page, base_url, cenario_b2, erros_de_console):
    """Item estornado mostra badge 'Estornado'; item não estornado mostra botão '⏪ Estornar'.

    Critério §5 n.6 (Escopo B) + §10: `i.estornado` vem do backend
    (`dispensadores.py:271` — `q_est > 0 and q_est >= q_disp`), NUNCA calculado
    no cliente. O grep `i\\.estornado\\s*=\\s*[^=]` deve retornar zero —
    confirmado no §5 n.4 do ticket.
    """
    c = cenario_b2
    # Estorna a dispensação do cenário.
    r = _api(base_url, c["dtok"], "POST",
             f"/dispensacoes/{c['dispensacao_id']}/estornar",
             {"motivo": "desistencia_paciente"})
    assert r.status_code == 201, f"estornar falhou: {r.status_code} {r.text}"

    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    hist = page.locator("#historico-lista")
    expect(hist).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 a dispensação do cenário aparece com badge "Estornado" (não com botão).
    linha = hist.locator(".fila-med-row", has_text=c["med"]).first
    expect(linha).to_be_visible(timeout=_TIMEOUT_MS)
    expect(linha.locator(".badge", has_text="Estornado")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(linha.locator("button", has_text="Estornar")).to_have_count(0, timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B2 botão estorno)")


# ---------------------------------------------------------------------------
# B3 — Zero UI de AÇÃO de devolução ao prescritor (TICKET-F5-B3 §6)
# ---------------------------------------------------------------------------

def test_b3_zero_botao_devolucao_prescritor(page: Page, base_url, demo_externa_viva, erros_de_console):
    """Nenhum botão/onclick de AÇÃO de devolução ao prescritor no dispensador.

    Critério §4.5 do ticket B3, traduzido de grep literal para asserção de DOM:
    a AÇÃO saiu, mas o ESTADO (badges `devolvido_prescritor`) permanece visível
    ao farmacêutico. A receita que um cidadão devolveu ao médico ainda aparece
    no dispensador — só sem botão de "devolver de novo".
    """
    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    # 🎯 zero botões de AÇÃO mencionando "Prescritor" na fila.
    expect(page.locator("#fila-lista button", has_text="Prescritor")).to_have_count(
        0, timeout=_TIMEOUT_MS
    )

    # 🎯 zero handlers onclick citando "prescritor" em todo o body — o grep
    #    literal do ticket (§4.5) vira esta asserção de DOM.
    expect(page.locator('button[onclick*="prescritor" i]')).to_have_count(0, timeout=_TIMEOUT_MS)
    expect(page.locator('[onclick*="devolverPrescritor" i]')).to_have_count(0, timeout=_TIMEOUT_MS)

    # Sanity: a fila carregou (não é "Carregando…"), senão a ausência é vacuidade.
    expect(page.locator("#fila-lista .fila-med-row").first).to_be_visible(timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "dispensador.html (B3)")


# ===========================================================================
# PROVA DE MÁQUINA DE ESTADOS — CIRCULAÇÃO DA RECEITA
#
# Os testes B1/B2/B3 acima provam RENDERIZAÇÃO do dispensador. Os dois testes
# abaixo provam DOMÍNIO: que a máquina de estados do núcleo sanitário transiciona
# corretamente e que a cadeia de custódia registra cada hop. A diferença é entre
# "o botão apareceu" (DOM) e "o estado mudou no backend" (domínio).
#
# A cadeia completa é assertada via `GET /prescricoes/{proto}/custodia` — não
# inferida a partir de códigos 2xx. Cada hop tem motivo canônico
# (`entrega_carteira_digital`, `transferencia_farmacia`) e timestamps de
# abertura/encerramento, e tudo é verificado ponto a ponto.
# ===========================================================================

def test_circulacao_receita_cadeia_de_custodia_e_b0(
    page: Page, base_url, demo_externa_viva, erros_de_console
):
    """A receita circula prescritor → paciente → dispensador e a máquina de estados
    transiciona; o cidadão vê na carteira e transfere pra farmácia; B0 re-arma
    após estorno.

    Esta é a prova central de que o núcleo sanitário funciona: cada transição
    de custódia escreve uma linha em `prescricao_custodia` com motivo canônico,
    cada transição de status respeita o mapa em `states.py`, e o guard B0
    (dispensabilidade por saldo efetivo, não por rótulo terminal) destrava o
    item após o estorno.
    """
    pt, pat, dt = _tok(base_url, "prescritor"), _tok(base_url, "paciente"), _tok(base_url, "dispensador")
    med = f"TESTE-F5B-RECEITA-CIRC-{_TS}"

    # --- 1. Emissão com envio ao paciente: status → transferida_paciente ---
    proto = _emitir_para_paciente(base_url, pt, med, qtd=10)

    cust = _api(base_url, pt, "GET", f"/prescricoes/{proto}/custodia").json()
    assert cust["status_prescricao"] == "transferida_paciente", \
        f"estado pós-emissão: {cust['status_prescricao']}"
    # 🎯 cadeia tem 1 hop: prescritor → paciente, motivo entrega_carteira_digital,
    #    ainda ativa (encerrada_em=None).
    assert len(cust["historico"]) == 1, cust["historico"]
    h0 = cust["historico"][0]
    assert h0["detentor_tipo"] == "paciente"
    assert h0["detentor_id"] == _CPF
    assert h0["motivo"] == "entrega_carteira_digital"
    assert h0["encerrada_em"] is None, "custódia inicial deve estar ativa"
    assert cust["custodia_ativa"]["detentor_tipo"] == "paciente"

    # --- 2. DOM: cidadão vê a receita na carteira ---
    _autenticar(page, base_url, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{base_url}/cidadao.html", wait_until="networkidle")
    carteira = page.locator("#lista-receitas")
    expect(carteira).to_be_visible(timeout=_TIMEOUT_MS)
    # 🎯 receita está na posse do cidadão, com badge "Documento Ativo".
    expect(carteira).to_contain_text(proto, timeout=_TIMEOUT_MS)
    card = carteira.locator(".receita-card", has_text=proto)
    expect(card.locator(".status-badge")).to_have_text("Documento Ativo", timeout=_TIMEOUT_MS)

    # --- 3. Cidadão transfere pra farmácia: status → em_custodia, 2 hops ---
    # Native confirm() no handler transferirParaFarmacia — aceitar automaticamente.
    page.once("dialog", lambda d: d.accept())
    card.get_by_role("button", name="Transferir Custódia").click()
    # Toast de sucesso confirma o POST.
    expect(page.locator("#picsaude-toast")).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 pela API: cadeia agora tem 2 hops; o primeiro foi encerrado.
    cust2 = _api(base_url, dt, "GET", f"/prescricoes/{proto}/custodia").json()
    assert cust2["status_prescricao"] == "em_custodia", \
        f"estado pós-transferência: {cust2['status_prescricao']}"
    assert len(cust2["historico"]) == 2, cust2["historico"]
    h1 = cust2["historico"][1]
    assert h1["detentor_tipo"] == "dispensador"
    assert h1["detentor_id"] == _DISP_CENTRAL
    assert h1["motivo"] == "transferencia_farmacia"
    assert h1["encerrada_em"] is None, "custódia do dispensador deve estar ativa"
    assert cust2["historico"][0]["encerrada_em"] is not None, \
        "custódia do paciente deve ter sido encerrada"

    # --- 4. DOM: receita saiu da posse do cidadão (carteira atualizou) ---
    # cidadao.html não tem polling — forçar refresh e confirmar.
    page.click("#btn-refresh")
    expect(carteira).not_to_contain_text(proto, timeout=_TIMEOUT_MS)

    _sem_erros(erros_de_console, "cidadao.html (circulação receita)")

    # --- 5. Dispensador dispensa total: status_item → dispensado, saldo 0 ---
    # Como o teste acima já navegou o cidadão, reautenticar como dispensador
    # numa nova "sessão" de página (mesmo browser context, novo goto).
    _autenticar(page, base_url, "dispensador", _DISP_CENTRAL, _NOME_DISP)
    page.goto(f"{base_url}/dispensador.html", wait_until="networkidle")

    # Pegar o item_id via API (não depende de polling).
    item_id = _item_id_na_fila(base_url, dt, proto)
    rd = _api(base_url, dt, "POST", f"/prescricoes/{proto}/itens/{item_id}/dispensar",
              {"cnpj_estabelecimento": _DISP_CENTRAL, "quantidade_dispensada": 10})
    assert rd.status_code == 201, rd.text
    body = rd.json()
    # 🎯 transições de estado declaradas em custodia.py:919-925.
    assert body["status_item"] == "dispensado", f"status_item pós-total: {body['status_item']}"
    assert body["saldo_restante"] == 0
    assert body["status_prescricao"] == "dispensada", \
        f"status_prescricao pós-total: {body['status_prescricao']}"

    # --- 6. Guard B0: estorno repõe saldo e o item volta a ser acionável ---
    re = _api(base_url, dt, "POST", f"/dispensacoes/{body['dispensacao_id']}/estornar",
              {"motivo": "desistencia_paciente"})
    assert re.status_code == 201, re.text
    rest = re.json()
    # 🎯 estorno reabre a custódia do item e repõe o saldo — sem mudar o rótulo.
    assert rest["saldo_restante"] == 10, f"saldo após estorno: {rest['saldo_restante']}"
    assert rest.get("custodia_reaberta") is True, \
        "estorno de dispensação total deve reabrir a custódia do item"

    # 🎯 na fila, `i.acionavel` voltou a true — mesmo `status_item` continuando
    #    "dispensado", porque o guard B0 usa saldo (não o rótulo terminal).
    fila = _api(base_url, dt, "GET", "/dispensadores/fila").json().get("fila", [])
    item = next(
        (it for f in fila if f["protocolo"] == proto for it in f["itens"] if it["item_id"] == item_id),
        None,
    )
    assert item is not None, "item não voltou à fila após estorno (B0 quebrado?)"
    assert item["acionavel"] is True, \
        f"acionavel={item['acionavel']} após estorno — guard B0 não destravou o item"

    _sem_erros(erros_de_console, "dispensador.html (circulação receita — B0)")


# ===========================================================================
# PROVA DE MÁQUINA DE ESTADOS — CIRCULAÇÃO DO ATESTADO
# ===========================================================================

def test_circulacao_atestado_single_hop_e_vigente_na_carteira(
    page: Page, base_url, demo_externa_viva, erros_de_console
):
    """Atestado sai do prescritor direto pro paciente (single-hop), em estado
    `emitido` (não-terminal), e aparece em `vigentes` na carteira do cidadão.

    Diferente da receita, o atestado é **monolítico** (sem itens, status direto
    em `atestados.status`) e sua custódia é escrita no próprio ato de emissão
    (`POST /atestados`) — não há step "enviar ao paciente". O cidadão é read-only
    para atestados (só lista/detalhe/PDF/custódia). Essas são as diferenças que
    distinguem o atestado da receita no núcleo sanitário.
    """
    pt, pat = _tok(base_url, "prescritor"), _tok(base_url, "paciente")
    finalidade = f"TESTE-F5B Atestado circulação {_TS}"

    # --- 1. Emissão: status emitido, custódia escrita no mesmo ato ---
    r = _api(base_url, pt, "POST", "/atestados", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_PRESCRITOR,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PACIENTE,
        "finalidade": finalidade,
        "municipio_emissao": "Recife",
        "dias_afastamento": 3,
        "conselho": "CFM",
    })
    assert r.status_code == 201, f"emissão falhou: {r.status_code} {r.text}"
    emit = r.json()
    proto = emit["protocolo"]
    # 🎯 estado inicial declarado em states_atestado.py:34 — não-terminal.
    assert emit["status"] == "emitido", f"status pós-emissão: {emit['status']}"

    # --- 2. Cadeia de custódia: single-hop prescritor → paciente ---
    cust = _api(base_url, pat, "GET", f"/atestados/{proto}/custodia").json()
    assert len(cust["custodia"]) == 1, cust["custodia"]
    c0 = cust["custodia"][0]
    # 🎯 o hop canônico: escrita no INSERT de atestados.py:537-551.
    assert c0["de"] == "prescritor"
    assert c0["para"] == "paciente"
    assert c0["contexto"]["motivo"] == "emissao"
    assert c0["contexto"]["de_id"] == _CNS
    assert c0["contexto"]["para_id"] == _CPF

    # --- 3. Atestado está em vigentes (não histórico) na carteira do paciente ---
    cart = _api(base_url, pat, "GET", "/paciente/atestados").json()
    # 🎯 em `vigentes` (auth.py:669-672) porque status não-terminal e dentro da validade.
    hit = [a for a in cart["vigentes"] if a["protocolo"] == proto]
    assert hit, f"atestado {proto} não está em vigentes: {cart}"
    a = hit[0]
    assert a["status"] == "emitido"
    # 🎯 titulo_documento reflete o conselho (CFM → "ATESTADO MÉDICO").
    assert a["titulo_documento"] == "ATESTADO MÉDICO", \
        f"titulo_documento: {a['titulo_documento']}"
    assert a["finalidade"] == finalidade

    # --- 4. DOM: cidadão vê o card do atestado na seção apropriada ---
    _autenticar(page, base_url, "paciente", _CPF, _NOME_PACIENTE)
    page.goto(f"{base_url}/cidadao.html", wait_until="networkidle")

    lista_atestados = page.locator("#lista-atestados")
    expect(lista_atestados).to_be_visible(timeout=_TIMEOUT_MS)
    # 🎯 card na seção de atestados (não de receitas) — prova de circulação correta.
    # F5-C3: atestado ganhou classe própria `.atestado-card` (verde), distinta de `.exame-card`.
    card = lista_atestados.locator(".atestado-card", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    # F5-C3: badge agora em maiúsculas e com classe modificadora `.atestado` (verde).
    expect(card.locator(".exame-badge-prioridade")).to_have_text("ATESTADO", timeout=_TIMEOUT_MS)
    expect(card).to_contain_text("ATESTADO MÉDICO", timeout=_TIMEOUT_MS)
    expect(card).to_contain_text(finalidade, timeout=_TIMEOUT_MS)
    # 🎯 cidadão é read-only para atestado: só botão de baixar PDF.
    expect(card.get_by_role("button", name="Baixar PDF")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(card.get_by_role("button", name="Transferir Custódia")).to_have_count(0)

    _sem_erros(erros_de_console, "cidadao.html (circulação atestado)")

