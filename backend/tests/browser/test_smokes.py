"""
tests/browser/test_smokes.py — os 4 smokes de navegador do TICKET-GATE-BROWSER.

É SMOKE, NÃO REGRESSÃO DE UI. A pergunta que estes testes respondem é "a tela
abre e mostra o essencial?", não "o pixel está no lugar?". Asserção de layout,
cor ou espaçamento NÃO entra aqui — envelhece mal e transforma o gate em ruído.

    (a) Portal → cada card entra no módulo sem quebrar
    (b) Dispensador: fila lista itens COM unidade e COM selo de controlado
    (c) Prescritor → aba Atestado: seletor de conselho POPULADO
    (d) Zero erro de console em cada tela

O smoke (c) é o guarda de regressão do defeito do #103 (temporal dead zone: a
IIFE de bootstrap rodava antes da declaração de `_catalogoConselhos`, e o
seletor de conselho ficava vazio). As guardas estáticas cobrem a ORDEM do
código; este cobre o RESULTADO. Ver o teste de mutação no docstring de
`TestSeletorDeConselho`.
"""
from __future__ import annotations

import pytest
from playwright.sync_api import expect

# Personas do seed de demo (backend/seed_demo.py).
_PRESCRITOR = {"sub": "980001112223334", "nome": "Dra. Demo Maria Souza"}

# Cards do portal → módulo de destino. Espelha index.html; o smoke (a) percorre
# todos. `clinica.html` e `validar.html` não passam pelo /demo/login (não têm
# papel), mas precisam abrir.
_CARDS = [
    ("prescritor.html", "Prescritor"),
    ("dispensador.html", "Dispensador"),
    ("cidadao.html", "Cidadão"),
    ("clinica.html", "Clínica / Laboratório"),
    ("validar.html", "Verificar Prescrição"),
]

_TIMEOUT_MS = 15_000


def _autenticar(page, base_url: str, role: str, sub: str, nome: str) -> None:
    """Semeia a sessão de demo antes de qualquer navegação.

    O frontend guarda a sessão em sessionStorage (NÃO localStorage). Fazemos o
    /demo/login por API e plantamos as chaves via `add_init_script`, em vez de
    clicar no portal: o objetivo do smoke é a TELA DE DESTINO, e passar pelo
    clique acoplaria cada teste ao portal (que já é o smoke (a)).
    """
    import httpx

    resp = httpx.post(f"{base_url}/demo/login", json={"role": role}, timeout=10.0)
    resp.raise_for_status()
    token = resp.json()["access_token"]

    page.add_init_script(
        f"""
        sessionStorage.setItem('picsaude_demo_token', {token!r});
        sessionStorage.setItem('picsaude_demo_role',  {role!r});
        sessionStorage.setItem('picsaude_demo_sub',   {sub!r});
        sessionStorage.setItem('picsaude_demo_nome',  {nome!r});
        """
    )


def _sem_erros(erros: list[str], tela: str) -> None:
    assert not erros, f"Erros de console/JS em {tela}:\n" + "\n".join(f"  - {e}" for e in erros)


# ---------------------------------------------------------------------------
# (a) Portal
# ---------------------------------------------------------------------------

class TestPortal:
    def test_portal_abre_e_lista_os_cards(self, page, app_demo, erros_de_console):
        page.goto(app_demo, wait_until="networkidle")

        for href, rotulo in _CARDS:
            card = page.locator(f'a.card[href="{href}"]')
            expect(card).to_be_visible(timeout=_TIMEOUT_MS)
            expect(card).to_contain_text(rotulo)

        _sem_erros(erros_de_console, "portal (index.html)")

    @pytest.mark.parametrize("href,rotulo", _CARDS, ids=[c[0] for c in _CARDS])
    def test_cada_card_entra_no_modulo(self, page, app_demo, erros_de_console, href, rotulo):
        """Navega direto para o destino de cada card e confirma que a tela monta.

        Navegação direta em vez de clique: em DEMO_MODE o portal intercepta o
        clique para fazer /demo/login, e só os papéis de `demo_roles` são
        interceptados — clicar em `clinica.html` e `validar.html` seguiria o link
        cru de qualquer forma. Navegar direto testa o que importa (a tela abre)
        de modo uniforme para os cinco.
        """
        page.goto(f"{app_demo}/{href}", wait_until="networkidle")

        # O <body> montou e tem conteúdo — o mínimo de "não quebrou".
        expect(page.locator("body")).not_to_be_empty(timeout=_TIMEOUT_MS)
        _sem_erros(erros_de_console, href)


# ---------------------------------------------------------------------------
# (b) Fila do dispensador
# ---------------------------------------------------------------------------

