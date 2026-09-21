"""
tests/browser/test_eng018_receita_viva.py — as guardas da RECEITA VIVA (ENG-018).

O QUE ESTE ARQUIVO DEFENDE
--------------------------
O desenho (`docs/tickets/DESENHO-RECEITA-VIVA.md`) parte de um defeito medido: no
papel a receita existe DURANTE o ato; nesta tela ela só nascia depois do ponto de
não-retorno. O conserto é a folha ao lado da pena — e a peça central não é o
layout, é o **template único**: UMA função geradora, DOIS alvos.

A guarda que importa é a §7 do despacho, o W ≡ Y: **o mesmo estado renderiza
igual nos dois alvos, e sabotar um deles reprova o teste**. Sem ela, "zero
surpresa no pós-emissão" seria intenção; com ela, é invariante — e é o que
impede a volta do defeito que o ticket fechou (dois templates do mesmo
documento, livres para derivar em silêncio).

Um AC, um teste, nomeado pelo AC. Os nove do §4 do despacho estão aqui.

PADRÃO
------
Segue os smokes da casa: `app_demo` (subprocesso efêmero em DEMO_MODE) e
asserções sobre o DOM RENDERIZADO. Em DEMO o par nome+CPF do paciente é
`readonly` (lock M-D) — daí os testes preencherem tudo MENOS esses dois.
"""
from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

_TIMEOUT_MS = 15_000

# Um CID que NÃO é o digitado na indicação — o par do AC6.
_CID_CANONICO = "E11"
_CID_DESCRICAO = "Diabetes mellitus tipo 2"

