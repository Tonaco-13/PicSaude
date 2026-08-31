"""
tests/browser/test_lente_real_abertura.py — a lente real na abertura (30/08).

Despacho: "a seção da lente fiação o lente.js + /public/* (neutros por
construção), mantendo o rótulo de demonstração onde a resposta for
ilustrativa e comportamento real onde houver protocolo/chave."

O DESENHO
---------
A seção da lente em `/` (abertura) tem um ESTADO DE REPOUSO — o cartão
ilustrativo original, com o chip "exemplo ilustrativo" — visível desde o
carregamento da página, sem depender de nenhuma busca. Submeter o
formulário com um termo real dispara `LenteAuditoria.consultar()` contra
`/public/*` de verdade (mesmo componente de `demo.html`/`cidadao.html`,
TICKET-J.11) e SUBSTITUI o cartão ilustrativo pelo resultado real —
achado ou não. Campo vazio volta ao repouso ilustrativo.

Anônimo por desenho: a abertura não tem sessão nenhuma, então
`LenteAuditoria.consultar()` é chamado sem token — só os endpoints
`/public/*` respondem (circulação autenticada nunca entra em jogo aqui,
o mesmo neutro-por-construção do componente).

O QUE ESTE ARQUIVO PROVA
-------------------------
1. Em repouso, a lente mostra o exemplo ilustrativo (chip visível).
2. Protocolo REAL (emitido via API) → cartão REAL do componente
   (`.lente-card`, sem o chip "exemplo ilustrativo").
3. Protocolo inexistente → mensagem de "não encontrado" do PRÓPRIO
   componente (R4: nunca calar), sem inventar texto novo.
4. Campo vazio + submit → volta ao repouso ilustrativo.
"""
from __future__ import annotations

import time

import httpx
from playwright.sync_api import expect, Page

_TIMEOUT_MS = 15_000
_TS = time.strftime("%Y%m%d%H%M%S")

# Personas canônicas do seed de demo.
_CNS_PRESCRITOR = "980001112223334"
_NOME_PRESCRITOR = "Dra. Demo Maria Souza"
_CPF_PACIENTE = "12345678909"
_NOME_PACIENTE = "João Demo da Silva"


def _tok(base_url: str, role: str) -> str:
    r = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    r.raise_for_status()
    return r.json()["access_token"]


def _emitir_prescricao(base_url: str, sufixo: str) -> str:
    tok = _tok(base_url, "prescritor")
    r = httpx.post(
        f"{base_url}/prescricoes",
        headers={"Authorization": f"Bearer {tok}"},
        json={
            "cns_prescritor": _CNS_PRESCRITOR, "nome_prescritor": _NOME_PRESCRITOR,
            "cpf_paciente": _CPF_PACIENTE, "nome_paciente": _NOME_PACIENTE,
            "tipo_emissao": "nova",
            "itens": [{
                "nome_medicamento": f"LENTE-REAL {sufixo}",
                "quantidade": 5, "posologia": "1cp/dia",
            }],
        },
        timeout=15.0,
    )
    assert r.status_code in (200, 201), f"emissão falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _buscar(page: Page, termo: str) -> None:
    page.fill("#lenteInput", termo)
    page.locator("#lenteForm button[type=submit]").click()


# ===========================================================================
# 1 — repouso: exemplo ilustrativo visível sem nenhuma busca
# ===========================================================================

def test_lente_em_repouso_mostra_exemplo_ilustrativo(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    resultado = page.locator("#lenteResult")
    expect(resultado).to_be_visible(timeout=_TIMEOUT_MS)
    expect(resultado).to_contain_text("exemplo ilustrativo")


# ===========================================================================
# 2 — protocolo REAL → cartão REAL (não o canned de repouso)
# ===========================================================================

def test_protocolo_real_traz_cartao_real(page: Page, app_demo):
    proto = _emitir_prescricao(app_demo, f"{_TS}A")

    page.goto(f"{app_demo}/", wait_until="networkidle")
    _buscar(page, proto)

    resultado = page.locator("#lenteResult")
    expect(resultado).to_contain_text(proto, timeout=_TIMEOUT_MS)
    expect(resultado).to_contain_text("Receita (prescrição)")
    expect(resultado).not_to_contain_text("exemplo ilustrativo")
    # o cartão real vem do componente compartilhado — a nota de neutralidade
    # é dele, não texto inventado nesta seção.
    expect(resultado).to_contain_text("sem conteúdo clínico")


# ===========================================================================
# 3 — protocolo inexistente → mensagem honesta do componente (R4)
# ===========================================================================

def test_protocolo_inexistente_mostra_mensagem_do_componente(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    _buscar(page, "00000000-0000-0000-0000-000000000000")

    resultado = page.locator("#lenteResult")
    expect(resultado).to_contain_text(
        "Nenhum objeto sanitário encontrado", timeout=_TIMEOUT_MS
    )
    expect(resultado).not_to_contain_text("exemplo ilustrativo")


# ===========================================================================
# 4 — campo vazio volta ao repouso ilustrativo
# ===========================================================================

def test_campo_vazio_volta_ao_repouso_ilustrativo(page: Page, app_demo):
    page.goto(f"{app_demo}/", wait_until="networkidle")
    _buscar(page, "00000000-0000-0000-0000-000000000000")
    resultado = page.locator("#lenteResult")
    expect(resultado).to_contain_text("Nenhum objeto", timeout=_TIMEOUT_MS)

    _buscar(page, "")
    expect(resultado).to_contain_text("exemplo ilustrativo", timeout=_TIMEOUT_MS)


# ===========================================================================
# 5 — anônimo por desenho: nenhuma chamada carrega Authorization
# ===========================================================================

def test_busca_na_abertura_nunca_manda_token(page: Page, app_demo):
    """A abertura não tem sessão — `consultar()` é chamado sem token
    (§ neutro por construção). Se algum dia alguém plantar sessão aqui e
    esquecer de filtrar, esta guarda pega o vazamento."""
    proto = _emitir_prescricao(app_demo, f"{_TS}B")
    pedidos = []
    page.on("request", lambda req: pedidos.append(req) if "/public/" in req.url else None)

    page.goto(f"{app_demo}/", wait_until="networkidle")
    _buscar(page, proto)
    expect(page.locator("#lenteResult")).to_contain_text(proto, timeout=_TIMEOUT_MS)

    assert pedidos, "nenhuma chamada a /public/* observada — busca não disparou"
    for req in pedidos:
        assert req.headers.get("authorization") is None, (
            f"busca anônima da abertura mandou Authorization: {req.url}"
        )