class TestFilaDispensador:
    """A fila do seed tem 3 itens, 1 deles controlado B1 (`_garantir_receita_na_fila`).

    Os dois marcadores auditados aqui não são cosméticos:
      - UNIDADE   → sem ela, "30" no balcão é ambíguo (30 comprimidos? 30 ml?).
      - CONTROLADO → é o que distingue uma receita comum de uma sujeita a
                     escrituração regulatória.
    """

    def test_fila_lista_itens_com_unidade_e_selo_de_controlado(
        self, page, app_demo, erros_de_console
    ):
        # dispensador.html se auto-autentica em DEMO_MODE, mas semeamos a sessão
        # explicitamente para não depender desse atalho.
        _autenticar(page, app_demo, "dispensador", "99999999000191", "Farmácia Demo Central")
        page.goto(f"{app_demo}/dispensador.html", wait_until="networkidle")

        lista = page.locator("#fila-lista")
        expect(lista).to_be_visible(timeout=_TIMEOUT_MS)

        # A fila carregou de fato — não ficou no "Carregando fila…" nem no vazio.
        linhas = lista.locator(".fila-med-row")
        expect(linhas.first).to_be_visible(timeout=_TIMEOUT_MS)

        # UNIDADE: todo saldo traz unidade. "não informada" é o texto que o
        # frontend usa quando o dado falta — se aparecer, o seed regrediu.
        saldos = lista.locator(".fila-saldo")
        assert saldos.count() > 0, "Nenhum saldo renderizado na fila."
        for i in range(saldos.count()):
            texto = saldos.nth(i).inner_text()
            assert "saldo" in texto.lower(), f"Saldo sem rótulo: {texto!r}"
            assert "não informada" not in texto, (
                f"Item na fila sem unidade de quantidade: {texto!r}. "
                "No balcão isso é uma quantidade ambígua."
            )

        # SELO DE CONTROLADO: o seed garante ao menos um item B1.
        selos = lista.locator(".fila-selo-controlado")
        assert selos.count() >= 1, (
            "Nenhum selo de controlado na fila. O seed cria 1 item B1 — "
            "ou o selo sumiu da tela, ou o seed regrediu."
        )
        # textContent é minúsculo; o uppercase é só CSS. Não asserir no visual.
        expect(selos.first).to_contain_text("controlado")

        _sem_erros(erros_de_console, "dispensador.html (fila)")


# ---------------------------------------------------------------------------
# (c) Seletor de conselho — guarda de regressão do #103
# ---------------------------------------------------------------------------

class TestSeletorDeConselho:
    """Guarda de regressão do defeito corrigido em 4933c20 (PR #103).

    O defeito: a IIFE de bootstrap chamava `_montarSeletoresRegistroAtestado()`
    antes da declaração `let _catalogoConselhos`, e o ReferenceError de temporal
    dead zone deixava o seletor de conselho com só o placeholder. O prescritor
    não conseguia escolher CFM/CFO — e o atestado sairia sempre como médico.

    TESTE DE MUTAÇÃO (executado, ver relato do ticket): movendo a IIFE de
    bootstrap para antes das declarações em prescritor.html, este teste FALHA —
    o select fica com 1 option (só o placeholder) e um 'pageerror' de
    ReferenceError aparece. Restaurada a ordem, passa. Guarda que não falha
    quando deveria é decoração.
    """

    def test_seletor_de_conselho_populado(self, page, app_demo, erros_de_console):
        _autenticar(page, app_demo, "prescritor", _PRESCRITOR["sub"], _PRESCRITOR["nome"])
        page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

        page.locator("#btn-submod-atestado").click()

        seletor = page.locator("#atestado-conselho")
        expect(seletor).to_be_visible(timeout=_TIMEOUT_MS)

        # A montagem é async (busca /config/public). Esperar o efeito, não o tempo.
        opcoes = seletor.locator("option")
        expect(opcoes).not_to_have_count(1, timeout=_TIMEOUT_MS)

        # value = slug federal, label = sigla regional. O prescritor vê "CRM",
        # o backend recebe "CFM" — asserir os dois lados, senão um swap passa.
        valores = seletor.locator("option").evaluate_all(
            "els => els.map(e => e.value).filter(Boolean)"
        )
        rotulos = seletor.locator("option").evaluate_all(
            "els => els.map(e => e.textContent.trim()).filter(Boolean)"
        )

        assert "CFM" in valores, f"Conselho CFM ausente do seletor. Valores: {valores}"
        assert "CFO" in valores, f"Conselho CFO ausente do seletor. Valores: {valores}"
        assert "CRM" in rotulos, f"Sigla CRM ausente do seletor. Rótulos: {rotulos}"
        assert "CRO" in rotulos, f"Sigla CRO ausente do seletor. Rótulos: {rotulos}"

        # A degradação é silenciosa por design (o atestado "sairia como médico").
        # Se o catálogo tivesse falhado, o hint diria — e o seletor acima já teria
        # falhado. Conferimos o hint para não confundir sucesso com degradação.
        hint = page.locator("#atestado-conselho-hint").inner_text()
        assert "indisponível" not in hint.lower(), (
            f"Seletor degradou para o modo 'sairia como médico': {hint!r}"
        )

        _sem_erros(erros_de_console, "prescritor.html (aba Atestado)")

    def test_escolher_odontologia_muda_o_documento(self, page, app_demo):
        """O seletor não só popula — ele MOVE o documento resultante.

        Sem isto, um seletor populado mas desconectado do handler passaria.
        """
        _autenticar(page, app_demo, "prescritor", _PRESCRITOR["sub"], _PRESCRITOR["nome"])
        page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        page.locator("#btn-submod-atestado").click()

        seletor = page.locator("#atestado-conselho")
        expect(seletor.locator("option")).not_to_have_count(1, timeout=_TIMEOUT_MS)

        seletor.select_option("CFO")
        expect(page.locator("#atestado-conselho-hint")).to_contain_text(
            "ODONTOLÓGICO", timeout=_TIMEOUT_MS
        )


# ---------------------------------------------------------------------------
# (d) Zero erro de console em cada tela
# ---------------------------------------------------------------------------

class TestConsoleLimpo:
    """Rede fina que pega o que os smokes específicos não olham.

    Vale especialmente para 'pageerror': o ReferenceError do #103 era invisível
    para qualquer asserção de conteúdo que não olhasse justamente o seletor.
    """

    @pytest.mark.parametrize("href", [c[0] for c in _CARDS] + [""], ids=lambda h: h or "index.html")
    def test_tela_sem_erro_de_console(self, page, app_demo, erros_de_console, href):
        page.goto(f"{app_demo}/{href}", wait_until="networkidle")
        expect(page.locator("body")).not_to_be_empty(timeout=_TIMEOUT_MS)
        _sem_erros(erros_de_console, href or "index.html")
