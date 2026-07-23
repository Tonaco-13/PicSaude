"""
tests/browser/test_coer2_fix.py — E2E do TICKET-COER2-POS-MERGE-FIX (Opção 1, core).

POR QUE ESTE TESTE EXISTE (e por que é só UM)
---------------------------------------------
O COER-2 (`test_coer2_e2e.py`) só exercitava o caminho FRESH: item `pendente` → devolver.
O bug vivia no caminho COMPOSTO — item `devolvido_paciente` (rescaldo de estorno + devolução
ao paciente) → devolver ao médico. `auth.py::devolver_prescritor` só virava itens `pendente`,
então a receita ia a `transferida_prescritor` mas o item ficava `devolvido_paciente`:
contraditório e INVISÍVEL no painel de correções.

Este arquivo prova a ÚNICA coisa que exige um NAVEGADOR: que o painel do prescritor
RENDERIZA a receita não-fresh na seção "#lista-devolvidas" com o motivo do cidadão.
Toda a coerência de backend (item → devolvido_prescritor, custódia sem órfã, sai da
posse, guarda de incoerência) vive em `tests/integration/test_custodia_devolucao.py`
(COER-12/13) — contra PostgreSQL, o gate certo para asserção de estado. Manter o gate
de navegador enxuto: um PR de estado não deve inflar a sessão do app_demo com asserções
que não precisam de tela (lição do #122 — smokes estouraram o timeout de goto).
"""
from __future__ import annotations

import httpx
from playwright.sync_api import expect

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (demo.py::_PERSONAS).
_CNS, _NOME_P = "980001112223334", "Dra. Demo Maria Souza"
_CPF, _NOME_PA = "12345678909", "João Demo da Silva"
_DISP = "99999999000191"

_MOTIVO_NAO_FRESH = "Erro composto pos-estorno - COER2FIX"


# ---------------------------------------------------------------------------
# Coreografia via API de demo (mesma origem) — proven em test_coer2_e2e.py
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


def _emit_para_paciente(base_url: str, ptok: str, med: str) -> str:
    r = _api(base_url, ptok, "POST", "/prescricoes", {
        "cns_prescritor": _CNS, "nome_prescritor": _NOME_P,
        "cpf_paciente": _CPF, "nome_paciente": _NOME_PA,
        "enviar_ao_paciente": True,
        "itens": [{"nome_medicamento": med, "quantidade": 10,
                   "posologia": "1cp 8/8h", "unidade_quantidade": "comprimido"}],
    })
    assert r.status_code in (200, 201), f"emit falhou: {r.status_code} {r.text}"
    return r.json()["protocolo"]


def _item_id(base_url: str, dtok: str, proto: str) -> int:
    for f in _api(base_url, dtok, "GET", "/dispensadores/fila").json()["fila"]:
        if f["protocolo"] == proto:
            return f["itens"][0]["item_id"]
    raise AssertionError(f"proto {proto} não está na fila do dispensador")


def _autenticar(page, base_url: str, role: str, sub: str, nome: str) -> None:
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


# ---------------------------------------------------------------------------
# O caminho COMPOSTO renderiza no painel do prescritor (DOM)
# ---------------------------------------------------------------------------

def test_nao_fresh_motivo_renderiza_na_caixa_de_correcoes(page, app_demo, erros_de_console):
    """🎯 item devolvido_paciente → devolver ao médico → motivo RENDERIZADO em
    #lista-devolvidas. Na main pré-fix o item continuava devolvido_paciente e a
    receita não aparecia na caixa. Único assert que exige NAVEGADOR."""
    base = app_demo
    pt, pat, dt = _tok(base, "prescritor"), _tok(base, "paciente"), _tok(base, "dispensador")

    # Cenário 1 (COER-9) primeiro: item termina em devolvido_paciente.
    proto = _emit_para_paciente(base, pt, "AMOXICILINA-COER2FIX-NF")
    assert _api(base, pat, "POST", f"/paciente/prescricoes/{proto}/transferir-farmacia",
                {"cnpj_farmacia": _DISP}).status_code == 201
    iid = _item_id(base, dt, proto)
    rd = _api(base, dt, "POST", f"/prescricoes/{proto}/itens/{iid}/dispensar",
              {"cnpj_estabelecimento": _DISP, "quantidade_dispensada": 10})
    assert rd.status_code == 201, rd.text
    assert _api(base, dt, "POST", f"/dispensacoes/{rd.json()['dispensacao_id']}/estornar",
                {"motivo": "desistencia_paciente"}).status_code == 201
    assert _api(base, dt, "POST", f"/prescricoes/{proto}/itens/{iid}/devolver",
                {"para": "paciente", "motivo": "desistiu"}).status_code == 200
    # E agora o caminho que faltava: cidadão devolve ao médico um item devolvido_paciente.
    assert _api(base, pat, "POST", f"/paciente/prescricoes/{proto}/devolver-prescritor",
                {"motivo": _MOTIVO_NAO_FRESH}).status_code == 201

    _autenticar(page, base, "prescritor", _CNS, _NOME_P)
    page.goto(f"{base}/prescritor.html", wait_until="networkidle")

    devolvidas = page.locator("#lista-devolvidas")
    expect(devolvidas).to_contain_text("Erro composto pos-estorno", timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "prescritor.html (COER2-POS-MERGE-FIX não-fresh)")
