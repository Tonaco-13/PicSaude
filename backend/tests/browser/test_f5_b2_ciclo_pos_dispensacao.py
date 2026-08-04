"""
tests/browser/test_f5_b2_ciclo_pos_dispensacao.py — Browser-E2E do
TICKET-F5-B2 §6 (ciclo pós-dispensação: fila só dispensáveis + histórico com
comprovante ESTORNADO).

POR QUE ESTE TESTE EXISTE
-------------------------
O B2 está implementado e mergeado (PR #93), mas o browser-E2E obrigatório do
critério §5 n.14 nunca foi entregue. Este arquivo fecha a lacuna (despacho
KIMI3-001 §3.2), nos 5 cenários do ticket.

O QUE PROVA (invariantes do ticket B2 §5)
------------------------------------------
Escopo A — fila: receita com todos os itens terminais NÃO aparece na fila;
após estorno total (B0 repondo saldo) ela REAPARECE acionável.
Escopo B — ciclo: botão Estorno só existe se `i.estornado === false` — estado
DERIVADO DO BACKEND (§10), nunca calculado no cliente (guarda estática incluída).
Escopo C — comprovante: dispensação estornada mostra carimbo inequívoco SEM
apagar/editar os dados originais (R1); protocolo e dispensacao_id idênticos
antes/depois (§6b Regra de Ouro); a linha da dispensação permanece intacta
(ledger imutável — lição do COER-2).

PADRÃO
------
Segue test_coer2_e2e.py: coreografia via API de demo (mesma origem) montada UMA
vez em fixture de sessão; as asserções são sobre o DOM RENDERIZADO — foi um
agente navegando a demo que pegou os bugs de posse dupla que 22 testes PG não
pegaram (LEARNINGS do COER-2).
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import expect

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (demo.py::_PERSONAS).
_CNS, _NOME_P = "980001112223334", "Dra. Demo Maria Souza"
_CPF, _NOME_PA = "12345678909", "João Demo da Silva"
_DISP = "99999999000191"   # Farmácia Demo Central

_QTD = 10

_HTML = Path(__file__).resolve().parents[3] / "dispensador.html"


# ---------------------------------------------------------------------------
# Coreografia via API de demo (mesma origem) — padrão de test_coer2_e2e.py
# ---------------------------------------------------------------------------

def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _api(base_url: str, token: str, method: str, path: str, body=None) -> httpx.Response:
    return httpx.request(
        method, f"{base_url}{path}",
        headers={"Authorization": f"Bearer {token}"}, json=body, timeout=15.0,
    )


def _emitir_para_paciente(base_url: str, ptok: str, med: str) -> str:
    r = _api(base_url, ptok, "POST", "/prescricoes", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_P,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PA,
        "enviar_ao_paciente": True,
        "itens": [{"nome_medicamento": med, "quantidade": _QTD,
                   "posologia": "1cp 8/8h", "unidade_quantidade": "comprimido"}],
    })
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _transferir_para_farmacia(base_url: str, pattok: str, proto: str) -> None:
    r = _api(base_url, pattok, "POST",
             f"/paciente/prescricoes/{proto}/transferir-farmacia",
             {"cnpj_farmacia": _DISP})
    assert r.status_code == 201, f"transferência falhou: {r.status_code} {r.text}"


def _item_id(base_url: str, dtok: str, proto: str) -> int:
    for f in _api(base_url, dtok, "GET", "/dispensadores/fila").json()["fila"]:
        if f["protocolo"] == proto:
            return f["itens"][0]["item_id"]
    raise AssertionError(f"proto {proto} não está na fila do dispensador")


def _dispensar_total(base_url: str, dtok: str, proto: str,
                     lote: str | None = None) -> dict:
    iid = _item_id(base_url, dtok, proto)
    body = {"cnpj_estabelecimento": _DISP, "quantidade_dispensada": _QTD}
    if lote:
        body["lote"] = lote
        body["fabricante"] = "Farmacêutica Demo"
    r = _api(base_url, dtok, "POST",
             f"/prescricoes/{proto}/itens/{iid}/dispensar", body)
    assert r.status_code == 201, f"dispensação falhou: {r.status_code} {r.text}"
    return r.json()


def _estornar(base_url: str, dtok: str, dispensacao_id: int) -> dict:
    r = _api(base_url, dtok, "POST",
             f"/dispensacoes/{dispensacao_id}/estornar",
             {"motivo": "desistencia_paciente"})
    assert r.status_code == 201, f"estorno falhou: {r.status_code} {r.text}"
    return r.json()


def _montar_ciclo(base_url: str, med: str, ptok: str, pattok: str, dtok: str,
                  lote: str | None = None, estornar: bool = False) -> dict:
    """Emite → paciente transfere → dispensador dispensa TOTAL (→ opcionalmente estorna)."""
    proto = _emitir_para_paciente(base_url, ptok, med)
    _transferir_para_farmacia(base_url, pattok, proto)
    disp = _dispensar_total(base_url, dtok, proto, lote=lote)
    ciclo = {"proto": proto, "dispensacao_id": disp["dispensacao_id"]}
    if estornar:
        est = _estornar(base_url, dtok, disp["dispensacao_id"])
        ciclo["estorno_protocolo"] = est["protocolo"]
    return ciclo


@pytest.fixture(scope="session")
def cenarios(app_demo) -> dict:
    """Monta os 4 ciclos do B2 uma única vez (fixture de sessão, como coer2)."""
    base = app_demo
    pt, pat, dt = _tok(base, "prescritor"), _tok(base, "paciente"), _tok(base, "dispensador")
    return {
        # Escopo A.1 — dispensação total SEM estorno: sai da fila, fica no histórico.
        "fila_total": _montar_ciclo(base, "IBUPROFENO-B2-FILA", pt, pat, dt),
        # Escopo A.2 — dispensação total COM estorno: saldo reposto (B0), volta à fila.
        "reentrada": _montar_ciclo(base, "PARACETAMOL-B2-REEN", pt, pat, dt, estornar=True),
        # Escopos B/C — dispensação estornada COM lote (carimbo + dados originais).
        "estornada": _montar_ciclo(base, "AMOXICILINA-B2-EST", pt, pat, dt,
                                   lote="LOTE-B2-001", estornar=True),
        # Escopos B/C — dispensação NÃO estornada (botão habilitado, sem carimbo).
        "nao_estornada": _montar_ciclo(base, "DIPIRONA-B2-OK", pt, pat, dt,
                                       lote="LOTE-B2-002"),
    }


# ---------------------------------------------------------------------------
# Sessão de demo no navegador (mesmo padrão de test_coer2_e2e.py)
# ---------------------------------------------------------------------------

def _autenticar_dispensador(page, base_url: str) -> None:
    tok = _tok(base_url, "dispensador")
    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {tok!r});
        sessionStorage.setItem('picsaude_demo_role',  'dispensador');
        sessionStorage.setItem('picsaude_demo_sub',   {_DISP!r});
        sessionStorage.setItem('picsaude_demo_nome',  'Farmácia Demo Central');
        """
    )


