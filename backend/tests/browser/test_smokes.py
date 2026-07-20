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

import re

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
# (d) Carteira do cidadão — seção de atestados
# ---------------------------------------------------------------------------

class TestAtestadoNaCarteira:
    """TICKET-ATESTADO-CARTEIRA-CIDADAO — o atestado chega ao paciente.

    O seed cria DEMO-ATESTADO-0001 já sob custódia do paciente (a transferência
    acontece na emissão). Este smoke prova o ponto do ticket: entre emitir e o
    cidadão VER não existe nenhuma ação do prescritor. Se um dia alguém
    acrescentar um passo "enviar atestado", este teste fica vermelho — que é
    exatamente o alarme desejado.
    """

    def _abrir_carteira(self, page, app_demo):
        _autenticar(page, app_demo, "paciente", "12345678909", "João Demo da Silva")
        page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        lista = page.locator("#lista-atestados")
        expect(lista).to_be_visible(timeout=_TIMEOUT_MS)
        return lista

    def test_atestado_do_seed_aparece_sem_acao_do_prescritor(
        self, page, app_demo, erros_de_console
    ):
        lista = self._abrir_carteira(page, app_demo)

        # Carregou de fato — não ficou no estado vazio.
        expect(lista).not_to_contain_text("Nenhum atestado disponível", timeout=_TIMEOUT_MS)

        # O TÍTULO vem do backend (domain/conselho_profissional). O HTML não
        # conhece "ATESTADO MÉDICO"; se conhecesse, a bifurcação médico vs.
        # odontológico existiria em dois lugares.
        expect(lista).to_contain_text("ATESTADO MÉDICO", timeout=_TIMEOUT_MS)
        expect(lista).to_contain_text("trabalhistas")
        expect(lista).to_contain_text("Recife")

        # O seed afasta por 3 dias — a linha de afastamento tem que existir.
        expect(lista).to_contain_text("Afastamento")
        expect(lista).to_contain_text("3 dia(s)")

        # E o botão de PDF, que é como o documento sai da carteira.
        expect(lista.get_by_role("button", name=re.compile("Baixar PDF"))).to_be_visible()

        _sem_erros(erros_de_console, "cidadao.html (atestados)")

    def test_carteira_nao_exibe_diagnostico(self, page, app_demo):
        """CID não entra na LISTA (CFM art. 3º).

        O CID é opcional e só entra no documento com anuência do paciente. Numa
        lista viraria exibição incidental de diagnóstico — o titular abre a
        carteira para ver um comprovante e leva o diagnóstico na tela junto.
        """
        lista = self._abrir_carteira(page, app_demo)
        texto = lista.inner_text()

        assert "CID" not in texto.upper(), (
            f"Diagnóstico exposto na carteira: {texto!r}"
        )

    def test_atestado_sem_afastamento_nao_mostra_campo_de_dias(self, page, app_demo):
        """AUSÊNCIA É INFORMAÇÃO: nem todo atestado afasta.

        Um atestado de comparecimento não tem dias. Renderizar "Afastamento: —"
        afirmaria que houve afastamento de nada; a linha inteira tem que sumir.
        O atestado é emitido pela API (o seed só tem o de 3 dias) e chega à
        carteira sem nenhuma ação extra — mesma prova do primeiro teste.
        """
        import httpx

        token = httpx.post(
            f"{app_demo}/demo/login", json={"role": "prescritor"}, timeout=10.0
        ).json()["access_token"]
        criado = httpx.post(
            f"{app_demo}/atestados",
            json={
                "cns_prescritor": _PRESCRITOR["sub"],
                "nome_prescritor": _PRESCRITOR["nome"],
                "cpf_paciente": "12345678909",
                "nome_paciente": "João Demo da Silva",
                "finalidade": "Comparecimento a consulta",
                "municipio_emissao": "Recife",
                "dias_afastamento": None,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        assert criado.status_code == 201, criado.text

        lista = self._abrir_carteira(page, app_demo)
        expect(lista).to_contain_text("Comparecimento a consulta", timeout=_TIMEOUT_MS)

        card = lista.locator(".exame-card").filter(
            has_text="Comparecimento a consulta"
        )
        assert "Afastamento" not in card.inner_text(), (
            f"Campo de dias renderizado num atestado que não afasta: "
            f"{card.inner_text()!r}"
        )

    def test_sem_botao_de_enviar(self, page, app_demo):
        """O atestado É do paciente: o profissional entrega, não retém.

        Um "enviar ao paciente" aqui significaria estar tratando atestado como
        receita — a receita exige o envio explícito, o atestado não.
        """
        lista = self._abrir_carteira(page, app_demo)

        assert "enviar" not in lista.inner_text().lower()


# ---------------------------------------------------------------------------
# (e) Imprimir rascunho funciona com bloqueador de pop-up
# ---------------------------------------------------------------------------

# Simula o AMBIENTE do Fabiano e instrumenta o resultado. Roda antes de qualquer
# script da página (add_init_script):
#
#   1. `window.open` devolve null — é o que um bloqueador de pop-up faz em
#      domínio não confiável (127.0.0.1). Era exatamente aqui que o clique
#      morria calado.
#   2. `print` de todo iframe passa a contar em vez de abrir diálogo. Sem isto o
#      headless poderia travar num diálogo de impressão, e não teríamos como
#      afirmar que a impressão foi REALMENTE disparada — só que o iframe existe.
_SIMULAR_BLOQUEADOR_DE_POPUP = """
(() => {
  window.open = () => null;
  window.__impressoes = 0;
  const getter = Object.getOwnPropertyDescriptor(
    HTMLIFrameElement.prototype, 'contentWindow').get;
  Object.defineProperty(HTMLIFrameElement.prototype, 'contentWindow', {
    get() {
      const w = getter.call(this);
      if (w && !w.__printPatched) {
        w.__printPatched = true;
        w.print = () => { window.__impressoes += 1; };
      }
      return w;
    }
  });
})();
"""

# Mutação: o veículo novo falha. Prova que a SEGUNDA camada (aviso visível)
# existe de verdade — uma guarda que nunca é exercitada é decoração.
_SABOTAR_IFRAME = """
(() => {
  const original = document.createElement.bind(document);
  document.createElement = (tag, ...resto) => {
    if (String(tag).toLowerCase() === 'iframe') {
      throw new Error('iframe negado (mutação de teste)');
    }
    return original(tag, ...resto);
  };
})();
"""


class TestImpressaoDoRascunho:
    """O defeito que Fabiano encontrou: "Imprimir rascunho não funcionou".

    `window.open('', '_blank', …)` devolve null sob bloqueador de pop-up, e o
    código saía por um `return` mudo. Funcionava em picsaude.com.br (domínio
    confiável) e não em 127.0.0.1 — não era regressão, era ambiente. Mesma
    doutrina do R4 aplicada à tela: falhar alto, nunca calar.

    Os dois testes cobrem as duas camadas da correção:
      - o iframe, que nenhum bloqueador intercepta (caminho feliz);
      - o aviso visível, para o que ainda assim escapar (mutação).
    """

    def _abrir_rascunho(self, page, app_demo):
        """Preenche o mínimo para a IA Documental devolver ok=True."""
        _autenticar(page, app_demo, "prescritor", _PRESCRITOR["sub"], _PRESCRITOR["nome"])
        page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")
        page.locator("#btn-submod-atestado").click()

        page.locator("#atestado-paciente").fill("João Demo da Silva")
        page.locator("#atestado-finalidade").select_option("trabalhistas")
        page.locator("#atestado-dias").fill("3")
        page.locator("#atestado-data").fill("2026-07-20")
        page.locator("#atestado-municipio").fill("Recife")
        page.locator("#atestado-profissional").fill("Dra. Demo Maria Souza")
        page.locator("#atestado-registro").fill("12345")

        page.get_by_role("button", name=re.compile("Validar atestado")).click()

        preview = page.locator("#atestado-preview-texto")
        expect(preview).to_be_visible(timeout=_TIMEOUT_MS)
        return preview

    def test_imprime_mesmo_com_popup_bloqueado(self, page, app_demo, erros_de_console):
        """O cenário do Fabiano: pop-up bloqueado, e a impressão ACONTECE."""
        page.add_init_script(_SIMULAR_BLOQUEADOR_DE_POPUP)
        self._abrir_rascunho(page, app_demo)

        page.get_by_role("button", name=re.compile("Imprimir rascunho")).click()

        # 1. A impressão foi disparada — não basta o iframe existir.
        expect(page.locator("#picsaude-print-frame")).to_have_count(1, timeout=_TIMEOUT_MS)
        page.wait_for_function("() => window.__impressoes > 0", timeout=_TIMEOUT_MS)

        # 2. E o que foi para a impressora é o PAPEL DE TRABALHO, não um
        #    documento com cara de atestado pronto.
        conteudo = page.frame_locator("#picsaude-print-frame").locator("body")
        expect(conteudo).to_contain_text("RASCUNHO — SEM VALIDADE LEGAL", timeout=_TIMEOUT_MS)
        expect(conteudo).not_to_contain_text("Protocolo")

        # 3. Caminho feliz não mostra aviso de falha.
        assert page.locator("#atestado-print-aviso").inner_text().strip() == ""

        _sem_erros(erros_de_console, "prescritor.html (imprimir rascunho)")

    def test_falha_do_iframe_vira_aviso_visivel_nunca_silencio(self, page, app_demo):
        """MUTAÇÃO: iframe negado → o usuário PRECISA saber.

        Sem esta camada, qualquer falha futura do veículo reproduz o defeito
        original — clique sem efeito e sem explicação.
        """
        page.add_init_script(_SIMULAR_BLOQUEADOR_DE_POPUP)
        page.add_init_script(_SABOTAR_IFRAME)
        self._abrir_rascunho(page, app_demo)

        page.get_by_role("button", name=re.compile("Imprimir rascunho")).click()

        aviso = page.locator("#atestado-print-aviso")
        expect(aviso).to_be_visible(timeout=_TIMEOUT_MS)
        expect(aviso).to_contain_text("bloqueou a impressão", timeout=_TIMEOUT_MS)
        # Diz o que fazer, não só que falhou.
        expect(aviso).to_contain_text("Ctrl+P")


# ---------------------------------------------------------------------------
# (f) Ação que desiste avisa — TICKET-FALHA-SILENCIOSA-FRONTEND
# ---------------------------------------------------------------------------

class TestAcaoAvisaQuandoDesiste:
    """As guardas estáticas dizem que a chamada de aviso ESTÁ no código.
    Este smoke diz que o aviso APARECE na tela — perguntas diferentes.

    `prescritor.html` não tem markup de toast: o elemento e o CSS nascem do
    config.js sob demanda. Se essa criação quebrar, a chamada continua lá e a
    guarda estática continua verde — só este teste pega.
    """

    def test_baixar_pdf_sem_emissao_mostra_aviso(self, page, app_demo, erros_de_console):
        _autenticar(page, app_demo, "prescritor", _PRESCRITOR["sub"], _PRESCRITOR["nome"])
        page.goto(f"{app_demo}/prescritor.html", wait_until="networkidle")

        # Nenhum atestado emitido nesta sessão: a ação desiste — e tem de dizer.
        page.evaluate("baixarPdfAtestado()")

        toast = page.locator("#picsaude-toast")
        expect(toast).to_be_visible(timeout=_TIMEOUT_MS)
        expect(toast).to_contain_text("Nenhum atestado emitido", timeout=_TIMEOUT_MS)
        # Diz o que FAZER, não só que falhou.
        expect(toast).to_contain_text("Emita o atestado")

        _sem_erros(erros_de_console, "prescritor.html (aviso de ação)")

    def test_promocao_do_toast_nao_quebrou_a_carteira(self, page, app_demo):
        """cidadao.html tinha a implementação original e ~20 chamadores.

        A promoção para o config.js manteve nome e assinatura; este teste prova
        que a página segue usando o SEU elemento, sem ganhar um segundo.
        """
        page.goto(f"{app_demo}/cidadao.html", wait_until="networkidle")
        page.evaluate("showToast('promocao ok', 'success')")

        toast = page.locator("#picsaude-toast")
        expect(toast).to_be_visible(timeout=_TIMEOUT_MS)
        expect(toast).to_contain_text("promocao ok")
        assert toast.count() == 1, "config.js criou um segundo toast por cima do da página"


# ---------------------------------------------------------------------------
# (g) Zero erro de console em cada tela
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