# Placeholders do FORMULÁRIO. Nenhum deles pode aparecer na folha como texto:
# lá o vocabulário é o do DOCUMENTO, e placeholder vazado seria a folha
# mentindo sobre o que o cidadão vai receber (AC2).
_PLACEHOLDERS_DO_FORMULARIO = (
    "Ex: 45",
    "DDD + Número",
    "Apto, Bloco",
    "Princípio ativo (sem dose)",
    "Instruções de Uso (Posologia)",
    "Forma farmacêutica (ex: comprimido revestido)",
    "Apresentação comercial",
    "Hipótese diagnóstica ou motivo",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _abrir(pg: Page, base: str) -> None:
    pg.goto(f"{base}/prescritor.html", wait_until="networkidle")
    # A folha está MONTADA (não necessariamente à vista): em viewport de
    # celular ela mora atrás do botão flutuante, e exigir visibilidade aqui
    # faria o helper contradizer a martelada ③.
    expect(pg.locator("#folha-viva .rec-folha")).to_have_count(1, timeout=_TIMEOUT_MS)


def _card(pg: Page, n: int = 0):
    return pg.locator("#lista-medicamentos .med-card").nth(n)


def _preencher_paciente(pg: Page) -> None:
    """Tudo menos nome e CPF — esses dois são do lock M-D em DEMO."""
    pg.fill("#pac-idade", "58")
    pg.fill("#pac-telefone", "81999990000")
    pg.fill("#pac-endereco", "Rua das Flores, 123 - Boa Viagem")
    pg.fill("#pac-complemento", "Apto 502")
    pg.fill("#pac-cidade", "Recife")
    pg.fill("#pac-cep", "51021030")


def _preencher_farmaco(pg: Page, n: int = 0, nome: str = "Losartana Potassica") -> None:
    card = _card(pg, n)
    card.locator(".med-nome").fill(nome)
    card.locator(".med-conc").fill("50 mg")
    card.locator(".med-qtd").fill("30")
    card.locator(".med-unidade").select_option("comprimido")
    card.locator(".med-forma").fill("comprimido revestido")
    card.locator(".med-posologia").fill("Tomar 1 comprimido pela manha, todos os dias.")


def _receita_completa(pg: Page) -> None:
    _preencher_paciente(pg)
    _preencher_farmaco(pg)
    pg.wait_for_timeout(300)


def _texto_da_folha(pg: Page) -> str:
    """O texto do documento pela régua ÚNICA (`Receituario.textoDoDocumento`).

    Não normalizamos por conta própria: W ≡ Y só vale se os dois lados forem
    medidos pela mesma régua, e essa régua tem dono (receituario.js).
    """
    return pg.evaluate("() => Receituario.textoDoDocumento('folha-viva')")


def _texto_do_documento(pg: Page) -> str:
    return pg.evaluate("() => Receituario.textoDoDocumento('print-area')")


def _alvos_batem(pg: Page) -> bool:
    """W ≡ Y medido numa TACADA só, dentro da página.

    Ler um alvo e depois o outro em chamadas separadas abre janela para um
    repintar legítimo cair no meio (o debounce da IA Farmacêutica mexe no card
    e a folha se refaz). O resultado seria um teste que acusa — ou absolve —
    por acidente de tempo. Uma avaliação síncrona não tem esse meio.
    """
    return pg.evaluate(
        """() => Receituario.textoDoDocumento('folha-viva')
                 === Receituario.textoDoDocumento('print-area')"""
    )


# ===========================================================================
# AC1 — a folha se escreve a cada tecla
# ===========================================================================

def test_ac1_a_folha_se_escreve_a_cada_tecla(page: Page, app_demo):
    """Cada campo cai na folha no evento de input — e a delegação aguenta
    card removido, recriado e limpo (o padrão do `_initBuscaMedDelegada`)."""
    _abrir(page, app_demo)

    _preencher_paciente(page)
    page.fill("#prescricao-indicacao", "Hipertensao arterial sistemica")
    _preencher_farmaco(page)
    page.wait_for_timeout(300)

    folha = _texto_da_folha(page)
    for pedaco in (
        "58 anos",
        "81999990000",
        "Rua das Flores, 123 - Boa Viagem",
        "Comp: Apto 502",
        "51021-030",
        "Recife - PE",
        "Hipertensao arterial sistemica",
        "LOSARTANA POTASSICA",
        "50 mg",
        "30 comprimido",
        "comprimido revestido",
        "Tomar 1 comprimido pela manha",
    ):
        assert pedaco in folha, f"{pedaco!r} digitado no formulário não apareceu na folha"

    # — card NOVO: a delegação alcança o que ainda não existia
    page.get_by_role("button", name="+ Adicionar Fármaco").click()
    _preencher_farmaco(page, 1, nome="Hidroclorotiazida")
    page.wait_for_timeout(300)
    assert "HIDROCLOROTIAZIDA" in _texto_da_folha(page)
    expect(page.locator('#folha-viva .rec-item[data-item="2"]')).to_have_count(1)

    # — card REMOVIDO: a folha encolhe junto
    _card(page, 1).get_by_role("button", name="X Remover").click()
    page.wait_for_timeout(300)
    assert "HIDROCLOROTIAZIDA" not in _texto_da_folha(page)
    expect(page.locator('#folha-viva .rec-item[data-item="2"]')).to_have_count(0)

    # — card LIMPO: volta a lacuna, o fármaco some do documento
    _card(page, 0).get_by_role("button", name="Limpar").click()
    page.wait_for_timeout(300)
    assert "LOSARTANA POTASSICA" not in _texto_da_folha(page)
    expect(page.locator('#folha-viva .rec-item[data-item="1"] .rec-lacuna')).not_to_have_count(0)


# ===========================================================================
# AC2 — lacuna pontilhada, e nenhum placeholder de formulário vazado
# ===========================================================================

def test_ac2_campo_vazio_e_lacuna_e_placeholder_nao_vaza(page: Page, app_demo):
    _abrir(page, app_demo)

    # Numa folha em branco, os campos que o documento final exibe estão todos
    # pontilhados — inclusive protocolo e hash (a outra metade do AC4).
    # `local-data` fica de fora de propósito: a data existe sempre, então esse
    # campo nunca é lacuna — listá-lo aqui seria exigir o que o documento não
    # promete.
    for campo in ("protocolo", "hash", "paciente-telefone", "paciente-endereco",
                  "emitente-contato", "assinatura"):
        expect(
            page.locator(f'#folha-viva [data-campo="{campo}"] .rec-lacuna')
        ).not_to_have_count(0), f"campo vazio {campo!r} deveria aparecer como lacuna"

    folha = _texto_da_folha(page)
    for placeholder in _PLACEHOLDERS_DO_FORMULARIO:
        assert placeholder not in folha, (
            f"placeholder do formulário {placeholder!r} vazou para a folha como "
            "texto do documento"
        )

    # A lacuna SOME quando a tinta cai — ela é espera, não decoração fixa.
    page.fill("#pac-telefone", "81999990000")
    page.wait_for_timeout(300)
    expect(page.locator('#folha-viva [data-campo="paciente-telefone"] .rec-lacuna')).to_have_count(0)


# ===========================================================================
# AC3 — TEMPLATE ÚNICO POR CONSTRUÇÃO (W ≡ Y) — a guarda central do ticket
# ===========================================================================

def test_ac3_w_equivale_a_y_e_sabotar_um_alvo_reprova(page: Page, app_demo):
    """Mesmo estado → mesmo documento nos dois alvos. E a guarda MORDE:
    adulterar o `#print-area` faz a comparação falhar na hora."""
    _abrir(page, app_demo)
    _receita_completa(page)

    assert _alvos_batem(page), (
        "a folha viva e o #print-area divergiram no MESMO estado — o template "
        "deixou de ser único (DESENHO-RECEITA-VIVA.md §3)"
    )

    # — vermelho por construção: a sabotagem e as duas leituras acontecem na
    #   MESMA tacada, senão um repintar legítimo apagaria a adulteração antes
    #   da medição e a guarda passaria verde sem ter sido posta à prova.
    veredito = page.evaluate(
        """() => {
            const igual = () => Receituario.textoDoDocumento('folha-viva')
                                === Receituario.textoDoDocumento('print-area');
            const antes = igual();
            document.querySelector('#print-area [data-bloco="paciente"]')
                    .insertAdjacentHTML('beforeend', '<span>SABOTAGEM</span>');
            return { antes: antes, depois: igual() };
        }"""
    )
    assert veredito["antes"] is True
    assert veredito["depois"] is False, (
        "a comparação W ≡ Y não detectou uma divergência plantada — a guarda "
        "está cega e não protege nada"
    )

    # — e volta ao normal na próxima tecla: os dois alvos saem da mesma função
    page.fill("#pac-telefone", "81988887777")
    page.wait_for_timeout(300)
    assert _alvos_batem(page)


# ===========================================================================
# AC4 — o carimbo cai na MESMA folha, sem navegar
# ===========================================================================

def test_ac4_o_carimbo_cai_na_mesma_folha_sem_navegar(page: Page, app_demo):
    _abrir(page, app_demo)
    _receita_completa(page)

    # Antes: protocolo e hash pontilhados.
    expect(page.locator('#folha-viva [data-campo="protocolo"] .rec-lacuna')).to_have_count(1)
    expect(page.locator('#folha-viva [data-campo="hash"] .rec-lacuna')).to_have_count(1)

    # Marca o nó da folha: se a tela navegasse para um render novo, a marca
    # morreria junto com o elemento.
    page.evaluate("() => { document.getElementById('folha-viva').dataset.marcaDoTeste = 'a-mesma-folha'; }")

    page.locator("#btn-emitir").click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)

    assert page.evaluate(
        "() => document.getElementById('folha-viva').dataset.marcaDoTeste"
    ) == "a-mesma-folha", "a folha foi substituída na emissão — houve render novo"

    # A tela NÃO navegou: o dashboard e o formulário seguem no ar.
    expect(page.locator("#tela-dashboard")).to_be_visible()
    expect(page.locator("#submod-receita")).to_be_visible()
    expect(page.locator("#folha-viva")).to_be_visible()

    # E o carimbo caiu: protocolo e hash preencheram as próprias lacunas.
    expect(page.locator('#folha-viva [data-campo="protocolo"] .rec-lacuna')).to_have_count(0)
    expect(page.locator('#folha-viva [data-campo="hash"] .rec-lacuna')).to_have_count(0)
    expect(page.locator("#folha-viva .rec-carimbo")).to_be_visible()

    folha = _texto_da_folha(page)
    assert re.search(r"Protocolo: [0-9a-f]{8}-[0-9a-f]{4}", folha), (
        f"protocolo do backend não carimbou a folha: {folha[:200]!r}"
    )
    assert re.search(r"Hash SHA-256: [0-9a-f]{64}", folha), (
        f"hash de integridade não carimbou a folha: {folha[:200]!r}"
    )

    # O documento acompanhou — o carimbo não é enfeite de tela.
    assert _alvos_batem(page)