def _sem_erros(erros: list[str], tela: str) -> None:
    assert not erros, f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in erros)


def _abrir_dispensador(page, app_demo: str) -> None:
    _autenticar_dispensador(page, app_demo)
    page.goto(f"{app_demo}/dispensador.html", wait_until="networkidle")
    # A fila carregou de fato (DEMO-FILA-0001 do seed garante ao menos uma
    # linha) — sem isto, asserções de AUSÊNCIA passariam por vacuidade.
    lista = page.locator("#fila-lista")
    expect(lista.locator(".fila-med-row").first).to_be_visible(timeout=_TIMEOUT_MS)


# ---------------------------------------------------------------------------
# Guarda estática (critério §5 n.4 — §10: estornado NUNCA calculado no cliente)
# ---------------------------------------------------------------------------

def test_b2_cliente_nunca_calcula_estornado():
    """`grep -nE "i\\.estornado\\s*=\\s*[^=]" dispensador.html` deve ser zero."""
    html = _HTML.read_text(encoding="utf-8")
    assert not re.search(r"i\.estornado\s*=\s*[^=]", html), (
        "dispensador.html atribui i.estornado no cliente — o campo é derivado "
        "do backend (B2 §2 / §10); o cliente só renderiza."
    )


# ---------------------------------------------------------------------------
# Escopo A — fila só dispensáveis (critérios §5 n.1 e n.3)
# ---------------------------------------------------------------------------

