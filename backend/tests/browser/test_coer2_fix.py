"""
tests/browser/test_coer2_fix.py — E2E do TICKET-COER2-POS-MERGE-FIX (Opção 1, core).

POR QUE ESTE TESTE EXISTE
-------------------------
O COER-2 (PR #120) modelou a volta ao médico no NÍVEL PRESCRIÇÃO (`transferida_prescritor`),
mas o E2E (`test_coer2_e2e.py`) só exercitava o caminho FRESH: item `pendente` → devolver.
O bug vivia no caminho COMPOSTO — item `devolvido_paciente` (rescaldo de estorno + devolução
ao paciente) → devolver ao médico. `auth.py::devolver_prescritor` só virava itens `pendente`,
então a receita ia para `transferida_prescritor` mas o item ficava em `devolvido_paciente`:
contraditório e INVISÍVEL no painel de correções (prescritor.py lê item-level
`devolvido_prescritor`). Eco de "dupla posse" no nível de estado.

O QUE PROVA
-----------
1. FRESH (regressão): item `pendente` → devolver → aparece em #lista-devolvidas.
2. NÃO-FRESH (o buraco): item `devolvido_paciente` → devolver → item vira `devolvido_prescritor`,
   prescrição vai a `transferida_prescritor`, o motivo do cidadão CHEGA renderizado ao
   painel, e a custódia de ITEM no nome do paciente é FECHADA (sem órfã).
   >>> DEVE FALHAR na main pré-fix (item continua `devolvido_paciente`, ausente da caixa).
3. GUARDA de coerência: nenhum item em `devolvido_paciente` enquanto a prescrição está
   em `transferida_prescritor`; e a receita devolvida não tem custódia de item órfã.

Coreografia via API de demo (mesma origem) — proven em test_coer2_e2e.py. O valor é a
asserção sobre o DOM renderizado + o estado do backend nas 3 telas.
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

_MOTIVO_FRESH = "Erro simples na receita virgem - COER2FIX FRESH"
_MOTIVO_NAO_FRESH = "Erro composto pos-estorno - COER2FIX NAO-FRESH"


# ---------------------------------------------------------------------------
# Coreografia via API de demo (mesma origem)
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


def _panel_entry(base_url: str, ptok: str, proto: str) -> dict | None:
    """Entrada da prescrição no painel do prescritor (GET /prescritor/prescricoes)."""
    d = _api(base_url, ptok, "GET", "/prescritor/prescricoes").json()
    for p in d["historico"]:
        if p["protocolo"] == proto:
            return p
    return None


def _in_correcoes(base_url: str, ptok: str, proto: str) -> bool:
    d = _api(base_url, ptok, "GET", "/prescritor/prescricoes").json()
    return any(p["protocolo"] == proto for p in d["correcoes"])


@pytest.fixture(scope="session")
def cenarios_fix(app_demo) -> dict:
    """Roda os 2 caminhos (fresh e não-fresh) uma vez e devolve os protocolos."""
    base = app_demo
    pt, pat, dt = _tok(base, "prescritor"), _tok(base, "paciente"), _tok(base, "dispensador")

    # --- FRESH: item pendente → devolver ao prescritor ---
    fresh = _emit_para_paciente(base, pt, "DIPIRONA-COER2FIX-FRESH")
    assert _api(base, pat, "POST", f"/paciente/prescricoes/{fresh}/devolver-prescritor",
                {"motivo": _MOTIVO_FRESH}).status_code == 201

    # --- NÃO-FRESH: item devolvido_paciente → devolver ao prescritor (o buraco) ---
    nf = _emit_para_paciente(base, pt, "AMOXICILINA-COER2FIX-NF")
    assert _api(base, pat, "POST", f"/paciente/prescricoes/{nf}/transferir-farmacia",
                {"cnpj_farmacia": _DISP}).status_code == 201
    iid = _item_id(base, dt, nf)
    rd = _api(base, dt, "POST", f"/prescricoes/{nf}/itens/{iid}/dispensar",
              {"cnpj_estabelecimento": _DISP, "quantidade_dispensada": 10})
    assert rd.status_code == 201, rd.text
    assert _api(base, dt, "POST", f"/dispensacoes/{rd.json()['dispensacao_id']}/estornar",
                {"motivo": "desistencia_paciente"}).status_code == 201
    rv = _api(base, dt, "POST", f"/prescricoes/{nf}/itens/{iid}/devolver",
              {"para": "paciente", "motivo": "desistiu"})
    assert rv.status_code == 200, rv.text  # item agora em devolvido_paciente
    # E AGORA o caminho que faltava: cidadão devolve ao médico um item devolvido_paciente.
    rdp = _api(base, pat, "POST", f"/paciente/prescricoes/{nf}/devolver-prescritor",
               {"motivo": _MOTIVO_NAO_FRESH})
    assert rdp.status_code == 201, rdp.text

    return {"fresh": fresh, "nao_fresh": nf, "item_id_nf": iid}


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
# 1. FRESH — regressão: continua aparecendo na caixa
# ---------------------------------------------------------------------------

def test_fix_fresh_aparece_na_caixa_de_correcoes(page, app_demo, cenarios_fix, erros_de_console):
    _autenticar(page, app_demo, "prescritor", _CNS, _NOME_P)
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

    devolvidas = page.locator("#lista-devolvidas")
    expect(devolvidas).to_contain_text("Erro simples na receita virgem", timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "prescritor.html (FIX fresh)")


# ---------------------------------------------------------------------------
# 2. NÃO-FRESH — o buraco do COER-2 (DEVE falhar na main pré-fix)
# ---------------------------------------------------------------------------

def test_fix_nao_fresh_motivo_chega_ao_prescritor(page, app_demo, cenarios_fix, erros_de_console):
    """🎯 Item devolvido_paciente → devolver ao médico → motivo RENDERIZADO na caixa.
    Na main pré-fix o item continuava devolvido_paciente e a receita não aparecia."""
    _autenticar(page, app_demo, "prescritor", _CNS, _NOME_P)
    page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

    devolvidas = page.locator("#lista-devolvidas")
    expect(devolvidas).to_contain_text("Erro composto pos-estorno", timeout=_TIMEOUT_MS)
    _sem_erros(erros_de_console, "prescritor.html (FIX não-fresh)")


def test_fix_nao_fresh_estado_backend_coerente(app_demo, cenarios_fix):
    """§5.3: item em devolvido_prescritor, prescrição em transferida_prescritor,
    receita na caixa de correções. Prova o backend sob o DOM."""
    proto = cenarios_fix["nao_fresh"]
    pt = _tok(app_demo, "prescritor")

    entry = _panel_entry(app_demo, pt, proto)
    assert entry is not None, "prescrição não-fresh sumiu do painel do prescritor"
    assert entry["status"] == "transferida_prescritor", entry["status"]
    status_itens = [i["status_item"] for i in entry["itens"]]
    # 🎯 o item TEM de ter virado devolvido_prescritor (na main pré-fix: devolvido_paciente).
    assert status_itens == ["devolvido_prescritor"], status_itens
    assert _in_correcoes(app_demo, pt, proto), "não-fresh não entrou em #correcoes"


def test_fix_nao_fresh_saiu_da_posse_do_cidadao(app_demo, cenarios_fix):
    """A receita devolvida ao médico sai da POSSE do cidadão (não é mais 'ativa')."""
    proto = cenarios_fix["nao_fresh"]
    pat = _tok(app_demo, "paciente")
    wallet = _api(app_demo, pat, "GET", "/paciente/prescricoes").json()
    posse = {p["protocolo"] for p in wallet["posse"]}
    assert proto not in posse, "receita devolvida ao médico ainda está na posse do cidadão"


def test_fix_nao_fresh_sem_custodia_de_item_orfa(app_demo, cenarios_fix):
    """🎯 COER2-POS-MERGE-FIX (custódia): ao virar terminal devolvido_prescritor, a
    custódia de ITEM no nome do paciente (aberta por devolver_item para=paciente) é
    FECHADA. Senão fica órfã — item terminal + custódia ativa = a mesma dupla posse
    que o COER-2 mata. Sob a prescrição, a custódia ativa é a de nível-prescrição no
    prescritor; NENHUMA custódia de item deve estar aberta."""
    proto = cenarios_fix["nao_fresh"]
    item_id = cenarios_fix["item_id_nf"]
    pt = _tok(app_demo, "prescritor")
    cust = _api(app_demo, pt, "GET", f"/prescricoes/{proto}/custodia").json()

    ativa = cust["custodia_ativa"]
    assert ativa is not None
    assert ativa["detentor_tipo"] == "prescritor", ativa
    assert ativa["item_id"] is None, ativa  # posse é da prescrição inteira, não do item

    # Nenhuma custódia de ITEM ativa (a do paciente foi fechada pelo fix).
    itens_ativos = cust.get("itens_custodia_ativa") or []
    orfas = [c for c in itens_ativos if c.get("item_id") == item_id and c.get("encerrada_em") is None]
    assert not orfas, f"custódia de item órfã (item terminal + custódia ativa): {orfas}"


# ---------------------------------------------------------------------------
# 3. GUARDA de coerência de estado (não pode haver a contradição de novo)
# ---------------------------------------------------------------------------

def test_fix_guarda_incoerencia_estado(app_demo, cenarios_fix):
    """Invariante: nenhum item em devolvido_paciente enquanto a prescrição está em
    transferida_prescritor (seria a incoerência do Cenário 2). Para item em
    devolvido_prescritor, a prescrição PODE (e deve) estar em transferida_prescritor."""
    pt = _tok(app_demo, "prescritor")
    d = _api(app_demo, pt, "GET", "/prescritor/prescricoes").json()
    for p in d["historico"]:
        if p["status"] == "transferida_prescritor":
            itens = [i["status_item"] for i in p["itens"]]
            assert "devolvido_paciente" not in itens, (
                f"INCOERÊNCIA: prescrição {p['protocolo']} em transferida_prescritor "
                f"com item devolvido_paciente: {itens}"
            )