def test_ac4_receita_emitida_nao_se_edita(page: Page, app_demo):
    """§1 dentro da tela: com a receita emitida, mexer no formulário não
    reescreve o documento carimbado. Ele é imutável — e a folha diz isso."""
    _abrir(page, app_demo)
    _receita_completa(page)
    page.locator("#btn-emitir").click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)

    congelada = _texto_da_folha(page)
    page.fill("#pac-telefone", "81900000000")
    page.wait_for_timeout(300)
    assert _texto_da_folha(page) == congelada, (
        "editar o formulário alterou a folha JÁ EMITIDA — objeto sanitário "
        "emitido não se edita (CLAUDE.md §1)"
    )

    # "Nova Prescrição" devolve o papel em branco — de verdade. Não basta o
    # carimbo sumir: o que foi digitado tem de sair da folha junto. `.reset()`
    # não dispara evento algum, então uma folha que dependesse do acaso de
    # algum input disparar ficaria com os dados do paciente anterior à vista.
    page.get_by_role("button", name="Nova Prescrição").click()
    expect(page.locator("#painel-emissao")).to_be_hidden(timeout=_TIMEOUT_MS)
    expect(page.locator('#folha-viva [data-campo="protocolo"] .rec-lacuna')).to_have_count(1)
    em_branco = _texto_da_folha(page)
    for resto in ("81900000000", "Rua das Flores", "Losartana", "LOSARTANA", "Recife - PE"):
        assert resto not in em_branco, (
            f"{resto!r} da receita anterior sobrou na folha depois de "
            "'Nova Prescrição'"
        )
    assert _alvos_batem(page)