def test_b2_escopo_a_fila_so_dispensaveis(page, app_demo, cenarios, erros_de_console):
    """Receita com todos os itens terminais não aparece na fila (só no histórico)."""
    proto = cenarios["fila_total"]["proto"]
    _abrir_dispensador(page, app_demo)

    # 🎯 NÃO está na fila renderizada (saldo 0 → nenhum item acionável, B2 §4.1).
    expect(page.locator("#fila-lista")).not_to_contain_text(proto)
    # 🎯 ESTÁ no histórico renderizado.
    expect(page.locator("#historico-lista")).to_contain_text(proto, timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "dispensador.html (B2 — fila só dispensáveis)")


def test_b2_escopo_a_reentrada_por_estorno(page, app_demo, cenarios, erros_de_console):
    """Após estornar dispensação total, a receita reaparece na fila com saldo > 0."""
    proto = cenarios["reentrada"]["proto"]
    _abrir_dispensador(page, app_demo)

    # 🎯 VOLTOU pra fila — o estorno total repôs o saldo (B0) e o item voltou
    # acionável (i.acionavel do backend — um item `dispensado` com saldo reposto
    # É acionável; _FILA_TERMINAIS sozinho não decide, handoff §5 aviso 4).
    card = page.locator("#fila-lista .fila-item", has_text=proto)
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    expect(card).to_contain_text(f"saldo {_QTD}/{_QTD}")
    # E continua no histórico (a dispensação/estorno são movimentos do ledger).
    expect(page.locator("#historico-lista")).to_contain_text(proto, timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "dispensador.html (B2 — reentrada por estorno)")


# ---------------------------------------------------------------------------
# Escopo B — botão Estorno dirigido pelo estado do backend (critérios n.5 e n.6)
# ---------------------------------------------------------------------------

def test_b2_escopo_b_botao_estorno_estado_do_backend(page, app_demo, cenarios, erros_de_console):
    """Botão Estorno só habilitado se !i.estornado (campo do backend, §10)."""
    est = cenarios["estornada"]
    nao = cenarios["nao_estornada"]
    _abrir_dispensador(page, app_demo)
    hist = page.locator("#historico-lista")

    # Dispensação JÁ estornada → badge "Estornado", SEM botão Estorno.
    card_est = hist.locator(".fila-item", has_text=est["proto"])
    expect(card_est).to_be_visible(timeout=_TIMEOUT_MS)
    expect(card_est.locator(".badge")).to_contain_text("Estornado")
    assert card_est.get_by_role("button", name="Estornar").count() == 0, (
        "dispensação estornada exibiu botão Estorno — estado não veio do backend"
    )
    expect(card_est.get_by_role("button", name="Comprovante")).to_be_visible()

    # Dispensação NÃO estornada → botão Estorno presente e habilitado.
    card_nao = hist.locator(".fila-item", has_text=nao["proto"])
    expect(card_nao).to_be_visible(timeout=_TIMEOUT_MS)
    expect(card_nao.get_by_role("button", name="Estornar")).to_be_enabled()
    _sem_erros(erros_de_console, "dispensador.html (B2 — botão estorno)")


