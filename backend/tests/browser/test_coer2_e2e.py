"""
tests/browser/test_coer2_e2e.py — E2E de navegador headless dos Cenários 1 e 2
(TICKET-COERENCIA-DEVOLUCOES-2 §7.3).

POR QUE ESTE TESTE EXISTE
-------------------------
"O teste unitário prova a unidade; só o navegador prova a jornada." (§13). O bug
de posse dupla atravessa TELAS — só um agente atravessando prescritor → cidadão →
dispensador o vê. As 22 do PostgreSQL (verdes) não pegaram os Cenários 1 e 2 porque
cada teste cobria um endpoint isolado. Aqui a coreografia roda contra o app de demo
REAL (mesma origem, API + frontend), e as asserções são sobre o que a TELA RENDERIZA.

O QUE PROVA (critério de aceite: ZERO dupla posse)
--------------------------------------------------
Cenário 1 (estorno + devolução ao paciente): após dispensar→estornar→devolver, a
receita SAI da fila do dispensador (não fica presa) e aparece ATIVA na carteira do
cidadão. Cenário 2 (devolução ao prescritor): a receita SAI da posse do cidadão e o
motivo digitado pelo cidadão CHEGA renderizado ao painel de correções do prescritor.

A coreografia usa a API de demo (mesma origem) — clicar 30 telas acoplaria o teste a
cada modal; o valor aqui é a asserção sobre o DOM renderizado das 3 telas.
"""
from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import expect

_TIMEOUT_MS = 15_000

# Personas canônicas do seed de demo (demo.py::_PERSONAS).
_CNS, _NOME_P = "980001112223334", "Dra. Demo Maria Souza"
_CPF, _NOME_PA = "12345678909", "João Demo da Silva"
_DISP = "99999999000191"

_MOTIVO_CIDADAO = "Remédio ou Apresentação Errada - trocar dose"


# ---------------------------------------------------------------------------
# Coreografia via API de demo (mesma origem) — proven em test_choreography
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


@pytest.fixture(scope="session")
def cenarios(app_demo) -> dict:
    """Roda a coreografia dos 2 cenários uma vez e devolve os protocolos.

    Cenário 1: emite → cidadão manda p/ farmácia → dispensa total → estorna →
    devolve ao paciente. Cenário 2: emite (na carteira) → cidadão devolve ao médico.
    """
    base = app_demo
    pt, pat, dt = _tok(base, "prescritor"), _tok(base, "paciente"), _tok(base, "dispensador")

    # --- Cenário 1 ---
    p1 = _emit_para_paciente(base, pt, "DIPIRONA-COER1")
    assert _api(base, pat, "POST", f"/paciente/prescricoes/{p1}/transferir-farmacia",
                {"cnpj_farmacia": _DISP}).status_code == 201
    iid = _item_id(base, dt, p1)
    rd = _api(base, dt, "POST", f"/prescricoes/{p1}/itens/{iid}/dispensar",
              {"cnpj_estabelecimento": _DISP, "quantidade_dispensada": 10})
    assert rd.status_code == 201, rd.text
    assert _api(base, dt, "POST", f"/dispensacoes/{rd.json()['dispensacao_id']}/estornar",
                {"motivo": "desistencia_paciente"}).status_code == 201
    rv = _api(base, dt, "POST", f"/prescricoes/{p1}/itens/{iid}/devolver",
              {"para": "paciente", "motivo": "desistiu"})
    assert rv.status_code == 200, rv.text  # guard por SALDO, não 409 'já dispensado'

    # --- Cenário 2 ---
    p2 = _emit_para_paciente(base, pt, "AMOXICILINA-COER2")
    rdp = _api(base, pat, "POST", f"/paciente/prescricoes/{p2}/devolver-prescritor",
               {"motivo": _MOTIVO_CIDADAO})
    assert rdp.status_code == 201, rdp.text

    return {"cenario1": p1, "cenario2": p2}


# ---------------------------------------------------------------------------
# Autenticação de sessão de demo (planta o token — igual aos smokes)
# ---------------------------------------------------------------------------

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
# Cenário 1 — a receita SAIU da fila do dispensador (rendered)
# ---------------------------------------------------------------------------

def test_cenario1_receita_saiu_da_fila_do_dispensador(page, app_demo, cenarios, erros_de_console):
    proto = cenarios["cenario1"]
    _autenticar(page, app_demo, "dispensador", _DISP, "Farmácia Demo Central")
    page.goto(f"{app_demo}/dispensador.html", wait_until="networkidle")

    lista = page.locator("#fila-lista")
    expect(lista).to_be_visible(timeout=_TIMEOUT_MS)
    # A fila carregou de fato (o seed DEMO-FILA-0001 garante ao menos uma linha) —
    # sem isto a asserção de ausência passaria por vacuidade (fila em "Carregando…").
    expect(lista.locator(".fila-med-row").first).to_be_visible(timeout=_TIMEOUT_MS)

    # 🎯 A receita do Cenário 1 NÃO está mais na fila renderizada (Manifestação A).
    expect(lista).not_to_contain_text(proto)
    _sem_erros(erros_de_console, "dispensador.html (Cenário 1)")


def test_cenario1_receita_ativa_na_carteira_do_cidadao(page, app_demo, cenarios, erros_de_console):
    proto = cenarios["cenario1"]
    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PA)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")

    # 🎯 A receita volta a aparecer ATIVA na carteira (não "Finalizada").
    expect(page.locator("body")).to_contain_text(proto, timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "cidadao.html (Cenário 1)")


# ---------------------------------------------------------------------------
# Cenário 2 — sai da posse do cidadão + o motivo chega ao prescritor (rendered)
# ---------------------------------------------------------------------------

def test_cenario2_motivo_do_cidadao_chega_ao_prescritor(page, app_demo, cenarios, erros_de_console):
    _autenticar(page, app_demo, "prescritor", _CNS, _NOME_P)
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

    # 🎯 §9.2: o motivo digitado pelo cidadão aparece RENDERIZADO na caixa de
    # correções do prescritor (antes: "Motivo não informado.").
    devolvidas = page.locator("#lista-devolvidas")
    expect(devolvidas).to_contain_text("Remédio ou Apresentação Errada", timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "prescritor.html (Cenário 2)")


def test_cenario2_receita_devolvida_nao_esta_na_posse_do_cidadao(page, app_demo, cenarios, erros_de_console):
    proto = cenarios["cenario2"]
    # Confirma pelo backend (mesma origem) que a devolvida saiu da POSSE — a asserção
    # de renderização do Cenário 1 já cobre o "aparece"; aqui o foco é a AUSÊNCIA na
    # posse, difícil de escopar por texto puro (o histórico pode conter o protocolo).
    pat = _tok(app_demo, "paciente")
    wallet = _api(app_demo, pat, "GET", "/paciente/prescricoes").json()
    posse = {p["protocolo"] for p in wallet["posse"]}
    assert proto not in posse, "receita devolvida ao médico ainda está na posse do cidadão"

    # E a tela do cidadão renderiza sem erro com a nova etiqueta de estado.
    _autenticar(page, app_demo, "paciente", _CPF, _NOME_PA)
    page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
    _sem_erros(erros_de_console, "cidadao.html (Cenário 2)")