# ===========================================================================
# AC5 — a pena não é engolida pela folha (desktop comum, 1366px)
# ===========================================================================

def test_ac5_a_pena_nao_e_engolida_pela_folha_em_1366(page: Page, app_demo):
    page.set_viewport_size({"width": 1366, "height": 900})
    _abrir(page, app_demo)
    _preencher_farmaco(page)

    # Um bloco de IA Farmacêutica real, do tamanho que ela desenha.
    page.evaluate(
        """() => {
            const c = document.querySelector('#lista-medicamentos .med-card .ia-container');
            c.innerHTML = '<div class="ia-bloco ia-bloco-sugestao">'
                + '<div class="ia-header">IA Farmacêutica</div>'
                + '<div class="ia-chips"><span class="ia-chip">comprimido revestido</span>'
                + '<span class="ia-chip">50 mg</span></div>'
                + '<div class="ia-meta">base DCB &middot; confianca alta</div></div>';
        }"""
    )
    page.wait_for_timeout(200)

    pena = page.locator(".receita-pena").bounding_box()
    papel = page.locator("#folha-viva").bounding_box()
    assert pena and papel
    assert pena["width"] >= 520, (
        f"a coluna da pena ficou com {pena['width']:.0f}px em 1366 — os painéis "
        "de IA, semáforo e sugestões não cabem legíveis"
    )
    assert papel["width"] >= 420, f"a folha ficou estreita demais ({papel['width']:.0f}px)"

    # Os dois lados convivem: a folha está à direita da pena, não por cima.
    assert papel["x"] >= pena["x"] + pena["width"] - 1, "a folha invadiu a coluna da pena"

    # O bloco de IA cabe inteiro na coluna esquerda.
    ia = page.locator("#lista-medicamentos .med-card .ia-bloco").bounding_box()
    assert ia and ia["width"] >= 300, f"bloco de IA espremido ({ia['width'] if ia else 0:.0f}px)"
    assert ia["x"] + ia["width"] <= pena["x"] + pena["width"] + 2, "o bloco de IA vazou da coluna"

    expect(page.locator("#lista-medicamentos .med-card .med-semaforo")).to_have_count(1)

    # E a tela não passou a rolar de lado por causa do palco alargado.
    largura, viewport = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )
    assert largura <= viewport + 2, f"rolagem horizontal em 1366px ({largura} > {viewport})"