# ---------------------------------------------------------------------------
# Escopo C — comprovante ESTORNADO (critérios n.9, n.12 e n.13)
# ---------------------------------------------------------------------------

def test_b2_escopo_c_comprovante_estornado(page, app_demo, cenarios, erros_de_console):
    """Comprovante de dispensação estornada tem carimbo e preserva o original."""
    ciclo = cenarios["estornada"]

    # Regra de Ouro + ledger (§6b / §5 n.13) — camada de contrato: após o
    # estorno, a linha da dispensação PERMANECE intacta (nada apagado/editado),
    # com o mesmo dispensacao_id e a quantidade original.
    dt = _tok(app_demo, "dispensador")
    hist_api = _api(app_demo, dt, "GET", "/dispensadores/historico").json()["historico"]
    card_api = next(h for h in hist_api if h["protocolo"] == ciclo["proto"])
    item_api = next(i for i in card_api["itens_dispensados"]
                    if i["dispensacao_id"] == ciclo["dispensacao_id"])
    assert item_api["quantidade_dispensada"] == _QTD, (
        "linha da dispensação foi alterada/apagada após o estorno — ledger violado (R1)"
    )
    assert item_api["estornado"] is True

    # Camada de DOM renderizado.
    _abrir_dispensador(page, app_demo)
    card = page.locator("#historico-lista .fila-item", has_text=ciclo["proto"])
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    card.get_by_role("button", name="Comprovante").click()

    expect(page.locator("#modal-comprovante")).to_be_visible(timeout=_TIMEOUT_MS)
    body = page.locator("#comprovante-body")

    # 🎯 Carimbo inequívoco no TOPO (B2 §4.4 / B3).
    expect(body.locator(".comp-carimbo-estorno")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(body).to_contain_text("DISPENSAÇÃO ESTORNADA")
    expect(body).to_contain_text(f"ref. estorno {ciclo['estorno_protocolo']}")

    # 🎯 R1 — dados da dispensação original PERMANECEM (qtd, lote).
    expect(body).to_contain_text("LOTE-B2-001")
    expect(body).to_contain_text(f"Qtd. dispensada: {_QTD}")

    # 🎯 §6b Regra de Ouro — identificação idêntica antes/depois do estorno.
    expect(body).to_contain_text(f"Dispensação nº {ciclo['dispensacao_id']}")
    expect(body).to_contain_text(ciclo["proto"])
    _sem_erros(erros_de_console, "dispensador.html (B2 — comprovante estornado)")


def test_b2_escopo_c_comprovante_nao_estornado(page, app_demo, cenarios, erros_de_console):
    """Comprovante de dispensação não estornada permanece idêntico (sem carimbo)."""
    ciclo = cenarios["nao_estornada"]
    _abrir_dispensador(page, app_demo)
    card = page.locator("#historico-lista .fila-item", has_text=ciclo["proto"])
    expect(card).to_be_visible(timeout=_TIMEOUT_MS)
    card.get_by_role("button", name="Comprovante").click()

    expect(page.locator("#modal-comprovante")).to_be_visible(timeout=_TIMEOUT_MS)
    body = page.locator("#comprovante-body")

    # 🎯 NENHUM carimbo de estorno — comprovante idêntico ao comportamento atual.
    assert body.locator(".comp-carimbo-estorno").count() == 0, (
        "comprovante de dispensação NÃO estornada exibiu carimbo de estorno"
    )
    expect(body).not_to_contain_text("ESTORNADA")

    # Identificação e dados originais presentes (critério n.11).
    expect(body).to_contain_text(f"Dispensação nº {ciclo['dispensacao_id']}")
    expect(body).to_contain_text(ciclo["proto"])
    expect(body).to_contain_text("LOTE-B2-002")
    _sem_erros(erros_de_console, "dispensador.html (B2 — comprovante não estornado)")