# ===========================================================================
# AC6 — o selo de CID vem do valor CANÔNICO (o hidden do typeahead)
# ===========================================================================

def test_ac6_selo_de_cid_vem_do_hidden_canonico(page: Page, app_demo):
    _abrir(page, app_demo)

    # O texto digitado MENCIONA outro CID de propósito: o selo não pode sair
    # daqui. A folha não adivinha diagnóstico.
    page.fill("#prescricao-indicacao", "quadro compativel com I10, investigar")
    # O caminho real do botão "Usar este CID" do typeahead.
    page.evaluate(
        """([codigo, desc]) => _usarCid('ia-cid-prescricao-chips',
                                        'prescricao-cid-escolhido', codigo, desc)""",
        [_CID_CANONICO, _CID_DESCRICAO],
    )
    page.wait_for_timeout(300)

    selo = page.locator("#folha-viva .rec-selo-cid")
    expect(selo).to_have_count(1)
    expect(selo).to_contain_text(f"CID-10 {_CID_CANONICO}")
    expect(selo).to_contain_text(_CID_DESCRICAO)
    assert page.locator('#folha-viva .rec-selo-cid[data-cid="I10"]').count() == 0, (
        "o selo saiu do TEXTO digitado na indicação, não do hidden canônico"
    )

    # Tirar a etiqueta tira o selo — a fonte é uma só.
    page.locator("#ia-cid-prescricao-chips .ia-cid-chip-x").click()
    page.wait_for_timeout(300)
    expect(page.locator("#folha-viva .rec-selo-cid")).to_have_count(0)


# ===========================================================================
# AC7 — M-D e A2 sobrevivem ao campo que subiu de seção
# ===========================================================================

def test_ac7_md_e_a2_sobrevivem_ao_cpf_que_subiu(page: Page, app_demo):
    _abrir(page, app_demo)

    chave = page.locator("#pac-chave")

    # Martelada ① — o campo agora senta na Identificação do paciente, junto do
    # nome e do endereço, e não mais no bloco de Modo de Emissão.
    bloco = page.locator("#main-prescription-form > div").first
    expect(bloco).to_contain_text("Identificação do Paciente")
    assert bloco.locator("#pac-chave").count() == 1, (
        "o CPF/CNI não está no bloco de identificação do paciente (martelada ①)"
    )
    assert page.locator("#pac-nome").count() == 1

    # A2 — a máscara numérica viajou com o campo.
    expect(chave).to_have_attribute("data-tipo", "cpf")
    expect(chave).to_have_class(re.compile(r"\bcpf-input\b"))

    # M-D — em DEMO o par nome+CPF continua travado no cidadão canônico...
    assert chave.evaluate("el => el.readOnly") is True, "lock M-D do CPF sumiu"
    assert page.locator("#pac-nome").evaluate("el => el.readOnly") is True, "lock M-D do nome sumiu"

    # ...e é o valor travado que a folha exibe, já mascarado.
    assert re.search(r"CPF / CNI: \d{3}\.\d{3}\.\d{3}-\d{2}", _texto_da_folha(page)), (
        f"o CPF travado não chegou formatado à folha: {_texto_da_folha(page)[:300]!r}"
    )


# ===========================================================================
# AC8 — mobile: o flutuante não cobre o botão de emitir
# ===========================================================================

def _se_cruzam(a: dict, b: dict) -> bool:
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def test_ac8_o_flutuante_nunca_cobre_o_botao_de_emitir(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)

    fab = page.locator("#receita-fab")
    emitir = page.locator("#btn-emitir")

    # Longe do gesto de emitir, a chamada da folha está lá.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(300)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)

    # Com o botão de emitir em cena, os dois não podem dividir o canto.
    emitir.scroll_into_view_if_needed()
    page.wait_for_timeout(400)
    caixa_fab = fab.bounding_box() if fab.is_visible() else None
    caixa_emitir = emitir.bounding_box()
    assert caixa_emitir is not None
    if caixa_fab is not None:
        assert not _se_cruzam(caixa_fab, caixa_emitir), (
            "o botão flutuante da folha está por cima do botão de emitir"
        )

    # E ele volta quando o gesto sai de cena — recolher não pode virar sumir.
    page.evaluate("() => window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    expect(fab).to_be_visible(timeout=_TIMEOUT_MS)


def test_ac8_o_flutuante_abre_e_fecha_a_folha(page: Page, app_demo):
    page.set_viewport_size({"width": 390, "height": 844})
    _abrir(page, app_demo)
    _preencher_farmaco(page)

    papel = page.locator("#receita-papel")
    expect(papel).to_be_hidden()

    page.locator("#receita-fab").click()
    expect(papel).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#folha-viva")).to_contain_text("LOSARTANA POTASSICA")

    page.get_by_role("button", name="✕ Voltar ao formulário").click()
    expect(papel).to_be_hidden(timeout=_TIMEOUT_MS)


# ===========================================================================
# AC9 — o fluxo físico sai pelo MESMO documento
# ===========================================================================

@pytest.fixture
def sem_dialogo_de_impressao(page: Page):
    """`window.print()` abre diálogo nativo e trava a sessão — trocamos por um
    contador. Não é atalho de teste: é o único jeito de PROVAR que a impressão
    foi chamada sem congelar o navegador."""
    page.add_init_script(
        "window.__impressoes = 0; window.print = () => { window.__impressoes += 1; };"
    )
    return page


def test_ac9_fluxo_fisico_sai_pelo_mesmo_documento(sem_dialogo_de_impressao, app_demo):
    page = sem_dialogo_de_impressao
    _abrir(page, app_demo)
    _receita_completa(page)

    page.get_by_role(
        "button", name="🖨️ Apenas Imprimir Físico (sem envio digital)"
    ).click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)
    expect(page.locator("#sucesso-titulo")).to_have_text("Prescrição Física Registrada")

    # O documento impresso é a MESMA folha — sem adaptação de roteiro.
    assert _alvos_batem(page)

    documento = _texto_do_documento(page)
    assert "Emissão física — sem custódia digital" in documento
    assert re.search(r"Protocolo: REC-\d{4}-\d{6}", documento), (
        f"a emissão física deveria carimbar o ID local: {documento[:200]!r}"
    )
    assert "ID local" in documento, (
        "a folha física precisa dizer que o número não é consultável publicamente"
    )
    # Sem documento canônico não há hash — e a folha diz isso em vez de
    # prometer uma lacuna que nunca vai ser preenchida.
    assert "não gerado — emissão física" in documento

    page.wait_for_timeout(900)   # o imprimirDireto chama window.print() em 500ms
    assert page.evaluate("() => window.__impressoes") >= 1, "window.print() não foi chamado"


def test_ac9_segunda_via_imprime_o_documento_em_dia(sem_dialogo_de_impressao, app_demo):
    """A 2ª via continua saindo pelo mesmo botão e pelo mesmo documento."""
    page = sem_dialogo_de_impressao
    _abrir(page, app_demo)
    _receita_completa(page)
    page.locator("#btn-emitir").click()
    expect(page.locator("#painel-emissao")).to_be_visible(timeout=_TIMEOUT_MS)

    antes = page.evaluate("() => window.__impressoes")
    page.get_by_role("button", name="🖨️ Imprimir 2ª Via / Físico").click()
    page.wait_for_timeout(300)
    assert page.evaluate("() => window.__impressoes") == antes + 1

    assert _alvos_batem(page)
    assert "Documento emitido com assinatura digital" in _texto_do_documento(page)
